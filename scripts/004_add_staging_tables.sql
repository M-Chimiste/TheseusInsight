-- Migration 004: Add staging tables for bulk operations
-- This migration adds staging tables to support high-performance bulk imports
-- using PostgreSQL COPY command and efficient deduplication

-- Create staging table for papers
CREATE TABLE IF NOT EXISTS papers_staging (
    LIKE papers INCLUDING ALL,
    staging_batch_id UUID,
    staging_timestamp TIMESTAMP DEFAULT NOW()
);

-- Create staging table for embeddings
CREATE TABLE IF NOT EXISTS embeddings_staging (
    paper_id INTEGER,
    embedding vector(768),
    embedding_model VARCHAR(255),
    staging_batch_id UUID,
    staging_timestamp TIMESTAMP DEFAULT NOW()
);

-- Create staging table for keywords
CREATE TABLE IF NOT EXISTS keywords_staging (
    paper_id INTEGER,
    keywords_json JSONB,
    staging_batch_id UUID,
    staging_timestamp TIMESTAMP DEFAULT NOW()
);

-- Create staging table for paper profile scores
CREATE TABLE IF NOT EXISTS paper_profile_scores_staging (
    paper_id INTEGER,
    profile_id INTEGER,
    score INTEGER,
    related BOOLEAN,
    rationale TEXT,
    judge_model VARCHAR(255),
    date_scored TIMESTAMP DEFAULT NOW(),
    staging_batch_id UUID,
    staging_timestamp TIMESTAMP DEFAULT NOW()
);

-- Create indexes for efficient deduplication
CREATE INDEX IF NOT EXISTS idx_papers_staging_url ON papers_staging(url);
CREATE INDEX IF NOT EXISTS idx_papers_staging_title ON papers_staging(title);
CREATE INDEX IF NOT EXISTS idx_papers_staging_batch ON papers_staging(staging_batch_id);

CREATE INDEX IF NOT EXISTS idx_embeddings_staging_paper ON embeddings_staging(paper_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_staging_batch ON embeddings_staging(staging_batch_id);

CREATE INDEX IF NOT EXISTS idx_keywords_staging_paper ON keywords_staging(paper_id);
CREATE INDEX IF NOT EXISTS idx_keywords_staging_batch ON keywords_staging(staging_batch_id);

CREATE INDEX IF NOT EXISTS idx_scores_staging_paper_profile ON paper_profile_scores_staging(paper_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_scores_staging_batch ON paper_profile_scores_staging(staging_batch_id);

-- Create composite index on papers table for faster duplicate checking
CREATE INDEX IF NOT EXISTS idx_papers_url_title ON papers(url, title);

-- Add function for efficient batch deduplication
CREATE OR REPLACE FUNCTION deduplicate_staging_papers(batch_id UUID)
RETURNS TABLE(duplicate_count INTEGER, new_count INTEGER) AS $$
DECLARE
    dup_count INTEGER;
    new_count INTEGER;
BEGIN
    -- Count duplicates
    SELECT COUNT(*) INTO dup_count
    FROM papers_staging ps
    WHERE ps.staging_batch_id = batch_id
      AND (EXISTS (SELECT 1 FROM papers p WHERE p.url = ps.url)
           OR EXISTS (SELECT 1 FROM papers p WHERE p.title = ps.title));
    
    -- Delete duplicates from staging
    DELETE FROM papers_staging ps
    WHERE ps.staging_batch_id = batch_id
      AND (EXISTS (SELECT 1 FROM papers p WHERE p.url = ps.url)
           OR EXISTS (SELECT 1 FROM papers p WHERE p.title = ps.title));
    
    -- Count remaining new papers
    SELECT COUNT(*) INTO new_count
    FROM papers_staging
    WHERE staging_batch_id = batch_id;
    
    RETURN QUERY SELECT dup_count, new_count;
END;
$$ LANGUAGE plpgsql;

-- Add function for merging staging data into main tables
CREATE OR REPLACE FUNCTION merge_staging_to_main(batch_id UUID)
RETURNS TABLE(papers_inserted INTEGER, embeddings_updated INTEGER, keywords_updated INTEGER, scores_inserted INTEGER) AS $$
DECLARE
    papers_count INTEGER;
    embeddings_count INTEGER;
    keywords_count INTEGER;
    scores_count INTEGER;
BEGIN
    -- Insert new papers from staging
    INSERT INTO papers (title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, 
                       embedding_model, embedding, keywords_json, fulltext_extraction_status, downloaded_pdf_path)
    SELECT title, abstract, date, date_run, score, rationale, related, cosine_similarity, url,
           embedding_model, embedding, keywords_json, fulltext_extraction_status, downloaded_pdf_path
    FROM papers_staging
    WHERE staging_batch_id = batch_id;
    
    GET DIAGNOSTICS papers_count = ROW_COUNT;
    
    -- Update embeddings from staging
    UPDATE papers p
    SET embedding = es.embedding,
        embedding_model = es.embedding_model
    FROM embeddings_staging es
    WHERE p.id = es.paper_id
      AND es.staging_batch_id = batch_id;
    
    GET DIAGNOSTICS embeddings_count = ROW_COUNT;
    
    -- Update keywords from staging
    UPDATE papers p
    SET keywords_json = ks.keywords_json
    FROM keywords_staging ks
    WHERE p.id = ks.paper_id
      AND ks.staging_batch_id = batch_id;
    
    GET DIAGNOSTICS keywords_count = ROW_COUNT;
    
    -- Insert profile scores from staging
    INSERT INTO paper_profile_scores (paper_id, profile_id, score, related, rationale, judge_model, date_scored)
    SELECT paper_id, profile_id, score, related, rationale, judge_model, date_scored
    FROM paper_profile_scores_staging
    WHERE staging_batch_id = batch_id
    ON CONFLICT (paper_id, profile_id) DO UPDATE
    SET score = EXCLUDED.score,
        related = EXCLUDED.related,
        rationale = EXCLUDED.rationale,
        judge_model = EXCLUDED.judge_model,
        date_scored = EXCLUDED.date_scored;
    
    GET DIAGNOSTICS scores_count = ROW_COUNT;
    
    -- Clean up staging tables for this batch
    DELETE FROM papers_staging WHERE staging_batch_id = batch_id;
    DELETE FROM embeddings_staging WHERE staging_batch_id = batch_id;
    DELETE FROM keywords_staging WHERE staging_batch_id = batch_id;
    DELETE FROM paper_profile_scores_staging WHERE staging_batch_id = batch_id;
    
    RETURN QUERY SELECT papers_count, embeddings_count, keywords_count, scores_count;
END;
$$ LANGUAGE plpgsql;

-- Add comment explaining staging table purpose
COMMENT ON TABLE papers_staging IS 'Temporary staging table for bulk paper imports using COPY';
COMMENT ON TABLE embeddings_staging IS 'Temporary staging table for bulk embedding updates';
COMMENT ON TABLE keywords_staging IS 'Temporary staging table for bulk keyword updates';
COMMENT ON TABLE paper_profile_scores_staging IS 'Temporary staging table for bulk profile score imports';