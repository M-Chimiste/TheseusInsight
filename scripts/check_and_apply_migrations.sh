#!/usr/bin/env bash
# Intelligent migration detection and application for Theseus Insight
# This script checks which migrations need to be applied and runs them in order

set -euo pipefail

# Ensure we're running with bash, not sh
if [ -z "$BASH_VERSION" ]; then
    echo "Error: This script must be run with bash, not sh"
    echo "Please run: bash $0 or ./$0"
    exit 1
fi

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

# Define migrations in order (using regular arrays for compatibility)
migration_files=(
    "000_migration_compatibility.sql"
    "001_init_schema_postgres.sql"
    "002_migrate_to_profiles.sql"
    "003_profiles_trends_integration.sql"
    "004_add_staging_tables.sql"
    "005_optimize_indexes.sql"
    "006_add_processing_checkpoints.sql"
    "007_add_scheduled_tasks.sql"
    "008_add_multi_ollama_support.sql"
    "009_add_lmstudio_multi_server.sql"
    "010_add_per_server_model_config.sql"
)

migration_descriptions=(
    "Migration helper functions"
    "Initial database schema"
    "Add research profiles feature"
    "Integrate profiles with trends"
    "Add staging tables for bulk operations"
    "Optimize indexes for performance"
    "Add checkpoint system for resumable processing"
    "Add scheduled task system"
    "Add multi-Ollama server support for bulk judge operations"
    "Add LMStudio multi-server support and rename to inference_servers"
    "Add per-server model name and config overrides for non-homogeneous deployments"
)

# Check and apply migrations
migrations_applied=0
migrations_needed=0

for i in ${!migration_files[@]}; do
    version=$((i + 1))
    filename="${migration_files[$i]}"
    description="${migration_descriptions[$i]}"
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
echo "  Total migrations: ${#migration_files[@]}"
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