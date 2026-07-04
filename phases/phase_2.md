# Phase 2 — Synthetic Data + Ground-Truth Oracle

## Goal
`/data/generator.py` (synthetic PIBAS-format teller sessions with injected variance errors) + `/data/ground_truth.py` (test oracle: labeled case suite + engine scoring). Covers all 6 variance signatures. This is the gate before any matching-engine work.

## Project structure
```
/data
  generator.py       # Txn/Case models, clean-session builder, 6 error injectors, CSV writer, CLI
  ground_truth.py    # case suite (singles + doubles), evaluate(engine), gate check, self-check CLI
  sample/            # demo CSV output (gitignored)
/docs
  pibas_csv_format.md   # CSV column spec
```

## Steps
1. generator.py — clean session (30–70 cash txns, opening float, legit reversal pairs), posted-vs-actual model, one injector per signature:
   - digit_transposition: posted amount has two adjacent digits swapped (variance divisible by 9)
   - duplicate_posting: same txn posted twice (variance = ±amount)
   - missed_reversal: cash returned physically, reversal never posted (variance = ±amount)
   - denomination_shortfall: k notes of one denomination missing from count (variance = -k×denom)
   - cash_inout_miskey: cash_in keyed as cash_out or vice versa (variance = ±2×amount)
   - wrong_adjacent_account: posted to near-miss account number (no cash variance)
2. Denomination breakdown of counted cash (one count per session — the only teller input).
3. ground_truth.py — deterministic suite: 120 single-error (20/signature) + 40 two-error cases; evaluate() scores an engine (correct = every injected error matched in top-5 by signature + txn ref); gate = ≥90% single / ≥70% double.
4. Self-check mode: determinism, variance math consistency, signature coverage.
5. docs/pibas_csv_format.md.

## Commands
```
python data/ground_truth.py                  # oracle self-check
python data/generator.py --out data/sample   # write demo CSVs (one case per signature)
```
(if no host Python: docker run --rm -v "D:\ZeroBalance\data:/data" zerobalance-backend python /data/ground_truth.py)

## What to expect
- Self-check prints: suite = 120 singles + 40 doubles, all 6 signatures ≥20 cases, determinism OK, variance math OK for every case → `SELF-CHECK PASSED`, exit 0.
- Generator CLI writes 6 files ×3 (CSV + meta JSON + truth JSON) into data/sample/.
- Every case: variance == counted_cash − system_cash, denomination breakdown sums to counted_cash.

## Achieved
- data/generator.py: posted-vs-actual session model (stdlib-only dataclasses so the oracle runs without a venv), clean sessions with legit reversal pairs, all 6 injectors, denomination breakdown with reserved note counts (shortfall always subtractable), PIBAS CSV + meta/truth JSON writer, CLI.
- data/ground_truth.py: deterministic suite (120 singles = 20/signature + 40 doubles, seed 2026), evaluate(engine) with top-5 signature+ref matching, passes_gate() (≥90%/≥70%), self-check CLI.
- Self-check PASSED on host Python 3.13: byte-identical rebuild (determinism), variance math consistent for all 160 cases, full signature coverage.
- evaluate() harness verified: null engine → 0%, truth-reading engine → 100%.
- Demo CSVs written to data/sample/ (gitignored); variances match signature math (transposition −63 divisible by 9, miskey +13,400 = 2×6,700).
- docs/pibas_csv_format.md: column spec + signature cheat-sheet.

Gate passed: all 6 signatures covered by the oracle → matching-engine work (Phase 3) unblocked.
