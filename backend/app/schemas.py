from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from .engine.models import Signature


class HealthResponse(BaseModel):
    status: str
    service: str


class IngestMeta(BaseModel):
    """Teller inputs at EOD: opening float + the single denomination count."""

    opening_float: int = Field(ge=0)
    denomination_count: dict[int, int]


class SuspectOut(BaseModel):
    rank: int
    signature: Signature
    txn_refs: list[str]
    cash_delta: int
    rule_score: int
    evidence: dict[str, int | str]
    anomaly_score: float | None = None
    explanation_ur: str | None = None


class SessionSummary(BaseModel):
    id: int
    branch_code: str
    teller_id: str
    business_date: str
    system_cash: int
    counted_cash: int
    variance: int
    status: str
    age_days: int
    suspect_count: int


class SessionDetail(SessionSummary):
    txn_count: int
    denomination_count: dict[int, int]
    suspects: list[SuspectOut]


class ResolveRequest(BaseModel):
    note: str = Field(min_length=1)
    actor: str = "teller"


class LedgerVerifyOut(BaseModel):
    ok: bool
    entries: int
    head: str


# --- v2: Digital Excess Ledger --------------------------------------------


class ExcessOpenRequest(BaseModel):
    branch_code: str = Field(min_length=1)
    teller_id: str = Field(min_length=1)
    business_date: str = Field(min_length=10, max_length=10)  # ISO date
    entry_kind: Literal["excess", "short"]
    amount: Decimal = Field(gt=0)
    opener: str = Field(min_length=1)
    note: str | None = None


class ExcessCountersignRequest(BaseModel):
    officer: str = Field(min_length=1)


class ExcessCloseRequest(BaseModel):
    officer: str = Field(min_length=1)
    resolution_note: str = Field(min_length=1)


class ExcessCaseOut(BaseModel):
    case_ref: str
    branch_code: str
    teller_id: str
    business_date: str
    entry_kind: Literal["excess", "short"]
    amount: str
    state: Literal["opened", "countersigned", "closed"]
    opener: str
    countersigner: str | None = None
    closer: str | None = None
    reason: str | None = None
    resolution: str | None = None
    opened_at: str
    countersigned_at: str | None = None
    closed_at: str | None = None


class ExcessChainVerifyOut(BaseModel):
    ok: bool
    rows: int
    head: str


# --- v2: Cheque capture ---------------------------------------------------


class ChequeCaptureRequest(BaseModel):
    branch_code: str = Field(min_length=1)
    teller_id: str = Field(min_length=1)
    business_date: str = Field(min_length=10, max_length=10)
    micr: str = Field(min_length=1)
    account_number: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    denomination_out: dict[str, int]


class ChequeOut(BaseModel):
    id: int
    branch_code: str
    teller_id: str
    business_date: str
    micr: str
    account_number: str
    amount: str
    denomination_out: dict[str, int]
    captured_at: str


# --- v2: Pre-post validation (demo-only surface) --------------------------


class PrepostRequest(BaseModel):
    teller_id: str = Field(min_length=1)
    input: dict


class PrepostResult(BaseModel):
    check_name: Literal[
        "denom_sum", "cnic_name_match", "duplicate_check",
        "large_amount_confirm", "sanity",
    ]
    passed: bool
    reason: str | None = None
