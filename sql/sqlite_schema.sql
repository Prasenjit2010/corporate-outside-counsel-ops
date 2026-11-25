-- CounselGrid local fallback schema (SQLite). Mirrors sql/schema.sql table for
-- table; RLS is replaced by the fact that the database file never leaves the
-- machine it runs on. Conflict entries are protected by append-only triggers.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS outside_firms (
    firm_id                                 INTEGER PRIMARY KEY,
    firm_name                               TEXT    NOT NULL UNIQUE,
    hq_city                                 TEXT    NOT NULL,
    state                                   TEXT    NOT NULL CHECK (length(state) = 2),
    am_law_tier                             TEXT    NOT NULL
        CHECK (am_law_tier IN ('AmLaw 50', 'AmLaw 100', 'Regional Boutique')),
    diversity_certified                     INTEGER NOT NULL DEFAULT 0 CHECK (diversity_certified IN (0, 1)),
    msa_status                              TEXT    NOT NULL
        CHECK (msa_status IN ('Active', 'Under Review', 'Expired')),
    msa_expiration_date                     TEXT    NOT NULL,
    blended_hourly_rate_usd                 REAL    NOT NULL CHECK (blended_hourly_rate_usd > 0),
    alternative_fee_arrangement_available   INTEGER NOT NULL DEFAULT 0
        CHECK (alternative_fee_arrangement_available IN (0, 1)),
    cyber_compliance_score                  INTEGER NOT NULL CHECK (cyber_compliance_score BETWEEN 1 AND 100)
);

CREATE TABLE IF NOT EXISTS firm_practice_capabilities (
    capability_id           INTEGER PRIMARY KEY,
    firm_id                 INTEGER NOT NULL REFERENCES outside_firms (firm_id) ON DELETE CASCADE,
    corporate_domain        TEXT    NOT NULL CHECK (corporate_domain IN (
                                'M&A / Corporate Governance',
                                'International Trade & Customs',
                                'Supply Chain & Commercial Contracts',
                                'IP & Patent Litigation',
                                'Regulatory & Antitrust',
                                'Labor & Employment',
                                'Data Privacy & Cybersecurity')),
    partner_bench_depth     INTEGER NOT NULL CHECK (partner_bench_depth >= 0),
    jurisdiction_coverage   TEXT    NOT NULL,
    UNIQUE (firm_id, corporate_domain)
);

CREATE TABLE IF NOT EXISTS conflict_registry (
    conflict_id             INTEGER PRIMARY KEY,
    firm_id                 INTEGER NOT NULL REFERENCES outside_firms (firm_id) ON DELETE RESTRICT,
    adverse_entity_name     TEXT    NOT NULL CHECK (length(trim(adverse_entity_name)) > 0),
    matter_type             TEXT    NOT NULL,
    conflict_severity       TEXT    NOT NULL CHECK (conflict_severity IN (
                                'Hard Block - Active Representation',
                                'Soft Check - Historical/Waivable',
                                'Clear')),
    logged_date             TEXT    NOT NULL DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS matter_engagements (
    matter_id                           INTEGER PRIMARY KEY,
    internal_department                 TEXT    NOT NULL CHECK (internal_department IN (
                                            'Supply Chain', 'Corporate Affairs', 'M&A', 'HR', 'Engineering')),
    matter_title                        TEXT    NOT NULL,
    corporate_domain                    TEXT    NOT NULL CHECK (corporate_domain IN (
                                            'M&A / Corporate Governance',
                                            'International Trade & Customs',
                                            'Supply Chain & Commercial Contracts',
                                            'IP & Patent Litigation',
                                            'Regulatory & Antitrust',
                                            'Labor & Employment',
                                            'Data Privacy & Cybersecurity')),
    opposing_or_counterparty_entity     TEXT    NOT NULL,
    estimated_budget_usd                REAL    NOT NULL CHECK (estimated_budget_usd > 0),
    selected_firm_id                    INTEGER REFERENCES outside_firms (firm_id) ON DELETE RESTRICT,
    fee_structure                       TEXT    NOT NULL CHECK (fee_structure IN (
                                            'Hourly', 'Capped Fee', 'Fixed Retainer')),
    status                              TEXT    NOT NULL DEFAULT 'Intake' CHECK (status IN (
                                            'Intake', 'Active', 'On Hold', 'Closed')),
    estimated_hours                     INTEGER NOT NULL DEFAULT 0 CHECK (estimated_hours >= 0),
    actual_spend_usd                    REAL    NOT NULL DEFAULT 0 CHECK (actual_spend_usd >= 0),
    created_at                          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS conflict_screening_log (
    screening_id        INTEGER PRIMARY KEY,
    matter_id           INTEGER NOT NULL REFERENCES matter_engagements (matter_id) ON DELETE CASCADE,
    firm_id             INTEGER NOT NULL REFERENCES outside_firms (firm_id) ON DELETE RESTRICT,
    gate_outcome        TEXT    NOT NULL CHECK (gate_outcome IN (
                            'Hard Block', 'Soft Check - Waiver Required', 'Eligible',
                            'Ineligible - MSA', 'Ineligible - No Domain Capability')),
    matched_entity      TEXT,
    match_score         REAL,
    governance_score    REAL,
    screened_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_capabilities_domain  ON firm_practice_capabilities (corporate_domain);
CREATE INDEX IF NOT EXISTS idx_conflicts_firm       ON conflict_registry (firm_id);
CREATE INDEX IF NOT EXISTS idx_matters_firm         ON matter_engagements (selected_firm_id);
CREATE INDEX IF NOT EXISTS idx_matters_department   ON matter_engagements (internal_department);
CREATE INDEX IF NOT EXISTS idx_screening_matter     ON conflict_screening_log (matter_id);

CREATE TRIGGER IF NOT EXISTS conflict_registry_no_update
BEFORE UPDATE ON conflict_registry
BEGIN
    SELECT RAISE(ABORT, 'conflict_registry is append-only');
END;

CREATE TRIGGER IF NOT EXISTS conflict_registry_no_delete
BEFORE DELETE ON conflict_registry
BEGIN
    SELECT RAISE(ABORT, 'conflict_registry is append-only');
END;
