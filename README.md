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
   (Note: `scripts/setup_database.sh` is no longer needed as SQLite databases are created on demand.)

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
# `ALLOW_DB_CONNECTION` related to PostgreSQL is removed. SQLite access is direct file access.
| `GMAIL_SENDER_ADDRESS` | Gmail address used to send newsletters |
| `GMAIL_APP_PASSWORD` | Gmail App password for SMTP authentication see: [Gmail App Password Instructions](https://support.google.com/mail/answer/185833?hl=en)|
| `DATABASE_URL` | Connection string for the SQLite database (e.g., `sqlite:///./data/theseus.db` for a local file, or `sqlite:////app/data/theseus.db` in Docker). For the Electron app, this is set automatically to a path in the user's application data directory. |
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

## Database Access

Theseus Insight now uses an SQLite database.
- **Local/Docker**: The database file (e.g., `theseus.db`) is typically stored in the `./data` directory (mounted into `/app/data` in Docker). You can access it using any SQLite browser or tool by opening this file.
- **Electron App**: The SQLite database file is stored in the user's application data directory (e.g., `~/Library/Application Support/theseus-desktop/theseus.db` on macOS).

No special scripts or Docker overrides are needed for "external access" beyond accessing the SQLite file directly.

---

## Custom Data Storage Location

Theseus Insight stores application-generated files (podcasts, newsletters, visualizations, temporary files) and the SQLite database (`theseus.db`) in a data directory. By default, this is `./data` relative to the project root, which is mounted to `/app/data` in Docker.

You can change this data storage location, for example, to use an external drive.

### Configuration

1.  **Set `DATA_DIR_PATH` Environment Variable**:
    In your `.env` file (or directly in `docker-compose.yml` if preferred), set the `DATA_DIR_PATH` variable to your desired absolute path.
    ```env
    # Example for .env file
    DATA_DIR_PATH=/path/to/your/external/storage/theseus_insight_data
    ```

2.  **Update Docker Compose Volume Mount (if using Docker)**:
    Modify the `volumes` section for the `theseus-insight-app` service in your `docker-compose.yml` to map your custom host path to `/app/data` in the container:
    ```yaml
    services:
      theseus-insight-app:
        # ... other configurations ...
        volumes:
          - ${DATA_DIR_PATH:-./data}:/app/data
        environment:
          # Ensure Python backend also knows this if needed for absolute path access internally,
          # though typically it should work relative to /app/data.
          # The DATABASE_URL for SQLite will point to /app/data/theseus.db.
    ```
    The `${DATA_DIR_PATH:-./data}` syntax uses the environment variable `DATA_DIR_PATH` if set, otherwise defaults to `./data`.

### Storage Structure

Your custom data directory will contain:
```
/path/to/your/external/storage/theseus_insight_data/
├── theseus.db              # SQLite database file
├── newsletters/            # Generated newsletters
├── podcasts/               # Generated podcast audio/video
├── visualizations/         # Generated visualizations
└── temp/                   # Temporary processing files
```

### Platform-Specific Paths for `DATA_DIR_PATH`

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

# Copy existing application data (excluding old PostgreSQL data)
# Ensure your new DATA_DIR_PATH is created, e.g.,
# mkdir -p /path/to/your/external/storage/theseus_insight_data
# cp -r ./data/* /path/to/your/external/storage/theseus_insight_data/
# (Ensure you copy the new theseus.db if it exists in the old ./data, and other relevant app files)

# Start the application with the updated .env or docker-compose.yml
docker compose up --build
```

### Benefits of External Storage

- **Space Management**: Keep large files (podcasts, visualizations) off limited internal storage
- **Performance**: Can use faster external SSDs for improved I/O performance
- **Portability**: Easily move data between machines by moving the external drive
- **Backup**: Simpler to backup data by cloning the external drive
- **Scalability**: Easy to upgrade storage capacity without affecting the main system

### Important Considerations

⚠️ **External Drive Requirements:**
- Must be mounted and accessible before starting the application.
- The user/process running Docker (or the application directly) needs read/write permissions to this path.
- Use a reliable connection if it's a portable drive.
- SSDs are recommended for better performance.

⚠️ **macOS Specific Notes:**
- External drives are typically mounted under `/Volumes/`.
- Ensure file system compatibility (e.g., APFS, exFAT).

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
- **BM25-Enhanced Keyword Search**: Uses SQLite's FTS5 for sophisticated term frequency and document ranking.
- **Dual-Mode Search**: Simultaneously performs semantic similarity using vector embeddings (via `sqlite-vec`) and advanced keyword ranking across paper titles and abstracts.
- **Weighted Scoring**: User-adjustable weights for combining semantic and keyword scores (default: 60% semantic, 40% keyword).
- **Real-Time Scoring**: Returns individual `semantic_score`, `keyword_score` (and normalized keyword score), and combined `hybrid_score` for transparency.
- **Full Integration**: Works seamlessly with existing filters (date range, score threshold, pagination).
- **Performance Optimized**: Database-level operations using SQLite with `sqlite-vec` for vector search and FTS5 for text search.

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
- **SQLite Full-Text Search**: Leverages FTS5 virtual tables with triggers for automatic synchronization and BM25 ranking.
- **Vector Search**: Uses `sqlite-vec` extension for efficient similarity search on embeddings.
- **Index Optimization**: FTS5 and `sqlite-vec` (via its VSS component) provide efficient indexing for their respective search types.

See [docs/embedding_functionality_README.md](docs/embedding_functionality_README.md) and [docs/hybrid_search_functionality_README.md](docs/hybrid_search_functionality_README.md) for more details.
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

**Export database to archive (example from an old PostgreSQL DB):**
```bash
python -m theseus_insight.utils.db_migration.db_migrate export \
    --source-db "postgresql://user:pass@old-postgres-host:5432/theseus_pg_db" \
    --output ./pg_backup.tar.gz
```

**Import archive to new SQLite database:**
```bash
# Ensure target directory for SQLite DB exists if not in current dir
python -m theseus_insight.utils.db_migration.db_migrate import \
    --target-db "sqlite:///./data/theseus_prod.db" \
    --input ./pg_backup.tar.gz
```

**Direct migration (PostgreSQL to SQLite example):**
```bash
python -m theseus_insight.utils.db_migration.db_migrate migrate \
    --source-db "postgresql://user:pass@old-postgres-host:5432/theseus_pg_db" \
    --target-db "sqlite:///./data/migrated_theseus.db" \
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
Python backend and uses an SQLite database with `sqlite-vec`. The SQLite database file is stored in the user's application data directory.

### Building

```
cd electron-app
npm install
# No separate database build/download step needed for SQLite
npm run build
```

See [`electron-app/README.md`](electron-app/README.md) for platform specific
instructions.

---

## Troubleshooting

### SQLite-Vec Extension Loading Errors (e.g., `dlopen` or `DLL load failed`)

You might encounter errors when the Python backend starts, related to loading the `sqlite-vec` extensions (`vector0` or `vss0`). Common manifestations include:

*   `sqlite3.OperationalError: dlopen(vector0.dylib, 0x000A): tried: 'vector0.dylib' (no such file)...` (macOS specific example)
*   `sqlite3.OperationalError: undefined symbol: sqlite3_vector_init` (Linux, if the extension isn't correctly loaded by SQLite)
*   `ImportError: Fatal: Could not load sqlite-vec extensions (vector0, vss0)...` (This is the error raised by `data_handling.py` if loading fails).

**Cause**:
This type of error typically means that while the `sqlite-vec` Python package might be installed, the SQLite engine itself cannot find or load the compiled shared library files (e.g., `.dylib` on macOS, `.so` on Linux, `.dll` on Windows) that provide the actual vector search functionality.

**Troubleshooting Steps**:

1.  **Verify `sqlite-vec` Installation**:
    *   Check if `sqlite-vec` is installed and find its location:
        ```bash
        pip show sqlite-vec
        ```
    *   Try reinstalling it to ensure a clean installation:
        ```bash
        pip uninstall sqlite-vec
        pip install sqlite-vec --no-cache-dir
        ```

2.  **Consult Official `sqlite-vec` Documentation**:
    *   Visit the `sqlite-vec` GitHub repository (e.g., `https://github.com/asg017/sqlite-vec`) or its PyPI page for platform-specific installation instructions, pre-compiled binaries, or known issues.

3.  **Locate Shared Libraries**:
    *   The compiled libraries (e.g., `vector0.dylib`/`.so`, `vss0.dylib`/`.so`) are usually located within the `sqlite_vec` package directory. You can find your Python packages directory via `pip show sqlite-vec` (see `Location:` field). Inside that location, look for a `sqlite_vec` subdirectory, often containing a `lib` folder or the shared objects directly.
    *   A helper command to find the `sqlite-vec` installation path:
        ```bash
        python -c "import site; print(site.getsitepackages()[0])" # Or site.getusersitepackages()
        ```
        Then navigate into `sqlite_vec` within that path.

4.  **Set Library Path (Workaround for Local Environments)**:
    *   If the libraries are installed but not found by SQLite, you might need to tell your system where to find them. This is a common workaround for local development but might not be suitable for all deployment scenarios.
    *   **macOS**:
        ```bash
        export DYLD_LIBRARY_PATH=/path/to/directory/containing/dylibs:$DYLD_LIBRARY_PATH
        ```
        (Replace `/path/to/directory/containing/dylibs` with the actual path found in step 3, e.g., `.../site-packages/sqlite_vec/lib`)
    *   **Linux**:
        ```bash
        export LD_LIBRARY_PATH=/path/to/directory/containing/sos:$LD_LIBRARY_PATH
        ```
        (Replace `/path/to/directory/containing/sos` accordingly, e.g., `.../site-packages/sqlite_vec/lib`)
    *   **Windows**: Add the directory containing the `.dll` files to your system's `PATH` environment variable.
    *   **Note**: These environment variables must be set in the terminal session where you launch the Python application or configured for the environment where the backend process runs (e.g., for the Electron app's backend).

5.  **Conda Environments**:
    *   If using Conda, ensure `sqlite-vec` is installed correctly within the active Conda environment. Conda has its own way of managing library paths. Sometimes, installing from specific Conda channels (if available for `sqlite-vec`) can resolve such issues.

6.  **Electron App Specifics**:
    *   If this error occurs in the packaged Electron application, it indicates an issue with how the `sqlite-vec` compiled extensions were (or weren't) bundled with the Python dependencies. The `python_deps` bundling mechanism in `electron-app/bundle-python-deps.sh` should correctly include these shared libraries from the `sqlite-vec` package. Ensure that the `asarUnpack` configuration in `electron-app/package.json` includes any necessary patterns if these libraries are being packed into the asar archive and need to be unpacked at runtime. However, typically, Python C extensions are used directly from their location within the `python_deps` bundle.

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
- [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://pydantic-docs.helpmanual.io/), [SQLite](https://www.sqlite.org/) with [sqlite-vec](https://github.com/asg017/sqlite-vec) for backend processing.

Theseus Insight is maintained by [M. Chimiste](https://github.com/M-Chimiste) & contributors.

