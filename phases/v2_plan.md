# ZeroBalance v2 — Phase Plan

**Fork:** v1 frozen at `D:\ZeroBalance`. All v2 work in `D:\ZeroBalance_v2`.

**v1 phases 1–8** in `/phases/phase_<1..8>.md` are historical delivery log. Do not edit.

**v2 phases 9–15** delivered (see `phases/phase_<9..15>.md`).

**v2.1 phases 16–17** below — added Jul 12 after Kimi review + Cash Movement Ledger scope call.

Per CLAUDE.md phase workflow, each phase gets its own `/phases/phase_<n>.md` created at start (Goal / Structure / Steps / Commands / Expected) and updated at close (Actual outcome).

## Phase table

| # | Phase | Owner | Est | Gate to next | Status |
|---|---|---|---|---|---|
| 9 | v2 Baseline Cleanup | Arham | 2h | Docker Compose runs clean (no Qdrant); no `rahbar` imports resolve; `pytest` green | Done |
| 10 | Schema v2 + ground_truth v2 extension | Arham + Miswan | 3h | 4 new tables migrate cleanly; oracle covers Excess Ledger, cheque MICR mismatch, 5 pre-post checks | Done |
| 11 | Digital Excess Ledger (backend) — **flagship** | Arham | 4h | CRUD + dual sign-off + hash chain; state transitions are INSERTs only; tests green | Done |
| 12 | Cheque Capture + Pre-post demo endpoints (backend) | Arham | 4h | Cheque MICR + denom-out saved; 5 pre-post endpoints return check results; tests green | Done |
| 13 | Groq extension + PDF report additions | Arham | 3h | Urdu explanations for Excess Ledger + cheque variance; Excess Ledger Daily Register PDF renders on brand | Done |
| 14 | Frontend v2 (4 screens) | Wahaj / Claude | 10h | Excess Ledger + EOD worklist + Cheque Capture + Pre-post Demo — all wired to backend, brand-correct, RTL-safe | Done |
| 15 | Integration + demo dry run | All | 2h | End-to-end CSV → PDF flow works twice back-to-back; hash chain verify green; no console errors | Done |
| **16** | **Cash Movement Ledger backend + migration** | **Claude** | **3h** | **CML endpoints green; `opening_float_declaration` dropped (0 rows, no dependents); `ground_truth_v2.py` covers reissue + handover; tests green** | **Done** — `phases/phase_16.md`, 95 passed |
| **17** | **Cash Movement UI + Denom-view EOD + Verify Chain button** | **Wahaj / Claude** | **3h** | **Cash Movement screen renders 4 event types; denomination-view EOD table wired; verify-chain button hits both chains; no console errors** | **Pending — backend gate green** |

**Total v2.1: ~34h delivered + ~6h remaining. Well within 65h load.**

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

**Wahaj owns** *(Claude built by explicit user instruction — see `phases/phase_14.md`)*. Four screens, build order = pitch priority:

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

---

## Phase 16 — Cash Movement Ledger backend + migration *(NEW in v2.1)*

**Why this phase exists:** v2 shipped with `opening_float_declaration` scoped as day-start only. Two gaps surfaced Jul 12:

1. **Mid-day vault reissue** — teller runs low on a denomination, OM reopens vault, issues more cash. Happens 1–3× per high-volume day per Khursheed. Without capture, opening + transactions − closing ≠ 0 for every teller who got a reissue → Excess Ledger fills with false positives.
2. **Shift handover** — between-shift teller swap has no capture surface.

Both fix via a single event-typed ledger. See vault: `Cash Movement Ledger.md` for full design.

**Goal:** Add `cash_movement_ledger` + `cash_movement_denominations` tables. Migrate `opening_float_declaration` rows into `cash_movement_ledger` with `event_type='day_start'`. Expose CRUD + verify-chain endpoints. Extend variance calculation to sum across `day_start` + `reissue` events. Update oracle.

**Touches:**
- `backend/schema.sql` — append the 2 new tables + hash-chain trigger mirroring `excess_ledger`. Drop `opening_float_declaration` table AFTER data migrates. (If migration risk is unacceptable at demo time, leave `opening_float_declaration` as a VIEW over `cash_movement_ledger WHERE event_type='day_start'`.)
- `backend/app/db_models.py` — SQLAlchemy models for `CashMovementLedger`, `CashMovementDenomination`. Remove old `OpeningFloatDeclaration` model (or keep as read-only view mapping).
- `backend/app/service.py` — `cash_movement_service`. Creates one ledger row + N denomination rows in a single transaction. Enforces dual-sign requirement per event type (`handover` needs three signers).
- `backend/app/api.py` — 4 new routes:
  - `POST /api/v1/cash-movement` — `{ event_type, teller_id, counterparty_id?, om_id, session_id, denominations: [{denom, count}], signoffs: {teller, counterparty?, om} }`
  - `GET /api/v1/cash-movement?teller_id=&session_id=&from_date=&to_date=` — event stream with denomination breakdown JOINed
  - `GET /api/v1/cash-movement/verify-chain` — chain integrity report
  - `GET /api/v1/eod/reconciliation?teller_id=&business_date=` — computed `{ per_denom: [{ denom, opening_plus_reissues, deposits_in, withdrawals_out, expected, physical, variance }], top_signatures: [...] }`
- `backend/app/reconcile.py` — update variance calculation to SUM(count) FROM `cash_movement_denominations` JOIN ledger WHERE `event_type IN ('day_start','reissue')` per denomination.
- `backend/tests/test_cash_movement.py` — new. Test happy path per event type + reissue variance flow + handover three-signer + INSERT-only enforcement + hash chain across events.
- `data/ground_truth_v2.py` — add scenarios: `reissue_midday_single_denom`, `reissue_midday_multiple_denoms`, `handover_between_tellers`, `variance_after_reissue_correctly_zero`, `variance_after_reissue_denom_swap`.
- Migration script `migrations/016_cash_movement_ledger.sql` — additive DDL + `INSERT INTO cash_movement_ledger SELECT ... FROM opening_float_declaration`. Idempotent.

**As delivered (see `phases/phase_16.md` for full detail) — two deviations from this sketch, both intentional:**
1. `opening_float_declaration` had 0 rows and no reader/writer anywhere in the app (grepped before touching it) — dropped outright rather than migrated/kept as a view. No `service.py` cash_movement_service either; landed as its own `app/cash_movement.py` module (event log, not a state machine, so it didn't fit alongside `service.py`'s CSV-ingest orchestration).
2. `GET /eod/reconciliation` returns `{ per_denom: [{ denomination, opening_plus_reissues, physical, variance }] }` — no `deposits_in`/`withdrawals_out`/`expected`/`top_signatures`. CBS transactions carry no denomination breakdown (per-transaction denomination capture is permanently forbidden), so `deposits_in`/`withdrawals_out` per denomination isn't computable from real data — building it would mean inventing numbers. `top_signatures` was dropped as redundant: the existing `suspects` ranking is already served by the session-detail endpoint from Phase 1-8, and the P17 UI plan already places this table "above the existing ranked-suspects list" as a separate element.

**Verify:**
- `docker compose exec backend pytest -q` — full suite green including new tests.
- Existing v2 tests (78 passing) still green after schema change.
- `SELECT COUNT(*) FROM cash_movement_ledger WHERE event_type='day_start'` matches pre-migration `opening_float_declaration` count.
- Hash chain verify green across a `day_start` → `reissue` → `day_end` sequence.
- EOD variance = 0 across all denominations for a simulated day with 3 hours of transactions + 1 mid-day reissue.

**Non-goals for P16:**
- No UI work. That's Phase 17.
- No new `event_type` values beyond the four locked (`day_start` / `reissue` / `handover` / `day_end`).
- No cross-teller aggregation queries. Per-teller only.

## Phase 17 — Cash Movement UI + Denomination-view EOD + Verify Chain button *(NEW in v2.1)*

**Goal:** Surface Phase 16 backend in the dashboard. Add two more Kimi-approved UI beats (denomination-view EOD table + verify-chain button).

**Touches:**
- `frontend/src/screens/CashMovement.tsx` — one component, four contexts (config-driven by `event_type`). Denomination grid + dual/triple PIN sign-off. Reuse denomination grid component from Excess Ledger where possible.
  - `day_start` context: "Opening float — receive from OM" header, Teller + OM PIN.
  - `reissue` context: "Vault reissue — additional cash" header, Teller + OM PIN.
  - `handover` context: "Shift handover to [Teller B]" header, three PINs.
  - `day_end` context: "Closing count" header, Teller + OM PIN.
- `frontend/src/screens/EODReconciliation.tsx` — add denomination-view table:
  - Columns: denomination, opening + reissues, deposits in, withdrawals out, expected, physical, variance (highlighted red if ≠ 0).
  - Wire to `GET /api/v1/eod/reconciliation`.
  - Sits above the existing ranked-suspects list.
- `frontend/src/screens/EODReconciliation.tsx` — add **Verify Chain** button:
  - Button labeled "Verify Audit Chain" — mocha accent, ink text.
  - On click: parallel calls to `GET /excess-ledger/verify-chain` + `GET /cash-movement/verify-chain`.
  - Result panel: rows scroll in with green check per row for OK, red X + break location for failure. 30-second demo beat.
- `frontend/src/router.tsx` — add `/cash-movement/:eventType?` route.
- `frontend/src/components/DenominationGrid.tsx` — extract from Excess Ledger for reuse.

**Verify:**
- All 5 screens (Excess Ledger, EOD, Cheque, Pre-post Demo, Cash Movement) render and route.
- Cash Movement screen renders correctly for all 4 `event_type` values.
- Denomination-view EOD table shows zero variance for a simulated clean day.
- Verify Chain button animates through both chains in <3s.
- Docker Compose clean bring-up, no console errors, RTL Urdu still safe.
- Brand palette respected.

**Gate:** Phase 16 backend must be fully green. Do not start P17 UI on stub backend.

## Anti-scope-creep checkpoint (run at every phase close)

Before marking a phase complete, answer four questions:

1. Did we build anything not on the LOCKED four-feature list?
2. Did any decision, ranking, or filter route through Groq that should be deterministic?
3. Did any UPDATE / DELETE sneak into ledger paths?
4. Did we build anything OM / BOM / Regional / half-yearly-specific?

**Additional check for P16/P17:**

5. Did we build cross-teller aggregation, OM dashboards, or teller performance analytics? (All rejected in Jul 12 Kimi review — see CLAUDE.md "Rejected in v2.1".)
6. Did per-transaction denomination entry sneak in anywhere? (Permanently forbidden.)

Any yes → revert or file as roadmap slide. Do not advance the phase.

## Parallel non-code track (outside phases)

Not code work, but blocks the pitch — Arham owns scheduling:

- **Half-year closing scope call (B vs. C)** — dedicated discussion in a fresh chat (see `hy_closing_chat_kickoff.md`). Blocks pitch deck update.
- **2 more teller interviews** — still n=1 (Khursheed only) as of Jul 12.
- Paper wireframes for Cash Movement screen (Phase 17) before Session 6.
- Manual browser dress rehearsal of full pitch demo under 5 minutes — carried forward from Phase 15 follow-ups.
- Rewrite pitch deck around Excess Ledger as flagship. Do NOT use Kimi's rejected demo script (contains the "20-year veteran teller" false claim).