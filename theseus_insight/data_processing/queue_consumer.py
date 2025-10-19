"""Queue consumer service for processing judge tasks."""

from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import asyncio
import logging

from ..data_access.judge_task_queue import JudgeTaskQueueRepository, JudgeTask
from ..data_access.worker_heartbeats import WorkerHeartbeatsRepository
from ..data_access.papers import PaperRepository
from ..data_access.profiles import ProfileRepository, ProfileInterestsRepository, ProfileScoreRepository
from ..inference.llm import OllamaInference
from ..prompt import RESEARCH_INTERESTS_SYSTEM_PROMPT, research_prompt
from .error_handler import DistributedErrorHandler, error_handler
import json_repair

logger = logging.getLogger(__name__)


class JudgeQueueConsumer:
    """Service for consuming and processing judge tasks from the durable queue."""

    def __init__(
        self,
        server_url: str,
        worker_id: str,
        max_retries: int = 3,
        timeout: int = 30,
        lease_duration_minutes: int = 5,
        heartbeat_interval: int = 30
    ):
        self.server_url = server_url
        self.worker_id = worker_id
        self.max_retries = max_retries
        self.timeout = timeout
        self.lease_duration_minutes = lease_duration_minutes
        self.heartbeat_interval = heartbeat_interval

        # Initialize repositories
        self.task_queue_repo = JudgeTaskQueueRepository()
        self.heartbeat_repo = WorkerHeartbeatsRepository()

        # Load judge model config from database settings
        judge_config = self._load_judge_config()
        model_name = judge_config.get('model_name', 'phi4-mini:3.8b-q8_0')
        max_new_tokens = judge_config.get('max_new_tokens', 512)
        temperature = judge_config.get('temperature', 0.1)
        num_ctx = judge_config.get('num_ctx', 4096)
        
        logger.info(f"Loaded judge model config: {model_name}")

        # Initialize Ollama client with timeout for bulk processing
        self.ollama_client = OllamaInference(
            model_name=model_name,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            num_ctx=num_ctx,
            request_timeout=timeout
        )
        self.ollama_client.base_url = server_url

        # Worker state
        self.running = False
        self.tasks_processed = 0
        self.consecutive_failures = 0
        self.circuit_breaker_threshold = 5
        self.current_task_id = None

        logger.info(f"Initialized queue consumer {worker_id} for server {server_url}")

    def _load_judge_config(self) -> dict:
        """Load judge model configuration from database settings."""
        try:
            from ..data_access import SettingsRepository
            import json
            
            orch_json = SettingsRepository.get("orchestration")
            if orch_json:
                orchestration_config = json.loads(orch_json)
                judge_config = orchestration_config.get('judge_model', {})
                if judge_config:
                    logger.info(f"Loaded judge config from database: {judge_config.get('model_name', 'unknown')}")
                    return judge_config
                else:
                    logger.warning("No judge_model found in orchestration config, using defaults")
            else:
                logger.warning("No orchestration config found in database, using defaults")
        except Exception as e:
            logger.error(f"Failed to load judge config from database: {e}")
        
        # Return default config if loading fails
        return {
            'model_name': 'phi4-mini:3.8b-q8_0',
            'max_new_tokens': 512,
            'temperature': 0.1,
            'num_ctx': 4096
        }

    async def start_processing(self, job_id: Optional[UUID] = None):
        """Start processing tasks from the queue."""
        self.running = True
        logger.info(f"Starting queue consumer {self.worker_id} for job {job_id}")

        try:
            await self._processing_loop(job_id)
        except Exception as e:
            logger.error(f"Queue consumer {self.worker_id} failed: {e}")
        finally:
            await self._cleanup()

    def stop_processing(self):
        """Stop processing tasks."""
        logger.info(f"Stopping queue consumer {self.worker_id}")
        self.running = False

    async def _processing_loop(self, job_id: Optional[UUID]):
        """Main processing loop."""
        last_heartbeat = datetime.now()

        while self.running:
            try:
                # Send heartbeat if needed
                now = datetime.now()
                if (now - last_heartbeat).total_seconds() >= self.heartbeat_interval:
                    await self._send_heartbeat(job_id)
                    last_heartbeat = now

                # Check for expired leases and requeue them
                expired_count = self.task_queue_repo.requeue_expired_leases()
                if expired_count > 0:
                    logger.info(f"Requeued {expired_count} expired tasks")

                # Try to lease a task
                task = self.task_queue_repo.lease_next_task(
                    server_url=self.server_url,
                    worker_id=self.worker_id,
                    lease_duration_minutes=self.lease_duration_minutes
                )

                if task:
                    self.current_task_id = task.id
                    await self._send_heartbeat(job_id)  # Update with current task

                    logger.info(
                        f"Consumer {self.worker_id} leased task {task.id} "
                        f"(paper {task.paper_id}, profile {task.profile_id})"
                    )

                    success = await self._process_task(task)

                    if success:
                        self.consecutive_failures = 0
                        self.tasks_processed += 1
                        # Record success in circuit breaker
                        circuit_breaker = error_handler.get_circuit_breaker(self.server_url)
                        circuit_breaker.record_success()
                    else:
                        self.consecutive_failures += 1
                        # Record failure in circuit breaker
                        circuit_breaker = error_handler.get_circuit_breaker(self.server_url)
                        circuit_breaker.record_failure()

                    self.current_task_id = None
                    await self._send_heartbeat(job_id)  # Update after task completion
                else:
                    # No tasks available, wait before checking again
                    await asyncio.sleep(5)

                # Check circuit breaker using intelligent error handler
                circuit_breaker = error_handler.get_circuit_breaker(self.server_url)
                if not circuit_breaker.can_attempt():
                    logger.error(
                        f"Consumer {self.worker_id} circuit breaker open "
                        f"(failures: {circuit_breaker.failure_count}, state: {circuit_breaker.state})"
                    )
                    break

                # Check consecutive failures for worker termination
                if self.consecutive_failures >= 5:
                    logger.error(
                        f"Consumer {self.worker_id} terminating after "
                        f"{self.consecutive_failures} consecutive failures"
                    )
                    break

            except Exception as e:
                logger.error(f"Consumer {self.worker_id} error in processing loop: {e}")
                await asyncio.sleep(10)  # Back off on errors

    async def _process_task(self, task: JudgeTask) -> bool:
        """Process a single judge task with intelligent error handling."""
        try:
            # Mark task as in progress
            success = self.task_queue_repo.mark_task_in_progress(task.id, self.worker_id)
            if not success:
                logger.warning(f"Failed to mark task {task.id} as in progress")
                return False

            # Get paper and profile data
            paper = PaperRepository.get_by_id(task.paper_id)
            if not paper:
                raise ValueError(f"Paper {task.paper_id} not found")

            profile = ProfileRepository.get_by_id(task.profile_id)
            if not profile:
                raise ValueError(f"Profile {task.profile_id} not found")

            # Get research interests
            research_interests = ProfileInterestsRepository.get_interests_text_by_profile(task.profile_id)
            if not research_interests:
                raise ValueError(f"No research interests found for profile {task.profile_id}")

            # Perform LLM judge scoring with intelligent error handling
            score_data = await self._score_paper_with_error_handling(task, paper, research_interests)

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
            self.task_queue_repo.mark_task_completed(task.id)

            logger.info(
                f"Consumer {self.worker_id} completed task {task.id} "
                f"with score {score_data['score']}"
            )

            return True

        except Exception as e:
            # Use intelligent error classification
            classification = error_handler.classify_error(e, {
                "task_id": task.id,
                "paper_id": task.paper_id,
                "profile_id": task.profile_id,
                "worker_id": self.worker_id,
                "server_url": self.server_url
            })

            # Log the error with classification details
            await error_handler.log_error(
                classification,
                str(task.job_id),
                task.id,
                self.server_url,
                self.worker_id
            )

            logger.warning(
                f"Consumer {self.worker_id} task {task.id} failed "
                f"(attempt {task.attempts + 1}): {e} "
                f"[Type: {classification.error_type.value}, Severity: {classification.severity.value}]"
            )

            # Handle based on error classification
            should_retry = await self._handle_classified_error(task, classification)

            return False

    async def _score_paper_with_error_handling(self, task: JudgeTask, paper: dict, research_interests: str) -> dict:
        """Score a paper using LLM judge with intelligent error handling and retry logic."""
        async def _attempt_scoring():
            """Single attempt at scoring the paper."""
            messages = [
                {"role": "user", "content": research_prompt(research_interests, paper['abstract'])}
            ]

            response = self.ollama_client.invoke(
                messages=messages,
                system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT
            )

            # Parse the response
            response_json = json_repair.loads(response)

            # Validate response
            if not isinstance(response_json, dict):
                raise ValueError("Invalid JSON response from LLM")

            required_keys = ['score', 'related', 'rationale']
            if not all(key in response_json for key in required_keys):
                raise ValueError(f"Missing required keys in response: {response_json}")

            # Validate and convert values
            score_val = int(response_json['score'])
            related_val = bool(response_json['related'])
            rationale_val = str(response_json['rationale'])

            # Validate score range
            if not (1 <= score_val <= 10):
                score_val = max(1, min(10, score_val))  # Clamp to valid range

            return {
                'score': score_val,
                'related': related_val,
                'rationale': rationale_val
            }

        # Use intelligent error handling with retry
        result, classification = await error_handler.handle_error_with_retry(
            operation=_attempt_scoring,
            server_url=self.server_url,
            context={
                "task_id": task.id,
                "paper_id": task.paper_id,
                "profile_id": task.profile_id,
                "worker_id": self.worker_id
            }
        )

        if result is None:
            # All retries exhausted
            raise Exception(f"Scoring failed after retries: {classification.description}")

        return result

    async def _handle_classified_error(self, task: JudgeTask, classification) -> bool:
        """Handle error based on intelligent classification."""
        # Check if worker should terminate
        should_terminate = await error_handler.should_terminate_worker(
            classification, self.consecutive_failures
        )

        if should_terminate:
            logger.error(
                f"Consumer {self.worker_id} terminating due to error classification: "
                f"{classification.error_type.value} (severity: {classification.severity.value})"
            )
            self.running = False
            return False

        # Determine if task should be retried or failed
        if classification.error_type.value == 'data_issue':
            # Data issues should not be retried
            self.task_queue_repo.mark_task_failed(task.id, classification.description)
            logger.info(f"Task {task.id} marked as failed due to data issue")
            return False

        # Check retry attempts
        if task.attempts >= classification.retry_strategy.max_retries:
            # Max retries reached
            self.task_queue_repo.mark_task_failed(
                task.id,
                f"Max retries ({task.attempts}) exceeded: {classification.description}"
            )
            logger.info(f"Task {task.id} failed after {task.attempts} attempts")
            return False

        # Increment attempts and requeue
        self.task_queue_repo.increment_task_attempts(task.id, classification.description)
        logger.info(f"Task {task.id} requeued for retry (attempt {task.attempts + 1})")
        return True

    def _is_llm_error(self, error_message: str) -> bool:
        """Check if error is LLM-related (parsing, malformed response, etc.)."""
        llm_error_keywords = [
            'json', 'parse', 'malformed', 'response', 'schema',
            'validation', 'content', 'format'
        ]
        return any(keyword in error_message.lower() for keyword in llm_error_keywords)

    def _is_server_error(self, error_message: str) -> bool:
        """Check if error is server-related (connectivity, HTTP errors, etc.)."""
        server_error_keywords = [
            'connection', 'timeout', 'refused', 'unreachable',
            'http', 'network', 'server', 'ollama'
        ]
        return any(keyword in error_message.lower() for keyword in server_error_keywords)

    async def _handle_llm_error(self, task: JudgeTask, error_message: str):
        """Handle LLM inference errors (retry up to max_retries)."""
        task.attempts += 1

        if task.attempts >= self.max_retries:
            self.task_queue_repo.mark_task_failed(
                task.id, f"LLM Error: {error_message}", increment_attempts=False
            )
            logger.error(
                f"Consumer {self.worker_id} permanently failed task {task.id} "
                f"after {task.attempts} LLM attempts"
            )
        else:
            self.task_queue_repo.mark_task_failed(
                task.id, f"LLM Error: {error_message}"
            )
            logger.info(
                f"Consumer {self.worker_id} will retry task {task.id} "
                f"(LLM attempt {task.attempts + 1})"
            )

    async def _handle_server_error(self, task: JudgeTask, error_message: str):
        """Handle server connectivity errors (retry up to max_retries, then terminate worker)."""
        task.attempts += 1

        if task.attempts >= self.max_retries:
            self.task_queue_repo.mark_task_failed(
                task.id, f"Server Error: {error_message}", increment_attempts=False
            )
            logger.error(
                f"Consumer {self.worker_id} terminating due to server errors "
                f"after {task.attempts} attempts"
            )
            self.running = False  # Terminate worker
        else:
            self.task_queue_repo.mark_task_failed(
                task.id, f"Server Error: {error_message}"
            )
            logger.info(
                f"Consumer {self.worker_id} will retry task {task.id} "
                f"(server attempt {task.attempts + 1})"
            )

    async def _handle_data_error(self, task: JudgeTask, error_message: str):
        """Handle data-related errors (fail immediately)."""
        self.task_queue_repo.mark_task_failed(
            task.id, f"Data Error: {error_message}", increment_attempts=False
        )
        logger.error(
            f"Consumer {self.worker_id} permanently failed task {task.id} "
            f"due to data error: {error_message}"
        )

    async def _send_heartbeat(self, job_id: Optional[UUID]):
        """Send heartbeat to indicate consumer is alive."""
        try:
            self.heartbeat_repo.upsert_heartbeat(
                worker_id=self.worker_id,
                server_url=self.server_url,
                job_id=job_id,
                status='active',
                tasks_processed=self.tasks_processed,
                current_task_id=self.current_task_id
            )
        except Exception as e:
            logger.warning(f"Consumer {self.worker_id} failed to send heartbeat: {e}")

    async def _cleanup(self):
        """Clean up consumer resources."""
        logger.info(f"Consumer {self.worker_id} cleaning up")

        # Mark as inactive
        try:
            self.heartbeat_repo.mark_worker_inactive(
                worker_id=self.worker_id,
                server_url=self.server_url,
                job_id=None  # Clean up all jobs for this worker
            )
        except Exception as e:
            logger.warning(f"Consumer {self.worker_id} failed to cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get consumer statistics."""
        return {
            'worker_id': self.worker_id,
            'server_url': self.server_url,
            'tasks_processed': self.tasks_processed,
            'consecutive_failures': self.consecutive_failures,
            'current_task_id': self.current_task_id,
            'running': self.running
        }
