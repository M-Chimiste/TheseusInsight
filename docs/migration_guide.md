# Migration Guide: SQLite to PostgreSQL

This guide provides step-by-step instructions for migrating your Theseus Insight installation from SQLite to PostgreSQL. The migration preserves all your data including papers, embeddings, summaries, keywords, podcasts, newsletters, and settings.

## Overview

The migration process involves:
1. **Exporting** data from your existing SQLite database
2. **Setting up** PostgreSQL with pgvector extension
3. **Importing** data into the new PostgreSQL database
4. **Verifying** the migration was successful

**Migration Time**: Typically 5-30 minutes depending on database size (1000 papers ≈ 2-5 minutes)

---

## Prerequisites

### What You'll Need

- **Existing Theseus Insight installation** with SQLite database (typically `data/theseus.db`)
- **PostgreSQL 14+** with pgvector extension (see [PostgreSQL Setup Guide](postgresql_setup.md))
- **Backup space** for your existing data (recommended)
- **Python environment** with Theseus Insight dependencies installed

### Before You Begin

1. **Backup your existing database:**
   ```bash
   cp data/theseus.db data/theseus_backup_$(date +%Y%m%d).db
   ```

2. **Stop the application** if it's currently running:
   ```bash
   # If running with Docker
   docker compose down
   
   # If running locally
   # Stop your uvicorn server (Ctrl+C)
   ```

3. **Verify database location:**
   ```bash
   ls -la data/theseus.db
   # Should show your SQLite database file
   ```

---

## Migration Methods

### Method 1: Automated Migration (Recommended)

The automated migration script handles the entire process:

```bash
# Run the automated migration
python -m theseus_insight.utils.db_migration.migrate_to_postgresql

# Follow the interactive prompts:
# 1. Confirm SQLite database path
# 2. Enter PostgreSQL connection details
# 3. Choose to backup existing data
# 4. Verify migration completion
```

**What the script does:**
- ✅ Validates source SQLite database
- ✅ Tests PostgreSQL connection
- ✅ Creates PostgreSQL schema with pgvector
- ✅ Exports all data from SQLite
- ✅ Imports data with type conversion
- ✅ Updates search vectors and indexes
- ✅ Verifies data integrity
- ✅ Updates your `.env` file

### Method 2: Manual Migration

For users who prefer manual control or need custom configurations:

#### Step 1: Export SQLite Data

```bash
# Export all data to JSON format
python -m theseus_insight.utils.db_migration.db_export \
    --source-db data/theseus.db \
    --output ./migration_backup.json \
    --include-vectors
```

**Expected output:**
```
🔍 Scanning SQLite database...
📊 Found 1,247 papers, 15 podcasts, 8 newsletters, 12 settings
💾 Exporting data...
✅ Export completed: migration_backup.json (45.2 MB)
📈 Export summary:
   - Papers: 1,247 (with embeddings)
   - Podcasts: 15 
   - Newsletters: 8
   - Settings: 12 (encrypted)
```

#### Step 2: Set Up PostgreSQL

If you haven't already, set up PostgreSQL:
- [Local PostgreSQL Setup](postgresql_setup.md)
- [Docker PostgreSQL Setup](docker_postgresql.md)

#### Step 3: Update Environment Variables

Update your `.env` file:

```bash
# Change from SQLite
# DATABASE_URL=data/theseus.db

# To PostgreSQL
DATABASE_URL=postgresql://username:password@localhost:5432/theseus_insight
```

#### Step 4: Import Data to PostgreSQL

```bash
# Import the exported data
python -m theseus_insight.utils.db_migration.db_import \
    --input ./migration_backup.json \
    --verify-vectors
```

**Expected output:**
```
🔍 Connecting to PostgreSQL...
🏗️  Creating schema with pgvector...
📊 Importing 1,247 papers...
🧠 Importing vector embeddings...
🎧 Importing 15 podcasts...
📧 Importing 8 newsletters...
⚙️  Importing 12 settings...
🔍 Building search indexes...
✅ Import completed successfully!
📈 Verification: All data imported correctly
```

#### Step 5: Verify Migration

```bash
# Run verification script
python -m theseus_insight.utils.db_migration.verify_migration \
    --source-db data/theseus.db \
    --verify-embeddings
```

---

## Data Preservation

### What Gets Migrated

✅ **Papers Table**
- Paper metadata (title, abstract, authors, arxiv_id, etc.)
- Publication dates and URLs
- Research categories and keywords
- Generated summaries
- Full-text content

✅ **Vector Embeddings**
- All paper embeddings (preserving exact numerical values)
- Embedding dimensions and model metadata
- Search vector indexes

✅ **Generated Content**
- Podcast episodes with metadata
- Newsletter content and dates
- Generated scripts and summaries

✅ **Settings & Configuration**
- Encrypted API credentials
- Application settings
- Research interests and orchestration configs

✅ **Indexes & Performance**
- Full-text search indexes (migrated to PostgreSQL)
- Vector similarity indexes (pgvector)
- Primary keys and foreign key relationships

### Type Conversions

The migration automatically handles SQLite to PostgreSQL type conversions:

| SQLite Type | PostgreSQL Type | Notes |
|-------------|-----------------|-------|
| `INTEGER` | `SERIAL`/`INTEGER` | Auto-increment preserved |
| `TEXT` | `TEXT`/`VARCHAR` | Full UTF-8 support |
| `BLOB` | `VECTOR` | Embeddings converted to pgvector |
| `REAL` | `REAL`/`NUMERIC` | Floating point precision preserved |
| `DATETIME` | `TIMESTAMP` | Timezone handling improved |

---

## Post-Migration Steps

### 1. Test Application Startup

```bash
# Start the application
uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000

# Check startup logs for any errors
# Should see: "Connected to PostgreSQL database"
```

### 2. Verify Data in UI

1. **Open the application**: http://localhost:8000
2. **Check Papers tab**: Verify your papers are loaded
3. **Test search**: Perform a semantic similarity search
4. **Check settings**: Verify API credentials are preserved
5. **Test generation**: Try generating a small newsletter/podcast

### 3. Performance Optimization

After migration, optimize PostgreSQL for your workload:

```sql
-- Connect to your database
psql postgresql://username:password@localhost:5432/theseus_insight

-- Analyze tables for query optimization
ANALYZE papers;
ANALYZE podcasts;
ANALYZE newsletters;

-- Check vector index status
\d+ papers;
-- Should show pgvector indexes on embedding column
```

### 4. Update Backup Scripts

Update any backup scripts to use PostgreSQL:

```bash
# Old SQLite backup
# cp data/theseus.db backups/

# New PostgreSQL backup
pg_dump postgresql://username:password@localhost:5432/theseus_insight > backup.sql
```

---

## Troubleshooting

### Common Issues

#### Database Connection Errors

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solutions:**
1. Verify PostgreSQL is running: `pg_ctl status`
2. Check connection string format: `postgresql://user:pass@host:port/db`
3. Test connection manually: `psql postgresql://...`
4. Check firewall/network settings

#### pgvector Extension Missing

**Error**: `UndefinedFile: extension "vector" is not available`

**Solutions:**
1. Install pgvector: See [PostgreSQL Setup Guide](postgresql_setup.md)
2. Enable extension: `CREATE EXTENSION vector;`
3. Verify installation: `SELECT * FROM pg_extension WHERE extname = 'vector';`

#### Embedding Import Failures

**Error**: `could not parse vector value` or `dimension mismatch`

**Solutions:**
1. Re-export with `--include-vectors` flag
2. Check embedding dimensions: Should be 1536 for OpenAI
3. Verify no corrupted embeddings in source database

#### Memory Issues During Large Migrations

**Error**: `MemoryError` or slow performance with large databases

**Solutions:**
1. Increase PostgreSQL memory settings:
   ```sql
   ALTER SYSTEM SET shared_buffers = '1GB';
   ALTER SYSTEM SET work_mem = '256MB';
   SELECT pg_reload_conf();
   ```
2. Use batch import mode:
   ```bash
   python -m theseus_insight.utils.db_migration.db_import \
       --input ./migration_backup.json \
       --batch-size 100
   ```

#### Permission Issues

**Error**: `permission denied for table papers`

**Solutions:**
1. Grant proper permissions:
   ```sql
   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
   GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_user;
   ```
2. Check database owner: `\l` in psql
3. Verify user has CREATEDB privilege

---

## Verification Checklist

After migration, verify these key areas:

### Data Integrity
- [ ] Paper count matches original database
- [ ] All embeddings preserved (check random samples)
- [ ] Settings and API keys accessible
- [ ] Generated content (podcasts/newsletters) present

### Functionality Tests
- [ ] Application starts without errors
- [ ] Search functionality works (semantic + keyword)
- [ ] Can generate new embeddings
- [ ] Mind-map generation works
- [ ] Can create new podcasts/newsletters

### Performance Tests
- [ ] Search queries return results quickly (< 2 seconds)
- [ ] Vector similarity search performs well
- [ ] Database operations feel responsive
- [ ] No memory leaks or connection issues

---

## Rollback Plan

If you need to rollback to SQLite:

### Immediate Rollback

1. **Stop the application**
2. **Restore original `.env`**:
   ```bash
   # Change back to SQLite
   DATABASE_URL=data/theseus.db
   ```
3. **Restore backup database**:
   ```bash
   cp data/theseus_backup_YYYYMMDD.db data/theseus.db
   ```
4. **Restart application**

### Export from PostgreSQL (for later rollback)

```bash
# Export from PostgreSQL to SQLite format
python -m theseus_insight.utils.db_migration.export_to_sqlite \
    --output ./postgresql_backup.db
```

---

## Performance Expectations

### Before Migration (SQLite)
- **Search**: 0.5-2 seconds for similarity search
- **Storage**: Single file database
- **Concurrency**: Limited concurrent access
- **Scalability**: Works well up to ~10K papers

### After Migration (PostgreSQL)
- **Search**: 0.1-0.5 seconds for similarity search
- **Storage**: Distributed with proper indexing
- **Concurrency**: Full multi-user support
- **Scalability**: Handles 100K+ papers efficiently
- **Features**: Advanced full-text search, better analytics

---

## Getting Help

If you encounter issues during migration:

1. **Check logs**: Look for specific error messages
2. **Verify prerequisites**: Ensure PostgreSQL and pgvector are properly installed
3. **Test connections**: Verify you can connect to PostgreSQL manually
4. **Review this guide**: Double-check each step
5. **Create an issue**: Include error messages and system details

**Support Resources:**
- [PostgreSQL Setup Guide](postgresql_setup.md)
- [Docker PostgreSQL Guide](docker_postgresql.md)
- [Database Specification](db_spec.md)
- [Embedding Functionality Guide](embedding_functionality_README.md)

---

## Migration Complete! 🎉

Once your migration is successful, you'll have:
- ✅ **Enhanced Performance**: Faster search and better scalability
- ✅ **Advanced Features**: PostgreSQL full-text search with pgvector
- ✅ **Better Concurrency**: Multi-user support for production deployments
- ✅ **Preserved Data**: All your research papers and generated content intact
- ✅ **Future-Ready**: Foundation for advanced analytics and features

Welcome to PostgreSQL-powered Theseus Insight! 