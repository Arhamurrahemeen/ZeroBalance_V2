from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import cash_movement as cash_movement_svc
from . import cheque as cheque_svc
from . import excess_ledger as excess
from . import prepost as prepost_svc
from .db import append_ledger, get_db, verify_ledger
from .db_models import EodSessionRow
from .schemas import (
    CashMovementChainVerifyOut,
    CashMovementOut,
    CashMovementRequest,
    ChequeCaptureRequest,
    ChequeExplainOut,
    ChequeExplainRequest,
    ChequeOut,
    DenomReconciliation,
    EodReconciliationOut,
    ExcessCaseOut,
    ExcessChainVerifyOut,
    ExcessCloseRequest,
    ExcessCountersignRequest,
    ExcessExplainOut,
    ExcessExplainRequest,
    ExcessOpenRequest,
    HealthResponse,
    IngestMeta,
    LedgerVerifyOut,
    PrepostRequest,
    PrepostResult,
    ResolveRequest,
    SessionDetail,
    SessionSummary,
)
from .service import CsvFormatError, ingest_session, to_detail, to_summary

router = APIRouter()
DbDep = Annotated[Session, Depends(get_db)]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="zerobalance-backend")


@router.post("/sessions", response_model=SessionDetail, status_code=201)
async def create_session(file: UploadFile, meta: Annotated[str, Form()],
                         db: DbDep) -> SessionDetail:
    try:
        meta_obj = IngestMeta.model_validate_json(meta)
    except ValidationError as e:
        raise HTTPException(422, f"bad meta: {e.errors()}") from e
    text = (await file.read()).decode("utf-8-sig")
    try:
        row = ingest_session(db, text, meta_obj)
    except CsvFormatError as e:
        raise HTTPException(400, str(e)) from e
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(409, "session already ingested for this teller/date") from e
    return to_detail(db, row)


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(db: DbDep, status: str | None = None) -> list[SessionSummary]:
    q = select(EodSessionRow).order_by(
        EodSessionRow.business_date.desc(), EodSessionRow.id.desc()
    )
    if status is not None:
        q = q.where(EodSessionRow.status == status)
    return [to_summary(db, r) for r in db.execute(q).scalars()]


def _get_session(db: Session, session_id: int) -> EodSessionRow:
    row = db.get(EodSessionRow, session_id)
    if row is None:
        raise HTTPException(404, f"session {session_id} not found")
    return row


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def session_detail(session_id: int, db: DbDep) -> SessionDetail:
    return to_detail(db, _get_session(db, session_id))


@router.get("/sessions/{session_id}/report.pdf")
def session_report_pdf(session_id: int, db: DbDep) -> Response:
    # binary route: returns application/pdf, not a Pydantic model
    from .report import generate_report_pdf

    row = _get_session(db, session_id)
    pdf = generate_report_pdf(db, row)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="zerobalance_recon_{row.id}.pdf"'},
    )


@router.post("/sessions/{session_id}/resolve", response_model=SessionSummary)
def resolve_session(session_id: int, body: ResolveRequest, db: DbDep) -> SessionSummary:
    row = _get_session(db, session_id)
    if row.status in ("resolved", "closed"):
        raise HTTPException(409, f"session already {row.status}")
    row.status = "resolved"
    append_ledger(db, actor=body.actor, action="SESSION_RESOLVED", payload={
        "session_id": row.id, "note": body.note,
    })
    db.commit()
    return to_summary(db, row)


@router.post("/sessions/{session_id}/explain", response_model=SessionDetail)
def explain_session(session_id: int, db: DbDep,
                    lang: Literal["ur", "en"] = "ur", force: bool = False) -> SessionDetail:
    from .config import settings
    from .explain import explain_suspects

    row = _get_session(db, session_id)
    if not settings.groq_api_key or settings.groq_api_key.startswith("your-"):
        raise HTTPException(503, "GROQ_API_KEY not configured")
    try:
        explain_suspects(db, row, lang=lang, force=force)
    except Exception as e:  # upstream/network failure must not corrupt state
        db.rollback()
        raise HTTPException(502, f"explanation service failed: {e}") from e
    return to_detail(db, row)


@router.get("/ledger/verify", response_model=LedgerVerifyOut)
def ledger_verify(db: DbDep) -> LedgerVerifyOut:
    ok, entries, head = verify_ledger(db)
    return LedgerVerifyOut(ok=ok, entries=entries, head=head)


# --- v2: Digital Excess Ledger --------------------------------------------


def _view_to_out(v: excess.CaseView) -> ExcessCaseOut:
    return ExcessCaseOut(
        case_ref=v.case_ref, branch_code=v.branch_code, teller_id=v.teller_id,
        business_date=v.business_date, entry_kind=v.entry_kind, amount=v.amount,
        state=v.state, opener=v.opener, countersigner=v.countersigner,
        closer=v.closer, reason=v.reason, resolution=v.resolution,
        opened_at=v.opened_at, countersigned_at=v.countersigned_at,
        closed_at=v.closed_at,
    )


def _map_excess_error(e: excess.ExcessLedgerError) -> HTTPException:
    if isinstance(e, excess.CaseNotFound):
        return HTTPException(404, str(e))
    return HTTPException(409, str(e))


@router.post("/excess-ledger/open", response_model=ExcessCaseOut, status_code=201)
def excess_open(body: ExcessOpenRequest, db: DbDep) -> ExcessCaseOut:
    try:
        row = excess.open_entry(
            db, branch_code=body.branch_code, teller_id=body.teller_id,
            business_date=date.fromisoformat(body.business_date),
            entry_kind=body.entry_kind, amount=body.amount, opener=body.opener,
            note=body.note,
        )
    except excess.ExcessLedgerError as e:
        db.rollback()
        raise _map_excess_error(e) from e
    return _view_to_out(excess.get_case(db, str(row.case_ref)))


@router.post("/excess-ledger/{case_ref}/countersign", response_model=ExcessCaseOut)
def excess_countersign(
    case_ref: str, body: ExcessCountersignRequest, db: DbDep,
) -> ExcessCaseOut:
    try:
        excess.countersign(db, case_ref=case_ref, officer=body.officer)
    except excess.ExcessLedgerError as e:
        db.rollback()
        raise _map_excess_error(e) from e
    return _view_to_out(excess.get_case(db, case_ref))


@router.post("/excess-ledger/{case_ref}/close", response_model=ExcessCaseOut)
def excess_close(
    case_ref: str, body: ExcessCloseRequest, db: DbDep,
) -> ExcessCaseOut:
    try:
        excess.close_entry(
            db, case_ref=case_ref, officer=body.officer,
            resolution_note=body.resolution_note,
        )
    except excess.ExcessLedgerError as e:
        db.rollback()
        raise _map_excess_error(e) from e
    return _view_to_out(excess.get_case(db, case_ref))


@router.get("/excess-ledger", response_model=list[ExcessCaseOut])
def excess_register(
    db: DbDep, from_date: str, to_date: str, branch: str | None = None,
) -> list[ExcessCaseOut]:
    try:
        f = date.fromisoformat(from_date)
        t = date.fromisoformat(to_date)
    except ValueError as e:
        raise HTTPException(422, f"bad date: {e}") from e
    if f > t:
        raise HTTPException(422, "from_date must be <= to_date")
    views = excess.list_register(db, from_date=f, to_date=t, branch_code=branch)
    return [_view_to_out(v) for v in views]


@router.get("/excess-ledger/verify-chain", response_model=ExcessChainVerifyOut)
def excess_verify_chain(db: DbDep) -> ExcessChainVerifyOut:
    ok, rows, head = excess.verify_chain(db)
    return ExcessChainVerifyOut(ok=ok, rows=rows, head=head)


@router.get("/excess-ledger/report.pdf")
def excess_register_pdf(
    db: DbDep, from_date: str, to_date: str, branch: str | None = None,
) -> Response:
    from .report import generate_excess_register_pdf

    try:
        f = date.fromisoformat(from_date)
        t = date.fromisoformat(to_date)
    except ValueError as e:
        raise HTTPException(422, f"bad date: {e}") from e
    if f > t:
        raise HTTPException(422, "from_date must be <= to_date")
    pdf = generate_excess_register_pdf(db, from_date=f, to_date=t, branch=branch)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition":
                 f'inline; filename="excess_register_{from_date}_{to_date}.pdf"'},
    )


@router.post("/excess-ledger/{case_ref}/explain", response_model=ExcessExplainOut)
def excess_explain(case_ref: str, body: ExcessExplainRequest, db: DbDep) -> ExcessExplainOut:
    from .config import settings
    from .explain import explain_excess_case

    if not settings.groq_api_key or settings.groq_api_key.startswith("your-"):
        raise HTTPException(503, "GROQ_API_KEY not configured")
    try:
        text = explain_excess_case(db, case_ref, lang=body.lang)
    except excess.CaseNotFound as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:  # upstream/network failure must not corrupt state
        db.rollback()
        raise HTTPException(502, f"explanation service failed: {e}") from e
    return ExcessExplainOut(case_ref=case_ref, lang=body.lang, explanation=text)


# --- v2: Cheque capture ---------------------------------------------------


def _cheque_view_to_out(v: cheque_svc.ChequeView) -> ChequeOut:
    return ChequeOut(
        id=v.id, branch_code=v.branch_code, teller_id=v.teller_id,
        business_date=v.business_date, micr=v.micr,
        account_number=v.account_number, amount=v.amount,
        denomination_out=v.denomination_out, captured_at=v.captured_at,
    )


@router.post("/cheque", response_model=ChequeOut, status_code=201)
def cheque_capture(body: ChequeCaptureRequest, db: DbDep) -> ChequeOut:
    try:
        row = cheque_svc.capture(
            db, branch_code=body.branch_code, teller_id=body.teller_id,
            business_date=date.fromisoformat(body.business_date),
            micr=body.micr, account_number=body.account_number,
            amount=body.amount, denomination_out=body.denomination_out,
        )
    except cheque_svc.ChequeError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    return _cheque_view_to_out(cheque_svc._view(row))


@router.get("/cheque", response_model=list[ChequeOut])
def cheque_list(
    db: DbDep, from_date: str, to_date: str, branch: str | None = None,
) -> list[ChequeOut]:
    try:
        f = date.fromisoformat(from_date)
        t = date.fromisoformat(to_date)
    except ValueError as e:
        raise HTTPException(422, f"bad date: {e}") from e
    if f > t:
        raise HTTPException(422, "from_date must be <= to_date")
    return [_cheque_view_to_out(v)
            for v in cheque_svc.list_captures(db, from_date=f, to_date=t, branch_code=branch)]


@router.post("/cheque/explain", response_model=ChequeExplainOut)
def cheque_explain(body: ChequeExplainRequest, db: DbDep) -> ChequeExplainOut:
    from .config import settings
    from .explain import explain_cheque_variance

    if not settings.groq_api_key or settings.groq_api_key.startswith("your-"):
        raise HTTPException(503, "GROQ_API_KEY not configured")
    try:
        result = explain_cheque_variance(
            db, branch_code=body.branch_code, teller_id=body.teller_id,
            business_date=date.fromisoformat(body.business_date),
            micr=body.micr, account_number=body.account_number,
            amount=body.amount, denomination_out=body.denomination_out,
            lang=body.lang,
        )
    except cheque_svc.NoVarianceError as e:
        raise HTTPException(409, str(e)) from e
    except cheque_svc.ChequeError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # upstream/network failure must not corrupt state
        db.rollback()
        raise HTTPException(502, f"explanation service failed: {e}") from e
    return ChequeExplainOut(
        lang=body.lang, explanation=result.text, mismatch_types=result.mismatch_types,
    )


# --- v2.1: Cash Movement Ledger --------------------------------------------


def _movement_view_to_out(v: cash_movement_svc.MovementView) -> CashMovementOut:
    return CashMovementOut(
        id=v.id, event_type=v.event_type, teller_id=v.teller_id,
        counterparty_id=v.counterparty_id, om_id=v.om_id, session_id=v.session_id,
        event_time=v.event_time, total_amount=v.total_amount,
        denominations=v.denominations,
    )


@router.post("/cash-movement", response_model=CashMovementOut, status_code=201)
def cash_movement_record(body: CashMovementRequest, db: DbDep) -> CashMovementOut:
    try:
        row = cash_movement_svc.record_event(
            db, event_type=body.event_type, teller_id=body.teller_id,
            counterparty_id=body.counterparty_id, om_id=body.om_id,
            session_id=body.session_id, denominations=body.denominations,
            signoff_teller=body.signoff_teller,
            signoff_counterparty=body.signoff_counterparty,
            signoff_om=body.signoff_om,
        )
    except cash_movement_svc.CashMovementError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    return _movement_view_to_out(cash_movement_svc.to_view(db, row))


@router.get("/cash-movement", response_model=list[CashMovementOut])
def cash_movement_list(
    db: DbDep, teller_id: str | None = None, session_id: str | None = None,
    from_date: str | None = None, to_date: str | None = None,
) -> list[CashMovementOut]:
    try:
        f = date.fromisoformat(from_date) if from_date else None
        t = date.fromisoformat(to_date) if to_date else None
    except ValueError as e:
        raise HTTPException(422, f"bad date: {e}") from e
    if f and t and f > t:
        raise HTTPException(422, "from_date must be <= to_date")
    views = cash_movement_svc.list_events(
        db, teller_id=teller_id, session_id=session_id, from_date=f, to_date=t,
    )
    return [_movement_view_to_out(v) for v in views]


@router.get("/cash-movement/verify-chain", response_model=CashMovementChainVerifyOut)
def cash_movement_verify_chain(db: DbDep) -> CashMovementChainVerifyOut:
    ok, rows, head = cash_movement_svc.verify_chain(db)
    return CashMovementChainVerifyOut(ok=ok, rows=rows, head=head)


@router.get("/eod/reconciliation", response_model=EodReconciliationOut)
def eod_reconciliation(db: DbDep, teller_id: str, business_date: str) -> EodReconciliationOut:
    from . import reconcile

    try:
        bd = date.fromisoformat(business_date)
    except ValueError as e:
        raise HTTPException(422, f"bad date: {e}") from e
    per_denom = reconcile.denomination_view(db, teller_id=teller_id, business_date=bd)
    return EodReconciliationOut(
        teller_id=teller_id, business_date=business_date,
        per_denom=[DenomReconciliation(**d) for d in per_denom],
    )


# --- v2: Pre-post validation (DEMO-ONLY SURFACE) --------------------------
# Not wired into any real CBS write path. Endpoints exist for the UI screen
# to fire them on typed input. See CLAUDE.md hard-constraint #6.


def _run_prepost(
    db: Session, check_name: prepost_svc.CheckName, body: PrepostRequest,
) -> PrepostResult:
    try:
        passed, reason = prepost_svc.run_check(
            db, teller_id=body.teller_id, check_name=check_name, inp=body.input,
        )
    except prepost_svc.PrepostError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    return PrepostResult(check_name=check_name, passed=passed, reason=reason)


@router.post("/prepost/denom-sum", response_model=PrepostResult)
def prepost_denom_sum(body: PrepostRequest, db: DbDep) -> PrepostResult:
    return _run_prepost(db, "denom_sum", body)


@router.post("/prepost/cnic-name-match", response_model=PrepostResult)
def prepost_cnic_name_match(body: PrepostRequest, db: DbDep) -> PrepostResult:
    return _run_prepost(db, "cnic_name_match", body)


@router.post("/prepost/duplicate-check", response_model=PrepostResult)
def prepost_duplicate_check(body: PrepostRequest, db: DbDep) -> PrepostResult:
    return _run_prepost(db, "duplicate_check", body)


@router.post("/prepost/large-amount-confirm", response_model=PrepostResult)
def prepost_large_amount_confirm(body: PrepostRequest, db: DbDep) -> PrepostResult:
    return _run_prepost(db, "large_amount_confirm", body)


@router.post("/prepost/sanity", response_model=PrepostResult)
def prepost_sanity(body: PrepostRequest, db: DbDep) -> PrepostResult:
    return _run_prepost(db, "sanity", body)
