-- Migration 011: Newsletter Multi-Server Judge Support
-- This migration adds support for multi-server LLM judge scoring in newsletter generation.
-- It creates the newsletter_jobs table and extends judge_task_queue to support newsletter tasks
-- alongside existing bulk judge operations.
-- Note: Newsletter uses profile-specific scoring like bulk judge. Scores are stored in
-- paper_profile_scores for each (paper, profile) combination and aggregated for the newsletter.
-- Job tracking is done via newsletter_jobs and judge_task_queue.

-- Create newsletter_jobs table for tracking newsletter generation with multi-server scoring
CREATE TABLE IF NOT EXISTS newsletter_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_ids INTEGER[] NOT NULL,
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'scoring', 'generating', 'completed', 'failed', 'canceled')),
    use_multi_server BOOLEAN DEFAULT FALSE,
    server_ids INTEGER[],
    scoring_mode VARCHAR(20) DEFAULT 'single'
        CHECK (scoring_mode IN ('single', 'multi-server')),
    papers_to_score INTEGER DEFAULT 0,
    papers_scored INTEGER DEFAULT 0,
    research_interests TEXT,
    date_range_start TIMESTAMP WITH TIME ZONE,
    date_range_end TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    result_data JSONB DEFAULT '{}'
);

-- Add indexes for newsletter_jobs
CREATE INDEX idx_newsletter_jobs_status ON newsletter_jobs(status);
CREATE INDEX idx_newsletter_jobs_created_at ON newsletter_jobs(created_at DESC);
CREATE INDEX idx_newsletter_jobs_profile_ids ON newsletter_jobs USING GIN(profile_ids);

-- Add updated_at trigger for newsletter_jobs
DROP TRIGGER IF EXISTS update_newsletter_jobs_updated_at ON newsletter_jobs;
CREATE TRIGGER update_newsletter_jobs_updated_at
    BEFORE UPDATE ON newsletter_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add job_type column to judge_task_queue to distinguish between bulk judge and newsletter tasks
ALTER TABLE judge_task_queue
ADD COLUMN IF NOT EXISTS job_type VARCHAR(20) DEFAULT 'bulk_judge'
    CHECK (job_type IN ('bulk_judge', 'newsletter'));

-- Add newsletter-specific columns to judge_task_queue
ALTER TABLE judge_task_queue
ADD COLUMN IF NOT EXISTS research_interests TEXT,
ADD COLUMN IF NOT EXISTS paper_title TEXT,
ADD COLUMN IF NOT EXISTS paper_abstract TEXT;

-- Update existing tasks to ensure job_type is set (for safety)
UPDATE judge_task_queue
SET job_type = 'bulk_judge'
WHERE job_type IS NULL OR job_type = '';

-- Drop the foreign key constraint on job_id since we now support two job types:
-- - bulk_judge jobs reference processing_jobs(id)
-- - newsletter jobs reference newsletter_jobs(id)
-- Referential integrity will be maintained at the application layer
ALTER TABLE judge_task_queue
DROP CONSTRAINT IF EXISTS judge_task_queue_job_id_fkey;

-- Also drop the foreign key constraint on worker_heartbeats.job_id for the same reason
ALTER TABLE worker_heartbeats
DROP CONSTRAINT IF EXISTS worker_heartbeats_job_id_fkey;

-- Drop existing unique constraint (job_id, paper_id, profile_id)
ALTER TABLE judge_task_queue
DROP CONSTRAINT IF EXISTS judge_task_queue_job_id_paper_id_profile_id_key;

-- Create conditional unique indexes for bulk_judge and newsletter job types
-- Both use (job_id, paper_id, profile_id) for profile-specific scoring
CREATE UNIQUE INDEX IF NOT EXISTS judge_task_queue_bulk_unique
    ON judge_task_queue(job_id, paper_id, profile_id)
    WHERE job_type = 'bulk_judge';

-- Newsletter also uses profile-specific scoring (same as bulk judge)
-- This allows newsletters with multiple profiles to score each paper against each profile
CREATE UNIQUE INDEX IF NOT EXISTS judge_task_queue_newsletter_unique
    ON judge_task_queue(job_id, paper_id, profile_id)
    WHERE job_type = 'newsletter';

-- Add index for job_type to improve filtering performance
CREATE INDEX IF NOT EXISTS idx_judge_task_queue_job_type ON judge_task_queue(job_type);

-- Add index for newsletter task queries
CREATE INDEX IF NOT EXISTS idx_judge_task_queue_newsletter_status
    ON judge_task_queue(job_id, status)
    WHERE job_type = 'newsletter';

-- Add comments for documentation
COMMENT ON TABLE newsletter_jobs IS 'Tracks newsletter generation jobs with multi-server LLM judge scoring support';
COMMENT ON COLUMN newsletter_jobs.status IS 'Job status: pending, scoring, generating, completed, failed, canceled';
COMMENT ON COLUMN newsletter_jobs.use_multi_server IS 'Whether multi-server judge scoring is enabled for this job';
COMMENT ON COLUMN newsletter_jobs.server_ids IS 'Array of inference_servers.id used for multi-server scoring';
COMMENT ON COLUMN newsletter_jobs.scoring_mode IS 'Scoring mode: single (sequential) or multi-server (parallel worker pool)';
COMMENT ON COLUMN newsletter_jobs.papers_to_score IS 'Total number of papers to score for this newsletter';
COMMENT ON COLUMN newsletter_jobs.papers_scored IS 'Number of papers scored so far (for progress tracking)';
COMMENT ON COLUMN newsletter_jobs.result_data IS 'JSON containing newsletter generation results and metadata';

COMMENT ON COLUMN judge_task_queue.job_type IS 'Type of job: bulk_judge or newsletter (both use profile-specific scoring)';
COMMENT ON COLUMN judge_task_queue.research_interests IS 'Cached research interests from profile (avoids profile lookup in worker)';
COMMENT ON COLUMN judge_task_queue.paper_title IS 'Cached paper title for display and logging';
COMMENT ON COLUMN judge_task_queue.paper_abstract IS 'Cached paper abstract for scoring (avoids paper lookup in worker)';

-- Create a view for monitoring newsletter scoring progress
CREATE OR REPLACE VIEW newsletter_scoring_progress AS
SELECT
    nj.id as newsletter_job_id,
    nj.status as job_status,
    nj.use_multi_server,
    nj.scoring_mode,
    nj.papers_to_score,
    nj.papers_scored,
    CASE
        WHEN nj.papers_to_score > 0 THEN ROUND((nj.papers_scored::numeric / nj.papers_to_score::numeric) * 100, 2)
        ELSE 0
    END as progress_percent,
    COUNT(CASE WHEN jt.status = 'pending' THEN 1 END) as pending_tasks,
    COUNT(CASE WHEN jt.status = 'leased' THEN 1 END) as leased_tasks,
    COUNT(CASE WHEN jt.status = 'in_progress' THEN 1 END) as in_progress_tasks,
    COUNT(CASE WHEN jt.status = 'completed' THEN 1 END) as completed_tasks,
    COUNT(CASE WHEN jt.status = 'failed' THEN 1 END) as failed_tasks,
    nj.created_at,
    nj.completed_at,
    CASE
        WHEN nj.completed_at IS NOT NULL THEN
            EXTRACT(EPOCH FROM (nj.completed_at - nj.created_at))
        ELSE
            EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - nj.created_at))
    END as duration_seconds
FROM newsletter_jobs nj
LEFT JOIN judge_task_queue jt ON nj.id::text = jt.job_id::text AND jt.job_type = 'newsletter'
WHERE nj.use_multi_server = TRUE
GROUP BY nj.id, nj.status, nj.use_multi_server, nj.scoring_mode, nj.papers_to_score, nj.papers_scored,
         nj.created_at, nj.completed_at
ORDER BY nj.created_at DESC;

COMMENT ON VIEW newsletter_scoring_progress IS
    'Real-time view of newsletter multi-server scoring progress with task breakdown and performance metrics';

-- Create a view for per-server statistics in newsletter jobs
CREATE OR REPLACE VIEW newsletter_server_stats AS
SELECT
    nj.id as newsletter_job_id,
    jt.assigned_server_url,
    COUNT(*) as total_tasks,
    COUNT(CASE WHEN jt.status = 'completed' THEN 1 END) as completed_tasks,
    COUNT(CASE WHEN jt.status = 'failed' THEN 1 END) as failed_tasks,
    COUNT(CASE WHEN jt.status IN ('pending', 'leased', 'in_progress') THEN 1 END) as active_tasks,
    AVG(CASE
        WHEN jt.status = 'completed' AND jt.updated_at > jt.created_at THEN
            EXTRACT(EPOCH FROM (jt.updated_at - jt.created_at))
        ELSE NULL
    END) as avg_task_duration_seconds,
    MAX(jt.updated_at) as last_completed_at
FROM newsletter_jobs nj
JOIN judge_task_queue jt ON nj.id::text = jt.job_id::text AND jt.job_type = 'newsletter'
WHERE nj.use_multi_server = TRUE AND jt.assigned_server_url IS NOT NULL
GROUP BY nj.id, jt.assigned_server_url
ORDER BY nj.id DESC, jt.assigned_server_url;

COMMENT ON VIEW newsletter_server_stats IS
    'Per-server performance statistics for newsletter multi-server scoring jobs';

-- Migration verification and reporting
DO $$
DECLARE
    newsletter_jobs_count INTEGER;
    newsletter_tasks_count INTEGER;
    bulk_tasks_count INTEGER;
BEGIN
    -- Count existing records
    SELECT COUNT(*) INTO newsletter_jobs_count FROM newsletter_jobs;
    SELECT COUNT(*) INTO newsletter_tasks_count FROM judge_task_queue WHERE job_type = 'newsletter';
    SELECT COUNT(*) INTO bulk_tasks_count FROM judge_task_queue WHERE job_type = 'bulk_judge';

    -- Report migration status
    RAISE NOTICE 'Migration 011 completed successfully';
    RAISE NOTICE 'Newsletter jobs table created: % existing jobs', newsletter_jobs_count;
    RAISE NOTICE 'Judge task queue extended with job_type column';
    RAISE NOTICE '  - Newsletter tasks: %', newsletter_tasks_count;
    RAISE NOTICE '  - Bulk judge tasks: %', bulk_tasks_count;
    RAISE NOTICE 'Unique constraints updated for dual job type support';
    RAISE NOTICE 'Views created: newsletter_scoring_progress, newsletter_server_stats';
END $$;
