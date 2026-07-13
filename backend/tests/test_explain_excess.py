"""Phase 13 tests — Groq Urdu explanation for Digital Excess Ledger openings.

Reuses the fake Groq client from test_explain.py (EOD suspects explain) so
"never touches Groq for real" is enforced the same way everywhere. Every
scenario comes from ground_truth_v2.ExcessScenario — including the
PII-bearing note used to prove masking, which lives in the oracle rather
than being hand-written here.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ground_truth_v2 import ExcessScenario, build_suite_v2
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


def _open(client: TestClient, s: ExcessScenario) -> str:
    opened = s.events[0]
    r = client.post("/api/v1/excess-ledger/open", json={
        "branch_code": s.branch_code, "teller_id": s.teller_id,
        "business_date": s.business_date, "entry_kind": s.entry_kind,
        "amount": str(opened.amount), "opener": opened.actor,
        "note": opened.note or None,
    })
    assert r.status_code == 201, r.text
    return r.json()["case_ref"]


def _explained_payloads() -> list[dict]:
    with OrmSession(get_engine()) as db:
        rows = db.execute(
            select(AuditLedgerRow).where(AuditLedgerRow.action == "EXCESS_EXPLAINED")
        ).scalars().all()
        return [dict(r.payload) for r in rows]


def test_explain_opened_case_in_urdu(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().excess if s.expected_outcome == "accepted")
    case_ref = _open(client, s)

    r = client.post(f"/api/v1/excess-ledger/{case_ref}/explain", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["case_ref"] == case_ref
    assert body["lang"] == "ur"
    assert body["explanation"] == "یہ لین دین دو بار درج ہوا ہے۔"


def test_explanation_writes_exactly_one_audit_row(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().excess if s.expected_outcome == "accepted")
    case_ref = _open(client, s)
    before = len(_explained_payloads())

    client.post(f"/api/v1/excess-ledger/{case_ref}/explain", json={})

    payloads = _explained_payloads()
    assert len(payloads) == before + 1
    assert payloads[-1]["case_ref"] == case_ref


def test_explanation_masks_account_and_cnic_in_note(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().excess if s.case_id == "excess_happy_note_with_pii"
    )
    case_ref = _open(client, s)

    r = client.post(f"/api/v1/excess-ledger/{case_ref}/explain", json={})
    assert r.status_code == 200, r.text

    prompt = client.fake.completions.calls[-1]["messages"][1]["content"]  # type: ignore[attr-defined]
    assert "00456789" not in prompt
    assert "42101-1234567-1" not in prompt
    assert "****" in prompt  # proves redaction happened, not deletion


def test_explain_unknown_case_is_404(client: TestClient) -> None:
    r = client.post(
        "/api/v1/excess-ledger/00000000-0000-4000-8000-000000000099/explain", json={}
    )
    assert r.status_code == 404


def test_explain_without_key_is_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = next(s for s in build_suite_v2().excess if s.expected_outcome == "accepted")
    case_ref = _open(client, s)
    monkeypatch.setattr("app.config.settings.groq_api_key", "your-groq-api-key-here")
    r = client.post(f"/api/v1/excess-ledger/{case_ref}/explain", json={})
    assert r.status_code == 503
