"""Synthetic PIBAS-format teller-session generator with injected variance errors.

Model: a Case holds two transaction lists —
  actual: what physically happened at the counter (drives counted cash)
  posted: what CBS shows (the CSV export the engine sees)
A clean case has identical lists; each injector perturbs one side to create
one of the 6 variance signatures. Engines may only read: posted, opening_float,
system_cash, counted_cash, denomination_count, variance. Never `actual`/`errors`.

Stdlib-only on purpose: the oracle must run anywhere without a venv.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path
from random import Random

SIGNATURES: tuple[str, ...] = (
    "digit_transposition",
    "duplicate_posting",
    "missed_reversal",
    "denomination_shortfall",
    "cash_inout_miskey",
    "wrong_adjacent_account",
)

DENOMS: tuple[int, ...] = (5000, 1000, 500, 100, 50, 20, 10, 5, 2, 1)

CSV_COLUMNS = [
    "BRANCH_CODE", "TELLER_ID", "TXN_DATE", "TXN_TIME",
    "TXN_REF", "ACCOUNT_NO", "TXN_TYPE", "AMOUNT", "NARRATION",
]


@dataclass(frozen=True)
class Txn:
    ref: str
    account: str
    txn_type: str  # cash_in | cash_out | reversal
    amount: int    # whole PKR
    time: str      # HH:MM:SS
    narration: str = ""
    reverses: str | None = None  # ref of reversed txn (reversal rows only)


@dataclass
class TruthError:
    signature: str
    refs: list[str]              # culprit txn ref(s); empty for denomination_shortfall
    detail: dict[str, int | str] = field(default_factory=dict)
    cash_delta: int = 0          # this error's contribution to variance


@dataclass
class Case:
    case_id: str
    branch: str
    teller: str
    business_date: str
    opening_float: int
    posted: list[Txn]
    actual: list[Txn]                 # truth side — engines must not read
    system_cash: int = 0
    counted_cash: int = 0
    denomination_count: dict[int, int] = field(default_factory=dict)
    variance: int = 0
    errors: list[TruthError] = field(default_factory=list)


def _cash_effect(txns: list[Txn]) -> int:
    by_ref = {t.ref: t for t in txns}
    total = 0
    for t in txns:
        if t.txn_type == "cash_in":
            total += t.amount
        elif t.txn_type == "cash_out":
            total -= t.amount
        else:  # reversal: opposite effect of the original
            orig = by_ref.get(t.reverses or "")
            if orig is None:
                raise ValueError(f"reversal {t.ref} has no original in list")
            total += orig.amount if orig.txn_type == "cash_out" else -orig.amount
    return total


def _amount(rng: Random) -> int:
    band = rng.random()
    if band < 0.6:
        return rng.randrange(500, 20_000, 10)
    if band < 0.9:
        return rng.randrange(20_000, 100_000, 100)
    return rng.randrange(100_000, 500_000, 500)


def _account(rng: Random) -> str:
    return f"{rng.randrange(10**11, 10**12)}"  # 12-digit


def _breakdown(total: int, rng: Random) -> dict[int, int]:
    # reserve 6 notes of each denom >= 10 so a shortfall of up to 5 notes
    # of any injectable denomination is always physically subtractable
    out: dict[int, int] = {d: (6 if d >= 10 else 0) for d in DENOMS}
    left = total - sum(d * n for d, n in out.items())
    if left < 0:
        raise ValueError(f"counted cash {total} too small to denominate")
    for d in DENOMS:
        n_max = left // d
        n = n_max if d == 1 else (rng.randint(int(n_max * 0.6), n_max) if n_max else 0)
        out[d] += n
        left -= n * d
    assert left == 0
    return out


class SessionBuilder:
    """Builds one clean session, then applies injectors."""

    def __init__(self, rng: Random, case_id: str) -> None:
        self.rng = rng
        self.case_id = case_id
        self.branch = f"{rng.randint(1, 999):04d}"
        self.teller = f"T{rng.randint(1, 9):02d}"
        self.business_date = "2026-07-01"
        self.opening_float = 2_000_000
        self._seq = 0
        self._clock = datetime(2026, 7, 1, 9, 0, 0)
        self.actual: list[Txn] = []
        self.posted: list[Txn] = []
        self.reversal_involved: set[str] = set()  # refs off-limits to injectors
        self.shortfall_amount = 0

    def next_ref(self) -> str:
        self._seq += 1
        return f"TXN{self._seq:04d}"

    def _next_time(self) -> str:
        self._clock += timedelta(minutes=self.rng.randint(1, 5))
        return self._clock.strftime("%H:%M:%S")

    def build_clean(self) -> None:
        rng = self.rng
        balance = self.opening_float
        n = rng.randint(30, 70)
        # repeat customers: accounts drawn from a per-session pool, so a
        # near-miss account is detectable against its correct occurrences
        self.account_pool = [_account(rng) for _ in range(max(8, n // 3))]
        for _ in range(n):
            amount = _amount(rng)
            if rng.random() < 0.6 or amount > balance * 0.5:
                txn_type = "cash_in"
                balance += amount
            else:
                txn_type = "cash_out"
                balance -= amount
            t = Txn(self.next_ref(), rng.choice(self.account_pool), txn_type,
                    amount, self._next_time())
            self.actual.append(t)
            # ~8% of txns get a legit posted reversal pair (cancels out)
            if rng.random() < 0.08:
                rev = Txn(self.next_ref(), t.account, "reversal", t.amount,
                          self._next_time(), narration=f"REV:{t.ref}", reverses=t.ref)
                self.actual.append(rev)
                self.reversal_involved.update({t.ref, rev.ref})
                balance += amount if txn_type == "cash_out" else -amount
        self.posted = list(self.actual)

    def _pick_target(self, exclude: set[str]) -> tuple[int, Txn]:
        candidates = [
            (i, t) for i, t in enumerate(self.posted)
            if t.txn_type in ("cash_in", "cash_out")
            and t.ref not in self.reversal_involved
            and t.ref not in exclude
        ]
        return self.rng.choice(candidates)

    # --- injectors: one per signature -------------------------------------

    def inject_digit_transposition(self, exclude: set[str]) -> TruthError:
        rng = self.rng
        for _ in range(200):
            i, t = self._pick_target(exclude)
            s = str(t.amount)
            pairs = [p for p in range(len(s) - 1)
                     if s[p] != s[p + 1] and not (p == 0 and s[p + 1] == "0")]
            if not pairs:
                continue
            p = rng.choice(pairs)
            transposed = int(s[:p] + s[p + 1] + s[p] + s[p + 2:])
            self.posted[i] = replace(t, amount=transposed)
            sign = 1 if t.txn_type == "cash_in" else -1
            return TruthError(
                "digit_transposition", [t.ref],
                {"actual_amount": t.amount, "posted_amount": transposed},
                cash_delta=sign * (t.amount - transposed),
            )
        raise RuntimeError("no transposable txn found")

    def inject_duplicate_posting(self, exclude: set[str]) -> TruthError:
        _, t = self._pick_target(exclude)
        dup = replace(t, ref=self.next_ref(), time=self._next_time())
        self.posted.append(dup)
        sign = 1 if t.txn_type == "cash_in" else -1
        return TruthError(
            "duplicate_posting", [t.ref, dup.ref],
            {"amount": t.amount, "account": t.account},
            cash_delta=-sign * t.amount,
        )

    def inject_missed_reversal(self, exclude: set[str]) -> TruthError:
        _, t = self._pick_target(exclude)
        # cash physically returned/recovered at the counter, reversal never posted
        phantom = Txn(self.next_ref(), t.account, "reversal", t.amount,
                      self._next_time(), reverses=t.ref)
        self.actual.append(phantom)
        sign = 1 if t.txn_type == "cash_in" else -1
        return TruthError(
            "missed_reversal", [t.ref],
            {"amount": t.amount},
            cash_delta=-sign * t.amount,
        )

    def inject_denomination_shortfall(self, exclude: set[str]) -> TruthError:
        # applied to the breakdown in finalize(); record intent here
        denom = self.rng.choice((5000, 1000, 500, 100, 50))
        k = self.rng.randint(1, 5)
        self.shortfall_amount += denom * k
        return TruthError(
            "denomination_shortfall", [],
            {"denomination": denom, "notes_short": k},
            cash_delta=-denom * k,
        )

    def inject_cash_inout_miskey(self, exclude: set[str]) -> TruthError:
        i, t = self._pick_target(exclude)
        flipped = "cash_out" if t.txn_type == "cash_in" else "cash_in"
        self.posted[i] = replace(t, txn_type=flipped)
        sign = 1 if t.txn_type == "cash_in" else -1
        return TruthError(
            "cash_inout_miskey", [t.ref],
            {"actual_type": t.txn_type, "posted_type": flipped, "amount": t.amount},
            cash_delta=sign * 2 * t.amount,
        )

    def inject_wrong_adjacent_account(self, exclude: set[str]) -> TruthError:
        rng = self.rng
        from collections import Counter

        counts = Counter(x.account for x in self.posted)
        i = t = None
        for _ in range(200):  # target an account posted correctly elsewhere too
            j, cand = self._pick_target(exclude)
            if counts[cand.account] >= 2:
                i, t = j, cand
                break
        if t is None:
            i, t = self._pick_target(exclude)
        pool = set(self.account_pool)
        while True:
            digits = list(t.account)
            pairs = [p for p in range(len(digits) - 1)
                     if digits[p] != digits[p + 1] and not (p == 0 and digits[p + 1] == "0")]
            if pairs and rng.random() < 0.5:
                p = rng.choice(pairs)
                digits[p], digits[p + 1] = digits[p + 1], digits[p]
            else:
                p = rng.randrange(1, len(digits))
                digits[p] = str((int(digits[p]) + rng.choice((-1, 1))) % 10)
            wrong = "".join(digits)
            if wrong != t.account and wrong not in pool:
                break
        self.posted[i] = replace(t, account=wrong)
        return TruthError(
            "wrong_adjacent_account", [t.ref],
            {"intended_account": t.account, "posted_account": wrong},
            cash_delta=0,
        )

    # -----------------------------------------------------------------------

    def finalize(self, errors: list[TruthError]) -> Case:
        system_cash = self.opening_float + _cash_effect(self.posted)
        counted = self.opening_float + _cash_effect(self.actual) - self.shortfall_amount
        breakdown = _breakdown(counted + self.shortfall_amount, self.rng)
        # remove the missing notes from the physical count
        for e in errors:
            if e.signature == "denomination_shortfall":
                d, k = int(e.detail["denomination"]), int(e.detail["notes_short"])
                breakdown[d] -= k
        return Case(
            case_id=self.case_id,
            branch=self.branch,
            teller=self.teller,
            business_date=self.business_date,
            opening_float=self.opening_float,
            posted=sorted(self.posted, key=lambda t: (t.time, t.ref)),
            actual=self.actual,
            system_cash=system_cash,
            counted_cash=counted,
            denomination_count=breakdown,
            variance=counted - system_cash,
            errors=errors,
        )


INJECTORS = {
    "digit_transposition": SessionBuilder.inject_digit_transposition,
    "duplicate_posting": SessionBuilder.inject_duplicate_posting,
    "missed_reversal": SessionBuilder.inject_missed_reversal,
    "denomination_shortfall": SessionBuilder.inject_denomination_shortfall,
    "cash_inout_miskey": SessionBuilder.inject_cash_inout_miskey,
    "wrong_adjacent_account": SessionBuilder.inject_wrong_adjacent_account,
}


def make_case(case_id: str, signatures: list[str], seed: int) -> Case:
    b = SessionBuilder(Random(seed), case_id)
    b.build_clean()
    errors: list[TruthError] = []
    exclude: set[str] = set()
    for sig in signatures:
        err = INJECTORS[sig](b, exclude)
        errors.append(err)
        exclude.update(err.refs)
    return b.finalize(errors)


def write_case(case: Case, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / f"{case.case_id}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for t in case.posted:
            w.writerow([case.branch, case.teller, case.business_date, t.time,
                        t.ref, t.account, t.txn_type.upper(), t.amount, t.narration])
    meta = {
        "case_id": case.case_id,
        "opening_float": case.opening_float,
        "counted_cash": case.counted_cash,
        "denomination_count": case.denomination_count,
    }
    (out_dir / f"{case.case_id}_meta.json").write_text(json.dumps(meta, indent=2))
    truth = [asdict(e) for e in case.errors]
    (out_dir / f"{case.case_id}_truth.json").write_text(json.dumps(truth, indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "sample")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    for n, sig in enumerate(SIGNATURES):
        case = make_case(f"demo_{sig}", [sig], seed=args.seed + n)
        write_case(case, args.out)
        print(f"{case.case_id}: variance {case.variance:+,} PKR, "
              f"{len(case.posted)} posted txns -> {args.out}")


if __name__ == "__main__":
    main()
