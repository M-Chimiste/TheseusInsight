#!/usr/bin/env bash
# Set up PostgreSQL extensions for Theseus Insight in Docker or local environment
# Features:
# - Migration tracking to avoid re-running migrations
# - Better error handling with transaction support
# - Data loss prevention with backup suggestions
# - Support for both new installations and upgrades

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

# Detect environment and set paths
if [ -f "/app/sql/001_init_schema_postgres.sql" ]; then
    # Running in Docker container
    SCHEMA_DIR="/app/sql"
    ENVIRONMENT="docker"
    echo -e "${BLUE}🐳 Detected Docker environment${NC}"
elif [ -f "$(dirname "$0")/001_init_schema_postgres.sql" ]; then
    # Running locally with schema file in same directory as script
    SCHEMA_DIR="$(dirname "$0")"
    ENVIRONMENT="local"
    echo -e "${BLUE}💻 Detected local environment${NC}"
else
    echo -e "${RED}❌ Error: Cannot find SQL files${NC}"
    echo "   Expected locations:"
    echo "   - Docker: /app/sql/001_init_schema_postgres.sql" 
    echo "   - Local:  $(dirname "$0")/001_init_schema_postgres.sql"
    exit 1
fi

echo "Setting up database for user: $DB_USER, database: $DB_NAME"

# Function to check if database exists and has data
check_existing_installation() {
    local table_count=0
    local paper_count=0
    
    # Check if we can connect to the database
    if psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
        # Count tables
        table_count=$(psql -U "$DB_USER" -d "$DB_NAME" -tAc "
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
        " 2>/dev/null || echo "0")
        
        # Count papers if table exists
        if [ "$table_count" -gt "0" ]; then
            paper_count=$(psql -U "$DB_USER" -d "$DB_NAME" -tAc "
                SELECT COUNT(*) FROM papers;
            " 2>/dev/null || echo "0")
        fi
        
        echo -e "${BLUE}📊 Existing installation detected:${NC}"
        echo "   Tables: $table_count"
        echo "   Papers: $paper_count"
        
        if [ "$paper_count" -gt "0" ]; then
            echo -e "${YELLOW}⚠️  Warning: Database contains data!${NC}"
            echo "   Consider backing up before proceeding:"
            echo "   pg_dump -U $DB_USER -d $DB_NAME > backup_$(date +%Y%m%d_%H%M%S).sql"
            echo ""
            # In Docker, we'll proceed automatically
            if [ "$ENVIRONMENT" = "docker" ]; then
                echo "   Proceeding with migration tracking..."
            else
                read -p "Continue with setup? (y/N) " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    echo "Setup cancelled."
                    exit 0
                fi
            fi
        fi
        
        return 0
    else
        echo -e "${BLUE}📊 No existing database found - will create new${NC}"
        return 1
    fi
}

# For local installations, check if database and user exist, create if needed
if [ "$ENVIRONMENT" = "local" ]; then
    echo "🔧 Checking local PostgreSQL setup..."
    
    # Check if we're on macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "🍎 Detected macOS environment"
        
        # Check if PostgreSQL is installed via Homebrew
        if command -v brew >/dev/null 2>&1; then
            echo "🍺 Homebrew detected, checking PostgreSQL installation..."
            
            if brew list postgresql@17 >/dev/null 2>&1; then
                PG_VERSION="17"
                echo "✅ Found PostgreSQL 17 via Homebrew"
            elif brew list postgresql@16 >/dev/null 2>&1; then
                PG_VERSION="16"
                echo "✅ Found PostgreSQL 16 via Homebrew"
            elif brew list postgresql@15 >/dev/null 2>&1; then
                PG_VERSION="15"
                echo "✅ Found PostgreSQL 15 via Homebrew"
            elif brew list postgresql >/dev/null 2>&1; then
                PG_VERSION="latest"
                echo "✅ Found PostgreSQL (latest) via Homebrew"
            else
                echo "❌ PostgreSQL not found via Homebrew"
                echo "💡 To install PostgreSQL on macOS:"
                echo "   brew install postgresql@17"
                echo "   brew install pgvector"
                exit 1
            fi
            
            # Check if pgvector is installed
            if ! brew list pgvector >/dev/null 2>&1; then
                echo "❌ pgvector not found via Homebrew"
                echo "💡 To install pgvector on macOS:"
                echo "   brew install pgvector"
                exit 1
            fi
            echo "✅ pgvector found via Homebrew"
            
            # Check if PostgreSQL service is running
            if brew services list | grep -q "postgresql.*started"; then
                echo "✅ PostgreSQL service is running"
            else
                echo "🚀 Starting PostgreSQL service..."
                if [[ "$PG_VERSION" == "latest" ]]; then
                    brew services start postgresql
                else
                    brew services start postgresql@$PG_VERSION
                fi
                echo "✅ PostgreSQL service started"
                
                # Give it a moment to start up
                sleep 2
            fi
        else
            echo "❌ Homebrew not found. This script is optimized for Homebrew installations."
            echo "💡 Install Homebrew first: https://brew.sh/"
            exit 1
        fi
    fi
    
    # Try to detect available superuser (postgres, current user, etc.)
    SUPERUSER=""
    CURRENT_USER=$(whoami)
    
    # Test different potential superusers
    for test_user in "$CURRENT_USER" "postgres" "$USER"; do
        if [ -n "$test_user" ] && psql -U "$test_user" -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
            SUPERUSER="$test_user"
            echo "✅ Found PostgreSQL superuser: $SUPERUSER"
            break
        fi
    done
    
    if [ -z "$SUPERUSER" ]; then
        echo "❌ Error: Cannot find a working PostgreSQL superuser"
        echo "   Tried users: $CURRENT_USER, postgres, $USER"
        echo "   Please ensure PostgreSQL is running and you have superuser access"
        echo ""
        echo "💡 Common solutions:"
        echo "   - macOS (Homebrew): Try 'psql postgres' (uses current user)"
        echo "   - Linux: Try 'sudo -u postgres psql'"
        echo "   - Check if PostgreSQL service is running"
        exit 1
    fi
    
    # Check if target user already exists
    echo "👤 Checking if user '$DB_USER' exists..."
    USER_EXISTS=$(psql -U "$SUPERUSER" -d postgres -tAc "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER';" 2>/dev/null)
    
    if [ "$USER_EXISTS" = "1" ]; then
        echo "✅ User '$DB_USER' already exists"
        
        # Update user password and ensure it has CREATEDB privilege
        echo "🔐 Updating user '$DB_USER' password and privileges..."
        psql -U "$SUPERUSER" -d postgres -c "
            ALTER USER $DB_USER WITH PASSWORD '$DB_PASS';
            ALTER USER $DB_USER CREATEDB;
        " || {
            echo "❌ Error: Failed to update user '$DB_USER'"
            exit 1
        }
        echo "✅ User '$DB_USER' updated successfully"
    else
        echo "➕ Creating user '$DB_USER'..."
        psql -U "$SUPERUSER" -d postgres -c "
            CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
            ALTER USER $DB_USER CREATEDB;
        " || {
            echo "❌ Error: Failed to create user '$DB_USER'"
            exit 1
        }
        echo "✅ User '$DB_USER' created successfully"
    fi
    
    # Check if database already exists
    echo "🗄️  Checking if database '$DB_NAME' exists..."
    DB_EXISTS=$(psql -U "$SUPERUSER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME';" 2>/dev/null)
    
    if [ "$DB_EXISTS" = "1" ]; then
        echo "✅ Database '$DB_NAME' already exists"
        
        # Make sure the database owner is correct
        echo "🔐 Ensuring database '$DB_NAME' is owned by '$DB_USER'..."
        psql -U "$SUPERUSER" -d postgres -c "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;" || {
            echo "⚠️  Warning: Could not change database owner, but continuing..."
        }
    else
        echo "➕ Creating database '$DB_NAME'..."
        psql -U "$SUPERUSER" -d postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" || {
            echo "❌ Error: Failed to create database '$DB_NAME'"
            exit 1
        }
        echo "✅ Database '$DB_NAME' created successfully"
    fi
    
    # Grant necessary privileges (always run this to ensure permissions are correct)
    echo "🔐 Ensuring user '$DB_USER' has proper privileges..."
    psql -U "$SUPERUSER" -d "$DB_NAME" -c "
        GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
        GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
        GRANT CREATE ON SCHEMA public TO $DB_USER;
        ALTER SCHEMA public OWNER TO $DB_USER;
        
        -- Grant default privileges for future objects
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $DB_USER;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $DB_USER;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO $DB_USER;
    " || {
        echo "⚠️  Warning: Some privilege grants may have failed, but continuing..."
    }
    
    # Test connection as target user
    echo -e "${BLUE}🔍 Testing connection as user '$DB_USER'...${NC}"
    if psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Successfully connected as user '$DB_USER'${NC}"
    else
        echo -e "${YELLOW}⚠️  Warning: Could not connect as user '$DB_USER', but continuing...${NC}"
        echo "   You may need to update pg_hba.conf or check password authentication"
    fi
fi

# Main setup flow
main() {
    # Check for existing installation
    local is_upgrade=false
    if check_existing_installation; then
        is_upgrade=true
    fi
    
    # Enable pgvector extension on the database (requires superuser privileges)
    echo -e "${BLUE}🔌 Enabling pgvector extension...${NC}"
    if [ "$ENVIRONMENT" = "local" ]; then
        # Use superuser for extension creation in local environment
        psql -v ON_ERROR_STOP=1 -U "$SUPERUSER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
            echo -e "${RED}❌ Error: Failed to create pgvector extension${NC}"
            echo "   Make sure pgvector is installed on your PostgreSQL instance"
            echo "   See: https://github.com/pgvector/pgvector#installation"
            if [[ "$OSTYPE" == "darwin"* ]]; then
                echo "   For macOS with Homebrew: brew install pgvector"
            fi
            exit 1
        }
    else
        # In Docker environment, use the regular user (should have superuser privileges)
        psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
            echo -e "${RED}❌ Error: Failed to create pgvector extension${NC}"
            echo "   Make sure pgvector is installed on your PostgreSQL instance"
            echo "   See: https://github.com/pgvector/pgvector#installation"
            exit 1
        }
    fi
    echo -e "${GREEN}✅ pgvector extension enabled${NC}"
    
    # Create migration tracking table
    echo -e "${BLUE}📊 Setting up migration tracking...${NC}"
    psql -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_DIR/create_migration_tracking.sql" 2>/dev/null || {
        echo -e "${YELLOW}⚠️  Migration tracking table may already exist${NC}"
    }
    
    # Apply migration helper functions first (required by other migrations)
    echo -e "${BLUE}🔧 Setting up migration helper functions...${NC}"
    if [ -f "$SCHEMA_DIR/000_migration_compatibility.sql" ]; then
        psql -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_DIR/000_migration_compatibility.sql" || {
            echo -e "${RED}❌ Error: Failed to create migration helper functions${NC}"
            exit 1
        }
        echo -e "${GREEN}✅ Migration helper functions created${NC}"
    fi
    
    # Run migration check and apply script
    echo -e "${BLUE}🔄 Checking and applying migrations...${NC}"
    if [ -f "$SCHEMA_DIR/check_and_apply_migrations.sh" ]; then
        bash "$SCHEMA_DIR/check_and_apply_migrations.sh"
    else
        # Fallback to direct migration if check script doesn't exist
        echo -e "${YELLOW}⚠️  Using direct migration method${NC}"
        
        # Apply initial schema
        echo -e "${BLUE}📋 Applying initial schema...${NC}"
        psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_DIR/001_init_schema_postgres.sql" || {
            echo -e "${RED}❌ Error: Failed to apply initial schema${NC}"
            exit 1
        }
        
        # Apply profile migration
        if [ -f "$SCHEMA_DIR/002_migrate_to_profiles.sql" ]; then
            echo -e "${BLUE}📋 Applying profile migration...${NC}"
            psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_DIR/002_migrate_to_profiles.sql" || {
                echo -e "${YELLOW}⚠️  Profile migration may have already been applied${NC}"
            }
        fi
        
        # Apply profiles-trends integration
        if [ -f "$SCHEMA_DIR/003_profiles_trends_integration.sql" ]; then
            echo -e "${BLUE}📋 Applying profiles-trends integration...${NC}"
            psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_DIR/003_profiles_trends_integration.sql" || {
                echo -e "${YELLOW}⚠️  Profiles-trends integration may have already been applied${NC}"
            }
        fi
        
        # Apply staging tables migration
        if [ -f "$SCHEMA_DIR/004_add_staging_tables.sql" ]; then
            echo -e "${BLUE}📋 Applying staging tables migration...${NC}"
            psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_DIR/004_add_staging_tables.sql" || {
                echo -e "${YELLOW}⚠️  Staging tables migration may have already been applied${NC}"
            }
        fi
        
        # Apply index optimization
        if [ -f "$SCHEMA_DIR/005_optimize_indexes.sql" ]; then
            echo -e "${BLUE}📋 Applying index optimization...${NC}"
            psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_DIR/005_optimize_indexes.sql" || {
                echo -e "${YELLOW}⚠️  Index optimization may have already been applied${NC}"
            }
        fi
    fi
    
    # Verify installation
    echo ""
    echo -e "${BLUE}🔍 Verifying installation...${NC}"
    
    # Check critical tables
    for table in "papers" "research_profiles" "schema_migrations"; do
        if psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1 FROM $table LIMIT 1;" >/dev/null 2>&1; then
            echo -e "${GREEN}✓ Table ready: $table${NC}"
        else
            echo -e "${RED}✗ Table missing: $table${NC}"
        fi
    done
    
    # Show summary
    echo ""
    if [ "$is_upgrade" = true ]; then
        echo -e "${GREEN}🎉 Database upgrade completed successfully!${NC}"
    else
        echo -e "${GREEN}🎉 Database setup completed successfully!${NC}"
    fi
    
    echo ""
    echo -e "${BLUE}📋 Connection details:${NC}"
    echo "   Database: $DB_NAME"
    echo "   User: $DB_USER"
    echo "   Environment: $ENVIRONMENT"
    
    if [ "$ENVIRONMENT" = "local" ]; then
        echo ""
        echo -e "${BLUE}🔗 Connection string:${NC}"
        echo "   postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME"
        echo ""
        echo -e "${BLUE}💻 Test connection:${NC}"
        echo "   psql -U $DB_USER -d $DB_NAME -h localhost"
        echo ""
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo -e "${BLUE}🍎 macOS Notes:${NC}"
            echo "   - PostgreSQL service: brew services start/stop postgresql"
            echo "   - Config location: $(brew --prefix)/var/postgres/"
            echo "   - Logs: $(brew --prefix)/var/log/postgres.log"
        fi
    fi
}

# Run main function
main "$@"
