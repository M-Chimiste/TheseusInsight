from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import tempfile
import uuid
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

from ..tasks import task_manager
from ...db import get_pool_stats

router = APIRouter(prefix="/api/settings/database", tags=["database"])

class ExportRequest(BaseModel):
    """Request model for database export with incremental options."""
    incremental: bool = False
    since_timestamp: Optional[str] = None  # ISO format timestamp
    tables: Optional[List[str]] = None
    batch_size: int = 1000
    streaming: bool = False
    parallel: bool = False
    max_workers: int = 4

@router.get("/export")
async def export_database(background_tasks: BackgroundTasks):
    """
    Initiates the database export process and returns a background task for cleanup.

    This endpoint triggers the export of the database to a compressed archive file.
    It creates a background task to clean up the exported file after a certain period of time.

    Args:
        background_tasks (BackgroundTasks): An instance of BackgroundTasks for managing background tasks.

    Returns:
        None: This endpoint does not return a value. It initiates a background task for database export and cleanup.

    Raises:
        HTTPException: If the database export fails or the archive file is not created successfully.
        Exception: If an internal server error occurs while processing the database export.
    """
    try:
        from ...utils.db_migration.db_export import DatabaseExporter
        
        print("INFO:     Starting database export...")
        
        # Create timestamp for filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Get database URL from environment
        DB_URL = os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb")
        
        # Create a temporary directory for the export files
        with tempfile.TemporaryDirectory() as temp_dir:
            export_dir = os.path.join(temp_dir, "export")
            
            # Use the existing DatabaseExporter
            exporter = DatabaseExporter(DB_URL, export_dir)
            
            print("INFO:     Exporting database tables...")
            # Export all data to JSON files
            papers_file = exporter.export_papers()
            podcasts_file = exporter.export_podcasts()
            newsletters_file = exporter.export_newsletters()
            metadata_file = exporter.create_metadata()
            
            # Create archive file outside temp directory to persist after context exit
            # Create data/temp directory if it doesn't exist
            os.makedirs("data/temp", exist_ok=True)
            archive_file = os.path.join("data/temp", f"theseus_backup_{timestamp}.tar.gz")
            
            print(f"INFO:     Creating archive at {archive_file}...")
            # Create compressed archive
            import tarfile
            with tarfile.open(archive_file, "w:gz") as tar:
                tar.add(export_dir, arcname=".")
        
        # Verify archive was created successfully
        if not os.path.exists(archive_file):
            raise HTTPException(status_code=500, detail="Archive file was not created successfully")
        
        archive_size = os.path.getsize(archive_file)
        if archive_size == 0:
            raise HTTPException(status_code=500, detail="Archive file is empty")
        
        print(f"INFO:     Export complete. Archive size: {archive_size / 1024 / 1024:.1f} MB")
        
        # Add a background task to clean up the file after 10 minutes (enough time for download)
        def cleanup_export_file(file_path: str):
            try:
                import time
                time.sleep(600)  # Wait 10 minutes
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"INFO:     Cleaned up export file: {file_path}")
            except Exception as e:
                print(f"Warning: Could not clean up export file {file_path}: {e}")
        
        background_tasks.add_task(cleanup_export_file, archive_file)
        
        # Return the archive file (temp directory is now cleaned up but archive persists)
        return FileResponse(
            archive_file,
            media_type="application/gzip",
            filename=f"theseus_backup_{timestamp}.tar.gz",
            headers={
                "Content-Disposition": f"attachment; filename=theseus_backup_{timestamp}.tar.gz",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
            
    except Exception as e:
        print(f"ERROR: Database export failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Database export failed: {str(e)}")

@router.post("/export-task")
async def start_database_export(request: ExportRequest = ExportRequest()):
    """
    Initiates a background database export task with optional incremental support.

    This endpoint initiates a new task for exporting the database to a compressed archive file.
    Supports both full and incremental exports with configurable options.

    Args:
        request: Export request with incremental options

    Returns:
        dict: A dictionary containing the task ID and a message for tracking the export progress.
    """
    import asyncio
    
    task_id = str(uuid.uuid4())

    # Prepare configuration for the export task
    config = {
        "incremental": request.incremental,
        "since_timestamp": request.since_timestamp,
        "tables": request.tables,
        "batch_size": request.batch_size,
        "streaming": request.streaming,
        "parallel": request.parallel,
        "max_workers": request.max_workers
    }

    await task_manager.create_task(
        task_id=task_id,
        task_type="database_export",
        config=config,
    )

    await task_manager.enqueue_task(task_manager.run_database_export_task, task_id)
    
    # Add a small delay to ensure task is fully initialized
    await asyncio.sleep(0.1)

    return {
        "task_id": task_id,
        "message": f"Database export started. Use WebSocket /ws/database-export/{task_id} for progress updates."
    }

@router.get("/export-task/{task_id}/download")
async def download_exported_database(task_id: str):
    """
    Downloads the archive generated by a completed export task.

    This endpoint retrieves the archive file generated by a completed database export task.
    It returns the archive file for download.

    Args:
        task_id (str): The ID of the completed export task.

    Returns:
        FileResponse: A file response containing the archive file.

    Raises:
        HTTPException: If the task is not found or not completed.
    """
    from ..tasks import TaskStatus
    
    task = task_manager.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if task["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Task is not completed (current status: {task['status']})")

    result = task.get("result_json", {})
    archive_path = result.get("archive_path")
    
    # Debug logging
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Task result: {result}")
    logger.info(f"Archive path from result: {archive_path}")
    
    if not archive_path or not os.path.exists(archive_path):
        logger.error(f"Archive path not found. Result: {result}, Path exists: {os.path.exists(archive_path) if archive_path else 'No path'}")
        raise HTTPException(status_code=404, detail="Export file not available")

    return FileResponse(
        archive_path,
        media_type="application/gzip",
        filename=os.path.basename(archive_path),
        headers={
            "Content-Disposition": f"attachment; filename={os.path.basename(archive_path)}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

@router.post("/import")
async def import_database(
    background_tasks: BackgroundTasks,
    backup_file: UploadFile = File(...),
    import_mode: str = Form("merge", description="Import mode: 'merge' (default) or 'overwrite'")
):
    """
    Imports a database from a compressed backup file using background task with progress updates.

    This endpoint accepts a compressed backup file and imports it into the database.
    It creates a background task to track the import progress.

    Args:
        background_tasks (BackgroundTasks): An instance of BackgroundTasks for managing background tasks.
        backup_file (UploadFile): The compressed backup file to import.
        import_mode (str): The import mode: 'merge' (default) or 'overwrite'.

    Returns:
        dict: A dictionary containing the task ID and a message for tracking the import progress.

    Raises:
        HTTPException: If the file format is invalid or the import mode is invalid.
        Exception: If an internal server error occurs while processing the database import.
    """
    try:
        if not backup_file.filename or not backup_file.filename.endswith(('.tar.gz', '.tgz')):
            raise HTTPException(
                status_code=400, 
                detail="Invalid file format. Please upload a .tar.gz or .tgz file."
            )
        
        if import_mode not in ["merge", "overwrite"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid import mode. Must be 'merge' or 'overwrite'."
            )
        
        # Create a task ID for tracking
        task_id = str(uuid.uuid4())
        
        # Save the uploaded file to a temporary location
        temp_file_path = f"data/temp/{task_id}_import.tar.gz"
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        
        with open(temp_file_path, "wb") as f:
            content = await backup_file.read()
            f.write(content)
        
        # Create the background task
        task_config = {
            "archive_path": temp_file_path,
            "import_mode": import_mode,
            "filename": backup_file.filename
        }
        
        await task_manager.create_task(
            task_id=task_id,
            task_type="database_import",
            config=task_config
        )
        
        await task_manager.enqueue_task(task_manager.run_database_import_task, task_id)
        
        return {
            "task_id": task_id,
            "message": f"Database import started. Use WebSocket /ws/database-import/{task_id} for progress updates."
        }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database import failed: {str(e)}")


@router.get("/pool-stats")
async def get_database_pool_stats() -> Dict[str, Any]:
    """
    Get connection pool statistics.
    
    Returns statistics about the database connection pool including:
    - Pool size and available connections
    - Connection reuse ratio
    - Average wait times
    - Error counts
    
    Returns:
        dict: Connection pool statistics or message if pooling is disabled
    """
    stats = get_pool_stats()
    
    if stats is None:
        return {
            "enabled": False,
            "message": "Connection pooling is disabled. Set DB_USE_POOL=true to enable."
        }
    
    return {
        "enabled": True,
        "pool_size": stats.get("pool_size", "N/A"),
        "pool_available": stats.get("pool_available", "N/A"),
        "connections_created": stats.get("connections_created", 0),
        "connections_reused": stats.get("connections_reused", 0),
        "reuse_ratio": f"{stats.get('reuse_ratio', 0):.1%}",
        "avg_wait_time_ms": round(stats.get("avg_wait_time", 0) * 1000, 2),
        "timeouts": stats.get("timeouts", 0),
        "errors": stats.get("errors", 0),
        "requests_queued": stats.get("requests_queued", 0),
        "last_reset": stats.get("last_reset", "N/A")
    } 