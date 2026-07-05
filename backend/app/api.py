from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import append_ledger, get_db, verify_ledger
from .db_models import EodSessionRow
from .rahbar import QueryPair, RahbarAnswer
from .schemas import (
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


class RahbarAskRequest(BaseModel):
    question: str
    lang: Literal["ur", "en"] = "ur"


@router.post("/rahbar/ask", response_model=RahbarAnswer)
def rahbar_ask(body: RahbarAskRequest) -> RahbarAnswer:
    from .config import settings
    from .rahbar import ask

    if not settings.groq_api_key or settings.groq_api_key.startswith("your-"):
        raise HTTPException(503, "GROQ_API_KEY not configured")
    if not body.question.strip():
        raise HTTPException(422, "question must not be empty")
    try:
        return ask(body.question, lang=body.lang)
    except Exception as e:
        raise HTTPException(502, f"rahbar failed: {e}") from e


@router.get("/rahbar/queries", response_model=list[QueryPair])
def rahbar_queries() -> list[QueryPair]:
    from .rahbar import sample_query_pairs

    return sample_query_pairs()
