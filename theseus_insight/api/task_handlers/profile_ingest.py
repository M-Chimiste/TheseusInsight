"""Task handler(s) extracted from TaskManager (refactor B6): run_profile_aware_ingest_task."""
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
    """Run profile-aware paper ingestion task."""
    try:
        print(f"DEBUG: Starting profile-aware ingestion task {task_id}")
        task = TaskRepository.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if isinstance(task["config_json"], str):
            config = json.loads(task["config_json"])
        else:
            config = task["config_json"]

        # Extract configuration parameters
        start_date = config.get("start_date")
        end_date = config.get("end_date")
        profile_ids = config.get("profile_ids", [])
        profile_tags = config.get("profile_tags", [])
        score_all_profiles = config.get("score_all_profiles", False)
        overwrite_existing = config.get("overwrite_existing", False)
        cosine_threshold = config.get("cosine_threshold", 0.5)
        arxiv_categories = config.get("arxiv_categories", [])
        batch_size = config.get("batch_size", 10)
        send_error_notifications = config.get("send_error_notifications", False)

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            "Starting profile-aware paper ingestion",
            progress=5,
            current_step="initializing",
        )

        # Resolve target profiles
        from ..data_access.profiles import ProfileRepository
        target_profiles = []

        if profile_ids:
            for profile_id in profile_ids:
                profile = ProfileRepository.get_by_id(profile_id)
                if profile and profile['is_active']:
                    target_profiles.append(profile)

        if profile_tags:
            tag_profiles = ProfileRepository.get_by_tags(profile_tags)
            for profile in tag_profiles:
                if profile['is_active'] and profile not in target_profiles:
                    target_profiles.append(profile)

        if score_all_profiles and not target_profiles:
            target_profiles = ProfileRepository.get_all_active()

        if not target_profiles:
            raise ValueError("No active profiles found matching the criteria")

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            f"Resolved {len(target_profiles)} target profiles",
            progress=10,
            current_step="profiles_resolved",
        )

        # Stage 1: Run paper ingestion pipeline
        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            "Running paper ingestion pipeline",
            progress=15,
            current_step="ingestion_start",
        )

        # Get existing paper IDs before ingestion to track what's new
        from ..data_access.papers import PaperRepository
        existing_paper_ids = set(PaperRepository.get_paper_ids_in_date_range(start_date, end_date))

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            f"Found {len(existing_paper_ids)} existing papers in date range",
            progress=12,
            current_step="existing_papers_checked",
        )

        # Create progress callback for pipeline
        def pipeline_progress_callback(stage: str, progress: float, message: str = ""):
            # Convert pipeline progress to task progress (15% - 60%)
            task_progress = 15 + (progress * 0.45)

            # Use sync version of update_task_status to avoid event loop issues
            task_manager.update_task_status_sync(
                task_id,
                TaskStatus.PROCESSING,
                f"Ingestion: {stage} - {message}",
                progress=task_progress,
                current_step=f"ingestion_{stage}",
            )

        # Get orchestration config with proper fallback hierarchy: DB -> config file -> defaults
        orchestration_config = get_orchestration_config(verbose=True)

        # Update ArXiv categories if specified
        if arxiv_categories:
            if 'arxiv_search_categories' not in orchestration_config:
                orchestration_config['arxiv_search_categories'] = {}
            orchestration_config['arxiv_search_categories']['filter_categories'] = arxiv_categories

        # Run profile-aware ingestion pipeline
        theseus_insight = TheseusInsight(
            start_date_override=start_date,
            end_date_override=end_date,
            cosine_similarity_threshold=cosine_threshold,
            db_saving=True,
            verbose=True,
            orchestration_config=orchestration_config,
            task_id=task_id,
            send_error_notifications=send_error_notifications,
            generate_email=False  # Bulk operations should not send newsletters
        )

        # Run the profiles pipeline (stores all papers without scoring)
        # Use asyncio.to_thread to avoid blocking the event loop during embedding
        ingestion_result = await asyncio.to_thread(
            theseus_insight.run_profiles_pipeline,
            progress_callback=pipeline_progress_callback
        )

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            f"Ingestion completed: {ingestion_result.get('saved_count', 0)} papers saved",
            progress=60,
            current_step="ingestion_complete",
        )

        # Get new paper IDs after ingestion
        all_paper_ids_after = set(PaperRepository.get_paper_ids_in_date_range(start_date, end_date))
        new_paper_ids = list(all_paper_ids_after - existing_paper_ids)

        # If overwrite_existing is True, score all papers, not just new ones
        papers_to_score_ids = None if overwrite_existing else new_paper_ids

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            f"Identified {len(new_paper_ids)} new papers, will score {len(papers_to_score_ids) if papers_to_score_ids else 'all'} papers",
            progress=62,
            current_step="new_papers_identified",
        )

        # Stage 2: Run profile-aware scoring
        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            "Starting profile-aware scoring",
            progress=65,
            current_step="scoring_start",
        )

        # Create bulk judge runner
        judge_config = orchestration_config.get("judge_model", {})

        # Get embedding model for optimizations if available
        embedding_model = None
        embedding_config = orchestration_config.get("embedding_model", {})
        if embedding_config:
            try:
                from LLMFactory import LLMModelFactory
                # Normalize model_type: handle both "sentence-transformers" and "sentence-transformer"
                embedding_model_type = embedding_config.get("model_type", "sentence-transformer")
                if embedding_model_type == "sentence-transformers":
                    embedding_model_type = "sentence-transformer"

                embedding_model = LLMModelFactory.create_model(
                    model_type=embedding_model_type,
                    model_name=embedding_config.get("model_name", "Alibaba-NLP/gte-large-en-v1.5"),
                    **{k: v for k, v in embedding_config.items() if k not in ["model_type", "model_name"]}
                )
            except Exception as e:
                print(f"Warning: Could not load embedding model for optimizations: {e}")

        from ..data_access.bulk_judge import BulkJudgeRunner
        bulk_judge = BulkJudgeRunner(
            judge_config, 
            verbose=True,
            use_optimized_scorer=True,
            embedding_model=embedding_model
        )

        # Create bulk judge request
        from ..api.models import BulkJudgeRunRequest
        judge_request = BulkJudgeRunRequest(
            profile_ids=profile_ids if profile_ids else None,
            profile_tags=profile_tags if profile_tags else None,
            date_from=start_date,
            date_to=end_date,
            batch_size=batch_size,
            overwrite_existing=overwrite_existing,
            paper_ids=papers_to_score_ids  # Only score new papers unless overwrite_existing
        )

        # Scoring progress callback
        def scoring_progress_callback(stage: str, current: int, total: int):
            # Convert scoring progress to task progress (65% - 95%)
            scoring_progress = (current / total) * 100 if total > 0 else 0
            task_progress = 65 + (scoring_progress * 0.30)

            # Use sync version of update_task_status to avoid event loop issues
            task_manager.update_task_status_sync(
                task_id,
                TaskStatus.PROCESSING,
                f"Scoring: {stage} ({current}/{total})",
                progress=task_progress,
                current_step=f"scoring_{stage}",
            )

        # Run bulk judge scoring
        judge_result = await bulk_judge.run_bulk_judge(
            judge_request,
            progress_callback=scoring_progress_callback
        )

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            "Profile-aware scoring completed",
            progress=95,
            current_step="scoring_complete",
        )

        # Create final result
        final_result = {
            "ingestion_result": ingestion_result,
            "scoring_result": {
                "job_id": judge_result.job_id,
                "status": judge_result.status,
                "profile_count": judge_result.profile_count,
                "estimated_papers": judge_result.estimated_papers,
                "message": judge_result.message
            },
            "target_profiles": [p['name'] for p in target_profiles],
            "papers_ingested": ingestion_result.get('saved_count', 0),
            "papers_scored": judge_result.estimated_papers
        }

        await task_manager.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            f"Profile-aware ingestion completed: {ingestion_result.get('saved_count', 0)} papers ingested, {judge_result.profile_count} profiles scored",
            progress=100,
            current_step="task_complete",
            result=final_result,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        await task_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            f"Profile-aware ingestion task failed: {str(e)}",
            error=str(e),
            current_step="task_failed",
        )
        raise
