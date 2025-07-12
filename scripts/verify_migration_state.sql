-- Database Migration State Verification Script
-- Run this to check the current state of your database

-- Check if critical tables exist
SELECT 
    'Tables Check' as check_type,
    table_name,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_name = t.table_name
    ) THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (VALUES 
    ('papers'),
    ('research_profiles'),
    ('profile_research_interests'),
    ('paper_profile_scores'),
    ('topics'),
    ('topic_metrics'),
    ('settings'),
    ('model_providers')
) AS t(table_name)
ORDER BY table_name;

-- Check for profile-related columns in topics tables
SELECT 
    'Profile Integration Check' as check_type,
    table_name || '.' || column_name as object,
    CASE WHEN column_exists(table_name, column_name) 
        THEN '✓ EXISTS' ELSE '✗ MISSING' END as status
FROM (VALUES
    ('topics', 'profile_id'),
    ('topic_metrics', 'profile_id')
) AS t(table_name, column_name);

-- Check for critical constraints
SELECT 
    'Constraints Check' as check_type,
    conname as constraint_name,
    '✓ EXISTS' as status
FROM pg_constraint
WHERE conname IN (
    'fk_topics_profile_id',
    'fk_topic_metrics_profile_id'
);

-- Check for critical indexes
SELECT 
    'Indexes Check' as check_type,
    indexname,
    '✓ EXISTS' as status
FROM pg_indexes
WHERE schemaname = 'public'
AND indexname IN (
    'idx_papers_date',
    'idx_papers_score',
    'idx_topics_profile_id',
    'idx_paper_profile_scores_profile'
)
ORDER BY indexname;

-- Check migration history
SELECT 
    'Migration History' as check_type,
    version || ': ' || name as migration,
    to_char(applied_at, 'YYYY-MM-DD HH24:MI:SS') as applied_at
FROM schema_migrations
ORDER BY version;

-- Check for any papers without profile assignments (if profiles exist)
WITH profile_check AS (
    SELECT COUNT(*) as profile_count FROM research_profiles
)
SELECT 
    'Data Integrity Check' as check_type,
    'Papers without profile scores' as issue,
    COUNT(DISTINCT p.id) || ' papers' as count
FROM papers p
CROSS JOIN profile_check pc
LEFT JOIN paper_profile_scores pps ON p.id = pps.paper_id
WHERE pc.profile_count > 0
AND pps.id IS NULL
HAVING COUNT(DISTINCT p.id) > 0

UNION ALL

SELECT 
    'Data Integrity Check' as check_type,
    'Topics without profile assignment' as issue,
    COUNT(*) || ' topics' as count
FROM topics
WHERE profile_id IS NULL
HAVING COUNT(*) > 0;