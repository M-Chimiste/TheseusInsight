from typing import Dict, Optional, List
import asyncio
import json
from datetime import datetime
from enum import Enum
from .models import RunStatus, NodeStatus
from ..data_access import TaskRepository, LogsRepository

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


    # ------------------------------------------------------------------
    # Task handlers — extracted to api/task_handlers/ (refactor B6).
    # These thin delegates keep the bound-method references that routers
    # pass to enqueue_task working unchanged. Imports are deliberately
    # lazy: handler modules import TaskStatus from this module.
    # ------------------------------------------------------------------

    async def run_newsletter_task(self, task_id: str):
        from .task_handlers import newsletter
        await newsletter.run(self, task_id)

    async def run_podcast_task(self, task_id: str):
        from .task_handlers import podcast
        await podcast.run(self, task_id)

    async def run_visualizer_task(self, task_id: str):
        from .task_handlers import visualizer
        await visualizer.run(self, task_id)

    async def run_database_export_task(self, task_id: str):
        from .task_handlers import database_io
        await database_io.run_export(self, task_id)

    async def run_database_import_task(self, task_id: str):
        from .task_handlers import database_io
        await database_io.run_import(self, task_id)

    async def run_mindmap_expand_task(self, task_id: str):
        from .task_handlers import mindmap
        await mindmap.run_expand(self, task_id)

    async def run_mindmap_pdf_parse_task(self, task_id: str):
        from .task_handlers import mindmap
        await mindmap.run_pdf_parse(self, task_id)

    async def run_profile_aware_ingest_task(self, task_id: str):
        from .task_handlers import profile_ingest
        await profile_ingest.run(self, task_id)

    async def run_bulk_embed_task(self, task_id: str):
        from .task_handlers import bulk_embed
        await bulk_embed.run(self, task_id)



            









# Create global task manager instance
task_manager = TaskManager() 
