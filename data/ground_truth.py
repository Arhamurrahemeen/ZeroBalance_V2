"""ZeroBalance test oracle.

Engine correctness is measured against this suite — never against hand-picked
examples. Gate: >=90% on single-error cases, >=70% on two-error cases.

An engine is a callable Case -> ranked predictions (top 3-5). A truth error
counts as matched when a prediction in the top `TOP_K` has the same signature
and (for txn-level errors) overlaps the culprit refs. A case is correct only
if every injected error is matched.

Run `python ground_truth.py` for the self-check (determinism, variance math,
signature coverage). Exits non-zero on failure.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field

from generator import SIGNATURES, Case, make_case

TOP_K = 5
SINGLES_PER_SIGNATURE = 20
DOUBLE_CASES = 40
SUITE_SEED = 2026


@dataclass(frozen=True)
class Prediction:
    signature: str
    refs: tuple[str, ...] = ()   # culprit txn ref(s); empty for denomination-level


EngineFn = Callable[[Case], Sequence[Prediction]]


@dataclass
class Suite:
    singles: list[Case]
    doubles: list[Case]


@dataclass
class Report:
    single_accuracy: float
    double_accuracy: float
    per_signature: dict[str, float]
    failures: list[str] = field(default_factory=list)


def build_suite(seed: int = SUITE_SEED) -> Suite:
    from random import Random

    rng = Random(seed)
    singles = [
        make_case(f"single_{sig}_{n:02d}", [sig], seed=rng.randrange(10**9))
        for sig in SIGNATURES
        for n in range(SINGLES_PER_SIGNATURE)
    ]
    doubles = []
    for n in range(DOUBLE_CASES):
        pair = rng.sample(SIGNATURES, 2)
        doubles.append(make_case(f"double_{n:02d}", pair, seed=rng.randrange(10**9)))
    return Suite(singles=singles, doubles=doubles)


def _case_correct(case: Case, preds: Sequence[Prediction]) -> bool:
    top = list(preds)[:TOP_K]
    for err in case.errors:
        hit = any(
            p.signature == err.signature
            and (not err.refs or set(p.refs) & set(err.refs))
            for p in top
        )
        if not hit:
            return False
    return True


def evaluate(engine: EngineFn, suite: Suite | None = None) -> Report:
    suite = suite or build_suite()
    failures: list[str] = []
    sig_total: dict[str, int] = dict.fromkeys(SIGNATURES, 0)
    sig_hit: dict[str, int] = dict.fromkeys(SIGNATURES, 0)

    single_hits = 0
    for case in suite.singles:
        sig = case.errors[0].signature
        sig_total[sig] += 1
        if _case_correct(case, engine(case)):
            single_hits += 1
            sig_hit[sig] += 1
        else:
            failures.append(case.case_id)

    double_hits = 0
    for case in suite.doubles:
        if _case_correct(case, engine(case)):
            double_hits += 1
        else:
            failures.append(case.case_id)

    return Report(
        single_accuracy=single_hits / len(suite.singles),
        double_accuracy=double_hits / len(suite.doubles),
        per_signature={s: sig_hit[s] / sig_total[s] for s in SIGNATURES},
        failures=failures,
    )


def passes_gate(report: Report) -> bool:
    return report.single_accuracy >= 0.90 and report.double_accuracy >= 0.70


# --- self-check --------------------------------------------------------------


def _check_case(case: Case) -> list[str]:
    problems: list[str] = []
    if case.variance != case.counted_cash - case.system_cash:
        problems.append("variance != counted - system")
    if sum(d * n for d, n in case.denomination_count.items()) != case.counted_cash:
        problems.append("denomination breakdown does not sum to counted_cash")
    if any(n < 0 for n in case.denomination_count.values()):
        problems.append("negative note count")
    if sum(e.cash_delta for e in case.errors) != case.variance:
        problems.append("sum of error cash_deltas != variance")
    posted_refs = [t.ref for t in case.posted]
    if len(posted_refs) != len(set(posted_refs)):
        problems.append("duplicate refs in posted")
    for e in case.errors:
        if e.signature != "denomination_shortfall" and not e.refs:
            problems.append(f"{e.signature}: no culprit refs")
    return problems


def self_check() -> bool:
    suite = build_suite()
    ok = True

    dump = json.dumps([asdict(c) for c in suite.singles + suite.doubles], default=str)
    redump = json.dumps(
        [asdict(c) for c in (lambda s: s.singles + s.doubles)(build_suite())], default=str
    )
    if dump != redump:
        print("FAIL determinism: two builds with the same seed differ")
        ok = False
    else:
        print(f"determinism OK (suite rebuild is byte-identical, {len(dump):,} bytes)")

    bad = 0
    for case in suite.singles + suite.doubles:
        problems = _check_case(case)
        if problems:
            bad += 1
            print(f"FAIL {case.case_id}: {'; '.join(problems)}")
    if bad:
        ok = False
    else:
        print(f"variance math OK for all {len(suite.singles) + len(suite.doubles)} cases")

    per_sig = {s: sum(1 for c in suite.singles if c.errors[0].signature == s)
               for s in SIGNATURES}
    print(f"coverage: {per_sig}")
    if any(n < SINGLES_PER_SIGNATURE for n in per_sig.values()):
        print("FAIL coverage: a signature has too few single cases")
        ok = False

    print(f"suite: {len(suite.singles)} singles + {len(suite.doubles)} doubles")
    print("SELF-CHECK PASSED" if ok else "SELF-CHECK FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if self_check() else 1)
