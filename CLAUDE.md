# CLAUDE.md — ZeroBalance v2.1

Bank-teller back-office validation + reconciliation layer. Sits between the teller and the CBS (PIBAS / T24 / Symbols). On-prem. **Overlay, not replacement** — never re-architects CBS; always monitors it or sits beside it.

Hackathon MVP (UBL National Innovation Hackathon, 72-hour final). This file is authoritative for v2.1 — do not re-architect anything marked LOCKED.

**v1 is frozen at `D:\ZeroBalance`.** All v2 work happens in `D:\ZeroBalance_v2`. Do not touch v1.

**v2.1 delta from v2 (Jul 12):** Cash Movement Ledger replaces `opening_float_declaration` — captures mid-day vault reissues + handovers, denomination-broken, dual-signed. Kimi (external LLM) review outcomes applied. See `phases/phase_16.md` onward.

## Value proposition — LOCKED

*"CBS posts what the teller types. ZeroBalance makes sure the teller typed the truth."*

Two audit cadences from **one artifact set**:

- **Daily EOD** — teller close-of-day certification.
- **Half-yearly closing** — same artifacts, different query window. No new features. Do not hard-code `yesterday` or `today` in queries — take a date range.

## Persona scope

| Persona | v2 build scope | v2 pitch role |
|---|---|---|
| Teller | **Yes** — primary user | Primary buyer signal |
| Operations Manager / BOM | **Sign-off only** — no OM dashboard | Phase 2 narrative slide |
| Regional Ops / SBP reporting | **No** | Phase 3 narrative slide |

Anyone proposing OM dashboards, branch-aggregate views, or cross-teller analytics as v2 build → stop and flag. OM interaction is limited to dual sign-off on Excess Ledger and Cash Movement events.

## Feature set — LOCKED (four items, nothing else)

Ranked by willingness-to-buy. Each row shows overlay posture (how it sits relative to CBS) and whether it touches the CBS write path.

| # | Feature | Overlay posture | Touches CBS write path? | Build scope |
|---|---|---|---|---|
| 1 | Digital Excess Ledger + dual sign-off + audit hash | Sidecar | No | **Full — flagship** |
| 2 | EOD recon (Cash Movement Ledger → engine → ranked culprits → signed PDF) | Monitor (reads CBS CSV export) | No | Full |
| 3 | Cheque capture (MICR + denomination-out breakdown) | Sidecar | No | Full |
| 4 | Pre-post real-time validation (5 checks) | Intercept | Yes (in front of CBS) | **Demo-only surface** — endpoints + UI screen, NOT wired into CBS write path |

**Data spine (infrastructure, not user-visible as a "feature"):** Cash Movement Ledger — event-typed (`day_start` / `reissue` / `handover` / `day_end`), denomination-broken, dual-signed, hash-chained, INSERT-only. Powers feature 2. See `phases/phase_16.md`.

Pre-post is the only feature that touches the CBS write path — that's why banks can veto it, and that's why it stays a demo surface, not a wired intercept.

## Stack — LOCKED

| Layer | Choice | Notes |
|---|---|---|
| Backend | FastAPI (Python 3.12) | |
| Database | PostgreSQL 16 | Audit ledger + Excess Ledger + Cash Movement Ledger all append-only; hash chains; never weaken |
| Matching | Rule-based variance signatures | Deterministic. No ML ranking anywhere |
| String matching | rapidfuzz | **Kept in v1 dependency set** for Excess Ledger case-ref fuzzy search only. Pre-post CNIC↔name matching stays demo-only. |
| Anomaly | scikit-learn Isolation Forest | **Display-only signal.** Cannot override or re-rank rule flags |
| AI explanation | Groq API (Llama 3.3 70B) | Explains engine output post-hoc, in Urdu. NEVER decides, ranks, filters, or scores |
| Frontend | React 18 + Vite + TanStack Query | No Next.js, no SSR |
| Infra | Docker Compose | Postgres + backend + frontend. **No Qdrant** |

**Cut from v2** (were present in v1 — remain removed):

- Rahbar / Saathi RAG (Qdrant). Do not restore `backend/app/rahbar.py`, `backend/tests/test_rahbar.py`, `qdrant-client` in `requirements.txt`, or the `qdrant` service in `docker-compose.yml`.

**Rejected in v2.1 (Kimi review, Jul 12) — do not build:**

- Per-transaction denomination capture (permanently forbidden — double-entry burden that killed prior digital rollouts)
- Teller performance scorecard (politically toxic in PK banking; fabricated ROI from synthetic data)
- Global competitive matrix vs. HighRadius/Trintech/BlackLine (category confusion; enterprise GL, not teller-workstation)
- Mid-shift checkpoint (n=0 user validation — roadmap only)
- Half-year closing "4h vs 4d" narrative with fabricated stats (see anti-delusion guard)

Do not add new dependencies, services, or frameworks without explicit approval in chat.

## Architecture — LOCKED

Primary flow: `Teller Input → [Pre-post checks (demo)] → Matching Engine → Flag Engine → Groq (Urdu explanation) → Dashboard → PostgreSQL audit ledger`

Sidecar artifacts (parallel to CBS, not in its write path): Digital Excess Ledger, Cash Movement Ledger, cheque capture — separately hashed and signed.

Hard constraints:

1. **Deterministic engine.** Culprit detection = pattern match on variance signatures: digit transposition, duplicate posting, missed reversal, denomination-specific shortfall, cash-in/out miskey, wrong adjacent account. Output: ranked top 3–5 suspects. Every ranking reproducible and rule-explainable. No learned ranking anywhere in this path.
2. **Groq explains, never decides.** Groq receives the engine's already-ranked picks and produces Urdu explanations. If a change routes any decision, score, ranking, or filtering through Groq → stop and flag.
3. **One denomination count per Cash Movement event.** Never per-transaction. Denomination breakdown at `day_start`, `reissue`, `handover`, `day_end` only. Per-transaction denomination entry is a forbidden anti-pattern — do not build forms, endpoints, or schema for it.
4. **Cash Movement Ledger is the audit-trail spine.** All vault↔teller cash movement is denomination-broken, dual-signed, and hash-chained. `event_type` in {`day_start`, `reissue`, `handover`, `day_end`}. Every teller session begins with a `day_start` event. Mid-day vault reopenings emit a `reissue` event. Every event required for correct EOD variance calculation.
5. **Ingestion = CSV export from CBS (PIBAS format).** Do not build against any PIBAS API or direct DB connection — that surface does not exist for us.
6. **Pre-post is demo-only.** Endpoints exist for the 5 checks, UI screen shows them firing on typed input. But: **no CBS write-path interception in the actual production flow.** Marketing surface, not production surface.
7. **On-prem posture.** No cloud services beyond the Groq API call. No customer data in external logs.
8. **Append-only ledgers.** Audit ledger, Excess Ledger, AND Cash Movement Ledger. Never add UPDATE/DELETE paths. Dual sign-off = two INSERT rows referencing the same entry, not an UPDATE. Same for corrections.

## Schema v2.1 — five tables + one rename

Additive to v1 schema. Do not modify existing tables destructively.

| Table | Purpose |
|---|---|
| `cash_movement_ledger` *(NEW in v2.1, replaces `opening_float_declaration`)* | Event-typed ledger for vault↔teller cash movement. `event_type` ∈ {`day_start`, `reissue`, `handover`, `day_end`}. `teller_id`, `counterparty_id` (OM or other teller for handover), `om_id`, `session_id`, `event_time`, `total_amount`, `signoff_teller`, `signoff_counterparty`, `signoff_om`, `prev_hash`, `row_hash`. Hash-chained, INSERT-only. |
| `cash_movement_denominations` *(NEW in v2.1)* | Denomination breakdown per movement event. `movement_id`, `denomination` ∈ {5000, 1000, 500, 100, 50, 20, 10}, `count`, generated `amount`. UNIQUE (movement_id, denomination). |
| `excess_ledger` | Flagship. Append-only event table. Rows share `case_ref` (UUID) and are sequenced by `event_seq`. `event_type` in {opened, countersigned, closed}. Global hash chain (prev_hash / entry_hash). Trigger blocks UPDATE/DELETE. |
| `cheque_transactions` | MICR string, account_number, amount, denomination_out (JSONB), captured_at. Plain INSERT — not chained. |
| `validation_log` | Pre-post demo log. teller_id, check_name (enum of the 5 checks), input_hash (SHA-256), passed, failed_reason, checked_at. |

**Deprecation:** `opening_float_declaration` from v2 — **dropped in Phase 16**, not left as a view. Grepped before dropping: no endpoint ever wrote to it (`IngestMeta.opening_float`, the value the matching engine actually uses, is a teller-typed scalar passed at CSV-ingest time, never connected to this table) and the live dev DB had 0 rows. No migration risk, so the CLAUDE.md fallback ("leave as VIEW") didn't apply.

## Build sequence & gates

Order: baseline cleanup → schema v2 → ground_truth v2 → Excess Ledger backend → cheque + pre-post backend → Groq + PDF → frontend v2 → integration → **Cash Movement Ledger backend (P16) → Cash Movement UI + denom-view EOD + verify-chain button (P17)**.

Gates — do not start a later phase until the earlier gate passes:

- **v2 frontend work is blocked** until Excess Ledger backend is green (Phase 11). [Already met.]
- **EOD frontend work** stays blocked until the matching engine hits ≥90% single-error / ≥70% two-error against `ground_truth.py` (v1 gate carries forward). [Already met.]
- `ground_truth_v2.py` must cover the 5 pre-post checks + Excess Ledger open/countersign/close + cheque MICR-mismatch scenarios before feature phases advance. [Already met.]
- **Phase 17 UI work is blocked** until Phase 16 Cash Movement Ledger backend is green + `ground_truth_v2.py` covers reissue + handover scenarios.
- Docker Compose must run clean with no Qdrant references before Phase 14 frontend integration begins. [Already met.]

## Phase workflow

- Before starting a phase, create `/phases/phase_<n>.md` with: Phase Goal, Project Structure, Steps, Commands, What to Expect (so it can be diffed against reality). Minimal text.
- After the phase is complete, update the same `/phases/phase_<n>.md` with what actually happened.
- **v2 phases start at `phase_9.md`.** `phase_1.md` through `phase_8.md` are v1 delivery log — do not edit.
- v2 roadmap index lives at `/phases/v2_plan.md`.

## Progress (as of Jul 13 2026)

| Phase | Scope | Status |
|---|---|---|
| 9 | v2 baseline cleanup (Rahbar / Qdrant cut, README v2) | **Done** — `phases/phase_9.md` |
| 10 | Schema v2 (4 new tables) + `ground_truth_v2.py` (20 scenarios) | **Done** — `phases/phase_10.md` |
| 11 | Digital Excess Ledger backend (flagship) — 5 endpoints, hash chain, dual sign-off | **Done** — `phases/phase_11.md` |
| 12 | Cheque capture + pre-post demo endpoints — 7 endpoints total | **Done** — `phases/phase_12.md` |
| 13 | Groq Urdu extensions (Excess Ledger + cheque variance) + Excess Ledger Daily Register PDF | **Done** — `phases/phase_13.md` |
| 14 | Frontend v2 (4 screens) | **Done** — `phases/phase_14.md`. Built by Claude on explicit user instruction, ahead of the original "Wahaj owns" handoff. No browser-automation tool was available to visually verify the UI; contracts were smoke-tested live against the backend instead. |
| 15 | Integration + demo dry run | **Done** — `phases/phase_15.md`. Clean-state bring-up + full demo sequence run twice via the API. |
| **16** | **Cash Movement Ledger backend — schema addition, drop `opening_float_declaration`, 4 endpoints, `ground_truth_v2.py` scenario expansion** | **Done** — `phases/phase_16.md`. `opening_float_declaration` dropped outright (0 rows, no reader/writer ever existed). `GET /eod/reconciliation` built without the originally-sketched `deposits_in`/`withdrawals_out` fields — that data doesn't exist (no per-transaction denomination capture) and fabricating it would violate anti-delusion guardrail #6; returns `opening_plus_reissues` / `physical` / `variance` per denomination instead. |
| **17** | **Cash Movement Ledger UI + Denomination-view EOD reconciliation table + Verify-chain demo button surfacing** | **Pending** — backend gate (Phase 16) is green |

**Verified before advancing** (user's local Postgres): all tests through the completed phase must pass under `docker compose exec backend pytest -q`. Do not start a later phase without that gate. Full suite as of Phase 16: **95 passed**, confirmed on a from-scratch `docker compose down -v && up --build`.

**Public API so far** (v2 additions under `/api/v1`):

- `POST /excess-ledger/open`, `POST /excess-ledger/{case_ref}/countersign`, `POST /excess-ledger/{case_ref}/close`, `GET /excess-ledger?from_date=&to_date=&branch=`, `GET /excess-ledger/verify-chain`, `POST /excess-ledger/{case_ref}/explain`, `GET /excess-ledger/report.pdf?from_date=&to_date=&branch=`
- `POST /cheque`, `GET /cheque?from_date=&to_date=&branch=`, `POST /cheque/explain`
- `POST /prepost/denom-sum`, `/cnic-name-match`, `/duplicate-check`, `/large-amount-confirm`, `/sanity`
- `POST /cash-movement` — creates one event row + denomination rows, dual/triple-signed (handover = triple), hash-chained.
- `GET /cash-movement?teller_id=&session_id=&from_date=&to_date=` — event stream with denom breakdown (all filters optional).
- `GET /cash-movement/verify-chain` — chain integrity across the ledger.
- `GET /eod/reconciliation?teller_id=&business_date=` — per-denomination `opening_plus_reissues` / `physical` / `variance` (feeds denomination-view EOD table in P17).

**Outstanding founder follow-ups (not code — see `phases/phase_15.md` for detail):**

- Manual browser pass of all screens (devtools open, check console/RTL Urdu rendering) — no browser-automation tool exists in this environment.
- One timed human dress rehearsal of the pitch demo, under 5 minutes.
- Anti-delusion guardrail carries forward unchanged: still n=1 teller interviews (Khursheed) as of this update.
- **Half-year closing scope call (B vs. C):** deferred to a separate discussion. See vault: `Feature List.md` → "Half-year closing — under review."

## Testing

- `data/ground_truth.py` is the engine oracle (variance signatures). Do not mix v2 scenarios into it.
- `data/ground_truth_v2.py` is the v2 scenario oracle (Excess Ledger transitions, cheque MICR/denom, 5 pre-post checks, Cash Movement event types). 29 scenarios (7 excess + 4 cheque + 10 prepost + 8 cash_movement).
- pytest for backend. Every variance-signature rule, every Excess Ledger state transition, every cheque validation, every pre-post check, and every Cash Movement event type gets at least one oracle-backed test.
- Tests run inside the compose container (`docker compose exec backend pytest -q`) against the live dev Postgres. Fixtures truncate the v2 tables + `audit_ledger` + `cash_movement_ledger` + `cash_movement_denominations` per test (`TRUNCATE ... RESTART IDENTITY CASCADE`).
- Never "fix" a failing test by loosening the oracle — flag the mismatch instead.

## Frontend / brand

Palette: ink `#1A1A18`, mocha `#8B7355`, cream `#FAF8F3`. Cream backgrounds, ink text, mocha accents.

Fonts: Cambria for headings, Calibri for body — with web-safe fallbacks: `Cambria, Georgia, serif` / `Calibri, 'Segoe UI', system-ui, sans-serif`.

Language: English UI chrome; Groq explanations render in Urdu inside RTL-safe containers.

**v2 dashboard screens (five in v2.1; nothing else):**

1. **Excess Ledger** — open entry, countersign, close, daily register view. Flagship.
2. **EOD Recon Report** — worklist, ranked suspects, denomination-view reconciliation table *(new in P17)*, signed PDF download, **Verify Chain button** *(new in P17 — surfaces existing `GET /excess-ledger/verify-chain` + new `GET /cash-movement/verify-chain`)*.
3. **Cheque Capture** — MICR + amount + denomination-out breakdown.
4. **Pre-post Demo** — 5 checks firing live on typed input. Demo/marketing surface.
5. **Cash Movement** *(new in P17)* — denomination grid + dual PIN sign-off. Same component rendered four ways via `event_type` (`day_start` / `reissue` / `handover` / `day_end`).

**Removed from v1 dashboard** (do not restore in v2):

- Ageing view — BOM feature, out of scope.
- Rahbar chat panel — RAG cut.

## Conventions

- Python: type hints everywhere, Pydantic v2 models, ruff for lint/format.
- API: REST, versioned under `/api/v1`. Pydantic response models on every route.
- Secrets (Groq key, DB creds) via `.env` — never committed, never hardcoded.
- Commits: small, per-feature. No mass rewrites of files that already pass their gate.
- If a request conflicts with anything LOCKED in this file → stop and say so instead of complying.

## Roadmap — DO NOT BUILD

Pitch slides only. Building any of them is scope creep:

- BOM branch console / OM dashboard → **Phase 2 pitch narrative**
- Regional Ops rollup, SBP report auto-export → **Phase 3 pitch narrative**
- Cash counter hardware integration (Glory / Kisan serial/USB)
- PIBAS direct API/DB integration
- Per-transaction denomination capture (permanently forbidden, not just deferred)
- Rahbar / Saathi RAG (cut from v2; do not restore)
- Isolation Forest as a ranking or filtering signal (must stay display-only)
- Pre-post CNIC↔name rapidfuzz check as production feature (roadmap; needs 3+ wrong-account incident evidence from partner data)
- Teller performance scorecard (rejected Jul 12)
- Mid-shift checkpoint (rejected Jul 12)
- Half-yearly closing option A (GL closing — different layer, different system)

## Anti-delusion guardrails

1. **n=1 is not evidence.** Every feature must survive 2+ teller conversations before it's called validated. As of Jul 12: still n=1 (Khursheed only).
2. **New feature ideas must pass three tests:** (a) 72hr demo-able, (b) strengthens novelty, (c) infra we control. Two nos → roadmap slide.
3. **Winning the hackathon ≠ shipping to a bank.** Don't pitch category-leader ambitions with hackathon-team evidence.
4. **Overlay, not replacement.** If a design starts asking CBS to change, it's the wrong design.
5. **External LLM proposals (Kimi, Claude, etc.) filter through the same guardrails as founder proposals.** LLMs pattern-match against generic banking-modernization templates, not against a specific Karachi branch. They fabricate stats and invent pain points. Jul 12 outcome: 2 of 5 Kimi proposals survived (both UI-only). Never accept LLM proposals wholesale — audit each against the three-tests + n=1 rule.
6. **Never claim a capability we don't have.** Especially in fintech. Simulated fake-note detection, fabricated accuracy numbers, and "20-year veteran teller" claims are all disqualifying if a judge asks for evidence. Report only what we measured.