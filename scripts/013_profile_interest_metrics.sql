-- Migration: Add profile-aware research interest metrics tables
-- This creates NEW tables for profile-specific interest tracking
-- DOES NOT modify or delete any existing tables/data

-- Table: profile_paper_interests
-- Links papers to profile-specific research interests
-- Similar to paper_research_interests but uses profile_research_interests
CREATE TABLE IF NOT EXISTS profile_paper_interests (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    profile_interest_id INTEGER NOT NULL REFERENCES profile_research_interests(id) ON DELETE CASCADE,
    similarity_score FLOAT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(paper_id, profile_interest_id)
);

-- Indexes for profile_paper_interests
CREATE INDEX IF NOT EXISTS idx_profile_paper_interests_paper
    ON profile_paper_interests(paper_id);
CREATE INDEX IF NOT EXISTS idx_profile_paper_interests_interest
    ON profile_paper_interests(profile_interest_id);
CREATE INDEX IF NOT EXISTS idx_profile_paper_interests_similarity
    ON profile_paper_interests(similarity_score DESC);

-- Table: profile_interest_metrics
-- Time-series metrics for profile-specific research interests
-- Similar to research_interest_metrics but uses profile_research_interests
CREATE TABLE IF NOT EXISTS profile_interest_metrics (
    id SERIAL PRIMARY KEY,
    profile_interest_id INTEGER NOT NULL REFERENCES profile_research_interests(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    period_type VARCHAR(20) NOT NULL CHECK (period_type IN ('week', 'month', 'quarter')),
    doc_count INTEGER DEFAULT 0,
    avg_relevance_score FLOAT,
    avg_paper_score FLOAT,
    growth_rate FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(profile_interest_id, period_start, period_type)
);

-- Indexes for profile_interest_metrics
CREATE INDEX IF NOT EXISTS idx_profile_interest_metrics_interest
    ON profile_interest_metrics(profile_interest_id);
CREATE INDEX IF NOT EXISTS idx_profile_interest_metrics_period
    ON profile_interest_metrics(period_start DESC, period_type);
CREATE INDEX IF NOT EXISTS idx_profile_interest_metrics_type_date
    ON profile_interest_metrics(period_type, period_start DESC);

-- Add composite index for dashboard queries
CREATE INDEX IF NOT EXISTS idx_profile_interest_metrics_dashboard
    ON profile_interest_metrics(profile_interest_id, period_type, period_start DESC);
