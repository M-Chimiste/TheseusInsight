#!/usr/bin/env python3
"""
Database Migration Example

This script demonstrates how to use the updated Theseus Insight database migration tools
that now support MindMap and Research Agent data.

The migration system is backwards compatible - you can:
1. Export/import older databases without the new tables
2. Export/import with the new tables included (default)
3. Selectively exclude new tables for backwards compatibility
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the parent directory to the path so we can import the migration modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from theseus_insight.utils.db_migration import DatabaseExporter, DatabaseImporter, DatabaseMigrator


def example_export_with_new_tables():
    """Example: Export database including new MindMap and Research Agent tables."""
    print("=== Example: Export with New Tables (Default) ===")
    
    source_db_path = "data/papers.db"  # Adjust path as needed
    output_dir = "temp_export"
    
    try:
        exporter = DatabaseExporter(source_db_path, output_dir)
        
        # Export with new tables included (default behavior)
        result = exporter.export_all(
            create_archive=True,
            archive_name="full_export_with_new_features"
        )
        
        print(f"Export completed!")
        print(f"Files exported: {list(result['files'].keys())}")
        print(f"Archive created: {result.get('archive', 'No archive created')}")
        
        return result
        
    except Exception as e:
        print(f"Export failed: {e}")
        return None


def example_export_backwards_compatible():
    """Example: Export database excluding new tables for backwards compatibility."""
    print("\n=== Example: Export for Backwards Compatibility ===")
    
    source_db_path = "data/papers.db"  # Adjust path as needed
    output_dir = "temp_export_compat"
    
    try:
        exporter = DatabaseExporter(source_db_path, output_dir)
        
        # Export without new tables (backwards compatible)
        result = exporter.export_all(
            create_archive=True,
            archive_name="backwards_compatible_export",
            include_new_tables=False  # Exclude new tables
        )
        
        print(f"Export completed!")
        print(f"Files exported: {list(result['files'].keys())}")
        print(f"Archive created: {result.get('archive', 'No archive created')}")
        
        return result
        
    except Exception as e:
        print(f"Export failed: {e}")
        return None


def example_import_with_auto_detection():
    """Example: Import database with automatic new table detection."""
    print("\n=== Example: Import with Auto Detection ===")
    
    archive_path = "temp_export/full_export_with_new_features.tar.gz"
    target_db_path = "data/imported_papers.db"
    
    try:
        importer = DatabaseImporter(target_db_path)
        
        # Import will automatically detect and handle new tables if present
        result = importer.import_all(archive_path, skip_duplicates=True)
        
        print(f"Import completed!")
        for table, stats in result.items():
            if isinstance(stats, dict) and 'imported' in stats:
                print(f"{table}: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
            elif isinstance(stats, dict) and 'note' in stats:
                print(f"{table}: {stats['note']}")
            elif isinstance(stats, dict) and 'error' in stats:
                print(f"{table}: {stats['error']}")
        
        return result
        
    except Exception as e:
        print(f"Import failed: {e}")
        return None


def example_full_migration():
    """Example: Complete migration between databases."""
    print("\n=== Example: Full Database Migration ===")
    
    source_db_path = "data/papers.db"
    target_db_path = "data/migrated_papers.db"
    
    try:
        migrator = DatabaseMigrator()
        
        # Migrate including new tables
        result = migrator.migrate_database(
            source_db=source_db_path,
            target_db=target_db_path,
            skip_duplicates=True,
            keep_archive=True,
            archive_path="migration_backup.tar.gz",
            include_new_tables=True  # Include new tables
        )
        
        print(f"Migration completed!")
        print(f"Export result: {result['export']['files'].keys()}")
        print(f"Import result available for each table")
        
        # Verify the migration
        verification = migrator.verify_migration(source_db_path, target_db_path)
        print(f"\nVerification Results:")
        for table, stats in verification.items():
            if table == "overall_success":
                continue
            if isinstance(stats, dict) and "match" in stats:
                status = "✓" if stats["match"] else "✗"
                print(f"{status} {table}: {stats['source_count']} → {stats['target_count']}")
            else:
                print(f"- {table}: {stats.get('note', 'Not verified')}")
        
        print(f"\nOverall success: {'✓' if verification['overall_success'] else '✗'}")
        
        return result
        
    except Exception as e:
        print(f"Migration failed: {e}")
        return None


def example_new_table_operations():
    """Example: Working with the new tables specifically."""
    print("\n=== Example: New Table Operations ===")
    
    from theseus_insight.data_model.data_handling import PaperDatabase
    
    db_path = "data/papers.db"
    
    try:
        db = PaperDatabase(db_path)
        
        # Check for new table data
        print("Checking for new table data...")
        
        # Research Agent data
        research_runs = db.get_research_runs_history(limit=5)
        print(f"Research runs found: {len(research_runs)}")
        
        # MindMap data
        mindmap_reports = db.get_mindmap_reports(limit=5)
        print(f"MindMap reports found: {len(mindmap_reports)}")
        
        # Model catalog data
        model_catalog = db.search_model_catalog(page_size=5)
        print(f"Model catalog entries found: {len(model_catalog['models'])}")
        
        # Full-text papers
        papers_without_fulltext = db.get_papers_without_fulltext(limit=5)
        print(f"Papers without full-text: {len(papers_without_fulltext)}")
        
        print("New table data check completed!")
        
    except Exception as e:
        print(f"New table operations failed: {e}")


def cleanup_temp_files():
    """Clean up temporary files created during examples."""
    print("\n=== Cleanup ===")
    
    temp_dirs = ["temp_export", "temp_export_compat"]
    temp_files = ["migration_backup.tar.gz"]
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
            print(f"Removed directory: {temp_dir}")
    
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            os.remove(temp_file)
            print(f"Removed file: {temp_file}")


def main():
    """Run all migration examples."""
    print("Theseus Insight Database Migration Examples")
    print("=" * 50)
    
    # Check if database exists
    if not os.path.exists("data/papers.db"):
        print("Warning: Database file 'data/papers.db' not found.")
        print("Please adjust the database paths in the examples or create a test database.")
        print("\nShowing examples with placeholder data...")
    
    # Run examples
    try:
        # Example 1: Export with new tables
        export_result = example_export_with_new_tables()
        
        # Example 2: Export for backwards compatibility
        compat_result = example_export_backwards_compatible()
        
        # Example 3: Import with auto-detection
        if export_result and export_result.get('archive'):
            example_import_with_auto_detection()
        
        # Example 4: Full migration
        example_full_migration()
        
        # Example 5: New table operations
        example_new_table_operations()
        
    except Exception as e:
        print(f"Examples failed: {e}")
    
    finally:
        # Clean up
        cleanup_temp_files()
    
    print("\n" + "=" * 50)
    print("Migration examples completed!")
    print("\nKey Features:")
    print("✓ Backwards compatible migration")
    print("✓ Automatic new table detection")
    print("✓ Selective table inclusion/exclusion")
    print("✓ MindMap and Research Agent data support")
    print("✓ Comprehensive verification")


if __name__ == "__main__":
    main() 