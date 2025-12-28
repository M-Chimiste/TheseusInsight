-- Migration tracking system for Theseus Insight
-- This creates a simple migration tracking table to prevent re-running migrations
-- and to track which migrations have been applied

-- Create migration tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    checksum TEXT -- Optional: store file checksum to detect changes
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_schema_migrations_name ON schema_migrations(name);

-- Insert initial migration records if tables already exist
-- This prevents re-running migrations on existing installations
DO $$
BEGIN
    -- Check if initial schema exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'papers') THEN
        INSERT INTO schema_migrations (version, name, description) 
        VALUES (1, 'init_schema_postgres.sql', 'Initial database schema')
        ON CONFLICT (version) DO NOTHING;
    END IF;
    
    -- Check if profiles exist
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'research_profiles') THEN
        INSERT INTO schema_migrations (version, name, description) 
        VALUES (2, 'migrate_to_profiles.sql', 'Add research profiles feature')
        ON CONFLICT (version) DO NOTHING;
    END IF;
    
    -- Check if trends integration exists
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'topics' AND column_name = 'profile_id') THEN
        INSERT INTO schema_migrations (version, name, description) 
        VALUES (3, 'profiles_trends_integration.sql', 'Integrate profiles with trends')
        ON CONFLICT (version) DO NOTHING;
    END IF;
END $$;