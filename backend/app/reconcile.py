"""EOD denomination-view reconciliation (Phase 16).

Deliberately narrower than the sketch in v2_plan.md's Phase 16 section, which
listed per-denomination `deposits_in` / `withdrawals_out` columns. That data
does not exist: CBS transactions carry no denomination breakdown (per-
transaction denomination capture is permanently forbidden — CLAUDE.md hard
constraint #3), so there is nothing to compute those columns from. Building
them would mean inventing numbers, which the anti-delusion guardrails forbid.

What IS real and computable: the denomination counts declared at `day_start`
+ `reissue` (what was put in) versus the denomination counts declared at
`day_end` (what was physically counted at close). This is a reference view
for the teller/auditor — it does not replace the aggregate variance +
ranked-suspects engine in `engine/matching.py`, which remains the sole
authority on *why* a variance happened.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db_models import CashMovementDenominationRow, CashMovementLedgerRow

OPENING_EVENT_TYPES = ("day_start", "reissue")


def denomination_view(
    db: Session, *, teller_id: str, business_date: date,
) -> list[dict]:
    lo = datetime.combine(business_date, datetime.min.time())
    hi = lo + timedelta(days=1)

    rows = db.execute(
        select(CashMovementLedgerRow, CashMovementDenominationRow)
        .join(
            CashMovementDenominationRow,
            CashMovementDenominationRow.movement_id == CashMovementLedgerRow.id,
        )
        .where(CashMovementLedgerRow.teller_id == teller_id)
        .where(CashMovementLedgerRow.event_time >= lo)
        .where(CashMovementLedgerRow.event_time < hi)
    ).all()

    opening: dict[int, int] = defaultdict(int)
    physical: dict[int, int] = defaultdict(int)
    for ledger, denom in rows:
        if ledger.event_type in OPENING_EVENT_TYPES:
            opening[denom.denomination] += denom.count
        elif ledger.event_type == "day_end":
            physical[denom.denomination] += denom.count

    denominations = sorted(set(opening) | set(physical), reverse=True)
    return [
        {
            "denomination": d,
            "opening_plus_reissues": opening.get(d, 0),
            "physical": physical.get(d, 0),
            "variance": physical.get(d, 0) - opening.get(d, 0),
        }
        for d in denominations
    ]
