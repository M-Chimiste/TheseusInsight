from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from typing import Optional, Dict, Any
import json
import os
import tempfile
from datetime import datetime
from ..theseus_insight import TheseusInsight

router = APIRouter()

# Store active tasks and their status
active_tasks: Dict[str, Dict[str, Any]] = {}

async def run_theseus_insight_task(
    task_id: str,
    config: dict,
    research_interests_path: Optional[str] = None,
    orchestration_path: Optional[str] = None
) -> None:
    try:
        # Update task status
        active_tasks[task_id]["status"] = "running"
        
        # Initialize Theseus Insight with config
        theseus_insight = TheseusInsight(
            research_interests_path=research_interests_path or config.get('researchInterestsPath'),
            orchestration_config=orchestration_path or config.get('orchestrationConfigPath'),
            n_days=config.get('nDays', 7),
            top_n=config.get('topN', 5),
            start_date=config.get('startDate'),
            end_date=config.get('endDate'),
            receiver_address=config.get('emails', []),
            # Visualizer settings
            resolution=config.get('visualizerConfig', {}).get('resolution', [1920, 1080]),
            fps=config.get('visualizerConfig', {}).get('fps', 30),
            matrix_count=config.get('visualizerConfig', {}).get('matrix_count', 200),
            matrix_head_color=config.get('visualizerConfig', {}).get('matrix_head_color', "#e0ffe7"),
            matrix_tail_color=config.get('visualizerConfig', {}).get('matrix_tail_color', "0x00b000"),
            matrix_char_size=config.get('visualizerConfig', {}).get('matrix_char_size', 24),
            fade_time=config.get('visualizerConfig', {}).get('fade_time', 1.5),
            head_saw_period=config.get('visualizerConfig', {}).get('head_saw_period', 1.5),
            wave_color=config.get('visualizerConfig', {}).get('wave_color', "#d703fc"),
            trail_colors=config.get('visualizerConfig', {}).get('trail_colors', ["#fc03b6", "#ba03fc", "#ce6bf2"]),
            line_width=config.get('visualizerConfig', {}).get('line_width', 6),
            font_path=config.get('visualizerConfig', {}).get('font_path', ""),
        )

        # Add progress callback
        def progress_callback(stage: str, progress: float, message: str):
            active_tasks[task_id].update({
                "stage": stage,
                "progress": progress,
                "message": message
            })

        # Run Theseus Insight with progress tracking
        theseus_insight.run(progress_callback=progress_callback)
        
        # Update final status
        active_tasks[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": "Theseus Insight run completed successfully"
        })

    except Exception as e:
        active_tasks[task_id].update({
            "status": "failed",
            "error": str(e)
        })
        raise

@router.post("/run")
async def run_theseus_insight(
    background_tasks: BackgroundTasks,
    config: str = Form(...),
    research_interests_file: Optional[UploadFile] = File(None),
    orchestration_file: Optional[UploadFile] = File(None)
):
    try:
        # Parse config
        config_dict = json.loads(config)
        
        # Generate task ID
        task_id = f"theseus_insight_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Initialize task status
        active_tasks[task_id] = {
            "status": "initializing",
            "progress": 0,
            "message": "Initializing Theseus Insight run"
        }

        # Handle file uploads if provided
        research_interests_path = None
        orchestration_path = None

        if research_interests_file:
            # Create temp file for research interests
            suffix = os.path.splitext(research_interests_file.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                content = await research_interests_file.read()
                temp_file.write(content)
                research_interests_path = temp_file.name

        if orchestration_file:
            # Create temp file for orchestration config
            suffix = os.path.splitext(orchestration_file.filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                content = await orchestration_file.read()
                temp_file.write(content)
                orchestration_path = temp_file.name

        # Start background task
        background_tasks.add_task(
            run_theseus_insight_task,
            task_id,
            config_dict,
            research_interests_path,
            orchestration_path
        )

        return {"task_id": task_id, "status": "started"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}")
async def get_status(task_id: str):
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return active_tasks[task_id] 