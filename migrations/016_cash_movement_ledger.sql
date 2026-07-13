-- Migration 016 — Cash Movement Ledger (v2.1)
--
-- For existing (non-fresh) dev volumes only. Fresh bring-up
-- (`docker compose down -v && up --build`) applies this via schema.sql
-- directly through /docker-entrypoint-initdb.d and does NOT need this file.
--
-- opening_float_declaration is dropped, not migrated into a VIEW: it was
-- never written to by any endpoint (IngestMeta.opening_float, the value the
-- matching engine actually uses, is a teller-typed scalar passed at
-- CSV-ingest time and was never connected to this table). Verify zero rows
-- before running this in any environment:
--
--   SELECT COUNT(*) FROM opening_float_declaration;
--
-- Idempotent: guarded with IF EXISTS / IF NOT EXISTS throughout.

BEGIN;

DROP TABLE IF EXISTS opening_float_declaration;

CREATE TABLE IF NOT EXISTS cash_movement_ledger (
    id                    BIGSERIAL PRIMARY KEY,
    event_type            TEXT           NOT NULL CHECK (event_type IN (
                              'day_start', 'reissue', 'handover', 'day_end')),
    teller_id             TEXT           NOT NULL,
    counterparty_id       TEXT,
    om_id                 TEXT           NOT NULL,
    session_id            TEXT           NOT NULL,
    event_time            TIMESTAMPTZ    NOT NULL DEFAULT now(),
    total_amount          NUMERIC(14, 2) NOT NULL CHECK (total_amount > 0),
    signoff_teller        TEXT           NOT NULL,
    signoff_counterparty  TEXT,
    signoff_om            TEXT           NOT NULL,
    prev_hash             TEXT           NOT NULL,
    row_hash              TEXT           NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_cash_movement_session ON cash_movement_ledger (session_id);
CREATE INDEX IF NOT EXISTS idx_cash_movement_teller_time ON cash_movement_ledger (teller_id, event_time);

DROP TRIGGER IF EXISTS cash_movement_ledger_append_only ON cash_movement_ledger;
CREATE TRIGGER cash_movement_ledger_append_only
    BEFORE UPDATE OR DELETE ON cash_movement_ledger
    FOR EACH ROW EXECUTE FUNCTION forbid_ledger_mutation();

CREATE TABLE IF NOT EXISTS cash_movement_denominations (
    id           BIGSERIAL PRIMARY KEY,
    movement_id  BIGINT  NOT NULL REFERENCES cash_movement_ledger (id),
    denomination INTEGER NOT NULL CHECK (denomination IN (5000, 1000, 500, 100, 50, 20, 10)),
    count        INTEGER NOT NULL CHECK (count >= 0),
    amount       NUMERIC(14, 2) GENERATED ALWAYS AS (denomination * count) STORED,
    UNIQUE (movement_id, denomination)
);
CREATE INDEX IF NOT EXISTS idx_cash_movement_denom_movement ON cash_movement_denominations (movement_id);

COMMIT;
