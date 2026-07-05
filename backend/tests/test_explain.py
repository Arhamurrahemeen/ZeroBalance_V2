"""Explanation layer tests — offline (fake Groq client). The invariant under
test: explaining NEVER adds, removes, reorders, or re-scores suspects."""

from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from generator import make_case
from sqlalchemy import text as sqltext
from test_api import TABLES, ingest  # reuse helpers

from app import explain as explain_mod
from app.db import get_engine
from app.explain import build_prompt, mask_account
from app.main import app


@dataclass
class FakeMessage:
    content: str = "یہ لین دین دو بار درج ہوا ہے۔"


@dataclass
class FakeChoice:
    message: FakeMessage = field(default_factory=FakeMessage)


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)

        class R:
            choices = [FakeChoice()]

        return R()


class FakeClient:
    def __init__(self) -> None:
        self.completions = FakeCompletions()

    @property
    def chat(self) -> "FakeClient":
        return self


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    with get_engine().connect() as conn:
        conn.execute(sqltext(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        conn.commit()
    fake = FakeClient()
    monkeypatch.setattr(explain_mod, "_client_factory", lambda: fake)
    monkeypatch.setattr("app.config.settings.groq_api_key", "gsk_test")
    tc = TestClient(app)
    tc.fake = fake  # type: ignore[attr-defined]
    return tc


def test_explain_fills_urdu_and_never_reorders(client: TestClient) -> None:
    case = make_case("exp_dup", ["duplicate_posting"], seed=21)
    sid = ingest(client, case).json()["id"]
    before = client.get(f"/api/v1/sessions/{sid}").json()["suspects"]

    r = client.post(f"/api/v1/sessions/{sid}/explain")
    assert r.status_code == 200, r.text
    after = r.json()["suspects"]

    assert len(after) == len(before)
    for b, a in zip(before, after, strict=True):
        assert (b["rank"], b["signature"], b["txn_refs"]) == (
            a["rank"], a["signature"], a["txn_refs"])
        assert b["cash_delta"] == a["cash_delta"] and b["evidence"] == a["evidence"]
        assert a["explanation_ur"] == "یہ لین دین دو بار درج ہوا ہے۔"


def test_explain_is_idempotent(client: TestClient) -> None:
    case = make_case("exp_idem", ["cash_inout_miskey"], seed=22)
    sid = ingest(client, case).json()["id"]
    client.post(f"/api/v1/sessions/{sid}/explain")
    calls_after_first = len(client.fake.completions.calls)  # type: ignore[attr-defined]
    client.post(f"/api/v1/sessions/{sid}/explain")
    assert len(client.fake.completions.calls) == calls_after_first  # type: ignore[attr-defined]


def test_prompt_masks_accounts_and_carries_engine_facts(client: TestClient) -> None:
    case = make_case("exp_mask", ["wrong_adjacent_account"], seed=23)
    sid = ingest(client, case).json()["id"]

    from sqlalchemy.orm import Session as OrmSession

    from app.db_models import EodSessionRow, SuspectRow

    with OrmSession(get_engine()) as db:
        row = db.get(EodSessionRow, sid)
        suspect = db.query(SuspectRow).filter_by(session_id=sid, rank=1).one()
        prompt = build_prompt(row, suspect)
        posted = suspect.rule_evidence["detail"]["posted_account"]
        assert posted not in prompt          # full account never leaves the box
        assert f"****{posted[-4:]}" in prompt
        assert suspect.signature in prompt
        assert suspect.rule_evidence["txn_refs"][0] in prompt


def test_mask_account() -> None:
    assert mask_account("301029743649") == "****3649"
    assert mask_account("123") == "****"


def test_upstream_failure_returns_502_and_keeps_state(client: TestClient) -> None:
    case = make_case("exp_fail", ["missed_reversal"], seed=24)
    sid = ingest(client, case).json()["id"]

    def boom(**kwargs: object) -> object:
        raise RuntimeError("rate limited")

    client.fake.completions.create = boom  # type: ignore[attr-defined]
    r = client.post(f"/api/v1/sessions/{sid}/explain")
    assert r.status_code == 502
    suspects = client.get(f"/api/v1/sessions/{sid}").json()["suspects"]
    assert all(s["explanation_ur"] is None for s in suspects)


def test_explain_without_key_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    case = make_case("exp_nokey", ["digit_transposition"], seed=25)
    sid = ingest(client, case).json()["id"]
    monkeypatch.setattr("app.config.settings.groq_api_key", "your-groq-api-key-here")
    assert client.post(f"/api/v1/sessions/{sid}/explain").status_code == 503
