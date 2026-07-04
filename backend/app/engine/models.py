from typing import Literal

from pydantic import BaseModel, Field

TxnType = Literal["cash_in", "cash_out", "reversal"]

Signature = Literal[
    "digit_transposition",
    "duplicate_posting",
    "missed_reversal",
    "denomination_shortfall",
    "cash_inout_miskey",
    "wrong_adjacent_account",
]


class TxnInput(BaseModel):
    """One posted CBS transaction (from the PIBAS CSV export)."""

    ref: str
    account: str
    txn_type: TxnType
    amount: int = Field(gt=0)
    time: str = ""
    narration: str = ""
    reverses: str | None = None


class SessionInput(BaseModel):
    """Everything the engine may see. Deliberately no truth-side fields."""

    branch: str = ""
    teller: str = ""
    business_date: str = ""
    opening_float: int
    counted_cash: int
    denomination_count: dict[int, int] = Field(default_factory=dict)
    txns: list[TxnInput]


class Suspect(BaseModel):
    """One ranked engine pick. rule_score is deterministic rule specificity —
    anomaly_score is a display-only secondary signal and never affects rank."""

    rank: int = Field(ge=1, le=5)
    signature: Signature
    txn_refs: tuple[str, ...]
    cash_delta: int
    rule_score: int
    evidence: dict[str, int | str]
    anomaly_score: float | None = None
