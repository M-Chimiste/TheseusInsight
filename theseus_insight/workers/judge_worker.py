#!/usr/bin/env python3
"""
Theseus Judge Worker - Simple synchronous worker with single persistent connection.

This worker processes judge tasks synchronously using one database connection
for the entire worker lifetime to avoid connection pool issues.

Usage:
    python -m theseus_insight.workers.judge_worker --server-url http://localhost:11434 --job-id <uuid>
    python -m theseus_insight.workers.judge_worker --all-enabled  # Process all enabled servers
"""

import argparse
import json
import logging
import signal
import sys
import os
import time
import psycopg
import threading
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

# Configure logging
# Set up both console and file logging for worker diagnostics
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'logs')
os.makedirs(log_dir, exist_ok=True)

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# File handler - separate log file per worker (will be set in __init__)
# This will be added per-worker instance
logger.addHandler(console_handler)

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb")


class JudgeWorker:
    """Worker with single persistent database connection."""

    def __init__(
        self,
        server_url: str,
        job_id: Optional[UUID] = None,
        worker_id: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        judge_model_config: Optional[dict] = None
    ):
        self.server_url = server_url
        self.job_id = job_id
        self.worker_id = worker_id or f"worker_{server_url.replace('://', '_').replace('/', '_')}"
        self.max_retries = max_retries
        self.timeout = timeout
        self.running = False
        self.tasks_processed = 0
        self.consecutive_failures = 0
        self.consecutive_empty_checks = 0  # Track empty queue checks
        self.last_health_check = 0
        self.server_healthy = True
        
        # Create single persistent connection with autocommit to avoid transaction state conflicts
        # When using cursor context managers with a persistent connection, autocommit=True
        # prevents psycopg3 internal deadlocks on commit()
        self.conn = psycopg.connect(DATABASE_URL, autocommit=True)
        # Enforce sane timeouts to prevent indefinite waits on DB operations
        try:
            with self.conn.cursor() as _cur:
                _cur.execute("SET statement_timeout = '10s'")
                _cur.execute("SET lock_timeout = '3s'")
                _cur.execute("SET idle_in_transaction_session_timeout = '10s'")
        except Exception as _e:
            logger.warning(f"Failed to apply DB session timeouts: {_e}")
        
        # Cache for profile research interests to avoid repeated DB queries
        self.interests_cache = {}
        self.profile_cache = {}
        
        # Load judge model configuration from database if not provided
        if judge_model_config is None:
            judge_model_config = self._load_judge_config()
        
        self.judge_model_config = judge_model_config
        logger.info(f"Using judge model: {judge_model_config.get('model_name')} (type: {judge_model_config.get('model_type')})")
        
        # Initialize Ollama client once with configuration from settings
        from ..inference.llm import OllamaInference
        self.ollama_client = OllamaInference(
            model_name=judge_model_config.get('model_name', 'phi4-mini:3.8b-q8_0'),
            max_new_tokens=judge_model_config.get('max_new_tokens', 512),
            temperature=judge_model_config.get('temperature', 0.1),
            num_ctx=judge_model_config.get('num_ctx', 4096),
            url=server_url,
            request_timeout=timeout
        )
        
        # Add file handler for this specific worker
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'logs')
        log_file = os.path.join(log_dir, f'judge_worker_{self.worker_id}.log')
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        self.log_file = log_file
        
        # Watchdog to dump stack traces if we stall
        self.last_progress_ts = time.time()
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()
        
        logger.info(f"Initialized worker {self.worker_id} for server {server_url}")
        logger.info(f"Logging to {log_file}")

    def _load_judge_config(self) -> dict:
        """Load judge model configuration from database settings or config file."""
        try:
            # Try to load from database first
            with self.conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                cur.execute("SELECT value FROM settings WHERE key = %s", ('orchestration',))
                row = cur.fetchone()
                
                if row and row['value']:
                    orchestration_config = json.loads(row['value'])
                    judge_config = orchestration_config.get('judge_model', {})
                    if judge_config:
                        logger.info("Loaded judge model config from database settings")
                        return judge_config
        except Exception as e:
            logger.warning(f"Failed to load judge config from database: {e}")
        
        # Fallback to config file
        try:
            import pathlib
            project_root = pathlib.Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "orchestration.json"
            
            if config_path.exists():
                with open(config_path) as f:
                    orchestration_config = json.load(f)
                    judge_config = orchestration_config.get('judge_model', {})
                    if judge_config:
                        logger.info("Loaded judge model config from file")
                        return judge_config
        except Exception as e:
            logger.warning(f"Failed to load judge config from file: {e}")
        
        # Ultimate fallback to hardcoded defaults
        logger.warning("Using hardcoded default judge model config")
        return {
            'model_name': 'phi4-mini:3.8b-q8_0',
            'model_type': 'ollama',
            'max_new_tokens': 512,
            'temperature': 0.1,
            'num_ctx': 4096
        }

    def start(self):
        """Start the worker process."""
        logger.info(f"Starting worker {self.worker_id} for job {self.job_id}")
        self.running = True
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        last_heartbeat = time.time()
        last_lease_cleanup = time.time()
        heartbeat_interval = 30  # seconds
        lease_cleanup_interval = 60  # seconds
        
        try:
            while self.running:
                try:
                    # Mark progress for watchdog
                    self.last_progress_ts = time.time()
                    logger.debug("Loop tick start")
                    # Send heartbeat periodically
                    now = time.time()
                    if (now - last_heartbeat) >= heartbeat_interval:
                        logger.debug("Sending heartbeat...")
                        self._send_heartbeat()
                        logger.debug("Heartbeat sent")
                        last_heartbeat = now
                    
                    # Clean up expired leases periodically
                    if (now - last_lease_cleanup) >= lease_cleanup_interval:
                        logger.debug("Running lease cleanup...")
                        expired_count = self._requeue_expired_leases()
                        logger.debug(f"Lease cleanup completed ({expired_count} requeued)")
                        if expired_count > 0:
                            logger.info(f"Requeued {expired_count} expired leases")
                        last_lease_cleanup = now
                    
                    # Check Ollama server health every 60 seconds (informational only)
                    if now - self.last_health_check > 60:
                        logger.debug("Checking Ollama health...")
                        self._check_ollama_health()
                        logger.debug("Health check completed")
                        self.last_health_check = now
                    
                    # Note: We don't skip processing based on health check alone
                    # Let actual task failures determine if server is down
                    
                    # Try to lease a task
                    logger.debug(f"Attempting to lease task for {self.server_url}")
                    task = self._lease_next_task()
                    
                    if task:
                        logger.info(f"Leased task {task['id']} (paper {task['paper_id']}, profile {task['profile_id']})")
                        self._process_task(task)
                        
                        if self.tasks_processed % 10 == 0:
                            logger.info(f"Worker {self.worker_id}: {self.tasks_processed} tasks completed")
                        
                        # Log recovery if we had consecutive failures
                        if self.consecutive_failures >= 3:
                            logger.info(f"Worker recovered after {self.consecutive_failures} consecutive failures")
                        
                        # Reset consecutive failures and empty checks on success
                        self.consecutive_failures = 0
                        self.consecutive_empty_checks = 0
                    else:
                        # No tasks available - increment counter
                        self.consecutive_empty_checks += 1
                        logger.debug(f"No tasks available for {self.server_url} (check {self.consecutive_empty_checks}/6)")
                        
                        # Exit gracefully if queue has been empty for too long
                        if self.consecutive_empty_checks >= 6:
                            logger.info(f"Worker {self.worker_id}: No tasks found after {self.consecutive_empty_checks} checks. All work appears done - exiting gracefully.")
                            break
                        
                        time.sleep(5)
                        
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}", exc_info=True)
                    self.consecutive_failures += 1
                    
                    # With autocommit mode, no need to rollback
                    
                    # If too many failures, exit
                    if self.consecutive_failures >= 10:
                        logger.error("Too many consecutive failures, shutting down")
                        break
                    
                    time.sleep(10)
        finally:
            self._cleanup()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Worker {self.worker_id} received signal {signum}, shutting down...")
        self.running = False
    
    def _watchdog_loop(self):
        """Watch for stalls and dump stack traces to the log."""
        import traceback, sys
        stall_threshold = 45  # seconds without progress
        while True:
            try:
                time.sleep(15)
                if not self.running:
                    return
                idle = time.time() - getattr(self, 'last_progress_ts', time.time())
                if idle > stall_threshold:
                    logger.error(f"Watchdog: worker stalled for {int(idle)}s. Dumping stack traces...")
                    for thread_id, frame in sys._current_frames().items():
                        stack = ''.join(traceback.format_stack(frame))
                        logger.error(f"Thread {thread_id} stack:\n{stack}")
                    # Also write a marker to the log file
                    try:
                        with open(self.log_file, 'a') as f:
                            f.write(f"\n==== Watchdog dump at {time.strftime('%Y-%m-%d %H:%M:%S')} (idle {int(idle)}s) ====\n")
                            for thread_id, frame in sys._current_frames().items():
                                f.write(f"\n--- Thread {thread_id} ---\n")
                                f.write(''.join(traceback.format_stack(frame)))
                    except Exception:
                        pass
                    # Reset timer to avoid spamming
                    self.last_progress_ts = time.time()
            except Exception:
                # Watchdog should never crash the worker
                pass
    
    def _check_ollama_health(self):
        """Check if the Ollama server is responding."""
        import requests
        try:
            # Try to get the version endpoint with a short timeout
            # Use a session to avoid connection pool exhaustion
            with requests.Session() as session:
                response = session.get(f"{self.server_url}/api/version", timeout=5)
                if response.status_code == 200:
                    if not self.server_healthy:
                        logger.info(f"Ollama server {self.server_url} is now healthy")
                    self.server_healthy = True
                else:
                    if self.server_healthy:
                        logger.warning(f"Ollama server {self.server_url} returned status {response.status_code}")
                    self.server_healthy = False
        except Exception as e:
            # Log but don't immediately mark as unhealthy - could be transient
            logger.warning(f"Ollama server health check failed (will retry): {e}")
            # Don't set server_healthy = False here - let actual task failures determine that

    def _lease_next_task(self):
        """Lease the next available task."""
        task = None
        try:
            leased_until = datetime.now() + timedelta(minutes=5)
            
            # Use cursor context manager to execute queries
            with self.conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
                # First check if there are ANY pending tasks for this server
                cur.execute("""
                    SELECT COUNT(*) as count FROM judge_task_queue
                    WHERE status = 'pending'
                    AND (assigned_server_url IS NULL OR assigned_server_url = %s)
                """, (self.server_url,))
                count_result = cur.fetchone()
                pending_count = count_result['count'] if count_result else 0
                
                if pending_count == 0:
                    logger.debug(f"No pending tasks for {self.server_url}")
                    # Don't commit/rollback here - do it outside the with block
                    return None
                
                logger.debug(f"Found {pending_count} pending tasks for {self.server_url}, attempting lease")
                
                # Now try to lease one
                cur.execute("""
                    UPDATE judge_task_queue
                    SET status = 'leased',
                        assigned_server_url = %s,
                        leased_until = %s,
                        leased_by_worker = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = (
                        SELECT id FROM judge_task_queue
                        WHERE status = 'pending'
                        AND (assigned_server_url IS NULL OR assigned_server_url = %s)
                        ORDER BY created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    RETURNING id, job_id, paper_id, profile_id, attempts
                """, (self.server_url, leased_until, self.worker_id, self.server_url))
                
                row = cur.fetchone()
                task = dict(row) if row else None
                
                # Log while still inside cursor context to avoid accessing closed cursor data
                if task:
                    logger.debug(f"Successfully leased task {task['id']}")
                else:
                    logger.warning(f"Failed to lease task (likely locked by another worker)")
            
            # Return task (row data is safe to use after cursor closes in psycopg3)
            return task
            
        except Exception as e:
            logger.error(f"Error leasing task: {e}", exc_info=True)
            return None

    def _requeue_expired_leases(self):
        """Requeue tasks with expired leases or stuck in_progress."""
        try:
            # Execute queries inside cursor context
            with self.conn.cursor() as cur:
                # Requeue expired leases
                cur.execute("""
                    UPDATE judge_task_queue
                    SET status = 'pending',
                        assigned_server_url = NULL,
                        leased_until = NULL,
                        leased_by_worker = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE status = 'leased'
                      AND leased_until < CURRENT_TIMESTAMP
                """)
                count = cur.rowcount
                
                # Also requeue tasks stuck in_progress for more than 2 minutes
                # (normal processing should complete within timeout + buffer)
                cur.execute("""
                    UPDATE judge_task_queue
                    SET status = 'pending',
                        assigned_server_url = NULL,
                        leased_until = NULL,
                        leased_by_worker = NULL,
                        last_error = 'Timed out - stuck in progress',
                        attempts = attempts + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE status = 'in_progress'
                      AND updated_at < CURRENT_TIMESTAMP - INTERVAL '2 minutes'
                """)
                stuck_count = cur.rowcount
            
            # With autocommit mode, transaction commits automatically
            if stuck_count > 0:
                logger.warning(f"Requeued {stuck_count} tasks stuck in_progress")
            
            return count + stuck_count
        except Exception as e:
            logger.error(f"Error requeuing expired leases: {e}")
            return 0

    def _process_task(self, task):
        """Process a single task."""
        cur = None
        try:
            # Create a fresh cursor for this task
            cur = self.conn.cursor(row_factory=psycopg.rows.dict_row)
            
            # Mark task as in progress
            cur.execute("""
                UPDATE judge_task_queue
                SET status = 'in_progress',
                    leased_by_worker = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND status = 'leased'
            """, (self.worker_id, task['id']))
            
            if cur.rowcount == 0:
                logger.warning(f"Failed to mark task {task['id']} as in progress")
                cur.close()
                return
            
            # Get paper
            cur.execute("SELECT * FROM papers WHERE id = %s", (task['paper_id'],))
            paper_row = cur.fetchone()
            paper = dict(paper_row) if paper_row else None
            if not paper:
                raise ValueError(f"Paper {task['paper_id']} not found")
            
            # Get profile (with caching)
            profile_id = task['profile_id']
            if profile_id in self.profile_cache:
                profile = self.profile_cache[profile_id]
            else:
                cur.execute("SELECT * FROM research_profiles WHERE id = %s", (profile_id,))
                profile_row = cur.fetchone()
                profile = dict(profile_row) if profile_row else None
                if not profile:
                    raise ValueError(f"Profile {profile_id} not found")
                self.profile_cache[profile_id] = profile
            
            # Get research interests (with caching)
            if profile_id in self.interests_cache:
                research_interests = self.interests_cache[profile_id]
            else:
                cur.execute(
                    "SELECT interest_text FROM profile_research_interests WHERE profile_id = %s",
                    (profile_id,)
                )
                interests_rows = cur.fetchall()
                if not interests_rows:
                    raise ValueError(f"No interests for profile {profile_id}")
                research_interests = " ".join([row['interest_text'] for row in interests_rows])
                self.interests_cache[profile_id] = research_interests
            
            # Close cursor to free resources
            # With autocommit mode, transaction already committed
            cur.close()
            cur = None
            
            # Perform LLM scoring (this happens outside any transaction)
            logger.info(f"Scoring paper for profile {profile['name']}")
            try:
                score_data = self._score_paper(paper, research_interests)
            except Exception as e:
                # If LLM fails, mark the task as failed and continue
                logger.error(f"LLM scoring failed: {e}")
                raise Exception(f"LLM inference failed: {e}")
            
            # Create a new cursor for saving results
            cur = self.conn.cursor(row_factory=psycopg.rows.dict_row)
            
            # Save the score
            cur.execute("""
                INSERT INTO paper_profile_scores (paper_id, profile_id, score, related, rationale, judge_model)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (paper_id, profile_id)
                DO UPDATE SET
                    score = EXCLUDED.score,
                    related = EXCLUDED.related,
                    rationale = EXCLUDED.rationale,
                    judge_model = EXCLUDED.judge_model,
                    date_scored = CURRENT_TIMESTAMP
            """, (
                task['paper_id'],
                task['profile_id'],
                score_data['score'],
                score_data['related'],
                score_data['rationale'],
                self.ollama_client.model_name
            ))
            
            # Mark task as completed
            cur.execute("""
                UPDATE judge_task_queue
                SET status = 'completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (task['id'],))
            
            # Close cursor to free resources
            # With autocommit mode, transaction already committed
            cur.close()
            cur = None
            
            self.tasks_processed += 1
            logger.info(f"Completed task with score {score_data['score']} (total: {self.tasks_processed})")
            
        except Exception as e:
            logger.error(f"Task {task['id']} failed: {e}")
            
            # Increment consecutive failures for circuit breaker
            self.consecutive_failures += 1
            
            # Mark task as failed using a fresh cursor
            try:
                if cur:
                    cur.close()
                with self.conn.cursor() as err_cur:
                    err_cur.execute("""
                        UPDATE judge_task_queue
                        SET status = 'failed',
                            last_error = %s,
                            attempts = attempts + 1,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (str(e), task['id']))
                    # With autocommit mode, already committed
            except:
                pass
        finally:
            # Ensure cursor is closed
            if cur:
                try:
                    cur.close()
                except:
                    pass

    def _score_paper(self, paper: dict, research_interests: str) -> dict:
        """Score a paper using the LLM with timeout enforcement."""
        from ..prompt import RESEARCH_INTERESTS_SYSTEM_PROMPT, research_prompt
        from ..prompt.data_models import ResearchInterestsPromptData
        
        messages = [
            {"role": "user", "content": research_prompt(research_interests, paper['abstract'])}
        ]
        
        # Use a timeout wrapper to prevent hanging
        result = [None]
        exception = [None]
        
        def _invoke_with_timeout():
            try:
                result[0] = self.ollama_client.invoke(
                    messages=messages,
                    system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT,
                    schema=ResearchInterestsPromptData
                )
            except Exception as e:
                exception[0] = e
        
        thread = threading.Thread(target=_invoke_with_timeout, daemon=True)
        thread.start()
        thread.join(timeout=self.timeout + 5)  # Timeout + 5 second buffer
        
        if thread.is_alive():
            # Thread is still running - LLM call hung
            raise TimeoutError(f"LLM inference exceeded {self.timeout + 5}s timeout")
        
        if exception[0]:
            raise exception[0]
        
        if result[0] is None:
            raise RuntimeError("LLM inference failed without exception")
        
        response = result[0]
        
        import json_repair
        response_json = json_repair.loads(response)
        
        score = response_json.get('score', 5)
        if not isinstance(score, (int, float)):
            score = 5
        score = max(1, min(10, int(score)))
        
        return {
            'score': score,
            'related': bool(response_json.get('related', False)),
            'rationale': str(response_json.get('rationale', ''))
        }

    def _send_heartbeat(self):
        """Send worker heartbeat."""
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO worker_heartbeats (worker_id, server_url, job_id, status, tasks_processed, last_heartbeat)
                    VALUES (%s, %s, %s, 'active', %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (worker_id, server_url, job_id)
                    DO UPDATE SET
                        status = 'active',
                        tasks_processed = EXCLUDED.tasks_processed,
                        last_heartbeat = CURRENT_TIMESTAMP
                """, (
                    self.worker_id,
                    self.server_url,
                    str(self.job_id) if self.job_id else None,
                    self.tasks_processed
                ))
            # With autocommit mode, transaction commits automatically
        except Exception as e:
            logger.warning(f"Failed to send heartbeat: {e}")

    def _cleanup(self):
        """Clean up on shutdown."""
        logger.info(f"Worker {self.worker_id} shutting down (processed {self.tasks_processed} tasks)")
        
        # Mark worker as inactive
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE worker_heartbeats
                    SET status = 'inactive',
                        last_heartbeat = CURRENT_TIMESTAMP
                    WHERE worker_id = %s
                      AND server_url = %s
                      AND (job_id = %s OR (%s IS NULL AND job_id IS NULL))
                """, (
                    self.worker_id,
                    self.server_url,
                    str(self.job_id) if self.job_id else None,
                    str(self.job_id) if self.job_id else None
                ))
            # With autocommit mode, transaction commits automatically
        except Exception as e:
            logger.warning(f"Failed to mark worker as inactive: {e}")
        
        # Close Ollama client connections
        try:
            if hasattr(self.ollama_client, 'close'):
                self.ollama_client.close()
        except:
            pass
        
        # Close database connection
        try:
            self.conn.close()
        except:
            pass


def run_worker(server_url: str, job_id: Optional[UUID], max_retries: int, timeout: int, judge_model_config: Optional[dict] = None):
    """Run a single worker for a server."""
    worker = JudgeWorker(
        server_url=server_url,
        job_id=job_id,
        max_retries=max_retries,
        timeout=timeout,
        judge_model_config=judge_model_config
    )
    
    try:
        worker.start()
    except Exception as e:
        logger.error(f"Worker for {server_url} failed: {e}", exc_info=True)


def main():
    """Main entry point for the worker launcher."""
    parser = argparse.ArgumentParser(description='Theseus Judge Worker')
    parser.add_argument('--server-url', help='Ollama server URL to process')
    parser.add_argument('--job-id', help='Specific job ID to process')
    parser.add_argument('--all-enabled', action='store_true', help='Process all enabled servers')
    parser.add_argument('--max-retries', type=int, default=3, help='Max retries per task')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')

    args = parser.parse_args()

    # For --all-enabled, we need to get the list of servers
    # Import here to avoid early module loading
    if args.all_enabled:
        from ..data_access.ollama_servers import OllamaServersRepository
        servers = OllamaServersRepository.get_enabled()
        servers_to_process = [(server.url, args.job_id) for server in servers]
        logger.info(f"Processing all {len(servers_to_process)} enabled servers")
    elif args.server_url:
        servers_to_process = [(args.server_url, args.job_id)]
        logger.info(f"Processing single server: {args.server_url}")
    else:
        logger.error("Must specify either --server-url or --all-enabled")
        sys.exit(1)

    # For multiple servers, fork processes
    if len(servers_to_process) > 1:
        import multiprocessing
        processes = []
        
        for server_url, job_id in servers_to_process:
            job_uuid = UUID(job_id) if job_id else None
            p = multiprocessing.Process(
                target=run_worker,
                args=(server_url, job_uuid, args.max_retries, args.timeout, None)  # None = load from settings
            )
            p.start()
            processes.append(p)
            logger.info(f"Started worker process for {server_url}")
        
        # Wait for all processes
        try:
            for p in processes:
                p.join()
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, terminating workers...")
            for p in processes:
                p.terminate()
            for p in processes:
                p.join(timeout=5)
    else:
        # Single server - run directly
        server_url, job_id = servers_to_process[0]
        job_uuid = UUID(job_id) if job_id else None
        run_worker(server_url, job_uuid, args.max_retries, args.timeout, None)  # None = load from settings


if __name__ == "__main__":
    main()