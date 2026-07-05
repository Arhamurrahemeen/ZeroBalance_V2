# Phase 6 — Saathi (Qdrant RAG, Urdu Q&A)

## Goal
Static-corpus RAG: synthetic SBP-style circulars + branch SOP snippets in Qdrant, retrieval + Groq-generated Urdu answers. Demo scope only: 10 pre-tested Urdu queries. No corpus-management UI, no live upload.

## Dependency note
qdrant-client[fastembed] extra enabled (local ONNX multilingual embedder, paraphrase-multilingual-MiniLM-L12-v2, 384-dim) — Groq has no embeddings API and RAG needs an embedder. Official extra of the approved qdrant-client; model baked into the Docker image (on-prem, downloaded once at build). Flagged in chat.

## Project structure
```
/backend/app
  saathi.py             # corpus load, ensure_indexed (idempotent), retrieve, ask (Groq)
  saathi_corpus.json    # 16 synthetic Urdu snippets (clearly marked مصنوعی ڈیمو)
  api.py                # + POST /saathi/ask, GET /saathi/queries
/backend/tests
  test_saathi.py        # retrieval top-3 accuracy on the 10 queries; offline ask (fake Groq)
/docs
  saathi_queries.md     # the 10 pre-tested queries + expected snippet
```

## Steps
1. Corpus: 16 Urdu snippets (EOD balancing, denomination count, variance thresholds, shortage policy, duplicate/reversal/miskey/wrong-account SOPs, counterfeit, teller limit, vault dual custody, CCTV, retention, ageing, complaints, audit ledger). All synthetic, marked as demo.
2. saathi.py: lazy singleton embedder; ensure_indexed recreates collection iff point count differs; retrieve top-3; ask = retrieval + Groq (answer only from context, simple Urdu, cite source, say "don't know" if absent).
3. Routes: POST /api/v1/saathi/ask {question} → {answer_ur, sources}; GET /api/v1/saathi/queries → the 10 demo queries (for UI dropdown). Nothing else.
4. Dockerfile bakes the embedding model; requirements.txt gains the [fastembed] extra; image rebuild.
5. Tests: each of the 10 queries must retrieve its expected snippet in top-3 (real Qdrant + embedder, offline); ask flow with fake Groq; live smoke once.

## Commands
```
docker compose up -d --build backend      # rebuild with fastembed + baked model
docker compose exec backend pytest -q
# live: POST /api/v1/saathi/ask {"question": "دن کے اختتام پر کیش کیسے ملایا جائے؟"}
```

## What to expect
- Rebuild downloads the embedding model once (~120MB layer).
- pytest: 25 prior + saathi tests green; 10/10 queries hit expected snippet in top-3.
- Live ask returns a grounded Urdu answer citing a corpus source.

## Achieved
- app/saathi_corpus.json: 16 synthetic Urdu snippets, every source marked مصنوعی ڈیمو (test-enforced).
- app/saathi.py: lazy multilingual embedder (fastembed extra, model baked in image), corpus-sha fingerprint in payloads so content edits trigger reindex, retrieve top-3, ask() grounded Groq answers (Urdu, cite ماخذ, refuse outside context).
- Routes: POST /saathi/ask (503 no key, 502 upstream), GET /saathi/queries (the 10 demo queries). No corpus management anywhere.
- Query curation loop (in-scope for "pre-tested"): 2 queries initially missed top-3 due to vocabulary gaps (ڈبل پوسٹنگ vs دو بار پوسٹ) → enriched those snippets → 10/10 retrieval.
- 37 tests green (12 new: 10 retrieval + corpus-static + grounded-ask), ruff clean.
- Live smoke: threshold query → correct grounded Urdu answer citing the variance-reporting circular.

Next: Phase 7 — React dashboard (worklist, ageing, recon report views).
