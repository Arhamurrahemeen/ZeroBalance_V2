---
project: ZeroBalance
type: reassessment
created: 2026-07-08
updated: 2026-07-08
trigger: Bootcamp Session 3 — Design Thinking & Problem-Solution Fit (Nidal Sheikh)
status: live
tags:
  - project/zerobalance
  - type/reassessment
  - status/live
---
## Why this note exists

Session 3 ([[Bootcamp_notes#Session 3 — Design Thinking & Problem-Solution Fit (Jul 8)]]) was a PSF stress test dressed as a design thinking session. The GASGADE case study is the direct mirror for ZeroBalance: technically dominant, no market competition, killed by end-user friction. This note re-audits ZeroBalance against that lens before Session 4 (Lean Canvas / DVF Fit, Jul 9) locks the pitch narrative.

**Governing thesis after Session 3:** every feature earns its slot by answering one question — *does this cut minutes off the teller's EOD close, or doesn't it?* Everything else is a roadmap slide.

## Current tagline

**Locked:** *"Every tool reconciles the institution. ZeroBalance reconciles the human."*

**Proposed sharpening for the teller-facing pitch:** *"Every tool reconciles the institution. ZeroBalance sends the teller home."*

> Two audiences, two lines. "Reconciles the human" stays on the bank-buyer slide (emotional, positioning). "Sends the teller home" goes on the teller-facing slide (concrete, time-based, testable). The second line is what design thinking demands — the value is measurable in minutes, not vibes.

## Current scope (from [[Technical Architecture]])

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Teller MVP — back-office EOD reconciliation co-pilot | Hackathon build (72 hours) |
| Phase 2 | BOM branch console | Roadmap slide |
| Phase 3 | Regional Ops rollup + SBP report auto-export | Roadmap slide |

**Deployment:** on-prem in bank data center via internal WAN (PIBAS posture). No public cloud. No customer data leaves bank perimeter.
**Ingestion:** CSV export from PIBAS at EOD (MVP). Direct DB/API integration is post-hackathon.
**Teller input:** one denomination count at EOD. Never per-transaction.
**Hardware:** manual denomination entry for MVP. Serial/USB integration with Glory/Kisan is roadmap.

## Current features vs. Session 3 lens

| Feature                                                                                                                                            | Cuts teller time-to-close?                          | Session 3 verdict                                 | Action                                         |
| -------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------- |
| Matching engine → ranked top 3–5 culprits                                                                                                          | Yes — replaces manual ledger hunt                   | Core value                                        | Keep, core                                     |
| Denomination count input                                                                                                                           | Yes — one entry vs. paper recount                   | Core value                                        | Keep, core                                     |
| Deterministic pattern-match (digit transposition, duplicate posting, missed reversal, denomination shortfall, cash miskey, wrong adjacent account) | Yes — the actual "reconciles the human" mechanic    | Core value                                        | Keep, core                                     |
| One-line Urdu explanation (Groq/Llama 3.3)                                                                                                         | Maybe — needs Khursheed test                        | Nice, but unvalidated                             | Keep, shrink to one sentence, test with teller |
| Signed EOD Recon Report (PDF, audit ledger hash)                                                                                                   | Yes — replaces handwritten sheet                    | Handover artifact matters                         | Keep, simplify template                        |
| Exception worklist (React dashboard)                                                                                                               | Yes — if minimal-click. No — if it looks like Jira. | Core value if UX is right                         | Keep, wireframe on paper first                 |
| Isolation Forest fraud layer                                                                                                                       | No — teller doesn't care at 6pm                     | GASGADE trap — judge-impressive, teller-invisible | **Remove from MVP → roadmap slide**            |
| Saathi RAG (Qdrant + LLM chatbot)                                                                                                                  | No — adds interaction cost, not saves time          | GASGADE trap — highest risk in stack              | **Remove from MVP → roadmap slide**            |
| Ageing view                                                                                                                                        | No — that's a BOM console feature                   | Wrong phase                                       | **Remove from MVP → Phase 2**                  |

**Collapsed MVP flow after Session 3 cut:**
`denomination count input → matching engine → ranked top 3 culprits → one-line Urdu explanation → confirm/resolve → signed PDF report`

## Current technical architecture (from [[Technical Architecture]])

| Layer | Choice | Session 3 verdict |
|---|---|---|
| Backend | FastAPI | Keep |
| Database | PostgreSQL 16 (audit-trail, ACID) | Keep |
| Matching | rapidfuzz (exact + fuzzy), scikit-learn (Isolation Forest) | Keep rapidfuzz. Isolation Forest → roadmap. |
| AI explanation | Groq API serving Llama 3.3 70B (was Gemini) | Keep, but scoped to one sentence per exception |
| RAG (Saathi) | Qdrant + LLM | **Cut from MVP** — no evidence teller needs it |
| Frontend | React 18 + Vite + TanStack Query | Keep — but paper wireframe first |
| Infra | Docker Compose | Keep |

**Flow (current):** Teller Input → Matching Engine → Flag Engine → LLM (explanation) → Dashboard → PostgreSQL audit ledger.
**Flow (proposed, post-cut):** Denomination Count → Matching Engine → Ranked Culprits → Urdu One-Liner → Confirm/Resolve → Signed PDF + Audit Ledger.

## Design thinking flaws — the five phases, honestly graded

| Phase | Status | The gap |
|---|---|---|
| Empathize | Failed | n=1 (Khursheed), interview only, zero observed EOD close |
| Define | Half-done | Problem defined from the **bank's** angle (SBP audit, suspense, overtime). Not from the teller's job-to-be-done: *go home.* |
| Ideate | Over-done | Five features stacked. Team of 3, 72 hours. |
| Prototype | Skipped a step | Went straight to React + FastAPI. No paper wireframe tested with a teller. |
| Test | Not started | `ground_truth.py` is a synthetic oracle, not a user test. Zero teller usability sessions. |

### Deeper flaws surfaced by Session 3

1. **Solving for the buyer, not the user.** Every current feature answers "why should the bank buy" (audit hash, SBP compliance, deterministic engine). None answer "why does the teller reach for it tomorrow at 6pm." Direct GASGADE inversion.
2. **Saathi RAG is `[Likely]` judge-bait, not teller need.** A tired teller at EOD does not want to converse with a chatbot. Highest GASGADE-risk feature in the stack.
3. **Urdu explanation layer is untested.** Might comfort the teller. Might add cognitive load. No evidence either way.
4. **"Reconciles the human" is unvalidated with a teller.** Beautiful positioning. Never spoken to a career banker to check if it lands or sounds like therapy talk.
5. **Prototype-before-test inversion.** Building on assumptions from weeks-old Khursheed conversations, not fresh validation.

## What to remove / add — side by side

### Remove (from MVP → roadmap)

| Item | Why |
|---|---|
| Isolation Forest fraud layer | Judge-impressive, teller-invisible. No time-to-close impact. |
| Saathi RAG (Qdrant + LLM) | Zero teller-need evidence. Adds interaction cost. |
| Ageing view | Wrong phase — BOM console feature. |
| Long Urdu explanations | Shrink to one sentence. Longer versions add reading time, not comfort. |

### Add (must exist before Session 6, Jul 13)

| Item | Why |
|---|---|
| Paper wireframe of exception screen | Test the concept before Wahaj writes more React |
| 30-min shadow protocol for Khursheed | Observe, don't ask. Watch where he hesitates during a real EOD. |
| Time-to-close-EOD baseline (current paper/Excel flow) | The one north-star metric. Ask Khursheed: good-day time, bad-day time. |
| 2–3 more teller conversations via Khursheed | n=1 is not PSF evidence. Session 4 will surface this gap. |
| "Teller says no" objection log | Every objection Khursheed and other tellers raise, written down, addressed before Session 9 (Pitch, Jul 16). |
| One live usability test at Session 6 (Rapid Prototyping) | Not a demo — a task: "close this EOD." Watch. |

## What to work on this week (priority order)

1. **Today** — cut MVP scope to the collapsed flow above. Update [[Technical Architecture]] to reflect the cut. Isolation Forest, Saathi RAG, ageing view → roadmap slide language.
2. **Tonight** — draft paper wireframes + 20-min shadow protocol for Khursheed. Sketch on paper, not Figma.
3. **Jul 9 (before Session 4)** — send shadow protocol to Khursheed. Ask him for 2–3 more teller intros. Get the current-flow time-to-close baseline number (good day + bad day).
4. **Jul 9–10** — Wahaj holds React work until paper wireframes are teller-validated. Miswan focuses on matching engine + ranked culprits (the actual time-saver), not fraud layer.
5. **Jul 13 (Session 6, Rapid Prototyping)** — Khursheed live task: "close this EOD on ZeroBalance." Stopwatch it. Compare to baseline.
6. **Jul 16 (before Session 9, Pitch)** — objection log closed out. Pitch story rewritten around minutes saved, not features shipped.

## The one question that decides everything

If Khursheed says "this is more work than my paper sheet" after the paper walkthrough — are we willing to gut the flow and restart, or are we going to defend the current build because code is already written?

Answer that now. Not on Jul 13.

## Related
- [[Bootcamp_notes]] — Session 3 raw notes and action items
- [[Technical Architecture]] — needs update to reflect MVP cut
- [[Product & Positioning]] — tagline layer, buyer vs. user split
- [[Team & Roles]] — Wahaj (frontend hold), Miswan (engine focus), Arham (Khursheed + shadow protocol)
- [[Hackathon Logistics]] — Stage 2 timeline

---

## v2 Addendum — Jul 9 (post-[[Teller Workflow - Khursheed Interview 2|Khursheed Interview #2]])

### What changed in the product
Product & Positioning shifted from **EOD reconciliation co-pilot** to **validation + reconciliation layer** — adds pre-post (real-time) validation, cheque capture, digital Excess Ledger. Full v2 in [[Product & Positioning]].

### Honest tension with Session 3 governing thesis
Session 3 thesis: *"does this feature cut minutes off the teller's EOD close?"*

Pre-post validation does **not** directly cut EOD minutes. It prevents errors during the day, which indirectly means fewer EOD variances to resolve. Different value proposition surface.

**The GASGADE-inversion risk this creates:**
- v1 MVP was a **single-touchpoint** product — teller opens ZB once, at EOD.
- v2 MVP is an **all-day-touchpoint** product — teller interacts with ZB on every transaction.
- Expanded surface = more chances for the teller to find ZB slower/more friction than raw CBS entry, at which point adoption dies.

**Which is worse: Session 3 GASGADE (build for judges, not tellers) or v2 GASGADE (build a validation layer the teller experiences as friction)?**

Both. The v2 pre-post layer must be validated with Khursheed via paper wireframe before any code. If the pre-post UX adds >2 seconds per transaction vs raw CBS entry, we cut it back to EOD-only.

### v2 north-star metric — TWO now, not one
1. **Original:** teller time-to-close-EOD on ZeroBalance vs current paper flow (must be faster)
2. **New:** teller time-per-transaction on ZeroBalance vs raw CBS (must not be slower)

Both metrics get tested at Session 6 (Rapid Prototyping, Jul 13).

### Design Thinking re-audit against v2

| Phase | v1 status | v2 status | Gap |
|---|---|---|---|
| Empathize | Failed (n=1) | Improved — Interview #2 surfaced 3 new fault modes we didn't know about | Still n=1. Shadow protocol not run yet. |
| Define | Half-done | **Sharpened** — "CBS is a dumb pipe" is a crisp, defensible problem definition | Buyer-side framing dominant, teller JTBD ("go home") still secondary |
| Ideate | Over-done | **Worse** — v2 added 3 more feature surfaces (pre-post, cheque capture, Excess Ledger) | Anti-scope-creep guard says all 3 pass (72hr demo-able, novelty +, infra controlled). But surface area matters — see GASGADE-inversion above. |
| Prototype | Skipped | Still skipped | Paper wireframes URGENT — now cover 2 surfaces (pre-post + EOD) |
| Test | Not started | Not started | Session 6 must test both new metrics |

### v2 doesn't change these Session 3 cuts
Isolation Forest → still cut. Saathi RAG → still cut. Ageing view → still Phase 2.

### The one question v2 raises
**Is pre-post validation a real product need or a founder-anchored reaction to a single interview insight?**

- Case for: Khursheed named CBS validation gap as the root of typo errors. Direct evidence.
- Case against: he also said miscounts are "rare." If errors are rare, is a pre-post layer solving a small problem with a large product surface?
- Resolution: 2–3 more teller interviews. If they confirm "CBS accepts anything, we've all had typo posts," pre-post stays. If they say "we never mistype," pre-post is founder anchoring — cut it.

Answer this before Session 6 (Jul 13), not after.

### Updated action items
- [ ] Paper wireframe of pre-post validation screen (new)
- [ ] Paper wireframe of cheque capture screen (new)
- [ ] Paper wireframe of digital Excess Ledger + dual sign-off (new)
- [ ] Push Khursheed for 2–3 teller intros — the pre-post-vs-cut decision hinges on this
- [ ] Extend `ground_truth.py` to cover pre-post validation test cases
- [ ] Update `schema.sql` with 4 new tables per [[Technical Architecture#Schema deltas (from v1 `schema.sql`)]]
