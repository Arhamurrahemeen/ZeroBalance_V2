"""Phase 16 tests — Cash Movement Ledger backend.

Unlike Excess Ledger, this is NOT a state machine: each POST inserts exactly
one event row + its denomination rows, hash-chained into a single global
chain. Sign-off shape depends on event_type (day_start/reissue/day_end need
teller+OM; handover needs teller+counterparty+OM).

Every scenario is sourced from `ground_truth_v2.CashMovementScenario` so the
oracle stays the single source of truth for "what should happen".
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from ground_truth_v2 import CashMovementScenario, build_suite_v2
from sqlalchemy import text as sqltext

from app.db import get_engine
from app.main import app

TRUNCATE_TABLES = (
    "validation_log, cheque_transactions, excess_ledger, "
    "cash_movement_denominations, cash_movement_ledger, audit_ledger, "
    "suspects, denomination_counts, transactions, recon_reports, eod_sessions"
)


@pytest.fixture()
def client() -> TestClient:
    with get_engine().connect() as conn:
        conn.execute(sqltext(f"TRUNCATE {TRUNCATE_TABLES} RESTART IDENTITY CASCADE"))
        conn.commit()
    return TestClient(app)


# --- helpers -----------------------------------------------------------------


def _body(s: CashMovementScenario) -> dict:
    body: dict = {
        "event_type": s.event_type,
        "teller_id": s.teller_id,
        "om_id": s.om_id,
        "session_id": s.session_id,
        "denominations": s.denominations,
        "signoff_teller": s.signoff_teller,
        "signoff_om": s.signoff_om,
    }
    if s.counterparty_id is not None:
        body["counterparty_id"] = s.counterparty_id
    if s.signoff_counterparty is not None:
        body["signoff_counterparty"] = s.signoff_counterparty
    return body


def _post(client: TestClient, s: CashMovementScenario):
    return client.post("/api/v1/cash-movement", json=_body(s))


def _denom_total(s: CashMovementScenario) -> Decimal:
    return Decimal(sum(int(k) * v for k, v in s.denominations.items()))


# --- happy-path scenarios ------------------------------------------------


@pytest.mark.parametrize(
    "scenario",
    [s for s in build_suite_v2().cash_movement if s.expected_outcome == "accepted"],
    ids=lambda s: s.case_id,
)
def test_happy_event_recorded(client: TestClient, scenario: CashMovementScenario) -> None:
    r = _post(client, scenario)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["event_type"] == scenario.event_type
    assert body["teller_id"] == scenario.teller_id
    assert body["session_id"] == scenario.session_id
    assert Decimal(body["total_amount"]) == _denom_total(scenario)
    assert body["denominations"] == {
        str(k): v for k, v in scenario.denominations.items()
    }
    if scenario.event_type == "handover":
        assert body["counterparty_id"] == scenario.counterparty_id


# --- rejection scenarios ------------------------------------------------


@pytest.mark.parametrize(
    "scenario",
    [s for s in build_suite_v2().cash_movement if s.expected_outcome != "accepted"],
    ids=lambda s: s.case_id,
)
def test_rejected_scenarios_return_422(
    client: TestClient, scenario: CashMovementScenario,
) -> None:
    r = _post(client, scenario)
    assert r.status_code == 422, r.text


def test_missing_om_signoff_message(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().cash_movement
        if s.expected_outcome == "rejected_missing_om_signoff"
    )
    r = _post(client, s)
    assert r.status_code == 422
    assert "om" in r.json()["detail"].lower()


def test_handover_missing_counterparty_signoff_message(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().cash_movement
        if s.expected_outcome == "rejected_missing_counterparty_signoff"
    )
    r = _post(client, s)
    assert r.status_code == 422
    assert "counterparty" in r.json()["detail"].lower()


def test_bad_denomination_rejected(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().cash_movement
        if s.expected_outcome == "rejected_bad_denomination"
    )
    r = _post(client, s)
    assert r.status_code == 422


# --- invariants -----------------------------------------------------------


def test_no_rows_persisted_on_rejection(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().cash_movement
        if s.expected_outcome == "rejected_missing_om_signoff"
    )
    _post(client, s)
    with get_engine().connect() as conn:
        n = conn.execute(sqltext("SELECT COUNT(*) FROM cash_movement_ledger")).scalar_one()
    assert n == 0


def test_hash_chain_verify_after_several_events(client: TestClient) -> None:
    accepted = [s for s in build_suite_v2().cash_movement if s.expected_outcome == "accepted"]
    for s in accepted:
        _post(client, s).raise_for_status()

    r = client.get("/api/v1/cash-movement/verify-chain")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["rows"] == len(accepted)
    assert body["head"] != "GENESIS"


def test_list_filters_by_teller_and_session(client: TestClient) -> None:
    day_start = next(
        s for s in build_suite_v2().cash_movement
        if s.case_id == "cash_day_start_happy"
    )
    reissue = next(
        s for s in build_suite_v2().cash_movement
        if s.case_id == "cash_reissue_happy"
    )
    _post(client, day_start).raise_for_status()
    _post(client, reissue).raise_for_status()

    r = client.get("/api/v1/cash-movement", params={
        "teller_id": day_start.teller_id, "session_id": day_start.session_id,
    })
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert {e["event_type"] for e in body} == {"day_start", "reissue"}


def test_denomination_sum_becomes_total_amount(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().cash_movement
        if s.case_id == "cash_day_start_happy"
    )
    r = _post(client, s)
    assert r.status_code == 201
    assert Decimal(r.json()["total_amount"]) == _denom_total(s)


# --- segregation of duties (Finding #1) ------------------------------------


def _valid_day_start_body() -> dict:
    return {
        "event_type": "day_start", "teller_id": "TLR-100", "om_id": "OM-1",
        "session_id": "SES-100", "denominations": {"5000": 2, "1000": 3},
        "signoff_teller": "PIN-TLR", "signoff_om": "PIN-OM",
    }


def test_teller_cannot_sign_as_own_om(client: TestClient) -> None:
    body = _valid_day_start_body()
    body["signoff_om"] = body["signoff_teller"]  # one person signs both roles
    r = client.post("/api/v1/cash-movement", json=body)
    assert r.status_code == 422, r.text
    assert "different" in r.json()["detail"].lower()


def test_handover_requires_three_distinct_signers(client: TestClient) -> None:
    body = {
        "event_type": "handover", "teller_id": "TLR-100", "counterparty_id": "TLR-200",
        "om_id": "OM-1", "session_id": "SES-100",
        "denominations": {"5000": 2}, "signoff_teller": "PIN-TLR",
        "signoff_counterparty": "PIN-TLR", "signoff_om": "PIN-OM",  # cp == teller
    }
    r = client.post("/api/v1/cash-movement", json=body)
    assert r.status_code == 422, r.text
    assert "distinct" in r.json()["detail"].lower()


def test_teller_cannot_hand_over_to_themselves(client: TestClient) -> None:
    body = {
        "event_type": "handover", "teller_id": "TLR-100", "counterparty_id": "TLR-100",
        "om_id": "OM-1", "session_id": "SES-100",
        "denominations": {"5000": 2}, "signoff_teller": "PIN-TLR",
        "signoff_counterparty": "PIN-TLR2", "signoff_om": "PIN-OM",
    }
    r = client.post("/api/v1/cash-movement", json=body)
    assert r.status_code == 422, r.text
    assert "themselves" in r.json()["detail"].lower()


# --- sign-off tamper-evidence (Finding #2) ---------------------------------


def test_forged_signoff_breaks_chain(client: TestClient) -> None:
    """The hash chain must cover WHO signed. Rewriting an approver directly in
    the DB (bypassing the append-only trigger) must make verify-chain fail."""
    r = client.post("/api/v1/cash-movement", json=_valid_day_start_body())
    assert r.status_code == 201, r.text
    assert client.get("/api/v1/cash-movement/verify-chain").json()["ok"] is True

    with get_engine().connect() as conn:
        conn.execute(sqltext(
            "ALTER TABLE cash_movement_ledger "
            "DISABLE TRIGGER cash_movement_ledger_append_only"
        ))
        conn.execute(sqltext(
            "UPDATE cash_movement_ledger SET signoff_om = 'FORGED_APPROVER'"
        ))
        conn.execute(sqltext(
            "ALTER TABLE cash_movement_ledger "
            "ENABLE TRIGGER cash_movement_ledger_append_only"
        ))
        conn.commit()

    assert client.get("/api/v1/cash-movement/verify-chain").json()["ok"] is False


# --- GET /eod/reconciliation -----------------------------------------------


def test_reconciliation_shows_opening_vs_physical_per_denom(client: TestClient) -> None:
    suite = build_suite_v2().cash_movement
    day_start = next(s for s in suite if s.case_id == "cash_day_start_happy")
    reissue = next(s for s in suite if s.case_id == "cash_reissue_happy")
    day_end = next(s for s in suite if s.case_id == "cash_day_end_happy")
    for s in (day_start, reissue, day_end):
        _post(client, s).raise_for_status()

    r = client.get("/api/v1/eod/reconciliation", params={
        "teller_id": day_start.teller_id, "business_date": date.today().isoformat(),
    })
    assert r.status_code == 200, r.text
    body = r.json()
    by_denom = {row["denomination"]: row for row in body["per_denom"]}

    # 5000: day_start had 10, day_end had 8 -> opening 10, physical 8, variance -2
    assert by_denom[5000]["opening_plus_reissues"] == 10
    assert by_denom[5000]["physical"] == 8
    assert by_denom[5000]["variance"] == -2
    # 1000: day_start 20 + reissue 30 = 50 opening; day_end 15 physical
    assert by_denom[1000]["opening_plus_reissues"] == 50
    assert by_denom[1000]["physical"] == 15
    assert by_denom[1000]["variance"] == -35

    # No fabricated per-transaction deposit/withdrawal columns — that data
    # doesn't exist (per-transaction denomination capture is forbidden).
    for row in body["per_denom"]:
        assert "deposits_in" not in row
        assert "withdrawals_out" not in row


def test_reconciliation_empty_for_teller_with_no_events(client: TestClient) -> None:
    r = client.get("/api/v1/eod/reconciliation", params={
        "teller_id": "TLR-999", "business_date": date.today().isoformat(),
    })
    assert r.status_code == 200
    assert r.json()["per_denom"] == []
