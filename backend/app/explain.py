"""Groq explanation layer — post-hoc only.

The engine has already decided and ranked. This module turns each stored
suspect's rule evidence into a short explanation for the teller, in Urdu or
English per the `lang` toggle (default Urdu).
It must never add, remove, reorder, or re-score suspects.
Account numbers are masked before anything leaves the box.

Note: explanations persist in the existing `explanation_ur` column regardless
of which language they were generated in (no schema change made here — flag
if you want a dedicated `explanation_lang` column instead). Because of that,
switching languages on a session that already has explanations requires
`force=True` to regenerate and overwrite; otherwise the previously-generated
text stays as-is.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from .cheque import ChequeVariance, NoVarianceError, describe_variance
from .config import settings
from .db import append_ledger
from .db_models import EodSessionRow, SuspectRow
from .excess_ledger import CaseView, get_case

Lang = Literal["ur", "en"]

SIGNATURE_UR = {
    "digit_transposition": "ہندسوں کی ادلا بدلی",
    "duplicate_posting": "دوہری پوسٹنگ",
    "missed_reversal": "ریورسل درج نہیں ہوا",
    "denomination_shortfall": "نوٹوں کی کمی",
    "cash_inout_miskey": "کیش اِن/آؤٹ کا غلط اندراج",
    "wrong_adjacent_account": "غلط اکاؤنٹ میں اندراج",
}

SIGNATURE_EN = {
    "digit_transposition": "digit transposition",
    "duplicate_posting": "duplicate posting",
    "missed_reversal": "missed reversal",
    "denomination_shortfall": "denomination shortfall",
    "cash_inout_miskey": "cash in/out miskey",
    "wrong_adjacent_account": "wrong adjacent account",
}

SYSTEM_PROMPTS = {
    "ur": (
        "You are the explanation assistant inside ZeroBalance, a cash-reconciliation "
        "co-pilot for bank tellers in Pakistan. The deterministic matching engine has "
        "ALREADY identified and ranked the suspect transactions — that decision is final. "
        "Your only job: explain in simple Urdu why the engine flagged the given suspect, "
        "so the teller can verify it quickly.\n"
        "Rules: 2-3 short sentences, Urdu script only, numbers in western digits (e.g. 66,400). "
        "Use amounts and transaction references exactly as given. Do not invent facts, do not "
        "suggest other suspects, do not question the ranking, and do not declare anyone guilty — "
        "explain the evidence only."
    ),
    "en": (
        "You are the explanation assistant inside ZeroBalance, a cash-reconciliation "
        "co-pilot for bank tellers in Pakistan. The deterministic matching engine has "
        "ALREADY identified and ranked the suspect transactions — that decision is final. "
        "Your only job: explain in plain English why the engine flagged the given suspect, "
        "so the teller can verify it quickly.\n"
        "Rules: 2-3 short sentences, English only, numbers in western digits (e.g. 66,400). "
        "Use amounts and transaction references exactly as given. Do not invent facts, do not "
        "suggest other suspects, do not question the ranking, and do not declare anyone guilty — "
        "explain the evidence only."
    ),
}

_MASK_KEYS = {"account", "posted_account", "intended_account"}


class _ChatClient(Protocol):  # what we need from groq.Groq
    chat: Any


def _client_factory() -> _ChatClient:
    from groq import Groq

    return Groq(api_key=settings.groq_api_key)


def mask_account(account: str) -> str:
    return f"****{account[-4:]}" if len(account) > 4 else "****"


def mask_cnic(cnic: str) -> str:
    digits = cnic.replace("-", "")
    return f"*********{digits[-4:]}" if len(digits) > 4 else "****"


_CNIC_RX = re.compile(r"\d{5}-\d{7}-\d")
_LONG_DIGITS_RX = re.compile(r"\d{6,}")


def redact_pii(text: str | None) -> str | None:
    """Scrub CNIC-shaped and account-number-shaped (6+ digit) substrings out
    of free text before it reaches a prompt. Used for fields a teller can
    type anything into (e.g. Excess Ledger notes), where there's no
    dedicated account/CNIC column to mask instead."""
    if not text:
        return text
    text = _CNIC_RX.sub(lambda m: mask_cnic(m.group()), text)
    text = _LONG_DIGITS_RX.sub(lambda m: mask_account(m.group()), text)
    return text


def build_prompt(session: EodSessionRow, suspect: SuspectRow, lang: Lang = "ur") -> str:
    ev = suspect.rule_evidence
    detail = {
        k: (mask_account(str(v)) if k in _MASK_KEYS else v)
        for k, v in ev.get("detail", {}).items()
    }
    signature_label = (
        f"{suspect.signature} ({SIGNATURE_UR[suspect.signature]})" if lang == "ur"
        else f"{suspect.signature} ({SIGNATURE_EN[suspect.signature]})"
    )
    lines = [
        f"EOD variance for teller {session.teller_id} on {session.business_date}: "
        f"{int(session.variance or 0):+,} PKR "
        f"(counted {int(session.counted_cash or 0):,}, system {int(session.system_cash or 0):,}).",
        f"Suspect rank {suspect.rank} of the engine's list.",
        f"Error type: {signature_label}.",
        "Transaction reference(s): "
        f"{', '.join(ev.get('txn_refs', [])) or 'none (till-count level)'}.",
        f"Cash impact if confirmed: {ev.get('cash_delta', 0):+,} PKR.",
        f"Evidence: {detail}.",
        f"Explain this suspicion to the teller in {'Urdu' if lang == 'ur' else 'English'}.",
    ]
    return "\n".join(lines)


def explain_suspects(db: Session, session: EodSessionRow, lang: Lang = "ur",
                     client: _ChatClient | None = None, force: bool = False) -> int:
    """Fill explanation_ur for suspects that lack one (or all of them, if
    force=True — needed when the teller flips the language toggle on a
    session that already has explanations, since this column doesn't track
    which language it was last written in). Returns count generated.
    Touches nothing but explanation_ur."""
    if lang not in SYSTEM_PROMPTS:
        raise ValueError(f"unsupported lang: {lang!r} (expected 'ur' or 'en')")
    client = client or _client_factory()
    query = select(SuspectRow).where(SuspectRow.session_id == session.id)
    if not force:
        query = query.where(SuspectRow.explanation_ur.is_(None))
    suspects = db.execute(query.order_by(SuspectRow.rank)).scalars().all()
    for s in suspects:
        resp = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPTS[lang]},
                {"role": "user", "content": build_prompt(session, s, lang)},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        s.explanation_ur = (resp.choices[0].message.content or "").strip() or None
    db.commit()
    return len(suspects)


# --- v2: Digital Excess Ledger openings -------------------------------------

SYSTEM_PROMPTS_EXCESS = {
    "ur": (
        "You are the explanation assistant inside ZeroBalance, a cash-reconciliation "
        "co-pilot for bank tellers in Pakistan. A teller has ALREADY opened a Digital "
        "Excess Ledger case for a till excess or short — that fact is final and already "
        "recorded. Your only job: explain in simple Urdu what this entry means and why "
        "dual sign-off plus a resolution note are required before it can close.\n"
        "Rules: 2-3 short sentences, Urdu script only, numbers in western digits. Cite "
        "the teller's note only if one was provided. Do not invent a cause for the "
        "discrepancy, do not accuse anyone, do not decide whether it will be approved."
    ),
    "en": (
        "You are the explanation assistant inside ZeroBalance, a cash-reconciliation "
        "co-pilot for bank tellers in Pakistan. A teller has ALREADY opened a Digital "
        "Excess Ledger case for a till excess or short — that fact is final and already "
        "recorded. Your only job: explain in plain English what this entry means and why "
        "dual sign-off plus a resolution note are required before it can close.\n"
        "Rules: 2-3 short sentences, English only, numbers in western digits. Cite the "
        "teller's note only if one was provided. Do not invent a cause for the "
        "discrepancy, do not accuse anyone, do not decide whether it will be approved."
    ),
}


def build_excess_prompt(view: CaseView, lang: Lang = "ur") -> str:
    masked_note = redact_pii(view.reason)
    signers = f"Opened by {view.opener}."
    if view.countersigner:
        signers += f" Countersigned by {view.countersigner}."
    if view.closer:
        signers += f" Closed by {view.closer}."
    lines = [
        f"{view.entry_kind.upper()} entry — branch {view.branch_code}, teller "
        f"{view.teller_id}, business date {view.business_date}.",
        f"Amount: {view.amount} PKR. Current state: {view.state}.",
        signers,
        f"Teller's note: {masked_note or 'none provided'}.",
        f"Explain this cash {view.entry_kind} to bank staff in "
        f"{'Urdu' if lang == 'ur' else 'English'}.",
    ]
    return "\n".join(lines)


def explain_excess_case(
    db: Session, case_ref: str, lang: Lang = "ur", client: _ChatClient | None = None,
) -> str:
    """Explain an already-opened Excess Ledger case. Post-hoc only — the
    case's state is never touched. Not idempotent: every call is an
    explicit action and writes a fresh EXCESS_EXPLAINED audit_ledger row
    (there's no column to cache the result against without a schema
    change)."""
    if lang not in SYSTEM_PROMPTS_EXCESS:
        raise ValueError(f"unsupported lang: {lang!r} (expected 'ur' or 'en')")
    view = get_case(db, case_ref)
    client = client or _client_factory()
    resp = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPTS_EXCESS[lang]},
            {"role": "user", "content": build_excess_prompt(view, lang)},
        ],
        temperature=0.3,
        max_tokens=300,
    )
    text = (resp.choices[0].message.content or "").strip()
    append_ledger(db, actor="system", action="EXCESS_EXPLAINED", payload={
        "case_ref": case_ref, "lang": lang, "explanation": text,
    })
    db.commit()
    return text


# --- v2: Cheque capture variance --------------------------------------------

SYSTEM_PROMPTS_CHEQUE = {
    "ur": (
        "You are the explanation assistant inside ZeroBalance, a cash-reconciliation "
        "co-pilot for bank tellers in Pakistan. A cheque capture has ALREADY been "
        "rejected by the deterministic validation service — that decision is final. "
        "Your only job: explain in simple Urdu why the capture was rejected, so the "
        "teller knows what to re-check before recapturing.\n"
        "Rules: 2-3 short sentences, Urdu script only, numbers in western digits. "
        "Describe only the mismatch already detected — do not allege fraud, do not "
        "invent other causes, do not decide whether to allow a retry."
    ),
    "en": (
        "You are the explanation assistant inside ZeroBalance, a cash-reconciliation "
        "co-pilot for bank tellers in Pakistan. A cheque capture has ALREADY been "
        "rejected by the deterministic validation service — that decision is final. "
        "Your only job: explain in plain English why the capture was rejected, so the "
        "teller knows what to re-check before recapturing.\n"
        "Rules: 2-3 short sentences, English only, numbers in western digits. Describe "
        "only the mismatch already detected — do not allege fraud, do not invent other "
        "causes, do not decide whether to allow a retry."
    ),
}


def build_cheque_variance_prompt(
    variance: ChequeVariance, *, branch_code: str, teller_id: str,
    business_date: str, lang: Lang = "ur",
) -> str:
    reasons = []
    if "denom_sum" in variance.mismatch_types:
        reasons.append(
            f"denomination-out total {variance.denom_sum_total} PKR does not equal "
            f"the cheque amount {variance.amount} PKR"
        )
    if "micr_account" in variance.mismatch_types:
        masked_micr = (
            mask_account(variance.micr_account) if variance.micr_account else "unreadable"
        )
        reasons.append(
            f"the account encoded on the cheque's MICR line ({masked_micr}) does not "
            f"match the typed account number ({mask_account(variance.account_number)})"
        )
    lines = [
        f"Cheque capture rejected — branch {branch_code}, teller {teller_id}, "
        f"business date {business_date}.",
        f"Detected variance: {'; '.join(reasons)}.",
        f"Explain this rejection to the teller in {'Urdu' if lang == 'ur' else 'English'}.",
    ]
    return "\n".join(lines)


@dataclass(frozen=True)
class ChequeExplanation:
    text: str
    mismatch_types: list[str]


def explain_cheque_variance(
    db: Session, *, branch_code: str, teller_id: str, business_date: date,
    micr: str, account_number: str, amount: Decimal,
    denomination_out: dict[str, int], lang: Lang = "ur",
    client: _ChatClient | None = None,
) -> ChequeExplanation:
    """Explain why a cheque capture would be/was rejected. Stateless w.r.t.
    cheque_transactions — never inserts a row, valid or not. Raises
    NoVarianceError if the input actually passes validation."""
    if lang not in SYSTEM_PROMPTS_CHEQUE:
        raise ValueError(f"unsupported lang: {lang!r} (expected 'ur' or 'en')")
    variance = describe_variance(
        micr=micr, account_number=account_number, amount=amount,
        denomination_out=denomination_out,
    )
    if variance is None:
        raise NoVarianceError("cheque passes validation; nothing to explain")
    client = client or _client_factory()
    resp = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPTS_CHEQUE[lang]},
            {"role": "user", "content": build_cheque_variance_prompt(
                variance, branch_code=branch_code, teller_id=teller_id,
                business_date=business_date.isoformat(), lang=lang,
            )},
        ],
        temperature=0.3,
        max_tokens=300,
    )
    text = (resp.choices[0].message.content or "").strip()
    append_ledger(db, actor="system", action="CHEQUE_EXPLAINED", payload={
        "branch": branch_code, "teller": teller_id,
        "business_date": business_date.isoformat(),
        "mismatch_types": variance.mismatch_types, "lang": lang,
        "explanation": text,
    })
    db.commit()
    return ChequeExplanation(text=text, mismatch_types=variance.mismatch_types)
