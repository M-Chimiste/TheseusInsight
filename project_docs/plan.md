# Theseus Insight – UI & Backend Integration Implementation Plan (v0.1)

*This document provides an actionable, dependency‑driven task graph for building the Next.js + shadcn/ui front‑end and extending the FastAPI backend to support it.*

> **Legend**
> **ID** – unique task code · **Depends On** – comma‑separated list of IDs that must complete first · **Output** – tangible artefact or milestone.

---

## 1 · High‑Level Stages

1. **Foundation:** repo scaffolding, shared utilities, layout shell, API client.
2. **Backend Extensions:** DB migrations + new endpoints (newsletter, podcast, runs, papers, download).
3. **Core UI Pages:** Settings → Newsletter → Podcast → Papers → Runs.
4. **Polish & Hardening:** validation, accessibility, error states, Zipping + download flow.

---

## 2 · Work‑Breakdown Structure

| ID       | Task                                                                                                                                 | Depends On          | Output                                       |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------- | -------------------------------------------- |
| **F‑01** | Initialise `theseus-gui` Next.js (TS) repo with Tailwind & shadcn/ui generator; commit baseline.                                     | –                   | Git repo root with basic homepage.           |
| **F‑02** | Add global providers: `<QueryClientProvider>`, `<ToastProvider>`, custom `ApiProvider` with base URL config.                         | F‑01                | `src/providers` module.                      |
| **F‑03** | Implement `<Sidebar />` + `<MainLayout />` (collapsible, active‑link highlighting).                                                  | F‑02                | Persistent layout rendering children routes. |
| **F‑04** | Create `useWebSocketProgress` hook with reconnect logic (socket.io).                                                                 | F‑02                | Hook in `src/hooks`.                         |
| **B‑01** | Add `pipeline_type` & `artifact_path` columns to `runs` table; create Alembic migration.                                             | –                   | DB migration script applied locally.         |
| **B‑02** | Implement newsletter endpoints: `POST /newsletter/run`, `WS /newsletter/progress`.                                                   | B‑01                | `newsletter.py` router.                      |
| **B‑03** | Extend podcast router: `GET /podcast/{id}/download` returning zip, progress WS unified.                                              | B‑01                | Updated `podcast.py`.                        |
| **B‑04** | Add filtered list endpoints: `GET /papers`, `GET /runs` with query params & pagination.                                              | B‑01                | New controller functions.                    |
| **U‑01** | **Settings Page** – tabs, JSON editor, live save via `PUT /settings`.                                                                | F‑03                | Route `/settings`.                           |
| **U‑02** | **Newsletter Builder Page** – date picker, model selectors, "also create podcast" options, run trigger + progress viewer.            | U‑01, B‑02, F‑04    | Route `/newsletter`.                         |
| **U‑03** | **Podcast Builder Page** – file/URL input, model selectors, visualiser options, run trigger + progress viewer + zip download button. | U‑01, B‑03, F‑04    | Route `/podcast`.                            |
| **U‑04** | **Paper Ratings Page** – DataTable with filters; infinite scroll via `useInfiniteQuery`.                                             | B‑04                | Route `/papers`.                             |
| **U‑05** | **Run Log Page** – DataTable with status badges, date filter, link to artifact.                                                      | B‑04                | Route `/runs`.                               |
| **P‑01** | Integrate `zod` schemas for all form inputs + client validation.                                                                     | U‑01 – U‑05         | Validation layer.                            |
| **P‑02** | Add error boundaries & toast error mapping for `react-query` failures.                                                               | U‑01 – U‑05         | Resilient UX.                                |
| **P‑03** | Accessibility sweep – keyboard navigation, aria labels, colour contrast.                                                             | P‑01                | WCAG‑AA compliance report.                   |
| **P‑04** | Bundle optimisation & static asset audit (`pnpm build --profile`).                                                                   | All buildable tasks | Production‑ready build artefacts.            |

---

## 3 · Iteration‑Ready Milestones

1. **Milestone M1 – App Skeleton (F‑01 → F‑04)**

   * Visible sidebar and layout; live toasts; WebSocket connection test page.
2. **Milestone M2 – Backend API Ready (B‑01 → B‑04)**

   * DB migrated; all new endpoints return stubbed data.
3. **Milestone M3 – Settings & Newsletter (U‑01, U‑02)**

   * End‑to‑end newsletter generation works with live progress.
4. **Milestone M4 – Podcast Builder (U‑03)**

   * File upload, generation status, ZIP download operational.
5. **Milestone M5 – History Tables (U‑04, U‑05)**

   * Paper ratings & run logs browseable with filters.
6. **Milestone M6 – Polish & QA (P‑01 → P‑04)**

   * Validations, error states, accessibility, production build.

---

## 4 · Notes & Assumptions

* The backend runs at `localhost:8000`; the Next.js dev server proxies `/api/*` requests accordingly.
* WebSocket namespaces follow pattern `/ws/{pipeline}` and emit JSON nodes: `{ id, status, message, ts }`.
* All long‑running jobs are already queued in the Python side; UI only consumes status.
* File uploads remain < 1 GB; `multipart/form‑data` limit not adjusted here.

---

## 4 · Task by Task Details

> The following expands each WBS item into concrete sub‑steps and acceptance checks.
> **Owner** abbreviations: **FE** = Front‑end dev, **BE** = Back‑end dev.

### Foundation (F‑prefix)

| ID                                | Owner | Detailed Steps                                                                                                                                                                                   | Acceptance Criteria                                                          |
| --------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| **F‑01** Next.js Repo Scaffolding | FE    | 1. Scaffold Next.js project with Tailwind & TypeScript.2. Initialise git & Husky pre‑commit for ESLint+Prettier.3. Push baseline to `gui/main` branch.4. Add README showing dev commands.        | • `pnpm dev` renders starter page.• `eslint` passes with no errors.          |
| **F‑02** Global Providers         | FE    | 1. Install `@tanstack/react-query`, Radix Toast, `lucide-react`.2. Create `src/providers/index.tsx` bundling QueryClientProvider, ToastProvider, ApiProvider.3. Wrap root layout with providers. | • React Query Devtools visible in dev mode.• `useApi()` returns bound fetch. |
| **F‑03** Sidebar & Layout         | FE    | 1. Generate `<Sidebar>` (shadcn NavigationMenu) with collapse logic under 1024 px.2. Build `<MainLayout>` flex container (`h-screen flex`).                                                      | • Sidebar highlights active link.• Content starts top‑left, not centred.     |
| **F‑04** WebSocket Progress Hook  | FE    | 1. Add `socket.io-client`.2. Implement `useRunProgress(runId)` returning node statuses.3. Auto‑reconnect with exponential backoff.                                                               | • Storybook demo logs mock node events in real time.                         |

### Backend Extensions (B‑prefix)

| ID                               | Owner | Detailed Steps                                                                                                                                 | Acceptance Criteria                                                                 |
| -------------------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **B‑01** Runs Table Migration    | BE    | 1. Modify SQLModel to add `pipeline_type` & `artifact_path`.2. Generate Alembic migration & apply.3. Back‑fill pipeline\_type for old rows.    | • Alembic upgrade succeeds.• Existing queries unaffected.                           |
| **B‑02** Newsletter Endpoints    | BE    | 1. Create `routers/newsletter.py` POST & WS routes.2. Wire to job queue (BackgroundTasks/Celery).3. Emit node events schema.                   | • POST returns 201 with `run_id`.• WS streams at least 3 node updates.              |
| **B‑03** Podcast Download Route  | BE    | 1. Archive outputs with `shutil.make_archive`.2. Persist zip path in `runs` row\.3. `GET /podcast/{id}/download` streams file (Range support). | • Endpoint returns `Content-Disposition: attachment`.• Zip contains expected files. |
| **B‑04** Filtered List Endpoints | BE    | 1. Add `/papers` with score/date filters & pagination.2. Add `/runs` with date filter, order desc.3. Unit tests via pytest.                    | • API responds with correct filtered rows.• Pagination works.                       |

### Core UI Pages (U‑prefix)

| ID                           | Owner | Detailed Steps                                                                                                                                                                            | Acceptance Criteria                                                                 |
| ---------------------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **U‑01** Settings Page       | FE    | 1. Build tabbed form using shadcn Tabs.2. Fetch & cache settings via React Query.3. Monaco editor for orchestration JSON with live validation.4. Save triggers optimistic update & toast. | • Editing model path saves & persists.• Invalid JSON disables save.                 |
| **U‑02** Newsletter Builder  | FE    | 1. DateRangePicker or N‑days input.2. Model dropdowns populated from settings.3. Optional podcast section revealed by checkbox.4. POST run then progress drawer.                          | • Complete run logs success in Runs table.• Email is sent (verified via log entry). |
| **U‑03** Podcast Builder     | FE    | 1. File/URL inputs with validation.2. Visualiser param accordion.3. Run progress and ZIP download link.                                                                                   | • ZIP contains script.json + mp3 (+mp4 if visualiser).                              |
| **U‑04** Paper Ratings Table | FE    | 1. DataTable with server‑side filters.2. Infinite scroll using `useInfiniteQuery`.3. Score slider filter.                                                                                 | • Scrolling loads additional pages seamlessly.                                      |
| **U‑05** Run Log Table       | FE    | 1. DataTable with status badges & date filter.2. Artifact link downloads file.                                                                                                            | • Sorting & filtering update view in <300 ms.                                       |

### Polish & Hardening (P‑prefix)

| ID                                 | Owner | Detailed Steps                                                                                                       | Acceptance Criteria                                                          |
| ---------------------------------- | ----- | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| **P‑01** Zod Validation            | FE    | 1. Define schemas for each form.2. Integrate with React Hook Form.3. Show inline error feedback.                     | • Submitting invalid form blocks action & highlights fields.                 |
| **P‑02** Error Boundaries & Toasts | FE    | 1. Add React Error Boundary wrapper.2. Map `react-query` errors to toasts.3. Global 404/500 pages.                   | • Simulated server error shows red toast & boundary fallback.                |
| **P‑03** Accessibility Pass        | FE    | 1. Run Axe; fix aria/contrast.2. Ensure keyboard focus ring visible.3. Add skip navigation link.                     | • Axe reports 0 critical violations.                                         |
| **P‑04** Production Optimisation   | FE    | 1. Analyse bundle; code‑split Monaco.2. Optimise images & fonts.3. Generate Dockerfile for static export (optional). | • `next build` bundle <600 kB gzip JS.• Lighthouse performance ≥ 90 desktop. |

---

Last updated:\* 2025‑05‑12
