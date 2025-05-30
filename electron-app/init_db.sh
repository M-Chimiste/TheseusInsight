#!/bin/bash

# PostgreSQL initialization script for Theseus Insight Electron app
# This script creates the required database user and database

# Set up variables
PGPORT=55432
PGHOST=localhost
# Use the current user as the database superuser (this is what initdb creates by default)
POSTGRES_USER=$(whoami)
THESEUS_USER=theseus
THESEUS_PASSWORD=theseus
THESEUS_DB=theseusdb

# Get the path to the PostgreSQL binaries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PG_BIN_DIR="$SCRIPT_DIR/postgres/$(uname -s | tr '[:upper:]' '[:lower:]')/bin"

# Check if PostgreSQL is running
if ! "$PG_BIN_DIR/pg_isready" -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" > /dev/null 2>&1; then
    echo "PostgreSQL is not running on port $PGPORT. Please start it first."
    exit 1
fi

echo "Initializing Theseus Insight database..."
echo "Connecting as user: $POSTGRES_USER"

# Create the theseus user
echo "Creating user '$THESEUS_USER'..."
"$PG_BIN_DIR/psql" -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" -d postgres -c \
    "CREATE USER $THESEUS_USER WITH PASSWORD '$THESEUS_PASSWORD';" 2>/dev/null || \
    echo "User '$THESEUS_USER' already exists or failed to create."

# Create the theseusdb database
echo "Creating database '$THESEUS_DB'..."
"$PG_BIN_DIR/psql" -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" -d postgres -c \
    "CREATE DATABASE $THESEUS_DB OWNER $THESEUS_USER;" 2>/dev/null || \
    echo "Database '$THESEUS_DB' already exists or failed to create."

# Grant privileges
echo "Granting privileges..."
"$PG_BIN_DIR/psql" -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" -d postgres -c \
    "GRANT ALL PRIVILEGES ON DATABASE $THESEUS_DB TO $THESEUS_USER;" 2>/dev/null

# Install pgvector extension
echo "Installing pgvector extension..."
"$PG_BIN_DIR/psql" -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" -d "$THESEUS_DB" -c \
    "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || \
    echo "pgvector extension installation failed or already exists."

echo "Database initialization complete!"
echo "You can now connect to the database with:"
echo "  Host: $PGHOST"
echo "  Port: $PGPORT"
echo "  Database: $THESEUS_DB"
echo "  Username: $THESEUS_USER"
echo "  Password: $THESEUS_PASSWORD" 