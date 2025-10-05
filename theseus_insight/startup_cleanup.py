"""Startup cleanup utilities for TheseusInsight.

This module handles cleanup of stuck jobs and orphaned processes on API startup.
"""
import subprocess
from typing import Optional

from .db.pool import get_connection_pool


async def cleanup_stuck_jobs_and_processes():
    """
    Clean up stuck jobs and orphaned worker processes on API startup.
    
    This function:
    1. Terminates any orphaned worker processes from previous sessions
    2. Marks all stuck jobs (running/pending) as failed
    3. Resets task queue states
    4. Marks worker heartbeats as inactive
    
    This prevents stuck jobs from blocking new operations after server restarts or crashes.
    """
    try:
        # Step 1: Clean up orphaned worker processes
        await _cleanup_orphaned_worker_processes()
        
        # Step 2: Clean up database state (stuck jobs)
        await _cleanup_stuck_jobs_in_database()
        
        print("✅ Startup cleanup completed successfully")
        
    except Exception as e:
        print(f"⚠️  Error during startup cleanup: {e}")
        import traceback
        traceback.print_exc()
        # Don't fail startup if cleanup fails


async def _cleanup_orphaned_worker_processes():
    """Clean up any orphaned judge worker processes from previous sessions."""
    try:
        print("🧹 Checking for orphaned worker processes...")
        
        # Get all judge_worker processes
        result = subprocess.run([
            "ps", "aux"
        ], capture_output=True, text=True, check=True)
        
        orphaned_processes = []
        for line in result.stdout.split('\n'):
            if 'theseus_insight.workers.judge_worker' in line:
                # Extract PID (second column)
                parts = line.split()
                if len(parts) > 1:
                    try:
                        pid = int(parts[1])
                        orphaned_processes.append(pid)
                    except ValueError:
                        continue
        
        if orphaned_processes:
            print(f"🛑 Found {len(orphaned_processes)} orphaned worker processes, terminating...")
            
            # Terminate processes gracefully first
            for pid in orphaned_processes:
                try:
                    subprocess.run(["kill", "-TERM", str(pid)], check=False)
                except Exception as e:
                    print(f"Warning: Could not terminate process {pid}: {e}")
            
            # Wait a moment, then force kill any remaining processes
            import asyncio
            await asyncio.sleep(2)
            
            for pid in orphaned_processes:
                try:
                    # Check if process still exists
                    subprocess.run(["kill", "-0", str(pid)], check=True, capture_output=True)
                    # If we get here, process still exists, force kill it
                    subprocess.run(["kill", "-KILL", str(pid)], check=False)
                except subprocess.CalledProcessError:
                    # Process already terminated
                    pass
                except Exception as e:
                    print(f"Warning: Could not force kill process {pid}: {e}")
            
            print(f"✅ Cleaned up {len(orphaned_processes)} orphaned worker processes")
        else:
            print("✅ No orphaned worker processes found")
            
    except Exception as e:
        print(f"⚠️  Error cleaning up orphaned processes: {e}")


async def _cleanup_stuck_jobs_in_database():
    """
    Clean up stuck jobs in the database on startup.
    
    1. Auto-completes jobs that are 100% done but stuck in "running" status
    2. Marks interrupted jobs as failed since they were terminated by restart/crash
    """
    try:
        print("🧹 Cleaning up stuck jobs in database...")
        
        pool = await get_connection_pool()
        async with pool.acquire() as conn:
            # First, auto-complete multi-server bulk judge jobs that are 100% done
            # Check judge_task_queue to see if all tasks are completed
            completed_jobs = await conn.fetch(
                """
                WITH job_progress AS (
                    SELECT 
                        job_id,
                        COUNT(*) as total_tasks,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed_tasks,
                        COUNT(*) FILTER (WHERE status IN ('pending', 'leased', 'in_progress')) as active_tasks
                    FROM judge_task_queue
                    GROUP BY job_id
                )
                SELECT 
                    pj.id,
                    jp.total_tasks,
                    jp.completed_tasks,
                    pj.job_type
                FROM processing_jobs pj
                INNER JOIN job_progress jp ON pj.id = jp.job_id
                WHERE pj.status = 'running'
                AND pj.job_type = 'bulk_judge'
                AND jp.completed_tasks >= jp.total_tasks
                AND jp.total_tasks > 0
                AND jp.active_tasks = 0
                """
            )
            
            if completed_jobs:
                print(f"🎉 Found {len(completed_jobs)} completed jobs stuck in 'running' status")
                for job in completed_jobs:
                    await conn.execute(
                        """
                        UPDATE processing_jobs 
                        SET status = 'completed',
                            error_message = NULL,
                            completed_at = NOW()
                        WHERE id = $1
                        """,
                        job['id']
                    )
                    print(f"✅ Auto-completed job {job['id']}: {job['completed_tasks']}/{job['total_tasks']} tasks")
                
                # Terminate worker processes for these completed jobs
                from .api.routers.bulk_operations import _signal_workers_cancel
                for job in completed_jobs:
                    try:
                        await _signal_workers_cancel(job['id'])
                        print(f"🛑 Terminated workers for completed job {job['id']}")
                    except Exception as e:
                        print(f"⚠️  Could not terminate workers for job {job['id']}: {e}")
            
            # Mark any OTHER running/pending resource-intensive jobs as failed
            # (These are jobs that were truly interrupted by restart)
            result = await conn.execute(
                """
                UPDATE processing_jobs 
                SET status = 'failed', 
                    error_message = 'Job terminated on server restart',
                    completed_at = NOW()
                WHERE status IN ('running', 'pending') 
                AND job_type IN ('bulk_judge', 'harvest_judge', 'newsletter_generation', 
                                 'mindmap_generation', 'podcast_generation')
                """
            )
            
            # Extract number of rows updated
            jobs_cleaned = result.split()[-1] if result else "0"
            if jobs_cleaned != "0":
                print(f"🧹 Marked {jobs_cleaned} interrupted jobs as failed")
            
            # Clear task queue of leased/in-progress items
            await conn.execute(
                """
                UPDATE judge_task_queue 
                SET status = 'failed', 
                    last_error = 'Task reset on server restart',
                    updated_at = NOW()
                WHERE status IN ('leased', 'in_progress')
                """
            )
            
            # Mark all worker heartbeats as inactive (preserve failure history)
            await conn.execute(
                """
                UPDATE worker_heartbeats 
                SET status = CASE 
                    WHEN status = 'failed' THEN 'failed'
                    ELSE 'inactive'
                END,
                last_heartbeat = NOW()
                WHERE status NOT IN ('inactive', 'failed')
                """
            )
            
        print("✅ Database state cleaned up")
        
    except Exception as e:
        print(f"⚠️  Error cleaning up database state: {e}")
        import traceback
        traceback.print_exc()

