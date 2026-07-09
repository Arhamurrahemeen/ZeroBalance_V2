---
project: ZeroBalance
type: product
updated: 2026-07-09
version: v2
status: live
tags:
  - project/zerobalance
  - type/product
  - status/live
---

# Product & Positioning (v2)

**Version note:** v2 restatement following [[Teller Workflow - Khursheed Interview 2|Khursheed Interview #2]] (Jul 9). Key shift: ZeroBalance is now a **validation + reconciliation layer**, not just an EOD reconciliation co-pilot. See §Version history at bottom for what changed.

## What it is (1 paragraph)

ZeroBalance is a back-office validation and reconciliation layer for bank tellers, sitting between the teller and the bank's core banking system (CBS). Because CBS platforms like AHBS (Allied), T24 (most banks), and Symbols (UBL) are dumb posting engines — they accept whatever the teller types with no sanity check — errors, typos, and cash variances only surface at end-of-day, sometimes days later, and often as SBP audit findings. ZeroBalance catches errors *before* they hit CBS (real-time input validation) and reconciles physical cash against CBS records *after* the day closes (EOD reconciliation), while replacing paper artifacts like the Excess Ledger with a signed digital audit trail. Deployed on-prem inside the bank's data center. Used by the teller, bought by the bank.

## Taglines

| Audience | Line |
|---|---|
| Bank buyer (primary) | **"CBS posts what the teller types. ZeroBalance makes sure the teller typed the truth."** |
| Teller-facing (from Session 3) | *"Every tool reconciles the institution. ZeroBalance sends the teller home."* |
| Backup / emotional positioning | *"Every tool reconciles the institution. ZeroBalance reconciles the human."* (retired as lead) |

## The two intervention points

**1. Pre-post — real-time validation (NEW in v2)**
Catches errors during the day, before CBS commits the transaction.
- Denomination sum == typed amount
- CNIC ↔ account-holder name fuzzy match
- Duplicate-post detection (same amount + account within N seconds)
- Large-amount soft confirmation prompt
- Basic sanity (impossible withdrawals, wrong-account patterns)

**2. Post-facto — EOD reconciliation (ORIGINAL scope)**
Physical cash count vs CBS records. Variance signature detection, culprit ranking (top 3–5), Urdu explanation via Groq/Llama 3.3, signed PDF Recon Report, **digital Excess Ledger with dual sign-off** (replaces paper).

## Fault modes now addressed

| Fault (from [[Teller Workflow - Khursheed Interview 2|Khursheed #2]]) | Where we catch it |
|---|---|
| Typed amount ≠ denomination breakdown | Pre-post |
| Extra-digit typo (100 → 1000) | Pre-post |
| Wrong account number | Pre-post (CNIC ↔ name check) |
| Duplicate posting | Pre-post |
| Cheque cash-out with no digital trail | New: cheque capture screen |
| Large-amount miscount | EOD variance detection |
| Paper Excess Ledger corruption | Digital Excess Ledger + dual sign-off + audit hash |
| ATM stuck-card excess | Out of scope — roadmap |

## Anchor line (user vs. buyer)
Teller = user, emotional story. Bank = buyer, ROI target.
Chain: teller error → suspense account → SBP audit finding + forced overtime.
**Buyer hook:** *"CBS was never designed to catch teller errors. ZeroBalance is the missing validation layer."*

## Novelty framing (honest)
Positional, not algorithmic. Frontline teller + SBP/RAAST/CDM + Urdu + wellbeing + **the pre-post validation gap that every PK CBS leaves open**. The last item is v2's real differentiator — no competitor pitches at the pre-post seam because none live at the teller's daily workstation. Underlying tech (deterministic matching, LLM explanation) is mature. Frontline-teller grounding comes from [[Domain Consultant|Khursheed Alam]].

## Deterministic-engine framing
"We don't hand auditors a black box; we use deterministic matching they can audit, then AI explains it in Urdu."
LLM (Llama 3.3 via Groq) explains, never decides — see [[Technical Architecture#System flow]]. Open-weight model doubles as the on-prem answer to "banks don't allow cloud AI."

## Competitor reference set
- Global: BlackLine, Trintech (Cadency/Adra), Duco, ReconArt, FloQast, HighRadius, AutoRek, OneStream, Kani, Aurum
- Pakistan: OMA, Euronet, NLS Banking, MoneyTree/Forvis Mazars

**All compete at controllership/CFO level. None sit at the teller workstation. None address the pre-post validation gap.**

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
PIBAS, Symbols (UBL), AHBS (Allied), T24 (most PK banks), CARTS, Altitude, Ultimus. PIBAS is the CSV ingestion source for the MVP.

## Production integration note (honest)
Pre-post validation in production requires either: (a) browser extension over the CBS portal, or (b) middleware proxy between teller portal and CBS. Both are Phase-2 conversations. **For hackathon demo:** ZeroBalance IS the teller UI. Validation fires visibly, then we "post to CBS" (mocked). Have this answer ready if judges ask.

## Version history

**v2 (Jul 9, 2026)** — Khursheed Interview #2 revealed CBS does zero input validation. Reframed from "EOD reconciliation co-pilot" to "validation + reconciliation layer." Added: pre-post validation, cheque capture, digital Excess Ledger. Retired: "reconciles the human" as lead tagline (now buyer's line leads).

**v1 (Jul 7, 2026)** — EOD reconciliation co-pilot only. Teller error → suspense → SBP audit chain. Deterministic matching + Groq/Llama Urdu explanation.

## Related
- [[Technical Architecture]] — engine, flow, validation layer, deployment
- [[Teller Workflow - Khursheed Interview 2]] — v2 source material
- [[Domain Consultant]] — Khursheed background
- [[Design Thinking Reassessment]] — v2 addendum flags product-surface expansion risk
- [[Brand Voice]] — tone/format
