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
- [Database Setup](#database-setup)
- [Environment Variables](#environment-variables)
- [Running the API](#running-the-api)
- [Running the Frontend](#running-the-frontend)
- [Custom Data Storage Location](#custom-data-storage-location)
- [Desktop Build](#desktop-build)
- [Key Endpoints](#key-endpoints)
  - [PDF Uploads](#pdf-uploads)
  - [Podcast Generation](#podcast-generation)
  - [Script Management](#script-management)
  - [Visualizer Generation](#visualizer-generation)
  - [Similarity Search](#similarity-search)
  - [Mind-Map Explorer](#mind-map-explorer)
  - [Theseus Insight Run Orchestration](#theseus-insight-run-orchestration)
- [Using Theseus Insight as a Library](#using-theseus-insight-as-a-library)
- [Database Migration](#database-migration)
- [License](#license)
- [Credits](#credits)

---

## Overview

Theseus Insight fetches and ranks papers from [ArXiv](https://arxiv.org/) or provided PDFs, produces newsletters summarising the most relevant papers and can create podcast episodes with optional video visualisations.  A modern React UI communicates with the FastAPI backend via REST and WebSocket endpoints, providing real‑time feedback while background tasks run. 

**🔄 Now Powered by PostgreSQL:** The latest version has been fully migrated from SQLite to PostgreSQL with pgvector, enabling advanced vector similarity search, improved performance, and enhanced scalability for large research paper collections.

The system introduces the **Mind-Map Explorer**, an interactive visualization system for exploring multi-order research paper relationships through configurable network graphs, enabling researchers to discover both direct and indirect connections in the academic literature.

---

## Quickstart

1. **Clone the repository**
   ```bash
   git clone https://github.com/M-Chimiste/TheseusInsight.git
   cd TheseusInsight
   ```

2. **Set up PostgreSQL database** (see [Database Setup](#database-setup) for details)
   > **📋 Note:** Theseus Insight now requires PostgreSQL with pgvector. SQLite is no longer supported in the latest version.

3. **Create a `.env` file** with your PostgreSQL connection and API keys (see [Environment Variables](#environment-variables)):
   ```bash
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/theseus
   OPENAI_API_KEY=your_key_here
   # ... other variables
   ```

4. **Start the stack with Docker** (includes PostgreSQL)
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

### 🔄 Upgrading from SQLite Version?

If you're upgrading from a previous SQLite-based installation of Theseus Insight, you'll need to migrate your data to PostgreSQL. The process is automated and preserves all your papers, embeddings, and generated content:

📖 **[Complete Migration Guide](docs/migration_guide.md)** - Step-by-step migration instructions with examples.

**Quick Migration:**
```bash
# 1. Export your SQLite data
python -m theseus_insight.utils.db_migration.db_export --source-db data/theseus.db --output backup.json

# 2. Set up PostgreSQL and update your .env file
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/theseus

# 3. Import to PostgreSQL
python -m theseus_insight.utils.db_migration.db_import --input backup.json
```

---

## Features

- **FastAPI** server with endpoints for paper management, newsletter and podcast pipelines and visualiser generation.
- **React** frontend built with Vite and Material UI, served from the backend in production.
- **Real‑time progress** streaming over WebSockets for long running tasks.
- **PostgreSQL database** (with pgvector) for storing papers, runs and configuration data with advanced vector similarity search and full-text indexing.
- **Advanced hybrid search capabilities** combining semantic similarity via vector embeddings with keyword precision using PostgreSQL's native full-text search - significantly more powerful than traditional SQLite-based approaches.
- **Robust ArXiv Data Access**: Automatic fallback from live ArXiv OAI-PMH API to Kaggle dataset (1.7M+ papers) with auto-download and cleanup when the API is unavailable.
- **Cached Summaries & Keywords**: LLM-generated paper summaries and YAKE-extracted top keywords are stored in the database, eliminating redundant generation and dramatically speeding up subsequent mind-map builds.
- **Mind-Map Explorer**: An interactive visualization tool to explore the intellectual neighborhood of research papers.
  - **Multi-Order Expansion**: Generate mind-maps with configurable expansion orders (1-5) to explore deeper connections between papers.
  - **Visual Network Exploration**: Interactive force-directed layouts with similarity-based node positioning and edge weighting.
  - **Configurable Parameters**: Adjust similarity thresholds (10%-80%), paper count (5-30), and nodes per expansion order (5-50).
  - **Smart Deduplication**: Automatic duplicate detection and removal across expansion orders for clean visualizations.
  - **Real-Time Progress Tracking**: WebSocket-powered progress updates with detailed step information during generation.
  - **Save & Share Reports**: Save mind-map configurations and results for future reference and collaboration.
  - **Seamless Integration**: Launch from any paper in the research library or similarity search results.
- **Flexible LLM and TTS providers** including OpenAI, Anthropic, Gemini, Ollama, Polly and KokoroTTS.
- **Encrypted credential storage** with a UI for managing API keys in Settings.
- **Dockerfile and Compose setup** to run the entire application in containers with PostgreSQL.

---

## Database Setup

Theseus Insight uses **PostgreSQL 14+ with pgvector** as its primary database system, providing significant advantages over the previous SQLite-based architecture:

**✨ PostgreSQL Benefits:**
- **Advanced Vector Search**: Native pgvector extension for efficient semantic similarity
- **Full-Text Search**: Built-in PostgreSQL search with stemming and ranking
- **Hybrid Search**: Combine semantic and keyword search for superior accuracy
- **Scalability**: Handle large research paper collections with excellent performance
- **Concurrent Access**: Multiple users and processes can access the database simultaneously
- **ACID Compliance**: Robust data integrity and transaction support

You have several PostgreSQL setup options:

### Option 1: Docker Compose (Recommended)
PostgreSQL is automatically configured when using Docker Compose:

```bash
docker compose up --build
```

### Option 2: Local PostgreSQL Installation
For development or production installations:

📖 **[Local PostgreSQL Setup Guide](docs/postgresql_setup.md)** - Detailed instructions for installing and configuring PostgreSQL locally.

### Option 3: Docker PostgreSQL Only
To run just PostgreSQL in Docker while running the application locally:

📖 **[Docker PostgreSQL Guide](docs/docker_postgresql.md)** - Instructions for running PostgreSQL in Docker.

### Migrating from SQLite
If you're upgrading from a previous SQLite installation:

📖 **[Migration Guide](docs/migration_guide.md)** - Step-by-step instructions for migrating from SQLite to PostgreSQL.

---

## Environment Variables

Create a `.env` file in the project root containing keys and settings:

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (default: `postgresql://postgres:postgres@localhost:5432/theseus`) |
| `OPENAI_API_KEY` | API key for OpenAI models and TTS |
| `ANTHROPIC_API_KEY` | API key for Anthropic Claude models |
| `GOOGLE_API_KEY` | API key for Google Gemini models |
| `OLLAMA_URL` | Base URL of a local Ollama server (default `http://127.0.0.1:11434`) |
| `OLLAMA_PASSTHROUGH` | When `true` (default), Docker containers redirect localhost Ollama URLs to host machine. Set to `false` to use container-local Ollama installation |
| `GMAIL_SENDER_ADDRESS` | Gmail address used to send newsletters |
| `GMAIL_APP_PASSWORD` | Gmail App password for SMTP authentication see: [Gmail App Password Instructions](https://support.google.com/mail/answer/185833?hl=en)|
| `DEBUG` | When set to `true`, `1`, or `yes` globally re-enables verbose `print()` statements and DEBUG-level logger output. Leave unset (default) for a quiet console |
| `CLIENT_ID`, `PROJECT_ID`, `CLIENT_SECRET`, `REDIRECT_URI` | OAuth credentials for the YouTube upload helper |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `REGION_NAME` | Credentials for Amazon Polly TTS |
| `PRODUCTION_FRONTEND_URL` | Allowed origin for CORS when deploying the frontend |
| `RUNNING_IN_DOCKER` | Set to `true` in Docker images for correct static file paths |
| `APP_SECRET_KEY` | Secret used to encrypt API credentials stored in the database |

### PostgreSQL Connection Examples

**Local PostgreSQL:**
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/theseus_insight
```

**Docker PostgreSQL:**
```bash
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/theseus
```

**Cloud PostgreSQL (e.g., AWS RDS):**
```bash
DATABASE_URL=postgresql://username:password@hostname:5432/database_name
```

### Manual Installation

If you prefer to install manually or the automated scripts don't work for your environment:

#### Prerequisites
- **Python 3.8+** - Download from [python.org](https://www.python.org/downloads/)
- **Node.js 16+** - Download from [nodejs.org](https://nodejs.org/)
- **PostgreSQL 14+** - See [Database Setup](#database-setup) for installation options

#### Steps
1. **Install Python dependencies**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate.bat
   
   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Install and build frontend**
   ```bash
   cd theseus-ui
   npm install
   npm run build
   cd ..
   ```

3. **Set up PostgreSQL database** (see [Database Setup](#database-setup))

4. **Create data directories**
   ```bash
   mkdir -p data/{newsletters,podcasts,visualizations,temp}
   mkdir -p config
   ```

5. **Configure environment variables** (see [Environment Variables](#environment-variables) section)

6. **Start the application**
   ```bash
   # Backend (in one terminal)
   source venv/bin/activate
   uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload
   
   # Frontend (in another terminal) 
   cd theseus-ui
   npm run dev
   ```

The PostgreSQL database schema will be created automatically on first run.

## Custom Data Storage Location

By default, Theseus Insight stores generated files (newsletters, podcasts, visualizations) in the local `./data` directory, while the PostgreSQL database is hosted separately. For installations with limited internal storage, you can redirect generated content to an external drive or custom location.

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
└── (PostgreSQL data is stored separately via DATABASE_URL)
```

**Note:** Unlike the previous SQLite-based system, PostgreSQL database files are not stored in the application data directory but are managed by the PostgreSQL server according to your `DATABASE_URL` configuration.

#### Hybrid Search Functionality
Theseus Insight features advanced hybrid search capabilities that combine the precision of PostgreSQL's full-text search with the contextual understanding of semantic similarity using pgvector. This provides significantly enhanced search accuracy compared to traditional keyword-only or semantic-only approaches.

**Key Features:**
- **PostgreSQL Full-Text Search**: Uses native `tsvector` and `tsquery` for accurate term frequency scoring with stemming and ranking
- **pgvector Semantic Search**: Leverages PostgreSQL's pgvector extension for efficient cosine similarity search across paper embeddings
- **Dual-Mode Search**: Simultaneously performs semantic similarity using vector embeddings and advanced keyword ranking across paper titles and abstracts
- **Weighted Scoring**: User-adjustable weights for combining semantic and keyword scores (default: 60% semantic, 40% keyword)
- **Real-Time Scoring**: Returns individual `semantic_score`, `keyword_score`, and combined `hybrid_score` for transparency
- **Full Integration**: Works seamlessly with existing filters (date range, score threshold, pagination)
- **Performance Optimized**: Database-level operations use pgvector indexes and PostgreSQL's GIN indexes for scalable performance

**Technical Implementation:**
- **PostgreSQL Full-Text Search**: Utilizes native `tsvector`/`tsquery` with English language configuration and stemming
- **Ranking Algorithm**: Uses `ts_rank()` function for weighted relevance scoring
- **Vector Operations**: Employs pgvector's cosine distance operator (`<=>`) for semantic similarity
- **Index Optimization**: GIN indexes for full-text search and IVFFlat indexes for vector operations
- **Automatic Schema**: PostgreSQL schema automatically includes search vectors and indexes

**Performance Optimized**: Database-level operations use pgvector for vector search and PostgreSQL's native full-text search indexes for scalable performance

### Mind-Map Explorer

**Technical Implementation:**
- **PostgreSQL Integration**: Complete CRUD operations for mind-map reports with JSON storage for configurations and results
- **Vector Similarity**: Uses pgvector for efficient similarity calculations across large paper collections
- **Performance Optimization**: Leverages PostgreSQL's indexing for fast paper retrieval and similarity computation

## Database Migration

Theseus Insight includes comprehensive database migration tools for transferring data between environments and migrating from legacy SQLite installations to PostgreSQL.

### SQLite to PostgreSQL Migration

For users upgrading from previous SQLite-based installations:

📖 **[Complete Migration Guide](docs/migration_guide.md)** - Detailed instructions for migrating from SQLite to PostgreSQL.

**Quick Migration Example:**
```bash
# Export from SQLite
python -m theseus_insight.utils.db_migration.db_export \
    --source-db data/theseus.db \
    --output ./sqlite_backup.json

# Import to PostgreSQL
python -m theseus_insight.utils.db_migration.db_import \
    --input ./sqlite_backup.json
```

### PostgreSQL to PostgreSQL Migration

**Export PostgreSQL database to archive:**
```bash
python -m theseus_insight.utils.db_migration.db_export \
    --output ./backup.json
```

**Import archive to new PostgreSQL database:**
```bash
python -m theseus_insight.utils.db_migration.db_import \
    --input ./backup.json
```

**Direct migration with verification:**
```bash
python -m theseus_insight.utils.db_migration.db_migrate \
    --source-db "postgresql://user:pass@old-host:5432/db" \
    --target-db "postgresql://user:pass@new-host:5432/db" \
    --verify
```

### Features
- **Cross-Database Migration** - Full support for SQLite to PostgreSQL migration
- **Intelligent duplicate handling** - Papers detected by URL, podcasts by title, newsletters by date range
- **Vector embedding preservation** - Maintains exact embeddings during migration with pgvector compatibility
- **Schema translation** - Automatic conversion between SQLite and PostgreSQL data types
- **Verification tools** - Compare source and target databases after migration
- **PostgreSQL Optimization** - Optimized imports using PostgreSQL-specific features like COPY and bulk operations

For detailed documentation and advanced usage examples, see [docs/db_migration_README.md](docs/db_migration_README.md).

---

## Credits

- [paperswithcode.com](https://paperswithcode.com/) for research paper data.
- [arxiv.org](https://arxiv.org/) for open access to research paper data.
- [Docling](https://github.com/doclingjs/docling) for document parsing.
- [pydub](https://github.com/jiaaro/pydub) for audio processing.
- [Amazon Polly](https://aws.amazon.com/polly/), [OpenAI TTS](https://platform.openai.com/docs/) for text-to-speech.
- [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://pydantic-docs.helpmanual.io/), PostgreSQL with [pgvector](https://github.com/pgvector/pgvector) for backend processing.

Theseus Insight is maintained by [M. Chimiste](https://github.com/M-Chimiste) & contributors.

