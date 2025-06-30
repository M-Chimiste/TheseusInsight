#!/usr/bin/env python3
"""
One-time utility to generate YAKE keywords for every paper that does not yet
have them stored in the database.

Usage
-----
$ python -m theseus_insight.utils.backfill_keywords

Options
-------
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

from theseus_insight.data_access import PaperRepository
import yake  # type: ignore


def backfill_keywords(
    top_k: int = 5,
    dry_run: bool = False,
    verbose: bool = True,
):
    if verbose:
        print("Connecting to database using repository pattern...")

    # Query papers missing keywords
    papers_without_keywords = PaperRepository.get_papers_without_keywords()
    
    total_missing = len(papers_without_keywords)
    if verbose:
        print(f"Found {total_missing} papers without keywords")

    if total_missing == 0:
        return

    if dry_run:
        print("DRY RUN – showing first 10 papers to be processed:")
        for paper in papers_without_keywords[:10]:
            print(f"  • {paper['id']}: {paper['title'][:80]}…")
        return

    extractor = yake.KeywordExtractor(lan="en", n=1, top=top_k)
    updated = 0
    for paper in tqdm(papers_without_keywords, desc="Generating keywords"):
        paper_id = paper['id']
        title = paper['title']
        abstract = paper['abstract']
        text = f"{title} {abstract}"
        try:
            kw_scores = extractor.extract_keywords(text)
            keywords = [kw for kw, _ in kw_scores]
            PaperRepository.update_keywords(paper_id, keywords)
            updated += 1
        except Exception as e:
            if verbose:
                print(f"Error extracting for ID {paper_id}: {e}")
            continue

    if verbose:
        print(f"Keywords generated for {updated}/{total_missing} papers")


def main():
    parser = argparse.ArgumentParser(description="Backfill YAKE keywords for papers")
    parser.add_argument("--top-k", type=int, default=5, help="Top N keywords to keep (default 5)")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    args = parser.parse_args()

    backfill_keywords(
        top_k=args.top_k,
        dry_run=args.dry_run,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main() 