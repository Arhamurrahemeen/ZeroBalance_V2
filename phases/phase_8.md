# Phase 8 — EOD Recon Report PDF

## Goal
Server-generated PDF of the EOD Recon Report, carrying the audit-ledger head hash (LOCKED constraint: recon reports carry a ledger hash). recon_reports row + REPORT_GENERATED ledger entry per generation.

## Dependency note
weasyprint==62.3 (approved in chat): HTML→PDF with native RTL/bidi for the Urdu explanations. Alternative reportlab would need 3 packages (+arabic-reshaper +python-bidi) and manual RTL shaping. System deps baked in image: libpango + fonts-noto-core (Noto Naskh Arabic for Urdu) — on-prem, no runtime downloads.

## Project structure
```
/backend/app
  report.py     # HTML template (escaped) + WeasyPrint render + ledger bookkeeping
  api.py        # + GET /sessions/{id}/report.pdf (binary route — Response, not a Pydantic model)
/backend/tests
  test_report.py
/frontend/src/components/Report.jsx   # + Download PDF button
Dockerfile      # + apt pango/noto layer
```

## Steps
1. report.py: render_html(detail, ledger_head, generated_at) — same sections as the web report (cash position, denomination count, engine findings + Urdu RTL, hash footer), brand palette, html-escaped values.
2. generate_report_pdf: capture ledger head → render → insert recon_reports(session_id, ledger_hash=head) → append REPORT_GENERATED ledger entry → commit. Regeneration allowed; every generation is ledgered.
3. GET /api/v1/sessions/{id}/report.pdf → application/pdf inline.
4. Frontend: Download PDF button beside Print.
5. Tests: %PDF magic, content-type, recon_reports row stores the pre-generation head, ledger gains entry and chain stays valid.

## Commands
```
docker compose up -d --build backend
docker compose exec backend pytest -q
# browser: Report tab -> Download PDF
```

## What to expect
- Rebuild adds pango + Noto fonts layer.
- pytest green (37 prior + report tests).
- PDF opens with correct Urdu (RTL, shaped) and ledger hash footer; hash equals /ledger/verify head at generation time.

## Achieved
- app/report.py: HTML template (escaped, brand palette, RTL .urdu blocks) + WeasyPrint render; generate_report_pdf captures ledger head → recon_reports row → REPORT_GENERATED ledger entry → commit.
- GET /api/v1/sessions/{id}/report.pdf (binary route, inline content-disposition). Frontend Report view gained Download PDF button (build verified).
- Version pin: pydyf==0.10.0 (weasyprint 62.x breaks against pydyf 0.11 transform API — hit live, fixed, baked into image).
- Dockerfile: libpango + fonts-noto-core layer (on-prem, no runtime downloads).
- 40 tests green (3 new: pdf magic/content-type/size + pre-generation head stored + regeneration ledgered with distinct heads + 404), ruff clean.
- Live e2e: 6 demo sessions seeded → Urdu explanation → 30.7KB PDF; embedded fonts include Noto-Naskh-Arabic (proves Urdu shaped+rendered); ledger chain valid at 7 entries.

Build sequence COMPLETE: all 8 phases done (engine gate 100%/92.5%, 40 tests, full stack in compose).
