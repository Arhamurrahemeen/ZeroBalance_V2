# Phase 1 — Foundation

## Goal
Repo scaffold, backend dependencies (requirements.txt), Postgres schema (schema.sql, append-only audit ledger), Docker Compose (postgres + qdrant + backend stub). Gate for Phase 2 (synthetic data + oracle).

## Project structure
```
/backend
  Dockerfile
  requirements.txt
  pyproject.toml          # ruff config
  app/
    __init__.py
    main.py               # FastAPI app + /api/v1/health
  schema.sql              # mounted into Postgres initdb
/frontend                 # placeholder (UI blocked until engine gate)
/data                     # placeholder (Phase 2)
/docs                     # placeholder
docker-compose.yml
.env.example
.gitignore
```

## Steps
1. Create folder layout + .gitignore + .env.example
2. requirements.txt (locked stack only)
3. schema.sql — sessions, transactions, denomination_counts (one count per session), suspects, audit_ledger (UPDATE/DELETE blocked by trigger), recon_reports
4. Minimal FastAPI app with health route (Pydantic response model)
5. docker-compose.yml — db, qdrant, backend
6. Validate compose config

## Commands
```
cp .env.example .env        # then fill GROQ_API_KEY
docker compose up -d --build
curl http://localhost:8000/api/v1/health
```

## What to expect
- `docker compose up -d --build` → 3 containers running: db (healthy), qdrant, backend.
- `curl http://localhost:8000/api/v1/health` → `{"status":"ok","service":"zerobalance-backend"}`.
- `psql \dt` → 6 tables: eod_sessions, transactions, denomination_counts, suspects, audit_ledger, recon_reports.
- `UPDATE`/`DELETE` on audit_ledger → rejected with `audit_ledger is append-only`.

## Achieved
- Repo scaffolded: /backend (app/, Dockerfile, requirements.txt, pyproject.toml, schema.sql), /frontend, /data, /docs placeholders, docker-compose.yml, .env/.env.example, .gitignore.
- Stack swap: Gemini → Groq (free tier) for the explanation layer, per explicit chat approval. Updated CLAUDE.md LOCKED table + constraints, requirements.txt (`groq` replaces `google-genai`), .env/.env.example, schema.sql comments.
- schema.sql applied via Postgres initdb: eod_sessions, transactions, denomination_counts (one row per denomination per session, no per-txn FK — enforces the single-count rule), suspects, audit_ledger, recon_reports.
- audit_ledger append-only trigger verified live: UPDATE raises `audit_ledger is append-only`; batched INSERT+UPDATE rolled back atomically, ledger stays empty.
- docker compose up: db (healthy), qdrant, backend all running. `GET /api/v1/health` → `{"status":"ok","service":"zerobalance-backend"}`.
- Fixed a real Groq key that had been placed in .env.example (tracked file, not gitignored) — replaced with placeholder before it could leak via commit.

Gate passed: Phase 2 (synthetic generator + ground_truth.py) unblocked.
