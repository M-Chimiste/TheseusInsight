from typing import Dict, Optional, List
import asyncio
import os
from datetime import datetime
from enum import Enum
from .models import RunStatus, NodeStatus
from ..theseus_insight import TheseusInsight
from ..podcast.generator import PodcastGenerator
from ..data_model import PaperDatabase, Logs

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManager:
    def __init__(self):
        self.status_updates: Dict[str, List[asyncio.Queue]] = {}
        self.db = PaperDatabase(os.getenv("THESEUS_DB_PATH", "data/papers.db"))
        
        # Mark any interrupted tasks as failed on startup
        interrupted_count = self.db.mark_interrupted_tasks_as_failed()
        
        # Clean up old tasks on startup
        self.db.cleanup_old_tasks(days_old=7)
        
    async def cleanup(self):
        """Clean up all asyncio resources."""
        for task_id, queues in self.status_updates.items():
            for queue in queues:
                # Put a sentinel value to unblock any waiting consumers
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
        self.status_updates.clear()
        
    async def create_task(self, task_id: str, task_type: str, config: dict):
        """Create a new task."""
        start_time = datetime.now().isoformat()
        
        # Store task in database
        self.db.insert_task(
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING.value,
            config=config,
            start_time=start_time,
            progress=0,
            current_step="initializing",
            message="Task created"
        )
        
        # Initialize WebSocket subscriptions
        self.status_updates[task_id] = []
        
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get the current status of a task."""
        return self.db.get_task(task_id)
        
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
            
    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        message: str = "",
        progress: float = 0,
        error: str | None = None,
        current_step: str | None = None,
        result: dict | None = None,
    ) -> None:
        """Update task status and notify subscribers."""
        # Check if task exists in database
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Calculate final progress based on status
        final_progress = progress if status == TaskStatus.PROCESSING else (100 if status == TaskStatus.COMPLETED else 0)
        
        # Update task in database
        end_time = datetime.now().isoformat() if status in [TaskStatus.COMPLETED, TaskStatus.FAILED] else None
        self.db.update_task_status(
            task_id=task_id,
            status=status.value,
            progress=final_progress,
            current_step=current_step,
            message=message,
            error=error,
            result=result,
            end_time=end_time
        )
        
        # Create status update for WebSocket clients
        timestamp = datetime.now().isoformat()
        status_obj = RunStatus(
            taskId=task_id,
            nodes=[
                NodeStatus(
                    nodeId="main",
                    status=status,
                    message=message,
                    progress=final_progress,
                    timestamp=timestamp,
                )
            ],
            overallStatus=status,
            currentStep=current_step,
            progress=final_progress,
            message=message,
            result=result,
            error=error,
        )
        
        # Log to the logs table as well
        final_status = status_obj.overallStatus
        log = Logs(task_id=task_id, 
                   status=final_status, 
                   datetime_run=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self.db.insert_log(log)
        
        # Notify all subscribers
        if task_id in self.status_updates:
            for queue in self.status_updates[task_id]:
                await queue.put(status_obj)
                
        # Clean up queues for completed/failed tasks
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            if task_id in self.status_updates:
                del self.status_updates[task_id]

    def _progress_callback(self, task_id: str):
        """Create a progress callback function for TheseusInsight."""
        loop = asyncio.get_event_loop()

        def callback(stage: str, progress: float, message: str = ""):
            coro = self.update_task_status(
                task_id=task_id,
                status=TaskStatus.PROCESSING,
                message=f"{stage}: {message}",
                progress=progress,
                current_step=stage
            )
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, loop)
            else:
                # This case might occur if the main loop is stopped or not accessible.
                # For robustness, you could log this or handle it differently.
                # For now, we attempt to run it in a new loop, though this has implications.
                try:
                    asyncio.run(coro) # Fallback, but be cautious with this approach.
                except RuntimeError as e:
                    print(f"RuntimeError in progress_callback fallback: {e}. Status update for '{stage}' might be lost.")
        return callback

    async def run_newsletter_task(self, task_id: str):
        """Run the newsletter generation task."""
        try:
            task = self.db.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            config = task["config"]
            email_recipients = config.get("emailRecipients", None)
            research_interests_override = config.get("researchInterests", None)
            orchestration_config = self.db.get_setting("orchestration")
            if not orchestration_config:
                orchestration_config = "config/orchestration.json"
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
                generate_podcast=False,  # We handle podcast generation separately for now
                data_path=self.db.path,
                generate_email=True,
                receiver_address_override=email_recipients,
                research_interests_override=research_interests_override,
                orchestration_config=orchestration_config
            )
            
            # Run the pipeline with progress tracking
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Starting newsletter generation",
                current_step="initializing",
            )
            
            # Create progress callback
            progress_callback = self._progress_callback(task_id)
            
            # Run the pipeline
            result = await asyncio.to_thread(
                insight.run,
                progress_callback=progress_callback
            )
            
            # Result will be stored via update_task_status call
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                "Newsletter generated successfully",
                progress=100,
                current_step="newsletter_complete",
                result=result,
            )
            
        except Exception as e:
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                "Newsletter generation failed",
                error=str(e),
                current_step="newsletter_failed",
            )
            raise
            
    async def run_podcast_task(self, task_id: str):
        """Run the podcast generation task."""
        try:
            task = self.db.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            config = task["config"]
            
            # Initialize podcast generator
            # The text_model parameter expects the entire model configuration dictionary.
            # The key for this dictionary in the config is "podcast_model_config".
            podcast_model_configuration = config.get("podcast_model_config")
            if not podcast_model_configuration:
                raise ValueError("Podcast model configuration (podcast_model_config) is missing from task config.")

            podcast_gen = PodcastGenerator(
                text_model=podcast_model_configuration, # Use the correct key here
                tts_provider=config.get("tts_model_config", {}).get("tts_provider", "openai"),
                speaker_1_voice=config.get("tts_model_config", {}).get("speaker_1_voice", "sage"),
                speaker_2_voice=config.get("tts_model_config", {}).get("speaker_2_voice", "ash"),
                speaker_1_speed=config.get("tts_model_config", {}).get("speaker_1_speed", 1.0),
                speaker_2_speed=config.get("tts_model_config", {}).get("speaker_2_speed", 1.0),
                intro_music_path=config.get("intro_music_path", None),
                verbose=config.get("verbose", True) # Added verbose from config
            )
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Starting podcast generation",
                current_step="podcast_init",
            )
            
            # Get input sources from config
            input_type = config.get("input_type") # Should be present, validated by Pydantic model
            if not input_type: # Defensive check
                raise ValueError("input_type is missing from task config.")
                
            urls_to_process = config.get("urls", [])
            input_pdf_paths = config.get("input_pdf_paths", [])

            final_input_paths = []
            if input_type == "URLs": # Matches what api_client sends
                if not urls_to_process:
                    # It's valid to have URLs type with no URLs yet, user might be about to input them
                    # or it's an error if pipeline starts. For now, assume it's an error if empty at execution.
                    raise ValueError("No URLs provided for podcast generation when input_type is 'URLs'.")
                final_input_paths = urls_to_process
            elif input_type == "pdfs": # Matches what api_client sends
                if not input_pdf_paths:
                    raise ValueError("No PDF paths provided for podcast generation when input_type is 'pdfs'.")
                final_input_paths = input_pdf_paths
            else:
                # This case should ideally not be reached if PodcastGenerationParams validates input_type
                raise ValueError(f"Unsupported input_type for podcast received in task: {input_type}")
            
            # Create output directories
            # Use task_id in output_dir_base for better organization as done in main.py
            output_dir_base = config.get("output_dir_base", "data/podcasts")
            output_dir = os.path.join(output_dir_base, task_id) 
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate podcast with progress tracking
            # Ensure the progress_callback in PodcastGenerator is compatible or adapt here
            # For now, assuming PodcastGenerator.generate_podcast uses a simple callback structure if any.
            # The callback here is for the TaskManager, not directly for PodcastGenerator stages if it has finer-grained ones.

            visualizer_settings = config.get("visualizer_settings")
            create_visualization = config.get("create_visualization", False)
            
            # Run podcast generation
            # The generate_podcast method in the stub takes pdf_paths. 
            # We should ensure it can handle URLs or pre-processed PDF paths based on input_type.
            # For now, passing final_input_paths which could be URLs or local PDF paths.
            # PodcastGenerator needs to handle this logic internally.
            result = await asyncio.to_thread(
                podcast_gen.generate_podcast,
                pdf_paths=final_input_paths, # This is now a list of URLs or local PDF paths
                output_dir=output_dir,
                prefix=f"podcast_{task_id}", 
                final_filename=f"podcast_{task_id}_final",
                visualizer=create_visualization,
                # Pass specific visualizer settings if available and visualizer is True
                **(visualizer_settings if create_visualization and visualizer_settings else {}),
                progress_callback=self._progress_callback(task_id) # If PodcastGenerator takes a callback
            )
            
            # Result will be stored via update_task_status call
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                "Podcast generated successfully",
                progress=100,
                current_step="podcast_complete",
                result=result,
            )
            
        except Exception as e:
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                "Podcast generation failed",
                error=str(e),
                current_step="podcast_failed",
            )
            raise

    async def run_visualizer_task(self, task_id: str):
        """Run the audio visualization task."""
        try:
            task = self.db.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            config = task["config"]
            audio_file_path = config.get("audio_file_path")
            visualizer_params_dict = config.get("visualizer_params")
            output_dir_base = config.get("output_dir_base", "data/visualizations")
            
            if not audio_file_path or not os.path.exists(audio_file_path):
                raise ValueError(f"Audio file not found at path: {audio_file_path}")
            if not visualizer_params_dict:
                raise ValueError("Visualizer parameters are missing from task config.")

            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Starting visualization generation",
                current_step="visualizer_init",
            )

            output_dir = os.path.join(output_dir_base, task_id)
            os.makedirs(output_dir, exist_ok=True)
            
            final_video_filename = f"visualization_{task_id}.mp4"
            final_video_path = os.path.join(output_dir, final_video_filename)

            # Import locally to avoid circular dependencies if any, and keep generator specific
            from ..podcast.generator import generate_visualizer_video

            # Convert visualizer_params_dict to appropriate arguments for generate_visualizer_video
            # The generate_visualizer_video function expects individual arguments.
            vis_params = {
                "audio_filepath": audio_file_path,
                "output_filepath": final_video_path,
                "resolution": (visualizer_params_dict.get('resolution_width', 1920), visualizer_params_dict.get('resolution_height', 1080)),
                "fps": visualizer_params_dict.get('fps', 30),
                "matrix_count": visualizer_params_dict.get('matrix_count', 150),
                "matrix_head_color": visualizer_params_dict.get('matrix_head_color', "#e0ffe7"),
                "matrix_tail_color": visualizer_params_dict.get('matrix_tail_color', "#00b000"),
                "matrix_char_size": visualizer_params_dict.get('matrix_char_size', 24),
                "head_step_time": visualizer_params_dict.get('head_step_time', 0.3),
                "random_x_jitter": visualizer_params_dict.get('random_x_jitter', 3.0),
                "fade_time": visualizer_params_dict.get('fade_time', 3.0),
                "head_glow_passes": visualizer_params_dict.get('head_glow_passes', 3),
                "head_glow_alpha_decay": visualizer_params_dict.get('head_glow_alpha_decay', 50),
                "head_spawn_delay_range": (
                    visualizer_params_dict.get('head_spawn_delay_range_min', 1.0),
                    visualizer_params_dict.get('head_spawn_delay_range_max', 3.0)
                ),
                "head_saw_period": visualizer_params_dict.get('head_saw_period', 1.5),
                "line_width": visualizer_params_dict.get('line_width', 3),
                "wave_color": visualizer_params_dict.get('wave_color', "#d703fc"),
                "trail_colors": [
                    visualizer_params_dict.get('trail_color_1', "#fc03b6"),
                    visualizer_params_dict.get('trail_color_2', "#ba03fc"),
                    visualizer_params_dict.get('trail_color_3', "#ce6bf2")
                ],
                "glow_passes": visualizer_params_dict.get('glow_passes', 3),
                "glow_alpha_decay": visualizer_params_dict.get('glow_alpha_decay', 40),
                "font_path": visualizer_params_dict.get('font_path', "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc")
            }
            
            # Progress callback for generate_visualizer_video if it supports it
            # For now, just running it in a thread.
            await asyncio.to_thread(generate_visualizer_video, **vis_params)

            result = {
                "visualizer_file": final_video_path # Ensure this key matches what main.py expects for video downloads
            }
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                "Visualization generated successfully",
                progress=100,
                current_step="visualizer_complete",
                result=result,
            )

        except Exception as e:
            import traceback
            error_details = f"Error in visualizer task: {str(e)}\n{traceback.format_exc()}"
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                "Visualization generation failed",
                error=error_details,
                current_step="visualizer_failed",
            )
            print(error_details) # Log to server console
            raise

# Create global task manager instance
task_manager = TaskManager() 