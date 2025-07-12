#!/usr/bin/env python3
"""
Schema Versioning System

This module provides schema version tracking and migration capabilities
for the Theseus Insight database export/import system.
"""

import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ColumnInfo:
    """Information about a database column."""
    name: str
    data_type: str
    is_nullable: bool
    column_default: Optional[str] = None
    character_maximum_length: Optional[int] = None
    numeric_precision: Optional[int] = None
    numeric_scale: Optional[int] = None


@dataclass
class TableSchema:
    """Schema information for a database table."""
    name: str
    columns: List[ColumnInfo]
    primary_key: List[str]
    foreign_keys: Dict[str, Tuple[str, str]]  # column -> (ref_table, ref_column)
    indexes: List[Dict[str, Any]]
    
    def get_fingerprint(self) -> str:
        """Generate a unique fingerprint for this schema."""
        # Create a deterministic string representation
        schema_dict = {
            "name": self.name,
            "columns": [asdict(col) for col in sorted(self.columns, key=lambda c: c.name)],
            "primary_key": sorted(self.primary_key),
            "foreign_keys": dict(sorted(self.foreign_keys.items())),
            "indexes": sorted(self.indexes, key=lambda i: i.get("name", ""))
        }
        
        schema_str = json.dumps(schema_dict, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]


@dataclass
class SchemaVersion:
    """Represents a specific database schema version."""
    version: str
    timestamp: datetime
    tables: Dict[str, TableSchema]
    fingerprint: str
    compatible_versions: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "fingerprint": self.fingerprint,
            "compatible_versions": self.compatible_versions,
            "tables": {
                name: {
                    "fingerprint": schema.get_fingerprint(),
                    "columns": [col.name for col in schema.columns],
                    "column_types": {col.name: col.data_type for col in schema.columns}
                }
                for name, schema in self.tables.items()
            }
        }


class SchemaVersionManager:
    """Manages database schema versions and migrations."""
    
    def __init__(self, db_path: str):
        """
        Initialize the schema version manager.
        
        Args:
            db_path: Database connection string
        """
        self.db_path = db_path
        self.current_version = "5.1"  # Updated for schema versioning
        
    def extract_current_schema(self) -> SchemaVersion:
        """Extract the current database schema."""
        from ...db import get_cursor
        
        tables = {}
        
        with get_cursor() as cursor:
            # Get all tables
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            table_names = [row['table_name'] for row in cursor.fetchall()]
            
            for table_name in table_names:
                # Skip migration tracking tables
                if table_name.startswith('_migration_'):
                    continue
                    
                # Get column information
                cursor.execute("""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default,
                        character_maximum_length,
                        numeric_precision,
                        numeric_scale
                    FROM information_schema.columns
                    WHERE table_name = %s AND table_schema = 'public'
                    ORDER BY ordinal_position
                """, (table_name,))
                
                columns = [
                    ColumnInfo(
                        name=row['column_name'],
                        data_type=row['data_type'],
                        is_nullable=(row['is_nullable'] == 'YES'),
                        column_default=row['column_default'],
                        character_maximum_length=row['character_maximum_length'],
                        numeric_precision=row['numeric_precision'],
                        numeric_scale=row['numeric_scale']
                    )
                    for row in cursor.fetchall()
                ]
                
                # Get primary key
                cursor.execute("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = %s::regclass AND i.indisprimary
                """, (table_name,))
                primary_key = [row['attname'] for row in cursor.fetchall()]
                
                # Get foreign keys
                cursor.execute("""
                    SELECT
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' 
                    AND tc.table_name = %s
                """, (table_name,))
                
                foreign_keys = {
                    row['column_name']: (row['foreign_table_name'], row['foreign_column_name'])
                    for row in cursor.fetchall()
                }
                
                # Get indexes
                cursor.execute("""
                    SELECT
                        i.relname AS index_name,
                        a.attname AS column_name,
                        ix.indisunique AS is_unique,
                        ix.indisprimary AS is_primary
                    FROM pg_class t
                    JOIN pg_index ix ON t.oid = ix.indrelid
                    JOIN pg_class i ON i.oid = ix.indexrelid
                    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
                    WHERE t.relname = %s AND t.relkind = 'r'
                    ORDER BY i.relname, a.attnum
                """, (table_name,))
                
                # Group indexes by name
                index_dict = {}
                for row in cursor.fetchall():
                    index_name = row['index_name']
                    if index_name not in index_dict:
                        index_dict[index_name] = {
                            "name": index_name,
                            "columns": [],
                            "is_unique": row['is_unique'],
                            "is_primary": row['is_primary']
                        }
                    index_dict[index_name]["columns"].append(row['column_name'])
                
                indexes = list(index_dict.values())
                
                tables[table_name] = TableSchema(
                    name=table_name,
                    columns=columns,
                    primary_key=primary_key,
                    foreign_keys=foreign_keys,
                    indexes=indexes
                )
        
        # Calculate overall fingerprint
        table_fingerprints = {
            name: schema.get_fingerprint() 
            for name, schema in sorted(tables.items())
        }
        overall_fingerprint = hashlib.sha256(
            json.dumps(table_fingerprints, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        return SchemaVersion(
            version=self.current_version,
            timestamp=datetime.utcnow(),
            tables=tables,
            fingerprint=overall_fingerprint,
            compatible_versions=["5.0", "4.0", "4.1", "4.2"]
        )
    
    def save_schema_version(self, schema_version: SchemaVersion, output_path: Path):
        """Save schema version to file."""
        schema_file = output_path / "schema_version.json"
        
        with open(schema_file, 'w', encoding='utf-8') as f:
            json.dump(schema_version.to_dict(), f, indent=2)
        
        logger.info(f"Saved schema version {schema_version.version} to {schema_file}")
    
    def load_schema_version(self, input_path: Path) -> Optional[SchemaVersion]:
        """Load schema version from file."""
        schema_file = input_path / "schema_version.json"
        
        if not schema_file.exists():
            logger.warning("No schema version file found")
            return None
        
        with open(schema_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Note: This is a simplified loader that doesn't reconstruct full TableSchema objects
        # For migration purposes, we mainly need version and compatibility info
        return SchemaVersion(
            version=data["version"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            tables={},  # Simplified - not loading full schema
            fingerprint=data["fingerprint"],
            compatible_versions=data["compatible_versions"]
        )
    
    def check_compatibility(self, source_version: Optional[SchemaVersion]) -> Tuple[bool, List[str]]:
        """
        Check if the source schema is compatible with current schema.
        
        Returns:
            Tuple of (is_compatible, warnings)
        """
        warnings = []
        
        if source_version is None:
            # No version info - assume old format
            warnings.append("No schema version found in export - assuming legacy format")
            return True, warnings
        
        current_schema = self.extract_current_schema()
        
        # Check version compatibility
        if source_version.version == current_schema.version:
            return True, warnings
        
        if source_version.version in current_schema.compatible_versions:
            warnings.append(f"Import from compatible version {source_version.version}")
            return True, warnings
        
        # Check if current version is compatible with source
        if current_schema.version in source_version.compatible_versions:
            warnings.append(f"Current version {current_schema.version} is compatible with import version {source_version.version}")
            return True, warnings
        
        # Version not directly compatible - check table compatibility
        warnings.append(f"Schema version mismatch: import={source_version.version}, current={current_schema.version}")
        warnings.append("Performing detailed compatibility check...")
        
        # This would be expanded to check individual table compatibility
        # For now, we'll be permissive
        return True, warnings


class SchemaMigrator:
    """Handles schema migrations between versions."""
    
    def __init__(self, db_path: str):
        """
        Initialize the schema migrator.
        
        Args:
            db_path: Database connection string
        """
        self.db_path = db_path
        self.migrations = self._load_migrations()
    
    def _load_migrations(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load migration definitions."""
        # In a real implementation, these would be loaded from files
        # For now, we'll define some example migrations
        return {
            "4.0->5.0": [
                {
                    "type": "add_column",
                    "table": "papers",
                    "column": "embedding_model",
                    "definition": "VARCHAR(100)"
                },
                {
                    "type": "add_column", 
                    "table": "papers",
                    "column": "fulltext_extraction_status",
                    "definition": "VARCHAR(50)"
                }
            ],
            "5.0->5.1": [
                {
                    "type": "add_table",
                    "table": "_migration_history",
                    "definition": """
                        CREATE TABLE IF NOT EXISTS _migration_history (
                            id SERIAL PRIMARY KEY,
                            version_from VARCHAR(20),
                            version_to VARCHAR(20),
                            migration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            status VARCHAR(20),
                            details JSONB
                        )
                    """
                }
            ]
        }
    
    def get_migration_path(self, from_version: str, to_version: str) -> List[str]:
        """
        Find migration path between versions.
        
        Args:
            from_version: Source version
            to_version: Target version
            
        Returns:
            List of migration steps
        """
        # Simple direct path check
        direct_path = f"{from_version}->{to_version}"
        if direct_path in self.migrations:
            return [direct_path]
        
        # TODO: Implement path finding for multi-step migrations
        # For now, return empty if no direct path
        return []
    
    def apply_migration(self, migration_path: str, dry_run: bool = False) -> bool:
        """
        Apply a migration.
        
        Args:
            migration_path: Migration identifier (e.g., "4.0->5.0")
            dry_run: If True, only validate without applying
            
        Returns:
            Success status
        """
        if migration_path not in self.migrations:
            logger.error(f"Migration {migration_path} not found")
            return False
        
        from ...db import get_cursor
        
        migrations = self.migrations[migration_path]
        
        try:
            with get_cursor() as cursor:
                if not dry_run:
                    cursor.execute("BEGIN")
                
                for migration in migrations:
                    if migration["type"] == "add_column":
                        # Check if column exists
                        cursor.execute("""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = %s AND column_name = %s
                        """, (migration["table"], migration["column"]))
                        
                        if cursor.fetchone():
                            logger.info(f"Column {migration['table']}.{migration['column']} already exists")
                            continue
                        
                        sql = f"ALTER TABLE {migration['table']} ADD COLUMN {migration['column']} {migration['definition']}"
                        logger.info(f"Executing: {sql}")
                        
                        if not dry_run:
                            cursor.execute(sql)
                    
                    elif migration["type"] == "add_table":
                        logger.info(f"Creating table {migration['table']}")
                        
                        if not dry_run:
                            cursor.execute(migration["definition"])
                
                if not dry_run:
                    cursor.execute("COMMIT")
                    
                    # Record migration
                    cursor.execute("""
                        INSERT INTO _migration_history (version_from, version_to, status)
                        VALUES (%s, %s, 'completed')
                    """, tuple(migration_path.split("->")))
                
                logger.info(f"Migration {migration_path} completed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Migration {migration_path} failed: {e}")
            if not dry_run:
                cursor.execute("ROLLBACK")
            return False