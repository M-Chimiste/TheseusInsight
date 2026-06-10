#!/usr/bin/env python3
"""Dump the FastAPI OpenAPI spec to a file without running the server.

Used by the frontend type codegen:
    cd theseus-ui && npm run generate:api

Importing theseus_insight.main touches the database at import time, so a
reachable database is required (the dev DB by default; point DATABASE_URL
at the test DB on port 5434 if the dev DB isn't running).
"""
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

os.environ.setdefault("DB_POOL_TIMEOUT", "10")
os.environ.setdefault("DB_POOL_MIN_SIZE", "1")
os.environ.setdefault("DB_POOL_MAX_SIZE", "5")

OUT = pathlib.Path(__file__).resolve().parent.parent / "theseus-ui" / "openapi.json"

def main() -> int:
    from theseus_insight.main import app

    spec = app.openapi()
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    out.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {out} ({len(spec['paths'])} paths)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
