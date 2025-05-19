# Theseus Insight

Theseus Insight is a multi-purpose project that processes PDF research papers, ranks them against your research interests, generates personalized newsletters, and can also produce podcast episodes (including optional visualized audio). It uses a combination of FastAPI endpoints, language models (LLMs), text-to-speech engines, and various utility scripts.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Architecture and Modules](#architecture-and-modules)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [Running the API](#running-the-api)
- [Key Endpoints](#key-endpoints)
  - [PDF Uploads](#pdf-uploads)
  - [Podcast Generation](#podcast-generation)
  - [Script Management](#script-management)
  - [Visualizer Generation](#visualizer-generation)
  - [Theseus Insight Run Orchestration](#theseus-insight-run-orchestration)
- [Using Theseus Insight as a Library](#using-theseus-insight-as-a-library)
  - [Core Workflow](#core-workflow)
  - [Example Usage](#example-usage)
- [License](#license)
- [Credits](#credits)

---

## Overview

Theseus Insight is designed to automate tasks around recent research papers. It:

1. **Fetches & parses** papers from [paperswithcode.com](https://paperswithcode.com/) dumps within a date range.
2. **Embeds** papers, checks their relevance to your research interests, and ranks them with large language models.
3. **Generates** personalized newsletters describing those papers.
4. **Produces** a TTS-based podcast from PDF or textual content, optionally with a dynamic visualizer video.
5. **Sends** the newsletter via Gmail (if configured), and can optionally upload podcast videos to YouTube.

It leverages multiple text models (Anthropic, OpenAI, Ollama, or Google Gemini) for summarization, ranking, or conversation tasks, and can use different TTS providers (Polly, OpenAI TTS, or [KokoroTTS](https://github.com/fakeyh/kokoro-tts)).

---

## Features

- **FastAPI** server with endpoints to handle:
  - Uploading PDFs
  - Generating scripts & podcasts
  - Managing TTS visualizer generation
  - Checking generation status, downloading results
  - Handling a "Theseus Insight run" that orchestrates the entire pipeline
- **In-memory or SQLite** database for:
  - Storing references to papers
  - Saving newsletters
  - Tracking podcasts & logs
- **Flexible LLM usage**: can switch among Anthropic, OpenAI, Ollama, or Gemini for inference tasks.
- **TTS**: Choose KokoroTTS, Amazon Polly, or OpenAI TTS. Generate final MP3 or WAV files.
- **Podcast**: Compose multi-speaker dialogues automatically, then convert them to TTS, merge segments into a final audio file, and optionally create a matrix-based visualizer.
- **Newsletter**: Summarizes new relevant papers, providing references and sending them via email.
- **Configurable orchestration**: All model and pipeline orchestration is handled via `config/orchestration.json`.

---

## Architecture and Modules

```
theseus_insight/
  api/
    routers/
      pdf.py          # Handles PDF upload
      podcast.py      # Long-running tasks to generate podcasts
      script.py       # Script management for saved dialogues
      visualizer.py   # Endpoint to generate video visualizers from audio
    theseus_insight_routes.py # Endpoint to orchestrate Theseus Insight runs
    __init__.py
    uploads/         # Uploaded files
    scripts/         # Saved scripts
  communication/
    communication.py  # Gmail email sending
    youtube_integration.py # YouTube uploading
    __init__.py
  data_model/
    dialog.py         # Pydantic models for dialogues
    data_handling.py  # SQLite DB interactions (papers, newsletters, podcasts)
    papers.py         # Paper metadata models
    __init__.py
  data_processing/
    arxiv.py          # Arxiv data download/processing
    harvester.py      # Data harvesting utilities
    __init__.py
  inference/
    llm.py            # LLM classes for Anthropic, OpenAI, Ollama, Gemini, etc.
    tts.py            # TTS classes for Kokoro, Polly, OpenAI TTS
    __init__.py
  pdf/
    parsers.py        # PDF -> Markdown parsers (using docling)
    processing.py     # Table & figure extraction from PDFs
    __init__.py
  podcast/
    generator.py      # Podcast generation logic (main: PodcastGenerator)
    visualizer.py     # Visualizer logic (pygame + moviepy)
    __init__.py
  prompt/
    prompting.py      # Jinja2-based prompt decorator
    data_models.py
    newsletter_prompts.py
    podcast_prompts.py
    system_prompts.py
    templates.py
    __init__.py
  constants.py        # Project-wide constants
  main.py             # FastAPI entrypoint
  theseus_insight.py  # Main orchestrator class (TheseusInsight)
  utils.py            # Cosine similarity, date helpers, other utilities
  __init__.py         # Root init
config/
  orchestration.json  # Model and pipeline orchestration config
run_paperpal.py       # CLI entrypoint for running the full pipeline
```

**Key classes include:**
- `TheseusInsight`: The main orchestrator to download, embed, rank, generate newsletters, produce podcasts, and optionally email or upload final artifacts.
- `PodcastGenerator`: Assembles multi-speaker dialogues from PDF or text, converts them to TTS, and optionally produces a matrix-based visualizer.
- Various FastAPI routers for structured endpoints.

---

## Installation

1. **Clone or download** this repository.
2. **Install dependencies**. For example:
   ```bash
   pip install -r requirements.txt
   ```
   (Make sure your environment has the relevant TTS/LLM dependencies.)

3. **(Optional) Configure LLM & TTS providers** as described in the Environment Variables section.

---

## Running the API

Run the FastAPI app using uvicorn:

```bash
uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload
```

View interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---
## React Frontend (MVP)

A minimal React application is provided in the `react_frontend` directory. It communicates with the FastAPI backend using REST and WebSocket endpoints.

```bash
cd react_frontend
npm install
npm run dev
```

The development server expects the backend to be running on the same host. Adjust URLs in `src/App.jsx` if your API is hosted elsewhere.

---

## Key Endpoints

### PDF Uploads
- **`POST /api/pdf/upload`**  Upload a single PDF file.
- **`POST /api/pdf/batch-upload`**  Upload multiple PDFs.

### Podcast Generation
- **`POST /api/podcast/generate`**  Generate a podcast from PDFs or text.
- **`GET /api/podcast/status/{task_id}`**  Check status of a podcast generation task.
- **`GET /api/podcast/download/{filename}`**  Download the final podcast file.

### Script Management
- **`POST /api/script/save`**  Save a generated script.
- **`GET /api/script/list`**  List saved scripts.
- **`GET /api/script/download/{filename}`**  Download a saved script.

### Visualizer Generation
- **`POST /api/visualizer/generate`**  Generate a visualizer video.
- **`GET /api/visualizer/status/{task_id}`**  Check visualizer generation status.

### Theseus Insight Run Orchestration
- **`POST /api/theseus_insight/run`**  Orchestrate the full pipeline (papers, newsletter, podcast, etc).

---

## Using Theseus Insight as a Library

You can use the main orchestrator directly in your own scripts:

```python
from theseus_insight import TheseusInsight

ti = TheseusInsight(
    research_interests_path="config/research_interests.txt",
    orchestration_config="config/orchestration.json",
    # ... other config options ...
)
ti.run()
```

Or use the CLI entrypoint:

```bash
python run_theseus_insight.py --generate-podcast True --generate-email True
```

---

## License

This project is licensed under the [Apache License 2.0](LICENSE) unless otherwise stated in specific files.

---

## Credits

- [paperswithcode.com](https://paperswithcode.com/) for research paper data.
- [Docling](https://github.com/doclingjs/docling) for document parsing.
- [pydub](https://github.com/jiaaro/pydub) for audio processing.
- [KokoroTTS](https://github.com/fakeyh/kokoro-tts), [Amazon Polly](https://aws.amazon.com/polly/), [OpenAI TTS](https://platform.openai.com/docs/) for text-to-speech.
- [FastAPI](https://fastapi.tiangolo.com/), [Pydantic](https://pydantic-docs.helpmanual.io/), [SQLite](https://www.sqlite.org/) for backend processing.

Theseus Insight is maintained by [M. Chimiste](https://github.com/fakeyh) & contributors.

