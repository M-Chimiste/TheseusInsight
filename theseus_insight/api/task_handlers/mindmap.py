"""Task handler(s) extracted from TaskManager (refactor B6): run_mindmap_expand_task, run_mindmap_pdf_parse_task."""
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

if TYPE_CHECKING:
    from ..tasks import TaskManager


async def run_expand(task_manager: "TaskManager", task_id: str):
    """Run the mind-map expansion task."""
    try:
        print(f"DEBUG: Starting mind-map expansion task {task_id}")
        task = TaskRepository.get_task(task_id)
        if not task:
            print(f"DEBUG: Task {task_id} not found in database")
            raise ValueError(f"Task {task_id} not found")

        print(f"DEBUG: Task found: {task}")
        print(f"DEBUG: config_json type: {type(task['config_json'])}")
        print(f"DEBUG: config_json value: {task['config_json']}")
        if isinstance(task["config_json"], str):
            config = json.loads(task["config_json"])
        else:
            config = task["config_json"]
        paper_id = config.get("paper_id")
        topic_id = config.get("topic_id")  # Extract topic_id for auto-save functionality
        k = config.get("k", 15)
        similarity_threshold = config.get("similarity_threshold", 0.3)
        expansion_order = config.get("expansion_order", 1)
        max_nodes_per_order = config.get("max_nodes_per_order", 20)
        layout_algorithm = config.get("layout_algorithm", "force")
        model_config_override = config.get("model_config_override")
        # Profile filtering parameters
        profile_id = config.get("profile_id")
        profile_ids = config.get("profile_ids")
        profile_tag = config.get("profile_tag")
        profile_tags = config.get("profile_tags")

        print(f"DEBUG: Task config - paper_id: {paper_id}, k: {k}, threshold: {similarity_threshold}, expansion_order: {expansion_order}, max_nodes_per_order: {max_nodes_per_order}")

        if not paper_id:
            print(f"DEBUG: No paper_id provided in config")
            raise ValueError("Paper ID is required for mind-map expansion")

        # Import the mind-map workflow
        from ...mindmap.workflow import create_mindmap_workflow

        # Get configuration from database or fallback file
        orchestration_json = SettingsRepository.get("orchestration")
        if orchestration_json:
            print("DEBUG: Loaded orchestration config from DB settings table")
            orchestration_config = json.loads(orchestration_json)
        else:
            # Fallback to bundled config/orchestration.json file
            try:
                from pathlib import Path
                cfg_path = Path(__file__).resolve().parents[2] / "config" / "orchestration.json"
                print(f"DEBUG: Loading orchestration config from file: {cfg_path}")
                orchestration_config = json.loads(cfg_path.read_text())
            except Exception as e:
                print(f"DEBUG: Failed to load orchestration config file: {e}")
                orchestration_config = {}

        # Pull mind-map specific defaults from orchestration config if not provided
        mind_cfg = orchestration_config.get("mind_map_config", {})
        k = config.get("k", mind_cfg.get("k", 15))
        similarity_threshold = config.get("similarity_threshold", mind_cfg.get("similarity_threshold", 0.3))
        expansion_order = config.get("expansion_order", mind_cfg.get("expansion_order", 1))
        max_nodes_per_order = config.get("max_nodes_per_order", mind_cfg.get("max_nodes_per_order", 20))
        layout_algorithm = config.get("layout_algorithm", mind_cfg.get("layout_algorithm", "force"))

        print(f"DEBUG: Final parameters after orchestration defaults – k:{k} thresh:{similarity_threshold} order:{expansion_order} max_per_order:{max_nodes_per_order}")

        # Get LLM model configuration for summarization
        llm_model_config = model_config_override
        if not llm_model_config:
            llm_model_config = mind_cfg.get("summarization_model")
            if llm_model_config:
                print("DEBUG: Using mind_map_config.summarization_model as LLM config")
        if not llm_model_config:
            # Try alternative fallbacks
            llm_model_config = (
                orchestration_config.get("content_extraction_model") or
                orchestration_config.get("judge_model") or
                orchestration_config.get("newsletter_sections_model")
            )
            print(f"DEBUG: Using generic fallback LLM config: {llm_model_config}")
        else:
            print(f"DEBUG: LLM model config determined: {llm_model_config}")

        print(f"DEBUG: Creating mind-map workflow...")
        # Create workflow with database connection
        workflow = create_mindmap_workflow(
            db=None,  # Pass None - workflow nodes will use repositories directly
            config=orchestration_config
        )
        print(f"DEBUG: Mind-map workflow created successfully")

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            "Mind-map workflow initialized. Processing...",
            progress=10,
            current_step="workflow_initialized",
        )
        print(f"DEBUG: Initial status update sent")

        # Define progress callback wrapper for sync execution
        def sync_progress_callback(step: str, progress: float, message: str = ""):
            print(f"DEBUG: sync_progress_callback called - step: {step}, progress: {progress}, message: {message}")
            # Map workflow progress (0-100) to task progress (10-90)
            task_progress = 10 + (progress * 0.8)

            try:
                task_manager.update_task_status_sync(
                    task_id,
                    TaskStatus.PROCESSING,
                    message or f"Processing step: {step}",
                    progress=task_progress,
                    current_step=step,
                )
            except Exception as e:
                print(f"DEBUG: Progress status update failed (sync): {e}")

        # Run the mind-map workflow synchronously
        print(f"DEBUG: About to call workflow.generate_mindmap_sync for task {task_id}")
        print(f"DEBUG: Profile parameters - ID: {profile_id}, IDs: {profile_ids}, tag: {profile_tag}, tags: {profile_tags}")
        result = workflow.generate_mindmap_sync(
            seed_paper_id=int(paper_id),
            k_neighbors=k,
            similarity_threshold=similarity_threshold,
            expansion_order=expansion_order,
            max_nodes_per_order=max_nodes_per_order,
            layout_algorithm=layout_algorithm,
            embedding_model_config=None,  # Will be pulled from config
            llm_model_config=llm_model_config,
            task_id=task_id,  # Use the actual task ID
            progress_callback=sync_progress_callback,  # Pass the sync progress callback
            profile_id=profile_id,
            profile_ids=profile_ids,
            profile_tag=profile_tag,
            profile_tags=profile_tags
        )
        print(f"DEBUG: workflow.generate_mindmap_sync completed for task {task_id}")
        print(f"DEBUG: Result success: {result.get('success', False)}")
        print(f"DEBUG: Result keys: {list(result.keys())}")
        if result.get('mindmap_data'):
            mindmap_data = result['mindmap_data']
            print(f"DEBUG: Mindmap data keys: {list(mindmap_data.keys())}")
            print(f"DEBUG: Nodes count: {len(mindmap_data.get('nodes', []))}")
            print(f"DEBUG: Edges count: {len(mindmap_data.get('edges', []))}")

        if result.get("error"):
            print(f"DEBUG: Result contains error: {result['error']}")
            await task_manager.update_task_status(
                task_id,
                TaskStatus.FAILED,
                f"Mind-map generation failed: {result['error']}",
                error=result["error"],
                current_step="generation_failed",
            )
            print(f"DEBUG: Failed status update sent")
            return

        mindmap_data = result.get("mindmap_data", {})
        nodes = mindmap_data.get("nodes", [])
        edges = mindmap_data.get("edges", [])

        # Auto-save the mind-map as a report if generated from a topic
        report_id = None
        topic_id = config.get("topic_id")
        if topic_id and mindmap_data:
            try:
                print(f"DEBUG: Auto-saving mind-map for topic {topic_id}")
                from ...data_access import TopicsRepository, MindmapReportRepository

                # Get topic details for report title
                topic_data = TopicsRepository.get(topic_id)
                topic_label = topic_data['label'] if topic_data else f"Topic {topic_id}"

                # Create auto-save title
                auto_title = f"Mind-Map: {topic_label[:60]}..." if len(topic_label) > 60 else f"Mind-Map: {topic_label}"

                # Get seed paper for report
                seed_paper = PaperRepository.get_by_id(int(paper_id))
                seed_paper_title = seed_paper['title'] if seed_paper else f"Paper {paper_id}"

                # Prepare parameters from config and result
                save_parameters = {
                    "k": config.get("k", 10),
                    "similarity_threshold": config.get("similarity_threshold", 0.3),
                    "layout_algorithm": layout_algorithm,
                    "expansion_order": config.get("expansion_order", 2),
                    "max_nodes_per_order": config.get("max_nodes_per_order", 5),
                    "generated_from": "topic",
                    "topic_id": topic_id,
                    "auto_generated": True
                }

                # Save as report
                report_id = MindmapReportRepository.insert(
                    title=auto_title,
                    description=f"Auto-generated mind-map from topic '{topic_label}' using seed paper: {seed_paper_title}",
                    seed_paper_id=int(paper_id),
                    seed_paper_title=seed_paper_title,
                    mindmap_data=mindmap_data,
                    parameters=save_parameters,
                    statistics=result.get('statistics', {
                        "nodes_count": len(nodes),
                        "edges_count": len(edges), 
                        "layout_algorithm": layout_algorithm
                    })
                )
                print(f"DEBUG: Mind-map auto-saved as report {report_id}")

            except Exception as save_error:
                print(f"DEBUG: Failed to auto-save mind-map: {save_error}")
                # Don't fail the task if save fails, just log it

        print(f"DEBUG: About to send completion status update")
        # Add a small delay to ensure WebSocket has time to connect
        await asyncio.sleep(0.5)

        # Create the result object that will be sent via WebSocket
        completion_result = {
            "mindmap_data": mindmap_data,
            "seed_paper_id": paper_id,
            "nodes_count": len(nodes),
            "edges_count": len(edges),
            "layout_algorithm": layout_algorithm,
            "report_id": report_id,  # Include the saved report ID
            "auto_saved": report_id is not None
        }
        print(f"DEBUG: Completion result structure: {list(completion_result.keys())}")
        print(f"DEBUG: Mindmap data structure being sent: {list(mindmap_data.keys()) if mindmap_data else 'None'}")
        if mindmap_data and 'nodes' in mindmap_data:
            print(f"DEBUG: First node sample: {mindmap_data['nodes'][0] if mindmap_data['nodes'] else 'No nodes'}")

        # Create completion message
        base_message = f"Mind-map generated successfully with {len(nodes)} nodes and {len(edges)} edges"
        if report_id:
            completion_message = f"{base_message} and auto-saved as report #{report_id}"
        else:
            completion_message = base_message

        await task_manager.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            completion_message,
            progress=100,
            current_step="generation_complete",
            result=completion_result,
        )
        print(f"DEBUG: Completion status update sent")

    except Exception as e:
        import traceback
        traceback.print_exc()
        await task_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            f"Mind-map expansion task failed: {str(e)}",
            error=str(e),
            current_step="task_failed",
        )
        raise


async def run_pdf_parse(task_manager: "TaskManager", task_id: str):
    """Run the PDF parsing task for mind-map papers."""
    try:
        print(f"DEBUG: Starting mind-map PDF parsing task {task_id}")
        task = TaskRepository.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if isinstance(task["config_json"], str):
            config = json.loads(task["config_json"])
        else:
            config = task["config_json"]
        paper_ids = config.get("paper_ids", [])

        if not paper_ids:
            raise ValueError("No paper IDs provided for parsing")

        await task_manager.update_task_status(
            task_id,
            TaskStatus.PROCESSING,
            f"Starting PDF parsing for {len(paper_ids)} papers",
            progress=5,
            current_step="initializing",
        )

        # Import PDF processing utilities
        from ...pdf.processing import MarkitdownDocProcessor
        from LLMFactory import LLMModelFactory

        # Get embedding model configuration with proper fallback hierarchy: DB -> config file -> defaults
        orchestration_config = get_orchestration_config()
        embedding_config = orchestration_config.get("embedding_model", {})

        # Create embedding model
        # Normalize model_type: handle both "sentence-transformers" and "sentence-transformer"
        embedding_model_type = embedding_config.get("model_type", "sentence-transformer")
        if embedding_model_type == "sentence-transformers":
            embedding_model_type = "sentence-transformer"

        embedding_model = LLMModelFactory.create_model(
            model_type=embedding_model_type,
            model_name=embedding_config.get("model_name", "Alibaba-NLP/gte-large-en-v1.5"),
            **{k: v for k, v in embedding_config.items() if k not in ["model_type", "model_name"]}
        )

        # Initialize PDF processor
        pdf_processor = MarkitdownDocProcessor()

        # Process each paper
        parsed_papers = []
        failed_papers = []

        for i, paper_id in enumerate(paper_ids):
            try:
                # Update progress
                progress = 10 + (i / len(paper_ids)) * 80
                await task_manager.update_task_status(
                    task_id,
                    TaskStatus.PROCESSING,
                    f"Processing paper {i+1}/{len(paper_ids)}: {paper_id}",
                    progress=progress,
                    current_step=f"processing_paper_{paper_id}",
                )

                # Get paper details
                paper = PaperRepository.get_by_id(int(paper_id))
                if not paper:
                    failed_papers.append({"paper_id": paper_id, "error": "Paper not found"})
                    continue

                # Check if paper has URL for PDF download
                paper_url = paper.get('url', '')
                if not paper_url:
                    failed_papers.append({"paper_id": paper_id, "error": "No URL available"})
                    continue

                # Process PDF (this is a simplified version - you may need to adapt based on your PDF processing pipeline)
                try:
                    # Extract text from PDF
                    text_content = await pdf_processor.process_url(paper_url)

                    if not text_content:
                        failed_papers.append({"paper_id": paper_id, "error": "Failed to extract text"})
                        continue

                    # Generate embedding for the full text
                    embedding = embedding_model.invoke(text_content, to_list=True)

                    # Store in database
                    PaperFulltextRepository.insert(
                        paper_id=int(paper_id),
                        content=text_content,
                        embedding=embedding,
                        embedding_model=embedding_config.get("model_name", "unknown")
                    )

                    parsed_papers.append(paper_id)

                except Exception as pdf_error:
                    failed_papers.append({"paper_id": paper_id, "error": str(pdf_error)})
                    continue

            except Exception as e:
                failed_papers.append({"paper_id": paper_id, "error": str(e)})
                continue

        # Complete the task
        success_count = len(parsed_papers)
        failure_count = len(failed_papers)

        await task_manager.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            f"PDF parsing completed: {success_count} successful, {failure_count} failed",
            progress=100,
            current_step="parsing_complete",
            result={
                "parsed_papers": parsed_papers,
                "failed_papers": failed_papers,
                "success_count": success_count,
                "failure_count": failure_count,
                "total_requested": len(paper_ids)
            },
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        await task_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            f"PDF parsing task failed: {str(e)}",
            error=str(e),
            current_step="task_failed",
        )
        raise
