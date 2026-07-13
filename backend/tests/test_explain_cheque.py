"""Phase 13 tests — Groq Urdu explanation for cheque capture variances.

Same design goal as test_explain_excess.py ("cheque variance" is the other
half of Phase 13's Groq extension) — driven by ground_truth_v2.ChequeScenario
so the mismatch data isn't hand-written here either.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ground_truth_v2 import ChequeScenario, build_suite_v2
from sqlalchemy import select
from sqlalchemy import text as sqltext
from sqlalchemy.orm import Session as OrmSession
from test_explain import FakeClient  # reuse fake Groq client

from app import explain as explain_mod
from app.db import get_engine
from app.db_models import AuditLedgerRow
from app.main import app

TRUNCATE_TABLES = (
    "validation_log, cheque_transactions, excess_ledger, "
    "cash_movement_denominations, cash_movement_ledger, audit_ledger, suspects, denomination_counts, "
    "transactions, recon_reports, eod_sessions"
)


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    with get_engine().connect() as conn:
        conn.execute(sqltext(f"TRUNCATE {TRUNCATE_TABLES} RESTART IDENTITY CASCADE"))
        conn.commit()
    fake = FakeClient()
    monkeypatch.setattr(explain_mod, "_client_factory", lambda: fake)
    monkeypatch.setattr("app.config.settings.groq_api_key", "gsk_test")
    tc = TestClient(app)
    tc.fake = fake  # type: ignore[attr-defined]
    return tc


def _explain_body(s: ChequeScenario) -> dict:
    return {
        "branch_code": s.branch_code, "teller_id": s.teller_id,
        "business_date": s.business_date, "micr": s.micr,
        "account_number": s.account_number, "amount": str(s.amount),
        "denomination_out": s.denomination_out,
    }


def test_explains_micr_mismatch(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().cheque if s.expected_outcome == "invalid_micr")
    r = client.post("/api/v1/cheque/explain", json=_explain_body(s))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mismatch_types"] == ["micr_account"]
    assert body["explanation"] == "یہ لین دین دو بار درج ہوا ہے۔"


def test_explains_denom_sum_mismatch(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().cheque if s.expected_outcome == "invalid_denom_sum"
    )
    r = client.post("/api/v1/cheque/explain", json=_explain_body(s))
    assert r.status_code == 200, r.text
    assert r.json()["mismatch_types"] == ["denom_sum"]


def test_valid_cheque_has_nothing_to_explain(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().cheque if s.expected_outcome == "valid")
    r = client.post("/api/v1/cheque/explain", json=_explain_body(s))
    assert r.status_code == 409


def test_explanation_masks_account_and_micr(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().cheque if s.expected_outcome == "invalid_micr")
    r = client.post("/api/v1/cheque/explain", json=_explain_body(s))
    assert r.status_code == 200, r.text

    prompt = client.fake.completions.calls[-1]["messages"][1]["content"]  # type: ignore[attr-defined]
    assert s.account_number not in prompt
    micr_account = s.micr.split("⑆")[1]
    assert micr_account not in prompt
    assert "****" in prompt


def test_explanation_writes_exactly_one_audit_row(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().cheque if s.expected_outcome == "invalid_denom_sum"
    )

    def _count() -> int:
        with OrmSession(get_engine()) as db:
            return len(db.execute(
                select(AuditLedgerRow).where(AuditLedgerRow.action == "CHEQUE_EXPLAINED")
            ).scalars().all())

    before = _count()
    client.post("/api/v1/cheque/explain", json=_explain_body(s))
    assert _count() == before + 1


def test_explain_without_key_is_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = next(s for s in build_suite_v2().cheque if s.expected_outcome == "invalid_micr")
    monkeypatch.setattr("app.config.settings.groq_api_key", "your-groq-api-key-here")
    r = client.post("/api/v1/cheque/explain", json=_explain_body(s))
    assert r.status_code == 503
