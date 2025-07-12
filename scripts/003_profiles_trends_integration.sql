-- Migration script to integrate Research Profiles with Trends Analysis
-- This script adds profile_id columns to trends tables and migrates existing data
-- Version: 3.1 - Profiles-Trends Integration
-- Date: January 2025

-- ===================================================================
-- Add Profile Context to Topics Tables
-- ===================================================================

-- Add profile_id column to topics table
ALTER TABLE topics ADD COLUMN IF NOT EXISTS profile_id INTEGER;

-- Add foreign key constraint to research_profiles
ALTER TABLE topics ADD CONSTRAINT fk_topics_profile_id 
    FOREIGN KEY (profile_id) REFERENCES research_profiles(id) ON DELETE CASCADE;

-- Add profile_id column to topic_metrics table
ALTER TABLE topic_metrics ADD COLUMN IF NOT EXISTS profile_id INTEGER;

-- Add foreign key constraint for topic_metrics
ALTER TABLE topic_metrics ADD CONSTRAINT fk_topic_metrics_profile_id 
    FOREIGN KEY (profile_id) REFERENCES research_profiles(id) ON DELETE CASCADE;

-- ===================================================================
-- Migrate Existing Topics to Default Profile
-- ===================================================================

DO $$
DECLARE
    default_profile_id INTEGER;
    topics_updated INTEGER;
    metrics_updated INTEGER;
BEGIN
    -- Get the default profile ID
    SELECT id INTO default_profile_id 
    FROM research_profiles 
    WHERE is_default = TRUE 
    LIMIT 1;
    
    IF default_profile_id IS NULL THEN
        RAISE EXCEPTION 'No default profile found. Please run profiles migration first.';
    END IF;
    
    RAISE NOTICE 'Using default profile ID: %', default_profile_id;
    
    -- Update existing topics to belong to default profile
    UPDATE topics 
    SET profile_id = default_profile_id 
    WHERE profile_id IS NULL;
    
    GET DIAGNOSTICS topics_updated = ROW_COUNT;
    RAISE NOTICE 'Updated % topics to use default profile', topics_updated;
    
    -- Update existing topic metrics to belong to default profile
    UPDATE topic_metrics 
    SET profile_id = default_profile_id 
    WHERE profile_id IS NULL;
    
    GET DIAGNOSTICS metrics_updated = ROW_COUNT;
    RAISE NOTICE 'Updated % topic metrics to use default profile', metrics_updated;
    
END $$;

-- ===================================================================
-- Make Profile Columns Required
-- ===================================================================

-- Make profile_id NOT NULL for topics
ALTER TABLE topics ALTER COLUMN profile_id SET NOT NULL;

-- Make profile_id NOT NULL for topic_metrics  
ALTER TABLE topic_metrics ALTER COLUMN profile_id SET NOT NULL;

-- ===================================================================
-- Create Indexes for Performance
-- ===================================================================

-- Index for topics by profile
CREATE INDEX IF NOT EXISTS idx_topics_profile_id ON topics(profile_id);
CREATE INDEX IF NOT EXISTS idx_topics_profile_label ON topics(profile_id, label);

-- Index for topic metrics by profile
CREATE INDEX IF NOT EXISTS idx_topic_metrics_profile_id ON topic_metrics(profile_id);
CREATE INDEX IF NOT EXISTS idx_topic_metrics_profile_period ON topic_metrics(profile_id, period_type, period_start);

-- Composite index for efficient profile-topic queries
CREATE INDEX IF NOT EXISTS idx_topics_profile_created ON topics(profile_id, created_at DESC);

-- ===================================================================
-- Update Research Interest Tables (if needed)
-- ===================================================================

-- Note: The research_interests table will be phased out in favor of 
-- profile_research_interests, but we'll keep it for backward compatibility
-- during the transition period.

-- ===================================================================
-- Verification Queries
-- ===================================================================

DO $$
DECLARE
    total_topics INTEGER;
    total_metrics INTEGER;
    default_profile_topics INTEGER;
    default_profile_metrics INTEGER;
BEGIN
    -- Count totals
    SELECT COUNT(*) INTO total_topics FROM topics;
    SELECT COUNT(*) INTO total_metrics FROM topic_metrics;
    
    -- Count default profile assignments
    SELECT COUNT(*) INTO default_profile_topics 
    FROM topics t 
    JOIN research_profiles rp ON t.profile_id = rp.id 
    WHERE rp.is_default = TRUE;
    
    SELECT COUNT(*) INTO default_profile_metrics 
    FROM topic_metrics tm 
    JOIN research_profiles rp ON tm.profile_id = rp.id 
    WHERE rp.is_default = TRUE;
    
    RAISE NOTICE '=== PROFILES-TRENDS INTEGRATION SUMMARY ===';
    RAISE NOTICE 'Total topics: % (% assigned to default profile)', total_topics, default_profile_topics;
    RAISE NOTICE 'Total topic metrics: % (% assigned to default profile)', total_metrics, default_profile_metrics;
    RAISE NOTICE '==============================================';
END $$;

-- ===================================================================
-- Show Sample Data
-- ===================================================================

-- Show topics with profile information
SELECT 
    'Topics with Profile Info:' AS info,
    t.id,
    t.label,
    rp.name as profile_name,
    rp.is_default,
    t.created_at
FROM topics t
JOIN research_profiles rp ON t.profile_id = rp.id
ORDER BY t.created_at DESC
LIMIT 5;

-- Show metrics with profile information
SELECT 
    'Topic Metrics with Profile Info:' AS info,
    tm.id,
    tm.topic_id,
    rp.name as profile_name,
    tm.period_type,
    tm.doc_count,
    tm.period_start
FROM topic_metrics tm
JOIN research_profiles rp ON tm.profile_id = rp.id
JOIN topics t ON tm.topic_id = t.id
ORDER BY tm.period_start DESC
LIMIT 5;

COMMIT; 