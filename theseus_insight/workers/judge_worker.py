#!/usr/bin/env python3
"""
Theseus Judge Worker - Multi-process worker for distributed LLM judge processing.

This script launches worker processes that handle judge tasks from the durable queue.
Each worker process handles one Ollama server and processes tasks concurrently.

Usage:
    python -m theseus_insight.workers.judge_worker --server-url http://localhost:11434 --job-id <uuid>
    python -m theseus_insight.workers.judge_worker --all-enabled  # Process all enabled servers
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
from typing import Optional, List
from uuid import UUID
from pathlib import Path

from ..utils.environment import EnvironmentDetector
from ..data_access.ollama_servers import OllamaServersRepository
from ..data_access.judge_task_queue import JudgeTaskQueueRepository
from ..data_access.worker_heartbeats import WorkerHeartbeatsRepository
from ..inference.llm import OllamaInference
from ..data_access.profiles import ProfileRepository, ProfileInterestsRepository, ProfileScoreRepository
from ..data_access.papers import PaperRepository
from ..prompt import RESEARCH_INTERESTS_SYSTEM_PROMPT, research_prompt
from ..prompt.data_models import ResearchInterestsPromptData

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JudgeWorker:
    """Worker process for processing judge tasks from the queue."""

    def __init__(
        self,
        server_url: str,
        job_id: Optional[UUID] = None,
        worker_id: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 30,
        heartbeat_interval: int = 30
    ):
        self.server_url = server_url
        self.job_id = job_id
        self.worker_id = worker_id or f"worker_{server_url.replace('://', '_').replace('/', '_')}"
        self.max_retries = max_retries
        self.timeout = timeout
        self.heartbeat_interval = heartbeat_interval
        self.running = False
        self.tasks_processed = 0
        self.consecutive_failures = 0
        self.circuit_breaker_threshold = 5
        self._start_time = None  # Will be set when worker starts

        # Initialize Ollama client with timeout for bulk processing
        self.ollama_client = OllamaInference(
            model_name="phi4-mini:3.8b-q8_0",  # Default model, should be configurable
            max_new_tokens=512,
            temperature=0.1,
            num_ctx=4096,
            url=server_url,  # Pass server URL directly to constructor
            request_timeout=timeout  # Set timeout during initialization
        )

        logger.info(f"Initialized worker {self.worker_id} for server {server_url}")

    async def start(self):
        """Start the worker process."""
        logger.info(f"Starting worker {self.worker_id} for job {self.job_id}")
        self.running = True
        self._start_time = asyncio.get_event_loop().time()  # Track start time for failure logging

        # Set custom thread pool - now we only need a few threads per worker
        # Main task processing uses 1 thread, heartbeats/cleanup use another
        import concurrent.futures
        loop = asyncio.get_running_loop()
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=3,  # Minimal: 1 for task, 1 for heartbeat, 1 spare
            thread_name_prefix=f"worker_{self.worker_id}_"
        )
        loop.set_default_executor(executor)
        logger.info(f"Worker {self.worker_id} initialized thread pool with 3 workers")

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            await self._worker_loop()
        except Exception as e:
            logger.error(f"Worker {self.worker_id} failed: {e}")
        finally:
            await self._cleanup()

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Worker {self.worker_id} received signal {signum}, shutting down...")
        self.running = False

    async def _worker_loop(self):
        """Main worker processing loop."""
        logger.info(f"Worker {self.worker_id} entering processing loop")
        last_lease_cleanup = asyncio.get_event_loop().time()
        lease_cleanup_interval = 60  # Check for expired leases every 60 seconds

        while self.running:
            try:
                # Send heartbeat
                await self._send_heartbeat()

                # Periodically clean up expired leases (prevents queue deadlock)
                now = asyncio.get_event_loop().time()
                if (now - last_lease_cleanup) >= lease_cleanup_interval:
                    expired_count = await asyncio.to_thread(
                        JudgeTaskQueueRepository.requeue_expired_leases
                    )
                    if expired_count > 0:
                        logger.info(f"Worker {self.worker_id} requeued {expired_count} expired leases")
                    last_lease_cleanup = now

                # Try to lease a task (in thread to avoid blocking event loop)
                task = await asyncio.to_thread(
                    JudgeTaskQueueRepository.lease_next_task,
                    server_url=self.server_url,
                    worker_id=self.worker_id
                )

                if task:
                    logger.info(f"Worker {self.worker_id} leased task {task.id} (paper {task.paper_id}, profile {task.profile_id})")
                    await self._process_task(task)
                else:
                    # No tasks available, wait before checking again
                    await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Worker {self.worker_id} error in main loop: {e}")
                await asyncio.sleep(10)  # Back off on errors

    async def _process_task(self, task):
        """Process a single judge task."""
        try:
            # Process entire task in a single thread to avoid connection pool issues
            # This ensures each task gets its own DB connection that's properly cleaned up
            result = await asyncio.to_thread(self._process_task_sync, task)
            
            if result is None:
                return
                
            score_data, error = result
            if error:
                raise Exception(error)
                
            self.tasks_processed += 1
            self.consecutive_failures = 0
            logger.info(f"Worker {self.worker_id} completed task {task.id} with score {score_data['score']} (total processed: {self.tasks_processed})")

        except Exception as e:
            # Classify the error to determine if it should trigger circuit breaker
            error_type = self._classify_error(e)
            await self._handle_task_error(task, str(e), error_type)
    
    def _process_task_sync(self, task):
        """Process a task synchronously in a dedicated thread.
        
        This method runs entirely in a single thread, ensuring DB connections
        are acquired and released properly without connection pool issues.
        
        Returns:
            tuple: (score_data, error_message) or None if task failed to mark as in_progress
        """
        try:
            # Mark task as in progress
            success = JudgeTaskQueueRepository.mark_task_in_progress(task.id, self.worker_id)
            if not success:
                logger.warning(f"Failed to mark task {task.id} as in progress")
                return None

            # Get paper and profile data
            paper = PaperRepository.get_by_id(task.paper_id)
            if not paper:
                return None, f"Paper {task.paper_id} not found"

            profile = ProfileRepository.get_by_id(task.profile_id)
            if not profile:
                return None, f"Profile {task.profile_id} not found"

            # Get research interests
            research_interests = ProfileInterestsRepository.get_interests_text_by_profile(task.profile_id)
            if not research_interests:
                return None, f"No research interests found for profile {task.profile_id}"

            # Perform LLM judge scoring (synchronous - GPU inference)
            score_data = self._score_paper_sync(paper, research_interests)

            # Save the score
            ProfileScoreRepository.create_or_update_score(
                paper_id=task.paper_id,
                profile_id=task.profile_id,
                score=score_data['score'],
                related=score_data['related'],
                rationale=score_data['rationale'],
                judge_model=self.ollama_client.model_name
            )

            # Mark task as completed
            JudgeTaskQueueRepository.mark_task_completed(task.id)
            
            return score_data, None
            
        except Exception as e:
            return None, str(e)

    def _score_paper_sync(self, paper: dict, research_interests: str) -> dict:
        """Synchronous version of _score_paper for use in worker threads."""
        messages = [
            {"role": "user", "content": research_prompt(research_interests, paper['abstract'])}
        ]

        # Use structured output schema to force Ollama to output valid JSON
        response = self.ollama_client.invoke(
            messages=messages,
            system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT,
            schema=ResearchInterestsPromptData
        )

        # Parse the response
        import json_repair
        response_json = json_repair.loads(response)

        # Validate response structure
        if not isinstance(response_json, dict):
            raise ValueError(f"Invalid response format: expected dict, got {type(response_json)}")

        required_keys = ['score', 'related', 'rationale']
        missing_keys = [key for key in required_keys if key not in response_json]
        if missing_keys:
            raise ValueError(f"Missing required keys in response: {missing_keys}")

        # Validate and clamp score to valid range (1-10)
        score = response_json.get('score', 5)
        if not isinstance(score, (int, float)):
            score = 5
        score = max(1, min(10, int(score)))

        return {
            'score': score,
            'related': bool(response_json.get('related', False)),
            'rationale': str(response_json.get('rationale', ''))
        }

    async def _score_paper(self, paper: dict, research_interests: str) -> dict:
        """Score a paper using LLM judge with structured output for reliable JSON parsing."""
        messages = [
            {"role": "user", "content": research_prompt(research_interests, paper['abstract'])}
        ]

        # Use structured output schema to force Ollama to output valid JSON
        # This dramatically reduces JSON parsing failures
        # Wrap in asyncio.to_thread to prevent blocking the event loop
        response = await asyncio.to_thread(
            self.ollama_client.invoke,
            messages=messages,
            system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT,
            schema=ResearchInterestsPromptData  # Forces valid JSON output!
        )

        # Parse the response - should always be valid JSON now
        import json_repair
        response_json = json_repair.loads(response)

        # Validate response structure
        if not isinstance(response_json, dict):
            raise ValueError(f"Invalid response format: expected dict, got {type(response_json)}")

        required_keys = ['score', 'related', 'rationale']
        missing_keys = [key for key in required_keys if key not in response_json]
        if missing_keys:
            raise ValueError(f"Missing required keys in response: {missing_keys}")

        # Validate and clamp score to valid range (1-10)
        score_val = int(response_json['score'])
        score_val = max(1, min(10, score_val))  # Clamp to valid range

        return {
            'score': score_val,
            'related': bool(response_json['related']),
            'rationale': str(response_json['rationale'])
        }

    def _classify_error(self, error: Exception) -> str:
        """Classify error type to determine appropriate handling."""
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Server connectivity issues - should trigger circuit breaker
        if any(keyword in error_str for keyword in [
            'connection refused', 'connection timeout', 'connection error',
            'network unreachable', 'host unreachable', 'timeout',
            'connection reset', 'connection aborted', 'server unavailable',
            'service unavailable', 'bad gateway', 'gateway timeout'
        ]):
            return 'SERVER_CONNECTIVITY'
        
        # HTTP/API errors that indicate server issues
        if any(keyword in error_str for keyword in [
            '500 internal server error', '502 bad gateway', '503 service unavailable',
            '504 gateway timeout', 'ollama server error'
        ]):
            return 'SERVER_ERROR'
        
        # Data/validation errors - should not trigger circuit breaker
        if any(keyword in error_str for keyword in [
            'not found', 'no research interests', 'paper', 'profile',
            'invalid data', 'missing data', 'validation error'
        ]) or error_type in ['ValueError', 'KeyError']:
            return 'DATA_ERROR'
        
        # LLM/inference errors - should not trigger circuit breaker
        if any(keyword in error_str for keyword in [
            'json', 'parsing', 'invalid response', 'model error',
            'inference error', 'generation failed', 'token limit'
        ]):
            return 'INFERENCE_ERROR'
        
        # Default to inference error for unknown errors (safer approach)
        return 'INFERENCE_ERROR'

    async def _handle_task_error(self, task, error_message: str, error_type: str = 'INFERENCE_ERROR'):
        """Handle task processing errors with intelligent error classification and server health verification."""
        task.attempts += 1
        
        # Track consecutive server failures
        if error_type in ['SERVER_CONNECTIVITY', 'SERVER_ERROR']:
            self.consecutive_failures += 1
            logger.error(f"Worker {self.worker_id} server error on task {task.id} (attempt {task.attempts}): {error_message}")
        else:
            self.consecutive_failures = 0
            logger.warning(f"Worker {self.worker_id} task error on task {task.id} (attempt {task.attempts}, type: {error_type}): {error_message}")

        # Log detailed error information
        await self._log_task_error(task, error_message, error_type)

        # After 3rd retry - need to decide if this is a server or paper problem
        if task.attempts >= self.max_retries:
            logger.warning(f"Task {task.id} exhausted {self.max_retries} retries")
            
            # For SERVER errors: verify server health before deciding action
            if error_type in ['SERVER_CONNECTIVITY', 'SERVER_ERROR']:
                logger.info(f"Performing server health check for {self.server_url}...")
                server_is_healthy = await self._check_server_health()
                
                if server_is_healthy:
                    # Server is fine, this paper is just problematic
                    logger.warning(
                        f"✅ Server {self.server_url} is healthy - this paper is the problem. "
                        f"Marking task {task.id} as permanently failed and continuing."
                    )
                    await asyncio.to_thread(
                        JudgeTaskQueueRepository.mark_task_failed,
                        task.id,
                        f"[PAPER_ISSUE] Failed {self.max_retries} times but server is healthy: {error_message}",
                        increment_attempts=False
                    )
                    self.consecutive_failures = 0  # Reset since server is fine
                    return  # Continue to next task
                else:
                    # Server is actually down
                    logger.error(f"❌ Server {self.server_url} health check FAILED - shutting down worker")
                    await self._shutdown_worker(f"Server unreachable after {task.attempts} attempts on task {task.id}")
                    return
            else:
                # Non-server errors (LLM inference, data issues): mark failed and continue
                logger.warning(
                    f"Task {task.id} permanently failed due to {error_type} after {task.attempts} attempts - continuing with next task"
                )
                await asyncio.to_thread(
                    JudgeTaskQueueRepository.mark_task_failed,
                    task.id,
                    f"[{error_type}] {error_message}",
                    increment_attempts=False
                )
                self.consecutive_failures = 0
                return  # Continue to next task
        else:
            # Still have retries left - mark failed for requeue
            await asyncio.to_thread(
                JudgeTaskQueueRepository.mark_task_failed,
                task.id,
                f"[{error_type}] {error_message}"
            )
            logger.info(f"Task {task.id} will be retried (attempt {task.attempts}/{self.max_retries}, type: {error_type})")

        # ⚡ CIRCUIT BREAKER: Check if we've hit threshold of consecutive failures
        if error_type in ['SERVER_CONNECTIVITY', 'SERVER_ERROR'] and self.consecutive_failures >= self.circuit_breaker_threshold:
            logger.warning(
                f"⚠️  Circuit breaker threshold reached ({self.consecutive_failures} consecutive server errors). "
                f"Performing server health check..."
            )
            
            server_is_healthy = await self._check_server_health()
            
            if not server_is_healthy:
                # Server is down - trigger circuit breaker
                logger.error(
                    f"❌ Circuit breaker TRIGGERED: Server {self.server_url} is unreachable after "
                    f"{self.consecutive_failures} consecutive failures"
                )
                await self._shutdown_worker(f"Circuit breaker triggered: server unreachable after {self.consecutive_failures} errors")
            else:
                # False alarm - server is fine, just bad papers
                logger.info(
                    f"✅ Circuit breaker check: Server {self.server_url} is healthy despite "
                    f"{self.consecutive_failures} consecutive failures. Resetting counter and continuing."
                )
                self.consecutive_failures = 0  # Reset and keep going

    async def _check_server_health(self) -> bool:
        """Perform a health check on the Ollama server.
        
        Returns:
            bool: True if server is healthy and reachable, False if down
        """
        try:
            import httpx
            logger.debug(f"Health checking server: {self.server_url}")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Try to hit the Ollama tags endpoint (lightweight check)
                response = await client.get(f"{self.server_url}/api/tags")
                
                if response.status_code == 200:
                    logger.debug(f"Server {self.server_url} health check PASSED (status 200)")
                    return True
                else:
                    logger.warning(f"Server {self.server_url} returned status {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.warning(f"Server {self.server_url} health check FAILED: {e}")
            return False

    async def _send_heartbeat(self):
        """Send heartbeat to indicate worker is alive."""
        try:
            # DB call in thread to avoid blocking event loop
            await asyncio.to_thread(
                WorkerHeartbeatsRepository.upsert_heartbeat,
                worker_id=self.worker_id,
                server_url=self.server_url,
                job_id=self.job_id,
                status='active',
                tasks_processed=self.tasks_processed
            )
            logger.debug(f"Worker {self.worker_id} sent heartbeat successfully")
        except Exception as e:
            logger.warning(f"Worker {self.worker_id} failed to send heartbeat: {e}")

    async def _log_task_error(self, task, error_message: str, error_type: str):
        """Log detailed task error information to error_logs table."""
        try:
            from ..db.pool import get_connection_pool
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO error_logs (job_id, task_id, server_url, worker_id, error_type, severity, description, context)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, 
                str(self.job_id) if self.job_id else None,
                task.id,
                self.server_url,
                self.worker_id,
                f'TASK_{error_type}',
                'HIGH' if error_type in ['SERVER_CONNECTIVITY', 'SERVER_ERROR'] else 'MEDIUM',
                f"Task {task.id} failed: {error_message}",
                json.dumps({
                    'paper_id': task.paper_id,
                    'profile_id': task.profile_id,
                    'task_attempts': task.attempts,
                    'max_retries': self.max_retries,
                    'error_classification': error_type,
                    'consecutive_failures': self.consecutive_failures,
                    'tasks_processed': self.tasks_processed,
                    'will_retry': task.attempts < self.max_retries
                })
                )
        except Exception as e:
            logger.warning(f"Failed to log task error to error_logs: {e}")

    async def _shutdown_worker(self, reason: str = "Normal shutdown"):
        """Shutdown this worker."""
        logger.info(f"Worker {self.worker_id} shutting down: {reason}")
        self.running = False

        # Mark as failed with reason if it's an error, otherwise inactive
        try:
            if "error" in reason.lower() or "failed" in reason.lower() or "circuit breaker" in reason.lower():
                await asyncio.to_thread(
                    WorkerHeartbeatsRepository.mark_worker_failed,
                    worker_id=self.worker_id,
                    server_url=self.server_url,
                    job_id=self.job_id,
                    failure_reason=reason
                )
                logger.error(f"Worker {self.worker_id} marked as failed: {reason}")
                
                # Log the failure to error_logs table for detailed tracking
                await self._log_worker_failure(reason)
            else:
                await asyncio.to_thread(
                    WorkerHeartbeatsRepository.mark_worker_inactive,
                    worker_id=self.worker_id,
                    server_url=self.server_url,
                    job_id=self.job_id
                )
        except Exception as e:
            logger.warning(f"Worker {self.worker_id} failed to update status: {e}")

    async def _log_worker_failure(self, reason: str):
        """Log worker failure to error_logs table for detailed tracking."""
        try:
            from ..db.pool import get_connection_pool
            pool = await get_connection_pool()
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO error_logs (job_id, server_url, worker_id, error_type, severity, description, context)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, 
                str(self.job_id) if self.job_id else None,
                self.server_url,
                self.worker_id,
                'WORKER_FAILURE',
                'HIGH',
                f"Worker terminated: {reason}",
                json.dumps({
                    'tasks_processed': self.tasks_processed,
                    'consecutive_failures': self.consecutive_failures,
                    'shutdown_reason': reason,
                    'worker_runtime_seconds': (asyncio.get_event_loop().time() - getattr(self, '_start_time', 0))
                })
                )
            logger.info(f"Worker {self.worker_id} failure logged to error_logs table")
        except Exception as e:
            logger.warning(f"Failed to log worker failure to error_logs: {e}")

    async def _cleanup(self):
        """Clean up worker resources."""
        logger.info(f"Worker {self.worker_id} cleaning up")

        # Mark any leased tasks as failed if we're shutting down
        try:
            # This would need to be implemented in the repository
            pass
        except Exception as e:
            logger.warning(f"Worker {self.worker_id} cleanup failed: {e}")


async def main():
    """Main entry point for the worker launcher."""
    parser = argparse.ArgumentParser(description='Theseus Judge Worker')
    parser.add_argument('--server-url', help='Ollama server URL to process')
    parser.add_argument('--job-id', help='Specific job ID to process')
    parser.add_argument('--all-enabled', action='store_true', help='Process all enabled servers')
    parser.add_argument('--max-retries', type=int, default=3, help='Max retries per task')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds for bulk processing')
    parser.add_argument('--heartbeat-interval', type=int, default=30, help='Heartbeat interval in seconds')

    args = parser.parse_args()

    # Validate environment
    env_info = EnvironmentDetector.validate_environment()

    if not env_info['valid']:
        logger.error("Environment validation failed:")
        for issue in env_info['issues']:
            logger.error(f"  - {issue}")
        sys.exit(1)

    logger.info(f"Environment validated. Hash: {env_info['environment_hash']}")

    # Determine which servers to process
    servers_to_process = []

    if args.all_enabled:
        # Get all enabled servers
        servers = OllamaServersRepository.get_enabled()
        servers_to_process = [(server.url, args.job_id) for server in servers]
        logger.info(f"Processing all {len(servers_to_process)} enabled servers")
    elif args.server_url:
        servers_to_process = [(args.server_url, args.job_id)]
        logger.info(f"Processing single server: {args.server_url}")
    else:
        logger.error("Must specify either --server-url or --all-enabled")
        sys.exit(1)

    # Create and start workers
    workers = []
    for server_url, job_id in servers_to_process:
        job_uuid = UUID(job_id) if job_id else None
        worker = JudgeWorker(
            server_url=server_url,
            job_id=job_uuid,
            max_retries=args.max_retries,
            timeout=args.timeout,
            heartbeat_interval=args.heartbeat_interval
        )
        workers.append(worker)

    # Start all workers concurrently
    logger.info(f"Starting {len(workers)} worker(s)")
    tasks = [worker.start() for worker in workers]

    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down workers...")
    except Exception as e:
        logger.error(f"Worker launcher failed: {e}")
    finally:
        logger.info("Worker launcher shutting down")


if __name__ == "__main__":
    asyncio.run(main())

