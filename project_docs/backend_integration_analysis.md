# Backend Integration Analysis for Newsletter UI Overhaul
## Multi-Server Support & WebSocket Data Flow

---

## 🔍 Current Backend Implementation

### WebSocket Progress Updates

**Current Flow:**
1. Newsletter pipeline runs in background task
2. Progress callback updates task manager: `pipeline_progress_callback(stage, progress_val, message)`
3. Task manager broadcasts to WebSocket via `update_task_status()`
4. Frontend receives updates via `useTaskState` hook

**Data Structure Sent to Frontend:**
```typescript
interface RunStatus {
  taskId: string;
  nodes: NodeStatus[];
  overallStatus: TaskStatus;
  currentStep: string;      // e.g., "harvest", "rank", "write", "send"
  progress: number;         // 0-100
  message: string;          // Human-readable status message
  result?: any;
  error?: string;
}
```

**Location:**
- [theseus_insight/api/tasks.py:215-294](../theseus_insight/api/tasks.py#L215)

---

## 📊 Multi-Server Scoring Data Available

### Database Views & Repositories

#### 1. **Overall Job Progress** (`newsletter_scoring_progress` view)

**Available via:** `NewsletterJobRepository.get_job_progress(job_id)`

**Data Structure:**
```python
{
    'newsletter_job_id': UUID,
    'job_status': str,           # 'pending', 'scoring', 'generating', 'completed', 'failed'
    'use_multi_server': bool,
    'scoring_mode': str,
    'papers_to_score': int,      # Total tasks
    'papers_scored': int,        # Completed tasks
    'progress_percentage': float, # Calculated percentage
    'completed_tasks': int,
    'failed_tasks': int,
    'pending_tasks': int,
    'in_progress_tasks': int,
    'avg_task_duration_seconds': float,
    'estimated_time_remaining_seconds': float
}
```

**Location:**
- [theseus_insight/data_access/newsletters.py:287-297](../theseus_insight/data_access/newsletters.py#L287)
- [scripts/011_newsletter_multi_server.sql:110-143](../scripts/011_newsletter_multi_server.sql#L110)

---

#### 2. **Per-Server Statistics** (`newsletter_server_stats` view)

**Available via:** `NewsletterJobRepository.get_job_server_stats(job_id)`

**Data Structure:**
```python
[
    {
        'newsletter_job_id': UUID,
        'assigned_server_url': str,       # e.g., "http://localhost:11434"
        'total_tasks': int,               # Tasks assigned to this server
        'completed_tasks': int,
        'failed_tasks': int,
        'active_tasks': int,              # pending + leased + in_progress
        'avg_task_duration_seconds': float,
        'last_completed_at': datetime
    },
    # ... one entry per server
]
```

**Location:**
- [theseus_insight/data_access/newsletters.py:299-310](../theseus_insight/data_access/newsletters.py#L299)
- [scripts/011_newsletter_multi_server.sql:146-167](../scripts/011_newsletter_multi_server.sql#L146)

---

#### 3. **Progress Monitoring** (during scoring)

**Location:** `NewsletterScorer._monitor_scoring_progress()`

**Current Behavior:**
- Polls every 5 seconds for job progress
- Calls `progress_callback('scoring', progress_pct / 100.0)`
- Has access to:
  - `completed`, `failed`, `pending`, `in_progress` counts
  - Progress percentage

**Location:**
- [theseus_insight/data_processing/newsletter_scorer.py:247-322](../theseus_insight/data_processing/newsletter_scorer.py#L247)

---

## 🎯 What's Working vs What's Missing

### ✅ What We Already Have

1. **Basic Progress Updates**
   - Stage name (`current_step`)
   - Overall progress percentage
   - Status messages

2. **Multi-Server Infrastructure**
   - Database views with detailed stats
   - Repository methods to query data
   - Worker processes per server
   - Task distribution system

3. **WebSocket Broadcast**
   - Task manager broadcasts to all connected clients
   - Real-time updates on progress changes

### ❌ What's Missing for Enhanced UI

1. **Granular Progress Data in WebSocket Messages**
   - Current: Only sends `progress` (0-100) and generic `message`
   - Needed: Structured data with paper counts, server stats, substage info

2. **Per-Server Activity Updates**
   - Current: Server stats exist in DB but not broadcast via WebSocket
   - Needed: Real-time per-server progress updates

3. **Detailed Stage Information**
   - Current: Basic stage name only
   - Needed: Papers discovered count, papers scored count, processing rate

4. **Newsletter Job ID in Task Updates**
   - Current: Task updates don't include newsletter_job_id
   - Needed: To query per-server stats during updates

---

## 🛠️ Recommended Backend Enhancements

### Option 1: **Minimal Changes** (Use Current Infrastructure)

**Approach:** Parse existing messages and poll API for additional data

**Frontend Changes:**
- Extract counts from status messages using regex (e.g., "Scoring papers... (23/47)")
- Add API polling for `get_job_server_stats()` when multi-server mode active
- Calculate stats client-side

**Backend Changes:**
- **None required** - works with existing implementation

**Pros:**
- No backend changes needed
- Can implement immediately
- Low risk

**Cons:**
- Message parsing is fragile
- Extra API calls for server stats
- Not real-time for per-server updates
- Inefficient polling

---

### Option 2: **Enhanced Progress Callback** (Recommended)

**Approach:** Extend the progress callback to include structured metadata

**Changes Required:**

#### 2.1. Update Progress Callback Signature

**File:** `theseus_insight/api/routers/newsletters_and_podcasts.py:133`

**Current:**
```python
def pipeline_progress_callback(stage: str, progress_val: float, message: str):
    # ...
```

**Enhanced:**
```python
def pipeline_progress_callback(
    stage: str,
    progress_val: float,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Enhanced callback with structured metadata.

    metadata example:
    {
        'papers_discovered': 47,
        'papers_to_score': 47,
        'papers_scored': 23,
        'current_paper': 24,
        'newsletter_job_id': 'uuid-here',
        'server_stats': [
            {'server_url': '...', 'completed': 10, 'active': 2},
            ...
        ]
    }
    """
    # Update task with metadata
    async def update_status_async():
        await task_manager.update_task_status(
            task_id,
            overall_status_for_tm,
            message=status_detail,
            progress=progress_val,
            current_step=stage,
            metadata=metadata  # NEW: pass metadata
        )
    # ...
```

---

#### 2.2. Extend TaskManager to Store Metadata

**File:** `theseus_insight/api/tasks.py:215`

**Add metadata field to `update_task_status()`:**
```python
async def update_task_status(
    self,
    task_id: str,
    status: TaskStatus,
    message: str = "",
    progress: float = 0,
    error: str | None = None,
    current_step: str | None = None,
    result: dict | None = None,
    metadata: dict | None = None,  # NEW
) -> None:
```

**Update WebSocket broadcast to include metadata:**
```python
status_obj = RunStatus(
    taskId=task_id,
    nodes=[...],
    overallStatus=status,
    currentStep=current_step,
    progress=final_progress,
    message=message,
    result=result,
    error=error,
    metadata=metadata  # NEW
)
```

---

#### 2.3. Update NewsletterScorer to Send Metadata

**File:** `theseus_insight/data_processing/newsletter_scorer.py:247`

**In `_monitor_scoring_progress()`:**
```python
async def _monitor_scoring_progress(
    self,
    job_id: UUID,
    total_tasks: int,
    progress_callback: Optional[Callable[[str, float, str, Optional[Dict]], None]] = None,
    poll_interval_sec: int = 5
):
    # ... existing code ...

    while iteration < max_iterations:
        # Get progress
        progress = JudgeTaskQueueRepository.get_job_progress(job_id)

        # Get per-server stats
        server_stats = NewsletterJobRepository.get_job_server_stats(job_id)

        # Format server stats for frontend
        formatted_server_stats = [
            {
                'server_url': stat['assigned_server_url'],
                'completed': stat['completed_tasks'],
                'failed': stat['failed_tasks'],
                'active': stat['active_tasks'],
                'avg_duration': stat['avg_task_duration_seconds']
            }
            for stat in server_stats
        ]

        # Build metadata
        metadata = {
            'newsletter_job_id': str(job_id),
            'papers_to_score': total_tasks,
            'papers_scored': progress.get('completed_tasks', 0),
            'papers_failed': progress.get('failed_tasks', 0),
            'papers_pending': progress.get('pending_tasks', 0),
            'papers_in_progress': progress.get('in_progress_tasks', 0),
            'server_stats': formatted_server_stats,
            'avg_task_duration': progress.get('avg_task_duration_seconds'),
            'estimated_time_remaining': progress.get('estimated_time_remaining_seconds')
        }

        # Call progress callback with metadata
        if progress_callback:
            progress_callback('scoring', progress_pct / 100.0, message, metadata)

        # ...
```

---

#### 2.4. Update TheseusInsight to Pass Metadata for Other Stages

**File:** `theseus_insight/theseus_insight.py`

**In harvest stage:**
```python
# After harvesting papers
metadata = {
    'papers_discovered': len(all_filtered_papers),
    'date_range_start': self.start_date,
    'date_range_end': self.end_date
}
if progress_callback:
    progress_callback('harvest', 100.0, f"Discovered {len(all_filtered_papers)} papers", metadata)
```

**In ranking stage (single-server mode):**
```python
# During sequential scoring
for idx, paper in enumerate(papers):
    # ... score paper ...
    metadata = {
        'papers_to_score': total_papers,
        'papers_scored': idx + 1,
        'current_paper_title': paper.get('title', 'Unknown')
    }
    if progress_callback:
        progress_callback('rank', (idx + 1) / total_papers * 100,
                         f"Scoring paper {idx + 1}/{total_papers}", metadata)
```

---

#### 2.5. Update Frontend Types

**File:** `theseus-ui/src/services/api.ts`

```typescript
export interface TaskState {
  taskId: string;
  isRunning: boolean;
  stage: string;
  progress: number;
  message: string;
  error?: string;
  metadata?: {
    papers_discovered?: number;
    papers_to_score?: number;
    papers_scored?: number;
    papers_failed?: number;
    papers_pending?: number;
    papers_in_progress?: number;
    current_paper_title?: string;
    newsletter_job_id?: string;
    server_stats?: ServerStats[];
    avg_task_duration?: number;
    estimated_time_remaining?: number;
  };
}

export interface ServerStats {
  server_url: string;
  completed: number;
  failed: number;
  active: number;
  avg_duration: number;
}
```

---

### Option 3: **REST API Endpoints** (Alternative)

**Approach:** Create dedicated API endpoints for enhanced progress queries

**New Endpoints:**

```python
# theseus_insight/api/routers/newsletters_and_podcasts.py

@router.get("/api/newsletter/job/{job_id}/progress")
async def get_newsletter_job_progress(job_id: str):
    """Get detailed progress for a newsletter job."""
    from uuid import UUID
    from ...data_access.newsletters import NewsletterJobRepository

    job_uuid = UUID(job_id)
    progress = NewsletterJobRepository.get_job_progress(job_uuid)
    server_stats = NewsletterJobRepository.get_job_server_stats(job_uuid)

    return {
        'job_id': job_id,
        'progress': progress,
        'server_stats': server_stats
    }

@router.get("/api/tasks/{task_id}/metadata")
async def get_task_metadata(task_id: str):
    """Get enhanced metadata for a task including newsletter job info."""
    task = TaskRepository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Extract newsletter_job_id from task config if available
    config = task.get('config', {})
    newsletter_job_id = config.get('newsletter_job_id')

    metadata = {}
    if newsletter_job_id:
        progress = NewsletterJobRepository.get_job_progress(UUID(newsletter_job_id))
        server_stats = NewsletterJobRepository.get_job_server_stats(UUID(newsletter_job_id))
        metadata = {
            'newsletter_progress': progress,
            'server_stats': server_stats
        }

    return {
        'task_id': task_id,
        'metadata': metadata
    }
```

**Frontend Changes:**
- Poll these endpoints every 2-5 seconds during multi-server scoring
- Combine with WebSocket updates for complete picture

**Pros:**
- Clean separation of concerns
- Flexible querying
- No changes to WebSocket structure

**Cons:**
- Requires polling (not truly real-time)
- Extra HTTP requests
- More complex state management in frontend

---

## 📋 Recommendation Summary

### **Recommended Approach: Option 2 (Enhanced Progress Callback)**

**Why:**
1. **Truly Real-Time** - Metadata flows through existing WebSocket infrastructure
2. **Minimal Refactoring** - Extends existing callback pattern
3. **Structured Data** - Eliminates fragile message parsing
4. **Scalable** - Easy to add more metadata fields in future
5. **Efficient** - No extra API calls or polling needed

**Implementation Effort:**
- **Backend:** ~3-4 hours (update callback, task manager, scorer, theseus_insight)
- **Frontend Types:** ~30 minutes (update TypeScript interfaces)
- **Testing:** 1-2 hours

**Total:** ~5-7 hours

---

## 🚀 Implementation Priority

### Phase 1: Essential Backend Changes (Option 2)
1. ✅ Add `metadata` parameter to `pipeline_progress_callback`
2. ✅ Update `TaskManager.update_task_status()` to accept and broadcast metadata
3. ✅ Update `NewsletterScorer._monitor_scoring_progress()` to send server stats
4. ✅ Update frontend TypeScript types

### Phase 2: Enhanced Metadata for All Stages
5. Add paper discovery counts in harvest stage
6. Add paper scoring progress in rank stage (single-server)
7. Add writer stage metadata (sections completed, word count, etc.)
8. Add email sending progress

### Phase 3: Optional REST API (Option 3)
9. Add `/api/newsletter/job/{job_id}/progress` endpoint as backup
10. Add `/api/tasks/{task_id}/metadata` endpoint for on-demand queries

---

## 🧪 Testing Checklist

After implementing backend changes:

- [ ] WebSocket broadcasts include metadata during multi-server scoring
- [ ] Per-server stats update in real-time (every 5 seconds)
- [ ] Paper counts accurate (discovered, scored, pending)
- [ ] Single-server mode still works (metadata optional)
- [ ] Error states handled gracefully (no metadata if job_id unavailable)
- [ ] Multiple concurrent newsletter runs don't interfere
- [ ] WebSocket reconnection preserves progress display
- [ ] Task history shows metadata in database

---

## 🔄 Backward Compatibility

**Existing Behavior Preserved:**
- Progress callback signature extended with optional `metadata` parameter
- Old callers without metadata continue to work
- Frontend gracefully handles missing metadata fields
- No breaking changes to WebSocket message format (metadata is additional field)

---

## 💡 Future Enhancements

Once metadata infrastructure is in place:

1. **Processing Rate Metrics**
   - Papers/second throughput
   - Real-time performance graphs

2. **Worker Health Monitoring**
   - Track which workers are active/idle
   - Worker failure detection
   - Auto-scaling signals

3. **Cost Estimation**
   - Token usage tracking
   - Time-based cost estimates

4. **Historical Analytics**
   - Compare current run to previous runs
   - Performance trends over time

5. **Predictive Completion**
   - More accurate ETA based on current rate
   - Variance calculations

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Newsletter Pipeline                      │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│  │ Harvest  │ -> │  Scorer  │ -> │  Writer  │ -> ...      │
│  └──────────┘    └──────────┘    └──────────┘            │
│       │               │                                     │
└───────┼───────────────┼─────────────────────────────────────┘
        │               │
        │               │ _monitor_scoring_progress()
        │               │ (polls every 5s)
        │               ├─> get_job_progress(job_id)
        │               ├─> get_job_server_stats(job_id)
        │               │
        ▼               ▼
   progress_callback(stage, progress, message, metadata)
        │
        │
        ▼
   TaskManager.update_task_status(
       task_id, status, message, progress, metadata
   )
        │
        │
        ▼
   WebSocket Broadcast
   {
       taskId, status, progress, message,
       metadata: {
           papers_discovered, papers_scored,
           server_stats: [{server_url, completed, active}, ...]
       }
   }
        │
        │
        ▼
   ┌─────────────────────────────────────┐
   │         Frontend (React)            │
   │                                     │
   │  useTaskState() hook                │
   │    ├─> taskState.metadata           │
   │    ├─> taskState.progress           │
   │    └─> taskState.stage              │
   │                                     │
   │  NewsletterPipeline Component       │
   │    ├─> StatsGrid (uses metadata)    │
   │    └─> ServerActivityIndicator      │
   │        (uses metadata.server_stats) │
   └─────────────────────────────────────┘
```

---

## ✅ Conclusion

**Answer to your question:**

> Are you aware if we also need any backend callback changes?

**Yes, backend changes are recommended** to fully support the enhanced UI with multi-server visualization:

1. **Essential Changes** (Option 2):
   - Extend progress callback to include `metadata` parameter
   - Update `TaskManager.update_task_status()` to broadcast metadata
   - Update `NewsletterScorer` to query and send server stats in metadata
   - Update frontend TypeScript types

2. **Alternative** (Option 1):
   - No backend changes, but requires fragile message parsing and polling

3. **Hybrid** (Option 2 + 3):
   - Implement Option 2 for real-time updates
   - Add REST endpoints for on-demand detailed queries

**The current backend has all the data we need** (via database views and repositories), but it's not being sent through the WebSocket pipeline. The recommended Option 2 changes are straightforward and will enable a much richer, real-time UI experience.

---

**Next Steps:**
1. Review this analysis
2. Approve Option 2 approach
3. I can implement the backend changes
4. Update frontend components to consume metadata
5. Test with actual multi-server newsletter run

Let me know if you'd like me to proceed with implementing Option 2!
