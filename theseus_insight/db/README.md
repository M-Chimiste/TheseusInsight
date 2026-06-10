# Database access policy

Two pools exist in this package. The split is deliberate — do not merge
them, and do not add new asyncpg call sites.

## Sync psycopg pool — canonical (`get_cursor` / `get_connection`)

All ~34 repositories in `data_access/` use the pooled sync psycopg layer
via the module-level `get_cursor()` context manager. This is the single
canonical way to touch the database. New queries belong in a repository
using this layer.

**From async code** (FastAPI endpoints, task handlers): calling a sync
repository directly blocks the event loop for the duration of the query.
Wrap the call with `async_bridge.run_repo`:

```python
from ...db.async_bridge import run_repo

rows = await run_repo(PaperRepository.get_paginated, page=page)
```

Short single-row lookups are tolerable inline; anything that scans
papers/topics or runs the trends CTEs should go through the bridge.

## asyncpg pool — confined island (`get_connection_pool`)

Used only by the checkpoint/jobs subsystem:
`data_processing/checkpoint_manager.py`, `api/routers/jobs.py`,
`utils/backfill_keywords.py`. The `CheckpointManager` semantics are
load-bearing for resumable pipeline runs, so this island is wrapped,
never migrated. Do not add new users.

## Why not migrate everything to asyncpg?

Evaluated and rejected during the 2026-06 refactor: it would mean
rewriting every query (`%s` → `$1`), losing dict_row, and breaking every
sync caller (workers, harvest scripts, pipelines) — with zero duplicated
SQL between the layers today, there is no consolidation payoff to buy
that risk.
