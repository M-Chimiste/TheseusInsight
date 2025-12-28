# Database Migration Tools

This directory contains utilities for migrating Theseus Insight databases between different environments. The tools support exporting data to portable archives and importing them to new databases while handling duplicates intelligently and maintaining full backward compatibility.

## Overview

The migration system consists of three main components:

- **`db_export.py`** - Exports database contents to JSON files and tar.gz archives
- **`db_import.py`** - Imports data from JSON files or archives into databases
- **`db_migrate.py`** - High-level orchestration for complete migration workflows

The system now supports **16 different table types** covering the complete Theseus Insight feature set including research agents, mind maps, trends analysis, and research interest clustering.

## Supported Tables

### Core Data Tables
- **papers** - Research papers with embeddings, keywords, and metadata
- **podcasts** - Generated podcast content and scripts
- **newsletters** - Newsletter content and metadata
- **literature_reviews** - Literature review reports and traces

### Research Agent Tables  
- **research_runs** - AI research task executions and results
- **research_agent_state** - State snapshots during research workflows

### Advanced Features
- **paper_fulltext** - Full-text content extraction from papers
- **mindmap_reports** - Mind map visualizations and data
- **model_catalog** - LLM model configurations and metadata

### Trends & Topics Analysis
- **topics** - Automatically discovered research topics
- **topic_metrics** - Time series metrics for topic evolution
- **paper_topics** - Paper-to-topic relationship mappings

### Research Interest Clustering
- **research_interests** - User-defined research interests
- **research_interest_metrics** - Time series metrics for research interests
- **paper_research_interests** - Paper-to-research interest mappings

### Utility Tables
- **label_summaries** - Cached label summaries for performance

## Quick Start

### 1. Export Database to Archive

```bash
# Export your complete database (all 16 tables)
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://user:pass@localhost:5432/theseus_dev" \
    --output ./my_backup_v3.tar.gz
```

### 2. Import Archive to New Database

```bash
# Import to production database (skips duplicates by default)
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "postgresql://user:pass@prod-server:5432/theseus_prod" \
    --input ./my_backup_v3.tar.gz
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

#### Complete Export (All Features)
```bash
python -m theseus_insight.utils.db_migration.db_export \
    --db-path "postgresql://user:pass@localhost:5432/theseus_db" \
    --output-dir ./export_data
```

#### Backward Compatible Export (Core Tables Only)
```bash
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://user:pass@localhost:5432/theseus_db" \
    --output ./core_backup.tar.gz \
    --exclude-new-tables
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

#### Import from Archive (All Tables)
```bash
python -m theseus_insight.utils.db_migration.db_import \
    --db-path "postgresql://user:pass@localhost:5432/theseus_new" \
    --input-path ./backup_v3.tar.gz
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
    --input-path ./backup_v3.tar.gz \
    --allow-duplicates
```

### Migration Operations

#### Complete Migration (All Features)
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
    --archive-path ./migration_backup_v3.tar.gz
```

#### Migration with Verification
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-server:5432/theseus_db" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_db" \
    --verify
```

#### Core Tables Only Migration (Backward Compatibility)
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-server:5432/theseus_db" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_db" \
    --exclude-new-tables
```

### Verification

#### Verify Migration Success (All Tables)
```bash
python -m theseus_insight.utils.db_migration.db_migrate verify \
    --source-db "postgresql://user:pass@old-server:5432/theseus_db" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_db"
```

## Duplicate Handling

The migration tools handle duplicates intelligently across all table types:

### Core Tables
- **Papers**: Duplicates detected by URL
- **Podcasts**: Duplicates detected by title  
- **Newsletters**: Duplicates detected by date range (start_date + end_date)
- **Literature Reviews**: Duplicates detected by research question and timestamp

### Research Agent Tables
- **Research Runs**: Duplicates detected by task_id
- **Research Agent State**: Duplicates detected by task_id + node_name + timestamp

### Advanced Features
- **Paper Fulltext**: Duplicates detected by paper_id
- **Mindmap Reports**: Duplicates detected by title and creation timestamp
- **Model Catalog**: Duplicates detected by alias

### Trends & Research Interests
- **Topics**: Duplicates detected by label
- **Topic/Research Interest Metrics**: Duplicates detected by unique period constraints
- **Relationship Tables**: Duplicates detected by unique key combinations

By default, duplicates are skipped during import. Use `--allow-duplicates` to override this behavior.

## Complete Database Overwrite

When performing a complete database overwrite (import_mode="overwrite"), the system:

1. **Checks which tables exist** in the target database
2. **Clears all existing data** in the correct order respecting foreign key constraints
3. **Deletes child tables first**, then parent tables to avoid FK violations
4. **Skips tables that don't exist** (graceful handling of schema differences)
5. **Imports the new data** from the archive

The deletion order follows this hierarchy:
- System tables (logs, tasks, error_logs)
- Worker management tables (worker_heartbeats, judge_task_queue)
- Processing jobs and scheduler tables
- Research agent state and runs
- Content tables (newsletters, podcasts, fulltext, mindmaps)
- Topics, metrics, and relationship tables
- Research interests and their relationships
- Profile scores and interests
- Core tables (papers, research_profiles)

**Important**: Complete overwrites are destructive and cannot be undone. Always ensure you have a backup before performing an overwrite operation.

### Schema Compatibility

The overwrite process is designed to work across different schema versions:

- **Newer schemas**: All tables are cleared in the correct order
- **Older schemas**: Missing tables are gracefully skipped (e.g., tables from migrations 006-008)
- **Partial migrations**: Only existing tables are cleared, preventing errors

This ensures that database overwrites work correctly regardless of which migrations have been applied to the target database.

### Research Profiles - Special Handling

Research profiles have special handling during import, particularly for the Default profile:

#### Default Profile Comparison

When importing a Default profile, the system compares it with the existing Default profile in the target database:

- **Profiles Match**: If `arxiv_filters`, `tags`, and `email_recipients` are identical:
  - The import maps the source profile ID to the existing Default profile
  - All associated papers/scores are imported to the existing Default profile
  - **NEW:** Any research interests in the source that don't exist in the target are automatically merged

- **Profiles Differ**: If any of these fields differ:
  - A new profile named "Default (Imported)" is created
  - All papers/scores and research interests are imported into this new profile

#### Research Interest Merging (New Feature)

By default (`merge_interests=True`), when profiles match:

1. The system detects research interests in the source that don't exist in the target (case-insensitive comparison)
2. These new interests are automatically added to the existing profile
3. Existing interests are preserved - no interests are ever removed during merge

This ensures that when you import a backup from another machine where you've added new research interests, those interests are properly merged into your existing profile rather than being lost.

**Example:**
```
Source DB Default Profile:
  - arxiv_filters: ["cs.AI"]
  - interests: ["neural networks", "transformers", "vision models"]

Target DB Default Profile:
  - arxiv_filters: ["cs.AI"]  
  - interests: ["neural networks", "language models"]

Result (merge_interests=True):
  - Profile matched (same arxiv_filters)
  - New interests "transformers" and "vision models" merged
  - Final interests: ["neural networks", "language models", "transformers", "vision models"]
```

#### API Parameter

When using the import API, you can control this behavior:

```bash
# Default: merge interests when profiles match
curl -X POST "/api/settings/database/import" \
  -F "backup_file=@backup.tar.gz" \
  -F "import_mode=merge" \
  -F "merge_interests=true"

# Disable interest merging (older behavior)
curl -X POST "/api/settings/database/import" \
  -F "backup_file=@backup.tar.gz" \
  -F "import_mode=merge" \
  -F "merge_interests=false"
```

#### Example Scenarios

**Scenario 1 - Matching Profiles with Interest Merge:**
```
Source DB: Default profile with arxiv_filters: ["cs.AI", "cs.LG"], 5 research interests
Target DB: Default profile with arxiv_filters: ["cs.AI", "cs.LG"], 3 research interests
Result: Papers imported to existing Default profile, 2 new interests merged
```

**Scenario 2 - Different Profiles:**
```
Source DB: Default profile with arxiv_filters: ["cs.AI", "cs.LG"], 700k papers
Target DB: Default profile with arxiv_filters: ["cs.CV", "cs.RO"]
Result: New "Default (Imported)" profile created, all 700k papers and interests imported there
```

#### Non-Default Profiles

Non-Default profiles are matched by name:
- If a profile with the same name exists:
  - Papers are mapped to the existing profile
  - Research interests are merged (if `merge_interests=True`)
- If no match exists, a new profile is created

See [Database Import Profile Handling](database_import_profile_handling.md) for detailed documentation.

## Archive Format

### Version 3.0 Archives (Current)
Archives are created as compressed tar.gz files containing all 16 table types:

```
backup_v3.tar.gz
├── papers.json                     # Research papers with embeddings
├── podcasts.json                   # Podcast content  
├── newsletters.json                # Newsletter content
├── literature_reviews.json         # Literature review reports
├── research_runs.json              # Research agent executions
├── research_agent_state.json       # Research workflow states
├── paper_fulltext.json             # Full-text paper content
├── mindmap_reports.json            # Mind map visualizations
├── model_catalog.json              # LLM model configurations
├── topics.json                     # Discovered research topics
├── topic_metrics.json              # Topic evolution metrics
├── paper_topics.json               # Paper-topic relationships
├── research_interests.json         # User research interests
├── research_interest_metrics.json  # Research interest metrics
├── paper_research_interests.json   # Paper-research interest relationships
├── label_summaries.json            # Cached label summaries
└── metadata.json                   # Export metadata and version info
```

### Metadata Structure (v3.0)
```json
{
  "export_timestamp": "2024-01-15T10:30:00",
  "export_version": "3.0",
  "tables_exported": [
    "papers", "podcasts", "newsletters", "literature_reviews",
    "research_runs", "research_agent_state", "paper_fulltext", 
    "mindmap_reports", "model_catalog", "topics", "topic_metrics",
    "paper_topics", "research_interests", "research_interest_metrics",
    "paper_research_interests", "label_summaries"
  ],
  "description": "Theseus Insight database export with Trends, Research Interests, and full feature set",
  "backwards_compatible": true,
  "new_features": [
    "research_runs", "research_agent_state", "paper_fulltext",
    "mindmap_reports", "model_catalog", "topics", "topic_metrics",
    "paper_topics", "research_interests", "research_interest_metrics",
    "paper_research_interests", "label_summaries"
  ]
}
```

## Backward Compatibility

### Export Compatibility
- **v1.0 Exports**: Core tables only (papers, podcasts, newsletters)
- **v2.0 Exports**: Core + Research Agent + Advanced features  
- **v3.0 Exports**: Complete feature set including Trends and Research Interests

### Import Compatibility
- ✅ **v3.0 imports can read**: v1.0, v2.0, and v3.0 exports
- ✅ **Missing tables**: Handled gracefully with informative messages
- ✅ **Core functionality**: Always preserved regardless of export version
- ✅ **Progressive enhancement**: New features imported when available

### Migration Strategies
```bash
# Import older backup to current system
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "postgresql://user:pass@localhost:5432/theseus_current" \
    --input ./old_backup_v1.tar.gz
# → Core tables imported, new features remain empty

# Export for older system  
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://user:pass@localhost:5432/theseus_current" \
    --output ./compatible_backup.tar.gz \
    --exclude-new-tables
# → Only core tables exported for compatibility
```

## Database Connection Strings

The tools accept PostgreSQL connection URLs:

```bash
# Standard PostgreSQL URL
postgresql://username:password@hostname:port/database

# With SSL
postgresql://username:password@hostname:port/database?sslmode=require

# Local connection
postgresql://localhost/theseus_db
```

## Error Handling

The tools provide comprehensive error reporting:

- **Export errors**: Issues reading from source database, missing tables
- **Import errors**: Validation failures, constraint violations, embedding conversion
- **Network errors**: Connection timeouts, authentication failures
- **File errors**: Corrupt archives, missing files, malformed JSON
- **Data errors**: Invalid embeddings, foreign key violations, duplicate keys

All operations return appropriate exit codes:
- `0`: Success
- `1`: Error occurred

Example error output:
```
Warning: Could not export topics: relation "topics" does not exist
Note: research_interests.json not found (this is optional for older exports)
✓ Papers import completed: 1250 imported, 45 skipped, 0 errors
```

## Performance Considerations

### Large Datasets
- **Memory efficiency**: Processes data in chunks, not loading entire tables
- **Compression**: Archives are gzip compressed (typically 70-80% size reduction)
- **Batch imports**: Uses bulk operations for improved performance
- **Progress tracking**: Real-time progress updates for long operations

### Vector Embeddings
- **Preservation**: Embeddings preserved exactly as pgvector format
- **Conversion**: Automatic conversion between JSON and pgvector formats
- **Large embeddings**: 768-dimension vectors handled efficiently
- **Memory usage**: Streaming processing prevents memory overflow

### Network Transfers
- **Compression**: Use compression for remote transfers
- **Bandwidth**: Consider limitations for large embedding tables
- **Archive size**: Complete archives typically 10-30% of raw database size
- **Parallel processing**: Multiple table exports can run concurrently

### Performance Examples
```bash
# Large database migration with progress
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "$SOURCE_DB" \
    --target-db "$TARGET_DB" \
    --verify 2>&1 | tee migration.log

# Monitor archive size
ls -lh *.tar.gz
# typical: 50MB archive from 200MB database
```

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
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO migration_user;
```

#### Missing Tables (Graceful Degradation)
```bash
# Check what tables are available
python -c "
from theseus_insight.utils.db_migration.db_export import DatabaseExporter
exporter = DatabaseExporter('postgresql://...', './test')
# Will show warnings for missing tables but continue
"
```

#### Archive Corruption
```bash
# Test archive integrity
tar -tzf backup_v3.tar.gz > /dev/null && echo "Archive OK"

# List archive contents
tar -tzf backup_v3.tar.gz | head -20
```

#### Embedding Conversion Issues
```bash
# Check pgvector extension
psql "postgresql://..." -c "SELECT * FROM pg_extension WHERE extname='vector';"

# Verify embedding format in export
python -c "
import json
with open('export/papers.json') as f:
    papers = json.load(f)
    print('Sample embedding:', papers[0]['embedding'][:5] if papers else 'No papers')
"
```

### Debugging

Enable verbose output:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Or set environment variable
export THESEUS_LOG_LEVEL=DEBUG
```

## Integration with CI/CD

### Automated Backups
```bash
#!/bin/bash
# Daily backup script with all features
DATE=$(date +%Y%m%d_%H%M%S)
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "$PROD_DB_URL" \
    --output "./backups/full_backup_$DATE.tar.gz"

# Keep only last 30 days
find ./backups -name "full_backup_*.tar.gz" -mtime +30 -delete
```

### Environment Promotion
```bash
#!/bin/bash
# Promote staging to production with verification
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "$STAGING_DB_URL" \
    --target-db "$PROD_DB_URL" \
    --verify \
    --keep-archive \
    --archive-path "./releases/prod_migration_$TIMESTAMP.tar.gz"

if [ $? -eq 0 ]; then
    echo "✅ Migration successful, archive saved to ./releases/"
    # Trigger application restart, cache clearing, etc.
else
    echo "❌ Migration failed, check logs"
    exit 1
fi
```

### Feature Flag Migrations
```bash
#!/bin/bash
# Migrate core features only (for gradual rollouts)
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "$SOURCE_DB_URL" \
    --target-db "$TARGET_DB_URL" \
    --exclude-new-tables \
    --verify

# Later: migrate trends features
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "$SOURCE_DB_URL" \
    --output ./trends_data.tar.gz \
    # ... custom filtering for specific tables
```

## Security Considerations

- **Credentials**: Store database credentials securely (environment variables, secrets management)
- **Encryption**: Use SSL connections for remote databases (`sslmode=require`)  
- **Archive security**: Consider encrypting archives for sensitive data
- **Access control**: Audit migration operations in production environments
- **Data privacy**: Be aware of embedding data containing sensitive information
- **Network security**: Use VPNs or secure networks for database migrations

### Secure Migration Example
```bash
# Use environment variables for credentials
export SOURCE_DB="postgresql://$DB_USER:$DB_PASS@$DB_HOST:$DB_PORT/$DB_NAME?sslmode=require"
export TARGET_DB="postgresql://$DB_USER:$DB_PASS@$TARGET_HOST:$TARGET_PORT/$TARGET_DB?sslmode=require"

# Migrate with encryption
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "$SOURCE_DB" \
    --target-db "$TARGET_DB" \
    --verify \
    --keep-archive \
    --archive-path "./secure_migration_$(date +%Y%m%d).tar.gz"

# Encrypt archive
gpg --cipher-algo AES256 --compress-algo 1 --symmetric \
    "./secure_migration_$(date +%Y%m%d).tar.gz"
```

## Version Compatibility

- **Export format version**: 3.0 (backward compatible with 1.0, 2.0)
- **Python requirement**: 3.8+
- **Database**: PostgreSQL 12+ with pgvector extension
- **Dependencies**: psycopg2, numpy, pydantic

### Version Migration Path
```
v1.0 → v2.0 → v3.0
 │       │       │
 │       │       ├─ Trends & Research Interests
 │       │       ├─ Label Summaries  
 │       │       └─ Complete Feature Set
 │       │
 │       ├─ Research Agent
 │       ├─ Mind Maps
 │       ├─ Model Catalog
 │       └─ Paper Fulltext
 │
 ├─ Core Tables
 ├─ Papers with Embeddings
 └─ Basic Features
```

## Support

For issues or questions:
1. **Check compatibility**: Verify export/import version compatibility
2. **Test connectivity**: Ensure database connections work with `psql`
3. **Validate data**: Test with small datasets first
4. **Review logs**: Check error messages and warnings
5. **Check permissions**: Verify database user has required privileges
6. **Archive integrity**: Test archive files before importing

### Common Migration Scenarios

**New Installation**: Import any version export (graceful handling of missing features)
**Version Upgrade**: Export v3.0 from upgraded system, import to new system  
**Feature Rollback**: Export with `--exclude-new-tables` for compatibility
**Partial Migration**: Import specific tables by using directory import method 