---
project: ZeroBalance
type: team
updated: 2026-07-07
---

# Team & Roles

Team lead / sole technical builder: Arham (also CEO of OmniteX — kept separate, ZeroBalance pitched as standalone team product, not OmniteX-branded). Event context: [[Hackathon Logistics]].

## Status: rebuilding the roster
Previous team members removed. Solo for now — all deliverables below owned by Arham until new members are added and roles get re-split.

## Roles
| Person | Role | Owns |
|---|---|---|
| Arham (me) | Lead / CTO (solo, full stack) | Matching engine core + Postgres schema + Gemini explanation layer + overall architecture + Saathi RAG + FastAPI layer + ingestion (CSV parser, denomination model) + fraud layer (Isolation Forest) + `ground_truth.py` (test oracle) + React dashboard (exception worklist, ageing view, recon report) + UI/UX + Urdu polish + Streamlit demo prototype |

Full technical scope for each layer above: [[Technical Architecture]].

## Critical seam
`ground_truth.py` (test oracle) must connect to the [[Technical Architecture#Build sequence|matching engine]] before any UI work starts — currently a sequencing dependency on Arham alone.

## Next step
When new members join: re-split the table above by domain (backend/AI, data/ML, frontend, etc.), re-derive ownership of the critical seam, and re-check the DUET eligibility/roster rules in [[Hackathon Logistics]].

## Related
- [[Technical Architecture]] — critical seam and build sequence
- [[Hackathon Logistics]] — team eligibility and event context
- [[Domain Consultant]] — non-team domain expert feeding product decisions
