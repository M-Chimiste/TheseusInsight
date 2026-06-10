"""Task handler(s) extracted from TaskManager (refactor B6): run_database_export_task, run_database_import_task."""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional, List
import asyncio
import json
import os
from datetime import datetime

from ..tasks import TaskStatus
from ...data_access import (
    TaskRepository, LogsRepository, SettingsRepository,
    PaperRepository, PaperFulltextRepository
)
from ._common import get_orchestration_config, progress_callback

if TYPE_CHECKING:
    from ..tasks import TaskManager


async def run_export(task_manager: "TaskManager", task_id: str):
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
        await task_manager.update_task_status(
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
                    task_manager.update_task_status(
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

        await task_manager.update_task_status(
            task_id,
            TaskStatus.COMPLETED,
            f"{export_type.capitalize()} database export completed",
            progress=100,
            current_step="export_complete",
            result={"archive_path": result.get("archive")},
        )

    except Exception as e:
        await task_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            "Database export failed",
            error=str(e),
            current_step="export_failed",
        )
        raise


async def run_import(task_manager: "TaskManager", task_id: str):
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

        await task_manager.update_task_status(
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
                    task_manager.update_task_status(
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
                    task_manager.update_task_status(
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
            await task_manager.update_task_status(
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
            await task_manager.update_task_status(
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

        await task_manager.update_task_status(
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

        await task_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            "Database import failed",
            error=str(e),
            current_step="import_failed",
        )
        raise
