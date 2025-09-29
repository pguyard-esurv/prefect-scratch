"""
Container configuration management system.

This module provides the ContainerConfigManager class that extends the existing
ConfigManager to handle container-specific configuration requirements including
CONTAINER_ prefix environment variable mapping, service dependency validation,
and startup configuration validation with detailed error reporting.
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Optional

from core.config import ConfigManager


@dataclass
class DatabaseConfig:
    """Database connection configuration for containers."""

    name: str
    connection_string: str
    database_type: str
    connection_pool_size: int = 5
    connection_timeout: int = 30
    health_check_query: str = "SELECT 1"
    retry_config: Optional[dict[str, Any]] = None


@dataclass
class ServiceDependency:
    """Service dependency configuration for containers."""

    service_name: str
    health_endpoint: str
    timeout: int = 30
    retry_attempts: int = 3
    required: bool = True


@dataclass
class ValidationResult:
    """Result of configuration validation."""

    valid: bool
    errors: list[str]
    warnings: list[str]
    details: dict[str, Any]


@dataclass
class StartupReport:
    """Comprehensive startup validation report."""

    timestamp: datetime
    environment: str
    flow_name: Optional[str]
    validation_results: dict[str, ValidationResult]
    overall_status: Literal["success", "warning", "error"]
    startup_duration: float
    recommendations: list[str]


class ContainerConfigManager(ConfigManager):
    """
    Extended configuration manager for container environments.

    Provides container-specific configuration management including:
    - CONTAINER_ prefix environment variable mapping
    - Database connection validation
    - Service dependency management
    - Startup configuration validation with detailed error reporting
    """

    def __init__(
        self,
        flow_name: Optional[str] = None,
        environment: Optional[str] = None,
        container_id: Optional[str] = None,
    ):
        """
        Initialize the container configuration manager.

        Args:
            flow_name: Name of the flow (e.g., 'rpa1', 'rpa2', 'rpa3')
            environment: Environment name (e.g., 'development', 'staging', 'production')
            container_id: Unique container identifier for logging and tracking
        """
        super().__init__(flow_name, environment)
        self.container_id = container_id or os.getenv("HOSTNAME", "unknown")
        self._startup_time = time.time()
        self._validation_cache = {}

    def load_container_config(self) -> dict[str, Any]:
        """
        Load complete container configuration with CONTAINER_ prefix mapping.

        Maps environment variables with CONTAINER_ prefix to configuration sections:
        - CONTAINER_DATABASE_* -> database configuration
        - CONTAINER_SERVICE_* -> service dependency configuration
        - CONTAINER_MONITORING_* -> monitoring configuration
        - CONTAINER_SECURITY_* -> security configuration

        Returns:
            Dictionary containing complete container configuration
        """
        config = {
            "container_id": self.container_id,
            "environment": self.environment,
            "flow_name": self.flow_name,
            "databases": self._load_database_configs(),
            "services": self._load_service_dependencies(),
            "monitoring": self._load_monitoring_config(),
            "security": self._load_security_config(),
            "resources": self._load_resource_config(),
        }

        return config

    def _load_database_configs(self) -> dict[str, DatabaseConfig]:
        """Load database configurations from CONTAINER_DATABASE_* environment variables."""
        databases = {}

        # Get list of required databases
        required_databases = self._get_container_config(
            "DATABASE_REQUIRED", "rpa_db,SurveyHub"
        )
        if isinstance(required_databases, str):
            db_names = [
                db.strip() for db in required_databases.split(",") if db.strip()
            ]
        else:
            db_names = ["rpa_db", "SurveyHub"]

        for db_name in db_names:
            # Try CONTAINER_ prefix first, then fall back to standard config
            connection_string = self._get_container_config(
                f"DATABASE_{db_name.upper()}_CONNECTION_STRING"
            ) or self.get_secret(f"{db_name}_connection_string")

            db_type = self._get_container_config(
                f"DATABASE_{db_name.upper()}_TYPE"
            ) or self.get_variable(f"{db_name}_type")

            if connection_string and db_type:
                pool_size_str = self._get_container_config(
                    f"DATABASE_{db_name.upper()}_POOL_SIZE", "5"
                )
                timeout_str = self._get_container_config(
                    f"DATABASE_{db_name.upper()}_TIMEOUT", "30"
                )
                health_query = self._get_container_config(
                    f"DATABASE_{db_name.upper()}_HEALTH_QUERY", "SELECT 1"
                )

                databases[db_name] = DatabaseConfig(
                    name=db_name,
                    connection_string=connection_string,
                    database_type=db_type,
                    connection_pool_size=int(pool_size_str) if pool_size_str else 5,
                    connection_timeout=int(timeout_str) if timeout_str else 30,
                    health_check_query=health_query if health_query else "SELECT 1",
                )

        return databases

    def _load_service_dependencies(self) -> list[ServiceDependency]:
        """Load service dependency configurations from CONTAINER_SERVICE_* environment variables."""
        services = []

        # Get list of required services
        required_services = self._get_container_config("SERVICE_REQUIRED", "prefect")
        if isinstance(required_services, str):
            service_names = [
                svc.strip() for svc in required_services.split(",") if svc.strip()
            ]
        else:
            service_names = ["prefect"]

        for service_name in service_names:
            health_endpoint = self._get_container_config(
                f"SERVICE_{service_name.upper()}_HEALTH_ENDPOINT"
            )

            if health_endpoint:
                timeout_str = self._get_container_config(
                    f"SERVICE_{service_name.upper()}_TIMEOUT", "30"
                )
                retry_str = self._get_container_config(
                    f"SERVICE_{service_name.upper()}_RETRY_ATTEMPTS", "3"
                )
                required_str = self._get_container_config(
                    f"SERVICE_{service_name.upper()}_REQUIRED", "true"
                )

                services.append(
                    ServiceDependency(
                        service_name=service_name,
                        health_endpoint=health_endpoint,
                        timeout=int(timeout_str) if timeout_str else 30,
                        retry_attempts=int(retry_str) if retry_str else 3,
                        required=(required_str or "true").lower()
                        in ("true", "1", "yes"),
                    )
                )

        return services

    def _load_monitoring_config(self) -> dict[str, Any]:
        """Load monitoring configuration from CONTAINER_MONITORING_* environment variables."""
        health_enabled_str = self._get_container_config(
            "MONITORING_HEALTH_CHECK_ENABLED", "true"
        )
        health_interval_str = self._get_container_config(
            "MONITORING_HEALTH_CHECK_INTERVAL", "60"
        )
        metrics_enabled_str = self._get_container_config(
            "MONITORING_METRICS_ENABLED", "true"
        )
        metrics_port_str = self._get_container_config("MONITORING_METRICS_PORT", "8080")
        log_level_str = self._get_container_config("MONITORING_LOG_LEVEL", "INFO")
        structured_logging_str = self._get_container_config(
            "MONITORING_STRUCTURED_LOGGING", "true"
        )

        return {
            "health_check_enabled": (health_enabled_str or "true").lower()
            in ("true", "1", "yes"),
            "health_check_interval": int(health_interval_str)
            if health_interval_str
            else 60,
            "metrics_enabled": (metrics_enabled_str or "true").lower()
            in ("true", "1", "yes"),
            "metrics_port": int(metrics_port_str) if metrics_port_str else 8080,
            "log_level": log_level_str or "INFO",
            "structured_logging": (structured_logging_str or "true").lower()
            in ("true", "1", "yes"),
        }

    def _load_security_config(self) -> dict[str, Any]:
        """Load security configuration from CONTAINER_SECURITY_* environment variables."""
        run_as_non_root_str = self._get_container_config(
            "SECURITY_RUN_AS_NON_ROOT", "true"
        )
        user_id_str = self._get_container_config("SECURITY_USER_ID", "1000")
        group_id_str = self._get_container_config("SECURITY_GROUP_ID", "1000")
        read_only_str = self._get_container_config(
            "SECURITY_READ_ONLY_ROOT_FS", "false"
        )
        drop_caps_str = self._get_container_config("SECURITY_DROP_CAPABILITIES", "ALL")
        secrets_path_str = self._get_container_config(
            "SECURITY_SECRETS_MOUNT_PATH", "/var/secrets"
        )

        return {
            "run_as_non_root": (run_as_non_root_str or "true").lower()
            in ("true", "1", "yes"),
            "user_id": int(user_id_str) if user_id_str else 1000,
            "group_id": int(group_id_str) if group_id_str else 1000,
            "read_only_root_filesystem": (read_only_str or "false").lower()
            in ("true", "1", "yes"),
            "drop_capabilities": (drop_caps_str or "ALL").split(","),
            "secrets_mount_path": secrets_path_str or "/var/secrets",
        }

    def _load_resource_config(self) -> dict[str, Any]:
        """Load resource configuration from CONTAINER_RESOURCE_* environment variables."""
        cpu_limit = self._get_container_config("RESOURCE_CPU_LIMIT", "1.0")
        memory_limit = self._get_container_config("RESOURCE_MEMORY_LIMIT", "512Mi")
        cpu_request = self._get_container_config("RESOURCE_CPU_REQUEST", "0.1")
        memory_request = self._get_container_config("RESOURCE_MEMORY_REQUEST", "128Mi")
        disk_limit = self._get_container_config("RESOURCE_DISK_LIMIT", "1Gi")

        return {
            "cpu_limit": cpu_limit or "1.0",
            "memory_limit": memory_limit or "512Mi",
            "cpu_request": cpu_request or "0.1",
            "memory_request": memory_request or "128Mi",
            "disk_limit": disk_limit or "1Gi",
        }

    def _get_container_config(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with CONTAINER_ prefix mapping.

        Args:
            key: Configuration key (without CONTAINER_ prefix)
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        # Try CONTAINER_ prefixed environment variable first
        container_key = f"CONTAINER_{key}"
        value = os.getenv(container_key)

        if value is not None:
            return value

        # Fall back to standard configuration methods
        return self.get_config(key, default)

    def validate_container_environment(self) -> ValidationResult:
        """
        Validate container environment configuration.

        Performs comprehensive validation of:
        - Required environment variables
        - Database connection configurations
        - Service dependency configurations
        - Security settings
        - Resource limits

        Returns:
            ValidationResult with detailed validation information
        """
        errors = []
        warnings = []
        details = {}

        try:
            # Load container configuration
            config = self.load_container_config()
            details["config"] = config

            # Validate databases
            db_validation = self._validate_database_configs(config["databases"])
            if not db_validation.valid:
                errors.extend(db_validation.errors)
            warnings.extend(db_validation.warnings)
            details["database_validation"] = db_validation

            # Validate services
            service_validation = self._validate_service_dependencies(config["services"])
            if not service_validation.valid:
                errors.extend(service_validation.errors)
            warnings.extend(service_validation.warnings)
            details["service_validation"] = service_validation

            # Validate security settings
            security_validation = self._validate_security_config(config["security"])
            if not security_validation.valid:
                errors.extend(security_validation.errors)
            warnings.extend(security_validation.warnings)
            details["security_validation"] = security_validation

            # Validate resource settings
            resource_validation = self._validate_resource_config(config["resources"])
            if not resource_validation.valid:
                errors.extend(resource_validation.errors)
            warnings.extend(resource_validation.warnings)
            details["resource_validation"] = resource_validation

        except Exception as e:
            errors.append(f"Configuration loading failed: {str(e)}")

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_database_configs(
        self, databases: dict[str, DatabaseConfig]
    ) -> ValidationResult:
        """Validate database configurations."""
        errors = []
        warnings = []
        details = {}

        if not databases:
            errors.append("No database configurations found")
            return ValidationResult(False, errors, warnings, details)

        for db_name, db_config in databases.items():
            db_errors = []
            db_warnings = []

            # Validate connection string format
            if not db_config.connection_string:
                db_errors.append(f"Missing connection string for database '{db_name}'")
            elif not self._validate_connection_string_format(
                db_config.connection_string, db_config.database_type
            ):
                db_errors.append(
                    f"Invalid connection string format for database '{db_name}'"
                )

            # Validate database type
            if db_config.database_type not in ["postgresql", "sqlserver"]:
                db_errors.append(
                    f"Unsupported database type '{db_config.database_type}' for database '{db_name}'"
                )

            # Validate pool settings
            if (
                db_config.connection_pool_size <= 0
                or db_config.connection_pool_size > 50
            ):
                db_warnings.append(
                    f"Connection pool size {db_config.connection_pool_size} for database '{db_name}' may be suboptimal"
                )

            # Validate timeout settings
            if db_config.connection_timeout <= 0 or db_config.connection_timeout > 300:
                db_warnings.append(
                    f"Connection timeout {db_config.connection_timeout}s for database '{db_name}' may be suboptimal"
                )

            details[db_name] = {
                "errors": db_errors,
                "warnings": db_warnings,
                "config": db_config,
            }

            errors.extend(db_errors)
            warnings.extend(db_warnings)

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_service_dependencies(
        self, services: list[ServiceDependency]
    ) -> ValidationResult:
        """Validate service dependency configurations."""
        errors = []
        warnings = []
        details = {}

        for service in services:
            service_errors = []
            service_warnings = []

            # Validate health endpoint format
            if not service.health_endpoint:
                service_errors.append(
                    f"Missing health endpoint for service '{service.service_name}'"
                )
            elif not (
                service.health_endpoint.startswith("http://")
                or service.health_endpoint.startswith("https://")
            ):
                service_errors.append(
                    f"Invalid health endpoint format for service '{service.service_name}': must start with http:// or https://"
                )

            # Validate timeout and retry settings
            if service.timeout <= 0 or service.timeout > 300:
                service_warnings.append(
                    f"Service timeout {service.timeout}s for '{service.service_name}' may be suboptimal"
                )

            if service.retry_attempts <= 0 or service.retry_attempts > 10:
                service_warnings.append(
                    f"Retry attempts {service.retry_attempts} for service '{service.service_name}' may be suboptimal"
                )

            details[service.service_name] = {
                "errors": service_errors,
                "warnings": service_warnings,
                "config": service,
            }

            errors.extend(service_errors)
            warnings.extend(service_warnings)

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_security_config(self, security: dict[str, Any]) -> ValidationResult:
        """Validate security configuration."""
        errors = []
        warnings = []
        details = {"config": security}

        # Validate non-root execution
        if not security.get("run_as_non_root", True):
            warnings.append("Container configured to run as root user - security risk")

        # Validate user/group IDs
        user_id = security.get("user_id", 1000)
        if user_id == 0:
            errors.append(
                "Container configured with root user ID (0) - security violation"
            )
        elif user_id < 1000:
            warnings.append(
                f"Container user ID {user_id} is below 1000 - may conflict with system users"
            )

        group_id = security.get("group_id", 1000)
        if group_id == 0:
            errors.append(
                "Container configured with root group ID (0) - security violation"
            )
        elif group_id < 1000:
            warnings.append(
                f"Container group ID {group_id} is below 1000 - may conflict with system groups"
            )

        # Validate capabilities
        drop_capabilities = security.get("drop_capabilities", [])
        if "ALL" not in drop_capabilities:
            warnings.append(
                "Container not configured to drop all capabilities - consider security implications"
            )

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_resource_config(self, resources: dict[str, Any]) -> ValidationResult:
        """Validate resource configuration."""
        errors = []
        warnings = []
        details = {"config": resources}

        # Validate CPU settings
        try:
            cpu_limit_str = resources.get("cpu_limit", "1.0")
            cpu_request_str = resources.get("cpu_request", "0.1")

            # Handle None values
            if cpu_limit_str is None:
                cpu_limit_str = "1.0"
            if cpu_request_str is None:
                cpu_request_str = "0.1"

            cpu_limit = float(cpu_limit_str)
            cpu_request = float(cpu_request_str)

            if cpu_request > cpu_limit:
                errors.append(
                    f"CPU request ({cpu_request}) exceeds CPU limit ({cpu_limit})"
                )

            if cpu_limit > 8.0:
                warnings.append(
                    f"High CPU limit ({cpu_limit}) - ensure cluster has sufficient resources"
                )

        except (ValueError, TypeError) as e:
            errors.append(f"Invalid CPU configuration: {e}")

        # Validate memory settings
        memory_limit = resources.get("memory_limit", "512Mi")
        memory_request = resources.get("memory_request", "128Mi")

        # Handle None values
        if memory_limit is None:
            memory_limit = "512Mi"
        if memory_request is None:
            memory_request = "128Mi"

        if not self._validate_memory_format(memory_limit):
            errors.append(f"Invalid memory limit format: {memory_limit}")

        if not self._validate_memory_format(memory_request):
            errors.append(f"Invalid memory request format: {memory_request}")

        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings, details=details
        )

    def _validate_connection_string_format(
        self, connection_string: str, db_type: str
    ) -> bool:
        """Validate database connection string format."""
        if db_type == "postgresql":
            return connection_string.startswith(("postgresql://", "postgres://"))
        elif db_type == "sqlserver":
            return connection_string.startswith(("mssql://", "sqlserver://"))
        return False

    def _validate_memory_format(self, memory_value: str) -> bool:
        """Validate Kubernetes memory format (e.g., 512Mi, 1Gi)."""
        import re

        # Require a unit suffix for Kubernetes memory format
        pattern = r"^\d+(\.\d+)?(Ki|Mi|Gi|Ti|Pi|Ei|k|M|G|T|P|E)$"
        return bool(re.match(pattern, memory_value))

    def wait_for_dependencies(self, timeout: int = 300) -> bool:
        """
        Wait for all service dependencies to become available.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if all dependencies are available, False if timeout exceeded
        """
        from time import sleep

        import requests

        config = self.load_container_config()
        services = config["services"]

        if not services:
            return True  # No dependencies to wait for

        start_time = time.time()

        while time.time() - start_time < timeout:
            all_healthy = True

            for service in services:
                try:
                    response = requests.get(
                        service.health_endpoint, timeout=service.timeout
                    )
                    if response.status_code != 200:
                        all_healthy = False
                        break
                except Exception:
                    all_healthy = False
                    break

            if all_healthy:
                return True

            sleep(5)  # Wait 5 seconds before next check

        return False

    def generate_startup_report(self) -> StartupReport:
        """
        Generate comprehensive startup validation report.

        Returns:
            StartupReport with complete validation results and recommendations
        """
        startup_duration = time.time() - self._startup_time

        # Perform all validations
        env_validation = self.validate_container_environment()

        # Determine overall status
        if env_validation.errors:
            overall_status = "error"
        elif env_validation.warnings:
            overall_status = "warning"
        else:
            overall_status = "success"

        # Generate recommendations
        recommendations = self._generate_recommendations(env_validation)

        return StartupReport(
            timestamp=datetime.now(),
            environment=self.environment,
            flow_name=self.flow_name,
            validation_results={"environment": env_validation},
            overall_status=overall_status,
            startup_duration=startup_duration,
            recommendations=recommendations,
        )

    def _generate_recommendations(self, validation: ValidationResult) -> list[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        if validation.errors:
            recommendations.append(
                "Fix configuration errors before proceeding to production"
            )

        if validation.warnings:
            recommendations.append(
                "Review configuration warnings for optimization opportunities"
            )

        # Add specific recommendations based on validation details
        if "database_validation" in validation.details:
            db_validation = validation.details["database_validation"]
            if db_validation.warnings:
                recommendations.append(
                    "Consider optimizing database connection pool settings"
                )

        if "security_validation" in validation.details:
            security_validation = validation.details["security_validation"]
            if security_validation.warnings:
                recommendations.append(
                    "Review security configuration for production deployment"
                )

        if not recommendations:
            recommendations.append("Configuration looks good - ready for deployment")

        return recommendations
