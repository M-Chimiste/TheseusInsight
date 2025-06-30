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
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional

from ...data_access import (
    PaperRepository, NewsletterRepository, PodcastRepository, 
    LitReviewRepository, ResearchRunRepository, ResearchAgentStateRepository,
    PaperFulltextRepository, MindmapReportRepository, ModelCatalogRepository
)
from ...data_model.papers import Paper, Podcast, Newsletter
from ...db import get_cursor


class DatabaseImporter:
    """Handles importing database contents from JSON files."""
    
    def __init__(self, db_path: str):
        """
        Initialize the importer.
        
        Args:
            db_path: Database connection string (PostgreSQL URL)
        """
        # Store the db_path for reference (repositories handle their own connections)
        self.db_path = db_path

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
            
            # Core required tables (literature_reviews is optional for backward compatibility)
            expected_tables = {"papers", "podcasts", "newsletters"}
            exported_tables = set(metadata["tables_exported"])
            
            if not expected_tables.issubset(exported_tables):
                missing = expected_tables - exported_tables
                print(f"Warning: Missing expected tables in export: {missing}")
                return False
            
            # Check version and available features
            export_version = metadata.get("export_version", "1.0")
            print(f"Export version: {export_version}")
            
            # List new features if available
            new_features = metadata.get("new_features", [])
            if new_features:
                print(f"New features detected: {new_features}")
            
            # Check if new tables are available
            new_table_names = {
                "research_runs", "research_agent_state", "paper_fulltext",
                "mindmap_reports", "model_catalog"
            }
            available_new_tables = new_table_names.intersection(exported_tables)
            if available_new_tables:
                print(f"New tables available for import: {available_new_tables}")
            
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

        seen_titles = set()
        seen_urls = set()

        for i, paper_data in enumerate(papers_data):
            try:
                # Skip if paper exists by title or URL in DB or has appeared earlier in this import
                if skip_duplicates:
                    if (
                        PaperRepository.exists_by_url(paper_data["url"]) or
                        PaperRepository.exists_by_title(paper_data["title"]) or
                        paper_data["url"] in seen_urls or
                        paper_data["title"] in seen_titles
                    ):
                        stats["skipped"] += 1
                        continue

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
                
                seen_titles.add(paper_data["title"])
                seen_urls.add(paper_data["url"])

                # Insert paper (with duplicate handling)
                was_inserted = PaperRepository.insert_paper(paper, skip_duplicates=skip_duplicates)
                
                # Get paper_id for additional updates
                paper_record = PaperRepository.get_by_url(paper_data["url"])
                paper_id = paper_record["id"] if paper_record else None

                if was_inserted:
                    stats["imported"] += 1
                else:
                    stats["skipped"] += 1
                    
                # Update summary / keywords if available and paper exists
                if paper_id:
                    # Handle backward compatibility: 'summary' field maps to 'text' in PostgreSQL
                    if paper_data.get("summary"):
                        try:
                            with get_cursor() as cursor:
                                cursor.execute("UPDATE papers SET text = %s WHERE id = %s", 
                                             (paper_data["summary"], paper_id))
                        except Exception:
                            pass
                    if paper_data.get("keywords"):
                        try:
                            PaperRepository.update_keywords(paper_id, paper_data["keywords"])
                        except Exception:
                            pass

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
                    with get_cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM podcasts WHERE title = %s", (podcast_data["title"],))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Create Podcast object
                podcast = Podcast(
                    title=podcast_data["title"],
                    date=podcast_data["date"],
                    script=podcast_data["script"],
                    description=podcast_data["description"]
                )
                
                # Insert podcast using repository
                PodcastRepository.insert(podcast)
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
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM newsletters 
                            WHERE start_date = %s AND end_date = %s
                        """, (newsletter_data["start_date"], newsletter_data["end_date"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Create Newsletter object
                newsletter = Newsletter(
                    content=newsletter_data["content"],
                    start_date=newsletter_data["start_date"],
                    end_date=newsletter_data["end_date"],
                    date_sent=newsletter_data["date_sent"]
                )
                
                # Insert newsletter using repository
                NewsletterRepository.insert(newsletter)
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing newsletter {newsletter_data.get('start_date', 'Unknown')}-{newsletter_data.get('end_date', 'Unknown')}: {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(newsletters_data), f"Importing newsletters: {i + 1}/{len(newsletters_data)}")
        
        print(f"Newsletters import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_literature_reviews(self, literature_reviews_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import literature reviews from JSON file.
        
        Args:
            literature_reviews_file: Path to literature_reviews.json file
            skip_duplicates: Whether to skip literature reviews that already exist (by research question and date)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing literature reviews...")
        
        with open(literature_reviews_file, 'r', encoding='utf-8') as f:
            literature_reviews_data = json.load(f)
        
        stats = {"total": len(literature_reviews_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, review_data in enumerate(literature_reviews_data):
            try:
                # Check for duplicates by research question and creation timestamp if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM lit_reviews 
                            WHERE research_question = %s AND created_ts = %s
                        """, (review_data["research_question"], review_data["created_ts"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert literature review using repository
                LitReviewRepository.insert(
                    research_question=review_data["research_question"],
                    summary_json=review_data["summary_json"],
                    trace_json=review_data["trace_json"],
                    report_text=review_data.get("report_text")  # Optional field for backward compatibility
                )
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing literature review '{review_data.get('research_question', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(literature_reviews_data), f"Importing literature reviews: {i + 1}/{len(literature_reviews_data)}")
        
        print(f"Literature reviews import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_research_runs(self, research_runs_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import research runs from JSON file.
        
        Args:
            research_runs_file: Path to research_runs.json file
            skip_duplicates: Whether to skip research runs that already exist (by task_id)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing research runs...")
        
        with open(research_runs_file, 'r', encoding='utf-8') as f:
            research_runs_data = json.load(f)
        
        stats = {"total": len(research_runs_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, run_data in enumerate(research_runs_data):
            try:
                # Check for duplicates by task_id if requested
                if skip_duplicates:
                    existing_run = ResearchRunRepository.get(run_data["task_id"])
                    if existing_run:
                        stats["skipped"] += 1
                        continue
                
                # Insert research run - use raw SQL to handle all fields including timestamps
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_runs 
                        (task_id, research_question, status, config_json, created_at, started_at,
                         completed_at, error_message, final_answer, generation_summary, statistics_json,
                         sub_queries_json, sources_gathered_json, judged_sources_json, evidence_json,
                         compressed_notes, workflow_messages_json, research_loop_count, is_sufficient, save_to_library)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        run_data["task_id"],
                        run_data["research_question"],
                        run_data["status"],
                        json.dumps(run_data.get("config")) if run_data.get("config") else None,
                        run_data["created_at"],
                        run_data.get("started_at"),
                        run_data.get("completed_at"),
                        run_data.get("error_message"),
                        run_data.get("final_answer"),
                        run_data.get("generation_summary"),
                        json.dumps(run_data.get("statistics")) if run_data.get("statistics") else None,
                        json.dumps(run_data.get("sub_queries", [])),
                        json.dumps(run_data.get("sources_gathered", [])),
                        json.dumps(run_data.get("judged_sources", [])),
                        json.dumps(run_data.get("evidence", [])),
                        run_data.get("compressed_notes"),
                        json.dumps(run_data.get("workflow_messages", [])),
                        run_data.get("research_loop_count", 0),
                        run_data.get("is_sufficient", False),
                        run_data.get("save_to_library", True)
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing research run '{run_data.get('task_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(research_runs_data), f"Importing research runs: {i + 1}/{len(research_runs_data)}")
        
        print(f"Research runs import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_research_agent_state(self, research_agent_state_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import research agent state snapshots from JSON file.
        
        Args:
            research_agent_state_file: Path to research_agent_state.json file
            skip_duplicates: Whether to skip state snapshots that already exist (by id or timestamp+task_id+node_name)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing research agent state...")
        
        with open(research_agent_state_file, 'r', encoding='utf-8') as f:
            state_data = json.load(f)
        
        stats = {"total": len(state_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, state_record in enumerate(state_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM research_agent_state 
                            WHERE task_id = %s AND node_name = %s AND timestamp = %s
                        """, (state_record["task_id"], state_record["node_name"], state_record["timestamp"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert state record
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO research_agent_state (task_id, node_name, state_json, timestamp)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        state_record["task_id"],
                        state_record["node_name"],
                        state_record["state_json"],
                        state_record["timestamp"]
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing research agent state for task '{state_record.get('task_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(state_data), f"Importing research agent state: {i + 1}/{len(state_data)}")
        
        print(f"Research agent state import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_paper_fulltext(self, paper_fulltext_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import paper full-text content from JSON file.
        
        Args:
            paper_fulltext_file: Path to paper_fulltext.json file
            skip_duplicates: Whether to skip full-text entries that already exist (by paper_id)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing paper full-text content...")
        
        with open(paper_fulltext_file, 'r', encoding='utf-8') as f:
            fulltext_data = json.load(f)
        
        stats = {"total": len(fulltext_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, fulltext_record in enumerate(fulltext_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    if PaperFulltextRepository.exists(fulltext_record["paper_id"]):
                        stats["skipped"] += 1
                        continue
                
                # Convert embedding from list to pgvector format if present
                embedding_str = None
                if fulltext_record.get("embedding"):
                    try:
                        # Convert list to JSON string for pgvector
                        embedding_str = json.dumps(fulltext_record["embedding"])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for paper_id {fulltext_record['paper_id']}: {e}")
                
                # Handle metadata
                metadata_str = None
                if fulltext_record.get("metadata"):
                    try:
                        metadata_str = json.dumps(fulltext_record["metadata"]) if isinstance(fulltext_record["metadata"], dict) else fulltext_record["metadata"]
                    except:
                        metadata_str = str(fulltext_record["metadata"])
                
                # Insert full-text record using repository
                PaperFulltextRepository.insert(
                    paper_id=fulltext_record["paper_id"],
                    content=fulltext_record["content"],
                    embedding=embedding_str,
                    embedding_model=fulltext_record.get("embedding_model"),
                    extraction_method=fulltext_record.get("extraction_method", "unknown"),
                    metadata=metadata_str
                )
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing paper fulltext for paper_id '{fulltext_record.get('paper_id', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(fulltext_data), f"Importing paper fulltext: {i + 1}/{len(fulltext_data)}")
        
        print(f"Paper fulltext import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_mindmap_reports(self, mindmap_reports_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import mindmap reports from JSON file.
        
        Args:
            mindmap_reports_file: Path to mindmap_reports.json file
            skip_duplicates: Whether to skip mindmap reports that already exist (by title and created_at)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing mindmap reports...")
        
        with open(mindmap_reports_file, 'r', encoding='utf-8') as f:
            reports_data = json.load(f)
        
        stats = {"total": len(reports_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, report_data in enumerate(reports_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT COUNT(*) FROM mindmap_reports 
                            WHERE title = %s AND created_at = %s
                        """, (report_data["title"], report_data["created_at"]))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert mindmap report directly to preserve all original data including IDs
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO mindmap_reports 
                        (title, description, seed_paper_id, seed_paper_title, mindmap_data_json, 
                         parameters_json, statistics_json, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        report_data["title"],
                        report_data.get("description"),
                        report_data["seed_paper_id"],
                        report_data["seed_paper_title"],
                        json.dumps(report_data.get("mindmap_data", {})),
                        json.dumps(report_data.get("parameters", {})),
                        json.dumps(report_data.get("statistics", {})),
                        report_data["created_at"]
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing mindmap report '{report_data.get('title', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(reports_data), f"Importing mindmap reports: {i + 1}/{len(reports_data)}")
        
        print(f"Mindmap reports import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
        return stats
    
    def import_model_catalog(self, model_catalog_file: str, skip_duplicates: bool = True, progress_callback=None) -> Dict[str, int]:
        """
        Import model catalog entries from JSON file.
        
        Args:
            model_catalog_file: Path to model_catalog.json file
            skip_duplicates: Whether to skip model catalog entries that already exist (by alias)
            progress_callback: Optional callback function(current, total, message)
            
        Returns:
            Dictionary with import statistics
        """
        print("Importing model catalog...")
        
        with open(model_catalog_file, 'r', encoding='utf-8') as f:
            catalog_data = json.load(f)
        
        stats = {"total": len(catalog_data), "imported": 0, "skipped": 0, "errors": 0}
        
        for i, model_data in enumerate(catalog_data):
            try:
                # Check for duplicates if requested
                if skip_duplicates:
                    with get_cursor() as cursor:
                        cursor.execute("SELECT COUNT(*) FROM model_catalog WHERE alias = %s", (model_data["alias"],))
                        if cursor.fetchone()[0] > 0:
                            stats["skipped"] += 1
                            continue
                
                # Insert model catalog entry
                with get_cursor() as cursor:
                    cursor.execute("""
                        INSERT INTO model_catalog 
                        (alias, model_string, provider_name, model_type, description, max_new_tokens,
                         temperature, num_ctx, trust_remote_code, tags_json, is_favorite, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        model_data["alias"],
                        model_data["model_string"],
                        model_data["provider_name"],
                        model_data["model_type"],
                        model_data.get("description"),
                        model_data.get("max_new_tokens"),
                        model_data.get("temperature"),
                        model_data.get("num_ctx"),
                        model_data.get("trust_remote_code", False),
                        json.dumps(model_data.get("tags", [])),
                        model_data.get("is_favorite", False),
                        model_data.get("created_at"),
                        model_data.get("updated_at")
                    ))
                
                stats["imported"] += 1
                
            except Exception as e:
                print(f"Error importing model catalog entry '{model_data.get('alias', 'Unknown')}': {e}")
                stats["errors"] += 1
            
            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(catalog_data), f"Importing model catalog: {i + 1}/{len(catalog_data)}")
        
        print(f"Model catalog import completed: {stats['imported']} imported, {stats['skipped']} skipped, {stats['errors']} errors")
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
        
        # Check what files are available
        available_files = []
        file_map = {
            "papers": "papers.json",
            "podcasts": "podcasts.json", 
            "newsletters": "newsletters.json",
            "literature_reviews": "literature_reviews.json",
            "research_runs": "research_runs.json",
            "research_agent_state": "research_agent_state.json",
            "paper_fulltext": "paper_fulltext.json",
            "mindmap_reports": "mindmap_reports.json",
            "model_catalog": "model_catalog.json"
        }
        
        for table_name, filename in file_map.items():
            if (input_path / filename).exists():
                available_files.append(table_name)
        
        total_steps = len(available_files)
        
        # Helper function to create progress callback for each import
        def create_progress_callback(step_index, table_name):
            def table_progress_callback(current, total, message):
                if progress_callback:
                    # Calculate overall progress: each table gets equal weight
                    step_progress = (current / total) * (100 / total_steps)
                    overall_progress = int((step_index / total_steps) * 100 + step_progress)
                    progress_callback(overall_progress, 100, f"{table_name}: {message}")
            return table_progress_callback
        
        # Import each available table
        for i, table_name in enumerate(available_files):
            filename = file_map[table_name]
            file_path = input_path / filename
            
            if progress_callback:
                progress_callback(int((i / total_steps) * 100), 100, f"Starting {table_name} import...")
            
            try:
                if table_name == "papers":
                    results[table_name] = self.import_papers(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "podcasts":
                    results[table_name] = self.import_podcasts(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "newsletters":
                    results[table_name] = self.import_newsletters(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "literature_reviews":
                    results[table_name] = self.import_literature_reviews(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "research_runs":
                    results[table_name] = self.import_research_runs(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "research_agent_state":
                    results[table_name] = self.import_research_agent_state(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "paper_fulltext":
                    results[table_name] = self.import_paper_fulltext(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "mindmap_reports":
                    results[table_name] = self.import_mindmap_reports(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
                elif table_name == "model_catalog":
                    results[table_name] = self.import_model_catalog(
                        str(file_path), skip_duplicates, create_progress_callback(i, table_name)
                    )
            except Exception as e:
                print(f"Error importing {table_name}: {e}")
                results[table_name] = {"error": str(e)}
        
        # Handle missing files with informative messages
        for table_name, filename in file_map.items():
            if table_name not in results:
                if table_name in ["papers", "podcasts", "newsletters"]:
                    print(f"Warning: {filename} not found")
                    results[table_name] = {"error": "File not found"}
                else:
                    print(f"Note: {filename} not found (this is optional for older exports)")
                    results[table_name] = {"note": "File not found (optional)"}
        
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
        Clear all data from the main tables.
        WARNING: This is destructive and cannot be undone.
        
        Args:
            progress_callback: Optional callback function(current, total, message)
        
        Returns:
            Dictionary with counts of deleted records for each table
        """
        print("WARNING: Clearing all data from database tables...")
        
        # Tables to clear in order (respecting potential foreign key constraints)
        tables_to_clear = [
            'logs', 'tasks', 'research_agent_state', 'research_runs', 'lit_reviews', 
            'mindmap_reports', 'model_catalog', 'paper_fulltext', 'newsletters', 'podcasts', 'papers'
        ]
        deletion_counts = {}
        total_tables = len(tables_to_clear)
        
        with get_cursor() as cursor:
            for i, table in enumerate(tables_to_clear):
                if progress_callback:
                    progress_callback(i, total_tables, f"Clearing {table} table...")
                
                try:
                    # Get count before deletion
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count_before = cursor.fetchone()[0]
                    
                    # Delete all records (PostgreSQL doesn't require special syntax)
                    cursor.execute(f"DELETE FROM {table}")
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