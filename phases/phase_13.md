# Phase 13 — Groq Urdu extensions + Excess Ledger Daily Register PDF

## Goal

Extend the existing post-hoc Groq explanation layer (`explain.py`) to two new
v2 surfaces — Excess Ledger openings and cheque capture variances — and add
an Excess Ledger Daily Register PDF (`report.py`), mirroring the EOD recon
report's brand/tone. No schema changes. No frontend changes (Phase 14 is
Wahaj's, blocked on this phase closing).

## Design decisions locked here

1. **No new tables/columns.** `excess_ledger` stays append-only with exactly
   the columns from Phase 10 — an explanation is not a state transition, so
   it does not become a 4th event type. Every explanation is persisted as an
   `audit_ledger` row (`EXCESS_EXPLAINED` / `CHEQUE_EXPLAINED`) with the
   explanation text in the JSONB payload. This is the same mechanism
   `EXCESS_OPENED`/`CHEQUE_CAPTURED` already use — no schema migration
   needed, and it keeps this phase's touched files to the app layer.
2. **Excess Ledger explain is not idempotent/cached** (unlike EOD suspects,
   which persist to a column and skip already-explained rows). Every
   `POST .../explain` call is a fresh, explicit action and always calls Groq
   again — there's nowhere to cache the result without a schema change, and
   re-explaining on request is fine since nothing about the case data itself
   changes.
3. **Cheque "variance" = a capture that would be rejected.** `cheque.py`
   gets a new pure function, `describe_variance()`, that runs the same two
   checks as `capture()` (denom-sum, MICR-vs-account) but never inserts a
   row and never raises — it returns `None` (valid, nothing to explain) or a
   `ChequeVariance` with the mismatch types. `capture()` itself is untouched
   (already gated and passing; not worth the risk of refactoring a
   Phase-12-verified function for this).
4. **Masking.** Account numbers and MICR account blocks go through the
   existing `mask_account()` (keep last 4). A new `mask_cnic()` does the
   same for CNIC. Since `excess_ledger` has no account/CNIC columns at all,
   the only place PII could leak from that surface is the free-text `note`
   a teller can type — so a new `redact_pii()` regex-scrubs CNIC-shaped and
   6+-digit runs out of free text before it reaches `build_excess_prompt()`.
5. **`POST /cheque/explain` is stateless** — it takes the same shape of
   input as `POST /cheque` (so a UI can immediately retry the failed
   capture's body against `/explain`), never persists a `cheque_transactions`
   row, and 409s if the input actually validates (nothing to explain).
6. **PDF generation is ledgered but not row-tracked.** Unlike
   `recon_reports` (one row per EOD session), there's no natural 1:1 row for
   a date-range register PDF. `EXCESS_REGISTER_REPORT_GENERATED` in
   `audit_ledger` (payload: range, branch, case_count, ledger_hash at
   generation) is the attestation — consistent with how `CHEQUE_CAPTURED`
   etc. don't get their own bookkeeping table either.
7. **Oracle extension.** `ground_truth_v2.py` gets one new, additive excess
   scenario (`excess_happy_note_with_pii`) whose opened note contains an
   account-number- and CNIC-shaped string, so the masking test is
   oracle-driven instead of hand-written test data. Appended at the end of
   `_excess_scenarios()` — doesn't change which scenario any existing
   `next(...)` lookup picks.

## Project structure touched

```
data/
  ground_truth_v2.py     EDIT — +1 excess scenario (PII-bearing note)
backend/
  app/
    cheque.py             EDIT — +ChequeVariance, +describe_variance(), +NoVarianceError
    explain.py             EDIT — +mask_cnic, +redact_pii, +excess/cheque prompt builders,
                                   +explain_excess_case(), +explain_cheque_variance()
    report.py              EDIT — +render_excess_register_html(), +generate_excess_register_pdf()
    schemas.py              EDIT — +ExcessExplainRequest/Out, +ChequeExplainRequest/Out
    api.py                   EDIT — +POST /excess-ledger/{case_ref}/explain
                                     +GET  /excess-ledger/report.pdf
                                     +POST /cheque/explain
  tests/
    test_explain_excess.py         NEW — required by kickoff
    test_report_excess_register.py NEW — required by kickoff
    test_explain_cheque.py         NEW — same design goal ("cheque variance"), oracle-driven
```

## Steps

1. Extend `data/ground_truth_v2.py` with `excess_happy_note_with_pii`.
2. `backend/app/cheque.py`: add `NoVarianceError(ChequeError)`, `ChequeVariance`
   dataclass, `describe_variance()`.
3. `backend/app/explain.py`: add `mask_cnic()`, `redact_pii()`,
   `SYSTEM_PROMPTS_EXCESS`, `SYSTEM_PROMPTS_CHEQUE`, `build_excess_prompt()`,
   `build_cheque_variance_prompt()`, `explain_excess_case()`,
   `ChequeExplanation` + `explain_cheque_variance()`.
4. `backend/app/report.py`: add `render_excess_register_html()` (reuses the
   existing `_CSS` brand constant) + `generate_excess_register_pdf()`.
5. `backend/app/schemas.py`: request/response models for the 2 new POST
   bodies and the explain response shapes.
6. `backend/app/api.py`: wire the 3 new routes; map `CaseNotFound` → 404,
   `NoVarianceError` → 409, `ChequeError` → 422, missing/placeholder Groq key
   → 503, upstream Groq failure → 502 + rollback (same pattern as
   `/sessions/{id}/explain`).
7. Tests as listed above, all oracle-backed.

## Commands to run

```bash
# Sandbox — parse only NEW/EDITED files
python3 -c "import ast; ast.parse(open('backend/app/explain.py','rb').read().decode())"
python3 -c "import ast; ast.parse(open('backend/app/report.py','rb').read().decode())"
python3 -c "import ast; ast.parse(open('backend/app/cheque.py','rb').read().decode())"
python3 data/ground_truth_v2.py   # self-check, exit 0

# Local — against live Postgres (compose)
docker compose exec backend pytest -q tests/test_explain_excess.py tests/test_report_excess_register.py tests/test_explain_cheque.py
docker compose exec backend pytest -q
```

## What to expect

- Oracle self-check still exits 0 with 7 excess scenarios (was 6).
- ~14-16 new tests, all green, full suite green (was 61, expect ~75-77).
- `POST /excess-ledger/{case_ref}/explain` → 200 with Urdu explanation;
  exactly 1 new `audit_ledger` row (`EXCESS_EXPLAINED`) per call; 404 on
  unknown case; 503 without a configured key.
- `POST /cheque/explain` → 200 + mismatch_types for a rejected-shape input;
  409 if the input is actually valid; masks MICR account + typed account.
- `GET /excess-ledger/report.pdf` → `application/pdf`, brand palette, shows
  case count; empty range still returns a valid (smaller) PDF; generation is
  ledgered.

## Anti-scope-creep checkpoint (answer before closing)

1. Anything off the LOCKED four-feature list? **No** — feature #1 (Excess
   Ledger) and #3 (cheque capture) Groq/PDF extensions only.
2. Any decision/ranking/filter routed through Groq? **No.** Both explain
   functions run strictly after the deterministic state (excess case
   already opened / cheque variance already computed by
   `describe_variance()`); Groq only turns already-decided facts into
   Urdu/English prose.
3. Any UPDATE/DELETE on ledger tables? **No.** `excess_ledger` is untouched
   by this phase — explanations go into `audit_ledger` as new INSERT rows
   only (`EXCESS_EXPLAINED`, `CHEQUE_EXPLAINED`,
   `EXCESS_REGISTER_REPORT_GENERATED`).
4. OM/BOM/Regional/half-yearly-specific build? **No.** The register PDF
   takes a `from_date`/`to_date` range (works for daily or half-yearly)
   exactly like the existing `/excess-ledger` register endpoint — no new
   query-window assumptions.

## Actual outcome

**Status: complete.** All gates green.

### Pre-flight (before touching Phase 13 code)

Ran the requested gates first and hit two infra issues, both resolved before
any product code was touched:

- **Port 5432 conflict**: an unrelated `zerobalance_v3` stack (postgres +
  backend + frontend + qdrant, up ~6h) already held host port 5432. Added an
  untracked `docker-compose.override.yml` (`ports: !override ["5433:5432"]`,
  gitignored) rather than editing the committed compose file.
- **Backend image build failed** (`paging file is too small`) — the host has
  8GB RAM and was down to ~757MB free with both stacks' containers running.
  Stopped the four `zerobalance_v3-*` containers (with explicit confirmation)
  to free memory; build then succeeded.
- **Found and fixed a real Phase 12 bug** during the gate run (not part of
  Phase 13's scope, but blocking the gate): `check_cnic_name_match` in
  `backend/app/prepost.py` scored `fuzz.token_set_ratio` without case
  normalization, so oracle case `prepost_cnic_name_pass`
  (`"AHMED ALI KHAN"` vs `"Ahmed Ali Khan"`) scored 35.7 instead of 100 and
  failed the 80 threshold. Fixed with `.upper()` on both sides before
  scoring — oracle was correct, this was a service bug. Logged in
  `phases/phase_12.md`.

Gates after the fix: 61/61 tests green, `\dt` showed all 10 tables.

### Files written / edited

| File | Type | Content |
|---|---|---|
| `data/ground_truth_v2.py` | EDIT | +1 excess scenario (`excess_happy_note_with_pii`) with an account-number- and CNIC-shaped string in the free-text note, for an oracle-backed masking test |
| `backend/app/cheque.py` | EDIT | `+NoVarianceError`, `+ChequeVariance`, `+describe_variance()` — pure, no DB/insert side effects |
| `backend/app/explain.py` | EDIT | `+mask_cnic()`, `+redact_pii()`, `+SYSTEM_PROMPTS_EXCESS/CHEQUE`, `+build_excess_prompt()`, `+build_cheque_variance_prompt()`, `+explain_excess_case()`, `+ChequeExplanation`, `+explain_cheque_variance()` |
| `backend/app/report.py` | EDIT | `+render_excess_register_html()` (reuses existing brand `_CSS`), `+generate_excess_register_pdf()` |
| `backend/app/schemas.py` | EDIT | `+ExcessExplainRequest/Out`, `+ChequeExplainRequest/Out` |
| `backend/app/api.py` | EDIT | `+POST /excess-ledger/{case_ref}/explain`, `+GET /excess-ledger/report.pdf`, `+POST /cheque/explain` |
| `backend/app/prepost.py` | EDIT (pre-flight fix) | case-normalize before `fuzz.token_set_ratio` in `check_cnic_name_match` |
| `backend/tests/test_explain_excess.py` | NEW | 5 tests |
| `backend/tests/test_explain_cheque.py` | NEW | 6 tests |
| `backend/tests/test_report_excess_register.py` | NEW | 5 tests |
| `.gitignore` | EDIT | `+docker-compose.override.yml` (local-only port remap, not for commit) |

### Endpoints wired

| Method | Path | Purpose | Success | Rejection |
|---|---|---|---|---|
| POST | `/api/v1/excess-ledger/{case_ref}/explain` | Urdu/English explanation of an opened case | 200 | 404 unknown case, 503 no key, 502 upstream failure |
| GET | `/api/v1/excess-ledger/report.pdf` | Daily/half-yearly Excess Ledger register PDF | 200 `application/pdf` | 422 bad/inverted range |
| POST | `/api/v1/cheque/explain` | Explains a rejected-shape cheque capture (denom-sum and/or MICR mismatch) | 200 | 409 input actually valid, 422 malformed input, 503 no key, 502 upstream failure |

### Design rules encoded

1. **No schema changes.** Explanations live only in `audit_ledger` payloads
   (`EXCESS_EXPLAINED`, `CHEQUE_EXPLAINED`); PDF generation is attested via
   `EXCESS_REGISTER_REPORT_GENERATED`. `excess_ledger` gained no 4th event
   type and no new columns.
2. **Masking.** `mask_account()` (existing) + new `mask_cnic()` for
   structured fields (MICR account block, typed account number); new
   `redact_pii()` regex-scrubs CNIC-shaped and 6+-digit runs out of the
   Excess Ledger's free-text `note` before it reaches a prompt, since that
   field has no dedicated account/CNIC column to mask directly. Verified by
   test (`test_explanation_masks_account_and_cnic_in_note`,
   `test_explanation_masks_account_and_micr`).
3. **Cheque variance is a stateless preview.** `describe_variance()` never
   inserts into `cheque_transactions`, valid or not — `/cheque/explain` can
   be called with the exact body that a `/cheque` 422 just rejected, without
   double-booking anything on success.
4. **Every explain call = exactly one audit_ledger row.** Verified for both
   surfaces (`test_explanation_writes_exactly_one_audit_row` in each of
   `test_explain_excess.py` / `test_explain_cheque.py`).
5. **Every Groq call is an explicit action** — both new endpoints are
   direct POST handlers, nothing on a background job.
6. **Groq never decides.** Both prompts describe already-final facts
   (a case that's already opened; a variance already computed
   deterministically) and instruct the model not to invent causes, accuse
   anyone, or decide outcomes.

### Sandbox / local gates

- `python data/ground_truth_v2.py` (in-container) → `SELECT-CHECK PASSED`,
  7 excess / 4 cheque / 10 prepost scenarios, determinism OK.
- `docker compose exec backend pytest -q` → **78 passed** (was 61; +16 new
  Phase 13 tests + 1 extra parametrized case from the new oracle scenario
  flowing through the existing `test_happy_close` happy-path test).

### Ready for Phase 14

Backend Phases 11–13 are green. Frontend (Wahaj, 4 screens) is unblocked.
Phase 13 stops here per instructions — not starting Phase 14.
