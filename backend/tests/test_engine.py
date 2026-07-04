"""Oracle-backed engine tests. Never loosen thresholds to make these pass —
flag the mismatch instead (CLAUDE.md / Testing)."""

import pytest
from generator import SIGNATURES, Case
from ground_truth import Prediction, Report, Suite, build_suite, evaluate, passes_gate

from app.engine import SessionInput, TxnInput, analyze


def to_session(case: Case) -> SessionInput:
    return SessionInput(
        branch=case.branch,
        teller=case.teller,
        business_date=case.business_date,
        opening_float=case.opening_float,
        counted_cash=case.counted_cash,
        denomination_count=case.denomination_count,
        txns=[
            TxnInput(
                ref=t.ref, account=t.account, txn_type=t.txn_type,
                amount=t.amount, time=t.time, narration=t.narration,
                reverses=t.reverses,
            )
            for t in case.posted
        ],
    )


def engine_fn(case: Case) -> list[Prediction]:
    return [Prediction(s.signature, s.txn_refs) for s in analyze(to_session(case))]


@pytest.fixture(scope="session")
def suite() -> Suite:
    return build_suite()


@pytest.fixture(scope="session")
def report(suite: Suite) -> Report:
    r = evaluate(engine_fn, suite)
    print(f"\nsingle={r.single_accuracy:.1%} double={r.double_accuracy:.1%} "
          f"per_signature={ {k: f'{v:.0%}' for k, v in r.per_signature.items()} }")
    return r


@pytest.mark.parametrize("signature", SIGNATURES)
def test_signature_rule(report: Report, signature: str) -> None:
    assert report.per_signature[signature] >= 0.90, (
        f"{signature}: {report.per_signature[signature]:.1%}"
    )


def test_single_error_gate(report: Report) -> None:
    assert report.single_accuracy >= 0.90, f"{report.single_accuracy:.1%}"


def test_two_error_gate(report: Report) -> None:
    assert report.double_accuracy >= 0.70, f"{report.double_accuracy:.1%}"


def test_passes_gate(report: Report) -> None:
    assert passes_gate(report)


def test_deterministic(suite: Suite) -> None:
    case = suite.doubles[0]
    assert analyze(to_session(case)) == analyze(to_session(case))


def test_engine_output_shape(suite: Suite) -> None:
    for case in suite.singles[:10]:
        suspects = analyze(to_session(case))
        assert 1 <= len(suspects) <= 5
        assert [s.rank for s in suspects] == list(range(1, len(suspects) + 1))


def test_anomaly_is_display_only_and_deterministic(suite: Suite) -> None:
    from app.engine.anomaly import anomaly_scores

    session = to_session(suite.singles[0])
    scores = anomaly_scores(session)
    assert set(scores) == {t.ref for t in session.txns}
    assert all(0.0 <= v <= 1.0 for v in scores.values())
    assert scores == anomaly_scores(session)
    # ranking must be identical whether or not anomaly scores exist
    assert [s.txn_refs for s in analyze(session)] == [s.txn_refs for s in analyze(session)]
