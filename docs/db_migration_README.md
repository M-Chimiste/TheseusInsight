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
# Import to production database (skips duplicates by default)
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "postgresql://user:pass@prod-server:5432/theseus_prod" \
    --input ./my_backup.tar.gz
```

### 3. Direct Database Migration

```bash
# Migrate directly between databases with verification
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@localhost:5432/theseus_dev" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_prod" \
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
    --db-path "postgresql://user:pass@localhost:5432/theseus_new" \
    --input-path ./backup.tar.gz
```

#### Import from Directory
```bash
python -m theseus_insight.utils.db_migration.db_import \
    --db-path "postgresql://user:pass@localhost:5432/theseus_new" \
    --input-path ./export_data/
```

#### Allow Duplicate Entries
```bash
python -m theseus_insight.utils.db_migration.db_import \
    --db-path "postgresql://user:pass@localhost:5432/theseus_new" \
    --input-path ./backup.tar.gz \
    --allow-duplicates
```

### Migration Operations

#### Basic Migration
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-server:5432/theseus_db" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_db"
```

#### Migration with Archive Preservation
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-server:5432/theseus_db" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_db" \
    --keep-archive \
    --archive-path ./migration_backup.tar.gz
```

#### Migration with Verification
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-server:5432/theseus_db" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_db" \
    --verify
```

### Verification

#### Verify Migration Success
```bash
python -m theseus_insight.utils.db_migration.db_migrate verify \
    --source-db "postgresql://user:pass@old-server:5432/theseus_db" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_db"
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

The tools support standard PostgreSQL connection strings:

```bash
# Basic format
postgresql://username:password@hostname:port/database

# Examples
postgresql://theseus:secret@localhost:5432/theseus_dev
postgresql://user@localhost/theseus_db
postgresql://user:pass@prod-server.com:5432/theseus_production
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
```bash
# Test database connectivity first
psql "postgresql://user:pass@host:port/db" -c "SELECT 1;"
```

#### Permission Errors
```bash
# Ensure user has necessary permissions
GRANT SELECT ON ALL TABLES IN SCHEMA public TO migration_user;
GRANT INSERT ON ALL TABLES IN SCHEMA public TO migration_user;
```

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
- Compatible with PostgreSQL 12+
- Requires Python 3.8+
- Dependencies: psycopg, pgvector, pydantic

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify database connectivity and permissions
3. Test with a small dataset first
4. Review error messages and logs 