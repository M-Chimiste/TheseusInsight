from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Optional, List, Dict
from pydantic import ValidationError
import uuid
import os
import json
import asyncio
from datetime import datetime

from ..models import (
    NewsletterConfig, PodcastGenerationParams, NewsletterRunParams,
    PodcastListItemResponse, PodcastDetailResponse
)
from ..dependencies import db, DB_URL
from ..tasks import task_manager, TaskStatus
from ...theseus_insight import TheseusInsight

router = APIRouter(tags=["newsletters-and-podcasts"])

# Newsletter endpoints
@router.post("/api/newsletter/run")
async def run_newsletter(
    background_tasks: BackgroundTasks,
    config: Optional[str] = Form(None),
    intro_music_file: Optional[UploadFile] = File(None)
):
    """Start the newsletter generation pipeline."""
    try:
        # Parse config
        if not config:
            raise HTTPException(status_code=400, detail="Newsletter configuration is required")
        
        newsletter_config = NewsletterConfig.parse_raw(config)
        task_id = str(uuid.uuid4())
        
        # Save intro music file if provided
        if intro_music_file:
            file_path = f"data/temp/{task_id}/intro_music{os.path.splitext(intro_music_file.filename)[1]}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(await intro_music_file.read())
            newsletter_config.dict()["intro_music_path"] = file_path
        
        # Create and start task
        await task_manager.create_task(
            task_id=task_id,
            task_type="newsletter",
            config=newsletter_config.dict()
        )
        await task_manager.enqueue_task(task_manager.run_newsletter_task, task_id)
        
        return {"taskId": task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/actions/run-newsletter-pipeline", response_model=Dict[str, str])
async def run_newsletter_pipeline_endpoint(
    params: NewsletterRunParams,
    background_tasks: BackgroundTasks
):
    task_id = str(uuid.uuid4())
    run_db_path = DB_URL
    loop = asyncio.get_event_loop()

    def pipeline_progress_callback(stage: str, progress_val: float, message: str):
        """Relay progress from TheseusInsight.run to connected WebSocket clients."""
        status_detail = f"Stage: {stage} - {message} ({progress_val:.2f}%)"
        overall_status_for_tm = TaskStatus.PROCESSING
        if stage.lower() == "newsletter_complete" and progress_val >= 100.0:
            overall_status_for_tm = TaskStatus.COMPLETED

        async def update_status_async():
            await task_manager.update_task_status(
                task_id,
                overall_status_for_tm,
                message=status_detail,
                progress=progress_val,
                current_step=stage,            )

        if loop.is_running():
            # Running from a background thread -> use thread-safe scheduling
            asyncio.run_coroutine_threadsafe(update_status_async(), loop)
        else:
            # Fallback if no running loop was found
            try:
                asyncio.create_task(update_status_async())
            except RuntimeError as e:
                print(
                    "RuntimeError creating task for status update (loop might not be running or accessible): "
                    f"{e}"
                )
                # Consider logging this to a file or a more robust system if it occurs

    async def background_pipeline_run():
        try:
            await task_manager.create_task(
                task_id=task_id,
                task_type="custom_newsletter_run",
                config=params.dict()
            )
            await task_manager.update_task_status(
                task_id,
                TaskStatus.PENDING,
                message="Pipeline initialized.",
                current_step="initializing",
            )

            ti_instance = TheseusInsight(
                research_interests_override=params.research_interests,
                start_date_override=params.start_date,
                end_date_override=params.end_date,
                receiver_address_override=params.email_recipients,
                generate_podcast=params.generate_podcast_run,
                db_saving=True, 
                data_path=run_db_path,
                verbose=True,
                task_id=task_id
            )
            await asyncio.to_thread(
                ti_instance.run,
                progress_callback=pipeline_progress_callback,
            )
            
            current_task_status = task_manager.get_task_status(task_id)
            # If the progress callback hasn't already marked completion
            if current_task_status and current_task_status.get("status") == TaskStatus.PROCESSING:
                await task_manager.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    message="Pipeline finished processing.",
                    current_step="newsletter_complete",
                )

        except Exception as e:
            error_message = f"Error in newsletter pipeline for task {task_id}: {type(e).__name__} - {str(e)}"
            if task_manager:
                await task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error=error_message,
                    message=error_message,
                    current_step="newsletter_failed",
                )
            print(error_message) # Log to server console as well

    await task_manager.enqueue_task(lambda _tid: background_pipeline_run(), task_id)
    return {"task_id": task_id, "message": "Newsletter generation process has been initiated."}

# Podcast endpoints
@router.post("/api/podcast/generate")
async def generate_podcast_pipeline(
    background_tasks: BackgroundTasks,
    params_json: str = Form(..., description="JSON string of PodcastGenerationParams"),
    intro_music_file: Optional[UploadFile] = File(None),
    pdf_files: Optional[List[UploadFile]] = File(None, description="List of PDF files if input_type is 'pdfs'")
):
    """
    Start the podcast generation pipeline using detailed parameters.
    Accepts PodcastGenerationParams as a JSON string in 'params_json' form field,
    an optional intro music file, and optional PDF files.
    """
    try:
        generation_params = PodcastGenerationParams.parse_raw(params_json)
        task_id = str(uuid.uuid4())

        # This will be the main config dictionary passed to the task manager
        # It will be used by the background task to instantiate and run PodcastGenerator
        task_config = {
            "input_type": generation_params.input_type,
            "podcast_model_config": generation_params.podcast_model_config.dict(),
            "tts_model_config": generation_params.tts_model_config.dict(),
            "create_visualization": generation_params.create_visualization,
            "db_saving": True, # Default, can be made configurable if needed
            "data_path": DB_URL, # Global DB URL
            "verbose": True, # Default, can be made configurable
            "output_dir_base": "data/podcasts", # Base directory for task outputs
            "task_id": task_id # Pass task_id for organizing outputs
        }

        if generation_params.urls:
            task_config["urls"] = generation_params.urls
        
        # Handle uploaded intro music file
        if intro_music_file:
            temp_dir = f"data/temp/{task_id}"
            os.makedirs(temp_dir, exist_ok=True)
            intro_music_path = os.path.join(temp_dir, f"intro_{intro_music_file.filename}")
            with open(intro_music_path, "wb") as f:
                f.write(await intro_music_file.read())
            task_config["intro_music_path"] = intro_music_path

        # Handle uploaded PDF files
        if generation_params.input_type == "pdfs" and pdf_files:
            saved_pdf_paths = []
            pdf_temp_dir = f"data/temp/{task_id}/uploaded_pdfs"
            os.makedirs(pdf_temp_dir, exist_ok=True)
            for i, pdf_file in enumerate(pdf_files):
                # Sanitize filename or use a unique name
                safe_filename = f"doc_{i}_{os.path.basename(pdf_file.filename or f'file{i}.pdf')}"
                pdf_path = os.path.join(pdf_temp_dir, safe_filename)
                with open(pdf_path, "wb") as f:
                    f.write(await pdf_file.read())
                saved_pdf_paths.append(pdf_path)
            task_config["input_pdf_paths"] = saved_pdf_paths
        elif generation_params.input_type == "pdfs" and not pdf_files:
            raise HTTPException(status_code=400, detail="PDF files are required when input_type is 'pdfs'.")


        if generation_params.create_visualization and generation_params.visualizer_params:
            vis_p = generation_params.visualizer_params
            task_config.update({
                "visualizer_settings": vis_p.dict() # Pass the whole dict
            })
        else:
            task_config["visualizer_settings"] = None


        # Create task with the comprehensive config
        await task_manager.create_task(
            task_id=task_id,
            task_type="podcast", # Using existing "podcast" type, assuming run_podcast_task can handle new config
            config=task_config 
        )
        
        # The task_manager.run_podcast_task needs to be able to:
        # 1. Instantiate PodcastGenerator with relevant parts of task_config
        #    (podcast_model_config, tts_model_config, intro_music_path, etc.)
        # 2. Call PodcastGenerator.generate_podcast() with input_pdf_paths or processed URLs,
        #    output directory derived from task_id, and visualizer settings.
        # 3. Handle URL fetching and conversion to PDF if input_type is 'urls' (this is complex).
        #    For now, this implementation primarily supports 'pdfs' directly for PodcastGenerator.
        #    If 'urls' are passed, 'run_podcast_task' needs to manage downloading/converting them to PDF paths.
        await task_manager.enqueue_task(task_manager.run_podcast_task, task_id)
        
        return {"task_id": task_id, "message": "Podcast generation process initiated."}
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for params_json.")
    except ValueError as e: # Handles Pydantic validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException: # Re-raise existing HTTPExceptions
        raise
    except Exception as e:
        print(f"Error in /api/podcast/generate: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error processing podcast request: {str(e)}")

@router.get("/api/podcasts/history", response_model=List[PodcastListItemResponse])
async def get_podcast_history_list():
    """Get a list of all podcasts, sorted by date, for history view."""
    try:
        podcasts_data = db.fetch_all_podcasts() # This already sorts by id DESC, which is fine if new IDs are always later dates. If date sorting is strict, we'd sort here.
        
        response_items = []
        for p_data in podcasts_data:
            description_snippet = (p_data['description'][:150] + '...') if len(p_data['description']) > 150 else p_data['description']
            response_items.append(
                PodcastListItemResponse(
                    id=p_data['id'],
                    title=p_data['title'],
                    date=p_data['date'],
                    description_snippet=description_snippet
                )
            )
        # To strictly sort by date if IDs don't guarantee it:
        response_items.sort(key=lambda x: datetime.strptime(x.date, '%Y-%m-%d'), reverse=True)
        return response_items
    except Exception as e:
        print(f"Error fetching podcast history list: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching podcast history.")

@router.get("/api/podcasts/history/{podcast_id}", response_model=PodcastDetailResponse)
async def get_podcast_detail(podcast_id: int):
    """Get detailed information for a single podcast, including its parsed script."""
    try:
        podcast_data = db.fetch_podcast_by_id(podcast_id)
        if not podcast_data:
            raise HTTPException(status_code=404, detail=f"Podcast with ID {podcast_id} not found.")
        
        # The script from db.fetch_podcast_by_id is already a Python list of dicts
        # Pydantic will validate it against List[PodcastScriptItem]
        return PodcastDetailResponse(
            id=podcast_data['id'],
            title=podcast_data['title'],
            date=podcast_data['date'],
            description=podcast_data['description'],
            script=podcast_data['script'] # Pydantic validation happens here
        )
    except HTTPException: # Re-raise HTTPException directly
        raise
    except ValidationError as ve: # Catch Pydantic validation errors specifically for the script
        print(f"Validation error for podcast script (ID: {podcast_id}): {ve}")
        raise HTTPException(status_code=500, detail=f"Error validating podcast script data for podcast ID {podcast_id}.")
    except Exception as e:
        print(f"Error fetching podcast detail (ID: {podcast_id}): {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred while fetching details for podcast ID {podcast_id}.")

@router.delete("/api/podcasts/history/{podcast_id}")
async def delete_podcast(podcast_id: int):
    """Delete a podcast by its ID."""
    try:
        # Check if podcast exists first
        podcast_data = db.fetch_podcast_by_id(podcast_id)
        if not podcast_data:
            raise HTTPException(status_code=404, detail=f"Podcast with ID {podcast_id} not found.")
        
        # Delete the podcast
        was_deleted = db.delete_podcast_by_id(podcast_id)
        if not was_deleted:
            raise HTTPException(status_code=404, detail=f"Podcast with ID {podcast_id} not found.")
        
        return {"status": "success", "message": f"Podcast with ID {podcast_id} has been deleted successfully."}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting podcast (ID: {podcast_id}): {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred while deleting podcast ID {podcast_id}.")

@router.put("/api/podcasts/history/{podcast_id}/title")
async def update_podcast_title(podcast_id: int, title_data: dict):
    """Update the title of a podcast by its ID."""
    try:
        # Validate request body
        if "title" not in title_data:
            raise HTTPException(status_code=400, detail="Title field is required.")
        
        new_title = title_data["title"].strip()
        if not new_title:
            raise HTTPException(status_code=400, detail="Title cannot be empty.")
        
        # Check if podcast exists first
        podcast_data = db.fetch_podcast_by_id(podcast_id)
        if not podcast_data:
            raise HTTPException(status_code=404, detail=f"Podcast with ID {podcast_id} not found.")
        
        # Update the podcast title
        was_updated = db.update_podcast_title(podcast_id, new_title)
        if not was_updated:
            raise HTTPException(status_code=404, detail=f"Podcast with ID {podcast_id} not found.")
        
        return {"status": "success", "message": f"Podcast title updated successfully.", "title": new_title}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating podcast title (ID: {podcast_id}): {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred while updating podcast title for ID {podcast_id}.") 