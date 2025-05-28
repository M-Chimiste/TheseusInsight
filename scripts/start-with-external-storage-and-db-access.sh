#!/usr/bin/env bash
# Helper script to start Theseus Insight with external storage AND database access
# This script redirects all data storage to an external drive AND exposes the database port

set -euo pipefail

# Default external storage path (modify as needed)
DEFAULT_EXTERNAL_PATH="/Volumes/Metis/theseus_insight_data"

# Allow override via command line argument
EXTERNAL_DATA_PATH="${1:-$DEFAULT_EXTERNAL_PATH}"

echo "🚀 Starting Theseus Insight with external storage + database access..."
echo ""
echo "📁 Data will be stored at: $EXTERNAL_DATA_PATH"
echo "🔗 Database will be accessible on: localhost:5433"
echo ""
echo "📋 Storage structure will be:"
echo "   Application data: $EXTERNAL_DATA_PATH/app_data/"
echo "   PostgreSQL data:  $EXTERNAL_DATA_PATH/postgres_data/"
echo ""
echo "🔗 Database connection details:"
echo "   Host: localhost"
echo "   Port: 5433"
echo "   Database: theseusdb"
echo "   Username: theseus"
echo "   Password: theseus"
echo "   Connection string: postgresql://theseus:theseus@localhost:5433/theseusdb"
echo ""

# Check if the external path exists and is writable
if [ ! -d "$EXTERNAL_DATA_PATH" ]; then
    echo "⚠️  Creating external data directory: $EXTERNAL_DATA_PATH"
    mkdir -p "$EXTERNAL_DATA_PATH" || {
        echo "❌ Error: Cannot create directory $EXTERNAL_DATA_PATH"
        echo "   Please check that the external drive is mounted and writable."
        exit 1
    }
fi

# Create subdirectories if they don't exist
mkdir -p "$EXTERNAL_DATA_PATH/app_data"/{newsletters,podcasts,visualizations,temp}
mkdir -p "$EXTERNAL_DATA_PATH/postgres_data"

# Check write permissions
if [ ! -w "$EXTERNAL_DATA_PATH" ]; then
    echo "❌ Error: No write permissions for $EXTERNAL_DATA_PATH"
    echo "   Please check the external drive permissions."
    exit 1
fi

echo "✅ External storage directory is ready!"
echo ""
echo "🔧 Starting with external storage + database access configuration..."

# Export the path for docker-compose
export EXTERNAL_DATA_PATH

# Start with the main compose file and the combined external storage + db access override
docker-compose -f docker-compose.yml -f docker-compose.external-storage-with-db-access.yml up --build "${@:2}" 