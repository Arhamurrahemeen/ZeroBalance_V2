---
project: ZeroBalance
type: bootcamp-notes
created: 2026-07-07
updated: 2026-07-07
---
## Gap

Sessions 1–2 logged. Day 2 detail image (IMG_9061.JPG) referenced but not yet shared — send it and I'll fold it in.

Part of Stage 2 in [[Hackathon Logistics]]. Session content feeds [[Team & Roles]] (theme/team fit) and [[Technical Architecture]] (scope-cutting sessions from Jul 10 and Jul 15 onward).

## Full Schedule (10 sessions, July 6–17)

| # | Session | Day / Date | Time | Status |
|---|---|---|---|---|
| 1 | Welcome & Thematic Introduction | Mon, Jul 6 | 2:30–6:00 PM | Attended |
| 2 | Hacking a Hackathon! | Tue, Jul 7 | 10:00 AM–1:00 PM | Attended |
| 3 | Design Thinking & Problem-Solution Fit | Wed, Jul 8 | 10:00 AM–1:00 PM | Upcoming |
| 4 | Lean Canvas Development / DVF Fit | Thu, Jul 9 | 10:00 AM–1:00 PM | Upcoming |
| 5 | Technical Architecture Development | Fri, Jul 10 | 9:30 AM–12:30 PM | Upcoming |
| 6 | Rapid Prototyping | Mon, Jul 13 | 10:00 AM–1:00 PM | Upcoming |
| 7 | UI/UX Fundamentals | Tue, Jul 14 | 10:00 AM–1:00 PM | Upcoming |
| 8 | Vibe Coding | Wed, Jul 15 | 10:00 AM–1:00 PM | Upcoming |
| 9 | Pitch Development | Thu, Jul 16 | 10:00 AM–1:00 PM | Upcoming |
| 10 | Pitching & Storytelling | Fri, Jul 17 | 9:30 AM–12:30 PM | Upcoming |

## Session 1 — Welcome & Thematic Introduction (Jul 6)

**Format:** 6 panelists, each 20+ years in fintech, cross-domain. Names/domains not yet captured — add if you recall them.

### Ground rules confirmed
| # | Rule |
|---|---|
| 1 | Solution/idea not locked — can still pivot |
| 2 | Team roster not locked — can add/remove members |
| 3 | Theme can change, but only before the last bootcamp session (Jul 17), not after |
| 4 | AI usage unrestricted — use as much as wanted |
| 5 | Advised: diverse-domain team members, not all-technical |

### What a prototype should look like (any of 4 forms)
| Form | Examples |
|---|---|
| Clickable experience | App screens, service flow, onboarding, complaint journey |
| Workflow simulation | Payment flow, consent flow, fraud alert journey, merchant reconciliation |
| Functional demo | Chatbot, dashboard, AI classifier, mock verification engine |
| Technical blueprint | Mock API architecture, data assumptions, security model, pilot feasibility note |

Explicit from deck: "Prototype does not mean production-ready banking software. It means a clear, testable version of the product logic."

### 72-hour build path (per primer deck)
0–6h problem + user → 6–18h concept + flow → 18–36h prototype v1 → 36–54h refine + test → 54–72h pitch + submit.

**Minimum submission package:** problem definition, user persona, prototype/demo/wireframe, technical approach, data assumptions, risk/compliance note, pitch deck, pilot-readiness note.

> Gap: richer than what's currently logged in [[Hackathon Logistics#Final deliverables (due August)]] ("15-page report + pitch deck"). Needs reconciling.

### Our themes: AI in Banking + Emerging Fintech Solutions

**Theme 1 — Artificial Intelligence in Banking**
| | |
|---|---|
| What teams may build (official examples) | AI financial coach, fraud/scam awareness alert, complaint/friction classifier, customer support assistant |
| Expected outputs by final submission | AI workflow, explainability note, prototype/chatbot demo, compliance considerations, pilot roadmap |

> Risk flag: every official example is customer-facing. ZeroBalance is back-office/teller-facing — none of the listed examples match our angle. The positional-novelty bet in [[Product & Positioning#Novelty framing (honest)]] cuts both ways here: differentiator if judges reward it, risk if their rubric is anchored on these examples. Worth a direct check with a mentor/panelist.

**Theme 5 — Emerging Fintech Solutions**
| | |
|---|---|
| Sub-tracks | Merchant Growth Platform, Next-Gen Raast Experience, Freelancer Financial Toolkit, SME Financial Health Dashboard |
| Closest official anchor | Merchant Growth Platform — explicitly lists "reconciliation and cashflow visibility" |
| Expected outputs | Business use case, dashboard prototype, payment workflow, revenue/adoption model, banking integration concept |

Open question: does a dual-theme pick (Theme 1 + Theme 5) mean we're expected to hit both expected-outputs lists, or pick one as primary and the other as flavor? Not answered yet.

### Other themes (reference only — not building here)

Logged for completeness/pivot-awareness per the theme-lock rule (can still switch before Jul 17). None of these currently compete with our Theme 1 + 5 pick.

**Theme 2 — Blockchain & Digital Trust**
| | |
|---|---|
| Why it matters | Document/identity verification, consent tracking, tamper-evident records. Not crypto speculation — trust, verification, auditability. |
| What teams may build | Digital trust framework for document/identity verification, consent tracking workflow, tamper-evident audit trail, trusted verification trail for a financial service interaction |
| Expected outputs | Verification workflow, trust model, consent flow, security considerations, pilot feasibility note |

**Theme 3 — UX/UI for Inclusive Financial Services**
| | |
|---|---|
| Why it matters | Adoption depends on simplicity, trust, accessibility, local relevance. Reduces drop-offs for users new to formal digital finance. |
| What teams may build | Banking journey for first-time users, inclusive account opening flow, complaint/card-management redesign, local-language or accessibility-first mobile screens |
| Expected outputs | User personas, customer journey maps, clickable prototype/demo, inclusion impact assessment, pilot-readiness note |

**Theme 4 — Open Banking APIs**
| | |
|---|---|
| Why it matters | Secure, consent-based connections between banks, fintechs, and approved partners. Teams use mock APIs and simulated workflows — no real bank integration expected. |
| What teams may build | Mock API use case for fintech partnership, consent-based data sharing flow, personal finance/SME dashboard on dummy data, API architecture for customer value |
| Expected outputs | API architecture, mock API flow, consent framework, security assessment, pilot feasibility review |

Note: ZeroBalance's audit ledger + deterministic matching engine could technically read as a Theme 2 (tamper-evident record / trust layer) argument too, if the back-office framing struggles to land in Theme 1's judging rubric — worth keeping as a fallback narrative, not a rebuild.

### AI governance rulebook (flagged for AI-theme builds — Day_1.JPG)
| Category | Reference |
|---|---|
| Standards | ISO/IEC 42001 & 23894 |
| Framework | NIST AI RMF (Govern, Map, Measure, Manage) |
| Principles | OECD AI Principles |
| Data discipline | DAMA-DMBOK |
| Privacy | GDPR |
| Regulation | EU AI Act (risk-tiered) |
| National policy | Country AI strategies — action: read SBP-published national AI/fintech policy |
| Financial sector | Prudential guidance (SR 11-7-style model risk management, extended to AI/ML) |

Panelist "so what": map controls once against ISO/NIST/OECD → satisfies 80%+ of GDPR, EU AI Act, and SBP expectations simultaneously. Build the control library once, reuse everywhere. Ties directly into [[Product & Positioning#Regulatory anchors]] and the deterministic-engine framing in [[Technical Architecture#System flow]].

## Session 2 — Hacking a Hackathon! (Jul 7)

**Speaker:** Sarfaraz — Co-founder & CTO, Plouton AI

### Deliverables due before the final hackathon
Lean Canvas Model, Problem-Solution Fit, Prototype Blueprint, Attendance, Pitch Deck.

### Judging rubric (first real scoring breakdown we have)
| Criterion | Weight |
|---|---|
| Problem clarity & impact | 30% |
| Working demo over slides | 25% |
| Feasibility & scrappiness | 20% |
| Execution quality | 15% |
| Presentation & confidence | 10% |

> Use this to arbitrate every build-vs-polish decision from here on. 25% on "working demo over slides" argues against over-investing in deck design; 30% on problem clarity argues for nailing the "teller error → suspense account → SBP audit finding" chain early and hard.

### 72-hour timeline (per Sarfaraz)
| Hours | Phase |
|---|---|
| 0–6 | Define |
| 6–24 | Core build |
| 24–48 | Extend |
| 48–60 | Harden |
| 60–72 | Pitch prep |

> Discrepancy: doesn't match the primer deck's timeline logged under Session 1 (0–6h problem+user, 6–18h concept+flow, 18–36h prototype v1, 36–54h refine+test, 54–72h pitch+submit). Two sources, two breakdowns — not urgent, but pick one (or blend) before the actual 72 hours start.

### Scope discipline
Can't build everything in 72 hours. Cut scope mid-build; keep cut features as an explicit "future roadmap" line in the pitch, not a silent drop. Validates the existing phase split in [[Technical Architecture#Scope (phased)]] (Phase 1 MVP / Phase 2–3 roadmap slides).

### Team roles (Sarfaraz's framework)
The Builder, The Validator, The Story Teller, The Integrator.

> Doesn't map cleanly onto a solo team — right now Arham covers all four implicitly. Worth revisiting once new members join — see [[Team & Roles]].

### Pitch deck structure (locked, 8–10 slides)
Problem → Solution (business-framed, not technical) → Live Demo → Impact → The Ask.

> Reinforces [[Brand Voice#Document tone]] and the "reconciles the human" framing over architecture diagrams on the Solution slide.

### Key takeaways (verbatim from slide)
1. Pick one specific problem and one specific user — precision beats scope.
2. Have a working demo by hour 24. Ugly and working beats pretty and broken.
3. Build the pitch story alongside the product, not the night before.
4. Checkpoint every 6 hours and cut scope early, without guilt.
5. Rehearse the pitch out loud, on the real demo, more than once.

### Flags from Day 2

- **Unclear line:** "60% Product and 40% Product matters" — as transcribed this is self-contradictory (likely a typo for Product vs. Presentation/Pitch). Not guessing at it — confirm the real split.
- **Critical flag:** "Banks don't allow cloud service providers and AI models due to security risks." Consistent with the existing on-prem, no-public-cloud call in [[Technical Architecture#Deployment model]] — but potentially in tension with the Gemini API explanation layer, which is a cloud-hosted external call. Need to clarify whether this is a blanket ban on AI models or specifically opaque/black-box models (which the deterministic-engine framing already argues against). If literal, the pitch needs an on-prem/open-weight LLM fallback story even if Gemini stays for the hackathon demo itself.

## Action Items

- [ ] Read SBP-published national AI/fintech policy circulars — feeds [[Product & Positioning#Regulatory anchors]] and Theme 1's "compliance considerations" output.
- [ ] Reconcile the minimum submission package above against [[Hackathon Logistics#Final deliverables (due August)]] — currently under-logged there.
- [ ] Decide: build strictly within Theme 1's official (customer-facing) examples, or defend the back-office/teller angle as deliberate novelty. Needed before the Jul 17 theme-lock deadline.
- [ ] Confirm with a mentor whether dual-theme submission must satisfy both themes' expected-outputs lists.
- [ ] Get the correct "Product vs. X" split — "60% Product and 40% Product" as noted doesn't parse.
- [ ] Resolve the "no cloud AI models" objection against the Gemini explanation layer — on-prem LLM fallback story needed before pitch.
- [ ] Reconcile the two conflicting 72-hour timelines (primer deck vs. Sarfaraz's Define/Build/Extend/Harden/Pitch).
- [ ] Share IMG_9061.JPG for the rest of Day 2 detail.
- [ ] Map the new team (once formed) to Sarfaraz's 4 roles (Builder/Validator/Storyteller/Integrator).
- [ ] Add new team members to [[Team & Roles]] as they're recruited; re-split ownership.

## Related
- [[Hackathon Logistics]] — Stage 2 context, NDA, final deliverables
- [[Team & Roles]] — team this bootcamp trains
- [[Technical Architecture]] — where scope-cutting sessions (Jul 10, 15) should land
- [[Product & Positioning]] — theme-fit risk and regulatory anchors surfaced in Session 1
