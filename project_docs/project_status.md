# Project Status

## Implemented
- **Overall Refactoring & Feature Implementation (Cumulative - reflects state after user's latest summary):**
    - **FastAPI Backend as Central Hub (`theseus_insight/main.py`, `theseus_insight/api/models.py`, `theseus_insight/api/tasks.py`):**
        - Established FastAPI as the sole interface for all settings management and action triggering (newsletter/podcast generation).
        - Comprehensive Pydantic models (`ModelConfig`, `OrchestrationConfig`, `ArxivCategoriesConfig`, `ModelProvider`, `EmailRecipients`, `ResearchInterests`, `TTSModelConfig`, `NewsletterRunParams`, `PodcastVisualizerParams`, `PodcastGenerationParams`, `NodeStatus`, `RunStatus`, `LogEntry`) define data structures for settings and pipeline parameters.
        - Settings endpoints (e.g., `/api/settings/orchestration`, `/api/settings/arxiv-categories`, `/api/model-providers`, `/api/settings/email-recipients`, `/api/settings/research-interests`) for GET (retrieve with fallbacks) and PUT (update DB and JSON).
        - Action endpoint `POST /api/actions/run-newsletter-pipeline`: Accepts `NewsletterRunParams`, runs `TheseusInsight.run()` in background, uses `task_manager` for progress.
        - Action endpoint `POST /api/podcast/generate`: Accepts `PodcastGenerationParams` (JSON string in form field) and optional files (`intro_music_file`, `pdf_files`). Uses `task_manager` for task creation and execution.
        - Action endpoint `GET /api/logs`: Fetches run logs from the database, filterable by date and limit.
        - Introduced `TaskManager` for creating, tracking, and updating status of background tasks (newsletter/podcast) using Pydantic status models.
        - WebSocket endpoints (`/ws/newsletter/{task_id}`, `/ws/podcast/{task_id}`) for streaming real-time `RunStatus` updates.
    - **Database Interaction (`theseus_insight/data_model/data_handling.py`):**
        - `PaperDatabase` class updated with methods for storing/retrieving configurations (general models, ArXiv, etc.) from SQLite. Settings are prioritized from DB, then JSON, then defaults.
        - `get_recent_logs` method enhanced to support date-based filtering for fetching run logs.
        - Corrected `insert_log` method by removing validation for a non-existent `status_code` attribute on the `Logs` model, which likely caused 500 errors when fetching logs.
    - **Streamlit API Client (`streamlit_app/api_client.py`):**
        - Created a dedicated API client with functions to interact with all FastAPI settings and action endpoints.
        - Includes `APIClientError` custom exception and `API_HOST_URL` configuration.
        - Added `start_podcast_generation_pipeline` to handle `multipart/form-data` for podcast creation.
    - **Streamlit Views Refactor (`streamlit_app/views/`):**
        - **Settings Page (`settings.py`):**
            - All direct DB/file I/O removed; now uses `api_client.py`.
            - `render_model_config_ui` helper for dynamic UI.
            - Theme management (Dark/Light/System) with dynamic CSS.
        - **Newsletter Generation Page (`newsletter.py`):**
            - UI for date pickers, editable recipients/interests (pre-filled via API), "Generate Podcast" checkbox.
            - Calls `api_client.start_theseus_newsletter_run` on "Generate Newsletter" click.
            - Real-time status updates via WebSocket listener (`listen_to_task_status_async`) in a separate thread, updating `st.session_state`.
        - **Podcast Creator Page (`podcast.py`):**
            - UI for input selection (URLs/PDFs), model configuration (reusing `render_model_config_ui`, saving to main orchestration config via API), optional intro music, and visualization settings.
            - Calls `api_client.start_podcast_generation_pipeline` on "Generate Podcast" click.
            - Reuses WebSocket listener logic (`common_listen_to_task_status`) for status updates to `/ws/podcast/{task_id}`.
            - Session state (`st.session_state.pc_...`) for UI and task tracking, with robust initialization.
    - **`TheseusInsight` Class (`theseus_insight/theseus_insight.py`):**
        - `__init__` modified to accept overrides for dates, interests, recipients, and `generate_podcast` flag.
        - `run()` method updated to accept a `progress_callback` for FastAPI task manager updates.
        - Fallback to default `arxiv_search_categories` if not in `orchestration.json`.
- **Overall Refactoring & Feature Implementation (Sessions 1-19 Summary - now integrated into the above cumulative summary, this section can be removed or condensed if redundant):**
    - **Settings Management Overhaul:**
        - Migrated all application settings (Orchestration, ArXiv Categories, Model Providers, Email Recipients, Research Interests, Podcast Models, TTS Models) from direct DB/JSON interaction within Streamlit views to a FastAPI backend.
        - FastAPI backend (`theseus_insight/main.py`, `theseus_insight/api/models.py`) now serves as the sole interface for GET/PUT operations on settings.
        - Settings are stored in an SQLite database (`theseus_insight/data_model/data_handling.py`) with fallbacks to JSON files (e.g., `orchestration.json`, `config/research_interests.txt`) or Pydantic model defaults.
        - Comprehensive Pydantic models define the structure for all configurations.
        - Streamlit frontend (`streamlit_app/views/settings.py`) exclusively uses a dedicated API client (`streamlit_app/api_client.py`) for all settings operations.
        - Introduced `render_model_config_ui` in `streamlit_app/views/settings.py` for dynamic UI generation for different model types.
        - Implemented theme management (Dark/Light/System) in Streamlit settings, with dynamic CSS injection for theme application.
    - **Newsletter Generation Pipeline Rewrite:**
        - Developed functionality to configure and trigger the `TheseusInsight` newsletter generation pipeline via the API.
        - Created a FastAPI endpoint `POST /api/actions/run-newsletter-pipeline` in `theseus_insight/main.py`.
            - Accepts `NewsletterRunParams` (start/end dates, recipients, interests, generate_podcast flag).
            - Instantiates `TheseusInsight` with overrides for pipeline parameters.
            - Executes `TheseusInsight.run()` in a background task.
            - Provides real-time status updates via a WebSocket endpoint (`/ws/newsletter/{task_id}`) by leveraging a `task_manager` and a `progress_callback` within `TheseusInsight.run()`.
        - Updated `theseus_insight/theseus_insight.py` (`TheseusInsight` class) to accept runtime overrides and a `progress_callback`.
        - Rewritten the Streamlit newsletter view (`streamlit_app/views/newsletter.py`):
            - UI allows configuration of dates, recipients, research interests (pre-filled via API), and podcast generation.
            - Triggers the pipeline by calling `streamlit_app.api_client.start_theseus_newsletter_run`.
            - Displays real-time status updates by listening to the WebSocket endpoint in a separate, non-blocking daemon thread (`threading.Thread`) and updating `st.session_state`.
- Updated model settings in `streamlit_app/views/settings.py`.
  - Model configurations are now loaded by prioritizing the SQLite database, then `orchestration.json`, and finally hardcoded defaults.
  - Saving model configurations now writes to both `orchestration.json` and the SQLite database (`models` table).
- Modified `theseus_insight/data_model/data_handling.py`:
  - Added `upsert_model` method to `PaperDatabase` for inserting or updating model configurations.
  - Enhanced `get_models` method in `PaperDatabase` to allow fetching a model by `provider_id` and `name`.
- Updated ArXiv settings in `streamlit_app/views/settings.py`:
  - ArXiv configuration now loads by prioritizing SQLite DB, then `orchestration.json`, then defaults.
  - Saving ArXiv configuration now writes to both `orchestration.json` and SQLite DB.
- Fixed `ModuleNotFoundError` for `theseus_insight` package in Streamlit app:
  - Added code to `streamlit_app/app.py` to append the project root directory to `sys.path`.
- Refactored Streamlit settings page (`streamlit_app/views/settings.py`) to use FastAPI backend exclusively:
  - Removed direct database and file system access for configurations.
  - Integrated `streamlit_app/api_client.py` for all settings-related data operations.
  - Centralized model configuration UI rendering with a new `render_model_config_ui` helper function.
  - Settings (Orchestration, ArXiv categories, Model Providers) are now fetched from and saved to the API.
- Enhanced FastAPI backend (`theseus_insight/main.py` and `theseus_insight/api/models.py`):
  - Updated Pydantic models (`OrchestrationConfig`, `ModelConfig`, `ArxivCategoriesConfig`, `ModelProvider`) for comprehensive settings management.
  - Modified `/api/settings/orchestration` endpoints to use the detailed `OrchestrationConfig` and provide defaults.
  - Added `/api/settings/arxiv-categories` (GET/PUT) endpoints with defaults.
  - Added `/api/model-providers` (GET) endpoint.
- Created `streamlit_app/api_client.py` to abstract API communication for the Streamlit app.
- Corrected `AttributeError` in Streamlit error handling for `APIClientError` by using `str(e)` instead of `e.message`.
- Standardized URL construction in `streamlit_app/api_client.py` to prevent 404 errors by using `API_HOST_URL` and consistently prefixing paths with `/api/`.
- Fixed CSS styling for Light Theme in `streamlit_app/views/settings.py` (Session 8):
  - Updated `apply_theme` function with more specific CSS rules for `.stSelectbox` to ensure they render correctly in light mode.
  - Improved styling for select box dropdown menus and radio button labels in light mode.
- Corrected Theme Toggle Logic and Styling (Session 9):
  - In `streamlit_app/views/settings.py` (`show_settings_page`):
    - Ensured `st.toggle` for Dark Mode uses a correct boolean `value`.
    - Implemented `st.rerun()` after theme state change for consistent application.
    - Defaulted initial theme to 'Light' if not set in session state.
  - In `streamlit_app/views/settings.py` (`apply_theme` function, Light theme CSS):
    - Refined CSS for `.stToggle` to improve visibility of track and thumb in its "off" state (when Light Mode is active).
    - Added specific styling for thumb positioning and appearance for both checked and unchecked states.
- Implemented System Theme Default and Dynamic CSS Injection (Session 10):
  - In `streamlit_app/views/settings.py`:
    - Defined `DARK_THEME_CSS`, `LIGHT_THEME_CSS`, and `EMPTY_STYLE_TAG` as module-level constants.
    - Modified `apply_theme` function to accept an `st.empty()` placeholder and inject appropriate CSS (or empty style for 'System' theme) into it.
    - Updated `show_settings_page` to initialize `st.session_state.theme` to `'System'` by default.
    - Created an `st.empty()` placeholder for theme CSS injection.
    - Adjusted Dark Mode toggle logic to reflect 'System' default: toggle is OFF for 'System' or 'Light', ON for 'Dark'. User interaction overrides 'System' with explicit 'Light'/'Dark'.
    - Updated toggle help text.
- Feature: Added Podcast and TTS Model Configurations (Session 11):
  - Backend (`theseus_insight/api/models.py`):
    - Created `TTSModelConfig` Pydantic model with fields for provider, model name, speaker voices, and validated speeds (0.5-3.5).
    - Extended `OrchestrationConfig` to include `podcast_model: Optional[ModelConfig]` and `tts_model: Optional[TTSModelConfig]`.
  - Backend (`theseus_insight/main.py`):
    - Updated `/api/settings/orchestration` GET endpoint to correctly load `podcast_model` and `tts_model` from DB or JSON, applying comprehensive defaults if fields are missing.
    - Updated `/api/settings/orchestration` PUT endpoint to save the complete `OrchestrationConfig` (including new models) to both DB and `orchestration.json`.
  - Frontend (`streamlit_app/api_client.py`):
    - Updated docstrings for `get_orchestration_config` and `update_orchestration_config` to reflect inclusion of new models (no functional change needed as it handles dicts).
  - Frontend (`streamlit_app/views/settings.py`):
    - Added "Podcast Model Settings" expander using `render_model_config_ui`.
    - Added "TTS Model Settings" expander with custom UI for its specific fields (dropdowns for provider, model, voices; number inputs for speeds).
    - Ensured save buttons for new panes update the full orchestration config via API.
  - Resolved 500 error from Pydantic validation by making `podcast_model` and `tts_model` optional in `OrchestrationConfig` and ensuring the GET endpoint provides full default objects if these are not found in storage.
- Resolved Streamlit UI error `StreamlitAPIException: Expanders may not be nested inside other expanders`:
  - In `streamlit_app/views/settings.py`, moved "Podcast Model Settings" and "TTS Model Settings" expanders to be top-level, instead of nested within "Data Source Settings".
  - Corrected a typo in an exception name from `APIClient_Error` to `APIClientError` in the TTS model settings save logic.
- Feature: Added Research Interests Setting:
  - Backend (`theseus_insight/main.py`):
    - Updated `/api/settings/research-interests` GET endpoint to fetch from DB, then `config/research_interests.txt`, then default to empty string.
    - Updated `/api/settings/research-interests` PUT endpoint to save to both DB and `config/research_interests.txt`.
  - API Client (`streamlit_app/api_client.py`):
    - Added `get_research_interests` and `update_research_interests` functions.
  - Frontend (`streamlit_app/views/settings.py`):
    - Added "Research Interests Settings" expander after "ArXiv Settings".
    - Included a `st.text_area` for input and a save button.
    - Integrated API calls to load and save research interests.
- Feature: Added Email Recipients Setting:
  - Backend (`theseus_insight/main.py` and `theseus_insight/api/models.py`): Verified existing Pydantic model `EmailRecipients` and FastAPI endpoints (`/api/settings/email-recipients`) are suitable.
  - API Client (`streamlit_app/api_client.py`): Verified existing `get_email_recipients` and `update_email_recipients` functions are suitable.
  - Frontend (`streamlit_app/views/settings.py`):
    - Added "Email Recipients Settings" expander after "Research Interests Settings".
    - Initialized session state variable `settings_email_recipients`.
    - Updated API loading logic to include `api_client.get_email_recipients()`.
    - Used `st.text_area` for inputting email addresses (newline or comma-separated).
    - Implemented save logic to process input and call `api_client.update_email_recipients()`.
- **React Frontend and FastAPI Backend Migration:**
    - **`Settings.tsx` Page (frontend/src/pages/Settings.tsx):**
        - **Layout & Core Structure:**
            - Switched from MUI `Grid` to `Box` with flexbox due to linter errors.
            - Adopted a wider, full-screen layout with `Container`, `Card`, and `Tabs`.
            - Added "Display Settings" with a Dark Mode toggle (theme connection TODO).
        - **Model Configuration Section:**
            - Mirrors Streamlit `settings.py` for model types (embedding, judge, etc.).
            - Fetches model providers (`/api/model-providers`).
            - Uses `orchestration.json` (via `/api/settings/orchestration`) as settings source.
            - `renderModelConfigFields` for dynamic form inputs.
            - Per-model type "Save" buttons, updating `orchestrationConfig` via `react-query` mutation.
            - TTS model section matches Streamlit UI (provider, model name, speaker voice/speed).
        - **ArXiv Categories Section:**
            - User-friendly category selection using `arxiv_taxonomy.json`.
            - Main category dropdown; `Autocomplete` for multi-select subcategories.
            - Logic to filter/re-add subcategories.
            - Initial data from `/api/settings/arxiv-categories` or `orchestration.json`.
            - "Save ArXiv Settings" button.
        - **Research Interests & Email Recipients Sections:**
            - `TextField` areas, data from `/api/settings/research-interests` and `/api/settings/email-recipients`.
            - Individual "Save" buttons.
            - "Send Test Email" button in Email Recipients card.
        - **Visualizer Settings Section:**
            - Removed, functionality to be part of newsletter/podcast flows.
    - **`Newsletter.tsx` Page (frontend/src/pages/Newsletter.tsx):**
        - **Core Functionality (Mirroring Streamlit):**
            - Date Range Selection (Start, End, Days) with synchronization.
            - Email Recipients: Text area, displayed as deletable MUI `Chip`s, defaults from settings.
            - Research Interests: Text area, defaults from settings.
            - "Generate Newsletter" button.
            - Pipeline Status display (node-based progress via WebSocket).
        - **Implementation Details:**
            - Dependencies: `@mui/x-date-pickers`, `date-fns`.
            - API endpoint: `runNewsletterPipeline` (`services/api.ts`, POST to `/api/actions/run-newsletter-pipeline`).
            - State variables for inputs and pipeline status (isRunning, stage, progress, message, error, taskId).
            - `useEffect` for fetching defaults and date sync.
            - Date helper functions.
            - Handlers for date changes, email input (parsing to chips), chip deletion.
            - **WebSocket Integration (`useWebSocket` hook):**
                - Connects to `ws://localhost:8000/ws/newsletter/{taskId}`.
                - Debugged "Order of Hooks" error (conditional call resolved by unconditional call with nullable taskId).
                - Resolved type errors (signature/return type mismatches, consumption in `Newsletter.tsx`).
                - Ensured correct parsing of JSON `RunStatusPayload`.
                - Hook accepts `taskId | null` and `type` ('newsletter'/'podcast'), returns `lastMessage` (parsed payload), `readyState`, `error`.
                - `Newsletter.tsx` uses `useEffect` to update local `pipelineStatus` and `statusMessages` from hook.
                - `RunStatusPayload`, `NodeStatusPayload` interfaces defined.
            - `handleGenerateNewsletter` calls API, updates `taskId`, triggering WebSocket.
            - UI: MUI `Card`, `DatePicker`, `TextField`, `Button`, `LinearProgress`, `Alert`, `Chip`.
    - **`Podcast.tsx` Page (frontend/src/pages/Podcast.tsx):**
        - Cleaned up unused state variables (`isCompleted`, `downloadUrl`) and `NodeStatusPayload` interface to reduce linter warnings.
        - **User Request & Initial Structure (Phase 1 Goals):**
            - Inputs for PDF uploads and URLs (add/delete, use simultaneously).
            - "Podcast Model Settings" & "TTS Model Settings" cards (view/edit fetched data).
            - Optional intro music upload.
        - **Implementation Steps & Refinements:**
            - **Content Sources (PDFs/URLs):**
                - Removed `Tabs`, displaying PDF upload and URL input simultaneously in one "Content Sources" card.
                - PDF upload button, filenames as deletable `Chip`s.
                - URL `TextField` (Add button, Enter support), URLs as deletable `Chip`s.
            - **Model Configuration Cards ("Podcast Model Settings", "TTS Model Settings"):**
                - Separate `Card` components.
                - Fetch `orchestrationConfig` and `modelProviders`.
                - Local state (`podcastModelConfig`, `ttsModelConfig`) initialized from `orchestrationConfig`.
                - Podcast Card Fields: Model Type (Provider), Model Name, Max New Tokens, Temperature.
                - TTS Card Fields: TTS Provider, TTS Model Name, Speaker 1 Voice/Speed, Speaker 2 Voice/Speed.
                - Individual "Save" buttons, update `orchestrationConfig` via `settingsApi.updateOrchestrationConfig`.
            - **Layout:**
                - `Container` `maxWidth` to `xl`.
                - Two-column `Grid` (Left 2/3: Content, Podcast Model, TTS Model; Right 1/3: Intro Music, Generate Button & Status).
            - **Intro Music Upload:**
                - `Card` with upload button, filename as deletable `Chip`.
            - **Generate Podcast Functionality:**
                - State: `generating`, `podcastTaskId`, `podcastError`.
                - `handleGeneratePodcast`:
                    - Constructs `params` for `podcastApi.generatePodcast` (dynamic `input_type`, `urls`, model configs).
                    - Calls `podcastApi.generatePodcast` (multipart form data: params as JSON string, files).
                    - Updates state with `taskId` or error.
                - "Generate Podcast" button (disabled if no PDFs/URLs).
                - Basic status display (spinner, error, task ID).
            - **Download Functionality:**
                - `useEffect` polls `taskApi.getTaskStatus(podcastTaskId)` if `podcastTaskId` exists.
                - On "completed": calls `taskApi.downloadTaskArtifact(podcastTaskId, 'audio')`.
                - Converts blob to object URL, renders "Download Podcast" button.
                - On "failed": displays error.
            - **WebSocket Integration (`useWebSocket` hook for Podcast.tsx):**
                - Connects to `ws://localhost:8000/ws/podcast/{taskId}`.
                - Handles `RunStatusPayload` to update `pipelineStatus` (stage, progress, message) and `statusMessages` (live log).
                - Sets `generating` to `false` on task completion/failure.
                - Prepares download link for audio/video based on `createVisualization` state when task completes with a result.
    - **`Visualizer.tsx` Page (frontend/src/pages/Visualizer.tsx):**
        - **Core Functionality:**
            - Audio file upload component.
            - Visualization settings form (copied from `Podcast.tsx`).
            - "Generate Visualization" button.
            - WebSocket integration (`useWebSocket` with type `'visualizer'`) for live status and log.
            - Download button for the generated video artifact.
        - **Backend Integration:**
            - API endpoint `POST /api/actions/run-visualizer-pipeline` in `main.py` (accepts audio file, visualizer params JSON).
            - Task `run_visualizer_task` in `tasks.py` (imports `generate_visualizer_video` from `podcast.generator`).
            - `taskApi.runVisualizerPipeline` in `frontend/src/services/api.ts`.
            - Added `'visualizer'` to `useWebSocket` hook types.
    - **React Frontend - Run History Page (`theseus-ui/src/pages/RunHistory.tsx`):**
        - Created backend API endpoint `/api/logs` in `main.py` to fetch logs from `logs` table, filterable by date (`from_date`, `to_date`) and `limit`.
        - Added `LogEntry` Pydantic model in `main.py`.
        - Updated `data_handling.py` (`get_recent_logs`) to support date filtering.
        - Added `getLogs` function and `LogEntry` interface to `theseus-ui/src/services/api.ts`.
        - Created `RunHistory.tsx` component:
            - Fetches logs using `getLogs`.
            - Displays logs in a paginated MUI `Table`.
            - Provides MUI `DatePicker` components for `fromDate` and `toDate` filtering.
            - Resolved MUI v7 `Grid` API compatibility issues by updating to `size` prop and removing `item` prop.
        - Added "Run History" to sidebar in `Layout.tsx` and routing in `App.tsx`.
    - **React Frontend - Podcast History & Detail Pages (`theseus-ui/src/pages/PodcastHistory.tsx`, `theseus-ui/src/pages/PodcastDetail.tsx`):**
        - **Backend (`main.py`, `api/models.py`, `data_model/dialog.py`, `data_model/data_handling.py`):**
            - Updated Pydantic models (`DialogueItem` for flexible speaker naming, added `PodcastScriptItem`, `PodcastListItemResponse`, `PodcastDetailResponse`).
            - Added `fetch_podcast_by_id` to `PaperDatabase` to retrieve a single podcast and parse its script.
            - Created FastAPI endpoints: `GET /api/podcasts/history` (list view with snippets) and `GET /api/podcasts/history/:podcastId` (detail view with full script).
        - **Frontend (`services/api.ts`, `pages/PodcastHistory.tsx`, `pages/PodcastDetail.tsx`, `App.tsx`, `components/Layout.tsx`):**
            - Added new interfaces and API functions to `api.ts`.
            - Created `PodcastHistory.tsx`: Displays list of podcasts as MUI Cards, linking to detail page. Resolved MUI Grid v7 issues.
            - Created `PodcastDetail.tsx`: Displays full podcast details, including transcript with distinct styling per speaker (supports up to 5 speakers by default, configurable).
            - Added new routes to `App.tsx` and a "Podcast History" link to the sidebar in `Layout.tsx`.
            - Corrected `AxiosResponse` import in `api.ts` and added 'visualizer' type to `createWebSocket`.
    - **React Frontend - Papers Page (`Papers.tsx`, `PaperCard.tsx`, `PaperRowCard.tsx`):**
        - Enhanced dark mode visibility for paper cards:
            - Updated primary blue color in `darkTheme` (`styles/theme.ts`) to a lighter shade (`#60a5fa`) for better contrast.
            - In `PaperRowCard.tsx`:
                - Title color explicitly set to white in dark mode.
                - Score `Chip` text color set to white in dark mode, border uses the new lighter primary blue.
            - In `PaperCard.tsx`:
                - Title and Score text colors explicitly set to white in dark mode.
                - Added the "Relevant" / "Not Relevant" chip to the unexpanded card view.
            - In `PaperRowCard.tsx`:
                - Added the "Considered Relevant" / "Considered Not Relevant" chip below the score, matching the grid view.
                - Shortened relevance chip labels to "Relevant" / "Not Relevant" to prevent text cutoff.
                - Increased date font size by changing Typography variant to `body2`.

## Next Steps
- **React Frontend - `Podcast.tsx` Development:**
    - Test PDF and URL inputs thoroughly, individually and combined.
    - Test intro music upload and inclusion in the generated podcast.
    - Test model configuration changes and their effect on generation.
    - Finalize styling and layout for a polished user experience.
    - Implement client-side validation for inputs where appropriate.
- **General:**
    - Address any TODOs noted in the code (e.g., Dark Mode theme connection in `Settings.tsx`).
    - Conduct thorough testing across all implemented React pages (`Settings`, `Newsletter`, `Podcast`, `Visualizer`, `RunHistory`).
    - Review and refactor code for maintainability and scalability as per guidelines.
- Awaiting next task or specific area of focus from the user for other areas.

## Debug Log (Current Session - Podcast History Feature)
- **Goal:** Implement Podcast History and Detail pages.
- **Backend (`main.py`, `api/models.py`, `data_model/dialog.py`, `data_model/data_handling.py`):**
    - Changed `DialogueItem.speaker` from `Literal` to `str` for flexibility.
    - Added `PodcastScriptItem`, `PodcastListItemResponse`, `PodcastDetailResponse` Pydantic models.
    - Implemented `db.fetch_podcast_by_id()`.
    - Created `GET /api/podcasts/history` and `GET /api/podcasts/history/:podcastId` endpoints.
- **Frontend (`services/api.ts`, `pages/PodcastHistory.tsx`, `pages/PodcastDetail.tsx`, `App.tsx`, `components/Layout.tsx`):**
    - Added corresponding interfaces and API client functions in `api.ts`.
    - Created `PodcastHistory.tsx` (list view) and `PodcastDetail.tsx` (detail view with styled dialog).
    - Fixed MUI Grid v7 prop usage in `PodcastHistory.tsx`.
    - Added routes in `App.tsx` and sidebar link in `Layout.tsx`.
    - Corrected `AxiosResponse` type-only import in `api.ts` and added `visualizer` type to `createWebSocket`.
- Resolved `Settings.tsx` text input issue by using local state for `researchInterestsInput` and `emailRecipientsInput`.

## Project Status Update - <YYYY-MM-DD HH:MM>

### Implemented:

**Dockerization of Application:**
1.  **Backend Preparation & `Dockerfile` Creation:**
    *   Created a `.dockerignore` file to exclude unnecessary files from the build context.
    *   Developed a multi-stage `Dockerfile`:
        *   **Frontend Stage:** Uses a Node image to build the React application (`theseus-ui`).
        *   **Backend Stage:** Uses a Python image, sets up the environment, installs system dependencies including `ffmpeg`, `fonts-noto-cjk` (for Japanese font support), and `fontconfig`. Runs `fc-cache` to make the font available.
        *   Installs Python dependencies from `requirements.txt`.
        *   Copies backend application code and the built React frontend (to `/app/static_frontend`).
        *   Creates necessary data directories and exposes port 8000.
        *   Sets the default command to run FastAPI with Uvicorn.
2.  **`docker-compose.yml` Configuration:**
    *   Created `docker-compose.yml` to define the application service (`theseus-insight-app`).
    *   Configured the service to build from the `Dockerfile`.
    *   Maps host port 8000 to container port 8000.
    *   Uses `env_file: .env` to load environment variables into the container.
    *   Mounts the local `./data` directory to `/app/data` in the container for data persistence (SQLite DB, generated files).
    *   Sets the `THESEUS_DB_PATH` environment variable within the container to `/app/data/papers.db`.
3.  **FastAPI Backend Updates (`theseus_insight/main.py`):**
    *   **Lifespan Event Handler:** Replaced deprecated `@app.on_event("startup")` and `@app.on_event("shutdown")` with the `lifespan` context manager for handling startup and shutdown tasks.
        *   Startup logic includes directory creation, environment variable checks, and pre-population of Orchestration settings (from `../config/orchestration.json`) and Research Interests (from `../config/research_interests.txt`) into the database if they are not already present.
        *   Shutdown logic includes closing WebSocket connections.
    *   **Static File Serving:** Added logic to serve the built React frontend:
        *   Mounted the `/app/static_frontend/assets` directory to `/assets` for serving static assets like CSS, JS, images.
        *   Added a catch-all GET route (`"/{full_path:path}"`) to serve `static_frontend/index.html` for any path not caught by API routes, enabling client-side routing.

**Previously Implemented (Papers Page - Pagination & Infinite Scrolling):**
*   Backend: Enhanced `/api/papers` to support `page_size` and return `total_items`, `total_pages`, `current_page`.
*   Frontend: Updated `Papers.tsx` with infinite scrolling using `IntersectionObserver` and a page size selector.

### To Be Implemented Next:

1.  **Refine Papers Page Functionality (Filters):**
    *   **Backend Filtering:** Enhance `db.fetch_all_papers()` and the `/api/papers` endpoint to perform filtering (search term, score range, date range) directly at the database level.
    *   **Advanced Frontend Filtering:** Add UI elements to `Papers.tsx` for users to input filter criteria.
2.  **Visualizer Page Development & Font Update:** Implement the UI for triggering and viewing audio visualizations. Update font path in relevant backend/UI code to use the newly installed CJK font (`/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc`).
3.  **Newsletter Generation Page Enhancements.**
4.  **Testing:** Thoroughly test the Dockerized application, including environment variable passing, volume mounts, and functionality of all pages.

### Debug Log:

*   Ensured `db` (database connection) is initialized before the FastAPI `app` instance in `main.py` due to its use in the `lifespan` startup phase.
*   The WebSocket manager shutdown logic in `lifespan` was made conditional based on the availability of the `manager` object.
*   The path for the Japanese font in the Docker image is `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` as requested.
*   Static file serving in `main.py` is configured to serve assets from `/assets` and `index.html` via a catch-all route placed after API routes.

---
(Previous content of project_status.md should be preserved below this block if any)