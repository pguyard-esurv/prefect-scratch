"""
Container Lifecycle Management System

This module provides comprehensive container lifecycle management including:
- Container startup validation and dependency checking
- Graceful shutdown handling with proper cleanup
- Container restart policies and failure recovery automation
- Container health monitoring and automatic remediation
- Lifecycle event logging and metrics
"""

import json
import logging
import os
import signal
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

import psutil

from core.container_config import ContainerConfigManager
from core.health_monitor import HealthMonitor
from core.service_orchestrator import ServiceOrchestrator


class ContainerState(Enum):
    """Container lifecycle states"""

    INITIALIZING = "initializing"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"
    RESTARTING = "restarting"


class RestartPolicy(Enum):
    """Container restart policies"""

    NO = "no"
    ALWAYS = "always"
    ON_FAILURE = "on-failure"
    UNLESS_STOPPED = "unless-stopped"


class LifecycleEvent(Enum):
    """Container lifecycle events"""

    STARTUP_INITIATED = "startup_initiated"
    DEPENDENCIES_READY = "dependencies_ready"
    STARTUP_COMPLETED = "startup_completed"
    HEALTH_CHECK_PASSED = "health_check_passed"
    HEALTH_CHECK_FAILED = "health_check_failed"
    SHUTDOWN_INITIATED = "shutdown_initiated"
    SHUTDOWN_COMPLETED = "shutdown_completed"
    RESTART_INITIATED = "restart_initiated"
    FAILURE_DETECTED = "failure_detected"
    RECOVERY_COMPLETED = "recovery_completed"


@dataclass
class StartupValidationResult:
    """Result of startup validation checks"""

    success: bool
    checks_passed: list[str] = field(default_factory=list)
    checks_failed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyCheck:
    """Configuration for dependency checking"""

    name: str
    check_function: Callable[[], bool]
    timeout_seconds: int = 60
    retry_interval: int = 2
    required: bool = True
    description: str = ""


@dataclass
class RestartConfig:
    """Configuration for container restart policies"""

    policy: RestartPolicy = RestartPolicy.ON_FAILURE
    max_restart_attempts: int = 5
    restart_delay_seconds: int = 10
    exponential_backoff: bool = True
    max_delay_seconds: int = 300
    restart_window_minutes: int = 60


@dataclass
class LifecycleEventRecord:
    """Record of a lifecycle event"""

    event: LifecycleEvent
    timestamp: datetime
    container_id: str
    flow_name: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None


@dataclass
class ContainerMetrics:
    """Container lifecycle metrics"""

    startup_count: int = 0
    successful_startups: int = 0
    failed_startups: int = 0
    restart_count: int = 0
    graceful_shutdowns: int = 0
    forced_shutdowns: int = 0
    health_check_failures: int = 0
    total_uptime_seconds: float = 0.0
    last_startup_time: Optional[datetime] = None
    last_shutdown_time: Optional[datetime] = None


class ContainerLifecycleManager:
    """
    Comprehensive container lifecycle management system.

    Manages the complete lifecycle of containers including startup validation,
    dependency checking, health monitoring, graceful shutdown, and restart policies.
    """

    def __init__(
        self,
        container_id: str,
        flow_name: str,
        config_manager: Optional[ContainerConfigManager] = None,
        restart_config: Optional[RestartConfig] = None,
    ):
        """
        Initialize container lifecycle manager.

        Args:
            container_id: Unique identifier for this container instance
            flow_name: Name of the flow this container runs
            config_manager: Configuration manager instance
            restart_config: Restart policy configuration
        """
        self.container_id = container_id
        self.flow_name = flow_name
        self.config_manager = config_manager or ContainerConfigManager(flow_name)
        self.restart_config = restart_config or RestartConfig()

        # Initialize state
        self.state = ContainerState.INITIALIZING
        self.startup_time: Optional[datetime] = None
        self.shutdown_requested = False
        self.restart_count = 0
        self.last_restart_time: Optional[datetime] = None

        # Initialize components
        self.service_orchestrator = ServiceOrchestrator(self.config_manager, flow_name)
        self.health_monitor: Optional[HealthMonitor] = None

        # Event tracking
        self.event_history: list[LifecycleEventRecord] = []
        self.metrics = ContainerMetrics()

        # Dependency checks
        self.dependency_checks: list[DependencyCheck] = []

        # Cleanup handlers
        self.cleanup_handlers: list[Callable[[], None]] = []

        # Health monitoring
        self.health_check_interval = 30  # seconds
        self.health_check_failures = 0
        self.max_health_check_failures = 3

        # Setup logging
        self.logger = self._setup_logging()

        # Setup signal handlers
        self._setup_signal_handlers()

        self.logger.info(
            f"Container lifecycle manager initialized for {flow_name} "
            f"(container_id: {container_id})"
        )

    def _setup_logging(self) -> logging.Logger:
        """Setup structured logging for lifecycle events"""
        logger = logging.getLogger(f"lifecycle_manager_{self.flow_name}")

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"component": "lifecycle_manager", "container_id": "'
                + self.container_id
                + '", '
                '"flow": "' + self.flow_name + '", "message": "%(message)s"}'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        return logger

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            self.shutdown_requested = True

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def add_dependency_check(self, check: DependencyCheck):
        """Add a dependency check to be performed during startup"""
        self.dependency_checks.append(check)
        self.logger.debug(f"Added dependency check: {check.name}")

    def add_cleanup_handler(self, handler: Callable[[], None]):
        """Add a cleanup handler to be called during shutdown"""
        self.cleanup_handlers.append(handler)
        self.logger.debug("Added cleanup handler")

    def _record_event(
        self,
        event: LifecycleEvent,
        details: Optional[dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
    ):
        """Record a lifecycle event"""
        event_record = LifecycleEventRecord(
            event=event,
            timestamp=datetime.now(),
            container_id=self.container_id,
            flow_name=self.flow_name,
            details=details or {},
            duration_ms=duration_ms,
        )

        self.event_history.append(event_record)

        # Log the event
        self.logger.info(
            f"Lifecycle event: {event.value}",
            extra={
                "event": event.value,
                "details": details,
                "duration_ms": duration_ms,
            },
        )

    def validate_startup_environment(self) -> StartupValidationResult:
        """
        Validate container startup environment and configuration.

        Returns:
            StartupValidationResult with validation details
        """
        start_time = time.time()
        result = StartupValidationResult(success=True)

        self.logger.info("Starting startup environment validation")

        try:
            # Check 1: Required environment variables
            required_env_vars = [
                "CONTAINER_FLOW_NAME",
                "CONTAINER_ENVIRONMENT",
                "CONTAINER_RPA_DB_CONNECTION_STRING",
            ]

            missing_vars = []
            for var in required_env_vars:
                if not os.getenv(var):
                    missing_vars.append(var)

            if missing_vars:
                result.checks_failed.append(
                    f"Missing environment variables: {missing_vars}"
                )
                result.success = False
            else:
                result.checks_passed.append("Environment variables validation")

            # Check 2: Flow name consistency
            env_flow_name = os.getenv("CONTAINER_FLOW_NAME")
            if env_flow_name != self.flow_name:
                result.checks_failed.append(
                    f"Flow name mismatch: expected {self.flow_name}, got {env_flow_name}"
                )
                result.success = False
            else:
                result.checks_passed.append("Flow name consistency")

            # Check 3: Configuration loading
            try:
                self.config_manager.load_container_config()
                result.checks_passed.append("Configuration loading")
                result.details["config_loaded"] = True
            except Exception as e:
                result.checks_failed.append(f"Configuration loading failed: {e}")
                result.success = False

            # Check 4: Required directories
            required_dirs = ["/app/logs", "/app/data", "/app/output"]
            for dir_path in required_dirs:
                if not os.path.exists(dir_path):
                    try:
                        os.makedirs(dir_path, exist_ok=True)
                        result.warnings.append(f"Created missing directory: {dir_path}")
                    except Exception as e:
                        result.checks_failed.append(
                            f"Cannot create directory {dir_path}: {e}"
                        )
                        result.success = False
                else:
                    result.checks_passed.append(f"Directory exists: {dir_path}")

            # Check 5: Resource limits
            try:
                memory_limit = os.getenv("CONTAINER_MAX_MEMORY_MB")
                cpu_limit = os.getenv("CONTAINER_MAX_CPU_PERCENT")

                if memory_limit:
                    result.details["memory_limit_mb"] = int(memory_limit)
                if cpu_limit:
                    result.details["cpu_limit_percent"] = int(cpu_limit)

                result.checks_passed.append("Resource limits configuration")
            except Exception as e:
                result.warnings.append(f"Resource limits validation warning: {e}")

            # Check 6: Disk space
            try:
                disk_usage = psutil.disk_usage("/")
                free_space_gb = disk_usage.free / (1024**3)

                if free_space_gb < 1.0:  # Less than 1GB free
                    result.checks_failed.append(
                        f"Insufficient disk space: {free_space_gb:.2f}GB free"
                    )
                    result.success = False
                elif free_space_gb < 5.0:  # Less than 5GB free
                    result.warnings.append(
                        f"Low disk space: {free_space_gb:.2f}GB free"
                    )

                result.details["free_disk_space_gb"] = free_space_gb
                result.checks_passed.append("Disk space validation")
            except Exception as e:
                result.warnings.append(f"Disk space check warning: {e}")

        except Exception as e:
            result.checks_failed.append(f"Validation error: {e}")
            result.success = False

        result.duration_seconds = time.time() - start_time

        self.logger.info(
            f"Startup validation completed: {'SUCCESS' if result.success else 'FAILED'} "
            f"({result.duration_seconds:.2f}s)"
        )

        return result

    def check_dependencies(self) -> bool:
        """
        Check all configured dependencies.

        Returns:
            True if all required dependencies are available
        """
        self.logger.info(f"Checking {len(self.dependency_checks)} dependencies")

        # Add default dependency checks if none configured
        if not self.dependency_checks:
            self._add_default_dependency_checks()

        failed_required_deps = []
        failed_optional_deps = []

        for dep_check in self.dependency_checks:
            self.logger.info(f"Checking dependency: {dep_check.name}")

            success = self._check_single_dependency(dep_check)

            if success:
                self.logger.info(f"Dependency check passed: {dep_check.name}")
            else:
                if dep_check.required:
                    failed_required_deps.append(dep_check.name)
                    self.logger.error(
                        f"Required dependency check failed: {dep_check.name}"
                    )
                else:
                    failed_optional_deps.append(dep_check.name)
                    self.logger.warning(
                        f"Optional dependency check failed: {dep_check.name}"
                    )

        if failed_optional_deps:
            self.logger.warning(f"Optional dependencies failed: {failed_optional_deps}")

        if failed_required_deps:
            self.logger.error(f"Required dependencies failed: {failed_required_deps}")
            return False

        self.logger.info("All required dependencies are available")
        return True

    def _add_default_dependency_checks(self):
        """Add default dependency checks"""
        # Database dependency
        self.add_dependency_check(
            DependencyCheck(
                name="database",
                check_function=lambda: self.service_orchestrator.wait_for_database(
                    "rpa_db", timeout=120
                ),
                timeout_seconds=120,
                required=True,
                description="RPA database connectivity",
            )
        )

        # Prefect server dependency
        self.add_dependency_check(
            DependencyCheck(
                name="prefect_server",
                check_function=lambda: self.service_orchestrator.wait_for_prefect_server(
                    timeout=60
                ),
                timeout_seconds=60,
                required=False,  # Optional for some flows
                description="Prefect server connectivity",
            )
        )

    def _check_single_dependency(self, dep_check: DependencyCheck) -> bool:
        """Check a single dependency with timeout and retry logic"""
        start_time = time.time()

        while time.time() - start_time < dep_check.timeout_seconds:
            try:
                if dep_check.check_function():
                    return True
            except Exception as e:
                self.logger.debug(f"Dependency check {dep_check.name} failed: {e}")

            if time.time() - start_time < dep_check.timeout_seconds:
                time.sleep(dep_check.retry_interval)

        return False

    def initialize_health_monitoring(self) -> bool:
        """
        Initialize health monitoring system.

        Returns:
            True if initialization successful
        """
        self.logger.info("Initializing health monitoring")

        try:
            # Get database managers from service orchestrator
            database_managers = getattr(
                self.service_orchestrator, "_database_managers", {}
            )

            self.health_monitor = HealthMonitor(
                database_managers=database_managers,
                enable_prometheus=True,
                enable_structured_logging=True,
            )

            # Perform initial health check
            health_report = self.health_monitor.comprehensive_health_check()

            self.logger.info(
                f"Health monitoring initialized. Initial status: {health_report['overall_status']}"
            )

            return True

        except Exception as e:
            self.logger.error(f"Health monitoring initialization failed: {e}")
            return False

    def startup(self) -> bool:
        """
        Perform complete container startup process.

        Returns:
            True if startup successful, False otherwise
        """
        startup_start_time = time.time()
        self.startup_time = datetime.now()
        self.state = ContainerState.STARTING

        self._record_event(LifecycleEvent.STARTUP_INITIATED)
        self.metrics.startup_count += 1

        self.logger.info("Starting container startup process")

        try:
            # Step 1: Validate startup environment
            validation_result = self.validate_startup_environment()
            if not validation_result.success:
                self.logger.error("Startup environment validation failed")
                self.state = ContainerState.FAILED
                self.metrics.failed_startups += 1
                return False

            # Step 2: Check dependencies
            if not self.check_dependencies():
                self.logger.error("Dependency checks failed")
                self.state = ContainerState.FAILED
                self.metrics.failed_startups += 1
                return False

            self._record_event(LifecycleEvent.DEPENDENCIES_READY)

            # Step 3: Initialize health monitoring
            if not self.initialize_health_monitoring():
                self.logger.error("Health monitoring initialization failed")
                self.state = ContainerState.FAILED
                self.metrics.failed_startups += 1
                return False

            # Step 4: Perform initial health check
            if self.health_monitor:
                health_report = self.health_monitor.comprehensive_health_check()
                if health_report["overall_status"] == "unhealthy":
                    self.logger.error("Initial health check failed")
                    self.state = ContainerState.FAILED
                    self.metrics.failed_startups += 1
                    return False

                self._record_event(LifecycleEvent.HEALTH_CHECK_PASSED)

            # Startup completed successfully
            self.state = ContainerState.RUNNING
            startup_duration = time.time() - startup_start_time

            self._record_event(
                LifecycleEvent.STARTUP_COMPLETED,
                details={"duration_seconds": startup_duration},
                duration_ms=startup_duration * 1000,
            )

            self.metrics.successful_startups += 1
            self.metrics.last_startup_time = self.startup_time

            self.logger.info(
                f"Container startup completed successfully ({startup_duration:.2f}s)"
            )
            return True

        except Exception as e:
            self.logger.error(f"Container startup failed: {e}")
            self.state = ContainerState.FAILED
            self.metrics.failed_startups += 1

            self._record_event(
                LifecycleEvent.FAILURE_DETECTED,
                details={"error": str(e), "phase": "startup"},
            )

            return False

    def run_health_monitoring_loop(self):
        """Run continuous health monitoring loop"""
        self.logger.info("Starting health monitoring loop")

        last_health_check = 0

        while not self.shutdown_requested and self.state == ContainerState.RUNNING:
            try:
                current_time = time.time()

                # Perform health check
                if current_time - last_health_check >= self.health_check_interval:
                    if self.health_monitor:
                        health_report = self.health_monitor.comprehensive_health_check()

                        if health_report["overall_status"] == "healthy":
                            self.health_check_failures = 0
                            self._record_event(LifecycleEvent.HEALTH_CHECK_PASSED)
                        else:
                            self.health_check_failures += 1
                            self._record_event(
                                LifecycleEvent.HEALTH_CHECK_FAILED,
                                details={
                                    "status": health_report["overall_status"],
                                    "failure_count": self.health_check_failures,
                                },
                            )

                            self.logger.warning(
                                f"Health check failed ({self.health_check_failures}/"
                                f"{self.max_health_check_failures}): {health_report['overall_status']}"
                            )

                            # Trigger remediation if too many failures
                            if (
                                self.health_check_failures
                                >= self.max_health_check_failures
                            ):
                                self._trigger_health_remediation(health_report)

                    last_health_check = current_time

                # Sleep for a short interval
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(5)

    def _trigger_health_remediation(self, health_report: dict[str, Any]):
        """Trigger automatic health remediation"""
        self.logger.warning("Triggering health remediation due to repeated failures")

        try:
            # Analyze health report to determine remediation actions
            remediation_actions = []

            # Check for database issues
            for check_name, check_result in health_report.get("checks", {}).items():
                if (
                    check_name.startswith("database_")
                    and check_result["status"] != "healthy"
                ):
                    remediation_actions.append(
                        f"restart_database_connection_{check_name}"
                    )

            # Check for resource issues
            resource_status = health_report.get("resource_status", {})
            if resource_status.get("memory_usage_percent", 0) > 90:
                remediation_actions.append("memory_cleanup")

            if resource_status.get("disk_usage_percent", 0) > 90:
                remediation_actions.append("disk_cleanup")

            # Execute remediation actions
            for action in remediation_actions:
                self._execute_remediation_action(action)

            # Reset failure count after remediation attempt
            self.health_check_failures = 0

            self._record_event(
                LifecycleEvent.RECOVERY_COMPLETED,
                details={"actions": remediation_actions},
            )

        except Exception as e:
            self.logger.error(f"Health remediation failed: {e}")

    def _execute_remediation_action(self, action: str):
        """Execute a specific remediation action"""
        self.logger.info(f"Executing remediation action: {action}")

        try:
            if action.startswith("restart_database_connection_"):
                # Restart database connections
                if hasattr(self.service_orchestrator, "_database_managers"):
                    for (
                        db_name,
                        db_manager,
                    ) in self.service_orchestrator._database_managers.items():
                        try:
                            # Force reconnection by clearing connection pool
                            if hasattr(db_manager, "close_connections"):
                                db_manager.close_connections()
                            self.logger.info(
                                f"Restarted database connection: {db_name}"
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Failed to restart database connection {db_name}: {e}"
                            )

            elif action == "memory_cleanup":
                # Trigger garbage collection and memory cleanup
                import gc

                gc.collect()
                self.logger.info("Performed memory cleanup")

            elif action == "disk_cleanup":
                # Clean up temporary files

                temp_dirs = ["/tmp", "/app/logs", "/app/output"]
                for temp_dir in temp_dirs:
                    if os.path.exists(temp_dir):
                        # Clean old files (older than 1 hour)
                        cutoff_time = time.time() - 3600
                        for root, _dirs, files in os.walk(temp_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    if os.path.getmtime(file_path) < cutoff_time:
                                        os.remove(file_path)
                                except Exception:
                                    pass  # Ignore cleanup errors

                self.logger.info("Performed disk cleanup")

        except Exception as e:
            self.logger.error(f"Remediation action {action} failed: {e}")

    def graceful_shutdown(self, timeout_seconds: int = 30) -> bool:
        """
        Perform graceful shutdown with proper cleanup.

        Args:
            timeout_seconds: Maximum time to wait for graceful shutdown

        Returns:
            True if shutdown completed gracefully, False if forced
        """
        shutdown_start_time = time.time()
        self.state = ContainerState.STOPPING

        self._record_event(LifecycleEvent.SHUTDOWN_INITIATED)

        self.logger.info(f"Starting graceful shutdown (timeout: {timeout_seconds}s)")

        try:
            # Step 1: Stop accepting new work
            self.shutdown_requested = True

            # Step 2: Execute cleanup handlers
            for i, handler in enumerate(self.cleanup_handlers):
                try:
                    self.logger.debug(
                        f"Executing cleanup handler {i+1}/{len(self.cleanup_handlers)}"
                    )
                    handler()
                except Exception as e:
                    self.logger.error(f"Cleanup handler {i+1} failed: {e}")

            # Step 3: Final health check and metrics
            if self.health_monitor:
                try:
                    final_health = self.health_monitor.comprehensive_health_check()
                    self.logger.info(
                        f"Final health status: {final_health['overall_status']}"
                    )
                except Exception as e:
                    self.logger.warning(f"Final health check failed: {e}")

            # Step 4: Update metrics
            shutdown_duration = time.time() - shutdown_start_time
            if self.startup_time:
                uptime = (datetime.now() - self.startup_time).total_seconds()
                self.metrics.total_uptime_seconds += uptime

            self.metrics.last_shutdown_time = datetime.now()

            # Check if shutdown completed within timeout
            if shutdown_duration <= timeout_seconds:
                self.state = ContainerState.STOPPED
                self.metrics.graceful_shutdowns += 1

                self._record_event(
                    LifecycleEvent.SHUTDOWN_COMPLETED,
                    details={"duration_seconds": shutdown_duration, "graceful": True},
                    duration_ms=shutdown_duration * 1000,
                )

                self.logger.info(
                    f"Graceful shutdown completed ({shutdown_duration:.2f}s)"
                )
                return True
            else:
                self.state = ContainerState.STOPPED
                self.metrics.forced_shutdowns += 1

                self._record_event(
                    LifecycleEvent.SHUTDOWN_COMPLETED,
                    details={"duration_seconds": shutdown_duration, "graceful": False},
                    duration_ms=shutdown_duration * 1000,
                )

                self.logger.warning(
                    f"Shutdown timeout exceeded ({shutdown_duration:.2f}s)"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")
            self.state = ContainerState.STOPPED
            self.metrics.forced_shutdowns += 1
            return False

    def should_restart(self) -> bool:
        """
        Determine if container should be restarted based on restart policy.

        Returns:
            True if container should be restarted
        """
        if self.restart_config.policy == RestartPolicy.NO:
            return False

        if self.restart_config.policy == RestartPolicy.ALWAYS:
            return True

        if self.restart_config.policy == RestartPolicy.UNLESS_STOPPED:
            return self.state != ContainerState.STOPPED

        if self.restart_config.policy == RestartPolicy.ON_FAILURE:
            return self.state == ContainerState.FAILED

        return False

    def calculate_restart_delay(self) -> int:
        """Calculate delay before restart based on configuration"""
        base_delay = self.restart_config.restart_delay_seconds

        if not self.restart_config.exponential_backoff:
            return base_delay

        # Exponential backoff: delay = base_delay * (2 ^ restart_count)
        delay = base_delay * (2 ** min(self.restart_count, 5))  # Cap at 2^5 = 32x

        return min(delay, self.restart_config.max_delay_seconds)

    def attempt_restart(self) -> bool:
        """
        Attempt to restart the container.

        Returns:
            True if restart was successful
        """
        if self.restart_count >= self.restart_config.max_restart_attempts:
            self.logger.error(
                f"Maximum restart attempts ({self.restart_config.max_restart_attempts}) exceeded"
            )
            return False

        # Check restart window
        if self.last_restart_time:
            time_since_last_restart = datetime.now() - self.last_restart_time
            if time_since_last_restart.total_seconds() < (
                self.restart_config.restart_window_minutes * 60
            ):
                self.restart_count += 1
            else:
                # Reset restart count if outside window
                self.restart_count = 1
        else:
            self.restart_count = 1

        self.last_restart_time = datetime.now()

        self._record_event(
            LifecycleEvent.RESTART_INITIATED, details={"attempt": self.restart_count}
        )

        self.logger.info(f"Attempting restart (attempt {self.restart_count})")

        # Calculate and apply restart delay
        delay = self.calculate_restart_delay()
        if delay > 0:
            self.logger.info(f"Waiting {delay}s before restart")
            time.sleep(delay)

        # Reset state and attempt startup
        self.state = ContainerState.RESTARTING
        self.health_check_failures = 0

        return self.startup()

    def get_lifecycle_metrics(self) -> dict[str, Any]:
        """Get comprehensive lifecycle metrics"""
        current_uptime = 0.0
        if self.startup_time and self.state == ContainerState.RUNNING:
            current_uptime = (datetime.now() - self.startup_time).total_seconds()

        return {
            "container_id": self.container_id,
            "flow_name": self.flow_name,
            "current_state": self.state.value,
            "metrics": asdict(self.metrics),
            "current_uptime_seconds": current_uptime,
            "restart_count": self.restart_count,
            "health_check_failures": self.health_check_failures,
            "event_count": len(self.event_history),
            "last_events": [
                {
                    "event": event.event.value,
                    "timestamp": event.timestamp.isoformat(),
                    "details": event.details,
                }
                for event in self.event_history[-10:]  # Last 10 events
            ],
        }

    def export_lifecycle_report(
        self, file_path: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Export comprehensive lifecycle report.

        Args:
            file_path: Optional file path to save report

        Returns:
            Complete lifecycle report
        """
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "container_info": {
                "container_id": self.container_id,
                "flow_name": self.flow_name,
                "current_state": self.state.value,
                "startup_time": (
                    self.startup_time.isoformat() if self.startup_time else None
                ),
            },
            "metrics": self.get_lifecycle_metrics(),
            "restart_config": {
                **asdict(self.restart_config),
                "policy": self.restart_config.policy.value,
            },
            "event_history": [
                {
                    "event": event.event.value,
                    "timestamp": event.timestamp.isoformat(),
                    "details": event.details,
                    "duration_ms": event.duration_ms,
                }
                for event in self.event_history
            ],
            "dependency_checks": [
                {
                    "name": check.name,
                    "required": check.required,
                    "timeout_seconds": check.timeout_seconds,
                    "description": check.description,
                }
                for check in self.dependency_checks
            ],
        }

        if file_path:
            try:
                with open(file_path, "w") as f:
                    json.dump(report, f, indent=2)
                self.logger.info(f"Lifecycle report exported to {file_path}")
            except Exception as e:
                self.logger.error(f"Failed to export lifecycle report: {e}")

        return report
