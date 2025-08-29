## PRD: Multi-Ollama Server Support for Bulk Profile-Aware Ingestion (LLM-as-Judge)

- Author: TheseusInsight Team
- Date: 2025-08-20
- Status: Draft (for review)

### Summary

Add first-class support for running bulk profile-aware “LLM as Judge” scoring across multiple Ollama servers (by URL) with one-concurrency-per-server workers, a durable job queue, and a separate long-running worker process. Provide UI controls to enable multi-server execution per bulk job, manage Ollama servers in Settings (CRUD + Test), display a live health dashboard for jobs, suspend all scheduled tasks during the run, and ensure robust idempotency, checkpointing, retry, and timeout handling for 10–200k records and >10-hour runs.

### Goals

- Use multiple Ollama servers identified by URL; no auth (vanilla installs; external hosts allowed).
- Ensure one-concurrency-per-server to avoid GPU contention; faster servers must process more items automatically (no slow server bottlenecks).
- Prevent UI/API hangs by isolating heavy processing into a separate worker service.
- Avoid active health checks under load; rely on request success/failure and timeouts.
- Make retry count and timeout (seconds) configurable (global defaults + per-run overrides).
- Suspend all scheduled tasks for the duration of a bulk judge job; auto-restore prior states on completion/failure/cancel.
- Idempotency via Paper+Profile existing score; optional overwrite.
- Allow cancel/abort for active jobs; maintain resumability via checkpoints/queue state.

### Non-Goals

- Authentication/TLS to Ollama servers.
- Cross-provider balancing (scope limited to Ollama for judge path).
- Changing research agent pipelines unrelated to bulk judging.
- Parallelism within a single Ollama server (remains 1).

### User Stories

- As an admin, I can configure multiple Ollama servers in Settings (name, URL, enabled), test connectivity, and set default timeout/retry values.
- As an operator, I can start a bulk judge run with a toggle to use multiple servers, choose which servers (or “all enabled”), and optionally override timeout/retry values.
- As an operator, I can see a job health dashboard showing queue progress, per-server throughput/latency/error counts, and recent failures.
- As an operator, I can cancel an ongoing job; work in-flight finishes or is safely re-queued.
- As an operator, I can trust that already-scored Paper+Profile pairs are not reprocessed unless I enable “overwrite existing.”
- As an operator, I can run 10–200k records for >10 hours without the API/UI freezing.

### UX and UI

- Settings → “Ollama Servers” (new section)
  - List: name, URL, enabled, last tested at, last latency/result, notes.
  - Actions: Add, Edit, Delete, Enable/Disable, Test Connection (pings server endpoint; no health polling under load).
  - Defaults: global request timeout (sec), global max retries.

- Bulk Jobs → “Bulk Judge”
  - New toggle: “Use multiple Ollama servers for judge”. When enabled:
    - Multi-select: Servers (defaults to all enabled).
    - Overrides: request timeout (sec), max retries.
    - Toggle: “Suspend all scheduled tasks during this run” (default ON).
  - Health Dashboard (visible during run):
    - Overall: queued, in-progress, completed, failed, ETA.
    - Per-server: active/disabled, tasks processed, avg latency, error rate, last error, circuit state.
    - Actions: Cancel Job.

### Functional Requirements

1) Configuration and Settings
- Manage servers: name (string), url (string), enabled (bool), notes (string optional).
- Test connection endpoint: returns version/ok and measured latency.
- Global defaults: request_timeout_sec (int), max_retries (int).

2) Job Submission (Bulk Judge)
- New parameters: use_multi_server (bool), server_ids (list, optional), request_timeout_sec (optional), max_retries (optional), suspend_scheduled_tasks (bool; default true).
- Job creation:
  - Build the workset of Paper+Profile pairs based on filters and overwrite flag.
  - Enqueue one task per pair into a durable DB-backed queue.
  - Initialize job state and progress counters.
  - If suspend_scheduled_tasks true: snapshot enabled states and disable all scheduled tasks.

3) Durable Queue
- Table stores: id, job_id, paper_id, profile_id, status [pending, leased, in_progress, completed, failed, canceled], attempts, last_error, assigned_server_url (nullable), leased_until (nullable), created_at/updated_at.
- Unique constraint: (job_id, paper_id, profile_id).
- Fetch policy: SELECT FOR UPDATE SKIP LOCKED on pending tasks; use short leases to recover from worker death (leased_until).
- Completion updates job progress counters. Failed tasks re-queued until attempts ≥ max_retries; then marked failed.

4) Worker Service (separate process)
- One worker per configured/selected server, with concurrency fixed at 1.
- Pulls tasks from the queue; assigns itself (server_url), and processes sequentially.
- Distribution policy: dynamic natural balancing—faster workers finish and request next task sooner; no global throttling.
- Circuit breaker per server within job: after N consecutive failures (configurable; default derived from max_retries), mark server disabled for remainder of job; unassign and requeue any leased tasks.
- Timeouts at request level; classify timeouts/connection errors as retriable; parsing/validation errors count as attempt and may either retry or be marked failed (configurable simple policy; default retry up to max_retries).
- No periodic health checks during load; rely on request results only.
- On cancel: worker stops pulling new tasks, completes in-flight, and exits gracefully.

5) Scoring Logic
- Continue using `OptimizedOllamaScorer` caching/prefiltering where applicable, adapted to per-task execution and idempotency.
- Idempotency: If a Paper+Profile already has a score and overwrite is false, skip (do not enqueue or treat as no-op on execution).
- Persist scores in batches when possible; ensure safe retry behavior (upsert by Paper+Profile).

6) Scheduled Tasks Suspension
- On job start: snapshot all tasks where is_enabled=true; set is_enabled=false.
- On job end (completed/failed/canceled): restore prior states from snapshot.
- Store snapshot in job state to survive process restarts.

7) Observability & Logs
- Per-job, per-server metrics: processed count, average latency, error counts, last error.
- Expose read APIs for dashboard; polling-based UI (no websockets required, optional later).
- Append structured logs for failures and circuit events, tagged with job_id and server_url.

### Non-Functional Requirements

- Reliability: tolerate restarts—queued tasks survive; leased tasks auto-recover after lease expiry.
- Scalability: handle 10–200k tasks and >10-hour runs; minimal DB contention via SKIP LOCKED, indexes.
- Safety: no health probes during load; all calls bounded by request timeout.
- Backward compatibility: single-server mode remains default and operational.

### Data Model (proposed migrations)

- ollama_servers
  - id (serial PK)
  - name (varchar)
  - url (varchar unique)
  - enabled (bool default true)
  - notes (text nullable)
  - last_tested_at (timestamp nullable)
  - last_test_latency_ms (int nullable)
  - last_test_ok (bool nullable)
  - created_at, updated_at

- judge_task_queue
  - id (serial PK)
  - job_id (UUID; FK to processing_jobs)
  - paper_id (int)
  - profile_id (int)
  - status (enum: pending, leased, in_progress, completed, failed, canceled)
  - attempts (int default 0)
  - last_error (text nullable)
  - assigned_server_url (varchar nullable)
  - leased_until (timestamp nullable)
  - created_at, updated_at
  - Indexes: (job_id, status), (status, leased_until), (paper_id, profile_id)
  - Unique: (job_id, paper_id, profile_id)

- processing_jobs (extension)
  - Add fields: cancel_requested (bool default false)
  - state JSONB to contain: suspended_tasks_snapshot, circuit_breakers, selected_server_ids, overrides

### API Changes

- Settings/Ollama Servers
  - GET /settings/ollama-servers
  - POST /settings/ollama-servers
  - PUT /settings/ollama-servers/{id}
  - DELETE /settings/ollama-servers/{id}
  - POST /settings/ollama-servers/{id}/test

- Bulk Judge
  - POST /bulk/judge-run (extend payload): use_multi_server, server_ids, request_timeout_sec, max_retries, suspend_scheduled_tasks
  - POST /bulk/judge-run/{job_id}/cancel
  - GET /bulk/judge-run/{job_id}/status (overall + per-server metrics)

### Worker Runtime

- New CLI/service: theseus-judge-worker
  - Loads selected servers for active jobs, spawns one worker per server.
  - Each worker loop: fetch task (SKIP LOCKED + lease), process with timeout, update result, maintain counters/circuit.
  - Periodically reports metrics for dashboard endpoints.
  - Safe shutdown on cancel or SIGTERM.

### Error Handling & Retries

- Global retry budget per task (attempts ≤ max_retries).
- Timeouts are retriable up to budget, then fail.
- Server-level circuit breaker: after N consecutive failures within this job, mark server disabled for job’s remainder; requeue any leased tasks.
- Log all failures with context for post-mortem.

### Security & Operations

- Assumes no auth and plain HTTP Ollama endpoints; document risks and recommend isolating servers on trusted network segments.
- Document environment sizing and expectations for heterogeneous servers.

### Rollout Plan

- Phase 1: DB migrations (servers table, queue table, processing_jobs extensions).
- Phase 2: Settings UI + APIs (CRUD + Test).
- Phase 3: Queue producer in Bulk Judge submission path; update job schema and suspension logic.
- Phase 4: Worker service; integrate scoring and idempotency; implement retries/timeouts/circuits.
- Phase 5: Bulk Jobs UI enhancements (toggle, server selection, overrides, health dashboard, cancel).
- Phase 6: Hardening & perf: long-run tests, failure injection, resume/cancel scenarios, and documentation.

### Testing Strategy

- Unit tests: queue operations (enqueue, lease, complete, retry), circuit breaker, suspension/resume of scheduled tasks snapshot.
- Integration: two mock Ollama servers (fast/slow) verify dynamic distribution; timeouts and failover requeue; cancel mid-run; resume after restart.
- E2E: 10k sample run across 2–4 servers; verify no UI/API hangs; verify no reprocessing when rerun without overwrite.

### Risks and Mitigations

- DB contention on large queues: mitigate with SKIP LOCKED, proper indexes, batched inserts, and short leases.
- Worker/process crashes: leases and idempotent upserts ensure recovery; progress is reflected in queue and job counters.
- Server lockups: bounded per-request timeout and circuit breaker prevent global stalls; other servers continue to progress.
- Scheduler restoration correctness: snapshot persisted in job state; restoration is idempotent on job exit handlers.

### Architecture Rationale (Scalability & Maintainability)

The DB-backed task queue with one worker per Ollama server achieves natural dynamic load balancing: faster servers complete tasks sooner and therefore pull more work, without central coordination. One-concurrency-per-server satisfies GPU contention constraints. Using short leases and SKIP LOCKED ensures progress despite crashes, and storing state in `processing_jobs` and the queue makes long (>10h) runs robust to restarts and redeploys.

Separating the worker process from the FastAPI service avoids UI-induced stalls and isolates long-running compute. The modular design (servers config, queue producer, worker, and UI dashboard) localizes concerns and supports incremental rollout. Circuit breakers, bounded timeouts, and global retry policies limit blast radius when a server degrades. The system remains maintainable through clear data models, explicit APIs, and observability endpoints.


