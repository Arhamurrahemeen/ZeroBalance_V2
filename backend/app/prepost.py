"""Pre-post validation — DEMO-ONLY SURFACE.

These endpoints exist so the UI can show the 5 checks firing live on typed
input. They are NOT wired into any real CBS write path. In production this
would be an intercept in front of the teller's CBS submission; in this
hackathon build it is not, and CLAUDE.md forbids adding that wiring.

Every check returns `(passed: bool, reason: str | None)` and writes exactly one
`validation_log` row. Input is a plain dict — check-specific keys are
documented on each function.

Rules mirror `ground_truth_v2.PrepostScenario` case-for-case.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from .db_models import ValidationLogRow

CheckName = Literal[
    "denom_sum", "cnic_name_match", "duplicate_check",
    "large_amount_confirm", "sanity",
]

_VALID_TXN_TYPES = {"cash_in", "cash_out", "reversal"}
_VALID_ACCOUNT_TYPES = {"current", "savings", "checking"}


class PrepostError(ValueError):
    """Malformed input for a check (422)."""


def _hash_input(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


# --- Individual checks -----------------------------------------------------


def check_denom_sum(inp: dict) -> tuple[bool, str | None]:
    """Input: {amount: int, denominations: {"5000": int, ...}}."""
    if "amount" not in inp or "denominations" not in inp:
        raise PrepostError("denom_sum requires keys 'amount' and 'denominations'")
    amount = int(inp["amount"])
    total = 0
    for k, v in inp["denominations"].items():
        if not str(k).isdigit():
            raise PrepostError(f"denomination key {k!r} must be a digit string")
        total += int(k) * int(v)
    if total == amount:
        return True, None
    return False, f"denomination sum {total} != amount {amount}"


def check_cnic_name_match(inp: dict) -> tuple[bool, str | None]:
    """Input: {cnic: str, account_holder: str, typed_name: str}."""
    for k in ("cnic", "account_holder", "typed_name"):
        if k not in inp or not str(inp[k]).strip():
            raise PrepostError(f"cnic_name_match requires non-empty {k!r}")
    score = fuzz.token_set_ratio(str(inp["account_holder"]), str(inp["typed_name"]))
    if score >= 80:
        return True, None
    return False, (
        f"typed_name does not match account_holder (fuzzy score below threshold)"
    )


def check_duplicate(inp: dict) -> tuple[bool, str | None]:
    """Input: {cbs_ref: str, recent_refs: list[str]}."""
    if "cbs_ref" not in inp or "recent_refs" not in inp:
        raise PrepostError(
            "duplicate_check requires keys 'cbs_ref' and 'recent_refs'"
        )
    if inp["cbs_ref"] in list(inp["recent_refs"]):
        return False, "cbs_ref already posted in recent window"
    return True, None


def check_large_amount_confirm(inp: dict) -> tuple[bool, str | None]:
    """Input: {amount: number, threshold: number, confirmed: bool}."""
    for k in ("amount", "threshold", "confirmed"):
        if k not in inp:
            raise PrepostError(f"large_amount_confirm requires key {k!r}")
    if float(inp["amount"]) > float(inp["threshold"]) and not bool(inp["confirmed"]):
        return False, "amount above threshold requires explicit confirmation"
    return True, None


def check_sanity(inp: dict) -> tuple[bool, str | None]:
    """Input: {amount: number, account_type: str, txn_type: str}."""
    for k in ("amount", "account_type", "txn_type"):
        if k not in inp:
            raise PrepostError(f"sanity requires key {k!r}")
    if float(inp["amount"]) <= 0:
        return False, "amount must be positive"
    if str(inp["txn_type"]) not in _VALID_TXN_TYPES:
        return False, f"txn_type must be one of {sorted(_VALID_TXN_TYPES)}"
    if str(inp["account_type"]) not in _VALID_ACCOUNT_TYPES:
        return False, f"account_type must be one of {sorted(_VALID_ACCOUNT_TYPES)}"
    return True, None


_CHECKS = {
    "denom_sum": check_denom_sum,
    "cnic_name_match": check_cnic_name_match,
    "duplicate_check": check_duplicate,
    "large_amount_confirm": check_large_amount_confirm,
    "sanity": check_sanity,
}


# --- Dispatch + logging ---------------------------------------------------


def run_check(
    db: Session, *, teller_id: str, check_name: CheckName, inp: dict,
) -> tuple[bool, str | None]:
    """Run the named check on `inp`, write a `validation_log` row, return result."""
    if check_name not in _CHECKS:
        raise PrepostError(f"unknown check_name {check_name!r}")
    passed, reason = _CHECKS[check_name](inp)
    db.add(ValidationLogRow(
        teller_id=teller_id, check_name=check_name,
        input_hash=_hash_input(inp), passed=passed, failed_reason=reason,
    ))
    db.commit()
    return passed, reason
