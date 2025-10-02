"""
Error Types and Exceptions

Defines custom exception types for the deployment system with detailed
error information and remediation guidance.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""

    FLOW_DISCOVERY = "flow_discovery"
    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    DOCKER = "docker"
    PREFECT_API = "prefect_api"
    DEPLOYMENT = "deployment"
    NETWORK = "network"
    FILESYSTEM = "filesystem"


@dataclass
class ErrorContext:
    """Additional context information for errors."""

    flow_name: Optional[str] = None
    deployment_name: Optional[str] = None
    environment: Optional[str] = None
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    operation: Optional[str] = None
    additional_info: Optional[Dict[str, Any]] = None


class DeploymentSystemError(Exception):
    """Base exception for deployment system errors."""

    def __init__(
        self,
        message: str,
        error_code: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[ErrorContext] = None,
        remediation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.context = context or ErrorContext()
        self.remediation = remediation or ""
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary representation."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": {
                "flow_name": self.context.flow_name,
                "deployment_name": self.context.deployment_name,
                "environment": self.context.environment,
                "file_path": self.context.file_path,
                "line_number": self.context.line_number,
                "operation": self.context.operation,
                "additional_info": self.context.additional_info,
            },
            "remediation": self.remediation,
            "cause": str(self.cause) if self.cause else None,
        }


class FlowDiscoveryError(DeploymentSystemError):
    """Errors related to flow discovery and scanning."""

    def __init__(
        self,
        message: str,
        error_code: str = "FLOW_DISCOVERY_ERROR",
        context: Optional[ErrorContext] = None,
        remediation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.FLOW_DISCOVERY,
            severity=ErrorSeverity.MEDIUM,
            context=context,
            remediation=remediation,
            cause=cause,
        )


class ValidationError(DeploymentSystemError):
    """Errors related to validation failures."""

    def __init__(
        self,
        message: str,
        error_code: str = "VALIDATION_ERROR",
        context: Optional[ErrorContext] = None,
        remediation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            remediation=remediation,
            cause=cause,
        )


class ConfigurationError(DeploymentSystemError):
    """Errors related to configuration issues."""

    def __init__(
        self,
        message: str,
        error_code: str = "CONFIGURATION_ERROR",
        context: Optional[ErrorContext] = None,
        remediation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            context=context,
            remediation=remediation,
            cause=cause,
        )


class DockerError(DeploymentSystemError):
    """Errors related to Docker operations."""

    def __init__(
        self,
        message: str,
        error_code: str = "DOCKER_ERROR",
        context: Optional[ErrorContext] = None,
        remediation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.DOCKER,
            severity=ErrorSeverity.HIGH,
            context=context,
            remediation=remediation,
            cause=cause,
        )


class PrefectAPIError(DeploymentSystemError):
    """Errors related to Prefect API operations."""

    def __init__(
        self,
        message: str,
        error_code: str = "PREFECT_API_ERROR",
        context: Optional[ErrorContext] = None,
        remediation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.PREFECT_API,
            severity=ErrorSeverity.HIGH,
            context=context,
            remediation=remediation,
            cause=cause,
        )


class DeploymentError(DeploymentSystemError):
    """Errors related to deployment operations."""

    def __init__(
        self,
        message: str,
        error_code: str = "DEPLOYMENT_ERROR",
        context: Optional[ErrorContext] = None,
        remediation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.DEPLOYMENT,
            severity=ErrorSeverity.HIGH,
            context=context,
            remediation=remediation,
            cause=cause,
        )


class RecoveryError(DeploymentSystemError):
    """Errors related to recovery operations."""

    def __init__(
        self,
        message: str,
        error_code: str = "RECOVERY_ERROR",
        context: Optional[ErrorContext] = None,
        remediation: Optional[str] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            category=ErrorCategory.DEPLOYMENT,
            severity=ErrorSeverity.CRITICAL,
            context=context,
            remediation=remediation,
            cause=cause,
        )


# Predefined error codes and messages
class ErrorCodes:
    """Common error codes and their default messages."""

    # Flow Discovery Errors
    FLOW_NOT_FOUND = "FLOW_NOT_FOUND"
    FLOW_SYNTAX_ERROR = "FLOW_SYNTAX_ERROR"
    FLOW_MISSING_DEPENDENCIES = "FLOW_MISSING_DEPENDENCIES"
    FLOW_INVALID_STRUCTURE = "FLOW_INVALID_STRUCTURE"

    # Validation Errors
    VALIDATION_FAILED = "VALIDATION_FAILED"
    DEPENDENCY_CONFLICT = "DEPENDENCY_CONFLICT"
    MISSING_REQUIREMENTS = "MISSING_REQUIREMENTS"

    # Configuration Errors
    CONFIG_FILE_NOT_FOUND = "CONFIG_FILE_NOT_FOUND"
    CONFIG_INVALID_FORMAT = "CONFIG_INVALID_FORMAT"
    CONFIG_MISSING_REQUIRED_FIELD = "CONFIG_MISSING_REQUIRED_FIELD"
    ENVIRONMENT_NOT_CONFIGURED = "ENVIRONMENT_NOT_CONFIGURED"

    # Docker Errors
    DOCKER_BUILD_FAILED = "DOCKER_BUILD_FAILED"
    DOCKER_IMAGE_NOT_FOUND = "DOCKER_IMAGE_NOT_FOUND"
    DOCKERFILE_NOT_FOUND = "DOCKERFILE_NOT_FOUND"
    DOCKER_DAEMON_UNAVAILABLE = "DOCKER_DAEMON_UNAVAILABLE"

    # Prefect API Errors
    PREFECT_API_UNAVAILABLE = "PREFECT_API_UNAVAILABLE"
    PREFECT_AUTH_FAILED = "PREFECT_AUTH_FAILED"
    WORK_POOL_NOT_FOUND = "WORK_POOL_NOT_FOUND"
    DEPLOYMENT_CREATE_FAILED = "DEPLOYMENT_CREATE_FAILED"
    DEPLOYMENT_UPDATE_FAILED = "DEPLOYMENT_UPDATE_FAILED"

    # Deployment Errors
    DEPLOYMENT_ROLLBACK_FAILED = "DEPLOYMENT_ROLLBACK_FAILED"
    DEPLOYMENT_CLEANUP_FAILED = "DEPLOYMENT_CLEANUP_FAILED"


class ErrorMessages:
    """Default error messages and remediation steps."""

    MESSAGES = {
        ErrorCodes.FLOW_NOT_FOUND: {
            "message": "Flow file not found at specified path",
            "remediation": "Check that the flow file exists and the path is correct",
        },
        ErrorCodes.FLOW_SYNTAX_ERROR: {
            "message": "Flow file contains syntax errors",
            "remediation": "Fix syntax errors in the flow file and ensure it's valid Python",
        },
        ErrorCodes.FLOW_MISSING_DEPENDENCIES: {
            "message": "Flow has missing or unresolvable dependencies",
            "remediation": "Install missing dependencies or update requirements.txt",
        },
        ErrorCodes.DOCKER_BUILD_FAILED: {
            "message": "Docker image build failed",
            "remediation": "Check Dockerfile syntax and ensure all required files are present",
        },
        ErrorCodes.PREFECT_API_UNAVAILABLE: {
            "message": "Cannot connect to Prefect API server",
            "remediation": "Ensure Prefect server is running and API URL is correct",
        },
        ErrorCodes.WORK_POOL_NOT_FOUND: {
            "message": "Specified work pool does not exist",
            "remediation": "Create the work pool or update configuration to use an existing one",
        },
    }

    @classmethod
    def get_message(cls, error_code: str) -> str:
        """Get default message for error code."""
        return cls.MESSAGES.get(error_code, {}).get("message", "Unknown error")

    @classmethod
    def get_remediation(cls, error_code: str) -> str:
        """Get default remediation for error code."""
        return cls.MESSAGES.get(error_code, {}).get(
            "remediation", "No remediation available"
        )
