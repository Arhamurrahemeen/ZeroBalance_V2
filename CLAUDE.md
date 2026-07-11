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

- Rahbar / Saathi RAG (Qdrant). Delete `backend/app/rahbar.py`, `backend/tests/test_rahbar.py`, `qdrant-client` from `requirements.txt`, `qdrant` service from `docker-compose.yml`.

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
| `opening_float_declaration` | Teller declares denomination breakdown at day-start. teller_id, 