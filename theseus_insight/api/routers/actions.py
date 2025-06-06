from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from pydantic import ValidationError
import uuid
import os
import json

from ..models import VisualizerSettings
from ..dependencies import db
from ..tasks import task_manager

router = APIRouter(prefix="/api/actions", tags=["actions"])

@router.post("/run-visualizer-pipeline")
async def run_visualizer_pipeline_endpoint(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(..., description="Audio file to visualize"),
    visualizer_params_json: str = Form(..., description="JSON string of VisualizerSettings")
):
    task_id = str(uuid.uuid4())
    try:
        visualizer_params = VisualizerSettings.parse_raw(visualizer_params_json)
        
        temp_dir = f"data/temp/{task_id}"
        os.makedirs(temp_dir, exist_ok=True)
        
        audio_file_path = os.path.join(temp_dir, f"audio_input_{audio_file.filename}")
        with open(audio_file_path, "wb") as f:
            f.write(await audio_file.read())

        task_config = {
            "audio_file_path": audio_file_path,
            "visualizer_params": visualizer_params.dict(),
            "output_dir_base": "data/visualizations", # Base directory for task outputs
            "task_id": task_id
        }

        await task_manager.create_task(
            task_id=task_id,
            task_type="visualizer",
            config=task_config
        )
        
        await task_manager.enqueue_task(task_manager.run_visualizer_task, task_id, visualizer=True)
        
        return {"task_id": task_id, "message": "Visualizer generation process initiated."}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for visualizer_params_json.")
    except ValidationError as e: # Pydantic validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error processing visualizer request: {str(e)}") 