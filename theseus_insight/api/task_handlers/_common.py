"""Shared helpers for task handlers (extracted from TaskManager, B6)."""
from __future__ import annotations

from typing import TYPE_CHECKING
import asyncio
import json

from ...data_access import SettingsRepository
from ..tasks import TaskStatus

if TYPE_CHECKING:
    from ..tasks import TaskManager


def progress_callback(task_manager: "TaskManager", task_id: str):
    """Create a progress callback function for TheseusInsight."""
    loop = asyncio.get_event_loop()

    def callback(stage: str, progress: float, message: str = ""):
        coro = task_manager.update_task_status(
            task_id=task_id,
            status=TaskStatus.PROCESSING,
            message=f"{stage}: {message}",
            progress=progress,
            current_step=stage
        )
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, loop)
        else:
            # This case might occur if the main loop is stopped or not accessible.
            # For robustness, you could log this or handle it differently.
            # For now, we attempt to run it in a new loop, though this has implications.
            try:
                asyncio.run(coro) # Fallback, but be cautious with this approach.
            except RuntimeError as e:
                print(f"RuntimeError in progress_callback fallback: {e}. Status update for '{stage}' might be lost.")
    return callback


def get_orchestration_config(verbose: bool = False) -> dict:
    """
    Get orchestration config with proper fallback hierarchy: DB -> config file -> defaults.

    Args:
        verbose: Whether to print debug information about config source

    Returns:
        Dictionary containing orchestration configuration
    """
    orchestration_json = SettingsRepository.get("orchestration")
    if orchestration_json:
        orchestration_config = json.loads(orchestration_json)
        if verbose:
            print("📊 Using orchestration config from database settings")
        return orchestration_config
    else:
        # Fallback to config file
        try:
            from pathlib import Path
            # parents[3]: this file sits one level deeper than tasks.py did
            config_path = Path(__file__).resolve().parents[3] / "config" / "orchestration.json"
            orchestration_config = json.loads(config_path.read_text())
            if verbose:
                print("📊 Using orchestration config from config file")
            return orchestration_config
        except Exception as e:
            print(f"Warning: Could not load orchestration config from file: {e}")
            if verbose:
                print("📊 Using empty orchestration config (defaults only)")
            return {}
