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

-- ============================================================================
-- v2 additions — do not modify v1 tables above destructively.
-- Features: digital excess ledger, cheque capture, pre-post validation log.
-- Cash Movement Ledger (v2.1) is further below.
-- ============================================================================

-- ============================================================================
-- v2.1 addition — Cash Movement Ledger, replaces opening_float_declaration
-- (dropped below; that table was never written or read by any endpoint).
-- Event-typed, denomination-broken, dual/triple-signed, hash-chained,
-- INSERT-only. One row per event — NOT a state machine like excess_ledger.
-- ============================================================================

CREATE TABLE cash_movement_ledger (
    id                 BIGSERIAL PRIMARY KEY,
    event_type         TEXT           NOT NULL CHECK (event_type IN (
                           'day_start', 'reissue', 'handover', 'day_end')),
    teller_id          TEXT           NOT NULL,
    counterparty_id    TEXT,                        -- other teller, handover only
    om_id              TEXT           NOT NULL,
    session_id         TEXT           NOT NULL,      -- groups events into one teller day
    event_time         TIMESTAMPTZ    NOT NULL DEFAULT now(),
    total_amount       NUMERIC(14, 2) NOT NULL CHECK (total_amount > 0),
    signoff_teller      TEXT          NOT NULL,
    signoff_counterparty TEXT,                       -- required only for handover
    signoff_om          TEXT          NOT NULL,
    prev_hash          TEXT           NOT NULL,      -- row_hash of previous row ('GENESIS' for first)
    row_hash            TEXT          NOT NULL UNIQUE
);
CREATE INDEX idx_cash_movement_session ON cash_movement_ledger (session_id);
CREATE INDEX idx_cash_movement_teller_time ON cash_movement_ledger (teller_id, event_time);

CREATE TRIGGER cash_movement_ledger_append_only
    BEFORE UPDATE OR DELETE ON cash_movement_ledger
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();

-- Denomination breakdown per movement event. One row per denomination.
CREATE TABLE cash_movement_denominations (
    id           BIGSERIAL PRIMARY KEY,
    movement_id  BIGINT  NOT NULL REFERENCES cash_movement_ledger (id),
    denomination INTEGER NOT NULL CHECK (denomination IN (5000, 1000, 500, 100, 50, 20, 10)),
    count        INTEGER NOT NULL CHECK (count >= 0),
    amount       NUMERIC(14, 2) GENERATED ALWAYS AS (denomination * count) STORED,
    UNIQUE (movement_id, denomination)
);
CREATE INDEX idx_cash_movement_denom_movement ON cash_movement_denominations (movement_id);

-- Digital Excess Ledger — flagship v2 feature.
-- Append-only event table. Each row is a state event on a case_ref.
-- Dual sign-off = ('opened' by teller) + ('countersigned' by different actor).
-- Close requires prior countersign. State-machine rules enforced in service layer.
-- Hash chain is GLOBAL across the table (matches audit_ledger pattern).
CREATE TABLE excess_ledger (
    id             BIGSERIAL PRIMARY KEY,
    case_ref       UUID           NOT NULL,     -- shared across events of one entry
    event_seq      INTEGER        NOT NULL CHECK (event_seq >= 1),
    event_type     TEXT           NOT NULL CHECK (event_type IN (
                       'opened', 'countersigned', 'closed')),
    branch_code    TEXT           NOT NULL,
    teller_id      TEXT           NOT NULL,
    business_date  DATE           NOT NULL,
    entry_kind     TEXT           NOT NULL CHECK (entry_kind IN ('excess', 'short')),
    amount         NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    actor          TEXT           NOT NULL,     -- teller_id for opened; officer_id for countersigned/closed
    note           TEXT,                        -- reason on open; resolution on close
    at             TIMESTAMPTZ    NOT NULL DEFAULT now(),
    prev_hash      TEXT           NOT NULL,     -- entry_hash of previous row ('GENESIS' for first)
    entry_hash     TEXT           NOT NULL UNIQUE,
    UNIQUE (case_ref, event_seq)
);
CREATE INDEX idx_excess_ledger_case ON excess_ledger (case_ref);
CREATE INDEX idx_excess_ledger_date ON excess_ledger (business_date);

CREATE TRIGGER excess_ledger_append_only
    BEFORE UPDATE OR DELETE ON excess_ledger
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();

-- Cheque capture — sidecar artifact (parallel to CBS, not in its write path).
-- Denomination-out breakdown must sum to amount (enforced in service layer).
CREATE TABLE cheque_transactions (
    id                BIGSERIAL PRIMARY KEY,
    branch_code       TEXT           NOT NULL,
    teller_id         TEXT           NOT NULL,
    business_date     DATE           NOT NULL,
    micr              TEXT           NOT NULL,     -- MICR line as captured
    account_number    TEXT           NOT NULL,
    amount            NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    denomination_out  JSONB          NOT NULL,     -- {"5000": 10, "1000": 50, ...}
    captured_at       TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX idx_cheque_teller_date ON cheque_transactions (teller_id, business_date);

-- Pre-post validation log — feeds the demo screen. NOT wired to CBS write path.
-- Each row records one check firing on typed input. Not append-only.
CREATE TABLE validation_log (
    id             BIGSERIAL PRIMARY KEY,
    teller_id      TEXT           NOT NULL,
    check_name     TEXT           NOT NULL CHECK (check_name IN (
                       'denom_sum', 'cnic_name_match', 'duplicate_check',
                       'large_amount_confirm', 'sanity')),
    input_hash     TEXT           NOT NULL,     -- SHA-256 of input payload
    passed         BOOLEAN        NOT NULL,
    failed_reason  TEXT,
    checked_at     TIMESTAMPTZ    NOT NULL DEFAULT now()
);
CREATE INDEX idx_validation_log_teller ON validation_log (teller_id, checked_at);
