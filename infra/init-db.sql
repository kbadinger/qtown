-- Qtown v2 — Database Initialization
-- Creates per-service schemas and enables pgvector extension.
-- Runs automatically on first postgres container start.

-- Enable pgvector for RAG embeddings (Academy)
CREATE EXTENSION IF NOT EXISTS vector;

-- Per-service schemas
CREATE SCHEMA IF NOT EXISTS core;       -- Town Core (existing simulation)
CREATE SCHEMA IF NOT EXISTS market;     -- Market District order book
CREATE SCHEMA IF NOT EXISTS academy;    -- Academy RAG + model stats
CREATE SCHEMA IF NOT EXISTS fortress;   -- Fortress audit logs

-- Academy: vector store for RAG
CREATE TABLE IF NOT EXISTS academy.event_embeddings (
    id          SERIAL PRIMARY KEY,
    event_id    INTEGER NOT NULL,
    tick        INTEGER NOT NULL,
    event_type  VARCHAR(100),
    text        TEXT NOT NULL,
    embedding   vector(1024),  -- Ollama nomic-embed-text dimension
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_embeddings_vector
    ON academy.event_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Market District: order and trade history
CREATE TABLE IF NOT EXISTS market.orders (
    id          VARCHAR(64) PRIMARY KEY,
    npc_id      INTEGER NOT NULL,
    resource    VARCHAR(50) NOT NULL,
    side        VARCHAR(3) NOT NULL,  -- BID or ASK
    price       NUMERIC(12,4) NOT NULL,
    quantity    NUMERIC(12,4) NOT NULL,
    status      VARCHAR(20) DEFAULT 'open',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market.trades (
    id              VARCHAR(64) PRIMARY KEY,
    buy_order_id    VARCHAR(64) REFERENCES market.orders(id),
    sell_order_id   VARCHAR(64) REFERENCES market.orders(id),
    resource        VARCHAR(50) NOT NULL,
    price           NUMERIC(12,4) NOT NULL,
    quantity        NUMERIC(12,4) NOT NULL,
    executed_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Fortress: audit log
CREATE TABLE IF NOT EXISTS fortress.validation_log (
    id          SERIAL PRIMARY KEY,
    event_id    VARCHAR(64),
    rule_name   VARCHAR(100) NOT NULL,
    valid       BOOLEAN NOT NULL,
    message     TEXT,
    checked_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Academy: model routing stats
CREATE TABLE IF NOT EXISTS academy.model_routing_log (
    id          SERIAL PRIMARY KEY,
    task_type   VARCHAR(50) NOT NULL,
    model_name  VARCHAR(100) NOT NULL,
    tier        VARCHAR(20) NOT NULL,
    latency_ms  REAL,
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    cost_usd    REAL DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Grant all schemas to qtown user
GRANT ALL ON SCHEMA core, market, academy, fortress TO qtown;
GRANT ALL ON ALL TABLES IN SCHEMA core, market, academy, fortress TO qtown;
GRANT ALL ON ALL SEQUENCES IN SCHEMA core, market, academy, fortress TO qtown;
