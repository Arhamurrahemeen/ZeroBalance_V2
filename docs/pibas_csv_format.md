# PIBAS CSV export format (synthetic)

One CSV per teller per business day — the CBS export the engine ingests.

| Column | Example | Notes |
|---|---|---|
| BRANCH_CODE | 0111 | 4-digit |
| TELLER_ID | T08 | |
| TXN_DATE | 2026-07-01 | ISO date |
| TXN_TIME | 09:04:00 | HH:MM:SS, ascending |
| TXN_REF | TXN0001 | unique per session |
| ACCOUNT_NO | 301029743649 | 12-digit |
| TXN_TYPE | CASH_IN / CASH_OUT / REVERSAL | maps to schema enum lowercase |
| AMOUNT | 7100 | whole PKR, always positive |
| NARRATION | REV:TXN0012 | reversals carry `REV:<original ref>` |

Alongside each CSV, `<case>_meta.json` holds the teller inputs: `opening_float`,
`counted_cash`, and `denomination_count` (the single EOD count — denom → note count).
`<case>_truth.json` is oracle-only; the engine must never read it.

Cash effect: CASH_IN adds to the till, CASH_OUT removes, REVERSAL applies the
opposite effect of the original txn it references.

Variance signatures (variance = counted − system):
- digit_transposition: divisible by 9 (adjacent-digit swap in a posted amount)
- duplicate_posting / missed_reversal: |variance| equals one txn amount
- denomination_shortfall: −k × one denomination, visible in the count
- cash_inout_miskey: |variance| = 2 × one txn amount
- wrong_adjacent_account: no cash variance; near-miss account number
