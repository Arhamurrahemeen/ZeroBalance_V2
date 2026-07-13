# Phase 16 — Cash Movement Ledger backend + migration

## Goal

Add the event-typed Cash Movement Ledger: `day_start` / `reissue` / `handover` / `day_end`, denomination-broken, dual- (triple- for handover) signed, hash-chained, INSERT-only. Replaces `opening_float_declaration` (dead table — schema-only, never written or read by any endpoint; migration is a zero-row no-op). Expose CRUD + verify-chain + a denomination-view EOD reconciliation endpoint.

## Design decisions locked here

1. **No state machine, unlike Excess Ledger.** Each cash movement event is one row, not a sequence sharing a case_ref. A `POST /cash-movement` call inserts exactly one ledger row + N denomination rows in one transaction, hash-chained into a single global chain (same pattern as `excess_ledger`, field names `prev_hash`/`row_hash` per CLAUDE.md schema table).
2. **Sign-off shape differs by `event_type`.** `day_start` / `reissue` / `day_end` require `signoff_teller` + `signoff_om` (`signoff_counterparty` must be absent). `handover` requires all three (`signoff_teller` + `signoff_counterparty` + `signoff_om`) — the only three-signer event. Enforced in the service layer, not the DB.
3. **`total_amount` is derived, not trusted.** Computed server-side from the posted `denominations` list; any client-sent total is ignored/recomputed. Mirrors cheque capture's denom-sum-must-match-amount pattern, but here there's no separate "amount" to check against — the denomination sum *is* the total.
4. **`GET /eod/reconciliation` omits fabricated fields.** The Phase 16 sketch in `v2_plan.md` lists `deposits_in` / `withdrawals_out` per denomination — but CBS transactions carry no denomination breakdown (per-transaction denomination capture is permanently forbidden, CLAUDE.md). That data does not exist in this system. Building those columns would mean inventing numbers, which anti-delusion guardrail #6 forbids. The endpoint instead returns, per denomination: `opening_plus_reissues` (from `day_start`+`reissue` events), `physical` (from the `day_end` event), `variance` (`physical - opening_plus_reissues`). The existing aggregate variance + ranked-suspects engine (`engine/matching.py`, untouched) remains the authority on *why* a variance happened; this endpoint is a denomination-level reference view, not a second engine.
5. **`opening_float_declaration` dropped outright, not left as a view.** Grepped the codebase: no endpoint ever inserted into it (`IngestMeta.opening_float` — the value the matching engine actually uses — is a teller-typed scalar passed at CSV-ingest time, unconnected to this table). Zero rows exist in any real environment. The CLAUDE.md-offered fallback ("leave as VIEW if migration risk is unacceptable") doesn't apply — there is no risk because there is no data or dependent code.

## Project structure touched

```
backend/
  schema.sql              EDIT — +cash_movement_ledger, +cash_movement_denominations, append-only trigger; drop opening_float_declaration
  app/
    db_models.py           EDIT — CashMovementLedgerRow, CashMovementDenominationRow; remove OpeningFloatDeclarationRow
    cash_movement.py        NEW — service: record(), list_events(), verify_chain()
    reconcile.py             NEW — GET /eod/reconciliation computation
    schemas.py              EDIT — request/response models for both endpoint groups
    api.py                  EDIT — POST/GET /cash-movement, GET /cash-movement/verify-chain, GET /eod/reconciliation
  tests/
    test_cash_movement.py    NEW — pytest, driven by ground_truth_v2 CashMovementScenario
migrations/
  016_cash_movement_ledger.sql  NEW — additive DDL for existing (non-fresh) dev volumes
data/
  ground_truth_v2.py       EDIT — +CashMovementScenario (day_start/reissue/handover/day_end + rejections)
```

## Steps

1. Schema: add the two tables + append-only trigger (reuse `forbid_ledger_mutation()`), drop `opening_float_declaration`.
2. `db_models.py`: SQLAlchemy mappings for the two new tables; remove the old model.
3. `ground_truth_v2.py`: add `CashMovementScenario` + `_cash_movement_scenarios()`, wire into `ScenarioSuiteV2`, extend `self_check()`.
4. TDD `cash_movement.py` against `test_cash_movement.py`: one failing test at a time, watched red, then minimal code green.
5. `reconcile.py` + `GET /eod/reconciliation`.
6. `migrations/016_cash_movement_ledger.sql` for non-fresh volumes.
7. Full `pytest -q` in the compose container; then a from-scratch `docker compose down -v && up --build` to confirm the fresh-init gate.

## Commands

```bash
docker compose exec backend pytest -q tests/test_cash_movement.py
docker compose exec backend pytest -q                       # full v2.1 suite
docker compose down -v && docker compose up --build -d      # fresh-init gate
python data/ground_truth_v2.py                               # oracle self-check
```

## What to expect

- New scenarios cover: happy `day_start`, happy `reissue`, happy `handover` (3 signers), happy `day_end`, rejected (missing OM signoff), rejected (handover missing counterparty signoff), rejected (denomination sum doesn't match — n/a, no separate amount field so this collapses into "always trusted"; actually N/A, dropped), rejected (bad denomination key).
- `verify-chain` returns `ok=true` after any sequence of accepted events.
- `eod/reconciliation` returns real, non-fabricated per-denomination figures only.
- Full suite green in-container; fresh `down -v && up --build` succeeds with the new schema.

## Anti-scope-creep checkpoint

1. Off the LOCKED feature list? No — this is the data spine for feature #2 (EOD recon), explicitly named in CLAUDE.md.
2. Any decision routed through Groq? No.
3. Any UPDATE/DELETE on ledger paths? No — trigger blocks it; service only INSERTs.
4. Anything OM/BOM/Regional/half-yearly-specific? No — OM's role stays limited to sign-off, matching the persona table.

## Actual outcome

**Status: complete.** Verified live against the user's Postgres, including a from-scratch `docker compose down -v && up --build`.

### Files written / edited

| File | Type | Content |
|---|---|---|
| `backend/schema.sql` | EDIT | Dropped `opening_float_declaration` (confirmed 0 rows, no reader/writer anywhere in the app); added `cash_movement_ledger` + `cash_movement_denominations` + append-only trigger reusing `forbid_ledger_mutation()` |
| `backend/app/db_models.py` | EDIT | Removed `OpeningFloatDeclarationRow`; added `CashMovementLedgerRow`, `CashMovementDenominationRow` (generated `amount` column mapped via `Computed()`) |
| `backend/app/cash_movement.py` | NEW (~230 lines) | `record_event()`, `list_events()`, `verify_chain()`, `to_view()`; errors `CashMovementError`, `BadDenomination`, `SignoffError` |
| `backend/app/reconcile.py` | NEW | `denomination_view()` — opening(day_start+reissue) vs physical(day_end) vs variance, per denomination. No fabricated fields. |
| `backend/app/schemas.py` | EDIT | +6 Pydantic models: `CashMovementRequest`, `CashMovementOut`, `CashMovementChainVerifyOut`, `DenomReconciliation`, `EodReconciliationOut` |
| `backend/app/api.py` | EDIT | +4 routes: `POST/GET /cash-movement`, `GET /cash-movement/verify-chain`, `GET /eod/reconciliation` |
| `backend/tests/test_cash_movement.py` | NEW (~230 lines) | 17 tests, driven by `ground_truth_v2.CashMovementScenario` |
| `backend/tests/test_{excess_ledger,cheque,prepost,explain_cheque,explain_excess,report_excess_register}.py` | EDIT | `TRUNCATE_TABLES` updated: `opening_float_declaration` → `cash_movement_denominations, cash_movement_ledger` |
| `data/ground_truth_v2.py` | EDIT | +`CashMovementScenario`, `_cash_movement_scenarios()` (8 scenarios), `_check_cash_movement()`, coverage assertions in `self_check()` |
| `migrations/016_cash_movement_ledger.sql` | NEW | Additive, idempotent DDL for non-fresh dev volumes (fresh bring-up uses `schema.sql` directly) |

### Design deviation from the v2_plan.md sketch — flagged, not silently built

The Phase 16 sketch in `v2_plan.md` specified `GET /eod/reconciliation` returning per-denomination `deposits_in` / `withdrawals_out`. That data doesn't exist: CBS transactions carry no denomination breakdown (per-transaction denomination capture is permanently forbidden — CLAUDE.md hard constraint #3), so there was nothing to compute those two columns from. Built the endpoint with only what's real: `opening_plus_reissues`, `physical`, `variance` per denomination. Explicit test (`test_reconciliation_shows_opening_vs_physical_per_denom`) asserts `deposits_in`/`withdrawals_out` keys are absent, so this doesn't silently regress back to fabricated numbers later.

### `opening_float_declaration` — dropped outright, not left as a VIEW

Verified via grep before touching schema: no endpoint anywhere ever wrote to this table (`IngestMeta.opening_float`, the value the matching engine uses, is a teller-typed scalar passed at CSV-ingest time — never connected to this table) and `SELECT COUNT(*)` on the live dev DB returned 0. The CLAUDE.md-offered fallback ("leave as VIEW if migration risk is unacceptable") didn't apply — there was no data and no dependent code, so dropping outright was the correct, lower-complexity move.

### Endpoints wired

| Method | Path | Purpose | Success | Rejection |
|---|---|---|---|---|
| POST | `/api/v1/cash-movement` | Record one event (day_start/reissue/handover/day_end) + its denominations | 201 | 422 on bad denomination, missing/unexpected signoffs |
| GET | `/api/v1/cash-movement?teller_id=&session_id=&from_date=&to_date=` | Event stream, all filters optional | 200 (list) | 422 bad range |
| GET | `/api/v1/cash-movement/verify-chain` | Global chain walk | 200 `{ok, rows, head}` | — |
| GET | `/api/v1/eod/reconciliation?teller_id=&business_date=` | Denomination-view reconciliation | 200 `{teller_id, business_date, per_denom}` | 422 bad date |

### Design rules encoded (locked in code)

1. **Not a state machine.** Each `POST /cash-movement` is exactly one INSERT (+ N denomination rows), unlike Excess Ledger's opened→countersigned→closed sequence. Simpler because Cash Movement events aren't transitions on a shared case — they're independent, hash-chained facts on a timeline.
2. **Sign-off shape is event_type-dependent.** `day_start`/`reissue`/`day_end`: teller + OM. `handover`: teller + counterparty + OM (three signers) — the only event requiring `counterparty_id`. Enforced in `_validate_signoffs()`, not the DB; `signoff_counterparty` present on a non-handover event is itself a rejection (data-integrity guard against UI/client confusion).
3. **`total_amount` is derived, never trusted from the client.** Computed server-side as `sum(denomination * count)`. No separate client-sent total to cross-check — the denomination sum *is* the total, matching "one denomination count per Cash Movement event."
4. **Denomination set is banknotes only:** `{5000, 1000, 500, 100, 50, 20, 10}` — matches CLAUDE.md's schema table exactly (narrower than `denomination_counts`, which also allows 5/2/1 coins for EOD sessions).
5. **Every write also touches `audit_ledger`.** `CASH_MOVEMENT_RECORDED` action, same pattern as Excess Ledger and cheque capture.
6. **`opening_float_declaration` fully removed**, not deprecated-in-place — see above.

### Verification

```
docker compose exec backend pytest -q tests/test_cash_movement.py   # 17 passed
docker compose exec backend pytest -q                                # 95 passed (78 prior + 17 new)
python data/ground_truth_v2.py                                       # SELF-CHECK PASSED (8 cash_movement scenarios)
docker compose down -v && docker compose up --build -d               # fresh-init gate: clean, 11 tables, no opening_float_declaration
docker compose exec backend pytest -q  (post fresh-init)             # 95 passed
```

### Anti-scope-creep checkpoint

1. Off the LOCKED feature list? **No** — this is the data spine for feature #2 (EOD recon), explicitly named in CLAUDE.md.
2. Any decision routed through Groq? **No.**
3. Any UPDATE/DELETE on ledger paths? **No** — trigger blocks it (mirrors `excess_ledger`); service only calls `db.add()`.
4. Anything OM/BOM/Regional/half-yearly-specific? **No** — OM's role stays limited to sign-off (`signoff_om` on every event), matching the persona table. No cross-teller aggregation: `list_events`/`denomination_view` are always scoped to a single `teller_id`.
5. Cross-teller aggregation, OM dashboards, teller performance analytics? **No.**
6. Per-transaction denomination entry? **No** — and the reconciliation endpoint's field omission (see above) actively guards against it creeping back in via the "deposits_in/withdrawals_out" sketch.

### Ready for Phase 17

Cash Movement UI + denomination-view EOD table + Verify Chain button. Backend gate is green.
