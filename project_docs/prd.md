# Theseus Insight UI & Dockerized Deployment – Product Requirements Document (v0.1)

---

## 1. Vision & Purpose

Theseus Insight currently exposes a powerful FastAPI backend for harvesting arXiv papers, generating AI‑driven newsletters, podcasts, and audio visualizations. The purpose of this project is to add a **first‑class graphical user interface (GUI)** and deliver the whole system as a **single Docker container**, empowering non‑technical knowledge‑workers to configure, run, and review Theseus Insight workflows without touching the command line.

**North‑star outcome:** “In < 5 minutes a user can pull the Docker image, start the container, open a browser, configure their preferences, and publish a newsletter or podcast.”

---

## 2. Goals & Non‑Goals

| #  | Goal                                                                                                                                                   | Success Metric                                                  |
| -- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| G1 | Provide an intuitive settings panel that maps 1‑for‑1 to existing configuration files (`config/orchestration.json`, research‑interest text, etc.).     | 90 % of beta testers can locate and edit settings unaided.      |
| G2 | Wizard‑style flows to execute (a) Newsletter, (b) Podcast, (c) Visualization jobs with progress indicators that surface `/status/{task_id}` endpoints. | 95 % of jobs launched from UI complete without user abandoning. |
| G3 | Data Explorer table for **Papers DB** with filters, ratings, and multi‑select to feed ad‑hoc newsletters/podcasts.                                     | < 2 seconds mean response when filtering 10 k papers.           |
| G4 | One‑command Docker deployment (`docker run -p 8000:8000 theseus/insight-ui:latest`).                                                                   | “Getting Started” takes < 5 commands on macOS/Linux/Windows.    |
| G5 | Zero‑config local persistence of `papers.db`, generated assets and user settings via bind‑mount or named Docker volume.                                | Data survives container restarts in 100 % of test runs.         |

**Non‑Goals**

* Re‑architecting backend business logic (FastAPI routers remain the source of truth). 
* Large‑scale multi‑tenant SaaS deployment—this PRD targets single‑user or small‑team self‑hosting.

---

## 3. Personas

| Persona                     | Description                         | Key Jobs‑To‑Be‑Done                                                         |
| --------------------------- | ----------------------------------- | --------------------------------------------------------------------------- |
| **Alex – Research Lead**    | Curates weekly AI updates for lab.  | ‑ Adjust arXiv filters, send newsletter every Friday.                       |
| **Jamie – Content Creator** | Produces YouTube shorts & podcasts. | ‑ Upload PDFs, generate podcast & visualization, ship to YouTube.           |
| **Taylor – Data Scientist** | Evaluates papers for internal R\&D. | ‑ Browse historical papers, flag interesting ones, request podcast summary. |

---

## 4. Use‑Case Summary (Epics & User Stories)

### Epic A – **Preferences & Config**

*UA‑1* As a user I can open **Settings ▸ Newsletter & Podcast** and set:

* Main category (e.g. ‘cs’) and sub‑categories multi‑select ➜ persisted to `config/orchestration.json`.
* LLM / TTS model drop‑downs with advanced toggles (temperature, max tokens).
* Email recipients list & SMTP creds.
  *Acceptance:* Edited values are written to disk and reflected by next backend run without container restart.

### Epic B – **Generate Newsletter**

*UB‑1* From **Dashboard** I click *Create Newsletter*, pick a date range, and press *Run*.
*UB‑2* Optional check‑box **“Also generate podcast + visualization”** triggers combined workflow via `POST /theseus_insight/run`. Progress bar binds to `/theseus_insight/status/{task}`.

### Epic C – **Standalone Podcast**

*UC‑1* I drag‑and‑drop PDFs or paste arXiv links ➜ UI calls `POST /podcast/generate` with `files[]`, `urls`.
*UC‑2* I can toggle **Visualizer** on/off and upload *intro music*.

### Epic D – **Audio Visualization**

*UD‑1* In **Visualizer** page I upload an MP3, tweak color/fx presets, hit *Render* ➜ UI calls `POST /visualizer/generate`.

### Epic E – **Papers Explorer**

*UE‑1* Navigate to **Papers** table displaying rows from SQLite `papers.db`; columns: Title, Created, Score, Similarity, Related?.
*UE‑2* Multi‑select rows → *Add to Newsletter* or *Generate Podcast* buttons issue backend calls with selected IDs.

---

## 5. Functional Requirements

| ID  | Requirement                                                                                    | API Contract                                                             |
| --- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| F‑1 | UI **must** expose CRUD for settings mapped to `orchestration.json` & research interests text. | Local file read/write via backend helper; hot‑reload signal.             |
| F‑2 | UI **must** upload ≥ 5 PDFs ≤ 100 MB each.                                                     | `POST /pdf/batch-upload` (multipart form). citeturn0file0             |
| F‑3 | UI **must** launch newsletter job with JSON config and show streaming progress.                | `POST /theseus_insight/run` ⇄ `GET /theseus_insight/status/{id}`.        |
| F‑4 | UI **must** launch podcast generation with uploaded files/URLs.                                | `POST /podcast/generate` ⇄ `GET /podcast/status/{id}`. citeturn0file0 |
| F‑5 | UI **must** download finished assets.                                                          | `GET /podcast/download/{file}`; `GET /visualizer/download/{file}`.       |
| F‑6 | UI **must** query, paginate, filter Papers table server‑side.                                  | `GET /papers` (new endpoint) or direct SQLite query helper.              |

---

## 6. Non‑Functional Requirements

* **Performance:** First meaningful paint < 1.5 s (local). CSV/PDF uploads stream to disk to avoid memory spikes.
* **Reliability:** Background jobs survive UI disconnect; task state held in `TASK_STATUS` dict. Failed jobs surface error tracebacks.
* **Security:** Run container as non‑root; enable CORS only for same‑origin UI. User secrets stored in mounted `config/` volume.
* **Portability:** Image must run on ARM64 & x86\_64 (base `python:3.11-slim` multi‑arch).

---

## 7. Information Architecture & Screens

| Page                  | Route         | Components                                                                |
| --------------------- | ------------- | ------------------------------------------------------------------------- |
| **Dashboard**         | `/`           | Quick‑start cards: Newsletter, Podcast, Visualization; Recent jobs table. |
| **Settings**          | `/settings`   | Tabs: General, Models, ArXiv Filters, Email, Audio/Video.                 |
| **Newsletter Wizard** | `/newsletter` | Date range picker, Advanced (LLM params), Run button, Progress drawer.    |
| **Podcast Wizard**    | `/podcast`    | File drop‑zone, URL input, Visualizer toggle, Intro music upload.         |
| **Visualizer**        | `/visualizer` | Audio upload, Visual settings panel, Render queue.                        |
| **Papers Explorer**   | `/papers`     | DataGrid with search, filters, bulk actions.                              |
| **Job History**       | `/jobs`       | List + detail view with download links and logs.                          |

UI built with **React + Vite** (or **HTMX** for lightweight), using **tanstack‑table** for grids and **Chakra‑UI** for styling; compiled assets served by FastAPI’s `StaticFiles`.

---

## 8. Technical Architecture

```
┌───────────────────────────┐
│        Browser UI         │
└──────────▲──────▲─────────┘
           │REST  │WS (live progress)
┌──────────┴──────┴─────────┐
│       FastAPI Backend     │  ← existing codebase
│  • /pdf • /podcast • etc. │
└──────────┬────────┬───────┘
           │SQLite  │Disk assets
┌──────────┴────────┴───────┐
│   Persistent Volume (/data)│
└───────────────────────────┘
```

---

## 9. Dockerization

**Dockerfile (high‑level)**

```Dockerfile
FROM python:3.11-slim
WORKDIR /app
# 1. Install system deps
RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*
# 2. Copy code & install python deps
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
# 3. Expose port & define entrypoint
EXPOSE 8000
ENV THESEUS_DATA_DIR=/data
VOLUME ["/data"]
CMD ["uvicorn", "theseus_insight.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Usage**

```bash
# Pull and run in detached mode, persisting outputs
docker run -d --name theseus \
  -p 8000:8000 \
  -v $(pwd)/data:/data \
  -e GOOGLE_API_KEY=… -e OPENAI_API_KEY=… \
  theseus/insight-ui:latest
```

*Stretch:* Provide optional `docker‑compose.yml` to pair with **nginx** (frontend static) and **watchtower** auto‑updates.

---

## 10. Data & Config Persistence

| Path inside container                 | Description                                 | Mount Suggestion       |
| ------------------------------------- | ------------------------------------------- | ---------------------- |
| `/data/papers.db`                     | SQLite DB                                   | Bind‑mount volume.     |
| `/data/output_audio` & `/data/output` | Generated MP3/MP4                           | Same volume.           |
| `/config`                             | orchestration.json, research\_interests.txt | Bind‑mount read‑write. |

Changes in UI are written to these paths via backend helper utilities.

---

## 11. Metrics & Observability

* **Job duration**, **success rate**, **LLM cost estimate** logged per task to `logs` table.
* Prometheus endpoint `/metrics` (fastapi‑instrumentator) for container‑level CPU/RAM.

---

## 12. Acceptance Criteria

* [ ] Docker image builds under 5 GB and starts successfully on both Apple Silicon & AMD64.
* [ ] All five epics (A‑E) reachable from Dashboard and functional.
* [ ] Settings persist across container restarts.
* [ ] Concurrent jobs (≥ 3) handled without race on `TASK_STATUS`.
* [ ] Unit tests (> 80 % coverage) for new UI helper APIs.

---

### Appendix A – Reference Backend Endpoints

See FastAPI router modules (`theseus_insight/api/routers/*.py`) for definitive list.

---