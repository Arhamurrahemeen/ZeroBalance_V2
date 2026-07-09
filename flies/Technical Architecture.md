---
project: ZeroBalance
type: technical
updated: 2026-07-09
version: v2
status: live
tags:
  - project/zerobalance
  - type/tech
  - status/live
---
	
# Technical Architecture (v2)

**Version note:** v2 following [[Teller Workflow - Khursheed Interview 2|Khursheed Interview #2]] and [[Product & Positioning|Product v2]]. Adds pre-post validation layer, cheque capture, and digital Excess Ledger. Original EOD reconciliation flow retained.

## Scope (phased)
| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Teller MVP — pre-post validation + EOD reconciliation | In build |
| Phase 2 | BOM branch console | Roadmap slide, not code |
| Phase 3 | Regional Ops rollup + SBP report auto-export | Roadmap slide, not code |

## Two intervention points

**A. Pre-post (real-time, during the day)**
Sits between teller input and CBS. Validates every transaction before commit.

**B. Post-facto (EOD)**
Reconciles physical cash to CBS records at day-close. Original v1 scope.

## Tool stack
| Layer | Choice |
|---|---|
| Backend | FastAPI |
| Database | PostgreSQL 16 (audit-trail, ACID) |
| Matching | rapidfuzz (exact + fuzzy) |
| Anomaly (roadmap) | scikit-learn Isolation Forest — cut from MVP per [[Design Thinking Reassessment]] |
| AI explanation | Groq API — Llama 3.3 70B (open-weight, on-prem story) |
| RAG (Saathi) | Qdrant — **cut from MVP** per [[Design Thinking Reassessment]] |
| Frontend | React 18 + Vite + TanStack Query |
| Infra | Docker Compose from day one |

## System flows

### Pre-post flow (NEW)
`Teller types transaction → ZeroBalance Validation Engine → [pass? → CBS post] [fail? → warn teller + log to validation_log]`

Checks fire in this order:
1. Denomination sum == typed amount
2. CNIC ↔ account-holder name fuzzy match (rapidfuzz)
3. Duplicate detection (same account + amount, N-second window)
4. Large-amount threshold → soft confirm
5. Basic sanity (impossible withdrawal, wrong-account pattern)

Failed checks: warning shown, teller can override with reason (logged), or correct and resubmit. All events → `validation_log`.

### EOD reconciliation flow (v1, retained)
`Teller Input (opening float + EOD count) → Matching Engine → Flag Engine → Groq/Llama 3.3 (Urdu explanation) → Dashboard → PostgreSQL audit ledger → Signed PDF Recon Report`

- **Ingestion from CBS (PIBAS):** CSV export at EOD. Direct DB/API integration is post-hackathon.
- **Opening float declaration (NEW in v2):** teller declares denomination breakdown of opening float at day-start (vault issues bulk cash without denomination — see [[Teller Workflow - Khursheed Interview 2|Khursheed #2]] §5.1). This anchors the whole audit chain.
- **Culprit detection:** deterministic variance signature match (digit transposition, duplicate posting, missed reversal, denomination shortfall, cash miskey, wrong adjacent account). Ranked top 3–5.
- **LLM role:** post-hoc Urdu explanation. Does not decide, does not rank.
- **Handover artifact:** signed EOD Recon Report (PDF) — teller ID, opening float, cash-in/out, expected vs actual, variance, exceptions + resolutions, audit ledger hash.

### Cheque capture flow (NEW)
`Cheque received → teller captures MICR + amount + denomination out → cheque_transactions table → drawer receipt logged`
Closes the current gap where cheque cash-outs bypass CBS entirely.

### Digital Excess Ledger flow (NEW)
`EOD variance detected → auto-entry to excess_ledger → dual sign-off required (teller + OM) → audit hash → SBP-audit-ready trail`
Replaces the paper Excess Ledger. Direct fraud-vector closure.

## Schema deltas (from v1 `schema.sql`)

New tables required:
- `validation_log` — every pre-post check, pass/fail, override reason, teller_id, timestamp
- `cheque_transactions` — MICR, amount, denomination out, drawer_ref, teller_id, timestamp
- `excess_ledger` — variance_id, amount, denomination, teller_id, om_id, dual_signoff_hash, resolution_status
- `opening_float_declaration` — teller_id, date, denomination breakdown, om_id

`schema.sql` update needed before any FastAPI route work resumes.

## Build sequence (revised)
`schema.sql v2 (add new tables)` → synthetic data generator update → **pre-post validation engine** → **matching engine (existing)** → FastAPI routes (validation + reconciliation) → React dashboard (teller input surface + EOD worklist + Excess Ledger view)

**Critical seam:** [[Team & Roles#Critical seam|`ground_truth.py`]] must extend to test pre-post validation cases in addition to EOD variance signatures.

## Deployment model
- On-prem, bank's data center, internal WAN — same posture as PIBAS.
- No public cloud (SBP data localization).
- No customer data leaves bank perimeter.

## Production integration (pre-post)
Real production requires one of:
- **Browser extension** over the CBS portal (intercept form submits, run validation, allow/warn)
- **Middleware proxy** between teller portal and CBS

Both are Phase-2 conversations. **Demo path:** ZeroBalance IS the teller UI. Validation fires visibly. "CBS post" is mocked. Have integration answer ready for judges.

## Hardware
Hardware-agnostic. Manual denomination entry is MVP. Serial/USB integration (Glory/Kisan) is roadmap.

## What's cut from MVP (per [[Design Thinking Reassessment]])
- Isolation Forest fraud layer → roadmap
- Saathi RAG (Qdrant + chatbot) → roadmap
- Ageing view → Phase 2 BOM console

## Related
- [[Product & Positioning]] — why validation + reconciliation, not just reconciliation
- [[Teller Workflow - Khursheed Interview 2]] — source of the CBS-is-dumb finding
- [[Design Thinking Reassessment]] — MVP cut list, v2 tension flagged
- [[Team & Roles]] — layer ownership
- [[Brand Voice]] — Recon Report formatting
