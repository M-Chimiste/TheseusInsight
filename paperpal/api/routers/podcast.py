from fastapi import APIRouter, HTTPException, BackgroundTasks, File, UploadFile, Form
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from pathlib import Path
from paperpal.podcast.generator import PaperPalPodcastGenerator
from paperpal.api.routers.script import Script, SCRIPT_DIR
from paperpal.data_processing.data_handling import PaperDatabase, Podcast
import json
import tempfile
import os
import time
from fastapi.responses import FileResponse

router = APIRouter()

# Configure paths
DB_PATH = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "data/papers.db"
SCRIPT_DIR = Path("scripts")
SCRIPT_DIR.mkdir(parents=True, exist_ok=True)

# Initialize database
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db = PaperDatabase(str(DB_PATH))

# Configure output directories with absolute path
OUTPUT_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))) / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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
    tts_provider: str = "kokoro"
    speaker_1_voice: str = "af_bella"
    speaker_1_speed: float = 1.15
    speaker_2_voice: str = "am_adam"
    speaker_2_speed: float = 1.15
    output_format: str = "mp3"
    visualizer: bool = False
    resolution: tuple = (1920, 1080)
    fps: int = 30

class PodcastGenerationRequest(BaseModel):
    texts: List[str]
    paperpal_sections: List[str]
    config: Optional[PodcastGenerationConfig] = PodcastGenerationConfig()

@router.post("/generate")
async def generate_podcast(
    background_tasks: BackgroundTasks,
    config: str = Form(...),
    urls: str = Form(default="[]"),
    files: List[UploadFile] = File(default=[])
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
        for file in files:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                content = await file.read()
                temp_file.write(content)
                temp_files.append(temp_file.name)
        
        # Combine URLs and temp file paths
        all_sources = urls_list + temp_files
        
        # Generate task ID and initialize status
        task_id = f"podcast-{int(time.time())}"
        output_filename = f"podcast_{task_id}.{config_obj.output_format}"
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
        generator = PaperPalPodcastGenerator(
            text_model=config_obj.text_model,
            tts_provider=config_obj.tts_provider,
            speaker_1_voice=config_obj.speaker_1_voice,
            speaker_1_speed=config_obj.speaker_1_speed,
            speaker_2_voice=config_obj.speaker_2_voice,
            speaker_2_speed=config_obj.speaker_2_speed
        )
        
        # Define background task with progress tracking
        def generate_with_progress():
            try:
                progress_callback(task_id, "Processing PDFs", 10)
                
                # Start the generation process
                result = generator.generate_podcast(
                    pdf_paths=all_sources,
                    paperpal_sections=[],  # TODO: Add paperpal sections support
                    output_format=config_obj.output_format,
                    output_dir=str(OUTPUT_DIR),
                    visualizer=config_obj.visualizer,
                    resolution=config_obj.resolution,
                    fps=config_obj.fps,
                    progress_callback=lambda step, prog: progress_callback(task_id, step, prog)
                )
                
                if not result or "output_file" not in result:
                    raise ValueError("Podcast generation failed: No output file produced")
                
                # Save the script to both the scripts directory and database
                script_filename = f"podcast_{task_id}.json"
                script_path = SCRIPT_DIR / script_filename
                script_data = {
                    "dialogue": result.get("dialogue", {}).get("dialogue", []),
                    "metadata": {
                        "description": result.get("description", "A podcast episode generated by PaperPal."),
                        "created_at": time.time(),
                        "output_file": str(result.get("output_file")),
                        "visualizer_file": str(result.get("visualizer_file"))
                    }
                }
                
                # Save to JSON file
                with open(script_path, "w") as f:
                    json.dump(script_data, f, indent=2)
                
                # Save to database
                podcast = Podcast(
                    title=f"Podcast {task_id}",
                    date=time.strftime('%Y-%m-%d'),
                    script=script_data["dialogue"],
                    description=result.get("description", "A podcast episode generated by PaperPal.")
                )
                db.insert_podcast(podcast)
                
                TASK_STATUS[task_id].update({
                    "status": "completed",
                    "progress": 100,
                    "current_step": "Completed",
                    "output_file": result.get("output_file", output_path),
                    "description": result.get("description", "A podcast episode generated by PaperPal."),
                    "script_file": script_filename,
                    "updated_at": time.time()
                })
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
                # Clean up temp files
                for temp_file in temp_files:
                    try:
                        os.unlink(temp_file)
                    except Exception as e:
                        print(f"Failed to clean up temp file {temp_file}: {str(e)}")
                        pass
        
        # Start the background task
        background_tasks.add_task(generate_with_progress)
        
        return {
            "message": "Podcast generation started",
            "status": "processing",
            "task_id": task_id
        }
    except Exception as e:
        # Clean up temp files on error
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/regenerate")
async def regenerate_podcast(script: Script, config: PodcastGenerationConfig):
    """
    Regenerate a podcast from an existing script with new configuration.
    """
    try:
        generator = PaperPalPodcastGenerator(
            text_model=config.text_model,
            tts_provider=config.tts_provider,
            speaker_1_voice=config.speaker_1_voice,
            speaker_1_speed=config.speaker_1_speed,
            speaker_2_voice=config.speaker_2_voice,
            speaker_2_speed=config.speaker_2_speed
        )
        
        result = generator.regenerate_podcast_from_script(
            dialogue_dict=script.dict(),
            output_format=config.output_format,
            output_dir=str(OUTPUT_DIR),
            visualizer=config.visualizer,
            resolution=config.resolution,
            fps=config.fps
        )
        
        return result
    except Exception as e:
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
    
    return {
        "status": task["status"],
        "current_step": task["current_step"],
        "progress": task["progress"],
        "error": task["error"],
        "output_url": f"/api/podcast/download/{Path(task['output_file']).name}" if task["status"] == "completed" else None
    }

@router.get("/download/{filename}")
async def download_podcast(filename: str):
    """
    Download a generated podcast file.
    """
    # Clean the filename to prevent path traversal
    safe_filename = Path(filename).name
    file_path = OUTPUT_DIR.resolve() / safe_filename
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    return FileResponse(
        path=str(file_path),
        filename=safe_filename,
        media_type="audio/mpeg" if filename.endswith('.mp3') else "audio/wav"
    )
