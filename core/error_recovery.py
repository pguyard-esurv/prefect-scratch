"""
Error handling and recovery mechanisms for container environments.

This module provides comprehensive error handling, retry logic, automatic recovery,
local operation queuing, disk space monitoring, and alerting integration for
containerized distributed processing systems.
"""

import json
import logging
import os
import shutil
import signal
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Optional

from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from core.database import DatabaseManager, _is_transient_error


class ErrorSeverity(Enum):
    """Error severity levels for alerting."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(Enum):
    """Recovery action types."""

    RETRY = "retry"
    RESTART = "restart"
    QUEUE_LOCALLY = "queue_locally"
    ALERT_AND_CONTINUE = "alert_and_continue"
    FAIL_FAST = "fail_fast"


@dataclass
class ErrorContext:
    """Context information for error handling."""

    error_type: str
    error_message: str
    component: str
    operation: str
    timestamp: datetime
    retry_count: int
    severity: ErrorSeverity
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat() + "Z"
        result["severity"] = self.severity.value
        return result


@dataclass
class RecoveryResult:
    """Result of recovery operation."""

    success: bool
    action_taken: RecoveryAction
    message: str
    retry_count: int
    duration_seconds: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        result["action_taken"] = self.action_taken.value
        return result


class LocalOperationQueue:
    """Local queue for operations during network partitions."""

    def __init__(self, max_size: int = 10000, persistence_file: Optional[str] = None):
        """
        Initialize local operation queue.

        Args:
            max_size: Maximum number of operations to queue
            persistence_file: Optional file to persist queue across restarts
        """
        self.queue = Queue(maxsize=max_size)
        self.max_size = max_size
        self.persistence_file = persistence_file
        self.lock = threading.Lock()
        self._load_persisted_operations()

    def enqueue_operation(self, operation: dict[str, Any]) -> bool:
        """
        Enqueue an operation for later processing.

        Args:
            operation: Operation data to queue

        Returns:
            True if operation was queued, False if queue is full
        """
        try:
            operation["queued_at"] = datetime.now().isoformat() + "Z"
            self.queue.put_nowait(operation)
            self._persist_queue()
            return True
        except Exception:
            return False

    def dequeue_operation(self, timeout: float = 1.0) -> Optional[dict[str, Any]]:
        """
        Dequeue an operation for processing.

        Args:
            timeout: Timeout in seconds

        Returns:
            Operation data or None if queue is empty
        """
        try:
            operation = self.queue.get(timeout=timeout)
            self._persist_queue()
            return operation
        except Empty:
            return None

    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()

    def is_full(self) -> bool:
        """Check if queue is full."""
        return self.queue.full()

    def clear_queue(self) -> int:
        """Clear all operations from queue and return count cleared."""
        count = 0
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                count += 1
            except Empty:
                break
        self._persist_queue()
        return count

    def _persist_queue(self):
        """Persist queue to file if persistence is enabled."""
        if not self.persistence_file:
            return

        try:
            with self.lock:
                operations = []
                temp_queue = Queue()

                # Extract all operations
                while not self.queue.empty():
                    try:
                        op = self.queue.get_nowait()
                        operations.append(op)
                        temp_queue.put(op)
                    except Empty:
                        break

                # Restore queue
                while not temp_queue.empty():
                    try:
                        self.queue.put_nowait(temp_queue.get_nowait())
                    except Exception:
                        break

                # Write to file
                with open(self.persistence_file, "w") as f:
                    json.dump(operations, f, indent=2)

        except Exception as e:
            logging.warning(f"Failed to persist operation queue: {e}")

    def _load_persisted_operations(self):
        """Load persisted operations from file."""
        if not self.persistence_file or not os.path.exists(self.persistence_file):
            return

        try:
            with open(self.persistence_file) as f:
                operations = json.load(f)

            for operation in operations:
                try:
                    self.queue.put_nowait(operation)
                except Exception:
                    break  # Queue is full

        except Exception as e:
            logging.warning(f"Failed to load persisted operations: {e}")


class DiskSpaceMonitor:
    """Monitor disk space and perform cleanup when needed."""

    def __init__(
        self,
        paths_to_monitor: list[str],
        warning_threshold_percent: float = 80.0,
        critical_threshold_percent: float = 90.0,
        cleanup_paths: Optional[list[str]] = None,
    ):
        """
        Initialize disk space monitor.

        Args:
            paths_to_monitor: List of paths to monitor for disk usage
            warning_threshold_percent: Warning threshold percentage
            critical_threshold_percent: Critical threshold percentage
            cleanup_paths: Optional list of paths to clean up when space is low
        """
        self.paths_to_monitor = paths_to_monitor
        self.warning_threshold = warning_threshold_percent
        self.critical_threshold = critical_threshold_percent
        self.cleanup_paths = cleanup_paths or []
        self.logger = logging.getLogger(__name__)

    def check_disk_space(self) -> dict[str, Any]:
        """
        Check disk space for all monitored paths.

        Returns:
            Dictionary with disk space information and alerts
        """
        results = {
            "timestamp": datetime.now().isoformat() + "Z",
            "paths": {},
            "alerts": [],
            "overall_status": "healthy",
        }

        for path in self.paths_to_monitor:
            try:
                usage = shutil.disk_usage(path)
                used_percent = (usage.used / usage.total) * 100

                path_info = {
                    "path": path,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "used_percent": round(used_percent, 2),
                    "status": "healthy",
                }

                if used_percent >= self.critical_threshold:
                    path_info["status"] = "critical"
                    results["overall_status"] = "critical"
                    results["alerts"].append(
                        {
                            "severity": "critical",
                            "message": f"Critical disk space on {path}: {used_percent:.1f}% used",
                            "path": path,
                            "used_percent": used_percent,
                        }
                    )
                elif used_percent >= self.warning_threshold:
                    path_info["status"] = "warning"
                    if results["overall_status"] == "healthy":
                        results["overall_status"] = "warning"
                    results["alerts"].append(
                        {
                            "severity": "warning",
                            "message": f"Low disk space on {path}: {used_percent:.1f}% used",
                            "path": path,
                            "used_percent": used_percent,
                        }
                    )

                results["paths"][path] = path_info

            except Exception as e:
                results["paths"][path] = {
                    "path": path,
                    "error": str(e),
                    "status": "error",
                }
                results["alerts"].append(
                    {
                        "severity": "high",
                        "message": f"Failed to check disk space for {path}: {e}",
                        "path": path,
                    }
                )

        return results

    def cleanup_disk_space(self, target_free_percent: float = 20.0) -> dict[str, Any]:
        """
        Perform disk cleanup operations.

        Args:
            target_free_percent: Target free space percentage after cleanup

        Returns:
            Dictionary with cleanup results
        """
        results = {
            "timestamp": datetime.now().isoformat() + "Z",
            "target_free_percent": target_free_percent,
            "cleanup_operations": [],
            "space_freed_gb": 0.0,
            "success": True,
        }

        for cleanup_path in self.cleanup_paths:
            try:
                cleanup_result = self._cleanup_path(cleanup_path, target_free_percent)
                results["cleanup_operations"].append(cleanup_result)
                results["space_freed_gb"] += cleanup_result.get("space_freed_gb", 0)

            except Exception as e:
                results["cleanup_operations"].append(
                    {"path": cleanup_path, "error": str(e), "success": False}
                )
                results["success"] = False

        return results

    def _cleanup_path(self, path: str, target_free_percent: float) -> dict[str, Any]:
        """Clean up a specific path."""
        cleanup_result = {
            "path": path,
            "files_removed": 0,
            "space_freed_gb": 0.0,
            "success": True,
            "operations": [],
        }

        if not os.path.exists(path):
            cleanup_result["success"] = False
            cleanup_result["error"] = "Path does not exist"
            return cleanup_result

        initial_usage = shutil.disk_usage(path)

        # Clean up log files older than 7 days
        if "log" in path.lower():
            cleanup_result["operations"].append(
                self._cleanup_old_files(path, "*.log", days=7)
            )

        # Clean up temporary files
        if "tmp" in path.lower() or "temp" in path.lower():
            cleanup_result["operations"].append(
                self._cleanup_old_files(path, "*", days=1)
            )

        # Clean up cache files older than 3 days
        if "cache" in path.lower():
            cleanup_result["operations"].append(
                self._cleanup_old_files(path, "*", days=3)
            )

        final_usage = shutil.disk_usage(path)
        space_freed = initial_usage.used - final_usage.used
        cleanup_result["space_freed_gb"] = round(space_freed / (1024**3), 2)

        return cleanup_result

    def _cleanup_old_files(self, path: str, pattern: str, days: int) -> dict[str, Any]:
        """Clean up old files matching pattern."""
        operation_result = {
            "operation": f"cleanup_files_older_than_{days}_days",
            "path": path,
            "pattern": pattern,
            "files_removed": 0,
            "space_freed_gb": 0.0,
        }

        try:
            cutoff_time = datetime.now() - timedelta(days=days)
            total_size = 0

            for file_path in Path(path).rglob(pattern):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        operation_result["files_removed"] += 1
                        total_size += file_size

            operation_result["space_freed_gb"] = round(total_size / (1024**3), 2)

        except Exception as e:
            operation_result["error"] = str(e)

        return operation_result


class AlertManager:
    """Manage alerts for critical error scenarios."""

    def __init__(self, alert_handlers: Optional[list[Callable]] = None):
        """
        Initialize alert manager.

        Args:
            alert_handlers: List of alert handler functions
        """
        self.alert_handlers = alert_handlers or []
        self.logger = logging.getLogger(__name__)
        self.alert_history = []

    def add_alert_handler(self, handler: Callable):
        """Add an alert handler function."""
        self.alert_handlers.append(handler)

    def send_alert(
        self,
        severity: ErrorSeverity,
        title: str,
        message: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Send an alert through all configured handlers.

        Args:
            severity: Alert severity level
            title: Alert title
            message: Alert message
            metadata: Optional additional metadata

        Returns:
            True if at least one handler succeeded
        """
        alert_data = {
            "timestamp": datetime.now().isoformat() + "Z",
            "severity": severity.value,
            "title": title,
            "message": message,
            "metadata": metadata or {},
            "component": "error_recovery",
        }

        # Add to history
        self.alert_history.append(alert_data)

        # Keep only last 1000 alerts
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

        success_count = 0

        for handler in self.alert_handlers:
            try:
                handler(alert_data)
                success_count += 1
            except Exception as e:
                self.logger.error(f"Alert handler failed: {e}")

        # Log alert
        log_level = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL,
        }.get(severity, logging.WARNING)

        self.logger.log(
            log_level, f"ALERT [{severity.value.upper()}] {title}: {message}"
        )

        return success_count > 0

    def get_alert_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent alert history."""
        return self.alert_history[-limit:]


class ErrorRecoveryManager:
    """Comprehensive error handling and recovery manager."""

    def __init__(
        self,
        database_managers: Optional[dict[str, DatabaseManager]] = None,
        local_queue_path: Optional[str] = None,
        disk_monitor_paths: Optional[list[str]] = None,
        alert_manager: Optional[AlertManager] = None,
    ):
        """
        Initialize error recovery manager.

        Args:
            database_managers: Dictionary of database managers
            local_queue_path: Path for local operation queue persistence
            disk_monitor_paths: Paths to monitor for disk space
            alert_manager: Alert manager instance
        """
        self.database_managers = database_managers or {}
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.local_queue = LocalOperationQueue(persistence_file=local_queue_path)

        self.disk_monitor = DiskSpaceMonitor(
            paths_to_monitor=disk_monitor_paths or ["/", "/tmp", "/var/log"],
            cleanup_paths=["/tmp", "/var/log", "/app/logs"],
        )

        self.alert_manager = alert_manager or AlertManager()

        # Recovery statistics
        self.recovery_stats = {
            "total_errors": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "retry_attempts": 0,
            "container_restarts": 0,
        }

        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self._graceful_shutdown()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def _graceful_shutdown(self):
        """Perform graceful shutdown operations."""
        try:
            # Process remaining queued operations
            self.logger.info("Processing remaining queued operations...")
            processed = 0
            while not self.local_queue.queue.empty() and processed < 100:
                operation = self.local_queue.dequeue_operation(timeout=0.1)
                if operation:
                    self._process_queued_operation(operation)
                    processed += 1

            self.logger.info(f"Processed {processed} queued operations during shutdown")

        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")

    def handle_database_error(
        self,
        error: Exception,
        database_name: str,
        operation: str,
        context: Optional[dict[str, Any]] = None,
    ) -> RecoveryResult:
        """
        Handle database-related errors with retry logic.

        Args:
            error: The database error
            database_name: Name of the database
            operation: Operation that failed
            context: Additional context information

        Returns:
            RecoveryResult with recovery outcome
        """
        start_time = time.time()
        self.recovery_stats["total_errors"] += 1

        error_context = ErrorContext(
            error_type=type(error).__name__,
            error_message=str(error),
            component="database",
            operation=operation,
            timestamp=datetime.now(),
            retry_count=0,
            severity=self._determine_error_severity(error),
            metadata=context or {},
        )

        # Check if error is transient and retryable
        if _is_transient_error(error):
            return self._retry_database_operation(
                error_context, database_name, operation, context
            )
        else:
            # Non-transient error - queue operation locally if possible
            if self._can_queue_operation(operation):
                return self._queue_operation_locally(error_context, operation, context)
            else:
                # Critical error - send alert and fail
                self.alert_manager.send_alert(
                    ErrorSeverity.CRITICAL,
                    f"Critical Database Error - {database_name}",
                    f"Non-recoverable database error in {operation}: {error}",
                    error_context.to_dict(),
                )

                self.recovery_stats["failed_recoveries"] += 1

                return RecoveryResult(
                    success=False,
                    action_taken=RecoveryAction.FAIL_FAST,
                    message=f"Non-recoverable database error: {error}",
                    retry_count=0,
                    duration_seconds=time.time() - start_time,
                    metadata=error_context.to_dict(),
                )

    def _retry_database_operation(
        self,
        error_context: ErrorContext,
        database_name: str,
        operation: str,
        context: Optional[dict[str, Any]],
    ) -> RecoveryResult:
        """Retry database operation with exponential backoff."""
        start_time = time.time()

        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=2, min=1, max=30),
            retry=retry_if_exception(_is_transient_error),
            before_sleep=before_sleep_log(self.logger, logging.WARNING),
            after=after_log(self.logger, logging.INFO),
        )
        def _execute_with_retry():
            # This would be implemented by the calling code
            # Here we just simulate the retry mechanism
            if database_name in self.database_managers:
                db_manager = self.database_managers[database_name]
                # Test connectivity
                db_manager.health_check()
                return True
            else:
                raise RuntimeError(f"Database manager '{database_name}' not found")

        try:
            _execute_with_retry()

            self.recovery_stats["successful_recoveries"] += 1
            self.recovery_stats["retry_attempts"] += error_context.retry_count

            return RecoveryResult(
                success=True,
                action_taken=RecoveryAction.RETRY,
                message="Successfully recovered from database error after retry",
                retry_count=error_context.retry_count,
                duration_seconds=time.time() - start_time,
                metadata=error_context.to_dict(),
            )

        except Exception:
            # Retry failed - queue operation locally
            return self._queue_operation_locally(error_context, operation, context)

    def _queue_operation_locally(
        self,
        error_context: ErrorContext,
        operation: str,
        context: Optional[dict[str, Any]],
    ) -> RecoveryResult:
        """Queue operation locally for later processing."""
        start_time = time.time()

        operation_data = {
            "operation": operation,
            "context": context,
            "error_context": error_context.to_dict(),
            "retry_count": 0,
            "max_retries": 3,
        }

        if self.local_queue.enqueue_operation(operation_data):
            self.alert_manager.send_alert(
                ErrorSeverity.MEDIUM,
                "Operation Queued Locally",
                f"Operation '{operation}' queued locally due to database connectivity issues",
                {"queue_size": self.local_queue.get_queue_size()},
            )

            return RecoveryResult(
                success=True,
                action_taken=RecoveryAction.QUEUE_LOCALLY,
                message="Operation queued locally for later processing",
                retry_count=0,
                duration_seconds=time.time() - start_time,
                metadata={
                    "queue_size": self.local_queue.get_queue_size(),
                    "operation": operation,
                },
            )
        else:
            # Queue is full - critical situation
            self.alert_manager.send_alert(
                ErrorSeverity.CRITICAL,
                "Local Queue Full",
                f"Cannot queue operation '{operation}' - local queue is full",
                {"queue_size": self.local_queue.get_queue_size()},
            )

            self.recovery_stats["failed_recoveries"] += 1

            return RecoveryResult(
                success=False,
                action_taken=RecoveryAction.FAIL_FAST,
                message="Local queue is full, cannot queue operation",
                retry_count=0,
                duration_seconds=time.time() - start_time,
                metadata={"queue_size": self.local_queue.get_queue_size()},
            )

    def process_queued_operations(self) -> dict[str, Any]:
        """
        Process operations from the local queue.

        Returns:
            Dictionary with processing results
        """
        results = {
            "timestamp": datetime.now().isoformat() + "Z",
            "operations_processed": 0,
            "operations_successful": 0,
            "operations_failed": 0,
            "operations_requeued": 0,
            "queue_size_before": self.local_queue.get_queue_size(),
            "queue_size_after": 0,
        }

        # Process up to 100 operations per batch
        max_operations = 100
        processed = 0

        while processed < max_operations and not self.local_queue.queue.empty():
            operation = self.local_queue.dequeue_operation(timeout=0.1)
            if not operation:
                break

            processed += 1
            results["operations_processed"] += 1

            try:
                success = self._process_queued_operation(operation)
                if success:
                    results["operations_successful"] += 1
                else:
                    # Check if we should retry
                    retry_count = operation.get("retry_count", 0)
                    max_retries = operation.get("max_retries", 3)

                    if retry_count < max_retries:
                        operation["retry_count"] = retry_count + 1
                        self.local_queue.enqueue_operation(operation)
                        results["operations_requeued"] += 1
                    else:
                        results["operations_failed"] += 1

            except Exception as e:
                self.logger.error(f"Failed to process queued operation: {e}")
                results["operations_failed"] += 1

        results["queue_size_after"] = self.local_queue.get_queue_size()

        if results["operations_processed"] > 0:
            self.logger.info(
                f"Processed {results['operations_processed']} queued operations: "
                f"{results['operations_successful']} successful, "
                f"{results['operations_failed']} failed, "
                f"{results['operations_requeued']} requeued"
            )

        return results

    def _process_queued_operation(self, operation: dict[str, Any]) -> bool:
        """
        Process a single queued operation.

        Args:
            operation: Operation data

        Returns:
            True if operation was processed successfully
        """
        try:
            operation_type = operation.get("operation", "unknown")
            operation.get("context", {})

            # This is a placeholder - actual implementation would depend on operation type
            if operation_type.startswith("database_"):
                # Test database connectivity
                for _db_name, db_manager in self.database_managers.items():
                    health = db_manager.health_check()
                    if health.get("status") != "healthy":
                        return False
                return True

            # Default success for unknown operations
            return True

        except Exception as e:
            self.logger.error(f"Error processing queued operation: {e}")
            return False

    def monitor_and_cleanup_disk_space(self) -> dict[str, Any]:
        """
        Monitor disk space and perform cleanup if needed.

        Returns:
            Dictionary with monitoring and cleanup results
        """
        # Check disk space
        disk_status = self.disk_monitor.check_disk_space()

        results = {
            "timestamp": datetime.now().isoformat() + "Z",
            "disk_status": disk_status,
            "cleanup_performed": False,
            "cleanup_results": {},
        }

        # Send alerts for disk space issues
        for alert in disk_status.get("alerts", []):
            severity_map = {
                "warning": ErrorSeverity.MEDIUM,
                "critical": ErrorSeverity.CRITICAL,
                "high": ErrorSeverity.HIGH,
            }

            severity = severity_map.get(
                alert.get("severity", "medium"), ErrorSeverity.MEDIUM
            )

            self.alert_manager.send_alert(
                severity,
                "Disk Space Alert",
                alert["message"],
                {"path": alert.get("path"), "used_percent": alert.get("used_percent")},
            )

        # Perform cleanup if critical threshold is reached
        if disk_status["overall_status"] == "critical":
            self.logger.warning("Critical disk space detected, performing cleanup")

            cleanup_results = self.disk_monitor.cleanup_disk_space()
            results["cleanup_performed"] = True
            results["cleanup_results"] = cleanup_results

            if cleanup_results["success"]:
                self.alert_manager.send_alert(
                    ErrorSeverity.MEDIUM,
                    "Disk Cleanup Completed",
                    f"Freed {cleanup_results['space_freed_gb']:.2f} GB of disk space",
                    cleanup_results,
                )
            else:
                self.alert_manager.send_alert(
                    ErrorSeverity.HIGH,
                    "Disk Cleanup Failed",
                    "Automatic disk cleanup failed - manual intervention required",
                    cleanup_results,
                )

        return results

    def handle_container_restart(self, reason: str) -> RecoveryResult:
        """
        Handle container restart scenario.

        Args:
            reason: Reason for restart

        Returns:
            RecoveryResult with restart handling outcome
        """
        start_time = time.time()
        self.recovery_stats["container_restarts"] += 1

        self.logger.info(f"Handling container restart: {reason}")

        try:
            # Save current state
            state_data = {
                "restart_timestamp": datetime.now().isoformat() + "Z",
                "restart_reason": reason,
                "queue_size": self.local_queue.get_queue_size(),
                "recovery_stats": self.recovery_stats.copy(),
            }

            # Persist state to file
            state_file = "/tmp/container_restart_state.json"
            with open(state_file, "w") as f:
                json.dump(state_data, f, indent=2)

            # Send alert
            self.alert_manager.send_alert(
                ErrorSeverity.HIGH,
                "Container Restart",
                f"Container restarting due to: {reason}",
                state_data,
            )

            return RecoveryResult(
                success=True,
                action_taken=RecoveryAction.RESTART,
                message=f"Container restart handled successfully: {reason}",
                retry_count=0,
                duration_seconds=time.time() - start_time,
                metadata=state_data,
            )

        except Exception as e:
            self.logger.error(f"Error handling container restart: {e}")

            return RecoveryResult(
                success=False,
                action_taken=RecoveryAction.RESTART,
                message=f"Failed to handle container restart: {e}",
                retry_count=0,
                duration_seconds=time.time() - start_time,
                metadata={"error": str(e)},
            )

    def get_recovery_status(self) -> dict[str, Any]:
        """
        Get current recovery system status.

        Returns:
            Dictionary with recovery system status
        """
        return {
            "timestamp": datetime.now().isoformat() + "Z",
            "recovery_stats": self.recovery_stats.copy(),
            "local_queue": {
                "size": self.local_queue.get_queue_size(),
                "is_full": self.local_queue.is_full(),
                "max_size": self.local_queue.max_size,
            },
            "disk_status": self.disk_monitor.check_disk_space(),
            "alert_history_count": len(self.alert_manager.alert_history),
            "database_managers": list(self.database_managers.keys()),
        }

    def _determine_error_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity based on error type and message."""
        error_message = str(error).lower()

        # Critical errors
        if any(
            keyword in error_message
            for keyword in [
                "out of memory",
                "disk full",
                "no space left",
                "connection refused",
            ]
        ):
            return ErrorSeverity.CRITICAL

        # High severity errors
        if any(
            keyword in error_message
            for keyword in ["timeout", "connection lost", "authentication failed"]
        ):
            return ErrorSeverity.HIGH

        # Medium severity errors
        if any(
            keyword in error_message
            for keyword in ["temporary failure", "retry", "network error"]
        ):
            return ErrorSeverity.MEDIUM

        # Default to medium severity
        return ErrorSeverity.MEDIUM

    def _can_queue_operation(self, operation: str) -> bool:
        """Check if an operation can be queued locally."""
        # Define operations that can be safely queued
        queueable_operations = [
            "database_insert",
            "database_update",
            "log_entry",
            "metric_update",
            "status_update",
        ]

        return any(op in operation for op in queueable_operations)


# Default alert handlers


def log_alert_handler(alert_data: dict[str, Any]):
    """Default alert handler that logs alerts."""
    logger = logging.getLogger("alert_handler")

    severity = alert_data.get("severity", "medium")
    title = alert_data.get("title", "Alert")
    message = alert_data.get("message", "No message")

    log_level = {
        "low": logging.INFO,
        "medium": logging.WARNING,
        "high": logging.ERROR,
        "critical": logging.CRITICAL,
    }.get(severity, logging.WARNING)

    logger.log(log_level, f"ALERT [{severity.upper()}] {title}: {message}")


def file_alert_handler(alert_data: dict[str, Any]):
    """Alert handler that writes alerts to a file."""
    alert_file = "/app/logs/alerts.json"

    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(alert_file), exist_ok=True)

        # Append alert to file
        with open(alert_file, "a") as f:
            f.write(json.dumps(alert_data) + "\n")

    except Exception as e:
        logging.error(f"Failed to write alert to file: {e}")
