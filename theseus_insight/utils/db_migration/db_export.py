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
import numpy as np
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
        
        # Retrieve papers with summary & keywords if they exist
        with self.db.get_cursor(register_vectors=False) as cursor:
            cursor.execute(
                "SELECT id, title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, embedding_model, embedding, summary, keywords_json "
                "FROM papers ORDER BY id DESC"
            )
            rows = cursor.fetchall()

        papers = []
        for row in rows:
            # Convert date objects to strings
            def _to_str(val):
                return val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val)

            emb = row[11]
            if emb is not None and not isinstance(emb, list):
                try:
                    import json as _json
                    emb = _json.loads(emb)
                except Exception:
                    emb = None

            import json as _json
            kw_json = row[13] if len(row) > 13 else None
            keywords = []
            if kw_json:
                try:
                    keywords = _json.loads(kw_json)
                except Exception:
                    keywords = []

            papers.append({
                'id': row[0],
                'title': row[1],
                'abstract': row[2],
                'date': _to_str(row[3]),
                'date_run': _to_str(row[4]),
                'score': row[5],
                'rationale': row[6],
                'related': bool(row[7]),
                'cosine_similarity': row[8],
                'url': row[9],
                'embedding_model': row[10],
                'embedding': emb,
                'summary': row[12],
                'keywords': keywords,
            })

        # Convert any remaining non-serializable objects (embedding)
        serializable_papers = []
        for paper_copy in papers:
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
    
    def export_research_runs(self) -> str:
        """Export all research runs to JSON file."""
        print("Exporting research runs...")
        
        # Get all research runs using the database method
        research_runs = self.db.get_research_runs_history(limit=10000)  # Get all runs
        
        output_file = self.output_dir / "research_runs.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(research_runs, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(research_runs)} research runs to {output_file}")
        return str(output_file)
    
    def export_research_agent_state(self) -> str:
        """Export all research agent state snapshots to JSON file."""
        print("Exporting research agent state...")
        
        # Get all research agent states by querying the database directly
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, task_id, node_name, state_json, timestamp
                FROM research_agent_state
                ORDER BY timestamp ASC
            """)
            rows = cursor.fetchall()
            
            states = []
            for row in rows:
                states.append({
                    'id': row[0],
                    'task_id': row[1],
                    'node_name': row[2],
                    'state_json': row[3],
                    'timestamp': row[4]
                })
        
        output_file = self.output_dir / "research_agent_state.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(states, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(states)} research agent states to {output_file}")
        return str(output_file)
    
    def export_paper_fulltext(self) -> str:
        """Export all paper full-text content to JSON file."""
        print("Exporting paper full-text content...")
        
        # Get all paper full-text content
        with self.db.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, paper_id, content, embedding, embedding_model, created_at
                FROM paper_fulltext
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            
            fulltext_data = []
            for row in rows:
                # Handle embedding conversion from bytes to list
                embedding = None
                if row[3]:  # If embedding exists
                    try:
                        # Convert bytes to numpy array then to list
                        embedding = np.frombuffer(row[3], dtype=np.float32).tolist()
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for paper_id {row[1]}: {e}")
                        embedding = None
                
                fulltext_data.append({
                    'id': row[0],
                    'paper_id': row[1],
                    'content': row[2],
                    'embedding': embedding,
                    'embedding_model': row[4],
                    'created_at': row[5]
                })
        
        output_file = self.output_dir / "paper_fulltext.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(fulltext_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(fulltext_data)} paper full-text entries to {output_file}")
        return str(output_file)
    
    def export_mindmap_reports(self) -> str:
        """Export all mindmap reports to JSON file."""
        print("Exporting mindmap reports...")
        
        # Get all mindmap reports
        mindmap_reports = self.db.get_mindmap_reports(limit=10000)  # Get all reports
        
        output_file = self.output_dir / "mindmap_reports.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(mindmap_reports, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(mindmap_reports)} mindmap reports to {output_file}")
        return str(output_file)
    
    def export_model_catalog(self) -> str:
        """Export all model catalog entries to JSON file."""
        print("Exporting model catalog...")
        
        # Get all model catalog entries
        model_catalog = self.db.search_model_catalog(page_size=10000)  # Get all models
        
        output_file = self.output_dir / "model_catalog.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(model_catalog['models'], f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(model_catalog['models'])} model catalog entries to {output_file}")
        return str(output_file)
    
    def create_metadata(self) -> str:
        """Create metadata file with export information."""
        metadata = {
            "export_timestamp": datetime.datetime.now().isoformat(),
            "export_version": "2.0",  # Incremented version for new tables
            "tables_exported": [
                "papers", "podcasts", "newsletters", "literature_reviews",
                "research_runs", "research_agent_state", "paper_fulltext", 
                "mindmap_reports", "model_catalog"
            ],
            "description": "Theseus Insight database export with MindMap and Research Agent data",
            "backwards_compatible": True,
            "new_features": [
                "research_runs", "research_agent_state", "paper_fulltext",
                "mindmap_reports", "model_catalog"
            ]
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
        include_new_tables: bool = True,
    ) -> Dict[str, Any]:
        """
        Export all data and optionally create an archive.

        Args:
            create_archive: Whether to create a tar.gz archive
            archive_name: Name for the archive file
            progress_callback: Optional callback reporting percentage and message
            include_new_tables: Whether to include new MindMap and Research Agent tables

        Returns:
            Dictionary with export results
        """
        print("Starting database export...")
        if progress_callback:
            progress_callback(0, "starting")

        # Export core tables (backwards compatible)
        papers_file = self.export_papers()
        if progress_callback:
            progress_callback(15, "papers_exported")
        podcasts_file = self.export_podcasts()
        if progress_callback:
            progress_callback(25, "podcasts_exported")
        newsletters_file = self.export_newsletters()
        if progress_callback:
            progress_callback(35, "newsletters_exported")
        literature_reviews_file = self.export_literature_reviews()
        if progress_callback:
            progress_callback(45, "literature_reviews_exported")
        
        result = {
            "files": {
                "papers": papers_file,
                "podcasts": podcasts_file,
                "newsletters": newsletters_file,
                "literature_reviews": literature_reviews_file,
            },
            "output_directory": str(self.output_dir)
        }
        
        # Export new tables if requested
        if include_new_tables:
            try:
                research_runs_file = self.export_research_runs()
                if progress_callback:
                    progress_callback(55, "research_runs_exported")
                result["files"]["research_runs"] = research_runs_file
            except Exception as e:
                print(f"Warning: Could not export research runs: {e}")
            
            try:
                research_agent_state_file = self.export_research_agent_state()
                if progress_callback:
                    progress_callback(65, "research_agent_state_exported")
                result["files"]["research_agent_state"] = research_agent_state_file
            except Exception as e:
                print(f"Warning: Could not export research agent state: {e}")
            
            try:
                paper_fulltext_file = self.export_paper_fulltext()
                if progress_callback:
                    progress_callback(75, "paper_fulltext_exported")
                result["files"]["paper_fulltext"] = paper_fulltext_file
            except Exception as e:
                print(f"Warning: Could not export paper fulltext: {e}")
            
            try:
                mindmap_reports_file = self.export_mindmap_reports()
                if progress_callback:
                    progress_callback(85, "mindmap_reports_exported")
                result["files"]["mindmap_reports"] = mindmap_reports_file
            except Exception as e:
                print(f"Warning: Could not export mindmap reports: {e}")
            
            try:
                model_catalog_file = self.export_model_catalog()
                if progress_callback:
                    progress_callback(90, "model_catalog_exported")
                result["files"]["model_catalog"] = model_catalog_file
            except Exception as e:
                print(f"Warning: Could not export model catalog: {e}")
        
        metadata_file = self.create_metadata()
        if progress_callback:
            progress_callback(95, "metadata_created")
        result["files"]["metadata"] = metadata_file
        
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
    parser.add_argument("--exclude-new-tables", action="store_true", 
                       help="Exclude new MindMap and Research Agent tables (backwards compatibility)")
    
    args = parser.parse_args()
    
    try:
        exporter = DatabaseExporter(args.db_path, args.output_dir)
        result = exporter.export_all(
            create_archive=not args.no_archive,
            archive_name=args.archive_name,
            include_new_tables=not args.exclude_new_tables
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