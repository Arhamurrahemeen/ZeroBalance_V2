---
project: ZeroBalance
type: bootcamp-notes
created: 2026-07-07
updated: 2026-07-08
status: live
tags:
  - project/zerobalance
  - type/notes
  - status/live
---
## Gap

Sessions 1–3 logged. Day 2 detail image (IMG_9061.JPG) referenced but not yet shared — send it and I'll fold it in.

Part of Stage 2 in [[Hackathon Logistics]]. Session content feeds [[Team & Roles]] (theme/team fit) and [[Technical Architecture]] (scope-cutting sessions from Jul 10 and Jul 15 onward).

## Full Schedule (10 sessions, July 6–17)

| #   | Session                                | Day / Date  | Time             | Status   |
| --- | -------------------------------------- | ----------- | ---------------- | -------- |
| 1   | Welcome & Thematic Introduction        | Mon, Jul 6  | 2:30–6:00 PM     | Attended |
| 2   | Hacking a Hackathon!                   | Tue, Jul 7  | 10:00 AM–1:00 PM | Attended |
| 3   | Design Thinking & Problem-Solution Fit | Wed, Jul 8  | 10:00 AM–1:00 PM | Attended |
| 4   | Lean Canvas Development / DVF Fit      | Thu, Jul 9  | 10:00 AM–1:00 PM | Upcoming |
| 5   | Technical Architecture Development     | Fri, Jul 10 | 9:30 AM–12:30 PM | Upcoming |
| 6   | Rapid Prototyping                      | Mon, Jul 13 | 10:00 AM–1:00 PM | Upcoming |
| 7   | UI/UX Fundamentals                     | Tue, Jul 14 | 10:00 AM–1:00 PM | Upcoming |
| 8   | Vibe Coding                            | Wed, Jul 15 | 10:00 AM–1:00 PM | Upcoming |
| 9   | Pitch Development                      | Thu, Jul 16 | 10:00 AM–1:00 PM | Upcoming |
| 10  | Pitching & Storytelling                | Fri, Jul 17 | 9:30 AM–12:30 PM | Upcoming |

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

### UI/UX design guidance (panelist)
- "The best design is the one with minimal clicks." Fewer clicks/buttons on screen = better UX.
- "A picture says a thousand words." Use icons and visuals to guide the user, not just text.

> Direct application to ZeroBalance: the teller dashboard ([[Technical Architecture#Tool stack|React dashboard]]) runs at EOD, under time pressure, one denomination count. Minimal-click design isn't just good UX here — it's the "reconciles the human" pitch made literal. Icon-first exception flags (denomination shortfall, digit transposition, etc.) over dense text tables. Also feeds [[Product & Positioning#Locked pitch line]] and Theme 3 reference notes below.

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

> The minimal-clicks / icon-first panelist guidance above applies directly even though we're not building in this theme — it's general UX doctrine for the whole hackathon, not theme-specific.

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
- **Critical flag:** "Banks don't allow cloud service providers and AI models due to security risks." Consistent with the existing on-prem, no-public-cloud call in [[Technical Architecture#Deployment model]] — but in tension with any cloud-hosted LLM call. **Update (Jul 7):** explanation layer switched Gemini → Groq API serving Llama 3.3 70B (Gemini free-tier limits hit too fast). This strengthens the fallback story: Llama 3.3 is open-weight, so production can self-host the exact same model on-prem — Groq is demo-only inference. Still need to make that story explicit in the pitch.

## Session 3 — Design Thinking & Problem-Solution Fit (Jul 8)

**Speaker:** Nidal Sheikh

### Opening frame
> "What if you build something perfectly, but nobody cares?"

Direct hit on the ZeroBalance PSF risk — the whole session was a PSF stress test wrapped in a design thinking session. Cuts against the founder reflex of building solutions before confirming the pain is real.

### Core points
| Point | Note |
|---|---|
| "You have to be delusional to achieve what you want" | Bootcamp bravado — flag, not doctrine. Delusion is what killed the case study below. Conviction + validation is the operating principle; do not quote the delusion line at judges. |
| Build the MVP/prototype the moment you get an idea | Understanding and gaps only surface once you're deep in the build. Aligns with the ugly-and-working-by-hour-24 rule from [[#Session 2 — Hacking a Hackathon! (Jul 7)]]. |
| Never stop brainstorming | Keep the idea funnel open even mid-build. |
| Modular schema — plug features in like USB | Build so any new feature drops in cleanly. Already the ZeroBalance stance — see the phased Phase 1 / Phase 2 / Phase 3 split in [[Technical Architecture#Scope (phased)]]. |
| Be fast enough to validate on the spot | Test the solution as you build, not after. |

### Case studies
| Case                                                                                                                                   | Lesson                                                                                                                                                                                                                         |
| -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| IDEO — multiple products                                                                                                               | Design thinking scales into real product impact. Reference dropped, no detail given.                                                                                                                                           |
| GASGADE (name unconfirmed — rough phonetic capture) — AI visual/media tool built by Pakistani editors working in Hollywood VFX/editing | Technically dominant, no market competition — failed because even expert editors got lost in the UI. Design thinking = build for the end user, not the business. If the end user is productive, the business grows on its own. |

> Direct application to ZeroBalance: GASGADE is the mirror. Dense stack (matching engine + Isolation Forest + RAG + Urdu explanation via Groq/Llama + React dashboard) with a tired teller at EOD as the end user. If the exception worklist takes longer than the current paper/Excel sheet, adoption dies — bank buys, teller ignores, renewal fails. The one UX metric that matters: teller time-to-close-EOD on ZeroBalance vs. current paper flow. Feeds the scope-cutting sessions logged in [[Technical Architecture]] (Jul 10 & 15).

### Key takeaways
1. "Nobody cares" is the default outcome unless the pain is real and precise — precision beats polish.
2. Build for the end user; the business follows. Do not invert this because the bank is the buyer.
3. Modular = optionality. Design for feature swap-in from day one.
4. Validate on the spot; don't stack unvalidated features on top of each other.
5. Delusion is a bootcamp line, not a build strategy.

### Flags from Day 3
- **Case study name unconfirmed** — "GASGADE" is a rough phonetic capture. Confirm the correct spelling / product name with Nidal or a co-attendee before it goes near a pitch, one-pager, or investor doc.
- **n=1 domain source risk** — Session 4 (Lean Canvas / DVF Fit, Jul 9) will likely ask how many users we've spoken to. Khursheed alone is not PSF evidence.

## Action Items

- [ ] Read SBP-published national AI/fintech policy circulars — feeds [[Product & Positioning#Regulatory anchors]] and Theme 1's "compliance considerations" output.
- [ ] Reconcile the minimum submission package above against [[Hackathon Logistics#Final deliverables (due August)]] — currently under-logged there.
- [ ] Decide: build strictly within Theme 1's official (customer-facing) examples, or defend the back-office/teller angle as deliberate novelty. Needed before the Jul 17 theme-lock deadline.
- [ ] Confirm with a mentor whether dual-theme submission must satisfy both themes' expected-outputs lists.
- [ ] Get the correct "Product vs. X" split — "60% Product and 40% Product" as noted doesn't parse.
- [ ] Bake the "open-weight Llama 3.3 self-hosts on-prem; Groq is demo-only" line into the pitch — answers the "no cloud AI models" objection.
- [ ] Reconcile the two conflicting 72-hour timelines (primer deck vs. Sarfaraz's Define/Build/Extend/Harden/Pitch).
- [ ] Share IMG_9061.JPG for the rest of Day 2 detail.
- [ ] Map the new team (once formed) to Sarfaraz's 4 roles (Builder/Validator/Storyteller/Integrator).
- [x] Add new team members to [[Team & Roles]] — done Jul 7: Wahaj (frontend) + Miswan (data/ML); ownership re-split and locked.
- [ ] Apply minimal-click / icon-first UX guidance when the React dashboard wireframes start (Session 7, Jul 14 UI/UX Fundamentals).
- [ ] Define one UX metric before Session 6 (Rapid Prototyping, Jul 13): teller time-to-close-EOD on ZeroBalance vs. current paper/Excel flow. If not faster, we're building GASGADE.
- [ ] Kill or defer the Isolation Forest fraud layer for the 72-hour MVP if it doesn't reduce teller time-to-close. Impressive to judges, invisible to the end user — same GASGADE trap.
- [ ] Push Khursheed for 2–3 more teller shadows this week — n=1 is not PSF evidence and Session 4 (Jul 9) will surface it.
- [ ] Draft a 20-min EOD shadow protocol for Khursheed — observe, don't ask.
- [ ] Confirm the correct name of the "GASGADE" case study before it goes anywhere external.

## Related
- [[Hackathon Logistics]] — Stage 2 context, NDA, final deliverables
- [[Team & Roles]] — team this bootcamp trains
- [[Technical Architecture]] — where scope-cutting sessions (Jul 10, 15) should land
- [[Product & Positioning]] — theme-fit risk and regulatory anchors surfaced in Session 1
