# CLAUDE.md — ZeroBalance v2

Bank-teller back-office validation + reconciliation layer. Sits between the teller and the CBS (PIBAS / T24 / Symbols). On-prem. **Overlay, not replacement** — never re-architects CBS; always monitors it or sits beside it.

Hackathon MVP (UBL National Innovation Hackathon, 72-hour final). This file is authoritative for v2 — do not re-architect anything marked LOCKED.

**v1 is frozen at `D:\ZeroBalance`.** All v2 work happens in `D:\ZeroBalance_v2`. Do not touch v1.

## Value proposition — LOCKED

*"CBS posts what the teller types. ZeroBalance makes sure the teller typed the truth."*

Two audit cadences from **one artifact set**:

- **Daily EOD** — teller close-of-day certification.
- **Half-yearly closing** — same artifacts, different query window. No new features. Do not hard-code `yesterday` or `today` in queries — take a date range.

## Persona scope

| Persona | v2 build scope | v2 pitch role |
|---|---|---|
| Teller | **Yes** — primary user | Primary buyer signal |
| Operations Manager / BOM | **No** | Phase 2 narrative slide |
| Regional Ops / SBP reporting | **No** | Phase 3 narrative slide |

Anyone proposing OM UI, branch-aggregate views, or cash-movement between tellers as v2 build → stop and flag.

## Feature set — LOCKED (four items, nothing else)

Ranked by willingness-to-buy. Each row shows overlay posture (how it sits relative to CBS) and whether it touches the CBS write path.

| # | Feature | Overlay posture | Touches CBS write path? | Build scope |
|---|---|---|---|---|
| 1 | Digital Excess Ledger + dual sign-off + audit hash | Sidecar | No | **Full — flagship** |
| 2 | EOD recon (opening float → engine → ranked culprits → signed PDF) | Monitor (reads CBS CSV export) | No | Full |
| 3 | Cheque capture (MICR + denomination-out breakdown) | Sidecar | No | Full |
| 4 | Pre-post real-time validation (5 checks) | Intercept | Yes (in front of CBS) | **Demo-only surface** — endpoints + UI screen, NOT wired into CBS write path |

Pre-post is the only feature that touches the CBS write path — that's why banks can veto it, and that's why it stays a demo surface, not a wired intercept.

## Stack — LOCKED

| Layer | Choice | Notes |
|---|---|---|
| Backend | FastAPI (Python 3.12) | |
| Database | PostgreSQL 16 | Audit ledger + Excess Ledger both append-only; hash chain; never weaken |
| Matching | rapidfuzz + rule-based flags | Deterministic. No ML ranking anywhere |
| Anomaly | scikit-learn Isolation Forest | **Display-only signal.** Cannot override or re-rank rule flags |
| AI explanation | Groq API (Llama 3.3 70B) | Explains engine output post-hoc, in Urdu. NEVER decides, ranks, filters, or scores |
| Frontend | React 18 + Vite + TanStack Query | No Next.js, no SSR |
| Infra | Docker Compose | Postgres + backend + frontend. **No Qdrant** |

**Cut from v2** (were present in v1 — remove from code, do not restore):

- Rahbar / Saathi RAG (Qdrant). Do not restore `backend/app/rahbar.py`, `backend/tests/test_rahbar.py`, `qdrant-client` in `requirements.txt`, or the `qdrant` service in `docker-compose.yml`.

Do not add new dependencies, services, or frameworks without explicit approval in chat.

## Architecture — LOCKED

Primary flow: `Teller Input → [Pre-post checks (demo)] → Matching Engine → Flag Engine → Groq (Urdu explanation) → Dashboard → PostgreSQL audit ledger`

Sidecar artifacts (parallel to CBS, not in its write path): Digital Excess Ledger, cheque capture — separately hashed and signed.

Hard constraints:

1. **Deterministic engine.** Culprit detection = pattern match on variance signatures: digit transposition, duplicate posting, missed reversal, denomination-specific shortfall, cash-in/out miskey, wrong adjacent account. Output: ranked top 3–5 suspects. Every ranking reproducible and rule-explainable. No learned ranking anywhere in this path.
2. **Groq explains, never decides.** Groq receives the engine's already-ranked picks and produces Urdu explanations. If a change routes any decision, score, ranking, or filtering through Groq → stop and flag.
3. **One denomination count at EOD.** The only teller input for EOD. Per-transaction denomination entry is a forbidden anti-pattern — do not build forms, endpoints, or schema for it.
4. **Opening float declaration required.** Teller declares denomination breakdown at day-start (bulk cash is issued by OM without denomination — this is where the audit trail actually starts).
5. **Ingestion = CSV export from CBS (PIBAS format).** Do not build against any PIBAS API or direct DB connection — that surface does not exist for us.
6. **Pre-post is demo-only.** Endpoints exist for the 5 checks, UI screen shows them firing on typed input. But: **no CBS write-path interception in the actual production flow.** Marketing surface, not production surface.
7. **On-prem posture.** No cloud services beyond the Groq API call. No customer data in external logs.
8. **Append-only ledgers.** Audit ledger AND Excess Ledger. Never add UPDATE/DELETE paths. Dual sign-off = two INSERT rows referencing the same entry, not an UPDATE.

## Schema v2 — four new tables

Additive to v1 schema. Do not modify existing tables destructively.

| Table | Purpose |
|---|---|
| `opening_float_declaration` | Teller declares denomination breakdown at day-start. teller_id, branch_code, business_date, denominations (JSONB), total_amount, signed_by, signed_at. UNIQUE per (branch, teller, day). |
| `excess_ledger` | Flagship. Append-only event table. Rows share `case_ref` (UUID) and are sequenced by `event_seq`. `event_type` in {opened, countersigned, closed}. Global hash chain (prev_hash / entry_hash). Trigger blocks UPDATE/DELETE. |
| `cheque_transactions` | MICR string, account_number, amount, denomination_out (JSONB), captured_at. Plain INSERT — not chained. |
| `validation_log` | Pre-post demo log. teller_id, check_name (enum of the 5 checks), input_hash (SHA-256), passed, failed_reason, checked_at. |

## Build sequence & gates

Order: baseline cleanup → schema v2 → ground_truth v2 → Excess Ledger backend → cheque + pre-post backend → Groq + PDF → frontend v2 → integration.

Gates — do not start a later phase until the earlier gate passes:

- **v2 frontend work is blocked** until Excess Ledger backend is green (Phase 11).
- **EOD frontend work** stays blocked until the matching engine hits ≥90% single-error / ≥70% two-error against `ground_truth.py` (v1 gate carries forward).
- `ground_truth_v2.py` must cover the 5 pre-post checks + Excess Ledger open/countersign/close + cheque MICR-mismatch scenarios before feature phases advance.
- Docker Compose must run clean with no Qdrant references before Phase 14 frontend integration begins.

## Phase workflow

- Before starting a phase, create `/phases/phase_<n>.md` with: Phase Goal, Project Structure, Steps, Commands, What to Expect (so it can be diffed against reality). Minimal text.
- After the phase is complete, update the same `/phases/phase_<n>.md` with what actually happened.
- **v2 phases start at `phase_9.md`.** `phase_1.md` through `phase_8.md` are v1 delivery log — do not edit.
- v2 roadmap index lives at `/phases/v2_plan.md`.

## Progress (as of Jul 12 2026)

| Phase | Scope | Status |
|---|---|---|
| 9 | v2 baseline cleanup (Rahbar / Qdrant cut, README v2) | **Done** — `phases/phase_9.md` |
| 10 | Schema v2 (4 new tables) + `ground_truth_v2.py` (20 scenarios) | **Done** — `phases/phase_10.md` |
| 11 | Digital Excess Ledger backend (flagship) — 5 endpoints, hash chain, dual sign-off | **Done** — `phases/phase_11.md` |
| 12 | Cheque capture + pre-post demo endpoints — 7 endpoints total | **Done** — `phases/phase_12.md` |
| 13 | Groq Urdu extensions (Excess Ledger + cheque variance) + Excess Ledger Daily Register PDF | **Done** — `phases/phase_13.md` |
| 14 | Frontend v2 (4 screens) | **Done** — `phases/phase_14.md`. Built by Claude on explicit user instruction, ahead of the original "Wahaj owns" handoff — see that file's ownership note. No browser-automation tool was available to visually verify the UI; contracts were smoke-tested live against the backend instead. |
| 15 | Integration + demo dry run | **Done** — `phases/phase_15.md`. Clean-state bring-up + full demo sequence run twice via the API (no browser tool available for a human-timed rehearsal — flagged as a founder follow-up). |

**Verified before advancing** (user's local Postgres): all tests through the completed phase must pass under `docker compose exec backend pytest -q`. Do not start a later phase without that gate. Full suite as of Phase 15: **78 passed**, confirmed on a from-scratch `docker compose down -v && up --build`.

**Public API so far** (v2 additions under `/api/v1`):

- `POST /excess-ledger/open`, `POST /excess-ledger/{case_ref}/countersign`, `POST /excess-ledger/{case_ref}/close`, `GET /excess-ledger?from_date=&to_date=&branch=`, `GET /excess-ledger/verify-chain`, `POST /excess-ledger/{case_ref}/explain`, `GET /excess-ledger/report.pdf?from_date=&to_date=&branch=`
- `POST /cheque`, `GET /cheque?from_date=&to_date=&branch=`, `POST /cheque/explain`
- `POST /prepost/denom-sum`, `/cnic-name-match`, `/duplicate-check`, `/large-amount-confirm`, `/sanity`

**Outstanding founder follow-ups (not code — see `phases/phase_15.md` for detail):**

- Manual browser pass of all 4 screens (devtools open, check console/RTL Urdu rendering) — no browser-automation tool exists in this environment.
- One timed human dress rehearsal of the pitch demo, under 5 minutes.
- Anti-delusion guardrail carries forward unchanged: still n=1 teller interviews (Khursheed) as of this update; Session 6 (Jul 13) is the window CLAUDE.md flags as closing.

## Testing

- `data/ground_truth.py` is the engine oracle (variance signatures). Do not mix v2 scenarios into it.
- `data/ground_truth_v2.py` is the v2 scenario oracle (Excess Ledger transitions, cheque MICR/denom, 5 pre-post checks). 20 scenarios. Every new v2 feature test must pull from here — do not hand-write scenario data in tests.
- pytest for backend. Every variance-signature rule, every Excess Ledger state transition, every cheque validation, and every pre-post check gets at least one oracle-backed test.
- Tests run inside the compose container (`docker compose exec backend pytest -q`) against the live dev Postgres. Fixtures truncate the v2 tables + `audit_ledger` per test (`TRUNCATE ... RESTART IDENTITY CASCADE` bypasses row triggers by design).
- Never "fix" a failing test by loosening the oracle — flag the mismatch instead.

## Frontend / brand

Palette: ink `#1A1A18`, mocha `#8B7355`, cream `#FAF8F3`. Cream backgrounds, ink text, mocha accents.

Fonts: Cambria for headings, Calibri for body — with web-safe fallbacks: `Cambria, Georgia, serif` / `Calibri, 'Segoe UI', system-ui, sans-serif`.

Language: English UI chrome; Groq explanations render in Urdu inside RTL-safe containers.

**v2 dashboard screens (four; nothing else):**

1. **Excess Ledger** — open entry, countersign, close, daily register view. Flagship.
2. **EOD Recon Report** — worklist, ranked suspects, signed PDF download.
3. **Cheque Capture** — MICR + amount + denomination-out breakdown.
4. **Pre-post Demo** — 5 checks firing live on typed input. Demo/marketing surface.

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

## Anti-delusion guardrails

1. **n=1 is not evidence.** Every feature must survive 2+ teller conversations before it's called validated. As of Jul 11: still n=1 (Khursheed only). Session 6 = Jul 13 — the window closes.
2. **New feature ideas must pass three tests:** (a) 72hr demo-able, (b) strengthens novelty, (c) infra we control. Two nos → roadmap slide.
3. **Winning the hackathon ≠ shipping to a bank.** Don't pitch category-leader ambitions with hackathon-team evidence.
4. **Overlay, not replacement.** If a design starts asking CBS to change, it's the wrong design.
