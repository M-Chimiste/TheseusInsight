-- Migration: Add indexes for Research Timeline View
-- Optimizes timeline queries with period-based lookups and paper retrieval

-- Index for efficient timeline metric lookups by topic and period
-- Supports descending order for most-recent-first queries
CREATE INDEX IF NOT EXISTS idx_topic_metrics_timeline
ON topic_metrics (topic_id, period_type, period_start DESC);

-- Index for paper date lookups within topic context
-- Used when fetching key papers for each timeline period
CREATE INDEX IF NOT EXISTS idx_papers_date
ON papers (date);

-- Composite index on paper_topics for relevance-ordered paper retrieval
-- Optimizes the key papers query that joins papers with topic assignments
CREATE INDEX IF NOT EXISTS idx_paper_topics_relevance
ON paper_topics (topic_id, relevance_score DESC);
