#!/usr/bin/env bash
# Set up PostgreSQL role and database for Theseus Insight

set -euo pipefail

DB_USER="${DB_USER:-theseus}"
DB_PASS="${DB_PASS:-theseus}"
DB_NAME="${DB_NAME:-theseusdb}"

# Commands will be executed as the postgres superuser
# Usage: run this script with a superuser account that can run `psql`

psql -v ON_ERROR_STOP=1 <<SQL
DO
\$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}'
   ) THEN
      CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';
      ALTER ROLE ${DB_USER} CREATEDB;
   END IF;
END
\$;

IF NOT EXISTS (
    SELECT FROM pg_database WHERE datname = '${DB_NAME}'
) THEN
    CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
END IF;
SQL

# Enable pgvector extension on the new database
psql -v ON_ERROR_STOP=1 -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "Database \"$DB_NAME\" and role \"$DB_USER\" are ready."
