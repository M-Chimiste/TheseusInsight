# Theseus Insight – Frontend ⇄ Backend API Contract

> **Purpose**  Map every HTTP/WebSocket call issued by the current frontend so the backend can expose matching endpoints with the correct shapes. All routes are *relative to the FastAPI root* (e.g. `http://localhost:8000`). Status codes shown are what the frontend expects – stricter codes are fine as long as `response.ok` is **true** in success cases.

---

## 1  Quick‑Reference Matrix

| Area                              | Method   | Path                                | Req. Body / Query                                           | Response (happy path) |
| --------------------------------- | -------- | ----------------------------------- | ----------------------------------------------------------- | --------------------- |
| **Model Catalog**                 | `GET`    | `/api/model-catalog/`               | `page, page_size, provider, model_type, search, tags, is_favorite` | `ModelCatalogSearchResponse` |
|                                   | `POST`   | `/api/model-catalog/`               | `ModelCatalogEntry`                                         | `ModelCatalogEntry`   |
|                                   | `PUT`    | `/api/model-catalog/{id}`           | `ModelCatalogEntry`                                         | `ModelCatalogEntry`   |
|                                   | `DELETE` | `/api/model-catalog/{id}`           | –                                                           | *(empty / 204)*       |
|                                   | `GET`    | `/api/model-catalog/{id}`           | –                                                           | `ModelCatalogEntry`   |
|                                   | `POST`   | `/api/model-catalog/{id}/toggle-favorite` | –                                                           | `ModelCatalogEntry`   |
| **Model Providers**               | `GET`    | `/api/model-providers`              | –                                                           | `ModelProvider[]`     |
| **Newsletter**                    | `POST`   | `/api/newsletter/run`               | `multipart/form‑data`                                       | `{ taskId: string }`  |
|                                   | `WS`     | `/ws/newsletter/{taskId}`           | –                                                           | `RunStatus` stream    |
| **Podcast**                       | `POST`   | `/api/podcast/generate`             | `multipart/form‑data`                                       | `{ taskId: string }`  |
|                                   | `WS`     | `/ws/podcast/{taskId}`              | –                                                           | `RunStatus` stream    |
|                                   | `GET`    | `/api/podcasts/history`             | –                                                           | `PodcastListItem[]`   |
|                                   | `GET`    | `/api/podcasts/history/{id}`        | –                                                           | `PodcastDetail`       |
|                                   | `DELETE` | `/api/podcasts/history/{id}`        | –                                                           | *(empty / 204)*       |
|                                   | `PUT`    | `/api/podcasts/history/{id}/title`  | `{ title: string }`                                         | `{ status: string, message: string, title: string }` |
| **Papers**                        | `GET`    | `/api/papers`                       | `page, score, max_score, sort_field, sort_direction, search, from_date, to_date, page_size, profile_ids` | `PaginatedPapersResponse` |
|                                   | `POST`   | `/api/papers/similarity-search`     | `SimilaritySearchRequest`                                   | `SimilaritySearchResponse` |
|                                   | `POST`   | `/api/papers/hybrid-search`         | `HybridSearchRequest`                                       | `HybridSearchResponse` |
| **Research Agent**                | `POST`   | `/api/research-agent/run`           | `ResearchAgentRunRequest`                                   | `ResearchAgentRunResponse` |
|                                   | `GET`    | `/api/research-agent/status/{taskId}` | –                                                         | `TaskStatus`          |
|                                   | `GET`    | `/api/research-agent/result/{taskId}` | –                                                         | `ResearchTaskResult`  |
|                                   | `GET`    | `/api/research-agent/history`       | `limit, offset, status_filter`                             | `ResearchHistoryResponse` |
|                                   | `DELETE` | `/api/research-agent/{taskId}`      | –                                                           | `{ message: string }` |
|                                   | `GET`    | `/api/research-agent/workflow/info` | –                                                           | `WorkflowInfo`        |
|                                   | `GET`    | `/api/research-agent/health`        | –                                                           | `{ status: string }`  |
|                                   | `WS`     | `/ws/research-agent/{taskId}`       | –                                                           | `RunStatus` stream    |
| **Mind Maps**                     | `POST`   | `/api/mindmap/expand`               | `MindMapExpandRequest`                                      | `MindMapExpandResponse` |
|                                   | `POST`   | `/api/mindmap/parse-pdfs`           | `PDFParseRequest`                                           | `PDFParseResponse`    |
|                                   | `GET`    | `/api/mindmap/search-seeds`         | `query, limit`                                              | `MindMapSeedSearchResponse` |
|                                   | `GET`    | `/api/mindmap/paper/{id}`           | –                                                           | `PaperApiResponse`    |
|                                   | `GET`    | `/api/mindmap/reports`              | –                                                           | `MindMapReportListResponse` |
|                                   | `POST`   | `/api/mindmap/reports`              | `MindMapReportSaveRequest`                                  | `MindMapReportSaveResponse` |
|                                   | `GET`    | `/api/mindmap/reports/{id}`         | –                                                           | `MindMapReport`       |
|                                   | `PUT`    | `/api/mindmap/reports/{id}`         | `MindMapReportUpdateRequest`                                | `{ message: string, id: number }` |
|                                   | `DELETE` | `/api/mindmap/reports/{id}`         | –                                                           | `{ status: string, message: string }` |
|                                   | `PUT`    | `/api/mindmap/reports/{id}/title`   | `{ title: string }`                                         | `{ status: string, message: string, title: string }` |
|                                   | `PUT`    | `/api/mindmap/reports/{id}/description` | `{ description: string }`                               | `{ status: string, message: string, description: string }` |
|                                   | `WS`     | `/ws/mindmap/{taskId}`              | –                                                           | `RunStatus` stream    |
|                                   | `WS`     | `/ws/mindmap-pdf-parse/{taskId}`    | –                                                           | `RunStatus` stream    |
| **Research Timeline**             | `GET`    | `/api/trends/timeline-data`         | `topic_ids, profile_ids, period_type, start_date, end_date, include_key_papers, key_papers_limit, limit, source` | `TimelineDataResponse` |
|                                   | `POST`   | `/api/trends/generate-short-labels` | `{ profile_ids?: number[] }`                                | `{ status: string, count: number }` |
|                                   | `GET`    | `/api/profiles/{profile_id}/research-interests` | –                                             | `ProfileResearchInterestsResponse` |
| **Runs**                          | `GET`    | `/api/runs`                         | `page, sort_field, sort_direction, from_date, to_date`     | `PaginatedResponse`   |
|                                   | `DELETE` | `/api/runs/{runId}/artifact`        | –                                                           | *(empty / 204)*       |
| **Logs**                          | `GET`    | `/api/logs`                         | `limit, from_date, to_date`                                 | `LogEntry[]`          |
|                                   | `GET`    | `/api/task-history`                 | `limit, from_date, to_date`                                 | `TaskHistoryEntry[]`  |
| **Visualizer**                    | `POST`   | `/api/actions/run-visualizer-pipeline` | `multipart/form‑data`                                   | `{ taskId: string }`  |
|                                   | `WS`     | `/ws/visualizer/{taskId}`           | –                                                           | `RunStatus` stream    |
| **Task Management**               | `GET`    | `/api/tasks/{taskId}/status`        | –                                                           | `TaskStatus`          |
|                                   | `GET`    | `/api/tasks/active`                 | `task_types`                                                | `{ active_tasks: Task[] }` |
|                                   | `GET`    | `/api/tasks/recent-completed`       | `task_types`                                                | `{ completed_tasks: Task[] }` |
|                                   | `GET`    | `/api/tasks/{taskId}/result`        | –                                                           | object                |
|                                   | `POST`   | `/api/tasks/{taskId}/abort`         | –                                                           | `{ status: string }`  |
|                                   | `GET`    | `/api/tasks/{taskId}/download/{fileType}` | –                                                       | binary                |
| **Settings – orchestration**      | `GET`    | `/api/settings/orchestration`       | –                                                           | `OrchestrationConfig` |
|                                   | `PUT`    | `/api/settings/orchestration`       | `OrchestrationConfig`                                       | *(empty / 204)*       |
| **Settings – arxiv categories**   | `GET`    | `/api/settings/arxiv-categories`    | –                                                           | `ArxivCategoriesConfig` |
|                                   | `PUT`    | `/api/settings/arxiv-categories`    | `ArxivCategoriesConfig`                                     | *(empty / 204)*       |
| **Settings – research interests** | `GET`    | `/api/settings/research-interests`  | –                                                           | `ResearchInterests`   |
|                                   | `PUT`    | `/api/settings/research-interests`  | `{ interests: string }`                                     | *(empty / 204)*       |
| **Settings – visualizer**         | `GET`    | `/api/settings/visualizer-settings` | –                                                           | `VisualizerSettings`  |
|                                   | `PUT`    | `/api/settings/visualizer-settings` | `VisualizerSettings`                                        | *(empty / 204)*       |
| **Settings – email recipients**   | `GET`    | `/api/settings/email-recipients`    | –                                                           | `EmailRecipients`     |
|                                   | `PUT`    | `/api/settings/email-recipients`    | `{ recipients: string[] }`                                  | *(empty / 204)*       |
|                                   | `POST`   | `/api/settings/send-test-email`     | –                                                           | *(empty / 204)*       |
| **Settings – credentials**        | `GET`    | `/api/settings/credentials`         | –                                                           | `object`              |
|                                   | `PUT`    | `/api/settings/credentials`         | `object`                                                    | *(empty / 204)*       |
| **Settings – database**           | `GET`    | `/api/settings/database/export`     | –                                                           | binary (compressed archive) |
|                                   | `POST`   | `/api/settings/database/export-task` | –                                                         | `{ taskId: string }`  |

---

## 2  Shared Type Definitions (as used in the frontend)

```ts
// --- basic domain entities -----------------------------------------------
interface ModelProvider {
  id: number;
  name: string;        // "openai", "anthropic", "ollama", etc.
}

interface ModelCatalogEntry {
  id: number;
  alias: string;       // display name
  model_string: string; // actual model identifier
  provider_name: string;
  model_type: string;  // "chat", "embedding", "tts", etc.
  description?: string;
  max_new_tokens?: number;
  temperature?: number;
  num_ctx?: number;
  trust_remote_code?: boolean;
  tags?: string[];
  is_favorite?: boolean;
  created_at: string;
  updated_at: string;
}

interface Paper {
  id: number;
  title: string;
  abstract: string;
  score: number;       // similarity / relevance score
  date: string;        // ISO 8601
  url: string;
  rationale?: string;
  related?: boolean;
  cosine_similarity?: number;
  summary?: string;
  keywords?: string[];
}

interface PaperApiResponse extends Paper {
  embedding_model?: string;
  text?: string;
}

interface Run {
  id: number;
  date: string;        // ISO 8601
  pipeline_type: 'newsletter' | 'podcast';
  status: 'completed' | 'failed' | 'processing';
  duration: number;    // seconds
  artifact_path: string | null;
  artifact_size?: number; // bytes (optional)
}

// --- Research Agent types ------------------------------------------------
interface ResearchTaskResult {
  task_id: string;
  research_question: string;
  status: string;
  final_answer?: string;
  generation_summary?: string;
  statistics?: object;
  sub_queries?: string[];
  sources_gathered?: object[];
  judged_sources?: object[];
  evidence?: object[];
  compressed_notes?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  research_loop_count?: number;
  is_sufficient?: boolean;
  save_to_library?: boolean;
}

interface ResearchHistoryItem {
  task_id: string;
  research_question: string;
  status: string;
  created_at: string;
  completed_at?: string;
  error_message?: string;
}

interface ResearchHistoryResponse {
  tasks: ResearchHistoryItem[];
  total_count: number;
  limit: number;
  offset: number;
}

// --- Mind Map types -------------------------------------------------------
interface MindMapExpandRequest {
  paper_id?: string;
  topic_id?: number;
  k?: number;
  similarity_threshold?: number;
  layout_algorithm?: string;
  model_config_override?: object;
  expansion_order?: number;
  max_nodes_per_order?: number;
}

interface MindMapReport {
  id: number;
  title: string;
  description?: string;
  seed_paper_id: number;
  seed_paper_title: string;
  mindmap_data: object;
  parameters: object;
  statistics?: object;
  created_at: string;
}

interface MindMapReportListResponse {
  reports: MindMapReport[];
  total_count: number;
}

// --- Research Timeline types ----------------------------------------------
interface TimelineTopicData {
  topic_id: number;
  label: string;
  short_label?: string;
  total_papers: number;
  periods: TimelinePeriod[];
}

interface TimelinePeriod {
  period_start: string;
  period_end: string;
  period_type: string;  // "week" | "month" | "quarter" | "year"
  doc_count: number;
  growth_rate?: number;
  phase?: string;       // "emerging" | "growth" | "stable" | "declining"
  key_papers?: TimelineKeyPaper[];
}

interface TimelineKeyPaper {
  id: number;
  title: string;
  score: number;
  date: string;
}

interface TimelineDataResponse {
  topics: TimelineTopicData[];
  period_type: string;
  start_date: string;
  end_date: string;
  total_periods: number;
}

interface ProfileResearchInterest {
  id: number;
  interest_text: string;
  short_label?: string;
  similarity_threshold?: number;
  paper_count?: number;
}

interface ProfileResearchInterestsResponse {
  profile_id: number;
  profile_name: string;
  interests: ProfileResearchInterest[];
}

// --- worker progress via WebSocket ---------------------------------------
interface NodeStatus {
  nodeId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  progress: number;    // 0‑100
  timestamp: string;   // ISO 8601
}

interface RunStatus {
  taskId: string;
  nodes: NodeStatus[];
  overallStatus: 'pending' | 'processing' | 'completed' | 'failed';
  error?: string;
}

// --- pagination wrapper ---------------------------------------------------
interface Paginated<T> {
  items: T[];
  total_items: number;
  total_pages: number;
  current_page: number;
  nextPage: number | null;
}

interface PaginatedPapersResponse extends Paginated<PaperApiResponse> {}

interface ModelCatalogSearchResponse {
  models: ModelCatalogEntry[];
  total_count: number;
  total_pages: number;
  current_page: number;
  page_size: number;
}

// --- Settings types -------------------------------------------------------
interface OrchestrationConfig {
  judge_model: object;
  newsletter_model: object;
  podcast_script_model: object;
  tts_model: object;
  embedding_model: object;
  research_agent_model: object;
  mindmap_model: object;
  trends_model: object;
}

interface ArxivCategoriesConfig {
  main_category: string;
  filter_categories: string[];
}

interface ResearchInterests {
  interests: string;
}

interface EmailRecipients {
  recipients: string[];
}

interface VisualizerSettings {
  background_color: string;
  particle_color: string;
  line_color: string;
  fps: number;
  particle_count: number;
  [key: string]: any;
}

interface SystemInfoResponse {
  cpu_count: number;
  memory_total_gb: number;
  memory_available_gb: number;
  disk_free_gb: number;
  python_version: string;
  platform: string;
  database_size_mb: number;
  papers_count: number;
  topics_count: number;
  research_interests_count: number;
}

interface PerformanceConfig {
  enable_multithreading: boolean;
  thread_pool_size: number;
  batch_size: number;
  memory_limit_gb: number;
  enable_caching: boolean;
  log_level: string;
}
```

---

## 3  Endpoint Details

### 3.1  Model Catalog Endpoints

#### `GET /api/model-catalog/`

Search and filter models in the catalog.

Query parameters:
- `page` (int) – Page number (1-based)
- `page_size` (int) – Items per page (max 100)
- `provider` (string) – Filter by provider name
- `model_type` (string) – Filter by model type
- `search` (string) – Search in alias and description
- `tags` (string) – Comma-separated tag filters
- `is_favorite` (boolean) – Filter favorites only

Returns `ModelCatalogSearchResponse` with pagination metadata.

#### `POST /api/model-catalog/`

Create a new model entry.

```json
{
  "alias": "My Custom Model",
  "model_string": "org/custom-model-7b",
  "provider_name": "huggingface",
  "model_type": "chat",
  "description": "Custom fine-tuned model",
  "max_new_tokens": 2048,
  "temperature": 0.7,
  "tags": ["custom", "fine-tuned"]
}
```

#### `PUT /api/model-catalog/{id}`

Update an existing model entry. Same schema as POST.

#### `POST /api/model-catalog/{id}/toggle-favorite`

Toggle the favorite status of a model.

---

### 3.2  Research Agent Endpoints

#### `POST /api/research-agent/run`

Start a new research task.

```json
{
  "research_question": "What are the latest developments in multimodal LLMs?",
  "enable_sub_questions": true,
  "max_research_loops": 3,
  "save_to_library": true,
  "model_config": {
    "model_name": "gpt-4o",
    "temperature": 0.3
  }
}
```

Returns `{ task_id: string, message: string }`.

#### `GET /api/research-agent/history`

Retrieve research task history with optional filtering.

Query parameters:
- `limit` (int) – Maximum items to return (default: 50)
- `offset` (int) – Pagination offset (default: 0)
- `status_filter` (string) – Filter by status

#### `DELETE /api/research-agent/{taskId}`

Cancel a running task or delete a completed task.

#### WebSocket `/ws/research-agent/{taskId}`

Real-time progress updates for research tasks.

---

### 3.3  Mind Map Endpoints

#### `POST /api/mindmap/expand`

Generate a mind map from a seed paper or topic.

```json
{
  "paper_id": "12345",           // OR topic_id
  "topic_id": 42,                // OR paper_id
  "k": 10,                       // Number of similar papers
  "similarity_threshold": 0.3,
  "layout_algorithm": "force-directed",
  "expansion_order": 2,
  "max_nodes_per_order": 5
}
```

#### `POST /api/mindmap/parse-pdfs`

Parse PDF content for specified papers.

```json
{
  "paper_ids": ["123", "456", "789"]
}
```

#### `GET /api/mindmap/search-seeds`

Search for suitable seed papers.

Query parameters:
- `query` (string) – Search query
- `limit` (int) – Maximum results (default: 10)

#### Mind Map Reports

- `GET /api/mindmap/reports` – List all saved reports
- `POST /api/mindmap/reports` – Save a new report
- `GET /api/mindmap/reports/{id}` – Get specific report
- `PUT /api/mindmap/reports/{id}` – Update report
- `DELETE /api/mindmap/reports/{id}` – Delete report
- `PUT /api/mindmap/reports/{id}/title` – Update title only

#### WebSocket `/ws/mindmap/{taskId}`

Progress updates for mind map generation.

#### WebSocket `/ws/mindmap-pdf-parse/{taskId}`

Progress updates for PDF parsing tasks.

---

### 3.4  Research Timeline Endpoints

The Research Timeline provides an interactive stream graph visualization for tracking how your research interests evolve over time.

#### `GET /api/trends/timeline-data`

Get timeline data for stream graph visualization.

Query parameters:
- `topic_ids` (string) – Comma-separated list of research interest IDs to include
- `profile_ids` (string) – Comma-separated list of profile IDs to filter by
- `period_type` (string) – Time granularity: "week", "month", "quarter", "year" (default: "month")
- `start_date` (string) – Optional start date filter (ISO 8601)
- `end_date` (string) – Optional end date filter (ISO 8601)
- `include_key_papers` (boolean) – Include influential papers for each period (default: true)
- `key_papers_limit` (int) – Number of key papers per topic per period (default: 3)
- `limit` (int) – Maximum number of topics to return (default: 10)
- `source` (string) – Data source, use `profile_interests` for profile-specific interests

Returns `TimelineDataResponse` with topics, periods, paper counts, growth rates, and key papers.

#### `POST /api/trends/generate-short-labels`

Generate AI-summarized short labels for research interests.

```json
{
  "profile_ids": [1, 2]  // Optional: specific profiles to generate labels for
}
```

Returns processing status with count of labels generated. Uses configured LLM model and caches results in database.

#### `GET /api/profiles/{profile_id}/research-interests`

Get research interests for a specific profile for timeline selection.

Returns profile's research interests with metadata including interest descriptions, similarity thresholds, short labels, and associated paper counts.

---

### 3.5  Enhanced Papers Endpoints

#### `GET /api/papers`

Enhanced with additional filtering:

Query parameters:
- `page` (int) – Page number
- `score` (float) – Minimum score
- `max_score` (float) – Maximum score
- `sort_field` ("date" | "score")
- `sort_direction` ("asc" | "desc")
- `search` (string) – Full-text search
- `from_date`, `to_date` (ISO 8601) – Date range
- `page_size` (int) – Items per page (max 100)
- `profile_ids` (string) – Comma-separated profile IDs to filter by

#### `POST /api/papers/similarity-search`

Semantic similarity search.

```json
{
  "query_text": "multimodal language models",
  "limit": 20,
  "similarity_threshold": 0.7
}
```

#### `POST /api/papers/hybrid-search`

Combined semantic and keyword search.

```json
{
  "query_text": "transformer architecture",
  "semantic_weight": 0.6,
  "keyword_weight": 0.4,
  "limit": 20
}
```

---

### 3.7  Enhanced Settings Endpoints

All settings endpoints now support both GET and PUT operations:

#### Orchestration Settings
- `GET /api/settings/orchestration` – Retrieve current config
- `PUT /api/settings/orchestration` – Update config

#### ArXiv Categories
- `GET /api/settings/arxiv-categories` – Get categories
- `PUT /api/settings/arxiv-categories` – Update categories

#### Research Interests
- `GET /api/settings/research-interests` – Get interests
- `PUT /api/settings/research-interests` – Update interests

#### Email Recipients
- `GET /api/settings/email-recipients` – Get recipients
- `PUT /api/settings/email-recipients` – Update recipients

#### Visualizer Settings
- `GET /api/settings/visualizer-settings` – Get visualizer config
- `PUT /api/settings/visualizer-settings` – Update config

#### API Credentials
- `GET /api/settings/credentials` – Get masked credentials
- `PUT /api/settings/credentials` – Update credentials

#### Database Management
- `GET /api/settings/database/export` – Export database (streaming download)
- `POST /api/settings/database/export-task` – Start export as background task

---

### 3.8  Enhanced Task Management

#### `GET /api/tasks/recent-completed`

Get recently completed tasks with results available.

Query parameters:
- `task_types` (string) – Comma-separated filter

#### `GET /api/tasks/{taskId}/download/{fileType}`

Download task artifacts:
- `fileType`: "markdown", "audio", "video"

Returns binary data with appropriate `Content-Disposition` headers.

---

### 3.9  Podcast History Management

#### `GET /api/podcasts/history`

List all generated podcasts.

#### `GET /api/podcasts/history/{id}`

Get detailed podcast information.

#### `DELETE /api/podcasts/history/{id}`

Delete a podcast.

#### `PUT /api/podcasts/history/{id}/title`

Update podcast title.

```json
{ "title": "New Podcast Title" }
```

---

### 3.10  Logs & History

#### `GET /api/logs`

Get operational logs.

Query parameters:
- `limit` (int) – Maximum entries (1-1000, default: 100)
- `from_date` (string) – Start date (YYYY-MM-DD)
- `to_date` (string) – End date (YYYY-MM-DD)

#### `GET /api/task-history`

Get comprehensive task execution history.

Same query parameters as logs endpoint.

---

## 4  WebSocket Endpoints

All WebSocket endpoints follow the pattern `/ws/{type}/{taskId}` and return `RunStatus` messages:

- `/ws/newsletter/{taskId}` – Newsletter generation
- `/ws/podcast/{taskId}` – Podcast generation  
- `/ws/visualizer/{taskId}` – Audio visualization
- `/ws/research-agent/{taskId}` – Research agent tasks
- `/ws/mindmap/{taskId}` – Mind map generation
- `/ws/mindmap-pdf-parse/{taskId}` – PDF parsing

---

## 5  Error Handling

Frontend treats any non‑OK response as failure and shows a toast. Prefer returning JSON error bodies:

```json
{ "detail": "<human‑readable message>" }
```

Common error codes:
- `400` – Bad Request (validation errors)
- `404` – Not Found (resource doesn't exist)
- `409` – Conflict (duplicate entries)
- `500` – Internal Server Error

---

## 6  Breaking Changes from v0.2

1. **Model Management**: Replaced simple `/api/models` with comprehensive `/api/model-catalog/` endpoints
2. **Enhanced Pagination**: Added `total_items`, `total_pages`, `current_page` to pagination responses
3. **New Feature Areas**: Research Agent, Mind Maps, Research Timeline
4. **Settings Enhancement**: All settings now support GET operations
5. **WebSocket Expansion**: Added multiple new WebSocket types for different features
6. **Paper Filtering**: Enhanced with topic filtering and semantic/hybrid search
7. **Task Management**: Added recent completed tasks and artifact downloads

---

*Last updated: 2025‑01‑27 – reflects current application state including all major features.* 