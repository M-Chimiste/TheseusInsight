## PRD: Multi-Ollama Server Support for Bulk Profile-Aware Ingestion (LLM-as-Judge)

- Author: TheseusInsight Team
- Date: 2025-08-20
- Status: Ready for Implementation
- Version: 2.0 (Updated with detailed implementation plan)

### Summary

Add first-class support for running bulk profile-aware "LLM as Judge" scoring across multiple Ollama servers (by URL) with one-concurrency-per-server workers, a durable job queue, and a separate long-running worker process. Provide UI controls to enable multi-server execution per bulk job, manage Ollama servers in Settings (CRUD + Test), display a live health dashboard for jobs, suspend all scheduled tasks during the run, and ensure robust idempotency, checkpointing, retry, and timeout handling for 10–200k records and >10-hour runs.

### Goals

- Use multiple Ollama servers identified by URL; no auth (vanilla installs; external hosts allowed).
- Ensure one-concurrency-per-server to avoid GPU contention; faster servers must process more items automatically (dynamic balancing).
- Prevent UI/API hangs by isolating heavy processing into separate worker processes.
- Avoid active health checks under load; rely on request success/failure and timeouts.
- Make retry count and timeout (seconds) configurable (global defaults + per-run overrides).
- Suspend all scheduled tasks for the duration of a bulk judge job; auto-restore prior states on completion/failure/cancel.
- Idempotency via Paper+Profile existing score; optional overwrite.
- Allow cancel/abort for active jobs; maintain resumability via checkpoints/queue state.
- Intelligent error handling: differentiate between LLM inference failures, server connectivity issues, and data problems.
- Real-time monitoring dashboard with error rates, processing rates, ETA, and pause/resume/cancel functionality.

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

### UX and UI Requirements

#### 1. Settings → Ollama Servers Management
- **Server List View**:
  - Table columns: Name, URL, Status, Last Test, Latency, Actions
  - Status indicators: Online (green), Offline (red), Testing (yellow)
  - Bulk actions: Enable/Disable multiple servers, Test all servers

- **Server Configuration Modal**:
  - Fields: Name, URL, Notes, Enable/Disable toggle
  - Test Connection button with real-time feedback
  - Latency measurement and success/failure indicators

- **Global Configuration Panel**:
  - Default timeout settings (seconds)
  - Default max retries per error type
  - Circuit breaker thresholds

#### 2. Bulk Judge Job Interface
- **Enhanced Job Creation**:
  - Multi-server toggle with server selection
  - Configuration overrides (timeout, retries)
  - Scheduler suspension toggle (default: ON)
  - Conflict detection with other running jobs

- **Real-time Monitoring Dashboard**:
  - **Overall Progress**: Queued/In-Progress/Completed/Failed counts, ETA calculation
  - **Per-Server Metrics**: Processing rate (papers/sec), error rate, average latency
  - **Visual Indicators**: Progress bars, status badges, error notifications
  - **Job Controls**: Pause/Resume/Cancel buttons with confirmation dialogs

#### 3. Job History & Monitoring Page
- **Active Jobs View**:
  - List of running bulk judge jobs with quick stats
  - Server utilization overview
  - Quick access to detailed monitoring

- **Job Details Modal**:
  - Comprehensive job information
  - Per-server performance breakdown
  - Error logs and retry attempts
  - Timeline view of job progress

#### 4. Conflict Prevention System
- **Job Conflict Detection**:
  - Warning when starting newsletter/mindmap/other jobs during bulk operations
  - Automatic suggestions to pause bulk jobs
  - Clear messaging about resource conflicts

- **Status Notifications**:
  - Toast notifications for job state changes
  - Error alerts with actionable information
  - Progress updates without being intrusive

#### 5. Responsive Design Considerations
- **Desktop**: Full dashboard with detailed metrics and controls
- **Tablet**: Condensed view with collapsible sections
- **Mobile**: Essential controls and high-level status only

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
- Intelligent error handling:
  - **LLM Inference Errors**: Malformed responses, parsing failures, content validation (retry up to 3 times, then mark failed)
  - **Server Connectivity**: Network timeouts, connection refused, HTTP errors (retry up to 3 times, then terminate worker)
  - **Data Issues**: Corrupted paper data, missing abstracts, encoding problems (mark failed immediately)
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
- Real-time monitoring dashboard with:
  - Error rates per server
  - Processing rates (papers/second per server)
  - Estimated completion time based on current rates
  - Pause/resume/cancel functionality
  - Warning prompts when starting conflicting jobs (newsletter, mindmap, etc.)
- Per-job, per-server metrics: processed count, average latency, error counts, last error.
- Expose read APIs for dashboard; polling-based UI (refresh every few seconds).
- Append structured logs for failures and circuit events, tagged with job_id and server_url.

### Non-Functional Requirements

- Reliability: tolerate restarts—queued tasks survive; leased tasks auto-recover after lease expiry.
- Scalability: handle 10–200k tasks and >10-hour runs; minimal DB contention via SKIP LOCKED, indexes.
- Safety: no health probes during load; all calls bounded by request timeout.
- Backward compatibility: single-server mode remains default and operational.

### Data Model (proposed migrations)

#### 1. `ollama_servers` (New Table)
```sql
CREATE TABLE ollama_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(500) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    notes TEXT,
    last_tested_at TIMESTAMP WITH TIME ZONE,
    last_test_latency_ms INTEGER,
    last_test_ok BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

#### 2. `judge_task_queue` (New Table)
```sql
CREATE TABLE judge_task_queue (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES processing_jobs(id) ON DELETE CASCADE,
    paper_id INTEGER NOT NULL,
    profile_id INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'leased', 'in_progress', 'completed', 'failed', 'canceled')),
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    assigned_server_url VARCHAR(500),
    leased_until TIMESTAMP WITH TIME ZONE,
    leased_by_worker VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, paper_id, profile_id)
);

-- Performance indexes
CREATE INDEX idx_judge_queue_status ON judge_task_queue(status);
CREATE INDEX idx_judge_queue_job_status ON judge_task_queue(job_id, status);
CREATE INDEX idx_judge_queue_lease ON judge_task_queue(status, leased_until) WHERE leased_until IS NOT NULL;
CREATE INDEX idx_judge_queue_server ON judge_task_queue(assigned_server_url, status);
```

#### 3. `processing_jobs` Extensions
```sql
-- Add bulk judge specific fields to existing processing_jobs table
ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS job_type VARCHAR(50) DEFAULT 'bulk_judge';
ALTER TABLE processing_jobs ADD COLUMN IF NOT EXISTS cancel_requested BOOLEAN DEFAULT FALSE;

-- Extend state JSONB to include bulk judge specific data
-- Will contain: suspended_tasks_snapshot, circuit_breakers, selected_server_ids, overrides, server_metrics
```

#### 4. Worker Heartbeat Table (Optional)
```sql
CREATE TABLE worker_heartbeats (
    id SERIAL PRIMARY KEY,
    worker_id VARCHAR(100) NOT NULL,
    server_url VARCHAR(500) NOT NULL,
    job_id UUID REFERENCES processing_jobs(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    tasks_processed INTEGER DEFAULT 0,
    current_task_id INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(worker_id, server_url, job_id)
);
```

### API Changes

#### 1. Ollama Server Management
```
GET    /api/settings/ollama-servers           # List all servers
POST   /api/settings/ollama-servers           # Create new server
GET    /api/settings/ollama-servers/{id}      # Get server details
PUT    /api/settings/ollama-servers/{id}      # Update server
DELETE /api/settings/ollama-servers/{id}      # Delete server
POST   /api/settings/ollama-servers/{id}/test # Test server connectivity
POST   /api/settings/ollama-servers/{id}/toggle # Enable/disable server
```

#### 2. Bulk Judge Operations
```
POST   /api/bulk-operations/bulk-judge          # Start bulk judge job (extended)
GET    /api/bulk-operations/job/{job_id}       # Get job status
POST   /api/bulk-operations/job/{job_id}/pause # Pause job
POST   /api/bulk-operations/job/{job_id}/resume # Resume job
POST   /api/bulk-operations/job/{job_id}/cancel # Cancel job
GET    /api/bulk-operations/job/{job_id}/metrics # Get detailed metrics
```

#### 3. Job Monitoring & Dashboard
```
GET    /api/bulk-operations/active-jobs         # List active bulk jobs
GET    /api/bulk-operations/server-metrics      # Get per-server performance
GET    /api/bulk-operations/queue-status        # Get queue depth and status
POST   /api/bulk-operations/conflict-check      # Check for job conflicts
```

#### 4. Worker Management (Internal)
```
POST   /api/workers/launch                      # Launch worker processes
GET    /api/workers/status                      # Get worker status
POST   /api/workers/shutdown/{worker_id}       # Shutdown specific worker
GET    /api/workers/heartbeats                  # Get worker heartbeats
```

#### 5. Configuration Management
```
GET    /api/settings/bulk-judge-config         # Get global defaults
PUT    /api/settings/bulk-judge-config         # Update global defaults
GET    /api/settings/scheduler-status          # Get scheduler status
POST   /api/settings/scheduler/pause           # Pause all scheduled tasks
POST   /api/settings/scheduler/resume          # Resume scheduled tasks
```

### Worker Runtime Architecture

#### 1. Process Management
- **Launcher Script**: `theseus-judge-worker` (Python script)
- **Environment Detection**: Uses `DATABASE_URL` and working directory for identification
- **Multi-Process Architecture**: One worker process per Ollama server
- **Process Monitoring**: Heartbeat system with automatic recovery

#### 2. Worker Lifecycle
```
1. Environment validation and database connection
2. Server assignment and configuration loading
3. Queue monitoring and task leasing
4. Processing loop with intelligent error handling
5. Graceful shutdown with in-flight task completion
```

#### 3. Processing Loop (Per Worker)
```python
while active:
    # 1. Lease next available task (SKIP LOCKED)
    task = lease_next_task(server_url, job_id)

    # 2. Process with appropriate error handling
    if task:
        try:
            result = process_paper(task, server_config)
            mark_task_completed(task.id, result)
        except LLMError:
            handle_llm_error(task, attempt_count)
        except ServerError:
            handle_server_error(task, attempt_count)
        except DataError:
            mark_task_failed(task, "Data issue")

    # 3. Update heartbeat and metrics
    update_worker_status()
```

#### 4. Error Handling Strategy
- **LLM Inference Errors**: Retry up to 3 times, then mark failed
- **Server Connectivity**: Retry up to 3 times, then terminate worker
- **Data Issues**: Immediate failure without retries
- **Circuit Breaker**: Disable server after consecutive failures

#### 5. Heartbeat & Monitoring
- **Frequency**: Every 30 seconds during active processing
- **Data**: Tasks processed, current status, error counts, performance metrics
- **Recovery**: Automatic lease expiration (5 minutes) for crashed workers

### Intelligent Error Handling & Classification

#### 1. Error Types & Strategies

| Error Type | Examples | Retry Strategy | Max Retries | Action After Max |
|------------|----------|----------------|-------------|------------------|
| **LLM Inference** | Malformed JSON, parsing errors, content validation failures | Exponential backoff | 3 | Mark task failed |
| **Server Connectivity** | Network timeouts, connection refused, HTTP 5xx errors | Linear backoff | 3 | Terminate worker |
| **Data Issues** | Missing abstracts, corrupted content, encoding errors | No retry | 0 | Mark task failed |
| **Rate Limiting** | HTTP 429, temporary server overload | Exponential backoff | 5 | Mark task failed |

#### 2. Circuit Breaker Logic
- **Trigger**: N consecutive failures (configurable, default: 5)
- **Action**: Mark server disabled for current job
- **Recovery**: Server remains disabled until job completion
- **Requeuing**: Any leased tasks automatically requeued for other servers

#### 3. Worker Termination Conditions
- **Server Connectivity**: After 3 consecutive server errors
- **Process Health**: Memory usage > threshold, unresponsive threads
- **Job Cancellation**: Graceful shutdown with in-flight task completion
- **Lease Expiration**: Automatic recovery for crashed workers (5-minute timeout)

#### 4. Logging & Monitoring
- **Structured Logs**: Error type, retry count, server URL, task ID
- **Metrics Collection**: Error rates, retry success rates, worker health
- **Post-Mortem Analysis**: Detailed error context for debugging
- **Alerting**: High error rates trigger notifications

### Security & Operations

- Assumes no auth and plain HTTP Ollama endpoints; document risks and recommend isolating servers on trusted network segments.
- Document environment sizing and expectations for heterogeneous servers.

### Implementation Timeline

**Total Duration**: 4 weeks  
**Total Effort**: ~15-20 days of development

#### Phase 1: Database Foundation & Core Infrastructure (Week 1)
- **Duration**: 3-4 days
- **Deliverables**: Database migrations, worker process setup, core queue infrastructure
- **Risk Level**: Low (infrastructure work)

#### Phase 2: Ollama Server Management & Settings (Week 1-2)
- **Duration**: 2-3 days
- **Deliverables**: Server CRUD APIs, Settings UI, configuration management
- **Risk Level**: Low (standard CRUD operations)

#### Phase 3: Job Management & Scheduler Integration (Week 2)
- **Duration**: 3-4 days
- **Deliverables**: Enhanced bulk judge API, scheduler suspension, error handling
- **Risk Level**: Medium (integrates with existing systems)

#### Phase 4: Worker Service & Processing Logic (Week 2-3)
- **Duration**: 4-5 days
- **Deliverables**: Multi-process workers, scoring integration, queue management
- **Risk Level**: High (core processing logic)

#### Phase 5: Monitoring Dashboard & UI (Week 3-4)
- **Duration**: 4-5 days
- **Deliverables**: Real-time dashboard, job controls, conflict prevention
- **Risk Level**: Medium (UI and monitoring)

#### Phase 6: Testing & Hardening (Week 4)
- **Duration**: 3-4 days
- **Deliverables**: Comprehensive testing, production hardening, documentation
- **Risk Level**: Low (testing and documentation)

### Testing Strategy

- Unit tests: queue operations (enqueue, lease, complete, retry), circuit breaker, suspension/resume of scheduled tasks snapshot.
- Integration: two mock Ollama servers (fast/slow) verify dynamic distribution; timeouts and failover requeue; cancel mid-run; resume after restart.
- E2E: 10k sample run across 2–4 servers; verify no UI/API hangs; verify no reprocessing when rerun without overwrite.

## Implementation Plan

### Phase 1: Database Foundation & Core Infrastructure (Week 1)
**Estimated Time**: 3-4 days

#### 1.1 Database Schema Creation
- Create `ollama_servers` table with CRUD operations
- Create new `judge_task_queue` table (drop existing if present)
- Extend `processing_jobs` table with bulk judge specific fields
- Add database indexes for performance
- Create migration scripts

#### 1.2 Environment Detection & Worker Process Setup
- Implement environment identification (DATABASE_URL + working directory)
- Create worker process launcher script
- Set up process management and monitoring
- Implement worker heartbeat mechanism

#### 1.3 Core Queue Infrastructure
- Implement queue producer (enqueue papers for processing)
- Implement queue consumer with SKIP LOCKED
- Create lease management system
- Add idempotency checks (Paper+Profile score existence)

### Phase 2: Ollama Server Management & Settings (Week 1-2)
**Estimated Time**: 2-3 days

#### 2.1 Backend API for Server Management
- CRUD operations for Ollama servers
- Server connectivity testing
- Server health monitoring (without active probes)
- Configuration validation

#### 2.2 Frontend Settings Integration
- Ollama Servers management UI in Settings
- Server testing interface
- Global defaults configuration (timeout, retries)
- Server enable/disable controls

### Phase 3: Job Management & Scheduler Integration (Week 2)
**Estimated Time**: 3-4 days

#### 3.1 Enhanced Bulk Judge API
- Extend bulk judge endpoint with multi-server support
- Implement job creation with server selection
- Add configuration overrides (timeout, retries per job)
- Integrate with existing checkpoint system

#### 3.2 Scheduler Suspension System
- Implement scheduled task snapshot mechanism
- Create pause/resume functionality for background jobs
- Add automatic restoration on job completion/failure
- Prevent conflicts with newsletter/mindmap/other jobs

#### 3.3 Intelligent Error Handling
- LLM Inference Error handling (3 retries, then fail)
- Server Connectivity Error handling (3 retries, then terminate worker)
- Data Issue handling (immediate failure)
- Error classification and appropriate retry strategies

### Phase 4: Worker Service & Processing Logic (Week 2-3)
**Estimated Time**: 4-5 days

#### 4.1 Worker Process Architecture
- Multi-process worker launcher
- One worker per Ollama server (concurrency = 1)
- Dynamic load balancing implementation
- Process monitoring and health checks

#### 4.2 Scoring Integration
- Adapt OptimizedOllamaScorer for queue-based processing
- Implement batch score persistence
- Add circuit breaker per server
- Integrate with existing profile scoring logic

#### 4.3 Queue Management
- Task leasing and lease expiration handling
- Progress tracking and checkpoint saving
- Failed task re-queuing logic
- Worker shutdown and cleanup procedures

### Phase 5: Monitoring Dashboard & UI (Week 3-4)
**Estimated Time**: 4-5 days

#### 5.1 Backend Monitoring APIs
- Real-time job status endpoints
- Per-server metrics (processing rates, error rates)
- ETA calculation based on current performance
- Job control APIs (pause, resume, cancel)

#### 5.2 Frontend Dashboard
- Job monitoring page with live updates (every few seconds)
- Per-server performance visualization
- Error rate and processing rate displays
- Pause/resume/cancel controls

#### 5.3 Conflict Prevention
- Job conflict detection and warning system
- Prompts when starting conflicting jobs during bulk operations
- Automatic bulk job pause suggestions

### Phase 6: Testing & Hardening (Week 4)
**Estimated Time**: 3-4 days

#### 6.1 Comprehensive Testing
- Unit tests for all new components
- Integration tests with mock Ollama servers
- End-to-end testing with real workloads
- Performance benchmarking

#### 6.2 Production Readiness
- Error handling edge cases
- Process crash recovery testing
- Long-running job stability testing
- Documentation and deployment guides

### Technical Architecture Decisions

#### Database Strategy
- **New judge_task_queue table**: Clean separation from existing processing_jobs
- **Existing PostgreSQL**: Leverage current infrastructure and connection pooling
- **SKIP LOCKED**: Prevent worker conflicts and ensure fair task distribution
- **Lease-based recovery**: Handle worker crashes gracefully

#### Process Architecture
- **Environment sharing**: Use DATABASE_URL and working directory for worker identification
- **Multi-process workers**: One process per Ollama server for isolation
- **Heartbeat monitoring**: Non-locking status updates for dashboard
- **Graceful shutdown**: Clean worker termination with in-flight task completion

#### Error Handling Strategy
- **LLM Errors**: Retry up to 3 times, then mark failed (data issues)
- **Server Errors**: Retry up to 3 times, then terminate worker (connectivity issues)
- **Circuit Breaker**: Disable problematic servers for job remainder
- **Data Issues**: Immediate failure without retries

#### Monitoring Approach
- **Polling-based**: Refresh every few seconds (simple, reliable)
- **Real-time metrics**: Error rates, processing rates, ETA calculation
- **Job controls**: Pause, resume, cancel with conflict prevention
- **Visual feedback**: Clear status indicators and performance graphs

### Success Metrics

- **Performance**: 2-5x speedup compared to single-server processing
- **Reliability**: <1% job failure rate with intelligent error handling
- **Scalability**: Support for 10-200k papers across multiple servers
- **User Experience**: Real-time monitoring without UI blocking
- **Maintainability**: Clear separation of concerns and modular architecture

### Risks and Mitigations

- DB contention on large queues: mitigate with SKIP LOCKED, proper indexes, batched inserts, and short leases.
- Worker/process crashes: leases and idempotent upserts ensure recovery; progress is reflected in queue and job counters.
- Server lockups: bounded per-request timeout and circuit breaker prevent global stalls; other servers continue to progress.
- Scheduler restoration correctness: snapshot persisted in job state; restoration is idempotent on job exit handlers.

### Architecture Rationale (Scalability & Maintainability)

The DB-backed task queue with one worker per Ollama server achieves natural dynamic load balancing: faster servers complete tasks sooner and therefore pull more work, without central coordination. One-concurrency-per-server satisfies GPU contention constraints. Using short leases and SKIP LOCKED ensures progress despite crashes, and storing state in `processing_jobs` and the queue makes long (>10h) runs robust to restarts and redeploys.

Separating the worker process from the FastAPI service avoids UI-induced stalls and isolates long-running compute. The modular design (servers config, queue producer, worker, and UI dashboard) localizes concerns and supports incremental rollout. Circuit breakers, bounded timeouts, and global retry policies limit blast radius when a server degrades. The system remains maintainable through clear data models, explicit APIs, and observability endpoints.


