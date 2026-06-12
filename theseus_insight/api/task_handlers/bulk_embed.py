"""Task handler(s) extracted from TaskManager (refactor B6): run_bulk_embed_task."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, List
import asyncio
import json
import os
from datetime import datetime

from ..tasks import TaskStatus
from ...data_access import (
    TaskRepository, LogsRepository, SettingsRepository,
    PaperRepository, PaperFulltextRepository
)
from ._common import get_orchestration_config, progress_callback
from ...theseus_insight import TheseusInsight

if TYPE_CHECKING:
    from ..tasks import TaskManager


async def run(task_manager: "TaskManager", task_id: str):
    """
    Run a bulk embedding task that downloads and embeds papers without profile scoring.

    This task:
    1. Downloads papers from ArXiv based on date range
    2. Embeds all paper abstracts without filtering
    3. Stores embedded papers in the database
    4. Does NOT perform any profile-specific scoring
    """
    try:
        # Get task configuration
        task = TaskRepository.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Debug: Check if config is in JSON format
        print(f"[DEBUG] Raw task data: {task}")
        config_json_value = task.get("config_json")
        print(f"[DEBUG] config_json value: {config_json_value} (type: {type(config_json_value)})")

        if isinstance(config_json_value, str):
            config = json.loads(config_json_value)
            print(f"[DEBUG] Parsed config from JSON string: {config}")
        elif isinstance(config_json_value, dict):
            config = config_json_value
            print(f"[DEBUG] Using config_json as dict: {config}")
        else:
            config = task.get("config", {})
            print(f"[DEBUG] Fallback to config field: {config}")

        start_date = config.get("start_date")
        end_date = config.get("end_date")
        batch_size = config.get("batch_size", 100)
        skip_existing = config.get("skip_existing", True)
        arxiv_categories = config.get("arxiv_categories", None)

        print(f"[DEBUG] Extracted from config - arxiv_categories: {arxiv_categories}")

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            f"Starting bulk embedding from {start_date} to {end_date}",
            progress=5,
            current_step="initialization",
        )

        # Check for existing papers if skip_existing is enabled
        if skip_existing:
            from ...data_access.papers import PaperRepository
            existing_papers = PaperRepository.get_papers_in_date_range(start_date, end_date)
            existing_count = len(existing_papers)
            embedded_count = sum(1 for p in existing_papers if p.get('embedding_model') is not None)

            await task_manager.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Found {existing_count} existing papers ({embedded_count} with embeddings)",
                progress=10,
                current_step="checking_existing",
            )

        # Create progress callback for pipeline
        def pipeline_progress_callback(stage: str, progress: float, message: str = ""):
            # Convert pipeline progress to task progress (10% - 90%)
            task_progress = 10 + (progress * 0.8)

            # Use sync version of update_task_status to avoid event loop issues
            task_manager.update_task_status_sync(
                task_id,
                TaskStatus.PROCESSING,
                f"Embedding: {stage} - {message}",
                progress=task_progress,
                current_step=f"embedding_{stage}",
            )

        # Get orchestration config with proper fallback hierarchy: DB -> config file -> defaults  
        orchestration_config = get_orchestration_config()

        # Debug: Always print what we received
        print(f"[DEBUG] Task handler received arxiv_categories: {arxiv_categories} (type: {type(arxiv_categories)})")
        print(f"[DEBUG] Current orchestration_config: {orchestration_config.get('arxiv_search_categories', 'NOT SET')}")

        # Override arxiv categories if provided
        if arxiv_categories is not None:
            print(f"[DEBUG] Processing arxiv_categories: {arxiv_categories}")
            if 'arxiv_search_categories' not in orchestration_config:
                orchestration_config['arxiv_search_categories'] = {}

            # Check for special "ALL" flag
            if arxiv_categories and len(arxiv_categories) > 0 and arxiv_categories[0] == 'ALL':
                orchestration_config['arxiv_search_categories']['filter_categories'] = None
                orchestration_config['arxiv_search_categories']['main_category'] = None
                print("[DEBUG] Setting categories to None for ALL papers")
            elif len(arxiv_categories) == 0:
                # Empty array - use defaults (shouldn't happen with new UI)
                print("[DEBUG] Empty array - using defaults")
            else:
                orchestration_config['arxiv_search_categories']['filter_categories'] = arxiv_categories
                # If main category is provided, use the prefix
                main_cat = arxiv_categories[0].split('.')[0]
                orchestration_config['arxiv_search_categories']['main_category'] = main_cat
                print(f"[DEBUG] Setting specific categories: {arxiv_categories}")
        else:
            print("[DEBUG] arxiv_categories is None - using existing config")

        print(f"[DEBUG] Final orchestration_config: {orchestration_config.get('arxiv_search_categories', 'NOT SET')}")

        # Run embedding-only pipeline
        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            "Starting paper download and embedding",
            progress=15,
            current_step="embedding_start",
        )

        theseus_insight = TheseusInsight(
            start_date_override=start_date,
            end_date_override=end_date,
            db_saving=True,
            verbose=True,
            orchestration_config=orchestration_config,
            task_id=task_id,
            generate_email=False  # Bulk operations should not send newsletters
        )

        # Set additional attributes after instantiation
        theseus_insight.batch_size = batch_size
        theseus_insight.skip_existing = skip_existing

        # Run the embedding-only pipeline
        # Use asyncio.to_thread to avoid blocking the event loop during embedding
        result = await asyncio.to_thread(
            theseus_insight.run_embedding_only_pipeline,
            progress_callback=pipeline_progress_callback
        )

        papers_saved = result.get('saved_count', 0)
        papers_skipped = result.get('skipped_count', 0)
        papers_embedded = result.get('embedded_count', 0)

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            f"Embedding completed: {papers_embedded} papers embedded, {papers_saved} new papers saved",
            progress=95,
            current_step="finalization",
        )

        # Prepare final result
        final_result = {
            "papers_saved": papers_saved,
            "papers_embedded": papers_embedded,
            "papers_skipped": papers_skipped,
            "start_date": start_date,
            "end_date": end_date,
            "batch_size": batch_size,
            "skip_existing": skip_existing,
            "status": "success"
        }

        await task_manager.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            f"Bulk embedding completed successfully. {papers_embedded} papers embedded.",
            result=final_result,
            progress=100,
            current_step="completed",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        await task_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            f"Bulk embedding task failed: {str(e)}",
            error=str(e),
            current_step="task_failed",
        )
        raise
