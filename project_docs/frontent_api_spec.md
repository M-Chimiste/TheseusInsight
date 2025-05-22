# Theseus Insight – Frontend ⇄ Backend API Contract (v0.1)

> **Purpose**  Map every HTTP/WebSocket call issued by the current frontend so the backend can expose matching endpoints with the correct shapes. All routes are *relative to the FastAPI root* (e.g. `http://localhost:8000`). Status codes shown are what the frontend expects – stricter codes are fine as long as `response.ok` is **true** in success cases.

---

## 1  Quick‑Reference Matrix

| Area                              | Method   | Path                                | Req. Body / Query                                           | Response (happy path) |
| --------------------------------- | -------- | ----------------------------------- | ----------------------------------------------------------- | --------------------- |
| **Models**                        | `GET`    | `/api/models`                       | –                                                           | `Model[]`             |
|                                   | `POST`   | `/api/models`                       | `ModelCreate`                                               | `Model`               |
|                                   | `DELETE` | `/api/models/{id}`                  | –                                                           | *(empty / 204)*       |
| **Newsletter**                    | `POST`   | `/api/newsletter/run`               | JSON **or** `multipart/form‑data`                           | `{ taskId: string }`  |
|                                   | `WS`     | `/ws/newsletter/{taskId}`           | –                                                           | `RunStatus` stream    |
| **Podcast**                       | `POST`   | `/api/podcast/generate`             | `multipart/form‑data`                                       | `{ taskId: string }`  |
|                                   | `WS`     | `/ws/podcast/{taskId}`              | –                                                           | `RunStatus` stream    |
| **Papers**                        | `GET`    | `/api/papers`                       | `page, score, sort_field, sort_direction, search, from, to` | `Paginated<Paper>`    |
| **Runs**                          | `GET`    | `/api/runs`                         | `page, sort_field, sort_direction, from, to`                | `Paginated<Run>`      |
|                                   | `DELETE` | `/api/runs/{runId}/artifact`        | –                                                           | *(empty / 204)*       |
| **Settings – orchestration**      | `GET`    | `/api/settings/orchestration`       | –                                                           | `OrchestrationConfig` |
|                                   | `PUT`    | `/api/settings/orchestration`       | `OrchestrationConfig`                                       | *(empty / 204)*       |
| **Settings – research interests** | `PUT`    | `/api/settings/research-interests`  | `{ interests: string }`                                     | *(empty / 204)*       |
| **Settings – visualizer**         | `PUT`    | `/api/settings/visualizer-settings` | `VisualizerSettings`                                        | *(empty / 204)*       |
| **Settings – email recipients**   | `PUT`    | `/api/settings/email-recipients`    | `{ recipients: string[] }`                                  | *(empty / 204)*       |
|                                   | `POST`   | `/api/settings/send-test-email`     | –                                                           | *(empty / 204)*       |

---

## 2  Shared Type Definitions (as used in the frontend)

```ts
// --- basic domain entities -----------------------------------------------
interface Model {
  id: string;          // primary‑key from DB
  name: string;        // display name (e.g. "gpt‑4o")
  provider: string;    // "openai", "azure-openai", etc.
}

interface Paper {
  id: number;
  title: string;
  abstract: string;
  score: number;       // similarity / relevance score
  date: string;        // ISO 8601
  url: string;
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
  nextPage: number | null;
}
```

---

## 3  Endpoint Details

### 3.1  `GET /api/models`

Returns every registered model so the UI can populate dropdowns.

```json
[
  { "id": "openai‑gpt-4o", "name": "GPT‑4o", "provider": "openai" },
  { "id": "hf‑mistral‑7b‑instruct", "name": "Mistral‑7B‑Instruct", "provider": "huggingface" }
]
```

*Status Codes*  `200 OK` ‑ success, `5xx` ‑ generic error.

---

### 3.2  `POST /api/models`

Used by the **Settings → Models** screen to add a new model.

```json
// request (example)
{
  "provider_id": 0,
  "name": "My‑LoRA‑13B",
  "config_json": {
    "model_name": "org/lora‑13b‑chat",
    "num_ctx": 4096,
    "temperature": 0.2
  }
}
```

Returns the created `Model` object.

*Status Codes*  `201 Created`, `400 Bad Request` (validation), `409 Conflict` (duplicate name).

---

### 3.3  `DELETE /api/models/{id}`

Deletes the model → frontend simply checks `response.ok`.

*Status Codes*  `204 No Content`, `404 Not Found`.

---

### 3.4  `POST /api/newsletter/run`

Starts the newsletter pipeline. Two payload styles are accepted:

1. **Pure JSON** – when *no* intro music is attached.
2. **`multipart/form‑data`** – `{ config: <stringified‑JSON>, intro_music_file: <binary> }`.

Minimal config schema:

```json
{
  "dateRange": { "from": "2025-04-01", "to": "2025-04-30" },
  "topics": ["LLM", "Mixture of Experts"],
  "judgeModel": "gpt‑4o",
  "newsletterModel": "gpt‑4o-mini",
  "podcastConfig": {
    "scriptModel": "gpt‑4",
    "ttsModel": "elevenlabs"
  }
}
```

*Response*

```json
{ "taskId": "23e8f9b2-138d-4d9c-9d06-d76b0a5ea9e7" }
```

*Status Codes*  `202 Accepted`, `400` (bad config).

#### WebSocket `/ws/newsletter/{taskId}`

Stream of `RunStatus` JSON messages until `overallStatus` reaches *completed* or *failed*.

---

### 3.5  `POST /api/podcast/generate`

Exactly mirrors the newsletter runner but always uses `multipart/form‑data` *(may include image/audio assets later)*.

Payload parts:

* `config` (string) – JSON with keys: `scriptModel`, `ttsModel`, `addVisualization`(bool), `visualizerConfig` (optional), `urls` (string\[]).
* Optional media files (e.g. `intro_music_file`).

*Response / WS* identical contract to the newsletter pipeline.

---

### 3.6  `GET /api/papers`

Query‐string params:

* `page` (int, **required**) – 1‑based page index.
* `score` (float) – min relevance score threshold.
* `sort_field` ("date" | "score").
* `sort_direction` ("asc" | "desc").
* `search` (string) – full‑text query.
* `from`, `to` (ISO 8601) – date filter.

*Response*

```json
{
  "items": [ /* Paper[] */ ],
  "nextPage": 3
}
```

---

### 3.7  `GET /api/runs`

Same paging/signature as `/api/papers`; returns `Paginated<Run>`.

### 3.8  `DELETE /api/runs/{runId}/artifact`

Drops the generated audio/video asset for a run.

---

## 3.9  Settings Endpoints

All settings screens follow the *fetch‑edit‑save* pattern:

| Path                                | Methods      | Notes                                                               |
| ----------------------------------- | ------------ | ------------------------------------------------------------------- |
| `/api/settings/orchestration`       | `GET`, `PUT` | Contract = `OrchestrationConfig` (see TS types in code)             |
| `/api/settings/research-interests`  | `PUT`        | `{ interests: string }`                                             |
| `/api/settings/visualizer-settings` | `PUT`        | `VisualizerSettings` – colours, FPS, etc.                           |
| `/api/settings/email-recipients`    | `PUT`        | `{ recipients: string[] }`                                          |
| `/api/settings/send-test-email`     | `POST`       | noop payload; backend should send a test email to saved recipients. |

All `PUT` calls expect `Content-Type: application/json` and treat **any** `2xx` as success.

---

## 4  Error Expectations

Frontend treats any non‑OK response as failure and shows a toast. Prefer returning JSON error bodies:

```json
{ "detail": "<human‑readable message>" }
```

---

## 5  Open Points / TODOs

1. **Download artifact** – UI currently lacks a *GET* for `/api/runs/{runId}/artifact`; if added, mirror `Content-Disposition: attachment` semantics.
2. **Settings retrieval** – UI only `PUT`s research‑interests/visualizer; if `GET` variants are added the UI could preload current values.
3. **Model update (PATCH)** – not yet wired; future enhancement.

---

*Last updated: 2025‑05‑14 – generated automatically from the React codebase.*
