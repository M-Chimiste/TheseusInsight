#!/usr/bin/env bash
# Helper script to start Theseus Insight with external database access enabled
# This allows connecting to the PostgreSQL database from external tools for migration,
# data population, debugging, or administration tasks.

set -euo pipefail

echo "🚀 Starting Theseus Insight with external database access..."
echo ""
echo "⚠️  SECURITY WARNING: Database will be accessible from host machine on port 5433"
echo "   Only use this in development environments or secure networks."
echo ""
echo "📋 Connection details:"
echo "   Host: localhost"
echo "   Port: 5433"
echo "   Database: theseusdb"
echo "   Username: theseus"
echo "   Password: theseus"
echo ""
echo "💻 Example connection commands:"
echo "   psql: psql -h localhost -p 5433 -U theseus -d theseusdb"
echo "   pgAdmin: Server: localhost:5433, User: theseus, DB: theseusdb"
echo ""

# Set environment variable to indicate external access is enabled
export ALLOW_DB_CONNECTION=true

# Start with both the main compose file and the external database override
docker-compose -f docker-compose.yml -f docker-compose.db-external.yml up --build "$@" 