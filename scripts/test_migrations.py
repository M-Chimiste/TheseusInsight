#!/usr/bin/env python3
"""Test the automatic migration system for Theseus Insight.

This script can be run manually to verify migrations work correctly.
"""
import sys
import os
import pathlib

# Add parent directory to path so we can import theseus_insight modules
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from theseus_insight.db.migrations import MigrationRunner
from theseus_insight.db import get_cursor, DATABASE_URL
import psycopg
from psycopg.rows import dict_row


def test_migrations():
    """Test the migration system."""
    print(f"Testing migrations with database: {DATABASE_URL}")
    print("-" * 80)
    
    # Initialize migration runner
    runner = MigrationRunner()
    print(f"Migration directory: {runner.migration_dir}")
    print(f"Available migrations: {len(runner.migrations)}")
    for version, filename, description in runner.migrations:
        print(f"  {version}: {filename} - {description}")
    print()
    
    # Run migrations
    print("Running migrations...")
    applied, skipped, issues = runner.run_migrations()
    
    print(f"\nMigration Results:")
    print(f"  Applied: {applied}")
    print(f"  Skipped: {skipped}")
    print(f"  Issues: {len(issues)}")
    
    if issues:
        print("\nIssues encountered:")
        for issue in issues:
            print(f"  - {issue}")
    
    # Verify tables exist
    print("\nVerifying database tables...")
    try:
        with get_cursor() as cur:
            # Check migration tracking table
            cur.execute("""
                SELECT version, name, description, applied_at 
                FROM schema_migrations 
                ORDER BY version
            """)
            migrations = cur.fetchall()
            print(f"\nApplied migrations ({len(migrations)}):")
            for m in migrations:
                print(f"  v{m['version']}: {m['name']} - {m['description']}")
                print(f"    Applied at: {m['applied_at']}")
            
            # Check critical tables
            critical_tables = [
                "papers",
                "research_profiles", 
                "profile_research_interests",
                "paper_profile_scores",
                "topics",
                "settings",
                "model_providers"
            ]
            
            print(f"\nChecking critical tables:")
            all_good = True
            for table in critical_tables:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = %s
                    ) as exists
                """, (table,))
                result = cur.fetchone()
                exists = result['exists'] if result else False
                status = "✓" if exists else "✗"
                print(f"  {status} {table}")
                if not exists:
                    all_good = False
            
            # Check for default profile
            print(f"\nChecking for default profile:")
            cur.execute("""
                SELECT id, name, is_default, is_active 
                FROM research_profiles 
                WHERE is_default = TRUE
            """)
            default_profile = cur.fetchone()
            if default_profile:
                print(f"  ✓ Default profile exists: {default_profile['name']} (ID: {default_profile['id']})")
            else:
                print(f"  ✗ No default profile found")
                all_good = False
            
            # Summary
            print(f"\n{'='*80}")
            if all_good and not issues:
                print("✅ SUCCESS: Database is properly configured!")
            else:
                print("❌ ISSUES DETECTED: Please check the errors above")
                return 1
                
    except Exception as e:
        print(f"\n❌ ERROR: Failed to verify database: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    # Check if database is accessible
    try:
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        print(f"✓ Database connection successful\n")
    except Exception as e:
        print(f"❌ Cannot connect to database: {e}")
        print(f"   DATABASE_URL: {DATABASE_URL}")
        print("\nPlease ensure PostgreSQL is running and accessible")
        sys.exit(1)
    
    # Run the test
    exit_code = test_migrations()
    sys.exit(exit_code)