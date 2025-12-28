# Docker PostgreSQL Guide

This guide covers running PostgreSQL with pgvector in Docker containers for Theseus Insight. Docker provides an easy, consistent way to deploy PostgreSQL across different environments without complex local installations.

## Overview

**Deployment Options:**
- **Full Docker Compose**: PostgreSQL + Theseus Insight application
- **PostgreSQL Only**: Database in Docker, application running locally
- **Development Setup**: Quick start for development work
- **Production Deployment**: Optimized configuration for production use

**Benefits of Docker PostgreSQL:**
- ✅ **Easy Setup**: No complex PostgreSQL installation
- ✅ **Consistent Environment**: Same setup across development/production
- ✅ **Built-in pgvector**: Pre-configured with vector extensions
- ✅ **Easy Backup/Restore**: Container volumes for data persistence
- ✅ **Scalable**: Easy to upgrade or change configurations

---

## Quick Start Options

### Option 1: Full Stack with Docker Compose (Recommended)
```bash
# Clone Theseus Insight repository
git clone https://github.com/M-Chimiste/TheseusInsight.git
cd TheseusInsight

# Create .env file
cp config/external-storage.env.template .env

# Start everything (PostgreSQL + Application)
docker compose up --build

# Access the application at http://localhost:8000
```

### Option 2: PostgreSQL Only (Development)
```bash
# Run just PostgreSQL with pgvector
docker run -d \
    --name theseus-postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=theseus \
    -p 5432:5432 \
    -v theseus-postgres-data:/var/lib/postgresql/data \
    pgvector/pgvector:pg14

# Connect from your local application
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/theseus
```

### Option 3: Custom Configuration
```bash
# Use custom Docker Compose configuration
docker-compose -f docker-compose.yml -f docker-compose.postgres.yml up
```

---

## Docker Compose Configurations

### Standard Configuration (docker-compose.yml)

The default `docker-compose.yml` includes PostgreSQL with pgvector:

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg14
    container_name: theseus-postgres
    environment:
      POSTGRES_DB: theseus
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=C --lc-ctype=C"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_schema_postgres.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d theseus"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

  app:
    build: .
    container_name: theseus-app
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/theseus
      - RUNNING_IN_DOCKER=true
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env
    command: ["uvicorn", "theseus_insight.main:app", "--host", "0.0.0.0", "--port", "8000"]

volumes:
  postgres_data:
```

### Development Configuration

For development with external database access:

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg14
    container_name: theseus-postgres-dev
    environment:
      POSTGRES_DB: theseus_dev
      POSTGRES_USER: theseus_user
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_dev_data:/var/lib/postgresql/data
      - ./scripts/init_schema_postgres.sql:/docker-entrypoint-initdb.d/init.sql
    command: >
      postgres 
      -c log_statement=all 
      -c log_min_duration_statement=0
      -c shared_buffers=256MB
      -c work_mem=64MB

volumes:
  postgres_dev_data:
```

```bash
# Start development database
docker-compose -f docker-compose.dev.yml up postgres

# Run application locally
export DATABASE_URL=postgresql://theseus_user:dev_password@localhost:5432/theseus_dev
uvicorn theseus_insight.main:app --reload
```

### Production Configuration

Optimized for production deployments:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg14
    container_name: theseus-postgres-prod
    restart: always
    environment:
      POSTGRES_DB: theseus
      POSTGRES_USER: theseus_user
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data
      - ./postgres.conf:/etc/postgresql/postgresql.conf
      - ./scripts/init_schema_postgres.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "127.0.0.1:5432:5432"  # Only local access
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U theseus_user -d theseus"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  app:
    build: 
      context: .
      dockerfile: Dockerfile.prod
    container_name: theseus-app-prod
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql://theseus_user:$(cat /run/secrets/postgres_password)@postgres:5432/theseus
      - RUNNING_IN_DOCKER=true
      - DEBUG=false
    secrets:
      - postgres_password
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data:ro
      - ./.env:/app/.env:ro
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt

volumes:
  postgres_prod_data:
    driver: local
```

---

## PostgreSQL Container Images

### Official Images with pgvector

#### pgvector/pgvector (Recommended)
```bash
# Latest PostgreSQL 14 with pgvector
docker pull pgvector/pgvector:pg14

# PostgreSQL 15 with pgvector
docker pull pgvector/pgvector:pg15

# Latest version
docker pull pgvector/pgvector:latest
```

#### ankane/pgvector (Alternative)
```bash
# Alternative pgvector image
docker pull ankane/pgvector

# Run with custom configuration
docker run -d \
    --name postgres-vector \
    -e POSTGRES_PASSWORD=postgres \
    -p 5432:5432 \
    ankane/pgvector
```

### Custom Dockerfile

For specialized requirements, create a custom PostgreSQL image:

```dockerfile
# Dockerfile.postgres
FROM postgres:14

# Install dependencies
RUN apt-get update \
    && apt-get install -y \
        git \
        build-essential \
        postgresql-server-dev-14 \
    && rm -rf /var/lib/apt/lists/*

# Install pgvector
RUN cd /tmp \
    && git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git \
    && cd pgvector \
    && make \
    && make install \
    && cd / \
    && rm -rf /tmp/pgvector

# Add initialization script
COPY init-pgvector.sql /docker-entrypoint-initdb.d/

# Custom PostgreSQL configuration
COPY postgresql.conf /etc/postgresql/postgresql.conf

# Set custom command
CMD ["postgres", "-c", "config_file=/etc/postgresql/postgresql.conf"]
```

```sql
-- init-pgvector.sql
CREATE EXTENSION IF NOT EXISTS vector;

-- Create application user
CREATE USER theseus_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE postgres TO theseus_user;

-- Grant schema privileges
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO theseus_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO theseus_user;
GRANT CREATE ON SCHEMA public TO theseus_user;
```

```bash
# Build custom image
docker build -f Dockerfile.postgres -t theseus-postgres:latest .

# Run custom image
docker run -d \
    --name theseus-postgres-custom \
    -e POSTGRES_DB=theseus \
    -p 5432:5432 \
    -v postgres_data:/var/lib/postgresql/data \
    theseus-postgres:latest
```

---

## Configuration and Environment Variables

### Essential Environment Variables

```bash
# Database configuration
POSTGRES_DB=theseus                    # Database name
POSTGRES_USER=theseus_user            # Database user
POSTGRES_PASSWORD=secure_password      # Database password

# Advanced configuration
POSTGRES_INITDB_ARGS="--encoding=UTF-8 --lc-collate=en_US.utf8 --lc-ctype=en_US.utf8"
POSTGRES_HOST_AUTH_METHOD=md5         # Authentication method
POSTGRES_SHARED_PRELOAD_LIBRARIES=vector  # Load pgvector on startup

# Performance tuning
POSTGRES_SHARED_BUFFERS=256MB         # Memory for shared buffers
POSTGRES_WORK_MEM=64MB               # Memory for sorting/joins
POSTGRES_MAINTENANCE_WORK_MEM=128MB  # Memory for maintenance operations
```

### Custom PostgreSQL Configuration

Create `postgres.conf` for production optimization:

```ini
# postgres.conf
# Memory settings
shared_buffers = 512MB                 # 25% of available RAM
work_mem = 128MB                       # Memory for query operations
maintenance_work_mem = 256MB           # Memory for maintenance tasks
effective_cache_size = 2GB             # Estimate of OS cache

# Connection settings
max_connections = 200                  # Maximum concurrent connections
listen_addresses = '*'                 # Listen on all interfaces

# Performance settings
random_page_cost = 1.1                 # Optimize for SSD storage
effective_io_concurrency = 2           # Concurrent I/O operations

# Logging (for debugging)
log_destination = 'stderr'
log_statement = 'mod'                  # Log data modifications
log_min_duration_statement = 1000      # Log slow queries (1 second+)
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '

# Vector-specific optimizations
shared_preload_libraries = 'vector'    # Load pgvector extension

# Checkpoint settings
checkpoint_completion_target = 0.9
wal_buffers = 16MB
checkpoint_timeout = 10min

# Query planner settings
default_statistics_target = 100
```

Mount the configuration file:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg14
    volumes:
      - ./postgres.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
```

---

## Data Persistence and Volumes

### Volume Types

#### Named Volumes (Recommended)
```yaml
services:
  postgres:
    image: pgvector/pgvector:pg14
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
    driver: local
```

#### Bind Mounts (Development)
```yaml
services:
  postgres:
    image: pgvector/pgvector:pg14
    volumes:
      - ./postgres_data:/var/lib/postgresql/data
```

#### External Volumes (Production)
```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/database/postgres
```

### Backup and Restore with Docker

#### Create Backups
```bash
# Backup database to file
docker exec theseus-postgres pg_dump -U postgres theseus > backup.sql

# Backup with compression
docker exec theseus-postgres pg_dump -U postgres -Fc theseus > backup.dump

# Backup specific tables
docker exec theseus-postgres pg_dump -U postgres -t papers -t podcasts theseus > partial_backup.sql
```

#### Restore Backups
```bash
# Restore from SQL file
docker exec -i theseus-postgres psql -U postgres theseus < backup.sql

# Restore from compressed dump
docker exec -i theseus-postgres pg_restore -U postgres -d theseus backup.dump

# Restore to new database
docker exec theseus-postgres createdb -U postgres theseus_restored
docker exec -i theseus-postgres psql -U postgres theseus_restored < backup.sql
```

#### Automated Backup Script
```bash
#!/bin/bash
# backup-postgres.sh

CONTAINER_NAME="theseus-postgres"
DB_NAME="theseus"
DB_USER="postgres"
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create backup
docker exec "$CONTAINER_NAME" pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$BACKUP_DIR/theseus_backup_$DATE.dump"

# Compress backup
gzip "$BACKUP_DIR/theseus_backup_$DATE.dump"

# Keep only last 7 days
find "$BACKUP_DIR" -name "theseus_backup_*.dump.gz" -mtime +7 -delete

echo "Backup completed: theseus_backup_$DATE.dump.gz"
```

---

## Security Configuration

### Basic Security

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg14
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password
    ports:
      - "127.0.0.1:5432:5432"  # Only localhost access
    
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
```

### SSL Configuration

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg14
    environment:
      POSTGRES_INITDB_ARGS: "--auth-host=md5"
    volumes:
      - ./ssl/server.crt:/var/lib/postgresql/server.crt:ro
      - ./ssl/server.key:/var/lib/postgresql/server.key:ro
      - ./postgres-ssl.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
```

```ini
# postgres-ssl.conf
ssl = on
ssl_cert_file = '/var/lib/postgresql/server.crt'
ssl_key_file = '/var/lib/postgresql/server.key'
ssl_prefer_server_ciphers = on
```

### Network Security

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg14
    networks:
      - theseus-network
    # No ports exposed to host
    
  app:
    build: .
    depends_on:
      - postgres
    networks:
      - theseus-network
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/theseus

networks:
  theseus-network:
    driver: bridge
    internal: false  # Set to true for complete isolation
```

---

## Monitoring and Logging

### Enable Query Logging

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg14
    environment:
      - POSTGRES_INITDB_ARGS=--auth-host=md5
    command: >
      postgres
      -c log_statement=all
      -c log_min_duration_statement=100
      -c log_connections=on
      -c log_disconnections=on
      -c log_duration=on
    volumes:
      - ./logs:/var/log/postgresql
```

### Health Checks

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg14
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d theseus"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
```

### Resource Monitoring

```bash
# Monitor container resource usage
docker stats theseus-postgres

# Check container logs
docker logs theseus-postgres

# Monitor database activity
docker exec -it theseus-postgres psql -U postgres -c "
SELECT 
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query 
FROM pg_stat_activity 
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';
"
```

---

## Development Workflows

### Local Development Setup

```bash
# Start PostgreSQL for development
docker-compose -f docker-compose.dev.yml up postgres -d

# Check connection
psql postgresql://theseus_user:dev_password@localhost:5432/theseus_dev

# Run application locally
export DATABASE_URL=postgresql://theseus_user:dev_password@localhost:5432/theseus_dev
python -m uvicorn theseus_insight.main:app --reload

# Stop when done
docker-compose -f docker-compose.dev.yml down
```

### Testing with Different PostgreSQL Versions

```bash
# Test with PostgreSQL 14
docker run -d --name pg14-test -e POSTGRES_PASSWORD=test pgvector/pgvector:pg14

# Test with PostgreSQL 15  
docker run -d --name pg15-test -e POSTGRES_PASSWORD=test pgvector/pgvector:pg15

# Run tests against different versions
export DATABASE_URL=postgresql://postgres:test@localhost:5432/postgres
python -m pytest tests/

# Cleanup
docker rm -f pg14-test pg15-test
```

### Database Migration Testing

```bash
# Start clean PostgreSQL instance
docker run -d --name migration-test \
    -e POSTGRES_PASSWORD=test \
    -e POSTGRES_DB=theseus_test \
    pgvector/pgvector:pg14

# Test migration scripts
export DATABASE_URL=postgresql://postgres:test@localhost:5432/theseus_test
python -m theseus_insight.utils.db_migration.db_import --input test_data.json

# Verify migration
docker exec migration-test psql -U postgres -d theseus_test -c "SELECT count(*) FROM papers;"

# Cleanup
docker rm -f migration-test
```

---

## Production Deployment

### Docker Swarm Deployment

```yaml
# docker-stack.yml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg14
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.role == manager
      resources:
        limits:
          memory: 2G
        reservations:
          memory: 1G
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets:
      - postgres_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - theseus-network

  app:
    image: theseus-insight:latest
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
      restart_policy:
        condition: on-failure
    depends_on:
      - postgres
    environment:
      - DATABASE_URL=postgresql://postgres:{{DOCKER-SECRET:postgres_password}}@postgres:5432/theseus
    networks:
      - theseus-network
    ports:
      - "8000:8000"

secrets:
  postgres_password:
    external: true

volumes:
  postgres_data:
    driver: local

networks:
  theseus-network:
    driver: overlay
    attachable: true
```

```bash
# Deploy to Docker Swarm
docker secret create postgres_password postgres_password.txt
docker stack deploy -c docker-stack.yml theseus
```

### Kubernetes Deployment

```yaml
# postgres-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: pgvector/pgvector:pg14
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        - name: POSTGRES_DB
          value: theseus
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
          requests:
            memory: "1Gi"
            cpu: "500m"
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc

---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432
  type: ClusterIP
```

---

## Troubleshooting

### Common Issues

#### Container Won't Start

**Error**: PostgreSQL container exits immediately

**Solutions:**
```bash
# Check container logs
docker logs theseus-postgres

# Common issues:
# 1. Data directory permissions
docker run -it --rm -v postgres_data:/data alpine chmod 700 /data

# 2. Port conflicts
docker ps | grep 5432
netstat -tulpn | grep 5432

# 3. Memory issues
docker stats theseus-postgres
```

#### pgvector Extension Missing

**Error**: `extension "vector" is not available`

**Solutions:**
```bash
# Verify image includes pgvector
docker run --rm pgvector/pgvector:pg14 psql --version

# Check available extensions
docker exec theseus-postgres psql -U postgres -c "SELECT * FROM pg_available_extensions WHERE name = 'vector';"

# Manually install if needed
docker exec -it theseus-postgres bash
apt-get update && apt-get install -y postgresql-14-pgvector
```

#### Connection Issues

**Error**: `could not connect to server`

**Solutions:**
```bash
# Check container is running
docker ps | grep postgres

# Test connection from host
psql postgresql://postgres:postgres@localhost:5432/theseus

# Check Docker networking
docker network ls
docker inspect bridge

# Test from another container
docker run --rm postgres:14 psql postgresql://postgres:postgres@host.docker.internal:5432/theseus
```

#### Performance Issues

**Error**: Slow query performance

**Solutions:**
```bash
# Monitor resource usage
docker stats theseus-postgres

# Check PostgreSQL configuration
docker exec theseus-postgres psql -U postgres -c "SHOW shared_buffers;"

# Analyze queries
docker exec theseus-postgres psql -U postgres -d theseus -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
"

# Create proper indexes
docker exec theseus-postgres psql -U postgres -d theseus -c "
CREATE INDEX CONCURRENTLY ON papers USING ivfflat (embedding vector_cosine_ops);
"
```

#### Data Persistence Issues

**Error**: Data lost after container restart

**Solutions:**
```bash
# Verify volume mounting
docker inspect theseus-postgres | grep -A 5 "Mounts"

# Check volume exists
docker volume ls | grep postgres

# Backup before troubleshooting
docker exec theseus-postgres pg_dump -U postgres theseus > emergency_backup.sql

# Recreate with proper volume
docker-compose down -v  # Warning: removes volumes
docker-compose up
```

---

## Best Practices

### Security Best Practices

1. **Use secrets for passwords:**
   ```yaml
   secrets:
     postgres_password:
       file: ./secrets/postgres_password.txt
   ```

2. **Limit network exposure:**
   ```yaml
   ports:
     - "127.0.0.1:5432:5432"  # Only localhost
   ```

3. **Use dedicated networks:**
   ```yaml
   networks:
     theseus-network:
       driver: bridge
   ```

4. **Regular security updates:**
   ```bash
   docker pull pgvector/pgvector:pg14
   docker-compose up -d postgres
   ```

### Performance Best Practices

1. **Allocate sufficient memory:**
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
       reservations:
         memory: 1G
   ```

2. **Use SSD storage:**
   ```yaml
   volumes:
     postgres_data:
       driver: local
       driver_opts:
         type: none
         o: bind
         device: /mnt/ssd/postgres
   ```

3. **Configure PostgreSQL properly:**
   ```ini
   shared_buffers = 25% of RAM
   work_mem = 64MB
   maintenance_work_mem = 256MB
   ```

4. **Monitor performance:**
   ```bash
   docker exec postgres psql -c "SELECT * FROM pg_stat_activity;"
   ```

### Backup Best Practices

1. **Automated backups:**
   ```bash
   # Add to crontab
   0 2 * * * /path/to/backup-postgres.sh
   ```

2. **Test restore procedures:**
   ```bash
   # Regular restore testing
   docker run --name restore-test pgvector/pgvector:pg14
   docker exec restore-test pg_restore backup.dump
   ```

3. **Multiple backup formats:**
   ```bash
   # SQL format for debugging
   pg_dump -U postgres theseus > backup.sql
   
   # Custom format for efficiency
   pg_dump -U postgres -Fc theseus > backup.dump
   ```

---

## Migration from Other Deployments

### From Local PostgreSQL to Docker

```bash
# 1. Backup existing data
pg_dump postgresql://user:pass@localhost:5432/theseus > local_backup.sql

# 2. Start Docker PostgreSQL
docker-compose up postgres -d

# 3. Import data
docker exec -i theseus-postgres psql -U postgres theseus < local_backup.sql

# 4. Update application configuration
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/theseus
```

### From SQLite to Docker PostgreSQL

```bash
# 1. Export SQLite data
python -m theseus_insight.utils.db_migration.db_export \
    --source-db data/theseus.db \
    --output sqlite_export.json

# 2. Start Docker PostgreSQL
docker-compose up postgres -d

# 3. Import to PostgreSQL
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/theseus
python -m theseus_insight.utils.db_migration.db_import \
    --input sqlite_export.json
```

---

## Getting Help

### Diagnostic Commands

```bash
# Container status
docker ps -a | grep postgres

# Container logs
docker logs theseus-postgres --tail 50

# Container resource usage
docker stats theseus-postgres --no-stream

# Database connection test
docker exec theseus-postgres pg_isready -U postgres

# Extension verification
docker exec theseus-postgres psql -U postgres -c "SELECT * FROM pg_extension;"
```

### Support Resources

- **Docker PostgreSQL Documentation**: [hub.docker.com/_/postgres](https://hub.docker.com/_/postgres)
- **pgvector Docker Image**: [hub.docker.com/r/pgvector/pgvector](https://hub.docker.com/r/pgvector/pgvector)
- **Docker Compose Documentation**: [docs.docker.com/compose/](https://docs.docker.com/compose/)
- **PostgreSQL Documentation**: [postgresql.org/docs/](https://www.postgresql.org/docs/)

### Related Guides

- [Migration Guide](migration_guide.md) - Moving from SQLite to PostgreSQL
- [PostgreSQL Setup Guide](postgresql_setup.md) - Local PostgreSQL installation
- [Database Specification](db_spec.md) - Theseus Insight database schema

---

## Summary

Docker provides an excellent way to run PostgreSQL with pgvector for Theseus Insight:

- ✅ **Easy Setup**: Pre-configured images with pgvector
- ✅ **Flexible Deployment**: Development to production ready
- ✅ **Data Persistence**: Reliable volume management
- ✅ **Scalable**: Easy to upgrade and configure
- ✅ **Secure**: Network isolation and secret management

Choose the deployment option that best fits your needs and follow the best practices for optimal performance and security.

Happy containerizing! 🐳 