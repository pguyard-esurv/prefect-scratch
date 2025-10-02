"""
Error Handling and Recovery System

Provides comprehensive error handling, recovery mechanisms, and retry logic
for the deployment system.
"""

from .error_types import (
    DeploymentSystemError,
    DeploymentError,
    FlowDiscoveryError,
    ValidationError,
    ConfigurationError,
    DockerError,
    PrefectAPIError,
    RecoveryError,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
    ErrorCodes,
    ErrorMessages,
)

from .recovery_manager import RecoveryManager
from .retry_handler import (
    RetryHandler,
    RetryPolicy,
    RetryStrategy,
    RetryPolicies,
    with_retry,
    with_async_retry,
)
from .error_reporter import (
    ErrorReporter,
    ErrorReport,
    get_global_reporter,
    report_error,
    format_user_error,
)
from .rollback_manager import (
    RollbackManager,
    RollbackOperation,
    RollbackPlan,
    OperationType,
    OperationStatus,
    get_global_rollback_manager,
)

__all__ = [
    # Error Types
    "DeploymentSystemError",
    "DeploymentError",
    "FlowDiscoveryError",
    "ValidationError",
    "ConfigurationError",
    "DockerError",
    "PrefectAPIError",
    "RecoveryError",
    "ErrorContext",
    "ErrorSeverity",
    "ErrorCategory",
    "ErrorCodes",
    "ErrorMessages",
    # Retry Handling
    "RetryHandler",
    "RetryPolicy",
    "RetryStrategy",
    "RetryPolicies",
    "with_retry",
    "with_async_retry",
    # Error Reporting
    "ErrorReporter",
    "ErrorReport",
    "get_global_reporter",
    "report_error",
    "format_user_error",
    # Rollback Management
    "RollbackManager",
    "RollbackOperation",
    "RollbackPlan",
    "OperationType",
    "OperationStatus",
    "get_global_rollback_manager",
    # Recovery Management
    "RecoveryManager",
]
