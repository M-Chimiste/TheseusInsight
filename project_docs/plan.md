# Theseus Insight – Phase 1 Task Graph (UI‑First, Local‑Dev)

*CI/CD is deferred; all work is executed and tested locally.*

---

## Overview

Phase 1 delivers a standalone GUI backed by FastAPI and SQLite. Focus areas:

1. React front‑end pages **Settings, Newsletter, Podcast, Visualization, Papers, Dashboard**.
2. Minimal new FastAPI routes & WebSocket hooks to support UI.
3. Local‑only dev/test workflow (no CI, no Docker yet).

---

## Task Table

| ID                               | Depends On | Objective (local)                         |
| -------------------------------- | ---------- | ----------------------------------------- |
| **T01 – Settings API**           | –          | CRUD endpoints wrapping file configs      |
| **T02 – Task Status WS**         | –          | REST + WebSocket for progress updates     |
| **T03 – Papers Query API**       | –          | Paginated search over `papers.db`         |
| **T04 – Serve SPA & Health**     | –          | Mount React bundle & `/healthz` route     |
| **T05 – React Scaffold**         | T01‑T04    | Vite + TS + Chakra app, shared components |
| **T06 – Settings Page**          | T05 T01    | Tabbed settings UI                        |
| **T07 – Newsletter Wizard**      | T05 T02    | Date/category form → `/run`               |
| **T08 – Podcast Wizard**         | T05 T02    | PDF/URL upload form → `/podcast/generate` |
| **T09 – Visualization Page**     | T05 T02    | Audio→video form                          |
| **T0A – Papers Explorer**        | T05 T03    | Virtualized table w/ bulk actions         |
| **T0B – Dashboard & Nav**        | T06‑T0A    | Top nav, quick‑start cards, recent jobs   |
| **T0C – Playwright E2E (local)** | T0B        | Node script runs dev server & E2E flows   |
| **T0D – Docs & Screenshots**     | T0C        | Update README, add UI walkthrough         |

---

## Detailed Tasks

### T01 – **Settings API**

*Expose `/settings` endpoints to read/write `config/orchestration.json` & `research_interests.txt`.*

* **Deliverables**

  * `GET /settings`, `PUT /settings` (Pydantic validation).
  * Unit test `python -m pytest tests/unit/test_settings_route.py`.
* **Done When** file edits persist and reload without server restart.

### T02 – **Task Status & WebSocket**

*REST + WebSocket layer over existing `TASK_STATUS` dict.*

* **Deliverables**

  * `GET /status/{task_id}` JSON.
  * `/ws/progress` pushes updates via `asyncio.Queue`.
  * Helper `broadcast_progress` imported by background jobs.
* **Done When** dummy task emits progress to a simple HTML client.

### T03 – **Papers Query API**

*High‑performance SQLite search endpoint for Papers Explorer.*

* Params: `q`, `score_min`, `score_max`, `limit`, `offset`, `sort`.
* Indexes on `score`, `created`.
* Returns `{total, rows:[…]}`.

### T04 – **Serve SPA & Health**

* Mount `StaticFiles("ui/dist")`.
* `GET /healthz` → `{status:"ok"}`.

### T05 – **React Scaffold & Shared Components**

* Vite + TS + Chakra UI.
* Axios instance `/api` base, SWR provider.
* `<JobDrawer>` listening to `/ws/progress`.
* `<MainLayout>` with nav, color‑mode toggle.

*(Remaining UI tasks unchanged; they build on T05 and respective backend routes.)*

### T06 – **Settings Page** – Tabbed form bound to `/settings`.

### T07 – **Newsletter Wizard** – Date range etc., posts `/theseus_insight/run`.

### T08 – **Podcast Wizard** – Dropzone + URL list; posts `/podcast/generate`.

### T09 – **Visualization Page** – Audio upload & render options.

### T0A – **Papers Explorer** – TanStack virtualized grid, bulk actions cart.

### T0B – **Dashboard & Navigation** – Quick‑start cards + recent jobs list.

### T0C – **Playwright E2E (Local)**

* Node script starts: `uvicorn theseus_insight.main:app` & `npm run dev` concurrently.
* Tests drive each flow, assert output files in `/data/output`.
* Run via `npm run test:e2e`.

### T0D – **Docs & Screenshots**

* Update `README` with local dev steps: `python -m venv`, install deps, `uvicorn`, `npm install`, `npm run dev`.
* Add `docs/UI.md` annotated screenshots.

---

## Definition of Done

* All endpoints functional; unit tests pass locally.
* `npm run dev` loads UI, each page round‑trips to backend.
* Job progress streams live via WebSocket.
* `npm run test:e2e` executes Playwright flows successfully.

---

*Last updated:* 2025‑05‑11
