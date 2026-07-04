# CLAUDE.md — ZeroBalance

EOD cash-reconciliation co-pilot for bank tellers. Hackathon MVP (UBL National Innovation Hackathon, 72-hour final build). This file is authoritative — do not re-architect anything marked LOCKED.

## Repo layout

```
/backend      FastAPI app, matching engine, Gemini layer, Saathi RAG
/frontend     React 18 + Vite + TanStack Query dashboard
/data         Synthetic transaction generator + ground_truth.py (test oracle)
/docs         EOD Recon Report template, schema notes
docker-compose.yml   Postgres 16 + Qdrant + backend + frontend
```

## Stack — LOCKED

| Layer | Choice | Notes |
|---|---|---|
| Backend | FastAPI (Python 3.12) | |
| Database | PostgreSQL 16 | Audit ledger is append-only; never weaken ACID/trigger constraints in schema.sql |
| Matching | rapidfuzz + rule-based flags | Deterministic. Never replace with ML ranking |
| Anomaly | scikit-learn Isolation Forest | SECONDARY signal only — can never override or re-rank rule flags |
| AI explanation | Gemini API | Explains engine output post-hoc, in Urdu. NEVER decides, ranks, filters, or scores |
| RAG (Saathi) | Qdrant | Static corpus, Urdu Q&A. No corpus-management UI, no live upload |
| Frontend | React 18 + Vite + TanStack Query | No Next.js, no SSR |
| Infra | Docker Compose | All services run via compose from day one |

Do not add new dependencies, services, or frameworks without explicit approval in chat.

## Architecture — LOCKED

Flow: Teller Input → Matching Engine → Flag Engine → Gemini (explanation) → Dashboard → PostgreSQL audit ledger

Hard constraints:

1. **Deterministic engine.** Culprit detection = pattern-match on variance signatures: digit transposition, duplicate posting, missed reversal, denomination-specific shortfall, cash-in/out miskey, wrong adjacent account. Output: ranked top 3–5 suspects. Every ranking must be reproducible and explainable by rules — no learned ranking anywhere in this path.
2. **Gemini explains, never decides.** Gemini receives the engine's already-ranked picks and produces Urdu explanations. If a change routes any decision, score, ranking, or filtering through Gemini, it is wrong — stop and flag.
3. **One denomination count at EOD.** The only teller input. Per-transaction denomination entry is a forbidden anti-pattern — do not build forms, endpoints, or schema for it.
4. **Ingestion = CSV export from CBS (PIBAS format).** Do not build against any PIBAS API or direct DB connection — that surface doesn't exist for us.
5. **On-prem posture.** No cloud services beyond the Gemini API call. No customer data in logs sent anywhere external.
6. **Audit ledger is append-only.** Recon reports carry a ledger hash. Never add UPDATE/DELETE paths to ledger tables.

## Build sequence & gates

Order: requirements.txt → schema.sql → synthetic generator + ground_truth.py → matching engine → FastAPI routes → Gemini layer → Saathi → React dashboard → Recon Report PDF.

Gates — do not start a later phase until the earlier gate passes:

- **UI work is blocked** until the matching engine scores ≥90% on single-error and ≥70% on two-error cases against ground_truth.py.
- ground_truth.py must cover all 6 variance signatures before engine tuning starts.
- Saathi demo scope: static corpus (SBP circulars + SOP snippets), 10 pre-tested Urdu queries. Nothing beyond that.

## Phase workflow

- Before starting a phase, create `/phases/phase_<n>.md` with: Phase Goal, Project Structure, Steps, Commands to run the phase. Minimal text.
- After the phase is complete, update the same `/phases/phase_<n>.md` with what was actually achieved.

## Testing

- ground_truth.py in /data is the oracle. Engine correctness = measured against it, not against hand-picked examples.
- pytest for backend. Every variance-signature rule gets at least one oracle-backed test.
- Never "fix" a failing test by loosening the oracle — flag the mismatch instead.

## Frontend / brand

- Palette: ink `#1A1A18`, mocha `#8B7355`, cream `#FAF8F3`. Cream backgrounds, ink text, mocha accents.
- Fonts: Cambria for headings, Calibri for body — with web-safe fallbacks: `Cambria, Georgia, serif` / `Calibri, 'Segoe UI', system-ui, sans-serif`.
- UI language: English UI chrome; Gemini explanations and Saathi answers render in Urdu (RTL-safe containers where Urdu text appears).
- Dashboard views: exception worklist, ageing view, EOD Recon Report. Nothing else in MVP.

## Conventions

- Python: type hints everywhere, Pydantic v2 models, ruff for lint/format.
- API: REST, versioned under /api/v1. Pydantic response models on every route.
- Secrets (Gemini key, DB creds) via .env — never committed, never hardcoded.
- Commits: small, per-feature. No mass rewrites of files that already pass their gate.
- If a request conflicts with anything LOCKED in this file, stop and say so instead of complying.

## Roadmap — DO NOT BUILD

These exist as pitch slides only. Building any of them is scope creep:

- BOM branch console / manager dashboard
- Regional Ops rollup, SBP report auto-export
- Cash counter hardware integration (Glory/Kisan serial/USB)
- PIBAS direct API/DB integration
- Per-transaction denomination capture (permanently forbidden, not just deferred)
