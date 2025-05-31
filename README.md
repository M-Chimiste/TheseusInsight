# Theseus Insight

<p align="center">
  <img src="assets/theseus%20insight%20logo.png" alt="Theseus Insight logo" width="300"/>
</p>

Theseus Insight is an end‑to‑end platform for analysing research papers and generating newsletters or podcast episodes from them.  The project provides a FastAPI backend, a React interface and utility scripts that orchestrate language models and text‑to‑speech engines.

## Table of Contents
- [Overview](#overview)
- [Quickstart](#quickstart)
- [Features](#features)
- [Architecture and Modules](#architecture-and-modules)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Running the API](#running-the-api)
- [Running the Frontend](#running-the-frontend)
- [External Database Access](#external-database-access)
- [External Database Access](#external-database-access)
- [Custom Data Storage Location](#custom-data-storage-location)
- [Desktop Build](#desktop-build)
- [Key Endpoints](#key-endpoints)
  - [PDF Uploads](#pdf-uploads)
  - [Podcast Generation](#podcast-generation)
  - [Script Management](#script-management)
  - [Visualizer Generation](#visualizer-generation)
  - [Similarity Search](#similarity-search)
  - [Theseus Insight Run Orchestration](#theseus-insight-run-orchestration)
- [Using Theseus Insight as a Library](#using-theseus-insight-as-a-library)
- [Database Migration](#database-migration)
- [License](#license)
- [Credits](#credits)

---

## Overview

Theseus Insight fetches and ranks papers from [ArXiv](https://arxiv.org/) or provided PDFs, produces newsletters summarising the most relevant papers and can create podcast episodes with optional video visualisations.  A modern React UI communicates with the FastAPI backend via REST and WebSocket endpoints, providing real‑time feedback while background tasks run.

---

## Quickstart

1. **Clone the repository**
   ```bash
   git clone https://github.com/M-Chimiste/TheseusInsight.git
   cd TheseusInsight
   ```
2. **Create a `.env` file** with the variables described in [Environment Variables](#environment-variables).
3. **Start the stack with Docker**
   ```bash
   docker compose up --build
   ```
   The API and built React frontend will be available on <http://localhost:8000>.

During development you can run the React interface separately:
```bash
cd theseus-ui
npm install
npm run dev
```
This starts Vite on <http://localhost:5173> which proxies API requests to the backend.


---

## Features


- **FastAPI** server with endpoints for paper management, newsletter and podcast pipelines and visualiser generation.
- **React** frontend built with Vite and Material UI, served from the backend in production.
- **Real‑time progress** streaming over WebSockets for long running tasks.
- **SQLite database** (with sqlite-vec) for storing papers, runs and configuration data.
- **Advanced search capabilities** including semantic similarity via vector embeddings and hybrid search combining semantic understanding with keyword precision.
- **Flexible LLM and TTS providers** including OpenAI, Anthropic, Gemini, Ollama, Polly and KokoroTTS.
- **Encrypted credential storage** with a UI for managing API keys in Settings.
- **Dockerfile and Compose setup** to run the entire application in containers.

---

## Architecture and Modules

```
theseus_insight/
  api/               # FastAPI models, tasks and routes
  communication/     # Gmail and YouTube helpers
  data_model/        # SQLite interactions and pydantic models
  data_processing/   # Arxiv harvesting utilities
  inference/         # LLM and TTS wrappers
  pdf/               # PDF parsing helpers
  podcast/           # Podcast and visualiser generation
  main.py            # FastAPI entrypoint
  theseus_insight.py # Pipeline orchestrator
```

Configuration files live in `config/` and the React app is located in `theseus-ui/`.

---

## Installation

If you prefer running locally without Docker:
1. Install Python dependencies
   ```bash

   pip install -r requirements.txt

   ```
2. (Optional) install Node.js 20+ and build the frontend
   ```bash
   cd theseus-ui
   npm install
   npm run build
   ```
3. Configure environment variables as shown below.
4. The SQLite database will be created automatically on first run.

---

## Environment Variables

Create a `.env` file in the project root containing keys and settings:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | API key for OpenAI models and TTS |
| `ANTHROPIC_API_KEY` | API key for Anthropic Claude models |
| `GOOGLE_API_KEY` | API key for Google Gemini models |
| `OLLAMA_URL` | Base URL of a local Ollama server (default `http://127.0.0.1:11434`) |
| `OLLAMA_PASSTHROUGH` | When `true` (default), Docker containers redirect localhost Ollama URLs to host machine. Set to `false` to use container-local Ollama installation |
| `ALLOW_DB_CONNECTION` | Deprecated - no external database |
| `GMAIL_SENDER_ADDRESS` | Gmail address used to send newsletters |
| `GMAIL_APP_PASSWORD` | Gmail App password for SMTP authentication see: [Gmail App Password Instructions](https://support.google.com/mail/answer/185833?hl=en)|
| `DATABASE_URL` | Path to the SQLite database file (default `data/theseus.db`) |
| `SQLITE_VEC_PATH` | Optional path to the `sqlite_vec` extension for vector similarity |

| `CLIENT_ID`, `PROJECT_ID`, `CLIENT_SECRET`, `REDIRECT_URI` | OAuth credentials for the YouTube upload helper |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `REGION_NAME` | Credentials for Amazon Polly TTS |
| `PRODUCTION_FRONTEND_URL` | Allowed origin for CORS when deploying the frontend |
| `RUNNING_IN_DOCKER` | Set to `true` in Docker images for correct static file paths |
| `APP_SECRET_KEY` | Secret used to encrypt API credentials stored in the database |

The application loads these credentials from the database at startup, falling back to `.env` values if necessary. You can view and update them from the **Settings → API Credentials** section in the UI.
More details are available in [docs/credential_management_README.md](docs/credential_management_README.md).

Note: The `APP_SECRET_KEY` is used to encrypt sensitive data in the database, such as OAuth tokens and API keys. It should be a long, random string that is kept secret from anyone who might access it. This value will default to an insecure password that is not recommended for production use.

### Ollama Docker Networking

When running Theseus Insight in Docker and using Ollama on your host machine, the `OLLAMA_PASSTHROUGH` environment variable controls network routing:

- **`OLLAMA_PASSTHROUGH=true` (default)**: Automatically redirects localhost URLs (e.g., `http://localhost:11434`) to `host.docker.internal` for Docker containers to access the host machine's Ollama installation.
- **`OLLAMA_PASSTHROUGH=false`**: Uses standard container networking, expecting Ollama to be running within the Docker network.

**Examples:**
- **Host Ollama with passthrough**: Set `OLLAMA_URL=http://localhost:11434` and `OLLAMA_PASSTHROUGH=true` in your `.env` file
- **Container Ollama**: Set `OLLAMA_URL=http://ollama:11434` and `OLLAMA_PASSTHROUGH=false` if running Ollama as a separate Docker service

This allows seamless switching between development (local Ollama) and production (containerized Ollama) environments without changing URLs manually.

---

## Running the API

Run the FastAPI app locally with Uvicorn:

```bash
uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs are served at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Running the Frontend

During development use the Vite dev server as shown in the [Quickstart](#quickstart) section.  When using Docker or after running `npm run build`, the compiled frontend is served automatically from FastAPI on port 8000.

---

## External Database Access

By default, the PostgreSQL database runs in an isolated Docker container and is not accessible from external tools. For development, debugging, data migration, or administrative tasks, you can enable external database access.

### Enabling External Access

**Option 1: Using the helper script (recommended)**
```bash
# Start with external database access enabled
./scripts/start-with-db-access.sh

# Or pass additional docker-compose arguments
./scripts/start-with-db-access.sh -d  # Run in detached mode
```

**Option 2: Manual Docker Compose override**
```bash
# Start with both compose files
docker-compose -f docker-compose.yml -f docker-compose.db-external.yml up --build
```

**Option 3: Environment variable in .env file**
```bash
# Add to your .env file
ALLOW_DB_CONNECTION=true

# Then start normally (this sets the variable but you still need the override file)
docker-compose -f docker-compose.yml -f docker-compose.db-external.yml up --build
```

### Connection Details

When external access is enabled, the database is accessible on:
- **Host**: `localhost`
- **Port**: `5433` (to avoid conflicts with local PostgreSQL)
- **Database**: `theseusdb`
- **Username**: `theseus`
- **Password**: `theseus`

### Example Connections

**Using psql command line:**
```bash
psql -h localhost -p 5433 -U theseus -d theseusdb
```

**Using pgAdmin:**
- Server: `localhost:5433`
- Maintenance database: `theseusdb`
- Username: `theseus`
- Password: `theseus`

**Using Python/SQLAlchemy:**
```python
from sqlalchemy import create_engine
engine = create_engine("postgresql://theseus:theseus@localhost:5433/theseusdb")
```

### Security Considerations

⚠️ **Important**: Only enable external database access in development environments or secure networks. When enabled:
- The database accepts connections from any IP address on the host machine
- Database credentials are transmitted over the network
- The database port is exposed on the host machine

For production deployments, use secure connection methods such as:
- VPN tunnels
- SSH port forwarding
- Database connection pools with authentication
- Network firewalls and access controls

---

## Custom Data Storage Location

By default, Theseus Insight stores data in the local `./data` directory and uses Docker named volumes for the PostgreSQL database. For installations with limited internal storage, you can redirect all data to an external drive or custom location.

### Quick Setup for External Storage

**Option 1: Using the helper script (recommended)**
```bash
# Start with data stored on external drive
./scripts/start-with-external-storage.sh

# Or specify a custom path
./scripts/start-with-external-storage.sh /path/to/your/storage

# Run in detached mode
./scripts/start-with-external-storage.sh /Volumes/nyx/theseus_insight_data -d
```

**Option 2: Manual Docker Compose override**
```bash
# Set the storage path
export EXTERNAL_DATA_PATH=/Volumes/nyx/theseus_insight_data

# Start with external storage configuration
docker-compose -f docker-compose.yml -f docker-compose.external-storage.yml up --build
```

**Option 3: Environment variable in .env file**
```bash
# Add to your .env file
EXTERNAL_DATA_PATH=/Volumes/nyx/theseus_insight_data

# Then start with the external storage override
docker-compose -f docker-compose.yml -f docker-compose.external-storage.yml up --build
```

### Storage Structure

When using external storage, the following directory structure is created:

```
/Volumes/nyx/theseus_insight_data/
├── app_data/                    # Application-generated files
│   ├── newsletters/             # Generated newsletters
│   ├── podcasts/               # Generated podcast audio/video
│   ├── visualizations/         # Generated visualizations
│   └── temp/                   # Temporary processing files
└── postgres_data/              # PostgreSQL database files
    ├── base/                   # Database tables and indexes
    ├── global/                 # Cluster-wide data
    ├── pg_wal/                 # Write-ahead log files
    └── ...                     # Other PostgreSQL system files
```

### Platform-Specific Paths

**macOS External Drive:**
```bash
/Volumes/your_drive_name/theseus_insight_data
```

**Linux External Drive:**
```bash
/mnt/external_drive/theseus_insight_data
# or
/media/username/drive_name/theseus_insight_data
```

**Windows External Drive:**
```bash
D:\theseus_insight_data
# or
E:\storage\theseus_insight_data
```

### Configuration Template

Use the provided template to set up your environment:

```bash
# Copy the template to your .env file
cp config/external-storage.env.template .env

# Edit .env to set your desired path
nano .env  # or use your preferred editor
```

### Data Migration from Default Location

If you've already been running Theseus Insight and want to move existing data to external storage:

```bash
# Stop the application
docker-compose down

# Create external storage directory
mkdir -p /Volumes/nyx/theseus_insight_data/{app_data,postgres_data}

# Copy existing application data
cp -r ./data/* /Volumes/nyx/theseus_insight_data/app_data/

# Export existing database (if you have data)
docker run --rm -v theseusinsight_theseus_db_data:/data -v /Volumes/nyx/theseus_insight_data/postgres_data:/backup alpine sh -c "cp -r /data/* /backup/"

# Start with external storage
./scripts/start-with-external-storage.sh
```

### Benefits of External Storage

- **Space Management**: Keep large files (podcasts, visualizations) off limited internal storage
- **Performance**: Can use faster external SSDs for improved I/O performance
- **Portability**: Easily move data between machines by moving the external drive
- **Backup**: Simpler to backup data by cloning the external drive
- **Scalability**: Easy to upgrade storage capacity without affecting the main system

### Important Considerations

⚠️ **External Drive Requirements:**
- Must be mounted and accessible before starting the application
- Requires read/write permissions for the Docker daemon
- Should use a reliable connection (avoid USB hubs for large data operations)
- Consider using SSDs for better performance with database operations

⚠️ **macOS Specific Notes:**
- External drives are typically mounted under `/Volumes/`
- NTFS drives may need third-party drivers for write access
- Consider using APFS or exFAT for better macOS compatibility

---

## Key Endpoints

### PDF Uploads
- **`POST /api/pdf/upload`** – upload a single PDF.
- **`POST /api/pdf/batch-upload`** – upload multiple PDFs.

### Podcast Generation
- **`POST /api/podcast/generate`** – start podcast generation.
- **`GET /api/podcast/status/{task_id}`** – check task status.
- **`GET /api/podcast/download/{filename}`** – download the final file.

### Script Management
- **`POST /api/script/save`** – save a generated script.
- **`GET /api/script/list`** – list saved scripts.
- **`GET /api/script/download/{filename}`** – download a script.

### Visualizer Generation
- **`POST /api/visualizer/generate`** – create a visualiser video.
- **`GET /api/visualizer/status/{task_id}`** – check generation status.

### Similarity Search
- **`POST /api/papers/similarity-search`** – semantic search using embeddings.
- **`POST /api/papers/hybrid-search`** – hybrid search combining semantic similarity and keyword matching.
- **`GET /api/papers/without-embeddings`** – list papers missing embeddings.
- **`POST /api/papers/{paper_id}/update-embedding`** – generate embedding for a paper.
- **`GET /api/papers/{paper_id}/similar`** – find papers similar to an existing one.

#### Hybrid Search Functionality
Theseus Insight features advanced hybrid search capabilities that combine the precision of BM25-style keyword ranking with the contextual understanding of semantic similarity. This provides significantly enhanced search accuracy compared to traditional keyword-only or semantic-only approaches.

**Key Features:**
- **BM25-Enhanced Keyword Search**: Uses PostgreSQL's full-text search with `ts_rank_cd()` for sophisticated term frequency and document ranking (replaces simple substring matching)
- **Dual-Mode Search**: Simultaneously performs semantic similarity using vector embeddings and advanced keyword ranking across paper titles and abstracts
- **Weighted Title Boost**: Title matches receive 2x scoring weight compared to abstract matches for improved relevance
- **Weighted Scoring**: User-adjustable weights for combining semantic and keyword scores (default: 60% semantic, 40% keyword)
- **Real-Time Scoring**: Returns individual `semantic_score`, `keyword_score`, and combined `hybrid_score` for transparency
- **Full Integration**: Works seamlessly with existing filters (date range, score threshold, pagination)
- **Performance Optimized**: Database-level operations using PostgreSQL with pgvector and GIN indexes for scalable performance

**Example API Request:**
```json
POST /api/papers/hybrid-search
{
  "query_text": "transformer attention mechanisms",
  "page": 1,
  "page_size": 10,
  "semantic_weight": 0.7,
  "keyword_weight": 0.3,
  "similarity_threshold": 0.3,
  "min_score": 5.0
}
```

**Example Response:**
```json
{
  "query_text": "transformer attention mechanisms",
  "results": [
    {
      "id": 1234,
      "title": "Attention Is All You Need: The Transformer Architecture",
      "semantic_score": 0.85,
      "keyword_score": 1.0,
      "hybrid_score": 0.895,
      "score": 8.5,
      "abstract": "We propose a new attention mechanism...",
      ...
    }
  ],
  "total_results": 247,
  "semantic_weight": 0.7,
  "keyword_weight": 0.3
}
```

**Frontend Integration:**
The React interface provides an intuitive toggle for enabling hybrid search with interactive weight adjustment sliders. Users can fine-tune the balance between semantic understanding and BM25-style keyword ranking to optimize results for their specific research needs.

**Technical Implementation:**
- **PostgreSQL Full-Text Search**: Leverages native `tsvector` and `tsquery` types with English language stemming and stopword filtering
- **Ranking Algorithm**: Uses `ts_rank_cd()` with normalization flags for document length and term frequency weighting
- **Index Optimization**: GIN (Generalized Inverted Index) indexes on title, abstract, and combined search vectors for fast retrieval
- **Automatic Migration**: Existing installations automatically gain BM25 capabilities through database schema updates

See [docs/embedding_functionality_README.md](docs/embedding_functionality_README.md) for more details.
### Theseus Insight Run Orchestration
- **`POST /api/theseus_insight/run`** – execute the full newsletter and podcast pipeline.

---

## Using Theseus Insight as a Library

```python
from theseus_insight import TheseusInsight

ti = TheseusInsight(
    research_interests_path="config/research_interests.txt",
    orchestration_config="config/orchestration.json",
)
ti.run()
```

Or via the CLI:
```bash
python run_theseus_insight.py --generate-podcast True --generate-email True
```

---

## Database Migration

Theseus Insight includes comprehensive database migration tools for transferring data between environments. These tools support exporting data to portable archives and importing them to new databases while handling duplicates intelligently.

### Quick Migration Examples

**Export database to archive:**
```bash
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://user:pass@localhost:5432/theseus_dev" \
    --output ./backup.tar.gz
```

**Import archive to new database:**
```bash
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "postgresql://user:pass@new-server:5432/theseus_prod" \
    --input ./backup.tar.gz
```

**Direct migration with verification:**
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-server:5432/theseus_dev" \
    --target-db "postgresql://user:pass@new-server:5432/theseus_prod" \
    --verify
```

### Features
- **Intelligent duplicate handling** - Papers detected by URL, podcasts by title, newsletters by date range
- **Compressed archives** - tar.gz format with metadata for easy transfer
- **Vector embedding preservation** - Maintains exact embeddings during migration
- **Verification tools** - Compare source and target databases after migration
- **Flexible import options** - Support for selective imports and batch processing

For detailed documentation and advanced usage examples, see [`theseus_insight/docs/db_migration_README.md`](theseus_insight/docs/db_migration_README.md).

---

## Desktop Build

An Electron wrapper is provided in the `electron-app` directory. It bundles the
Python backend and a PostgreSQL database using `pgvector`. PostgreSQL runs on
port **55432** to avoid conflicts with existing installations.

### Building

```
cd electron-app
npm install
npm run build-pg   # or npm run download-pg
npm run build
```

See [`electron-app/README.md`](electron-app/README.md) for platform specific
instructions.

---

## License

This project is licensed under the [Apache License 2.0](LICENSE) unless otherwise stated.

---

## Credits

- [paperswithcode.com](https://paperswithcode.com/) for research paper data.
- [arxiv.org](https://arxiv.org/) for open access to research paper data.
- [Docling](https://github.com/doclingjs/docling) for document parsing.
- [pydub](https://github.com/jiaaro/pydub) for audio processing.
- [Amazon Polly](https://aws.amazon.com/polly/), [OpenAI TTS](https://platform.openai.com/docs/) for text-to-speech.
- [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://pydantic-docs.helpmanual.io/), [PostgreSQL](https://www.postgresql.org/) with [pgvector](https://github.com/pgvector/pgvector) for backend processing.

Theseus Insight is maintained by [M. Chimiste](https://github.com/M-Chimiste) & contributors.

