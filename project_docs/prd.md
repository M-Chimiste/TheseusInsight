# Theseus Insight – Graphical User Interface (GUI) Product Requirements Document (v0.3)

> **Scope note:** This PRD covers *Phase 1* — adding a **browser‑based GUI** that runs locally, served by a lightweight **Python‑friendly** web server (e.g., **Streamlit**) and talking to the existing FastAPI backend + SQLite storage. Containerisation and remote deployment will be defined in a later phase.

---

## 1 · Goals & Non‑Goals

|                | Goals                                                                                                                                                                                                                                                                                                                   | Non‑Goals                                                                                                                                               |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **User Value** | • Provide a polished point‑and‑click experience so non‑technical users can harvest papers, generate newsletters & podcasts, and review results.<br>• Reduce reliance on CLI and manual JSON edits.                                                                                                                      | • Cloud/SaaS multi‑tenant hosting.<br>• Mobile‑first UX (desktop‑first for Phase 1).<br>• Full account management / OAuth (assume single‑user desktop). |
| **Technical**  | • Build the UI using a lightweight, Python‑based framework that supports rapid local development (e.g., **Streamlit** for the initial prototype).<br>• Keep the backend exactly as‑is (FastAPI) and communicate over REST/WebSockets.<br>• Hot‑reload/auto‑reload dev workflow should rely on the framework’s native tooling (e.g., `streamlit run`). | • Heavy CI/CD & Docker orchestration.<br>• Custom theming or advanced design‑system work beyond built‑in defaults.<br>• Data‑visualisation polish (simple first). |

---

## 2 · Personas & Primary Use‑Cases

| Persona           | Top Jobs‑To‑Be‑Done                                                                                                                                                                     |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Research Lead** | • Curate weekly newsletter from selected date range.<br>• Receive email + (optional) podcast audio based on newsletter.<br>• Filter historical paper scores to justify topic selection. |
| **Podcast Host**  | • Upload PDFs / arXiv URLs → auto‑generated script & TTS.<br>• Tweak intro music & visualiser params.<br>• Download final assets as ZIP.                                                |
| **Ops Engineer**  | • Verify background runs (log table) for failures.<br>• Update model paths or orchestration JSON in **Settings**.                                                                       |

---

## 3 · Technology Considerations

* The GUI should be implementable with minimal front‑end boilerplate.
* Preference for Python‑native frameworks to leverage existing expertise (e.g., **Streamlit** or **NiceGUI**), but the design is framework‑agnostic.
* The selected framework must support:
  * Persistent sidebar navigation.
  * File upload & download.
  * Real‑time progress updates via WebSockets or polling.
  * Responsive layouts and accessibility best practices.
* The PRD remains technology‑independent to allow future evolution; **Streamlit** is an acceptable choice for Phase 1.

---

## 4 · Functional Requirements

### 4.1 Site‑wide

1. **Persistent Sidebar Navigation**

   * Width ≈ 240 px, collapsible (<1024 px auto‑collapses).
   * Active link highlighted.
   * Main content area (main layout area) fills remaining space and starts at top‑left (no forced centring).
2. **Global Feedback**

   * Toast/notification mechanism provided by the chosen framework.
   * WebSocket hook (`useRunProgress`) streams node‑level status into progress bars / DAG viewer.
3. **Settings Hydration**

   * On app load call `GET /settings` → populate React context; `PUT /settings` on save.

### 4.2 Pages

| ID                          | Route         | Purpose                                | Core UI Elements                                                                                                                                                                                                                                                                                                                                                              | Backend Calls                                                               |
| --------------------------- | ------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **P‑01 Settings**           | `/settings`   | Edit all user‑configurable values.     | • Tabs inside `Card`: **Research Interests, Models, Email, Misc**.<br>• `<Textarea>` for interests list.<br>• `<Select>`s for model paths (populated from backend scan).<br>• Monaco‑powered JSON editor for orchestration string.<br>• "Send test email" button.                                                                                                             | `GET/PUT /settings`                                                         |
| **P‑02 Newsletter Builder** | `/newsletter` | Generate newsletter for a date range.  | • `DateRangePicker` *or* "last N days" `<InputNumber>`.<br>• Inline overrides for research interests & per‑stage models.<br>• Email recipient multi‑select (creatable tags).<br>• Checkbox "Also create podcast" → conditional accordion for script/TTS options & intro music upload (accepts mp3/wav).<br>• **Run** button → status panel with node timeline (vertical DAG). | `POST /newsletter/run` + `WS /newsletter/progress`                          |
| **P‑03 Podcast Builder**    | `/podcast`    | Create podcast from PDFs / arXiv URLs. | • `Dropzone` for files, `<Textarea>` for URLs (newline‑separated).<br>• Model selectors (script & TTS).<br>• Toggle "Add visualisation" → visualiser param form (FPS, colour‑scheme, intro/outro length).<br>• **Run & Download** button – shows link when done.                                                                                                              | `POST /podcast/run` + `WS /podcast/progress` + `GET /podcast/{id}/download` |
| **P‑04 Paper Ratings**      | `/papers`     | Browse historical paper scores.        | • `DataTable` with columns: Title (link), Abstract (ellipsis expandable), Score, Date.<br>• Filters in header bar: date range picker + score slider.<br>• Infinite scroll via react‑query `useInfiniteQuery`.                                                                                                                                                                 | `GET /papers` with query params                                             |
| **P‑05 Run Log**            | `/runs`       | Inspect historical runs.               | • `DataTable` with columns: Date, Pipeline, Status badge, Duration, Artifact link.<br>• Default sort = desc(date).<br>• Date filter (`<Calendar />`).                                                                                                                                                                                                                         | `GET /runs` with date filters                                               |

---

## 5 · Development Workflow

1. **Bootstrap**

   ```bash
   python -m venv .venv
   source .venv/bin/activate          # or use your preferred environment tool
   pip install -r requirements.txt    # include streamlit, requests, websockets, etc.
   ```

2. **Run**

   ```bash
   # terminal 1
   streamlit run gui_app.py           # Streamlit GUI on :8501 by default

   # terminal 2
   uvicorn backend.main:app --reload  # FastAPI on :8000
   ```

3. **Packaging**

   * For a self‑contained desktop app, consider bundling via PyInstaller or similar.
   * Containerisation and remote deployment will be addressed in a later phase.

---

## 6 · Non‑Functional Requirements

* **Performance:** Time‑to‑Interactive ≤ 1 s on M‑series Mac in dev; background tasks streamed every ≤ 2 s.
* **Accessibility:** Ensure chosen components meet WCAG 2.1 AA colour‑contrast and keyboard‑navigation standards.
* **Responsiveness:** Sidebar collapses at < 1024 px; layout degrades gracefully to single column.
* **Download Packaging:** Server‑side zipping unchanged (see backend spec). Frontend polls `/podcast/{id}` until `artifact_ready=true`.
* **Error Handling:** HTTP errors → toast, `react‑query` handles retries; WS disconnects → exponential backoff.

---

## 7 · Data Contracts / Schema Impacts

| Table      | Impact                                                                     |
| ---------- | -------------------------------------------------------------------------- |
| `settings` | Add `orchestration_json`, `intro_music_path` (nullable).                   |
| `runs`     | Add `pipeline_type` enum (`newsletter`, `podcast`), `artifact_path` (zip). |
| `papers`   | No change.                                                                 |

---

## 8 · API Additions (FastAPI)

```mermaid
flowchart TD
  UI-->NewsletterPOST[POST /newsletter/run]
  NewsletterPOST-->BGWorker
  BGWorker-- WS progress -->UI
  BGWorker-->EmailSvc
  BGWorker-->PodcastRun
  PodcastRun-->StorageZIP
  UI-- GET /podcast/{id}/download -->StorageZIP
```

---

## 9 · Acceptance Criteria

1. Running `pnpm dev` starts the UI at `http://localhost:3000` and sidebar never centres main content.
2. Creating a newsletter (podcast option off) logs a run and sends email; run appears in *Run Log*.
3. Podcast builder returns a ZIP containing script + mp3 when visualiser is unchecked and adds `video.mp4` when checked.
4. Filtering Paper Ratings by score/date updates table within < 300 ms.

---

## 10 · Risks & Mitigations

| Risk                       | Likelihood | Impact | Mitigation                                                              |
| -------------------------- | ---------- | ------ | ----------------------------------------------------------------------- |
| JS stack unfamiliarity     | Med        | Med    | Provide template repo + detailed README; leverage shadcn generator.     |
| WebSocket version mismatch | Low        | High   | Use `socket.io` on both ends or native WS with protocol version pinned. |

---

## 11 · Open Questions

1. Do any heavy tables need pre‑rendering, or can we rely on dynamic generation within the chosen framework?
2. How long should generated ZIPs persist on disk (7 days vs configurable)?
3. Future multi‑user auth: integrate NextAuth or rely on future backend JWT?

*Last updated:* 2025‑05‑16
