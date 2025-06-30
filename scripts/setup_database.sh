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

# Enable pgvector extension on the database
echo "🔌 Enabling pgvector extension..."
psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
    echo "❌ Error: Failed to create pgvector extension"
    echo "   Make sure pgvector is installed on your PostgreSQL instance"
    echo "   See: https://github.com/pgvector/pgvector#installation"
    exit 1
}

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
fi
