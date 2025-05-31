# Database Migration Tools

This directory contains utilities for migrating Theseus Insight databases between different environments. The tools support exporting data to portable archives and importing them to new databases while handling duplicates intelligently.

## Overview

The migration system consists of three main components:

- **`db_export.py`** - Exports database contents to JSON files and tar.gz archives
- **`db_import.py`** - Imports data from JSON files or archives into databases
- **`db_migrate.py`** - High-level orchestration for complete migration workflows

## Supported Tables

The migration tools focus on the core data tables:
- **papers** - Research papers with embeddings and metadata
- **podcasts** - Generated podcast content
- **newsletters** - Newsletter content and metadata

## Quick Start

### 1. Export Database to Archive

```bash
# Export your development database
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://user:pass@localhost:5432/theseus_dev" \
    --output ./my_backup.tar.gz
```

### 2. Import Archive to New Database

```bash
# Import to production database (SQLite) (skips duplicates by default)
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "sqlite:///./data/theseus_prod.db" \
    --input ./my_backup.tar.gz
```

### 3. Direct Database Migration

```bash
# Migrate directly (e.g., from PostgreSQL to SQLite) with verification
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@localhost:5432/theseus_pg_dev" \
    --target-db "sqlite:///./data/theseus_sqlite_prod.db" \
    --verify
```

## Detailed Usage

### Export Operations

#### Basic Export
```bash
python -m theseus_insight.utils.db_migration.db_export \
    --db-path "postgresql://user:pass@localhost:5432/theseus_db" \
    --output-dir ./export_data
```

#### Export with Custom Archive Name
```bash
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://user:pass@localhost:5432/theseus_db" \
    --output ./backups/ \
    --archive-name "production_backup_2024_01_15"
```

#### Export Without Creating Archive
```bash
python -m theseus_insight.utils.db_migration.db_export \
    --db-path "postgresql://user:pass@localhost:5432/theseus_db" \
    --output-dir ./export_data \
    --no-archive
```

### Import Operations

#### Import from Archive
```bash
python -m theseus_insight.utils.db_migration.db_import \
    --db-path "sqlite:///./data/theseus_new.db" \
    --input-path ./backup.tar.gz
```

#### Import from Directory
```bash
python -m theseus_insight.utils.db_migration.db_import \
    --db-path "sqlite:///./data/theseus_new.db" \
    --input-path ./export_data/
```

#### Allow Duplicate Entries
```bash
python -m theseus_insight.utils.db_migration.db_import \
    --db-path "sqlite:///./data/theseus_new.db" \
    --input-path ./backup.tar.gz \
    --allow-duplicates
```

### Migration Operations

#### Basic Migration (e.g., PostgreSQL to SQLite)
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-pg-server:5432/theseus_pg_db" \
    --target-db "sqlite:///./data/theseus_sqlite.db"
```

#### Migration with Archive Preservation
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-pg-server:5432/theseus_pg_db" \
    --target-db "sqlite:///./data/theseus_sqlite.db" \
    --keep-archive \
    --archive-path ./migration_pg_to_sqlite_backup.tar.gz
```

#### Migration with Verification
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-pg-server:5432/theseus_pg_db" \
    --target-db "sqlite:///./data/theseus_sqlite.db" \
    --verify
```

### Verification

#### Verify Migration Success (e.g., PostgreSQL source vs SQLite target)
```bash
python -m theseus_insight.utils.db_migration.db_migrate verify \
    --source-db "postgresql://user:pass@old-pg-server:5432/theseus_pg_db" \
    --target-db "sqlite:///./data/theseus_sqlite.db"
```

## Duplicate Handling

The migration tools handle duplicates intelligently:

- **Papers**: Duplicates detected by URL
- **Podcasts**: Duplicates detected by title
- **Newsletters**: Duplicates detected by date range (start_date + end_date)

By default, duplicates are skipped during import. Use `--allow-duplicates` to override this behavior.

## Archive Format

Archives are created as compressed tar.gz files containing:

```
backup.tar.gz
├── papers.json      # All papers with embeddings
├── podcasts.json    # All podcast content
├── newsletters.json # All newsletter content
└── metadata.json    # Export metadata and version info
```

### Metadata Structure
```json
{
  "export_timestamp": "2024-01-15T10:30:00",
  "export_version": "1.0",
  "tables_exported": ["papers", "podcasts", "newsletters"],
  "description": "Theseus Insight database export"
}
```

## Database Connection Strings

The tools use SQLAlchemy-compatible connection strings.
- **PostgreSQL (for source DBs in migration scenarios)**:
  ```
  postgresql://username:password@hostname:port/database
  # Example: postgresql://theseus:secret@localhost:5432/theseus_pg_db
  ```
- **SQLite (for target DBs)**:
  ```
  sqlite:///path/to/database_file.db
  # Example for a file in a 'data' subdirectory: sqlite:///./data/theseus.db
  # Example for an absolute path: sqlite:////mnt/data/theseus.db
  # For an in-memory database (testing only): sqlite:///:memory:
  ```

## Error Handling

The tools provide comprehensive error reporting:

- **Export errors**: Issues reading from source database
- **Import errors**: Validation failures, constraint violations
- **Network errors**: Connection timeouts, authentication failures
- **File errors**: Corrupt archives, missing files

All operations return appropriate exit codes:
- `0`: Success
- `1`: Error occurred

## Performance Considerations

### Large Datasets
- Exports are memory-efficient, processing data in chunks
- Archives are compressed to minimize transfer time
- Imports use batch operations where possible

### Network Transfers
- Use compression for remote transfers
- Consider bandwidth limitations for large embeddings
- Archive files are typically 10-20% of raw database size

### Embeddings
- Vector embeddings are preserved exactly
- Large embedding tables may take significant time to transfer
- Consider network timeouts for very large datasets

## Troubleshooting

### Common Issues

#### Connection Errors
For PostgreSQL source:
```bash
# Test database connectivity first
psql "postgresql://user:pass@host:port/db" -c "SELECT 1;"
```
For SQLite target: Ensure the directory for the database file exists and is writable.

#### Permission Errors
For PostgreSQL source:
```bash
# Ensure user has necessary permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO migration_user;
```
For SQLite target: Ensure file system permissions allow creating/writing the database file.

#### Archive Corruption
```bash
# Test archive integrity
tar -tzf backup.tar.gz > /dev/null && echo "Archive OK"
```

#### Memory Issues
```bash
# For very large datasets, increase available memory
export PYTHONHASHSEED=0
ulimit -v 8388608  # 8GB virtual memory limit
```

### Debugging

Enable verbose output by modifying the scripts to include debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration with CI/CD

### Automated Backups
```bash
#!/bin/bash
# Daily backup script
DATE=$(date +%Y%m%d)
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "$PROD_DB_URL" \
    --output "./backups/daily_backup_$DATE.tar.gz"
```

### Environment Promotion
```bash
#!/bin/bash
# Promote staging to production
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "$STAGING_DB_URL" \
    --target-db "$PROD_DB_URL" \
    --verify \
    --keep-archive \
    --archive-path "./releases/prod_migration_$(date +%Y%m%d).tar.gz"
```

## Security Considerations

- Store database credentials securely (environment variables, secrets management)
- Use SSL connections for remote databases
- Validate archive integrity before importing
- Audit migration operations in production environments
- Consider encrypting archives for sensitive data

## Version Compatibility

- Export format version: 1.0
- Source database compatibility (if PostgreSQL): PostgreSQL 12+
- Target database: SQLite 3.35+ (recommended for features like `ROW_NUMBER()` if used, FTS5, etc.)
- Requires Python 3.8+
- Core Dependencies: `sqlalchemy`, `pydantic`
- For PostgreSQL source: `psycopg2-binary`, `pgvector`
- For SQLite target: `sqlite-vec` (Python bindings for `sqlite3` should be able to load `sqlite-vec` C extensions)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify database connectivity and permissions
3. Test with a small dataset first
4. Review error messages and logs 