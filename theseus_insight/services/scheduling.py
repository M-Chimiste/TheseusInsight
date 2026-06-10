"""APScheduler suspend/restore around bulk jobs (extracted from the
bulk_operations router in refactor B7)."""
import logging
from uuid import UUID

from ..data_processing.checkpoint_manager import CheckpointManager

from ..scheduler import scheduler
from ..db import get_connection_pool

logger = logging.getLogger(__name__)

async def _suspend_scheduled_tasks():
    """Suspend all scheduled background tasks and return snapshot."""
    suspended_tasks = []

    try:
        # Get all scheduled jobs
        jobs = scheduler.scheduler.get_jobs()

        for job in jobs:
            if hasattr(job, 'id') and hasattr(job, 'next_run_time'):
                task_info = {
                    'job_id': job.id,
                    'name': getattr(job, 'name', ''),
                    'func': str(job.func),
                    'trigger': str(job.trigger),
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'enabled': True
                }
                suspended_tasks.append(task_info)

                # Pause the job
                job.pause()

        return suspended_tasks

    except Exception as e:
        print(f"Error suspending scheduled tasks: {e}")
        return suspended_tasks

async def _restore_scheduled_tasks(suspend_scheduled_tasks: bool, checkpoint_manager: CheckpointManager, job_id: UUID):
    """Restore suspended scheduled tasks."""
    if not suspend_scheduled_tasks:
        return

    try:
        # Get suspended tasks from job config
        job_record = await checkpoint_manager.get_job(job_id)
        if not job_record or not job_record.configuration:
            return

        suspended_tasks = job_record.configuration.get('suspended_tasks_snapshot', [])

        for task_info in suspended_tasks:
            try:
                # Find and resume the job
                jobs = scheduler.scheduler.get_jobs()
                for job in jobs:
                    if hasattr(job, 'id') and job.id == task_info.get('job_id'):
                        job.resume()
                        break
            except Exception as e:
                print(f"Error restoring task {task_info.get('job_id')}: {e}")

    except Exception as e:
        print(f"Error restoring scheduled tasks: {e}")

async def _restore_scheduled_tasks_on_cancel(job_id: UUID, pool):
    """Restore suspended tasks when job is canceled."""
    try:
        async with pool.acquire() as conn:
            configuration = await conn.fetchval(
                "SELECT configuration FROM processing_jobs WHERE id = $1",
                job_id
            )

            if configuration and isinstance(configuration, dict):
                suspend_scheduled_tasks = configuration.get('suspend_scheduled_tasks', False)
                if suspend_scheduled_tasks:
                    suspended_tasks = configuration.get('suspended_tasks_snapshot', [])

                    # Restore tasks using scheduler
                    for task_info in suspended_tasks:
                        try:
                            jobs = scheduler.scheduler.get_jobs()
                            for job in jobs:
                                if hasattr(job, 'id') and job.id == task_info.get('job_id'):
                                    job.resume()
                                    break
                        except Exception as e:
                            print(f"Error restoring task {task_info.get('job_id')}: {e}")

    except Exception as e:
        print(f"Error restoring scheduled tasks on cancel: {e}")
