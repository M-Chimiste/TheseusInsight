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
  - [Model Management](#model-management)
  - [Papers](#papers)
  - [Settings](#settings)
  - [Runs](#runs)
  - [Tasks](#tasks)
  - [Newsletter Generation](#newsletter-generation)
  - [Podcast Generation](#podcast-generation)
  - [WebSocket Status](#websocket-status)
- [Using Theseus Insight as a Library](#using-theseus-insight-as-a-library)
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

- **FastAPI** server for model management, paper retrieval, settings, and launching newsletter or podcast tasks.
- **WebSocket** updates for long-running tasks so you can monitor progress in real time.
- **SQLite** database storing papers, newsletters, podcasts and settings.
- **Flexible LLM usage**: switch among Anthropic, OpenAI, Ollama or Gemini for inference tasks.
- **TTS**: Choose KokoroTTS, Amazon Polly or OpenAI TTS to produce final MP3 or WAV files.
- **Podcast**: Compose multi-speaker dialogues automatically, convert them to TTS and optionally generate a matrix-style visualizer.
- **Newsletter**: Summarize new relevant papers and email them to configured recipients.
- **Configurable orchestration** via `config/orchestration.json`.

---

## Architecture and Modules

```
theseus_insight/
  api/
    __init__.py
    models.py       # Pydantic API models
    tasks.py        # Background task management
  communication/
    communication.py  # Gmail email sending
    youtube_integration.py # YouTube uploading
    __init__.py
  data_model/
    data_handling.py  # SQLite DB interactions
    dialog.py         # Dialogue models
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
run_theseus_insight.py  # CLI entrypoint for running the pipeline
```

**Key classes include:**
- `TheseusInsight`: The main orchestrator to download, embed, rank, generate newsletters, produce podcasts, and optionally email or upload final artifacts.
- `PodcastGenerator`: Assembles multi-speaker dialogues from PDF or text, converts them to TTS, and optionally produces a matrix-based visualizer.
- FastAPI endpoints are defined in `main.py` and leverage `api/models.py` and `api/tasks.py` for data handling.

---

## Installation

1. **Clone or download** this repository.
2. **Install dependencies**. For example:
   ```bash
   pip install -r requirements.txt
   ```
   (Make sure your environment has the relevant TTS/LLM dependencies.)

3. **(Optional) Configure environment variables** to enable LLM and TTS providers.

---

## Environment Variables

Set the following variables in your environment (or a `.env` file) to enable
model access and email functionality:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- `ELEVENLABS_API_KEY`
- `GMAIL_SENDER_ADDRESS`
- `GMAIL_APP_PASSWORD`

---

## Running the API

Run the FastAPI app using uvicorn:

```bash
uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload
```

View interactive docs at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Key Endpoints

### Model Management
- **`GET /api/models`** – list registered models.
- **`POST /api/models`** – add a new model.
- **`DELETE /api/models/{model_id}`** – remove a model.

### Papers
- **`GET /api/papers`** – list papers with optional filtering and pagination.

### Settings
- **`GET /api/settings/orchestration`** / **`PUT /api/settings/orchestration`**
- **`GET /api/settings/research-interests`** / **`PUT /api/settings/research-interests`**
- **`GET /api/settings/email-recipients`** / **`PUT /api/settings/email-recipients`**
- **`GET /api/settings/visualizer-settings`**
- **`POST /api/settings/send-test-email`**

### Runs
- **`GET /api/runs`** – list previous newsletters or podcasts.
- **`DELETE /api/runs/{run_id}/artifact`** – delete an associated artifact.

### Tasks
- **`GET /api/tasks/{task_id}/status`** – check progress of a running task.
- **`GET /api/tasks/{task_id}/result`** – fetch the final result once complete.
- **`GET /api/tasks/{task_id}/download/{file_type}`** – download the generated artifact.

### Newsletter Generation
- **`POST /api/newsletter/run`** – start the newsletter pipeline.

### Podcast Generation
- **`POST /api/podcast/generate`** – start the podcast pipeline.

### WebSocket Status
- **`/ws/newsletter/{task_id}`** – real-time newsletter status updates.
- **`/ws/podcast/{task_id}`** – real-time podcast status updates.

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

