# Theseus Insight API – Specification (v0.9.0)

> **Base URL**: `http(s)://<host>:<port>/api`
> All endpoints are JSON-first and CORS-enabled; FastAPI automatically serves interactive docs at `/docs` and `/redoc`.

---

## 1. General Information

| Item               | Value                                                                                                                                                                |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Content-Type       | `application/json` unless otherwise noted                                                                                                                            |
| Auth               | **None** (all routes are open; add a proxy/auth layer if needed)                                                                                                     |
| Long-running tasks | `/generate`, `/regenerate`, `/visualizer/generate`, `/theseus_insight/run` return a `task_id`. Poll their companion **`GET …/status/{task_id}`** routes for progress |
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

### 3.1 PDF (`/api/pdf`)

| Method & Path            | Purpose             | Request                                    | Response                                 |
| ------------------------ | ------------------- | ------------------------------------------ | ---------------------------------------- |
| **POST** `/upload`       | Upload a single PDF | **multipart/form-data** field `file` (PDF) | `{filename, file_path}`                  |
| **POST** `/batch-upload` | Upload many PDFs    | `files[]` (array of PDFs)                  | list of `{filename, file_path \| error}` |

### 3.2 Script (`/api/script`)

| Method     | Path                    | Purpose                                               |
| ---------- | ----------------------- | ----------------------------------------------------- |
| **GET**    | `/list`                 | List all saved scripts                                |
| **GET**    | `/load/{filename}`      | Fetch a script JSON                                   |
| **POST**   | `/save?filename={name}` | Save a script – body = `Script`                       |
| **DELETE** | `/{filename}`           | Delete script (and DB podcast if prefixed `podcast_`) |

Returns standard `200 OK` / `404 Not Found` / `500 Internal Server Error`.

### 3.3 Podcast (`/api/podcast`)

| Method   | Path                   | Purpose                                                                                                       |
| -------- | ---------------------- | ------------------------------------------------------------------------------------------------------------- |
| **POST** | `/generate`            | Create podcast from URLs, PDFs & config (multipart: `config`, `urls`, `files[]`, optional `intro_music_file`) |
| **POST** | `/regenerate`          | Regenerate audio from an existing `Script` & new `PodcastGenerationConfig`                                    |
| **GET**  | `/status/{task_id}`    | Poll progress (`status`, `current_step`, `progress`, `error`, `output_url`)                                   |
| **GET**  | `/download/{filename}` | Download final MP3/WAV                                                                                        |

Successful `/generate` and `/regenerate` return `{task_id, status: "processing"}`.

### 3.4 Visualizer (`/api/visualizer`)

| Method   | Path                   | Purpose                                                                            |
| -------- | ---------------------- | ---------------------------------------------------------------------------------- |
| **POST** | `/generate`            | Build MP4 waveform/matrix video for an audio file (`file`, optional `config` JSON) |
| **GET**  | `/status/{task_id}`    | Poll progress (`status`, `progress`, `output_url`)                                 |
| **GET**  | `/download/{filename}` | Download finished video                                                            |

### 3.5 Settings (`/api`)

| Method                      | Path                                                | Summary                    |
| --------------------------- | --------------------------------------------------- | -------------------------- |
| `GET`                       | `/settings`                                         | Key‑value dump             |
| `GET` \| `PUT` \| `DELETE`  | `/settings/{key}`                                   | CRUD single setting        |
| `GET` \| `POST` \| `DELETE` | `/providers` / `/providers/{id}`                    | LLM/TTS provider registry  |
| `GET` \| `POST` \| `DELETE` | `/models?provider_id=` / `/models` / `/models/{id}` | Model configs per provider |
| `GET` \| `PUT`              | `/settings/email-recipients`                        | Newsletter recipient list  |
| `GET` \| `PUT`              | `/settings/visualizer-settings`                     | Default visualizer prefs   |
| `POST`                      | `/settings/send-test-email`                         | Fire a test Gmail message  |

All settings endpoints answer with the persisted object or `{result: "deleted"}`.

### 3.6 Theseus Insight Pipeline (`/api/theseus_insight`)

| Method   | Path   | Purpose                                                                                                                                                                                                                                                                                           |
| -------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **POST** | `/run` | Kick off the full papers → newsletter → podcast workflow. Multipart body: **`config`** (JSON string) plus optional `research_interests_file`, `orchestration_file`. Returns `{task_id, status: "started"}` and progress via in-memory polling (future `/status` route is inside active task map). |

---

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

1. **Upload PDFs**

   ```bash
   curl -F "files=@paper1.pdf" -F "files=@paper2.pdf" \
        http://localhost:8000/api/pdf/batch-upload
   ```

2. **Generate podcast**

   ```bash
   curl -F "config=$(cat podcast_config.json)" \
        -F "files=@paper1.pdf" -F "files=@paper2.pdf" \
        http://localhost:8000/api/podcast/generate
   ```

3. **Poll until done**

   ```bash
   curl http://localhost:8000/api/podcast/status/<task_id>
   ```

4. **Download**

   ```bash
   curl -O http://localhost:8000/api/podcast/download/podcast_final_1715500000.mp3
   ```

---

## 6. Future Extensions

* Authentication middleware (JWT / API key)
* `/theseus_insight/status/{task_id}` for symmetry
* Pagination & filtering for `/script/list` and settings collections
