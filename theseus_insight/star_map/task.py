"""Async task runner for Profile Star Map recomputation."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from ..api.tasks import task_manager, TaskStatus
from ..data_access.tasks import TaskRepository
from ..data_access.star_map import ProfileStarMapRepository


async def run_profile_star_map_task(task_id: str) -> None:
    """Compute and cache the star map for a given profile.

    Task config expects:
      - profile_id: int
      - limit: int (optional, defaults to 10000)
    """
    try:
        task = await asyncio.to_thread(TaskRepository.get_task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        config: Dict[str, Any] = task.get("config_json") or task.get("config") or {}
        if isinstance(config, str):
            import json

            config = json.loads(config)

        profile_id = int(config.get("profile_id"))
        limit = int(config.get("limit", 10000))

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            f"Starting star map recompute for profile {profile_id}",
            progress=5,
            current_step="starting",
        )

        def progress_cb(step: str, pct: float, msg: str):
            # Runs in worker thread; use sync variant to avoid event-loop starvation.
            task_manager.update_task_status_sync(
                task_id,
                TaskStatus.PROCESSING,
                msg,
                progress=pct,
                current_step=step,
            )

        result = await asyncio.to_thread(
            ProfileStarMapRepository.recompute_profile_star_map,
            profile_id,
            limit=limit,
            progress_cb=progress_cb,
        )

        await task_manager.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            result.get("message", "Star map recompute completed"),
            progress=100,
            current_step="completed",
            result=result,
        )

    except Exception as e:
        await task_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            "Star map recompute failed",
            error=str(e),
            current_step="failed",
        )
        raise

