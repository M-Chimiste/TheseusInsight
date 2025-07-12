-- Update migration names to new 00X_ format
-- This script updates existing migration records to match the new naming convention

-- Update existing migration names
UPDATE schema_migrations SET name = '001_init_schema_postgres.sql' 
WHERE name = 'init_schema_postgres.sql';

UPDATE schema_migrations SET name = '002_migrate_to_profiles.sql' 
WHERE name = 'migrate_to_profiles.sql';

UPDATE schema_migrations SET name = '003_profiles_trends_integration.sql' 
WHERE name = 'profiles_trends_integration.sql';

-- The 004 and 005 migrations already have the correct format

-- Show the updated migrations
SELECT version, name, description, applied_at 
FROM schema_migrations 
ORDER BY version;