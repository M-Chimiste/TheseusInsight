-- Migration script to add Research Profiles feature to Theseus Insight
-- This script adds the necessary tables and modifies existing schema
-- Version: 1.0
-- Date: December 2024

-- === Research Profiles Tables ===

-- Main profiles table
CREATE TABLE IF NOT EXISTS research_profiles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT, -- UI color coding
    tags JSONB, -- Array of tags for profile organization
    email_recipients JSONB, -- Array of email addresses for newsletter distribution
    arxiv_filters JSONB, -- ArXiv category filters specific to this profile
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for profiles
CREATE INDEX IF NOT EXISTS idx_research_profiles_name ON research_profiles(name);
CREATE INDEX IF NOT EXISTS idx_research_profiles_active ON research_profiles(is_active);
CREATE INDEX IF NOT EXISTS idx_research_profiles_default ON research_profiles(is_default);
CREATE INDEX IF NOT EXISTS idx_research_profiles_tags ON research_profiles USING GIN(tags);

-- Profile-specific research interests
CREATE TABLE IF NOT EXISTS profile_research_interests (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    interest_text TEXT NOT NULL,
    embedding vector(768), -- Embedding for semantic similarity
    embedding_model TEXT, -- Model used for embedding
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(profile_id, interest_text) -- Prevent duplicate interests per profile
);

-- Indexes for profile research interests
CREATE INDEX IF NOT EXISTS idx_profile_research_interests_profile ON profile_research_interests(profile_id);
CREATE INDEX IF NOT EXISTS idx_profile_research_interests_embedding ON profile_research_interests USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);

-- Profile-specific paper scores
CREATE TABLE IF NOT EXISTS paper_profile_scores (
    id SERIAL PRIMARY KEY,
    paper_id INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    profile_id INTEGER NOT NULL REFERENCES research_profiles(id) ON DELETE CASCADE,
    score INTEGER CHECK (score BETWEEN 1 AND 10),
    related BOOLEAN,
    rationale TEXT,
    date_scored TIMESTAMPTZ DEFAULT now(),
    judge_model TEXT, -- Model used for scoring
    UNIQUE(paper_id, profile_id) -- One score per paper per profile
);

-- Indexes for paper profile scores
CREATE INDEX IF NOT EXISTS idx_paper_profile_scores_paper ON paper_profile_scores(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_profile_scores_profile ON paper_profile_scores(profile_id);
CREATE INDEX IF NOT EXISTS idx_paper_profile_scores_score ON paper_profile_scores(score);
CREATE INDEX IF NOT EXISTS idx_paper_profile_scores_related ON paper_profile_scores(related);
CREATE INDEX IF NOT EXISTS idx_paper_profile_scores_date ON paper_profile_scores(date_scored);

-- === Data Migration ===

-- Step 1: Create Default profile from existing settings
DO $$
DECLARE
    default_profile_id INTEGER;
    existing_interests TEXT;
    existing_email_recipients TEXT;
    existing_arxiv_categories TEXT;
    interest_record RECORD;
    embedding_model_name TEXT;
BEGIN
    -- Check if Default profile already exists
    SELECT id INTO default_profile_id FROM research_profiles WHERE name = 'Default';
    
    IF default_profile_id IS NULL THEN
        -- Get existing research interests from settings
        SELECT value INTO existing_interests FROM settings WHERE key = 'research_interests';
        
        -- Get existing email recipients from settings
        SELECT value INTO existing_email_recipients FROM settings WHERE key = 'email_recipients';
        
        -- Get existing ArXiv categories from settings
        SELECT value INTO existing_arxiv_categories FROM settings WHERE key = 'arxiv_search_categories';
        
        -- Create Default profile
        INSERT INTO research_profiles (
            name, 
            description, 
            color,
            email_recipients,
            arxiv_filters,
            is_active, 
            is_default,
            created_at,
            updated_at
        ) VALUES (
            'Default',
            'Migrated from existing system settings',
            '#1f77b4', -- Default blue color
            CASE 
                WHEN existing_email_recipients IS NOT NULL 
                THEN existing_email_recipients::jsonb
                ELSE '[]'::jsonb
            END,
            CASE 
                WHEN existing_arxiv_categories IS NOT NULL 
                THEN existing_arxiv_categories::jsonb
                ELSE '{}'::jsonb
            END,
            TRUE,
            TRUE,
            now(),
            now()
        ) RETURNING id INTO default_profile_id;
        
        RAISE NOTICE 'Created Default profile with ID: %', default_profile_id;
        
        -- Get embedding model name from orchestration config
        BEGIN
            SELECT value::json->>'embedding_model'->>'model_name' 
            INTO embedding_model_name 
            FROM settings 
            WHERE key = 'orchestration';
        EXCEPTION WHEN OTHERS THEN
            embedding_model_name := 'sentence-transformers/all-MiniLM-L6-v2'; -- fallback
        END;
        
        -- Step 2: Migrate existing research interests to Default profile
        IF existing_interests IS NOT NULL AND LENGTH(TRIM(existing_interests)) > 0 THEN
            -- Split research interests by newlines and insert each as separate interest
            FOR interest_record IN 
                SELECT TRIM(unnest(string_to_array(existing_interests, E'\n'))) AS interest_text
            LOOP
                IF LENGTH(TRIM(interest_record.interest_text)) > 0 THEN
                    INSERT INTO profile_research_interests (
                        profile_id,
                        interest_text,
                        embedding_model,
                        created_at,
                        updated_at
                    ) VALUES (
                        default_profile_id,
                        TRIM(interest_record.interest_text),
                        embedding_model_name,
                        now(),
                        now()
                    );
                END IF;
            END LOOP;
            
            RAISE NOTICE 'Migrated research interests to Default profile';
        END IF;
        
        -- Step 3: Create profile scores for existing papers
        -- Copy existing paper scores to the Default profile
        INSERT INTO paper_profile_scores (
            paper_id,
            profile_id,
            score,
            related,
            rationale,
            date_scored,
            judge_model
        )
        SELECT 
            p.id,
            default_profile_id,
            p.score,
            p.related,
            p.rationale,
                         COALESCE(p.date_run::timestamptz, now()),
            'migrated-legacy-model'
        FROM papers p
        WHERE p.score IS NOT NULL
        ON CONFLICT (paper_id, profile_id) DO NOTHING;
        
        RAISE NOTICE 'Migrated % paper scores to Default profile', 
            (SELECT COUNT(*) FROM papers WHERE score IS NOT NULL);
        
    ELSE
        RAISE NOTICE 'Default profile already exists with ID: %', default_profile_id;
    END IF;
END $$;

-- === Update Triggers ===

-- Trigger to update updated_at timestamp on research_profiles
CREATE OR REPLACE FUNCTION update_research_profiles_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS research_profiles_updated_at_trigger ON research_profiles;
CREATE TRIGGER research_profiles_updated_at_trigger
    BEFORE UPDATE ON research_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_research_profiles_updated_at();

-- Trigger to update updated_at timestamp on profile_research_interests
CREATE OR REPLACE FUNCTION update_profile_research_interests_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS profile_research_interests_updated_at_trigger ON profile_research_interests;
CREATE TRIGGER profile_research_interests_updated_at_trigger
    BEFORE UPDATE ON profile_research_interests
    FOR EACH ROW
    EXECUTE FUNCTION update_profile_research_interests_updated_at();

-- === Verification Queries ===

-- Verify migration results
DO $$
DECLARE
    profile_count INTEGER;
    interest_count INTEGER;
    score_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO profile_count FROM research_profiles;
    SELECT COUNT(*) INTO interest_count FROM profile_research_interests;
    SELECT COUNT(*) INTO score_count FROM paper_profile_scores;
    
    RAISE NOTICE '=== MIGRATION SUMMARY ===';
    RAISE NOTICE 'Profiles created: %', profile_count;
    RAISE NOTICE 'Research interests migrated: %', interest_count;
    RAISE NOTICE 'Paper scores migrated: %', score_count;
    RAISE NOTICE '========================';
END $$;

-- Show the Default profile details
SELECT 
    'Default Profile Details:' AS info,
    p.id,
    p.name,
    p.description,
    p.is_default,
    p.is_active,
    (SELECT COUNT(*) FROM profile_research_interests pri WHERE pri.profile_id = p.id) AS interest_count,
    (SELECT COUNT(*) FROM paper_profile_scores pps WHERE pps.profile_id = p.id) AS scored_papers_count
FROM research_profiles p 
WHERE p.name = 'Default';

COMMIT; 