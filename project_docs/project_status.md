# Project Status

## Implemented Features
- [x] Newsletter pipeline bug fix: 'dict' object has no attribute 'id' in checkpoint manager/data processing.
- [x] Newsletter pipeline bug fix: `cannot adapt type 'InferenceServer'` in multi-server scoring.
- [x] Newsletter pipeline bug fix: `AttributeError: 'TheseusInsight' object has no attribute 'progress_callback'`.
- [x] Newsletter pipeline bug fix: Progress percentage calculation > 100% and missing UI metadata.
- [x] Newsletter pipeline bug fix: KeyError 'active' in server stats monitoring.
- [x] Newsletter pipeline improvement: Changed from pre-assigned round-robin to dynamic queue-based task distribution.
- [x] UI improvement: Changed server activity display from progress bars to throughput metrics.

## Next Steps
- [ ] Refactor `theseus_insight/theseus_insight.py` to split the large file into smaller modules.
- [ ] Verify newsletter pipeline execution with new queue-based distribution.
- [ ] Consider adding real-time server health monitoring.

## Debug Log
### 2025-11-20 - Fix AttributeError in Newsletter Pipeline
- **Issue**: `AttributeError: 'dict' object has no attribute 'id'` when saving papers to DB.
- **Cause**: `PaperRepository.get_by_url` returns a dictionary, but the code was accessing it as an object (`existing_paper.id`).
- **Fix**: Changed `existing_paper.id` to `existing_paper['id']` in `theseus_insight/theseus_insight.py`. Also fixed another occurrence in `Saving LLM judge scores` section.

### 2025-11-20 - Fix Multi-Server Scoring Type Error
- **Issue**: `psycopg.ProgrammingError: cannot adapt type 'InferenceServer'` in multi-server scoring.
- **Cause**: Passing `InferenceServer` objects instead of their IDs to the TheseusInsight constructor.
- **Fix**: Changed to extract IDs from server objects: `judge_server_ids=[s.id for s in judge_servers] if judge_servers else None`.

### 2025-11-21 - Fix Progress Callback and UI Metadata
- **Issue**: Progress callback not initialized, UI not receiving metadata.
- **Cause**: TheseusInsight not storing progress_callback in __init__, callback signature mismatch.
- **Fix**: Added progress_callback to __init__, updated run() to store callback, fixed callback signatures.

### 2025-11-21 - Fix Server Stats KeyError
- **Issue**: `Error monitoring progress... 'active'` in newsletter scoring.
- **Cause**: Code was accessing `server_stat['active']` but the view column is named `active_tasks`.
- **Fix**: Updated to use `stat.get('active_tasks', 0)` in newsletter_scorer.py.

### 2025-11-21 - Improve Task Distribution Architecture
- **Issue**: Tasks were pre-assigned to servers using round-robin, causing uneven distribution.
- **Changes**:
  1. Removed server_urls parameter from task enqueueing - all tasks go to general queue
  2. Workers now pull tasks dynamically on a first-come-first-serve basis
  3. Updated UI to show throughput (papers/min) instead of progress bars
  4. Added server status indicators and real-time metrics
- **Benefits**: Better load balancing, more efficient use of faster servers, clearer performance visibility.

### 2025-11-21 - Fix Scoring Progress Reset & Metadata Regression
- **Issue**: When the scoring stage started, total progress snapped back to 0% and the dashboard cards reverted to zero values.
- **Cause**: The multi-server callback emitted raw 0-100 scoring percentages under a new `scoring` stage label, so task progress overwrote the global pipeline progress. Subsequent metadata frames also lacked `papers_discovered`, so the UI lost previously discovered counts.
- **Fix**: Scaled scoring progress into the existing 20-30% rank window, normalized the stage label back to `rank`, and enriched every progress frame with `papers_discovered`, `profile_count`, and the raw scoring percentage for debugging. Updated the UI to treat `scoring` as part of the Rank stage so the stage cards remain in order.

### 2025-11-21 - Fix Pending/Scored Dashboard Counters
- **Issue**: The stats cards stayed at `Pending=1840` / `Scored=0` even while the queue reported progress.
- **Cause**: The UI only displayed raw `papers_pending`/`papers_scored` fields, so any missing or delayed metadata kept the cards stuck at their initial values.
- **Fix**: Added defensive derivations on the front-end so `Scored`/`Pending` can be computed from any combination of `papers_to_score`, `papers_pending`, `papers_in_progress`, and `papers_failed`. Pending now reflects both pending and in-progress work, so the card tracks real outstanding work even if the backend omits one of the counters.

### 2025-11-21 - Derive Stats From Per-Server Data
- **Issue**: Even after enabling richer metadata, the dashboard cards still lagged because `papers_scored` and `papers_failed` only update when the global queue snapshot refreshes.
- **Fix**: The UI now falls back to summing the per-server `completed`, `failed`, and `in_progress` values that arrive with every progress callback. This keeps the “Scored” and “Pending” cards in sync with the multi-server activity bars, even if the queue view is momentarily stale.

### 2025-11-21 - Send Dedicated Scoring Summary Metadata
- **Issue**: Server stats aggregation still depended on per-server payloads, so card counts didn’t move until throughput data was available.
- **Fix**: The backend now bundles a `scoring_summary` block inside every progress callback (`completed`, `failed`, `pending`, `in_progress`, `total`). The UI prefers these authoritative totals and only falls back to server aggregates if the summary is missing, so the Papers Scored / Pending cards advance with each queue poll.

## Analysis & Reflections

The newsletter scoring system has evolved from a simple round-robin distribution to a more sophisticated queue-based architecture. This change addresses the fundamental issue where pre-assigning tasks to servers could lead to inefficiencies - slower servers would accumulate backlogs while faster servers sat idle.

The shift to throughput-based UI metrics provides better operational visibility. Progress bars were misleading when servers process at different rates. The new metrics (papers/minute, average latency, active status) give operators real-time insight into server performance and help identify bottlenecks.

### Future Improvements
1. **Health Monitoring**: Add periodic health checks for inference servers to detect failures early
2. **Smart Routing**: Consider implementing affinity-based routing where certain paper types go to specialized servers
3. **Autoscaling**: Monitor queue depth and automatically scale workers based on load
4. **Metrics Dashboard**: Create a dedicated monitoring dashboard with historical performance data