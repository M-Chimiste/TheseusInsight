#!/usr/bin/env bash
# Set up PostgreSQL extensions for Theseus Insight in Docker environment

set -euo pipefail

DB_USER="${POSTGRES_USER:-theseus}"
DB_PASS="${POSTGRES_PASSWORD:-theseus}"
DB_NAME="${POSTGRES_DB:-theseusdb}"

echo "Setting up pgvector extension for user: $DB_USER, database: $DB_NAME"

# Enable pgvector extension on the database (user and database already created by Docker)
psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "pgvector extension enabled for database \"$DB_NAME\"."
