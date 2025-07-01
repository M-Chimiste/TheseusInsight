-- Initial schema for Theseus Insight on PostgreSQL 14 + pgvector
-- Run by scripts/setup_database.sh during container bootstrap

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- === Core tables ===

CREATE TABLE IF NOT EXISTS papers (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT NOT NULL,
    date DATE NOT NULL,
    date_run DATE NOT NULL,
    score REAL,
    rationale TEXT,
    related BOOLEAN DEFAULT FALSE,
    cosine_similarity REAL,
    url TEXT UNIQUE,
    embedding_model TEXT,
    embedding vector(768),                -- modern BERT dimensions
    text TEXT,
    summary TEXT,
    keywords_json JSONB
);

-- Full-text search on title + abstract
ALTER TABLE papers
    ADD COLUMN IF NOT EXISTS fts TSVECTOR GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(abstract,'')), 'B')
    ) STORED;

CREATE INDEX IF NOT EXISTS idx_papers_fts ON papers USING GIN (fts);
CREATE INDEX IF NOT EXISTS idx_papers_score ON papers (score DESC);

-- === Logs ===
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    datetime_run TIMESTAMPTZ DEFAULT now()
);

-- === Newsletters ===
CREATE TABLE IF NOT EXISTS newsletters (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    date_sent DATE NOT NULL
);

-- === Podcasts ===
CREATE TABLE IF NOT EXISTS podcasts (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    date DATE NOT NULL,
    script JSONB NOT NULL,
    description TEXT NOT NULL
);

-- === Settings (key-value) ===
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- === Model Providers ===
CREATE TABLE IF NOT EXISTS model_providers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- === Tasks ===
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json JSONB NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ,
    error TEXT,
    result_json JSONB,
    progress REAL DEFAULT 0,
    current_step TEXT,
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
CREATE INDEX IF NOT EXISTS idx_tasks_start_time ON tasks (start_time DESC);

-- === Literature Reviews ===
CREATE TABLE IF NOT EXISTS lit_reviews (
    id SERIAL PRIMARY KEY,
    research_question TEXT NOT NULL,
    summary_json JSONB NOT NULL,
    trace_json JSONB NOT NULL,
    report_text TEXT,
    created_ts TIMESTAMPTZ DEFAULT now()
);

-- === Research Runs ===
CREATE TABLE IF NOT EXISTS research_runs (
    id SERIAL PRIMARY KEY,
    task_id TEXT UNIQUE NOT NULL,
    research_question TEXT NOT NULL,
    status TEXT NOT NULL,
    config_json JSONB,
    created_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    final_answer TEXT,
    generation_summary TEXT,
    statistics_json JSONB,
    sub_queries_json JSONB,
    sources_gathered_json JSONB,
    judged_sources_json JSONB,
    evidence_json JSONB,
    compressed_notes TEXT,
    workflow_messages_json JSONB,
    research_loop_count INTEGER DEFAULT 0,
    is_sufficient BOOLEAN DEFAULT FALSE,
    save_to_library BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_research_runs_status ON research_runs (status);
CREATE INDEX IF NOT EXISTS idx_research_runs_created_at ON research_runs (created_at DESC);

-- === Research Agent State ===
CREATE TABLE IF NOT EXISTS research_agent_state (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES research_runs(task_id) ON DELETE CASCADE,
    node_name TEXT NOT NULL,
    state_json JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_agent_state_task_id ON research_agent_state (task_id);

-- === Paper Fulltext ===
CREATE TABLE IF NOT EXISTS paper_fulltext (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER UNIQUE NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(768),
    embedding_model TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- FTS for fulltext content
ALTER TABLE paper_fulltext
    ADD COLUMN IF NOT EXISTS fts TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', coalesce(content,''))) STORED;
CREATE INDEX IF NOT EXISTS idx_paper_fulltext_fts ON paper_fulltext USING GIN (fts);
CREATE INDEX IF NOT EXISTS idx_paper_fulltext_paper_id ON paper_fulltext (paper_id);

-- === Mind-Map Reports ===
CREATE TABLE IF NOT EXISTS mindmap_reports (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    seed_paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    seed_paper_title TEXT NOT NULL,
    mindmap_data_json JSONB NOT NULL,
    parameters_json JSONB NOT NULL,
    statistics_json JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mindmap_reports_created_at ON mindmap_reports (created_at DESC);

-- === Model Catalog ===
CREATE TABLE IF NOT EXISTS model_catalog (
    id SERIAL PRIMARY KEY,
    alias TEXT NOT NULL,
    model_string TEXT NOT NULL,
    provider_name TEXT NOT NULL,
    model_type TEXT NOT NULL,
    description TEXT,
    max_new_tokens INTEGER,
    temperature REAL,
    num_ctx INTEGER,
    trust_remote_code BOOLEAN DEFAULT FALSE,
    tags_json JSONB,
    is_favorite BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_model_catalog_alias ON model_catalog (alias);
CREATE INDEX IF NOT EXISTS idx_model_catalog_provider ON model_catalog (provider_name);
CREATE INDEX IF NOT EXISTS idx_model_catalog_type ON model_catalog (model_type);
CREATE INDEX IF NOT EXISTS idx_model_catalog_favorite ON model_catalog (is_favorite);

-- Additional tables to be ported later (tasks, mindmap, research_* etc.) 