#!/usr/bin/env bash
# Set up PostgreSQL extensions for Theseus Insight in Docker or local environment

set -euo pipefail

DB_USER="${POSTGRES_USER:-theseus}"
DB_PASS="${POSTGRES_PASSWORD:-theseus}"
DB_NAME="${POSTGRES_DB:-theseusdb}"

# Detect environment and set schema file path
if [ -f "/docker-entrypoint-initdb.d/init_schema_postgres.sql" ]; then
    # Running in Docker container
    SCHEMA_FILE="/docker-entrypoint-initdb.d/init_schema_postgres.sql"
    ENVIRONMENT="docker"
    echo "🐳 Detected Docker environment"
elif [ -f "$(dirname "$0")/init_schema_postgres.sql" ]; then
    # Running locally with schema file in same directory as script
    SCHEMA_FILE="$(dirname "$0")/init_schema_postgres.sql"
    ENVIRONMENT="local"
    echo "💻 Detected local environment"
else
    echo "❌ Error: Cannot find init_schema_postgres.sql"
    echo "   Expected locations:"
    echo "   - Docker: /docker-entrypoint-initdb.d/init_schema_postgres.sql" 
    echo "   - Local:  $(dirname "$0")/init_schema_postgres.sql"
    exit 1
fi

echo "Setting up pgvector extension for user: $DB_USER, database: $DB_NAME"

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
    echo "🔍 Testing connection as user '$DB_USER'..."
    if psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
        echo "✅ Successfully connected as user '$DB_USER'"
    else
        echo "⚠️  Warning: Could not connect as user '$DB_USER', but continuing..."
        echo "   You may need to update pg_hba.conf or check password authentication"
    fi
fi

# Enable pgvector extension on the database (requires superuser privileges)
echo "🔌 Enabling pgvector extension..."
if [ "$ENVIRONMENT" = "local" ]; then
    # Use superuser for extension creation in local environment
    psql -v ON_ERROR_STOP=1 -U "$SUPERUSER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
        echo "❌ Error: Failed to create pgvector extension"
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
        echo "❌ Error: Failed to create pgvector extension"
        echo "   Make sure pgvector is installed on your PostgreSQL instance"
        echo "   See: https://github.com/pgvector/pgvector#installation"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "   For macOS with Homebrew: brew install pgvector"
        fi
        exit 1
    }
fi

echo "✅ pgvector extension enabled for database \"$DB_NAME\"."

# Apply initial schema
echo "📋 Applying initial schema from: $SCHEMA_FILE"
psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_FILE" || {
    echo "❌ Error: Failed to apply schema from $SCHEMA_FILE"
    exit 1
}

echo ""
echo "🎉 Database setup completed successfully!"
echo ""
echo "📋 Connection details:"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo "   Environment: $ENVIRONMENT"
echo ""
if [ "$ENVIRONMENT" = "local" ]; then
    echo "🔗 Connection string example:"
    echo "   postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME"
    echo ""
    echo "💻 Test connection:"
    echo "   psql -U $DB_USER -d $DB_NAME -h localhost"
    echo ""
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "🍎 macOS Notes:"
        echo "   - PostgreSQL service: brew services start/stop postgresql"
        echo "   - Config location: $(brew --prefix)/var/postgres/"
        echo "   - Logs: $(brew --prefix)/var/log/postgres.log"
    fi
fi
