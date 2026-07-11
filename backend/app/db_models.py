"""SQLAlchemy mappings for the existing schema. schema.sql owns the DDL —
never call create_all; the audit ledger is append-only (DB trigger enforced)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, Date, Float, ForeignKey, Integer, SmallInteger, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EodSessionRow(Base):
    __tablename__ = "eod_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_code: Mapped[str] = mapped_column(Text)
    teller_id: Mapped[str] = mapped_column(Text)
    business_date: Mapped[date] = mapped_column(Date)
    system_cash: Mapped[Decimal | None]
    counted_cash: Mapped[Decimal | None]
    variance: Mapped[Decimal | None]
    status: Mapped[str] = mapped_column(Text, default="open")
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class TransactionRow(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("eod_sessions.id"))
    cbs_ref: Mapped[str] = mapped_column(Text)
    account_number: Mapped[str] = mapped_column(Text)
    txn_type: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal]
    txn_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    narration: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class DenominationCountRow(Base):
    __tablename__ = "denomination_counts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("eod_sessions.id"))
    denomination: Mapped[int] = mapped_column(Integer)
    note_count: Mapped[int] = mapped_column(Integer)


class SuspectRow(Base):
    __tablename__ = "suspects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("eod_sessions.id"))
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"))
    rank: Mapped[int] = mapped_column(SmallInteger)
    signature: Mapped[str] = mapped_column(Text)
    rule_evidence: Mapped[dict] = mapped_column(JSONB)
    anomaly_score: Mapped[float | None] = mapped_column(Float)
    explanation_ur: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class AuditLedgerRow(Base):
    __tablename__ = "audit_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONB)
    prev_hash: Mapped[str] = mapped_column(Text)
    entry_hash: Mapped[str] = mapped_column(Text)


class ReconReportRow(Base):
    __tablename__ = "recon_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("eod_sessions.id"))
    ledger_hash: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


# ---------------------------------------------------------------------------
# v2 additions — do not add relationships; service layer handles joins.
# ---------------------------------------------------------------------------


class OpeningFloatDeclarationRow(Base):
    __tablename__ = "opening_float_declaration"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_code: Mapped[str] = mapped_column(Text)
    teller_id: Mapped[str] = mapped_column(Text)
    business_date: Mapped[date] = mapped_column(Date)
    denominations: Mapped[dict] = mapped_column(JSONB)
    total_amount: Mapped[Decimal]
    signed_by: Mapped[str] = mapped_column(Text)
    signed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class ExcessLedgerRow(Base):
    """Append-only event row for the Digital Excess Ledger.

    One case is a stream of rows sharing case_ref, seq'd by event_seq:
    opened -> countersigned -> closed. State-machine rules live in service
    layer; DB only enforces append-only + hash chain + CHECK constraints.
    """

    __tablename__ = "excess_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    case_ref: Mapped[str] = mapped_column(UUID(as_uuid=False))
    event_seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(Text)  # opened | countersigned | closed
    branch_code: Mapped[str] = mapped_column(Text)
    teller_id: Mapped[str] = mapped_column(Text)
    business_date: Mapped[date] = mapped_column(Date)
    entry_kind: Mapped[str] = mapped_column(Text)  # excess | short
    amount: Mapped[Decimal]
    actor: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    prev_hash: Mapped[str] = mapped_column(Text)
    entry_hash: Mapped[str] = mapped_column(Text)


class ChequeTransactionRow(Base):
    __tablename__ = "cheque_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    branch_code: Mapped[str] = mapped_column(Text)
    teller_id: Mapped[str] = mapped_column(Text)
    business_date: Mapped[date] = mapped_column(Date)
    micr: Mapped[str] = mapped_column(Text)
    account_number: Mapped[str] = mapped_column(Text)
    amount: Mapped[Decimal]
    denomination_out: Mapped[dict] = mapped_column(JSONB)
    captured_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )


class ValidationLogRow(Base):
    """Pre-post validation log. Fed by demo endpoints only — not wired to CBS."""

    __tablename__ = "validation_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    teller_id: Mapped[str] = mapped_column(Text)
    check_name: Mapped[str] = mapped_column(Text)
    input_hash: Mapped[str] = mapped_column(Text)
    passed: Mapped[bool] = mapped_column(Boolean)
    failed_reason: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
