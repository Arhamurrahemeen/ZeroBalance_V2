"""Deterministic matching engine.

Candidate generation: each rule proposes (signature, culprit refs, cash delta)
where delta is the exact contribution that error would make to the variance
V = counted_cash - system_cash. Selection keeps candidates whose delta equals V
(singles) and pairs of candidates whose deltas sum to V (two-error sessions).
Ranking is by fixed rule-specificity scores with lexicographic tiebreaks —
fully reproducible, no learned component anywhere.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from rapidfuzz.distance import OSA

from .models import SessionInput, Suspect, TxnInput

TOP_K = 5
SHORTFALL_DENOMS = (5000, 1000, 500, 100, 50)
MAX_NOTES_SHORT = 5


@dataclass(frozen=True)
class _Candidate:
    signature: str
    refs: tuple[str, ...]
    delta: int
    priority: int
    evidence: tuple[tuple[str, int | str], ...]


def system_cash(session: SessionInput) -> int:
    by_ref = {t.ref: t for t in session.txns}
    total = session.opening_float
    for t in session.txns:
        if t.txn_type == "cash_in":
            total += t.amount
        elif t.txn_type == "cash_out":
            total -= t.amount
        else:
            orig = by_ref.get(t.reverses or "")
            if orig is None:
                raise ValueError(f"reversal {t.ref} references unknown txn")
            total += orig.amount if orig.txn_type == "cash_out" else -orig.amount
    return total


def _sign(t: TxnInput) -> int:
    return 1 if t.txn_type == "cash_in" else -1


def _swaps(amount: int) -> list[int]:
    """All adjacent-digit transpositions of `amount` (no leading zero)."""
    s = str(amount)
    out = []
    for p in range(len(s) - 1):
        if s[p] == s[p + 1] or (p == 0 and s[p + 1] == "0"):
            continue
        out.append(int(s[: p] + s[p + 1] + s[p] + s[p + 2 :]))
    return out


def _candidates(session: SessionInput) -> list[_Candidate]:
    reversed_refs = {t.reverses for t in session.txns if t.reverses}
    plain = [
        t for t in session.txns
        if t.txn_type in ("cash_in", "cash_out") and t.ref not in reversed_refs
    ]
    out: list[_Candidate] = []

    # duplicate_posting: identical (account, amount, type) posted more than once
    groups: dict[tuple[str, int, str], list[TxnInput]] = defaultdict(list)
    for t in plain:
        groups[(t.account, t.amount, t.txn_type)].append(t)
    for (account, amount, txn_type), g in sorted(groups.items()):
        if len(g) < 2:
            continue
        sign = 1 if txn_type == "cash_in" else -1
        out.append(_Candidate(
            "duplicate_posting",
            tuple(sorted(t.ref for t in g)),
            -sign * amount * (len(g) - 1),
            5,
            (("amount", amount), ("account", account), ("copies", len(g))),
        ))

    for t in plain:
        s = _sign(t)
        out.append(_Candidate(
            "missed_reversal", (t.ref,), -s * t.amount, 3,
            (("amount", t.amount), ("txn_type", t.txn_type)),
        ))
        out.append(_Candidate(
            "cash_inout_miskey", (t.ref,), -2 * s * t.amount, 4,
            (("posted_type", t.txn_type), ("amount", t.amount)),
        ))
        # digit_transposition: corrected amount must be cash-like (multiple of 10)
        for corrected in _swaps(t.amount):
            if corrected % 10 != 0:
                continue
            priority = 6 if t.amount % 10 != 0 else 3
            out.append(_Candidate(
                "digit_transposition", (t.ref,), s * (corrected - t.amount), priority,
                (("posted_amount", t.amount), ("corrected_amount", corrected)),
            ))

    # denomination_shortfall: k notes of one denomination missing from the count
    for denom in SHORTFALL_DENOMS:
        for k in range(1, MAX_NOTES_SHORT + 1):
            out.append(_Candidate(
                "denomination_shortfall", (), -denom * k, 2,
                (("denomination", denom), ("notes_short", k)),
            ))

    # wrong_adjacent_account: account seen once, 1 edit away from another account
    account_count = Counter(t.account for t in session.txns)
    others = sorted(account_count)
    for t in plain:
        if account_count[t.account] != 1:
            continue
        for other in others:
            if other == t.account:
                continue
            if OSA.distance(t.account, other, score_cutoff=1) == 1:
                out.append(_Candidate(
                    "wrong_adjacent_account", (t.ref,), 0, 6,
                    (("posted_account", t.account), ("intended_account", other)),
                ))
                break
    return out


def _dedupe(cands: list[_Candidate]) -> list[_Candidate]:
    best: dict[tuple[str, tuple[str, ...], int], _Candidate] = {}
    for c in cands:  # first wins ties: generation order is fixed (e.g. largest denom)
        key = (c.signature, c.refs, c.delta)
        cur = best.get(key)
        if cur is None or c.priority > cur.priority:
            best[key] = c
    return sorted(best.values(), key=lambda c: (-c.priority, c.signature, c.refs))


def analyze(session: SessionInput, top_k: int = TOP_K) -> list[Suspect]:
    variance = session.counted_cash - system_cash(session)
    cands = _dedupe(_candidates(session))

    singles = [
        c for c in cands
        if c.delta == variance and (variance != 0 or c.signature == "wrong_adjacent_account")
    ]

    # balanced till: only zero-delta signatures are meaningful — canceling pairs
    # would be pure noise, and a clean session must yield zero suspects
    if variance == 0:
        ranked_zero: list[_Candidate] = []
        for c in singles[:top_k]:
            ranked_zero.append(c)
        return [
            Suspect(rank=i + 1, signature=c.signature,  # type: ignore[arg-type]
                    txn_refs=c.refs, cash_delta=c.delta, rule_score=c.priority,
                    evidence=dict(c.evidence))
            for i, c in enumerate(ranked_zero)
        ]

    by_delta: dict[int, list[_Candidate]] = defaultdict(list)
    for c in cands:
        by_delta[c.delta].append(c)
    pairs: list[tuple[_Candidate, _Candidate]] = []
    seen: set[tuple] = set()
    for c1 in cands:
        for c2 in by_delta.get(variance - c1.delta, []):
            if c1 is c2 or (set(c1.refs) & set(c2.refs)):
                continue
            if c1.signature == c2.signature == "denomination_shortfall":
                continue
            key = tuple(sorted(((c1.signature, c1.refs, c1.delta),
                                (c2.signature, c2.refs, c2.delta))))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((c1, c2))
    pairs.sort(key=lambda p: (
        -(p[0].priority + p[1].priority),
        p[0].signature, p[0].refs, p[1].signature, p[1].refs,
    ))

    ranked: list[_Candidate] = []

    def push(c: _Candidate) -> None:
        if len(ranked) < top_k and not any(
            r.signature == c.signature and r.refs == c.refs for r in ranked
        ):
            ranked.append(c)

    for c in singles:
        push(c)
    for c1, c2 in pairs:
        if len(ranked) > top_k - 2:
            break
        push(c1)
        push(c2)
    if not ranked:  # nothing explains V exactly: surface top raw candidates
        for c in cands[:3]:
            push(c)

    return [
        Suspect(
            rank=i + 1,
            signature=c.signature,  # type: ignore[arg-type]
            txn_refs=c.refs,
            cash_delta=c.delta,
            rule_score=c.priority,
            evidence=dict(c.evidence),
        )
        for i, c in enumerate(ranked)
    ]
