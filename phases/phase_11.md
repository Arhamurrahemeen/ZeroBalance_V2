# Phase 11 — Digital Excess Ledger (backend) — flagship

## Goal

Ship the backend for the v2 flagship: append-only Digital Excess Ledger with dual sign-off and a global hash chain. Every state transition is a new INSERT row — never an UPDATE. State-machine rules (opener ≠ countersigner; close requires prior countersign; no double countersign; no out-of-order events) live in the service layer and return HTTP 409 on violation.

Half-yearly closing is served by the register endpoint via `from_date` / `to_date` — no new tables, no separate half-yearly path.

## Design decisions locked here

1. **Hash chain reuses the v1 pattern.** SHA-256 over `f"{prev_hash}|{canonical_json(row_payload)}"`. `_chain_head()` returns latest `entry_hash` or `"GENESIS"`. `verify_chain()` walks in `id` order and recomputes.
2. **`amount` stays constant across a case.** `countersign` and `close` inherit `amount` from the `opened` event — the countersigner cannot silently change the number.
3. **`case_ref` (UUID) is the public identifier.** Routes use `/{case_ref}/countersign`, not `/{numeric_id}`. Numeric `id` is DB-internal only. Reason: case_ref survives copies/exports; DB id doesn't.
4. **Every service action also writes to `audit_ledger`.** Two chains, not one — Excess Ledger holds the domain state; audit_ledger holds the operational actor log. Same actor writes to both.
5. **Bootstrap-order errors go through `OutOfOrderEvent`.** No bare 500s: first event for a case_ref MUST be `opened`; anything else → 409.

## Project structure touched

```
backend/
  app/
    excess_ledger.py     NEW — service (open, countersign, close, register, verify_chain)
    schemas.py           EDIT — Pydantic models for the 5 endpoints
    api.py               EDIT — 5 routes under /api/v1/excess-ledger
  tests/
    test_excess_ledger.py  NEW — pytest, driven by ground_truth_v2 scenarios
```

## Steps

1. Write `backend/app/excess_ledger.py`:
   - Custom errors: `ExcessLedgerError`, `DualSignoffViolation`, `MissingCountersign`, `DoubleCountersign`, `OutOfOrderEvent`, `CaseNotFound`.
   - Internals: `_hash()`, `_chain_head()`, `_case_events()`, `_append()`.
   - Public API: `open_entry()`, `countersign()`, `close_entry()`, `list_register()`, `verify_chain()`.
   - Every write function commits and returns the row (or view).
2. Edit `backend/app/schemas.py`: add `ExcessOpenRequest`, `ExcessCountersignRequest`, `ExcessCloseRequest`, `ExcessCaseOut`, `ExcessChainVerifyOut`.
3. Edit `backend/app/api.py`: add 5 routes with error → HTTP mapping (409 for state violations, 404 for `CaseNotFound`).
4. Write `backend/tests/test_excess_ledger.py`:
   - Truncate `excess_ledger`, `audit_ledger` per-test.
   - Drive every `ExcessScenario` from `ground_truth_v2` through the API.
   - Assert `INSERT`-only via row count (3 rows after happy close; last event type asserted).
   - Assert dual sign-off (opener ≠ countersigner).
   - Assert hash chain verify returns `ok=True` after each happy scenario.
   - Assert register endpoint returns the right case view.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/excess-ledger/open` | Teller opens entry (excess or short). Body: branch_code, teller_id, business_date, entry_kind, amount, opener, note. Returns `ExcessCaseOut`. |
| POST | `/api/v1/excess-ledger/{case_ref}/countersign` | Officer countersigns. Body: officer. 409 if opener == officer. Returns `ExcessCaseOut`. |
| POST | `/api/v1/excess-ledger/{case_ref}/close` | Officer closes with resolution. Body: officer, resolution_note. 409 if no countersign yet. Returns `ExcessCaseOut`. |
| GET | `/api/v1/excess-ledger?from_date=&to_date=&branch=` | Daily register / half-yearly register. Returns `list[ExcessCaseOut]`. |
| GET | `/api/v1/excess-ledger/verify-chain` | Walk the global hash chain. Returns `{ok, rows, head}`. |

## Commands to run

```bash
# Sandbox syntax check (only on NEW files — mount cache is stale for Edit'd)
python3 -c "import ast; ast.parse(open('backend/app/excess_ledger.py','rb').read().rstrip(b'\\x00').decode())"
python3 -c "import ast; ast.parse(open('backend/tests/test_excess_ledger.py','rb').read().rstrip(b'\\x00').decode())"

# Local — user runs these against live Postgres
docker compose up -d db
docker compose exec backend pytest -q tests/test_excess_ledger.py
docker compose exec backend pytest -q                # full v2 suite
```

## What to expect

- New Python files parse cleanly.
- User's local `pytest tests/test_excess_ledger.py` — all excess scenarios green.
- User's local `pytest -q` — total = (v1 count minus rahbar) + new excess tests.
- On happy close: `SELECT COUNT(*) FROM excess_ledger WHERE case_ref = ?` returns 3.
- On happy close: `SELECT event_type FROM excess_ledger WHERE case_ref = ? ORDER BY event_seq` returns `[opened, countersigned, closed]`.
- `GET /verify-chain` after any successful run returns `{ok: true, ...}`.

## Anti-scope-creep checkpoint

1. Anything off the LOCKED feature list? **No** — this is feature #1, the flagship.
2. Any decision routed through Groq? **No** — service is pure deterministic Python.
3. Any UPDATE/DELETE on ledger? **No** — every transition is INSERT. Trigger blocks anything else.
4. Anything OM/BOM/Regional/half-yearly-specific? **No** — half-yearly served by date-range query on the same endpoint.

## Actual outcome

**Status: complete.** Sandbox syntax + design verified. Live pytest run deferred to user (needs Postgres).

### Files written / edited

| File | Type | Content |
|---|---|---|
| `backend/app/excess_ledger.py` | NEW (~245 lines) | 6 exception types, hash chain (`_hash`, `_chain_head`, `_canonical_payload`), state machine (`open_entry`, `countersign`, `close_entry`), `CaseView` dataclass, `get_case`, `list_register`, `verify_chain` |
| `backend/app/schemas.py` | EDIT | +5 Pydantic models: `ExcessOpenRequest`, `ExcessCountersignRequest`, `ExcessCloseRequest`, `ExcessCaseOut`, `ExcessChainVerifyOut`. `Decimal` + `Literal` imports added. |
| `backend/app/api.py` | EDIT | +5 routes under `/api/v1/excess-ledger`, error → HTTP mapping (`CaseNotFound → 404`, other `ExcessLedgerError → 409`) |
| `backend/tests/test_excess_ledger.py` | NEW (~230 lines) | 11 tests, all driven by `ground_truth_v2` scenarios where applicable |

### Endpoints wired

| Method | Path | Purpose | Success | Rejection |
|---|---|---|---|---|
| POST | `/api/v1/excess-ledger/open` | Open entry | 201 | 422 on bad body |
| POST | `/api/v1/excess-ledger/{case_ref}/countersign` | Countersign | 200 | 404 no case; 409 same actor / already countersigned / already closed |
| POST | `/api/v1/excess-ledger/{case_ref}/close` | Close with resolution | 200 | 404 no case; 409 missing countersign / already closed |
| GET | `/api/v1/excess-ledger?from_date=&to_date=&branch=` | Daily / half-yearly register | 200 (list) | 422 bad range |
| GET | `/api/v1/excess-ledger/verify-chain` | Global chain walk | 200 `{ok, rows, head}` | — |

### Design rules encoded (locked in code)

1. **Every state transition is `INSERT`.** No `UPDATE` path exists in `excess_ledger.py`. Test asserts row count = 3 after happy close, and event_types = `[opened, countersigned, closed]`.
2. **Dual sign-off.** Service refuses countersign when `officer == opened.actor`. Test covers.
3. **Close requires countersign.** Service refuses close when `countersigned` not in event list. Test covers.
4. **No double countersign / no re-close.** Service refuses when last event is already `countersigned` or `closed`. Test covers.
5. **Amount is fixed at open.** `countersign` and `close_entry` inherit `opened.amount` — the countersigner's request body has no amount field. Test asserts `countersigned.amount == opened.amount`.
6. **Both ledgers touched.** Every action also writes an `audit_ledger` row (`EXCESS_OPENED` / `EXCESS_COUNTERSIGNED` / `EXCESS_CLOSED`). Two chains, one operational log.
7. **`case_ref` (UUID) is the public identifier.** Numeric `id` never leaves the DB.
8. **Half-yearly = wide `from_date`/`to_date`.** No new endpoint, no hard-coded "yesterday" anywhere.

### Sandbox gates

- `ast.parse` on `backend/app/excess_ledger.py` → **OK**
- `ast.parse` on `backend/tests/test_excess_ledger.py` → **OK**
- `python data/ground_truth_v2.py` → **exit 0** (regression clean)
- Edit'd files (`api.py`, `schemas.py`) verified via `Read` tool (mount cache stale, `Read` is host-side truth). All new imports resolve, all 5 routes registered.

### Deferred to user's local Postgres

```bash
cd D:\ZeroBalance_v2
docker compose up -d db
docker compose exec backend pytest -q tests/test_excess_ledger.py
docker compose exec backend pytest -q                  # full suite
```

Expected: 11 new tests pass. Full-suite total = (v1 count minus rahbar) + 11.

### Anti-scope-creep checkpoint

1. Off the LOCKED feature list? **No** — this IS the flagship (feature #1).
2. Any Groq involvement? **No** — pure deterministic Python.
3. Any UPDATE/DELETE? **No** — every service function only calls `db.add()`. Trigger blocks the rest.
4. Any OM/BOM/Regional/half-yearly-specific code? **No** — `list_register` is the shared endpoint.

### Ready for Phase 12

Cheque capture + Pre-post demo endpoints. Same shape (backend + tests, no UI yet).
