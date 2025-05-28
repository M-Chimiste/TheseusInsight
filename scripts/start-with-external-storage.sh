#!/usr/bin/env bash
# Helper script to start Theseus Insight with external storage
# This script redirects all data storage to an external drive or custom path

set -euo pipefail

# Default external storage path (modify as needed)
DEFAULT_EXTERNAL_PATH="/Volumes/Metis/theseus_insight_data"

# Allow override via command line argument
EXTERNAL_DATA_PATH="${1:-$DEFAULT_EXTERNAL_PATH}"

echo "🚀 Starting Theseus Insight with external storage..."
echo ""
echo "📁 Data will be stored at: $EXTERNAL_DATA_PATH"
echo ""
echo "📋 Storage structure will be:"
echo "   Application data: $EXTERNAL_DATA_PATH/app_data/"
echo "   PostgreSQL data:  $EXTERNAL_DATA_PATH/postgres_data/"
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
echo "🔧 Starting with external storage configuration..."

# Export the path for docker-compose
export EXTERNAL_DATA_PATH
export ALLOW_DB_CONNECTION=true

# Start with both the main compose file and the external storage override
docker-compose -f docker-compose.yml -f docker-compose.external-storage.yml up --build "${@:2}" 