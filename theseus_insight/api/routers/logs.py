from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel

from ..dependencies import db

router = APIRouter(prefix="/api", tags=["logs"])

# Pydantic model for Log entries
class LogEntry(BaseModel):
    task_id: str
    status: str
    datetime_run: str

# Pydantic model for Task History entries 
class TaskHistoryEntry(BaseModel):
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
    from_date: Optional[str] = Query(None, regex="^\\d{4}-\\d{2}-\\d{2}$"), # YYYY-MM-DD
    to_date: Optional[str] = Query(None, regex="^\\d{4}-\\d{2}-\\d{2}$") # YYYY-MM-DD
):
    """Get recent logs, filterable by date."""
    try:
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date cannot be after to_date")
        
        logs_data = db.get_recent_logs(limit=limit, from_date=from_date, to_date=to_date)
        return [LogEntry(**log) for log in logs_data]
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Consider logging the exception for server-side debugging
        print(f"Error fetching logs: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching logs.")

@router.get("/task-history", response_model=List[TaskHistoryEntry])
async def get_task_history_api(
    limit: int = Query(100, gt=0, le=1000),
    from_date: Optional[str] = Query(None, regex="^\\d{4}-\\d{2}-\\d{2}$"), # YYYY-MM-DD
    to_date: Optional[str] = Query(None, regex="^\\d{4}-\\d{2}-\\d{2}$") # YYYY-MM-DD
):
    """Get recent task history with complete information including task type."""
    try:
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date cannot be after to_date")
        
        task_history_data = db.get_recent_task_history(limit=limit, from_date=from_date, to_date=to_date)
        return [TaskHistoryEntry(**task) for task in task_history_data]
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        print(f"Error fetching task history: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching task history.") 