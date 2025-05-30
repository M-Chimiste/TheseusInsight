# Project Status

## Implemented

### Latest Update: Database Import Progress Bar Fix for Complete Overwrite Mode

**Critical Bug Fix**: Fixed missing progress bar updates during "Complete Overwrite" mode database imports.

**Problem Identified**: 
- Database import progress bar worked correctly for "Merge" mode
- Progress bar remained at 0% during "Complete Overwrite" mode, even though the operation was working
- Users couldn't track progress during the destructive clearing phase before import

**Root Cause Analysis**:
- The `clear_all_data()` method in `DatabaseImporter` didn't accept or use a progress callback
- Task manager only provided progress tracking for the import phase, not the clearing phase
- In overwrite mode, clearing phase had no progress reporting, causing UI to appear stuck

**Changes Made**:

1. **Backend (`theseus_insight/utils/db_migration/db_import.py`)**:
   - Modified `clear_all_data()` method to accept `progress_callback` parameter
   - Added progress reporting as it clears each table (logs, tasks, newsletters, podcasts, papers)
   - Progress reports table-by-table completion: 0/5, 1/5, 2/5, etc.
   - Enhanced final status message with total records deleted count

2. **Backend (`theseus_insight/api/tasks.py`)**:
   - Completely restructured `run_database_import_task()` progress tracking
   - **Progress Mapping for Overwrite Mode**:
     - Clearing phase: 0-20% of overall progress
     - Import phase: 20-100% of overall progress
   - **Progress Mapping for Merge Mode**: 
     - Import phase: 0-100% (no clearing phase)
   - Created separate `clearing_progress_callback()` and `import_progress_callback()` functions
   - Added intermediate status update at 20% when clearing completes and import begins
   - Enhanced debugging logs for better troubleshooting

**Implementation Details**:
- **Phase Separation**: Clear separation between clearing (0-20%) and import (20-100%) phases in overwrite mode
- **Real-time Progress**: Both phases now report granular progress via WebSocket to frontend
- **Robust Mapping**: Mathematical progress mapping ensures smooth 0-100% progression across both phases
- **Error Handling**: Progress callbacks include proper error handling for edge cases
- **Backwards Compatibility**: Changes are fully backwards compatible with existing merge mode behavior

**User Experience Benefits**:
- ✅ **Visual Progress**: Users now see continuous progress updates during complete overwrite operations
- ✅ **Phase Awareness**: Clear messaging about which phase is running (clearing vs importing)
- ✅ **Time Estimation**: Better understanding of operation progress and remaining time
- ✅ **Confidence**: No more "stuck at 0%" that made users think the operation failed
- ✅ **Consistent UX**: Both merge and overwrite modes now have equally responsive progress tracking

**Technical Verification**:
- ✅ Python syntax validation passed for all modified files
- ✅ Progress mapping logic tested and verified with sample data
- ✅ Overwrite mode: Clearing 0→20%, Import 20→100%  
- ✅ Merge mode: Import 0→100% (unchanged behavior)

### Previous Update: Visualizer Task Recovery Implementation

**Feature Added**: Task recovery functionality for the Visualizer page to persist running tasks across navigation.

**Problem Solved**: Previously, if users navigated away from the Visualizer page while a visualization was generating, they couldn't return to check the status or download the result. The page would lose track of the running task.

**What Was Implemented**:
- **Migrated from Direct WebSocket to useTaskState Hook**: Replaced basic `useWebSocket` usage with the sophisticated `useTaskState('visualizer')` hook
- **Automatic Task Recovery**: When users navigate back to the Visualizer page, it automatically detects and reconnects to any running visualization tasks
- **Consistent State Management**: Now uses the same task management pattern as Podcast and Newsletter pages
- **Enhanced Download Logic**: Includes fallback mechanism to fetch task results directly if WebSocket data is missing
- **Improved User Experience**: Added "Start New Visualization" button and better status messaging

**Implementation Details**:
- **Hook Migration**: Replaced `useWebSocket` with `useTaskState('visualizer')` for unified task management
- **State Consolidation**: Removed redundant state variables (`generating`, `taskId`, `error`, `pipelineStatus`) in favor of `taskState` object
- **Download Enhancement**: Comprehensive download preparation with both WebSocket and direct API fallback mechanisms
- **Status Messaging**: Real-time log updates that persist across navigation sessions
- **Error Handling**: Robust error states and user-friendly messaging

**User Experience Benefits**:
- ✅ **Task Persistence**: Running visualizations continue even if users navigate away
- ✅ **Status Recovery**: Return to the page and immediately see current progress and status
- ✅ **Download Availability**: Completed visualizations remain downloadable after navigation
- ✅ **Consistent Interface**: Matches the reliable behavior of Podcast and Newsletter pages
- ✅ **Active Task Detection**: Shows "Checking for active tasks..." on page load when appropriate

**Technical Architecture**:
- **Unified Pattern**: All three generation pages (Newsletter, Podcast, Visualizer) now use identical task management
- **WebSocket Integration**: Automatic reconnection to running tasks via task ID
- **Fallback Mechanisms**: Multiple layers of error handling and result fetching
- **State Synchronization**: Real-time updates with local state management
- **Build Status**: ✅ TypeScript compilation successful, no linter errors

### Previous Update: Podcast History Page Grid/List View Implementation

**Feature Added**: Grid and list view options for the dedicated Podcast History page, completing the view toggle functionality across both podcast interfaces.

**What it does**:
- **Dedicated PodcastHistory.tsx Page**: Added view mode toggle to the standalone podcast history page
- **Consistent UI**: Matches the design patterns from Papers.tsx and main Podcast.tsx implementations
- **Grid View**: Card-based layout with 3 columns showing title, date, and description snippet with text truncation
- **List View**: Row-based layout with full content display and "View Details" action chips
- **Responsive Design**: Adapts to different screen sizes and maintains link functionality to detail pages
- **Complete Coverage**: Both podcast interfaces (main page section + dedicated history page) now have view toggles

**Implementation Details**:
- **PodcastHistory.tsx Updates**:
  - Added `ViewMode` type and state management for 'grid' | 'list' views
  - Imported Material-UI toggle components (`ToggleButtonGroup`, `ViewModuleIcon`, `ViewListIcon`, `HistoryIcon`)
  - Added header layout with title and toggle button group
  - Implemented conditional rendering for both view modes
  - Enhanced grid view with text truncation (WebkitLineClamp: 3)
  - Created list view with chips for action indicators
  - Maintained existing RouterLink navigation to detail pages

**User Experience**:
- **Unified Interface**: Both podcast history displays now have consistent view options
- **Clean Toggle**: Visual toggle between grid and list layouts with intuitive icons
- **Improved Content Display**: Grid view handles long descriptions with proper truncation
- **Action Clarity**: List view includes visual indicators for clickable items
- **Navigation Preservation**: All existing link functionality to podcast details maintained

**Technical Architecture**:
- **Consistent Patterns**: Reuses successful design patterns from Papers.tsx implementation
- **Type Safety**: Full TypeScript integration with proper interfaces
- **Component Structure**: Clean separation of concerns with conditional rendering
- **Performance**: Efficient rendering without unnecessary re-renders
- **Accessibility**: Proper ARIA labels and semantic HTML structure
- **✅ Build Status**: All TypeScript checks pass, no linter errors, production build successful

### Automated Media File Cleanup

**Feature Added**: Automated cleanup of old podcast and visualization files at API startup.

**What it does**:
- Runs automatically every time the API starts up
- Deletes media files older than 30 days from:
  - `data/podcasts/` - podcast audio/video files
  - `data/visualizations/` - visualization video files  
  - `data/temp/` - temporary files from processing
- **Preserves all database records** - only removes actual files to save disk space
- Removes empty directories after file cleanup
- Provides detailed logging of what was cleaned and how much space was freed
- Fails gracefully - startup continues even if cleanup encounters errors

**Implementation Details**:
- Added `cleanup_old_media_files()` function in `main.py`
- Integrated into FastAPI lifespan startup sequence
- Configurable age threshold via `MEDIA_CLEANUP_AGE_DAYS` environment variable (defaults to 30 days)
- Comprehensive error handling to prevent startup failures
- Detailed logging with file counts and space freed metrics

**Benefits**:
- Prevents disk space issues from accumulating old media files
- Maintains database history while managing storage costs
- Runs automatically without manual intervention
- Safe operation with graceful error handling

### Latest Update: Podcast Download Link Fix

**Critical Bug Fix**: Fixed the missing download links for completed podcast generation tasks.

**Problem Identified**: 
- Podcast generation was completing successfully and saving to database
- Download links weren't appearing on the frontend after completion
- Root cause: `useTaskState` hook was clearing completed tasks after 2 seconds, preventing download functionality

**Changes Made**:
- **Backend (`theseus_insight/data_model/data_handling.py`)**:
  - Added `get_recent_completed_tasks()` method to retrieve completed tasks with results within 24 hours
  - This ensures download artifacts remain accessible after completion

- **Backend (`theseus_insight/main.py`)**:
  - Added `/api/tasks/recent-completed` endpoint for frontend to fetch completed tasks with downloads
  - Enhanced download endpoint with better debugging and error messages

- **Frontend (`theseus-ui/src/hooks/useTaskState.ts`)**:
  - Modified to check both active and recent completed tasks on initialization
  - Preserved task results for download even after WebSocket completion
  - Added comprehensive debugging logs for troubleshooting

- **Frontend (`theseus-ui/src/pages/Podcast.tsx`)**:
  - Enhanced download effect with fallback mechanism to fetch results directly
  - Added better error handling and status messages for download preparation
  - Improved user feedback when downloads are being prepared

- **Frontend (`theseus-ui/src/services/api.ts`)**:
  - Added `getRecentCompletedTasks()` API method

**Result**: Download links now appear reliably after podcast generation completes, with robust fallback mechanisms for edge cases.

### Podcast Generator PostgreSQL Integration (CRITICAL FIX)

### Previous Update: Sticky Layout for Similarity View

**UI Enhancement**: Implemented a sticky layout for the similarity view to keep the header and reference paper visible while scrolling through similar papers.

**Changes Made**:
- **Frontend (`theseus-ui/src/pages/SimilarityView.tsx`)**:
  - Made the header bar sticky at the top with `position: sticky` and `zIndex: 1000`
  - Made the reference paper section sticky on the left side
  - Reference paper can scroll internally if content exceeds viewport height
  - Similar papers list scrolls independently on the right side
  - Removed "Similar Papers (x of x found)" text as requested
  - Cleaned up unused `totalSimilar` state and related code
  - Adjusted height calculations to account for sticky header (`calc(100vh - 64px)`)

**User Experience**: 
- Header controls (limit dropdown, close buttons) remain accessible while scrolling
- Reference paper stays visible for easy comparison with similar papers
- Similar papers list scrolls smoothly without affecting other UI elements
- Cleaner interface without redundant count information

**Previous Enhancement**: Custom Reference Paper Card for Similarity View

**UI Enhancement**: Created a dedicated, compact reference paper card for the similarity view that displays all information without expansion controls.

**Changes Made**:
- **Frontend (`theseus-ui/src/pages/ReferencePaperCard.tsx`)** - **NEW FILE**:
  - Created custom component specifically for reference paper display
  - Non-expandable design with all information visible
  - Header section with title, score, relevance tags, and metadata
  - Elegant divider separating header from body content
  - Body section with abstract, rationale, and ArXiv link
  - Compact layout optimized for sidebar display
  - Top-aligned content instead of centered

- **Frontend (`theseus-ui/src/pages/SimilarityView.tsx`)**:
  - Replaced expandable PaperCard with custom ReferencePaperCard
  - Removed unused PaperCard import
  - Updated left panel layout for better content flow

**User Experience**: The reference paper now takes up much less vertical space while showing all relevant information, allowing more room for the similar papers list and eliminating the need for expansion controls.

**Previous Enhancement**: Enhanced Paper Row View with Relevance Tags

**UI Enhancement**: Added "Considered Relevant" / "Considered Not Relevant" tags to the expanded row view in the Papers page.

**Changes Made**:
- **Frontend (`theseus-ui/src/pages/PaperRowCard.tsx`)**:
  - Added full relevance tag in the expanded view section
  - Now shows "Considered Relevant" or "Considered Not Relevant" (matching grid view behavior)
  - Positioned between the rationale section and the ArXiv link
  - Uses same styling as the grid view (green for relevant, default for not relevant)

**Previous Enhancement**: Sidebar Navigation Reordering

**UI Enhancement**: Reordered the sidebar navigation menu in the React frontend to improve user experience.

**Changes Made**:
- **Frontend (`theseus-ui/src/components/Layout.tsx`)**:
  - Moved "Papers" to appear after "Visualizer" (was previously last)
  - Moved "Run History" to be the last item in the sidebar
  - New order: Dashboard → Settings → Newsletter Builder → Podcast Creator → Visualizer → Papers → Podcast History → Run History

**Previous Bug Fix**: Fixed UnboundLocalError in Newsletter Pipeline

**Bug Fixed**: Resolved a critical UnboundLocalError that occurred when all papers in the pipeline were already present in the database.

**Issue**: When running the newsletter pipeline with 1944 papers already in the database, the code would crash with `UnboundLocalError: cannot access local variable 'filtered_df' where it is not associated with a value`. This happened because the embedding stage had a logic gap where `filtered_df` wasn't defined in certain edge cases.

**Root Cause**: In the embedding stage, when `self.db_saving` was True and all papers already existed in the database, the code path didn't always ensure `filtered_df` was properly defined before trying to use it.

**Solution**: Added a safety check in `theseus_insight/theseus_insight.py` that ensures `filtered_df` is always defined before the checkpoint save operation. If `filtered_df` is not defined, it creates an empty DataFrame with the proper structure to allow the pipeline to continue gracefully.

**Benefits**:
- Newsletter pipeline no longer crashes when all papers are duplicates
- Graceful handling of edge cases in the embedding stage
- Better error resilience for database-heavy scenarios
- Maintains pipeline flow even when no new papers need processing

### Previous Update: Task Abort Functionality

**Feature Added**: Added an abort button to the newsletter pipeline interface that allows users to terminate running tasks.

**Implementation**:

1. **Frontend (`theseus-ui/src/pages/Newsletter.tsx`)**:
   - Added abort button that appears only when a task is running
   - Button shows "Aborting..." state with loading spinner during abort request
   - Added `isAborting` state to manage button state
   - Positioned abort button next to the main generate button
   - Added error handling for abort requests with user feedback

2. **API Service (`theseus-ui/src/services/api.ts`)**:
   - Added `abortTask(taskId: string)` method to `settingsApi`
   - Makes POST request to `/api/tasks/{task_id}/abort` endpoint

3. **Backend API (`theseus_insight/main.py`)**:
   - Added `POST /api/tasks/{task_id}/abort` endpoint
   - Validates task exists and is in abortable state (PENDING or PROCESSING)
   - Marks task as FAILED with "Task aborted by user" message
   - Returns success response confirming abort

**Benefits**:
- Users can now stop long-running newsletter generation tasks
- Prevents resource waste when users realize they need to change parameters
- Provides immediate feedback when abort is requested
- Task state is properly updated to reflect user-initiated termination

### Previous Update: ArXiv API Error Handling and Email Notifications

**Issue Fixed**: The pipeline was crashing with a KeyError when ArXiv API returned 503 errors and no papers were retrieved, causing a hard failure instead of graceful handling.

**Solution Implemented**:

1. **ArXiv Data Processing (`theseus_insight/data_processing/arxiv.py`)**:
   - Added empty DataFrame handling in `download_and_process_data()` method
   - When no records are retrieved (due to 503 errors or no papers in date range), returns properly structured empty DataFrame
   - Prevents KeyError on 'created' column by ensuring DataFrame has expected structure

2. **Pipeline Error Handling (`theseus_insight/theseus_insight.py`)**:
   - Added `_handle_no_papers_found()` method to gracefully handle empty paper results
   - Sends informative email notification to users when no papers are found
   - Logs the event to database with "NO_PAPERS_FOUND" status
   - Early pipeline exit when no papers available, preventing unnecessary processing

3. **Email Notification System**:
   - Sends user-friendly notification explaining possible causes (ArXiv API issues, no new papers, network problems)
   - Includes search parameters and date range in notification
   - Fixed RFC 5322 compliance issue by properly handling email Subject headers
   - Prevents duplicate Subject headers that were causing Gmail to reject emails

4. **Pipeline Stage Improvements**:
   - Enhanced embedding stage to handle empty DataFrames gracefully
   - Updated ranking stage to skip processing when no papers available
   - Newsletter generation handles empty paper sets appropriately

**Benefits**:
- No more hard crashes when ArXiv API is temporarily unavailable
- Users receive informative notifications instead of silence
- Pipeline continues to function during ArXiv outages
- Better user experience with clear communication about issues

### Previous Update: Duplicate Paper Handling (Quality of Life Fix)
- **Database Layer (`theseus_insight/data_model/data_handling.py`):**
  - Added `paper_exists_by_url(url: str) -> bool` method to check if a paper with a given URL already exists in the database
  - Added `get_paper_by_url(url: str) -> dict | None` method to retrieve paper details by URL
  - Modified `insert_paper()` method to accept `skip_duplicates: bool = True` parameter and return `bool` indicating success
  - When `skip_duplicates=True`, the method checks for existing papers by URL and skips insertion if found, returning `False`
  - When `skip_duplicates=False`, the method forces insertion regardless of duplicates (original behavior)

- **Pipeline Integration (`theseus_insight/theseus_insight.py`):**
  - **Embedding Stage Optimization:** Added duplicate checking before embedding to save computational resources
    - When `db_saving=True`, checks for existing papers by URL before processing
    - Skips embedding for papers that already exist in the database
    - Only processes new papers through the embedding pipeline
    - Handles edge case where all papers are duplicates (creates empty filtered dataframe)
  
  - **Ranking Stage Enhancement:** Modified paper saving logic to track and handle duplicates gracefully
    - Uses `insert_paper(paper, skip_duplicates=True)` to attempt insertion
    - Tracks `saved_count`, `duplicate_count`, and `duplicate_urls` for reporting
    - Provides verbose logging of duplicate papers being skipped
    - Filters duplicate papers from `top_n_df` to exclude them from newsletter generation
    - Backfills `top_n_df` with additional non-duplicate papers if needed to maintain desired count
  
  - **Newsletter Generation Safeguards:** Added handling for cases where no new papers are available
    - Checks for empty paper lists at multiple stages (ranking, sections, content generation)
    - Generates appropriate fallback content: "No new papers found for this newsletter period..."
    - Handles email generation with empty content gracefully
    - Prevents pipeline crashes when all papers are duplicates

- **Error Prevention:** The implementation ensures no errors are thrown when duplicates are encountered
  - Papers are silently skipped with optional verbose logging
  - Pipeline continues normally even when all papers are duplicates
  - Maintains backward compatibility with existing code

- **Testing:** Created `test_duplicate_handling.py` script to verify functionality
  - Tests paper existence checking before and after insertion
  - Verifies duplicate detection and skipping behavior
  - Tests forced insertion without duplicate checking
  - Validates paper retrieval by URL

This quality-of-life improvement prevents duplicate papers from cluttering the database while ensuring the newsletter pipeline remains robust and informative even when processing previously seen papers.
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
                - Made the entire card content area clickable to expand/collapse details (removed expand icon button).
                - Removed hyperlink from the title and added a "View on ArXiv" link to the bottom of the expanded details section (matching grid view).
                - Fixed linter warning for unused `theme` variable in `TruncatedTypography` styled component.
    - **React Frontend - Dashboard Page (`Dashboard.tsx`, `App.tsx`, `Layout.tsx`):**
        - Created a new `Dashboard.tsx` page displaying a grid of clickable navigation cards for major application sections (Settings, Newsletter, Podcast, Papers, etc.).
        - Each card includes an icon, title, and brief description.
        - Added a route for the Dashboard at the root path (`/`) in `App.tsx`.
        - Added "Dashboard" as the first item in the sidebar navigation in `Layout.tsx`, using `DashboardIcon`.
        - Moved the "Settings" card to be the last item on the Dashboard grid.

    - **React Frontend - Linter Warning Fixes:**
        - **`Papers.tsx`:**
            - Commented out unused `SelectChangeEvent` import.
            - Prefixed unused `event` parameter in `handleViewModeChange` with an underscore.

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
    - Corrected `AxiosResponse` type-only import in `api.ts` and added 'visualizer' type to `createWebSocket`.
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
2.  **`

## Latest Updates (December 2024)

### Fixed: Intermittent KeyError in rank_papers Method
**Date**: December 2024  
**Issue**: Intermittent KeyErrors occurring in `rank_papers` method line 387, especially after processing hundreds of papers when using Ollama with schema validation.

**Root Cause**: Even with Ollama schema enforcement, the model could sometimes return:
- Malformed JSON that couldn't be parsed
- Valid JSON missing required keys (`score`, `related`, `rationale`)
- Invalid data types or values outside expected ranges

**Solution Implemented**: Comprehensive error handling and retry mechanism in `theseus_insight/theseus_insight.py`:

1. **Retry Logic**: 
   - Up to 3 attempts per paper before fallback
   - 1-second delay between retry attempts
   - Graceful degradation with default values for failed papers

2. **JSON Validation**:
   - Robust JSON parsing with `json_repair.loads()`
   - Validation of required keys existence
   - Type conversion validation and error handling
   - Score range validation (1-10) with clamping

3. **Partial Checkpointing**:
   - Progress saved every 50 papers to `ranking_partial` checkpoint
   - Resume capability from last successful checkpoint
   - Automatic cleanup of partial checkpoints on completion

4. **Cache Management**:
   - Added `_clear_judge_model_cache()` method
   - Automatic Ollama cache clearing after consecutive failures
   - Helps resolve potential model context corruption

5. **Enhanced Logging**:
   - Detailed error messages with paper indices and attempt numbers
   - Raw response logging for debugging
   - Failure tracking and reporting

**Files Modified**:
- `theseus_insight/theseus_insight.py`: Added robust error handling, retry logic, and partial checkpointing
- Added time import for retry delays
- Enhanced rank_papers method with comprehensive validation

**Impact**: 
- Eliminates pipeline failures due to intermittent JSON issues
- Provides detailed debugging information for troubleshooting
- Maintains data integrity with fallback values
- Enables recovery from partial failures

### Added: Similarity Search Feature in Papers Page
**Date**: December 2024  
**Feature**: Interactive similarity search functionality for papers with vector embeddings.

**Implementation Details**:

1. **API Integration**:
   - Added `findSimilarPapers` function to `theseus-ui/src/services/api.ts`
   - Utilizes existing `/api/papers/{paper_id}/similar` endpoint
   - Added `SimilarPapersResponse` interface for type safety

2. **UI Components Enhanced**:
   - **PaperCard.tsx**: Added "Find Similar" button in expanded view with `onFindSimilar` prop
   - **PaperRowCard.tsx**: Added "Find Similar" button in expanded view with `onFindSimilar` prop
   - **SimilarityView.tsx**: New component for similarity search results display

3. **SimilarityView Component Features**:
   - Split-screen layout: Reference paper (40% left) and similar papers (60% right)
   - Infinite scroll for similar papers with pagination
   - Similarity score display as percentage for each result
   - Back/Close buttons to return to original view
   - Scroll position preservation when returning to main view

4. **Papers.tsx Integration**:
   - Added `similarity` view mode to existing `grid`/`list` modes
   - State management for selected paper and scroll position
   - Conditional rendering to hide filters/headers in similarity view
   - `handleFindSimilar` function to transition to similarity view
   - `handleCloseSimilarity` function to return to previous view with scroll restoration

5. **User Experience**:
   - Click "Find Similar" on any expanded paper card
   - View transforms to show reference paper on left, similar papers on right
   - Similar papers displayed as row cards with similarity percentages
   - Infinite scroll loads more similar papers automatically
   - Back arrow or X button returns to original papers view
   - Original scroll position is restored when returning

**Files Modified**:
- `theseus-ui/src/services/api.ts`: Added similarity search API function and interfaces
- `theseus-ui/src/pages/PaperCard.tsx`: Added Find Similar button and onFindSimilar prop
- `theseus-ui/src/pages/PaperRowCard.tsx`: Added Find Similar button and onFindSimilar prop
- `theseus-ui/src/pages/SimilarityView.tsx`: New component for similarity search results
- `theseus-ui/src/pages/Papers.tsx`: Integrated similarity view mode and state management

**Technical Features**:
- Leverages existing vector embedding infrastructure
- Configurable similarity threshold (default 0.6 for more results)
- Responsive layout with proper overflow handling
- Error handling for failed similarity searches
- Loading states and empty state handling

### Enhanced: Similarity Search with Configurable Limits
**Date**: December 2024  
**Enhancement**: Added dropdown to allow users to select the number of similar papers to display.

**Implementation Details**:

1. **Dynamic Limit Selection**:
   - Added dropdown with options: 10, 30, 50, 100 papers
   - Replaces previous hardcoded limit of 10 papers
   - Automatic re-fetch when limit changes

2. **UI Improvements**:
   - **SimilarityView.tsx**: Added FormControl with Select dropdown in header
   - Shows "X of Y found" to indicate total available similar papers
   - Loading indicator during fetch operations
   - Removed infinite scroll in favor of explicit limit selection

3. **User Experience**:
   - Immediate feedback when changing limits
   - Clear indication of how many papers are shown vs. available
   - Simplified interface without complex pagination

**Files Modified**:
- `theseus-ui/src/pages/SimilarityView.tsx`: Added limit dropdown and updated state management

**Technical Implementation**:
- Removed infinite scroll complexity
- Simplified state management with single `limit` state
- Direct API calls with selected limit parameter
- Type-safe SelectChangeEvent handling

## Latest Update: 2024-12-19
**Session Focus:** Database Migration & Podcast Generator PostgreSQL Update

### What Has Been Implemented

#### ✅ Podcast Generator PostgreSQL Integration (CRITICAL FIX)
- **Database Migration Completion**: Updated PodcastGenerator to use PostgreSQL instead of SQLite
- **Parameter Rename**: Changed `db_path` to `db_url` to reflect PostgreSQL connection strings
- **Improved Error Handling**: Enhanced database insertion with better error messages and debugging
- **Script Serialization Fix**: Fixed podcast script storage to properly handle Pydantic dialogue objects
- **Integration Updates**: Updated all instantiation points (TheseusInsight, TaskManager) to pass database URLs
- **Backward Compatibility**: Maintained all existing functionality while switching to PostgreSQL

#### ✅ BM25-Enhanced Hybrid Search (MAJOR UPGRADE)
- **Database Schema Enhancement**: Added `search_vector`, `title_vector`, and `abstract_vector` columns to papers table
- **PostgreSQL Full-Text Search Integration**: Replaced simple LIKE queries with sophisticated `ts_rank_cd()` BM25-style ranking
- **Advanced Keyword Scoring**: 
  - Term frequency and inverse document frequency weighting
  - Document length normalization
  - English language stemming and stopword filtering
  - 2x weight boost for title matches vs abstract matches
- **Performance Optimization**: Added GIN indexes for fast full-text search
- **Automatic Migration**: Created `update_search_vectors.py` utility for seamless upgrades
- **Backward Compatibility**: All existing API endpoints work unchanged with improved scoring

#### ✅ UI Improvements (Filter Panel Optimization)  
- **Compact Layout**: Reduced filter panel vertical space by ~50%
- **Slider Optimization**: Fixed overlapping labels, made sliders smaller with proper spacing
- **Responsive Design**: Hybrid search weight sliders in horizontal layout with visual grouping
- **Enhanced UX**: All form elements now use `size="small"` for better space utilization

#### ✅ Previously Implemented Features
- **Collapsible Sidebar**: Responsive layout with 240px/64px states and smooth transitions
- **Sticky Header System**: Fixed positioning with dynamic sidebar width adjustment  
- **Infinite Scroll**: Optimized loading with scroll detection and throttling
- **Hybrid Search Foundation**: Original semantic + keyword combination with adjustable weights
- **Advanced Filtering**: Date range, score range, and search query filters
- **Multiple View Modes**: Grid, list, and similarity view with paper recommendations

### What Needs To Be Implemented Next

#### 🔄 Immediate Priorities
1. **Vector Index Optimization**: Resolve dimension issues to create optimized vector indexes for semantic search performance
2. **Query Performance Testing**: Benchmark large dataset performance with new BM25 implementation
3. **Frontend Polish**: Minor UI refinements based on user feedback

#### 📋 Medium-Term Features  
1. **Advanced Search Features**:
   - Multi-language support for non-English papers
   - Configurable BM25 parameters (k1, b values)
   - Query expansion with synonyms
   - Search result highlighting

2. **Performance Enhancements**:
   - Materialized views for common queries
   - Connection pooling optimization
   - Caching layer for frequent searches

3. **User Experience Improvements**:
   - Search history and saved queries
   - Relevance feedback learning
   - Export functionality for search results

#### 🎯 Long-Term Roadmap
1. **Analytics Dashboard**: Search usage patterns and performance metrics
2. **API Rate Limiting**: Production-ready API throttling and authentication
3. **Multi-tenant Support**: User accounts and personalized search preferences

### Technical Architecture Status

#### ✅ Current Architecture
- **Database**: PostgreSQL with pgvector + full-text search (GIN indexes)
- **Backend**: FastAPI with comprehensive error handling and WebSocket support
- **Frontend**: React with Material-UI, responsive design, real-time updates
- **Search**: Hybrid semantic + BM25 keyword ranking with user-adjustable weights

#### 🔧 Infrastructure Status  
- **Development**: Local Docker setup working perfectly
- **Database**: Auto-migration system ensures seamless upgrades
- **API**: RESTful design with WebSocket streaming for long-running tasks
- **Documentation**: Comprehensive README and implementation docs

### Debug Log

#### Latest Session (2024-12-19)
```
✅ FIXED: Podcast Generator PostgreSQL integration issues
✅ UPDATED: PodcastGenerator constructor to use db_url instead of db_path
✅ IMPROVED: Database record insertion with proper script serialization
✅ UPDATED: TheseusInsight class to pass database URL to PodcastGenerator
✅ UPDATED: TaskManager to pass database URL to PodcastGenerator  
✅ ENHANCED: Error handling and debugging in podcast database operations

Issues Resolved:
- Podcast generator was still expecting SQLite file paths instead of PostgreSQL URLs
- Script serialization was not properly handling Pydantic dialogue objects
- Database connections were failing due to incorrect parameter passing
- Error handling was too basic and didn't provide useful debugging information

Database Migration Completion:
- All components now consistently use PostgreSQL connection strings
- Podcast generation now properly saves to PostgreSQL database
- Maintains full backward compatibility with existing podcast functionality
- Enhanced error messages for easier debugging of database issues
```

#### Previous Sessions Summary
```
✅ Sticky header with dynamic sidebar width
✅ Infinite scroll with performance optimizations  
✅ Hybrid search foundation with weight adjustment
✅ Collapsible sidebar with tooltips and transitions
✅ Filter system with date/score ranges and search
✅ Multiple view modes (grid/list/similarity)
```

### Code Quality Status
- **Error Handling**: Comprehensive try-catch blocks with graceful fallbacks
- **Type Safety**: Full TypeScript frontend with proper API type definitions  
- **Testing**: Manual API testing confirmed, automated tests needed
- **Documentation**: Up-to-date README, implementation guides, and inline comments
- **Performance**: Database queries optimized, frontend responsive, real-time updates working

### Next Session Goals
1. **Performance Testing**: Benchmark BM25 search with large datasets
2. **Vector Index**: Resolve pgvector index creation for optimal semantic search speed
3. **UI Polish**: Any remaining frontend refinements
4. **User Testing**: Gather feedback on new search capabilities