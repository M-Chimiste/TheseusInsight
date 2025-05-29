#!/usr/bin/env bash
# Build PostgreSQL and pgvector from source for the current platform.
set -euo pipefail

VERSION="16.2"
PLATFORM="$(uname | tr 'A-Z' 'a-z')"
PREFIX="$(dirname "$0")/postgres/${PLATFORM}"
mkdir -p "$PREFIX"

SRC_DIR="$(mktemp -d)"
trap 'rm -rf "$SRC_DIR"' EXIT

cd "$SRC_DIR"
curl -L "https://ftp.postgresql.org/pub/source/v${VERSION}/postgresql-${VERSION}.tar.gz" -o pg.tar.gz

tar -xzf pg.tar.gz
cd postgresql-${VERSION}
./configure --prefix="$PREFIX"
make -j$(nproc)
make install
cd ..

git clone --depth 1 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG="$PREFIX/bin/pg_config"
make install PG_CONFIG="$PREFIX/bin/pg_config"

cd ..
rm -rf pg.tar.gz postgresql-${VERSION} pgvector

echo "PostgreSQL built and installed to $PREFIX"
