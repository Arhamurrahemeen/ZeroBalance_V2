"""PIBAS CSV parsing + recon orchestration (ingest → engine → persist → ledger)."""

from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import append_ledger
from .db_models import DenominationCountRow, EodSessionRow, SuspectRow, TransactionRow
from .engine import SessionInput, TxnInput, analyze, system_cash
from .engine.anomaly import anomaly_scores
from .schemas import IngestMeta, SessionDetail, SessionSummary, SuspectOut

CSV_COLUMNS = [
    "BRANCH_CODE", "TELLER_ID", "TXN_DATE", "TXN_TIME",
    "TXN_REF", "ACCOUNT_NO", "TXN_TYPE", "AMOUNT", "NARRATION",
]
TYPE_MAP = {"CASH_IN": "cash_in", "CASH_OUT": "cash_out", "REVERSAL": "reversal"}


class CsvFormatError(ValueError):
    pass


@dataclass
class ParsedCsv:
    branch: str
    teller: str
    business_date: str
    txns: list[TxnInput]


def parse_pibas_csv(text: str) -> ParsedCsv:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or list(reader.fieldnames) != CSV_COLUMNS:
        raise CsvFormatError(f"expected columns {CSV_COLUMNS}, got {reader.fieldnames}")
    rows = list(reader)
    if not rows:
        raise CsvFormatError("CSV has no transaction rows")

    for key, label in (("BRANCH_CODE", "branch"), ("TELLER_ID", "teller"),
                       ("TXN_DATE", "date")):
        if len({r[key] for r in rows}) != 1:
            raise CsvFormatError(f"CSV must contain exactly one {label}")

    txns: list[TxnInput] = []
    refs: set[str] = set()
    for r in rows:
        if r["TXN_TYPE"] not in TYPE_MAP:
            raise CsvFormatError(f"unknown TXN_TYPE {r['TXN_TYPE']!r} at {r['TXN_REF']}")
        if r["TXN_REF"] in refs:
            raise CsvFormatError(f"duplicate TXN_REF {r['TXN_REF']}")
        refs.add(r["TXN_REF"])
        try:
            amount = int(r["AMOUNT"])
        except ValueError as e:
            raise CsvFormatError(f"bad AMOUNT at {r['TXN_REF']}") from e
        if amount <= 0:
            raise CsvFormatError(f"AMOUNT must be positive at {r['TXN_REF']}")
        narration = r["NARRATION"] or ""
        reverses = narration.removeprefix("REV:") if narration.startswith("REV:") else None
        txns.append(TxnInput(
            ref=r["TXN_REF"], account=r["ACCOUNT_NO"],
            txn_type=TYPE_MAP[r["TXN_TYPE"]], amount=amount,
            time=r["TXN_TIME"], narration=narration, reverses=reverses,
        ))

    known = {t.ref for t in txns}
    for t in txns:
        if t.reverses and t.reverses not in known:
            raise CsvFormatError(f"reversal {t.ref} references unknown txn {t.reverses}")
    return ParsedCsv(rows[0]["BRANCH_CODE"], rows[0]["TELLER_ID"], rows[0]["TXN_DATE"], txns)


def ingest_session(db: Session, csv_text: str, meta: IngestMeta) -> EodSessionRow:
    parsed = parse_pibas_csv(csv_text)
    counted = sum(d * n for d, n in meta.denomination_count.items())
    session_input = SessionInput(
        branch=parsed.branch, teller=parsed.teller, business_date=parsed.business_date,
        opening_float=meta.opening_float, counted_cash=counted,
        denomination_count=meta.denomination_count, txns=parsed.txns,
    )
    sys_cash = system_cash(session_input)
    variance = counted - sys_cash
    suspects = analyze(session_input)
    scores = anomaly_scores(session_input) if suspects else {}

    row = EodSessionRow(
        branch_code=parsed.branch, teller_id=parsed.teller,
        business_date=date.fromisoformat(parsed.business_date),
        system_cash=sys_cash, counted_cash=counted, variance=variance,
        status="flagged" if (variance != 0 or suspects) else "closed",
    )
    db.add(row)
    db.flush()

    txn_ids: dict[str, int] = {}
    for t in parsed.txns:
        txn_row = TransactionRow(
            session_id=row.id, cbs_ref=t.ref, account_number=t.account,
            txn_type=t.txn_type, amount=t.amount,
            txn_time=datetime.fromisoformat(f"{parsed.business_date}T{t.time or '00:00:00'}"),
            narration=t.narration or None,
        )
        db.add(txn_row)
        db.flush()
        txn_ids[t.ref] = txn_row.id

    for denom, count in sorted(meta.denomination_count.items(), reverse=True):
        db.add(DenominationCountRow(session_id=row.id, denomination=denom, note_count=count))

    for s in suspects:
        db.add(SuspectRow(
            session_id=row.id,
            transaction_id=txn_ids.get(s.txn_refs[0]) if s.txn_refs else None,
            rank=s.rank, signature=s.signature,
            rule_evidence={
                "txn_refs": list(s.txn_refs), "cash_delta": s.cash_delta,
                "rule_score": s.rule_score, "detail": s.evidence,
            },
            anomaly_score=max((scores.get(r, 0.0) for r in s.txn_refs), default=None),
        ))

    append_ledger(db, actor=parsed.teller, action="SESSION_INGESTED", payload={
        "session_id": row.id, "branch": parsed.branch, "teller": parsed.teller,
        "business_date": parsed.business_date, "txn_count": len(parsed.txns),
        "system_cash": sys_cash, "counted_cash": counted, "variance": variance,
        "csv_sha256": hashlib.sha256(csv_text.encode()).hexdigest(),
        "suspects": [{"rank": s.rank, "signature": s.signature,
                      "txn_refs": list(s.txn_refs)} for s in suspects],
    })
    db.commit()
    return row


def to_summary(db: Session, row: EodSessionRow) -> SessionSummary:
    suspect_count = len(db.execute(
        select(SuspectRow.id).where(SuspectRow.session_id == row.id)
    ).all())
    return SessionSummary(
        id=row.id, branch_code=row.branch_code, teller_id=row.teller_id,
        business_date=row.business_date.isoformat(),
        system_cash=int(row.system_cash or 0), counted_cash=int(row.counted_cash or 0),
        variance=int(row.variance or 0), status=row.status,
        age_days=(date.today() - row.business_date).days,
        suspect_count=suspect_count,
    )


def to_detail(db: Session, row: EodSessionRow) -> SessionDetail:
    suspects = db.execute(
        select(SuspectRow).where(SuspectRow.session_id == row.id).order_by(SuspectRow.rank)
    ).scalars().all()
    txn_count = len(db.execute(
        select(TransactionRow.id).where(TransactionRow.session_id == row.id)
    ).all())
    denoms = db.execute(
        select(DenominationCountRow).where(DenominationCountRow.session_id == row.id)
    ).scalars().all()
    return SessionDetail(
        **to_summary(db, row).model_dump(),
        txn_count=txn_count,
        denomination_count={d.denomination: d.note_count for d in denoms},
        suspects=[
            SuspectOut(
                rank=s.rank, signature=s.signature,  # type: ignore[arg-type]
                txn_refs=s.rule_evidence.get("txn_refs", []),
                cash_delta=s.rule_evidence.get("cash_delta", 0),
                rule_score=s.rule_evidence.get("rule_score", 0),
                evidence=s.rule_evidence.get("detail", {}),
                anomaly_score=s.anomaly_score,
                explanation_ur=s.explanation_ur,
            )
            for s in suspects
        ],
    )
