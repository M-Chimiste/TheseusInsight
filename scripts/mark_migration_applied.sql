-- Manual script to mark a migration as applied in the schema_migrations table
-- Usage: psql -U theseus -d theseusdb -f mark_migration_applied.sql
-- 
-- This is useful when a migration was partially applied or when you need to
-- manually sync the migration tracking table with the actual database state.

-- Mark migration 007 as applied (if it was partially applied)
INSERT INTO schema_migrations (version, name, description, applied_at)
VALUES (7, '007_add_scheduled_tasks.sql', 'Add scheduled tasks configuration', NOW())
ON CONFLICT (version) DO NOTHING;

-- Verify the migration was recorded
SELECT version, name, description, applied_at 
FROM schema_migrations 
WHERE version = 7;

