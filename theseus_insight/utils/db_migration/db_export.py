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
import hashlib
import logging
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...data_access import (
    PaperRepository, NewsletterRepository, PodcastRepository, 
    LitReviewRepository, ResearchRunRepository, ResearchAgentStateRepository,
    PaperFulltextRepository, MindmapReportRepository, ModelCatalogRepository
)
from ...db import get_cursor

logger = logging.getLogger(__name__)

# Import parallel processor if available
try:
    from .parallel_processor import ParallelExporter
    PARALLEL_AVAILABLE = True
except ImportError:
    PARALLEL_AVAILABLE = False
    logger.debug("Parallel processing not available")


class DatabaseExporter:
    """Handles exporting database contents to JSON files."""
    
    def __init__(self, db_path: str, output_dir: str, batch_size: int = 1000, streaming: bool = False, parallel: bool = False, max_workers: int = 4, incremental: bool = False, since_timestamp: datetime.datetime = None):
        """
        Initialize the exporter.
        
        Args:
            db_path: Database connection string (PostgreSQL URL)
            output_dir: Directory to save exported files
            batch_size: Number of records to process at once when streaming
            streaming: Enable streaming mode for large datasets
            parallel: Enable parallel processing
            max_workers: Maximum parallel workers
            incremental: Enable incremental export mode
            since_timestamp: For incremental exports, export changes since this timestamp
        """
        # Store the db_path for reference (repositories handle their own connections)
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.batch_size = batch_size
        self.streaming = streaming
        self.parallel = parallel and PARALLEL_AVAILABLE
        self.max_workers = max_workers
        self.incremental = incremental
        self.since_timestamp = since_timestamp
        self.export_version = "6.0"  # Updated version with profile-scoped export support
        
    def _stream_table_data(self, table_name: str, query: str, params: tuple = None) -> Iterator[tuple[List[Dict], int]]:
        """
        Stream table data in batches to avoid memory issues.
        
        Args:
            table_name: Name of the table being exported
            query: SQL query to execute
            params: Query parameters
            
        Yields:
            Tuple of (batch of records, total count)
        """
        # Need to use autocommit=False to create a transaction block for the cursor
        with get_cursor(autocommit=False) as cursor:
            try:
                # Get total count for progress tracking
                count_query = f"SELECT COUNT(*) AS count FROM ({query}) AS subquery"
                cursor.execute(count_query, params)
                result = cursor.fetchone()
                print(f"[DEBUG] Count query result: {result}")
                print(f"[DEBUG] Result keys: {result.keys() if result else 'None'}")
                total_count = result['count'] if result else 0
                
                logger.info(f"Streaming {total_count} records from {table_name}")
                
                # Use server-side cursor for streaming
                cursor.execute(f"DECLARE export_cursor CURSOR FOR {query}", params)
                
                records_processed = 0
                while True:
                    cursor.execute(f"FETCH {self.batch_size} FROM export_cursor")
                    batch = cursor.fetchall()
                    
                    if not batch:
                        break
                        
                    records_processed += len(batch)
                    logger.debug(f"Processed {records_processed}/{total_count} records from {table_name}")
                    
                    yield (batch, total_count)
                
                cursor.execute("CLOSE export_cursor")
                cursor.connection.commit()  # Commit the transaction
            except Exception:
                cursor.connection.rollback()  # Rollback on error
                raise
    
    def _convert_special_types(self, row: Dict) -> Dict:
        """Convert special PostgreSQL types to JSON-serializable formats."""
        converted = {}
        
        for key, value in row.items():
            if value is None:
                converted[key] = None
            elif hasattr(value, 'strftime'):  # datetime
                converted[key] = value.isoformat()
            elif hasattr(value, 'tolist'):  # numpy array or similar
                converted[key] = value.tolist()
            elif key.endswith('_json') and isinstance(value, str):
                # Already JSON string, keep as is
                converted[key] = value
            elif key == 'embedding' and value is not None:
                # Handle pgvector embeddings
                try:
                    if isinstance(value, str):
                        converted[key] = json.loads(value)
                    elif isinstance(value, (list, tuple)):
                        converted[key] = list(value)
                    else:
                        converted[key] = value
                except Exception as e:
                    logger.warning(f"Could not convert embedding: {e}")
                    converted[key] = None
            else:
                converted[key] = value
                
        return converted
    
    def export_table_streaming(
        self, 
        table_name: str, 
        query: str,
        output_filename: str,
        params: tuple = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Export table data to JSON file using streaming to handle large datasets.
        
        Args:
            table_name: Table name for logging
            query: SQL query to execute
            output_filename: Output JSON file name (without extension)
            params: Query parameters
            progress_callback: Optional progress callback function
            
        Returns:
            Export statistics including file path, size, and checksum
        """
        output_file = self.output_dir / output_filename
        start_time = datetime.datetime.now()
        
        stats = {
            "file_path": str(output_file),
            "records_exported": 0,
            "batches_processed": 0,
            "export_time": 0,
            "file_size": 0,
            "checksum": "",
        }
        
        # Create checksum hasher
        hasher = hashlib.sha256()
        
        # Write JSON array manually to support streaming
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('[\n')
            first_record = True
            total_records = 0
            last_progress_pct = -1  # Track last reported progress to prevent flooding
            
            for batch_num, (batch, total_count) in enumerate(self._stream_table_data(table_name, query, params)):
                stats["batches_processed"] += 1
                total_records = total_count  # Store for progress reporting
                
                for row in batch:
                    # Convert special types
                    converted_row = self._convert_special_types(row)
                    
                    # Write record
                    if not first_record:
                        f.write(',\n')
                    first_record = False
                    
                    row_json = json.dumps(converted_row, ensure_ascii=False, default=str)
                    f.write('  ' + row_json)
                    
                    # Update checksum
                    hasher.update(row_json.encode())
                    
                    stats["records_exported"] += 1
                
                # Throttle progress callback - only report when percentage changes significantly
                if progress_callback and total_records > 0:
                    progress_pct = int((stats["records_exported"] / total_records) * 100)
                    # Only report progress if it changed by at least 5% or this is the last batch
                    if progress_pct >= last_progress_pct + 5 or stats["records_exported"] >= total_records:
                        progress_callback(
                            stats["records_exported"], 
                            total_records,
                            f"Exported {stats['records_exported']:,}/{total_records:,} records from {table_name}"
                        )
                        last_progress_pct = progress_pct
            
            f.write('\n]')
        
        # Calculate final stats
        stats["export_time"] = (datetime.datetime.now() - start_time).total_seconds()
        stats["file_size"] = output_file.stat().st_size
        stats["checksum"] = hasher.hexdigest()
        
        logger.info(f"Exported {stats['records_exported']} records from {table_name} in {stats['export_time']:.2f}s")
        
        return stats
        
    def export_papers(self, progress_callback: Optional[Callable] = None) -> str:
        """Export all papers to JSON file."""
        print("Exporting papers...")
        print(f"[DEBUG] Database URL: {os.getenv('DATABASE_URL', 'NOT SET')[:50]}...")  # Show first 50 chars
        print(f"[DEBUG] Streaming mode: {self.streaming}")
        print(f"[DEBUG] Incremental mode: {self.incremental}")
        
        # Test database connection first
        try:
            print("[DEBUG] Testing database connection...")
            with get_cursor() as cursor:
                cursor.execute("SELECT 1 AS test")
                result = cursor.fetchone()
                print(f"[DEBUG] Database connection test successful: {result}")
                
                # Also test papers count
                cursor.execute("SELECT COUNT(*) AS count FROM papers")
                count_result = cursor.fetchone()
                print(f"[DEBUG] Papers table has {count_result['count']} records")
        except Exception as e:
            print(f"[ERROR] Failed to connect to database: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Use streaming mode if enabled
        if self.streaming:
            print("[DEBUG] Using streaming mode for papers export")
            # Build query to get all columns
            try:
                print("[DEBUG] Getting database cursor...")
                with get_cursor() as cursor:
                    print("[DEBUG] Executing column query...")
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'papers' AND table_schema = 'public'
                    """)
                    existing_columns = {row['column_name'] for row in cursor.fetchall()}
                
                # Build column list based on what exists
                columns = ['id', 'title', 'abstract', 'date', 'date_run', 'score', 'rationale', 
                          'related', 'cosine_similarity', 'url', 'embedding_model', 'embedding']
                
                # Add optional columns if they exist
                if 'text' in existing_columns:
                    columns.append('text')
                if 'summary' in existing_columns:
                    columns.append('summary')
                if 'keywords_json' in existing_columns:
                    columns.append('keywords_json')
                if 'fulltext_extraction_status' in existing_columns:
                    columns.append('fulltext_extraction_status')
                if 'downloaded_pdf_path' in existing_columns:
                    columns.append('downloaded_pdf_path')
                
                # Build query
                column_str = ', '.join(columns)
                query = f"SELECT {column_str} FROM papers ORDER BY id DESC"
                
                # Use streaming export
                stats = self.export_table_streaming(
                                          "papers",
                      query,
                      "papers.json",
                      progress_callback=progress_callback
                )
                
                return str(self.output_dir / "papers.json")
            except Exception as e:
                print(f"[ERROR] Failed to export papers in streaming mode: {e}")
                import traceback
                traceback.print_exc()
                raise
        
        # Original non-streaming implementation
        papers = []
        print("[DEBUG] Starting non-streaming papers export")
        try:
            print("[DEBUG] Getting database cursor for papers export...")
            with get_cursor() as cursor:
                print("[DEBUG] Got cursor, checking existing columns...")
                # Check which columns exist in the papers table
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'papers' AND table_schema = 'public'
                """)
                print("[DEBUG] Column query executed, fetching results...")
                existing_columns = {row['column_name'] for row in cursor.fetchall()}
                print(f"[DEBUG] Found {len(existing_columns)} columns in papers table")
                
                # Build column list based on what exists
                columns = ['id', 'title', 'abstract', 'date', 'date_run', 'score', 'rationale', 
                          'related', 'cosine_similarity', 'url', 'embedding_model', 'embedding']
                
                # Add optional columns if they exist
                if 'text' in existing_columns:
                    columns.append('text')
                if 'summary' in existing_columns:
                    columns.append('summary')
                if 'keywords_json' in existing_columns:
                    columns.append('keywords_json')
                if 'fulltext_extraction_status' in existing_columns:
                    columns.append('fulltext_extraction_status')
                if 'downloaded_pdf_path' in existing_columns:
                    columns.append('downloaded_pdf_path')
                
                # Build and execute query
                column_str = ', '.join(columns)
                print(f"[DEBUG] Executing papers query with columns: {column_str[:100]}...")
                cursor.execute(f"SELECT {column_str} FROM papers ORDER BY id DESC")
                print("[DEBUG] Papers query executed, fetching all rows...")
                rows = cursor.fetchall()
                print(f"[DEBUG] Fetched {len(rows)} papers from database")

                for row in rows:
                    # Convert date objects to strings
                    def _to_str(val):
                        return val.strftime('%Y-%m-%d') if hasattr(val, 'strftime') else str(val) if val else None

                    # Handle embedding conversion from pgvector to list
                    embedding = None
                    if row['embedding'] is not None:
                        try:
                            # pgvector stores as string like '[1,2,3]'
                            if isinstance(row['embedding'], str):
                                embedding = json.loads(row['embedding'])
                            elif hasattr(row['embedding'], 'tolist'):
                                embedding = row['embedding'].tolist()
                            elif isinstance(row['embedding'], (list, tuple)):
                                embedding = list(row['embedding'])
                        except Exception as e:
                            print(f"Warning: Could not convert embedding for paper {row['id']}: {e}")
                            embedding = None

                    # Handle keywords JSON
                    keywords = []
                    keywords_json = row.get('keywords_json')
                    if keywords_json:
                        try:
                            if isinstance(keywords_json, str):
                                keywords = json.loads(keywords_json)
                            elif isinstance(keywords_json, dict):
                                # If it's already a dict, extract the keywords list
                                keywords = keywords_json.get('keywords', [])
                            elif isinstance(keywords_json, (list, tuple)):
                                keywords = list(keywords_json)
                        except Exception:
                            keywords = []

                    paper_data = {
                        'id': row['id'],
                        'title': row['title'],
                        'abstract': row['abstract'],
                        'date': _to_str(row['date']),
                        'date_run': _to_str(row['date_run']),
                        'score': row['score'],
                        'rationale': row['rationale'],
                        'related': bool(row['related']) if row['related'] is not None else None,
                        'cosine_similarity': row['cosine_similarity'],
                        'url': row['url'],
                        'embedding_model': row['embedding_model'],
                        'embedding': embedding,
                        'keywords': keywords,
                    }
                    
                    # Add optional fields if they exist
                    if 'text' in row:
                        paper_data['text'] = row.get('text')
                    if 'summary' in row:
                        paper_data['summary'] = row.get('summary')
                    elif 'text' in row:  # Fallback to text if no summary
                        paper_data['summary'] = row.get('text')
                    if 'keywords_json' in row:
                        paper_data['keywords_json'] = keywords_json
                    if 'fulltext_extraction_status' in row:
                        paper_data['fulltext_extraction_status'] = row.get('fulltext_extraction_status')
                    if 'downloaded_pdf_path' in row:
                        paper_data['downloaded_pdf_path'] = row.get('downloaded_pdf_path')
                    
                    papers.append(paper_data)
        
            print(f"[DEBUG] Processed {len(papers)} papers")
                
        except Exception as e:
            print(f"[ERROR] Failed to export papers: {e}")
            import traceback
            traceback.print_exc()
            raise
            
        output_file = self.output_dir / "papers.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(papers, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(papers)} papers to {output_file}")
        return str(output_file)
    
    def export_podcasts(self) -> str:
        """Export all podcasts to JSON file."""
        print("Exporting podcasts...")
        
        podcasts = []
        with get_cursor() as cursor:
            cursor.execute("SELECT id, title, date, script, description FROM podcasts ORDER BY id DESC")
            rows = cursor.fetchall()
            
            for row in rows:
                podcasts.append({
                    'id': row['id'],
                    'title': row['title'],
                    'date': row['date'].strftime('%Y-%m-%d') if row['date'] else None,
                    'script': row['script'],
                    'description': row['description']
                })
        
        output_file = self.output_dir / "podcasts.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(podcasts, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(podcasts)} podcasts to {output_file}")
        return str(output_file)
    
    def export_newsletters(self) -> str:
        """Export all newsletters to JSON file."""
        print("Exporting newsletters...")
        
        newsletters = []
        with get_cursor() as cursor:
            cursor.execute("SELECT id, content, start_date, end_date, date_sent FROM newsletters ORDER BY id DESC")
            rows = cursor.fetchall()
            
            for row in rows:
                newsletters.append({
                    'id': row['id'],
                    'content': row['content'],
                    'start_date': row['start_date'].strftime('%Y-%m-%d') if row['start_date'] else None,
                    'end_date': row['end_date'].strftime('%Y-%m-%d') if row['end_date'] else None,
                    'date_sent': row['date_sent'].strftime('%Y-%m-%d') if row['date_sent'] else None
                })
        
        output_file = self.output_dir / "newsletters.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(newsletters, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(newsletters)} newsletters to {output_file}")
        return str(output_file)
    
    def export_literature_reviews(self) -> str:
        """Export all literature reviews to JSON file."""
        print("Exporting literature reviews...")
        
        literature_reviews = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, research_question, summary_json, trace_json, report_text, created_ts
                FROM lit_reviews ORDER BY id DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                literature_reviews.append({
                    'id': row['id'],
                    'research_question': row['research_question'],
                    'summary_json': row['summary_json'],
                    'trace_json': row['trace_json'],
                    'report_text': row['report_text'],
                    'created_ts': row['created_ts'].isoformat() if row['created_ts'] else None
                })
        
        output_file = self.output_dir / "literature_reviews.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(literature_reviews, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(literature_reviews)} literature reviews to {output_file}")
        return str(output_file)
    
    def export_research_runs(self) -> str:
        """Export all research runs to JSON file."""
        print("Exporting research runs...")
        
        research_runs = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT task_id, research_question, status, config_json, created_at, started_at,
                       completed_at, error_message, final_answer, generation_summary, statistics_json,
                       sub_queries_json, sources_gathered_json, judged_sources_json, evidence_json,
                       compressed_notes, workflow_messages_json, research_loop_count, is_sufficient, save_to_library
                FROM research_runs ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                # Parse JSON fields
                def safe_json_parse(json_str):
                    if json_str:
                        try:
                            return json.loads(json_str) if isinstance(json_str, str) else json_str
                        except:
                            return json_str
                    return None

                research_runs.append({
                    'task_id': row['task_id'],
                    'research_question': row['research_question'],
                    'status': row['status'],
                    'config': safe_json_parse(row['config_json']),
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                    'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
                    'error_message': row['error_message'],
                    'final_answer': row['final_answer'],
                    'generation_summary': row['generation_summary'],
                    'statistics': safe_json_parse(row['statistics_json']),
                    'sub_queries': safe_json_parse(row['sub_queries_json']) or [],
                    'sources_gathered': safe_json_parse(row['sources_gathered_json']) or [],
                    'judged_sources': safe_json_parse(row['judged_sources_json']) or [],
                    'evidence': safe_json_parse(row['evidence_json']) or [],
                    'compressed_notes': row['compressed_notes'],
                    'workflow_messages': safe_json_parse(row['workflow_messages_json']) or [],
                    'research_loop_count': row['research_loop_count'] or 0,
                    'is_sufficient': bool(row['is_sufficient']) if row['is_sufficient'] is not None else False,
                    'save_to_library': bool(row['save_to_library']) if row['save_to_library'] is not None else True
                })
        
        output_file = self.output_dir / "research_runs.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(research_runs, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(research_runs)} research runs to {output_file}")
        return str(output_file)
    
    def export_research_agent_state(self) -> str:
        """Export all research agent state snapshots to JSON file."""
        print("Exporting research agent state...")
        
        states = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, task_id, node_name, state_json, timestamp
                FROM research_agent_state
                ORDER BY timestamp ASC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                states.append({
                    'id': row['id'],
                    'task_id': row['task_id'],
                    'node_name': row['node_name'],
                    'state_json': row['state_json'],
                    'timestamp': row['timestamp'].isoformat() if row['timestamp'] else None
                })
        
        output_file = self.output_dir / "research_agent_state.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(states, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(states)} research agent states to {output_file}")
        return str(output_file)
    
    def export_paper_fulltext(self) -> str:
        """Export all paper full-text content to JSON file."""
        print("Exporting paper full-text content...")
        
        fulltext_data = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, paper_id, content, embedding, embedding_model, created_at, extraction_method, metadata
                FROM paper_fulltext
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                # Handle embedding conversion from pgvector to list
                embedding = None
                if row['embedding']:
                    try:
                        if isinstance(row['embedding'], str):
                            embedding = json.loads(row['embedding'])
                        elif hasattr(row['embedding'], 'tolist'):
                            embedding = row['embedding'].tolist()
                        elif isinstance(row['embedding'], (list, tuple)):
                            embedding = list(row['embedding'])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for paper_id {row['paper_id']}: {e}")
                        embedding = None
                
                # Handle metadata JSON
                metadata = None
                if row['metadata']:
                    try:
                        metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                    except:
                        metadata = row['metadata']
                
                fulltext_data.append({
                    'id': row['id'],
                    'paper_id': row['paper_id'],
                    'content': row['content'],
                    'embedding': embedding,
                    'embedding_model': row['embedding_model'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'extraction_method': row['extraction_method'],
                    'metadata': metadata
                })
        
        output_file = self.output_dir / "paper_fulltext.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(fulltext_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(fulltext_data)} paper full-text entries to {output_file}")
        return str(output_file)
    
    def export_mindmap_reports(self) -> str:
        """Export all mindmap reports to JSON file."""
        print("Exporting mindmap reports...")
        
        reports = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, title, description, seed_paper_id, seed_paper_title, 
                       mindmap_data_json, parameters_json, statistics_json, created_at
                FROM mindmap_reports ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                def safe_json_parse(json_str):
                    if json_str:
                        try:
                            return json.loads(json_str) if isinstance(json_str, str) else json_str
                        except:
                            return json_str
                    return None

                reports.append({
                    'id': row['id'],
                    'title': row['title'],
                    'description': row['description'],
                    'seed_paper_id': row['seed_paper_id'],
                    'seed_paper_title': row['seed_paper_title'],
                    'mindmap_data': safe_json_parse(row['mindmap_data_json']),
                    'parameters': safe_json_parse(row['parameters_json']),
                    'statistics': safe_json_parse(row['statistics_json']),
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                })
        
        output_file = self.output_dir / "mindmap_reports.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(reports, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(reports)} mindmap reports to {output_file}")
        return str(output_file)
    
    def export_model_catalog(self) -> str:
        """Export all model catalog entries to JSON file."""
        print("Exporting model catalog...")
        
        models = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, alias, model_string, provider_name, model_type, description, 
                       max_new_tokens, temperature, num_ctx, trust_remote_code, tags_json, 
                       is_favorite, created_at, updated_at
                FROM model_catalog ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                # Parse tags JSON
                tags = []
                if row['tags_json']:
                    try:
                        tags = json.loads(row['tags_json']) if isinstance(row['tags_json'], str) else row['tags_json']
                    except:
                        tags = []

                models.append({
                    'id': row['id'],
                    'alias': row['alias'],
                    'model_string': row['model_string'],
                    'provider_name': row['provider_name'],
                    'model_type': row['model_type'],
                    'description': row['description'],
                    'max_new_tokens': row['max_new_tokens'],
                    'temperature': row['temperature'],
                    'num_ctx': row['num_ctx'],
                    'trust_remote_code': bool(row['trust_remote_code']) if row['trust_remote_code'] is not None else False,
                    'tags': tags,
                    'is_favorite': bool(row['is_favorite']) if row['is_favorite'] is not None else False,
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                })
        
        output_file = self.output_dir / "model_catalog.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(models, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(models)} model catalog entries to {output_file}")
        return str(output_file)
    
    def export_topics(self) -> str:
        """Export all topics to JSON file."""
        print("Exporting topics...")
        
        topics = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, label, keywords, centroid_embedding, embedding_model, created_at, updated_at
                FROM topics ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                # Handle embedding conversion from pgvector to list
                embedding = None
                if row['centroid_embedding']:
                    try:
                        if isinstance(row['centroid_embedding'], str):
                            embedding = json.loads(row['centroid_embedding'])
                        elif hasattr(row['centroid_embedding'], 'tolist'):
                            embedding = row['centroid_embedding'].tolist()
                        elif isinstance(row['centroid_embedding'], (list, tuple)):
                            embedding = list(row['centroid_embedding'])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for topic {row['id']}: {e}")
                        embedding = None

                topics.append({
                    'id': row['id'],
                    'label': row['label'],
                    'keywords': list(row['keywords']) if row['keywords'] else [],
                    'centroid_embedding': embedding,
                    'embedding_model': row['embedding_model'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                })
        
        output_file = self.output_dir / "topics.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(topics, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(topics)} topics to {output_file}")
        return str(output_file)
    
    def export_topic_metrics(self) -> str:
        """Export all topic metrics to JSON file."""
        print("Exporting topic metrics...")
        
        metrics = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, topic_id, period_start, period_end, period_type, doc_count, 
                       avg_score, growth_rate, forecast_1m, forecast_3m, forecast_6m, created_at
                FROM topic_metrics ORDER BY topic_id, period_start DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                metrics.append({
                    'id': row['id'],
                    'topic_id': row['topic_id'],
                    'period_start': row['period_start'].isoformat() if row['period_start'] else None,
                    'period_end': row['period_end'].isoformat() if row['period_end'] else None,
                    'period_type': row['period_type'],
                    'doc_count': row['doc_count'],
                    'avg_score': row['avg_score'],
                    'growth_rate': row['growth_rate'],
                    'forecast_1m': row['forecast_1m'],
                    'forecast_3m': row['forecast_3m'],
                    'forecast_6m': row['forecast_6m'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                })
        
        output_file = self.output_dir / "topic_metrics.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(metrics)} topic metrics to {output_file}")
        return str(output_file)
    
    def export_paper_topics(self) -> str:
        """Export all paper-topic relationships to JSON file."""
        print("Exporting paper-topic relationships...")
        
        relationships = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, paper_id, topic_id, relevance_score, created_at
                FROM paper_topics ORDER BY paper_id, topic_id
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                relationships.append({
                    'id': row['id'],
                    'paper_id': row['paper_id'],
                    'topic_id': row['topic_id'],
                    'relevance_score': row['relevance_score'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                })
        
        output_file = self.output_dir / "paper_topics.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(relationships, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(relationships)} paper-topic relationships to {output_file}")
        return str(output_file)
    
    def export_research_profiles(self) -> str:
        """Export all research profiles to JSON file."""
        print("Exporting research profiles...")
        
        profiles = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, description, color, tags, email_recipients, 
                       arxiv_filters, is_active, is_default, created_at, updated_at
                FROM research_profiles ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                # Parse JSON fields
                def safe_json_parse(json_data):
                    if json_data:
                        try:
                            return json.loads(json_data) if isinstance(json_data, str) else json_data
                        except:
                            return json_data
                    return None

                profiles.append({
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'color': row['color'],
                    'tags': safe_json_parse(row['tags']) or [],
                    'email_recipients': safe_json_parse(row['email_recipients']) or [],
                    'arxiv_filters': safe_json_parse(row['arxiv_filters']) or {},
                    'is_active': bool(row['is_active']) if row['is_active'] is not None else True,
                    'is_default': bool(row['is_default']) if row['is_default'] is not None else False,
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                })
        
        output_file = self.output_dir / "research_profiles.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(profiles)} research profiles to {output_file}")
        return str(output_file)
    
    def export_profile_research_interests(self) -> str:
        """Export all profile research interests to JSON file."""
        print("Exporting profile research interests...")
        
        interests = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, profile_id, interest_text, embedding, embedding_model, created_at, updated_at
                FROM profile_research_interests ORDER BY profile_id, created_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                # Handle embedding conversion from pgvector to list
                embedding = None
                if row['embedding']:
                    try:
                        if isinstance(row['embedding'], str):
                            embedding = json.loads(row['embedding'])
                        elif hasattr(row['embedding'], 'tolist'):
                            embedding = row['embedding'].tolist()
                        elif isinstance(row['embedding'], (list, tuple)):
                            embedding = list(row['embedding'])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for profile interest {row['id']}: {e}")
                        embedding = None

                interests.append({
                    'id': row['id'],
                    'profile_id': row['profile_id'],
                    'interest_text': row['interest_text'],
                    'embedding': embedding,
                    'embedding_model': row['embedding_model'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                })
        
        output_file = self.output_dir / "profile_research_interests.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(interests, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(interests)} profile research interests to {output_file}")
        return str(output_file)
    
    def export_paper_profile_scores(self) -> str:
        """Export all paper profile scores to JSON file."""
        print("Exporting paper profile scores...")
        
        scores = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, paper_id, profile_id, score, related, rationale, 
                       date_scored, judge_model
                FROM paper_profile_scores ORDER BY paper_id, profile_id
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                scores.append({
                    'id': row['id'],
                    'paper_id': row['paper_id'],
                    'profile_id': row['profile_id'],
                    'score': row['score'],
                    'related': bool(row['related']) if row['related'] is not None else None,
                    'rationale': row['rationale'],
                    'date_scored': row['date_scored'].isoformat() if row['date_scored'] else None,
                    'judge_model': row['judge_model']
                })
        
        output_file = self.output_dir / "paper_profile_scores.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(scores, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(scores)} paper profile scores to {output_file}")
        return str(output_file)
    
    def export_research_interests(self) -> str:
        """Export all research interests to JSON file (legacy table, being phased out)."""
        print("Exporting research interests (legacy)...")
        
        interests = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, interest_text, embedding, embedding_model, created_at, updated_at
                FROM research_interests ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                # Handle embedding conversion from pgvector to list
                embedding = None
                if row['embedding']:
                    try:
                        if isinstance(row['embedding'], str):
                            embedding = json.loads(row['embedding'])
                        elif hasattr(row['embedding'], 'tolist'):
                            embedding = row['embedding'].tolist()
                        elif isinstance(row['embedding'], (list, tuple)):
                            embedding = list(row['embedding'])
                    except Exception as e:
                        print(f"Warning: Could not convert embedding for research interest {row['id']}: {e}")
                        embedding = None

                interests.append({
                    'id': row['id'],
                    'interest_text': row['interest_text'],
                    'embedding': embedding,
                    'embedding_model': row['embedding_model'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                })
        
        output_file = self.output_dir / "research_interests.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(interests, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(interests)} research interests to {output_file}")
        return str(output_file)
    
    def export_research_interest_metrics(self) -> str:
        """Export all research interest metrics to JSON file."""
        print("Exporting research interest metrics...")
        
        metrics = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, research_interest_id, period_start, period_end, period_type, 
                       doc_count, avg_relevance_score, avg_paper_score, growth_rate, 
                       forecast_1m, forecast_3m, forecast_6m, created_at
                FROM research_interest_metrics ORDER BY research_interest_id, period_start DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                metrics.append({
                    'id': row['id'],
                    'research_interest_id': row['research_interest_id'],
                    'period_start': row['period_start'].isoformat() if row['period_start'] else None,
                    'period_end': row['period_end'].isoformat() if row['period_end'] else None,
                    'period_type': row['period_type'],
                    'doc_count': row['doc_count'],
                    'avg_relevance_score': row['avg_relevance_score'],
                    'avg_paper_score': row['avg_paper_score'],
                    'growth_rate': row['growth_rate'],
                    'forecast_1m': row['forecast_1m'],
                    'forecast_3m': row['forecast_3m'],
                    'forecast_6m': row['forecast_6m'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                })
        
        output_file = self.output_dir / "research_interest_metrics.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(metrics)} research interest metrics to {output_file}")
        return str(output_file)
    
    def export_paper_research_interests(self) -> str:
        """Export all paper-research interest relationships to JSON file."""
        print("Exporting paper-research interest relationships...")
        
        relationships = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, paper_id, research_interest_id, similarity_score, created_at
                FROM paper_research_interests ORDER BY paper_id, research_interest_id
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                relationships.append({
                    'id': row['id'],
                    'paper_id': row['paper_id'],
                    'research_interest_id': row['research_interest_id'],
                    'similarity_score': row['similarity_score'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None
                })
        
        output_file = self.output_dir / "paper_research_interests.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(relationships, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(relationships)} paper-research interest relationships to {output_file}")
        return str(output_file)
    
    def export_label_summaries(self) -> str:
        """Export all label summaries to JSON file."""
        print("Exporting label summaries...")
        
        summaries = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, original_label, summarized_label, model_used, created_at, updated_at
                FROM label_summaries ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                summaries.append({
                    'id': row['id'],
                    'original_label': row['original_label'],
                    'summarized_label': row['summarized_label'],
                    'model_used': row['model_used'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                })
        
        output_file = self.output_dir / "label_summaries.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summaries, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(summaries)} label summaries to {output_file}")
        return str(output_file)
    
    def export_scheduled_tasks(self) -> str:
        """Export scheduled tasks configuration."""
        print("Exporting scheduled tasks...")
        
        tasks = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, name, task_type, profile_id, is_enabled, frequency,
                       day_of_week, day_of_month, hour, minute, timezone,
                       config, last_run_at, next_run_at, last_run_status,
                       last_run_task_id, run_count, error_count,
                       created_at, updated_at
                FROM scheduled_tasks
                ORDER BY id
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                tasks.append({
                    'id': row['id'],
                    'name': row['name'],
                    'task_type': row['task_type'],
                    'profile_id': row['profile_id'],
                    'is_enabled': row['is_enabled'],
                    'frequency': row['frequency'],
                    'day_of_week': row['day_of_week'],
                    'day_of_month': row['day_of_month'],
                    'hour': row['hour'],
                    'minute': row['minute'],
                    'timezone': row['timezone'],
                    'config': row['config'],
                    'last_run_at': row['last_run_at'].isoformat() if row['last_run_at'] else None,
                    'next_run_at': row['next_run_at'].isoformat() if row['next_run_at'] else None,
                    'last_run_status': row['last_run_status'],
                    'last_run_task_id': row['last_run_task_id'],
                    'run_count': row['run_count'],
                    'error_count': row['error_count'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                })
        
        output_file = self.output_dir / "scheduled_tasks.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(tasks)} scheduled tasks to {output_file}")
        return str(output_file)
    
    def export_scheduled_task_runs(self) -> str:
        """Export scheduled task run history."""
        print("Exporting scheduled task runs...")
        
        runs = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, scheduled_task_id, task_id, started_at, completed_at,
                       status, error_message, result
                FROM scheduled_task_runs
                ORDER BY started_at DESC
            """)
            rows = cursor.fetchall()
            
            for row in rows:
                runs.append({
                    'id': row['id'],
                    'scheduled_task_id': row['scheduled_task_id'],
                    'task_id': row['task_id'],
                    'started_at': row['started_at'].isoformat() if row['started_at'] else None,
                    'completed_at': row['completed_at'].isoformat() if row['completed_at'] else None,
                    'status': row['status'],
                    'error_message': row['error_message'],
                    'result': row['result']
                })
        
        output_file = self.output_dir / "scheduled_task_runs.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(runs, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(runs)} scheduled task runs to {output_file}")
        return str(output_file)
    
    def create_metadata(self) -> str:
        """Create metadata file with export information."""
        # Extract schema version if available
        schema_info = {}
        try:
            from .schema_versioning import SchemaVersionManager
            schema_manager = SchemaVersionManager(self.db_path)
            current_schema = schema_manager.extract_current_schema()
            schema_manager.save_schema_version(current_schema, self.output_dir)
            
            schema_info = {
                "schema_version": current_schema.version,
                "schema_fingerprint": current_schema.fingerprint,
                "compatible_versions": current_schema.compatible_versions
            }
        except Exception as e:
            logger.warning(f"Could not extract schema version: {e}")
        
        metadata = {
            "export_timestamp": datetime.datetime.now().isoformat(),
            "export_version": self.export_version,  # Use version from instance
            "tables_exported": [
                "papers", "podcasts", "newsletters", "literature_reviews",
                "research_profiles", "profile_research_interests", "paper_profile_scores",
                "research_runs", "research_agent_state", "paper_fulltext", 
                "mindmap_reports", "model_catalog", "topics", "topic_metrics",
                "paper_topics", "research_interests", "research_interest_metrics",
                "paper_research_interests", "label_summaries", "scheduled_tasks",
                "scheduled_task_runs"
            ],
            "description": "Theseus Insight database export with Research Profiles, Trends, Research Interests, and full feature set",
            "backwards_compatible": True,
            **schema_info,  # Include schema information if available
            "new_features": [
                "research_profiles", "profile_research_interests", "paper_profile_scores",
                "research_runs", "research_agent_state", "paper_fulltext",
                "mindmap_reports", "model_catalog", "topics", "topic_metrics",
                "paper_topics", "research_interests", "research_interest_metrics",
                "paper_research_interests", "label_summaries", "scheduled_tasks",
                "scheduled_task_runs"
            ]
        }
        
        output_file = self.output_dir / "metadata.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        return str(output_file)
    
    def export_incremental(self, tables: List[str] = None, since_timestamp: datetime.datetime = None) -> Dict[str, Any]:
        """
        Perform incremental export of database changes.
        
        Args:
            tables: List of tables to export incrementally (None for all supported)
            since_timestamp: Export changes since this timestamp (None for auto-detect)
            
        Returns:
            Export results with incremental metadata
        """
        try:
            from .incremental_ops import IncrementalExporter
        except ImportError:
            raise RuntimeError("Incremental export functionality not available")
        
        # Use provided timestamp or the one from constructor
        export_since = since_timestamp or self.since_timestamp
        
        logger.info(f"Starting incremental export since {export_since}")
        
        # Create incremental exporter
        incremental_exporter = IncrementalExporter(self.db_path, str(self.output_dir))
        
        # Perform incremental export
        metadata = incremental_exporter.export_incremental(
            since_timestamp=export_since,
            tables=tables
        )
        
        # Create regular metadata file for compatibility
        export_metadata = self.create_metadata()
        
        # Update metadata to indicate incremental export
        with open(self.output_dir / "metadata.json", 'r') as f:
            regular_metadata = json.load(f)
        
        regular_metadata.update({
            "export_type": "incremental",
            "incremental_since": export_since.isoformat() if export_since else None,
            "incremental_export_id": metadata.export_id,
            "change_summary": metadata.change_summary
        })
        
        with open(self.output_dir / "metadata.json", 'w') as f:
            json.dump(regular_metadata, f, indent=2)
        
        result = {
            "export_type": "incremental",
            "export_id": metadata.export_id,
            "since_timestamp": export_since,
            "until_timestamp": metadata.until_timestamp,
            "tables_exported": metadata.tables_included,
            "change_summary": metadata.change_summary,
            "output_directory": str(self.output_dir)
        }
        
        logger.info(f"Incremental export completed: {result}")
        return result
    
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
    
    def export_tables_parallel(self, tables: List[str], progress_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Export tables in parallel for improved performance.

        Args:
            tables: List of tables to export
            progress_callback: Optional progress callback

        Returns:
            Export results
        """
        if not self.parallel:
            raise RuntimeError("Parallel processing is not enabled")

        parallel_exporter = ParallelExporter(self, self.max_workers)
        return parallel_exporter.export_tables_parallel(tables, progress_callback)

    def export_profile_scoped(
        self,
        profile_id: int = None,
        profile_name: str = None,
        include_papers: bool = True,
        include_fulltext: bool = True,
        include_topics: bool = False,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Export a single profile with all related data.

        Args:
            profile_id: Profile ID to export (mutually exclusive with profile_name)
            profile_name: Profile name to export (mutually exclusive with profile_id)
            include_papers: Include papers scored by this profile
            include_fulltext: Include paper fulltext content
            include_topics: Include topic relationships
            progress_callback: Optional progress callback

        Returns:
            Export results with profile mapping metadata
        """
        if not profile_id and not profile_name:
            raise ValueError("Either profile_id or profile_name must be provided")

        if profile_id and profile_name:
            raise ValueError("Provide either profile_id or profile_name, not both")

        print(f"Starting profile-scoped export for profile: {profile_id or profile_name}")

        # Get profile data
        with get_cursor() as cursor:
            if profile_id:
                cursor.execute("""
                    SELECT id, name, description, color, tags, email_recipients,
                           arxiv_filters, is_active, is_default, created_at, updated_at
                    FROM research_profiles WHERE id = %s
                """, (profile_id,))
            else:
                cursor.execute("""
                    SELECT id, name, description, color, tags, email_recipients,
                           arxiv_filters, is_active, is_default, created_at, updated_at
                    FROM research_profiles WHERE name = %s
                """, (profile_name,))

            profile_row = cursor.fetchone()
            if not profile_row:
                raise ValueError(f"Profile not found: {profile_id or profile_name}")

            # Use the actual profile ID from the database
            actual_profile_id = profile_row['id']

            # Parse JSON fields
            def safe_json_parse(json_data):
                if json_data:
                    try:
                        return json.loads(json_data) if isinstance(json_data, str) else json_data
                    except:
                        return json_data
                return None

            profile_data = {
                'id': profile_row['id'],
                'name': profile_row['name'],
                'description': profile_row['description'],
                'color': profile_row['color'],
                'tags': safe_json_parse(profile_row['tags']) or [],
                'email_recipients': safe_json_parse(profile_row['email_recipients']) or [],
                'arxiv_filters': safe_json_parse(profile_row['arxiv_filters']) or {},
                'is_active': bool(profile_row['is_active']) if profile_row['is_active'] is not None else True,
                'is_default': bool(profile_row['is_default']) if profile_row['is_default'] is not None else False,
                'created_at': profile_row['created_at'].isoformat() if profile_row['created_at'] else None,
                'updated_at': profile_row['updated_at'].isoformat() if profile_row['updated_at'] else None
            }

        # Save profile data
        output_file = self.output_dir / "research_profiles.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([profile_data], f, indent=2, ensure_ascii=False)

        result = {
            "files": {
                "research_profiles": str(output_file)
            },
            "profile_mapping": {
                "source_profile_id": actual_profile_id,
                "source_profile_name": profile_data['name'],
                "source_profile_color": profile_data['color']
            },
            "tables_included": ["research_profiles"]
        }

        # Export profile research interests
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, profile_id, interest_text, embedding, embedding_model, created_at, updated_at
                FROM profile_research_interests WHERE profile_id = %s
            """, (actual_profile_id,))
            interests_rows = cursor.fetchall()

            interests = []
            for row in interests_rows:
                # Handle embedding conversion
                embedding = None
                if row['embedding']:
                    try:
                        if isinstance(row['embedding'], str):
                            embedding = json.loads(row['embedding'])
                        elif hasattr(row['embedding'], 'tolist'):
                            embedding = row['embedding'].tolist()
                        elif isinstance(row['embedding'], (list, tuple)):
                            embedding = list(row['embedding'])
                    except Exception as e:
                        logger.warning(f"Could not convert embedding for profile interest {row['id']}: {e}")
                        embedding = None

                interests.append({
                    'id': row['id'],
                    'profile_id': row['profile_id'],
                    'interest_text': row['interest_text'],
                    'embedding': embedding,
                    'embedding_model': row['embedding_model'],
                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                })

        interests_file = self.output_dir / "profile_research_interests.json"
        with open(interests_file, 'w', encoding='utf-8') as f:
            json.dump(interests, f, indent=2, ensure_ascii=False)

        result["files"]["profile_research_interests"] = str(interests_file)
        result["tables_included"].append("profile_research_interests")

        # Get paper IDs scored by this profile
        if include_papers:
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT paper_id FROM paper_profile_scores WHERE profile_id = %s
                """, (actual_profile_id,))
                paper_ids = [row['paper_id'] for row in cursor.fetchall()]

            result["profile_mapping"]["papers_exported"] = len(paper_ids)
            result["profile_mapping"]["export_includes_all_papers"] = False
            result["profile_mapping"]["paper_selection_criteria"] = "all papers scored by this profile"

            if paper_ids:
                # Export papers scored by this profile using streaming
                paper_ids_str = ','.join(str(pid) for pid in paper_ids)

                # Build papers query
                with get_cursor() as cursor:
                    cursor.execute("""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = 'papers' AND table_schema = 'public'
                    """)
                    existing_columns = {row['column_name'] for row in cursor.fetchall()}

                columns = ['id', 'title', 'abstract', 'date', 'date_run', 'score', 'rationale',
                          'related', 'cosine_similarity', 'url', 'embedding_model', 'embedding']

                if 'text' in existing_columns:
                    columns.append('text')
                if 'summary' in existing_columns:
                    columns.append('summary')
                if 'keywords_json' in existing_columns:
                    columns.append('keywords_json')
                if 'fulltext_extraction_status' in existing_columns:
                    columns.append('fulltext_extraction_status')
                if 'downloaded_pdf_path' in existing_columns:
                    columns.append('downloaded_pdf_path')

                column_str = ', '.join(columns)
                query = f"SELECT {column_str} FROM papers WHERE id IN ({paper_ids_str}) ORDER BY id DESC"

                # Use streaming export for papers
                if self.streaming:
                    papers_stats = self.export_table_streaming(
                        "papers",
                        query,
                        "papers.json",
                        progress_callback=progress_callback
                    )
                    result["files"]["papers"] = str(self.output_dir / "papers.json")
                else:
                    # Non-streaming fallback
                    with get_cursor() as cursor:
                        cursor.execute(query)
                        rows = cursor.fetchall()

                        papers = []
                        for row in rows:
                            # Convert special types
                            converted_row = self._convert_special_types(row)
                            papers.append(converted_row)

                    papers_file = self.output_dir / "papers.json"
                    with open(papers_file, 'w', encoding='utf-8') as f:
                        json.dump(papers, f, indent=2, ensure_ascii=False)

                    result["files"]["papers"] = str(papers_file)

                result["tables_included"].append("papers")

                # Export paper_profile_scores for this profile
                with get_cursor() as cursor:
                    cursor.execute("""
                        SELECT id, paper_id, profile_id, score, related, rationale,
                               date_scored, judge_model
                        FROM paper_profile_scores
                        WHERE profile_id = %s AND paper_id IN ({})
                    """.format(paper_ids_str), (actual_profile_id,))
                    scores_rows = cursor.fetchall()

                    scores = []
                    for row in scores_rows:
                        scores.append({
                            'id': row['id'],
                            'paper_id': row['paper_id'],
                            'profile_id': row['profile_id'],
                            'score': row['score'],
                            'related': bool(row['related']) if row['related'] is not None else None,
                            'rationale': row['rationale'],
                            'date_scored': row['date_scored'].isoformat() if row['date_scored'] else None,
                            'judge_model': row['judge_model']
                        })

                scores_file = self.output_dir / "paper_profile_scores.json"
                with open(scores_file, 'w', encoding='utf-8') as f:
                    json.dump(scores, f, indent=2, ensure_ascii=False)

                result["files"]["paper_profile_scores"] = str(scores_file)
                result["tables_included"].append("paper_profile_scores")

                # Export paper fulltext if requested
                if include_fulltext and paper_ids:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT id, paper_id, content, embedding, embedding_model, created_at, extraction_method, metadata
                            FROM paper_fulltext
                            WHERE paper_id IN ({})
                        """.format(paper_ids_str))
                        fulltext_rows = cursor.fetchall()

                        fulltext_data = []
                        for row in fulltext_rows:
                            # Handle embedding conversion
                            embedding = None
                            if row['embedding']:
                                try:
                                    if isinstance(row['embedding'], str):
                                        embedding = json.loads(row['embedding'])
                                    elif hasattr(row['embedding'], 'tolist'):
                                        embedding = row['embedding'].tolist()
                                    elif isinstance(row['embedding'], (list, tuple)):
                                        embedding = list(row['embedding'])
                                except Exception as e:
                                    logger.warning(f"Could not convert embedding for paper_id {row['paper_id']}: {e}")
                                    embedding = None

                            # Handle metadata JSON
                            metadata = None
                            if row['metadata']:
                                try:
                                    metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
                                except:
                                    metadata = row['metadata']

                            fulltext_data.append({
                                'id': row['id'],
                                'paper_id': row['paper_id'],
                                'content': row['content'],
                                'embedding': embedding,
                                'embedding_model': row['embedding_model'],
                                'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                                'extraction_method': row['extraction_method'],
                                'metadata': metadata
                            })

                    fulltext_file = self.output_dir / "paper_fulltext.json"
                    with open(fulltext_file, 'w', encoding='utf-8') as f:
                        json.dump(fulltext_data, f, indent=2, ensure_ascii=False)

                    result["files"]["paper_fulltext"] = str(fulltext_file)
                    result["tables_included"].append("paper_fulltext")

                # Export topics if requested
                if include_topics and paper_ids:
                    with get_cursor() as cursor:
                        cursor.execute("""
                            SELECT id, paper_id, topic_id, relevance_score, created_at
                            FROM paper_topics
                            WHERE paper_id IN ({})
                        """.format(paper_ids_str))
                        paper_topics_rows = cursor.fetchall()

                        paper_topics = []
                        for row in paper_topics_rows:
                            paper_topics.append({
                                'id': row['id'],
                                'paper_id': row['paper_id'],
                                'topic_id': row['topic_id'],
                                'relevance_score': row['relevance_score'],
                                'created_at': row['created_at'].isoformat() if row['created_at'] else None
                            })

                    paper_topics_file = self.output_dir / "paper_topics.json"
                    with open(paper_topics_file, 'w', encoding='utf-8') as f:
                        json.dump(paper_topics, f, indent=2, ensure_ascii=False)

                    result["files"]["paper_topics"] = str(paper_topics_file)
                    result["tables_included"].append("paper_topics")

                    # Also export the topics themselves
                    topic_ids = list(set(pt['topic_id'] for pt in paper_topics))
                    if topic_ids:
                        topic_ids_str = ','.join(str(tid) for tid in topic_ids)

                        with get_cursor() as cursor:
                            cursor.execute("""
                                SELECT id, label, keywords, centroid_embedding, embedding_model, created_at, updated_at
                                FROM topics
                                WHERE id IN ({})
                            """.format(topic_ids_str))
                            topics_rows = cursor.fetchall()

                            topics = []
                            for row in topics_rows:
                                # Handle embedding conversion
                                embedding = None
                                if row['centroid_embedding']:
                                    try:
                                        if isinstance(row['centroid_embedding'], str):
                                            embedding = json.loads(row['centroid_embedding'])
                                        elif hasattr(row['centroid_embedding'], 'tolist'):
                                            embedding = row['centroid_embedding'].tolist()
                                        elif isinstance(row['centroid_embedding'], (list, tuple)):
                                            embedding = list(row['centroid_embedding'])
                                    except Exception as e:
                                        logger.warning(f"Could not convert embedding for topic {row['id']}: {e}")
                                        embedding = None

                                topics.append({
                                    'id': row['id'],
                                    'label': row['label'],
                                    'keywords': list(row['keywords']) if row['keywords'] else [],
                                    'centroid_embedding': embedding,
                                    'embedding_model': row['embedding_model'],
                                    'created_at': row['created_at'].isoformat() if row['created_at'] else None,
                                    'updated_at': row['updated_at'].isoformat() if row['updated_at'] else None
                                })

                        topics_file = self.output_dir / "topics.json"
                        with open(topics_file, 'w', encoding='utf-8') as f:
                            json.dump(topics, f, indent=2, ensure_ascii=False)

                        result["files"]["topics"] = str(topics_file)
                        result["tables_included"].append("topics")

        # Create v6.0 metadata
        metadata = {
            "export_version": "6.0",
            "export_type": "profile_scoped",
            "export_timestamp": datetime.datetime.now().isoformat(),
            "source_database": {
                "schema_version": "5.2"
            },
            "profile_mapping": result["profile_mapping"],
            "tables_included": result["tables_included"],
            "table_statistics": {
                table: 1 if table == "research_profiles" else len(json.load(open(result["files"][table])))
                for table in result["tables_included"]
                if table in result["files"]
            },
            "import_hints": {
                "profile_mapping_required": True,
                "suggested_mapping_strategy": "auto",
                "duplicate_handling": "skip_by_url"
            },
            "backward_compatible": True
        }

        metadata_file = self.output_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        result["files"]["metadata"] = str(metadata_file)
        result["export_type"] = "profile_scoped"
        result["output_directory"] = str(self.output_dir)

        print(f"Profile-scoped export completed: {len(result['tables_included'])} tables exported")
        return result
    
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
        # Handle incremental export mode
        if self.incremental:
            print("Starting incremental database export...")
            return self.export_incremental()
        
        print("Starting full database export...")
        if progress_callback:
            print("[DEBUG] Calling progress callback with 0% - starting")
            progress_callback(0, "starting")
        else:
            print("[DEBUG] No progress callback provided")

        # Export core tables (backwards compatible)
        # Create a sub-callback for papers export that maps to the overall progress (0-15%)
        def papers_progress_cb(current: int, total: int, message: str):
            if progress_callback and total > 0:
                # Map papers export progress (0-100%) to overall progress (0-15%)
                papers_pct = (current / total) * 100 if total > 0 else 0
                overall_pct = (papers_pct / 100) * 15  # Maps to 0-15% of overall progress
                progress_callback(overall_pct, f"Papers: {message}")
        
        papers_file = self.export_papers(progress_callback=papers_progress_cb)
        if progress_callback:
            print("[DEBUG] Calling progress callback with 15% - papers_exported")
            progress_callback(15, "papers_exported")
        podcasts_file = self.export_podcasts()
        if progress_callback:
            print("[DEBUG] Calling progress callback with 25% - podcasts_exported")
            progress_callback(25, "podcasts_exported")
        newsletters_file = self.export_newsletters()
        if progress_callback:
            print("[DEBUG] Calling progress callback with 35% - newsletters_exported")
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
            # Export profile-related tables first
            try:
                research_profiles_file = self.export_research_profiles()
                if progress_callback:
                    progress_callback(50, "research_profiles_exported")
                result["files"]["research_profiles"] = research_profiles_file
            except Exception as e:
                print(f"Warning: Could not export research profiles: {e}")
            
            try:
                profile_research_interests_file = self.export_profile_research_interests()
                if progress_callback:
                    progress_callback(52, "profile_research_interests_exported")
                result["files"]["profile_research_interests"] = profile_research_interests_file
            except Exception as e:
                print(f"Warning: Could not export profile research interests: {e}")
            
            try:
                paper_profile_scores_file = self.export_paper_profile_scores()
                if progress_callback:
                    progress_callback(54, "paper_profile_scores_exported")
                result["files"]["paper_profile_scores"] = paper_profile_scores_file
            except Exception as e:
                print(f"Warning: Could not export paper profile scores: {e}")
            
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
            
            try:
                topics_file = self.export_topics()
                if progress_callback:
                    progress_callback(91, "topics_exported")
                result["files"]["topics"] = topics_file
            except Exception as e:
                print(f"Warning: Could not export topics: {e}")
            
            try:
                topic_metrics_file = self.export_topic_metrics()
                if progress_callback:
                    progress_callback(92, "topic_metrics_exported")
                result["files"]["topic_metrics"] = topic_metrics_file
            except Exception as e:
                print(f"Warning: Could not export topic metrics: {e}")
            
            try:
                paper_topics_file = self.export_paper_topics()
                if progress_callback:
                    progress_callback(93, "paper_topics_exported")
                result["files"]["paper_topics"] = paper_topics_file
            except Exception as e:
                print(f"Warning: Could not export paper topics: {e}")
            
            try:
                research_interests_file = self.export_research_interests()
                if progress_callback:
                    progress_callback(94, "research_interests_exported")
                result["files"]["research_interests"] = research_interests_file
            except Exception as e:
                print(f"Warning: Could not export research interests: {e}")
            
            try:
                research_interest_metrics_file = self.export_research_interest_metrics()
                if progress_callback:
                    progress_callback(95, "research_interest_metrics_exported")
                result["files"]["research_interest_metrics"] = research_interest_metrics_file
            except Exception as e:
                print(f"Warning: Could not export research interest metrics: {e}")
            
            try:
                paper_research_interests_file = self.export_paper_research_interests()
                if progress_callback:
                    progress_callback(96, "paper_research_interests_exported")
                result["files"]["paper_research_interests"] = paper_research_interests_file
            except Exception as e:
                print(f"Warning: Could not export paper research interests: {e}")
            
            try:
                label_summaries_file = self.export_label_summaries()
                if progress_callback:
                    progress_callback(97, "label_summaries_exported")
                result["files"]["label_summaries"] = label_summaries_file
            except Exception as e:
                print(f"Warning: Could not export label summaries: {e}")
            
            try:
                scheduled_tasks_file = self.export_scheduled_tasks()
                if progress_callback:
                    progress_callback(98, "scheduled_tasks_exported")
                result["files"]["scheduled_tasks"] = scheduled_tasks_file
            except Exception as e:
                print(f"Warning: Could not export scheduled tasks: {e}")
            
            try:
                scheduled_task_runs_file = self.export_scheduled_task_runs()
                if progress_callback:
                    progress_callback(99, "scheduled_task_runs_exported")
                result["files"]["scheduled_task_runs"] = scheduled_task_runs_file
            except Exception as e:
                print(f"Warning: Could not export scheduled task runs: {e}")
        
        metadata_file = self.create_metadata()
        if progress_callback:
            progress_callback(98, "metadata_created")
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
    parser.add_argument("--streaming", action="store_true", help="Use streaming mode for large datasets")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for streaming mode")
    parser.add_argument("--parallel", action="store_true", help="Use parallel processing")
    parser.add_argument("--max-workers", type=int, default=4, help="Maximum parallel workers")
    parser.add_argument("--incremental", action="store_true", help="Perform incremental export")
    parser.add_argument("--since", help="For incremental exports, export changes since this timestamp (ISO format)")
    parser.add_argument("--tables", nargs="+", help="Specific tables to export incrementally")
    
    args = parser.parse_args()
    
    # Parse since timestamp if provided
    since_timestamp = None
    if args.since:
        try:
            since_timestamp = datetime.datetime.fromisoformat(args.since)
        except ValueError:
            print(f"Error: Invalid timestamp format: {args.since}")
            print("Use ISO format like: 2024-01-01T10:00:00 or 2024-01-01T10:00:00+00:00")
            return 1
    
    try:
        exporter = DatabaseExporter(
            args.db_path, 
            args.output_dir,
            batch_size=args.batch_size,
            streaming=args.streaming,
            parallel=args.parallel,
            max_workers=args.max_workers,
            incremental=args.incremental,
            since_timestamp=since_timestamp
        )
        
        if args.incremental:
            print(f"Performing incremental export...")
            if args.since:
                print(f"Exporting changes since: {since_timestamp}")
            else:
                print("Auto-detecting last export timestamp...")
            
            result = exporter.export_incremental(
                tables=args.tables,
                since_timestamp=since_timestamp
            )
        else:
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