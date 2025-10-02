-- Check for stuck or running jobs that might be blocking new operations
-- Usage: psql -U theseus -d theseusdb -f check_stuck_jobs.sql

\echo '=== Checking for running or pending jobs ==='
SELECT 
    id,
    job_type,
    status,
    started_at,
    last_checkpoint_at,
    progress_current,
    progress_total,
    CASE 
        WHEN progress_total > 0 THEN ROUND((progress_current::numeric / progress_total * 100), 2)
        ELSE 0
    END as progress_percent,
    EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_running,
    configuration->>'use_multi_server' as multi_server
FROM processing_jobs
WHERE status IN ('running', 'pending')
AND job_type IN ('bulk_judge', 'harvest_judge', 'newsletter_generation', 'mindmap_generation', 'podcast_generation')
ORDER BY started_at DESC;

\echo ''
\echo '=== Jobs that may be stuck (running > 60 minutes with no progress) ==='
SELECT 
    id,
    job_type,
    status,
    started_at,
    last_checkpoint_at,
    progress_current,
    progress_total,
    EXTRACT(EPOCH FROM (NOW() - started_at))/60 as minutes_running
FROM processing_jobs
WHERE status IN ('running', 'pending')
AND job_type IN ('bulk_judge', 'harvest_judge', 'newsletter_generation', 'mindmap_generation', 'podcast_generation')
AND EXTRACT(EPOCH FROM (NOW() - started_at))/60 > 60
AND (last_checkpoint_at IS NULL OR EXTRACT(EPOCH FROM (NOW() - last_checkpoint_at))/60 > 30)
ORDER BY started_at DESC;

\echo ''
\echo '=== To cancel stuck jobs, run: ==='
\echo 'UPDATE processing_jobs SET status = ''failed'', error_message = ''Manually cancelled - stuck job'' WHERE id = ''<job_id>'';'

