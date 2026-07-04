# Phase 4 — FastAPI Routes + Persistence

## Goal
REST API under /api/v1: CSV ingest (PIBAS upload + one EOD denomination count) → engine → Postgres persistence → hash-chained audit ledger. Pydantic response models on every route. Groq explanations deferred to Phase 5 (explanation_ur stays null).

## Project structure
```
/backend/app
  main.py          # app factory, CORS (Vite dev origin), mounts router
  config.py        # pydantic-settings (DATABASE_URL, GROQ_API_KEY, QDRANT_URL)
  db.py            # engine/session, ledger append + hash chain + verify
  db_models.py     # SQLAlchemy 2.0 mapped classes (schema.sql owns DDL — no create_all)
  schemas.py       # API response/request models
  service.py       # PIBAS CSV parser + recon orchestration
  api.py           # routes
/backend/tests
  test_api.py      # end-to-end: oracle case → upload → suspects match truth
```

## Steps
1. Routes: POST /sessions (multipart CSV + meta JSON) 201 → SessionDetail with ranked suspects; GET /sessions[?status] worklist (age_days for ageing view); GET /sessions/{id}; POST /sessions/{id}/resolve; GET /ledger/verify; GET /health.
2. Ledger: entry_hash = sha256(prev_hash | actor | action | canonical payload); ingest + resolve each append; verify walks the chain.
3. Engine tweak: variance == 0 → singles only (wrong_adjacent_account), no canceling-pair noise, no fallback → clean sessions close with zero suspects.
4. Status: variance≠0 or suspects → flagged, else closed; resolve → resolved (409 if already resolved/closed); duplicate (branch,teller,date) ingest → 409.
5. Anomaly scores attached to stored suspects (display only).
6. Tests: real Postgres from compose; tables truncated per test (dev DB, synthetic data only).

## Commands
```
docker compose exec backend pytest -q     # engine + API tests (wipes dev DB tables)
curl http://localhost:8000/api/v1/health
# demo ingest: use data/sample CSV + its _meta.json denomination_count
```

## What to expect
- pytest: all engine tests still green + API tests (ingest e2e, 409 duplicate, worklist/detail, resolve flow, ledger verify, balanced-session close, ledger UPDATE rejected).
- POST /sessions on an oracle case returns its exact variance and the truth culprit in suspects.
- GET /ledger/verify → {"ok": true, ...} with chain intact.

## Achieved
- app/: config.py (pydantic-settings), db_models.py (SQLAlchemy 2.0, schema.sql owns DDL), db.py (ledger append/verify, sha256 chain over prev|actor|action|canonical-payload), service.py (PIBAS parser with strict validation + recon orchestration), schemas.py, api.py, main.py (CORS for Vite).
- Routes: POST /sessions (201, multipart CSV+meta) · GET /sessions[?status] (worklist with age_days) · GET /sessions/{id} · POST /sessions/{id}/resolve · GET /ledger/verify · GET /health. Pydantic response models on all.
- Engine tweak: variance==0 → zero-delta singles only (wrong_adjacent_account), no canceling-pair noise/fallback → clean sessions close with 0 suspects. Engine gate re-verified (still 100%/92.5%).
- Ledger actions: SESSION_INGESTED (incl. csv_sha256 + suspect summary), SESSION_RESOLVED (note). UPDATE rejected by trigger (tested).
- 19 tests green (12 engine + 7 API e2e incl. 409 duplicate, 404, balanced-close, resolve conflict, bad-CSV 400, ledger immutability), ruff clean.
- Live smoke test over HTTP: demo duplicate case → 201, variance +66,400, true pair TXN0033/TXN0039 rank 1 (anomaly 0.28 display-only), ledger verify ok.

Next: Phase 5 — Groq explanation layer (fills suspects.explanation_ur post-hoc, Urdu).
