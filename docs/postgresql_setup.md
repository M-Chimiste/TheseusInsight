# PostgreSQL Setup Guide

This guide covers installing and configuring PostgreSQL 14+ with the pgvector extension for Theseus Insight. PostgreSQL provides enhanced performance, better scalability, and advanced search capabilities compared to SQLite.

## Overview

**What You'll Install:**
- **PostgreSQL 14+**: Core database server
- **pgvector extension**: Vector similarity search capabilities
- **Database and user**: Configured for Theseus Insight

**Time Required**: 15-30 minutes depending on your platform

---

## Quick Setup Options

### Option 1: Homebrew (macOS - Recommended)
```bash
# Install PostgreSQL and pgvector
brew install postgresql@14 pgvector

# Start PostgreSQL service  
brew services start postgresql@14

# Create database and user
createdb theseus_insight
psql theseus_insight -c "CREATE EXTENSION vector;"
```

### Option 2: Docker (All Platforms)
```bash
# Run PostgreSQL with pgvector in Docker
docker run -d \
    --name theseus-postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=theseus \
    -p 5432:5432 \
    pgvector/pgvector:pg14

# Test connection
psql postgresql://postgres:postgres@localhost:5432/theseus
```

### Option 3: Ubuntu/Debian
```bash
# Add PostgreSQL APT repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update

# Install PostgreSQL
sudo apt-get install postgresql-14 postgresql-contrib

# Install pgvector (see detailed steps below)
```

Continue reading for detailed platform-specific instructions and configuration.

---

## Platform-Specific Installation

### macOS Installation

#### Method 1: Homebrew (Recommended)

**Step 1: Install PostgreSQL**
```bash
# Install PostgreSQL 14
brew install postgresql@14

# Start PostgreSQL service
brew services start postgresql@14

# Add PostgreSQL to your PATH (add to ~/.zshrc or ~/.bash_profile)
export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"
```

**Step 2: Install pgvector**
```bash
# Install pgvector
brew install pgvector

# Verify installation
brew list pgvector
```

**Step 3: Create Database**
```bash
# Create the database
createdb theseus_insight

# Connect and enable pgvector
psql theseus_insight
```

```sql
-- Enable pgvector extension
CREATE EXTENSION vector;

-- Create user for Theseus Insight
CREATE USER theseus_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE theseus_insight TO theseus_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO theseus_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO theseus_user;

-- Exit psql
\q
```

#### Method 2: PostgreSQL.app (GUI Option)

1. **Download Postgres.app** from [postgresapp.com](https://postgresapp.com/)
2. **Install and run** the application
3. **Add to PATH**: Add `/Applications/Postgres.app/Contents/Versions/14/bin` to your PATH
4. **Install pgvector manually** (see pgvector section below)

### Linux Installation (Ubuntu/Debian)

**Step 1: Install PostgreSQL**
```bash
# Update package list
sudo apt update

# Add PostgreSQL APT repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'

# Import repository signing key
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# Update package list
sudo apt update

# Install PostgreSQL 14
sudo apt install postgresql-14 postgresql-contrib-14 postgresql-server-dev-14
```

**Step 2: Configure PostgreSQL**
```bash
# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Switch to postgres user
sudo -i -u postgres

# Create database and user
createdb theseus_insight
psql
```

```sql
-- Create user for Theseus Insight
CREATE USER theseus_user WITH PASSWORD 'secure_password';
ALTER ROLE theseus_user CREATEDB;
GRANT ALL PRIVILEGES ON DATABASE theseus_insight TO theseus_user;

-- Connect to the database
\c theseus_insight

-- Grant privileges on schema
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO theseus_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO theseus_user;
GRANT CREATE ON SCHEMA public TO theseus_user;

-- Exit psql and return to your user
\q
exit
```

**Step 3: Install pgvector**
```bash
# Install dependencies
sudo apt install git build-essential

# Clone and build pgvector
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector

# Build and install
make
sudo make install

# Enable extension in your database
psql -U theseus_user -d theseus_insight -h localhost
```

```sql
CREATE EXTENSION vector;
\q
```

### Linux Installation (CentOS/RHEL/Fedora)

**Step 1: Install PostgreSQL**
```bash
# Install PostgreSQL 14 repository
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/F-36-x86_64/pgdg-fedora-repo-latest.noarch.rpm

# Install PostgreSQL
sudo dnf install -y postgresql14-server postgresql14-contrib postgresql14-devel

# Initialize database
sudo /usr/pgsql-14/bin/postgresql-14-setup initdb

# Start and enable service
sudo systemctl enable --now postgresql-14
```

**Step 2: Configure Authentication**
```bash
# Edit pg_hba.conf for local connections
sudo nano /var/lib/pgsql/14/data/pg_hba.conf

# Change this line:
# local   all             all                                     peer
# To:
# local   all             all                                     md5

# Restart PostgreSQL
sudo systemctl restart postgresql-14
```

**Step 3: Create Database and Install pgvector**
```bash
# Switch to postgres user
sudo -i -u postgres

# Set password for postgres user
psql -c "ALTER USER postgres PASSWORD 'postgres';"

# Create database
createdb theseus_insight

# Install pgvector dependencies
sudo dnf groupinstall -y "Development Tools"

# Clone and build pgvector
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Enable extension
psql theseus_insight -c "CREATE EXTENSION vector;"
```

### Windows Installation

**Step 1: Install PostgreSQL**
1. **Download** PostgreSQL installer from [postgresql.org](https://www.postgresql.org/download/windows/)
2. **Run installer** and follow the setup wizard
3. **Remember** the password you set for the postgres user
4. **Add PostgreSQL to PATH**: Add `C:\Program Files\PostgreSQL\14\bin` to your system PATH

**Step 2: Install Build Tools**
1. **Install Visual Studio Build Tools** or Visual Studio Community
2. **Install Git for Windows** if not already installed

**Step 3: Install pgvector**
```cmd
REM Open Command Prompt as Administrator

REM Clone pgvector
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector

REM Build (requires Visual Studio Build Tools)
nmake /F Makefile.win
nmake /F Makefile.win install
```

**Step 4: Create Database**
```cmd
REM Create database
createdb -U postgres theseus_insight

REM Connect and enable extension
psql -U postgres -d theseus_insight
```

```sql
-- Enable pgvector extension
CREATE EXTENSION vector;

-- Create user
CREATE USER theseus_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE theseus_insight TO theseus_user;

\q
```

---

## pgvector Extension Setup

### What is pgvector?

pgvector is a PostgreSQL extension that adds vector similarity search capabilities, essential for Theseus Insight's semantic search features.

### Installation Methods

#### Method 1: Package Manager (Easiest)

**macOS (Homebrew):**
```bash
brew install pgvector
```

**Ubuntu/Debian:**
```bash
# Add pgvector repository
curl -fsSL https://packagecloud.io/pgvector/pgvector/gpgkey | sudo apt-key add -
echo "deb https://packagecloud.io/pgvector/pgvector/ubuntu/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/pgvector.list
sudo apt update
sudo apt install postgresql-14-pgvector
```

#### Method 2: Compile from Source

**Linux/macOS:**
```bash
# Install dependencies
# Ubuntu/Debian: sudo apt install git build-essential postgresql-server-dev-14
# macOS: xcode-select --install

# Clone and build
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Restart PostgreSQL
sudo systemctl restart postgresql  # Linux
brew services restart postgresql@14  # macOS
```

### Enable pgvector Extension

For each database that will use vector search:

```sql
-- Connect to your database
psql postgresql://username:password@localhost:5432/theseus_insight

-- Enable the extension
CREATE EXTENSION vector;

-- Verify installation
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Check available vector functions
\df *vector*
```

Expected output should show the vector extension is installed and various vector functions are available.

---

## Database Configuration

### Create Optimized Configuration

Create a custom PostgreSQL configuration optimized for Theseus Insight:

```bash
# Find your postgresql.conf file
sudo find /var -name "postgresql.conf" 2>/dev/null
# or
sudo find /opt -name "postgresql.conf" 2>/dev/null
```

**Edit postgresql.conf:**
```bash
sudo nano /path/to/postgresql.conf
```

**Add/modify these settings:**
```ini
# Memory settings
shared_buffers = 256MB                 # 25% of system RAM for small systems
work_mem = 64MB                        # Memory for sorting and joins
maintenance_work_mem = 128MB           # Memory for maintenance operations

# Connection settings
max_connections = 100                  # Adjust based on your needs

# Performance settings for vector operations
random_page_cost = 1.1                 # Optimize for SSD
effective_cache_size = 1GB             # Estimate of OS cache

# Logging (optional, for debugging)
log_statement = 'mod'                  # Log modifications
log_min_duration_statement = 1000      # Log slow queries (1 second+)
```

**Restart PostgreSQL:**
```bash
# Linux
sudo systemctl restart postgresql

# macOS
brew services restart postgresql@14
```

### Set Up Database User

Create a dedicated user for Theseus Insight:

```sql
-- Connect as superuser
psql postgresql://postgres:postgres@localhost:5432/postgres

-- Create user
CREATE USER theseus_user WITH PASSWORD 'your_secure_password';

-- Create database
CREATE DATABASE theseus_insight OWNER theseus_user;

-- Grant necessary privileges
GRANT ALL PRIVILEGES ON DATABASE theseus_insight TO theseus_user;

-- Connect to the new database
\c theseus_insight

-- Grant schema privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO theseus_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO theseus_user;
GRANT CREATE ON SCHEMA public TO theseus_user;

-- Enable pgvector extension
CREATE EXTENSION vector;

-- Verify setup
\l    -- List databases
\du   -- List users
```

---

## Configuration for Theseus Insight

### Environment Variables

Update your `.env` file:

```bash
# PostgreSQL connection
DATABASE_URL=postgresql://theseus_user:your_secure_password@localhost:5432/theseus_insight

# Optional: Connection pool settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=30
```

### Connection String Examples

**Local Development:**
```bash
DATABASE_URL=postgresql://theseus_user:password@localhost:5432/theseus_insight
```

**Production (with SSL):**
```bash
DATABASE_URL=postgresql://theseus_user:password@prod-server:5432/theseus_insight?sslmode=require
```

**Docker Compose:**
```bash
DATABASE_URL=postgresql://theseus_user:password@postgres:5432/theseus_insight
```

**Cloud Provider Examples:**
```bash
# AWS RDS
DATABASE_URL=postgresql://username:password@myinstance.123456789012.us-east-1.rds.amazonaws.com:5432/theseus_insight

# Google Cloud SQL
DATABASE_URL=postgresql://username:password@/theseus_insight?host=/cloudsql/project:region:instance

# Azure Database
DATABASE_URL=postgresql://username%40servername:password@servername.postgres.database.azure.com:5432/theseus_insight?sslmode=require
```

---

## Testing Your Setup

### Basic Connection Test

```bash
# Test connection with psql
psql postgresql://theseus_user:password@localhost:5432/theseus_insight

# Should connect successfully and show:
# psql (14.x)
# Type "help" for help.
# theseus_insight=>
```

### Test pgvector Functionality

```sql
-- Create a test table with vector column
CREATE TABLE test_vectors (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding VECTOR(1536)  -- OpenAI embedding dimension
);

-- Insert test data
INSERT INTO test_vectors (content, embedding) 
VALUES ('test', ARRAY[0.1, 0.2, 0.3]::REAL[]);

-- Test similarity search
SELECT content, embedding <=> ARRAY[0.1, 0.2, 0.3]::REAL[] AS distance 
FROM test_vectors 
ORDER BY distance 
LIMIT 5;

-- Clean up
DROP TABLE test_vectors;
```

### Test Theseus Insight Connection

```bash
# In your Theseus Insight directory
python -c "
from theseus_insight.data_access.base import get_cursor
cursor = get_cursor()
print('✅ Successfully connected to PostgreSQL!')
cursor.execute('SELECT version();')
print(f'PostgreSQL version: {cursor.fetchone()[0]}')
cursor.execute('SELECT * FROM pg_extension WHERE extname = \"vector\";')
if cursor.fetchone():
    print('✅ pgvector extension is installed!')
else:
    print('❌ pgvector extension not found!')
"
```

---

## Performance Optimization

### Index Configuration

After importing your data, create appropriate indexes:

```sql
-- Connect to your database
psql postgresql://theseus_user:password@localhost:5432/theseus_insight

-- Create vector index for similarity search (after data import)
CREATE INDEX CONCURRENTLY ON papers USING ivfflat (embedding vector_cosine_ops) 
WITH (lists = 100);

-- Create full-text search indexes
CREATE INDEX CONCURRENTLY ON papers USING gin(to_tsvector('english', title));
CREATE INDEX CONCURRENTLY ON papers USING gin(to_tsvector('english', abstract));

-- Analyze tables for query planning
ANALYZE papers;
ANALYZE podcasts;
ANALYZE newsletters;
ANALYZE settings;
```

### Monitor Performance

```sql
-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch 
FROM pg_stat_user_indexes 
ORDER BY idx_scan DESC;

-- Check table sizes
SELECT schemaname, tablename, 
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Monitor vector query performance
EXPLAIN (ANALYZE, BUFFERS) 
SELECT id, title, embedding <=> ARRAY[0.1, 0.2, ...]::REAL[] AS distance 
FROM papers 
ORDER BY distance 
LIMIT 10;
```

---

## Backup and Maintenance

### Regular Backups

```bash
# Create backup script
cat > backup_theseus.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="theseus_insight"

# Create backup
pg_dump postgresql://theseus_user:password@localhost:5432/$DB_NAME \
    > "$BACKUP_DIR/theseus_backup_$DATE.sql"

# Compress backup
gzip "$BACKUP_DIR/theseus_backup_$DATE.sql"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "theseus_backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: theseus_backup_$DATE.sql.gz"
EOF

# Make executable
chmod +x backup_theseus.sh

# Run manually or add to crontab
./backup_theseus.sh
```

### Automatic Maintenance

```bash
# Add to crontab for weekly maintenance
crontab -e

# Add this line for weekly vacuum and analyze
0 2 * * 0 psql postgresql://theseus_user:password@localhost:5432/theseus_insight -c "VACUUM ANALYZE;"
```

---

## Troubleshooting

### Common Issues

#### PostgreSQL Won't Start

**Error**: Service fails to start

**Solutions:**
```bash
# Check status and logs
sudo systemctl status postgresql
journalctl -u postgresql

# Check port conflicts
sudo netstat -tulpn | grep :5432

# Check disk space
df -h

# Reset data directory (last resort)
sudo -u postgres /usr/pgsql-14/bin/initdb -D /var/lib/pgsql/14/data/
```

#### pgvector Installation Issues

**Error**: `extension "vector" is not available`

**Solutions:**
1. **Verify compilation:**
   ```bash
   # Recompile pgvector
   cd pgvector
   make clean
   make
   sudo make install
   sudo systemctl restart postgresql
   ```

2. **Check installation path:**
   ```bash
   sudo find /usr -name "vector.so" 2>/dev/null
   # Should be in PostgreSQL extensions directory
   ```

3. **Verify PostgreSQL version compatibility:**
   ```bash
   psql -c "SELECT version();"
   # Ensure you're using PostgreSQL 14+
   ```

#### Connection Issues

**Error**: `psycopg2.OperationalError: could not connect to server`

**Solutions:**
1. **Check PostgreSQL is running:**
   ```bash
   sudo systemctl status postgresql
   ```

2. **Verify connection details:**
   ```bash
   psql postgresql://username:password@localhost:5432/database_name
   ```

3. **Check firewall:**
   ```bash
   sudo ufw allow 5432  # Ubuntu
   sudo firewall-cmd --add-port=5432/tcp --permanent  # CentOS/RHEL
   ```

4. **Check pg_hba.conf:**
   ```bash
   sudo nano /var/lib/pgsql/14/data/pg_hba.conf
   # Ensure local connections are allowed
   ```

#### Permission Issues

**Error**: `permission denied for table papers`

**Solutions:**
```sql
-- Connect as superuser
psql postgresql://postgres:postgres@localhost:5432/theseus_insight

-- Grant all necessary permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO theseus_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO theseus_user;
```

---

## Security Considerations

### Database Security

1. **Use strong passwords:**
   ```sql
   ALTER USER theseus_user PASSWORD 'very_strong_password_123!@#';
   ```

2. **Restrict network access:**
   ```bash
   # Edit postgresql.conf
   listen_addresses = 'localhost'  # Only local connections
   ```

3. **Use SSL in production:**
   ```bash
   # In postgresql.conf
   ssl = on
   ssl_cert_file = 'server.crt'
   ssl_key_file = 'server.key'
   ```

4. **Regular security updates:**
   ```bash
   # Keep PostgreSQL updated
   sudo apt update && sudo apt upgrade postgresql-14
   ```

### Connection Security

1. **Use environment variables for credentials**
2. **Never commit credentials to version control**
3. **Use connection pooling in production**
4. **Monitor connection logs for suspicious activity**

---

## Production Deployment

### Recommended Hardware

**Minimum Requirements:**
- **CPU**: 2 cores
- **RAM**: 4GB (2GB for PostgreSQL)
- **Storage**: 50GB SSD
- **Network**: Stable internet connection

**Recommended for Large Datasets:**
- **CPU**: 4+ cores
- **RAM**: 8GB+ (4GB+ for PostgreSQL)
- **Storage**: 100GB+ NVMe SSD
- **Network**: High-bandwidth connection

### Production Configuration

```ini
# postgresql.conf for production
shared_buffers = 2GB                   # 25% of system RAM
work_mem = 256MB
maintenance_work_mem = 512MB
effective_cache_size = 6GB             # 75% of system RAM
max_connections = 200

# Logging
log_destination = 'csvlog'
logging_collector = on
log_directory = 'pg_log'
log_rotation_age = 1d
log_rotation_size = 100MB

# Performance
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
```

### Monitoring

Set up monitoring for production deployments:

```bash
# Install pg_stat_statements extension
psql -c "CREATE EXTENSION pg_stat_statements;"

# Monitor queries
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
```

---

## Next Steps

After completing PostgreSQL setup:

1. **Test the connection** with Theseus Insight
2. **Import existing data** using the [Migration Guide](migration_guide.md)
3. **Configure application settings** in your `.env` file
4. **Set up regular backups** and monitoring
5. **Optimize performance** based on your usage patterns

**Related Documentation:**
- [Migration Guide](migration_guide.md) - Moving from SQLite to PostgreSQL
- [Docker PostgreSQL Guide](docker_postgresql.md) - Running PostgreSQL in containers
- [Database Specification](db_spec.md) - Theseus Insight database schema
- [Installation README](installation_README.md) - Complete application setup

---

## Getting Help

If you encounter issues:

1. **Check the troubleshooting section** above
2. **Verify all prerequisites** are met
3. **Test connections manually** with psql
4. **Check PostgreSQL logs** for error messages
5. **Create an issue** with detailed error information

**PostgreSQL Resources:**
- [Official PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [pgvector GitHub Repository](https://github.com/pgvector/pgvector)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)

Welcome to high-performance PostgreSQL-powered Theseus Insight! 🚀 