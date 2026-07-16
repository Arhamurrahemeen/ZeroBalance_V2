# ZeroBalance v2.1 — Adversarial Panel Evaluation

**Reviewer role:** UBL Hackathon panelist (20+ yrs fintech + bank operations), Devil's Judgment hat
**Date:** 2026-07-16
**Method:** Hostile inputs fired at the live engine and ledgers; one row forged directly in the running Postgres to test tamper-evidence claims.
**Environment:** `docker compose` stack up (backend + db + frontend), engine exercised in-container, DB tampered as superuser then cleaned.

> Every finding below is **reproduced**, not theorized. Commands and outputs are included so each can be re-run.

> **Update 2026-07-16:** Findings #1 and #2 (both 🔴 Critical) are **FIXED and verified** — see the resolution notes under each. Full suite: 99 passed (95 original + 4 new regression tests). #3–#6 remain open.

---

## Verdict

Solid engineering with genuinely above-average discipline (deterministic engine, append-only ledgers, honest CLAUDE.md). The audit spine originally had two holes that let a teller commit the exact fraud ZeroBalance sells protection against — and walk away with a green, "tamper-evident" chain as a receipt. **Both have since been closed** (Findings #1 and #2, resolved 2026-07-16).

Tagline under test: *"CBS posts what the teller types. ZeroBalance makes sure the teller typed the truth."*
Findings #1 and #2 broke that tagline on its own terms; the tagline now holds against both attacks.

---

## Findings — ranked by severity

| # | Severity | Title | Reproduced? | Status |
|---|----------|-------|-------------|--------|
| 1 | 🔴 Critical | Cash Movement Ledger has no segregation of duties (one person signs all 3 roles) | Yes | ✅ **Fixed 2026-07-16** |
| 2 | 🔴 Critical | Hash chain omits sign-off identities — forged approver passes verify-chain | Yes (live DB) | ✅ **Fixed 2026-07-16** |
| 3 | 🟠 High | "Nothing explains variance" fallback emits confident, wrong-signed suspects | Yes | Open |
| 4 | 🟠 Medium | `wrong_adjacent_account` false-fires on sequential account numbers | Yes | Open |
| 5 | 🟡 Medium | Demo CNIC/name check passes two different people | Yes | Open |
| 6 | 🟡 Design | Two independent "physical count" numbers are never reconciled | By inspection | Open |

---

### 🔴 CRITICAL 1 — Cash Movement Ledger has no segregation of duties  ✅ FIXED (2026-07-16)

**What's wrong.** The flagship Excess Ledger enforces `countersigner ≠ opener` ([excess_ledger.py:169](backend/app/excess_ledger.py#L169)). The **audit-trail spine** — described in CLAUDE.md as "dual-signed, triple-signed for handover" — does **not**. [`_validate_signoffs`](backend/app/cash_movement.py#L71) only checks that sign-off fields are *present*, never that they are *different people*.

**Reproduction.**
```python
from app.cash_movement import _validate_signoffs
_validate_signoffs("handover", counterparty_id="T2",
    signoff_teller="alice", signoff_counterparty="alice", signoff_om="alice")
# -> ACCEPTED
_validate_signoffs("day_start", counterparty_id=None,
    signoff_teller="alice", signoff_counterparty=None, signoff_om="alice")
# -> ACCEPTED (teller == om)
```
```
HANDOVER self-signed by alice x3:        ACCEPTED
DAY_START teller==om (alice==alice):     ACCEPTED
HANDOVER teller_id == counterparty_id:   ACCEPTED (self-handover)
```

**Why it matters.** A teller short PKR 200,000 at noon posts a `reissue` ("the vault gave me more cash"), signs as teller **and** as OM, and the shortfall disappears into a fully-signed, hash-chained record. This is the precise fraud dual control exists to prevent. It is worse than having no sign-off, because it is laundered through an "audit" ledger that looks authoritative.

**Fix.** In `_validate_signoffs`, reject when the signer identities collide:
- `day_start` / `reissue` / `day_end`: `signoff_teller != signoff_om`.
- `handover`: all three of `signoff_teller`, `signoff_counterparty`, `signoff_om` distinct, and `teller_id != counterparty_id`.

**✅ Resolution (2026-07-16).** Implemented in [cash_movement.py](backend/app/cash_movement.py): new `DuplicateSignerError(SignoffError)` and distinct-signer enforcement added to `_validate_signoffs` (which now also receives `teller_id`). A teller signing as their own OM, a handover with any duplicate signer, and a self-handover (`teller_id == counterparty_id`) all now return 422. Re-attack after fix:
```
handover self-signed x3              REJECTED: signoff_teller and signoff_om must be different people ...
day_start teller==om                 REJECTED: signoff_teller and signoff_om must be different people ...
handover teller_id==counterparty_id  REJECTED: handover teller_id and counterparty_id must differ ...
```
Locked by regression tests `test_teller_cannot_sign_as_own_om`, `test_handover_requires_three_distinct_signers`, `test_teller_cannot_hand_over_to_themselves`.

---

### 🔴 CRITICAL 2 — Hash chain does not protect *who signed*; a forged approver passes verify-chain  ✅ FIXED (2026-07-16)

**What's wrong.** [`_canonical_payload`](backend/app/cash_movement.py#L95-L105) hashes `event_type, teller_id, counterparty_id, om_id, session_id, total_amount, denominations`. It **omits** `signoff_teller`, `signoff_counterparty`, and `signoff_om`. So the sign-off identities are outside the tamper-evident chain. The append-only trigger is the *only* guard on those fields.

**Reproduction (against live Postgres).**
```
verify BEFORE tamper:                               True, rows 1
# disable trigger, UPDATE signoff_om 'bob' -> 'FORGED_APPROVER', re-enable trigger
verify AFTER forging signoff_om -> FORGED_APPROVER: True, rows 1
```
The verifier reported the chain **intact** after the approver was rewritten. *(The forged row was deleted afterward; `cash_movement_ledger` is back to 0 rows.)*

**Why it matters.** For an audit tool, "we can prove the amount wasn't tampered but not who approved it" is indefensible. It is also inconsistent with your own flagship: the Excess Ledger hashes the `actor` (signer) in its payload ([excess_ledger.py:70-81](backend/app/excess_ledger.py#L70-L81)), so tampering the signer there breaks the chain.

**Fix.** Add `signoff_teller`, `signoff_counterparty`, `signoff_om` (and consider `event_time`, `id`) into `_canonical_payload`, and include them when recomputing hashes in `verify_chain`. Add a regression test that forges a signoff and asserts `verify_chain` returns `False`.

**✅ Resolution (2026-07-16).** `_canonical_payload` in [cash_movement.py](backend/app/cash_movement.py) now includes all three `signoff_*` fields, so they are part of the row hash and are re-checked by `verify_chain`. Re-ran the exact live-DB forge (`signoff_om` `bob → FORGED_APPROVER`, trigger disabled to bypass append-only):
```
verify BEFORE:                 True
verify AFTER forging approver: False   <-- chain now catches the forgery
```
Locked by regression test `test_forged_signoff_breaks_chain`.
**Migration note:** because sign-off identities are now hashed, any cash-movement rows written *before* this change will fail `verify-chain`. The ledger was empty at fix time (0 rows), so there is no migration; do not pre-seed pre-fix rows and expect the chain to verify — seed fresh through the API.

---

### 🟠 HIGH 3 — Fallback emits a confident, wrong-signed suspect when no rule explains the variance

**What's wrong.** When no candidate (or pair) sums to the variance, the [fallback branch](backend/app/engine/matching.py#L204) (`if not ranked: for c in cands[:3]: push(c)`) surfaces the top-priority candidates **regardless of whether their delta relates to the variance** — including wrong sign and wrong magnitude.

**Reproduction.** A `cash_out` reversed by a `reversal` leaves a genuine **+100 excess**:
```
variance = +100  ->  r1 denomination_shortfall  delta = -5000
```
The engine tells the teller "you're short one 5000 note" when they are actually 100 **over**.

**Why it matters.** The engine's stated invariant is "every ranking reproducible and rule-explainable," and singles are meant to satisfy `delta == variance`. Emitting a suspect whose `delta ≠ variance` (and opposite sign) breaks that contract and misleads the user with false confidence. There is no "no rule explains this variance" state.

**Fix.** When the fallback fires, either return an explicit `unexplained` status (empty suspects + a flag) or clearly mark fallback candidates as non-reconciling (e.g. `explains_variance: false`) so the UI never presents them as equal-confidence culprits.

---

### 🟠 MEDIUM 4 — `wrong_adjacent_account` false-fires on sequential account numbers

**What's wrong.** The rule flags any single-occurrence account that is 1 edit away from another account, with cash delta 0. Because the delta is zero either way, it cannot distinguish a mis-post from two legitimate customers with adjacent account numbers.

**Reproduction.** Balanced, 100%-correct till, two different customers:
```
account 1234 (+1000), account 1235 (+2000), variance = 0
  r1 wrong_adjacent_account refs=('T1',) intended=1235
  r2 wrong_adjacent_account refs=('T2',) intended=1234
```

**Why it matters.** Accounts are issued sequentially, so adjacent account numbers are the **norm**, not an anomaly. This rule will fire constantly on clean sessions — an alert-fatigue generator, and alert fatigue is the #1 killer of teller-workstation overlays. Per your own anti-delusion guardrail #1 (n=1), the real-world false-positive rate is unmeasured.

**Fix.** Gate `wrong_adjacent_account` behind corroborating evidence (e.g. only when the account appears nowhere else in the branch's known account set, or when paired with a matching variance), or demote it to a display-only hint rather than a ranked suspect.

---

### 🟡 MEDIUM 5 — Demo CNIC/name check passes two different people

**What's wrong.** [`check_cnic_name_match`](backend/app/prepost.py#L62) uses `fuzz.token_set_ratio >= 80`, which scores high on shared tokens.

**Reproduction.**
```
holder=MUHAMMAD ALI    typed=MUHAMMAD HUSSAIN  score=80.0  -> PASS
holder=FATIMA BIBI     typed=FATIMA            score=100   -> PASS
holder=MUHAMMAD ARHAM  typed=ARHAM MUHAMMAD    score=100   -> PASS
holder=AYESHA SIDDIQUI typed=AYESHA KHAN       score=70.6  -> fail
```

**Why it matters.** In a country where "Muhammad" prefixes a large share of male names, `token_set_ratio ≥ 80` greenlights paying the wrong customer. CLAUDE.md correctly brands this demo/roadmap — but if a judge types `MUHAMMAD ALI` → `MUHAMMAD HUSSAIN` on the Pre-post screen and it flashes green, you have handed them the loophole live.

**Fix.** For the demo, raise the threshold and/or switch to `fuzz.ratio` / `WRatio`, or don't let judges type into that field. Keep it explicitly labeled demo-only.

---

### 🟡 DESIGN 6 — Two independent "physical count" numbers, never reconciled

**What's wrong.** EOD `counted_cash` is derived from `meta.denomination_count` at ingest ([service.py:83](backend/app/service.py#L83)) — good, the total can't disagree with the breakdown *there*. But the `day_end` cash-movement event carries its **own separate** denomination count, entered in a different screen, and [reconcile.py](backend/app/reconcile.py) only compares `day_start + reissue` vs `day_end` *within* the movement ledger. The EOD-ingest physical count and the `day_end`-event physical count are never tied together.

**Why it matters.** The "two audit cadences from one artifact set" pitch has a seam: a teller can declare one physical count to the recon engine and a different one to the spine, and nothing notices.

**Fix.** Cross-check the `day_end` event denomination total against the EOD session `counted_cash` for the same teller/date, and flag divergence.

---

## What actually held up (tried to break, couldn't)

- **`counted_cash` derived from the denomination breakdown** ([service.py:83](backend/app/service.py#L83)) ⇒ no total-vs-breakdown lie in the EOD path.
- **Reversal referencing an unknown txn raises**, not silently zeroes ([matching.py:45](backend/app/engine/matching.py#L45)).
- **Digit-transposition ranking is correct** (`120→210 = +90`, `190→910 = +720`); the multiple-of-10 "cash-like" guard is a thoughtful touch.
- **Excess Ledger controls enforced in code**: dual sign-off, close-requires-countersign, no double countersign, amount frozen at open — all unit-testable without Postgres.
- **Clean balanced till ⇒ zero suspects.** No noise on the happy path (except finding #4).
- **Append-only triggers present** on all three ledgers (`audit_ledger`, `cash_movement_ledger`, `excess_ledger`).

---

## Edge / tricky questions for the panel (rehearse these)

1. Show me you can't approve your own vault reissue. *(Currently you can — Finding #1.)*
2. If I get one night with your database, can I change who approved a cash movement without your chain noticing? *(Yes — Finding #2.)*
3. Your engine ranked a shortfall on a till that was over. Walk me through why I should trust rank 1. *(Finding #3.)*
4. Two of my customers have accounts 4401 and 4402. Why is your system accusing my teller of fraud every day? *(Finding #4.)*
5. You say "append-only." Enforced by what — a trigger a DBA disables in one line, or cryptography? *(Currently the trigger, and it doesn't cover sign-offs.)*
6. Who signs the teller-typed `opening_float`? What stops a teller typing an opening float that erases their shortfall? *(No sign-off or cross-check seen on `opening_float`.)*
7. "Half-yearly closing is the same artifacts, different date window." Prove the queries take a range and nothing hard-codes today. *(Register does take from/to — be ready to run a 6-month window live.)*
8. Isolation Forest is "display-only." Prove it cannot move a rank. What happens when it disagrees with the rules?
9. Groq writes the Urdu explanation. What does the teller do when Groq is down, or hallucinates a wrong account number into Urdu text a judge can't read?
10. n=1 (Khursheed). Why should a bank buy a fraud-control tool validated by one teller? *(Your own guardrail — own it first.)*

---

## Bottom line

Determinism, append-only discipline, and the honesty in CLAUDE.md (refusing to fabricate `deposits_in`/`withdrawals_out`) are above hackathon average. Findings #1 and #2 originally let a teller commit the fraud the product sells protection against and receive a green "verified" chain as proof — the line between an audit tool and audit theater. **Both are now fixed and regression-tested**, so the two questions a bank-ops judge reaches for first ("can a teller approve their own movement?" / "is your append-only real?") both have a live, demonstrable answer.

**Fix status before pitch:**
1. ✅ **Done** — distinct-signer validation in `_validate_signoffs` (Finding #1).
2. ✅ **Done** — sign-off identities added to `_canonical_payload` + `verify_chain`, with a forged-approver regression test (Finding #2).
3. ⬜ Open — mark or suppress non-reconciling fallback suspects (Finding #3).

**Verification of the fixes:** full backend suite `docker compose exec backend pytest -q` → **99 passed** (95 original + 4 new). Both original attacks re-run post-fix and now rejected/caught; dev DB left clean (`cash_movement_ledger` = 0 rows).
