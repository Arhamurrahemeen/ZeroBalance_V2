---
project: ZeroBalance
type: product
updated: 2026-07-07
---

# Product & Positioning

## What it is
Back-office EOD reconciliation co-pilot for bank tellers. Not customer-facing. Full build: [[Technical Architecture]].

## Locked pitch line
"Every tool reconciles the institution. ZeroBalance reconciles the human."

## Anchor line (user vs. buyer)
Teller = user, emotional story. Bank = buyer, ROI target.
Chain: teller error → suspense account → SBP audit finding + forced overtime.

"Used by the teller, but bought by the bank."

## Novelty framing (honest)
Positional, not algorithmic — frontline teller + SBP/RAAST/CDM context + Urdu + wellbeing.
Underlying tech (anomaly detection, RAG) is mature. Named competitors serve CFO/controllership level, top-down; none build for the individual frontline teller. Frontline-teller grounding comes from [[Domain Consultant|Khursheed Alam]].

## Deterministic-engine framing
"We don't hand auditors a black box; we use deterministic matching they can audit, then AI explains it in Urdu."
Gemini explains, never decides — see [[Technical Architecture#System flow]].

## Competitor reference set
- Global: BlackLine, Trintech (Cadency/Adra), Duco, ReconArt, FloQast, HighRadius, AutoRek, OneStream, Kani, Aurum
- Pakistan: OMA, Euronet, NLS Banking, MoneyTree/Forvis Mazars

## Market data (cited)
| Metric | Value |
|---|---|
| Reconciliation software market | ~$2–3.5B, ~14–16% CAGR |
| BFSI share | ~47% of market; APAC fastest-growing |
| Pakistan branches | 17,708 commercial bank branches (2024, IMF) |
| Pakistan depositors | ~98 million |
| Manual reconciliation time | ~30% of finance team time (PwC) |
| Manual error rate | 5–10% vs. <1% automated |
| Automation time savings | up to 80% cut in reconciliation time |

## Regulatory anchors
SBP half-yearly close (June 30 + Dec 31), RAAST, CDM, KYC, SBP circulars.

## Legacy systems in scope
PIBAS, Symbol, CARTS, Altitude, Ultimus. PIBAS is the CSV ingestion source for the MVP — see [[Technical Architecture#EOD reconciliation flow (locked)]].

## Related
- [[Technical Architecture]] — engine, flow, and deployment behind this pitch
- [[Domain Consultant]] — source of the frontline-teller framing
- [[Brand Voice]] — tone/format these lines are delivered in
