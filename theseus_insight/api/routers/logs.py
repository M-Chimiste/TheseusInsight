from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from ...data_access import LogsRepository, TaskRepository

router = APIRouter(prefix="/api", tags=["logs"])

def _convert_task_timestamps(task_dict: dict) -> dict:
    """Convert PostgreSQL datetime objects to ISO strings for Pydantic models."""
    task_copy = task_dict.copy()
    
    # Handle datetime fields - PostgreSQL returns datetime objects directly
    for field in ['start_time', 'end_time', 'datetime_run']:
        if task_copy.get(field):
            if isinstance(task_copy[field], datetime):
                task_copy[field] = task_copy[field].isoformat()
    
    return task_copy

# Pydantic model for Log entries
class LogEntry(BaseModel):
    """
    Pydantic model for Log entries.

    This model defines the structure of log entries in the database.
    """
    task_id: str
    status: str
    datetime_run: str

# Pydantic model for Task History entries 
class TaskHistoryEntry(BaseModel):
    """
    Pydantic model for Task History entries.

    This model defines the structure of task history entries in the database.
    """
    task_id: str
    task_type: str
    status: str
    start_time: str
    end_time: str | None
    progress: float | None
    current_step: str | None
    message: str | None
    error: str | None

@router.get("/logs", response_model=List[LogEntry])
async def get_logs_api(
    limit: int = Query(100, gt=0, le=1000),
    from_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"), # YYYY-MM-DD
    to_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$") # YYYY-MM-DD
):
    """
    Retrieves recent logs, filterable by date.

    This endpoint fetches the most recent logs from the database, optionally filtered by date range.
    It returns a list of log entries with task ID, status, and timestamp.
    """
    try:
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date cannot be after to_date")
        
        logs_data = LogsRepository.recent(limit=limit, from_date=from_date, to_date=to_date)
        return [LogEntry(**_convert_task_timestamps(log)) for log in logs_data]
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Consider logging the exception for server-side debugging
        print(f"Error fetching logs: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching logs.")

@router.get("/task-history", response_model=List[TaskHistoryEntry])
async def get_task_history_api(
    limit: int = Query(100, gt=0, le=1000),
    from_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"), # YYYY-MM-DD
    to_date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$") # YYYY-MM-DD
):
    """
    Retrieves recent task history with complete information including task type.

    This endpoint fetches the most recent task history from the database, optionally filtered by date range.
    It returns a list of task history entries with task ID, task type, status, start time, end time, progress, current step, message, and error.
    """
    try:
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date cannot be after to_date")
        
        task_history_data = TaskRepository.recent(limit=limit, from_date=from_date, to_date=to_date)
        return [TaskHistoryEntry(**_convert_task_timestamps(task)) for task in task_history_data]
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"Error fetching task history: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching task history.") 