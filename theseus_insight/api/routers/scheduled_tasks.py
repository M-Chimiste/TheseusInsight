"""
API router for scheduled tasks management.
Handles CRUD operations for user-configurable scheduled tasks.
"""

import asyncio
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ...db import get_cursor
from ...scheduler import scheduler as theseus_scheduler
from apscheduler.triggers.cron import CronTrigger
import json

router = APIRouter(prefix="/scheduled-tasks", tags=["scheduled_tasks"])


class ScheduledTaskConfig(BaseModel):
    """Configuration for scheduled tasks."""
    # Newsletter specific config
    emailRecipients: Optional[List[str]] = None
    researchInterests: Optional[List[str]] = None
    use_profile_recipients: Optional[bool] = False
    
    # General task config
    lookback_months: Optional[int] = None
    duration_months: Optional[int] = None
    min_papers: Optional[int] = None
    months_to_keep: Optional[int] = None
    
    # Additional fields can be added as needed

class ScheduledTaskCreate(BaseModel):
    """Request model for creating a scheduled task."""
    name: str = Field(..., description="Display name for the task")
    task_type: str = Field(..., description="Type of task (newsletter, trends_recomputation, etc.)")
    profile_id: Optional[int] = Field(None, description="Profile ID for profile-specific tasks")
    is_enabled: bool = Field(True, description="Whether the task is enabled")
    frequency: str = Field(..., description="Frequency: hourly, daily, weekly, monthly")
    
    # Schedule configuration
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    day_of_month: Optional[int] = Field(None, ge=1, le=31, description="Day of month (1-31)")
    hour: int = Field(..., ge=0, le=23, description="Hour (0-23)")
    minute: int = Field(0, ge=0, le=59, description="Minute (0-59)")
    timezone: str = Field("UTC", description="Timezone for the schedule")
    
    # Task-specific configuration
    config: ScheduledTaskConfig = Field(default_factory=ScheduledTaskConfig)


class ScheduledTaskUpdate(BaseModel):
    """Request model for updating a scheduled task."""
    name: Optional[str] = None
    is_enabled: Optional[bool] = None
    frequency: Optional[str] = None
    day_of_week: Optional[int] = Field(None, ge=0, le=6)
    day_of_month: Optional[int] = Field(None, ge=1, le=31)
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: Optional[int] = Field(None, ge=0, le=59)
    timezone: Optional[str] = None
    config: Optional[ScheduledTaskConfig] = None


class ScheduledTaskResponse(BaseModel):
    """Response model for scheduled task."""
    id: int
    name: str
    task_type: str
    profile_id: Optional[int]
    is_enabled: bool
    frequency: str
    day_of_week: Optional[int]
    day_of_month: Optional[int]
    hour: int
    minute: int
    timezone: str
    config: dict
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    last_run_status: Optional[str]
    last_run_task_id: Optional[str]
    run_count: int
    error_count: int
    created_at: datetime
    updated_at: datetime
    
    # Additional computed fields
    profile_name: Optional[str] = None


class ScheduledTaskRunResponse(BaseModel):
    """Response model for scheduled task run history."""
    id: int
    scheduled_task_id: int
    task_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    error_message: Optional[str]
    result: Optional[dict]


def calculate_next_run(frequency: str, hour: int, minute: int, 
                      day_of_week: Optional[int] = None, 
                      day_of_month: Optional[int] = None,
                      timezone: str = "UTC") -> datetime:
    """Calculate the next run time based on frequency and schedule settings."""
    now = datetime.utcnow()
    
    if frequency == "hourly":
        # Run at the specified minute of each hour
        next_run = now.replace(second=0, microsecond=0)
        if next_run.minute < minute:
            next_run = next_run.replace(minute=minute)
        else:
            next_run = next_run + timedelta(hours=1)
            next_run = next_run.replace(minute=minute)
            
    elif frequency == "daily":
        # Run at the specified hour and minute each day
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run = next_run + timedelta(days=1)
            
    elif frequency == "weekly":
        # Run on the specified day of week
        if day_of_week is None:
            day_of_week = 0  # Default to Monday
        
        days_ahead = day_of_week - now.weekday()
        if days_ahead < 0 or (days_ahead == 0 and now.time() > datetime.utcnow().replace(hour=hour, minute=minute).time()):
            days_ahead += 7
        
        next_run = now + timedelta(days=days_ahead)
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
    elif frequency == "monthly":
        # Run on the specified day of month
        if day_of_month is None:
            day_of_month = 1  # Default to first of month
        
        # Handle edge case where day doesn't exist in current month
        try:
            next_run = now.replace(day=day_of_month, hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            # If day doesn't exist (e.g., Feb 31), use last day of month
            import calendar
            last_day = calendar.monthrange(now.year, now.month)[1]
            next_run = now.replace(day=last_day, hour=hour, minute=minute, second=0, microsecond=0)
        
        if next_run <= now:
            # Move to next month
            if now.month == 12:
                next_run = next_run.replace(year=now.year + 1, month=1)
            else:
                next_run = next_run.replace(month=now.month + 1)
            
            # Handle edge case again for next month
            try:
                next_run = next_run.replace(day=day_of_month)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(next_run.year, next_run.month)[1]
                next_run = next_run.replace(day=last_day)
    
    return next_run


async def schedule_task_in_apscheduler(task_id: int, task_data: dict):
    """Schedule a task in APScheduler based on its configuration."""
    # Build cron trigger based on frequency
    frequency = task_data['frequency']
    hour = task_data['hour']
    minute = task_data['minute']
    
    if frequency == "hourly":
        trigger = CronTrigger(minute=minute)
    elif frequency == "daily":
        trigger = CronTrigger(hour=hour, minute=minute)
    elif frequency == "weekly":
        day_of_week = task_data.get('day_of_week', 0)
        trigger = CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)
    elif frequency == "monthly":
        day_of_month = task_data.get('day_of_month', 1)
        trigger = CronTrigger(day=day_of_month, hour=hour, minute=minute)
    else:
        raise ValueError(f"Unsupported frequency: {frequency}")
    
    # Add job to scheduler
    job = theseus_scheduler.scheduler.add_job(
        run_scheduled_task,
        trigger=trigger,
        args=[task_id],
        id=f"scheduled_task_{task_id}",
        name=task_data['name'],
        replace_existing=True
    )
    
    return job.next_run_time


async def run_scheduled_task(task_id: int):
    """Execute a scheduled task."""
    from ...api.tasks import task_manager
    from uuid import uuid4
    
    with get_cursor() as cursor:
        # Get task details
        cursor.execute("""
            SELECT id, name, task_type, profile_id, config
            FROM scheduled_tasks
            WHERE id = %s AND is_enabled = true
        """, (task_id,))
        task_data = cursor.fetchone()
        
        if not task_data:
            print(f"Scheduled task {task_id} not found or disabled")
            return
        
        # Create a unique task ID
        task_uuid = str(uuid4())
        
        # Record the run start
        cursor.execute("""
            INSERT INTO scheduled_task_runs (scheduled_task_id, task_id, started_at, status)
            VALUES (%s, %s, %s, 'running')
            RETURNING id
        """, (task_id, task_uuid, datetime.utcnow()))
        run_id = cursor.fetchone()['id']
        
        # Update last run info
        cursor.execute("""
            UPDATE scheduled_tasks 
            SET last_run_at = %s, last_run_task_id = %s
            WHERE id = %s
        """, (datetime.utcnow(), task_uuid, task_id))
    
    try:
        # Prepare task configuration based on task type
        task_config = task_data['config'] or {}
        
        if task_data['task_type'] == 'newsletter':
            # Newsletter generation task
            if task_data['profile_id']:
                task_config['profile_id'] = task_data['profile_id']
            
            await task_manager.create_task(
                task_id=task_uuid,
                task_type="newsletter",
                config=task_config
            )
            await task_manager.enqueue_task(
                task_manager.run_newsletter_task,
                task_uuid
            )
            
        elif task_data['task_type'] == 'trends_recomputation':
            # Trends recomputation - run directly
            from ...scheduler import scheduler
            await scheduler._run_nightly_trends_recomputation()
            
        elif task_data['task_type'] == 'database_cleanup':
            # Database cleanup - run directly
            from ...scheduler import scheduler
            await scheduler._run_weekly_cleanup()
            
        # Update run status
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE scheduled_task_runs
                SET completed_at = %s, status = 'completed'
                WHERE id = %s
            """, (datetime.utcnow(), run_id))
            
            cursor.execute("""
                UPDATE scheduled_tasks
                SET last_run_status = 'completed', run_count = run_count + 1,
                    next_run_at = %s
                WHERE id = %s
            """, (
                calculate_next_run(
                    task_data['frequency'],
                    task_data['hour'],
                    task_data['minute'],
                    task_data.get('day_of_week'),
                    task_data.get('day_of_month'),
                    task_data.get('timezone', 'UTC')
                ),
                task_id
            ))
            
    except Exception as e:
        # Record the error
        with get_cursor() as cursor:
            cursor.execute("""
                UPDATE scheduled_task_runs
                SET completed_at = %s, status = 'failed', error_message = %s
                WHERE id = %s
            """, (datetime.utcnow(), str(e), run_id))
            
            cursor.execute("""
                UPDATE scheduled_tasks
                SET last_run_status = 'failed', error_count = error_count + 1
                WHERE id = %s
            """, (task_id,))
        raise


@router.get("/", response_model=List[ScheduledTaskResponse])
async def get_scheduled_tasks(
    profile_id: Optional[int] = None,
    task_type: Optional[str] = None,
    is_enabled: Optional[bool] = None
):
    """Get all scheduled tasks with optional filtering."""
    with get_cursor() as cursor:
        query = """
            SELECT st.*, p.name as profile_name
            FROM scheduled_tasks st
            LEFT JOIN profiles p ON st.profile_id = p.id
            WHERE 1=1
        """
        params = []
        
        if profile_id is not None:
            query += " AND st.profile_id = %s"
            params.append(profile_id)
        
        if task_type:
            query += " AND st.task_type = %s"
            params.append(task_type)
            
        if is_enabled is not None:
            query += " AND st.is_enabled = %s"
            params.append(is_enabled)
            
        query += " ORDER BY st.created_at DESC"
        
        cursor.execute(query, params)
        tasks = cursor.fetchall()
        
        return [ScheduledTaskResponse(**task) for task in tasks]


@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_scheduled_task(task_id: int):
    """Get a specific scheduled task."""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT st.*, p.name as profile_name
            FROM scheduled_tasks st
            LEFT JOIN profiles p ON st.profile_id = p.id
            WHERE st.id = %s
        """, (task_id,))
        task = cursor.fetchone()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scheduled task not found")
        
        return ScheduledTaskResponse(**task)


@router.post("/", response_model=ScheduledTaskResponse)
async def create_scheduled_task(task: ScheduledTaskCreate):
    """Create a new scheduled task."""
    with get_cursor() as cursor:
        # Calculate next run time
        next_run_at = calculate_next_run(
            task.frequency,
            task.hour,
            task.minute,
            task.day_of_week,
            task.day_of_month,
            task.timezone
        )
        
        # Insert the task
        cursor.execute("""
            INSERT INTO scheduled_tasks (
                name, task_type, profile_id, is_enabled, frequency,
                day_of_week, day_of_month, hour, minute, timezone,
                config, next_run_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            ) RETURNING id
        """, (
            task.name,
            task.task_type,
            task.profile_id,
            task.is_enabled,
            task.frequency,
            task.day_of_week,
            task.day_of_month,
            task.hour,
            task.minute,
            task.timezone,
            json.dumps(task.config.dict()),
            next_run_at
        ))
        task_id = cursor.fetchone()['id']
        
        # If enabled, schedule in APScheduler
        if task.is_enabled:
            task_data = {
                'id': task_id,
                'name': task.name,
                'frequency': task.frequency,
                'hour': task.hour,
                'minute': task.minute,
                'day_of_week': task.day_of_week,
                'day_of_month': task.day_of_month
            }
            await schedule_task_in_apscheduler(task_id, task_data)
        
        # Fetch and return the created task
        cursor.execute("""
            SELECT st.*, p.name as profile_name
            FROM scheduled_tasks st
            LEFT JOIN profiles p ON st.profile_id = p.id
            WHERE st.id = %s
        """, (task_id,))
        
        return ScheduledTaskResponse(**cursor.fetchone())


@router.put("/{task_id}", response_model=ScheduledTaskResponse)
async def update_scheduled_task(task_id: int, update: ScheduledTaskUpdate):
    """Update a scheduled task."""
    with get_cursor() as cursor:
        # Get current task
        cursor.execute("SELECT * FROM scheduled_tasks WHERE id = %s", (task_id,))
        current_task = cursor.fetchone()
        
        if not current_task:
            raise HTTPException(status_code=404, detail="Scheduled task not found")
        
        # Build update query
        update_fields = []
        update_values = []
        
        if update.name is not None:
            update_fields.append("name = %s")
            update_values.append(update.name)
            
        if update.is_enabled is not None:
            update_fields.append("is_enabled = %s")
            update_values.append(update.is_enabled)
            
        if update.frequency is not None:
            update_fields.append("frequency = %s")
            update_values.append(update.frequency)
            
        if update.day_of_week is not None:
            update_fields.append("day_of_week = %s")
            update_values.append(update.day_of_week)
            
        if update.day_of_month is not None:
            update_fields.append("day_of_month = %s")
            update_values.append(update.day_of_month)
            
        if update.hour is not None:
            update_fields.append("hour = %s")
            update_values.append(update.hour)
            
        if update.minute is not None:
            update_fields.append("minute = %s")
            update_values.append(update.minute)
            
        if update.timezone is not None:
            update_fields.append("timezone = %s")
            update_values.append(update.timezone)
            
        if update.config is not None:
            update_fields.append("config = %s")
            update_values.append(json.dumps(update.config.dict()))
        
        # Calculate new next_run_at if schedule changed
        schedule_changed = any([
            update.frequency is not None,
            update.hour is not None,
            update.minute is not None,
            update.day_of_week is not None,
            update.day_of_month is not None
        ])
        
        if schedule_changed:
            # Use updated values or fall back to current
            next_run_at = calculate_next_run(
                update.frequency or current_task['frequency'],
                update.hour if update.hour is not None else current_task['hour'],
                update.minute if update.minute is not None else current_task['minute'],
                update.day_of_week if update.day_of_week is not None else current_task['day_of_week'],
                update.day_of_month if update.day_of_month is not None else current_task['day_of_month'],
                update.timezone or current_task['timezone']
            )
            update_fields.append("next_run_at = %s")
            update_values.append(next_run_at)
        
        # Execute update
        if update_fields:
            update_values.append(task_id)
            cursor.execute(f"""
                UPDATE scheduled_tasks 
                SET {', '.join(update_fields)}
                WHERE id = %s
            """, update_values)
        
        # Update APScheduler if needed
        is_enabled = update.is_enabled if update.is_enabled is not None else current_task['is_enabled']
        
        # Remove existing job
        try:
            theseus_scheduler.scheduler.remove_job(f"scheduled_task_{task_id}")
        except:
            pass
        
        # Add new job if enabled
        if is_enabled:
            cursor.execute("SELECT * FROM scheduled_tasks WHERE id = %s", (task_id,))
            updated_task = cursor.fetchone()
            await schedule_task_in_apscheduler(task_id, updated_task)
        
        # Return updated task
        cursor.execute("""
            SELECT st.*, p.name as profile_name
            FROM scheduled_tasks st
            LEFT JOIN profiles p ON st.profile_id = p.id
            WHERE st.id = %s
        """, (task_id,))
        
        return ScheduledTaskResponse(**cursor.fetchone())


@router.delete("/{task_id}")
async def delete_scheduled_task(task_id: int):
    """Delete a scheduled task."""
    with get_cursor() as cursor:
        # Check if task exists
        cursor.execute("SELECT id FROM scheduled_tasks WHERE id = %s", (task_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Scheduled task not found")
        
        # Remove from APScheduler
        try:
            theseus_scheduler.scheduler.remove_job(f"scheduled_task_{task_id}")
        except:
            pass
        
        # Delete from database (cascades to runs)
        cursor.execute("DELETE FROM scheduled_tasks WHERE id = %s", (task_id,))
        
        return {"message": "Scheduled task deleted successfully"}


@router.get("/{task_id}/runs", response_model=List[ScheduledTaskRunResponse])
async def get_scheduled_task_runs(
    task_id: int,
    limit: int = 10,
    offset: int = 0
):
    """Get run history for a scheduled task."""
    with get_cursor() as cursor:
        # Check if task exists
        cursor.execute("SELECT id FROM scheduled_tasks WHERE id = %s", (task_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Scheduled task not found")
        
        # Get runs
        cursor.execute("""
            SELECT * FROM scheduled_task_runs
            WHERE scheduled_task_id = %s
            ORDER BY started_at DESC
            LIMIT %s OFFSET %s
        """, (task_id, limit, offset))
        
        runs = cursor.fetchall()
        
        return [ScheduledTaskRunResponse(**run) for run in runs]


@router.post("/{task_id}/run")
async def run_scheduled_task_now(task_id: int):
    """Manually trigger a scheduled task to run immediately."""
    with get_cursor() as cursor:
        # Check if task exists and is enabled
        cursor.execute("""
            SELECT id, is_enabled FROM scheduled_tasks WHERE id = %s
        """, (task_id,))
        task = cursor.fetchone()
        
        if not task:
            raise HTTPException(status_code=404, detail="Scheduled task not found")
        
        if not task['is_enabled']:
            raise HTTPException(status_code=400, detail="Cannot run disabled task")
    
    # Run the task asynchronously
    asyncio.create_task(run_scheduled_task(task_id))
    
    return {"message": "Task execution started", "task_id": task_id}


@router.post("/sync")
async def sync_scheduled_tasks():
    """Sync scheduled tasks with APScheduler (e.g., after server restart)."""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM scheduled_tasks
            WHERE is_enabled = true
        """)
        tasks = cursor.fetchall()
        
        synced_count = 0
        for task in tasks:
            try:
                await schedule_task_in_apscheduler(task['id'], task)
                synced_count += 1
            except Exception as e:
                print(f"Failed to sync task {task['id']}: {e}")
    
    return {"message": f"Synced {synced_count} scheduled tasks"}