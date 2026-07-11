"""Digital Excess Ledger — v2 flagship service.

Append-only event table. Each excess/short entry is a stream of rows sharing a
`case_ref` UUID, sequenced by `event_seq`:

    opened -> countersigned -> closed

Rules enforced here (not in DB, so they're unit-testable without Postgres):

- Dual sign-off: countersigner MUST differ from opener.
- Close requires a prior countersign.
- No double countersign, no re-close, no out-of-order events.
- `amount` is fixed at open — countersign/close inherit it; the countersigner
  cannot silently mutate the number.

Every state transition is a fresh INSERT. The DB trigger blocks UPDATE/DELETE.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import append_ledger
from .db_models import ExcessLedgerRow

EventType = Literal["opened", "countersigned", "closed"]
EntryKind = Literal["excess", "short"]
State = Literal["opened", "countersigned", "closed"]


# --- Errors ----------------------------------------------------------------


class ExcessLedgerError(ValueError):
    """Base for all Excess Ledger state-machine violations."""


class CaseNotFound(ExcessLedgerError):
    pass


class DualSignoffViolation(ExcessLedgerError):
    """Countersigner is the same actor as the opener."""


class MissingCountersign(ExcessLedgerError):
    """Attempt to close before countersign."""


class DoubleCountersign(ExcessLedgerError):
    """Second countersign on a case that is already countersigned."""


class OutOfOrderEvent(ExcessLedgerError):
    """Any transition that violates the opened -> countersigned -> closed order."""


# --- Hash chain ------------------------------------------------------------


def _canonical_payload(
    *, case_ref: str, event_seq: int, event_type: EventType,
    branch_code: str, teller_id: str, business_date: date,
    entry_kind: EntryKind, amount: Decimal, actor: str, note: str | None,
) -> dict:
    return {
        "case_ref": case_ref, "event_seq": event_seq, "event_type": event_type,
        "branch_code": branch_code, "teller_id": teller_id,
        "business_date": business_date.isoformat(),
        "entry_kind": entry_kind, "amount": f"{amount:.2f}",
        "actor": actor, "note": note or "",
    }


def _hash(prev_hash: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}|{canonical}".encode()).hexdigest()


def _chain_head(db: Session) -> str:
    row = db.execute(
        select(ExcessLedgerRow).order_by(ExcessLedgerRow.id.desc()).limit(1)
    ).scalar_one_or_none()
    return row.entry_hash if row else "GENESIS"


def _case_events(db: Session, case_ref: str) -> list[ExcessLedgerRow]:
    return list(
        db.execute(
            select(ExcessLedgerRow)
            .where(ExcessLedgerRow.case_ref == case_ref)
            .order_by(ExcessLedgerRow.event_seq)
        ).scalars()
    )


def _append_event(
    db: Session, *, case_ref: str, event_seq: int, event_type: EventType,
    branch_code: str, teller_id: str, business_date: date,
    entry_kind: EntryKind, amount: Decimal, actor: str, note: str | None,
) -> ExcessLedgerRow:
    prev = _chain_head(db)
    payload = _canonical_payload(
        case_ref=case_ref, event_seq=event_seq, event_type=event_type,
        branch_code=branch_code, teller_id=teller_id,
        business_date=business_date, entry_kind=entry_kind, amount=amount,
        actor=actor, note=note,
    )
    row = ExcessLedgerRow(
        case_ref=case_ref, event_seq=event_seq, event_type=event_type,
        branch_code=branch_code, teller_id=teller_id, business_date=business_date,
        entry_kind=entry_kind, amount=amount, actor=actor, note=note,
        prev_hash=prev, entry_hash=_hash(prev, payload),
    )
    db.add(row)
    db.flush()
    return row


# --- State machine ---------------------------------------------------------


def open_entry(
    db: Session, *, branch_code: str, teller_id: str, business_date: date,
    entry_kind: EntryKind, amount: Decimal, opener: str,
    note: str | None = None,
) -> ExcessLedgerRow:
    """Teller opens a new excess/short entry. Returns the inserted row."""
    if entry_kind not in ("excess", "short"):
        raise ExcessLedgerError(f"entry_kind must be 'excess' or 'short', got {entry_kind!r}")
    if amount <= 0:
        raise ExcessLedgerError("amount must be positive")
    case_ref = str(uuid4())
    row = _append_event(
        db, case_ref=case_ref, event_seq=1, event_type="opened",
        branch_code=branch_code, teller_id=teller_id, business_date=business_date,
        entry_kind=entry_kind, amount=amount, actor=opener, note=note,
    )
    append_ledger(db, actor=opener, action="EXCESS_OPENED", payload={
        "case_ref": case_ref, "entry_kind": entry_kind,
        "amount": f"{amount:.2f}",
        "branch": branch_code, "teller": teller_id,
    })
    db.commit()
    return row


def countersign(db: Session, *, case_ref: str, officer: str) -> ExcessLedgerRow:
    events = _case_events(db, case_ref)
    if not events:
        raise CaseNotFound(f"case_ref {case_ref} not found")
    types = [e.event_type for e in events]
    if types[-1] == "closed":
        raise OutOfOrderEvent(f"case {case_ref} is already closed")
    if "countersigned" in types:
        raise DoubleCountersign(f"case {case_ref} already countersigned")
    if types != ["opened"]:
        raise OutOfOrderEvent(f"expected sequence ['opened'], got {types}")
    opened = events[0]
    if officer == opened.actor:
        raise DualSignoffViolation(
            f"countersigner ({officer}) must differ from opener ({opened.actor})"
        )
    row = _append_event(
        db, case_ref=case_ref, event_seq=events[-1].event_seq + 1,
        event_type="countersigned",
        branch_code=opened.branch_code, teller_id=opened.teller_id,
        business_date=opened.business_date, entry_kind=opened.entry_kind,
        amount=opened.amount, actor=officer, note=None,
    )
    append_ledger(db, actor=officer, action="EXCESS_COUNTERSIGNED", payload={
        "case_ref": case_ref,
    })
    db.commit()
    return row


def close_entry(
    db: Session, *, case_ref: str, officer: str, resolution_note: str,
) -> ExcessLedgerRow:
    if not resolution_note or not resolution_note.strip():
        raise ExcessLedgerError("resolution_note is required to close an entry")
    events = _case_events(db, case_ref)
    if not events:
        raise CaseNotFound(f"case_ref {case_ref} not found")
    types = [e.event_type for e in events]
    if types[-1] == "closed":
        raise OutOfOrderEvent(f"case {case_ref} is already closed")
    if "countersigned" not in types:
        raise MissingCountersign(f"case {case_ref} cannot close before countersign")
    if types != ["opened", "countersigned"]:
        raise OutOfOrderEvent(f"unexpected event sequence: {types}")
    opened = events[0]
    row = _append_event(
        db, case_ref=case_ref, event_seq=events[-1].event_seq + 1,
        event_type="closed",
        branch_code=opened.branch_code, teller_id=opened.teller_id,
        business_date=opened.business_date, entry_kind=opened.entry_kind,
        amount=opened.amount, actor=officer, note=resolution_note.strip(),
    )
    append_ledger(db, actor=officer, action="EXCESS_CLOSED", payload={
        "case_ref": case_ref, "resolution": resolution_note.strip(),
    })
    db.commit()
    return row


# --- Views + register ------------------------------------------------------


@dataclass(frozen=True)
class CaseView:
    case_ref: str
    branch_code: str
    teller_id: str
    business_date: str  # ISO
    entry_kind: EntryKind
    amount: str  # stringified Decimal for JSON safety
    state: State
    opener: str
    countersigner: str | None
    closer: str | None
    reason: str | None
    resolution: str | None
    opened_at: str
    countersigned_at: str | None
    closed_at: str | None


def _view(events: list[ExcessLedgerRow]) -> CaseView:
    by_type = {e.event_type: e for e in events}
    opened = by_type["opened"]
    countersigned = by_type.get("countersigned")
    closed = by_type.get("closed")
    state: State = "closed" if closed else ("countersigned" if countersigned else "opened")
    return CaseView(
        case_ref=str(opened.case_ref),
        branch_code=opened.branch_code,
        teller_id=opened.teller_id,
        business_date=opened.business_date.isoformat(),
        entry_kind=opened.entry_kind,  # type: ignore[arg-type]
        amount=f"{opened.amount:.2f}",
        state=state,
        opener=opened.actor,
        countersigner=countersigned.actor if countersigned else None,
        closer=closed.actor if closed else None,
        reason=opened.note,
        resolution=closed.note if closed else None,
        opened_at=opened.at.isoformat() if opened.at else "",
        countersigned_at=(
            countersigned.at.isoformat() if countersigned and countersigned.at else None
        ),
        closed_at=closed.at.isoformat() if closed and closed.at else None,
    )


def get_case(db: Session, case_ref: str) -> CaseView:
    events = _case_events(db, case_ref)
    if not events:
        raise CaseNotFound(f"case_ref {case_ref} not found")
    return _view(events)


def list_register(
    db: Session, *, from_date: date, to_date: date,
    branch_code: str | None = None,
) -> list[CaseView]:
    """All cases with any event in [from_date, to_date]. Half-yearly = wide range."""
    q = (
        select(ExcessLedgerRow)
        .where(ExcessLedgerRow.business_date >= from_date)
        .where(ExcessLedgerRow.business_date <= to_date)
        .order_by(ExcessLedgerRow.case_ref, ExcessLedgerRow.event_seq)
    )
    if branch_code:
        q = q.where(ExcessLedgerRow.branch_code == branch_code)
    rows = list(db.execute(q).scalars())
    by_case: dict[str, list[ExcessLedgerRow]] = {}
    for r in rows:
        by_case.setdefault(str(r.case_ref), []).append(r)
    return [_view(events) for events in by_case.values()]


# --- Chain verify ----------------------------------------------------------


def verify_chain(db: Session) -> tuple[bool, int, str]:
    """Walk the global excess_ledger chain in id order. Returns (ok, rows, head)."""
    prev = "GENESIS"
    n = 0
    for row in db.execute(
        select(ExcessLedgerRow).order_by(ExcessLedgerRow.id)
    ).scalars():
        payload = _canonical_payload(
            case_ref=str(row.case_ref), event_seq=row.event_seq,
            event_type=row.event_type,  # type: ignore[arg-type]
            branch_code=row.branch_code, teller_id=row.teller_id,
            business_date=row.business_date,
            entry_kind=row.entry_kind,  # type: ignore[arg-type]
            amount=row.amount, actor=row.actor, note=row.note,
        )
        if row.prev_hash != prev:
            return False, n, prev
        if row.entry_hash != _hash(prev, payload):
            return False, n, prev
        prev = row.entry_hash
        n += 1
    return True, n, prev
