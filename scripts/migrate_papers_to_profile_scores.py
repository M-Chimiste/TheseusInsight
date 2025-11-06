#!/usr/bin/env python3
"""
One-time migration script to add existing scored papers to paper_profile_scores table.

This script takes all papers that have scores in the papers table and creates
corresponding entries in the paper_profile_scores table for a specified profile.

Usage:
    python scripts/migrate_papers_to_profile_scores.py [--profile-id 1] [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD]
"""

import os
import sys
import argparse
from datetime import datetime

# Add parent directory to path so we can import from theseus_insight
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from theseus_insight.db import get_cursor
from theseus_insight.data_access.profiles import ProfileScoreRepository


def migrate_papers_to_profile_scores(
    profile_id: int = 1,
    date_from: str = None,
    date_to: str = None,
    overwrite_existing: bool = False
):
    """
    Migrate scored papers from papers table to paper_profile_scores table.

    Args:
        profile_id: Profile ID to associate papers with (default: 1 for Default profile)
        date_from: Only migrate papers from this date onwards (YYYY-MM-DD)
        date_to: Only migrate papers up to this date (YYYY-MM-DD)
        overwrite_existing: If True, overwrite existing profile scores. If False, skip them.
    """
    print(f"\n{'='*70}")
    print(f"MIGRATION: Papers → Profile Scores")
    print(f"{'='*70}")
    print(f"Profile ID: {profile_id}")
    print(f"Date range: {date_from or 'ALL'} to {date_to or 'ALL'}")
    print(f"Overwrite existing: {overwrite_existing}")
    print(f"{'='*70}\n")

    # Build query to get scored papers
    query = """
        SELECT id, score, related, rationale, url, title
        FROM papers
        WHERE score IS NOT NULL
    """
    params = []

    if date_from:
        query += " AND date >= %s"
        params.append(date_from)

    if date_to:
        query += " AND date <= %s"
        params.append(date_to)

    query += " ORDER BY date DESC, score DESC"

    # Get all scored papers
    with get_cursor() as cur:
        cur.execute(query, params)
        papers = cur.fetchall()

    if not papers:
        print("❌ No scored papers found matching criteria.")
        return

    print(f"📊 Found {len(papers)} scored papers")

    # Check which papers already have profile scores
    existing_count = 0
    if not overwrite_existing:
        with get_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) as count
                FROM paper_profile_scores
                WHERE profile_id = %s
            """, (profile_id,))
            existing_count = cur.fetchone()['count']

        if existing_count > 0:
            print(f"⚠️  Profile {profile_id} already has {existing_count} scored papers")
            print(f"    Will skip papers that already have scores (overwrite_existing=False)")

    # Migrate papers
    migrated_count = 0
    skipped_count = 0
    error_count = 0

    print(f"\n🔄 Starting migration...")

    for i, paper in enumerate(papers, 1):
        try:
            # Check if this paper already has a profile score
            if not overwrite_existing:
                with get_cursor() as cur:
                    cur.execute("""
                        SELECT id FROM paper_profile_scores
                        WHERE paper_id = %s AND profile_id = %s
                    """, (paper['id'], profile_id))
                    existing = cur.fetchone()

                if existing:
                    skipped_count += 1
                    if i % 100 == 0:
                        print(f"   [{i}/{len(papers)}] Skipped (already exists): {paper['title'][:50]}...")
                    continue

            # Create or update profile score
            success = ProfileScoreRepository.create_or_update_score(
                paper_id=paper['id'],
                profile_id=profile_id,
                score=int(paper['score']) if paper['score'] is not None else 0,
                related=bool(paper['related']) if paper['related'] is not None else False,
                rationale=str(paper['rationale']) if paper['rationale'] else 'Migrated from papers table',
                judge_model='historical'  # Mark as historical migration
            )

            if success:
                migrated_count += 1
                if i % 100 == 0:
                    print(f"   [{i}/{len(papers)}] Migrated: {paper['title'][:50]}...")
            else:
                error_count += 1
                print(f"   ❌ Failed to migrate paper {paper['id']}: {paper['title'][:50]}...")

        except Exception as e:
            error_count += 1
            print(f"   ❌ Error migrating paper {paper['id']}: {e}")

    # Summary
    print(f"\n{'='*70}")
    print(f"MIGRATION COMPLETE")
    print(f"{'='*70}")
    print(f"✅ Migrated: {migrated_count} papers")
    if skipped_count > 0:
        print(f"⏭️  Skipped: {skipped_count} papers (already exist)")
    if error_count > 0:
        print(f"❌ Errors: {error_count} papers")
    print(f"📊 Total processed: {len(papers)} papers")
    print(f"{'='*70}\n")

    # Verify results
    with get_cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) as count
            FROM paper_profile_scores
            WHERE profile_id = %s
        """, (profile_id,))
        final_count = cur.fetchone()['count']

    print(f"🔍 Verification: Profile {profile_id} now has {final_count} scored papers in paper_profile_scores")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate scored papers to paper_profile_scores table"
    )
    parser.add_argument(
        '--profile-id',
        type=int,
        default=1,
        help='Profile ID to associate papers with (default: 1)'
    )
    parser.add_argument(
        '--date-from',
        type=str,
        help='Only migrate papers from this date onwards (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--date-to',
        type=str,
        help='Only migrate papers up to this date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing profile scores (default: skip existing)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without actually doing it'
    )

    args = parser.parse_args()

    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be made\n")
        # Just count what would be migrated
        query = "SELECT COUNT(*) as count FROM papers WHERE score IS NOT NULL"
        params = []

        if args.date_from:
            query += " AND date >= %s"
            params.append(args.date_from)

        if args.date_to:
            query += " AND date <= %s"
            params.append(args.date_to)

        with get_cursor() as cur:
            cur.execute(query, params)
            count = cur.fetchone()['count']

        print(f"Would migrate {count} papers to profile {args.profile_id}")
        return

    # Confirm before proceeding
    print("\n⚠️  WARNING: This will modify the database")
    response = input("Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Cancelled")
        return

    migrate_papers_to_profile_scores(
        profile_id=args.profile_id,
        date_from=args.date_from,
        date_to=args.date_to,
        overwrite_existing=args.overwrite
    )


if __name__ == '__main__':
    main()
