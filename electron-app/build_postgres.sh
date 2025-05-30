#!/usr/bin/env bash
# Build PostgreSQL and pgvector from source for the current platform.
set -euo pipefail

VERSION="14.18"
PLATFORM="$(uname | tr 'A-Z' 'a-z')"
 # --prefix must be an absolute path
PREFIX="$(cd "$(dirname "$0")" && pwd)/postgres/${PLATFORM}"
mkdir -p "$PREFIX"

SRC_DIR="$(mktemp -d)"
trap 'rm -rf "$SRC_DIR"' EXIT

cd "$SRC_DIR"
curl -L "https://ftp.postgresql.org/pub/source/v${VERSION}/postgresql-${VERSION}.tar.gz" -o pg.tar.gz

tar -xzf pg.tar.gz
cd postgresql-${VERSION}
./configure --prefix="$PREFIX"
if command -v nproc >/dev/null 2>&1; then
  JOBS=$(nproc)
else
  JOBS=$(sysctl -n hw.ncpu)
fi
make -j${JOBS}
make install
cd ..

git clone --depth 1 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG="$PREFIX/bin/pg_config"
make install PG_CONFIG="$PREFIX/bin/pg_config"

cd ..
rm -rf pg.tar.gz postgresql-${VERSION} pgvector

echo "PostgreSQL built and installed to $PREFIX"
echo "pgvector extension compiled and installed as well"
