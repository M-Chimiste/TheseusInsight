#!/usr/bin/env python3
"""
Utility script to update existing papers with full-text search vectors.
This script should be run after upgrading to the BM25-enhanced hybrid search.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from theseus_insight.data_access.base import get_cursor

def update_search_vectors():
    """Update all existing papers with full-text search vectors."""
    print("Updating papers with full-text search vectors...")
    
    try:
        with get_cursor() as cursor:
            # Check if search vector columns exist
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'papers' AND column_name IN ('search_vector', 'title_vector', 'abstract_vector')
            """)
            existing_columns = [row[0] for row in cursor.fetchall()]
            
            if len(existing_columns) < 3:
                print("Full-text search columns don't exist yet. They will be created on next API startup.")
                return
            
            # Count papers without search vectors
            cursor.execute("SELECT COUNT(*) FROM papers WHERE search_vector IS NULL")
            count_without_vectors = cursor.fetchone()[0]
            
            if count_without_vectors == 0:
                print("All papers already have search vectors. No update needed.")
                return
                
            print(f"Found {count_without_vectors} papers without search vectors. Updating...")
            
            # Update papers with search vectors
            cursor.execute("""
                UPDATE papers 
                SET 
                    search_vector = to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, '')),
                    title_vector = to_tsvector('english', COALESCE(title, '')),
                    abstract_vector = to_tsvector('english', COALESCE(abstract, ''))
                WHERE search_vector IS NULL
            """)
            
            updated_count = cursor.rowcount
            print(f"Successfully updated {updated_count} papers with search vectors.")
            
            # Verify the update
            cursor.execute("SELECT COUNT(*) FROM papers WHERE search_vector IS NOT NULL")
            total_with_vectors = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM papers")
            total_papers = cursor.fetchone()[0]
            
            print(f"Total papers: {total_papers}")
            print(f"Papers with search vectors: {total_with_vectors}")
            print("Full-text search vectors update completed successfully!")
            
    except Exception as e:
        print(f"Error updating search vectors: {e}")
        raise

if __name__ == "__main__":
    update_search_vectors() 