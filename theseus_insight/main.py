from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict
import json
import os
import uuid
from datetime import datetime
from fastapi.responses import FileResponse, JSONResponse

from .data_model.data_handling import PaperDatabase
from .api.models import (
    Model, ModelCreate, Paper, Run, PaginatedResponse,
    NewsletterConfig, RunStatus, OrchestrationConfig,
    VisualizerSettings, ArxivCategoriesConfig, ModelProvider,
    EmailRecipients, ResearchInterests, ModelConfig
)
from .api.tasks import task_manager, TaskStatus

# Initialize FastAPI app
app = FastAPI(
    title="Theseus Insight API",
    description="Backend API for Theseus Insight research paper analysis platform",
    version="0.1.0"
)

# CORS configuration
CORS_ORIGINS = [
    "http://localhost:3000",  # Development frontend
    "http://localhost:8000",  # Development API
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
]

if os.getenv("PRODUCTION_FRONTEND_URL"):
    CORS_ORIGINS.append(os.getenv("PRODUCTION_FRONTEND_URL"))

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    try:
        # Ensure required directories exist
        os.makedirs("data/newsletters", exist_ok=True)
        os.makedirs("data/podcasts", exist_ok=True)
        os.makedirs("data/visualizations", exist_ok=True)
        
        # Initialize database if not exists
        # db._initialize_database()
        
        # Load environment variables
        required_env_vars = [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GMAIL_SENDER_ADDRESS",
            "CLIENT_SECRET",
            "PROJECT_ID",
            "GMAIL_APP_PASSWORD"
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")
            print("Some functionality may be limited.")
            
    except Exception as e:
        print(f"Error during startup: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup resources on shutdown."""
    try:
        # Close all WebSocket connections
        for task_id in list(manager.active_connections.keys()):
            await manager.close_all(task_id)
            
        # Cancel any running tasks
        await task_manager.cancel_all_tasks()
        
    except Exception as e:
        print(f"Error during shutdown: {e}")

# Initialize database
DB_PATH = os.getenv("THESEUS_DB_PATH", "data/papers.db")
db = PaperDatabase(DB_PATH)

# Models endpoints
@app.get("/api/models", response_model=List[Model])
async def get_models():
    """Get all registered models."""
    try:
        db_models = db.get_models()
        # Convert DB models to API models
        models = []
        for model in db_models:
            provider = next(p for p in db.get_model_providers() if p["id"] == model["provider_id"])
            models.append(Model(
                id=str(model["id"]),
                name=model["name"],
                provider=provider["name"]
            ))
        return models
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/models", response_model=Model, status_code=201)
async def create_model(model: ModelCreate):
    """Create a new model."""
    try:
        # Validate provider exists
        providers = db.get_model_providers()
        if not any(p["id"] == model.provider_id for p in providers):
            raise HTTPException(status_code=400, detail="Invalid provider_id")
        
        # Add model to database
        db.add_model(
            provider_id=model.provider_id,
            name=model.name,
            config_json=json.dumps(model.config_json)
        )
        
        # Get the created model
        created = db.get_models()[-1]  # Get last inserted model
        provider = next(p for p in providers if p["id"] == created["provider_id"])
        
        return Model(
            id=str(created["id"]),
            name=created["name"],
            provider=provider["name"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/models/{model_id}")
async def delete_model(model_id: int):
    """Delete a model by ID."""
    try:
        db.delete_model(model_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Papers endpoints
@app.get("/api/papers", response_model=PaginatedResponse)
async def get_papers(
    page: int = Query(1, gt=0),
    score: Optional[float] = None,
    sort_field: Optional[str] = Query(None, enum=['date', 'score']),
    sort_direction: Optional[str] = Query(None, enum=['asc', 'desc']),
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """Get paginated papers with filtering and sorting."""
    try:
        # Get all papers first
        papers = db.fetch_all_papers()
        filtered_papers = []
        
        # Convert to Paper objects and apply filters
        for p in papers:
            # Skip if doesn't meet score threshold
            if score is not None and p['score'] < score:
                continue
                
            # Skip if outside date range
            if from_date and p['date'] < from_date:
                continue
            if to_date and p['date'] > to_date:
                continue
                
            # Skip if doesn't match search term
            if search:
                search_lower = search.lower()
                if (search_lower not in p['title'].lower() and 
                    search_lower not in p['abstract'].lower()):
                    continue
            
            # Add to filtered list
            filtered_papers.append(Paper(
                id=p['id'],
                title=p['title'],
                abstract=p['abstract'],
                score=p['score'],
                date=p['date'],
                url=p['url']
            ))
        
        # Apply sorting
        if sort_field:
            reverse = sort_direction == 'desc'
            filtered_papers.sort(
                key=lambda x: getattr(x, sort_field),
                reverse=reverse
            )
        
        # Apply pagination
        page_size = 10
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_papers = filtered_papers[start_idx:end_idx]
        
        return PaginatedResponse(
            items=page_papers,
            nextPage=page + 1 if end_idx < len(filtered_papers) else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Settings endpoints
@app.get("/api/settings/orchestration", response_model=OrchestrationConfig)
async def get_orchestration_config_api():
    """Get orchestration configuration."""
    try:
        config_json = db.get_setting("orchestration")
        if config_json:
            return OrchestrationConfig.parse_raw(config_json)
        # Return default OrchestrationConfig if not found in DB
        return OrchestrationConfig(
            embedding_model=ModelConfig(model_name='Alibaba-NLP/gte-modernbert-base', model_type='sentence-transformers', trust_remote_code=True),
            judge_model=ModelConfig(model_name='phi4-mini:3.8b-q8_0', model_type='ollama', max_new_tokens=512, temperature=0.1, num_ctx=4096),
            content_extraction_model=ModelConfig(model_name='gemma3:27b-it-qat', model_type='ollama', max_new_tokens=4096, temperature=0.1, num_ctx=131072),
            newsletter_sections_model=ModelConfig(model_name='gemma3:27b-it-qat', model_type='ollama', max_new_tokens=4096, temperature=0.1, num_ctx=131072),
            newsletter_intro_model=ModelConfig(model_name='gemini-2.0-flash', model_type='gemini', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting orchestration config: {str(e)}")

@app.put("/api/settings/orchestration")
async def update_orchestration_config_api(config: OrchestrationConfig):
    """Update orchestration configuration."""
    try:
        db.set_setting("orchestration", config.json())
        return {"status": "success", "message": "Orchestration configuration updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating orchestration config: {str(e)}")

@app.get("/api/settings/arxiv-categories", response_model=ArxivCategoriesConfig)
async def get_arxiv_categories_api():
    """Get ArXiv search categories."""
    try:
        settings_json = db.get_setting("arxiv_search_categories")
        if settings_json:
            return ArxivCategoriesConfig.parse_raw(settings_json)
        # Return default ArXivCategoriesConfig if not found in DB
        return ArxivCategoriesConfig(
            main_category="cs",
            filter_categories=["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ArXiv categories: {str(e)}")

@app.put("/api/settings/arxiv-categories")
async def update_arxiv_categories_api(config: ArxivCategoriesConfig):
    """Update ArXiv search categories."""
    try:
        db.set_setting("arxiv_search_categories", config.json())
        return {"status": "success", "message": "ArXiv categories updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating ArXiv categories: {str(e)}")

@app.get("/api/model-providers", response_model=List[ModelProvider])
async def get_model_providers_api():
    """Get all available model providers."""
    try:
        providers_data = db.get_model_providers() # This returns a list of dicts like [{'id': 1, 'name': 'ollama'}]
        return [ModelProvider(id=p['id'], name=p['name']) for p in providers_data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting model providers: {str(e)}")

@app.get("/api/settings/research-interests")
async def get_research_interests():
    """Get research interests."""
    try:
        interests = db.get_setting("research_interests")
        if not interests:
            return {"interests": ""}
        return {"interests": interests}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/settings/research-interests")
async def update_research_interests(interests: Dict[str, str]):
    """Update research interests."""
    try:
        if "interests" not in interests:
            raise HTTPException(status_code=400, detail="Missing 'interests' field")
        db.set_setting("research_interests", interests["interests"])
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings/email-recipients", response_model=EmailRecipients)
async def get_email_recipients():
    """Get email recipients list."""
    try:
        recipients_list = db.get_email_recipients()
        return EmailRecipients(recipients=recipients_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/settings/email-recipients")
async def update_email_recipients(data: EmailRecipients):
    """Update email recipients list."""
    try:
        # Basic email validation (optional here if Pydantic model handles it, or keep for defense-in-depth)
        for email in data.recipients:
            if "@" not in email or "." not in email: # Basic check
                raise HTTPException(status_code=400, detail=f"Invalid email address: {email}")
        db.set_email_recipients(data.recipients)
        return {"status": "success", "message": "Email recipients updated successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings/visualizer-settings", response_model=VisualizerSettings)
async def get_visualizer_settings():
    """Get visualizer settings."""
    try:
        settings = db.get_visualizer_settings()
        if not settings:
            # Return default settings from the model
            return VisualizerSettings().dict()
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/send-test-email")
async def send_test_email():
    """Send a test email to configured recipients."""
    try:
        from .communication import GmailCommunication
        
        # Get email recipients
        recipients = db.get_email_recipients()
        if not recipients:
            raise HTTPException(status_code=400, detail="No email recipients configured")
            
        # Initialize email client
        gmail_sender = os.getenv("GMAIL_SENDER_ADDRESS")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        
        if not gmail_sender or not gmail_password:
            raise HTTPException(
                status_code=500,
                detail="Email credentials not configured"
            )
            
        comm = GmailCommunication(
            sender_address=gmail_sender,
            app_password=gmail_password,
            receiver_address=recipients
        )
        
        # Send test email
        test_content = """
        This is a test email from Theseus Insight.
        
        If you're receiving this, your email configuration is working correctly.
        
        Best regards,
        Theseus Insight Team
        """
        
        comm.compose_message(
            content=test_content,
            start_date=datetime.now().date(),
            end_date=datetime.now().date(),
            subject="Theseus Insight - Test Email"
        )
        comm.send_email()
        
        return {"status": "success", "message": "Test email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Runs endpoints
@app.get("/api/runs", response_model=PaginatedResponse)
async def get_runs(
    page: int = Query(1, gt=0),
    sort_field: Optional[str] = None,
    sort_direction: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """Get paginated list of runs."""
    try:
        # TODO: Implement proper pagination and filtering
        # For now, return all runs
        runs = []
        newsletters = db.fetch_all_newsletters()
        podcasts = db.fetch_all_podcasts()
        
        # Convert newsletters to runs
        for n in newsletters:
            runs.append(Run(
                id=n['id'],
                date=n['date_sent'],
                pipeline_type='newsletter',
                status='completed',  # Assuming all stored ones are completed
                duration=0.0,  # TODO: Add duration tracking
                artifact_path=f"newsletters/{n['id']}/content.md"
            ))
            
        # Convert podcasts to runs
        for p in podcasts:
            runs.append(Run(
                id=p['id'],
                date=p['date'],
                pipeline_type='podcast',
                status='completed',
                duration=0.0,
                artifact_path=f"podcasts/{p['id']}/audio.mp3"
            ))
            
        # Sort runs by date descending
        runs.sort(key=lambda x: x.date, reverse=True)
        
        # Basic pagination
        page_size = 10
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_runs = runs[start_idx:end_idx]
        
        return PaginatedResponse(
            items=page_runs,
            nextPage=page + 1 if end_idx < len(runs) else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/runs/{run_id}/artifact")
async def delete_run_artifact(run_id: int):
    """Delete the artifact associated with a run."""
    try:
        # First determine if this is a newsletter or podcast run
        newsletters = db.fetch_all_newsletters()
        podcasts = db.fetch_all_podcasts()
        
        # Check newsletters
        newsletter = next((n for n in newsletters if n['id'] == run_id), None)
        if newsletter:
            artifact_path = f"data/newsletters/{run_id}/content.md"
            if os.path.exists(artifact_path):
                os.remove(artifact_path)
                # Remove the directory if empty
                try:
                    os.rmdir(os.path.dirname(artifact_path))
                except OSError:
                    pass  # Directory not empty
            return {"status": "success"}
            
        # Check podcasts
        podcast = next((p for p in podcasts if p['id'] == run_id), None)
        if podcast:
            artifact_path = f"data/podcasts/{run_id}/audio.mp3"
            if os.path.exists(artifact_path):
                os.remove(artifact_path)
                # Remove the directory if empty
                try:
                    os.rmdir(os.path.dirname(artifact_path))
                except OSError:
                    pass  # Directory not empty
            return {"status": "success"}
            
        # If we get here, the run wasn't found
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Task status endpoints
@app.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get the current status of a task."""
    try:
        status = task_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """Get the result of a completed task."""
    try:
        task = task_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
        if task["status"] != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Task is not completed (current status: {task['status']})"
            )
            
        if not task.get("result"):
            raise HTTPException(status_code=404, detail="No result available for this task")
            
        return task["result"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/download/{file_type}")
async def download_task_artifact(task_id: str, file_type: str):
    """Download a task artifact (newsletter or podcast)."""
    try:
        task = task_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
        if task["status"] != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Task is not completed (current status: {task['status']})"
            )
            
        result = task.get("result")
        if not result:
            raise HTTPException(status_code=404, detail="No result available for this task")
            
        if task["type"] == "newsletter":
            if file_type != "markdown":
                raise HTTPException(status_code=400, detail="Only markdown format is available for newsletters")
                
            # Create a temporary markdown file
            output_path = f"data/temp/{task_id}/newsletter.md"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                f.write(result["newsletter_content"])
                
            return FileResponse(
                output_path,
                media_type="text/markdown",
                filename="newsletter.md"
            )
            
        elif task["type"] == "podcast":
            if file_type not in ["audio", "video"]:
                raise HTTPException(
                    status_code=400,
                    detail="Available formats for podcasts: audio, video"
                )
                
            # Get the appropriate file path
            if file_type == "audio":
                file_path = result["final_podcast_path"]
                media_type = "audio/mpeg"
                filename = "podcast.mp3"
            else:  # video
                if not result.get("visualizer_path"):
                    raise HTTPException(
                        status_code=404,
                        detail="No video visualization available for this podcast"
                    )
                file_path = result["visualizer_path"]
                media_type = "video/mp4"
                filename = "podcast.mp4"
                
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=404,
                    detail=f"Artifact file not found: {file_path}"
                )
                
            return FileResponse(
                file_path,
                media_type=media_type,
                filename=filename
            )
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown task type: {task['type']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Newsletter endpoints
@app.post("/api/newsletter/run")
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
        background_tasks.add_task(task_manager.run_newsletter_task, task_id)
        
        return {"taskId": task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Podcast endpoints
@app.post("/api/podcast/generate")
async def generate_podcast(
    background_tasks: BackgroundTasks,
    config: str = Form(...),
    intro_music_file: Optional[UploadFile] = File(None)
):
    """Start the podcast generation pipeline."""
    try:
        # Parse config
        config_dict = json.loads(config)
        if not isinstance(config_dict, dict):
            raise HTTPException(status_code=400, detail="Invalid config format")
            
        required_fields = ['scriptModel', 'ttsModel', 'addVisualization', 'urls']
        missing_fields = [f for f in required_fields if f not in config_dict]
        if missing_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        task_id = str(uuid.uuid4())
        
        # Save intro music file if provided
        if intro_music_file:
            file_path = f"data/temp/{task_id}/intro_music{os.path.splitext(intro_music_file.filename)[1]}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(await intro_music_file.read())
            config_dict["intro_music_path"] = file_path
        
        # Create and start task
        await task_manager.create_task(
            task_id=task_id,
            task_type="podcast",
            config=config_dict
        )
        background_tasks.add_task(task_manager.run_podcast_task, task_id)
        
        return {"taskId": task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Enhance the WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        """Connect a new WebSocket client."""
        try:
            await websocket.accept()
            if task_id not in self.active_connections:
                self.active_connections[task_id] = []
            self.active_connections[task_id].append(websocket)
        except Exception as e:
            print(f"Error connecting WebSocket: {e}")
            try:
                await websocket.close(code=4000, reason=str(e))
            except:
                pass
            raise

    def disconnect(self, task_id: str, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        try:
            if task_id in self.active_connections:
                if websocket in self.active_connections[task_id]:
                    self.active_connections[task_id].remove(websocket)
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
        except Exception as e:
            print(f"Error disconnecting WebSocket: {e}")

    async def broadcast_status(self, task_id: str, status: RunStatus):
        """Broadcast status to all connected clients for a task."""
        if task_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(status.dict())
                except WebSocketDisconnect:
                    dead_connections.append(connection)
                except Exception as e:
                    print(f"Error broadcasting to WebSocket: {e}")
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for dead in dead_connections:
                self.disconnect(task_id, dead)

    async def close_all(self, task_id: str):
        """Close all connections for a task."""
        if task_id in self.active_connections:
            for connection in self.active_connections[task_id]:
                try:
                    await connection.close(code=1000)
                except:
                    pass
            del self.active_connections[task_id]

manager = ConnectionManager()

# Update WebSocket endpoints
@app.websocket("/ws/newsletter/{task_id}")
async def newsletter_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for newsletter generation status updates."""
    status_queue = None
    try:
        await manager.connect(task_id, websocket)
        
        # Subscribe to task updates
        status_queue = await task_manager.subscribe_to_updates(task_id)
        
        while True:
            # Wait for status updates
            status = await status_queue.get()
            await websocket.send_json(status.dict())
            
            # If task is completed or failed, close connection
            if status.overallStatus in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                break
                
    except WebSocketDisconnect:
        pass
    except ValueError as e:
        try:
            await websocket.close(code=4004, reason=str(e))
        except:
            pass
    except Exception as e:
        try:
            await websocket.close(code=4000, reason=str(e))
        except:
            pass
    finally:
        if status_queue:
            await task_manager.unsubscribe_from_updates(task_id, status_queue)
        manager.disconnect(task_id, websocket)

@app.websocket("/ws/podcast/{task_id}")
async def podcast_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for podcast generation status updates."""
    status_queue = None
    try:
        await manager.connect(task_id, websocket)
        
        # Subscribe to task updates
        status_queue = await task_manager.subscribe_to_updates(task_id)
        
        while True:
            # Wait for status updates
            status = await status_queue.get()
            await websocket.send_json(status.dict())
            
            # If task is completed or failed, close connection
            if status.overallStatus in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                break
                
    except WebSocketDisconnect:
        pass
    except ValueError as e:
        try:
            await websocket.close(code=4004, reason=str(e))
        except:
            pass
    except Exception as e:
        try:
            await websocket.close(code=4000, reason=str(e))
        except:
            pass
    finally:
        if status_queue:
            await task_manager.unsubscribe_from_updates(task_id, status_queue)
        manager.disconnect(task_id, websocket) 