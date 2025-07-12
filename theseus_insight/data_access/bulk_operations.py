"""Bulk operations module for high-performance data imports using staging tables."""

from __future__ import annotations

import uuid
import csv
import io
from typing import List, Dict, Any, Optional, Tuple, Iterator
from datetime import datetime
import logging
import json

from psycopg import sql

from ..db import get_cursor, get_connection
from ..data_model.papers import Paper
from .base import to_pgvector

logger = logging.getLogger(__name__)


class BulkImporter:
    """Handles bulk import operations using PostgreSQL COPY and staging tables."""
    
    def __init__(self, batch_id: Optional[str] = None):
        """Initialize bulk importer with optional batch ID."""
        self.batch_id = batch_id or str(uuid.uuid4())
        self.papers_buffer = []
        self.embeddings_buffer = []
        self.keywords_buffer = []
        self.scores_buffer = []
        
    def add_paper(self, paper: Paper) -> None:
        """Add a paper to the import buffer."""
        self.papers_buffer.append(paper)
        
    def add_papers(self, papers: List[Paper]) -> None:
        """Add multiple papers to the import buffer."""
        self.papers_buffer.extend(papers)
        
    def add_embedding(self, paper_id: int, embedding: List[float], model: str) -> None:
        """Add an embedding update to the buffer."""
        self.embeddings_buffer.append({
            'paper_id': paper_id,
            'embedding': embedding,
            'model': model
        })
        
    def add_keywords(self, paper_id: int, keywords: List[str]) -> None:
        """Add keywords update to the buffer."""
        self.keywords_buffer.append({
            'paper_id': paper_id,
            'keywords': keywords
        })
        
    def add_profile_score(self, paper_id: int, profile_id: int, score: int, 
                         related: bool, rationale: str, judge_model: str) -> None:
        """Add a profile score to the buffer."""
        self.scores_buffer.append({
            'paper_id': paper_id,
            'profile_id': profile_id,
            'score': score,
            'related': related,
            'rationale': rationale,
            'judge_model': judge_model
        })
        
    def copy_papers_to_staging(self) -> int:
        """
        Copy papers from buffer to staging table using COPY.
        
        Returns:
            Number of papers copied
        """
        if not self.papers_buffer:
            return 0
            
        logger.info(f"Copying {len(self.papers_buffer)} papers to staging table (batch {self.batch_id})")
        
        # Prepare CSV data in memory
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        
        for paper in self.papers_buffer:
            # Convert embedding to PostgreSQL array format if present
            embedding_str = None
            if hasattr(paper, 'embedding') and paper.embedding:
                if isinstance(paper.embedding, list):
                    embedding_str = '[' + ','.join(str(x) for x in paper.embedding) + ']'
                else:
                    # Assume it's already in the right format
                    embedding_str = str(paper.embedding)
            
            # Convert keywords to JSON
            keywords_json = None
            if hasattr(paper, 'keywords') and paper.keywords:
                keywords_json = json.dumps(paper.keywords)
            
            # Write row (order must match table columns)
            writer.writerow([
                paper.title,
                paper.abstract,
                paper.date,
                paper.date_run,
                paper.score if hasattr(paper, 'score') else None,
                paper.rationale if hasattr(paper, 'rationale') else None,
                paper.related if hasattr(paper, 'related') else None,
                paper.cosine_similarity if hasattr(paper, 'cosine_similarity') else None,
                paper.url,
                paper.embedding_model if hasattr(paper, 'embedding_model') else None,
                embedding_str,
                keywords_json,
                paper.fulltext_extraction_status if hasattr(paper, 'fulltext_extraction_status') else None,
                paper.downloaded_pdf_path if hasattr(paper, 'downloaded_pdf_path') else None,
                self.batch_id,
                datetime.now().isoformat()
            ])
        
        # Get CSV content
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()
        
        # Copy to staging table
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Use COPY FROM STDIN
                with cur.copy(
                    """COPY papers_staging (
                        title, abstract, date, date_run, score, rationale, related, 
                        cosine_similarity, url, embedding_model, embedding, keywords_json,
                        fulltext_extraction_status, downloaded_pdf_path, 
                        staging_batch_id, staging_timestamp
                    ) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', QUOTE '"', NULL '\\N')"""
                ) as copy:
                    copy.write(csv_content.encode('utf-8'))
        
        papers_count = len(self.papers_buffer)
        self.papers_buffer.clear()
        logger.info(f"Successfully copied {papers_count} papers to staging")
        return papers_count
        
    def copy_embeddings_to_staging(self) -> int:
        """
        Copy embeddings from buffer to staging table using COPY.
        
        Returns:
            Number of embeddings copied
        """
        if not self.embeddings_buffer:
            return 0
            
        logger.info(f"Copying {len(self.embeddings_buffer)} embeddings to staging table")
        
        # Prepare CSV data
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        
        for item in self.embeddings_buffer:
            embedding_str = '[' + ','.join(str(x) for x in item['embedding']) + ']'
            writer.writerow([
                item['paper_id'],
                embedding_str,
                item['model'],
                self.batch_id,
                datetime.now().isoformat()
            ])
        
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()
        
        # Copy to staging table
        with get_connection() as conn:
            with conn.cursor() as cur:
                with cur.copy(
                    """COPY embeddings_staging (
                        paper_id, embedding, embedding_model, 
                        staging_batch_id, staging_timestamp
                    ) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t')"""
                ) as copy:
                    copy.write(csv_content.encode('utf-8'))
        
        count = len(self.embeddings_buffer)
        self.embeddings_buffer.clear()
        return count
        
    def copy_keywords_to_staging(self) -> int:
        """
        Copy keywords from buffer to staging table using COPY.
        
        Returns:
            Number of keyword sets copied
        """
        if not self.keywords_buffer:
            return 0
            
        logger.info(f"Copying {len(self.keywords_buffer)} keyword sets to staging table")
        
        # Prepare CSV data
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        
        for item in self.keywords_buffer:
            keywords_json = json.dumps(item['keywords'])
            writer.writerow([
                item['paper_id'],
                keywords_json,
                self.batch_id,
                datetime.now().isoformat()
            ])
        
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()
        
        # Copy to staging table
        with get_connection() as conn:
            with conn.cursor() as cur:
                with cur.copy(
                    """COPY keywords_staging (
                        paper_id, keywords_json,
                        staging_batch_id, staging_timestamp
                    ) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t')"""
                ) as copy:
                    copy.write(csv_content.encode('utf-8'))
        
        count = len(self.keywords_buffer)
        self.keywords_buffer.clear()
        return count
        
    def copy_scores_to_staging(self) -> int:
        """
        Copy profile scores from buffer to staging table using COPY.
        
        Returns:
            Number of scores copied
        """
        if not self.scores_buffer:
            return 0
            
        logger.info(f"Copying {len(self.scores_buffer)} scores to staging table")
        
        # Prepare CSV data
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
        
        for item in self.scores_buffer:
            writer.writerow([
                item['paper_id'],
                item['profile_id'],
                item['score'],
                'true' if item['related'] else 'false',
                item['rationale'],
                item['judge_model'],
                datetime.now().isoformat(),
                self.batch_id,
                datetime.now().isoformat()
            ])
        
        csv_content = csv_buffer.getvalue()
        csv_buffer.close()
        
        # Copy to staging table
        with get_connection() as conn:
            with conn.cursor() as cur:
                with cur.copy(
                    """COPY paper_profile_scores_staging (
                        paper_id, profile_id, score, related, rationale,
                        judge_model, date_scored,
                        staging_batch_id, staging_timestamp
                    ) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t')"""
                ) as copy:
                    copy.write(csv_content.encode('utf-8'))
        
        count = len(self.scores_buffer)
        self.scores_buffer.clear()
        return count
        
    def deduplicate_staging(self) -> Tuple[int, int]:
        """
        Remove duplicates from staging tables.
        
        Returns:
            Tuple of (duplicate_count, new_count)
        """
        logger.info(f"Deduplicating staging data for batch {self.batch_id}")
        
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM deduplicate_staging_papers(%s)",
                (self.batch_id,)
            )
            result = cur.fetchone()
            
        duplicate_count = result['duplicate_count']
        new_count = result['new_count']
        
        logger.info(f"Deduplication complete: {duplicate_count} duplicates removed, {new_count} new papers")
        return duplicate_count, new_count
        
    def merge_to_main_tables(self) -> Dict[str, int]:
        """
        Merge staging data into main tables.
        
        Returns:
            Dictionary with counts of inserted/updated records
        """
        logger.info(f"Merging staging data to main tables for batch {self.batch_id}")
        
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM merge_staging_to_main(%s)",
                (self.batch_id,)
            )
            result = cur.fetchone()
            
        stats = {
            'papers_inserted': result['papers_inserted'],
            'embeddings_updated': result['embeddings_updated'],
            'keywords_updated': result['keywords_updated'],
            'scores_inserted': result['scores_inserted']
        }
        
        logger.info(f"Merge complete: {stats}")
        return stats
        
    def import_papers(self, papers: List[Paper], 
                     deduplicate: bool = True,
                     merge: bool = True) -> Dict[str, Any]:
        """
        High-level method to import papers using staging tables.
        
        Args:
            papers: List of Paper objects to import
            deduplicate: Whether to remove duplicates
            merge: Whether to merge to main tables
            
        Returns:
            Dictionary with import statistics
        """
        stats = {
            'papers_staged': 0,
            'duplicates_removed': 0,
            'new_papers': 0,
            'papers_inserted': 0,
            'batch_id': self.batch_id
        }
        
        # Add papers to buffer and copy to staging
        self.add_papers(papers)
        stats['papers_staged'] = self.copy_papers_to_staging()
        
        # Deduplicate if requested
        if deduplicate:
            dup_count, new_count = self.deduplicate_staging()
            stats['duplicates_removed'] = dup_count
            stats['new_papers'] = new_count
        
        # Merge to main tables if requested
        if merge:
            merge_stats = self.merge_to_main_tables()
            stats.update(merge_stats)
            
        return stats


class BulkExporter:
    """Handles bulk export operations using PostgreSQL COPY TO."""
    
    @staticmethod
    def export_papers_to_csv(output_file: str,
                           start_date: Optional[str] = None,
                           end_date: Optional[str] = None) -> int:
        """
        Export papers to CSV file using COPY TO.
        
        Args:
            output_file: Path to output CSV file
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Number of papers exported
        """
        conditions = []
        params = []
        
        if start_date:
            conditions.append("date >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("date <= %s")
            params.append(end_date)
            
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Get count first
                cur.execute(f"SELECT COUNT(*) FROM papers {where_clause}", params)
                count = cur.fetchone()[0]
                
                # Export to file
                with open(output_file, 'w') as f:
                    with cur.copy(
                        f"""COPY (
                            SELECT id, title, abstract, date, url, score, related
                            FROM papers {where_clause}
                            ORDER BY date DESC
                        ) TO STDOUT WITH (FORMAT CSV, HEADER)"""
                    ) as copy:
                        for data in copy:
                            f.write(data.decode('utf-8'))
                            
        logger.info(f"Exported {count} papers to {output_file}")
        return count