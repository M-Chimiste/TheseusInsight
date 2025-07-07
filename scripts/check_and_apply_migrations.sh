#!/usr/bin/env bash
# Intelligent migration detection and application for Theseus Insight
# This script checks which migrations need to be applied and runs them in order

set -euo pipefail

DB_USER="${POSTGRES_USER:-theseus}"
DB_PASS="${POSTGRES_PASSWORD:-theseus}"
DB_NAME="${POSTGRES_DB:-theseusdb}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect environment
if [ -f "/app/sql/init_schema_postgres.sql" ]; then
    MIGRATION_DIR="/app/sql"
    ENVIRONMENT="docker"
else
    MIGRATION_DIR="$(dirname "$0")"
    ENVIRONMENT="local"
fi

echo -e "${BLUE}🔍 Checking database migrations...${NC}"
echo "Environment: $ENVIRONMENT"
echo "Migration directory: $MIGRATION_DIR"

# Function to check if a migration has been applied
check_migration_applied() {
    local migration_name="$1"
    local result=$(psql -U "$DB_USER" -d "$DB_NAME" -tAc "
        SELECT COUNT(*) FROM schema_migrations WHERE name = '$migration_name';
    " 2>/dev/null || echo "0")
    
    if [ "$result" = "1" ]; then
        return 0  # Migration applied
    else
        return 1  # Migration not applied
    fi
}

# Function to apply a migration
apply_migration() {
    local migration_file="$1"
    local migration_name=$(basename "$migration_file")
    local version="$2"
    local description="$3"
    
    echo -e "${YELLOW}📋 Applying migration: $migration_name${NC}"
    
    # Apply the migration
    if psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f "$migration_file"; then
        # Record the migration
        psql -U "$DB_USER" -d "$DB_NAME" -c "
            INSERT INTO schema_migrations (version, name, description) 
            VALUES ($version, '$migration_name', '$description')
            ON CONFLICT (version) DO NOTHING;
        "
        echo -e "${GREEN}✅ Migration applied successfully: $migration_name${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to apply migration: $migration_name${NC}"
        return 1
    fi
}

# First, ensure migration tracking table exists
echo -e "${BLUE}📊 Setting up migration tracking...${NC}"
psql -U "$DB_USER" -d "$DB_NAME" -f "$MIGRATION_DIR/create_migration_tracking.sql" 2>/dev/null || true

# Define migrations in order
declare -A migrations=(
    [1]="init_schema_postgres.sql|Initial database schema"
    [2]="migrate_to_profiles.sql|Add research profiles feature"
    [3]="profiles_trends_integration.sql|Integrate profiles with trends"
)

# Check and apply migrations
migrations_applied=0
migrations_needed=0

for version in 1 2 3; do
    IFS='|' read -r filename description <<< "${migrations[$version]}"
    migration_path="$MIGRATION_DIR/$filename"
    
    if [ ! -f "$migration_path" ]; then
        echo -e "${YELLOW}⚠️  Migration file not found: $filename${NC}"
        continue
    fi
    
    if check_migration_applied "$filename"; then
        echo -e "${GREEN}✓ Migration already applied: $filename${NC}"
        ((migrations_applied++))
    else
        echo -e "${YELLOW}→ Migration needed: $filename${NC}"
        ((migrations_needed++))
        
        if apply_migration "$migration_path" "$version" "$description"; then
            ((migrations_applied++))
            ((migrations_needed--))
        else
            echo -e "${RED}❌ Migration failed, stopping further migrations${NC}"
            exit 1
        fi
    fi
done

# Summary
echo ""
echo -e "${BLUE}📊 Migration Summary:${NC}"
echo "  Total migrations: 3"
echo "  Already applied: $migrations_applied"
echo "  Newly applied: $migrations_needed"

# Verify database state
echo ""
echo -e "${BLUE}🔍 Verifying database state...${NC}"

# Check critical tables
critical_tables=("papers" "research_profiles" "topics")
all_good=true

for table in "${critical_tables[@]}"; do
    if psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1 FROM $table LIMIT 1;" >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Table verified: $table${NC}"
    else
        echo -e "${RED}✗ Table missing or inaccessible: $table${NC}"
        all_good=false
    fi
done

if $all_good; then
    echo -e "${GREEN}🎉 Database is ready for use!${NC}"
    exit 0
else
    echo -e "${RED}❌ Database verification failed${NC}"
    exit 1
fi