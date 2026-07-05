"""Groq explanation layer — post-hoc only.

The engine has already decided and ranked. This module turns each stored
suspect's rule evidence into a short Urdu explanation for the teller.
It must never add, remove, reorder, or re-score suspects.
Account numbers are masked before anything leaves the box.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db_models import EodSessionRow, SuspectRow

SIGNATURE_UR = {
    "digit_transposition": "ہندسوں کی ادلا بدلی",
    "duplicate_posting": "دوہری پوسٹنگ",
    "missed_reversal": "ریورسل درج نہیں ہوا",
    "denomination_shortfall": "نوٹوں کی کمی",
    "cash_inout_miskey": "کیش اِن/آؤٹ کا غلط اندراج",
    "wrong_adjacent_account": "غلط اکاؤنٹ میں اندراج",
}

SYSTEM_PROMPT = (
    "You are the explanation assistant inside ZeroBalance, a cash-reconciliation "
    "co-pilot for bank tellers in Pakistan. The deterministic matching engine has "
    "ALREADY identified and ranked the suspect transactions — that decision is final. "
    "Your only job: explain in simple Urdu why the engine flagged the given suspect, "
    "so the teller can verify it quickly.\n"
    "Rules: 2-3 short sentences, Urdu script only, numbers in western digits (e.g. 66,400). "
    "Use amounts and transaction references exactly as given. Do not invent facts, do not "
    "suggest other suspects, do not question the ranking, and do not declare anyone guilty — "
    "explain the evidence only."
)

_MASK_KEYS = {"account", "posted_account", "intended_account"}


class _ChatClient(Protocol):  # what we need from groq.Groq
    chat: Any


def _client_factory() -> _ChatClient:
    from groq import Groq

    return Groq(api_key=settings.groq_api_key)


def mask_account(account: str) -> str:
    return f"****{account[-4:]}" if len(account) > 4 else "****"


def build_prompt(session: EodSessionRow, suspect: SuspectRow) -> str:
    ev = suspect.rule_evidence
    detail = {
        k: (mask_account(str(v)) if k in _MASK_KEYS else v)
        for k, v in ev.get("detail", {}).items()
    }
    lines = [
        f"EOD variance for teller {session.teller_id} on {session.business_date}: "
        f"{int(session.variance or 0):+,} PKR "
        f"(counted {int(session.counted_cash or 0):,}, system {int(session.system_cash or 0):,}).",
        f"Suspect rank {suspect.rank} of the engine's list.",
        f"Error type: {suspect.signature} ({SIGNATURE_UR[suspect.signature]}).",
        "Transaction reference(s): "
        f"{', '.join(ev.get('txn_refs', [])) or 'none (till-count level)'}.",
        f"Cash impact if confirmed: {ev.get('cash_delta', 0):+,} PKR.",
        f"Evidence: {detail}.",
        "Explain this suspicion to the teller in Urdu.",
    ]
    return "\n".join(lines)


def explain_suspects(db: Session, session: EodSessionRow,
                     client: _ChatClient | None = None) -> int:
    """Fill explanation_ur for suspects that lack one. Returns count generated.
    Reads suspects in stored rank order and touches nothing but explanation_ur."""
    client = client or _client_factory()
    suspects = db.execute(
        select(SuspectRow)
        .where(SuspectRow.session_id == session.id, SuspectRow.explanation_ur.is_(None))
        .order_by(SuspectRow.rank)
    ).scalars().all()
    for s in suspects:
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(session, s)},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        s.explanation_ur = (resp.choices[0].message.content or "").strip() or None
    db.commit()
    return len(suspects)
