"""Cheque capture — sidecar artifact.

Not in the CBS write path. Every capture:

1. Validates denomination-out sum matches amount.
2. Extracts the account block from the MICR line and compares it to the
   typed account_number. Mismatch = 422 (invalid_micr).
3. Inserts a `cheque_transactions` row (plain INSERT — not append-only).
4. Writes a `CHEQUE_CAPTURED` action to `audit_ledger` (hash-chained).

MICR format assumed:  `⑈<routing>⑈ ⑆<account>⑆`
The account block is anything between the last pair of `⑆` characters.
Real E-13B decoding is post-hackathon.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import append_ledger
from .db_models import ChequeTransactionRow


# --- Errors ----------------------------------------------------------------


class ChequeError(ValueError):
    """Base for cheque validation problems."""


class DenomSumMismatch(ChequeError):
    pass


class MicrAccountMismatch(ChequeError):
    pass


# --- MICR ------------------------------------------------------------------

# The last block wrapped in ⑆ ... ⑆ is the account number.
_MICR_ACCOUNT_RX = re.compile(r"⑆([^⑆]+)⑆")


def extract_micr_account(micr: str) -> str | None:
    """Return the account block from the MICR line, or None if not parseable."""
    matches = _MICR_ACCOUNT_RX.findall(micr or "")
    if not matches:
        return None
    return matches[-1].strip()


# --- Capture ---------------------------------------------------------------


def _sum_denominations(denomination_out: dict[str, int]) -> Decimal:
    total = 0
    for k, v in denomination_out.items():
        if not k.isdigit():
            raise ChequeError(f"bad denomination key {k!r} (must be digit string)")
        if v < 0:
            raise ChequeError(f"negative note count for {k}")
        total += int(k) * v
    return Decimal(total)


def capture(
    db: Session, *, branch_code: str, teller_id: str, business_date: date,
    micr: str, account_number: str, amount: Decimal,
    denomination_out: dict[str, int],
) -> ChequeTransactionRow:
    if amount <= 0:
        raise ChequeError("amount must be positive")
    total = _sum_denominations(denomination_out)
    if total != amount:
        raise DenomSumMismatch(
            f"denomination_out sum {total} != amount {amount}"
        )
    micr_account = extract_micr_account(micr)
    if not micr_account or micr_account != account_number:
        raise MicrAccountMismatch(
            f"MICR account {micr_account!r} does not match typed account_number "
            f"{account_number!r}"
        )
    row = ChequeTransactionRow(
        branch_code=branch_code, teller_id=teller_id,
        business_date=business_date, micr=micr,
        account_number=account_number, amount=amount,
        denomination_out=denomination_out,
    )
    db.add(row)
    db.flush()
    append_ledger(db, actor=teller_id, action="CHEQUE_CAPTURED", payload={
        "cheque_id": row.id, "branch": branch_code, "teller": teller_id,
        "account": account_number, "amount": f"{amount:.2f}",
        "business_date": business_date.isoformat(),
    })
    db.commit()
    return row


# --- Register --------------------------------------------------------------


@dataclass(frozen=True)
class ChequeView:
    id: int
    branch_code: str
    teller_id: str
    business_date: str
    micr: str
    account_number: str
    amount: str
    denomination_out: dict[str, int]
    captured_at: str


def _view(row: ChequeTransactionRow) -> ChequeView:
    return ChequeView(
        id=row.id, branch_code=row.branch_code, teller_id=row.teller_id,
        business_date=row.business_date.isoformat(),
        micr=row.micr, account_number=row.account_number,
        amount=f"{row.amount:.2f}",
        denomination_out={str(k): int(v) for k, v in row.denomination_out.items()},
        captured_at=row.captured_at.isoformat() if row.captured_at else "",
    )


def list_captures(
    db: Session, *, from_date: date, to_date: date,
    branch_code: str | None = None,
) -> list[ChequeView]:
    q = (
        select(ChequeTransactionRow)
        .where(ChequeTransactionRow.business_date >= from_date)
        .where(ChequeTransactionRow.business_date <= to_date)
        .order_by(ChequeTransactionRow.business_date, ChequeTransactionRow.id)
    )
    if branch_code:
        q = q.where(ChequeTransactionRow.branch_code == branch_code)
    return [_view(r) for r in db.execute(q).scalars()]
