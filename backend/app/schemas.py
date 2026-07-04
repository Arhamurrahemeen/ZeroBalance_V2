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
    suspects: list[SuspectOut]


class ResolveRequest(BaseModel):
    note: str = Field(min_length=1)
    actor: str = "teller"


class LedgerVerifyOut(BaseModel):
    ok: bool
    entries: int
    head: str
