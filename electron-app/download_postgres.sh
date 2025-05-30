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

# Determine archive type (zip vs tar.gz) from URL so we extract correctly
if [[ "$URL" == *.zip ]]; then
  EXT="zip"
else
  EXT="tar.gz"
fi
TMP_FILE="/tmp/postgresql-${VERSION}.${EXT}"

curl -L "$URL" -o "$TMP_FILE"

if [[ "$TMP_FILE" == *.zip ]]; then
  unzip -q "$TMP_FILE" -d "$TARGET_DIR"
else
  tar -xzf "$TMP_FILE" -C "$TARGET_DIR" --strip-components=1
fi

echo "PostgreSQL binaries extracted to $TARGET_DIR"

#
# ---- Build and install pgvector extension ----
#
# pgvector provides the required VECTOR data type for similarity search.
# It is compiled against the just‑downloaded PostgreSQL using its pg_config.
#
if [[ "$PLATFORM" != msys* && "$PLATFORM" != mingw* && "$PLATFORM" != cygwin* && "$PLATFORM" != win32 ]]; then
  echo "Building pgvector for $PLATFORM ..."
  export PATH="$TARGET_DIR/bin:$PATH"          # ensure our pg_config is first
  PGVECTOR_SRC="$(mktemp -d)"
  git clone --depth 1 https://github.com/pgvector/pgvector.git "$PGVECTOR_SRC"
  cd "$PGVECTOR_SRC"
  make PG_CONFIG="$TARGET_DIR/bin/pg_config"
  make PG_CONFIG="$TARGET_DIR/bin/pg_config" install
  cd - >/dev/null
  rm -rf "$PGVECTOR_SRC"
  echo "pgvector installed into $TARGET_DIR"
else
  echo "Skipping pgvector build on Windows platforms – please install pgvector manually."
fi
