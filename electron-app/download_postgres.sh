#!/usr/bin/env bash
# Download prebuilt PostgreSQL binaries for the current platform.
set -euo pipefail

VERSION="16.2"
PLATFORM="$(uname | tr 'A-Z' 'a-z')"
TARGET_DIR="$(dirname "$0")/postgres/${PLATFORM}"
mkdir -p "$TARGET_DIR"

case "$PLATFORM" in
  darwin)
    URL="https://get.enterprisedb.com/postgresql/postgresql-${VERSION}-1-osx-binaries.tar.gz"
    ;;
  linux)
    URL="https://get.enterprisedb.com/postgresql/postgresql-${VERSION}-1-linux-x64-binaries.tar.gz"
    ;;
  msys*|mingw*|cygwin*|win32)
    URL="https://get.enterprisedb.com/postgresql/postgresql-${VERSION}-1-windows-x64-binaries.zip"
    ;;
  *)
    echo "Unsupported platform $PLATFORM" >&2
    exit 1
    ;;
esac

echo "Downloading PostgreSQL ${VERSION} for $PLATFORM..."
TMP_FILE="/tmp/postgresql-${VERSION}.tar.gz"
curl -L "$URL" -o "$TMP_FILE"

if [[ "$TMP_FILE" == *.zip ]]; then
  unzip -q "$TMP_FILE" -d "$TARGET_DIR"
else
  tar -xzf "$TMP_FILE" -C "$TARGET_DIR" --strip-components=1
fi

echo "PostgreSQL binaries extracted to $TARGET_DIR"
