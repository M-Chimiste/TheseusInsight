#!/usr/bin/env python3
"""
Database Export Utility

This script exports data from the Theseus Insight database to JSON files
and packages them in a tar.gz archive for easy transfer.

Usage:
    python -m theseus_insight.utils.db_export --db-path "postgresql://..." --output-dir ./export
"""

import os
import json
import tarfile
import argparse
import datetime
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional

from ...data_model.data_handling import PaperDatabase


class DatabaseExporter:
    """Handles exporting database contents to JSON files."""
    
    def __init__(self, db_path: str, output_dir: str):
        """
        Initialize the exporter.
        
        Args:
            db_path: Database connection string
            output_dir: Directory to save exported files
        """
        self.db = PaperDatabase(db_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def export_papers(self) -> str:
        """Export all papers to JSON file."""
        print("Exporting papers...")
        papers = self.db.fetch_all_papers()
        
        # Convert any remaining non-serializable objects
        serializable_papers = []
        for paper in papers:
            paper_copy = paper.copy()
            # Convert embedding to list if it's not already
            if paper_copy.get('embedding') is not None:
                if hasattr(paper_copy['embedding'], 'tolist'):
                    paper_copy['embedding'] = paper_copy['embedding'].tolist()
                elif not isinstance(paper_copy['embedding'], list):
                    paper_copy['embedding'] = list(paper_copy['embedding'])
            serializable_papers.append(paper_copy)
        
        output_file = self.output_dir / "papers.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_papers, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(papers)} papers to {output_file}")
        return str(output_file)
    
    def export_podcasts(self) -> str:
        """Export all podcasts to JSON file."""
        print("Exporting podcasts...")
        podcasts = self.db.fetch_all_podcasts()
        
        output_file = self.output_dir / "podcasts.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(podcasts, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(podcasts)} podcasts to {output_file}")
        return str(output_file)
    
    def export_newsletters(self) -> str:
        """Export all newsletters to JSON file."""
        print("Exporting newsletters...")
        newsletters = self.db.fetch_all_newsletters()
        
        output_file = self.output_dir / "newsletters.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(newsletters, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(newsletters)} newsletters to {output_file}")
        return str(output_file)
    
    def export_literature_reviews(self) -> str:
        """Export all literature reviews to JSON file."""
        print("Exporting literature reviews...")
        literature_reviews = self.db.fetch_all_literature_reviews()
        
        output_file = self.output_dir / "literature_reviews.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(literature_reviews, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(literature_reviews)} literature reviews to {output_file}")
        return str(output_file)
    
    def create_metadata(self) -> str:
        """Create metadata file with export information."""
        metadata = {
            "export_timestamp": datetime.datetime.now().isoformat(),
            "export_version": "1.1",
            "tables_exported": ["papers", "podcasts", "newsletters", "literature_reviews"],
            "description": "Theseus Insight database export"
        }
        
        output_file = self.output_dir / "metadata.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        return str(output_file)
    
    def create_archive(self, archive_name: str = None) -> str:
        """
        Create a tar.gz archive of all exported files.
        
        Args:
            archive_name: Name of the archive file (without extension)
            
        Returns:
            Path to the created archive
        """
        if archive_name is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_name = f"theseus_db_export_{timestamp}"
        
        archive_path = self.output_dir.parent / f"{archive_name}.tar.gz"
        
        print(f"Creating archive: {archive_path}")
        with tarfile.open(archive_path, "w:gz") as tar:
            # Add all JSON files from the output directory
            for file_path in self.output_dir.glob("*.json"):
                tar.add(file_path, arcname=file_path.name)
        
        print(f"Archive created successfully: {archive_path}")
        return str(archive_path)
    
    def export_all(
        self,
        create_archive: bool = True,
        archive_name: str = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Export all data and optionally create an archive.

        Args:
            create_archive: Whether to create a tar.gz archive
            archive_name: Name for the archive file
            progress_callback: Optional callback reporting percentage and message

        Returns:
            Dictionary with export results
        """
        print("Starting database export...")
        if progress_callback:
            progress_callback(0, "starting")

        # Export all tables
        papers_file = self.export_papers()
        if progress_callback:
            progress_callback(20, "papers_exported")
        podcasts_file = self.export_podcasts()
        if progress_callback:
            progress_callback(40, "podcasts_exported")
        newsletters_file = self.export_newsletters()
        if progress_callback:
            progress_callback(60, "newsletters_exported")
        literature_reviews_file = self.export_literature_reviews()
        if progress_callback:
            progress_callback(80, "literature_reviews_exported")
        metadata_file = self.create_metadata()
        if progress_callback:
            progress_callback(90, "metadata_created")
        
        result = {
            "files": {
                "papers": papers_file,
                "podcasts": podcasts_file,
                "newsletters": newsletters_file,
                "literature_reviews": literature_reviews_file,
                "metadata": metadata_file
            },
            "output_directory": str(self.output_dir)
        }
        
        if create_archive:
            archive_path = self.create_archive(archive_name)
            result["archive"] = archive_path
            if progress_callback:
                progress_callback(100, "archive_created")
        else:
            if progress_callback:
                progress_callback(100, "export_complete")

        print("Export completed successfully!")
        return result


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Export Theseus Insight database to files")
    parser.add_argument("--db-path", required=True, help="Database connection string")
    parser.add_argument("--output-dir", default="./db_export", help="Output directory for exported files")
    parser.add_argument("--archive-name", help="Name for the archive file (without extension)")
    parser.add_argument("--no-archive", action="store_true", help="Don't create tar.gz archive")
    
    args = parser.parse_args()
    
    try:
        exporter = DatabaseExporter(args.db_path, args.output_dir)
        result = exporter.export_all(
            create_archive=not args.no_archive,
            archive_name=args.archive_name
        )
        
        print("\nExport Summary:")
        print(f"Output directory: {result['output_directory']}")
        for table, file_path in result['files'].items():
            print(f"{table.capitalize()}: {file_path}")
        
        if "archive" in result:
            print(f"Archive: {result['archive']}")
            
    except Exception as e:
        print(f"Export failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 