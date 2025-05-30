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
# Handle both development and packaged app scenarios
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Try to detect if we're running in a packaged Electron app
if [[ -n "$ELECTRON_RESOURCES_PATH" ]]; then
    # Running in packaged app - use the app bundle resources
    APP_DIR="$ELECTRON_RESOURCES_PATH/app"
    PG_BIN_DIR="$APP_DIR/postgres/$(uname -s | tr '[:upper:]' '[:lower:]')/bin"
    echo "Detected packaged app environment, using: $PG_BIN_DIR"
elif [[ "$SCRIPT_DIR" == */tmp/* ]] || [[ "$SCRIPT_DIR" == */var/folders/* ]]; then
    # Script is in temp directory, likely extracted from asar
    # Try to find the app bundle resources
    if [[ -n "$ELECTRON_IS_PACKAGED" && "$ELECTRON_IS_PACKAGED" == "true" ]]; then
        # Use environment variable set by main.js
        APP_DIR="$ELECTRON_RESOURCES_PATH/app"
        PG_BIN_DIR="$APP_DIR/postgres/$(uname -s | tr '[:upper:]' '[:lower:]')/bin"
        echo "Using packaged app PostgreSQL: $PG_BIN_DIR"
    else
        echo "Error: Cannot locate PostgreSQL binaries from temp directory"
        exit 1
    fi
else
    # Running in development mode
    PG_BIN_DIR="$SCRIPT_DIR/postgres/$(uname -s | tr '[:upper:]' '[:lower:]')/bin"
    echo "Using development PostgreSQL: $PG_BIN_DIR"
fi

# Verify PostgreSQL binaries exist
if [[ ! -x "$PG_BIN_DIR/pg_isready" ]]; then
    echo "Error: PostgreSQL binaries not found at $PG_BIN_DIR"
    echo "pg_isready executable not found or not executable"
    exit 1
fi

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