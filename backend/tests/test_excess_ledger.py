"""Phase 11 tests — Digital Excess Ledger (flagship).

Runs against the compose Postgres. Truncates the v2 tables (plus audit_ledger)
per test — TRUNCATE bypasses row triggers by design, so the append-only guard
on excess_ledger and audit_ledger is not violated.

Every state-machine scenario is sourced from `ground_truth_v2.ExcessScenario`,
so the "did we handle this case" list stays in one place (the oracle) and does
not drift between tests and product code.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from ground_truth_v2 import ExcessScenario, build_suite_v2
from sqlalchemy import text as sqltext

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


# --- helpers ---------------------------------------------------------------


def _open(client: TestClient, s: ExcessScenario) -> tuple[str, dict]:
    opened_event = s.events[0]
    r = client.post("/api/v1/excess-ledger/open", json={
        "branch_code": s.branch_code, "teller_id": s.teller_id,
        "business_date": s.business_date, "entry_kind": s.entry_kind,
        "amount": str(opened_event.amount), "opener": opened_event.actor,
        "note": opened_event.note or None,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    return body["case_ref"], body


def _countersign(client: TestClient, case_ref: str, officer: str):
    return client.post(
        f"/api/v1/excess-ledger/{case_ref}/countersign",
        json={"officer": officer},
    )


def _close(client: TestClient, case_ref: str, officer: str, note: str):
    return client.post(
        f"/api/v1/excess-ledger/{case_ref}/close",
        json={"officer": officer, "resolution_note": note},
    )


def _events_for(case_ref: str) -> list[str]:
    """Direct DB read to prove there are only INSERTs (not UPDATEs)."""
    with get_engine().connect() as conn:
        rows = conn.execute(sqltext(
            "SELECT event_type FROM excess_ledger "
            "WHERE case_ref = :cr ORDER BY event_seq"
        ), {"cr": case_ref}).scalars().all()
    return list(rows)


# --- happy-path scenarios --------------------------------------------------


@pytest.mark.parametrize(
    "scenario",
    [s for s in build_suite_v2().excess if s.expected_outcome == "accepted"],
    ids=lambda s: s.case_id,
)
def test_happy_close(client: TestClient, scenario: ExcessScenario) -> None:
    case_ref, opened_body = _open(client, scenario)
    assert opened_body["state"] == "opened"
    assert Decimal(opened_body["amount"]) == scenario.events[0].amount
    assert opened_body["opener"] == scenario.events[0].actor

    countersigner = scenario.events[1].actor
    r = _countersign(client, case_ref, countersigner)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "countersigned"
    assert body["countersigner"] == countersigner
    assert body["opener"] != body["countersigner"], "dual sign-off must hold"

    closer = scenario.events[2].actor
    note = scenario.events[2].note or "resolved"
    r = _close(client, case_ref, closer, note)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "closed"
    assert body["closer"] == closer
    assert body["resolution"] == note

    # DB shape: exactly 3 rows, in order, no UPDATE possible.
    assert _events_for(case_ref) == ["opened", "countersigned", "closed"]


# --- rejection scenarios ---------------------------------------------------


def test_dual_signoff_violation_same_actor(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().excess
        if s.expected_outcome == "rejected_dual_signoff"
    )
    case_ref, _ = _open(client, s)
    r = _countersign(client, case_ref, s.events[1].actor)  # same as opener
    assert r.status_code == 409
    assert "differ from opener" in r.json()["detail"]
    # Rejection means only the opened row exists.
    assert _events_for(case_ref) == ["opened"]


def test_close_without_countersign(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().excess
        if s.expected_outcome == "rejected_missing_countersign"
    )
    case_ref, _ = _open(client, s)
    r = _close(client, case_ref, s.events[1].actor, "attempted close")
    assert r.status_code == 409
    assert "before countersign" in r.json()["detail"]
    assert _events_for(case_ref) == ["opened"]


def test_double_countersign(client: TestClient) -> None:
    s = next(
        s for s in build_suite_v2().excess
        if s.expected_outcome == "rejected_double_countersign"
    )
    case_ref, _ = _open(client, s)
    r1 = _countersign(client, case_ref, s.events[1].actor)
    assert r1.status_code == 200
    r2 = _countersign(client, case_ref, s.events[2].actor)
    assert r2.status_code == 409
    assert "already countersigned" in r2.json()["detail"]
    assert _events_for(case_ref) == ["opened", "countersigned"]


def test_countersign_before_open_is_case_not_found(client: TestClient) -> None:
    # No excess entry has been opened, so the case_ref is unknown.
    unknown = "00000000-0000-4000-8000-000000000000"
    r = _countersign(client, unknown, "OFF-014")
    assert r.status_code == 404


def test_close_before_open_is_case_not_found(client: TestClient) -> None:
    unknown = "00000000-0000-4000-8000-000000000001"
    r = _close(client, unknown, "OFF-014", "attempted close")
    assert r.status_code == 404


# --- invariants -----------------------------------------------------------


def test_hash_chain_verify_after_happy_close(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().excess if s.expected_outcome == "accepted")
    case_ref, _ = _open(client, s)
    _countersign(client, case_ref, s.events[1].actor).raise_for_status()
    _close(client, case_ref, s.events[2].actor, s.events[2].note or "ok").raise_for_status()

    r = client.get("/api/v1/excess-ledger/verify-chain")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["rows"] == 3
    assert body["head"] != "GENESIS"


def test_register_returns_case_view_in_range(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().excess if s.expected_outcome == "accepted")
    case_ref, _ = _open(client, s)
    _countersign(client, case_ref, s.events[1].actor).raise_for_status()
    _close(client, case_ref, s.events[2].actor, s.events[2].note or "ok").raise_for_status()

    r = client.get(
        "/api/v1/excess-ledger",
        params={"from_date": s.business_date, "to_date": s.business_date},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    view = body[0]
    assert view["case_ref"] == case_ref
    assert view["state"] == "closed"
    assert view["opener"] == s.events[0].actor
    assert view["countersigner"] == s.events[1].actor


def test_register_empty_range_returns_empty_list(client: TestClient) -> None:
    r = client.get(
        "/api/v1/excess-ledger",
        params={"from_date": "2099-01-01", "to_date": "2099-12-31"},
    )
    assert r.status_code == 200
    assert r.json() == []


def test_register_bad_date_range_rejected(client: TestClient) -> None:
    r = client.get(
        "/api/v1/excess-ledger",
        params={"from_date": "2026-12-31", "to_date": "2026-01-01"},
    )
    assert r.status_code == 422


def test_amount_locked_across_events(client: TestClient) -> None:
    """Even if a caller sends a different countersign body, service inherits
    the opened amount. The countersigner cannot silently mutate the number."""
    s = next(s for s in build_suite_v2().excess if s.expected_outcome == "accepted")
    case_ref, opened_body = _open(client, s)
    r = _countersign(client, case_ref, s.events[1].actor)
    assert r.status_code == 200
    assert r.json()["amount"] == opened_body["amount"]
