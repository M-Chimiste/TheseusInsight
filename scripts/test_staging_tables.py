#!/usr/bin/env python3
"""Test script to verify staging tables migration and bulk operations work correctly."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from theseus_insight.db import get_cursor
from theseus_insight.data_access import BulkImporter
from theseus_insight.data_model.papers import Paper
from datetime import datetime


def test_staging_tables():
    """Test that staging tables exist and bulk operations work."""
    print("🧪 Testing staging tables migration...")
    
    # Check if staging tables exist
    staging_tables = [
        'papers_staging',
        'embeddings_staging', 
        'keywords_staging',
        'paper_profile_scores_staging'
    ]
    
    print("\n📋 Checking staging tables...")
    with get_cursor() as cur:
        for table in staging_tables:
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table}'
                );
            """)
            exists = cur.fetchone()['exists']
            if exists:
                print(f"✅ Table exists: {table}")
            else:
                print(f"❌ Table missing: {table}")
                return False
    
    # Check if functions exist
    print("\n📋 Checking PostgreSQL functions...")
    functions = ['deduplicate_staging_papers', 'merge_staging_to_main']
    
    with get_cursor() as cur:
        for func in functions:
            cur.execute(f"""
                SELECT EXISTS (
                    SELECT FROM pg_proc
                    WHERE proname = '{func}'
                );
            """)
            exists = cur.fetchone()['exists']
            if exists:
                print(f"✅ Function exists: {func}")
            else:
                print(f"❌ Function missing: {func}")
                return False
    
    # Test bulk import functionality
    print("\n📋 Testing bulk import functionality...")
    try:
        importer = BulkImporter()
        
        # Create a test paper
        test_paper = Paper(
            title="Test Paper for Staging Tables",
            abstract="This is a test abstract to verify bulk import works correctly.",
            url="https://example.com/test-paper-staging",
            date=datetime.now().strftime("%Y-%m-%d"),
            date_run=datetime.now().strftime("%Y-%m-%d"),
            score=8,
            related=True,
            rationale="Test rationale",
            cosine_similarity=0.85,
            embedding_model="test-model",
            embedding=[0.1] * 768,  # Dummy embedding
            keywords=["test", "staging", "bulk"]
        )
        
        # Test staging
        importer.add_paper(test_paper)
        staged_count = importer.copy_papers_to_staging()
        print(f"✅ Successfully staged {staged_count} papers")
        
        # Test deduplication
        dup_count, new_count = importer.deduplicate_staging()
        print(f"✅ Deduplication complete: {dup_count} duplicates, {new_count} new")
        
        # Clean up (don't merge to avoid polluting main tables)
        with get_cursor() as cur:
            cur.execute(f"DELETE FROM papers_staging WHERE staging_batch_id = %s", (importer.batch_id,))
        
        print("\n🎉 All staging table tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing bulk import: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Staging Tables Migration Test")
    print("=" * 50)
    
    success = test_staging_tables()
    
    if success:
        print("\n✅ All tests passed! Staging tables are ready for use.")
        print("\n💡 To use bulk imports in harvest_and_judge:")
        print("   python -m theseus_insight.utils.harvest_and_judge --use-bulk-insert ...")
    else:
        print("\n❌ Some tests failed. Please check the migration.")
        sys.exit(1)


if __name__ == "__main__":
    main()