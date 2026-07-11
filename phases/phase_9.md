# Phase 9 — v2 Baseline Cleanup

## Goal

Fork the v1 codebase into v2 by removing Rahbar / Qdrant surface (RAG cut) and updating baseline files. Isolation Forest stays as display-only signal — no code change needed if v1 already respects that constraint. This is a subtractive phase — nothing new gets added.

## Project structure touched

```
backend/
  app/
    rahbar.py                DELETE
    main.py                  EDIT — drop rahbar imports + route registration
    api.py                   EDIT — drop /rahbar routes if defined here
    schemas.py               EDIT — drop rahbar request/response models
    service.py               EDIT — drop rahbar service methods if any
    config.py                EDIT — drop QDRANT_URL if referenced
  tests/
    test_rahbar.py           DELETE
  requirements.txt           EDIT — drop qdrant-client
docker-compose.yml           EDIT — remove qdrant service + volume + QDRANT_URL env
README.md                    EDIT — v2 stub, cut Rahbar paragraph + Qdrant mention
```

## Steps

1. `grep -r -l -E "rahbar|qdrant|QDRANT" backend/ docker-compose.yml README.md` to surface every reference.
2. Delete `backend/app/rahbar.py` and `backend/tests/test_rahbar.py`.
3. Strip rahbar imports / route registration / schema classes from any file the grep surfaced.
4. Drop `qdrant-client` line from `backend/requirements.txt`.
5. Edit `docker-compose.yml` — remove `qdrant` service block, remove `qdrant_data` volume, remove `QDRANT_URL` env under backend, remove `qdrant` from backend `depends_on`.
6. Rewrite `README.md` — remove Rahbar paragraph, remove Qdrant from flow diagram references, mark it v2 in progress.
7. Run gates.

## Commands to run

```bash
# From D:\ZeroBalance_v2

# Surface
grep -rn -E "rahbar|Rahbar|qdrant|Qdrant|QDRANT" backend/ docker-compose.yml README.md requirements.txt 2>/dev/null

# Post-edit verification
grep -rn -E "rahbar|Rahbar|qdrant|Qdrant|QDRANT" backend/ docker-compose.yml README.md 2>/dev/null
docker compose config >/dev/null && echo "compose OK"
cd backend && pytest -q
```

## What to expect

- Pre-edit grep: hits in `rahbar.py`, `test_rahbar.py`, `main.py`, possibly `api.py` / `schemas.py` / `config.py`, `docker-compose.yml`, `README.md`, `requirements.txt`.
- Post-edit grep: **zero hits** (all cleared).
- `docker compose config`: exits 0 with "compose OK".
- `pytest -q`: green. Expected count = v1 count minus `test_rahbar.py` cases.

## Rollback

Phase is subtractive. Rollback = `git checkout -- .` on the v2 repo. v1 folder is not touched at any point.

## Anti-scope-creep checkpoint at close

1. Did we build anything not on the LOCKED four-feature list? Should be **no** — this phase only removes.
2. Did any decision route through Groq that should be deterministic? **N/A** — nothing added.
3. Did any UPDATE/DELETE sneak into ledger paths? **N/A** — no schema change in this phase.
4. Did we build anything OM / BOM / Regional / half-yearly-specific? **N/A** — no build.

## Actual outcome

**Status: complete.**

### Files deleted

- `backend/app/rahbar.py`
- `backend/app/rahbar_corpus.json`
- `backend/tests/test_rahbar.py`
- `docs/rahbar_queries.md`
- `backend/.pytest_cache/` (stale rahbar node ids)

### Files edited

| File | Change |
|---|---|
| `backend/app/api.py` | Dropped `from .rahbar import ...`; removed `RahbarAskRequest` class + `POST /rahbar/ask` + `GET /rahbar/queries` routes (25 lines). `Literal` import kept — still used by `explain_session`. |
| `backend/app/config.py` | Removed `qdrant_url` setting. |
| `backend/Dockerfile` | Removed the fastembed model-bake `RUN` step. |
| `backend/requirements.txt` | Removed `qdrant-client[fastembed]==1.14.2`. |
| `docker-compose.yml` | Removed `qdrant` service, `qdrant_data` volume, `QDRANT_URL` env under backend, `qdrant` from backend `depends_on`. |
| `README.md` | Full v2 rewrite: value prop, 4-feature table, overlay-posture callout, version history. Retains one historical mention of "Rahbar/Qdrant RAG cut" — intentional (documents what was removed). |

### Gate results

| Gate | Result |
|---|---|
| `grep -rn "rahbar\|qdrant\|QDRANT" backend/ docker-compose.yml` | CLEAN (0 hits) |
| Python `ast.parse` on all `backend/app/*.py` | 9/9 OK |
| YAML parse `docker-compose.yml` | services=`[db, backend, frontend]`, volumes=`[pgdata]`, backend env=`[DATABASE_URL]` only, backend depends_on=`[db]` |
| `qdrant` in `backend/requirements.txt` | absent |
| `test_rahbar.py` in test dir | gone; remaining: conftest, test_api, test_engine, test_explain, test_report |

### Deferred to user's local machine

- `docker compose config` — no docker in sandbox. User should run it once from `D:\ZeroBalance_v2` before Phase 14.
- `pytest -q` full run — needs live Postgres. Same window.

### Notes / gotchas

- The Cowork Linux mount reports trailing null-byte padding on files written from the host after Edit/Write. Verified via `Read` tool + Python decoding that the actual Windows-side content is clean. Runtime on the user's Windows host is unaffected. If the user inspects raw bytes via WSL or similar, they will see this padding — safe to ignore.
- No changes to schema.sql, engine code, matching logic, or Groq/explain layer. All still gated by v1 tests.
- Isolation Forest untouched — stays as display-only per CLAUDE.md v2 rule.

### Anti-scope-creep checkpoint

1. Built anything not on the LOCKED four-feature list? **No** — pure subtractive.
2. Any decision routed through Groq that should be deterministic? **No** — no logic added.
3. Any UPDATE/DELETE sneak into ledger paths? **No** — schema untouched.
4. Built anything OM / BOM / Regional / half-yearly-specific? **No.**

### Ready for Phase 10

Schema v2 + ground_truth v2 extension.
