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
    
    def export_database(
        self,
        source_db: str,
        output_path: str,
        archive_name: str = None,
        include_new_tables: bool = True,
        profile_id: int = None,
        profile_name: str = None,
        include_fulltext: bool = True,
        include_topics: bool = False,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Export a database to an archive file.

        Args:
            source_db: Source database connection string
            output_path: Output path for the archive
            archive_name: Name for the archive (without extension)
            include_new_tables: Whether to include new MindMap and Research Agent tables
            profile_id: Profile ID for profile-scoped export
            profile_name: Profile name for profile-scoped export
            include_fulltext: Include paper fulltext (profile-scoped only)
            include_topics: Include topic relationships (profile-scoped only)
            streaming: Use streaming mode for large datasets

        Returns:
            Dictionary with export results
        """
        print(f"Exporting database: {source_db}")

        # Create temporary directory for export
        with tempfile.TemporaryDirectory() as temp_dir:
            exporter = DatabaseExporter(source_db, temp_dir, streaming=streaming)

            # Check if this is a profile-scoped export
            if profile_id or profile_name:
                print(f"Performing profile-scoped export for: {profile_id or profile_name}")
                result = exporter.export_profile_scoped(
                    profile_id=profile_id,
                    profile_name=profile_name,
                    include_papers=True,
                    include_fulltext=include_fulltext,
                    include_topics=include_topics
                )

                # Create archive from the exported files
                archive_path = exporter.create_archive(archive_name)
                result["archive"] = archive_path
            else:
                # Full database export
                result = exporter.export_all(
                    create_archive=True,
                    archive_name=archive_name,
                    include_new_tables=include_new_tables
                )

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
    
    def import_database(
        self,
        target_db: str,
        input_path: str,
        skip_duplicates: bool = True,
        mapping_strategy: str = "auto",
        merge_to_profile_id: int = None,
        create_new_profile_name: str = None
    ) -> Dict[str, Any]:
        """
        Import data from an archive or directory to a database.

        Args:
            target_db: Target database connection string
            input_path: Path to archive file or directory
            skip_duplicates: Whether to skip duplicate entries
            mapping_strategy: Profile mapping strategy
            merge_to_profile_id: Target profile ID for merge_to strategy
            create_new_profile_name: Override profile name for create_new

        Returns:
            Dictionary with import results
        """
        print(f"Importing to database: {target_db}")

        importer = DatabaseImporter(target_db)
        result = importer.import_all(
            input_path,
            skip_duplicates=skip_duplicates,
            mapping_strategy=mapping_strategy,
            merge_to_profile_id=merge_to_profile_id,
            create_new_profile_name=create_new_profile_name
        )

        print("Database import completed")
        return result
    
    def migrate_database(self, source_db: str, target_db: str, skip_duplicates: bool = True, 
                        keep_archive: bool = False, archive_path: str = None, include_new_tables: bool = True) -> Dict[str, Any]:
        """
        Migrate data directly from one database to another.
        
        Args:
            source_db: Source database connection string
            target_db: Target database connection string
            skip_duplicates: Whether to skip duplicate entries
            keep_archive: Whether to keep the intermediate archive file
            archive_path: Path to save the archive (if keep_archive is True)
            include_new_tables: Whether to include new MindMap and Research Agent tables
            
        Returns:
            Dictionary with migration results
        """
        print(f"Migrating database from {source_db} to {target_db}")
        
        if keep_archive and archive_path:
            # Export to specified archive path
            export_result = self.export_database(source_db, archive_path, include_new_tables=include_new_tables)
            archive_file = export_result["final_archive_path"]
        else:
            # Use temporary archive
            with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
                temp_archive = temp_file.name
            
            export_result = self.export_database(source_db, temp_archive, include_new_tables=include_new_tables)
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
        
        from ...data_access import (
            PaperRepository, NewsletterRepository, PodcastRepository, 
            LitReviewRepository, ResearchRunRepository, MindmapReportRepository, ModelCatalogRepository
        )
        from ...db import get_cursor
        
        # Helper function to get counts from a database
        def get_table_counts(db_url: str) -> Dict[str, int]:
            # Temporarily set DATABASE_URL for this verification
            import os
            original_db_url = os.environ.get('DATABASE_URL')
            os.environ['DATABASE_URL'] = db_url
            
            try:
                counts = {}
                with get_cursor() as cursor:
                    # Count core tables
                    cursor.execute("SELECT COUNT(*) FROM papers")
                    counts['papers'] = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM podcasts")
                    counts['podcasts'] = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM newsletters")
                    counts['newsletters'] = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT COUNT(*) FROM lit_reviews")
                    counts['lit_reviews'] = cursor.fetchone()[0]
                    
                    # Count new tables if they exist
                    try:
                        cursor.execute("SELECT COUNT(*) FROM research_runs")
                        counts['research_runs'] = cursor.fetchone()[0]
                    except Exception:
                        counts['research_runs'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM research_agent_state")
                        counts['research_agent_state'] = cursor.fetchone()[0]
                    except Exception:
                        counts['research_agent_state'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM paper_fulltext")
                        counts['paper_fulltext'] = cursor.fetchone()[0]
                    except Exception:
                        counts['paper_fulltext'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM mindmap_reports")
                        counts['mindmap_reports'] = cursor.fetchone()[0]
                    except Exception:
                        counts['mindmap_reports'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM model_catalog")
                        counts['model_catalog'] = cursor.fetchone()[0]
                    except Exception:
                        counts['model_catalog'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM topics")
                        counts['topics'] = cursor.fetchone()[0]
                    except Exception:
                        counts['topics'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM topic_metrics")
                        counts['topic_metrics'] = cursor.fetchone()[0]
                    except Exception:
                        counts['topic_metrics'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM paper_topics")
                        counts['paper_topics'] = cursor.fetchone()[0]
                    except Exception:
                        counts['paper_topics'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM research_interests")
                        counts['research_interests'] = cursor.fetchone()[0]
                    except Exception:
                        counts['research_interests'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM research_interest_metrics")
                        counts['research_interest_metrics'] = cursor.fetchone()[0]
                    except Exception:
                        counts['research_interest_metrics'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM paper_research_interests")
                        counts['paper_research_interests'] = cursor.fetchone()[0]
                    except Exception:
                        counts['paper_research_interests'] = 0
                    
                    try:
                        cursor.execute("SELECT COUNT(*) FROM label_summaries")
                        counts['label_summaries'] = cursor.fetchone()[0]
                    except Exception:
                        counts['label_summaries'] = 0
                
                return counts
            finally:
                # Restore original DATABASE_URL
                if original_db_url:
                    os.environ['DATABASE_URL'] = original_db_url
                elif 'DATABASE_URL' in os.environ:
                    del os.environ['DATABASE_URL']
        
        # Get counts from both databases
        source_counts = get_table_counts(source_db)
        target_counts = get_table_counts(target_db)
        
        verification = {}
        for table in source_counts:
            verification[table] = {
                "source_count": source_counts[table],
                "target_count": target_counts[table],
                "match": source_counts[table] <= target_counts[table]  # Target can have more due to existing data
            }
        
        # Overall verification status
        all_match = all(v["match"] for v in verification.values())
        verification["overall_status"] = "SUCCESS" if all_match else "MISMATCH"
        
        print(f"Migration verification: {verification['overall_status']}")
        for table, info in verification.items():
            if table != "overall_status":
                status = "✓" if info["match"] else "✗"
                print(f"  {table}: {status} Source: {info['source_count']}, Target: {info['target_count']}")
        
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
    export_parser.add_argument("--exclude-new-tables", action="store_true",
                              help="Exclude new MindMap and Research Agent tables (backwards compatibility)")
    export_parser.add_argument("--profile-id", type=int, help="Export specific profile by ID (profile-scoped export)")
    export_parser.add_argument("--profile-name", help="Export specific profile by name (profile-scoped export)")
    export_parser.add_argument("--include-fulltext", action="store_true", default=True, help="Include paper fulltext (profile-scoped export)")
    export_parser.add_argument("--include-topics", action="store_true", help="Include topic relationships (profile-scoped export)")
    export_parser.add_argument("--streaming", action="store_true", help="Use streaming mode for large datasets")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import archive to database")
    import_parser.add_argument("--target-db", required=True, help="Target database connection string")
    import_parser.add_argument("--input", required=True, help="Input archive or directory path")
    import_parser.add_argument("--allow-duplicates", action="store_true", help="Allow duplicate entries")
    import_parser.add_argument("--mapping-strategy", choices=["auto", "create_new", "merge_to", "match_by_name"],
                              default="auto", help="Profile mapping strategy (default: auto)")
    import_parser.add_argument("--merge-to-profile-id", type=int, help="Merge into existing profile ID (requires --mapping-strategy merge_to)")
    import_parser.add_argument("--create-new-profile", action="store_true", help="Always create new profile (shortcut for --mapping-strategy create_new)")
    import_parser.add_argument("--new-profile-name", help="Override profile name when creating new profile")
    
    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate between databases")
    migrate_parser.add_argument("--source-db", required=True, help="Source database connection string")
    migrate_parser.add_argument("--target-db", required=True, help="Target database connection string")
    migrate_parser.add_argument("--allow-duplicates", action="store_true", help="Allow duplicate entries")
    migrate_parser.add_argument("--keep-archive", action="store_true", help="Keep intermediate archive file")
    migrate_parser.add_argument("--archive-path", help="Path to save archive (if --keep-archive)")
    migrate_parser.add_argument("--verify", action="store_true", help="Verify migration after completion")
    migrate_parser.add_argument("--exclude-new-tables", action="store_true", 
                               help="Exclude new MindMap and Research Agent tables (backwards compatibility)")
    
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
                args.archive_name,
                include_new_tables=not args.exclude_new_tables,
                profile_id=args.profile_id if hasattr(args, 'profile_id') else None,
                profile_name=args.profile_name if hasattr(args, 'profile_name') else None,
                include_fulltext=args.include_fulltext if hasattr(args, 'include_fulltext') else True,
                include_topics=args.include_topics if hasattr(args, 'include_topics') else False,
                streaming=args.streaming if hasattr(args, 'streaming') else False
            )
            print(f"\nExport completed successfully!")
            if result.get("export_type") == "profile_scoped":
                print(f"Export type: Profile-scoped")
                print(f"Profile: {result['profile_mapping']['source_profile_name']}")
                print(f"Papers exported: {result['profile_mapping'].get('papers_exported', 0)}")
            print(f"Archive saved to: {result['final_archive_path']}")
            
        elif args.command == "import":
            # Determine mapping strategy
            mapping_strategy = args.mapping_strategy
            if args.create_new_profile:
                mapping_strategy = "create_new"

            result = migrator.import_database(
                args.target_db,
                args.input,
                skip_duplicates=not args.allow_duplicates,
                mapping_strategy=mapping_strategy,
                merge_to_profile_id=args.merge_to_profile_id if hasattr(args, 'merge_to_profile_id') else None,
                create_new_profile_name=args.new_profile_name if hasattr(args, 'new_profile_name') else None
            )
            print(f"\nImport completed successfully!")

            # Show profile mapping info if available
            if "profile_mapping" in result:
                print(f"\nProfile Mapping:")
                for source_id, target_id in result["profile_mapping"].items():
                    print(f"  Source profile {source_id} → Target profile {target_id}")

            for table, stats in result.items():
                if table != "profile_mapping" and "error" not in stats:
                    print(f"{table.capitalize()}: {stats['imported']} imported, {stats['skipped']} skipped")
            
        elif args.command == "migrate":
            result = migrator.migrate_database(
                args.source_db,
                args.target_db,
                skip_duplicates=not args.allow_duplicates,
                keep_archive=args.keep_archive,
                archive_path=args.archive_path,
                include_new_tables=not args.exclude_new_tables
            )
            print(f"\nMigration completed successfully!")
            
            if args.verify:
                verification = migrator.verify_migration(args.source_db, args.target_db)
                print("\nVerification Results:")
                for table, stats in verification.items():
                    if table != "overall_status":
                        status = "✓" if stats["match"] else "✗"
                        print(f"{status} {table.capitalize()}: {stats['source_count']} → {stats['target_count']}")
                
                if verification["overall_status"] == "SUCCESS":
                    print("✓ Migration verification passed!")
                else:
                    print("✗ Migration verification failed!")
                    return 1
            
        elif args.command == "verify":
            result = migrator.verify_migration(args.source_db, args.target_db)
            print("\nVerification Results:")
            for table, stats in result.items():
                if table != "overall_status":
                    status = "✓" if stats["match"] else "✗"
                    print(f"{status} {table.capitalize()}: {stats['source_count']} → {stats['target_count']}")
            
            if result["overall_status"] == "SUCCESS":
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