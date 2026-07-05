"""Recon Report PDF tests: binary output + ledger-hash bookkeeping."""

from fastapi.testclient import TestClient
from generator import make_case
from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession
from test_api import client, ingest  # noqa: F401  (fixture reuse)

from app.db import get_engine
from app.db_models import ReconReportRow


def test_report_pdf_and_ledger_hash(client: TestClient) -> None:  # noqa: F811
    case = make_case("api_pdf", ["duplicate_posting"], seed=31)
    sid = ingest(client, case).json()["id"]
    head_before = client.get("/api/v1/ledger/verify").json()["head"]

    r = client.get(f"/api/v1/sessions/{sid}/report.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 5000

    # recon_reports row attests to the pre-generation ledger head
    with OrmSession(get_engine()) as db:
        row = db.execute(
            select(ReconReportRow).where(ReconReportRow.session_id == sid)
        ).scalar_one()
        assert row.ledger_hash == head_before

    # generation itself is ledgered and the chain still verifies
    v = client.get("/api/v1/ledger/verify").json()
    assert v["ok"] is True
    assert v["entries"] == 2  # SESSION_INGESTED + REPORT_GENERATED
    assert v["head"] != head_before


def test_report_regeneration_is_ledgered(client: TestClient) -> None:  # noqa: F811
    case = make_case("api_pdf2", ["missed_reversal"], seed=32)
    sid = ingest(client, case).json()["id"]
    client.get(f"/api/v1/sessions/{sid}/report.pdf")
    client.get(f"/api/v1/sessions/{sid}/report.pdf")
    v = client.get("/api/v1/ledger/verify").json()
    assert v["ok"] is True
    assert v["entries"] == 3
    with OrmSession(get_engine()) as db:
        rows = db.execute(
            select(ReconReportRow).where(ReconReportRow.session_id == sid)
        ).scalars().all()
        assert len(rows) == 2
        assert rows[0].ledger_hash != rows[1].ledger_hash  # second attests to newer head


def test_report_404(client: TestClient) -> None:  # noqa: F811
    assert client.get("/api/v1/sessions/424242/report.pdf").status_code == 404
