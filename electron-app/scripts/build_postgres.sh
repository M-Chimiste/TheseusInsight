#!/usr/bin/env bash
# Compile Postgres from source for the Electron desktop app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLATFORM="$(uname | tr '[:upper:]' '[:lower:]')"
DEST_DIR="$ROOT_DIR/postgres/$PLATFORM/bin"
mkdir -p "$DEST_DIR"

VERSION="15.5"
URL="https://ftp.postgresql.org/pub/source/v$VERSION/postgresql-$VERSION.tar.gz"
TMP_DIR="$(mktemp -d)"

echo "Downloading PostgreSQL source $VERSION..."
curl -L "$URL" -o "$TMP_DIR/postgres.tgz"
cd "$TMP_DIR"
tar -xzf postgres.tgz
cd "postgresql-$VERSION"

./configure --prefix="$DEST_DIR"
make
make install

cd "$ROOT_DIR"
rm -rf "$TMP_DIR"

echo "Postgres compiled and installed to $DEST_DIR"
