<p align="center">
  <img src="assets/zerobalance-banner.svg" alt="ZeroBalance — EOD Cash-Reconciliation Co-pilot" width="100%"/>
</p>

# ZeroBalance — EOD Cash-Reconciliation Co-pilot

> When a teller's till doesn't balance, someone still opens the ledger by hand and starts guessing.
> I built the part that shouldn't be manual anymore.

I built this for the UBL National Innovation Hackathon. The problem: a teller's till doesn't balance at end of day, and someone has to comb through the day's transactions to figure out why. ZeroBalance does that instead — it takes the CBS transaction export (PIBAS CSV) plus the teller's single denomination count, and runs both through a **deterministic rule engine** that pinpoints the likely culprit transactions: digit transpositions, duplicate postings, missed reversals, denomination shortfalls, cash-in/out miskeys, wrong-account postings. It ranks the top 3–5 suspects with exact cash-delta evidence, not a confidence score pulled out of nowhere.

Groq explains each pick **post-hoc, in Urdu**. It never decides or ranks anything — it just narrates what the engine already found. Every action lands in an append-only, hash-chained audit ledger, so nothing gets rewritten quietly after the fact. Saathi, a Qdrant-RAG side assistant, answers SOP and circular questions in Urdu from a static demo corpus.

Flow: `Teller input → Matching engine → Flag engine → Groq (explanation) → Dashboard → Postgres audit ledger`

<p align="center">
  <img src="assets/zerobalance-flow.svg" alt="ZeroBalance pipeline diagram" width="100%"/>
</p>

## Development summary

Built in 8 gated phases (details in `/phases/phase_<n>.md`):

| Phase | Delivered |
|---|---|
| 1 | Repo scaffold, requirements, Postgres schema (append-only ledger trigger), Docker Compose |
| 2 | Synthetic PIBAS generator + `ground_truth.py` oracle — 160 labeled cases, all 6 variance signatures |
| 3 | Matching engine — **gate: 100% single-error / 92.5% two-error** (required 90/70); Isolation Forest as display-only signal |
| 4 | FastAPI routes: ingest, worklist, resolve, hash-chained ledger + verify |
| 5 | Groq explanation layer — Urdu, post-hoc only, masked account numbers |
| 6 | Saathi — Qdrant RAG, 16-snippet synthetic Urdu corpus, 10 pre-tested queries (10/10 retrieval) |
| 7 | React dashboard — worklist, ageing, recon report views + ingest modal + Saathi drawer |
| 8 | EOD Recon Report PDF (WeasyPrint) carrying the audit-ledger head hash |

40 backend tests: engine oracle, API e2e, explain invariants, Saathi retrieval, PDF/ledger bookkeeping. I didn't ship a phase without its gate passing.

## Project structure

```
backend/            FastAPI (Python 3.12)
  app/
    engine/         deterministic matching engine + anomaly (display-only)
    api.py          REST routes under /api/v1
    service.py      PIBAS CSV parsing + recon orchestration
    explain.py      Groq Urdu explanations (post-hoc)
    saathi.py       Qdrant RAG Q&A (+ saathi_corpus.json)
    report.py       Recon Report PDF
    db.py           hash-chained append-only audit ledger
  schema.sql        Postgres DDL (ledger UPDATE/DELETE blocked by trigger)
  tests/            pytest suite (oracle-backed)
frontend/           React 18 + Vite + TanStack Query dashboard
data/               synthetic generator + ground_truth.py (test oracle)
docs/               PIBAS CSV format, Saathi query list
phases/             per-phase plan + what was achieved
docker-compose.yml  Postgres 16 · Qdrant · backend · frontend
```

## Run it

Prerequisites: Docker Desktop, a free [Groq API key](https://console.groq.com).

```bash
git clone https://github.com/Arhamurrahemeen/ZeroBalance_MVP.git
cd ZeroBalance_MVP

cp .env.example .env        # then set GROQ_API_KEY
docker compose up -d --build
```

- Dashboard: http://localhost:5173
- API docs: http://localhost:8000/docs

Seed demo data (one flagged session per variance signature):

```bash
python data/generator.py --out data/sample     # writes demo CSVs + meta JSON
```

Then in the dashboard: **+ New EOD Session** → pick a `data/sample/demo_*.csv`, paste its `*_meta.json` into the meta shortcut → **Ingest & reconcile**. Click the flagged row for ranked suspects, **Explain in Urdu**, and the **EOD Recon Report** tab for the printable/PDF report.

Tests (in-container; truncates the dev DB):

```bash
docker compose exec backend pytest -q          # 40 tests
python data/ground_truth.py                    # oracle self-check (host Python ok)
```

The engine decides. Groq just explains. That split is the whole point.

— Arham
