---
project: ZeroBalance
type: technical
updated: 2026-07-07
---

# Technical Architecture

## Scope (phased)
| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Teller MVP — hackathon build | In build |
| Phase 2 | BOM branch console | Roadmap slide, not code |
| Phase 3 | Regional Ops rollup + SBP report auto-export | Roadmap slide, not code |

## Tool stack
| Layer | Choice |
|---|---|
| Backend | FastAPI |
| Database | PostgreSQL 16 (audit-trail, ACID) |
| Matching | rapidfuzz (exact + fuzzy), scikit-learn (Isolation Forest) |
| AI explanation | Gemini API |
| RAG (Saathi) | Qdrant |
| Frontend | React 18 + Vite + TanStack Query |
| Infra | Docker Compose from day one |

## System flow
Teller Input → Matching Engine → Flag Engine → Gemini (explanation) → Dashboard → PostgreSQL audit ledger

Positioning behind this flow: [[Product & Positioning#Deterministic-engine framing]].

## EOD reconciliation flow (locked)
- **Ingestion from CBS (PIBAS):** CSV export at EOD for hackathon MVP. Direct DB/API integration is post-hackathon — do not build against a PIBAS API surface we've never seen. (See [[Product & Positioning#Legacy systems in scope]] for full legacy-system list.)
- **Teller input:** one denomination count at EOD only. Never per-transaction (anti-pattern — adds friction, new error source, breaks the "reconciles the human" pitch).
- **Culprit detection:** deterministic pattern-match on variance signature (digit transposition, duplicate posting, missed reversal, denomination-specific shortfall, cash-in/out miskey, wrong adjacent account). Ranked top 3–5.
- **Gemini's role:** post-hoc Urdu explanation of the engine's picks. Does not decide, does not rank.
- **Handover artifact:** signed EOD Recon Report (PDF) — teller ID, opening float, cash-in/out, expected vs actual, variance, exceptions + resolutions, audit ledger hash. Replaces current paper/Excel teller sheet. Format per [[Brand Voice]].

## Build sequence
`requirements.txt` → `schema.sql` → synthetic data generator → matching engine → FastAPI routes → React dashboard

`schema.sql` already generated: tables, ENUMs, triggers, views, functions, indexes.

**Critical seam:** [[Team & Roles#Critical seam|`ground_truth.py`]] (test oracle) must connect to the matching engine before any UI work starts.

## Deployment model
- On-prem, bank's data center, internal WAN — same posture as PIBAS.
- No public cloud (SBP data localization makes it a non-starter).
- No customer data leaves bank perimeter.

## Hardware
Hardware-agnostic on cash counters. Manual denomination entry is the MVP path. Serial/USB integration (Glory/Kisan/etc.) is roadmap — never a hackathon dependency.

## Related
- [[Team & Roles]] — who owns each layer, critical seam
- [[Product & Positioning]] — why the engine is deterministic, not ML-decided
- [[Brand Voice]] — EOD Recon Report formatting rules
