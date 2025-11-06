# Theseus Insight API – Specification (v1.1)

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
| Architecture       | **Modular Router System**: API endpoints are organized into focused router modules for better maintainability                                                       |

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

## 3. API Router Modules

The Theseus Insight API is organized into focused router modules for better maintainability and separation of concerns. Each router handles a specific domain:

### 3.1 Papers Router (`papers.py` → `/api/papers`)
**Handles**: Paper search, pagination, similarity search, embeddings
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/papers` | Paginated papers with filters |
| **POST** | `/api/papers/similarity-search` | Semantic similarity search |
| **POST** | `/api/papers/hybrid-search` | Hybrid semantic + keyword search |
| **GET** | `/api/papers/without-embeddings` | Papers missing embeddings |
| **POST** | `/api/papers/{paper_id}/update-embedding` | Generate embedding for a paper |
| **GET** | `/api/papers/{paper_id}/similar` | Find similar papers |

### 3.2 Newsletters & Podcasts Router (`newsletters_and_podcasts.py` → `/api/newsletter`, `/api/podcast`)
**Handles**: Content generation workflows
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **POST** | `/api/newsletter/run` | Start newsletter generation |
| **POST** | `/api/podcast/generate` | Generate podcast |
| **GET** | `/api/podcasts/history` | List generated podcasts |
| **GET** | `/api/podcasts/history/{id}` | Podcast details |

### 3.3 Settings Router (`settings.py` → `/api/settings`)
**Handles**: Configuration management, credentials, research interests
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/settings/orchestration` | Get orchestration config |
| **PUT** | `/api/settings/orchestration` | Update orchestration config |
| **GET** | `/api/settings/research-interests` | Get research interests |
| **PUT** | `/api/settings/research-interests` | Update research interests |
| **GET** | `/api/settings/email-recipients` | Get email recipients |
| **PUT** | `/api/settings/email-recipients` | Update email recipients |
| **GET** | `/api/settings/visualizer-settings` | Get default visualizer settings |
| **PUT** | `/api/settings/visualizer-settings` | Update visualizer settings |
| **POST** | `/api/settings/send-test-email` | Send test email |
| **GET** | `/api/settings/credentials` | Retrieve API credentials |
| **PUT** | `/api/settings/credentials` | Update API credentials |

### 3.4 Model Providers Router (`model_providers.py` → `/api/model-providers`)
**Handles**: Model provider management
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/model-providers` | List available model providers |

### 3.5 Runs & Tasks Router (`runs_and_tasks.py` → `/api/runs`, `/api/tasks`)
**Handles**: Task management, run history, status polling
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/runs` | Paginated run history |
| **DELETE** | `/api/runs/{run_id}/artifact` | Delete generated artifact |
| **GET** | `/api/tasks/{task_id}/status` | Poll task status |
| **GET** | `/api/tasks/active` | List active tasks |
| **GET** | `/api/tasks/{task_id}/result` | Fetch result payload |
| **POST** | `/api/tasks/{task_id}/abort` | Abort a running task |
| **GET** | `/api/tasks/{task_id}/download/{file_type}` | Download task output |

### 3.6 Logs Router (`logs.py` → `/api/logs`)
**Handles**: Logging and task history
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/logs` | Retrieve log entries |

### 3.7 Actions Router (`actions.py` → `/api/actions`)
**Handles**: Pipeline actions and workflow orchestration
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **POST** | `/api/actions/run-newsletter-pipeline` | Full TheseusInsight newsletter workflow |
| **POST** | `/api/actions/run-visualizer-pipeline` | Generate waveform video |

### 3.8 Database Router (`database.py` → `/api/database`)
**Handles**: Database import/export functionality
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **POST** | `/api/database/export` | Export database to archive |
| **POST** | `/api/database/import` | Import database from archive |

### 3.9 WebSockets Router (`websockets.py` → `/ws`)
**Handles**: Real-time progress updates
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **WS** | `/ws/newsletter/{task_id}` | WebSocket progress updates for newsletter generation |
| **WS** | `/ws/podcast/{task_id}` | WebSocket progress updates for podcast generation |
| **WS** | `/ws/visualizer/{task_id}` | WebSocket progress updates for visualizer generation |

### 3.10 Embedding Service Router (`embedding_service.py` → `/api/embedding-service`)
**Handles**: Bulk embedding job management, progress tracking, and hung job cleanup
| Method | Path | Purpose |
| ------ | ---- | ------- |
| **GET** | `/api/embedding-service/jobs` | List all active embedding jobs with checkpoints |
| **GET** | `/api/embedding-service/jobs/{job_id}` | Get status of a specific embedding job |
| **POST** | `/api/embedding-service/jobs/{job_id}/resume` | Resume an interrupted embedding job from checkpoint |
| **DELETE** | `/api/embedding-service/jobs/{job_id}` | Delete an embedding job and its checkpoint |
| **POST** | `/api/embedding-service/jobs/cleanup-hung` | Clean up jobs inactive >24 hours |

**Job Status Response:**
```json
{
  "job_id": "uuid",
  "operation": "embed_date_range | embed_all_missing",
  "parameters": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "model_name": "Alibaba-NLP/gte-large-en-v1.5"
  },
  "progress": {
    "total_papers": 500000,
    "processed_papers": 125000,
    "offset": 125000
  },
  "statistics": {
    "papers_embedded": 124500,
    "papers_failed": 500
  },
  "last_updated": "2025-10-17T10:30:00Z"
}
```

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

*Last updated: 2025-01-19 (v1.1 - Modular Router Architecture)*
