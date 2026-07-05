# Phase 7 — React Dashboard

## Goal
React 18 + Vite + TanStack Query dashboard (no Next.js/SSR). Views (LOCKED): exception worklist, ageing view, EOD Recon Report. Plus: ingest modal (CSV + the single EOD denomination count) and Saathi as a side drawer (demo surface for the 10 pre-tested queries — not a 4th dashboard view). Brand: ink/mocha/cream, Cambria/Calibri, English chrome, RTL Urdu containers.

## Project structure
```
/frontend
  package.json  vite.config.js  index.html
  src/
    main.jsx  App.jsx  api.js  index.css
    components/
      Worklist.jsx  SessionDetail.jsx  Ageing.jsx  Report.jsx
      IngestModal.jsx  Saathi.jsx
docker-compose.yml   # + frontend service (node:20-alpine dev server)
```

## Steps
1. Backend nicety: SessionDetail gains denomination_count (report view needs it).
2. Hand-written Vite scaffold (no npx): react 18, @tanstack/react-query v5 — no other UI deps.
3. Worklist: sessions table (flagged first), row → detail panel: ranked suspects with evidence, anomaly bar (display-only), Urdu explanation (RTL) via explain button, resolve with note.
4. Ageing: unresolved sessions bucketed 0–1d / 1–3d / 3d+.
5. Report: per-session EOD Recon Report (cash summary, denomination table, suspects + Urdu, ledger head hash + verify badge), print-friendly.
6. Ingest modal: CSV picker + opening float + denomination grid (one count; live total), meta-JSON paste helper for demo speed.
7. Saathi drawer: dropdown of the 10 queries only, RTL answer + sources.
8. Compose: frontend service (node:20-alpine, npm install + vite dev, anonymous node_modules volume).

## Commands
```
docker compose up -d frontend
# http://localhost:5173  (backend at :8000 already up)
```

## What to expect
- Vite serves at 5173; worklist lists ingested sessions; ingesting data/sample CSV + its meta JSON creates a flagged session with suspects.
- Explain button fills Urdu text (RTL); resolve moves session out of worklist; ageing buckets update; report renders with ledger hash.

## Achieved
- Backend: SessionDetail now includes denomination_count (report view); 37 tests still green.
- Frontend (hand-written scaffold, deps: react 18.3 + @tanstack/react-query 5 only):
  - Worklist: flagged-first table, row → detail panel (ranked suspects, evidence grid, anomaly bar labelled "secondary/display only", Urdu explanation RTL block, Explain + Resolve actions).
  - Ageing: 0–1d / 1–3d / 3+d (escalate) buckets over unresolved sessions.
  - Report: per-session printable EOD Recon Report — cash position, denomination table, engine findings with Urdu, ledger verify badge + head hash, print CSS.
  - IngestModal: CSV + opening float + one denomination count grid (live total) + meta-JSON paste shortcut.
  - Saathi drawer: dropdown restricted to the 10 pre-tested queries, RTL answer + source chips (side drawer, not a 4th dashboard view).
  - Brand: ink/mocha/cream, Cambria headings / Calibri body, .urdu RTL-safe containers.
- Compose: frontend service (node:20-alpine, anonymous node_modules volume), Vite on :5173.
- Verified: all 9 modules transform (Vite 200s), production build clean (85 modules), 6 demo sessions seeded via API (one per signature). Visual pass pending in user's browser: http://localhost:5173.

Next: Phase 8 — Recon Report PDF.
