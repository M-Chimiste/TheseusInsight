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

Theseus Insight fetches and ranks papers from [ArXiv](https://arxiv.org/) or provided PDFs, produces newsletters summarising the most relevant papers and can create podcast episodes with optional video visualisations.  A modern React UI communicates with the FastAPI backend via REST and WebSocket endpoints, providing real‑time feedback while background tasks run. The latest version introduces the **Mind-Map Explorer**, an interactive visualization system for exploring multi-order research paper relationships through configurable network graphs, enabling researchers to discover both direct and indirect connections in the academic literature.

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
- **Dockerfile and Compose setup** to run the entire application in containers.

---

## Architecture and Modules

```
theseus_insight/
  api/                    # FastAPI backend components
    routers/              # Modular API route definitions
      papers.py           # Paper search, similarity, embeddings
      settings.py         # Configuration and credentials
      model_providers.py  # Model provider management
      runs_and_tasks.py   # Task management and status
      logs.py             # Logging and task history
      newsletters_and_podcasts.py  # Content generation
      actions.py          # Visualizer pipeline actions
      database.py         # Import/export functionality
      mindmap.py          # Mind-map generation and reports
      websockets.py       # WebSocket connections
      __init__.py         # Router registry
    dependencies.py       # Shared dependencies (db, credentials)
    models.py            # Pydantic data models
    tasks.py             # Background task management
  communication/          # Gmail and YouTube helpers
  data_model/            # SQLite interactions and pydantic models
  data_processing/       # Arxiv harvesting utilities
  inference/             # LLM and TTS wrappers
  mindmap/               # Mind-map generation system
    nodes/               # LangGraph workflow nodes
      build_mindmap.py   # Mind-map data structure assembly
      embed_seed.py      # Seed paper embedding generation
      multi_order_retriever.py  # Multi-order similarity search
      retriever.py       # Single-order similarity search
      select_seed.py     # Seed paper selection and validation
      summariser.py      # Paper summarization for nodes
    state.py             # Mind-map workflow state management
    workflow.py          # LangGraph workflow orchestration
  pdf/                   # PDF parsing helpers
  podcast/               # Podcast and visualiser generation
  main.py                # FastAPI entrypoint and app configuration
  theseus_insight.py     # Pipeline orchestrator
```

Configuration files live in `config/` and the React app is located in `theseus-ui/`.

### API Router Architecture

The FastAPI backend uses a modular router architecture for better maintainability and separation of concerns:

- **Centralized Dependencies**: Shared resources like database connections and credential keys are managed in `api/dependencies.py`
- **Focused Routers**: Each router handles a specific domain (papers, settings, tasks, etc.)
- **Clean Separation**: Route definitions are separated from the main application setup
- **Easy Extension**: New functionality can be added by creating focused router modules

---

## Installation

### Automated Installation (Recommended)

For the fastest setup, use our automated installation scripts that handle all dependencies and start both servers:

#### macOS / Linux
```bash
# Make the script executable and run
chmod +x scripts/install-and-start.sh
./scripts/install-and-start.sh
```

#### Windows (Command Prompt)
```cmd
scripts\install-and-start.bat
```

#### Windows (PowerShell)
```powershell
.\scripts\install-and-start.ps1
```

**What the scripts do:**
- Check for Python 3.8+ and Node.js installations
- Create Python virtual environment and install dependencies
- Install and build the React frontend
- Create necessary data directories
- Generate default configuration files
- Start both backend (port 8000) and frontend (port 5173) servers

**Script Options:**
- `--install-only` - Only install dependencies, don't start servers
- `--start-only` - Only start servers (skip installation)  
- `--help` - Show help and usage information

**Examples:**
```bash
# Install dependencies only
./scripts/install-and-start.sh --install-only

# Start servers only (after installation)
./scripts/install-and-start.sh --start-only

# Full setup (default)
./scripts/install-and-start.sh
```

After successful installation, you'll have:
- **Backend API:** `http://localhost:8000`
- **Frontend UI:** `http://localhost:5173` 
- **API Documentation:** `http://localhost:8000/docs`

For detailed troubleshooting and platform-specific installation instructions, see [`docs/installation.md`](docs/installation_README.md).

### Manual Installation

If you prefer to install manually or the automated scripts don't work for your environment:

#### Prerequisites
- **Python 3.8+** - Download from [python.org](https://www.python.org/downloads/)
- **Node.js 16+** - Download from [nodejs.org](https://nodejs.org/)

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

3. **Create data directories**
   ```bash
   mkdir -p data/{newsletters,podcasts,visualizations,temp}
   mkdir -p config
   ```

4. **Configure environment variables** (see [Environment Variables](#environment-variables) section)

5. **Start the application**
   ```bash
   # Backend (in one terminal)
   source venv/bin/activate
   uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload
   
   # Frontend (in another terminal) 
   cd theseus-ui
   npm run dev
   ```

The SQLite database will be created automatically on first run.

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


## Custom Data Storage Location

By default, Theseus Insight stores data in the local `./data` directory. This folder contains the `theseus.db` SQLite database alongside generated newsletters, podcasts and other files. For installations with limited internal storage, you can redirect all data to an external drive or custom location.

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
└── theseus.db                 # SQLite database file
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
mkdir -p /Volumes/nyx/theseus_insight_data/app_data

# Copy existing application data
cp -r ./data/* /Volumes/nyx/theseus_insight_data/app_data/

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
- **BM25-Enhanced Keyword Search**: Uses SQLite FTS5 with the `bm25()` ranking function for accurate term frequency scoring
- **Dual-Mode Search**: Simultaneously performs semantic similarity using vector embeddings and advanced keyword ranking across paper titles and abstracts
- **Weighted Title Boost**: Title matches receive 2x scoring weight compared to abstract matches for improved relevance
- **Weighted Scoring**: User-adjustable weights for combining semantic and keyword scores (default: 60% semantic, 40% keyword)
- **Real-Time Scoring**: Returns individual `semantic_score`, `keyword_score`, and combined `hybrid_score` for transparency
- **Full Integration**: Works seamlessly with existing filters (date range, score threshold, pagination)
- **Performance Optimized**: Database-level operations use sqlite-vec for vector search and FTS5 indexes for scalable performance

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
- **SQLite Full-Text Search**: Utilises the FTS5 module with Unicode-aware tokenization and stopword filtering
- **Ranking Algorithm**: Uses the `bm25()` ranking function for weighted relevance
- **Index Optimization**: FTS5 indexes provide fast lookup over title and abstract text
- **Automatic Migration**: Existing installations automatically update the SQLite schema when new search features are introduced

See [docs/embedding_functionality_README.md](docs/embedding_functionality_README.md) for more details.
### Mind-Map Explorer
- **`POST /api/mindmap/expand`** – generate a mind-map from a seed paper.
- **`GET /api/mindmap/reports`** – list saved mind-map reports.
- **`POST /api/mindmap/reports`** – save a mind-map report.
- **`GET /api/mindmap/reports/{report_id}`** – retrieve a specific mind-map report.
- **`DELETE /api/mindmap/reports/{report_id}`** – delete a mind-map report.

#### Mind-Map Generation Features

The Mind-Map Explorer provides an advanced visualization system for exploring research paper relationships through interactive network graphs. Built on top of the existing similarity search infrastructure, it offers configurable multi-order expansion to discover both direct and indirect connections between papers.

**Core Capabilities:**
- **Multi-Order Expansion**: Generate mind-maps with 1-5 expansion orders to explore increasingly distant paper relationships
- **Similarity-Based Clustering**: Papers are automatically arranged in concentric rings based on similarity scores (≥80%, 60-80%, 40-60%, <40%)
- **Interactive Canvas**: Built with React Flow for smooth panning, zooming, and node interaction
- **Real-Time Generation**: WebSocket-powered progress tracking with detailed step information
- **Persistent Storage**: Save mind-map configurations and results as reports for future reference

**Configuration Parameters:**
- **Expansion Order** (1-5): Controls the depth of exploration (Order 1 = direct similarities, Order 2+ = indirect connections)
- **Papers per Order** (5-30): Number of similar papers to find at each expansion level
- **Max Nodes per Order** (5-50): Maximum nodes to include per expansion order for performance optimization
- **Similarity Threshold** (10%-80%): Minimum similarity score for including papers in the mind-map
- **Layout Algorithm**: Force-directed positioning with collision detection and edge optimization

**Technical Implementation:**
- **Deduplication Logic**: Automatic removal of duplicate papers across expansion orders using ID-based tracking
- **Efficient Routing**: Conditional workflow routing between single-order (`RetrieverNode`) and multi-order (`MultiOrderRetrieverNode`) based on expansion parameters
- **Progress Callbacks**: Specialized progress tracking for multi-order operations with step-by-step feedback
- **Database Integration**: Complete CRUD operations for mind-map reports with JSON storage for configurations and results

**Example API Request:**
```json
POST /api/mindmap/expand
{
  "paper_id": "12345",
  "k": 15,
  "similarity_threshold": 0.3,
  "layout_algorithm": "force",
  "expansion_order": 2,
  "max_nodes_per_order": 20
}
```

**Example Response:**
```json
{
  "status": "success",
  "data": {
    "task_id": "mindmap_abc123",
    "message": "Mind-map generation started"
  }
}
```

**Frontend Integration:**
The React interface provides an intuitive dialog for configuring mind-map parameters with real-time validation and helpful tooltips. The interactive canvas supports:
- **Node Expansion**: Double-click nodes to generate new mind-maps with that paper as the seed
- **Contextual Actions**: Right-click menus for opening papers, expanding nodes, and accessing additional options
- **Visual Feedback**: Similarity scores displayed as edge weights and node positioning
- **Save Functionality**: One-click saving of mind-map configurations and results
- **Fullscreen Mode**: Dedicated fullscreen view for detailed exploration

**Use Cases:**
- **Literature Review**: Discover related works and research trends around a specific paper
- **Research Planning**: Identify gaps and opportunities in research areas
- **Citation Analysis**: Explore indirect connections between papers through similarity rather than citations
- **Knowledge Discovery**: Find unexpected connections between seemingly unrelated research areas

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
    --source-db data/theseus.db \
    --output ./backup.tar.gz
```

**Import archive to new database:**
```bash
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db data/theseus.db \
    --input ./backup.tar.gz
```

**Direct migration with verification:**
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db old.db \
    --target-db new.db \
    --verify
```

### Features
- **Intelligent duplicate handling** - Papers detected by URL, podcasts by title, newsletters by date range
- **Compressed archives** - tar.gz format with metadata for easy transfer
- **Vector embedding preservation** - Maintains exact embeddings during migration
- **Verification tools** - Compare source and target databases after migration
- **Summary & Keyword Preservation** – Export/import routines now include the new `summary` and `keywords` columns so cached content moves seamlessly between installations.

For detailed documentation and advanced usage examples, see [`theseus_insight/docs/db_migration_README.md`](theseus_insight/docs/db_migration_README.md).

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
- [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://pydantic-docs.helpmanual.io/), SQLite with [sqlite-vec](https://github.com/asg017/sqlite-vss) for backend processing.

Theseus Insight is maintained by [M. Chimiste](https://github.com/M-Chimiste) & contributors.

