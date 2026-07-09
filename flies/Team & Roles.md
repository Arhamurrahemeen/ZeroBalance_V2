---
project: ZeroBalance
type: team
updated: 2026-07-07
status: reference
tags:
  - project/zerobalance
  - type/team
  - status/reference
---
	
# Team & Roles

Team lead / sole technical builder: Arham (also CEO of OmniteX — kept separate, ZeroBalance pitched as standalone team product, not OmniteX-branded). Event context: [[Hackathon Logistics]].

## Status: roster locked (Jul 7)
Three members: Arham, Wahaj, Miswan. Role split locked below.

## Roster background
| Person | Background |
|---|---|
| Wahaj | Final-year; MERN stack (React, Tailwind, Node/Express), Spring Boot, JWT auth, deployed full-stack projects. FYP: AR/VR applications. No prior FastAPI. |
| Miswan | 2nd-year BS AI (DUET); ~3 months into Data Science — Python, sklearn basics, SQL basics. Currently learning DL. No FastAPI, vector DBs, or production ML. |

## Roles (locked)
| Area | Owner | Support |
|---|---|---|
| Matching engine core + `ground_truth.py` (test oracle) | Arham | — (too demo-critical to delegate) |
| Postgres schema + audit ledger | Arham | — |
| Backend (FastAPI) | Arham (owns) | Wahaj (thin CRUD routes — learns FastAPI on the shallow end) |
| Frontend (React dashboard: exception worklist, ageing view, recon report) | Wahaj (owns) | Arham (UI/UX direction, Urdu polish) |
| Anomaly layer (Isolation Forest) | Miswan | Arham (review) |
| Synthetic data generator + CSV ingestion (PIBAS parser, denomination model) | Miswan | Arham (spec) |
| Saathi RAG (Qdrant) | Arham (owns) | Miswan (chunking, eval, corpus grunt work — learns by doing) |
| LLM explanation layer (Groq / Llama 3.3) | Arham | — |
| Infra (Docker Compose) | Arham | — |
| Pitch / storytelling | Arham | — |

**Design principle behind the split:** Miswan's failure mode costs a nice-to-have, never the core. Wahaj deploys his strongest verified skill (React) with zero ramp-up.

Full technical scope for each layer: [[Technical Architecture]].

## Critical seam
`ground_truth.py` (test oracle) must connect to the [[Technical Architecture#Build sequence|matching engine]] before Wahaj's UI work goes beyond static scaffolding — both sides Arham-owned, so the seam is self-contained.

## Next step
Map the three of us onto Sarfaraz's 4-role framework (Builder / Validator / Storyteller / Integrator) — see open action item in [[Bootcamp_notes]]. Storyteller = Arham (decided); rest TBD.

## Related
- [[Technical Architecture]] — critical seam and build sequence
- [[Hackathon Logistics]] — team eligibility and event context
- [[Domain Consultant]] — non-team domain expert feeding product decisions
