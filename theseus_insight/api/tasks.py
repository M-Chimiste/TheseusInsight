from typing import Dict, Optional, List
import asyncio
import os
from datetime import datetime
from enum import Enum
from .models import RunStatus, NodeStatus
from ..theseus_insight import TheseusInsight
from ..podcast.generator import PodcastGenerator
from ..data_model import PaperDatabase, Logs
from ..utils.summary_generator import generate_short_summary, extract_key_themes, enhance_summary_with_context
import json

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManager:
    def __init__(self):
        self.status_updates: Dict[str, List[asyncio.Queue]] = {}
        self.db = PaperDatabase(os.getenv("DATABASE_URL", "data/theseus.db"))

        # Queues and workers for task processing
        # general_task_queue handles newsletter/podcast/etc.
        # visualizer_queue allows a visualizer task to run concurrently
        self.general_task_queue: asyncio.Queue = asyncio.Queue()
        self.visualizer_queue: asyncio.Queue = asyncio.Queue()
        self.general_worker_task: Optional[asyncio.Task] = None
        self.visualizer_worker_task: Optional[asyncio.Task] = None

        # Mark any interrupted tasks as failed on startup
        self.db.mark_interrupted_tasks_as_failed()

        # Clean up old tasks on startup
        self.db.cleanup_old_tasks(days_old=7)

    async def start_worker(self) -> None:
        """Start the background workers that process queued tasks."""
        if self.general_worker_task is None or self.general_worker_task.done():
            self.general_worker_task = asyncio.create_task(self._worker(self.general_task_queue))
        if self.visualizer_worker_task is None or self.visualizer_worker_task.done():
            self.visualizer_worker_task = asyncio.create_task(self._worker(self.visualizer_queue))

    async def stop_worker(self) -> None:
        """Stop the background workers gracefully."""
        if self.general_worker_task:
            await self.general_task_queue.put(None)
            await self.general_worker_task
            self.general_worker_task = None
        if self.visualizer_worker_task:
            await self.visualizer_queue.put(None)
            await self.visualizer_worker_task
            self.visualizer_worker_task = None

    async def _worker(self, queue: asyncio.Queue) -> None:
        """Continuously process tasks from the given queue."""
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            func, task_id = item
            print(f"DEBUG: Worker processing task {task_id} with function {func.__name__}")
            try:
                await func(task_id)
                print(f"DEBUG: Worker completed task {task_id}")
            except Exception as e:
                print(f"DEBUG: Worker failed task {task_id}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                queue.task_done()

    async def enqueue_task(self, func, task_id: str, visualizer: bool = False) -> None:
        """Add a new task to the appropriate processing queue."""
        print(f"DEBUG: Enqueuing task {task_id} with function {func.__name__}")
        queue = self.visualizer_queue if visualizer or func == self.run_visualizer_task else self.general_task_queue
        await queue.put((func, task_id))
        print(f"DEBUG: Task {task_id} enqueued successfully")
        
    async def cleanup(self):
        """Clean up all asyncio resources."""
        # Stop worker processing
        await self.stop_worker()

        # First, notify all waiting consumers to exit
        for task_id, queues in self.status_updates.items():
            for queue in queues:
                # Put a sentinel value to unblock any waiting consumers
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass
        
        # Give a moment for consumers to process the sentinel values
        await asyncio.sleep(0.1)
        
        # Now properly drain all queues to release semaphores
        for task_id, queues in self.status_updates.items():
            for queue in queues:
                # Drain all remaining items from the queue
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                
                # For Python 3.9+, try to close the queue
                if hasattr(queue, '_close'):
                    try:
                        queue._close()
                    except Exception:
                        pass
                # For older Python versions, we rely on draining the queue
                # and letting garbage collection handle the cleanup
        
        self.status_updates.clear()
        
    async def create_task(self, task_id: str, task_type: str, config: dict):
        """Create a new task."""
        print(f"DEBUG: Creating task {task_id} of type {task_type}")
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
        print(f"DEBUG: Task {task_id} created and initialized in status_updates")
        
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get the current status of a task."""
        return self.db.get_task(task_id)
        
    async def subscribe_to_updates(self, task_id: str) -> asyncio.Queue:
        """Subscribe to status updates for a task."""
        print(f"DEBUG: Attempting to subscribe to task {task_id}")
        print(f"DEBUG: Current status_updates keys: {list(self.status_updates.keys())}")
        if task_id not in self.status_updates:
            print(f"DEBUG: Task {task_id} not found in status_updates")
            raise ValueError(f"Task {task_id} not found")
            
        queue = asyncio.Queue()
        self.status_updates[task_id].append(queue)
        print(f"DEBUG: Successfully subscribed to task {task_id}, queue count: {len(self.status_updates[task_id])}")
        return queue
        
    async def unsubscribe_from_updates(self, task_id: str, queue: asyncio.Queue):
        """Unsubscribe from status updates."""
        if task_id in self.status_updates and queue in self.status_updates[task_id]:
            self.status_updates[task_id].remove(queue)
            
            # Drain the queue to release semaphores
            while not queue.empty():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            
            # For Python 3.9+, try to close the queue
            if hasattr(queue, '_close'):
                try:
                    queue._close()
                except Exception:
                    pass
            
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
                    status=status.value,
                    message=message,
                    progress=final_progress,
                    timestamp=timestamp,
                )
            ],
            overallStatus=status.value,
            currentStep=current_step,
            progress=final_progress,
            message=message,
            result=result,
            error=error,
        )
        
        # Debug logging for completion status
        if status == TaskStatus.COMPLETED:
            print(f"DEBUG: Sending completion status for {task_id}")
            print(f"  overallStatus: {status_obj.overallStatus}")
            print(f"  result keys: {list(result.keys()) if result else 'None'}")
            print(f"  message: {message[:100]}..." if message else "No message")
        
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
                
        # Clean up queues for completed/failed tasks (with delay to ensure message delivery)
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            if task_id in self.status_updates:
                print(f"DEBUG: Scheduling cleanup for completed/failed task {task_id}")
                
                # Schedule cleanup after a short delay to ensure WebSocket message delivery
                async def delayed_cleanup():
                    await asyncio.sleep(0.5)  # Give WebSocket time to send the message
                    if task_id in self.status_updates:
                        print(f"DEBUG: Cleaning up status_updates for completed/failed task {task_id}")
                        for queue in self.status_updates[task_id]:
                            # Notify any waiting websocket handlers to exit
                            try:
                                queue.put_nowait(None)
                            except asyncio.QueueFull:
                                pass

                        # Allow consumers to process the sentinel values
                        await asyncio.sleep(0.1)

                        for queue in self.status_updates[task_id]:
                            # Drain any remaining items
                            while not queue.empty():
                                try:
                                    queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    break

                            if hasattr(queue, '_close'):
                                try:
                                    queue._close()
                                except Exception:
                                    pass

                        del self.status_updates[task_id]
                        print(f"DEBUG: Removed task {task_id} from status_updates")
                
                # Schedule the cleanup to run in the background
                asyncio.create_task(delayed_cleanup())

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
                verbose=config.get("verbose", True), # Added verbose from config
                db_url=config.get("data_path", None)  # Pass the database URL
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
            error_msg = str(e)
            
            # Provide user-friendly error messages for common issues
            if ("timeout" in error_msg.lower() or 
                "deadline" in error_msg.lower() or 
                "504" in error_msg or
                "DeadlineExceeded" in error_msg):
                user_friendly_msg = (
                    "Podcast generation failed due to API timeout. "
                    "This is usually temporary - please try again in a few minutes. "
                    "If the issue persists, consider using a different model in the orchestration settings."
                )
            elif "api" in error_msg.lower() and ("key" in error_msg.lower() or "auth" in error_msg.lower()):
                user_friendly_msg = (
                    "Podcast generation failed due to API authentication issues. "
                    "Please check your API keys in the settings."
                )
            else:
                user_friendly_msg = f"Podcast generation failed: {error_msg}"
            
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                user_friendly_msg,
                error=error_msg,
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

    async def run_database_export_task(self, task_id: str):
        """Run the database export task with progress tracking."""
        try:
            from ..utils.db_migration.db_export import DatabaseExporter

            task = self.db.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Starting database export",
                progress=0,
                current_step="export_init",
            )

            export_dir = f"data/temp/{task_id}_export"
            os.makedirs(export_dir, exist_ok=True)

            exporter = DatabaseExporter(self.db.db_path, export_dir)

            loop = asyncio.get_event_loop()

            def progress_cb(pct: float, msg: str):
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        self.update_task_status(
                            task_id,
                            TaskStatus.PROCESSING,
                            msg,
                            progress=pct,
                            current_step="exporting",
                        ),
                        loop,
                    )

            result = await asyncio.to_thread(
                exporter.export_all,
                True,
                f"theseus_backup_{task_id}",
                progress_cb,
            )

            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                "Database export completed",
                progress=100,
                current_step="export_complete",
                result={"archive_path": result.get("archive")},
            )

        except Exception as e:
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                "Database export failed",
                error=str(e),
                current_step="export_failed",
            )
            raise

    async def run_database_import_task(self, task_id: str):
        """Run the database import task with progress tracking."""
        try:
            print(f"DEBUG: Starting database import task {task_id}")
            task = self.db.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            config = task["config"]
            
            from ..utils.db_migration.db_import import DatabaseImporter
            
            archive_path = config.get("archive_path")
            import_mode = config.get("import_mode", "merge")
            filename = config.get("filename", "unknown")
            
            print(f"DEBUG: Archive path: {archive_path}, Mode: {import_mode}, Filename: {filename}")
            
            if not archive_path or not os.path.exists(archive_path):
                raise ValueError(f"Archive file not found: {archive_path}")
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Starting database import of {filename}",
                current_step="import_init",
            )
            
            # Initialize importer
            print(f"DEBUG: Initializing DatabaseImporter with db_path: {self.db.db_path}")
            importer = DatabaseImporter(self.db.db_path)
            
            # Create progress callback that updates task status
            # Capture the event loop from the main thread before going to thread pool
            main_loop = asyncio.get_event_loop()
            
            # Determine progress mapping based on import mode
            # For overwrite: clearing takes 0-20%, import takes 20-100%
            # For merge: import takes 0-100%
            clearing_progress_range = (0, 20) if import_mode == "overwrite" else None
            import_progress_range = (20, 100) if import_mode == "overwrite" else (0, 100)
            
            def clearing_progress_callback(current: int, total: int, message: str):
                """Progress callback for the clearing phase (overwrite mode only)."""
                print(f"DEBUG: Clearing progress callback - {current}/{total}: {message}")
                if main_loop.is_running() and clearing_progress_range:
                    # Map clearing progress to 0-20%
                    raw_progress = (current / total) if total > 0 else 0
                    progress_percentage = clearing_progress_range[0] + (raw_progress * (clearing_progress_range[1] - clearing_progress_range[0]))
                    print(f"DEBUG: Calculated clearing progress: {progress_percentage}%")
                    asyncio.run_coroutine_threadsafe(
                        self.update_task_status(
                            task_id,
                            TaskStatus.PROCESSING,
                            message,
                            progress=progress_percentage,
                            current_step="clearing_data",
                        ),
                        main_loop
                    )
                else:
                    print("DEBUG: Main event loop not running or no clearing progress range, cannot send progress update")
            
            def import_progress_callback(current: int, total: int, message: str):
                """Progress callback for the import phase."""
                print(f"DEBUG: Import progress callback - {current}/{total}: {message}")
                if main_loop.is_running():
                    # Map import progress to appropriate range
                    raw_progress = (current / total) if total > 0 else 0
                    progress_percentage = import_progress_range[0] + (raw_progress * (import_progress_range[1] - import_progress_range[0]))
                    print(f"DEBUG: Calculated import progress: {progress_percentage}%")
                    asyncio.run_coroutine_threadsafe(
                        self.update_task_status(
                            task_id,
                            TaskStatus.PROCESSING,
                            message,
                            progress=progress_percentage,
                            current_step="importing",
                        ),
                        main_loop
                    )
                else:
                    print("DEBUG: Main event loop not running, cannot send progress update")
            
            skip_duplicates = import_mode == "merge"
            
            if import_mode == "overwrite":
                print("DEBUG: Running in overwrite mode, clearing database")
                await self.update_task_status(
                    task_id,
                    TaskStatus.PROCESSING,
                    "Clearing existing database (overwrite mode)",
                    progress=0,
                    current_step="clearing_data",
                )
                
                # Clear existing data (destructive) with progress tracking
                deletion_results = await asyncio.to_thread(
                    importer.clear_all_data,
                    clearing_progress_callback
                )
                print(f"Database cleared. Deleted records: {deletion_results}")
                
                # Update to import phase start
                await self.update_task_status(
                    task_id,
                    TaskStatus.PROCESSING,
                    "Database cleared. Starting import...",
                    progress=20,
                    current_step="starting_import",
                )
            
            # Import the data
            print(f"DEBUG: Starting import from archive, skip_duplicates: {skip_duplicates}")
            results = await asyncio.to_thread(
                importer.import_from_archive,
                archive_path,
                skip_duplicates,
                import_progress_callback
            )
            
            print(f"DEBUG: Import completed with results: {results}")
            
            # Prepare result summary
            total_imported = sum(r.get("imported", 0) for r in results.values() if isinstance(r, dict))
            total_skipped = sum(r.get("skipped", 0) for r in results.values() if isinstance(r, dict))
            total_errors = sum(r.get("errors", 0) for r in results.values() if isinstance(r, dict))
            
            mode_text = "merged" if import_mode == "merge" else "imported"
            message = f"Database {mode_text} successfully. "
            message += f"Imported: {total_imported}, Skipped: {total_skipped}, Errors: {total_errors}"
            
            if import_mode == "merge":
                message += ". Existing records were preserved."
            
            print(f"DEBUG: Final message: {message}")
            
            # Clean up temporary file
            try:
                os.remove(archive_path)
                print(f"DEBUG: Cleaned up temporary file: {archive_path}")
            except Exception as e:
                print(f"DEBUG: Could not clean up temporary file: {e}")
                pass  # Don't fail the task if cleanup fails
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                message,
                progress=100,
                current_step="import_complete",
                result={
                    "import_stats": results,
                    "total_imported": total_imported,
                    "total_skipped": total_skipped,
                    "total_errors": total_errors,
                    "import_mode": import_mode
                },
            )
            
            print(f"DEBUG: Database import task {task_id} completed successfully")
            
        except Exception as e:
            print(f"DEBUG: Error in database import task {task_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Clean up temporary file on error
            try:
                config = task.get("config", {}) if 'task' in locals() else {}
                archive_path = config.get("archive_path")
                if archive_path and os.path.exists(archive_path):
                    os.remove(archive_path)
            except Exception:
                pass
                
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                "Database import failed",
                error=str(e),
                current_step="import_failed",
            )
            raise

    async def run_research_agent_task(self, task_id: str):
        """Run the enhanced research agent task with LangGraph workflow and streaming support."""
        try:
            print(f"DEBUG: Starting enhanced research agent task {task_id}")
            task = self.db.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            config = task["config"]
            research_question = config.get("research_question")
            num_papers_target = config.get("num_papers_target", 5)
            max_steps = config.get("max_steps", 10)
            enable_pdf_download = config.get("enable_pdf_download", True)
            conversation_history = config.get("conversation_history", [])
            
            print(f"DEBUG: Research question: {research_question}")
            print(f"DEBUG: Config: {config}")
            
            if not research_question:
                raise ValueError("Research question is required")
            
            print(f"DEBUG: Updating task status to PROCESSING for {task_id}")
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Starting enhanced literature review: {research_question}",
                progress=5,
                current_step="initializing_langgraph_agent",
            )
            print(f"DEBUG: Task status updated to PROCESSING for {task_id}")
            
            # Import enhanced research agent (LangGraph workflow)
            print(f"DEBUG: Importing enhanced research agent for {task_id}")
            from ..agentic_research.research_graph import create_research_agent
            from ..agentic_research.graph_configuration import AgentConfiguration
            from ..inference.llm import SentenceTransformerInference
            from langchain_core.messages import HumanMessage, AIMessage
            print(f"DEBUG: Enhanced research agent imported for {task_id}")
            
            # Create configuration for the LangGraph agent
            # Try to load configuration from database settings first
            langgraph_config_json = self.db.get_setting("research_agent_langgraph_config")
            if langgraph_config_json:
                try:
                    config_data = json.loads(langgraph_config_json)
                    
                    # Extract configuration parameters
                    max_research_loops = config_data.get("max_research_loops", max_steps)
                    initial_search_query_count = config_data.get("initial_search_query_count", 3)
                    local_search_limit = config_data.get("local_search_limit", num_papers_target)
                    external_search_limit = config_data.get("external_search_limit", 5)
                    search_config = config_data.get("search_config", {})
                    
                    # Create agent configuration
                    agent_config = AgentConfiguration(
                        local_search_limit=local_search_limit,
                        external_search_limit=external_search_limit,
                        max_research_loops=max_research_loops,
                        number_of_initial_queries=initial_search_query_count,
                        enable_pdf_download=search_config.get("enable_pdf_download", True),
                        semantic_weight=search_config.get("semantic_weight", 0.6),
                        keyword_weight=search_config.get("keyword_weight", 0.4),
                        similarity_threshold=search_config.get("similarity_threshold", 0.3),
                        external_search_delay=search_config.get("external_search_delay", 2.0)
                    )
                    
                    print(f"DEBUG: Using LangGraph configuration from database for {task_id}")
                    
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"DEBUG: Error parsing LangGraph config, using defaults: {e}")
                    # Fall back to default configuration
                    agent_config = AgentConfiguration(
                        local_search_limit=num_papers_target,
                        external_search_limit=5,
                        max_research_loops=max_steps,
                        number_of_initial_queries=3,
                        enable_pdf_download=enable_pdf_download,
                        external_search_delay=2.0
                    )
            else:
                print(f"DEBUG: No LangGraph config found, using defaults for {task_id}")
                # Use default configuration
                agent_config = AgentConfiguration(
                    local_search_limit=num_papers_target,
                    external_search_limit=5,
                    max_research_loops=max_steps,
                    number_of_initial_queries=3,
                    enable_pdf_download=enable_pdf_download,
                    external_search_delay=2.0
                )
            
            # Create research agent with properly configured embedding model
            print(f"DEBUG: Creating enhanced research agent for {task_id}")
            
            # Get embedding model configuration from database/orchestration settings
            try:
                orchestration_json = self.db.get_setting("orchestration")
                if orchestration_json:
                    orchestration_config = json.loads(orchestration_json)
                    embedding_config = orchestration_config.get('embedding_model', {})
                    model_name = embedding_config.get('model_name', 'Alibaba-NLP/gte-modernbert-base')
                    trust_remote_code = embedding_config.get('trust_remote_code', True)
                    print(f"DEBUG: Using configured embedding model: {model_name}")
                else:
                    model_name = 'Alibaba-NLP/gte-modernbert-base'
                    trust_remote_code = True
                    print(f"DEBUG: Using default embedding model: {model_name}")
                
                embedding_model = SentenceTransformerInference(
                    model_name=model_name,
                    remote_code=trust_remote_code
                )
            except Exception as e:
                print(f"DEBUG: Error loading embedding model config, using default: {e}")
                embedding_model = SentenceTransformerInference(
                    model_name='Alibaba-NLP/gte-modernbert-base',
                    remote_code=True
                )
            
            agent = create_research_agent(
                db=self.db,
                embedding_model=embedding_model,
                config=agent_config
            )
            print(f"DEBUG: Enhanced research agent created for {task_id}")
            
            # Convert conversation history to LangChain messages if provided
            messages = []
            if conversation_history:
                for msg in conversation_history:
                    if msg.get("role") == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    elif msg.get("role") == "assistant":
                        messages.append(AIMessage(content=msg["content"]))
            
            # Set up streaming with progress tracking
            research_config = {
                "local_search_limit": num_papers_target,
                "external_search_limit": 5,
                "max_research_loops": max_steps,
                "number_of_initial_queries": 3
            }
            
                                # Track progress through streaming
            sources_gathered = []
            search_results = []
            research_loop_count = 0
            query_count = 0
            final_message = None
            activity_log = []  # Track activity for research library
            
            print(f"DEBUG: Starting streaming research for {task_id}")
            
            try:
                # Use the async streaming capability
                async for chunk in agent.astream(
                    research_question, 
                    config=research_config,
                    conversation_history=messages
                ):
                    print(f"DEBUG: Received chunk for {task_id}: {chunk}")
                    
                    # Process different types of updates
                    for node_name, node_data in chunk.items():
                        if node_name == "query_refinement":
                            needs_clarification = node_data.get('needs_clarification', False)
                            
                            if needs_clarification:
                                # Format the clarifying questions for display
                                questions = node_data.get('clarifying_questions', [])
                                questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
                                
                                clarification_message = f"""I'd like to better understand your research needs to provide more focused results. Could you help clarify:

{questions_text}

Please respond with any additional details that would help me conduct more targeted research for you."""
                                
                                # Send the clarifying questions as the status message
                                await self.update_task_status(
                                    task_id,
                                    TaskStatus.PROCESSING,
                                    clarification_message,
                                    progress=10,
                                    current_step="query_refinement_waiting",
                                )
                                
                                # Record activity
                                activity_log.append({
                                    "timestamp": datetime.now().isoformat(),
                                    "step": "query_refinement",
                                    "action": "Requested clarification from user",
                                    "data": {
                                        "clarifying_questions": questions,
                                        "original_query": node_data.get('original_query', '')
                                    }
                                })
                                
                                # The workflow will end here, waiting for user response
                                # The user will need to continue the conversation
                                print(f"DEBUG: Query refinement requested clarification for {task_id}")
                                return  # Exit the task, user needs to respond
                            else:
                                # Query is clear, continue with research
                                await self.update_task_status(
                                    task_id,
                                    TaskStatus.PROCESSING,
                                    "Research question is clear, proceeding with search...",
                                    progress=10,
                                    current_step="query_refinement_complete",
                                )
                                
                                # Record activity
                                activity_log.append({
                                    "timestamp": datetime.now().isoformat(),
                                    "step": "query_refinement",
                                    "action": "Query is clear, no clarification needed",
                                    "data": {
                                        "refined_query": node_data.get('refined_query', ''),
                                        "original_query": node_data.get('original_query', '')
                                    }
                                })
                                
                        elif node_name == "generate_query":
                            await self.update_task_status(
                                task_id,
                                TaskStatus.PROCESSING,
                                f"Generated {len(node_data.get('query_list', []))} search queries",
                                progress=15,
                                current_step="query_generation",
                            )
                            query_count = len(node_data.get('query_list', []))
                            
                            # Record activity
                            activity_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "step": "query_generation",
                                "action": f"Generated {query_count} search queries",
                                "data": {"queries": node_data.get('query_list', [])}
                            })
                            
                        elif node_name == "local_research":
                            current_progress = 20 + (query_count * 5)  # Progress based on queries
                            await self.update_task_status(
                                task_id,
                                TaskStatus.PROCESSING,
                                f"Searching local database: {node_data.get('search_query', [''])[0]}",
                                progress=min(current_progress, 40),
                                current_step="local_search",
                            )
                            
                            # Collect sources and debug paper access
                            if node_data.get('sources_gathered'):
                                new_sources = node_data['sources_gathered']
                                sources_gathered.extend(new_sources)
                                
                                # Debug: Check what papers are being found and if they have full text
                                print(f"DEBUG: Local search found {len(new_sources)} papers for {task_id}")
                                for i, source in enumerate(new_sources[:3]):  # Log first 3 for debugging
                                    print(f"  Paper {i+1}: {source.get('title', 'No title')}")
                                    print(f"    Type: {source.get('source_type', 'unknown')}")
                                    if source.get('value'):
                                        print(f"    URL/Value: {source['value'][:100]}...")
                                    
                            if node_data.get('web_research_result'):
                                search_results.extend(node_data['web_research_result'])
                            
                            # Record activity
                            search_query = node_data.get('search_query', [''])[0]
                            sources_count = len(node_data.get('sources_gathered', []))
                            activity_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "step": "local_research",
                                "action": f"Searched local database for '{search_query}' - found {sources_count} sources",
                                "data": {"query": search_query, "sources_found": sources_count}
                            })
                                
                        elif node_name == "external_research":
                            current_progress = 50 + (research_loop_count * 10)
                            await self.update_task_status(
                                task_id,
                                TaskStatus.PROCESSING,
                                f"Searching external sources: {node_data.get('search_query', [''])[0]}",
                                progress=min(current_progress, 70),
                                current_step="external_search",
                            )
                            
                            # Collect sources
                            if node_data.get('sources_gathered'):
                                sources_gathered.extend(node_data['sources_gathered'])
                            if node_data.get('web_research_result'):
                                search_results.extend(node_data['web_research_result'])
                            
                            # Record activity
                            search_query = node_data.get('search_query', [''])[0]
                            sources_count = len(node_data.get('sources_gathered', []))
                            activity_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "step": "external_research",
                                "action": f"Searched external sources for '{search_query}' - found {sources_count} sources",
                                "data": {"query": search_query, "sources_found": sources_count}
                            })
                            
                        elif node_name == "sequential_external_research":
                            current_progress = 50 + (research_loop_count * 10)
                            await self.update_task_status(
                                task_id,
                                TaskStatus.PROCESSING,
                                "Running sequential external searches (respectful to APIs)...",
                                progress=min(current_progress, 70),
                                current_step="sequential_external_search",
                            )
                            
                            # Collect sources
                            if node_data.get('sources_gathered'):
                                sources_gathered.extend(node_data['sources_gathered'])
                            if node_data.get('web_research_result'):
                                search_results.extend(node_data['web_research_result'])
                            
                            # Record activity for all queries processed
                            queries = node_data.get('search_query', [])
                            total_sources = len(node_data.get('sources_gathered', []))
                            activity_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "step": "sequential_external_research",
                                "action": f"Searched external sources for {len(queries)} queries sequentially - found {total_sources} sources",
                                "data": {"queries": queries, "sources_found": total_sources}
                            })
                                
                        elif node_name == "reflection":
                            research_loop_count = node_data.get('research_loop_count', 0)
                            is_sufficient = node_data.get('is_sufficient', False)
                            
                            await self.update_task_status(
                                task_id,
                                TaskStatus.PROCESSING,
                                f"Analyzing findings (iteration {research_loop_count})" + 
                                (" - Research complete" if is_sufficient else " - Continuing research"),
                                progress=75 + (research_loop_count * 5),
                                current_step="reflection",
                            )
                            
                            # Record activity
                            activity_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "step": "reflection",
                                "action": f"Iteration {research_loop_count} - {'Research complete' if is_sufficient else 'Continuing research'}",
                                "data": {
                                    "iteration": research_loop_count,
                                    "is_sufficient": is_sufficient,
                                    "knowledge_gap": node_data.get('knowledge_gap', ''),
                                    "follow_up_queries": node_data.get('follow_up_queries', [])
                                }
                            })
                            
                        elif node_name == "finalize_answer":
                            await self.update_task_status(
                                task_id,
                                TaskStatus.PROCESSING,
                                "Generating final research summary...",
                                progress=90,
                                current_step="finalizing",
                            )
                            
                            # Extract the final message from the finalize_answer node
                            if node_data.get('messages'):
                                final_message = node_data['messages'][-1] if node_data['messages'] else None
                                
                                # Check if the final message contains an error
                                if final_message and hasattr(final_message, 'content'):
                                    if "Error generating research summary:" in final_message.content:
                                        print(f"DEBUG: Error detected in finalize_answer for {task_id}: {final_message.content}")
                                        raise ValueError(f"Research finalization failed: {final_message.content}")
                                
                                print(f"DEBUG: Extracted final message from finalize_answer for {task_id}")
                            
                            # Update sources if available
                            if node_data.get('sources_gathered'):
                                sources_gathered.extend(node_data['sources_gathered'])
                            
                            # Record activity
                            activity_log.append({
                                "timestamp": datetime.now().isoformat(),
                                "step": "finalize_answer",
                                "action": "Generated final research summary",
                                "data": {
                                    "total_sources": len(sources_gathered),
                                    "research_iterations": research_loop_count
                                }
                            })
                
                # Check if we got the final result from streaming
                print(f"DEBUG: Streaming completed for {task_id}, processing final result")
                
                # If we didn't get the final message from streaming, try to run agent again
                if not final_message:
                    print(f"DEBUG: No final message from streaming, running agent.arun() for {task_id}")
                    try:
                        result = await agent.arun(
                            research_question,
                            config=research_config,
                            conversation_history=messages
                        )
                        final_message = result.get('messages', [])[-1] if result.get('messages') else None
                        if result.get('sources_gathered'):
                            sources_gathered.extend(result['sources_gathered'])
                        print(f"DEBUG: Final result from arun() received for {task_id}")
                    except Exception as arun_error:
                        print(f"DEBUG: arun() failed for {task_id}: {arun_error}")
                else:
                    print(f"DEBUG: Using final message from streaming for {task_id}")
                
                final_sources = sources_gathered
                
                if final_message and hasattr(final_message, 'content'):
                    # Check if the final message contains an error
                    if "Error generating research summary:" in final_message.content:
                        print(f"DEBUG: Error detected in final message for {task_id}: {final_message.content}")
                        raise ValueError(f"Research failed: {final_message.content}")
                    
                    # Create a simplified literature review result
                    # This is a temporary structure - in a full implementation, 
                    # you might want to parse the final message to extract paper summaries
                    
                    await self.update_task_status(
                        task_id,
                        TaskStatus.PROCESSING,
                        "Saving enhanced research results...",
                        progress=95,
                        current_step="saving_results",
                    )
                    
                    # Extract structured paper information from sources and report
                    print(f"DEBUG: Extracting paper summaries from {len(sources_gathered)} sources for {task_id}")
                    
                    # Create structured summaries from sources_gathered
                    structured_summaries = []
                    for i, source in enumerate(sources_gathered):
                        try:
                            # Create a structured summary for each source
                            summary_entry = {
                                "paper_id": i + 1,  # Use index + 1 as paper_id
                                "title": source.get("title", f"Paper {i + 1}"),
                                "summary": f"Research source referenced in comprehensive analysis. {source.get('value', '')}",
                                "rationale": f"Source identified during research process with relevance to: {research_question}",
                                "relevance_score": 0.85 if source.get("source_type") == "local" else 0.75  # Higher score for local papers
                            }
                            structured_summaries.append(summary_entry)
                        except Exception as e:
                            print(f"DEBUG: Error creating summary for source {i}: {e}")
                    
                    # Convert structured summaries to JSON
                    summary_json = json.dumps(structured_summaries)
                    print(f"DEBUG: Created {len(structured_summaries)} structured summaries for {task_id}")
                    
                    # Create trace information
                    trace_data = [
                        {
                            "step": "paper_discovery",
                            "papers_found": len(sources_gathered),
                            "local_sources": len([s for s in sources_gathered if s.get("source_type") == "local"]),
                            "external_sources": len([s for s in sources_gathered if s.get("source_type") == "external"]),
                            "research_loops": research_loop_count
                        }
                    ]
                    trace_json = json.dumps(trace_data)
                    
                    # Generate short summary for research library
                    short_summary = enhance_summary_with_context(
                        research_question, 
                        extract_key_themes(research_question)
                    )
                    
                    # Convert activity log to JSON
                    activity_log_json = json.dumps(activity_log)
                    
                    # Save to database with proper paper count
                    review_id = self.db.insert_literature_review(
                        research_question=research_question,
                        summary_json=summary_json,
                        trace_json=trace_json,
                        report_text=final_message.content,
                        short_summary=short_summary,
                        activity_log=activity_log_json
                    )
                    
                    await self.update_task_status(
                        task_id,
                        TaskStatus.COMPLETED,
                        f"Enhanced literature review completed! Generated comprehensive research summary with {len(final_sources)} sources.",
                        progress=100,
                        current_step="enhanced_review_complete",
                        result={
                            "review_id": review_id,
                            "research_question": research_question,
                            "report_text": final_message.content,  # Include the actual report
                            "sources_found": len(final_sources),
                            "research_loops": research_loop_count,
                            "success": True,
                            "summary_length": len(final_message.content),
                            "enhanced_workflow": True,
                            "conversation_context": len(messages) > 0,
                            "final_sources": final_sources[:10]  # Include first 10 sources
                        },
                    )
                    
                    print(f"DEBUG: Enhanced research agent task {task_id} completed successfully")
                    
                else:
                    raise ValueError("No final message received from research agent")
                    
            except Exception as stream_error:
                print(f"DEBUG: Error during streaming for {task_id}: {stream_error}")
                # Fall back to non-streaming mode
                print(f"DEBUG: Falling back to non-streaming mode for {task_id}")
                
                result = await agent.arun(
                    research_question,
                    config=research_config,
                    conversation_history=messages
                )
                
                final_message = result.get('messages', [])[-1] if result.get('messages') else None
                final_sources = result.get('sources_gathered', [])
                
                if final_message and hasattr(final_message, 'content'):
                    # Generate short summary for research library
                    short_summary = enhance_summary_with_context(
                        research_question, 
                        extract_key_themes(research_question)
                    )
                    
                    # Create basic activity log for fallback mode
                    fallback_activity = [{
                        "timestamp": datetime.now().isoformat(),
                        "step": "fallback_research",
                        "action": "Completed research in fallback mode",
                        "data": {"total_sources": len(final_sources)}
                    }]
                    activity_log_json = json.dumps(fallback_activity)
                    
                    # Create basic structured summaries for fallback mode
                    fallback_summaries = []
                    if len(final_sources) > 0:
                        for i, source in enumerate(final_sources[:10]):  # Limit to first 10 sources
                            try:
                                summary_entry = {
                                    "paper_id": i + 1,
                                    "title": source.get("title", f"Fallback Paper {i + 1}"),
                                    "summary": f"Research source from fallback mode. {source.get('value', '')}",
                                    "rationale": f"Source identified during fallback research for: {research_question}",
                                    "relevance_score": 0.70  # Default score for fallback mode
                                }
                                fallback_summaries.append(summary_entry)
                            except Exception as e:
                                print(f"DEBUG: Error creating fallback summary for source {i}: {e}")
                    
                    fallback_summary_json = json.dumps(fallback_summaries)
                    fallback_trace_json = json.dumps([{"step": "fallback_research", "papers_found": len(final_sources)}])
                    
                    # Save to database with fallback data
                    review_id = self.db.insert_literature_review(
                        research_question=research_question,
                        summary_json=fallback_summary_json,
                        trace_json=fallback_trace_json,
                        report_text=final_message.content,
                        short_summary=short_summary,
                        activity_log=activity_log_json
                    )
                    
                    await self.update_task_status(
                        task_id,
                        TaskStatus.COMPLETED,
                        f"Literature review completed (fallback mode). Generated research summary with {len(final_sources)} sources.",
                        progress=100,
                        current_step="review_complete_fallback",
                        result={
                            "review_id": review_id,
                            "research_question": research_question,
                            "report_text": final_message.content,  # Include the actual report
                            "sources_found": len(final_sources),
                            "success": True,
                            "enhanced_workflow": True,
                            "fallback_mode": True
                        },
                    )
                else:
                    raise ValueError("No valid result received from research agent")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                f"Enhanced research agent task failed: {str(e)}",
                error=str(e),
                current_step="enhanced_task_failed",
            )
            raise


# Create global task manager instance
task_manager = TaskManager() 