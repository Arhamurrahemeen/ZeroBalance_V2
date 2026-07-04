from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import append_ledger, get_db, verify_ledger
from .db_models import EodSessionRow
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


@router.get("/ledger/verify", response_model=LedgerVerifyOut)
def ledger_verify(db: DbDep) -> LedgerVerifyOut:
    ok, entries, head = verify_ledger(db)
    return LedgerVerifyOut(ok=ok, entries=entries, head=head)
