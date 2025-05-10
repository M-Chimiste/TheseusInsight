from fastapi import APIRouter, HTTPException, BackgroundTasks, File, UploadFile, Form
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
from theseus_insight.podcast.generator import GeneralPodcastGenerator
from theseus_insight.api.routers.script import Script, SCRIPT_DIR
from theseus_insight.data_model import PaperDatabase, Podcast
import json
import tempfile
import os
import time
from fastapi.responses import FileResponse
import traceback

router = APIRouter()

# Configure paths
DB_PATH = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "data/papers.db"
print(DB_PATH)
SCRIPT_DIR = Path("scripts")
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db = PaperDatabase(str(DB_PATH))

# Configure output directories with absolute path
OUTPUT_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "output_audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"Configured OUTPUT_DIR: {OUTPUT_DIR}")  # Debug log

# In-memory task tracking
TASK_STATUS: Dict[str, Dict[str, Any]] = {}

def progress_callback(task_id: str, step: str, progress: float):
    """Update task status with progress information"""
    if task_id in TASK_STATUS:
        print(f"Progress update for {task_id}: {step} - {progress}%")  # Debug logging
        TASK_STATUS[task_id].update({
            "status": "processing",
            "current_step": step,
            "progress": min(round(progress, 1), 100),
            "updated_at": time.time()
        })

class PodcastGenerationConfig(BaseModel):
    text_model: dict = {
        "model_name": "claude-3-5-sonnet-20240620",
        "model_type": "anthropic",
        "max_new_tokens": 8192,
        "temperature": 0.1,
        "num_ctx": 131072
    }
    tts_provider: str = "openai"
    speaker_1_voice: str = "sage"
    speaker_1_speed: float = 1.15
    speaker_2_voice: str = "ash"
    speaker_2_speed: float = 1.15
    output_format: str = "mp3"
    visualizer: bool = False
    resolution: tuple = (1920, 1080)
    fps: int = 30
    matrix_count: int = 200
    fade_time: float = 3.0
    head_saw_period: float = 1.5
    font_path: str = ""
    
    # Insert a half-second pause at the end of each major podcast segment
    pause_duration: float = 0.5

class PodcastGenerationRequest(BaseModel):
    texts: List[str]
    config: Optional[PodcastGenerationConfig] = PodcastGenerationConfig()

@router.post("/generate")
async def generate_podcast(
    background_tasks: BackgroundTasks,
    config: str = Form(...),
    urls: str = Form(default="[]"),
    files: List[UploadFile] = File(default=[]),
    intro_music_file: UploadFile = File(default=None)
):
    """
    Generate a podcast from the provided files, URLs and configuration.
    This is a long-running task that will be processed in the background.
    """
    try:
        # Parse the config and URLs from JSON strings
        config_dict = json.loads(config)
        config_obj = PodcastGenerationConfig.model_validate(config_dict)
        urls_list = json.loads(urls)
        
        # Save uploaded files to temporary location
        temp_files = []
        intro_music_path = None
        
        # Save intro music if provided
        if intro_music_file:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                content = await intro_music_file.read()
                temp_file.write(content)
                intro_music_path = temp_file.name
        
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_files.append(temp_file.name)
        
        # Combine URLs and temp file paths
        all_sources = urls_list + temp_files
        
        # Generate task ID and initialize status
        task_id = f"podcast-{int(time.time())}"
        timestamp = int(time.time())
        output_filename = f"podcast_final_{timestamp}.{config_obj.output_format}"
        output_path = str(OUTPUT_DIR / output_filename)
        
        TASK_STATUS[task_id] = {
            "status": "processing",
            "current_step": "Initializing",
            "progress": 0,
            "created_at": time.time(),
            "updated_at": time.time(),
            "output_file": output_path,
            "error": None
        }
        
        # Initialize the generator with the provided configuration
        generator = GeneralPodcastGenerator(
            text_model=config_obj.text_model,
            tts_provider=config_obj.tts_provider,
            speaker_1_voice=config_obj.speaker_1_voice,
            speaker_1_speed=config_obj.speaker_1_speed,
            speaker_2_voice=config_obj.speaker_2_voice,
            speaker_2_speed=config_obj.speaker_2_speed,
            pause_duration=config_obj.pause_duration
        )
        
        # Define background task with progress tracking
        def generate_with_progress():
            try:
                progress_callback(task_id, "Processing PDFs", 10)
                
                # Start the generation process
                result = generator.generate_podcast(
                    pdf_paths=all_sources,
                    output_format=config_obj.output_format,
                    output_dir=str(OUTPUT_DIR),
                    prefix=f"segment_{timestamp}",
                    final_filename=f"podcast_final_{timestamp}",
                    visualizer=config_obj.visualizer,
                    resolution=config_obj.resolution,
                    fps=config_obj.fps,
                    matrix_count=config_obj.matrix_count,
                    fade_time=config_obj.fade_time,
                    head_saw_period=config_obj.head_saw_period,
                    font_path=config_obj.font_path,
                    intro_music_path=intro_music_path,
                    progress_callback=lambda step, prog: progress_callback(task_id, step, prog)
                )
                
                if not result or "output_file" not in result:
                    raise ValueError("Podcast generation failed: No output file produced")
                
                # Verify output file exists
                output_file = Path(result["output_file"])
                print(f"Generation task - Output file path: {output_file}")  # Debug log
                print(f"Generation task - Output file exists: {output_file.exists()}")  # Debug log
                
                if not output_file.exists():
                    raise ValueError(f"Generated output file not found at {output_file}")
                
                # Save the script to both the scripts directory and database
                script_filename = f"podcast_{timestamp}.json"
                script_path = SCRIPT_DIR / script_filename
                script_data = {
                    "dialogue": result.get("dialogue", {}).get("dialogue", []),
                    "metadata": {
                        "description": result.get("description", "A podcast episode generated by Theseus Insight."),
                        "created_at": time.time(),
                        "output_file": str(output_file),
                        "visualizer_file": str(result.get("visualizer_file")) if result.get("visualizer_file") else None
                    }
                }
                
                # Save to JSON file
                with open(script_path, "w") as f:
                    json.dump(script_data, f, indent=2)
                
                # Save to database
                podcast = Podcast(
                    title=f"Podcast {timestamp}",
                    date=time.strftime('%Y-%m-%d'),
                    script=script_data["dialogue"],
                    description=result.get("description", "A podcast episode generated by Theseus Insight.")
                )
                db.insert_podcast(podcast)
                
                TASK_STATUS[task_id].update({
                    "status": "completed",
                    "progress": 100,
                    "current_step": "Completed",
                    "output_file": str(output_file),
                    "description": result.get("description", "A podcast episode generated by Theseus Insight."),
                    "script_file": script_filename,
                    "updated_at": time.time()
                })
                
                print(f"Generation task - Final task status: {TASK_STATUS[task_id]}")  # Debug log
            except Exception as e:
                print(f"Error in podcast generation task: {str(e)}")
                TASK_STATUS[task_id].update({
                    "status": "failed",
                    "error": str(e),
                    "current_step": "Failed",
                    "updated_at": time.time(),
                    "description": None
                })
            finally:
                # Clean up the temporary PDF files and intro music file
                for temp_file in temp_files:
                    try:
                        if os.path.exists(temp_file):
                            os.unlink(temp_file)
                    except Exception as e:
                        print(f"Failed to clean up temp file {temp_file}: {str(e)}")
                
                if intro_music_path and os.path.exists(intro_music_path):
                    try:
                        os.unlink(intro_music_path)
                    except Exception as e:
                        print(f"Failed to clean up intro music file: {str(e)}")
        
        # Start the background task
        background_tasks.add_task(generate_with_progress)
        
        return {
            "message": "Podcast generation started",
            "status": "processing",
            "task_id": task_id
        }
    except Exception as e:
        error_msg = f"Error in generate_podcast endpoint: {str(e)}\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)
        # Clean up temp files on error
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/regenerate")
async def regenerate_podcast(script: Script, config: PodcastGenerationConfig):
    """
    Regenerate a podcast from an existing script with new configuration.
    """
    try:
        # Initialize the generator with the provided configuration
        generator = GeneralPodcastGenerator(
            text_model=config.text_model,
            tts_provider=config.tts_provider,
            speaker_1_voice=config.speaker_1_voice,
            speaker_1_speed=config.speaker_1_speed,
            speaker_2_voice=config.speaker_2_voice,
            speaker_2_speed=config.speaker_2_speed,
            pause_duration=config.pause_duration
        )
        
        timestamp = int(time.time())
        result = generator.regenerate_podcast_from_script(
            dialogue_dict=script.model_dump(),
            output_format=config.output_format,
            output_dir=str(OUTPUT_DIR),
            prefix=f"segment_{timestamp}",
            final_filename=f"podcast_final_{timestamp}",
            visualizer=config.visualizer,
            resolution=config.resolution,
            fps=config.fps,
            matrix_count=config.matrix_count,
            fade_time=config.fade_time,
            head_saw_period=config.head_saw_period,
            font_path=config.font_path
        )
        
        if not result or "output_file" not in result:
            raise HTTPException(
                status_code=500,
                detail="Podcast regeneration failed: No output file produced"
            )
        
        # Save the script to both the scripts directory and database
        script_filename = f"podcast_{timestamp}.json"
        script_path = SCRIPT_DIR / script_filename
        script_data = {
            "dialogue": script.dialogue,
            "metadata": {
                "description": result.get("description", "A regenerated podcast episode by Theseus Insight."),
                "created_at": time.time(),
                "output_file": str(result.get("output_file")),
                "visualizer_file": str(result.get("visualizer_file")) if result.get("visualizer_file") else None
            }
        }
        
        # Save to JSON file
        with open(script_path, "w") as f:
            json.dump(script_data, f, indent=2)
        
        # Save to database
        podcast = Podcast(
            title=f"Podcast {timestamp}",
            date=time.strftime('%Y-%m-%d'),
            script=script_data["dialogue"],
            description=result.get("description", "A regenerated podcast episode by Theseus Insight.")
        )
        db.insert_podcast(podcast)
        
        return {
            "status": "completed",
            "output_file": str(result.get("output_file")),
            "visualizer_file": str(result.get("visualizer_file")) if result.get("visualizer_file") else None,
            "script_file": script_filename,
            "description": result.get("description", "A regenerated podcast episode by Theseus Insight.")
        }
        
    except Exception as e:
        print(f"Error in podcast regeneration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{task_id}")
async def get_generation_status(task_id: str):
    """
    Get the status of a podcast generation task.
    """
    if task_id not in TASK_STATUS:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = TASK_STATUS[task_id]
    
    # Clean up completed tasks older than 1 hour
    current_time = time.time()
    if task["status"] in ["completed", "failed"] and current_time - task["updated_at"] > 3600:
        TASK_STATUS.pop(task_id)
    
    output_url = None
    if task["status"] == "completed" and "output_file" in task:
        output_filename = Path(task["output_file"]).name
        print(f"Status endpoint - Output filename: {output_filename}")  # Debug log
        output_url = f"/podcast/download/{output_filename}"  # Removed duplicate /api/
    
    return {
        "status": task["status"],
        "current_step": task["current_step"],
        "progress": task["progress"],
        "error": task["error"],
        "output_url": output_url
    }

@router.get("/download/{filename}")
async def download_podcast(filename: str):
    """
    Download a generated podcast file.
    """
    try:
        # Clean the filename to prevent path traversal
        safe_filename = Path(filename).name
        file_path = OUTPUT_DIR / safe_filename
        
        print(f"Download endpoint - Looking for file: {file_path}")  # Debug log
        print(f"Download endpoint - OUTPUT_DIR: {OUTPUT_DIR}")  # Debug log
        print(f"Download endpoint - File exists: {os.path.exists(file_path)}")  # Debug log
        print(f"Download endpoint - Current working directory: {os.getcwd()}")  # Debug log
        print(f"Download endpoint - Directory contents: {list(OUTPUT_DIR.glob('*'))}")  # Debug log
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=404, 
                detail=f"File not found at {file_path}. OUTPUT_DIR={OUTPUT_DIR}, CWD={os.getcwd()}, Available files: {list(OUTPUT_DIR.glob('*'))}"
            )
        
        media_type = "audio/mpeg" if filename.endswith('.mp3') else "audio/wav"
        print(f"Download endpoint - Serving file with media type: {media_type}")  # Debug log
        
        return FileResponse(
            path=str(file_path),
            filename=safe_filename,
            media_type=media_type
        )
    except Exception as e:
        print(f"Error in download endpoint: {str(e)}\nTraceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))
