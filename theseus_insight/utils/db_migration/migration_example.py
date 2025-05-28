#!/usr/bin/env python3
"""
Example script demonstrating how to use the database migration tools programmatically.

This script shows various migration scenarios and how to handle them in code.
"""

import os
import tempfile
from pathlib import Path

from .db_export import DatabaseExporter
from .db_import import DatabaseImporter
from .db_migrate import DatabaseMigrator


def example_export_to_archive():
    """Example: Export database to a timestamped archive."""
    print("=== Example: Export Database to Archive ===")
    
    # Database connection (replace with your actual connection string)
    source_db = os.getenv("SOURCE_DB_URL", "postgresql://user:pass@localhost:5432/theseus_dev")
    
    # Create exporter
    with tempfile.TemporaryDirectory() as temp_dir:
        exporter = DatabaseExporter(source_db, temp_dir)
        
        # Export with custom archive name
        result = exporter.export_all(
            create_archive=True,
            archive_name="dev_backup_manual"
        )
        
        print(f"Export completed!")
        print(f"Archive created: {result['archive']}")
        print(f"Files exported: {list(result['files'].keys())}")
        
        return result['archive']


def example_import_from_archive(archive_path: str):
    """Example: Import data from an archive to a new database."""
    print("\n=== Example: Import from Archive ===")
    
    # Target database connection (replace with your actual connection string)
    target_db = os.getenv("TARGET_DB_URL", "postgresql://user:pass@localhost:5432/theseus_new")
    
    # Create importer
    importer = DatabaseImporter(target_db)
    
    # Import data (skipping duplicates by default)
    result = importer.import_from_archive(archive_path, skip_duplicates=True)
    
    print("Import completed!")
    for table, stats in result.items():
        if "error" not in stats:
            print(f"{table}: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        else:
            print(f"{table}: {stats['error']}")
    
    return result


def example_direct_migration():
    """Example: Direct migration between two databases."""
    print("\n=== Example: Direct Database Migration ===")
    
    source_db = os.getenv("SOURCE_DB_URL", "postgresql://user:pass@localhost:5432/theseus_dev")
    target_db = os.getenv("TARGET_DB_URL", "postgresql://user:pass@localhost:5432/theseus_staging")
    
    # Create migrator
    migrator = DatabaseMigrator()
    
    # Perform migration with verification
    result = migrator.migrate_database(
        source_db=source_db,
        target_db=target_db,
        skip_duplicates=True,
        keep_archive=True,
        archive_path="./migration_backup.tar.gz"
    )
    
    print("Migration completed!")
    print(f"Archive saved: {result['archive_path']}")
    
    # Verify the migration
    verification = migrator.verify_migration(source_db, target_db)
    print("\nVerification Results:")
    for table, stats in verification.items():
        if table != "overall_success":
            status = "✓" if stats["match"] else "✗"
            print(f"{status} {table}: {stats['source_count']} → {stats['target_count']}")
    
    if verification["overall_success"]:
        print("✓ Migration verified successfully!")
    else:
        print("✗ Migration verification failed!")
    
    return result


def example_selective_import():
    """Example: Import only specific tables from an archive."""
    print("\n=== Example: Selective Import ===")
    
    # This example shows how you could modify the import process
    # to only import specific tables
    
    target_db = os.getenv("TARGET_DB_URL", "postgresql://user:pass@localhost:5432/theseus_test")
    archive_path = "./test_backup.tar.gz"
    
    # Extract archive to temporary directory
    importer = DatabaseImporter(target_db)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        extract_dir = importer.extract_archive(archive_path, temp_dir)
        
        # Import only papers (skip podcasts and newsletters)
        papers_file = Path(extract_dir) / "papers.json"
        if papers_file.exists():
            papers_result = importer.import_papers(str(papers_file), skip_duplicates=True)
            print(f"Papers: {papers_result['imported']} imported, {papers_result['skipped']} skipped")
        
        # You could add conditional logic here for other tables
        # based on your specific requirements
    
    print("Selective import completed!")


def example_batch_processing():
    """Example: Process multiple archives in batch."""
    print("\n=== Example: Batch Processing ===")
    
    target_db = os.getenv("TARGET_DB_URL", "postgresql://user:pass@localhost:5432/theseus_consolidated")
    archive_directory = "./archives/"
    
    # Find all tar.gz files in the directory
    archive_files = list(Path(archive_directory).glob("*.tar.gz"))
    
    if not archive_files:
        print("No archive files found in ./archives/")
        return
    
    importer = DatabaseImporter(target_db)
    total_stats = {"imported": 0, "skipped": 0, "errors": 0}
    
    for archive_file in archive_files:
        print(f"Processing: {archive_file.name}")
        
        try:
            result = importer.import_from_archive(str(archive_file), skip_duplicates=True)
            
            # Aggregate statistics
            for table_stats in result.values():
                if "error" not in table_stats:
                    total_stats["imported"] += table_stats.get("imported", 0)
                    total_stats["skipped"] += table_stats.get("skipped", 0)
                    total_stats["errors"] += table_stats.get("errors", 0)
        
        except Exception as e:
            print(f"Error processing {archive_file.name}: {e}")
            total_stats["errors"] += 1
    
    print(f"\nBatch processing completed!")
    print(f"Total: {total_stats['imported']} imported, {total_stats['skipped']} skipped, {total_stats['errors']} errors")


def example_error_handling():
    """Example: Proper error handling in migration scripts."""
    print("\n=== Example: Error Handling ===")
    
    source_db = "postgresql://invalid:connection@nonexistent:5432/fake_db"
    
    try:
        # This will fail, demonstrating error handling
        exporter = DatabaseExporter(source_db, "./temp_export")
        result = exporter.export_all()
        
    except Exception as e:
        print(f"Expected error caught: {type(e).__name__}: {e}")
        print("This demonstrates how to handle connection errors gracefully.")
        
        # In a real script, you might:
        # 1. Log the error
        # 2. Send notifications
        # 3. Retry with exponential backoff
        # 4. Fall back to alternative data sources
        
        return False
    
    return True


def main():
    """Run all examples."""
    print("Database Migration Examples")
    print("=" * 50)
    
    # Set up environment variables for examples
    # In practice, these would be set in your environment
    os.environ.setdefault("SOURCE_DB_URL", "postgresql://user:pass@localhost:5432/theseus_dev")
    os.environ.setdefault("TARGET_DB_URL", "postgresql://user:pass@localhost:5432/theseus_new")
    
    try:
        # Example 1: Export to archive
        archive_path = example_export_to_archive()
        
        # Example 2: Import from archive (using the archive we just created)
        if archive_path and Path(archive_path).exists():
            example_import_from_archive(archive_path)
        
        # Example 3: Direct migration
        # example_direct_migration()  # Uncomment to run
        
        # Example 4: Selective import
        # example_selective_import()  # Uncomment to run
        
        # Example 5: Batch processing
        # example_batch_processing()  # Uncomment to run
        
        # Example 6: Error handling
        example_error_handling()
        
    except Exception as e:
        print(f"Example failed: {e}")
        return 1
    
    print("\n" + "=" * 50)
    print("Examples completed! Check the output above for results.")
    print("\nTo run these examples with real databases:")
    print("1. Set SOURCE_DB_URL and TARGET_DB_URL environment variables")
    print("2. Ensure the databases exist and are accessible")
    print("3. Uncomment the examples you want to run")
    
    return 0


if __name__ == "__main__":
    exit(main()) 