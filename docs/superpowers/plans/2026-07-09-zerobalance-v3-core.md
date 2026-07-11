# ZeroBalance v3 Core — Position Engine & Drift Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The deterministic core of ZeroBalance v3 (Continuous Reconciliation): an append-only capture-event ledger, a position engine that replays a teller's day into an expected drawer state, stream reconciliation that explains drift against the CBS export exactly, and an oracle that gates it all.

**Architecture:** Capture events (opening float, cash txns, cheques, instruments, corrections, sign-offs-to-come) land in a new hash-chained `capture_events` table, mirroring the existing `audit_ledger` discipline. A pure-Python position engine replays a day's events into `TellerPosition`. Drift detection is **stream reconciliation** — matching the captured cash-txn stream against CBS-posted rows and classifying every unmatched or mismatched row — which is exact and deterministic, so mismatch deltas always sum to the total drift. The v1 matching engine (`app/engine/matching.py`) is NOT modified; it keeps its EOD role. A new stdlib-only day-level oracle (`data/day_generator.py` + `data/ground_truth_v3.py`) gates correctness.

**Tech Stack:** Python 3.12, FastAPI project layout (no new routes in this plan), Pydantic v2, SQLAlchemy 2 + PostgreSQL 16 (compose service `db`), pytest (runs in the `backend` container), stdlib-only oracle in `/data`.

**Plan ① of 3.** Plan ② (sign-off service, declarations, FastAPI routes, rollup report) and Plan ③ (teller capture surfaces, OM board) are written after this plan ships.

**Spec:** `docs/superpowers/specs/2026-07-09-continuous-reconciliation-design.md`

## Global Constraints

- Python 3.12, type hints everywhere, Pydantic v2 models. Ruff rules from `backend/pyproject.toml`: `select = ["E", "F", "I", "UP", "B", "ANN"]`, line-length 100. Run `docker compose exec backend ruff check app tests` before every commit.
- **No new dependencies** (no requirements.txt changes). No new compose services.
- **No ML anywhere in the trust path.** Position engine and reconciliation are pure arithmetic/matching.
- **Never modify** `backend/app/engine/matching.py`, `backend/app/engine/models.py`, `backend/app/service.py`, or existing tables in `backend/schema.sql` — v1 passed its gate. Additions to `schema.sql` are append-only (new statements at end of file).
- **Cash transactions never carry denominations** (forbidden anti-pattern per CLAUDE.md). Only opening-float, cheque (`denominations_out`), and EOD-count events carry denomination dicts.
- Ledger tables are append-only, hash-chained; corrections are new events, never UPDATEs.
- `/data` modules are **stdlib-only** (they must run without a venv).
- Tests run in-container: `docker compose exec backend pytest -q`. Oracle self-check: `python data/ground_truth_v3.py` from the repo root on the host.
- Commit messages: small, per-feature, ending with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Do not commit the spec or this plan file as part of task commits (user holds them uncommitted deliberately).

## Domain primer (read once)

A teller's day: the OM issues an opening cash float; the teller serves customers all day (cash in/out typed into the bank's core banking system, "CBS"); cheque cash-outs and some instruments never reach CBS at all; at end-of-day the drawer is counted and reconciled. v3's idea: capture every drawer-affecting action as an event the moment it happens, continuously compute the **expected** drawer position, and compare the captured cash-txn stream against the CBS CSV export to catch errors within minutes. Two slices of the position matter:

- `cbs_expected` = opening float + captured cash txns — the slice CBS must agree with.
- `expected_cash` = `cbs_expected` + cheque/instrument effects — what should physically be in the drawer.

Drift = `cbs_expected − cbs_cash`. Because reconciliation puts every capture and every CBS row in exactly one bucket (clean match or one classified mismatch), mismatch deltas always sum to the drift — an invariant the oracle checks. Zero-delta errors (wrong account, right amount) are invisible to cash drift by definition; the v1 EOD engine handles those at close.

## File Structure

```
backend/schema.sql                          MODIFY (append capture_events DDL)
backend/app/db_models.py                    MODIFY (add CaptureEventRow)
backend/app/engine/capture_models.py        CREATE (event payload vocabulary)
backend/app/events.py                       CREATE (append/verify/read the event ledger)
backend/app/engine/validation.py            CREATE (capture-time checks, pure)
backend/app/engine/position.py              CREATE (replay events -> TellerPosition)
backend/app/engine/drift.py                 CREATE (stream reconciliation -> DriftReport)
data/day_generator.py                       CREATE (synthetic branch days + fault injectors)
data/ground_truth_v3.py                     CREATE (oracle harness + self-check)
backend/tests/test_capture_models.py        CREATE
backend/tests/test_events.py                CREATE
backend/tests/test_validation.py            CREATE
backend/tests/test_position.py              CREATE
backend/tests/test_drift.py                 CREATE
backend/tests/test_drift_oracle.py          CREATE (the gate)
```

---

### Task 1: `capture_events` table + ORM mapping

**Files:**
- Modify: `backend/schema.sql` (append at end of file)
- Modify: `backend/app/db_models.py` (add one class at end of file)
- Test: `backend/tests/test_events.py` (new file; more tests added in Task 3)

**Interfaces:**
- Consumes: existing `forbid_ledger_mutation()` trigger function (already in schema.sql), existing `Base` in db_models.py.
- Produces: `CaptureEventRow` ORM class with columns `id, branch_code, teller_id, business_date, event_type, payload, at, prev_hash, entry_hash` — Tasks 3+ depend on these exact names.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_events.py`:

```python
"""capture_events ledger tests — needs the compose Postgres (same pattern as
test_api.py: dev DB, synthetic data only, TRUNCATE per test)."""

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy import text as sqltext
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

from app.db import get_engine
from app.db_models import CaptureEventRow

DAY = date(2026, 7, 9)


@pytest.fixture()
def db() -> Iterator[Session]:
    with get_engine().connect() as conn:
        conn.execute(sqltext("TRUNCATE capture_events RESTART IDENTITY"))
        conn.commit()
    with Session(get_engine()) as s:
        yield s


def _seed_row(db: Session) -> None:
    db.add(CaptureEventRow(
        branch_code="KHI-042", teller_id="T-07", business_date=DAY,
        event_type="drift_resolved", payload={"note": "x"},
        prev_hash="GENESIS", entry_hash="h1",
    ))
    db.commit()


def test_insert_and_read_back(db: Session) -> None:
    _seed_row(db)
    row = db.execute(
        sqltext("SELECT event_type, payload->>'note' AS note FROM capture_events")
    ).one()
    assert row.event_type == "drift_resolved"
    assert row.note == "x"


def test_append_only_trigger_blocks_update(db: Session) -> None:
    _seed_row(db)
    with pytest.raises(DatabaseError):
        db.execute(sqltext("UPDATE capture_events SET payload = '{}' WHERE TRUE"))
    db.rollback()


def test_append_only_trigger_blocks_delete(db: Session) -> None:
    _seed_row(db)
    with pytest.raises(DatabaseError):
        db.execute(sqltext("DELETE FROM capture_events WHERE TRUE"))
    db.rollback()


def test_unknown_event_type_rejected(db: Session) -> None:
    db.add(CaptureEventRow(
        branch_code="B", teller_id="T", business_date=DAY,
        event_type="not_a_real_event", payload={},
        prev_hash="GENESIS", entry_hash="h2",
    ))
    with pytest.raises(DatabaseError):
        db.commit()
    db.rollback()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_events.py -q`
Expected: FAIL — `ImportError: cannot import name 'CaptureEventRow'`

- [ ] **Step 3: Append DDL to `backend/schema.sql`**

Add at the very end of the file:

```sql
-- ===== v3: Continuous Reconciliation =====

-- All-day capture-event ledger. APPEND-ONLY, hash-chained (same discipline as
-- audit_ledger; reuses forbid_ledger_mutation). Corrections are new events.
CREATE TABLE capture_events (
    id            BIGSERIAL PRIMARY KEY,
    branch_code   TEXT        NOT NULL,
    teller_id     TEXT        NOT NULL,
    business_date DATE        NOT NULL,
    event_type    TEXT        NOT NULL CHECK (event_type IN (
                      'opening_float_declared', 'cash_txn_captured', 'cheque_captured',
                      'instrument_captured', 'eod_count_entered', 'validation_warned',
                      'override_logged', 'drift_flagged', 'drift_resolved',
                      'correction_logged')),
    payload       JSONB       NOT NULL,
    at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_hash     TEXT        NOT NULL,
    entry_hash    TEXT        NOT NULL UNIQUE
);
CREATE INDEX idx_capture_events_day
    ON capture_events (branch_code, teller_id, business_date, id);

CREATE TRIGGER capture_events_append_only
    BEFORE UPDATE OR DELETE ON capture_events
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();
```

- [ ] **Step 4: Apply the new DDL to the running dev DB**

(initdb only runs schema.sql on a fresh volume, so apply the delta by hand — Bash tool:)

```bash
docker compose exec -T db psql -U zerobalance -d zerobalance -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE capture_events (
    id            BIGSERIAL PRIMARY KEY,
    branch_code   TEXT        NOT NULL,
    teller_id     TEXT        NOT NULL,
    business_date DATE        NOT NULL,
    event_type    TEXT        NOT NULL CHECK (event_type IN (
                      'opening_float_declared', 'cash_txn_captured', 'cheque_captured',
                      'instrument_captured', 'eod_count_entered', 'validation_warned',
                      'override_logged', 'drift_flagged', 'drift_resolved',
                      'correction_logged')),
    payload       JSONB       NOT NULL,
    at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    prev_hash     TEXT        NOT NULL,
    entry_hash    TEXT        NOT NULL UNIQUE
);
CREATE INDEX idx_capture_events_day
    ON capture_events (branch_code, teller_id, business_date, id);
CREATE TRIGGER capture_events_append_only
    BEFORE UPDATE OR DELETE ON capture_events
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();
SQL
```

Expected output: `CREATE TABLE`, `CREATE INDEX`, `CREATE TRIGGER`.

- [ ] **Step 5: Add the ORM mapping**

Append to `backend/app/db_models.py`:

```python
class CaptureEventRow(Base):
    """v3 capture-event ledger row. Append-only (DB trigger); hash-chained."""

    __tablename__ = "capture_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_code: Mapped[str] = mapped_column(Text)
    teller_id: Mapped[str] = mapped_column(Text)
    business_date: Mapped[date] = mapped_column(Date)
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    prev_hash: Mapped[str] = mapped_column(Text)
    entry_hash: Mapped[str] = mapped_column(Text)
```

(All names used here — `BigInteger, Text, Date, JSONB, TIMESTAMP, func, Mapped, mapped_column, date, datetime` — are already imported at the top of db_models.py.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/test_events.py -q`
Expected: 4 passed

- [ ] **Step 7: Lint + commit**

```bash
docker compose exec backend ruff check app tests
git add backend/schema.sql backend/app/db_models.py backend/tests/test_events.py
git commit -m "feat(v3): capture_events append-only ledger table + ORM mapping

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Capture payload models

**Files:**
- Create: `backend/app/engine/capture_models.py`
- Test: `backend/tests/test_capture_models.py`

**Interfaces:**
- Consumes: nothing project-internal (pure Pydantic).
- Produces (used by Tasks 3–9): `VALID_DENOMS`, `Denominations = dict[int, int]`, `denomination_total(denominations) -> int`, models `OpeningFloatDeclared, CashTxnCaptured, ChequeCaptured, InstrumentCaptured, EodCountEntered, ValidationWarned, OverrideLogged, DriftFlagged, DriftResolved, CorrectionLogged`, union `CapturePayload`, and `parse_payload(data: dict) -> CapturePayload`. Every model has an `event_type` Literal discriminator matching the DB CHECK list from Task 1.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_capture_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.engine.capture_models import (
    CashTxnCaptured,
    ChequeCaptured,
    OpeningFloatDeclared,
    denomination_total,
    parse_payload,
)


def test_parse_payload_discriminates() -> None:
    p = parse_payload({"event_type": "cash_txn_captured", "ref": "T001",
                       "account": "0012345678", "txn_type": "cash_in", "amount": 5000})
    assert isinstance(p, CashTxnCaptured)
    assert p.amount == 5000


def test_denomination_total() -> None:
    assert denomination_total({5000: 2, 100: 3}) == 10_300


def test_jsonb_string_keys_coerced() -> None:
    # JSONB round-trips turn int dict keys into strings; validation restores them
    p = parse_payload({"event_type": "opening_float_declared",
                       "denominations": {"5000": 10, "100": 5}, "om_id": "OM-01"})
    assert isinstance(p, OpeningFloatDeclared)
    assert p.denominations == {5000: 10, 100: 5}


def test_invalid_denomination_rejected() -> None:
    with pytest.raises(ValidationError):
        ChequeCaptured(cheque_ref="C1", amount=700, denominations_out={700: 1})


def test_negative_note_count_rejected() -> None:
    with pytest.raises(ValidationError):
        OpeningFloatDeclared(denominations={100: -1}, om_id="OM-01")


def test_amount_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        CashTxnCaptured(ref="T1", account="A", txn_type="cash_in", amount=0)


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_payload({"event_type": "nonsense"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_capture_models.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.engine.capture_models'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/engine/capture_models.py`:

```python
"""Pydantic payloads for v3 capture events — the vocabulary of the event ledger.

Cash transactions NEVER carry denominations (forbidden anti-pattern, CLAUDE.md).
Cheque capture carries denominations_out because it digitizes what the teller
already writes on the back of the cheque. JSONB round-trips turn int dict keys
into strings; Pydantic coerces them back on validation."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator

VALID_DENOMS = frozenset({5000, 1000, 500, 100, 50, 20, 10, 5, 2, 1})

Denominations = dict[int, int]


def denomination_total(denominations: Denominations) -> int:
    return sum(d * n for d, n in denominations.items())


def _check_denoms(v: Denominations) -> Denominations:
    for denom, count in v.items():
        if denom not in VALID_DENOMS:
            raise ValueError(f"invalid denomination {denom}")
        if count < 0:
            raise ValueError(f"negative note count for {denom}")
    return v


class OpeningFloatDeclared(BaseModel):
    """Day anchor: OM-issued float broken down by denomination, dual-signed later."""

    event_type: Literal["opening_float_declared"] = "opening_float_declared"
    denominations: Denominations
    om_id: str

    @field_validator("denominations")
    @classmethod
    def _denoms(cls, v: Denominations) -> Denominations:
        return _check_denoms(v)


class CashTxnCaptured(BaseModel):
    """Mirror of the CBS entry. `ref` must equal the CBS TXN_REF (demo scope:
    ZeroBalance IS the teller UI and generates the ref used at CBS entry)."""

    event_type: Literal["cash_txn_captured"] = "cash_txn_captured"
    ref: str
    account: str
    txn_type: Literal["cash_in", "cash_out"]
    amount: int = Field(gt=0)


class ChequeCaptured(BaseModel):
    """Cheque cash-out: bypasses CBS entirely, affects the drawer directly."""

    event_type: Literal["cheque_captured"] = "cheque_captured"
    cheque_ref: str
    amount: int = Field(gt=0)
    denominations_out: Denominations

    @field_validator("denominations_out")
    @classmethod
    def _denoms(cls, v: Denominations) -> Denominations:
        return _check_denoms(v)


class InstrumentCaptured(BaseModel):
    """Non-CBS counter instrument that moves drawer cash (v3 Plan-1 model:
    instruments are capture-only; CBS reconciliation covers cash txns only)."""

    event_type: Literal["instrument_captured"] = "instrument_captured"
    instrument: Literal["remittance", "raast", "cdm", "bill", "pay_order"]
    ref: str
    direction: Literal["cash_in", "cash_out"]
    amount: int = Field(gt=0)


class EodCountEntered(BaseModel):
    event_type: Literal["eod_count_entered"] = "eod_count_entered"
    denominations: Denominations

    @field_validator("denominations")
    @classmethod
    def _denoms(cls, v: Denominations) -> Denominations:
        return _check_denoms(v)


class ValidationWarned(BaseModel):
    event_type: Literal["validation_warned"] = "validation_warned"
    check: str
    message: str
    capture_ref: str


class OverrideLogged(BaseModel):
    event_type: Literal["override_logged"] = "override_logged"
    check: str
    reason: str
    capture_ref: str


class DriftFlagged(BaseModel):
    event_type: Literal["drift_flagged"] = "drift_flagged"
    cbs_expected: int
    cbs_cash: int
    delta: int
    mismatch_count: int = Field(ge=0)


class DriftResolved(BaseModel):
    event_type: Literal["drift_resolved"] = "drift_resolved"
    note: str


class CorrectionLogged(BaseModel):
    """Corrects an earlier cash_txn_captured amount. Replay applies the LAST
    correction per ref; the original event is never mutated."""

    event_type: Literal["correction_logged"] = "correction_logged"
    ref: str
    corrected_amount: int = Field(gt=0)
    note: str


CapturePayload = Annotated[
    OpeningFloatDeclared
    | CashTxnCaptured
    | ChequeCaptured
    | InstrumentCaptured
    | EodCountEntered
    | ValidationWarned
    | OverrideLogged
    | DriftFlagged
    | DriftResolved
    | CorrectionLogged,
    Field(discriminator="event_type"),
]

_adapter: TypeAdapter[CapturePayload] = TypeAdapter(CapturePayload)


def parse_payload(data: dict) -> CapturePayload:
    """Validate a raw payload dict (e.g. loaded from JSONB) into its typed model."""
    return _adapter.validate_python(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/test_capture_models.py -q`
Expected: 7 passed

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend ruff check app tests
git add backend/app/engine/capture_models.py backend/tests/test_capture_models.py
git commit -m "feat(v3): capture-event payload vocabulary (Pydantic discriminated union)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Event ledger module (append / read / verify)

**Files:**
- Create: `backend/app/events.py`
- Test: `backend/tests/test_events.py` (extend the Task-1 file)

**Interfaces:**
- Consumes: `_entry_hash(prev, actor, action, payload) -> str` from `app/db.py`; `CaptureEventRow` (Task 1); `CapturePayload`, `parse_payload` (Task 2).
- Produces (used by Plan ② routes and Task 9 conceptually): `events_head(db) -> str`, `append_event(db, branch: str, teller: str, business_date: date, payload: CapturePayload) -> CaptureEventRow`, `day_events(db, branch, teller, business_date) -> list[CaptureEventRow]`, `day_payloads(db, branch, teller, business_date) -> list[CapturePayload]`, `verify_events(db) -> tuple[bool, int, str]`.
- **Critical detail:** hash the payload as `payload.model_dump(mode="json")`. `mode="json"` converts int dict keys (denominations) to strings — exactly what JSONB returns on read — so `verify_events` recomputes identical hashes. Hashing `model_dump()` (python mode) breaks verification because `json.dumps(..., sort_keys=True)` orders int keys numerically but string keys lexicographically.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_events.py`:

```python
from app.engine.capture_models import DriftResolved, OpeningFloatDeclared
from app.events import append_event, day_payloads, verify_events


def test_chain_links_and_verifies(db: Session) -> None:
    e1 = append_event(db, "KHI-042", "T-07", DAY,
                      OpeningFloatDeclared(denominations={1000: 5}, om_id="OM-01"))
    db.commit()
    e2 = append_event(db, "KHI-042", "T-07", DAY, DriftResolved(note="ok"))
    db.commit()
    assert e1.prev_hash == "GENESIS"
    assert e2.prev_hash == e1.entry_hash
    ok, n, head = verify_events(db)
    assert ok is True
    assert n == 2
    assert head == e2.entry_hash


def test_verify_survives_jsonb_roundtrip(db: Session) -> None:
    # denominations dict has int keys in Python but string keys after JSONB;
    # hashing model_dump(mode="json") makes both sides identical
    append_event(db, "KHI-042", "T-07", DAY,
                 OpeningFloatDeclared(denominations={5000: 2, 100: 7}, om_id="OM-01"))
    db.commit()
    with Session(get_engine()) as fresh:
        ok, n, _ = verify_events(fresh)
    assert ok is True
    assert n == 1


def test_tampered_chain_fails_verification(db: Session) -> None:
    append_event(db, "KHI-042", "T-07", DAY, DriftResolved(note="real"))
    db.commit()
    # bypass the trigger the same way test_api does: TRUNCATE + re-insert forged row
    with get_engine().connect() as conn:
        conn.execute(sqltext("TRUNCATE capture_events RESTART IDENTITY"))
        conn.execute(sqltext(
            "INSERT INTO capture_events (branch_code, teller_id, business_date, "
            "event_type, payload, prev_hash, entry_hash) VALUES "
            "('KHI-042', 'T-07', '2026-07-09', 'drift_resolved', "
            "'{\"note\": \"forged\", \"event_type\": \"drift_resolved\"}', "
            "'GENESIS', 'not-the-real-hash')"))
        conn.commit()
    ok, _, _ = verify_events(db)
    assert ok is False


def test_day_payloads_filters_by_teller_and_orders(db: Session) -> None:
    append_event(db, "KHI-042", "T-01", DAY,
                 OpeningFloatDeclared(denominations={100: 1}, om_id="OM-01"))
    db.commit()
    append_event(db, "KHI-042", "T-02", DAY,
                 OpeningFloatDeclared(denominations={100: 2}, om_id="OM-01"))
    db.commit()
    payloads = day_payloads(db, "KHI-042", "T-01", DAY)
    assert len(payloads) == 1
    assert isinstance(payloads[0], OpeningFloatDeclared)
    assert payloads[0].denominations == {100: 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec backend pytest tests/test_events.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.events'` (4 Task-1 tests still pass)

- [ ] **Step 3: Write the implementation**

Create `backend/app/events.py`:

```python
"""v3 capture-event ledger. Same append-only + hash-chain discipline as the
audit ledger (db.py): one global chain in insertion order, DB trigger blocks
UPDATE/DELETE, verification walks the whole chain.

Payloads are hashed as model_dump(mode="json") so int dict keys (denominations)
become strings at hash time — matching what JSONB returns — and verification
recomputes identical hashes after a round-trip."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import _entry_hash  # one hashing rule for both ledgers — intentional reuse
from .db_models import CaptureEventRow
from .engine.capture_models import CapturePayload, parse_payload


def events_head(db: Session) -> str:
    row = db.execute(
        select(CaptureEventRow).order_by(CaptureEventRow.id.desc()).limit(1)
    ).scalar_one_or_none()
    return row.entry_hash if row else "GENESIS"


def append_event(db: Session, branch: str, teller: str, business_date: date,
                 payload: CapturePayload) -> CaptureEventRow:
    data = payload.model_dump(mode="json")
    prev = events_head(db)
    h = _entry_hash(prev, f"{branch}/{teller}", payload.event_type, data)
    row = CaptureEventRow(
        branch_code=branch, teller_id=teller, business_date=business_date,
        event_type=payload.event_type, payload=data, prev_hash=prev, entry_hash=h,
    )
    db.add(row)
    return row


def day_events(db: Session, branch: str, teller: str,
               business_date: date) -> list[CaptureEventRow]:
    return list(db.execute(
        select(CaptureEventRow)
        .where(
            CaptureEventRow.branch_code == branch,
            CaptureEventRow.teller_id == teller,
            CaptureEventRow.business_date == business_date,
        )
        .order_by(CaptureEventRow.id)
    ).scalars())


def day_payloads(db: Session, branch: str, teller: str,
                 business_date: date) -> list[CapturePayload]:
    return [parse_payload(r.payload) for r in day_events(db, branch, teller, business_date)]


def verify_events(db: Session) -> tuple[bool, int, str]:
    """Walk the chain; returns (ok, entries_checked, head_hash)."""
    prev = "GENESIS"
    n = 0
    for row in db.execute(select(CaptureEventRow).order_by(CaptureEventRow.id)).scalars():
        if row.prev_hash != prev:
            return False, n, prev
        recomputed = _entry_hash(prev, f"{row.branch_code}/{row.teller_id}",
                                 row.event_type, row.payload)
        if row.entry_hash != recomputed:
            return False, n, prev
        prev = row.entry_hash
        n += 1
    return True, n, prev
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/test_events.py -q`
Expected: 8 passed

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend ruff check app tests
git add backend/app/events.py backend/tests/test_events.py
git commit -m "feat(v3): hash-chained capture-event ledger module (append/read/verify)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Capture-time validation checks

**Files:**
- Create: `backend/app/engine/validation.py`
- Test: `backend/tests/test_validation.py`

**Interfaces:**
- Consumes: `CashTxnCaptured`, `Denominations`, `denomination_total` (Task 2).
- Produces (used by Plan ② routes): `CheckWarning(check: str, message: str)`, `check_denomination_sum(amount, denominations) -> CheckWarning | None`, `check_duplicate(attempt, recent, window_s=120) -> CheckWarning | None` where `recent` is `Sequence[tuple[int, CashTxnCaptured]]` of `(seconds_ago, capture)`, `check_large_amount(amount, threshold=500_000) -> CheckWarning | None`, `run_cash_txn_checks(attempt, recent, *, duplicate_window_s=120, large_amount_threshold=500_000) -> list[CheckWarning]`.
- Spec rule: warnings never block; thresholds are branch-configurable — here they are parameters with defaults, wired to config/API in Plan ②.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_validation.py`:

```python
from app.engine.capture_models import CashTxnCaptured
from app.engine.validation import (
    check_denomination_sum,
    check_duplicate,
    check_large_amount,
    run_cash_txn_checks,
)

CAP = CashTxnCaptured(ref="T001", account="0011223344", txn_type="cash_in", amount=25_000)


def test_denomination_sum_mismatch_warns() -> None:
    w = check_denomination_sum(1500, {1000: 1, 100: 4})
    assert w is not None
    assert w.check == "denomination_sum"


def test_denomination_sum_ok() -> None:
    assert check_denomination_sum(1400, {1000: 1, 100: 4}) is None


def test_duplicate_within_window_warns() -> None:
    prior = CAP.model_copy(update={"ref": "T000"})
    w = check_duplicate(CAP, [(30, prior)])
    assert w is not None
    assert w.check == "duplicate"


def test_duplicate_outside_window_ok() -> None:
    prior = CAP.model_copy(update={"ref": "T000"})
    assert check_duplicate(CAP, [(300, prior)]) is None


def test_different_amount_is_not_duplicate() -> None:
    prior = CAP.model_copy(update={"ref": "T000", "amount": 26_000})
    assert check_duplicate(CAP, [(30, prior)]) is None


def test_large_amount_threshold() -> None:
    assert check_large_amount(500_000) is not None
    assert check_large_amount(499_999) is None


def test_run_cash_txn_checks_collects_all() -> None:
    big = CAP.model_copy(update={"amount": 900_000})
    prior = big.model_copy(update={"ref": "T000"})
    warnings = run_cash_txn_checks(big, [(10, prior)])
    assert {w.check for w in warnings} == {"duplicate", "large_amount"}


def test_clean_capture_no_warnings() -> None:
    assert run_cash_txn_checks(CAP, []) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_validation.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.engine.validation'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/engine/validation.py`:

```python
"""Capture-time validation. Pure and deterministic: warnings never block —
the caller shows them, and any override is logged as its own ledger event
(an override trail is stronger trust than a hard wall worked around on paper).
Thresholds are branch-configurable per the spec: parameters with defaults
here; config/API wiring lands with the routes (Plan 2)."""

from collections.abc import Sequence

from pydantic import BaseModel

from .capture_models import CashTxnCaptured, Denominations, denomination_total

DUPLICATE_WINDOW_S = 120
LARGE_AMOUNT_THRESHOLD = 500_000


class CheckWarning(BaseModel):
    check: str
    message: str


def check_denomination_sum(amount: int, denominations: Denominations) -> CheckWarning | None:
    total = denomination_total(denominations)
    if total != amount:
        return CheckWarning(
            check="denomination_sum",
            message=f"denominations total {total} but typed amount is {amount}",
        )
    return None


def check_duplicate(
    attempt: CashTxnCaptured,
    recent: Sequence[tuple[int, CashTxnCaptured]],
    window_s: int = DUPLICATE_WINDOW_S,
) -> CheckWarning | None:
    """`recent` holds (seconds_ago, capture) pairs for the teller, any order."""
    for age_s, cap in recent:
        same = (cap.account, cap.txn_type, cap.amount) == (
            attempt.account, attempt.txn_type, attempt.amount)
        if age_s <= window_s and same:
            return CheckWarning(
                check="duplicate",
                message=f"same account/amount/type captured {age_s}s ago (ref {cap.ref})",
            )
    return None


def check_large_amount(
    amount: int, threshold: int = LARGE_AMOUNT_THRESHOLD
) -> CheckWarning | None:
    if amount >= threshold:
        return CheckWarning(
            check="large_amount",
            message=f"amount {amount} is at/over the confirm threshold {threshold}",
        )
    return None


def run_cash_txn_checks(
    attempt: CashTxnCaptured,
    recent: Sequence[tuple[int, CashTxnCaptured]],
    *,
    duplicate_window_s: int = DUPLICATE_WINDOW_S,
    large_amount_threshold: int = LARGE_AMOUNT_THRESHOLD,
) -> list[CheckWarning]:
    warnings = [
        check_duplicate(attempt, recent, duplicate_window_s),
        check_large_amount(attempt.amount, large_amount_threshold),
    ]
    return [w for w in warnings if w is not None]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/test_validation.py -q`
Expected: 8 passed

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend ruff check app tests
git add backend/app/engine/validation.py backend/tests/test_validation.py
git commit -m "feat(v3): capture-time validation checks (denomination sum, duplicate, large amount)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Position replay engine

**Files:**
- Create: `backend/app/engine/position.py`
- Test: `backend/tests/test_position.py`

**Interfaces:**
- Consumes: `CapturePayload`, `CashTxnCaptured`, `denomination_total` (Task 2).
- Produces (used by Task 6, Task 9, Plan ②): `TellerPosition(opening_float: int, cbs_expected: int, expected_cash: int, denominated: dict[int, int], events_applied: int)`, `replay(payloads: Sequence[CapturePayload]) -> TellerPosition`, `corrected_cash_captures(payloads) -> list[CashTxnCaptured]`, and module-level `_effect(txn_type: str, amount: int) -> int` (imported by drift.py).
- Semantics: `cbs_expected` = opening float + captured cash txns (the slice CBS must agree with). `expected_cash` = `cbs_expected` + cheque/instrument effects (full drawer). `denominated` tracks only denomination-carrying events (float in, cheque notes out) — partial knowledge, may go negative, no floor. Corrections: last `correction_logged` per ref wins, applied to the capture's amount.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_position.py`:

```python
from app.engine.capture_models import CapturePayload, parse_payload
from app.engine.position import corrected_cash_captures, replay

FLOAT_ = {"event_type": "opening_float_declared",
          "denominations": {1000: 100, 100: 50}, "om_id": "OM-01"}  # = 105_000


def _payloads(*extra: dict) -> list[CapturePayload]:
    return [parse_payload(p) for p in (FLOAT_, *extra)]


def test_replay_opening_float() -> None:
    pos = replay(_payloads())
    assert pos.opening_float == 105_000
    assert pos.cbs_expected == 105_000
    assert pos.expected_cash == 105_000
    assert pos.denominated == {1000: 100, 100: 50}
    assert pos.events_applied == 1


def test_replay_cash_txns_move_both_slices() -> None:
    pos = replay(_payloads(
        {"event_type": "cash_txn_captured", "ref": "T001", "account": "A",
         "txn_type": "cash_in", "amount": 20_000},
        {"event_type": "cash_txn_captured", "ref": "T002", "account": "B",
         "txn_type": "cash_out", "amount": 5_000},
    ))
    assert pos.cbs_expected == 120_000
    assert pos.expected_cash == 120_000


def test_replay_cheque_affects_drawer_not_cbs_slice() -> None:
    pos = replay(_payloads(
        {"event_type": "cheque_captured", "cheque_ref": "C1", "amount": 3_000,
         "denominations_out": {1000: 3}},
    ))
    assert pos.cbs_expected == 105_000
    assert pos.expected_cash == 102_000
    assert pos.denominated[1000] == 97


def test_replay_instrument_affects_drawer_not_cbs_slice() -> None:
    pos = replay(_payloads(
        {"event_type": "instrument_captured", "instrument": "bill", "ref": "B1",
         "direction": "cash_in", "amount": 7_500},
    ))
    assert pos.cbs_expected == 105_000
    assert pos.expected_cash == 112_500


def test_correction_rewrites_captured_amount() -> None:
    payloads = _payloads(
        {"event_type": "cash_txn_captured", "ref": "T001", "account": "A",
         "txn_type": "cash_in", "amount": 20_000},
        {"event_type": "correction_logged", "ref": "T001",
         "corrected_amount": 2_000, "note": "typo"},
    )
    assert replay(payloads).cbs_expected == 107_000
    caps = corrected_cash_captures(payloads)
    assert len(caps) == 1
    assert caps[0].amount == 2_000


def test_last_correction_wins() -> None:
    payloads = _payloads(
        {"event_type": "cash_txn_captured", "ref": "T001", "account": "A",
         "txn_type": "cash_in", "amount": 20_000},
        {"event_type": "correction_logged", "ref": "T001",
         "corrected_amount": 2_000, "note": "first"},
        {"event_type": "correction_logged", "ref": "T001",
         "corrected_amount": 2_500, "note": "second"},
    )
    assert corrected_cash_captures(payloads)[0].amount == 2_500


def test_noncash_events_do_not_move_cash() -> None:
    pos = replay(_payloads(
        {"event_type": "eod_count_entered", "denominations": {1000: 100, 100: 50}},
        {"event_type": "validation_warned", "check": "duplicate",
         "message": "m", "capture_ref": "T001"},
        {"event_type": "drift_resolved", "note": "ok"},
    ))
    assert pos.expected_cash == 105_000
    assert pos.events_applied == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_position.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.engine.position'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/engine/position.py`:

```python
"""Deterministic position engine: replay a day's capture events into the
teller's expected drawer state. Pure arithmetic — no ML, ever (trust path).

Two slices:
  cbs_expected  — opening float + captured cash txns: what CBS must agree with
  expected_cash — cbs_expected + cheque/instrument effects: the full drawer
`denominated` is partial knowledge (only float-in and cheque-notes-out carry
denominations); it may legitimately go negative and is never floored."""

from collections.abc import Sequence

from pydantic import BaseModel, Field

from .capture_models import CapturePayload, CashTxnCaptured, denomination_total


class TellerPosition(BaseModel):
    opening_float: int = 0
    cbs_expected: int = 0
    expected_cash: int = 0
    denominated: dict[int, int] = Field(default_factory=dict)
    events_applied: int = 0


def _effect(txn_type: str, amount: int) -> int:
    return amount if txn_type == "cash_in" else -amount


def corrected_cash_captures(payloads: Sequence[CapturePayload]) -> list[CashTxnCaptured]:
    """Cash captures with corrections applied (last correction_logged per ref wins)."""
    corrections: dict[str, int] = {}
    for p in payloads:
        if p.event_type == "correction_logged":
            corrections[p.ref] = p.corrected_amount
    out: list[CashTxnCaptured] = []
    for p in payloads:
        if p.event_type == "cash_txn_captured":
            out.append(p.model_copy(update={"amount": corrections.get(p.ref, p.amount)}))
    return out


def replay(payloads: Sequence[CapturePayload]) -> TellerPosition:
    pos = TellerPosition()
    corrected = {c.ref: c for c in corrected_cash_captures(payloads)}
    for p in payloads:
        pos.events_applied += 1
        if p.event_type == "opening_float_declared":
            total = denomination_total(p.denominations)
            pos.opening_float += total
            pos.cbs_expected += total
            pos.expected_cash += total
            for denom, count in p.denominations.items():
                pos.denominated[denom] = pos.denominated.get(denom, 0) + count
        elif p.event_type == "cash_txn_captured":
            eff = _effect(p.txn_type, corrected[p.ref].amount)
            pos.cbs_expected += eff
            pos.expected_cash += eff
        elif p.event_type == "cheque_captured":
            pos.expected_cash -= p.amount
            for denom, count in p.denominations_out.items():
                pos.denominated[denom] = pos.denominated.get(denom, 0) - count
        elif p.event_type == "instrument_captured":
            pos.expected_cash += _effect(p.direction, p.amount)
        # eod_count_entered, validation_warned, override_logged, drift_flagged,
        # drift_resolved, correction_logged: no direct cash effect
    return pos
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/test_position.py -q`
Expected: 7 passed

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend ruff check app tests
git add backend/app/engine/position.py backend/tests/test_position.py
git commit -m "feat(v3): position replay engine (expected drawer state from capture events)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Drift reconciliation engine

**Files:**
- Create: `backend/app/engine/drift.py`
- Test: `backend/tests/test_drift.py`

**Interfaces:**
- Consumes: `CashTxnCaptured` (Task 2); `TellerPosition`, `_effect` (Task 5); `SessionInput`, `TxnInput` from `app/engine/models.py` and `system_cash` from `app/engine/matching.py` (existing v1 code — read-only reuse).
- Produces (used by Task 9 and Plan ②): `MismatchKind = Literal["amount_mismatch", "type_mismatch", "uncaptured_post", "unposted_capture"]`, `Mismatch(kind, capture_ref: str | None, cbs_ref: str | None, delta: int, detail: dict[str, int | str])`, `DriftReport(cbs_expected: int, cbs_cash: int, delta: int, mismatches: list[Mismatch])`, `reconcile(position: TellerPosition, captures: Sequence[CashTxnCaptured], cbs_txns: Sequence[TxnInput]) -> DriftReport`.
- Semantics: every capture and every plain CBS row lands in exactly one bucket (clean match or one mismatch), so `sum(m.delta) == report.delta` always (`delta` = `cbs_expected − cbs_cash`; each mismatch `delta` = capture effect − CBS effect). CBS reversal rows and the rows they reverse net to zero and are excluded from matching. Matching: pass 1 by exact ref; pass 2 pairs leftover refs by `(account, txn_type, amount)`; leftovers are one-sided (`unposted_capture` / `uncaptured_post`). An `uncaptured_post` whose attributes equal some capture gets `detail["possible_duplicate_of"]` as a hint. Zero-delta errors (wrong account) are out of scope here — the v1 EOD engine owns them.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_drift.py`:

```python
from app.engine.capture_models import CapturePayload, parse_payload
from app.engine.drift import DriftReport, reconcile
from app.engine.models import TxnInput
from app.engine.position import corrected_cash_captures, replay

FLOAT_ = {"event_type": "opening_float_declared",
          "denominations": {1000: 100}, "om_id": "OM-01"}  # = 100_000


def cap(ref: str, account: str, txn_type: str, amount: int) -> dict:
    return {"event_type": "cash_txn_captured", "ref": ref, "account": account,
            "txn_type": txn_type, "amount": amount}


def cbs(ref: str, account: str, txn_type: str, amount: int,
        reverses: str | None = None) -> TxnInput:
    return TxnInput(ref=ref, account=account, txn_type=txn_type, amount=amount,
                    reverses=reverses)


def run(cap_dicts: list[dict], cbs_txns: list[TxnInput]) -> DriftReport:
    payloads: list[CapturePayload] = [parse_payload(p) for p in [FLOAT_, *cap_dicts]]
    pos = replay(payloads)
    return reconcile(pos, corrected_cash_captures(payloads), cbs_txns)


def test_clean_streams_no_mismatches() -> None:
    r = run([cap("T1", "A", "cash_in", 5000)], [cbs("T1", "A", "cash_in", 5000)])
    assert r.delta == 0
    assert r.mismatches == []


def test_amount_mismatch_extra_digit() -> None:
    r = run([cap("T1", "A", "cash_in", 1000)], [cbs("T1", "A", "cash_in", 10_000)])
    assert r.delta == -9_000
    [m] = r.mismatches
    assert m.kind == "amount_mismatch"
    assert m.capture_ref == "T1" and m.cbs_ref == "T1"
    assert m.delta == -9_000
    assert m.detail == {"captured_amount": 1000, "posted_amount": 10_000}


def test_type_mismatch_miskey() -> None:
    r = run([cap("T1", "A", "cash_in", 5000)], [cbs("T1", "A", "cash_out", 5000)])
    assert r.delta == 10_000
    [m] = r.mismatches
    assert m.kind == "type_mismatch"
    assert m.delta == 10_000


def test_uncaptured_post_with_duplicate_hint() -> None:
    r = run(
        [cap("T1", "A", "cash_in", 5000)],
        [cbs("T1", "A", "cash_in", 5000), cbs("T1D", "A", "cash_in", 5000)],
    )
    assert r.delta == -5_000
    [m] = r.mismatches
    assert m.kind == "uncaptured_post"
    assert m.cbs_ref == "T1D"
    assert m.detail["possible_duplicate_of"] == "T1"


def test_unposted_capture() -> None:
    r = run([cap("T1", "A", "cash_out", 2000)], [])
    assert r.delta == -2_000
    [m] = r.mismatches
    assert m.kind == "unposted_capture"
    assert m.capture_ref == "T1"
    assert m.delta == -2_000


def test_attribute_match_when_refs_differ() -> None:
    # teller ref != CBS ref but same (account, type, amount): clean pair
    r = run([cap("X9", "A", "cash_in", 5000)], [cbs("T1", "A", "cash_in", 5000)])
    assert r.delta == 0
    assert r.mismatches == []


def test_cbs_reversal_pair_nets_out_of_matching() -> None:
    # CBS posted T1 then reversed it; teller's capture still stands -> drift +5000
    r = run(
        [cap("T1", "A", "cash_in", 5000)],
        [cbs("T1", "A", "cash_in", 5000), cbs("R1", "A", "reversal", 5000, reverses="T1")],
    )
    assert r.delta == 5_000
    [m] = r.mismatches
    assert m.kind == "unposted_capture"


def test_mismatch_deltas_always_sum_to_drift() -> None:
    r = run(
        [cap("T1", "A", "cash_in", 1000), cap("T2", "B", "cash_out", 700)],
        [cbs("T1", "A", "cash_in", 10_000), cbs("T3", "C", "cash_in", 400)],
    )
    assert sum(m.delta for m in r.mismatches) == r.delta
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec backend pytest tests/test_drift.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.engine.drift'`

- [ ] **Step 3: Write the implementation**

Create `backend/app/engine/drift.py`:

```python
"""Drift detection = deterministic stream reconciliation: the day's cash
captures vs the CBS export. Every capture and every plain CBS row lands in
exactly one bucket (clean match or one classified mismatch), so mismatch
deltas always sum to the total drift delta — an invariant the oracle checks.

CBS reversal rows and the rows they reverse net to zero cash effect and are
excluded from matching. Zero-delta errors (wrong account, right amount) are
invisible to cash drift by definition — the v1 engine handles them at EOD."""

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field

from .capture_models import CashTxnCaptured
from .matching import system_cash
from .models import SessionInput, TxnInput
from .position import TellerPosition, _effect

MismatchKind = Literal[
    "amount_mismatch", "type_mismatch", "uncaptured_post", "unposted_capture"
]


class Mismatch(BaseModel):
    kind: MismatchKind
    capture_ref: str | None = None
    cbs_ref: str | None = None
    delta: int  # capture effect minus CBS effect
    detail: dict[str, int | str] = Field(default_factory=dict)


class DriftReport(BaseModel):
    cbs_expected: int
    cbs_cash: int
    delta: int  # cbs_expected - cbs_cash == sum of mismatch deltas
    mismatches: list[Mismatch]


def reconcile(
    position: TellerPosition,
    captures: Sequence[CashTxnCaptured],
    cbs_txns: Sequence[TxnInput],
) -> DriftReport:
    cbs_cash = system_cash(SessionInput(
        opening_float=position.opening_float, counted_cash=0, txns=list(cbs_txns),
    ))
    reversed_refs = {t.reverses for t in cbs_txns if t.reverses}
    plain = [t for t in cbs_txns
             if t.txn_type != "reversal" and t.ref not in reversed_refs]

    cbs_by_ref = {t.ref: t for t in plain}
    mismatches: list[Mismatch] = []
    unmatched_caps: list[CashTxnCaptured] = []
    matched_cbs: set[str] = set()

    # pass 1: exact-ref matching (demo scope: capture ref == CBS TXN_REF)
    for capture in sorted(captures, key=lambda c: c.ref):
        posted = cbs_by_ref.get(capture.ref)
        if posted is None:
            unmatched_caps.append(capture)
            continue
        matched_cbs.add(posted.ref)
        cap_eff = _effect(capture.txn_type, capture.amount)
        cbs_eff = _effect(posted.txn_type, posted.amount)
        if capture.txn_type != posted.txn_type:
            mismatches.append(Mismatch(
                kind="type_mismatch", capture_ref=capture.ref, cbs_ref=posted.ref,
                delta=cap_eff - cbs_eff,
                detail={"captured_type": capture.txn_type,
                        "posted_type": posted.txn_type, "amount": capture.amount},
            ))
        elif capture.amount != posted.amount:
            mismatches.append(Mismatch(
                kind="amount_mismatch", capture_ref=capture.ref, cbs_ref=posted.ref,
                delta=cap_eff - cbs_eff,
                detail={"captured_amount": capture.amount,
                        "posted_amount": posted.amount},
            ))

    # pass 2: leftover refs paired by (account, type, amount) — clean pairs
    by_key: dict[tuple[str, str, int], list[TxnInput]] = {}
    for t in sorted((x for x in plain if x.ref not in matched_cbs), key=lambda t: t.ref):
        by_key.setdefault((t.account, t.txn_type, t.amount), []).append(t)
    still_unmatched: list[CashTxnCaptured] = []
    for capture in unmatched_caps:
        bucket = by_key.get((capture.account, capture.txn_type, capture.amount))
        if bucket:
            matched_cbs.add(bucket.pop(0).ref)
        else:
            still_unmatched.append(capture)

    # pass 3: one-sided leftovers
    for capture in still_unmatched:
        mismatches.append(Mismatch(
            kind="unposted_capture", capture_ref=capture.ref,
            delta=_effect(capture.txn_type, capture.amount),
            detail={"account": capture.account, "amount": capture.amount},
        ))
    for t in sorted((x for x in plain if x.ref not in matched_cbs), key=lambda t: t.ref):
        detail: dict[str, int | str] = {"account": t.account, "amount": t.amount}
        twin = next((c.ref for c in captures
                     if (c.account, c.txn_type, c.amount)
                     == (t.account, t.txn_type, t.amount)), None)
        if twin is not None:
            detail["possible_duplicate_of"] = twin
        mismatches.append(Mismatch(
            kind="uncaptured_post", cbs_ref=t.ref,
            delta=-_effect(t.txn_type, t.amount), detail=detail,
        ))

    return DriftReport(
        cbs_expected=position.cbs_expected, cbs_cash=cbs_cash,
        delta=position.cbs_expected - cbs_cash, mismatches=mismatches,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec backend pytest tests/test_drift.py -q`
Expected: 8 passed

- [ ] **Step 5: Run the whole backend suite (no v1 regressions)**

Run: `docker compose exec backend pytest -q`
Expected: all tests pass (v1 suites untouched and green)

- [ ] **Step 6: Lint + commit**

```bash
docker compose exec backend ruff check app tests
git add backend/app/engine/drift.py backend/tests/test_drift.py
git commit -m "feat(v3): drift reconciliation engine (captured stream vs CBS export)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: v3 day generator (synthetic branch days + fault injectors)

**Files:**
- Create: `data/day_generator.py`
- Test: via `data/ground_truth_v3.py` self-check (Task 8) — this task only needs the module to import and produce a clean day; full checks land in Task 8. Quick smoke test in Step 4.

**Interfaces:**
- Consumes: `Txn`, `_account`, `_amount` from `data/generator.py` (existing, stdlib-only).
- Produces (used by Task 8 and Task 9): `FAULTS: tuple[str, ...]` (6 kinds), `FAULT_TO_MISMATCH: dict[str, str]`, `DayFault(kind: str, refs: list[str], delta: int, detail: dict)`, `DayCase(case_id, branch, teller, business_date, opening_denoms: dict[int, int], captures: list[dict], posted: list[Txn], faults: list[DayFault], drift_delta: int)`, `make_day(case_id: str, fault_kinds: list[str], seed: int) -> DayCase`.
- Rules: stdlib-only. `captures` are raw payload dicts (backend validates them via `parse_payload`); `captures[0]` is always the opening-float declaration. Fault victims are distinct cash-txn refs; injectors locate rows by ref (never by stored index) so multiple injections compose safely. `drift_delta = sum(f.delta for f in faults)` and each `delta` is capture-effect − CBS-effect.

- [ ] **Step 1: Write the implementation**

Create `data/day_generator.py`:

```python
"""Synthetic branch-day generator for the v3 continuous-reconciliation oracle.

A DayCase holds two streams for one teller-day:
  captures: chronological capture-event payload dicts (what the teller recorded)
  posted:   CBS-side rows (reuses generator.Txn) — the CSV-export view
A clean day has mirrored cash streams (same refs); each injector perturbs one
side. Cheques and instruments are capture-only by design (they never hit CBS).
Engines may read: opening_denoms, captures, posted. Never faults/drift_delta.

Stdlib-only on purpose, like generator.py: the oracle runs anywhere."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from random import Random

from generator import Txn, _account, _amount

FAULTS: tuple[str, ...] = (
    "cbs_extra_digit",
    "cbs_transposition",
    "cbs_duplicate_post",
    "cbs_miskey_type",
    "skipped_capture",
    "unposted_capture",
)

# what a correct reconciliation engine should call each fault
FAULT_TO_MISMATCH: dict[str, str] = {
    "cbs_extra_digit": "amount_mismatch",
    "cbs_transposition": "amount_mismatch",
    "cbs_duplicate_post": "uncaptured_post",
    "cbs_miskey_type": "type_mismatch",
    "skipped_capture": "uncaptured_post",
    "unposted_capture": "unposted_capture",
}

OPENING_DENOMS: tuple[int, ...] = (5000, 1000, 500, 100, 50)


@dataclass
class DayFault:
    kind: str
    refs: list[str]                 # culprit ref(s), capture and/or CBS side
    delta: int                      # contribution to (cbs_expected - cbs_cash)
    detail: dict[str, int | str] = field(default_factory=dict)


@dataclass
class DayCase:
    case_id: str
    branch: str
    teller: str
    business_date: str
    opening_denoms: dict[int, int]
    captures: list[dict]            # payload dicts, chronological; [0] is the float
    posted: list[Txn]               # CBS export view
    faults: list[DayFault] = field(default_factory=list)
    drift_delta: int = 0            # truth: cbs_expected - cbs_cash


def _eff(txn_type: str, amount: int) -> int:
    return amount if txn_type == "cash_in" else -amount


def _extra_digit(amount: int, rng: Random) -> int:
    """Duplicate one digit of `amount` (e.g. 1000 -> 10000): classic extra-key typo."""
    s = str(amount)
    p = rng.randrange(1, len(s) + 1)     # insert after position p-1: no leading zero
    return int(s[:p] + s[p - 1] + s[p:])


def _transpose(amount: int, rng: Random) -> int | None:
    """Swap one pair of adjacent unequal digits; None if no legal swap exists."""
    s = str(amount)
    swaps = [p for p in range(len(s) - 1)
             if s[p] != s[p + 1] and not (p == 0 and s[p + 1] == "0")]
    if not swaps:
        return None
    p = rng.choice(swaps)
    return int(s[:p] + s[p + 1] + s[p] + s[p + 2:])


def _posted_index(case: DayCase, ref: str) -> int:
    for i, t in enumerate(case.posted):
        if t.ref == ref:
            return i
    raise KeyError(ref)


def _cash_capture(case: DayCase, ref: str) -> dict:
    for c in case.captures:
        if c.get("event_type") == "cash_txn_captured" and c["ref"] == ref:
            return c
    raise KeyError(ref)


def _inject_cbs_extra_digit(case: DayCase, ref: str, rng: Random) -> None:
    i = _posted_index(case, ref)
    t = case.posted[i]
    bad = _extra_digit(t.amount, rng)
    case.posted[i] = replace(t, amount=bad)
    case.faults.append(DayFault(
        kind="cbs_extra_digit", refs=[ref],
        delta=_eff(t.txn_type, t.amount) - _eff(t.txn_type, bad),
        detail={"captured_amount": t.amount, "posted_amount": bad}))


def _inject_cbs_transposition(case: DayCase, ref: str, rng: Random) -> None:
    i = _posted_index(case, ref)
    t = case.posted[i]
    amount = t.amount
    bad = _transpose(amount, rng)
    while bad is None:                   # amount like 1000 has no legal swap: redraw
        amount = _amount(rng)
        bad = _transpose(amount, rng)
    if amount != t.amount:               # re-seat both sides on the new amount
        _cash_capture(case, ref)["amount"] = amount
        t = replace(t, amount=amount)
    case.posted[i] = replace(t, amount=bad)
    case.faults.append(DayFault(
        kind="cbs_transposition", refs=[ref],
        delta=_eff(t.txn_type, amount) - _eff(t.txn_type, bad),
        detail={"captured_amount": amount, "posted_amount": bad}))


def _inject_cbs_duplicate_post(case: DayCase, ref: str, rng: Random) -> None:
    t = case.posted[_posted_index(case, ref)]
    dup = replace(t, ref=t.ref + "D")
    case.posted.append(dup)
    case.faults.append(DayFault(
        kind="cbs_duplicate_post", refs=[dup.ref],
        delta=-_eff(t.txn_type, t.amount),
        detail={"duplicate_of": t.ref, "amount": t.amount}))


def _inject_cbs_miskey_type(case: DayCase, ref: str, rng: Random) -> None:
    i = _posted_index(case, ref)
    t = case.posted[i]
    flipped = "cash_out" if t.txn_type == "cash_in" else "cash_in"
    case.posted[i] = replace(t, txn_type=flipped)
    case.faults.append(DayFault(
        kind="cbs_miskey_type", refs=[ref],
        delta=2 * _eff(t.txn_type, t.amount),   # t.txn_type is the CAPTURED type
        detail={"captured_type": t.txn_type, "posted_type": flipped,
                "amount": t.amount}))


def _inject_skipped_capture(case: DayCase, ref: str, rng: Random) -> None:
    t = case.posted[_posted_index(case, ref)]
    case.captures.remove(_cash_capture(case, ref))
    case.faults.append(DayFault(
        kind="skipped_capture", refs=[ref],
        delta=-_eff(t.txn_type, t.amount), detail={"amount": t.amount}))


def _inject_unposted_capture(case: DayCase, ref: str, rng: Random) -> None:
    t = case.posted.pop(_posted_index(case, ref))
    case.faults.append(DayFault(
        kind="unposted_capture", refs=[ref],
        delta=_eff(t.txn_type, t.amount), detail={"amount": t.amount}))


_INJECTORS = {
    "cbs_extra_digit": _inject_cbs_extra_digit,
    "cbs_transposition": _inject_cbs_transposition,
    "cbs_duplicate_post": _inject_cbs_duplicate_post,
    "cbs_miskey_type": _inject_cbs_miskey_type,
    "skipped_capture": _inject_skipped_capture,
    "unposted_capture": _inject_unposted_capture,
}


def make_day(case_id: str, fault_kinds: list[str], seed: int) -> DayCase:
    rng = Random(seed)
    opening = {d: rng.randrange(10, 60) for d in OPENING_DENOMS}

    n_txns = rng.randrange(12, 21)
    accounts = [_account(rng) for _ in range(max(4, n_txns // 3))]
    captures: list[dict] = [{"event_type": "opening_float_declared",
                             "denominations": dict(opening), "om_id": "OM-01"}]
    posted: list[Txn] = []
    for i in range(n_txns):
        minutes = 9 * 60 + i * 8
        t = Txn(ref=f"T{i:03d}", account=rng.choice(accounts),
                txn_type=rng.choice(("cash_in", "cash_out")),
                amount=_amount(rng),
                time=f"{minutes // 60:02d}:{minutes % 60:02d}:00")
        captures.append({"event_type": "cash_txn_captured", "ref": t.ref,
                         "account": t.account, "txn_type": t.txn_type,
                         "amount": t.amount})
        posted.append(t)

    for j in range(rng.randrange(1, 3)):        # cheque cash-outs: capture-only
        amt = max(100, _amount(rng) // 100 * 100)
        notes = {1000: amt // 1000}
        rem = amt % 1000
        if rem:
            notes[100] = rem // 100
        captures.append({"event_type": "cheque_captured", "cheque_ref": f"CHQ{j:02d}",
                         "amount": amt, "denominations_out": notes})
    if rng.random() < 0.7:                      # occasional non-CBS instrument
        captures.append({"event_type": "instrument_captured", "instrument": "bill",
                         "ref": "B00", "direction": "cash_in",
                         "amount": _amount(rng)})

    case = DayCase(case_id=case_id, branch="KHI-042", teller="T-07",
                   business_date="2026-07-09", opening_denoms=opening,
                   captures=captures, posted=posted)

    victim_refs = [f"T{i:03d}" for i in rng.sample(range(n_txns), len(fault_kinds))]
    for kind, ref in zip(fault_kinds, victim_refs, strict=True):
        _INJECTORS[kind](case, ref, rng)
    case.drift_delta = sum(f.delta for f in case.faults)
    return case
```

- [ ] **Step 2: Verify note-count math in `make_day` cheques**

`amt` is a positive multiple of 100, so `notes = {1000: amt // 1000}` plus `{100: (amt % 1000) // 100}` always sums exactly to `amt` — the generated cheque passes `check_denomination_sum` by construction. No action; this is a review checkpoint.

- [ ] **Step 3: Smoke-test importability and a clean day (host, repo root)**

Run: `python -c "import sys; sys.path.insert(0, 'data'); from day_generator import make_day; c = make_day('smoke', [], 7); print(len(c.captures), len(c.posted), c.drift_delta, c.faults)"`
Expected: prints something like `17 14 0 []` (counts vary with seed; `drift_delta` MUST be `0`, `faults` MUST be `[]`)

- [ ] **Step 4: Smoke-test one fault of each kind**

Run: `python -c "import sys; sys.path.insert(0, 'data'); from day_generator import FAULTS, make_day; [print(k, make_day('s', [k], 42).drift_delta) for k in FAULTS]"`
Expected: six lines; every kind prints a **non-zero** delta except none (all six non-zero; `cbs_extra_digit` and `cbs_transposition` deltas differ from 0 by construction).

- [ ] **Step 5: Lint + commit**

```bash
docker compose exec backend ruff check /data/day_generator.py
git add data/day_generator.py
git commit -m "feat(v3): synthetic branch-day generator with 6 drift-fault injectors

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: v3 oracle harness + self-check

**Files:**
- Create: `data/ground_truth_v3.py`

**Interfaces:**
- Consumes: `FAULTS`, `FAULT_TO_MISMATCH`, `DayCase`, `make_day` (Task 7).
- Produces (used by Task 9): `Prediction(kind: str, refs: tuple[str, ...])`, `EngineFn = Callable[[DayCase], tuple[int, Sequence[Prediction]]]`, `Suite(singles, doubles)`, `Report(single_accuracy, double_accuracy, per_fault, failures)`, `build_suite(seed=2026) -> Suite`, `evaluate(engine, suite=None) -> Report`, `passes_gate(report) -> bool` (≥0.90 single, ≥0.70 double).
- Correctness definition: a fault is matched when a prediction has kind `FAULT_TO_MISMATCH[fault.kind]` and ref overlap with `fault.refs`; a case is correct only if **every** fault is matched **and** the predicted delta equals `case.drift_delta`.

- [ ] **Step 1: Write the implementation**

Create `data/ground_truth_v3.py`:

```python
"""ZeroBalance v3 test oracle — continuous-reconciliation drift detection.

An engine is a callable DayCase -> (delta, predictions). A fault counts as
matched when a prediction has the fault's expected mismatch kind
(FAULT_TO_MISMATCH) and overlapping refs. A case is correct only if every
fault is matched AND the predicted delta equals the truth drift_delta.
Gate: >=90% single-fault, >=70% double-fault. Never loosen this oracle to
make an engine pass — flag the mismatch instead.

Run `python data/ground_truth_v3.py` for the self-check (determinism, delta
math, clean-day zero, fault coverage). Exits non-zero on failure."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from random import Random

from day_generator import FAULT_TO_MISMATCH, FAULTS, DayCase, make_day

SINGLES_PER_FAULT = 20
DOUBLE_CASES = 40
SUITE_SEED = 2026


@dataclass(frozen=True)
class Prediction:
    kind: str                      # mismatch kind (see FAULT_TO_MISMATCH values)
    refs: tuple[str, ...] = ()


EngineFn = Callable[[DayCase], tuple[int, Sequence[Prediction]]]


@dataclass
class Suite:
    singles: list[DayCase]
    doubles: list[DayCase]


@dataclass
class Report:
    single_accuracy: float
    double_accuracy: float
    per_fault: dict[str, float]
    failures: list[str] = field(default_factory=list)


def build_suite(seed: int = SUITE_SEED) -> Suite:
    rng = Random(seed)
    singles = [make_day(f"single_{kind}_{n:02d}", [kind], seed=rng.randrange(10**9))
               for kind in FAULTS for n in range(SINGLES_PER_FAULT)]
    doubles = [make_day(f"double_{n:02d}", rng.sample(FAULTS, 2),
                        seed=rng.randrange(10**9))
               for n in range(DOUBLE_CASES)]
    return Suite(singles=singles, doubles=doubles)


def _case_correct(case: DayCase, delta: int, preds: Sequence[Prediction]) -> bool:
    if delta != case.drift_delta:
        return False
    for fault in case.faults:
        want = FAULT_TO_MISMATCH[fault.kind]
        if not any(p.kind == want and set(p.refs) & set(fault.refs) for p in preds):
            return False
    return True


def evaluate(engine: EngineFn, suite: Suite | None = None) -> Report:
    suite = suite or build_suite()
    failures: list[str] = []
    fault_total: dict[str, int] = dict.fromkeys(FAULTS, 0)
    fault_hit: dict[str, int] = dict.fromkeys(FAULTS, 0)

    single_hits = 0
    for case in suite.singles:
        kind = case.faults[0].kind
        fault_total[kind] += 1
        delta, preds = engine(case)
        if _case_correct(case, delta, preds):
            single_hits += 1
            fault_hit[kind] += 1
        else:
            failures.append(case.case_id)

    double_hits = 0
    for case in suite.doubles:
        delta, preds = engine(case)
        if _case_correct(case, delta, preds):
            double_hits += 1
        else:
            failures.append(case.case_id)

    return Report(
        single_accuracy=single_hits / len(suite.singles),
        double_accuracy=double_hits / len(suite.doubles),
        per_fault={k: fault_hit[k] / fault_total[k] for k in FAULTS},
        failures=failures,
    )


def passes_gate(report: Report) -> bool:
    return report.single_accuracy >= 0.90 and report.double_accuracy >= 0.70


# --- self-check ---------------------------------------------------------------


def _self_check() -> list[str]:
    problems: list[str] = []

    a, b = build_suite(SUITE_SEED), build_suite(SUITE_SEED)
    if [asdict(c) for c in a.singles + a.doubles] != [asdict(c) for c in b.singles + b.doubles]:
        problems.append("suite is not deterministic for a fixed seed")

    clean = make_day("clean", [], seed=7)
    if clean.faults or clean.drift_delta != 0:
        problems.append("clean day must have no faults and zero drift")
    if clean.captures[0].get("event_type") != "opening_float_declared":
        problems.append("captures[0] must be the opening float declaration")

    for case in a.singles + a.doubles:
        if sum(f.delta for f in case.faults) != case.drift_delta:
            problems.append(f"{case.case_id}: fault deltas do not sum to drift_delta")
        for fault in case.faults:
            if fault.kind not in FAULT_TO_MISMATCH:
                problems.append(f"{case.case_id}: unknown fault kind {fault.kind}")
            if fault.delta == 0:
                problems.append(f"{case.case_id}: fault {fault.kind} has zero delta")

    seen = {c.faults[0].kind for c in a.singles}
    if seen != set(FAULTS):
        problems.append(f"missing single-fault coverage: {set(FAULTS) - seen}")

    return problems


if __name__ == "__main__":
    issues = _self_check()
    suite = build_suite()
    n = len(suite.singles) + len(suite.doubles)
    if issues:
        print(f"ground_truth_v3 self-check FAILED ({len(issues)} problems):")
        for p in issues:
            print(f"  - {p}")
        sys.exit(1)
    print(f"ground_truth_v3 self-check PASSED ({n} cases, determinism, delta math, coverage)")
```

- [ ] **Step 2: Run the self-check**

Run: `python data/ground_truth_v3.py` (from repo root; `data/` modules import each other so run with cwd=data if needed: `cd data && python ground_truth_v3.py && cd ..`)
Expected: `ground_truth_v3 self-check PASSED (160 cases, determinism, delta math, coverage)` — exit code 0

- [ ] **Step 3: Lint + commit**

```bash
docker compose exec backend ruff check /data/ground_truth_v3.py
git add data/ground_truth_v3.py
git commit -m "feat(v3): drift-detection oracle with self-check (90/70 gate)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: Oracle gate test (engine ↔ oracle wiring)

**Files:**
- Test: `backend/tests/test_drift_oracle.py`

**Interfaces:**
- Consumes: `make_day`, `build_suite`, `evaluate`, `passes_gate`, `Prediction` (Tasks 7–8, importable because conftest.py puts `/data` on sys.path); `parse_payload` (Task 2); `replay`, `corrected_cash_captures` (Task 5); `reconcile` (Task 6); `TxnInput` (existing).
- Produces: the v3 gate. **UI/route work in Plan ② is blocked until this passes.**

- [ ] **Step 1: Write the test (this is the deliverable — engine already exists)**

Create `backend/tests/test_drift_oracle.py`:

```python
"""v3 gate: position replay + stream reconciliation measured against the day
oracle. Never loosen the oracle to make this pass — flag the mismatch."""

from day_generator import DayCase, make_day
from ground_truth_v3 import Prediction, build_suite, evaluate, passes_gate

from app.engine.capture_models import parse_payload
from app.engine.drift import reconcile
from app.engine.models import TxnInput
from app.engine.position import corrected_cash_captures, replay


def run_engine(case: DayCase) -> tuple[int, list[Prediction]]:
    payloads = [parse_payload(c) for c in case.captures]
    position = replay(payloads)
    captures = corrected_cash_captures(payloads)
    cbs = [TxnInput(ref=t.ref, account=t.account, txn_type=t.txn_type,
                    amount=t.amount, time=t.time, narration=t.narration,
                    reverses=t.reverses) for t in case.posted]
    report = reconcile(position, captures, cbs)
    preds = [Prediction(kind=m.kind,
                        refs=tuple(r for r in (m.capture_ref, m.cbs_ref) if r))
             for m in report.mismatches]
    return report.delta, preds


def test_clean_day_zero_drift_no_mismatches() -> None:
    delta, preds = run_engine(make_day("clean", [], seed=11))
    assert delta == 0
    assert preds == []


def test_engine_is_deterministic() -> None:
    case = make_day("det", ["cbs_extra_digit"], seed=12)
    assert run_engine(case) == run_engine(case)


def test_v3_gate() -> None:
    report = evaluate(run_engine, build_suite())
    assert report.single_accuracy >= 0.90, (report.per_fault, report.failures[:10])
    assert report.double_accuracy >= 0.70, report.failures[:10]
    assert passes_gate(report)
```

- [ ] **Step 2: Run the gate**

Run: `docker compose exec backend pytest tests/test_drift_oracle.py -v`
Expected: 3 passed. Stream reconciliation is exact matching, so `single_accuracy` should be at or near 1.00 and `double_accuracy` ≥ 0.95. If the gate FAILS: debug the engine or the generator — **do not touch the gate numbers or `_case_correct`**.

- [ ] **Step 3: Run the entire suite one more time**

Run: `docker compose exec backend pytest -q`
Expected: all tests pass (v1 + v3)

- [ ] **Step 4: Lint + commit**

```bash
docker compose exec backend ruff check app tests
git add backend/tests/test_drift_oracle.py
git commit -m "test(v3): oracle gate for drift reconciliation (90/70) — passing

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Completion criteria

1. `docker compose exec backend pytest -q` — everything green, including `test_drift_oracle.py`.
2. `python data/ground_truth_v3.py` — self-check PASSED.
3. `docker compose exec backend ruff check app tests` — clean.
4. No diffs in `matching.py`, `models.py` (engine), `service.py`, or existing schema.sql tables.
5. Update `/phases/phase_9.md` per CLAUDE.md's phase workflow (goal/steps/commands/expected → achieved) — write it before starting Task 1, update after Task 9.

## Deferred to Plan ② (do NOT build here)

Sign-off service and dual-signature state machine; FastAPI routes for captures/positions/drift; CBS CSV ingest endpoint/watcher (parsing reuses the existing `parse_pibas_csv` in `app/service.py`); `drift_flagged`/`override_logged` event emission wiring; EOD close flow and excess-ledger objects; daily-close PDF and half-yearly rollup; config wiring for branch thresholds. Plan ③: React capture surfaces and OM board.
