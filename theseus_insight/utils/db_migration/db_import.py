#!/usr/bin/env python3
"""
Database Import Utility

This script imports data from JSON files or tar.gz archives into the Theseus Insight database.
It handles duplicate detection and provides options for handling conflicts.

Usage:
    python -m theseus_insight.utils.db_import --db-path "postgresql://..." --input-path ./export.tar.gz
    python -m theseus_insight.utils.db_import --db-path "postgresql://..." --input-dir ./export
"""

import os
import json
import tarfile
import argparse
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from ...data_model.data_handling import PaperDatabase
from ...data_model.papers import Paper, Podcast, Newsletter


class DatabaseImporter:
    """Handles importing database contents from JSON files."""
    
    def __init__(self, db_path: str):
        """
        Initialize the importer.
        
        Args:
            db_path: Database connection string
        """
        self.db = PaperDatabase(db_path)
        
    def extract_archive(self, archive_path: str, extract_dir: str) -> str:
        """
        Extract tar.gz archive to a directory.
        
        Args:
            archive_path: Path to the tar.gz archive
            extract_dir: Directory to extract files to
            
        Returns:
            Path to the extraction directory
        """
        print(f"Extracting archive: {archive_path}")
        
        extract_path = Path(extract_dir)
        extract_path.mkdir(parents=True, exist_ok=True)
        
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(extract_path)
        
        print(f"Archive extracted to: {extract_path}")
        return str(extract_path)
    
    def validate_metadata(self, metadata_path: str) -> bool:
        """
        Validate the metadata file to ensure compatibility.
        
        Args:
            metadata_path: Path to the metadata.json file
            
        Returns:
            True if metadata is valid
        """
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            required_fields = ["export_timestamp", "export_version", "tables_exported"]
            for field in required_fields:
                if field not in metadata:
                    print(f"Warning: Missing required metadata field: {field}")
                    return False
            
            expected_tables = {"papers", "podcasts", "newsletters"}
            exported_tables = set(metadata["tables_exported"])
            
            if not expected_tables.issubset(exported_tables):
                missing = expected_tables - exported_tables
                print(f"Warning: Missing expected tables in export: {missing}")
                return False
            
            print(f"Metadata validation passed. Export from: {metadata['export_timestamp']}")
            return True
            
        except Exception as e:
            print(f"Error validating metadata: {e}")
            return False
    
    def import_papers(self, papers_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import papers from JSON file.
        
        Args:
            papers_file: Path to papers.json file
            skip_duplicates: Whether to skip papers that already exist (by URL)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing papers...")
        
        with open(papers_file, 'r', encoding='utf-8') as f:
            papers_data = json.load(f)
        
        stats = {"total": len(papers_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, paper_data in enumerate(papers_data):
            try:
                # Create Paper object
                paper = Paper(
                    title=paper_data["title"],
                    abstract=paper_data["abstract"],
                    date=paper_data["date"],
                    date_run=paper_data["date_run"],
                    score=paper_data["score"],
                    rationale=paper_data["rationale"],
                    related=paper_data["related"],
                    cosine_similarity=paper_data["cosine_similarity"],
                    url=paper_data["url"],
                    embedding_model=paper_data["embedding_model"],
                    embedding=paper_data.get("embedding")
                )
                
                # Insert paper (with duplicate handling)
                was_inserted = self.db.insert_paper(paper, skip_duplicates=skip_duplicates)
                
                if was_inserted:
                    stats["imported"] += 1
                else:
                    stats["skipped"] += 1
                    
            except Exception as e:
                print(f"Error importing paper '{paper_data.get('title', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback and (i + 1) % 10 == 0 or i == len(papers_data) - 1:  # Update every 10 items or at end
                progress_callback(i + 1, len(papers_data), f"Importing papers: {i + 1}/{len(papers_data)}")
        
        print(f"Papers import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_podcasts(self, podcasts_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import podcasts from JSON file.
        
        Args:
            podcasts_file: Path to podcasts.json file
            skip_duplicates: Whether to skip podcasts that already exist (by title)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing podcasts...")
        
        with open(podcasts_file, 'r', encoding='utf-8') as f:
            podcasts_data = json.load(f)
        
        stats = {"total": len(podcasts_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, podcast_data in enumerate(podcasts_data):
            try:
                # Check for duplicates by title if requested
                if skip_duplicates:
                    # Check if podcast with same title already exists
                    existing_podcasts = self.db.fetch_all_podcasts()
                    if any(p["title"] == podcast_data["title"] for p in existing_podcasts):
                        stats["skipped"] += 1
                        continue
                
                # Create Podcast object
                podcast = Podcast(
                    title=podcast_data["title"],
                    date=podcast_data["date"],
                    script=podcast_data["script"],
                    description=podcast_data["description"]
                )
                
                # Insert podcast
                self.db.insert_podcast(podcast)
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing podcast '{podcast_data.get('title', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(podcasts_data), f"Importing podcasts: {i + 1}/{len(podcasts_data)}")
        
        print(f"Podcasts import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_newsletters(self, newsletters_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import newsletters from JSON file.
        
        Args:
            newsletters_file: Path to newsletters.json file
            skip_duplicates: Whether to skip newsletters that already exist (by date range)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing newsletters...")
        
        with open(newsletters_file, 'r', encoding='utf-8') as f:
            newsletters_data = json.load(f)
        
        stats = {"total": len(newsletters_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, newsletter_data in enumerate(newsletters_data):
            try:
                # Check for duplicates by date range if requested
                if skip_duplicates:
                    existing_newsletters = self.db.fetch_all_newsletters()
                    if any(n["start_date"] == newsletter_data["start_date"] and 
                          n["end_date"] == newsletter_data["end_date"] for n in existing_newsletters):
                        stats["skipped"] += 1
                        continue
                
                # Create Newsletter object
                newsletter = Newsletter(
                    content=newsletter_data["content"],
                    start_date=newsletter_data["start_date"],
                    end_date=newsletter_data["end_date"],
                    date_sent=newsletter_data["date_sent"]
                )
                
                # Insert newsletter
                self.db.insert_newsletter(newsletter)
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing newsletter from {newsletter_data.get('start_date', 'Unknown')} to {newsletter_data.get('end_date', 'Unknown')}: {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(newsletters_data), f"Importing newsletters: {i + 1}/{len(newsletters_data)}")
        
        print(f"Newsletters import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_from_directory(self, input_dir: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, Any]:
        """
        Import all data from a directory containing JSON files.
        
        Args:
            input_dir: Directory containing the JSON files
            skip_duplicates: Whether to skip duplicate entries
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import results
        """
        input_path = Path(input_dir)
        
        # Validate metadata if present
        metadata_file = input_path / "metadata.json"
        if metadata_file.exists():
            if not self.validate_metadata(str(metadata_file)):
                print("Warning: Metadata validation failed, continuing anyway...")
        
        results = {}
        current_step = 0
        total_steps = 3  # papers, podcasts, newsletters
        
        # Import papers
        papers_file = input_path / "papers.json"
        if papers_file.exists():
            if progress_callback:
                progress_callback(0, 100, "Starting papers import...")
            results["papers"] = self.import_papers(
                str(papers_file), 
                skip_duplicates, 
                lambda c, t, m: progress_callback(
                    int((current_step / total_steps) * 100 + (c / t) * (100 / total_steps)), 
                    100, 
                    m
                ) if progress_callback else None
            )
            current_step += 1
        else:
            print("Warning: papers.json not found")
            results["papers"] = {"error": "File not found"}
            current_step += 1
        
        # Import podcasts
        podcasts_file = input_path / "podcasts.json"
        if podcasts_file.exists():
            if progress_callback:
                progress_callback(int((current_step / total_steps) * 100), 100, "Starting podcasts import...")
            results["podcasts"] = self.import_podcasts(
                str(podcasts_file), 
                skip_duplicates,
                lambda c, t, m: progress_callback(
                    int((current_step / total_steps) * 100 + (c / t) * (100 / total_steps)), 
                    100, 
                    m
                ) if progress_callback else None
            )
            current_step += 1
        else:
            print("Warning: podcasts.json not found")
            results["podcasts"] = {"error": "File not found"}
            current_step += 1
        
        # Import newsletters
        newsletters_file = input_path / "newsletters.json"
        if newsletters_file.exists():
            if progress_callback:
                progress_callback(int((current_step / total_steps) * 100), 100, "Starting newsletters import...")
            results["newsletters"] = self.import_newsletters(
                str(newsletters_file), 
                skip_duplicates,
                lambda c, t, m: progress_callback(
                    int((current_step / total_steps) * 100 + (c / t) * (100 / total_steps)), 
                    100, 
                    m
                ) if progress_callback else None
            )
        else:
            print("Warning: newsletters.json not found")
            results["newsletters"] = {"error": "File not found"}
        
        if progress_callback:
            progress_callback(100, 100, "Import completed!")
        
        return results
    
    def import_from_archive(self, archive_path: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, Any]:
        """
        Import all data from a tar.gz archive.
        
        Args:
            archive_path: Path to the tar.gz archive
            skip_duplicates: Whether to skip duplicate entries
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import results
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            if progress_callback:
                progress_callback(0, 100, "Extracting archive...")
            extract_dir = self.extract_archive(archive_path, temp_dir)
            if progress_callback:
                progress_callback(10, 100, "Archive extracted, starting import...")
            
            # Adjust progress callback to account for extraction taking 10%
            def adjusted_progress_callback(current, total, message):
                if progress_callback:
                    # Map 0-100% import progress to 10-100% overall progress
                    adjusted_progress = 10 + int((current / total) * 90)
                    progress_callback(adjusted_progress, 100, message)
            
            return self.import_from_directory(extract_dir, skip_duplicates, adjusted_progress_callback)
    
    def import_all(self, input_path: str, skip_duplicates: bool = True) -> Dict[str, Any]:
        """
        Import data from either a directory or archive.
        
        Args:
            input_path: Path to directory or tar.gz archive
            skip_duplicates: Whether to skip duplicate entries
            
        Returns:
            Dictionary with import results
        """
        input_path_obj = Path(input_path)
        
        if input_path_obj.is_dir():
            print(f"Importing from directory: {input_path}")
            return self.import_from_directory(input_path, skip_duplicates)
        elif input_path_obj.suffix == ".gz" and input_path_obj.name.endswith(".tar.gz"):
            print(f"Importing from archive: {input_path}")
            return self.import_from_archive(input_path, skip_duplicates)
        else:
            raise ValueError(f"Input path must be a directory or .tar.gz archive: {input_path}")

    def clear_all_data(self, progress_callback=None) -> Dict[str, int]:
        """
        Clear all data from the main tables (papers, podcasts, newsletters, logs, tasks).
        WARNING: This is destructive and cannot be undone.
        
        Args:
            progress_callback: Optional callback function(current, total, message)
        
        Returns:
            Dictionary with counts of deleted records for each table
        """
        print("WARNING: Clearing all data from database tables...")
        
        # Tables to clear in order (respecting potential foreign key constraints)
        tables_to_clear = ['logs', 'tasks', 'newsletters', 'podcasts', 'papers']
        deletion_counts = {}
        total_tables = len(tables_to_clear)
        
        with self.db.get_cursor() as cursor:
            for i, table in enumerate(tables_to_clear):
                if progress_callback:
                    progress_callback(i, total_tables, f"Clearing {table} table...")
                
                try:
                    # Get count before deletion
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count_before = cursor.fetchone()[0]
                    
                    # Truncate the table (faster than DELETE and resets auto-increment)
                    cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
                    deletion_counts[table] = count_before
                    
                    print(f"Cleared {count_before} records from {table} table")
                    
                except Exception as e:
                    print(f"Error clearing table {table}: {e}")
                    deletion_counts[table] = 0
                
                if progress_callback:
                    progress_callback(i + 1, total_tables, f"Cleared {table} table")
        
        total_deleted = sum(deletion_counts.values())
        print(f"Total records cleared: {total_deleted}")
        
        if progress_callback:
            progress_callback(total_tables, total_tables, f"Database clearing complete. {total_deleted} records deleted.")
        
        return deletion_counts


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Import Theseus Insight database from files")
    parser.add_argument("--db-path", required=True, help="Database connection string")
    parser.add_argument("--input-path", required=True, help="Input directory or tar.gz archive")
    parser.add_argument("--allow-duplicates", action="store_true", help="Allow duplicate entries (don't skip)")
    
    args = parser.parse_args()
    
    try:
        importer = DatabaseImporter(args.db_path)
        results = importer.import_all(
            args.input_path,
            skip_duplicates=not args.allow_duplicates
        )
        
        print("\nImport Summary:")
        for table, stats in results.items():
            if "error" in stats:
                print(f"{table.capitalize()}: {stats['error']}")
            else:
                print(f"{table.capitalize()}: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        
        # Calculate totals
        total_imported = sum(stats.get('imported', 0) for stats in results.values())
        total_skipped = sum(stats.get('skipped', 0) for stats in results.values())
        total_errors = sum(stats.get('errors', 0) for stats in results.values())
        
        print(f"\nOverall: {total_imported} imported, {total_skipped} skipped, {total_errors} errors")
        
        if total_errors > 0:
            return 1
            
    except Exception as e:
        print(f"Import failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 