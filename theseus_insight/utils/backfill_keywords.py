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
from uuid import UUID
from datetime import datetime
import asyncio
import asyncpg

try:
    from tqdm import tqdm
except ImportError:  # graceful fallback
    def tqdm(iterable, **kwargs):
        return iterable  # type: ignore

# Ensure project root import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from theseus_insight.data_access import PaperRepository
from theseus_insight.data_processing.checkpoint_manager import CheckpointManager
from theseus_insight.db import get_connection_pool
import yake  # type: ignore


async def backfill_keywords(
    top_k: int = 5,
    dry_run: bool = False,
    verbose: bool = True,
    batch_size: int = 100,
    limit: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    use_database_checkpoints: bool = False,
    job_id: Optional[UUID] = None
):
    pool = await get_connection_pool()
    checkpoint_manager = None
    
    if use_database_checkpoints and job_id:
        checkpoint_manager = CheckpointManager(pool)
        # Try to resume from checkpoint
        last_checkpoint = await checkpoint_manager.get_latest_checkpoint(job_id, "keywords_batch")
        if last_checkpoint:
            if verbose:
                print(f"Resuming from checkpoint: processed {last_checkpoint.get('processed_count', 0)} papers")
    
    async with pool.acquire() as conn:
        # Build query for papers missing keywords
        query_parts = ["SELECT id, title, abstract FROM papers WHERE keywords_json IS NULL"]
        params = []
        param_count = 0
        
        if start_date:
            param_count += 1
            query_parts.append(f"AND published_date >= ${param_count}")
            params.append(datetime.strptime(start_date, "%Y-%m-%d"))
            
        if end_date:
            param_count += 1
            query_parts.append(f"AND published_date <= ${param_count}")
            params.append(datetime.strptime(end_date, "%Y-%m-%d"))
            
        query_parts.append("ORDER BY published_date DESC")
        
        if limit:
            param_count += 1
            query_parts.append(f"LIMIT ${param_count}")
            params.append(limit)
            
        query = " ".join(query_parts)
        papers_without_keywords = await conn.fetch(query, *params)
    
    total_missing = len(papers_without_keywords)
    if verbose:
        print(f"Found {total_missing} papers without keywords")

    if total_missing == 0:
        if checkpoint_manager and job_id:
            await checkpoint_manager.complete_job(job_id)
        return

    if dry_run:
        print("DRY RUN – showing first 10 papers to be processed:")
        for paper in papers_without_keywords[:10]:
            print(f"  • {paper['id']}: {paper['title'][:80]}…")
        return

    extractor = yake.KeywordExtractor(lan="en", n=1, top=top_k)
    updated = 0
    failed = 0
    batch_updates = []
    
    # Check if we need to skip already processed papers
    start_index = 0
    if checkpoint_manager and job_id:
        last_checkpoint = await checkpoint_manager.get_latest_checkpoint(job_id, "keywords_batch")
        if last_checkpoint:
            start_index = last_checkpoint.get('processed_count', 0)
    
    # Process with progress bar
    with tqdm(papers_without_keywords[start_index:], desc="Generating keywords", initial=start_index) as pbar:
        for i, paper in enumerate(pbar, start=start_index):
            paper_id = paper['id']
            title = paper['title']
            abstract = paper['abstract']
            text = f"{title} {abstract}"
            
            try:
                kw_scores = extractor.extract_keywords(text)
                keywords = [kw for kw, _ in kw_scores]
                batch_updates.append((paper_id, json.dumps(keywords)))
                
                # Update database when batch is full
                if len(batch_updates) >= batch_size:
                    async with pool.acquire() as conn:
                        # Bulk update keywords
                        await conn.executemany(
                            "UPDATE papers SET keywords_json = $2 WHERE id = $1",
                            batch_updates
                        )
                    updated += len(batch_updates)
                    batch_updates = []
                    
                    # Save checkpoint
                    if checkpoint_manager and job_id:
                        await checkpoint_manager.save_checkpoint(
                            job_id,
                            "keywords_batch",
                            {"processed_count": i + 1},
                            item_count=i + 1
                        )
                    
                    pbar.set_postfix({'updated': updated, 'failed': failed})
                    
            except Exception as e:
                failed += 1
                if verbose:
                    pbar.write(f"Error extracting for ID {paper_id}: {e}")
                continue
    
    # Update any remaining papers in the batch
    if batch_updates:
        async with pool.acquire() as conn:
            await conn.executemany(
                "UPDATE papers SET keywords_json = $2 WHERE id = $1",
                batch_updates
            )
        updated += len(batch_updates)

    if checkpoint_manager and job_id:
        await checkpoint_manager.complete_job(job_id)

    if verbose:
        print(f"Keywords generated for {updated}/{total_missing} papers")
        if failed > 0:
            print(f"Failed to generate keywords for {failed} papers")


def backfill_keywords_sync(
    top_k: int = 5,
    dry_run: bool = False,
    verbose: bool = True,
    batch_size: int = 100,
):
    """Synchronous wrapper for backward compatibility."""
    asyncio.run(backfill_keywords(
        top_k=top_k,
        dry_run=dry_run,
        verbose=verbose,
        batch_size=batch_size
    ))


def main():
    parser = argparse.ArgumentParser(description="Backfill YAKE keywords for papers")
    parser.add_argument("--top-k", type=int, default=5, help="Top N keywords to keep (default 5)")
    parser.add_argument("--dry-run", action="store_true", help="Only show what would be done")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for database updates (default 100)")
    parser.add_argument("--limit", type=int, help="Limit number of papers to process")
    parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    args = parser.parse_args()

    asyncio.run(backfill_keywords(
        top_k=args.top_k,
        dry_run=args.dry_run,
        verbose=not args.quiet,
        batch_size=args.batch_size,
        limit=args.limit,
        start_date=args.start_date,
        end_date=args.end_date
    ))


if __name__ == "__main__":
    main() 