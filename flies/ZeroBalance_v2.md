---
project: ZeroBalance
type: canonical-index
updated: 2026-07-09
version: v2
---

# ZeroBalance v2 — Canonical Index

**Read this first.** Single source of truth after [[Teller Workflow - Khursheed Interview 2|Khursheed Interview #2]] (Jul 9) and the honest-review conversation the same day.

---

## What ZeroBalance is (1 paragraph)

ZeroBalance is a back-office validation and reconciliation layer for bank tellers, sitting between the teller and the bank's core banking system (CBS). Because CBS platforms like AHBS (Allied), T24 (most banks), and Symbols (UBL) are dumb posting engines that accept whatever the teller types with no sanity check, errors and cash variances surface late — usually as SBP audit findings or corruption in paper artifacts. ZeroBalance catches errors before they hit CBS (pre-post validation) and reconciles physical cash against CBS records after the day closes (EOD), while replacing paper artifacts like the Excess Ledger with a signed digital audit trail. On-prem deployment. Used by the teller, bought by the bank.

## Tagline

**Primary (buyer):** *"CBS posts what the teller types. ZeroBalance makes sure the teller typed the truth."*
**Teller-facing:** *"Every tool reconciles the institution. ZeroBalance sends the teller home."*

## The four features (ranked by willingness-to-buy)

| #   | Feature                                  | Real user pain?                                 | 72hr build? | Bank appetite |
| --- | ---------------------------------------- | ----------------------------------------------- | ----------- | ------------- |
| 1   | Digital Excess Ledger + dual sign-off    | **Yes** — Khursheed flagged corruption directly | Yes         | Easy sell     |
| 2   | EOD reconciliation + signed PDF report   | Yes — replaces paper/Excel sheet                | Yes         | Easy sell     |
| 3   | Cheque capture (MICR + denomination out) | Yes — closes a real audit gap                   | Yes         | Yes with data |
| 4   | Pre-post real-time validation            | **Unvalidated** — inferred, not confirmed       | Yes         | Speculative   |

## Honest scoping (post Jul 9 review)

- **Flagship for pitch:** Digital Excess Ledger. Only feature Khursheed unprompted named as a corruption vector.
- **Pre-post validation:** DEMO as roadmap slide, not code the full surface. It was a Wednesday inference, not a validated need.
- **The gap:** n=1 domain source. Every design decision traces to one teller at Bank Al Habib Mirpurkhas. Get 2 more teller interviews before Session 6 (Jul 13) or the pitch dies at PSF questions.

## Two intervention points (technical)

| Point | Scope | Priority |
|---|---|---|
| Pre-post (during day) | 5 checks: denomination sum, CNIC↔name, duplicate, large-amount confirm, sanity | Demo-scope only |
| EOD (post-facto) | Opening float declaration → matching engine → ranked culprits → Urdu explanation → PDF + Excess Ledger | Full build |

Full architecture: [[Technical Architecture]].

## Fault modes addressed

| Fault | Solution |
|---|---|
| Paper Excess Ledger corruption | Digital ledger + dual sign-off + audit hash |
| Cheque cash-out with no digital trail | Cheque capture screen |
| Large-amount miscount | EOD variance detection |
| CBS accepts typos with no validation | Pre-post checks (demo-only) |
| ATM stuck-card excess | Out of scope — roadmap |

## What we cut and why

| Cut | Reason |
|---|---|
| Isolation Forest fraud layer | Judge-impressive, teller-invisible (Session 3 GASGADE test) |
| Saathi RAG (Qdrant + chatbot) | Zero teller-need evidence |
| Ageing view | Wrong phase — BOM console feature |
| Pre-post as flagship | Founder anchoring, not user-validated |

## Anti-delusion guardrails

1. **n=1 is not evidence.** Every feature must survive 2+ teller conversations before code.
2. **New feature ideas must pass three tests:** (a) 72hr demo-able, (b) strengthens novelty, (c) infra we control. Two nos = roadmap slide.
3. **Buyer pathway matters.** Winning the hackathon ≠ shipping to a bank. Don't pitch category-leader ambitions with hackathon-team evidence.
4. **The useful project is smaller than the pitched project.** Whenever the pitch outruns the evidence, cut back.

## Team (needs confirmation)

| Role | Person |
|---|---|
| Lead / CTO / full-stack + engine | Arham |
| Frontend | Wahaj |
| Data / ML | Miswan |
| Domain consultant | [[Domain Consultant|Khursheed Alam]] |

Full ownership split: [[Team & Roles]].

## Deployment

- On-prem, bank's data center, internal WAN — same posture as PIBAS.
- No public cloud (SBP data localization).
- LLM: Llama 3.3 via Groq (demo). Open-weight = credible on-prem self-hosting story.

## Bootcamp 3-day test results (Jul 9)

| Test | Verdict | Condition |
|---|---|---|
| Design Thinking | Conditional pass | Paper wireframes + 2 more teller interviews before Session 6 |
| 72hr / 3 devs | Pass | 65h load, 7h buffer. Wahaj is the bottleneck. |
| Problem-Solution Fit | Conditional pass | Excess Ledger + cheque solid. Pre-post needs Khursheed's paper walkthrough. |
| Banks want it | Pass on 3 of 4 features | Pre-post is the speculative one |

## Immediate next actions

- [ ] Paper wireframes: Excess Ledger, cheque capture, EOD worklist (before Session 6, Jul 13)
- [ ] 2 more teller interviews via Khursheed (before Jul 12)
- [ ] Schema v2 update: 4 new tables (`validation_log`, `cheque_transactions`, `excess_ledger`, `opening_float_declaration`)
- [ ] Extend `ground_truth.py` to cover pre-post cases
- [ ] Confirm team roster (Arham + Wahaj + Miswan? or solo?)
- [ ] Rewrite pitch around Excess Ledger as flagship

## Related notes

- [[Product & Positioning]] — v2 full statement
- [[Technical Architecture]] — v2 full architecture
- [[Teller Workflow - Khursheed Interview 2]] — v2 source material
- [[Design Thinking Reassessment]] — Session 3 cuts + v2 addendum
- [[Bootcamp_notes]] — session-by-session
- [[Team & Roles]] — ownership split
- [[Domain Consultant]] — Khursheed background
- [[Hackathon Logistics]] — dates, deliverables, NDA
- [[Brand Voice]] — tone, colors, fonts

## Version history

- **v2 (Jul 9)** — Post-Khursheed #2. Added pre-post + cheque + digital Excess Ledger. Later same day: honest review cut pre-post to demo-only. Excess Ledger is now flagship.
- **v1 (Jul 7)** — EOD reconciliation co-pilot only.
