# Phase 5 — Groq Explanation Layer

## Goal
Post-hoc Urdu explanations for already-ranked suspects via Groq (free tier). Groq NEVER decides, ranks, filters, or scores — it only verbalizes engine evidence. Fills suspects.explanation_ur on demand.

## Project structure
```
/backend/app
  explain.py       # prompt builder (masked accounts) + Groq calls, injectable client
  api.py           # + POST /sessions/{id}/explain
  config.py        # + groq_model setting
/backend/tests
  test_explain.py  # fake-client tests: fills text, idempotent, never reorders; masking
```

## Steps
1. explain.py: per-suspect prompt from engine facts only (signature, refs, cash delta, evidence, session variance); account numbers masked to ****last4 before leaving the box; temperature low; one Groq call per suspect (≤5).
2. System prompt pins the role: engine already decided; explain evidence in simple Urdu (2–3 sentences), no verdicts, no new suspects.
3. POST /api/v1/sessions/{id}/explain → generates only missing explanations, stores, returns SessionDetail. 503 if no API key, 502 on upstream failure.
4. Tests use a monkeypatched fake client (offline); assert suspect order/count/evidence unchanged by explanation pass.
5. One live smoke call through the endpoint (real key in .env).

## Commands
```
docker compose exec backend pytest -q
# live: POST http://localhost:8000/api/v1/sessions/{id}/explain
```

## What to expect
- pytest green (19 prior + explain tests), no network in tests.
- Live call returns suspects with explanation_ur filled in Urdu script; rank/evidence identical to pre-call.

## Achieved
- app/explain.py: per-suspect prompt from stored rule evidence only; SIGNATURE_UR Urdu glossary; accounts masked to ****last4 before leaving the box; injectable client (offline tests); system prompt pins post-hoc role (engine decision final, evidence only, no verdicts, Urdu script).
- POST /api/v1/sessions/{id}/explain: fills only missing explanation_ur (idempotent), 503 without key, 502 + rollback on upstream failure. Touches nothing but explanation_ur.
- config: groq_model = llama-3.3-70b-versatile.
- 25 tests green (6 new: fill+never-reorder invariant, idempotency, prompt masking, mask unit, 502 state-safety, 503), ruff clean. No network in tests (fake client).
- Live smoke: miskey demo case → Urdu explanation naming TXN0005, 6,700 cash_out, 13,400 PKR variance impact. Groq free tier + real key working.

Next: Phase 6 — Rahbar (Qdrant RAG, static corpus, 10 pre-tested Urdu queries).
