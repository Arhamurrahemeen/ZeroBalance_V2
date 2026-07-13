"""Phase 13 tests — Excess Ledger Daily Register PDF."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from ground_truth_v2 import ExcessScenario, build_suite_v2
from sqlalchemy import text as sqltext
from sqlalchemy.orm import Session as OrmSession

from app.db import get_engine
from app.excess_ledger import list_register
from app.main import app
from app.report import render_excess_register_html

TRUNCATE_TABLES = (
    "validation_log, cheque_transactions, excess_ledger, "
    "cash_movement_denominations, cash_movement_ledger, audit_ledger, suspects, denomination_counts, "
    "transactions, recon_reports, eod_sessions"
)


@pytest.fixture()
def client() -> TestClient:
    with get_engine().connect() as conn:
        conn.execute(sqltext(f"TRUNCATE {TRUNCATE_TABLES} RESTART IDENTITY CASCADE"))
        conn.commit()
    return TestClient(app)


def _full_cycle(client: TestClient, s: ExcessScenario) -> str:
    opened = s.events[0]
    r = client.post("/api/v1/excess-ledger/open", json={
        "branch_code": s.branch_code, "teller_id": s.teller_id,
        "business_date": s.business_date, "entry_kind": s.entry_kind,
        "amount": str(opened.amount), "opener": opened.actor,
        "note": opened.note or None,
    })
    case_ref = r.json()["case_ref"]
    client.post(f"/api/v1/excess-ledger/{case_ref}/countersign",
                json={"officer": s.events[1].actor}).raise_for_status()
    client.post(f"/api/v1/excess-ledger/{case_ref}/close", json={
        "officer": s.events[2].actor, "resolution_note": s.events[2].note or "resolved",
    }).raise_for_status()
    return case_ref


def test_register_pdf_returns_pdf(client: TestClient) -> None:
    accepted = [s for s in build_suite_v2().excess if s.expected_outcome == "accepted"]
    for s in accepted:
        _full_cycle(client, s)
    business_date = accepted[0].business_date

    r = client.get("/api/v1/excess-ledger/report.pdf", params={
        "from_date": business_date, "to_date": business_date,
    })
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 3000


def test_register_html_contains_case_count(client: TestClient) -> None:
    accepted = [s for s in build_suite_v2().excess if s.expected_outcome == "accepted"]
    for s in accepted:
        _full_cycle(client, s)
    bd = date.fromisoformat(accepted[0].business_date)

    with OrmSession(get_engine()) as db:
        views = list_register(db, from_date=bd, to_date=bd)
    assert len(views) == len(accepted)

    rendered = render_excess_register_html(
        views, bd.isoformat(), bd.isoformat(), None, "GENESIS", datetime.now(UTC),
    )
    assert f"{len(views)} case(s)" in rendered
    for v in views:
        assert v.case_ref[:8] in rendered


def test_register_pdf_empty_range_falls_back_gracefully(client: TestClient) -> None:
    r = client.get("/api/v1/excess-ledger/report.pdf", params={
        "from_date": "2099-01-01", "to_date": "2099-12-31",
    })
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 500


def test_register_pdf_bad_range_is_422(client: TestClient) -> None:
    r = client.get("/api/v1/excess-ledger/report.pdf", params={
        "from_date": "2026-12-31", "to_date": "2026-01-01",
    })
    assert r.status_code == 422


def test_register_pdf_generation_is_ledgered(client: TestClient) -> None:
    s = next(s for s in build_suite_v2().excess if s.expected_outcome == "accepted")
    _full_cycle(client, s)

    r = client.get("/api/v1/excess-ledger/report.pdf", params={
        "from_date": s.business_date, "to_date": s.business_date,
    })
    assert r.status_code == 200
    v = client.get("/api/v1/ledger/verify").json()
    assert v["ok"] is True
