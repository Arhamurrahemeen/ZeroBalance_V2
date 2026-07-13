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


class ExcessExplainRequest(BaseModel):
    lang: Literal["ur", "en"] = "ur"


class ExcessExplainOut(BaseModel):
    case_ref: str
    lang: Literal["ur", "en"]
    explanation: str


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


class ChequeExplainRequest(BaseModel):
    branch_code: str = Field(min_length=1)
    teller_id: str = Field(min_length=1)
    business_date: str = Field(min_length=10, max_length=10)
    micr: str = Field(min_length=1)
    account_number: str = Field(min_length=1)
    amount: Decimal = Field(gt=0)
    denomination_out: dict[str, int]
    lang: Literal["ur", "en"] = "ur"


class ChequeExplainOut(BaseModel):
    lang: Literal["ur", "en"]
    explanation: str
    mismatch_types: list[str]


# --- v2.1: Cash Movement Ledger --------------------------------------------


class CashMovementRequest(BaseModel):
    event_type: Literal["day_start", "reissue", "handover", "day_end"]
    teller_id: str = Field(min_length=1)
    counterparty_id: str | None = None
    om_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    denominations: dict[str, int]
    signoff_teller: str | None = None
    signoff_counterparty: str | None = None
    signoff_om: str | None = None


class CashMovementOut(BaseModel):
    id: int
    event_type: Literal["day_start", "reissue", "handover", "day_end"]
    teller_id: str
    counterparty_id: str | None = None
    om_id: str
    session_id: str
    event_time: str
    total_amount: str
    denominations: dict[str, int]


class CashMovementChainVerifyOut(BaseModel):
    ok: bool
    rows: int
    head: str


class DenomReconciliation(BaseModel):
    denomination: int
    opening_plus_reissues: int
    physical: int
    variance: int


class EodReconciliationOut(BaseModel):
    teller_id: str
    business_date: str
    per_denom: list[DenomReconciliation]


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
