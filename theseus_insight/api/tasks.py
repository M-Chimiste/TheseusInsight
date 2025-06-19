from typing import Dict, Optional, List
import asyncio
import json
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
            try:
                await func(task_id)
            finally:
                queue.task_done()

    async def enqueue_task(self, func, task_id: str, visualizer: bool = False) -> None:
        """Add a new task to the appropriate processing queue."""
        queue = self.visualizer_queue if visualizer or func == self.run_visualizer_task else self.general_task_queue
        await queue.put((func, task_id))
        
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
                # Send the status update
                await queue.put(status_obj)
                # For terminal states, also enqueue a sentinel (None) so
                # websocket handlers will exit cleanly **after** delivering
                # the final frame.
                if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    await queue.put(None)

        # Clean up mapping for terminal states *after* enqueuing items, but
        # do NOT drain the queues – the websocket consumer needs to read them.
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            if task_id in self.status_updates:
                # Remove reference so new subscribers won't be added, but keep
                # existing queues alive until consumers finish.
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

    # async def run_research_agent_task(self, task_id: str):
    #     """Run the research agent task with progress tracking."""
    #     try:
    #         print(f"DEBUG: Starting research agent task {task_id}")
    #         task = self.db.get_task(task_id)
    #         if not task:
    #             raise ValueError(f"Task {task_id} not found")
            
    #         config = task["config"]
    #         research_question = config.get("research_question")
    #         num_papers_target = config.get("num_papers_target", 5)
    #         max_steps = config.get("max_steps", 10)
    #         enable_pdf_download = config.get("enable_pdf_download", True)
            
    #         if not research_question:
    #             raise ValueError("Research question is required")
            
    #         await self.update_task_status(
    #             task_id,
    #             TaskStatus.PROCESSING,
    #             f"Starting literature review: {research_question}",
    #             progress=5,
    #             current_step="initializing_agent",
    #         )
            
    #         # Import research agent here to avoid circular imports
    #         from ..agentic_research.agent_loop import create_research_agent
            
    #         # Create research agent
    #         agent = create_research_agent(
    #             db=self.db,
    #             num_papers_target=num_papers_target,
    #             max_steps=max_steps,
    #             enable_pdf_download=enable_pdf_download
    #         )
            
    #         await self.update_task_status(
    #             task_id,
    #             TaskStatus.PROCESSING,
    #             "Research agent initialized. Starting literature review...",
    #             progress=10,
    #             current_step="starting_review",
    #         )
            
    #         # Custom progress tracking for agent iterations
    #         class ProgressTracker:
    #             def __init__(self, task_manager, task_id, max_steps, num_papers_target):
    #                 self.task_manager = task_manager
    #                 self.task_id = task_id
    #                 self.max_steps = max_steps
    #                 self.num_papers_target = num_papers_target
    #                 self.last_update_time = 0
                    
    #             async def update_progress(self, iteration, summaries_count, current_action=""):
    #                 # Calculate progress: 10% (start) + 80% (main work) + 10% (completion)
    #                 iteration_progress = min(iteration / self.max_steps, 1.0) * 0.6  # 60% for iterations
    #                 summary_progress = min(summaries_count / self.num_papers_target, 1.0) * 0.2  # 20% for summaries
    #                 total_progress = 10 + (iteration_progress + summary_progress) * 80
                    
    #                 message = f"Iteration {iteration}/{self.max_steps}, Found {summaries_count}/{self.num_papers_target} papers"
    #                 if current_action:
    #                     message += f". {current_action}"
                        
    #                 await self.task_manager.update_task_status(
    #                     self.task_id,
    #                     TaskStatus.PROCESSING,
    #                     message,
    #                     progress=total_progress,
    #                     current_step=f"iteration_{iteration}",
    #                 )
            
    #         progress_tracker = ProgressTracker(self, task_id, max_steps, num_papers_target)
            
    #         # Add a custom progress callback to the agent
    #         original_add_trace_entry = agent._add_trace_entry
            
    #         def enhanced_add_trace_entry(action_type, details, model_used=None, duration_seconds=None):
    #             # Call original method
    #             original_add_trace_entry(action_type, details, model_used, duration_seconds)
                
    #             # Update progress for key milestones
    #             if action_type in ["agent_response", "search_execution", "summary_extracted"]:
    #                 asyncio.create_task(progress_tracker.update_progress(
    #                     agent.current_iteration,
    #                     len(agent.collected_summaries),
    #                     action_type.replace("_", " ").title()
    #                 ))
            
    #         # Monkey-patch the trace entry method for progress updates
    #         agent._add_trace_entry = enhanced_add_trace_entry
            
    #         # Run the literature review
    #         result = agent.run_literature_review(research_question)
            
    #         if result.success:
    #             await self.update_task_status(
    #                 task_id,
    #                 TaskStatus.PROCESSING,
    #                 "Literature review completed. Saving results...",
    #                 progress=90,
    #                 current_step="saving_results",
    #             )
                
    #             # Save results to database
    #             review_id = agent.save_results(result)
                
    #             await self.update_task_status(
    #                 task_id,
    #                 TaskStatus.COMPLETED,
    #                 f"Literature review completed successfully! Found {len(result.summaries)} papers in {result.total_iterations} iterations.",
    #                 progress=100,
    #                 current_step="review_complete",
    #                 result={
    #                     "review_id": review_id,
    #                     "research_question": result.research_question,
    #                     "papers_found": len(result.summaries),
    #                     "iterations_used": result.total_iterations,
    #                     "success": result.success,
    #                     "summaries": [
    #                         {
    #                             "paper_id": s.paper_id,
    #                             "title": s.title,
    #                             "summary": s.summary,
    #                             "rationale": s.rationale,
    #                             "relevance_score": s.relevance_score
    #                         }
    #                         for s in result.summaries
    #                     ],
    #                     "trace_entries_count": len(result.trace_entries)
    #                 },
    #             )
    #         else:
    #             await self.update_task_status(
    #                 task_id,
    #                 TaskStatus.FAILED,
    #                 f"Literature review failed: {result.error or 'Unknown error'}",
    #                 error=result.error,
    #                 current_step="review_failed",
    #                 result={
    #                     "papers_found": len(result.summaries),
    #                     "iterations_used": result.total_iterations,
    #                     "success": result.success,
    #                     "error": result.error
    #                 },
    #             )
                
    #     except Exception as e:
    #         import traceback
    #         traceback.print_exc()
    #         await self.update_task_status(
    #             task_id,
    #             TaskStatus.FAILED,
    #             f"Research agent task failed: {str(e)}",
    #             error=str(e),
    #             current_step="task_failed",
    #         )
    #         raise

    async def run_mindmap_expand_task(self, task_id: str):
        """Run the mind-map expansion task."""
        try:
            print(f"DEBUG: Starting mind-map expansion task {task_id}")
            task = self.db.get_task(task_id)
            if not task:
                print(f"DEBUG: Task {task_id} not found in database")
                raise ValueError(f"Task {task_id} not found")
            
            print(f"DEBUG: Task found: {task}")
            config = task["config"]
            paper_id = config.get("paper_id")
            k = config.get("k", 15)
            similarity_threshold = config.get("similarity_threshold", 0.3)
            layout_algorithm = config.get("layout_algorithm", "force")
            model_config_override = config.get("model_config_override")
            
            print(f"DEBUG: Task config - paper_id: {paper_id}, k: {k}, threshold: {similarity_threshold}")
            
            if not paper_id:
                print(f"DEBUG: No paper_id provided in config")
                raise ValueError("Paper ID is required for mind-map expansion")
            
            # Import the mind-map workflow
            from ..mindmap.workflow import create_mindmap_workflow
            
            # Get configuration from database
            orchestration_json = self.db.get_setting("orchestration")
            orchestration_config = json.loads(orchestration_json) if orchestration_json else {}
            
            # Get LLM model configuration for summarization
            # Use override if provided, otherwise fall back to orchestration config
            llm_model_config = model_config_override
            if not llm_model_config:
                # Try to get a suitable LLM model from orchestration config
                # Priority: content_extraction_model > judge_model > newsletter_sections_model
                llm_model_config = (
                    orchestration_config.get("content_extraction_model") or
                    orchestration_config.get("judge_model") or
                    orchestration_config.get("newsletter_sections_model")
                )
                print(f"DEBUG: Using fallback LLM model config from orchestration: {llm_model_config}")
            else:
                print(f"DEBUG: Using provided LLM model config override: {llm_model_config}")
            
            print(f"DEBUG: Creating mind-map workflow...")
            # Create workflow
            workflow = create_mindmap_workflow(
                db=self.db,
                config=orchestration_config
            )
            print(f"DEBUG: Mind-map workflow created successfully")
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Mind-map workflow initialized. Processing...",
                progress=10,
                current_step="workflow_initialized",
            )
            print(f"DEBUG: Initial status update sent")
            
            # Define progress callback wrapper for sync execution
            def sync_progress_callback(step: str, progress: float, message: str = ""):
                print(f"DEBUG: sync_progress_callback called - step: {step}, progress: {progress}, message: {message}")
                # Map workflow progress (0-100) to task progress (10-90)
                task_progress = 10 + (progress * 0.8)
                
                # Create a task to update status asynchronously
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    print(f"DEBUG: Got event loop, is_running: {loop.is_running()}")
                    if loop.is_running():
                        # If we're in an async context, create a task
                        print(f"DEBUG: Creating task for async status update")
                        loop.create_task(self.update_task_status(
                            task_id,
                            TaskStatus.PROCESSING,
                            message or f"Processing step: {step}",
                            progress=task_progress,
                            current_step=step,
                        ))
                    else:
                        # If not, run it synchronously
                        print(f"DEBUG: Running status update synchronously")
                        loop.run_until_complete(self.update_task_status(
                            task_id,
                            TaskStatus.PROCESSING,
                            message or f"Processing step: {step}",
                            progress=task_progress,
                            current_step=step,
                        ))
                    print(f"DEBUG: Status update completed successfully")
                except Exception as e:
                    print(f"Progress callback error: {e}")
                    import traceback
                    print(f"Progress callback traceback: {traceback.format_exc()}")
            
            # Run the mind-map workflow synchronously
            print(f"DEBUG: About to call workflow.generate_mindmap_sync for task {task_id}")
            result = workflow.generate_mindmap_sync(
                seed_paper_id=int(paper_id),
                k_neighbors=k,
                similarity_threshold=similarity_threshold,
                layout_algorithm=layout_algorithm,
                embedding_model_config=None,  # Will be pulled from config
                llm_model_config=llm_model_config,
                task_id=task_id,  # Use the actual task ID
                progress_callback=sync_progress_callback  # Pass the sync progress callback
            )
            print(f"DEBUG: workflow.generate_mindmap_sync completed for task {task_id}")
            print(f"DEBUG: Result success: {result.get('success', False)}")
            print(f"DEBUG: Result keys: {list(result.keys())}")
            if result.get('mindmap_data'):
                mindmap_data = result['mindmap_data']
                print(f"DEBUG: Mindmap data keys: {list(mindmap_data.keys())}")
                print(f"DEBUG: Nodes count: {len(mindmap_data.get('nodes', []))}")
                print(f"DEBUG: Edges count: {len(mindmap_data.get('edges', []))}")
            
            if result.get("error"):
                print(f"DEBUG: Result contains error: {result['error']}")
                await self.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    f"Mind-map generation failed: {result['error']}",
                    error=result["error"],
                    current_step="generation_failed",
                )
                print(f"DEBUG: Failed status update sent")
                return

            mindmap_data = result.get("mindmap_data", {})
            nodes = mindmap_data.get("nodes", [])
            edges = mindmap_data.get("edges", [])
            
            print(f"DEBUG: About to send completion status update")
            # Add a small delay to ensure WebSocket has time to connect
            await asyncio.sleep(0.5)
            
            # Create the result object that will be sent via WebSocket
            completion_result = {
                "mindmap_data": mindmap_data,
                "seed_paper_id": paper_id,
                "nodes_count": len(nodes),
                "edges_count": len(edges),
                "layout_algorithm": layout_algorithm
            }
            print(f"DEBUG: Completion result structure: {list(completion_result.keys())}")
            print(f"DEBUG: Mindmap data structure being sent: {list(mindmap_data.keys()) if mindmap_data else 'None'}")
            if mindmap_data and 'nodes' in mindmap_data:
                print(f"DEBUG: First node sample: {mindmap_data['nodes'][0] if mindmap_data['nodes'] else 'No nodes'}")
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                f"Mind-map generated successfully with {len(nodes)} nodes and {len(edges)} edges",
                progress=100,
                current_step="generation_complete",
                result=completion_result,
            )
            print(f"DEBUG: Completion status update sent")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                f"Mind-map expansion task failed: {str(e)}",
                error=str(e),
                current_step="task_failed",
            )
            raise

    async def run_mindmap_pdf_parse_task(self, task_id: str):
        """Run the PDF parsing task for mind-map papers."""
        try:
            print(f"DEBUG: Starting mind-map PDF parsing task {task_id}")
            task = self.db.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            config = task["config"]
            paper_ids = config.get("paper_ids", [])
            
            if not paper_ids:
                raise ValueError("No paper IDs provided for parsing")
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Starting PDF parsing for {len(paper_ids)} papers",
                progress=5,
                current_step="initializing",
            )
            
            # Import PDF processing utilities
            from ..pdf.processing import MarkitdownDocProcessor
            from ..inference.llm import LLMModelFactory
            
            # Get embedding model configuration from orchestration settings
            orchestration_json = self.db.get_setting("orchestration")
            orchestration_config = json.loads(orchestration_json) if orchestration_json else {}
            embedding_config = orchestration_config.get("embedding_model", {})
            
            # Create embedding model
            embedding_model = LLMModelFactory.create_model(
                model_type=embedding_config.get("model_type", "sentence-transformer"),
                model_name=embedding_config.get("model_name", "Alibaba-NLP/gte-large-en-v1.5"),
                **{k: v for k, v in embedding_config.items() if k not in ["model_type", "model_name"]}
            )
            
            # Initialize PDF processor
            pdf_processor = MarkitdownDocProcessor()
            
            # Process each paper
            parsed_papers = []
            failed_papers = []
            
            for i, paper_id in enumerate(paper_ids):
                try:
                    # Update progress
                    progress = 10 + (i / len(paper_ids)) * 80
                    await self.update_task_status(
                        task_id,
                        TaskStatus.PROCESSING,
                        f"Processing paper {i+1}/{len(paper_ids)}: {paper_id}",
                        progress=progress,
                        current_step=f"processing_paper_{paper_id}",
                    )
                    
                    # Get paper details
                    paper = self.db.get_paper_by_id(int(paper_id))
                    if not paper:
                        failed_papers.append({"paper_id": paper_id, "error": "Paper not found"})
                        continue
                    
                    # Check if paper has URL for PDF download
                    paper_url = paper.get('url', '')
                    if not paper_url:
                        failed_papers.append({"paper_id": paper_id, "error": "No URL available"})
                        continue
                    
                    # Process PDF (this is a simplified version - you may need to adapt based on your PDF processing pipeline)
                    try:
                        # Extract text from PDF
                        text_content = await pdf_processor.process_url(paper_url)
                        
                        if not text_content:
                            failed_papers.append({"paper_id": paper_id, "error": "Failed to extract text"})
                            continue
                        
                        # Generate embedding for the full text
                        embedding = embedding_model.invoke(text_content, to_list=True)
                        
                        # Store in database
                        self.db.insert_paper_fulltext(
                            paper_id=int(paper_id),
                            content=text_content,
                            embedding=embedding,
                            embedding_model=embedding_config.get("model_name", "unknown")
                        )
                        
                        parsed_papers.append(paper_id)
                        
                    except Exception as pdf_error:
                        failed_papers.append({"paper_id": paper_id, "error": str(pdf_error)})
                        continue
                        
                except Exception as e:
                    failed_papers.append({"paper_id": paper_id, "error": str(e)})
                    continue
            
            # Complete the task
            success_count = len(parsed_papers)
            failure_count = len(failed_papers)
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                f"PDF parsing completed: {success_count} successful, {failure_count} failed",
                progress=100,
                current_step="parsing_complete",
                result={
                    "parsed_papers": parsed_papers,
                    "failed_papers": failed_papers,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "total_requested": len(paper_ids)
                },
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                f"PDF parsing task failed: {str(e)}",
                error=str(e),
                current_step="task_failed",
            )
            raise


# Create global task manager instance
task_manager = TaskManager() 