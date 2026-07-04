"""End-to-end API tests against the compose Postgres (dev DB, synthetic data
only — tables are truncated per test; TRUNCATE bypasses row triggers by design)."""

import csv
import io
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from generator import Case, make_case
from sqlalchemy import text as sqltext
from sqlalchemy.exc import DatabaseError

from app.db import get_engine
from app.main import app

TABLES = "audit_ledger, suspects, denomination_counts, transactions, recon_reports, eod_sessions"


@pytest.fixture()
def client() -> TestClient:
    with get_engine().connect() as conn:
        conn.execute(sqltext(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        conn.commit()
    return TestClient(app)


def case_csv(case: Case) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["BRANCH_CODE", "TELLER_ID", "TXN_DATE", "TXN_TIME",
                "TXN_REF", "ACCOUNT_NO", "TXN_TYPE", "AMOUNT", "NARRATION"])
    for t in case.posted:
        w.writerow([case.branch, case.teller, case.business_date, t.time,
                    t.ref, t.account, t.txn_type.upper(), t.amount, t.narration])
    return buf.getvalue()


def ingest(client: TestClient, case: Case) -> httpx.Response:
    meta = {"opening_float": case.opening_float,
            "denomination_count": case.denomination_count}
    return client.post(
        "/api/v1/sessions",
        files={"file": (f"{case.case_id}.csv", case_csv(case), "text/csv")},
        data={"meta": json.dumps(meta)},
    )


def test_ingest_end_to_end(client: TestClient) -> None:
    case = make_case("api_dup", ["duplicate_posting"], seed=7)
    r = ingest(client, case)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["variance"] == case.variance
    assert body["status"] == "flagged"
    assert body["txn_count"] == len(case.posted)
    truth = case.errors[0]
    assert any(
        s["signature"] == "duplicate_posting" and set(s["txn_refs"]) & set(truth.refs)
        for s in body["suspects"]
    ), body["suspects"]


def test_duplicate_ingest_conflict(client: TestClient) -> None:
    case = make_case("api_conflict", ["missed_reversal"], seed=8)
    assert ingest(client, case).status_code == 201
    assert ingest(client, case).status_code == 409


def test_worklist_and_detail(client: TestClient) -> None:
    c1 = make_case("api_w1", ["cash_inout_miskey"], seed=9)
    c2 = make_case("api_w2", ["denomination_shortfall"], seed=10)
    id1 = ingest(client, c1).json()["id"]
    ingest(client, c2)
    listing = client.get("/api/v1/sessions").json()
    assert len(listing) == 2
    assert {"age_days", "suspect_count", "variance"} <= set(listing[0])
    detail = client.get(f"/api/v1/sessions/{id1}").json()
    assert detail["id"] == id1
    assert detail["suspects"][0]["rank"] == 1
    assert client.get("/api/v1/sessions/99999").status_code == 404


def test_balanced_session_closes_with_no_suspects(client: TestClient) -> None:
    case = make_case("api_clean", [], seed=11)
    body = ingest(client, case).json()
    assert body["variance"] == 0
    assert body["status"] == "closed"
    assert body["suspects"] == []


def test_resolve_flow(client: TestClient) -> None:
    case = make_case("api_resolve", ["digit_transposition"], seed=12)
    sid = ingest(client, case).json()["id"]
    r = client.post(f"/api/v1/sessions/{sid}/resolve",
                    json={"note": "shortcash recovered", "actor": "T01"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"
    assert client.post(f"/api/v1/sessions/{sid}/resolve",
                       json={"note": "again"}).status_code == 409


def test_ledger_chain_and_immutability(client: TestClient) -> None:
    case = make_case("api_ledger", ["wrong_adjacent_account"], seed=13)
    sid = ingest(client, case).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/resolve", json={"note": "ok"})
    v = client.get("/api/v1/ledger/verify").json()
    assert v["ok"] is True
    assert v["entries"] == 2
    assert v["head"] != "GENESIS"
    # UPDATE must be rejected by the append-only trigger
    with get_engine().connect() as conn, pytest.raises(DatabaseError, match="append-only"):
        conn.execute(sqltext("UPDATE audit_ledger SET action = 'tampered' WHERE id = 1"))


def test_bad_csv_rejected(client: TestClient) -> None:
    r = client.post(
        "/api/v1/sessions",
        files={"file": ("bad.csv", "NOT,A,PIBAS,EXPORT\n1,2,3,4", "text/csv")},
        data={"meta": json.dumps({"opening_float": 0, "denomination_count": {}})},
    )
    assert r.status_code == 400
