# Continuous Reconciliation — Design

**Date:** 2026-07-09
**Project:** ZeroBalance (fresh exploration — deliberately unconstrained by v2 MVP scoping decisions)
**Status:** Draft — awaiting review, not committed

---

## Problem

Make a bank branch's daily operations, from teller to Operations Manager, faster — cutting time and workload while keeping trust and security.

In today's branch, reconciliation is a **batch event**. During the day nothing is cross-checked: CBS posts whatever the teller types, paper accumulates (cheque backs, excess ledger, handwritten reports), and all trust-verification work piles up at EOD. Twice a year it piles up catastrophically at the SBP half-yearly close (June 30 / Dec 31) — a branch-wide mega-EOD, forced-overtime event, and audit-exposure peak all at once. Every hour of teller/OM overtime is deferred reconciliation debt coming due.

**Reframe:** "make operations faster" = decide where the reconciliation work moves.

## Scoping decisions (from brainstorm)

| Question | Decision |
|---|---|
| Purpose | Fresh exploration; not bound by hackathon-MVP cut lines or v2 pitch decisions |
| Whose time | Teller's day + EOD close ritual + teller↔OM handoffs + half-yearly close |
| Trust stance | **Keep every control, digitize it.** Nothing removed — dual sign-off, counts, validation all stay, but become digital, parallel, instant |
| Scope | Cash lifecycle + all teller-touched work (cheques, remittances, RAAST/CDM, bills, pay orders) |
| CBS posture | **Layer around it.** CBS (AHBS/T24/Symbols) is untouchable legacy — validate before it, reconcile after it, keep trails beside it. Ingestion = CSV export only |

## Approaches considered

1. **A — Continuous Reconciliation** *(chosen)*: reconciliation becomes a background state maintained all day; EOD collapses to a confirmation. Biggest win, biggest teller-friction risk.
2. **B — Digitize the Handoffs**: only the five paper choke points (vault-out, cheque drawer, excess ledger, EOD report, OM validation) become signed digital artifacts. Teller's mid-day untouched, but the EOD investigation still exists. B is effectively a subset of A.
3. **C — The OM Cockpit**: OM-first supervision board. Requires A or B's data underneath to mean anything; alone it is a dashboard over a void. Becomes a natural later layer.

## Concept

**One line:** *The branch is always balanced — reconciliation is a state the system maintains all day, not an event the staff performs at night.*

The product is a **branch operations ledger** running beside CBS. It never touches CBS internals: it ingests CBS output (CSV exports, at whatever cadence the bank can produce) and captures everything CBS doesn't see — denominations, cheques, excess, handoffs, sign-offs — at the moment each happens. At any minute of the day it can answer: *"what should be in teller T's drawer right now, and does CBS agree?"*

### Design principles

1. **Every control kept, digitized.** Trust artifacts are append-only and hash-chained. Dual sign-off, physical counts, and validation all remain — digital, parallel, instant.
2. **The 2-second budget.** Any per-item capture must cost the teller ≤2 seconds over their current motion, or it gets redesigned or cut. The teller is the adoption gatekeeper.
3. **Reconcile continuously, close instantly.** Drift surfaces within minutes of occurring — while memory is fresh and the customer may still be at the counter — not at 6pm as archaeology.
4. **Every clean day makes the half-year free.** The half-yearly close is not a feature; it is a property. 180 signed, hash-chained daily closes roll up into a report on demand.

## The day, redesigned

| # | Stage | Today | Redesigned |
|---|---|---|---|
| 1 | Vault-out | OM hands bulk cash (e.g. PKR 1.9M), no denomination record; trust = memory | Denomination breakdown entered once (OM enters, or teller declares and OM confirms); both e-sign. This **opening float declaration** anchors the day's math. ~60s, once per day |
| 2 | Cash transactions | Teller types into CBS; CBS posts anything; errors invisible until EOD | Teller works in the ledger's thin transaction surface: validation (amount sanity, duplicate, large-amount confirm) then CBS entry. Each item updates the running expected-drawer position |
| 3 | Cheque cash-outs | Denominations handwritten on cheque back; cash out; cheque in drawer; zero digital trail | Quick capture: cheque amount + denominations out — same data the teller already writes, digital target. Within the 2s budget because it replaces a handwriting step |
| 4 | Other counter work (remittances, RAAST/CDM, bills, pay orders) | Per-instrument paper side-trails; all reconcile painfully at EOD | One lightweight capture per instrument type, feeding the same running position |
| 5 | Mid-day | Nothing; drift accumulates silently | Ledger continuously compares expected position vs. CBS ingests. Drift beyond threshold → quiet flag to teller (escalates to OM if unresolved). Caught in minutes |
| 6 | Excess cash | Paper Excess Ledger — corruption hotspot | Auto-entry to digital excess ledger when variance confirmed; dual sign-off; hash-chained. No silent-pocket path — the expected position already recorded the delta |
| 7 | EOD close | Count everything, hunt variances across the day, handwrite report, wait for OM | Count once, enter denomination totals. Expected position already known — match is instant. Residual variance ships with ranked culprits (existing ZeroBalance matching engine). Sign → OM co-signs → done. Target: minutes |
| 8 | OM validation & vault-in | Read paper report, re-verify manually, sequential per teller | Each teller's close arrives as a pre-verified card: expected vs. counted, exceptions resolved, signatures chained. Review + one sign-off; all tellers in parallel |
| 9 | Half-yearly close | Days of overtime; the half-year's uncaught errors surface at once | Rollup query over ~180 signed daily closes. The overtime event becomes a report button |

Structural change: stages 2–4 are where reconciliation debt used to be created; stage 5 pays it off continuously; stages 7–9 have almost nothing left to do.

## Architecture

Six components, one job each. Stack stays in the family the team knows: FastAPI (Python), PostgreSQL, React.

1. **Capture surfaces (React).** Thin per-instrument input screens: opening float, cash transaction, cheque cash-out, other instruments, EOD count. Minimal-click, icon-first, big-button denomination pads. Each surface is a small separate screen scoped to the current motion. The only part a teller ever touches.
2. **Position engine (Python, deterministic).** Maintains per-teller running state: `expected_drawer = opening_float + Σ(cash in) − Σ(cash out)`, at total and per-denomination level. Pure arithmetic plus the existing ZeroBalance variance-signature rules (digit transposition, duplicate posting, missed reversal, denomination shortfall, cash-in/out miskey, wrong adjacent account). **No ML in the trust path, ever** — every number reproducible and auditable by hand.
3. **Event ledger (Postgres, append-only).** Every capture, validation result, override, flag, and sign-off is an immutable event row, hash-chained (each event carries the previous event's hash). Corrections are new events referencing the old — never UPDATE/DELETE. This is what makes every control "digitized, not removed": the paper ledger's audit function, tamper-evident.
4. **CBS ingest (CSV).** Watches for CBS exports (PIBAS-format CSV), parses, matches CBS postings against captured events. Runs at whatever cadence the bank can export — EOD-only at worst, hourly at best. More frequent ingests only mean earlier drift detection; cadence is never a hard dependency.
5. **Sign-off service.** Dual sign-off as a first-class object: a declaration (float, excess entry, EOD close) is `pending` until both parties sign; signatures are ledger events, so chain of custody is queryable. PIN/credential re-entry per signature now; swappable for biometrics later without touching anything else.
6. **OM board (React, read-side only).** Per-teller position cards, exception queue, pending sign-offs, rollup report generator (daily close PDF → half-yearly rollup). Renders what components 2–3 already know; contains no logic of its own.

**Data flow:** capture surfaces → event ledger → position engine (recomputes expected position) → drift check against CBS ingest → flags/exceptions → sign-off service closes the loop → OM board renders it all.

**Explanation layer (optional, unchanged from ZeroBalance):** Groq/Llama Urdu one-liners explaining flagged exceptions — post-hoc, never deciding, ranking, or filtering.

## Exceptions & failure modes

- **Drift detected mid-day.** Quiet, non-blocking flag on the teller surface (e.g. "expected ₨1,942,500 / CBS shows ₨1,943,500 — likely extra-digit post around 11:42") with ranked candidate transactions. Teller resolves (correcting entry in CBS + correction event in ledger) or defers; deferred flags escalate to the OM board after a threshold. Never a hard block — the teller is serving a customer queue.
- **Validation failure at capture.** Warn; allow override with reason; the override is itself a ledger event. An override trail is stronger trust than a hard wall that gets worked around outside the system.
- **CBS export unavailable/delayed.** Graceful degradation to today's status quo: captures continue, position engine runs on captured data alone, reconciliation happens when the export lands.
- **Capture skipped in a counter rush.** The drift check catches it as a variance within the day, pointed at a time window — self-healing: cost of a missed capture is a localized flag, not a corrupted day.
- **Residual EOD variance (genuine loss/excess).** Flows to the digital excess ledger: amount, denominations, ranked culprits, resolution status, dual sign-off. Unresolved items stay visibly open on the OM board — they cannot silently age out (the paper ledger's exact corruption gap).
- **Sign-off refusal.** A dispute is an event; the close stays open with both positions recorded. Nothing merges until both sign.

## Success metrics

1. **Teller time-per-item** on capture surfaces vs. raw CBS entry: **≤ +2 seconds** (the adoption gate).
2. **Time-to-close-EOD** vs. current paper flow: **< 10 minutes on a clean day**; variance days measured separately.
3. **Half-yearly close effort**: rollup report in minutes; measured as overtime-days avoided. *(Baseline numbers for #2 and #3 needed from Khursheed / teller interviews.)*

## Testing

- **Oracle-driven.** Extend the existing `ground_truth.py` pattern: synthesize whole branch days (clean days, each fault mode, skipped captures, delayed ingests) with known-correct expected positions and culprits. Position engine and drift detection are tested exclusively against the oracle — never hand-picked examples. Never loosen the oracle to make a test pass.
- **Hash-chain integrity test.** Tamper with any event → chain verification must fail.
- **Sign-off state machine.** Exhaustive state-transition tests (pending → signed/disputed → closed).
- **Capture-surface stopwatch tests.** Human-timed against metric #1 before any polish work.

## Open questions / known risks

- **GASGADE risk is structural.** This is an all-day-touchpoint product; if per-item capture exceeds the 2-second budget in real use, adoption dies. Paper wireframes + teller stopwatch tests must precede real UI investment.
- **Evidence base is still n=1** (Khursheed, Bank Al Habib Mirpurkhas). The redesigned day must survive 2+ more teller walkthroughs, especially stages 3–4 (cheque + other instruments).
- **Relationship to the hackathon MVP is deliberately unresolved.** This design is the full vision; which slice (if any) becomes 72-hour build scope is a separate decision against the existing v2 cut lines.
- **CBS ingest cadence in production** (hourly vs. EOD-only) determines how "continuous" drift detection really is — worth asking Khursheed how often a branch can actually pull an export.
- **Thresholds are branch-configurable, not designed here.** Drift-flag threshold and large-amount confirmation threshold are config values with sane defaults (to be set with domain input), not hardcoded design decisions.
