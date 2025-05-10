from fastapi import APIRouter, HTTPException, UploadFile, BackgroundTasks, Form, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Tuple, Dict
from pathlib import Path
from ...podcast.visualizer import generate_visualizer_video
import tempfile
import os
import json
import time

router = APIRouter()

# Configure output directories with absolute path
OUTPUT_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# In-memory task tracking
TASK_STATUS: Dict[str, dict] = {}

class VisualizerConfig(BaseModel):
    resolution: Tuple[int, int] = (1920, 1080)
    fps: int = 30
    matrix_count: int = 200
    matrix_head_color: str = "#e0ffe7"
    matrix_tail_color: str = "0x00b000"
    matrix_char_size: int = 24
    head_step_time: float = 0.25
    random_x_jitter: float = 2.0
    fade_time: float = 5.0
    head_glow_passes: int = 3
    head_glow_alpha_decay: int = 50
    head_spawn_delay_range: Tuple[float, float] = (1.0, 3.0)
    head_saw_period: float = 0.5
    wave_color: str = "#d703fc"
    trail_colors: List[str] = ["#fc03b6", "#ba03fc", "#ce6bf2"]
    glow_passes: int = 3
    glow_alpha_decay: int = 40
    line_width: int = 6

def progress_callback(task_id: str, step: str, progress: float):
    """Update task status with progress information"""
    if task_id in TASK_STATUS:
        TASK_STATUS[task_id].update({
            "current_step": step,
            "progress": progress,
            "updated_at": time.time()
        })

@router.post("/generate")
async def generate_visualization(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    config: Optional[str] = Form(None)
):
    """
    Generate a visualization video for an audio file.
    Supports formats: wav, mp3, ogg, flac
    """
    supported_formats = ['.wav', '.mp3', '.ogg', '.flac']
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format. Must be one of: {', '.join(supported_formats)}"
        )
    
    try:
        # Parse config if provided, otherwise use defaults
        visualizer_config = VisualizerConfig()
        if config:
            config_dict = json.loads(config)
            visualizer_config = VisualizerConfig.model_validate(config_dict)

        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Generate output filename and task ID
        output_filename = f"visualizer_{Path(file.filename).stem}.mp4"
        output_path = f"{OUTPUT_DIR}/{output_filename}"
        task_id = f"task-{output_filename}"

        # Initialize task status
        TASK_STATUS[task_id] = {
            "status": "processing",
            "current_step": "Initializing",
            "progress": 0,
            "created_at": time.time(),
            "updated_at": time.time(),
            "output_file": str(output_path),
            "error": None
        }

        # Start the visualization generation in the background
        def generate_with_progress():
            try:
                generate_visualizer_video(
                    audio_filepath=temp_file_path,
                    output_filepath=str(output_path),
                    resolution=visualizer_config.resolution,
                    fps=visualizer_config.fps,
                    matrix_count=visualizer_config.matrix_count,
                    matrix_head_color=visualizer_config.matrix_head_color,
                    matrix_tail_color=visualizer_config.matrix_tail_color,
                    matrix_char_size=visualizer_config.matrix_char_size,
                    head_step_time=visualizer_config.head_step_time,
                    random_x_jitter=visualizer_config.random_x_jitter,
                    fade_time=visualizer_config.fade_time,
                    head_glow_passes=visualizer_config.head_glow_passes,
                    head_glow_alpha_decay=visualizer_config.head_glow_alpha_decay,
                    head_spawn_delay_range=visualizer_config.head_spawn_delay_range,
                    head_saw_period=visualizer_config.head_saw_period,
                    wave_color=visualizer_config.wave_color,
                    trail_colors=visualizer_config.trail_colors,
                    glow_passes=visualizer_config.glow_passes,
                    glow_alpha_decay=visualizer_config.glow_alpha_decay,
                    line_width=visualizer_config.line_width,
                    progress_callback=lambda step, progress: progress_callback(task_id, step, progress)
                )
                TASK_STATUS[task_id].update({
                    "status": "completed",
                    "progress": 100,
                    "current_step": "Completed",
                    "updated_at": time.time()
                })
            except Exception as e:
                TASK_STATUS[task_id].update({
                    "status": "failed",
                    "error": str(e),
                    "updated_at": time.time()
                })
            finally:
                # Clean up temp file
                os.unlink(temp_file_path)

        background_tasks.add_task(generate_with_progress)
        
        return {
            "message": "Visualization generation started",
            "output_file": output_filename,
            "status": "processing",
            "task_id": task_id
        }
    except Exception as e:
        # Clean up on error
        if 'temp_file_path' in locals():
            os.unlink(temp_file_path)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}")
async def get_visualization_status(task_id: str):
    """
    Get the status of a visualization generation task.
    """
    if task_id not in TASK_STATUS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = TASK_STATUS[task_id]
    
    # Clean up completed tasks older than 1 hour
    current_time = time.time()
    if task["status"] in ["completed", "failed"] and current_time - task["updated_at"] > 3600:
        TASK_STATUS.pop(task_id)
    
    return {
        "status": task["status"],
        "current_step": task["current_step"],
        "progress": task["progress"],
        "error": task["error"],
        "output_url": f"/visualizer/download/{Path(task['output_file']).name}" if task["status"] == "completed" else None
    }

@router.get("/download/{filename}")
async def download_visualization(filename: str):
    """
    Download a generated visualization video file.
    """
    # Clean the filename to prevent path traversal
    safe_filename = Path(filename).name
    file_path = OUTPUT_DIR / safe_filename
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
        media_type="video/mp4"
    )
