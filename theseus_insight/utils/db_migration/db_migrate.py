#!/usr/bin/env python3
"""
Database Migration Utility

This script provides a high-level interface for migrating Theseus Insight databases.
It can export from one database and import to another, or work with archive files.

Usage:
    # Export database to archive
    python -m theseus_insight.utils.db_migration.db_migrate export --source-db "postgresql://..." --output ./backup.tar.gz
    
    # Import archive to database
    python -m theseus_insight.utils.db_migration.db_migrate import --target-db "postgresql://..." --input ./backup.tar.gz
    
    # Direct migration between databases
    python -m theseus_insight.utils.db_migration.db_migrate migrate --source-db "postgresql://..." --target-db "postgresql://..."
"""

import argparse
import tempfile
from pathlib import Path
from typing import Dict, Any

from .db_export import DatabaseExporter
from .db_import import DatabaseImporter


class DatabaseMigrator:
    """Handles high-level database migration operations."""
    
    def __init__(self):
        """Initialize the migrator."""
        pass
    
    def export_database(self, source_db: str, output_path: str, archive_name: str = None) -> Dict[str, Any]:
        """
        Export a database to an archive file.
        
        Args:
            source_db: Source database connection string
            output_path: Output path for the archive
            archive_name: Name for the archive (without extension)
            
        Returns:
            Dictionary with export results
        """
        print(f"Exporting database: {source_db}")
        
        # Create temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = DatabaseExporter(source_db, temp_dir)
            result = exporter.export_all(create_archive=True, archive_name=archive_name)
            
            # Move archive to desired location
            archive_path = Path(result["archive"])
            output_path_obj = Path(output_path)
            
            if output_path_obj.is_dir():
                # If output is a directory, place archive there
                final_path = output_path_obj / archive_path.name
            else:
                # If output is a file path, use it directly
                final_path = output_path_obj
                final_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the archive
            archive_path.rename(final_path)
            result["final_archive_path"] = str(final_path)
            
            print(f"Database exported to: {final_path}")
            return result
    
    def import_database(self, target_db: str, input_path: str, skip_duplicates: bool = True) -> Dict[str, Any]:
        """
        Import data from an archive or directory to a database.
        
        Args:
            target_db: Target database connection string
            input_path: Path to archive file or directory
            skip_duplicates: Whether to skip duplicate entries
            
        Returns:
            Dictionary with import results
        """
        print(f"Importing to database: {target_db}")
        
        importer = DatabaseImporter(target_db)
        result = importer.import_all(input_path, skip_duplicates=skip_duplicates)
        
        print("Database import completed")
        return result
    
    def migrate_database(self, source_db: str, target_db: str, skip_duplicates: bool = True, 
                        keep_archive: bool = False, archive_path: str = None) -> Dict[str, Any]:
        """
        Migrate data directly from one database to another.
        
        Args:
            source_db: Source database connection string
            target_db: Target database connection string
            skip_duplicates: Whether to skip duplicate entries
            keep_archive: Whether to keep the intermediate archive file
            archive_path: Path to save the archive (if keep_archive is True)
            
        Returns:
            Dictionary with migration results
        """
        print(f"Migrating database from {source_db} to {target_db}")
        
        if keep_archive and archive_path:
            # Export to specified archive path
            export_result = self.export_database(source_db, archive_path)
            archive_file = export_result["final_archive_path"]
        else:
            # Use temporary archive
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
                temp_archive = temp_file.name
            
            export_result = self.export_database(source_db, temp_archive)
            archive_file = export_result["final_archive_path"]
        
        # Import from archive
        import_result = self.import_database(target_db, archive_file, skip_duplicates)
        
        # Clean up temporary archive if not keeping it
        if not keep_archive:
            Path(archive_file).unlink(missing_ok=True)
        
        result = {
            "export": export_result,
            "import": import_result,
            "archive_path": archive_file if keep_archive else None
        }
        
        print("Database migration completed")
        return result
    
    def verify_migration(self, source_db: str, target_db: str) -> Dict[str, Any]:
        """
        Verify that a migration was successful by comparing record counts.
        
        Args:
            source_db: Source database connection string
            target_db: Target database connection string
            
        Returns:
            Dictionary with verification results
        """
        print("Verifying migration...")
        
        source_exporter = DatabaseExporter(source_db, tempfile.mkdtemp())
        target_exporter = DatabaseExporter(target_db, tempfile.mkdtemp())
        
        # Get counts from both databases
        source_papers = source_exporter.db.fetch_all_papers()
        source_podcasts = source_exporter.db.fetch_all_podcasts()
        source_newsletters = source_exporter.db.fetch_all_newsletters()
        
        target_papers = target_exporter.db.fetch_all_papers()
        target_podcasts = target_exporter.db.fetch_all_podcasts()
        target_newsletters = target_exporter.db.fetch_all_newsletters()
        
        verification = {
            "papers": {
                "source_count": len(source_papers),
                "target_count": len(target_papers),
                "match": len(source_papers) <= len(target_papers)  # Target can have more due to existing data
            },
            "podcasts": {
                "source_count": len(source_podcasts),
                "target_count": len(target_podcasts),
                "match": len(source_podcasts) <= len(target_podcasts)
            },
            "newsletters": {
                "source_count": len(source_newsletters),
                "target_count": len(target_newsletters),
                "match": len(source_newsletters) <= len(target_newsletters)
            }
        }
        
        all_match = all(table["match"] for table in verification.values())
        verification["overall_success"] = all_match
        
        print("Verification completed")
        return verification


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Migrate Theseus Insight databases")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export database to archive")
    export_parser.add_argument("--source-db", required=True, help="Source database connection string")
    export_parser.add_argument("--output", required=True, help="Output path for archive")
    export_parser.add_argument("--archive-name", help="Name for the archive (without extension)")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import archive to database")
    import_parser.add_argument("--target-db", required=True, help="Target database connection string")
    import_parser.add_argument("--input", required=True, help="Input archive or directory path")
    import_parser.add_argument("--allow-duplicates", action="store_true", help="Allow duplicate entries")
    
    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate between databases")
    migrate_parser.add_argument("--source-db", required=True, help="Source database connection string")
    migrate_parser.add_argument("--target-db", required=True, help="Target database connection string")
    migrate_parser.add_argument("--allow-duplicates", action="store_true", help="Allow duplicate entries")
    migrate_parser.add_argument("--keep-archive", action="store_true", help="Keep intermediate archive file")
    migrate_parser.add_argument("--archive-path", help="Path to save archive (if --keep-archive)")
    migrate_parser.add_argument("--verify", action="store_true", help="Verify migration after completion")
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify migration between databases")
    verify_parser.add_argument("--source-db", required=True, help="Source database connection string")
    verify_parser.add_argument("--target-db", required=True, help="Target database connection string")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    migrator = DatabaseMigrator()
    
    try:
        if args.command == "export":
            result = migrator.export_database(
                args.source_db,
                args.output,
                args.archive_name
            )
            print(f"\nExport completed successfully!")
            print(f"Archive saved to: {result['final_archive_path']}")
            
        elif args.command == "import":
            result = migrator.import_database(
                args.target_db,
                args.input,
                skip_duplicates=not args.allow_duplicates
            )
            print(f"\nImport completed successfully!")
            for table, stats in result.items():
                if "error" not in stats:
                    print(f"{table.capitalize()}: {stats['imported']} imported, {stats['skipped']} skipped")
            
        elif args.command == "migrate":
            result = migrator.migrate_database(
                args.source_db,
                args.target_db,
                skip_duplicates=not args.allow_duplicates,
                keep_archive=args.keep_archive,
                archive_path=args.archive_path
            )
            print(f"\nMigration completed successfully!")
            
            if args.verify:
                verification = migrator.verify_migration(args.source_db, args.target_db)
                print("\nVerification Results:")
                for table, stats in verification.items():
                    if table != "overall_success":
                        status = "✓" if stats["match"] else "✗"
                        print(f"{status} {table.capitalize()}: {stats['source_count']} → {stats['target_count']}")
                
                if verification["overall_success"]:
                    print("✓ Migration verification passed!")
                else:
                    print("✗ Migration verification failed!")
                    return 1
            
        elif args.command == "verify":
            result = migrator.verify_migration(args.source_db, args.target_db)
            print("\nVerification Results:")
            for table, stats in result.items():
                if table != "overall_success":
                    status = "✓" if stats["match"] else "✗"
                    print(f"{status} {table.capitalize()}: {stats['source_count']} → {stats['target_count']}")
            
            if result["overall_success"]:
                print("✓ Verification passed!")
            else:
                print("✗ Verification failed!")
                return 1
        
    except Exception as e:
        print(f"Operation failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 