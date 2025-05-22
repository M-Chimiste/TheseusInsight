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
- [Key Endpoints](#key-endpoints)
  - [PDF Uploads](#pdf-uploads)
  - [Podcast Generation](#podcast-generation)
  - [Script Management](#script-management)
  - [Visualizer Generation](#visualizer-generation)
  - [Theseus Insight Run Orchestration](#theseus-insight-run-orchestration)
- [Using Theseus Insight as a Library](#using-theseus-insight-as-a-library)
- [License](#license)
- [Credits](#credits)

---

## Overview

Theseus Insight fetches and ranks papers from [paperswithcode.com](https://paperswithcode.com/) or provided PDFs, produces newsletters summarising the most relevant papers and can create podcast episodes with optional video visualisations.  A modern React UI communicates with the FastAPI backend via REST and WebSocket endpoints, providing real‑time feedback while background tasks run.

---

## Quickstart

1. **Clone the repository**
   ```bash
   git clone https://github.com/youruser/TheseusInsight.git
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
- **SQLite database** for storing papers, runs and configuration data.
- **Flexible LLM and TTS providers** including OpenAI, Anthropic, Gemini, Ollama, Polly and KokoroTTS.
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
2. (Optional) install Node.js 18+ and build the frontend
   ```bash
   cd theseus-ui
   npm install
   npm run build
   ```
3. Configure environment variables as shown below.

---

## Environment Variables

Create a `.env` file in the project root containing keys and settings:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | API key for OpenAI models and TTS |
| `ANTHROPIC_API_KEY` | API key for Anthropic Claude models |
| `GOOGLE_API_KEY` | API key for Google Gemini models |
| `OLLAMA_URL` | Base URL of a local Ollama server (default `http://127.0.0.1:11434`) |
| `GMAIL_SENDER_ADDRESS` | Gmail address used to send newsletters |
| `GMAIL_APP_PASSWORD` | Gmail App password for SMTP authentication |
| `THESEUS_DB_PATH` | Path to the SQLite database (default `data/papers.db`) |
| `CLIENT_ID`, `PROJECT_ID`, `CLIENT_SECRET`, `REDIRECT_URI` | OAuth credentials for the YouTube upload helper |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `REGION_NAME` | Credentials for Amazon Polly TTS |
| `PRODUCTION_FRONTEND_URL` | Allowed origin for CORS when deploying the frontend |

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

## License

This project is licensed under the [Apache License 2.0](LICENSE) unless otherwise stated.

---

## Credits

- [paperswithcode.com](https://paperswithcode.com/) for research paper data.
- [Docling](https://github.com/doclingjs/docling) for document parsing.
- [pydub](https://github.com/jiaaro/pydub) for audio processing.
- [KokoroTTS](https://github.com/fakeyh/kokoro-tts), [Amazon Polly](https://aws.amazon.com/polly/), [OpenAI TTS](https://platform.openai.com/docs/) for text-to-speech.
- [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://pydantic-docs.helpmanual.io/), [SQLite](https://www.sqlite.org/) for backend processing.

Theseus Insight is maintained by [M. Chimiste](https://github.com/fakeyh) & contributors.

