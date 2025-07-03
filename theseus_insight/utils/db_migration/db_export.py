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

from ...data_access import (
    PaperRepository, NewsletterRepository, PodcastRepository, 
    LitReviewRepository, ResearchRunRepository, ResearchAgentStateRepository,
    PaperFulltextRepository, MindmapReportRepository, ModelCatalogRepository
)
from ...db import get_cursor


class DatabaseExporter:
    """Handles exporting database contents to JSON files."""
    
    def __init__(self, db_path: str, output_dir: str):
        """
        Initialize the exporter.
        
        Args:
            db_path: Database connection string (PostgreSQL URL)
            output_dir: Directory to save exported files
        """
        # Store the db_path for reference (repositories handle their own connections)
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def export_papers(self) -> str:
        """Export all papers to JSON file."""
        print("Exporting papers...")
        
        # Get all papers using direct SQL to ensure we get all fields including PostgreSQL-specific ones
        papers = []
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT id, title, abstract, date, date_run, score, rationale, related, 
                       cosine_similarity, url, embedding_model, embedding, text, keywords
                FROM papers ORDER BY id DESC
            """)
            rows = cursor.fetchall()

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
                if row['keywords']:
                    try:
                        if isinstance(row['keywords'], str):
                            keywords = json.loads(row['keywords'])
                        elif isinstance(row['keywords'], (list, tuple)):
                            keywords = list(row['keywords'])
                    except Exception:
                        keywords = []

                papers.append({
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
                    'summary': row.get('text'),  # Map 'text' field to 'summary' for backwards compatibility
                    'keywords': keywords,
                })
        
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
    
    def export_research_interests(self) -> str:
        """Export all research interests to JSON file."""
        print("Exporting research interests...")
        
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
    
    def create_metadata(self) -> str:
        """Create metadata file with export information."""
        metadata = {
            "export_timestamp": datetime.datetime.now().isoformat(),
            "export_version": "3.0",  # Incremented version for trends and research interest tables
            "tables_exported": [
                "papers", "podcasts", "newsletters", "literature_reviews",
                "research_runs", "research_agent_state", "paper_fulltext", 
                "mindmap_reports", "model_catalog", "topics", "topic_metrics",
                "paper_topics", "research_interests", "research_interest_metrics",
                "paper_research_interests", "label_summaries"
            ],
            "description": "Theseus Insight database export with Trends, Research Interests, and full feature set",
            "backwards_compatible": True,
            "new_features": [
                "research_runs", "research_agent_state", "paper_fulltext",
                "mindmap_reports", "model_catalog", "topics", "topic_metrics",
                "paper_topics", "research_interests", "research_interest_metrics",
                "paper_research_interests", "label_summaries"
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