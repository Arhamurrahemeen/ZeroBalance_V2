"""DB access + append-only audit ledger with hash chain.

entry_hash = sha256(prev_hash | actor | action | canonical-json(payload)).
The DB trigger blocks UPDATE/DELETE on audit_ledger; this module only appends.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from .config import settings
from .db_models import AuditLedgerRow

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def get_db() -> Iterator[Session]:
    with Session(get_engine()) as db:
        yield db


def _entry_hash(prev: str, actor: str, action: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{prev}|{actor}|{action}|{canonical}".encode()).hexdigest()


def ledger_head(db: Session) -> str:
    row = db.execute(
        select(AuditLedgerRow).order_by(AuditLedgerRow.id.desc()).limit(1)
    ).scalar_one_or_none()
    return row.entry_hash if row else "GENESIS"


def append_ledger(db: Session, actor: str, action: str, payload: dict) -> str:
    prev = ledger_head(db)
    h = _entry_hash(prev, actor, action, payload)
    db.add(AuditLedgerRow(actor=actor, action=action, payload=payload,
                          prev_hash=prev, entry_hash=h))
    return h


def verify_ledger(db: Session) -> tuple[bool, int, str]:
    """Walk the chain; returns (ok, entries_checked, head_hash)."""
    prev = "GENESIS"
    n = 0
    for row in db.execute(select(AuditLedgerRow).order_by(AuditLedgerRow.id)).scalars():
        if row.prev_hash != prev:
            return False, n, prev
        if row.entry_hash != _entry_hash(prev, row.actor, row.action, row.payload):
            return False, n, prev
        prev = row.entry_hash
        n += 1
    return True, n, prev
