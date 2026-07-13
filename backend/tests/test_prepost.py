"""Phase 12 tests — pre-post validation (DEMO-ONLY SURFACE).

Every `ground_truth_v2.PrepostScenario` drives one API call. Also asserts that
each call writes exactly one `validation_log` row (fed to the UI demo screen).

This is not a production intercept. See CLAUDE.md hard-constraint #6.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ground_truth_v2 import PrepostScenario, build_suite_v2
from sqlalchemy import text as sqltext

from app.db import get_engine
from app.main import app

TRUNCATE_TABLES = (
    "validation_log, cheque_transactions, excess_ledger, "
    "cash_movement_denominations, cash_movement_ledger, audit_ledger, suspects, denomination_counts, "
    "transactions, recon_reports, eod_sessions"
)

_CHECK_ROUTE = {
    "denom_sum": "denom-sum",
    "cnic_name_match": "cnic-name-match",
    "duplicate_check": "duplicate-check",
    "large_amount_confirm": "large-amount-confirm",
    "sanity": "sanity",
}


@pytest.fixture()
def client() -> TestClient:
    with get_engine().connect() as conn:
        conn.execute(sqltext(f"TRUNCATE {TRUNCATE_TABLES} RESTART IDENTITY CASCADE"))
        conn.commit()
    return TestClient(app)


def _post(client: TestClient, s: PrepostScenario):
    path = f"/api/v1/prepost/{_CHECK_ROUTE[s.check_name]}"
    return client.post(path, json={"teller_id": "TLR-TEST", "input": s.input})


def _validation_log_count() -> int:
    with get_engine().connect() as conn:
        return conn.execute(sqltext("SELECT COUNT(*) FROM validation_log")).scalar_one()


@pytest.mark.parametrize(
    "scenario",
    list(build_suite_v2().prepost),
    ids=lambda s: s.case_id,
)
def test_prepost_scenario_matches_oracle(
    client: TestClient, scenario: PrepostScenario,
) -> None:
    r = _post(client, scenario)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["check_name"] == scenario.check_name
    assert body["passed"] == scenario.expected_passed, body
    if not scenario.expected_passed:
        assert body["reason"], "failed check must carry a reason"


def test_each_call_writes_exactly_one_validation_log_row(client: TestClient) -> None:
    s = build_suite_v2().prepost[0]
    assert _validation_log_count() == 0
    _post(client, s).raise_for_status()
    assert _validation_log_count() == 1
    _post(client, s).raise_for_status()
    assert _validation_log_count() == 2


def test_malformed_input_returns_422(client: TestClient) -> None:
    r = client.post(
        "/api/v1/prepost/denom-sum",
        json={"teller_id": "TLR-TEST", "input": {"amount": 5500}},  # no denominations
    )
    assert r.status_code == 422
