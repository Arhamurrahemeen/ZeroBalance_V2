from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from datetime import date

from .db import append_ledger, get_db, verify_ledger
from .db_models import EodSessionRow
from . import excess_ledger as excess
from .schemas import (
    ExcessCaseOut,
    ExcessChainVerifyOut,
    ExcessCloseRequest,
    ExcessCountersignRequest,
    ExcessOpenRequest,
    HealthResponse,
    IngestMeta,
    LedgerVerifyOut,
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
