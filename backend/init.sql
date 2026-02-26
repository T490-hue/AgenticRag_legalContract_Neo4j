-- Legal Graph RAG - PostgreSQL Schema

CREATE TABLE IF NOT EXISTS contracts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename        VARCHAR(255) NOT NULL,
    title           VARCHAR(500),
    contract_type   VARCHAR(100),
    effective_date  VARCHAR(100),
    expiry_date     VARCHAR(100),
    jurisdiction    VARCHAR(200),
    parties         TEXT[],
    file_size       INTEGER,
    status          VARCHAR(50) DEFAULT 'pending',
    error_msg       TEXT,
    chunk_count     INTEGER DEFAULT 0,
    clause_count    INTEGER DEFAULT 0,
    risk_score      FLOAT DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS query_history (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question              TEXT NOT NULL,
    graph_answer          TEXT,
    baseline_answer       TEXT,
    extractive_answer     TEXT,
    extractive_confidence FLOAT,
    graph_chunks          INTEGER,
    graph_only_chunks     INTEGER,
    graph_latency         FLOAT,
    baseline_latency      FLOAT,
    created_at            TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processing_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID REFERENCES contracts(id),
    stage       VARCHAR(100),
    status      VARCHAR(50),
    message     TEXT,
    duration_ms INTEGER,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clauses_extracted (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     UUID REFERENCES contracts(id),
    clause_type     VARCHAR(100),
    clause_text     TEXT,
    risk_level      VARCHAR(20),
    risk_reason     TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID REFERENCES contracts(id),
    flag_type   VARCHAR(100),
    severity    VARCHAR(20),
    description TEXT,
    clause_ref  TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contracts_status   ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_type     ON contracts(contract_type);
CREATE INDEX IF NOT EXISTS idx_query_history_date ON query_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_clauses_contract   ON clauses_extracted(contract_id);
CREATE INDEX IF NOT EXISTS idx_clauses_type       ON clauses_extracted(clause_type);
CREATE INDEX IF NOT EXISTS idx_risk_flags_contract ON risk_flags(contract_id);
CREATE INDEX IF NOT EXISTS idx_risk_flags_severity ON risk_flags(severity);
