# Theseus Insight – Phase 1 Task Graph (NiceGUI, Local-Dev)

*CI/CD is still deferred; all work runs and is tested locally.*

---

## Overview

Phase 1 delivers a **NiceGUI-based** GUI that shares the same FastAPI process and SQLite storage as the existing backend. Key work streams:

1. Stand-alone NiceGUI pages **Settings, Newsletter, Podcast, Visualiser, Papers, Dashboard**.
2. Minimal FastAPI additions (settings CRUD, task progress WS, paginated paper search).
3. Pure-Python dev workflow – **no Node, Vite, or Docker** in this phase.

---

## Task Table

| ID                                   | Depends On | Objective (local)                                    |
| ------------------------------------ | ---------- | ---------------------------------------------------- |
| **T01 – Settings API**               | –          | CRUD endpoints wrapping file configs                 |
| **T02 – Task Status WS**             | –          | REST + WebSocket for progress updates                |
| **T03 – Papers Query API**           | –          | Paginated search over `papers.db`                    |
| **T04 – NiceGUI Bootstrap & Health** | –          | Initialise `ui` object, mount at `/`, add `/healthz` |
| **T05 – NiceGUI Scaffold**           | T01-T04    | Create shared layout, nav, & util components         |
| **T06 – Settings Page**              | T05 T01    | Tabbed settings UI bound to `/settings`              |
| **T07 – Newsletter Wizard**          | T05 T02    | Date/category form → `/theseus_insight/run`          |
| **T08 – Podcast Wizard**             | T05 T02    | PDF/URL upload → `/podcast/generate`                 |
| **T09 – Visualiser Page**            | T05 T02    | Audio→video form & queue                             |
| **T0A – Papers Explorer**            | T05 T03    | Virtualised table & bulk actions                     |
| **T0B – Dashboard & Nav**            | T06-T0A    | Quick-start cards, recent jobs, top nav              |

---

## Detailed Tasks

### T01 – **Settings API**

Expose `/settings` endpoints that read/write `config/orchestration.json` & `research_interests.txt`.

* **Deliverables**

  * `GET /settings`, `PUT /settings` with Pydantic validation.
  * Unit tests: `pytest tests/unit/test_settings_route.py`.
* **Done When** edits persist to disk and downstream tasks pick up changes without server restart.

---

### T02 – **Task Status & WebSocket**

Provide unified progress tracking over the existing `TASK_STATUS` dict.

* **Deliverables**

  * `GET /status/{task_id}` returns JSON snapshot.
  * `/ws/progress/{task_id}` streams updates (NiceGUI `ui.run_async`).
  * Helper `broadcast_progress` in shared module.
* **Done When** a dummy long-running task streams progress to a local browser tab.

---

### T03 – **Papers Query API**

High-performance endpoint for the Papers Explorer page.

* Query params: `q`, `score_min`, `score_max`, `limit`, `offset`, `sort`.
* Adds SQLite indexes on `score`, `created`.
* Returns `{total, rows:[…]}`.

---

### T04 – **NiceGUI Bootstrap & Health**

* Instantiate `app = NiceGUI()` (aliased as `ui`).
* Mount it in `theseus_insight/ui.py`.
* Add `GET /healthz` → `{status: "ok"}`.
* Dev entrypoint: `python -m theseus_insight.ui --reload` (uvicorn hot-reload).

---

### T05 – **NiceGUI Scaffold & Shared Components**

* Create `<MainLayout>` function wrapping pages with side-nav, light/dark toggle.
* Implement `<JobDrawer>` that subscribes to `/ws/progress` and shows task details.
* Helper module `ui_helpers.py` for common widgets (date range picker, file-upload).

---

### T06 – **Settings Page**

* Tabs: General, Models, ArXiv, Email, Audio/Video.
* Uses NiceGUI `ui.tabs` + `ui.input`, `ui.select`, `ui.switch` bound via `get_settings()/put_settings()`.
* “Save” button gives green toast; errors show red toast.

---

### T07 – **Newsletter Wizard**

* Page `/newsletter` with date range, category multiselect, advanced accordion (LLM params).
* “Run” triggers `POST /theseus_insight/run` and opens `<JobDrawer>`.

---

### T08 – **Podcast Wizard**

* Page `/podcast`; `ui.upload` for PDFs, `ui.input` for arXiv URLs.
* Switch **Create visualiser** and intro-music `ui.upload`.
* Posts to `/podcast/generate`.

---

### T09 – **Visualiser Page**

* Upload MP3, colour/Fx presets (`ui.select`, `ui.slider`).
* Render queue with status chips and download buttons.

---

### T0A – **Papers Explorer**

* Server-side `ui.table` using data from T03.
* Column filters, score sliders, bulk action toolbar → newsletter / podcast endpoints.

---

### T0B – **Dashboard & Navigation**

* Home page `/` showing quick-start cards.
* Recent jobs table pulls `/status` for last ten tasks.
* Side navigation & brand header shared via `<MainLayout>`.

---

## Definition of Done

* All endpoints functional & unit tests green (`pytest`).
* `python -m theseus_insight.ui --reload` starts NiceGUI; pages round-trip successfully.
* Live progress streaming via WS is visible on JobDrawer.
* No Node/Vite.
