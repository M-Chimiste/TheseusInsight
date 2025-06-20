#!/usr/bin/env python3
"""
One-time utility to generate YAKE keywords for every paper that does not yet
have them stored in the database.

Usage
-----
$ python -m theseus_insight.utils.backfill_keywords --db-path data/theseus.db

Options
-------
--db-path PATH           Path to SQLite database (defaults to $DATABASE_URL
                         env var or ``data/theseus.db``)
--top-k N                How many keywords to keep (default 5)
--dry-run                Show which papers would be updated without writing
--verbose                Extra logging

The script is *idempotent*: it only writes keywords for papers whose
``keywords_json`` column is NULL/empty.
"""

import os
import sys
import json
import argparse
from typing import Optional

try:
    from tqdm import tqdm
except ImportError:  # graceful fallback
    def tqdm(iterable, **kwargs):
        return iterable  # type: ignore

# Ensure project root import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from theseus_insight.data_model.data_handling import PaperDatabase
import yake  # type: ignore


def backfill_keywords(
    db_path: str,
    top_k: int = 5,
    dry_run: bool = False,
    verbose: bool = True,
):
    if verbose:
        print(f"Connecting to database: {db_path}")
    db = PaperDatabase(db_path)

    # Query papers missing keywords
    with db.get_cursor(register_vectors=False) as cur:
        cur.execute(
            "SELECT id, title, abstract FROM papers WHERE keywords_json IS NULL OR keywords_json = ''"
        )
        rows = cur.fetchall()

    total_missing = len(rows)
    if verbose:
        print(f"Found {total_missing} papers without keywords")

    if total_missing == 0:
        return

    if dry_run:
        print("DRY RUN – showing first 10 papers to be processed:")
        for row in rows[:10]:
            print(f"  • {row[0]}: {row[1][:80]}…")
        return

    extractor = yake.KeywordExtractor(lan="en", n=1, top=top_k)
    updated = 0
    for row in tqdm(rows, desc="Generating keywords"):
        paper_id, title, abstract = row
        text = f"{title} {abstract}"
        try:
            kw_scores = extractor.extract_keywords(text)
            keywords = [kw for kw, _ in kw_scores]
            db.update_paper_keywords(paper_id, keywords)
            updated += 1
        except Exception as e:
            if verbose:
                print(f"Error extracting for ID {paper_id}: {e}")
            continue

    if verbose:
        print(f"Keywords generated for {updated}/{total_missing} papers")


def main():
    parser = argparse.ArgumentParser(description="Backfill YAKE keywords for papers")
    parser.add_argument("--db-path", default=os.getenv("DATABASE_URL", "data/theseus.db"), help="SQLite DB path")
    parser.add_argument("--top-k", type=int, default=5, help="Top N keywords to keep (default 5)")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = parser.parse_args()

    backfill_keywords(
        db_path=args.db_path,
        top_k=args.top_k,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main() 