---
project: ZeroBalance
type: interview
status: live
tags:
  - project/zerobalance
  - type/interview
  - status/live
---
# Teller Workflow — Khursheed Interview #2

**Source:** Khursheed Alam (Universal Teller, Bank Al Habib Mirpurkhas)
**Date logged:** 2026-07-09
**Purpose:** Ground-truth teller day, actual fault modes, root causes. Feeds gap analysis for ZeroBalance MVP scope.

---

## 1. Day-in-the-Life (chronological)

| # | Step | Actor | System touched |
|---|---|---|---|
| 1 | Arrive, report to OM (Operations Manager) | Teller | — |
| 2 | OM issues cash from vault to teller (e.g. PKR 1.9M) — **bulk amount only, no denomination breakdown** | OM → Teller | Manual handover |
| 3 | Teller updates portal with opening float | Teller | CBS (see §2) |
| 4 | Customer transactions all day — deposits, withdrawals | Teller ↔ Customer | CBS |
| 5 | Cheque deposits: teller writes **denomination on back of cheque**, hands cash to customer, cheque goes to drawer. **No portal entry.** | Teller | Paper only |
| 6 | EOD ATM reconciliation: count ATM cash physically, update ATM report on portal | Teller | CBS ATM module |
| 7 | EOD cash + cheque reconciliation via portal software: if `dashboard total == physical cash`, submit report + cash to OM | Teller | CBS |
| 8 | OM validates report → cash back to vault | OM | Vault |

---

## 2. Core Banking Systems Used

| Bank | CBS |
|---|---|
| Allied (Khursheed's prior) | **AHBS** |
| UBL | **Symbols** *(likely "Symbols"/Misys — verify spelling)* |
| "Most other banks" | **T24** (Temenos) |

**Portal input fields (all three):** Account Number, CNIC, Cash Amount.
**Not captured:** denomination breakdown, per-transaction time metadata beyond timestamp, cheque backing detail.
**Not present:** on-dashboard calculator.

---

## 3. Fault Modes Observed

### 3.1 Cash variance (excess / short)
- **Frequency:** rare
- **Trigger condition:** large-amount transactions (e.g. PKR 36.5 lac)
- **Root cause:** manual counting miscalculation on high-volume denomination stacks

### 3.2 ATM excess cash
- **Trigger:** customer card stuck in ATM. ATM software logs the withdrawal, physical cash never dispensed.
- **Result:** physical ATM cash > system-expected balance
- **Root cause:** ATM hardware/software desync — not teller error

### 3.3 Excess cash → paper Excess Ledger (**corruption hotspot**)
- Excess cash gets written into a **paper ledger**
- **Fraud vector:** teller pockets excess, never records it. No digital trail, no reconciliation against transaction anomalies.
- Khursheed flagged this as a known integrity problem

---

## 4. Root-Cause Breakdown

| Fault | Human | System | Hardware |
|---|---|---|---|
| Large-amount miscount | ✅ | | |
| ATM excess (stuck card) | | ✅ | ✅ |
| Excess ledger corruption | ✅ (intentional) | ✅ (paper trail gap) | |

---

## 5. Key Signals for ZeroBalance

1. **Denomination data is lost at vault-out.** OM hands bulk cash; teller never records denomination breakdown of opening float. Any denomination-level variance detection has to be inferred from close-of-day counts, not deltas from opening.
2. **Cheque transactions bypass the portal entirely.** A cash-back-on-cheque leaves no CBS entry. Reconciliation must reconcile drawer cheques against physical cash out.
3. **No calculator on dashboard** — tellers do arithmetic on paper or mental math on large amounts. Direct MVP win.
4. **Paper Excess Ledger is the single biggest integrity gap.** Digitizing this alone is a fraud-reduction story worth pitching.
5. **Frequency is low but severity is high.** Errors are rare but occur specifically on high-value transactions — exactly where audit exposure is worst.
6. **Symbols (UBL CBS) — verify exact name.** Khursheed said "Symbois" — likely Misys Symbols or a UBL-internal name. Get this right before the pitch.

---

## 6. Open Questions to Ask Khursheed Next

- When cash goes into the paper Excess Ledger, is it later reconciled against CBS at month-end or audit? Or does it just sit?
- Cheque-cash transactions: is there any log (register, drawer count, dual sign-off) or is it purely trust?
- ATM excess resolution — how is the "stuck card" refund flow handled? Does the teller manually reverse?
- Opening float — does OM at any point record denomination, or is it truly bulk-only across the chain?
- End-of-day: is the physical cash count done alone or dual-witnessed?


---

## 7. Addendum — CBS has no input validation

**Khursheed:** AHBS (Allied's CBS) performs **zero validation**. Teller can mistype the amount (extra digit, transposition, wrong decimal) and the system posts it anyway. No cross-check, no denomination sanity, no soft warning.

**Arham's hypothesis:** the missing validation is because there's no denomination field on the dashboard — so the system has nothing to cross-check against.

**Analysis:**
- Half true. Denomination cross-check would catch a class of typos (typed amount ≠ sum of denominations entered).
- But the deeper cause is CBS-architectural: legacy core banking systems (AHBS, T24, Symbols) are **posting engines, not validation engines**. They accept whatever the front-end sends. Validation is expected to live in the client/portal layer, and in most banks it doesn't exist.
- This is exactly the gap ZeroBalance fills — a validation and reconciliation layer that sits *between* teller and CBS.

**Fault modes this unlocks:**
- Extra-digit posting (100 typed as 1000) — undetected until EOD variance
- Wrong account number typed with valid amount — posted to wrong customer, no flag
- Duplicate submission (teller clicks twice) — CBS posts twice
- Amount/denomination mismatch — physically impossible transactions posted successfully
