"""Isolation Forest anomaly scores — SECONDARY signal, display only.

Never called from matching.py: scores are attached to already-ranked suspects
for the dashboard and must never override, filter, or re-rank rule output.
"""

from __future__ import annotations

from .models import SessionInput


def _minutes(hhmmss: str) -> int:
    try:
        h, m, _ = hhmmss.split(":")
        return int(h) * 60 + int(m)
    except ValueError:
        return 0


def anomaly_scores(session: SessionInput) -> dict[str, float]:
    """Per-txn anomaly score in [0, 1] (1 = most anomalous). Deterministic."""
    import math

    import numpy as np
    from sklearn.ensemble import IsolationForest

    txns = session.txns
    if len(txns) < 8:
        return {t.ref: 0.0 for t in txns}
    x = np.array([
        [t.amount, math.log10(t.amount), _minutes(t.time), 1 if t.txn_type == "cash_in" else 0]
        for t in txns
    ])
    forest = IsolationForest(n_estimators=100, random_state=0)
    raw = -forest.fit(x).score_samples(x)  # higher = more anomalous
    lo, hi = float(raw.min()), float(raw.max())
    span = (hi - lo) or 1.0
    return {t.ref: round((float(r) - lo) / span, 4) for t, r in zip(txns, raw, strict=True)}
