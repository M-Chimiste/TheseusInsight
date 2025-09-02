"""
Intelligent error handling for distributed multi-Ollama processing.
Provides error classification, retry strategies, and circuit breaker functionality.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json
import re

from ..db import get_connection_pool


class ErrorType(Enum):
    """Types of errors that can occur during distributed processing."""
    LLM_INFERENCE = "llm_inference"  # Malformed JSON, parsing errors, content validation
    SERVER_CONNECTIVITY = "server_connectivity"  # Network timeouts, connection refused, HTTP errors
    DATA_ISSUE = "data_issue"  # Missing abstracts, corrupted content, encoding problems
    RATE_LIMIT = "rate_limit"  # HTTP 429, temporary server overload
    RESOURCE_CONSTRAINT = "resource_constraint"  # GPU memory, disk space, etc.
    UNKNOWN = "unknown"  # Unclassified errors


class ErrorSeverity(Enum):
    """Severity levels for errors."""
    LOW = "low"      # Minor issues, continue processing
    MEDIUM = "medium"  # Moderate issues, may retry
    HIGH = "high"    # Serious issues, terminate worker
    CRITICAL = "critical"  # System-level issues, shutdown


class RetryStrategy:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for the given retry attempt."""
        delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)

        if self.jitter:
            # Add random jitter to prevent thundering herd
            import random
            delay = delay * (0.5 + random.random() * 0.5)

        return delay


class ErrorClassification:
    """Result of error classification."""

    def __init__(
        self,
        error_type: ErrorType,
        severity: ErrorSeverity,
        retry_strategy: RetryStrategy,
        description: str,
        recoverable: bool = True,
        context: Optional[Dict[str, Any]] = None
    ):
        self.error_type = error_type
        self.severity = severity
        self.retry_strategy = retry_strategy
        self.description = description
        self.recoverable = recoverable
        self.context = context or {}
        self.timestamp = datetime.utcnow()


class CircuitBreaker:
    """Circuit breaker for server failure management."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 300,  # 5 minutes
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open

    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def record_success(self):
        """Record a success and potentially close the circuit."""
        if self.state == "half_open":
            self.failure_count = 0
            self.state = "closed"
        elif self.state == "open":
            # Check if recovery timeout has passed
            if self.last_failure_time and \
               (datetime.utcnow() - self.last_failure_time).seconds > self.recovery_timeout:
                self.state = "half_open"

    def can_attempt(self) -> bool:
        """Check if an attempt can be made."""
        if self.state == "closed":
            return True
        elif self.state == "open":
            # Check if we should transition to half-open
            if self.last_failure_time and \
               (datetime.utcnow() - self.last_failure_time).seconds > self.recovery_timeout:
                self.state = "half_open"
                return True
            return False
        elif self.state == "half_open":
            return True
        return False


class DistributedErrorHandler:
    """Intelligent error handler for distributed multi-Ollama processing."""

    def __init__(self):
        self.server_circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_patterns = self._initialize_error_patterns()
        self.default_strategies = self._initialize_default_strategies()

    def _initialize_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize error pattern matching rules."""
        return {
            # LLM Inference Errors
            "json_decode_error": {
                "type": ErrorType.LLM_INFERENCE,
                "severity": ErrorSeverity.MEDIUM,
                "patterns": [
                    r"JSONDecodeError",
                    r"Expecting ',' delimiter",
                    r"Expecting ':' delimiter",
                    r"Unterminated string",
                    r"Invalid JSON"
                ]
            },
            "malformed_response": {
                "type": ErrorType.LLM_INFERENCE,
                "severity": ErrorSeverity.MEDIUM,
                "patterns": [
                    r"response is not valid JSON",
                    r"unexpected end of JSON",
                    r"invalid character",
                    r"malformed.*response"
                ]
            },
            "content_validation": {
                "type": ErrorType.LLM_INFERENCE,
                "severity": ErrorSeverity.LOW,
                "patterns": [
                    r"content validation failed",
                    r"missing required field",
                    r"invalid score format",
                    r"score out of range"
                ]
            },

            # Server Connectivity Errors
            "connection_refused": {
                "type": ErrorType.SERVER_CONNECTIVITY,
                "severity": ErrorSeverity.HIGH,
                "patterns": [
                    r"Connection refused",
                    r"Connection reset",
                    r"Connection aborted",
                    r"connection.*failed"
                ]
            },
            "timeout_error": {
                "type": ErrorType.SERVER_CONNECTIVITY,
                "severity": ErrorSeverity.MEDIUM,
                "patterns": [
                    r"timeout",
                    r"timed out",
                    r"request timeout",
                    r"ReadTimeout"
                ]
            },
            "http_error": {
                "type": ErrorType.SERVER_CONNECTIVITY,
                "severity": ErrorSeverity.HIGH,
                "patterns": [
                    r"HTTP.*5\d\d",  # 5xx errors
                    r"502 Bad Gateway",
                    r"503 Service Unavailable",
                    r"504 Gateway Timeout"
                ]
            },

            # Data Issues
            "missing_abstract": {
                "type": ErrorType.DATA_ISSUE,
                "severity": ErrorSeverity.LOW,
                "patterns": [
                    r"missing abstract",
                    r"no abstract available",
                    r"abstract is None",
                    r"empty abstract"
                ]
            },
            "encoding_error": {
                "type": ErrorType.DATA_ISSUE,
                "severity": ErrorSeverity.LOW,
                "patterns": [
                    r"encoding error",
                    r"UnicodeDecodeError",
                    r"codec can't decode",
                    r"character encoding"
                ]
            },
            "corrupted_content": {
                "type": ErrorType.DATA_ISSUE,
                "severity": ErrorSeverity.LOW,
                "patterns": [
                    r"corrupted content",
                    r"invalid content",
                    r"content validation error"
                ]
            },

            # Rate Limiting
            "rate_limit": {
                "type": ErrorType.RATE_LIMIT,
                "severity": ErrorSeverity.MEDIUM,
                "patterns": [
                    r"429 Too Many Requests",
                    r"rate limit exceeded",
                    r"too many requests",
                    r"quota exceeded"
                ]
            }
        }

    def _initialize_default_strategies(self) -> Dict[ErrorType, RetryStrategy]:
        """Initialize default retry strategies for each error type."""
        return {
            ErrorType.LLM_INFERENCE: RetryStrategy(
                max_retries=3,
                base_delay=2.0,
                max_delay=30.0,
                backoff_factor=1.5
            ),
            ErrorType.SERVER_CONNECTIVITY: RetryStrategy(
                max_retries=3,
                base_delay=5.0,
                max_delay=60.0,
                backoff_factor=2.0
            ),
            ErrorType.DATA_ISSUE: RetryStrategy(
                max_retries=0,  # No retries for data issues
                base_delay=0.0,
                max_delay=0.0
            ),
            ErrorType.RATE_LIMIT: RetryStrategy(
                max_retries=5,
                base_delay=10.0,
                max_delay=300.0,  # 5 minutes max
                backoff_factor=2.0
            ),
            ErrorType.RESOURCE_CONSTRAINT: RetryStrategy(
                max_retries=2,
                base_delay=30.0,
                max_delay=300.0,
                backoff_factor=2.0
            ),
            ErrorType.UNKNOWN: RetryStrategy(
                max_retries=1,
                base_delay=5.0,
                max_delay=30.0
            )
        }

    def classify_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorClassification:
        """Classify an error and determine appropriate handling strategy."""
        error_message = str(error).lower()
        error_type = str(type(error).__name__)

        # Combine error message and type for pattern matching
        full_error_text = f"{error_type}: {error_message}"

        # Try to match against known patterns
        for pattern_name, pattern_config in self.error_patterns.items():
            for pattern in pattern_config["patterns"]:
                if re.search(pattern, full_error_text, re.IGNORECASE):
                    error_type_enum = pattern_config["type"]
                    severity = pattern_config["severity"]

                    retry_strategy = self.default_strategies.get(error_type_enum, self.default_strategies[ErrorType.UNKNOWN])

                    # Adjust strategy based on severity
                    if severity == ErrorSeverity.HIGH:
                        retry_strategy = RetryStrategy(max_retries=1, base_delay=10.0)
                    elif severity == ErrorSeverity.CRITICAL:
                        retry_strategy = RetryStrategy(max_retries=0)

                    return ErrorClassification(
                        error_type=error_type_enum,
                        severity=severity,
                        retry_strategy=retry_strategy,
                        description=f"Pattern match: {pattern_name}",
                        recoverable=retry_strategy.max_retries > 0,
                        context={"matched_pattern": pattern_name, "original_error": str(error)}
                    )

        # No pattern matched - classify as unknown
        return ErrorClassification(
            error_type=ErrorType.UNKNOWN,
            severity=ErrorSeverity.MEDIUM,
            retry_strategy=self.default_strategies[ErrorType.UNKNOWN],
            description="Unknown error type",
            recoverable=True,
            context={"original_error": str(error), "error_type": error_type}
        )

    def get_circuit_breaker(self, server_url: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a server."""
        if server_url not in self.server_circuit_breakers:
            self.server_circuit_breakers[server_url] = CircuitBreaker()

        return self.server_circuit_breakers[server_url]

    async def handle_error_with_retry(
        self,
        error: Exception,
        operation: Callable,
        server_url: Optional[str] = None,
        max_attempts: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[Any, ErrorClassification]:
        """Handle an error with intelligent retry logic."""

        # Classify the error
        classification = self.classify_error(error, context)

        # Check circuit breaker if server URL provided
        if server_url:
            circuit_breaker = self.get_circuit_breaker(server_url)
            if not circuit_breaker.can_attempt():
                classification.description += " (circuit breaker open)"
                classification.recoverable = False
                return None, classification

        # Determine retry strategy
        retry_strategy = classification.retry_strategy
        if max_attempts is not None:
            retry_strategy.max_retries = min(retry_strategy.max_retries, max_attempts - 1)

        # Attempt retries
        last_error = error
        for attempt in range(retry_strategy.max_retries + 1):
            try:
                if attempt > 0:
                    # Wait before retry
                    delay = retry_strategy.get_delay(attempt - 1)
                    await asyncio.sleep(delay)

                # Attempt the operation
                result = await operation()

                # Success - record in circuit breaker
                if server_url:
                    circuit_breaker = self.get_circuit_breaker(server_url)
                    circuit_breaker.record_success()

                return result, classification

            except Exception as e:
                last_error = e

                # Record failure in circuit breaker
                if server_url:
                    circuit_breaker = self.get_circuit_breaker(server_url)
                    circuit_breaker.record_failure()

                # If this is the last attempt, break
                if attempt >= retry_strategy.max_retries:
                    break

        # All retries exhausted
        classification.context["final_error"] = str(last_error)
        classification.context["total_attempts"] = retry_strategy.max_retries + 1

        return None, classification

    async def should_terminate_worker(self, classification: ErrorClassification, consecutive_failures: int) -> bool:
        """Determine if a worker should terminate based on error classification."""
        # Always terminate on critical errors
        if classification.severity == ErrorSeverity.CRITICAL:
            return True

        # Terminate on high severity server connectivity errors
        if (classification.error_type == ErrorType.SERVER_CONNECTIVITY and
            classification.severity == ErrorSeverity.HIGH):
            return True

        # Terminate after too many consecutive failures
        if consecutive_failures >= 5:
            return True

        return False

    async def log_error(
        self,
        classification: ErrorClassification,
        job_id: str,
        task_id: Optional[int] = None,
        server_url: Optional[str] = None,
        worker_id: Optional[str] = None
    ):
        """Log error details to database for monitoring and debugging."""
        try:
            pool = await get_connection_pool()

            async with pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO error_logs (
                        job_id, task_id, server_url, worker_id,
                        error_type, severity, description, context,
                        created_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    """,
                    job_id,
                    task_id,
                    server_url,
                    worker_id,
                    classification.error_type.value,
                    classification.severity.value,
                    classification.description,
                    json.dumps(classification.context),
                    classification.timestamp
                )

        except Exception as e:
            # Don't let logging errors break the main flow
            print(f"Warning: Failed to log error: {e}")

    def get_error_summary(self, job_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get error summary for monitoring."""
        # This would query the error_logs table to provide insights
        # For now, return a placeholder structure
        return {
            "job_id": job_id,
            "time_range_hours": hours,
            "error_counts": {
                "llm_inference": 0,
                "server_connectivity": 0,
                "data_issue": 0,
                "rate_limit": 0,
                "resource_constraint": 0,
                "unknown": 0
            },
            "severity_counts": {
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0
            },
            "top_error_patterns": [],
            "circuit_breaker_status": {
                server_url: {
                    "state": cb.state,
                    "failure_count": cb.failure_count,
                    "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None
                }
                for server_url, cb in self.server_circuit_breakers.items()
            }
        }


# Global error handler instance
error_handler = DistributedErrorHandler()
