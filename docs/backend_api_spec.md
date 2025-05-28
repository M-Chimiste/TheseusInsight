# Theseus Insight API – Specification (v1.0)

> **Base URL**: `http(s)://<host>:<port>/api`
> All endpoints are JSON-first and CORS-enabled; FastAPI automatically serves interactive docs at `/docs` and `/redoc`.

---

## 1. General Information

| Item               | Value                                                                                                                                                                |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Content-Type       | `application/json` unless otherwise noted                                                                                                                            |
| Auth               | **None** (all routes are open; add a proxy/auth layer if needed)                                                                                                     |
| Long-running tasks | Pipeline endpoints return a `task_id`. Poll **`GET /api/tasks/{task_id}/status`** or use WebSocket updates for progress |
| Error model        | Standard HTTP status codes with `{"detail": "<message>"}`                                                                                                            |

---

## 2. Data Models (abridged)

| Model                                                                             | Core Fields                                                               |
| --------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `DialogueItem`                                                                    | `speaker: str`, `text: str`                                               |
| `Script`                                                                          | `dialogue: List[DialogueItem]`, optional `metadata: dict`                 |
| `PodcastGenerationConfig`                                                         | text/tts model spec, voices, `output_format`, visualizer & matrix options |
| `PodcastGenerationRequest`                                                        | `texts: List[str]`, optional `config: PodcastGenerationConfig`            |
| `VisualizerConfig`                                                                | `resolution`, `fps`, `colours`, `matrix settings`, …                      |
| `Setting` / `Provider` / `ModelConfig` / `EmailRecipients` / `VisualizerSettings` | CRUD payloads for the settings service                                    |

*(Full field lists are inline in the “Models” section of each route group.)*

---

## 3. Route Groups


### 3.1 Papers (`/api/papers`)
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/papers` | Paginated papers with filters |
| **POST** | `/api/papers/similarity-search` | Semantic similarity search |
| **POST** | `/api/papers/hybrid-search` | Hybrid semantic + keyword search |
| **GET** | `/api/papers/without-embeddings` | Papers missing embeddings |
| **POST** | `/api/papers/{paper_id}/update-embedding` | Generate embedding for a paper |
| **GET** | `/api/papers/{paper_id}/similar` | Find similar papers |

### 3.2 Newsletter (`/api/newsletter`)
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **POST** | `/api/newsletter/run` | Start newsletter generation |
| **WS** | `/ws/newsletter/{task_id}` | WebSocket progress updates |
| **POST** | `/api/actions/run-newsletter-pipeline` | Full TheseusInsight newsletter workflow |

### 3.3 Podcast (`/api/podcast`)
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **POST** | `/api/podcast/generate` | Generate podcast |
| **WS** | `/ws/podcast/{task_id}` | WebSocket progress updates |
| **GET** | `/api/podcasts/history` | List generated podcasts |
| **GET** | `/api/podcasts/history/{id}` | Podcast details |

### 3.4 Visualizer
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **POST** | `/api/actions/run-visualizer-pipeline` | Generate waveform video |
| **WS** | `/ws/visualizer/{task_id}` | Progress updates |

### 3.5 Settings (`/api/settings`)
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/settings/orchestration` | Get orchestration config |
| **PUT** | `/api/settings/orchestration` | Update orchestration config |
| **GET** | `/api/model-providers` | List model providers |
| **GET** | `/api/settings/research-interests` | Get research interests |
| **PUT** | `/api/settings/research-interests` | Update research interests |
| **GET** | `/api/settings/email-recipients` | Get email recipients |
| **PUT** | `/api/settings/email-recipients` | Update email recipients |
| **GET** | `/api/settings/visualizer-settings` | Get default visualizer settings |
| **PUT** | `/api/settings/visualizer-settings` | Update visualizer settings |
| **POST** | `/api/settings/send-test-email` | Send test email |
| **GET** | `/api/settings/credentials` | Retrieve API credentials |
| **PUT** | `/api/settings/credentials` | Update API credentials |

### 3.6 Runs & Logs
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/runs` | Paginated run history |
| **DELETE** | `/api/runs/{run_id}/artifact` | Delete generated artifact |
| **GET** | `/api/logs` | Retrieve log entries |

### 3.7 Task Management (`/api/tasks`)
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/tasks/{task_id}/status` | Poll task status |
| **GET** | `/api/tasks/active` | List active tasks |
| **GET** | `/api/tasks/{task_id}/result` | Fetch result payload |
| **POST** | `/api/tasks/{task_id}/abort` | Abort a running task |
| **GET** | `/api/tasks/{task_id}/download/{file_type}` | Download task output |

## 4. Status Objects

Long‑running status routes converge on the following schema:

```jsonc
{
  "status": "processing | completed | failed",
  "current_step": "string",
  "progress": 0-100,
  "error": "message or null",
  "output_url": "/api/<group>/download/<file>"   // when completed
}
```

---

## 5. Typical Workflow Example

1. **Run the newsletter pipeline**

   ```bash
   curl -F "config=$(cat newsletter.json)" \
        http://localhost:8000/api/newsletter/run
   ```

2. **Monitor progress**

   ```bash
   curl http://localhost:8000/api/tasks/<task_id>/status
   ```

3. **Generate a podcast**

   ```bash
   curl -F "params_json=$(cat podcast_params.json)" \
        -F "pdf_files=@paper.pdf" \
        http://localhost:8000/api/podcast/generate
   ```

4. **Download result**

   ```bash
   curl -O http://localhost:8000/api/tasks/<task_id>/download/audio
   ```

*Last updated: 2025-05-25.*
