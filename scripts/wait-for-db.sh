#!/bin/bash
# Wait for PostgreSQL to be ready

set -e

host="${DATABASE_HOST:-db}"
port="${DATABASE_PORT:-5432}"
user="${DATABASE_USER:-theseus}"
database="${DATABASE_NAME:-theseusdb}"

echo "Waiting for PostgreSQL at $host:$port..."

until pg_isready -h "$host" -p "$port" -U "$user" -d "$database"; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - executing command"
exec "$@" 