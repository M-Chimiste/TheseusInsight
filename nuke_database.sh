#!/bin/bash

# DANGER: Database Nuke Script - FOR DEVELOPMENT ONLY
# This script will drop all tables and objects from the database
# DO NOT use in production!

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

echo -e "${RED}================================================${NC}"
echo -e "${RED}⚠️  DATABASE NUKE SCRIPT - DEVELOPMENT ONLY ⚠️${NC}"
echo -e "${RED}================================================${NC}"
echo ""
echo -e "${YELLOW}This script will DROP ALL TABLES AND DATA from the database:${NC}"
echo "  - Drop ALL tables, views, and indexes"
echo "  - Remove ALL data and migration history"
echo "  - Keep the database and extensions intact"
echo ""
echo -e "${RED}THIS ACTION CANNOT BE UNDONE!${NC}"
echo ""

# First confirmation
read -p "Are you SURE you want to nuke the database? (type 'yes' to continue): " confirm1
if [ "$confirm1" != "yes" ]; then
    echo -e "${GREEN}Aborted. Database is safe.${NC}"
    exit 0
fi

# Second confirmation with database name
echo ""
echo -e "${YELLOW}Please type the database name 'theseusdb' to confirm:${NC}"
read -p "Database name: " dbname
if [ "$dbname" != "theseusdb" ]; then
    echo -e "${GREEN}Incorrect database name. Aborted.${NC}"
    exit 0
fi

# Final confirmation
echo ""
echo -e "${RED}FINAL WARNING: This will DELETE EVERYTHING in the database!${NC}"
read -p "Type 'NUKE IT' to proceed: " final_confirm
if [ "$final_confirm" != "NUKE IT" ]; then
    echo -e "${GREEN}Aborted. Database is safe.${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}Proceeding with database destruction...${NC}"

# Get database connection details from environment or use defaults
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_USER="${POSTGRES_USER:-theseus}"
DB_PASS="${POSTGRES_PASSWORD:-theseus}"
DB_NAME="${POSTGRES_DB:-theseusdb}"

# Export password for psql
export PGPASSWORD="$DB_PASS"

echo "Connecting to PostgreSQL at $DB_HOST:$DB_PORT as user $DB_USER..."

# Create a SQL script to drop all objects
echo -e "${YELLOW}Generating drop script for all database objects...${NC}"

DROP_SCRIPT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT 
    'DROP TABLE IF EXISTS \"' || tablename || '\" CASCADE;' 
FROM pg_tables 
WHERE schemaname = 'public'
UNION ALL
SELECT 
    'DROP VIEW IF EXISTS \"' || viewname || '\" CASCADE;' 
FROM pg_views 
WHERE schemaname = 'public'
UNION ALL
SELECT 
    'DROP MATERIALIZED VIEW IF EXISTS \"' || matviewname || '\" CASCADE;' 
FROM pg_matviews 
WHERE schemaname = 'public'
UNION ALL
SELECT 
    'DROP FUNCTION IF EXISTS ' || p.oid::regprocedure || ' CASCADE;' 
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
LEFT JOIN pg_depend d ON d.objid = p.oid AND d.deptype = 'e'
WHERE n.nspname = 'public' 
  AND d.objid IS NULL  -- Exclude extension dependencies
ORDER BY 1 DESC;
")

# Execute the drop script
echo -e "${YELLOW}Dropping all tables, views, and functions...${NC}"
echo -e "${YELLOW}Note: Errors about extension functions (pgvector, pg_trgm) are expected and safe to ignore.${NC}"
echo ""

# Execute with quieter error handling
echo "$DROP_SCRIPT" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" 2>&1 | grep -v "extension.*requires it" | grep -v "HINT:.*drop extension" || true

# Get summary of what remains
echo ""
echo -e "${YELLOW}Verifying database state...${NC}"

TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';
")

VIEW_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT COUNT(*) FROM pg_views WHERE schemaname = 'public';
")

FUNCTION_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT COUNT(*) 
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
LEFT JOIN pg_depend d ON d.objid = p.oid AND d.deptype = 'e'
WHERE n.nspname = 'public' AND d.objid IS NULL;
")

echo -e "${GREEN}Database state after nuke:${NC}"
echo -e "  Tables remaining:    $TABLE_COUNT"
echo -e "  Views remaining:     $VIEW_COUNT"
echo -e "  Functions remaining: $FUNCTION_COUNT"

# Unset password
unset PGPASSWORD

echo ""
echo -e "${GREEN}✅ Database successfully nuked!${NC}"
echo -e "${GREEN}All tables and data have been removed from '$DB_NAME'.${NC}"
echo -e "${GREEN}The database and extensions (pgvector, pg_trgm) remain intact.${NC}"
echo ""
echo "Next steps:"
echo "1. Run your setup/migration scripts to test fresh installation"
echo "2. Start the application to run migrations automatically"
echo ""
echo -e "${YELLOW}Remember: This script is for DEVELOPMENT ONLY!${NC}"