-- Migration Compatibility Script
-- This ensures migrations work for both fresh installs and upgrades
-- It handles cases where constraints/indexes may already exist

-- Helper function to check if a constraint exists
CREATE OR REPLACE FUNCTION constraint_exists(
    p_table_name TEXT,
    p_constraint_name TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE c.conname = p_constraint_name
        AND n.nspname = 'public'
        AND c.conrelid = (p_table_name)::regclass
    );
END;
$$ LANGUAGE plpgsql;

-- Helper function to check if an index exists
CREATE OR REPLACE FUNCTION index_exists(
    p_index_name TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 
        FROM pg_indexes 
        WHERE schemaname = 'public' 
        AND indexname = p_index_name
    );
END;
$$ LANGUAGE plpgsql;

-- Helper function to check if a column exists
CREATE OR REPLACE FUNCTION column_exists(
    p_table_name TEXT,
    p_column_name TEXT
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = p_table_name 
        AND column_name = p_column_name
    );
END;
$$ LANGUAGE plpgsql;

-- Helper function to safely add a constraint
CREATE OR REPLACE FUNCTION add_constraint_if_not_exists(
    p_table_name TEXT,
    p_constraint_name TEXT,
    p_constraint_definition TEXT
) RETURNS VOID AS $$
BEGIN
    IF NOT constraint_exists(p_table_name, p_constraint_name) THEN
        EXECUTE format('ALTER TABLE %I ADD CONSTRAINT %I %s', 
            p_table_name, p_constraint_name, p_constraint_definition);
        RAISE NOTICE 'Added constraint % to table %', p_constraint_name, p_table_name;
    ELSE
        RAISE NOTICE 'Constraint % already exists on table %, skipping', p_constraint_name, p_table_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Helper function to safely create an index
CREATE OR REPLACE FUNCTION create_index_if_not_exists(
    p_index_name TEXT,
    p_index_definition TEXT
) RETURNS VOID AS $$
BEGIN
    IF NOT index_exists(p_index_name) THEN
        EXECUTE format('CREATE INDEX %I %s', p_index_name, p_index_definition);
        RAISE NOTICE 'Created index %', p_index_name;
    ELSE
        RAISE NOTICE 'Index % already exists, skipping', p_index_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

COMMIT;