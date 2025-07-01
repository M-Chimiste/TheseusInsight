"""PostgreSQL connection helpers for Theseus Insight.

This lightweight wrapper centralises connection creation so that the rest of
 the codebase can start moving to Postgres without an ORM. It intentionally
 mirrors the context-manager pattern already used in `PaperDatabase.get_cursor`.
 As we complete the migration, higher-level abstractions will replace the
 remaining SQLite logic.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

# Example: postgresql://user:password@localhost:5432/dbname
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb"
)


@contextmanager
def get_cursor(*, autocommit: bool = True):
    """Context manager that yields a dict-row cursor and commits on exit."""
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            yield cur
        if autocommit:
            conn.commit() 