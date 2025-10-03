-- Clean up stuck jobs that are blocking new operations
-- Usage: psql -U theseus -d theseusdb -f cleanup_stuck_jobs.sql
--
-- WARNING: This will mark all running/pending jobs older than 2 hours as failed
-- Only run this if you're sure there are no active jobs

BEGIN;

\echo '=== Jobs that will be marked as failed ==='
SELECT 
    id,
    job_type,
    status,
    started_at,
    EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_running
FROM processing_jobs
WHERE status IN ('running', 'pending')
AND job_type IN ('bulk_judge', 'harvest_judge', 'newsletter_generation', 'mindmap_generation', 'podcast_generation')
AND EXTRACT(EPOCH FROM (NOW() - started_at))/60 > 120;  -- Older than 2 hours

\echo ''
\echo '=== Marking stuck jobs as failed ==='
UPDATE processing_jobs 
SET 
    status = 'failed',
    error_message = 'Automatically cancelled - job stuck for over 2 hours with no activity',
    completed_at = NOW()
WHERE status IN ('running', 'pending')
AND job_type IN ('bulk_judge', 'harvest_judge', 'newsletter_generation', 'mindmap_generation', 'podcast_generation')
AND EXTRACT(EPOCH FROM (NOW() - started_at))/60 > 120;

-- Show the count of updated jobs
\echo ''
\echo '=== Jobs cleaned up ==='
SELECT COUNT(*) as cleaned_up_jobs
FROM processing_jobs
WHERE status = 'failed'
AND error_message = 'Automatically cancelled - job stuck for over 2 hours with no activity';

-- Commit the changes
COMMIT;

\echo ''
\echo '=== Cleanup complete! ==='

