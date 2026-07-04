-- ZeroBalance schema — PostgreSQL 16
-- audit_ledger is APPEND-ONLY: UPDATE/DELETE blocked by trigger. Never weaken.

-- One EOD reconciliation session per teller per business day
CREATE TABLE eod_sessions (
    id            BIGSERIAL PRIMARY KEY,
    branch_code   TEXT        NOT NULL,
    teller_id     TEXT        NOT NULL,
    business_date DATE        NOT NULL,
    system_cash   NUMERIC(14, 2),          -- expected closing cash per CBS (CSV)
    counted_cash  NUMERIC(14, 2),          -- from the single EOD denomination count
    variance      NUMERIC(14, 2),          -- counted - system
    status        TEXT        NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'flagged', 'resolved', 'closed')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (branch_code, teller_id, business_date)
);

-- Transactions ingested from CBS CSV export (PIBAS format)
CREATE TABLE transactions (
    id             BIGSERIAL PRIMARY KEY,
    session_id     BIGINT      NOT NULL REFERENCES eod_sessions (id),
    cbs_ref        TEXT        NOT NULL,   -- PIBAS transaction reference
    account_number TEXT        NOT NULL,
    txn_type       TEXT        NOT NULL CHECK (txn_type IN ('cash_in', 'cash_out', 'reversal')),
    amount         NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    txn_time       TIMESTAMPTZ NOT NULL,
    narration      TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, cbs_ref)
);
CREATE INDEX idx_transactions_session ON transactions (session_id);

-- ONE denomination count per session (the only teller input).
-- One row per denomination; UNIQUE(session_id, denomination) keeps it a single count.
-- Per-transaction denomination capture is forbidden — no txn FK here, ever.
CREATE TABLE denomination_counts (
    id           BIGSERIAL PRIMARY KEY,
    session_id   BIGINT  NOT NULL REFERENCES eod_sessions (id),
    denomination INTEGER NOT NULL CHECK (denomination IN (5000, 1000, 500, 100, 50, 20, 10, 5, 2, 1)),
    note_count   INTEGER NOT NULL CHECK (note_count >= 0),
    UNIQUE (session_id, denomination)
);

-- Engine output: ranked suspects (top 3-5), deterministic rule evidence.
-- anomaly_score is a SECONDARY signal (display only). explanation_ur is post-hoc Groq text.
CREATE TABLE suspects (
    id             BIGSERIAL PRIMARY KEY,
    session_id     BIGINT   NOT NULL REFERENCES eod_sessions (id),
    transaction_id BIGINT   REFERENCES transactions (id),
    rank           SMALLINT NOT NULL CHECK (rank BETWEEN 1 AND 5),
    signature      TEXT     NOT NULL CHECK (signature IN (
                       'digit_transposition', 'duplicate_posting', 'missed_reversal',
                       'denomination_shortfall', 'cash_inout_miskey', 'wrong_adjacent_account')),
    rule_evidence  JSONB    NOT NULL,      -- reproducible rule facts behind this pick
    anomaly_score  REAL,                   -- Isolation Forest, informational only
    explanation_ur TEXT,                   -- Groq Urdu explanation, post-hoc
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (session_id, rank)
);
CREATE INDEX idx_suspects_session ON suspects (session_id);

-- Append-only audit ledger with hash chain
CREATE TABLE audit_ledger (
    id         BIGSERIAL PRIMARY KEY,
    at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor      TEXT  NOT NULL,
    action     TEXT  NOT NULL,
    payload    JSONB NOT NULL,
    prev_hash  TEXT  NOT NULL,             -- entry_hash of previous row ('GENESIS' for first)
    entry_hash TEXT  NOT NULL UNIQUE
);

CREATE FUNCTION forbid_ledger_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_ledger is append-only';
END;
$$;

CREATE TRIGGER audit_ledger_append_only
    BEFORE UPDATE OR DELETE ON audit_ledger
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();

-- EOD Recon Reports carry the ledger hash at generation time
CREATE TABLE recon_reports (
    id           BIGSERIAL PRIMARY KEY,
    session_id   BIGINT      NOT NULL REFERENCES eod_sessions (id),
    ledger_hash  TEXT        NOT NULL,     -- entry_hash of ledger head when generated
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
