# ZeroBalance v2 — Phase Plan

**Fork:** v1 frozen at `D:\ZeroBalance`. All v2 work in `D:\ZeroBalance_v2`.

**v1 phases 1–8** in `/phases/phase_<1..8>.md` are historical delivery log. Do not edit.

**v2 phases 9–15** below. Per CLAUDE.md phase workflow, each phase gets its own `/phases/phase_<n>.md` created at start (Goal / Structure / Steps / Commands / Expected) and updated at close (Actual outcome).

## Phase table

| # | Phase | Owner | Est | Gate to next |
|---|---|---|---|---|
| 9 | v2 Baseline Cleanup | Arham | 2h | Docker Compose runs clean (no Qdrant); no `rahbar` imports resolve; `pytest` green |
| 10 | Schema v2 + ground_truth v2 extension | Arham + Miswan | 3h | 4 new tables migrate cleanly; oracle covers Excess Ledger, cheque MICR mismatch, 5 pre-post checks |
| 11 | Digital Excess Ledger (backend) — **flagship** | Arham | 4h | CRUD + dual sign-off + hash chain; state transitions are INSERTs only; tests green |
| 12 | Cheque Capture + Pre-post demo endpoints (backend) | Arham | 4h | Cheque MICR + denom-out saved; 5 pre-post endpoints return check results; tests green |
| 13 | Groq extension + PDF report additions | Arham | 3h | Urdu explanations for Excess Ledger + cheque variance; Excess Ledger Daily Register PDF renders on brand |
| 14 | Frontend v2 (4 screens) | Wahaj | 10h | Excess Ledger + EOD worklist + Cheque Capture + Pre-post Demo — all wired to backend, brand-correct, RTL-safe |
| 15 | Integration + demo dry run | All | 2h | End-to-end CSV → PDF flow works twice back-to-back; hash chain verify green; no console errors |

**Total: ~28h.** Comfortably within 65h load. Wahaj no longer the bottleneck — Arham is at ~16h backend.

## Phase 9 — v2 Baseline Cleanup

**Goal:** Remove v1 dead code (Rahbar / Qdrant), keep Isolation Forest as display-only, update Docker Compose and README stub.

**Touches:**
- Delete: `backend/app/rahbar.py`, `backend/tests/test_rahbar.py`
- Edit: `backend/app/main.py` (drop rahbar route registration), `backend/requirements.txt` (drop `qdrant-client`), `docker-compose.yml` (remove `qdrant` service + volume + `QDRANT_URL` env), `README.md` (v2 stub — cut Rahbar paragraph, cut Qdrant mention).

**Verify:**
- `docker compose config` passes.
- `grep -r rahbar backend/` returns nothing.
- `pytest` still green (minus removed rahbar tests).

## Phase 10 — Schema v2 + ground_truth v2

**Goal:** Add 4 new tables. Extend the oracle to cover all new scenarios before we tune anything.

**Touches:**
- `backend/schema.sql` — append `opening_float_declaration`, `excess_ledger`, `cheque_transactions`, `validation_log`. Add hash-chain trigger on `excess_ledger` mirroring the existing audit-ledger trigger.
- `backend/app/db_models.py` — SQLAlchemy models for the 4 new tables.
- `data/ground_truth.py` — labeled cases for: Excess Ledger open→countersign→close happy path; Excess Ledger closed without countersign (must reject); cheque MICR-vs-account mismatch; 5 pre-post checks (denom sum, CNIC↔name fuzzy, duplicate post, large-amount confirm, sanity).

**Verify:**
- Fresh Postgres init from `docker compose up` loads schema clean.
- `pytest data/` covers every new scenario.
- Hash chain trigger rejects out-of-order inserts.

## Phase 11 — Digital Excess Ledger (flagship)

**Goal:** The one feature Khursheed flagged unprompted as a corruption vector. This is what the pitch stands on.

**Touches:**
- `backend/app/service.py` — Excess Ledger service.
- `backend/app/api.py` — routes under `/api/v1/excess-ledger`.
- `backend/tests/test_excess_ledger.py` — new.

**Endpoints:**
- `POST /api/v1/excess-ledger/open` — teller opens entry (excess or short, amount, note).
- `POST /api/v1/excess-ledger/{id}/countersign` — second officer signs. Insert row, not update.
- `POST /api/v1/excess-ledger/{id}/close` — resolution note + close. Insert row.
- `GET /api/v1/excess-ledger?from=&to=` — daily register (date range — supports half-yearly).
- `GET /api/v1/excess-ledger/verify-chain` — audit hash chain check.

**Verify:**
- Every state transition produces INSERT rows only (no UPDATE).
- Close without countersign is rejected at service layer.
- Hash chain verify returns clean after a full open→countersign→close sequence.

## Phase 12 — Cheque Capture + Pre-post demo

**Cheque:**
- `POST /api/v1/cheque` — MICR + account + amount + denomination-out breakdown.
- `GET /api/v1/cheque?from=&to=` — date range.
- Validation: denomination-out sum must equal amount; MICR must resolve to a known account.

**Pre-post (demo endpoints — NOT wired to CBS write path):**
- `POST /api/v1/prepost/denom-sum`
- `POST /api/v1/prepost/cnic-name-match`
- `POST /api/v1/prepost/duplicate-check`
- `POST /api/v1/prepost/large-amount-confirm`
- `POST /api/v1/prepost/sanity`

Each endpoint logs to `validation_log` and returns `{ passed: bool, reason?: string }`.

**Verify:** Every check has an oracle-backed test.

## Phase 13 — Groq + PDF

**Goal:** Extend Urdu explanations to Excess Ledger openings and cheque variances. Add Excess Ledger Daily Register PDF.

**Touches:** `backend/app/explain.py`, `backend/app/report.py`.

**Verify:**
- PDF renders with brand palette (ink / mocha / cream).
- Groq responses have CNIC + account masked before send.
- Explanations are post-hoc only — Groq never receives ranked-suspect input as a set to re-rank.

## Phase 14 — Frontend v2

**Wahaj owns.** Four screens, build order = pitch priority:

1. **Excess Ledger** — open + countersign + daily register. Ships first.
2. **EOD Recon Report** — worklist + PDF download.
3. **Cheque Capture** — MICR + amount + denom-out.
4. **Pre-post Demo** — 5 checks fire live on typed input (marketing surface — make it feel real).

**Gate:** Backend Phases 11–13 must be green. Excess Ledger UI ships before anything else on the frontend.

**Verify:**
- All 4 screens wired to backend.
- Urdu renders RTL-safe.
- Brand palette respected (cream backgrounds, ink text, mocha accents; Cambria/Calibri fonts with fallbacks).

## Phase 15 — Integration + demo dry run

**Goal:** End-to-end from PIBAS CSV → recon → Excess Ledger sign-off → signed PDFs. Rehearse the 5-minute demo. No console errors, no unhandled promise rejections.

**Verify:**
- `docker compose up` from a clean state.
- Demo runs twice back-to-back without state pollution between runs.
- Hash chain verify green after full run.
- One dress rehearsal timed under 5 minutes.

## Anti-scope-creep checkpoint (run at every phase close)

Before marking a phase complete, answer four questions:

1. Did we build anything not on the LOCKED four-feature list?
2. Did any decision, ranking, or filter route through Groq that should be deterministic?
3. Did any UPDATE / DELETE sneak into ledger paths?
4. Did we build anything OM / BOM / Regional / half-yearly-specific?

Any yes → revert or file as roadmap slide. Do not advance the phase.

## Parallel non-code track (outside phases)

Not code work, but blocks the pitch — Arham owns scheduling:

- **2 more teller interviews before Session 6 (Jul 13).** n=1 as of Jul 11. Session 6 kills the pitch at PSF questions otherwise.
- Paper wireframes for the 4 v2 screens before Session 6.
- Rewrite pitch deck around Excess Ledger as flagship (not pre-post).
