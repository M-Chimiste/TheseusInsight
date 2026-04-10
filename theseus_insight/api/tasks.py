from typing import Dict, Optional, List
import asyncio
import json
import os
from datetime import datetime
from enum import Enum
from .models import RunStatus, NodeStatus
from ..theseus_insight import TheseusInsight
from ..data_access import (
    TaskRepository, LogsRepository, SettingsRepository, 
    PaperRepository, PaperFulltextRepository
)

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManager:
    def __init__(self):
        self.status_updates: Dict[str, List[asyncio.Queue]] = {}
        # Remove legacy db instance - now using repositories directly

        # Queues and workers for task processing
        # general_task_queue handles newsletter/podcast/etc.
        # visualizer_queue allows a visualizer task to run concurrently
        self.general_task_queue: asyncio.Queue = asyncio.Queue()
        self.visualizer_queue: asyncio.Queue = asyncio.Queue()
        self.general_worker_task: Optional[asyncio.Task] = None
        self.visualizer_worker_task: Optional[asyncio.Task] = None

        # Mark any interrupted tasks as failed on startup
        self._mark_interrupted_tasks_as_failed()

        # Clean up old tasks on startup
        self._cleanup_old_tasks(days_old=7)

    def _mark_interrupted_tasks_as_failed(self):
        """Mark interrupted tasks as failed using repository pattern."""
        # Get all pending/processing tasks and mark them as failed
        try:
            active_tasks = TaskRepository.get_active_tasks()
            current_time = datetime.now().isoformat()
            
            for task in active_tasks:
                TaskRepository.update_task_status(
                    task_id=task['task_id'],
                    status="failed",
                    progress=0.0,
                    current_step="interrupted",
                    message="Task was interrupted by server restart",
                    error="Task was interrupted by server restart",
                    end_time=current_time
                )
        except Exception as e:
            print(f"Error marking interrupted tasks as failed: {e}")

    def _cleanup_old_tasks(self, days_old: int = 7):
        """Clean up old tasks using repository pattern."""
        try:
            # Get tasks older than specified days and delete them
            from datetime import timedelta
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()
            
            # For now, we'll implement this as a simple method
            # In the future, we could add a proper cleanup method to TaskRepository
            from ..db import get_cursor
            with get_cursor() as cur:
                cur.execute(
                    "DELETE FROM tasks WHERE start_time < %s AND status IN ('completed', 'failed')",
                    (cutoff_date,)
                )
        except Exception as e:
            print(f"Error cleaning up old tasks: {e}")

    async def start_worker(self) -> None:
        """Start the background workers that process queued tasks."""
        if self.general_worker_task is None or self.general_worker_task.done():
            print("INFO:     Starting general task worker")
            self.general_worker_task = asyncio.create_task(self._worker(self.general_task_queue))
        if self.visualizer_worker_task is None or self.visualizer_worker_task.done():
            print("INFO:     Starting visualizer task worker")
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
            except Exception as e:
                print(f"Error processing task {task_id}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                queue.task_done()

    async def enqueue_task(self, func, task_id: str, visualizer: bool = False) -> None:
        """Add a new task to the appropriate processing queue."""
        queue = self.visualizer_queue if visualizer or func == self.run_visualizer_task else self.general_task_queue
        await queue.put((func, task_id))
        
        # Ensure workers are still running
        await self.start_worker()

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
        print(f"[DEBUG] Creating task {task_id} with config: {config}")
        start_time = datetime.now().isoformat()
        
        # Store task in database using repository (run in thread to avoid blocking event loop)
        await asyncio.to_thread(
            TaskRepository.insert_task,
            task_id=task_id,
            task_type=task_type,
            status=TaskStatus.PENDING.value,
            config_json=config,
            start_time=start_time,
            progress=0,
            current_step="initializing",
            message="Task created"
        )
        print(f"[DEBUG] Task {task_id} created successfully")
        
        # Initialize WebSocket subscriptions
        self.status_updates[task_id] = []
        
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get the current status of a task."""
        return TaskRepository.get_task(task_id)
        
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
        metadata: dict | None = None,
    ) -> None:
        """Update task status and notify subscribers."""
        # Check if task exists in database (run in thread to avoid blocking event loop)
        task = await asyncio.to_thread(TaskRepository.get_task, task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        # Handle graceful completion: if task is already completed/failed, don't overwrite unless it's an error
        existing_status = task.get('status', '')
        if existing_status in ['completed', 'failed'] and status == TaskStatus.COMPLETED:
            # Task already completed, just return without error
            print(f"Task {task_id} already marked as {existing_status}, skipping duplicate completion")
            return
        
        # Calculate final progress based on status
        final_progress = progress if status == TaskStatus.PROCESSING else (100 if status == TaskStatus.COMPLETED else 0)

        # If metadata is not provided, preserve existing metadata from the task
        if metadata is None:
            existing_metadata = task.get('metadata')
            if existing_metadata:
                if isinstance(existing_metadata, str):
                    try:
                        metadata = json.loads(existing_metadata)
                    except json.JSONDecodeError:
                        # If it's a string but not valid JSON, use as is or ignore? 
                        # Ideally it should be a dict. Let's assume it might be a raw string or ignore.
                        print(f"[WARNING] Could not parse existing metadata for task {task_id}: {existing_metadata}")
                        metadata = {}
                elif isinstance(existing_metadata, dict):
                    metadata = existing_metadata
        
        # Update task in database using repository (run in thread to avoid blocking event loop)
        end_time = datetime.now().isoformat() if status in [TaskStatus.COMPLETED, TaskStatus.FAILED] else None
        await asyncio.to_thread(
            TaskRepository.update_task_status,
            task_id=task_id,
            status=status.value,
            progress=final_progress,
            current_step=current_step,
            message=message,
            error=error,
            result_json=result,
            end_time=end_time,
            metadata=metadata
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
            metadata=metadata,
        )
        
                # Log to the logs table as well
        final_status = status_obj.overallStatus
        LogsRepository.upsert(
            task_id=task_id,
            status=final_status,
            datetime_run=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
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

    # ------------------------------------------------------------------
    # Synchronous variant for situations where we are inside a blocking
    # workflow executed in the event-loop thread (e.g. sync_progress_callback)
    # ------------------------------------------------------------------
    def update_task_status_sync(
        self,
        task_id: str,
        status: TaskStatus,
        message: str = "",
        progress: float = 0,
        current_step: str | None = None,
        error: str | None = None,
        result: dict | None = None,
    ) -> None:
        """Synchronous, non-awaiting version of update_task_status.

        Runs directly inside the same thread – useful when long blocking
        operations (e.g. LLM summarisation) would otherwise prevent the
        event-loop from executing the regular async method and therefore the
        websocket clients would only receive updates at the very end.
        """
        # Update DB row immediately
        end_time = datetime.now().isoformat() if status in [TaskStatus.COMPLETED, TaskStatus.FAILED] else None
        TaskRepository.update_task_status(
            task_id=task_id,
            status=status.value,
            progress=progress,
            current_step=current_step,
            message=message,
            error=error,
            result_json=result,
            end_time=end_time,
        )

        timestamp = datetime.now().isoformat()
        status_obj = RunStatus(
            taskId=task_id,
            nodes=[
                NodeStatus(
                    nodeId="main",
                    status=status,
                    message=message,
                    progress=progress,
                    timestamp=timestamp,
                )
            ],
            overallStatus=status,
            currentStep=current_step,
            progress=progress,
            message=message,
            result=result,
            error=error,
        )

        # Persist to logs
        LogsRepository.upsert(task_id=task_id, status=status, datetime_run=timestamp)
        
        # Notify subscribers synchronously using put_nowait to avoid awaits
        if task_id in self.status_updates:
            for queue in list(self.status_updates[task_id]):
                try:
                    queue.put_nowait(status_obj)
                    if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                        queue.put_nowait(None)
                except Exception:
                    pass
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            self.status_updates.pop(task_id, None)

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

    def _get_orchestration_config(self, verbose: bool = False) -> dict:
        """
        Get orchestration config with proper fallback hierarchy: DB -> config file -> defaults.
        
        Args:
            verbose: Whether to print debug information about config source
            
        Returns:
            Dictionary containing orchestration configuration
        """
        orchestration_json = SettingsRepository.get("orchestration")
        if orchestration_json:
            orchestration_config = json.loads(orchestration_json)
            if verbose:
                print("📊 Using orchestration config from database settings")
            return orchestration_config
        else:
            # Fallback to config file
            try:
                from pathlib import Path
                config_path = Path(__file__).resolve().parents[2] / "config" / "orchestration.json"
                orchestration_config = json.loads(config_path.read_text())
                if verbose:
                    print("📊 Using orchestration config from config file")
                return orchestration_config
            except Exception as e:
                print(f"Warning: Could not load orchestration config from file: {e}")
                if verbose:
                    print("📊 Using empty orchestration config (defaults only)")
                return {}

    async def run_newsletter_task(self, task_id: str):
        """Run the newsletter generation task."""
        try:
            task = TaskRepository.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            config = task["config"]
            email_recipients = config.get("emailRecipients", None)
            research_interests_override = config.get("researchInterests", None)
            
            # Profile filtering parameters
            profile_id = config.get("profile_id")
            profile_ids = config.get("profile_ids")
            profile_tag = config.get("profile_tag")
            profile_tags = config.get("profile_tags")
            use_profile_recipients = config.get("use_profile_recipients", False)
            
            # Resolve profile context
            resolved_profile_ids = None
            profile_recipients = None
            
            if profile_id or profile_ids or profile_tag or profile_tags:
                from ..data_access import ProfileRepository
                
                # Resolve profile IDs from tags if provided
                if profile_tag or profile_tags:
                    tag_list = []
                    if profile_tag:
                        tag_list.append(profile_tag)
                    if profile_tags:
                        tag_list.extend(profile_tags)
                    
                    tag_profiles = ProfileRepository.get_by_tags(tag_list)
                    tag_profile_ids = [p['id'] for p in tag_profiles]
                    
                    if profile_ids:
                        # Combine explicit profile_ids with tag-resolved IDs
                        resolved_profile_ids = list(set(profile_ids + tag_profile_ids))
                    else:
                        resolved_profile_ids = tag_profile_ids
                elif profile_ids:
                    resolved_profile_ids = profile_ids
                elif profile_id:
                    resolved_profile_ids = [profile_id]
                
                # Get profile-specific email recipients if requested
                if use_profile_recipients and resolved_profile_ids:
                    profile_recipients = []
                    for pid in resolved_profile_ids:
                        profile = ProfileRepository.get_by_id(pid)
                        if profile and profile.get('email_recipients'):
                            profile_recipients.extend(profile['email_recipients'])
                    
                    # Remove duplicates while preserving order
                    profile_recipients = list(dict.fromkeys(profile_recipients))
                    
                    # Use profile recipients if available, otherwise fall back to config recipients
                    if profile_recipients:
                        email_recipients = profile_recipients
            
            orchestration_config = SettingsRepository.get("orchestration")
            if not orchestration_config:
                orchestration_config = "config/orchestration.json"

            # Create TheseusInsight instance for newsletter generation
            ti = TheseusInsight(
                research_interests_override=research_interests_override,
                orchestration_config=orchestration_config,
                task_id=task_id,
                progress_callback=self._progress_callback(task_id),
                profile_ids_override=resolved_profile_ids,  # Pass resolved profile IDs
                top_n=config.get("num_sections", 5),
                **{
                    k: v for k, v in config.items()
                    if k not in ["emailRecipients", "researchInterests", "profile_id", "profile_ids", "profile_tag", "profile_tags", "use_profile_recipients", "num_sections"]
                },
                generate_podcast=False,  # We handle podcast generation separately for now
                data_path=os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb"),
                generate_email=True,
                receiver_address_override=email_recipients,
                verbose=True
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
                ti.run,
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
            task = TaskRepository.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            config = task["config"]
            
            # Initialize podcast generator
            # The text_model parameter expects the entire model configuration dictionary.
            # The key for this dictionary in the config is "podcast_model_config".
            podcast_model_configuration = config.get("podcast_model_config")
            if not podcast_model_configuration:
                raise ValueError("Podcast model configuration (podcast_model_config) is missing from task config.")

            from ..podcast.generator import PodcastGenerator
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
            task = TaskRepository.get_task(task_id)
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

            task = TaskRepository.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Extract configuration
            config = task.get("config_json", {})
            if isinstance(config, str):
                config = json.loads(config)
            
            incremental = config.get("incremental", False)
            since_timestamp = config.get("since_timestamp")
            tables = config.get("tables")
            batch_size = config.get("batch_size", 1000)
            streaming = config.get("streaming", False)
            parallel = config.get("parallel", False)
            max_workers = config.get("max_workers", 4)
            
            export_type = "incremental" if incremental else "full"
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Starting {export_type} database export",
                progress=0,
                current_step="export_init",
            )

            export_dir = f"data/temp/{task_id}_export"
            os.makedirs(export_dir, exist_ok=True)

            # Get database URL from environment
            db_url = os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb")
            
            # Parse timestamp if provided
            parsed_timestamp = None
            if since_timestamp:
                try:
                    from datetime import datetime as dt
                    parsed_timestamp = dt.fromisoformat(since_timestamp)
                except ValueError:
                    raise ValueError(f"Invalid timestamp format: {since_timestamp}")
            
            exporter = DatabaseExporter(
                db_url, 
                export_dir,
                batch_size=batch_size,
                streaming=streaming,
                parallel=parallel,
                max_workers=max_workers,
                incremental=incremental,
                since_timestamp=parsed_timestamp
            )

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

            if incremental:
                # Run incremental export
                result = await asyncio.to_thread(
                    exporter.export_incremental,
                    tables,
                    parsed_timestamp
                )
                # Create archive for incremental export
                archive_file = await asyncio.to_thread(
                    exporter.create_archive,
                    f"theseus_incremental_{task_id}"
                )
                result["archive"] = archive_file
            else:
                # Run full export
                result = await asyncio.to_thread(
                    exporter.export_all,
                    True,
                    f"theseus_backup_{task_id}",
                    progress_cb,
                )

            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                f"{export_type.capitalize()} database export completed",
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
            task = TaskRepository.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            print(f"DEBUG: Task retrieved: {task}")
            # Get the config_json field (already parsed by PostgreSQL driver if it's JSON type)
            task_config = task.get("config_json", {})
            print(f"DEBUG: Task config: {task_config}")
            
            from ..utils.db_migration.db_import import DatabaseImporter
            
            archive_path = task_config.get("archive_path")
            import_mode = task_config.get("import_mode", "merge")
            filename = task_config.get("filename", "unknown")
            
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
            db_url = os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb")
            print(f"DEBUG: Initializing DatabaseImporter with db_url: {db_url}")
            importer = DatabaseImporter(db_url)
            
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
                print("DEBUG: About to call importer.clear_all_data")
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
            
            # Import the data with smart interest merging enabled
            # merge_interests=True ensures that when Default profiles match, any new
            # research interests from the import are merged into the existing profile
            merge_interests = task_config.get("merge_interests", True)
            print(f"DEBUG: Starting import from archive, skip_duplicates: {skip_duplicates}, merge_interests: {merge_interests}")
            print(f"DEBUG: About to call importer.import_from_archive with args: {archive_path}, {skip_duplicates}")
            try:
                results = await asyncio.to_thread(
                    importer.import_from_archive,
                    archive_path,
                    skip_duplicates,
                    import_progress_callback,
                    merge_interests
                )
                print(f"DEBUG: Import completed with results: {results}")
            except Exception as import_error:
                print(f"DEBUG: Error during import_from_archive: {import_error}")
                print(f"DEBUG: Import error type: {type(import_error)}")
                import traceback
                traceback.print_exc()
                raise
            
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
            print(f"DEBUG: Error type: {type(e)}")
            import traceback
            traceback.print_exc()
            
            # Clean up temporary file on error
            try:
                if 'task' in locals() and task:
                    task_config_cleanup = task.get("config_json", {})
                    archive_path_cleanup = task_config_cleanup.get("archive_path")
                    if archive_path_cleanup and os.path.exists(archive_path_cleanup):
                        os.remove(archive_path_cleanup)
                        print(f"DEBUG: Cleaned up temporary file on error: {archive_path_cleanup}")
            except Exception as cleanup_error:
                print(f"DEBUG: Error during cleanup: {cleanup_error}")
                pass
                
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                "Database import failed",
                error=str(e),
                current_step="import_failed",
            )
            raise

    async def run_mindmap_expand_task(self, task_id: str):
        """Run the mind-map expansion task."""
        try:
            print(f"DEBUG: Starting mind-map expansion task {task_id}")
            task = TaskRepository.get_task(task_id)
            if not task:
                print(f"DEBUG: Task {task_id} not found in database")
                raise ValueError(f"Task {task_id} not found")
            
            print(f"DEBUG: Task found: {task}")
            print(f"DEBUG: config_json type: {type(task['config_json'])}")
            print(f"DEBUG: config_json value: {task['config_json']}")
            if isinstance(task["config_json"], str):
                config = json.loads(task["config_json"])
            else:
                config = task["config_json"]
            paper_id = config.get("paper_id")
            topic_id = config.get("topic_id")  # Extract topic_id for auto-save functionality
            k = config.get("k", 15)
            similarity_threshold = config.get("similarity_threshold", 0.3)
            expansion_order = config.get("expansion_order", 1)
            max_nodes_per_order = config.get("max_nodes_per_order", 20)
            layout_algorithm = config.get("layout_algorithm", "force")
            model_config_override = config.get("model_config_override")
            # Profile filtering parameters
            profile_id = config.get("profile_id")
            profile_ids = config.get("profile_ids")
            profile_tag = config.get("profile_tag")
            profile_tags = config.get("profile_tags")
            
            print(f"DEBUG: Task config - paper_id: {paper_id}, k: {k}, threshold: {similarity_threshold}, expansion_order: {expansion_order}, max_nodes_per_order: {max_nodes_per_order}")
            
            if not paper_id:
                print(f"DEBUG: No paper_id provided in config")
                raise ValueError("Paper ID is required for mind-map expansion")
            
            # Import the mind-map workflow
            from ..mindmap.workflow import create_mindmap_workflow
            
            # Get configuration from database or fallback file
            orchestration_json = SettingsRepository.get("orchestration")
            if orchestration_json:
                print("DEBUG: Loaded orchestration config from DB settings table")
                orchestration_config = json.loads(orchestration_json)
            else:
                # Fallback to bundled config/orchestration.json file
                try:
                    from pathlib import Path
                    cfg_path = Path(__file__).resolve().parents[2] / "config" / "orchestration.json"
                    print(f"DEBUG: Loading orchestration config from file: {cfg_path}")
                    orchestration_config = json.loads(cfg_path.read_text())
                except Exception as e:
                    print(f"DEBUG: Failed to load orchestration config file: {e}")
                    orchestration_config = {}

            # Pull mind-map specific defaults from orchestration config if not provided
            mind_cfg = orchestration_config.get("mind_map_config", {})
            k = config.get("k", mind_cfg.get("k", 15))
            similarity_threshold = config.get("similarity_threshold", mind_cfg.get("similarity_threshold", 0.3))
            expansion_order = config.get("expansion_order", mind_cfg.get("expansion_order", 1))
            max_nodes_per_order = config.get("max_nodes_per_order", mind_cfg.get("max_nodes_per_order", 20))
            layout_algorithm = config.get("layout_algorithm", mind_cfg.get("layout_algorithm", "force"))

            print(f"DEBUG: Final parameters after orchestration defaults – k:{k} thresh:{similarity_threshold} order:{expansion_order} max_per_order:{max_nodes_per_order}")

            # Get LLM model configuration for summarization
            llm_model_config = model_config_override
            if not llm_model_config:
                llm_model_config = mind_cfg.get("summarization_model")
                if llm_model_config:
                    print("DEBUG: Using mind_map_config.summarization_model as LLM config")
            if not llm_model_config:
                # Try alternative fallbacks
                llm_model_config = (
                    orchestration_config.get("content_extraction_model") or
                    orchestration_config.get("judge_model") or
                    orchestration_config.get("newsletter_sections_model")
                )
                print(f"DEBUG: Using generic fallback LLM config: {llm_model_config}")
            else:
                print(f"DEBUG: LLM model config determined: {llm_model_config}")
            
            print(f"DEBUG: Creating mind-map workflow...")
            # Create workflow with database connection
            workflow = create_mindmap_workflow(
                db=None,  # Pass None - workflow nodes will use repositories directly
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

                try:
                    self.update_task_status_sync(
                        task_id,
                        TaskStatus.PROCESSING,
                        message or f"Processing step: {step}",
                        progress=task_progress,
                        current_step=step,
                    )
                except Exception as e:
                    print(f"DEBUG: Progress status update failed (sync): {e}")
            
            # Run the mind-map workflow synchronously
            print(f"DEBUG: About to call workflow.generate_mindmap_sync for task {task_id}")
            print(f"DEBUG: Profile parameters - ID: {profile_id}, IDs: {profile_ids}, tag: {profile_tag}, tags: {profile_tags}")
            result = workflow.generate_mindmap_sync(
                seed_paper_id=int(paper_id),
                k_neighbors=k,
                similarity_threshold=similarity_threshold,
                expansion_order=expansion_order,
                max_nodes_per_order=max_nodes_per_order,
                layout_algorithm=layout_algorithm,
                embedding_model_config=None,  # Will be pulled from config
                llm_model_config=llm_model_config,
                task_id=task_id,  # Use the actual task ID
                progress_callback=sync_progress_callback,  # Pass the sync progress callback
                profile_id=profile_id,
                profile_ids=profile_ids,
                profile_tag=profile_tag,
                profile_tags=profile_tags
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
            
            # Auto-save the mind-map as a report if generated from a topic
            report_id = None
            topic_id = config.get("topic_id")
            if topic_id and mindmap_data:
                try:
                    print(f"DEBUG: Auto-saving mind-map for topic {topic_id}")
                    from ..data_access import TopicsRepository, MindmapReportRepository
                    
                    # Get topic details for report title
                    topic_data = TopicsRepository.get(topic_id)
                    topic_label = topic_data['label'] if topic_data else f"Topic {topic_id}"
                    
                    # Create auto-save title
                    auto_title = f"Mind-Map: {topic_label[:60]}..." if len(topic_label) > 60 else f"Mind-Map: {topic_label}"
                    
                    # Get seed paper for report
                    seed_paper = PaperRepository.get_by_id(int(paper_id))
                    seed_paper_title = seed_paper['title'] if seed_paper else f"Paper {paper_id}"
                    
                    # Prepare parameters from config and result
                    save_parameters = {
                        "k": config.get("k", 10),
                        "similarity_threshold": config.get("similarity_threshold", 0.3),
                        "layout_algorithm": layout_algorithm,
                        "expansion_order": config.get("expansion_order", 2),
                        "max_nodes_per_order": config.get("max_nodes_per_order", 5),
                        "generated_from": "topic",
                        "topic_id": topic_id,
                        "auto_generated": True
                    }
                    
                    # Save as report
                    report_id = MindmapReportRepository.insert(
                        title=auto_title,
                        description=f"Auto-generated mind-map from topic '{topic_label}' using seed paper: {seed_paper_title}",
                        seed_paper_id=int(paper_id),
                        seed_paper_title=seed_paper_title,
                        mindmap_data=mindmap_data,
                        parameters=save_parameters,
                        statistics=result.get('statistics', {
                            "nodes_count": len(nodes),
                            "edges_count": len(edges), 
                            "layout_algorithm": layout_algorithm
                        })
                    )
                    print(f"DEBUG: Mind-map auto-saved as report {report_id}")
                    
                except Exception as save_error:
                    print(f"DEBUG: Failed to auto-save mind-map: {save_error}")
                    # Don't fail the task if save fails, just log it
            
            print(f"DEBUG: About to send completion status update")
            # Add a small delay to ensure WebSocket has time to connect
            await asyncio.sleep(0.5)
            
            # Create the result object that will be sent via WebSocket
            completion_result = {
                "mindmap_data": mindmap_data,
                "seed_paper_id": paper_id,
                "nodes_count": len(nodes),
                "edges_count": len(edges),
                "layout_algorithm": layout_algorithm,
                "report_id": report_id,  # Include the saved report ID
                "auto_saved": report_id is not None
            }
            print(f"DEBUG: Completion result structure: {list(completion_result.keys())}")
            print(f"DEBUG: Mindmap data structure being sent: {list(mindmap_data.keys()) if mindmap_data else 'None'}")
            if mindmap_data and 'nodes' in mindmap_data:
                print(f"DEBUG: First node sample: {mindmap_data['nodes'][0] if mindmap_data['nodes'] else 'No nodes'}")
            
            # Create completion message
            base_message = f"Mind-map generated successfully with {len(nodes)} nodes and {len(edges)} edges"
            if report_id:
                completion_message = f"{base_message} and auto-saved as report #{report_id}"
            else:
                completion_message = base_message
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                completion_message,
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
            task = TaskRepository.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            if isinstance(task["config_json"], str):
                config = json.loads(task["config_json"])
            else:
                config = task["config_json"]
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
            from LLMFactory import LLMModelFactory
            
            # Get embedding model configuration with proper fallback hierarchy: DB -> config file -> defaults
            orchestration_config = self._get_orchestration_config()
            embedding_config = orchestration_config.get("embedding_model", {})
            
            # Create embedding model
            # Normalize model_type: handle both "sentence-transformers" and "sentence-transformer"
            embedding_model_type = embedding_config.get("model_type", "sentence-transformer")
            if embedding_model_type == "sentence-transformers":
                embedding_model_type = "sentence-transformer"
            
            embedding_model = LLMModelFactory.create_model(
                model_type=embedding_model_type,
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
                    paper = PaperRepository.get_by_id(int(paper_id))
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
                        PaperFulltextRepository.insert(
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

    async def run_profile_aware_ingest_task(self, task_id: str):
        """Run profile-aware paper ingestion task."""
        try:
            print(f"DEBUG: Starting profile-aware ingestion task {task_id}")
            task = TaskRepository.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            if isinstance(task["config_json"], str):
                config = json.loads(task["config_json"])
            else:
                config = task["config_json"]
            
            # Extract configuration parameters
            start_date = config.get("start_date")
            end_date = config.get("end_date")
            profile_ids = config.get("profile_ids", [])
            profile_tags = config.get("profile_tags", [])
            score_all_profiles = config.get("score_all_profiles", False)
            overwrite_existing = config.get("overwrite_existing", False)
            cosine_threshold = config.get("cosine_threshold", 0.5)
            arxiv_categories = config.get("arxiv_categories", [])
            batch_size = config.get("batch_size", 10)
            send_error_notifications = config.get("send_error_notifications", False)
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Starting profile-aware paper ingestion",
                progress=5,
                current_step="initializing",
            )
            
            # Resolve target profiles
            from ..data_access.profiles import ProfileRepository
            target_profiles = []
            
            if profile_ids:
                for profile_id in profile_ids:
                    profile = ProfileRepository.get_by_id(profile_id)
                    if profile and profile['is_active']:
                        target_profiles.append(profile)
            
            if profile_tags:
                tag_profiles = ProfileRepository.get_by_tags(profile_tags)
                for profile in tag_profiles:
                    if profile['is_active'] and profile not in target_profiles:
                        target_profiles.append(profile)
            
            if score_all_profiles and not target_profiles:
                target_profiles = ProfileRepository.get_all_active()
            
            if not target_profiles:
                raise ValueError("No active profiles found matching the criteria")
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Resolved {len(target_profiles)} target profiles",
                progress=10,
                current_step="profiles_resolved",
            )
            
            # Stage 1: Run paper ingestion pipeline
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Running paper ingestion pipeline",
                progress=15,
                current_step="ingestion_start",
            )
            
            # Get existing paper IDs before ingestion to track what's new
            from ..data_access.papers import PaperRepository
            existing_paper_ids = set(PaperRepository.get_paper_ids_in_date_range(start_date, end_date))
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Found {len(existing_paper_ids)} existing papers in date range",
                progress=12,
                current_step="existing_papers_checked",
            )
            
            # Create progress callback for pipeline
            def pipeline_progress_callback(stage: str, progress: float, message: str = ""):
                # Convert pipeline progress to task progress (15% - 60%)
                task_progress = 15 + (progress * 0.45)
                
                # Use sync version of update_task_status to avoid event loop issues
                self.update_task_status_sync(
                    task_id,
                    TaskStatus.PROCESSING,
                    f"Ingestion: {stage} - {message}",
                    progress=task_progress,
                    current_step=f"ingestion_{stage}",
                )
            
            # Get orchestration config with proper fallback hierarchy: DB -> config file -> defaults
            orchestration_config = self._get_orchestration_config(verbose=True)
            
            # Update ArXiv categories if specified
            if arxiv_categories:
                if 'arxiv_search_categories' not in orchestration_config:
                    orchestration_config['arxiv_search_categories'] = {}
                orchestration_config['arxiv_search_categories']['filter_categories'] = arxiv_categories
            
            # Run profile-aware ingestion pipeline
            theseus_insight = TheseusInsight(
                start_date_override=start_date,
                end_date_override=end_date,
                cosine_similarity_threshold=cosine_threshold,
                db_saving=True,
                verbose=True,
                orchestration_config=orchestration_config,
                task_id=task_id,
                send_error_notifications=send_error_notifications,
                generate_email=False  # Bulk operations should not send newsletters
            )
            
            # Run the profiles pipeline (stores all papers without scoring)
            # Use asyncio.to_thread to avoid blocking the event loop during embedding
            ingestion_result = await asyncio.to_thread(
                theseus_insight.run_profiles_pipeline,
                progress_callback=pipeline_progress_callback
            )
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Ingestion completed: {ingestion_result.get('saved_count', 0)} papers saved",
                progress=60,
                current_step="ingestion_complete",
            )
            
            # Get new paper IDs after ingestion
            all_paper_ids_after = set(PaperRepository.get_paper_ids_in_date_range(start_date, end_date))
            new_paper_ids = list(all_paper_ids_after - existing_paper_ids)
            
            # If overwrite_existing is True, score all papers, not just new ones
            papers_to_score_ids = None if overwrite_existing else new_paper_ids
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Identified {len(new_paper_ids)} new papers, will score {len(papers_to_score_ids) if papers_to_score_ids else 'all'} papers",
                progress=62,
                current_step="new_papers_identified",
            )
            
            # Stage 2: Run profile-aware scoring
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Starting profile-aware scoring",
                progress=65,
                current_step="scoring_start",
            )
            
            # Create bulk judge runner
            judge_config = orchestration_config.get("judge_model", {})
            
            # Get embedding model for optimizations if available
            embedding_model = None
            embedding_config = orchestration_config.get("embedding_model", {})
            if embedding_config:
                try:
                    from LLMFactory import LLMModelFactory
                    # Normalize model_type: handle both "sentence-transformers" and "sentence-transformer"
                    embedding_model_type = embedding_config.get("model_type", "sentence-transformer")
                    if embedding_model_type == "sentence-transformers":
                        embedding_model_type = "sentence-transformer"
                    
                    embedding_model = LLMModelFactory.create_model(
                        model_type=embedding_model_type,
                        model_name=embedding_config.get("model_name", "Alibaba-NLP/gte-large-en-v1.5"),
                        **{k: v for k, v in embedding_config.items() if k not in ["model_type", "model_name"]}
                    )
                except Exception as e:
                    print(f"Warning: Could not load embedding model for optimizations: {e}")
            
            from ..data_access.bulk_judge import BulkJudgeRunner
            bulk_judge = BulkJudgeRunner(
                judge_config, 
                verbose=True,
                use_optimized_scorer=True,
                embedding_model=embedding_model
            )
            
            # Create bulk judge request
            from ..api.models import BulkJudgeRunRequest
            judge_request = BulkJudgeRunRequest(
                profile_ids=profile_ids if profile_ids else None,
                profile_tags=profile_tags if profile_tags else None,
                date_from=start_date,
                date_to=end_date,
                batch_size=batch_size,
                overwrite_existing=overwrite_existing,
                paper_ids=papers_to_score_ids  # Only score new papers unless overwrite_existing
            )
            
            # Scoring progress callback
            def scoring_progress_callback(stage: str, current: int, total: int):
                # Convert scoring progress to task progress (65% - 95%)
                scoring_progress = (current / total) * 100 if total > 0 else 0
                task_progress = 65 + (scoring_progress * 0.30)
                
                # Use sync version of update_task_status to avoid event loop issues
                self.update_task_status_sync(
                    task_id,
                    TaskStatus.PROCESSING,
                    f"Scoring: {stage} ({current}/{total})",
                    progress=task_progress,
                    current_step=f"scoring_{stage}",
                )
            
            # Run bulk judge scoring
            judge_result = await bulk_judge.run_bulk_judge(
                judge_request,
                progress_callback=scoring_progress_callback
            )
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Profile-aware scoring completed",
                progress=95,
                current_step="scoring_complete",
            )
            
            # Create final result
            final_result = {
                "ingestion_result": ingestion_result,
                "scoring_result": {
                    "job_id": judge_result.job_id,
                    "status": judge_result.status,
                    "profile_count": judge_result.profile_count,
                    "estimated_papers": judge_result.estimated_papers,
                    "message": judge_result.message
                },
                "target_profiles": [p['name'] for p in target_profiles],
                "papers_ingested": ingestion_result.get('saved_count', 0),
                "papers_scored": judge_result.estimated_papers
            }
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                f"Profile-aware ingestion completed: {ingestion_result.get('saved_count', 0)} papers ingested, {judge_result.profile_count} profiles scored",
                progress=100,
                current_step="task_complete",
                result=final_result,
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                f"Profile-aware ingestion task failed: {str(e)}",
                error=str(e),
                current_step="task_failed",
            )
            raise

    async def run_bulk_embed_task(self, task_id: str):
        """
        Run a bulk embedding task that downloads and embeds papers without profile scoring.
        
        This task:
        1. Downloads papers from ArXiv based on date range
        2. Embeds all paper abstracts without filtering
        3. Stores embedded papers in the database
        4. Does NOT perform any profile-specific scoring
        """
        try:
            # Get task configuration
            task = TaskRepository.get_task(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            # Debug: Check if config is in JSON format
            print(f"[DEBUG] Raw task data: {task}")
            config_json_value = task.get("config_json")
            print(f"[DEBUG] config_json value: {config_json_value} (type: {type(config_json_value)})")
            
            if isinstance(config_json_value, str):
                config = json.loads(config_json_value)
                print(f"[DEBUG] Parsed config from JSON string: {config}")
            elif isinstance(config_json_value, dict):
                config = config_json_value
                print(f"[DEBUG] Using config_json as dict: {config}")
            else:
                config = task.get("config", {})
                print(f"[DEBUG] Fallback to config field: {config}")
            
            start_date = config.get("start_date")
            end_date = config.get("end_date")
            batch_size = config.get("batch_size", 100)
            skip_existing = config.get("skip_existing", True)
            arxiv_categories = config.get("arxiv_categories", None)
            
            print(f"[DEBUG] Extracted from config - arxiv_categories: {arxiv_categories}")
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Starting bulk embedding from {start_date} to {end_date}",
                progress=5,
                current_step="initialization",
            )
            
            # Check for existing papers if skip_existing is enabled
            if skip_existing:
                from ..data_access.papers import PaperRepository
                existing_papers = PaperRepository.get_papers_in_date_range(start_date, end_date)
                existing_count = len(existing_papers)
                embedded_count = sum(1 for p in existing_papers if p.get('embedding_model') is not None)
                
                await self.update_task_status(
                    task_id,
                    TaskStatus.PROCESSING,
                    f"Found {existing_count} existing papers ({embedded_count} with embeddings)",
                    progress=10,
                    current_step="checking_existing",
                )
            
            # Create progress callback for pipeline
            def pipeline_progress_callback(stage: str, progress: float, message: str = ""):
                # Convert pipeline progress to task progress (10% - 90%)
                task_progress = 10 + (progress * 0.8)
                
                # Use sync version of update_task_status to avoid event loop issues
                self.update_task_status_sync(
                    task_id,
                    TaskStatus.PROCESSING,
                    f"Embedding: {stage} - {message}",
                    progress=task_progress,
                    current_step=f"embedding_{stage}",
                )
            
            # Get orchestration config with proper fallback hierarchy: DB -> config file -> defaults  
            orchestration_config = self._get_orchestration_config()
            
            # Debug: Always print what we received
            print(f"[DEBUG] Task handler received arxiv_categories: {arxiv_categories} (type: {type(arxiv_categories)})")
            print(f"[DEBUG] Current orchestration_config: {orchestration_config.get('arxiv_search_categories', 'NOT SET')}")
            
            # Override arxiv categories if provided
            if arxiv_categories is not None:
                print(f"[DEBUG] Processing arxiv_categories: {arxiv_categories}")
                if 'arxiv_search_categories' not in orchestration_config:
                    orchestration_config['arxiv_search_categories'] = {}
                
                # Check for special "ALL" flag
                if arxiv_categories and len(arxiv_categories) > 0 and arxiv_categories[0] == 'ALL':
                    orchestration_config['arxiv_search_categories']['filter_categories'] = None
                    orchestration_config['arxiv_search_categories']['main_category'] = None
                    print("[DEBUG] Setting categories to None for ALL papers")
                elif len(arxiv_categories) == 0:
                    # Empty array - use defaults (shouldn't happen with new UI)
                    print("[DEBUG] Empty array - using defaults")
                else:
                    orchestration_config['arxiv_search_categories']['filter_categories'] = arxiv_categories
                    # If main category is provided, use the prefix
                    main_cat = arxiv_categories[0].split('.')[0]
                    orchestration_config['arxiv_search_categories']['main_category'] = main_cat
                    print(f"[DEBUG] Setting specific categories: {arxiv_categories}")
            else:
                print("[DEBUG] arxiv_categories is None - using existing config")
            
            print(f"[DEBUG] Final orchestration_config: {orchestration_config.get('arxiv_search_categories', 'NOT SET')}")
            
            # Run embedding-only pipeline
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                "Starting paper download and embedding",
                progress=15,
                current_step="embedding_start",
            )
            
            theseus_insight = TheseusInsight(
                start_date_override=start_date,
                end_date_override=end_date,
                db_saving=True,
                verbose=True,
                orchestration_config=orchestration_config,
                task_id=task_id,
                generate_email=False  # Bulk operations should not send newsletters
            )
            
            # Set additional attributes after instantiation
            theseus_insight.batch_size = batch_size
            theseus_insight.skip_existing = skip_existing
            
            # Run the embedding-only pipeline
            # Use asyncio.to_thread to avoid blocking the event loop during embedding
            result = await asyncio.to_thread(
                theseus_insight.run_embedding_only_pipeline,
                progress_callback=pipeline_progress_callback
            )
            
            papers_saved = result.get('saved_count', 0)
            papers_skipped = result.get('skipped_count', 0)
            papers_embedded = result.get('embedded_count', 0)
            
            await self.update_task_status(
                task_id,
                TaskStatus.PROCESSING,
                f"Embedding completed: {papers_embedded} papers embedded, {papers_saved} new papers saved",
                progress=95,
                current_step="finalization",
            )
            
            # Prepare final result
            final_result = {
                "papers_saved": papers_saved,
                "papers_embedded": papers_embedded,
                "papers_skipped": papers_skipped,
                "start_date": start_date,
                "end_date": end_date,
                "batch_size": batch_size,
                "skip_existing": skip_existing,
                "status": "success"
            }
            
            await self.update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                f"Bulk embedding completed successfully. {papers_embedded} papers embedded.",
                result=final_result,
                progress=100,
                current_step="completed",
            )
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self.update_task_status(
                task_id,
                TaskStatus.FAILED,
                f"Bulk embedding task failed: {str(e)}",
                error=str(e),
                current_step="task_failed",
            )
            raise


# Create global task manager instance
task_manager = TaskManager() 
