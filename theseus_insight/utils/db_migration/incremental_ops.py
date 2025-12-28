#!/usr/bin/env python3
"""
Incremental Export/Import Operations

This module provides incremental export and import capabilities for the
Theseus Insight database migration system, allowing for efficient delta
operations based on timestamps and change tracking.
"""

import json
import logging
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ChangeTrackingInfo:
    """Information about change tracking for a table."""
    table_name: str
    timestamp_column: str
    primary_key_columns: List[str]
    supports_soft_delete: bool = False
    soft_delete_column: str = None
    last_export_timestamp: Optional[datetime] = None


@dataclass
class IncrementalMetadata:
    """Metadata for incremental exports."""
    export_type: str  # 'full' or 'incremental'
    base_export_timestamp: Optional[datetime]
    since_timestamp: Optional[datetime]
    until_timestamp: datetime
    tables_included: List[str]
    change_summary: Dict[str, Dict[str, int]]  # table -> {inserted, updated, deleted}
    parent_export_id: Optional[str] = None
    export_id: str = None
    
    def __post_init__(self):
        if self.export_id is None:
            # Generate unique export ID
            timestamp_str = self.until_timestamp.isoformat()
            export_data = f"{self.export_type}_{timestamp_str}_{','.join(sorted(self.tables_included))}"
            self.export_id = hashlib.md5(export_data.encode()).hexdigest()[:12]


class IncrementalExporter:
    """Handles incremental database exports."""
    
    def __init__(self, db_path: str, output_dir: str):
        """
        Initialize the incremental exporter.
        
        Args:
            db_path: Database connection string
            output_dir: Directory to save exported files
        """
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Define table change tracking configuration
        self.table_configs = {
            'papers': ChangeTrackingInfo(
                table_name='papers',
                timestamp_column='date_run',
                primary_key_columns=['id']
            ),
            'research_runs': ChangeTrackingInfo(
                table_name='research_runs',
                timestamp_column='created_at',
                primary_key_columns=['id']
            ),
            'mindmap_reports': ChangeTrackingInfo(
                table_name='mindmap_reports',
                timestamp_column='created_at',
                primary_key_columns=['id']
            ),
            'research_agent_state': ChangeTrackingInfo(
                table_name='research_agent_state',
                timestamp_column='updated_at',
                primary_key_columns=['id']
            ),
            'paper_fulltext': ChangeTrackingInfo(
                table_name='paper_fulltext',
                timestamp_column='created_at',
                primary_key_columns=['paper_id']
            ),
            'topics': ChangeTrackingInfo(
                table_name='topics',
                timestamp_column='updated_at',
                primary_key_columns=['id']
            ),
            'research_profiles': ChangeTrackingInfo(
                table_name='research_profiles',
                timestamp_column='updated_at',
                primary_key_columns=['id']
            ),
            # Tables without good timestamp columns (use creation order)
            'podcasts': ChangeTrackingInfo(
                table_name='podcasts',
                timestamp_column='id',  # Use ID as proxy for creation order
                primary_key_columns=['id']
            ),
            'newsletters': ChangeTrackingInfo(
                table_name='newsletters',
                timestamp_column='id',  # Use ID as proxy for creation order
                primary_key_columns=['id']
            )
        }
    
    def get_last_export_timestamp(self, table_name: str) -> Optional[datetime]:
        """
        Get the timestamp of the last incremental export for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            Last export timestamp or None if no previous export
        """
        metadata_file = self.output_dir / "incremental_metadata.json"
        if not metadata_file.exists():
            return None
        
        try:
            with open(metadata_file, 'r') as f:
                all_metadata = json.load(f)
            
            # Find the most recent incremental export that included this table
            latest_timestamp = None
            for export_data in all_metadata.get('exports', []):
                if table_name in export_data.get('tables_included', []):
                    export_timestamp = datetime.fromisoformat(export_data['until_timestamp'])
                    if latest_timestamp is None or export_timestamp > latest_timestamp:
                        latest_timestamp = export_timestamp
            
            return latest_timestamp
            
        except Exception as e:
            logger.warning(f"Could not read incremental metadata: {e}")
            return None
    
    def save_incremental_metadata(self, metadata: IncrementalMetadata):
        """
        Save incremental export metadata.
        
        Args:
            metadata: Incremental metadata to save
        """
        metadata_file = self.output_dir / "incremental_metadata.json"
        
        # Load existing metadata
        all_metadata = {"exports": []}
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    all_metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Could not read existing metadata: {e}")
        
        # Add new export metadata
        export_data = asdict(metadata)
        # Convert datetime objects to ISO strings
        for key, value in export_data.items():
            if isinstance(value, datetime):
                export_data[key] = value.isoformat()
        
        all_metadata['exports'].append(export_data)
        
        # Keep only last 50 exports to prevent file from growing too large
        all_metadata['exports'] = all_metadata['exports'][-50:]
        
        # Save updated metadata
        with open(metadata_file, 'w') as f:
            json.dump(all_metadata, f, indent=2, default=str)
        
        logger.info(f"Saved incremental metadata for export {metadata.export_id}")
    
    def export_table_incremental(self, table_name: str, since_timestamp: datetime, 
                                until_timestamp: datetime = None) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Export incremental changes for a table.
        
        Args:
            table_name: Name of the table to export
            since_timestamp: Export changes since this timestamp
            until_timestamp: Export changes until this timestamp (default: now)
            
        Returns:
            Tuple of (records, change_summary)
        """
        if until_timestamp is None:
            until_timestamp = datetime.now(timezone.utc)
        
        config = self.table_configs.get(table_name)
        if not config:
            logger.warning(f"No incremental config for table {table_name}, skipping")
            return [], {"inserted": 0, "updated": 0, "deleted": 0}
        
        from ...db import get_cursor
        
        records = []
        change_summary = {"inserted": 0, "updated": 0, "deleted": 0}
        
        with get_cursor() as cursor:
            # Build incremental query based on timestamp column
            timestamp_col = config.timestamp_column
            
            # For ID-based tables (no real timestamp), we approximate with ID ranges
            if timestamp_col == 'id':
                # Get the approximate ID range based on previous exports
                last_id = self._get_last_exported_id(table_name, since_timestamp)
                query = f"""
                    SELECT * FROM {table_name} 
                    WHERE id > %s
                    ORDER BY id
                """
                params = (last_id,)
            else:
                # Use proper timestamp filtering
                query = f"""
                    SELECT * FROM {table_name} 
                    WHERE {timestamp_col} > %s AND {timestamp_col} <= %s
                    ORDER BY {timestamp_col}
                """
                params = (since_timestamp, until_timestamp)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # Convert rows to dictionaries and track changes
            for row in rows:
                record = dict(row)
                
                # Handle special data types (dates, embeddings, etc.)
                record = self._process_record_for_export(record, table_name)
                
                # Add metadata for change tracking
                record['_incremental_action'] = 'upsert'  # Assume upsert for now
                record['_export_timestamp'] = until_timestamp.isoformat()
                
                records.append(record)
                change_summary["inserted"] += 1  # Simplified - assume all are inserts
        
        logger.info(f"Exported {len(records)} incremental records from {table_name}")
        return records, change_summary
    
    def _get_last_exported_id(self, table_name: str, since_timestamp: datetime) -> int:
        """
        Get the last exported ID for tables without proper timestamps.
        
        Args:
            table_name: Name of the table
            since_timestamp: Reference timestamp
            
        Returns:
            Last exported ID or 0 if none found
        """
        # This is a simplified implementation
        # In practice, you'd want to store this mapping
        from ...db import get_cursor
        
        # Try to find the highest ID from around the since_timestamp
        # This is an approximation since we don't have exact timestamps
        with get_cursor() as cursor:
            cursor.execute(f"SELECT MAX(id) FROM {table_name}")
            max_id = cursor.fetchone()[0] or 0
            
            # Return a conservative estimate (subtract some buffer)
            # This ensures we don't miss records but might have some overlap
            return max(0, max_id - 1000)  # Conservative buffer
    
    def _process_record_for_export(self, record: Dict, table_name: str) -> Dict:
        """
        Process a record for export, handling special data types.
        
        Args:
            record: Record dictionary
            table_name: Name of the table
            
        Returns:
            Processed record
        """
        # Handle date objects
        for key, value in record.items():
            if hasattr(value, 'strftime'):  # datetime/date object
                record[key] = value.isoformat()
            elif value is None:
                record[key] = None
            elif isinstance(value, (int, float, str, bool, list, dict)):
                # Already JSON serializable
                continue
            else:
                # Convert to string as fallback
                record[key] = str(value)
        
        # Handle embeddings for papers table
        if table_name == 'papers' and 'embedding' in record:
            embedding = record['embedding']
            if embedding is not None:
                try:
                    if isinstance(embedding, str):
                        record['embedding'] = json.loads(embedding)
                    elif hasattr(embedding, 'tolist'):
                        record['embedding'] = embedding.tolist()
                    elif isinstance(embedding, (list, tuple)):
                        record['embedding'] = list(embedding)
                except Exception as e:
                    logger.warning(f"Could not process embedding for record {record.get('id')}: {e}")
                    record['embedding'] = None
        
        return record
    
    def export_incremental(self, since_timestamp: datetime = None, 
                          tables: List[str] = None) -> IncrementalMetadata:
        """
        Perform incremental export of specified tables.
        
        Args:
            since_timestamp: Export changes since this timestamp (auto-detect if None)
            tables: List of tables to export (all configured tables if None)
            
        Returns:
            Incremental metadata for the export
        """
        until_timestamp = datetime.now(timezone.utc)
        
        if tables is None:
            tables = list(self.table_configs.keys())
        
        # Auto-detect since_timestamp if not provided
        if since_timestamp is None:
            # Find the earliest last export timestamp across all tables
            timestamps = []
            for table_name in tables:
                last_ts = self.get_last_export_timestamp(table_name)
                if last_ts:
                    timestamps.append(last_ts)
            
            if timestamps:
                since_timestamp = min(timestamps)
            else:
                # No previous exports, go back 7 days as default
                since_timestamp = until_timestamp - timedelta(days=7)
                logger.info(f"No previous exports found, using 7-day window: {since_timestamp}")
        
        logger.info(f"Starting incremental export from {since_timestamp} to {until_timestamp}")
        
        change_summary = {}
        total_records = 0
        
        # Export each table
        for table_name in tables:
            logger.info(f"Exporting incremental data for {table_name}")
            
            records, table_changes = self.export_table_incremental(
                table_name, since_timestamp, until_timestamp
            )
            
            if records:
                # Save table data
                output_file = self.output_dir / f"{table_name}_incremental.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(records, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Saved {len(records)} records to {output_file}")
                total_records += len(records)
            
            change_summary[table_name] = table_changes
        
        # Create incremental metadata
        metadata = IncrementalMetadata(
            export_type='incremental',
            base_export_timestamp=None,  # Could link to full export
            since_timestamp=since_timestamp,
            until_timestamp=until_timestamp,
            tables_included=tables,
            change_summary=change_summary
        )
        
        # Save metadata
        self.save_incremental_metadata(metadata)
        
        # Create summary metadata file for this export
        export_metadata = {
            "export_id": metadata.export_id,
            "export_type": "incremental",
            "export_timestamp": until_timestamp.isoformat(),
            "since_timestamp": since_timestamp.isoformat(),
            "tables_exported": tables,
            "total_records": total_records,
            "change_summary": change_summary,
            "incremental_version": "1.0"
        }
        
        metadata_file = self.output_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(export_metadata, f, indent=2)
        
        logger.info(f"Incremental export complete: {total_records} total records")
        return metadata


class IncrementalImporter:
    """Handles incremental database imports with delta processing."""
    
    def __init__(self, db_path: str):
        """
        Initialize the incremental importer.
        
        Args:
            db_path: Database connection string
        """
        self.db_path = db_path
        self.import_stats = {
            "inserted": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }
    
    def detect_incremental_import(self, input_path: str) -> bool:
        """
        Detect if the import data is incremental.
        
        Args:
            input_path: Path to import directory
            
        Returns:
            True if incremental import detected
        """
        input_dir = Path(input_path)
        metadata_file = input_dir / "metadata.json"
        
        if not metadata_file.exists():
            return False
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            return metadata.get("export_type") == "incremental"
            
        except Exception as e:
            logger.warning(f"Could not read metadata: {e}")
            return False
    
    def import_table_incremental(self, table_name: str, records: List[Dict], 
                                merge_strategy: str = 'upsert') -> Dict[str, int]:
        """
        Import incremental data for a table using UPSERT operations.
        
        Args:
            table_name: Name of the table
            records: List of records to import
            merge_strategy: 'upsert', 'insert_only', or 'update_only'
            
        Returns:
            Import statistics
        """
        if not records:
            return {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        
        from ...db import get_cursor
        
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        
        # Get table-specific UPSERT configuration
        upsert_config = self._get_upsert_config(table_name)
        if not upsert_config:
            logger.error(f"No UPSERT configuration for table {table_name}")
            return stats
        
        with get_cursor() as cursor:
            for record in records:
                try:
                    # Remove incremental metadata from record
                    clean_record = {k: v for k, v in record.items() 
                                  if not k.startswith('_incremental') and not k.startswith('_export')}
                    
                    if merge_strategy == 'upsert':
                        result = self._upsert_record(cursor, table_name, clean_record, upsert_config)
                        if result == 'inserted':
                            stats['inserted'] += 1
                        elif result == 'updated':
                            stats['updated'] += 1
                        else:
                            stats['skipped'] += 1
                    
                    elif merge_strategy == 'insert_only':
                        if self._record_exists(cursor, table_name, clean_record, upsert_config):
                            stats['skipped'] += 1
                        else:
                            self._insert_record(cursor, table_name, clean_record)
                            stats['inserted'] += 1
                    
                    elif merge_strategy == 'update_only':
                        if self._record_exists(cursor, table_name, clean_record, upsert_config):
                            self._update_record(cursor, table_name, clean_record, upsert_config)
                            stats['updated'] += 1
                        else:
                            stats['skipped'] += 1
                
                except Exception as e:
                    logger.error(f"Error importing record {record.get('id', 'unknown')}: {e}")
                    stats['errors'] += 1
        
        logger.info(f"Imported {table_name}: {stats}")
        return stats
    
    def _get_upsert_config(self, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Get UPSERT configuration for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            UPSERT configuration or None
        """
        configs = {
            'papers': {
                'primary_key': ['id'],
                'conflict_columns': ['id'],
                'update_columns': ['title', 'abstract', 'score', 'rationale', 'embedding', 'text', 'summary']
            },
            'research_profiles': {
                'primary_key': ['id'],
                'conflict_columns': ['id'],
                'update_columns': ['name', 'email', 'institution', 'bio', 'updated_at']
            },
            'research_runs': {
                'primary_key': ['id'],
                'conflict_columns': ['id'],
                'update_columns': ['status', 'results', 'updated_at']
            },
            'mindmap_reports': {
                'primary_key': ['id'],
                'conflict_columns': ['id'],
                'update_columns': ['content', 'status', 'updated_at']
            },
            'topics': {
                'primary_key': ['id'],
                'conflict_columns': ['id'],
                'update_columns': ['label', 'keywords', 'centroid_embedding', 'updated_at']
            },
            'paper_fulltext': {
                'primary_key': ['paper_id'],
                'conflict_columns': ['paper_id'],
                'update_columns': ['fulltext', 'extraction_status', 'updated_at']
            }
        }
        
        return configs.get(table_name)
    
    def _upsert_record(self, cursor, table_name: str, record: Dict, 
                      config: Dict[str, Any]) -> str:
        """
        Perform UPSERT operation on a record.
        
        Args:
            cursor: Database cursor
            table_name: Name of the table
            record: Record to upsert
            config: UPSERT configuration
            
        Returns:
            'inserted', 'updated', or 'skipped'
        """
        # Build UPSERT query using PostgreSQL's ON CONFLICT
        columns = list(record.keys())
        values_placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join(columns)
        
        conflict_columns = config['conflict_columns']
        update_columns = [col for col in config['update_columns'] if col in columns]
        
        if not update_columns:
            # No updateable columns, just insert or skip
            conflict_str = ', '.join(conflict_columns)
            query = f"""
                INSERT INTO {table_name} ({columns_str})
                VALUES ({values_placeholders})
                ON CONFLICT ({conflict_str}) DO NOTHING
                RETURNING (xmax = 0) AS inserted
            """
        else:
            # Build update clause
            update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in update_columns])
            conflict_str = ', '.join(conflict_columns)
            
            query = f"""
                INSERT INTO {table_name} ({columns_str})
                VALUES ({values_placeholders})
                ON CONFLICT ({conflict_str}) DO UPDATE SET {update_clause}
                RETURNING (xmax = 0) AS inserted
            """
        
        values = [record[col] for col in columns]
        
        try:
            cursor.execute(query, values)
            result = cursor.fetchone()
            
            if result and result['inserted']:
                return 'inserted'
            else:
                return 'updated'
                
        except Exception as e:
            logger.error(f"UPSERT failed for {table_name}: {e}")
            return 'skipped'
    
    def _record_exists(self, cursor, table_name: str, record: Dict, 
                      config: Dict[str, Any]) -> bool:
        """
        Check if a record exists in the table.
        
        Args:
            cursor: Database cursor
            table_name: Name of the table
            record: Record to check
            config: Table configuration
            
        Returns:
            True if record exists
        """
        primary_key = config['primary_key']
        where_clauses = [f"{col} = %s" for col in primary_key]
        where_str = ' AND '.join(where_clauses)
        values = [record[col] for col in primary_key]
        
        query = f"SELECT 1 FROM {table_name} WHERE {where_str}"
        cursor.execute(query, values)
        
        return cursor.fetchone() is not None
    
    def _insert_record(self, cursor, table_name: str, record: Dict):
        """Insert a new record."""
        columns = list(record.keys())
        values_placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join(columns)
        values = [record[col] for col in columns]
        
        query = f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_placeholders})"
        cursor.execute(query, values)
    
    def _update_record(self, cursor, table_name: str, record: Dict, 
                      config: Dict[str, Any]):
        """Update an existing record."""
        primary_key = config['primary_key']
        update_columns = [col for col in config['update_columns'] if col in record]
        
        set_clauses = [f"{col} = %s" for col in update_columns]
        where_clauses = [f"{col} = %s" for col in primary_key]
        
        set_str = ', '.join(set_clauses)
        where_str = ' AND '.join(where_clauses)
        
        values = [record[col] for col in update_columns] + [record[col] for col in primary_key]
        
        query = f"UPDATE {table_name} SET {set_str} WHERE {where_str}"
        cursor.execute(query, values)
    
    def import_incremental(self, input_path: str, merge_strategy: str = 'upsert') -> Dict[str, Any]:
        """
        Import incremental data from directory.
        
        Args:
            input_path: Path to incremental export directory
            merge_strategy: How to handle conflicts ('upsert', 'insert_only', 'update_only')
            
        Returns:
            Import results
        """
        input_dir = Path(input_path)
        
        # Load and validate metadata
        metadata_file = input_dir / "metadata.json"
        if not metadata_file.exists():
            raise ValueError("No metadata.json found in incremental export")
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        if metadata.get("export_type") != "incremental":
            raise ValueError("Not an incremental export")
        
        logger.info(f"Importing incremental data with {merge_strategy} strategy")
        
        total_stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
        table_results = {}
        
        # Import each table
        for table_name in metadata.get("tables_exported", []):
            incremental_file = input_dir / f"{table_name}_incremental.json"
            
            if not incremental_file.exists():
                logger.warning(f"Incremental file not found: {incremental_file}")
                continue
            
            logger.info(f"Importing incremental data for {table_name}")
            
            with open(incremental_file, 'r') as f:
                records = json.load(f)
            
            table_stats = self.import_table_incremental(table_name, records, merge_strategy)
            table_results[table_name] = table_stats
            
            # Aggregate stats
            for key in total_stats:
                total_stats[key] += table_stats[key]
        
        results = {
            "import_type": "incremental",
            "merge_strategy": merge_strategy,
            "total_stats": total_stats,
            "table_results": table_results,
            "metadata": metadata
        }
        
        logger.info(f"Incremental import complete: {total_stats}")
        return results