"""Cash Movement Ledger — v2.1 audit-trail spine (Phase 16).

Unlike the Digital Excess Ledger, this is NOT a state machine: one POST
inserts exactly one event row + its denomination rows, in a single
transaction, hash-chained into a single global chain (same pattern as
excess_ledger / audit_ledger — prev_hash / row_hash here).

Sign-off shape depends on event_type:
- day_start, reissue, day_end: signoff_teller + signoff_om required;
  signoff_counterparty must be absent.
- handover: signoff_teller + signoff_counterparty + signoff_om all required
  (the only three-signer event) — counterparty_id must also be set.

total_amount is never trusted from the caller — it is always the sum of the
posted denominations. Denomination keys must be in the allowed banknote set;
per-transaction denomination capture stays forbidden (this ledger only ever
records one denomination count per movement event).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import append_ledger
from .db_models import CashMovementDenominationRow, CashMovementLedgerRow

EventType = Literal["day_start", "reissue", "handover", "day_end"]

VALID_DENOMINATIONS = (5000, 1000, 500, 100, 50, 20, 10)


class CashMovementError(ValueError):
    """Base for all Cash Movement Ledger validation problems."""


class BadDenomination(CashMovementError):
    pass


class SignoffError(CashMovementError):
    """Sign-off shape doesn't match what event_type requires."""


def _requires_counterparty(event_type: EventType) -> bool:
    return event_type == "handover"


def _validate_denominations(denominations: dict[str, int]) -> dict[int, int]:
    if not denominations:
        raise BadDenomination("denominations must be non-empty")
    out: dict[int, int] = {}
    for k, v in denominations.items():
        if not str(k).isdigit() or int(k) not in VALID_DENOMINATIONS:
            raise BadDenomination(
                f"denomination {k!r} not in allowed banknote set {VALID_DENOMINATIONS}"
            )
        if v < 0:
            raise BadDenomination(f"negative note count for {k}")
        out[int(k)] = v
    return out


def _validate_signoffs(
    event_type: EventType, *, counterparty_id: str | None,
    signoff_teller: str | None, signoff_counterparty: str | None,
    signoff_om: str | None,
) -> None:
    if not signoff_teller:
        raise SignoffError("signoff_teller is required")
    if not signoff_om:
        raise SignoffError("signoff_om is required")
    if _requires_counterparty(event_type):
        if not counterparty_id:
            raise SignoffError("counterparty_id is required for handover")
        if not signoff_counterparty:
            raise SignoffError("signoff_counterparty is required for handover")
    else:
        if signoff_counterparty:
            raise SignoffError(
                f"signoff_counterparty is not expected for event_type={event_type!r}"
            )


# --- Hash chain --------------------------------------------------------------


def _canonical_payload(
    *, event_type: EventType, teller_id: str, counterparty_id: str | None,
    om_id: str, session_id: str, total_amount: Decimal,
    denominations: dict[int, int],
) -> dict:
    return {
        "event_type": event_type, "teller_id": teller_id,
        "counterparty_id": counterparty_id or "", "om_id": om_id,
        "session_id": session_id, "total_amount": f"{total_amount:.2f}",
        "denominations": {str(k): v for k, v in sorted(denominations.items())},
    }


def _hash(prev_hash: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev_hash}|{canonical}".encode()).hexdigest()


def _chain_head(db: Session) -> str:
    row = db.execute(
        select(CashMovementLedgerRow).order_by(CashMovementLedgerRow.id.desc()).limit(1)
    ).scalar_one_or_none()
    return row.row_hash if row else "GENESIS"


# --- Record --------------------------------------------------------------


def record_event(
    db: Session, *, event_type: EventType, teller_id: str, om_id: str,
    session_id: str, denominations: dict[str, int],
    signoff_teller: str | None, signoff_om: str | None,
    counterparty_id: str | None = None, signoff_counterparty: str | None = None,
) -> CashMovementLedgerRow:
    _validate_signoffs(
        event_type, counterparty_id=counterparty_id,
        signoff_teller=signoff_teller, signoff_counterparty=signoff_counterparty,
        signoff_om=signoff_om,
    )
    denoms = _validate_denominations(denominations)
    total_amount = Decimal(sum(k * v for k, v in denoms.items()))

    prev = _chain_head(db)
    payload = _canonical_payload(
        event_type=event_type, teller_id=teller_id, counterparty_id=counterparty_id,
        om_id=om_id, session_id=session_id, total_amount=total_amount,
        denominations=denoms,
    )
    row = CashMovementLedgerRow(
        event_type=event_type, teller_id=teller_id, counterparty_id=counterparty_id,
        om_id=om_id, session_id=session_id, total_amount=total_amount,
        signoff_teller=signoff_teller, signoff_counterparty=signoff_counterparty,
        signoff_om=signoff_om, prev_hash=prev, row_hash=_hash(prev, payload),
    )
    db.add(row)
    db.flush()

    for denom, count in sorted(denoms.items(), reverse=True):
        db.add(CashMovementDenominationRow(
            movement_id=row.id, denomination=denom, count=count,
        ))

    append_ledger(db, actor=teller_id, action="CASH_MOVEMENT_RECORDED", payload={
        "movement_id": row.id, "event_type": event_type, "teller_id": teller_id,
        "session_id": session_id, "total_amount": f"{total_amount:.2f}",
    })
    db.commit()
    return row


# --- Views -----------------------------------------------------------------


@dataclass(frozen=True)
class MovementView:
    id: int
    event_type: EventType
    teller_id: str
    counterparty_id: str | None
    om_id: str
    session_id: str
    event_time: str
    total_amount: str
    denominations: dict[str, int]


def _denominations_for(db: Session, movement_id: int) -> dict[str, int]:
    rows = db.execute(
        select(CashMovementDenominationRow)
        .where(CashMovementDenominationRow.movement_id == movement_id)
        .order_by(CashMovementDenominationRow.denomination.desc())
    ).scalars()
    return {str(r.denomination): r.count for r in rows}


def to_view(db: Session, row: CashMovementLedgerRow) -> MovementView:
    return MovementView(
        id=row.id, event_type=row.event_type,  # type: ignore[arg-type]
        teller_id=row.teller_id, counterparty_id=row.counterparty_id,
        om_id=row.om_id, session_id=row.session_id,
        event_time=row.event_time.isoformat() if row.event_time else "",
        total_amount=f"{row.total_amount:.2f}",
        denominations=_denominations_for(db, row.id),
    )


def list_events(
    db: Session, *, teller_id: str | None = None, session_id: str | None = None,
    from_date: date | None = None, to_date: date | None = None,
) -> list[MovementView]:
    q = select(CashMovementLedgerRow).order_by(CashMovementLedgerRow.id)
    if teller_id:
        q = q.where(CashMovementLedgerRow.teller_id == teller_id)
    if session_id:
        q = q.where(CashMovementLedgerRow.session_id == session_id)
    if from_date:
        q = q.where(
            CashMovementLedgerRow.event_time
            >= datetime.combine(from_date, datetime.min.time())
        )
    if to_date:
        q = q.where(
            CashMovementLedgerRow.event_time
            < datetime.combine(to_date, datetime.min.time()) + timedelta(days=1)
        )
    return [to_view(db, r) for r in db.execute(q).scalars()]


# --- Chain verify ------------------------------------------------------------


def verify_chain(db: Session) -> tuple[bool, int, str]:
    """Walk the global cash_movement_ledger chain in id order."""
    prev = "GENESIS"
    n = 0
    for row in db.execute(
        select(CashMovementLedgerRow).order_by(CashMovementLedgerRow.id)
    ).scalars():
        denoms = {
            r.denomination: r.count
            for r in db.execute(
                select(CashMovementDenominationRow)
                .where(CashMovementDenominationRow.movement_id == row.id)
            ).scalars()
        }
        payload = _canonical_payload(
            event_type=row.event_type,  # type: ignore[arg-type]
            teller_id=row.teller_id, counterparty_id=row.counterparty_id,
            om_id=row.om_id, session_id=row.session_id,
            total_amount=row.total_amount, denominations=denoms,
        )
        if row.prev_hash != prev:
            return False, n, prev
        if row.row_hash != _hash(prev, payload):
            return False, n, prev
        prev = row.row_hash
        n += 1
    return True, n, prev
