"""Phase 12 tests — cheque capture (sidecar).

Driven by `ground_truth_v2.ChequeScenario`. Runs against compose Postgres;
truncates v2 + audit tables per test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from ground_truth_v2 import ChequeScenario, build_suite_v2
from sqlalchemy import text as sqltext

from app.cheque import extract_micr_account
from app.db import get_engine
from app.main import app

TRUNCATE_TABLES = (
    "validation_log, cheque_transactions, excess_ledger, "
    "opening_float_declaration, audit_ledger, suspects, denomination_counts, "
    "transactions, recon_reports, eod_sessions"
)


@pytest.fixture()
def client() -> TestClient:
    with get_engine().connect() as conn:
        conn.execute(sqltext(f"TRUNCATE {TRUNCATE_TABLES} RESTART IDENTITY CASCADE"))
        conn.commit()
    return TestClient(app)


def _post(client: TestClient, s: ChequeScenario):
    return client.post("/api/v1/cheque", json={
        "branch_code": s.branch_code, "teller_id": s.teller_id,
        "business_date": s.business_date, "micr": s.micr,
        "account_number": s.account_number, "amount": str(s.amount),
        "denomination_out": s.denomination_out,
    })


# --- pure logic (no DB) ----------------------------------------------------


def test_extract_micr_account_takes_last_block() -> None:
    micr = "⑈042000123456⑈ ⑆00789012⑆"
    assert extract_micr_account(micr) == "00789012"


def test_extract_micr_account_returns_none_when_missing() -> None:
    assert extract_micr_account("no micr here") is None


# --- driven by ground_truth_v2 --------------------------------------------


@pytest.mark.parametrize(
    "scenario",
    [s for s in build_suite_v2().cheque if s.expected_outcome == "valid"],
    ids=lambda s: s.case_id,
)
def test_valid_scenarios_capture_ok(client: TestClient, scenario: ChequeScenario) -> None:
    r = _post(client, scenario)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["account_number"] == scenario.account_number
    assert Decimal(body["amount"]) == scenario.amount
    assert body["denomination_out"] == {str(k): int(v) for k, v in scenario.denomination_out.items()}


def test_denom_sum_mismatch_rejected(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().cheque if s.expected_outcome == "invalid_denom_sum")
    r = _post(client, s)
    assert r.status_code == 422
    assert "sum" in r.json()["detail"].lower()


def test_micr_account_mismatch_rejected(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().cheque if s.expected_outcome == "invalid_micr")
    r = _post(client, s)
    assert r.status_code == 422
    assert "micr" in r.json()["detail"].lower()


# --- register + range ------------------------------------------------------


def test_list_captures_returns_valid_scenarios_only(client: TestClient) -> None:
    for s in build_suite_v2().cheque:
        _post(client, s)  # invalid ones 422; valid ones 201
    # Take the first valid scenario's business_date for the range.
    valid = [s for s in build_suite_v2().cheque if s.expected_outcome == "valid"]
    d = valid[0].business_date
    r = client.get("/api/v1/cheque", params={"from_date": d, "to_date": d})
    assert r.status_code == 200
    body = r.json()
    assert len(body) == len(valid)


def test_list_captures_bad_range_rejected(client: TestClient) -> None:
    r = client.get(
        "/api/v1/cheque",
        params={"from_date": "2026-12-31", "to_date": "2026-01-01"},
    )
    assert r.status_code == 422
