#!/usr/bin/env python3
"""
Theseus Judge Worker - Multi-process worker for distributed LLM judge processing.

This script launches worker processes that handle judge tasks from the durable queue.
Each worker process handles one Ollama server and processes tasks concurrently.

Usage:
    python theseus_judge_worker.py --server-url http://localhost:11434 --job-id <uuid>
    python theseus_judge_worker.py --all-enabled  # Process all enabled servers
"""

import argparse
import asyncio
import logging
import signal
import sys
from typing import Optional, List
from uuid import UUID
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from theseus_insight.utils.environment import EnvironmentDetector
from theseus_insight.data_access.ollama_servers import OllamaServersRepository
from theseus_insight.data_access.judge_task_queue import JudgeTaskQueueRepository
from theseus_insight.data_access.worker_heartbeats import WorkerHeartbeatsRepository
from theseus_insight.inference.llm import OllamaInference
from theseus_insight.data_access.profiles import ProfileRepository, ProfileInterestsRepository, ProfileScoreRepository
from theseus_insight.data_access.papers import PaperRepository
from theseus_insight.prompt import RESEARCH_INTERESTS_SYSTEM_PROMPT, research_prompt

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

        while self.running:
            try:
                # Send heartbeat
                await self._send_heartbeat()

                # Try to lease a task (run in thread pool to avoid blocking)
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
            # Mark task as in progress (run in thread pool)
            success = await asyncio.to_thread(
                JudgeTaskQueueRepository.mark_task_in_progress,
                task.id,
                self.worker_id
            )
            if not success:
                logger.warning(f"Failed to mark task {task.id} as in progress")
                return

            # Get paper and profile data (run in thread pool)
            paper = await asyncio.to_thread(PaperRepository.get_by_id, task.paper_id)
            if not paper:
                raise ValueError(f"Paper {task.paper_id} not found")

            profile = await asyncio.to_thread(ProfileRepository.get_by_id, task.profile_id)
            if not profile:
                raise ValueError(f"Profile {task.profile_id} not found")

            # Get research interests (run in thread pool)
            research_interests = await asyncio.to_thread(
                ProfileInterestsRepository.get_interests_text_by_profile,
                task.profile_id
            )
            if not research_interests:
                raise ValueError(f"No research interests found for profile {task.profile_id}")

            # Perform LLM judge scoring
            score_data = await self._score_paper(paper, research_interests)

            # Save the score (run in thread pool)
            await asyncio.to_thread(
                ProfileScoreRepository.create_or_update_score,
                paper_id=task.paper_id,
                profile_id=task.profile_id,
                score=score_data['score'],
                related=score_data['related'],
                rationale=score_data['rationale'],
                judge_model=self.ollama_client.model_name
            )

            # Mark task as completed (run in thread pool)
            await asyncio.to_thread(JudgeTaskQueueRepository.mark_task_completed, task.id)

            self.tasks_processed += 1
            self.consecutive_failures = 0

            logger.info(f"Worker {self.worker_id} completed task {task.id} with score {score_data['score']}")

        except Exception as e:
            await self._handle_task_error(task, str(e))

    async def _score_paper(self, paper: dict, research_interests: str) -> dict:
        """Score a paper using LLM judge."""
        messages = [
            {"role": "user", "content": research_prompt(research_interests, paper['abstract'])}
        ]

        response = self.ollama_client.invoke(
            messages=messages,
            system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT
        )

        # Parse the response (simplified parsing)
        import json_repair
        response_json = json_repair.loads(response)

        return {
            'score': int(response_json.get('score', 5)),
            'related': bool(response_json.get('related', False)),
            'rationale': str(response_json.get('rationale', ''))
        }

    async def _handle_task_error(self, task, error_message: str):
        """Handle task processing errors."""
        task.attempts += 1
        self.consecutive_failures += 1

        logger.warning(f"Worker {self.worker_id} task {task.id} failed (attempt {task.attempts}): {error_message}")

        # Check if we should retry or fail permanently (run in thread pool)
        if task.attempts >= self.max_retries:
            await asyncio.to_thread(
                JudgeTaskQueueRepository.mark_task_failed,
                task.id,
                error_message,
                increment_attempts=False
            )
            logger.error(f"Worker {self.worker_id} permanently failed task {task.id} after {task.attempts} attempts")
        else:
            await asyncio.to_thread(
                JudgeTaskQueueRepository.mark_task_failed,
                task.id,
                error_message
            )
            logger.info(f"Worker {self.worker_id} will retry task {task.id} (attempt {task.attempts + 1})")

        # Check circuit breaker
        if self.consecutive_failures >= self.circuit_breaker_threshold:
            logger.error(f"Worker {self.worker_id} circuit breaker triggered after {self.consecutive_failures} failures")
            await self._shutdown_worker("Circuit breaker triggered")

    async def _send_heartbeat(self):
        """Send heartbeat to indicate worker is alive."""
        try:
            # Run synchronous database call in thread pool to avoid blocking
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

    async def _shutdown_worker(self, reason: str = "Normal shutdown"):
        """Shutdown this worker."""
        logger.info(f"Worker {self.worker_id} shutting down: {reason}")
        self.running = False

        # Mark as inactive (run in thread pool)
        try:
            await asyncio.to_thread(
                WorkerHeartbeatsRepository.mark_worker_inactive,
                worker_id=self.worker_id,
                server_url=self.server_url,
                job_id=self.job_id
            )
        except Exception as e:
            logger.warning(f"Worker {self.worker_id} failed to mark inactive: {e}")

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
