"""Bridge for calling sync (psycopg) repositories from async endpoints.

Policy (see README.md in this package): the sync psycopg pool is the
single canonical data-access layer; asyncpg stays confined to the
checkpoint/jobs subsystem. Async endpoints that call repositories
directly block the event loop for the duration of the query — wrap the
call in run_repo() to move it to a worker thread instead.

    papers = await run_repo(PaperRepository.get_paginated, page=1)

psycopg's ConnectionPool is thread-safe, so concurrent run_repo calls
are fine; they draw from the same pool as sync callers.
"""
import asyncio
from typing import Any, Callable, TypeVar

T = TypeVar("T")


async def run_repo(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """Run a sync repository call in a worker thread and await the result."""
    return await asyncio.to_thread(fn, *args, **kwargs)
