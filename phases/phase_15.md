# Phase 15 — Integration + demo dry run

## Goal

Prove the full pipeline works end-to-end from a clean `docker compose up`:
PIBAS CSV → matching engine → Excess Ledger sign-off → cheque capture →
signed PDFs, run twice back-to-back with no state pollution, hash chains
verified clean throughout.

## Design decisions locked here

1. **"Clean state" means wiping the dev Postgres volume**, not just
   restarting containers — otherwise "does the schema come up clean" isn't
   actually being tested (the volume has been alive since Phase 10). The
   data in it is exclusively test/demo rows generated during Phases 11–14's
   own verification — there's nothing of the user's to lose. `docker
   compose down -v` then a fresh `up --build`.
2. **The end-to-end "demo" is driven via the API, not a human clicking
   through the UI.** No browser-automation tool is available in this
   environment (flagged already in Phase 14). What CAN be verified
   end-to-end programmatically: CSV ingest → engine → Excess Ledger state
   machine → cheque capture → PDF generation → both hash chains, run twice
   back-to-back to catch state-pollution bugs (unique constraints,
   leftover chain state, etc.). What CANNOT be verified here: actual
   browser console errors/unhandled promise rejections, and a timed human
   dress rehearsal of the pitch narrative. Both are called out explicitly
   as founder follow-ups rather than silently skipped.
3. **CSV/case data comes from `data/generator.py`** (`make_case`), the same
   oracle-backed generator the backend test suite already uses — not
   hand-written CSV content.

## Steps

1. `docker compose down -v` — full teardown including the Postgres volume.
2. `docker compose up -d db backend frontend --build` from scratch.
3. Confirm schema (`\dt` → 10 tables) and full pytest gate on the fresh DB.
4. Run the demo sequence via the live API, twice back-to-back:
   a. Generate + ingest a PIBAS CSV session (`make_case`) → variance +
      ranked suspects.
   b. Explain the top suspect in Urdu (Groq).
   c. Download the signed EOD recon PDF.
   d. Open → countersign → close a Digital Excess Ledger case; explain it.
   e. Download the Excess Ledger Daily Register PDF.
   f. Capture a valid cheque; list the register.
   g. Fire 2 pre-post demo checks.
   h. Verify `excess-ledger/verify-chain` and `ledger/verify` — both `ok`.
5. Time the full 2-run sequence (informational, not the pitch rehearsal
   itself).

## Commands to run

```bash
docker compose down -v
docker compose up -d db backend frontend --build
docker compose exec backend pytest -q
docker compose exec db psql -U zerobalance -c "\dt"
# then the API-driven demo sequence, run twice
```

## What to expect

- Fresh volume, schema initializes clean, 10 tables, full suite green.
- Both demo runs complete without errors; second run doesn't collide with
  the first (different business_date/case_ref per run).
- Both hash chains `ok: true` after both runs.

## Anti-scope-creep checkpoint (answer before closing)

1. Anything off the LOCKED four-feature list exercised? **No** — all four:
   EOD recon, Excess Ledger, cheque capture, pre-post demo checks.
2. Any decision routed through Groq during the dry run? **No.** Both Groq
   calls (EOD suspect explain, Excess Ledger case explain) ran strictly
   after the deterministic engine/state-machine had already decided.
3. Any UPDATE/DELETE observed on ledger tables? **No** — every write in
   both runs was a fresh INSERT; both hash chains verified `ok: true`
   throughout, row/entry counts only ever grew.
4. OM/BOM/Regional-specific step included? **No.**

## Actual outcome

**Status: complete.** Clean-state bring-up verified; full demo sequence run
twice back-to-back via the live API with zero errors and clean hash chains
both times.

### Clean-state bring-up

- User explicitly approved wiping the dev Postgres volume (the harness's
  auto-mode classifier initially blocked `docker compose down -v` as an
  irreversible action not explicitly named in "complete all remaining
  phases" — asked, got explicit sign-off, then proceeded).
- `docker compose down -v` → `docker compose up -d db backend frontend
  --build` from a fully empty volume.
- `\dt` → all 10 tables present, schema.sql loaded clean with no manual
  intervention.
- `pytest -q` on the fresh DB → **78 passed** (same count as Phase 14's
  pre-existing-DB run — confirms the suite is DB-state-independent).

### Demo dry run (API-driven, twice back-to-back)

No browser-automation tool is available in this environment (same
limitation noted in Phase 14), so the "5-minute pitch demo" was rehearsed
at the API level — the same calls the UI makes, driven by a scratch script
(`generator.make_case` for the CSV, httpx against the live container) —
not by a human clicking through the SPA. This proves the pipeline and
state machine are sound; it is **not** a substitute for a human timing
their actual pitch delivery in a browser, which is called out below as a
founder follow-up.

Sequence per run: ingest PIBAS CSV → engine ranks suspects → Urdu explain
(Groq) → signed EOD PDF → Excess Ledger open → countersign → close →
explain (Groq) → Daily Register PDF → cheque capture → cheque register →
2 pre-post checks → both hash-chain verifies.

Run 1 (business_date = today) and run 2 (business_date = yesterday, to
guarantee the `(branch, teller, business_date)` uniqueness constraint
can't collide) both completed with every HTTP call returning
201/200/`passed: true` as expected — confirmed both via script assertions
and by tailing `docker compose logs backend` (no 4xx/5xx, no tracebacks).

| Run | Session variance | Excess case | Excess chain after | Audit chain after |
|---|---|---|---|---|
| 1 | −5,960 PKR | rows 1→6 (opened→countersigned→closed) | `ok: true`, 6 rows | `ok: true`, 12 entries |
| 2 | −67,300 PKR | rows 6→9 | `ok: true`, 9 rows (cumulative) | `ok: true`, 20 entries (cumulative) |

Both chains grew monotonically across the two runs (append-only, no
resets, no state pollution) and re-verified clean after run 2.

**Total API-level time for both full runs: 13.25s** — this is latency
headroom, not a substitute for the actual timed pitch rehearsal (see
below). Slowest steps were the two Groq calls (~2.7–2.9s each) and CSV
ingest/engine run (~0.4–3.1s); everything else (Excess Ledger
transitions, cheque capture, pre-post checks, chain verifies) was
double-digit milliseconds.

- Post-dry-run `pytest -q` re-run: still **78 passed** — the demo writes
  didn't disturb anything (test fixtures TRUNCATE their own tables).

### Stated limitations (founder follow-ups, not completed here)

1. **No browser console / unhandled-promise-rejection check.** Nothing in
   this environment can open the SPA in an actual browser. Recommend
   opening `http://localhost:5173` and clicking through all 4 screens with
   devtools open before the pitch.
2. **No timed human dress rehearsal.** The 13.25s figure above is backend
   API latency for a scripted run, not a human narrating the pitch through
   the UI. The "one dress rehearsal timed under 5 minutes" verification
   line in `v2_plan.md` still needs a person to actually do.
3. **Anti-delusion guardrail carries forward unchanged**: still n=1 teller
   interviews (Khursheed) as of this phase closing; Session 6 (Jul 13) is
   the window CLAUDE.md flags as closing. Nothing in Phases 13–15 changes
   that — it's a human research task, not a code task.

### All phases 9–15 now closed

Backend (11–13), frontend (14), and integration (15) all green on a
from-scratch bring-up. `docker compose up` works clean with no Qdrant
references anywhere in the stack.
