"""ZeroBalance v2 scenario oracle.

Labeled behavioral scenarios for the v2 feature set:

- Digital Excess Ledger — state machine (opened -> countersigned -> closed) +
  dual sign-off (countersigner MUST differ from opener).
- Cheque capture — denomination-out breakdown must sum to amount; MICR must
  resolve to the stated account.
- Pre-post validation — 5 checks (denom_sum, cnic_name_match, duplicate_check,
  large_amount_confirm, sanity), each with a pass and a fail scenario.

The engine oracle for EOD variance signatures stays in `ground_truth.py`.
This file is separate on purpose: mixing behavioral scenarios into the
matching-engine oracle would blur what "correct" means.

Run `python ground_truth_v2.py` for the self-check. Exits non-zero on failure.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

# --- Excess Ledger ----------------------------------------------------------

ExcessEventType = Literal["opened", "countersigned", "closed"]
ExcessOutcome = Literal[
    "accepted",
    "rejected_dual_signoff",
    "rejected_missing_countersign",
    "rejected_double_countersign",
    "rejected_out_of_order",
]


@dataclass(frozen=True)
class ExcessEvent:
    event_type: ExcessEventType
    actor: str
    amount: Decimal
    note: str = ""


@dataclass(frozen=True)
class ExcessScenario:
    case_id: str
    case_ref: str  # UUID string (not validated as UUID here — Phase 11 does)
    branch_code: str
    teller_id: str
    business_date: str  # ISO date
    entry_kind: Literal["excess", "short"]
    events: tuple[ExcessEvent, ...]
    expected_outcome: ExcessOutcome
    rejects_at_seq: int | None = None  # 1-indexed seq of the event that must be rejected


def _excess_scenarios() -> list[ExcessScenario]:
    D = Decimal
    return [
        # 1. Happy path — different actor countersigns, then closes.
        ExcessScenario(
            case_id="excess_happy_short",
            case_ref="11111111-1111-4111-8111-111111111111",
            branch_code="UBL-KHI-042", teller_id="TLR-001",
            business_date="2026-07-11", entry_kind="short",
            events=(
                ExcessEvent("opened", "TLR-001", D("500.00"), "till short by 500"),
                ExcessEvent("countersigned", "OFF-014", D("500.00")),
                ExcessEvent("closed", "OFF-014", D("500.00"), "adjusted from staff float"),
            ),
            expected_outcome="accepted",
        ),
        # 2. Happy path — excess entry, closes with different officer.
        ExcessScenario(
            case_id="excess_happy_excess",
            case_ref="22222222-2222-4222-8222-222222222222",
            branch_code="UBL-KHI-042", teller_id="TLR-002",
            business_date="2026-07-11", entry_kind="excess",
            events=(
                ExcessEvent("opened", "TLR-002", D("1200.00"), "excess of 1200"),
                ExcessEvent("countersigned", "OFF-014", D("1200.00")),
                ExcessEvent("closed", "OFF-021", D("1200.00"), "posted to sundries"),
            ),
            expected_outcome="accepted",
        ),
        # 3. Dual sign-off violation — countersigner is the same as opener.
        ExcessScenario(
            case_id="excess_same_signer",
            case_ref="33333333-3333-4333-8333-333333333333",
            branch_code="UBL-KHI-042", teller_id="TLR-003",
            business_date="2026-07-11", entry_kind="short",
            events=(
                ExcessEvent("opened", "TLR-003", D("300.00"), "short"),
                ExcessEvent("countersigned", "TLR-003", D("300.00")),
            ),
            expected_outcome="rejected_dual_signoff",
            rejects_at_seq=2,
        ),
        # 4. Close attempted before countersign.
        ExcessScenario(
            case_id="excess_close_without_countersign",
            case_ref="44444444-4444-4444-8444-444444444444",
            branch_code="UBL-KHI-042", teller_id="TLR-004",
            business_date="2026-07-11", entry_kind="short",
            events=(
                ExcessEvent("opened", "TLR-004", D("800.00"), "short"),
                ExcessEvent("closed", "OFF-014", D("800.00"), "attempted close"),
            ),
            expected_outcome="rejected_missing_countersign",
            rejects_at_seq=2,
        ),
        # 5. Double countersign — second countersign must be rejected.
        ExcessScenario(
            case_id="excess_double_countersign",
            case_ref="55555555-5555-4555-8555-555555555555",
            branch_code="UBL-KHI-042", teller_id="TLR-005",
            business_date="2026-07-11", entry_kind="excess",
            events=(
                ExcessEvent("opened", "TLR-005", D("450.00")),
                ExcessEvent("countersigned", "OFF-014", D("450.00")),
                ExcessEvent("countersigned", "OFF-021", D("450.00")),
            ),
            expected_outcome="rejected_double_countersign",
            rejects_at_seq=3,
        ),
        # 6. Out-of-order — countersign before open.
        ExcessScenario(
            case_id="excess_countersign_before_open",
            case_ref="66666666-6666-4666-8666-666666666666",
            branch_code="UBL-KHI-042", teller_id="TLR-006",
            business_date="2026-07-11", entry_kind="short",
            events=(
                ExcessEvent("countersigned", "OFF-014", D("200.00")),
            ),
            expected_outcome="rejected_out_of_order",
            rejects_at_seq=1,
        ),
    ]


# --- Cheque capture ---------------------------------------------------------

ChequeOutcome = Literal["valid", "invalid_denom_sum", "invalid_micr"]


@dataclass(frozen=True)
class ChequeScenario:
    case_id: str
    branch_code: str
    teller_id: str
    business_date: str
    micr: str
    account_number: str
    micr_valid: bool  # whether the MICR resolves to account_number (Phase 12 lookup)
    amount: Decimal
    denomination_out: dict[str, int]  # {"5000": 10, "1000": 50, ...}
    expected_outcome: ChequeOutcome


def _cheque_scenarios() -> list[ChequeScenario]:
    D = Decimal
    return [
        ChequeScenario(
            case_id="cheque_valid_simple",
            branch_code="UBL-KHI-042", teller_id="TLR-001",
            business_date="2026-07-11",
            micr="⑈042000123456⑈ ⑆00789012⑆",
            account_number="00789012",
            micr_valid=True,
            amount=D("15000.00"),
            denomination_out={"5000": 3},
            expected_outcome="valid",
        ),
        ChequeScenario(
            case_id="cheque_valid_multi_denom",
            branch_code="UBL-KHI-042", teller_id="TLR-001",
            business_date="2026-07-11",
            micr="⑈042000234567⑈ ⑆00456789⑆",
            account_number="00456789",
            micr_valid=True,
            amount=D("17500.00"),
            denomination_out={"5000": 3, "1000": 2, "500": 1},
            expected_outcome="valid",
        ),
        ChequeScenario(
            case_id="cheque_denom_sum_short",
            branch_code="UBL-KHI-042", teller_id="TLR-001",
            business_date="2026-07-11",
            micr="⑈042000345678⑈ ⑆00123456⑆",
            account_number="00123456",
            micr_valid=True,
            amount=D("10000.00"),
            denomination_out={"5000": 1},  # sums to 5000, not 10000
            expected_outcome="invalid_denom_sum",
        ),
        ChequeScenario(
            case_id="cheque_micr_mismatch",
            branch_code="UBL-KHI-042", teller_id="TLR-001",
            business_date="2026-07-11",
            micr="⑈042000456789⑈ ⑆00999999⑆",
            account_number="00123456",  # doesn't match MICR-encoded 00999999
            micr_valid=False,
            amount=D("5000.00"),
            denomination_out={"5000": 1},
            expected_outcome="invalid_micr",
        ),
    ]


# --- Pre-post validation (demo-only surface) --------------------------------

PrepostCheckName = Literal[
    "denom_sum", "cnic_name_match", "duplicate_check",
    "large_amount_confirm", "sanity",
]


@dataclass(frozen=True)
class PrepostScenario:
    case_id: str
    check_name: PrepostCheckName
    input: dict
    expected_passed: bool
    expected_reason: str = ""  # non-empty when expected_passed is False


def _prepost_scenarios() -> list[PrepostScenario]:
    return [
        # denom_sum
        PrepostScenario(
            "prepost_denom_sum_pass", "denom_sum",
            {"amount": 5500, "denominations": {"5000": 1, "500": 1}},
            True,
        ),
        PrepostScenario(
            "prepost_denom_sum_fail", "denom_sum",
            {"amount": 5500, "denominations": {"5000": 1}},
            False, "denomination sum 5000 != amount 5500",
        ),
        # cnic_name_match
        PrepostScenario(
            "prepost_cnic_name_pass", "cnic_name_match",
            {"cnic": "42101-1234567-1", "account_holder": "AHMED ALI KHAN",
             "typed_name": "Ahmed Ali Khan"},
            True,
        ),
        PrepostScenario(
            "prepost_cnic_name_fail", "cnic_name_match",
            {"cnic": "42101-1234567-1", "account_holder": "AHMED ALI KHAN",
             "typed_name": "Muhammad Yasir"},
            False, "typed_name does not match account_holder (fuzzy score below threshold)",
        ),
        # duplicate_check
        PrepostScenario(
            "prepost_duplicate_pass", "duplicate_check",
            {"cbs_ref": "TXN20260711001",
             "recent_refs": ["TXN20260711002", "TXN20260711003"]},
            True,
        ),
        PrepostScenario(
            "prepost_duplicate_fail", "duplicate_check",
            {"cbs_ref": "TXN20260711001",
             "recent_refs": ["TXN20260711001", "TXN20260711002"]},
            False, "cbs_ref already posted in recent window",
        ),
        # large_amount_confirm
        PrepostScenario(
            "prepost_large_confirmed", "large_amount_confirm",
            {"amount": 250000, "threshold": 50000, "confirmed": True},
            True,
        ),
        PrepostScenario(
            "prepost_large_not_confirmed", "large_amount_confirm",
            {"amount": 250000, "threshold": 50000, "confirmed": False},
            False, "amount above threshold requires explicit confirmation",
        ),
        # sanity
        PrepostScenario(
            "prepost_sanity_pass", "sanity",
            {"amount": 5000, "account_type": "current", "txn_type": "cash_out"},
            True,
        ),
        PrepostScenario(
            "prepost_sanity_fail", "sanity",
            {"amount": -5000, "account_type": "current", "txn_type": "cash_out"},
            False, "amount must be positive",
        ),
    ]


# --- Public suite -----------------------------------------------------------


@dataclass(frozen=True)
class ScenarioSuiteV2:
    excess: tuple[ExcessScenario, ...] = field(default_factory=tuple)
    cheque: tuple[ChequeScenario, ...] = field(default_factory=tuple)
    prepost: tuple[PrepostScenario, ...] = field(default_factory=tuple)


def build_suite_v2() -> ScenarioSuiteV2:
    return ScenarioSuiteV2(
        excess=tuple(_excess_scenarios()),
        cheque=tuple(_cheque_scenarios()),
        prepost=tuple(_prepost_scenarios()),
    )


# --- Self-check -------------------------------------------------------------


_VALID_PREPOST_CHECKS = {
    "denom_sum", "cnic_name_match", "duplicate_check",
    "large_amount_confirm", "sanity",
}
_VALID_EXCESS_OUTCOMES = {
    "accepted", "rejected_dual_signoff", "rejected_missing_countersign",
    "rejected_double_countersign", "rejected_out_of_order",
}


def _check_excess(s: ExcessScenario) -> list[str]:
    problems: list[str] = []
    if not s.events:
        problems.append("no events")
    if s.expected_outcome not in _VALID_EXCESS_OUTCOMES:
        problems.append(f"bad expected_outcome: {s.expected_outcome}")
    if s.expected_outcome == "accepted" and s.rejects_at_seq is not None:
        problems.append("accepted scenario should not carry rejects_at_seq")
    if s.expected_outcome != "accepted" and s.rejects_at_seq is None:
        problems.append("non-accepted scenario missing rejects_at_seq")
    for i, e in enumerate(s.events, start=1):
        if e.event_type not in ("opened", "countersigned", "closed"):
            problems.append(f"seq {i}: bad event_type {e.event_type}")
        if e.amount <= 0:
            problems.append(f"seq {i}: non-positive amount")
        if not e.actor:
            problems.append(f"seq {i}: empty actor")
    if s.expected_outcome == "accepted":
        # Must be a legal sequence: opened, countersigned, closed with distinct
        # opener vs countersigner.
        types = [e.event_type for e in s.events]
        if types != ["opened", "countersigned", "closed"]:
            problems.append(f"accepted but sequence is {types}")
        else:
            if s.events[0].actor == s.events[1].actor:
                problems.append("accepted but opener == countersigner")
    return problems


def _check_cheque(s: ChequeScenario) -> list[str]:
    problems: list[str] = []
    if s.amount <= 0:
        problems.append("non-positive amount")
    for k, v in s.denomination_out.items():
        if not k.isdigit() or int(k) not in {5000, 1000, 500, 100, 50, 20, 10, 5, 2, 1}:
            problems.append(f"bad denomination key {k}")
        if v < 0:
            problems.append(f"negative note count for {k}")
    total = Decimal(sum(int(k) * v for k, v in s.denomination_out.items()))
    if s.expected_outcome == "valid":
        if total != s.amount:
            problems.append(f"expected valid but sum {total} != amount {s.amount}")
        if not s.micr_valid:
            problems.append("expected valid but micr_valid is False")
    if s.expected_outcome == "invalid_denom_sum":
        if total == s.amount:
            problems.append("expected invalid_denom_sum but sums match")
    if s.expected_outcome == "invalid_micr":
        if s.micr_valid:
            problems.append("expected invalid_micr but micr_valid is True")
    return problems


def _check_prepost(s: PrepostScenario) -> list[str]:
    problems: list[str] = []
    if s.check_name not in _VALID_PREPOST_CHECKS:
        problems.append(f"bad check_name {s.check_name}")
    if not isinstance(s.input, dict) or not s.input:
        problems.append("input must be non-empty dict")
    if s.expected_passed and s.expected_reason:
        problems.append("expected_passed=True should carry no reason")
    if not s.expected_passed and not s.expected_reason:
        problems.append("expected_passed=False must carry a reason")
    return problems


def self_check() -> bool:
    suite = build_suite_v2()
    ok = True

    print(f"excess:  {len(suite.excess)} scenarios")
    print(f"cheque:  {len(suite.cheque)} scenarios")
    print(f"prepost: {len(suite.prepost)} scenarios")

    # Coverage assertions
    if len(suite.excess) < 4:
        print("FAIL coverage: need >=4 excess scenarios"); ok = False
    if len(suite.cheque) < 4:
        print("FAIL coverage: need >=4 cheque scenarios"); ok = False
    prepost_by_check = {c: 0 for c in _VALID_PREPOST_CHECKS}
    for s in suite.prepost:
        prepost_by_check[s.check_name] = prepost_by_check.get(s.check_name, 0) + 1
    for c, n in prepost_by_check.items():
        if n < 2:
            print(f"FAIL coverage: prepost check {c} has only {n} scenarios (need 2+)")
            ok = False

    # Per-scenario invariants
    def _report(kind: str, sid: str, problems: list[str]) -> None:
        nonlocal ok
        if problems:
            ok = False
            print(f"FAIL {kind} {sid}: {'; '.join(problems)}")

    for s in suite.excess:
        _report("excess", s.case_id, _check_excess(s))
    for s in suite.cheque:
        _report("cheque", s.case_id, _check_cheque(s))
    for s in suite.prepost:
        _report("prepost", s.case_id, _check_prepost(s))

    # Determinism: two builds are structurally identical.
    a = build_suite_v2()
    b = build_suite_v2()
    if a != b:
        print("FAIL determinism: two builds differ"); ok = False
    else:
        print("determinism OK (structural equality)")

    print("SELF-CHECK PASSED" if ok else "SELF-CHECK FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if self_check() else 1)
