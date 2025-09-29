"""
Service orchestration and dependency management for container environments.

This module provides the ServiceOrchestrator class that manages service startup
dependencies, database connection waiting with exponential backoff retry logic,
Prefect server health checks, and comprehensive service health monitoring.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Optional

import httpx
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.container_config import ContainerConfigManager, ServiceDependency
from core.database import DatabaseManager


@dataclass
class HealthStatus:
    """Health status information for services."""

    status: Literal["healthy", "degraded", "unhealthy"]
    message: str
    details: dict[str, Any]
    timestamp: datetime
    check_duration: float


@dataclass
class ServiceHealthStatus:
    """Comprehensive service health status."""

    overall_status: Literal["healthy", "degraded", "unhealthy"]
    services: dict[str, HealthStatus]
    databases: dict[str, HealthStatus]
    timestamp: datetime
    total_check_duration: float


class ServiceOrchestrator:
    """
    Manages service startup, dependencies, and health monitoring for containers.

    Provides comprehensive service orchestration including:
    - Database connection waiting with exponential backoff
    - Prefect server health checks and connection validation
    - Service dependency management with retry logic
    - Detailed health monitoring and status reporting
    """

    def __init__(
        self,
        config_manager: Optional[ContainerConfigManager] = None,
        flow_name: Optional[str] = None,
        environment: Optional[str] = None,
        cache_ttl: int = 30,
    ):
        """
        Initialize the service orchestrator.

        Args:
            config_manager: Container configuration manager instance
            flow_name: Name of the flow for configuration context
            environment: Environment name for configuration context
            cache_ttl: Cache TTL in seconds for health check results (default: 30)
        """
        self.config_manager = config_manager or ContainerConfigManager(
            flow_name, environment
        )
        self.flow_name = flow_name or self.config_manager.flow_name
        self.environment = environment or self.config_manager.environment

        # Initialize logger
        self._logger = None
        self._initialize_logger()

        # Cache for database managers
        self._database_managers: dict[str, DatabaseManager] = {}

        # Service health cache
        self._health_cache: dict[str, HealthStatus] = {}
        self._cache_ttl = cache_ttl  # Cache TTL in seconds

    def _initialize_logger(self):
        """Initialize logger with Prefect integration and fallback."""
        if self._logger is not None:
            return

        try:
            # Try to use Prefect's get_run_logger for task context
            from prefect import get_run_logger

            self._logger = get_run_logger()
            self._logger.info("ServiceOrchestrator initialized with Prefect logger")
        except (ImportError, RuntimeError):
            # Fallback to standard Python logging
            self._logger = logging.getLogger(
                f"ServiceOrchestrator.{self.flow_name or 'global'}"
            )
            if not self._logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                handler.setFormatter(formatter)
                self._logger.addHandler(handler)
                self._logger.setLevel(logging.INFO)
            self._logger.info("ServiceOrchestrator initialized with standard logger")

    @property
    def logger(self):
        """Get the logger instance, initializing if necessary."""
        if self._logger is None:
            self._initialize_logger()
        return self._logger

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(
            (ConnectionError, TimeoutError, requests.RequestException)
        ),
    )
    def wait_for_database(self, database_name: str, timeout: int = 300) -> bool:
        """
        Wait for database to become available with exponential backoff retry logic.

        Args:
            database_name: Name of the database to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            True if database is available, False if timeout exceeded

        Raises:
            ValueError: If database configuration is invalid
            RuntimeError: If database connection fails after all retries
        """
        start_time = time.time()

        self.logger.info(
            f"Waiting for database '{database_name}' to become available (timeout: {timeout}s)"
        )

        try:
            # Load container configuration to get database details
            config = self.config_manager.load_container_config()
            databases = config.get("databases", {})

            if database_name not in databases:
                raise ValueError(
                    f"Database '{database_name}' not found in configuration"
                )

            databases[database_name]

            # Get or create database manager
            if database_name not in self._database_managers:
                self._database_managers[database_name] = DatabaseManager(database_name)

            db_manager = self._database_managers[database_name]

            # Perform health check with retry logic
            while time.time() - start_time < timeout:
                try:
                    health_result = db_manager.health_check()

                    if health_result["status"] == "healthy":
                        elapsed = time.time() - start_time
                        self.logger.info(
                            f"Database '{database_name}' is healthy after {elapsed:.2f}s"
                        )
                        return True
                    elif health_result["status"] == "degraded":
                        self.logger.warning(
                            f"Database '{database_name}' is degraded: {health_result.get('error', 'Unknown issue')}"
                        )
                        # Continue waiting for degraded status
                    else:
                        self.logger.warning(
                            f"Database '{database_name}' is unhealthy: {health_result.get('error', 'Unknown issue')}"
                        )

                except Exception as e:
                    self.logger.debug(f"Database health check failed: {e}")
                    # Exception will trigger retry via tenacity decorator

                # Wait before next attempt (if not using tenacity retry)
                if time.time() - start_time < timeout:
                    time.sleep(2)

            # Timeout exceeded
            elapsed = time.time() - start_time
            self.logger.error(
                f"Database '{database_name}' did not become available within {timeout}s (elapsed: {elapsed:.2f}s)"
            )
            return False

        except Exception as e:
            self.logger.error(f"Failed to wait for database '{database_name}': {e}")
            raise RuntimeError(f"Database wait failed: {e}") from e

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(
            (
                ConnectionError,
                TimeoutError,
                requests.RequestException,
                httpx.RequestError,
            )
        ),
    )
    def wait_for_prefect_server(self, timeout: int = 300) -> bool:
        """
        Wait for Prefect server to become available with health check validation.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if Prefect server is available, False if timeout exceeded

        Raises:
            ValueError: If Prefect server configuration is missing
            RuntimeError: If Prefect server connection fails after all retries
        """
        start_time = time.time()

        self.logger.info(
            f"Waiting for Prefect server to become available (timeout: {timeout}s)"
        )

        try:
            # Get Prefect server configuration
            prefect_url = self.config_manager.get_config("PREFECT_API_URL")
            if not prefect_url:
                # Try container-specific configuration
                prefect_url = self.config_manager._get_container_config(
                    "SERVICE_PREFECT_HEALTH_ENDPOINT"
                )

            if not prefect_url:
                raise ValueError(
                    "Prefect server URL not configured. Set CONTAINER_SERVICE_PREFECT_HEALTH_ENDPOINT or PREFECT_API_URL"
                )

            # Ensure URL has health endpoint
            if not prefect_url.endswith("/health"):
                if prefect_url.endswith("/"):
                    prefect_url = prefect_url + "health"
                else:
                    prefect_url = prefect_url + "/health"

            self.logger.debug(f"Checking Prefect server health at: {prefect_url}")

            # Perform health check with retry logic
            while time.time() - start_time < timeout:
                try:
                    # Use both requests and httpx for compatibility
                    response = requests.get(prefect_url, timeout=10)

                    if response.status_code == 200:
                        elapsed = time.time() - start_time
                        self.logger.info(
                            f"Prefect server is healthy after {elapsed:.2f}s"
                        )

                        # Additional validation - check response content
                        try:
                            health_data = response.json()
                            if (
                                isinstance(health_data, dict)
                                and health_data.get("status") == "ready"
                            ):
                                self.logger.debug(
                                    "Prefect server health check passed with 'ready' status"
                                )
                            else:
                                self.logger.debug(
                                    f"Prefect server health response: {health_data}"
                                )
                        except Exception:
                            # JSON parsing failed, but 200 status is sufficient
                            self.logger.debug(
                                "Prefect server returned 200 status (non-JSON response)"
                            )

                        return True
                    else:
                        self.logger.warning(
                            f"Prefect server health check failed with status {response.status_code}"
                        )

                except requests.RequestException as e:
                    self.logger.debug(f"Prefect server health check failed: {e}")
                    # Exception will trigger retry via tenacity decorator

                # Wait before next attempt (if not using tenacity retry)
                if time.time() - start_time < timeout:
                    time.sleep(2)

            # Timeout exceeded
            elapsed = time.time() - start_time
            self.logger.error(
                f"Prefect server did not become available within {timeout}s (elapsed: {elapsed:.2f}s)"
            )
            return False

        except Exception as e:
            self.logger.error(f"Failed to wait for Prefect server: {e}")
            raise RuntimeError(f"Prefect server wait failed: {e}") from e

    def validate_service_health(self) -> ServiceHealthStatus:
        """
        Validate health of all configured services and databases.

        Performs comprehensive health checks on:
        - All configured databases
        - All configured service dependencies
        - Prefect server (if configured)

        Returns:
            ServiceHealthStatus with detailed health information for all services
        """
        start_time = time.time()
        timestamp = datetime.now(timezone.utc)

        self.logger.info("Starting comprehensive service health validation")

        services_health = {}
        databases_health = {}

        try:
            # Load container configuration
            config = self.config_manager.load_container_config()

            # Check database health
            databases = config.get("databases", {})
            for db_name in databases:
                db_health = self._check_database_health(db_name)
                databases_health[db_name] = db_health

            # Check service dependencies health
            services = config.get("services", [])
            for service in services:
                service_health = self._check_service_health(service)
                services_health[service.service_name] = service_health

            # Check Prefect server health (if not already in services)
            prefect_in_services = any(s.service_name == "prefect" for s in services)
            if not prefect_in_services:
                try:
                    prefect_health = self._check_prefect_health()
                    services_health["prefect"] = prefect_health
                except Exception as e:
                    self.logger.warning(f"Prefect health check failed: {e}")
                    services_health["prefect"] = HealthStatus(
                        status="unhealthy",
                        message=f"Prefect health check failed: {e}",
                        details={"error": str(e)},
                        timestamp=timestamp,
                        check_duration=0.0,
                    )

            # Determine overall status
            overall_status = self._determine_overall_status(
                services_health, databases_health
            )

            total_duration = time.time() - start_time

            self.logger.info(
                f"Service health validation completed in {total_duration:.2f}s - "
                f"Overall status: {overall_status}"
            )

            return ServiceHealthStatus(
                overall_status=overall_status,
                services=services_health,
                databases=databases_health,
                timestamp=timestamp,
                total_check_duration=total_duration,
            )

        except Exception as e:
            self.logger.error(f"Service health validation failed: {e}")

            # Return unhealthy status with error details
            return ServiceHealthStatus(
                overall_status="unhealthy",
                services=services_health,
                databases=databases_health,
                timestamp=timestamp,
                total_check_duration=time.time() - start_time,
            )

    def _check_database_health(self, database_name: str) -> HealthStatus:
        """Check health of a specific database."""
        start_time = time.time()
        timestamp = datetime.now(timezone.utc)

        try:
            # Get or create database manager
            if database_name not in self._database_managers:
                self._database_managers[database_name] = DatabaseManager(database_name)

            db_manager = self._database_managers[database_name]
            health_result = db_manager.health_check()

            duration = time.time() - start_time

            return HealthStatus(
                status=health_result["status"],
                message=health_result.get("error")
                or f"Database {database_name} is {health_result['status']}",
                details={
                    "database_name": database_name,
                    "connection": health_result.get("connection", False),
                    "query_test": health_result.get("query_test", False),
                    "response_time_ms": health_result.get("response_time_ms"),
                    "migration_status": health_result.get("migration_status"),
                },
                timestamp=timestamp,
                check_duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Database health check failed for '{database_name}': {e}"
            )

            return HealthStatus(
                status="unhealthy",
                message=f"Database health check failed: {e}",
                details={"database_name": database_name, "error": str(e)},
                timestamp=timestamp,
                check_duration=duration,
            )

    def _check_service_health(self, service: ServiceDependency) -> HealthStatus:
        """Check health of a specific service dependency."""
        start_time = time.time()
        timestamp = datetime.now(timezone.utc)

        try:
            # Check cache first
            cache_key = f"service_{service.service_name}"
            if cache_key in self._health_cache:
                cached_health = self._health_cache[cache_key]
                cache_age = (timestamp - cached_health.timestamp).total_seconds()
                if cache_age < self._cache_ttl:
                    self.logger.debug(
                        f"Using cached health status for service '{service.service_name}'"
                    )
                    return cached_health

            # Perform health check
            response = requests.get(service.health_endpoint, timeout=service.timeout)

            duration = time.time() - start_time

            if response.status_code == 200:
                status = "healthy"
                message = f"Service {service.service_name} is healthy"
            elif 200 <= response.status_code < 300:
                status = "healthy"
                message = f"Service {service.service_name} is healthy (status: {response.status_code})"
            elif 400 <= response.status_code < 500:
                status = "degraded"
                message = f"Service {service.service_name} returned client error: {response.status_code}"
            else:
                status = "unhealthy"
                message = f"Service {service.service_name} returned server error: {response.status_code}"

            health_status = HealthStatus(
                status=status,
                message=message,
                details={
                    "service_name": service.service_name,
                    "endpoint": service.health_endpoint,
                    "status_code": response.status_code,
                    "response_time_ms": round(duration * 1000, 2),
                    "required": service.required,
                },
                timestamp=timestamp,
                check_duration=duration,
            )

            # Cache the result
            self._health_cache[cache_key] = health_status

            return health_status

        except requests.RequestException as e:
            duration = time.time() - start_time
            self.logger.warning(
                f"Service health check failed for '{service.service_name}': {e}"
            )

            health_status = HealthStatus(
                status="unhealthy",
                message=f"Service health check failed: {e}",
                details={
                    "service_name": service.service_name,
                    "endpoint": service.health_endpoint,
                    "error": str(e),
                    "required": service.required,
                },
                timestamp=timestamp,
                check_duration=duration,
            )

            # Cache the error result (with shorter TTL)
            cache_key = f"service_{service.service_name}"
            self._health_cache[cache_key] = health_status

            return health_status

    def _check_prefect_health(self) -> HealthStatus:
        """Check Prefect server health."""
        start_time = time.time()
        timestamp = datetime.now(timezone.utc)

        try:
            # Get Prefect server configuration
            prefect_url = self.config_manager.get_config("PREFECT_API_URL")
            if not prefect_url:
                prefect_url = self.config_manager._get_container_config(
                    "SERVICE_PREFECT_HEALTH_ENDPOINT"
                )

            if not prefect_url:
                raise ValueError("Prefect server URL not configured")

            # Ensure URL has health endpoint
            if not prefect_url.endswith("/health"):
                if prefect_url.endswith("/"):
                    prefect_url = prefect_url + "health"
                else:
                    prefect_url = prefect_url + "/health"

            response = requests.get(prefect_url, timeout=10)
            duration = time.time() - start_time

            if response.status_code == 200:
                # Try to parse JSON response for additional details
                try:
                    health_data = response.json()
                    details = {
                        "endpoint": prefect_url,
                        "status_code": response.status_code,
                        "response_time_ms": round(duration * 1000, 2),
                        "health_data": health_data,
                    }

                    if (
                        isinstance(health_data, dict)
                        and health_data.get("status") == "ready"
                    ):
                        status = "healthy"
                        message = "Prefect server is ready"
                    else:
                        status = "healthy"
                        message = "Prefect server is responding"

                except Exception:
                    # JSON parsing failed, but 200 status is sufficient
                    status = "healthy"
                    message = "Prefect server is responding"
                    details = {
                        "endpoint": prefect_url,
                        "status_code": response.status_code,
                        "response_time_ms": round(duration * 1000, 2),
                    }
            else:
                status = "unhealthy"
                message = f"Prefect server returned status {response.status_code}"
                details = {
                    "endpoint": prefect_url,
                    "status_code": response.status_code,
                    "response_time_ms": round(duration * 1000, 2),
                }

            return HealthStatus(
                status=status,
                message=message,
                details=details,
                timestamp=timestamp,
                check_duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            return HealthStatus(
                status="unhealthy",
                message=f"Prefect health check failed: {e}",
                details={"error": str(e)},
                timestamp=timestamp,
                check_duration=duration,
            )

    def _determine_overall_status(
        self,
        services_health: dict[str, HealthStatus],
        databases_health: dict[str, HealthStatus],
    ) -> Literal["healthy", "degraded", "unhealthy"]:
        """Determine overall health status based on individual service and database health."""

        has_degraded = False

        # Check for any unhealthy required services or databases
        for health in list(services_health.values()) + list(databases_health.values()):
            if health.status == "unhealthy":
                # Check if this is a required service (databases are always required)
                is_required = health.details.get("required", True)
                if is_required:
                    return "unhealthy"
            elif health.status == "degraded":
                has_degraded = True

        # If we have degraded services but no unhealthy required services, return degraded
        if has_degraded:
            return "degraded"

        # All services are healthy
        return "healthy"

    def handle_service_failure(self, service: str, error: Exception) -> None:
        """
        Handle service failure with appropriate recovery actions.

        Args:
            service: Name of the failed service
            error: Exception that caused the failure
        """
        self.logger.error(f"Service failure detected for '{service}': {error}")

        # Clear health cache for the failed service
        cache_key = f"service_{service}"
        if cache_key in self._health_cache:
            del self._health_cache[cache_key]

        # Log detailed error information
        self.logger.error(
            f"Service '{service}' failure details: "
            f"Error type: {type(error).__name__}, "
            f"Error message: {str(error)}"
        )

        # Additional recovery actions could be implemented here:
        # - Restart service containers
        # - Switch to backup services
        # - Alert monitoring systems
        # - Implement circuit breaker pattern

    def wait_for_all_dependencies(self, timeout: int = 300) -> bool:
        """
        Wait for all configured service dependencies to become available.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if all dependencies are available, False if timeout exceeded
        """
        start_time = time.time()
        self.logger.info(f"Waiting for all service dependencies (timeout: {timeout}s)")

        try:
            # Load container configuration
            config = self.config_manager.load_container_config()

            # Wait for databases
            databases = config.get("databases", {})
            for db_name in databases:
                remaining_time = timeout - (time.time() - start_time)
                if remaining_time <= 0:
                    self.logger.error("Timeout exceeded while waiting for dependencies")
                    return False

                if not self.wait_for_database(db_name, int(remaining_time)):
                    self.logger.error(f"Database '{db_name}' did not become available")
                    return False

            # Wait for Prefect server
            remaining_time = timeout - (time.time() - start_time)
            if remaining_time > 0:
                if not self.wait_for_prefect_server(int(remaining_time)):
                    self.logger.error("Prefect server did not become available")
                    return False

            # Wait for other service dependencies
            services = config.get("services", [])
            for service in services:
                if service.service_name == "prefect":
                    continue  # Already checked above

                remaining_time = timeout - (time.time() - start_time)
                if remaining_time <= 0:
                    self.logger.error(
                        "Timeout exceeded while waiting for service dependencies"
                    )
                    return False

                if not self._wait_for_service(service, int(remaining_time)):
                    if service.required:
                        self.logger.error(
                            f"Required service '{service.service_name}' did not become available"
                        )
                        return False
                    else:
                        self.logger.warning(
                            f"Optional service '{service.service_name}' is not available"
                        )

            elapsed = time.time() - start_time
            self.logger.info(f"All dependencies are available after {elapsed:.2f}s")
            return True

        except Exception as e:
            self.logger.error(f"Failed to wait for dependencies: {e}")
            return False

    def _wait_for_service(self, service: ServiceDependency, timeout: int) -> bool:
        """Wait for a specific service to become available."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    service.health_endpoint, timeout=service.timeout
                )
                if response.status_code == 200:
                    elapsed = time.time() - start_time
                    self.logger.info(
                        f"Service '{service.service_name}' is available after {elapsed:.2f}s"
                    )
                    return True
            except Exception as e:
                self.logger.debug(
                    f"Service '{service.service_name}' not yet available: {e}"
                )

            time.sleep(2)

        return False
