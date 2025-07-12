-- Optimize indexes for bulk operations and common queries
-- This migration adds partial indexes and removes redundant ones

-- 1. Papers table optimizations
-- =================================

-- Drop redundant indexes that are covered by composite indexes
DROP INDEX IF EXISTS idx_papers_date;  -- Covered by idx_papers_date_score
DROP INDEX IF EXISTS idx_papers_related;  -- Rarely used alone

-- Add partial index for pending papers (papers without embeddings)
CREATE INDEX IF NOT EXISTS idx_papers_pending_embedding 
ON papers(id, date) 
WHERE embedding_model IS NULL;

-- Add index for recent papers (commonly queried)
-- Note: Cannot use CURRENT_DATE in partial index as it's not immutable
-- Using a regular index instead, application code should filter by date
CREATE INDEX IF NOT EXISTS idx_papers_recent 
ON papers(date DESC, score DESC);

-- Optimize the URL/title composite index for duplicate checking
DROP INDEX IF EXISTS idx_papers_url_title;
CREATE UNIQUE INDEX idx_papers_url_title_unique 
ON papers(url, title) 
WHERE url IS NOT NULL;

-- 2. Paper profile scores optimizations
-- =====================================

-- Add covering index for common profile queries
CREATE INDEX IF NOT EXISTS idx_paper_profile_scores_profile_covering 
ON paper_profile_scores(profile_id, score DESC, date_scored DESC) 
INCLUDE (paper_id, related);

-- Partial index for high-scoring papers per profile
CREATE INDEX IF NOT EXISTS idx_paper_profile_high_scores 
ON paper_profile_scores(profile_id, score DESC, paper_id) 
WHERE score >= 7;

-- 3. Embeddings table optimizations
-- =================================

-- Index for finding papers with/without embeddings of specific models
CREATE INDEX IF NOT EXISTS idx_embeddings_model_paper 
ON embeddings(embedding_model, paper_id);

-- 4. Keywords optimizations  
-- =========================

-- Optimize keyword lookups
DROP INDEX IF EXISTS idx_keywords_keyword;
CREATE INDEX IF NOT EXISTS idx_keywords_keyword_lower ON keywords(LOWER(keyword));

-- Add index for paper keyword associations
CREATE INDEX IF NOT EXISTS idx_paper_keywords_paper_keyword 
ON paper_keywords(paper_id, keyword_id);

-- 5. Topics and trends optimizations
-- ==================================

-- Index for active topics
CREATE INDEX IF NOT EXISTS idx_topics_active 
ON topics(is_active, created_at DESC) 
WHERE is_active = true;

-- Optimize paper topics for trend queries
CREATE INDEX IF NOT EXISTS idx_paper_topics_date_topic 
ON paper_topics(topic_id, assigned_at DESC) 
INCLUDE (paper_id);

-- Index for topic metrics queries
CREATE INDEX IF NOT EXISTS idx_topic_metrics_period_topic 
ON topic_metrics(period_type, period_end DESC, topic_id);

-- 6. Research profiles optimizations
-- ==================================

-- Partial index for active profiles
CREATE INDEX IF NOT EXISTS idx_profiles_active 
ON research_profiles(is_active, created_at DESC) 
WHERE is_active = true;

-- 7. Query performance views
-- ==========================

-- Create a materialized view for paper statistics (refresh periodically)
-- Note: View will include all data, filtering should be done at query time
CREATE MATERIALIZED VIEW IF NOT EXISTS paper_stats_mv AS
SELECT 
    DATE_TRUNC('day', date) as day,
    COUNT(*) as paper_count,
    COUNT(CASE WHEN embedding_model IS NOT NULL THEN 1 END) as embedded_count,
    AVG(score) as avg_score,
    COUNT(DISTINCT url) as unique_urls
FROM papers
GROUP BY DATE_TRUNC('day', date);

CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_stats_mv_day ON paper_stats_mv(day);

-- Create index to support the view refresh and date-based queries
CREATE INDEX IF NOT EXISTS idx_papers_date_stats 
ON papers(date);

-- Ensure the migration runs smoothly even if some objects already exist
-- This makes the migration idempotent

-- 8. Vacuum and analyze
-- =====================

-- Update table statistics for query planner
ANALYZE papers;
ANALYZE paper_profile_scores;
ANALYZE embeddings;
ANALYZE keywords;
ANALYZE paper_keywords;
ANALYZE topics;
ANALYZE paper_topics;
ANALYZE topic_metrics;
ANALYZE research_profiles;

-- Log index optimization completion
DO $$
BEGIN
    RAISE NOTICE 'Index optimization completed. Monitor query performance and adjust as needed.';
END $$;