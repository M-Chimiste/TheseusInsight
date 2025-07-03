# Theseus Insight Installation and Startup Scripts

This directory contains scripts to help you quickly install dependencies and start Theseus Insight on different operating systems.

## Quick Start

### macOS / Linux
```bash
# Make the script executable
chmod +x scripts/install-and-start.sh

# Install and start (full setup including PostgreSQL)
./scripts/install-and-start.sh
```

### Windows (Command Prompt)
```cmd
# Install and start (full setup including PostgreSQL)
scripts\install-and-start.bat
```

### Windows (PowerShell)
```powershell
# Install and start (full setup including PostgreSQL)
.\scripts\install-and-start.ps1
```

## Available Scripts

### 1. `install-and-start.sh` (macOS/Linux)
**Usage:**
```bash
./scripts/install-and-start.sh [OPTIONS]
```

**Options:**
- `--install-only` - Only install dependencies, don't start servers
- `--start-only` - Only start servers (skip installation)
- `--skip-db` - Skip PostgreSQL installation/setup
- `--help`, `-h` - Show help message

### 2. `install-and-start.bat` (Windows CMD)
**Usage:**
```cmd
scripts\install-and-start.bat [OPTIONS]
```

**Options:**
- `--install-only` - Only install dependencies, don't start servers
- `--start-only` - Only start servers (skip installation)
- `--skip-db` - Skip PostgreSQL installation/setup
- `--help`, `-h`, `/?` - Show help message

### 3. `install-and-start.ps1` (Windows PowerShell)
**Usage:**
```powershell
.\scripts\install-and-start.ps1 [OPTIONS]
```

**Options:**
- `-InstallOnly` - Only install dependencies, don't start servers
- `-StartOnly` - Only start servers (skip installation)
- `-SkipDB` - Skip PostgreSQL installation/setup
- `-Help` - Show help message

## What These Scripts Do

### Installation Phase
1. **Check System Requirements**
   - Verify Python 3.8+ is installed
   - Verify Node.js and npm are installed
   - Check PostgreSQL 14+ availability
   - Provide installation instructions if missing

2. **Setup PostgreSQL Database**
   - Install PostgreSQL and pgvector extension (if not present)
   - Create database and user for Theseus Insight
   - Initialize database schema
   - Configure optimal settings for vector search

3. **Create Directory Structure**
   - Create `data/` directory and subdirectories
   - Create `config/` directory
   - Ensure proper directory permissions

4. **Setup Python Environment**
   - Create Python virtual environment (`venv/`)
   - Activate the virtual environment
   - Upgrade pip to latest version
   - Install all Python dependencies from `requirements.txt`

5. **Setup Frontend**
   - Install npm dependencies from `package.json`
   - Build the React frontend using Vite

6. **Create Default Configuration**
   - Generate default `config/research_interests.txt` if not present
   - Set up database connection string in environment

### Startup Phase
1. **Verify Database Connection**
   - Test PostgreSQL connectivity
   - Ensure pgvector extension is available
   - Run database migrations if needed

2. **Start Backend Server**
   - Activate Python virtual environment
   - Start FastAPI server on `http://localhost:8000`
   - Enable auto-reload for development

3. **Start Frontend Development Server**
   - Start Vite development server on `http://localhost:5173`
   - Enable hot module replacement

4. **Provide Access Information**
   - Display URLs for frontend and backend
   - Show API documentation link
   - Explain how to stop the servers

## Prerequisites

### All Platforms
- **Python 3.8+** - Download from [python.org](https://www.python.org/downloads/)
- **Node.js 16+** - Download from [nodejs.org](https://nodejs.org/)
- **PostgreSQL 14+** - Database server with pgvector extension

### Platform-Specific Instructions

#### macOS
**Option 1: Using Homebrew (Recommended)**
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install all dependencies
brew install python3 node postgresql@14 pgvector

# Start PostgreSQL service
brew services start postgresql@14

# Add PostgreSQL to PATH (add to ~/.zshrc or ~/.bash_profile)
export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"
```

**Option 2: Download Installers**
- Download Python from [python.org](https://www.python.org/downloads/)
- Download Node.js from [nodejs.org](https://nodejs.org/)
- Download PostgreSQL from [postgresql.org](https://www.postgresql.org/download/macos/)
- Install pgvector manually (see detailed guide below)

#### Linux (Ubuntu/Debian)
```bash
# Update package index
sudo apt update

# Install Python and Node.js
sudo apt install python3 python3-pip python3-venv

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install PostgreSQL 14
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get install postgresql-14 postgresql-contrib-14 postgresql-server-dev-14

# Install pgvector
sudo apt install git build-essential
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector && make && sudo make install
cd .. && rm -rf pgvector

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### Linux (CentOS/RHEL)
```bash
# Install Python and development tools
sudo yum install python3 python3-pip

# Install Node.js
curl -fsSL https://rpm.nodesource.com/setup_lts.x | sudo bash -
sudo yum install nodejs

# Install PostgreSQL 14
sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/F-36-x86_64/pgdg-fedora-repo-latest.noarch.rpm
sudo dnf install -y postgresql14-server postgresql14-contrib postgresql14-devel

# Initialize and start PostgreSQL
sudo /usr/pgsql-14/bin/postgresql-14-setup initdb
sudo systemctl enable --now postgresql-14

# Install pgvector
sudo dnf groupinstall -y "Development Tools"
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector && make && sudo make install
cd .. && rm -rf pgvector
```

#### Windows
1. **Python:**
   - Download from [python.org](https://www.python.org/downloads/)
   - **Important:** Check "Add Python to PATH" during installation

2. **Node.js:**
   - Download from [nodejs.org](https://nodejs.org/)
   - Run the installer and follow prompts

3. **PostgreSQL:**
   - Download from [postgresql.org](https://www.postgresql.org/download/windows/)
   - Run installer with default settings
   - Remember the password for the postgres user
   - Add `C:\Program Files\PostgreSQL\14\bin` to your PATH

4. **pgvector Extension:**
   - Install Visual Studio Build Tools
   - Clone and compile pgvector (see detailed guide)
   - Or use pre-compiled binaries if available

## Database Setup

### Quick Database Setup

After installing PostgreSQL, create the database for Theseus Insight:

```bash
# Create database and user
createdb theseus_insight

# Connect to database
psql theseus_insight
```

```sql
-- Enable pgvector extension
CREATE EXTENSION vector;

-- Create user for Theseus Insight
CREATE USER theseus_user WITH PASSWORD 'secure_password_123';
GRANT ALL PRIVILEGES ON DATABASE theseus_insight TO theseus_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO theseus_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO theseus_user;
GRANT CREATE ON SCHEMA public TO theseus_user;

-- Exit psql
\q
```

### Set Database Connection

Create or update your `.env` file:

```bash
# PostgreSQL connection (update password)
DATABASE_URL=postgresql://theseus_user:secure_password_123@localhost:5432/theseus_insight

# Optional: Connection pool settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
```

### Alternative: Docker Setup

For a quick PostgreSQL setup with Docker:

```bash
# Run PostgreSQL with pgvector
docker run -d \
    --name theseus-postgres \
    -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=theseus_insight \
    -p 5432:5432 \
    pgvector/pgvector:pg14

# Set connection string
echo "DATABASE_URL=postgresql://postgres:postgres@localhost:5432/theseus_insight" > .env
```

## Common Usage Patterns

### First-Time Setup
```bash
# Full installation including PostgreSQL
./scripts/install-and-start.sh
```

### Development Workflow
```bash
# Install once (including database setup)
./scripts/install-and-start.sh --install-only

# Start servers when needed
./scripts/install-and-start.sh --start-only
```

### Skip Database Setup
```bash
# If you already have PostgreSQL configured
./scripts/install-and-start.sh --skip-db
```

### Updating Dependencies
```bash
# Re-run installation to update packages (skip database)
./scripts/install-and-start.sh --install-only --skip-db
```

## Troubleshooting

### Common Issues

#### "Command not found" errors
- Ensure Python, Node.js, and PostgreSQL are installed and in your PATH
- Restart your terminal/command prompt after installation
- On Windows, you may need to restart your computer

#### PostgreSQL Connection Issues
```bash
# Test PostgreSQL connection
psql postgresql://theseus_user:password@localhost:5432/theseus_insight

# Check if PostgreSQL is running
sudo systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS
```

#### pgvector Extension Missing
```sql
-- Check if pgvector is installed
SELECT * FROM pg_extension WHERE extname = 'vector';

-- If not found, install it
CREATE EXTENSION vector;
```

#### Permission denied (macOS/Linux)
```bash
# Make script executable
chmod +x scripts/install-and-start.sh
```

#### PowerShell execution policy (Windows)
```powershell
# Allow script execution (run as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine

# Or run with bypass
powershell -ExecutionPolicy Bypass -File scripts\install-and-start.ps1
```

#### Virtual environment issues
```bash
# Remove existing environment and retry
rm -rf venv
./scripts/install-and-start.sh --install-only
```

#### Port conflicts
If ports 5432, 8000, or 5173 are already in use:
- Stop other applications using these ports
- Or modify the ports in the scripts and update your configuration

### Database-Specific Troubleshooting

#### Database Connection Failed
```bash
# Check PostgreSQL status
sudo systemctl status postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql  # Linux
brew services restart postgresql@14  # macOS

# Verify user and database exist
psql -U postgres -c "\l"  # List databases
psql -U postgres -c "\du"  # List users
```

#### pgvector Extension Issues
```bash
# Recompile pgvector if needed
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make clean && make && sudo make install
sudo systemctl restart postgresql
```

#### Schema Initialization Failed
```bash
# Manually run schema initialization
psql postgresql://theseus_user:password@localhost:5432/theseus_insight < scripts/init_schema_postgres.sql
```

### Getting Help

1. **Check Prerequisites:** Ensure Python 3.8+, Node.js 16+, and PostgreSQL 14+ are installed
2. **Run with Help Flag:** Use `--help` to see available options
3. **Check Logs:** Scripts provide detailed output about what's happening
4. **Test Database Connection:** Verify PostgreSQL is accessible
5. **Manual Installation:** If scripts fail, you can install dependencies manually:

```bash
# Backend
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate.bat on Windows
pip install -r requirements.txt

# Frontend
cd theseus-ui
npm install
npm run build
cd ..

# Database (if needed)
createdb theseus_insight
psql theseus_insight -c "CREATE EXTENSION vector;"

# Start servers
export DATABASE_URL="postgresql://username:password@localhost:5432/theseus_insight"
uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload &
cd theseus-ui && npm run dev
```

## Performance Considerations

### Database Performance

For optimal performance with large datasets:

```sql
-- Create indexes after data import
CREATE INDEX CONCURRENTLY ON papers USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX CONCURRENTLY ON papers USING gin(to_tsvector('english', title));
CREATE INDEX CONCURRENTLY ON papers USING gin(to_tsvector('english', abstract));
```

### System Resources

**Minimum Requirements:**
- **RAM:** 4GB (2GB for PostgreSQL)
- **Storage:** 10GB free space
- **CPU:** 2 cores

**Recommended for Large Datasets:**
- **RAM:** 8GB+ (4GB+ for PostgreSQL)
- **Storage:** 50GB+ SSD
- **CPU:** 4+ cores

## Script Locations

All scripts should be run from the **root directory** of the Theseus Insight project (where `requirements.txt` and `theseus-ui/` are located).

```
theseus-insight/
├── requirements.txt
├── theseus-ui/
├── theseus_insight/
├── scripts/
│   ├── install-and-start.sh      # macOS/Linux
│   ├── install-and-start.bat     # Windows CMD
│   ├── install-and-start.ps1     # Windows PowerShell
│   ├── init_schema_postgres.sql  # Database schema
│   └── setup_database.sh         # Database setup helper
└── docs/
    ├── postgresql_setup.md       # Detailed PostgreSQL guide
    └── installation_README.md    # This file
```

## Environment Setup

After successful installation, you'll have:

- **PostgreSQL Database:** Running on `localhost:5432`
  - Database: `theseus_insight`
  - User: `theseus_user`
  - Extensions: `vector` (pgvector)
- **Backend API:** Running on `http://localhost:8000`
- **Frontend UI:** Running on `http://localhost:5173`
- **API Docs:** Available at `http://localhost:8000/docs`
- **Virtual Environment:** Python dependencies in `venv/`
- **Built Frontend:** Production build in `theseus-ui/dist/`

The frontend development server includes hot reload, so changes to the UI will be reflected immediately. The backend also runs with auto-reload enabled for development.

## Advanced Setup

### Custom Database Configuration

For production or performance tuning, see the detailed [PostgreSQL Setup Guide](postgresql_setup.md) which covers:

- **Performance optimization** for large datasets
- **Security configuration** for production deployment
- **Backup and maintenance** procedures
- **Monitoring and troubleshooting** advanced issues
- **Cloud deployment** configurations

### Migration from SQLite

If you have an existing SQLite installation:

1. **Export your data:**
   ```bash
   python -m theseus_insight.utils.db_migration.db_export --output backup.json
   ```

2. **Set up PostgreSQL** using this guide

3. **Import your data:**
   ```bash
   python -m theseus_insight.utils.db_migration.db_import --input backup.json
   ```

See the [Migration Guide](migration_guide.md) for detailed instructions.

### Production Deployment

For production deployments:

1. **Use strong passwords** for database users
2. **Configure SSL/TLS** for database connections
3. **Set up regular backups** and monitoring
4. **Use environment variables** for sensitive configuration
5. **Configure firewalls** and access controls

Refer to the [PostgreSQL Setup Guide](postgresql_setup.md) for production configuration details.

## Related Documentation

- **[PostgreSQL Setup Guide](postgresql_setup.md)** - Detailed database configuration
- **[Migration Guide](migration_guide.md)** - Moving from SQLite to PostgreSQL
- **[Database Specification](db_spec.md)** - Schema and API reference
- **[Docker PostgreSQL Guide](docker_postgresql.md)** - Container deployment

---

**Need Help?** Check the troubleshooting section above, or refer to the detailed PostgreSQL setup guide for advanced configuration and troubleshooting. 