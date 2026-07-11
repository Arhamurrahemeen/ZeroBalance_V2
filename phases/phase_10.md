# Phase 10 — Schema v2 + ground_truth v2 extension

## Goal

Add the 4 new v2 tables and label the new scenarios the engine + service layer must handle. Additive only — v1 tables untouched. Ground-truth scenarios in a companion file so `ground_truth.py` (engine oracle) stays clean.

## Design decisions locked here

1. **`excess_ledger` is append-only, single-table, event-sourced.** Dual sign-off = two INSERT rows (event_type `opened`, then `countersigned`, then `closed`), all sharing a `case_ref` UUID. No UPDATE path exists. Hash chain is **global** across the table (matches `audit_ledger` pattern) — simpler trigger, one truth.
2. **State-machine rules (opened → countersigned → closed; countersigner ≠ opener) live in the service layer, NOT in DB constraints.** DB just enforces append-only + hash chain + type CHECKs. Service returns 409 on illegal transitions. Rationale: keeps schema minimal; makes the rules unit-testable without Postgres.
3. **`opening_float_declaration` is a single row per (branch, teller, business_date).** UNIQUE enforced. The one-teller-input-at-EOD rule stays; this is the day-start counterpart.
4. **`validation_log` is not append-only.** It's a pre-post demo log; hash chain would be overkill. Fed by Phase 12 endpoints.
5. **`ground_truth_v2.py` is new** — labeled scenario dataclasses for Excess Ledger transitions, cheque MICR mismatch, and 5 pre-post checks. The engine oracle (`ground_truth.py`) is untouched. Reason: matching-engine gates are already green; mixing behavioral test data into it would blur the oracle.

## Project structure touched

```
backend/
  schema.sql               EDIT — append 4 tables + trigger on excess_ledger
  app/db_models.py         EDIT — 4 new SQLAlchemy models
data/
  ground_truth_v2.py       NEW — labeled scenarios + self-check
```

## Steps

1. Append 4 tables to `backend/schema.sql`:
   - `opening_float_declaration` — UNIQUE(branch_code, teller_id, business_date)
   - `excess_ledger` — append-only event table, UNIQUE(case_ref, event_seq), hash chain, trigger
   - `cheque_transactions` — with denomination_out JSONB
   - `validation_log` — pre-post check log
2. Add SQLAlchemy models to `backend/app/db_models.py`. No relationships defined — service layer handles joins.
3. Create `data/ground_truth_v2.py`:
   - `ExcessScenario` dataclass — case_ref, sequence of events, expected_final_state (`accepted` | `rejected_at_countersign` | `rejected_at_close` | `rejected_dual_signoff`).
   - `ChequeScenario` — micr, account_number, amount, denomination_out, expected `valid` | `invalid` + reason.
   - `PrepostScenario` — check_name, input dict, expected_passed bool, expected_reason.
   - Coverage: 3+ scenarios per Excess state-transition rule; 4+ cheque scenarios; 2+ scenarios (pass + fail) per pre-post check (10 total).
   - `self_check()` verifies invariants (denomination_out sums = amount for valid cheques, event sequences are consistent, etc.). Exits non-zero on failure.

## Commands to run

```bash
# From D:\ZeroBalance_v2

# SQL syntax check (offline — no live Postgres in sandbox)
python3 -c "import re, pathlib; sql = pathlib.Path('backend/schema.sql').read_text('utf-8').rstrip('\x00'); print('lines:', sql.count('\n'), 'CREATE TABLE:', sql.count('CREATE TABLE'))"

# Python parse
python3 -c "import ast; ast.parse(open('backend/app/db_models.py','rb').read().rstrip(b'\x00').decode())"
python3 -c "import ast; ast.parse(open('data/ground_truth_v2.py','rb').read().rstrip(b'\x00').decode())"

# Oracle self-check (must exit 0)
cd data && python3 ground_truth_v2.py
```

## What to expect

- `CREATE TABLE` count in schema.sql: was 6, becomes **10**.
- `db_models.py` `Base.metadata.tables` count: was 6, becomes **10**.
- `ground_truth_v2.py self_check`: prints scenario counts, all invariants pass, exits 0.

## Deferred to user's local Postgres

- `docker compose up -d db` + `\dt` — confirm 10 tables created.
- Hash chain trigger rejects UPDATE/DELETE on `excess_ledger` — verified in Phase 11 tests with live DB.

## Anti-scope-creep checkpoint

1. Anything built off the 4-feature list? **No** — all 4 tables map 1:1 to locked features.
2. Any decision routed through Groq? **No** — nothing added to explain layer.
3. Any UPDATE/DELETE path on ledger tables? **No** — trigger blocks them.
4. Any OM/BOM/Regional/half-yearly-specific schema? **No** — `business_date` and date-range queries handle half-yearly cadence without new tables.

## Actual outcome

**Status: complete.** Host-side content verified via Read tool.

### Files written

| File | Verified on disk |
|---|---|
| `backend/schema.sql` | 6 v1 + 4 v2 = **10 `CREATE TABLE`**; 4 `CREATE INDEX` on v2 tables; 2 `CREATE TRIGGER` (audit_ledger + excess_ledger append-only) |
| `backend/app/db_models.py` | Base + 6 v1 + 4 v2 = **11 classes** total. New: `OpeningFloatDeclarationRow`, `ExcessLedgerRow`, `ChequeTransactionRow`, `ValidationLogRow`. `Boolean` + `UUID` added to imports. |
| `data/ground_truth_v2.py` | **6 excess + 4 cheque + 10 prepost = 20 scenarios.** `self_check()` passes with exit 0 (verified in sandbox — this file is new so the mount cache serves fresh content). |

### Coverage confirmed by ground_truth_v2 self-check

- **excess:** 6 scenarios cover happy paths (short + excess), dual-signoff violation (same actor), close-without-countersign, double-countersign, out-of-order (countersign before open).
- **cheque:** 4 scenarios cover valid single-denom, valid multi-denom, denom sum mismatch, MICR/account mismatch.
- **prepost:** 10 scenarios — 2 per check (pass + fail with reason) — cover all 5 checks: `denom_sum`, `cnic_name_match`, `duplicate_check`, `large_amount_confirm`, `sanity`.

### Sandbox mount-cache issue (relevant to future phases)

The Cowork Linux mount serves a stale cached view of files after `Edit` operations. Symptoms:
1. Bash `cat` / `grep` / Python parse on Edit'd files see the pre-Edit content.
2. `Read` tool goes through the host-side filesystem and shows the actual on-disk content.
3. Newly `Write`n files (fresh files, not overwrites of existing ones) show correct content in bash.
4. **Do NOT** run `tr -d '\000'` or any rewrite based on the bash view of Edit'd files — it re-writes the stale content back to disk, destroying the edits. (This happened once mid-phase; recovered by re-applying.)

Rule going forward: after any Edit, verify with `Read` only. Skip bash syntax checks on Edit'd files.

### Deferred to user's local Postgres

- `docker compose up -d db` and `\dt` to confirm 10 tables actually create.
- Real trigger test: `UPDATE excess_ledger SET amount = 0 WHERE id = 1;` — must raise `audit_ledger is append-only` (trigger reuses `forbid_ledger_mutation`).
- `python -c "from app.db_models import Base; print(sorted(Base.metadata.tables.keys()))"` inside container.

### Anti-scope-creep checkpoint

1. Anything off the LOCKED feature list? **No** — 4 new tables map 1:1 to the 4 locked features.
2. Any decision routed through Groq? **No** — schema-only phase.
3. Any UPDATE/DELETE path on ledger tables? **No** — excess_ledger reuses the append-only trigger.
4. Any OM/BOM/Regional/half-yearly-specific schema? **No** — `business_date` supports half-yearly cadence with date-range queries; no new tables required for OM (Phase 2 roadmap).

### Ready for Phase 11

Digital Excess Ledger backend service — CRUD + dual sign-off + hash chain.
