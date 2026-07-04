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
cp .env.example .env        # then fill GEMINI_API_KEY
docker compose up -d --build
curl http://localhost:8000/api/v1/health
```

## Achieved
_(updated on completion)_
