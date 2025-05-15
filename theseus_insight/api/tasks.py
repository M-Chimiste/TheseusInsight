from typing import Dict, Optional, List
import asyncio
import json
import os
from datetime import datetime
from enum import Enum
from .models import RunStatus, NodeStatus
from ..theseus_insight import TheseusInsight
from ..podcast.generator import PodcastGenerator
from ..data_model import PaperDatabase

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.status_updates: Dict[str, List[asyncio.Queue]] = {}
        self.db = PaperDatabase(os.getenv("THESEUS_DB_PATH", "data/papers.db"))
        
    async def create_task(self, task_id: str, task_type: str, config: dict):
        """Create a new task."""
        self.tasks[task_id] = {
            "type": task_type,
            "config": config,
            "status": TaskStatus.PENDING,
            "start_time": datetime.now().isoformat(),
            "error": None,
            "result": None
        }
        self.status_updates[task_id] = []
        
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get the current status of a task."""
        return self.tasks.get(task_id)
        
    async def subscribe_to_updates(self, task_id: str) -> asyncio.Queue:
        """Subscribe to status updates for a task."""
        if task_id not in self.status_updates:
            raise ValueError(f"Task {task_id} not found")
            
        queue = asyncio.Queue()
        self.status_updates[task_id].append(queue)
        return queue
        
    async def unsubscribe_from_updates(self, task_id: str, queue: asyncio.Queue):
        """Unsubscribe from status updates."""
        if task_id in self.status_updates and queue in self.status_updates[task_id]:
            self.status_updates[task_id].remove(queue)
            
    async def update_task_status(self, task_id: str, status: TaskStatus, message: str = "", progress: float = 0, error: str = None):
        """Update task status and notify subscribers."""
        if task_id not in self.tasks:
            raise ValueError(f"Task {task_id} not found")
            
        self.tasks[task_id]["status"] = status
        if error:
            self.tasks[task_id]["error"] = error
            
        # Create status update
        timestamp = datetime.now().isoformat()
        status_obj = RunStatus(
            taskId=task_id,
            nodes=[
                NodeStatus(
                    nodeId="main",
                    status=status,
                    message=message,
                    progress=progress if status == TaskStatus.PROCESSING else (100 if status == TaskStatus.COMPLETED else 0),
                    timestamp=timestamp
                )
            ],
            overallStatus=status,
            error=error
        )
        
        # Notify all subscribers
        if task_id in self.status_updates:
            for queue in self.status_updates[task_id]:
                await queue.put(status_obj)

    def _progress_callback(self, task_id: str):
        """Create a progress callback function for TheseusInsight."""
        async def callback(stage: str, progress: float, message: str = ""):
            await self.update_task_status(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                message=f"{stage}: {message}",
                progress=progress
            )
        return callback

    async def run_newsletter_task(self, task_id: str):
        """Run the newsletter generation task."""
        try:
            config = self.tasks[task_id]["config"]
            
            # Extract configuration
            date_range = config.get("dateRange", {})
            start_date = date_range.get("from", None)
            end_date = date_range.get("to", None)
            
            # Initialize TheseusInsight with the configuration
            insight = TheseusInsight(
                start_date=start_date,
                end_date=end_date,
                judge_model_config={
                    "model_name": config["judgeModel"],
                    "model_type": "openai",  # You might want to make this configurable
                    "max_new_tokens": 1024,
                    "temperature": 0.1
                },
                newsletter_model_config={
                    "model_name": config["newsletterModel"],
                    "model_type": "openai",  # You might want to make this configurable
                    "max_new_tokens": 1024,
                    "temperature": 0.1
                },
                generate_podcast=False,  # We handle podcast generation separately
                data_path=os.getenv("THESEUS_DB_PATH", "data/papers.db"),
                generate_email=False  # We'll handle email sending separately
            )
            
            # Run the pipeline with progress tracking
            await self.update_task_status(task_id, TaskStatus.PROCESSING, "Starting newsletter generation")
            
            # Create progress callback
            progress_callback = self._progress_callback(task_id)
            
            # Run the pipeline
            result = await asyncio.to_thread(
                insight.run,
                progress_callback=progress_callback
            )
            
            # Store the result
            self.tasks[task_id]["result"] = result
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                "Newsletter generated successfully",
                progress=100
            )
            
        except Exception as e:
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                "Newsletter generation failed",
                error=str(e)
            )
            raise
            
    async def run_podcast_task(self, task_id: str):
        """Run the podcast generation task."""
        try:
            config = self.tasks[task_id]["config"]
            
            # Initialize podcast generator
            podcast_gen = PodcastGenerator(
                text_model={
                    "model_name": config["scriptModel"],
                    "model_type": "openai",  # You might want to make this configurable
                    "max_new_tokens": 1024,
                    "temperature": 0.1
                },
                tts_provider=config.get("ttsProvider", "openai"),
                speaker_1_voice=config.get("speaker1Voice", "sage"),
                speaker_2_voice=config.get("speaker2Voice", "ash"),
                speaker_1_speed=config.get("speaker1Speed", 1.0),
                speaker_2_speed=config.get("speaker2Speed", 1.0),
                intro_music_path=config.get("intro_music_path", None),
                verbose=True
            )
            
            await self.update_task_status(task_id, TaskStatus.PROCESSING, "Starting podcast generation")
            
            # Get URLs from config
            urls = config.get("urls", [])
            if not urls:
                raise ValueError("No URLs provided for podcast generation")
            
            # Create output directories
            output_dir = f"data/podcasts/{task_id}"
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate podcast with progress tracking
            def progress_callback(stage: str, progress: float):
                asyncio.create_task(
                    self.update_task_status(
                        task_id,
                        TaskStatus.PROCESSING,
                        f"{stage}",
                        progress=progress
                    )
                )
            
            # Run podcast generation
            result = await asyncio.to_thread(
                podcast_gen.generate_podcast,
                pdf_paths=urls,
                output_dir=output_dir,
                prefix=f"podcast_{task_id}",
                final_filename=f"podcast_{task_id}_final",
                visualizer=config.get("addVisualization", False),
                progress_callback=progress_callback
            )
            
            # Store the result
            self.tasks[task_id]["result"] = result
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                "Podcast generated successfully",
                progress=100
            )
            
        except Exception as e:
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                "Podcast generation failed",
                error=str(e)
            )
            raise

# Create global task manager instance
task_manager = TaskManager() 