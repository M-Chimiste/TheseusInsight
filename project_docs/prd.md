# Theseus Insight — NiceGUI Edition

Product Requirements Document (v0.2-NG)

---

## 1 · Vision & Purpose

Theseus Insight already ships a FastAPI backend that harvests arXiv papers and auto‑generates newsletters, podcasts and audio visualisations. We now want a **zero‑JavaScript graphical interface** so that non‑technical users can run the full workflow without a terminal or any web‑dev knowledge.

> **North‑star outcome:** “Within **5 minutes**, a first‑time user can `pip install` / pull a container, open a browser, pick their preferences in a NiceGUI app, and publish a newsletter or podcast.”

---

## 2 · Goals & Non‑Goals

| ID | Goal                                                                                           | Success Metric                                          |
| -- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| G1 | Settings pane that mirrors `config/orchestration.json` one‑to‑one.                             | ≥ 90 % of beta users locate & edit settings unaided.    |
| G2 | Wizard flows for Newsletter, Podcast, and Visualiser, each with real‑time task progress.       | ≥ 95 % of launched jobs finish without user abandoning. |
| G3 | Papers Explorer table with filter/sort over 10 k rows in < 2 s.                                | p95 response time < 2 s.                                |
| G4 | Single‑command local start (`python -m theseus_insight.ui` **or** `docker run …`).             | “Getting Started” ≤ 5 CLI commands across OSes.         |
| G5 | Persistent user data (`papers.db`, assets, settings) across restarts via bind‑mount or volume. | 100 % data retained after container stop/start.         |

**Out of scope (v0.2‑NG)**

* Multi‑tenant SaaS hosting.
* Refactor of core harvesting/business logic.

---

## 3 · Personas

| Persona                       | Description                      | Key Jobs‑To‑Be‑Done                           |
| ----------------------------- | -------------------------------- | --------------------------------------------- |
| **Alex – Research Lead**      | Curates weekly AI update.        | Adjust arXiv filters, send Friday newsletter. |
| **Jamie – Content Creator**   | Makes YouTube shorts & podcasts. | Upload PDFs, generate podcast + viz.          |
| **Taylor – Data Scientist**   | Evaluates papers for R\&D.       | Browse papers DB, flag interesting items.     |
| **Pat – Solo Hacker** *(NEW)* | Has no web‑dev background.       | Runs whole stack locally, tweaks Python only. |

---

## 4 · User‑Facing Epics & Stories

### Epic A — Settings & Config (`/settings`)

| Story   | Description                                                                                       | Acceptance                                                           |
| ------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| **A‑1** | User edits arXiv categories, LLM/TTS choices, SMTP creds in a NiceGUI `ui.card` with bound model. | Edits auto‑write to JSON; backend reloads on change without restart. |
| **A‑2** | “Test email” button sends a templated email with current SMTP settings.                           | Green toast on success, red toast on failure.                        |

### Epic B — Newsletter Wizard (`/newsletter`)

1. Date‑range picker → **Run**
2. Optional checkbox **Also podcast & viz** → `POST /theseus_insight/run`
3. Live progress modal (`ui.dialog` + `ui.linear_progress`) bound to WebSocket events.

### Epic C — Stand‑alone Podcast (`/podcast`)

* Drag‑and‑drop PDFs / paste arXiv URLs (`ui.upload` + `ui.input`).
* Toggle **Create visualiser**, upload intro music.
* Live status stream.

### Epic D — Audio Visualiser (`/visualiser`)

* Upload MP3 (`ui.upload`), pick colour/Fx presets (`ui.select`, `ui.slider`).
* Render queue list with download buttons.

### Epic E — Papers Explorer (`/papers`)

* Server‑side `datatable` backed by SQLite query; bulk‑select actions **Add to Newsletter** and **Generate Podcast**.

---

## 5 · Functional Requirements

| ID  | Requirement                                          | API Contract / NiceGUI Mechanism                      |
| --- | ---------------------------------------------------- | ----------------------------------------------------- |
| F‑1 | Expose CRUD for settings ↔ `orchestration.json`.     | NiceGUI model ↔ Pydantic ↔ file write.                |
| F‑2 | Upload ≥ 5 PDFs (≤ 100 MB each) without blocking UI. | `ui.upload` streams to `/pdf/batch-upload`.           |
| F‑3 | Launch newsletter job & show streaming progress.     | `POST /theseus_insight/run` + WS `/task/{id}/stream`. |
| F‑4 | Launch podcast job with files/URLs.                  | `POST /podcast/generate` + status WS.                 |
| F‑5 | Download finished assets.                            | Signed URL `GET /download/{file}`.                    |
| F‑6 | Query, paginate, filter Papers table server‑side.    | New endpoint `GET /papers?offset…`.                   |

---

## 6 · Non‑Functional Requirements

* **Performance** – First Interactive Paint < 1 s (localhost).
* **Reliability** – Background tasks persist; WS drops do not kill job.
* **Security** – Container runs as non‑root; CORS `same-origin`; secrets in mounted volume.
* **Accessibility** – Colour contrast ≥ 4.5:1; keyboard‑navigable.
* **Portability** – Works on ARM64 & x86\_64; base image `python:3.11-slim`.

---

## 7 · Information Architecture & Screens

| Page                  | Route         | Key Components                                                      |
| --------------------- | ------------- | ------------------------------------------------------------------- |
| **Dashboard**         | `/`           | `ui.card` quick‑start buttons; recent jobs (`ui.table`).            |
| **Settings**          | `/settings`   | Tab group → General · Models · ArXiv · Email · Audio/Video.         |
| **Newsletter Wizard** | `/newsletter` | `ui.datepicker`, advanced collapsible, run button, progress dialog. |
| **Podcast Wizard**    | `/podcast`    | `ui.upload`, `ui.input`, `ui.switch` (visualiser), run/progress.    |
| **Visualiser**        | `/visualiser` | Upload, presets, render queue (`ui.table`).                         |
| **Papers Explorer**   | `/papers`     | Server‑side `ui.table` with filter header.                          |
| **Job History**       | `/jobs`       | Table + expandable rows with logs & download links.                 |

---

## 8 · Technical Architecture

```
┌──────────── Browser (NiceGUI client) ────────────┐
│  HTML/JS delivered by NiceGUI (Tailwind‑Vue mix) │
└───────────────▲──────────▲───────────────────────┘
                │ REST     │ WebSocket (events)
┌───────────────┴──────────┴───────────────────────┐
│      FastAPI app  ─┬─  NiceGUI ui object         │
│  (domain routers)  │  (mounted at /)             │
│  /pdf /podcast …   │  ui.page('/…')              │
└──────────┬─────────┴───────────┬─────────────────┘
           │ SQLite (papers.db)  │ Assets on disk
           └──────────┬──────────┘
             Docker Volume / Bind Mount
```

---

## 9 · Packaging & Deployment

### 9.1 Local (dev)

```bash
pip install theseus-insight[ui]
python -m theseus_insight.ui
```

### 9.2 Docker (optional Phase 2)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y ffmpeg git && rm -rf /var/lib/apt/lists/*
COPY . /app
RUN pip install --no-cache-dir ".[ui]"
ENV THESEUS_DATA_DIR=/data
VOLUME ["/data"]
EXPOSE 8000
CMD ["uvicorn", "theseus_insight.ui:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 10 · Persistence Layout

| Path              | Purpose                                        | Mount               |
| ----------------- | ---------------------------------------------- | ------------------- |
| `/data/papers.db` | SQLite paper metadata                          | Bind‑mount / volume |
| `/data/output`    | MP3/MP4, images                                | Same                |
| `/config`         | `orchestration.json`, `research_interests.txt` | Bind‑mount (rw)     |

---

## 11 · Observability & Metrics

* Task events broadcast on WS `task/{id}/stream` (state, percent, ETA).
* Prometheus `/metrics` via `fastapi‑instrumentator`; labels: `task_type`, `model`, `status`.
* Job cost table (tokens × price) stored in SQLite `logs`.

---

## 12 · Acceptance Criteria

* [ ] NiceGUI UI reachable at root URL; no JS/TS build step required.
* [ ] G1–G5 metrics met in closed beta.
* [ ] Settings persist after container restart.
* [ ] Concurrent jobs ≥ 3 handled with correct state per user.
* [ ] Unit‑test coverage ≥ 80 % for new UI helper modules.
* [ ] Image size < 5 GB, boots on ARM64 + x86\_64.

---

## 13 · Risks & Mitigations

| Risk                                     | Likelihood | Impact | Mitigation                           |
| ---------------------------------------- | ---------- | ------ | ------------------------------------ |
| NiceGUI websocket drops under heavy load | M          | M      | Fallback polling every 3 s.          |
| Browser file‑upload > 100 MB times out   | M          | L      | Chunked upload streaming + size cap. |
| Task crashes leave stale `TASK_STATUS`   | L          | M      | Add expiry + cleanup on startup.     |

---

### Appendix A — Reference Backend Endpoints

Up‑to‑date in `theseus_insight/api/routers/`. UI must treat them as source of truth.
