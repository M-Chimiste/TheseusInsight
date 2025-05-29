#!/usr/bin/env bash
# Download prebuilt Postgres binaries for use with the Electron desktop app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PLATFORM="$(uname | tr '[:upper:]' '[:lower:]')"
DEST_DIR="$ROOT_DIR/postgres/$PLATFORM/bin"
mkdir -p "$DEST_DIR"

case "$PLATFORM" in
  darwin*)
    URL="https://get.enterprisedb.com/postgresql/postgresql-15.5-1-osx-binaries.tar.gz"
    ARCHIVE="postgres-darwin.tgz"
    ;;
  linux*)
    URL="https://get.enterprisedb.com/postgresql/postgresql-15.5-1-linux-x64-binaries.tar.gz"
    ARCHIVE="postgres-linux.tgz"
    ;;
  msys*|mingw*|cygwin*|windows*)
    URL="https://get.enterprisedb.com/postgresql/postgresql-15.5-1-windows-x64-binaries.zip"
    ARCHIVE="postgres-win.zip"
    ;;
  *)
    echo "Unsupported platform: $PLATFORM" >&2
    exit 1
    ;;
esac

TMP_FILE="$(mktemp)"
echo "Downloading Postgres binaries for $PLATFORM..."
curl -L "$URL" -o "$TMP_FILE"

if [[ "$ARCHIVE" == *.zip ]]; then
  unzip -q "$TMP_FILE" -d "$DEST_DIR"
else
  tar -xzf "$TMP_FILE" -C "$DEST_DIR" --strip-components=1
fi

rm "$TMP_FILE"
echo "Postgres binaries extracted to $DEST_DIR"
