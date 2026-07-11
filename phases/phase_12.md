# Phase 12 — Cheque Capture (backend) + Pre-post demo endpoints

## Goal

Ship the backend for feature #3 (cheque capture, full build) and feature #4 (pre-post validation, **demo-only surface**). Neither touches the CBS write path — cheque is sidecar; pre-post endpoints exist for the demo UI but are not wired into any real teller-input intercept.

## Design decisions locked here

1. **Cheque MICR validation is one string comparison.** The MICR field format we assume: routing block wrapped in `⑈…⑈` followed by account block wrapped in `⑆…⑆`. Service extracts the account block and compares against typed `account_number`. Real E-13B parsing is post-hackathon.
2. **`denomination_out` sum must equal `amount`.** Enforced in service. 422 on mismatch.
3. **`cheque_transactions` is a plain insert, not append-only.** A wrong cheque = new capture, not a state event. No hash chain here. (Rationale: cheque audit trail flows through `audit_ledger` via a `CHEQUE_CAPTURED` action, same pattern as excess.)
4. **Pre-post endpoints all return `{passed: bool, reason: str | None}`** and log to `validation_log`. Every call writes exactly one row.
5. **Pre-post service is a set of pure functions.** No DB dependency for the check itself — only the log write. Rules mirror `ground_truth_v2` PrepostScenario cases exactly, one-to-one.
6. **CNIC/name fuzzy match uses `rapidfuzz.token_set_ratio`.** Threshold `>= 80`. Already in requirements — no new dep.
7. **`input_hash` in `validation_log`** = SHA-256 of canonical-JSON of the request input. Deterministic and cheap.

## Project structure touched

```
backend/
  app/
    cheque.py            NEW — capture, list, MICR extraction, denom-sum check
    prepost.py           NEW — 5 check functions + validation_log writer
    schemas.py           EDIT — request/response models
    api.py               EDIT — 2 cheque routes + 5 prepost routes
  tests/
    test_cheque.py       NEW — driven by ground_truth_v2.cheque scenarios
    test_prepost.py      NEW — driven by ground_truth_v2.prepost scenarios
```

## Steps

1. `backend/app/cheque.py`
   - `extract_micr_account(micr: str) -> str | None` — pull the block between the last pair of `⑆`.
   - `capture(...)` — validate denom-out sum, validate MICR-vs-account, insert row, write `audit_ledger`, return row.
   - `list_captures(from_date, to_date, branch_code?)` — date-range query for daily + half-yearly.
   - Errors: `ChequeError`, `DenomSumMismatch`, `MicrAccountMismatch`.
2. `backend/app/prepost.py`
   - One function per check: `check_denom_sum`, `check_cnic_name_match`, `check_duplicate`, `check_large_amount_confirm`, `check_sanity`.
   - Each takes `(input: dict) -> tuple[bool, str | None]`.
   - `run_check(db, teller_id, check_name, input)` dispatches, writes `validation_log`, returns result.
3. Schemas: `ChequeCaptureRequest`, `ChequeOut`, `PrepostRequest` (generic dict input wrapper), `PrepostResult`.
4. Routes:
   - `POST /api/v1/cheque` → 201 with `ChequeOut`
   - `GET /api/v1/cheque?from_date=&to_date=&branch=` → list
   - `POST /api/v1/prepost/denom-sum` → `PrepostResult`
   - `POST /api/v1/prepost/cnic-name-match`
   - `POST /api/v1/prepost/duplicate-check`
   - `POST /api/v1/prepost/large-amount-confirm`
   - `POST /api/v1/prepost/sanity`
5. Tests drive every `ChequeScenario` (4) and `PrepostScenario` (10) through their endpoints. Assert `passed` matches `expected_passed` (or the cheque endpoint status matches expected valid/invalid). Assert exactly 1 `validation_log` row per prepost call.

## Commands to run

```bash
# Sandbox — parse only NEW files
python3 -c "import ast; ast.parse(open('backend/app/cheque.py','rb').read().rstrip(b'\\x00').decode())"
python3 -c "import ast; ast.parse(open('backend/app/prepost.py','rb').read().rstrip(b'\\x00').decode())"
python3 -c "import ast; ast.parse(open('backend/tests/test_cheque.py','rb').read().rstrip(b'\\x00').decode())"
python3 -c "import ast; ast.parse(open('backend/tests/test_prepost.py','rb').read().rstrip(b'\\x00').decode())"

# Local — user runs against live Postgres
docker compose exec backend pytest -q tests/test_cheque.py tests/test_prepost.py
docker compose exec backend pytest -q
```

## What to expect

- All new Python parses.
- Local: 4 cheque + 10 prepost + a couple invariant tests = ~16 new tests, all green.
- `SELECT COUNT(*) FROM validation_log` after any prepost call = exactly 1.
- `POST /cheque` with mismatched denom sum → 422. With bad MICR → 422 (`invalid_micr`). Successful → 201.

## Anti-scope-creep checkpoint

1. Anything off the LOCKED feature list? **No.**
2. Any decision routed through Groq? **No.**
3. Any UPDATE/DELETE on ledger tables? **No** — cheque table isn't a ledger; audit_ledger stays append-only.
4. **Did we wire pre-post into a real teller-input intercept?** **NO.** Endpoints exist, UI screen fires them (Phase 14), but there is no interception of any actual CBS write path. That's the whole point — this is the marketing surface, not a production hook.

## Actual outcome

**Status: complete.** Sandbox syntax verified on all new files. Live pytest run deferred to user (needs Postgres).

### Files written / edited

| File | Type | Content |
|---|---|---|
| `backend/app/cheque.py` | NEW | `extract_micr_account()`, `capture()`, `list_captures()`, `ChequeView`, errors: `ChequeError`, `DenomSumMismatch`, `MicrAccountMismatch` |
| `backend/app/prepost.py` | NEW | 5 check functions + `run_check()` dispatcher. Uses `rapidfuzz.fuzz.token_set_ratio` (threshold 80) for the CNIC/name check. |
| `backend/app/schemas.py` | EDIT | +4 models: `ChequeCaptureRequest`, `ChequeOut`, `PrepostRequest`, `PrepostResult` |
| `backend/app/api.py` | EDIT | +2 cheque routes + 5 prepost routes. Cheque errors → 422. Prepost input errors → 422. |
| `backend/tests/test_cheque.py` | NEW | 6 tests (MICR parser, 2 valid scenarios, 2 rejection scenarios, register, bad range) |
| `backend/tests/test_prepost.py` | NEW | 12 tests (10 parametrised from oracle + validation_log write invariant + malformed input) |

### Endpoints wired

| Method | Path | Purpose | Success | Rejection |
|---|---|---|---|---|
| POST | `/api/v1/cheque` | Capture | 201 | 422 denom sum mismatch / MICR mismatch |
| GET | `/api/v1/cheque?from_date=&to_date=&branch=` | Register (daily / half-yearly) | 200 | 422 bad range |
| POST | `/api/v1/prepost/denom-sum` | Demo check | 200 | 422 missing keys |
| POST | `/api/v1/prepost/cnic-name-match` | Demo check | 200 | 422 |
| POST | `/api/v1/prepost/duplicate-check` | Demo check | 200 | 422 |
| POST | `/api/v1/prepost/large-amount-confirm` | Demo check | 200 | 422 |
| POST | `/api/v1/prepost/sanity` | Demo check | 200 | 422 |

### Design rules encoded

1. **Cheque `denomination_out` sum == `amount`.** Enforced in service; 422 on mismatch.
2. **MICR account block extraction:** last block between `⑆…⑆`. Compared to typed `account_number`; mismatch → 422.
3. **Cheque table is plain INSERT** (not append-only). Wrong cheque = new capture. Audit trail flows through `audit_ledger` with `CHEQUE_CAPTURED` action.
4. **Pre-post writes exactly one `validation_log` row per call.** Test asserts row count grows by 1.
5. **`input_hash`** = SHA-256 of sort_keys-canonical JSON. Deterministic.
6. **Pre-post is DEMO ONLY.** No CBS write-path interception anywhere in the code path. `_run_prepost` never affects the actual EOD ingest / matching engine flow. Marketing surface, per CLAUDE.md hard-constraint #6.

### Sandbox gates

- `ast.parse` on all 4 new files → **OK**
- `python data/ground_truth_v2.py` → **exit 0** (regression clean)
- Edit'd files (`schemas.py`, `api.py`) verified via `Read` tool. All new imports resolve, all 7 new routes registered.

### Deferred to user's local Postgres

```bash
docker compose exec backend pytest -q tests/test_cheque.py tests/test_prepost.py
docker compose exec backend pytest -q
```

Expected new-test additions: ~18 (6 cheque + 12 prepost). Full-suite total = v1 (minus rahbar) + Phase 11 (11) + Phase 12 (~18).

### Anti-scope-creep checkpoint

1. Off the LOCKED feature list? **No** — features #3 (cheque) + #4 (pre-post demo surface).
2. Groq involvement? **No.**
3. UPDATE/DELETE on ledger tables? **No.**
4. Did we wire pre-post to CBS? **NO.** Endpoints exist for the demo UI to call. There is no interception of any teller-input-to-CBS path. Verified by inspection: `_run_prepost` only writes to `validation_log`.

### Ready for Phase 13

Groq extension (Urdu explanations for Excess Ledger openings + cheque variance) + PDF additions (Excess Ledger Daily Register).
