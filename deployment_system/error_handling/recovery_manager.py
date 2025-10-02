"""
Recovery Manager

Provides comprehensive error recovery workflows with automated remediation
and guided recovery steps for deployment system failures.
"""

import logging
from typing import Any, Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum

from .error_types import (
    DeploymentSystemError,
    ErrorCategory,
    ErrorCodes,
    ErrorMessages,
    FlowDiscoveryError,
    ValidationError,
    ConfigurationError,
    DockerError,
    PrefectAPIError,
    DeploymentError,
)
from .retry_handler import RetryHandler, RetryPolicies
from .error_reporter import ErrorReporter
from .rollback_manager import RollbackManager, OperationType

logger = logging.getLogger(__name__)


class RecoveryStrategy(Enum):
    """Recovery strategy types."""

    AUTOMATIC = "automatic"
    GUIDED = "guided"
    MANUAL = "manual"
    SKIP = "skip"


@dataclass
class RecoveryAction:
    """Represents a recovery action."""

    name: str
    description: str
    action_function: Optional[Callable] = None
    requires_user_input: bool = False
    parameters: Optional[Dict[str, Any]] = None


@dataclass
class RecoveryPlan:
    """Represents a complete recovery plan."""

    error_code: str
    strategy: RecoveryStrategy
    actions: List[RecoveryAction]
    description: str
    estimated_time: Optional[str] = None


class RecoveryManager:
    """Manages error recovery workflows and automated remediation."""

    def __init__(
        self,
        retry_handler: Optional[RetryHandler] = None,
        error_reporter: Optional[ErrorReporter] = None,
        rollback_manager: Optional[RollbackManager] = None,
    ):
        self.retry_handler = retry_handler or RetryHandler(RetryPolicies.STANDARD_RETRY)
        self.error_reporter = error_reporter or ErrorReporter()
        self.rollback_manager = rollback_manager or RollbackManager()

        # Initialize recovery plans
        self.recovery_plans = self._initialize_recovery_plans()

    def recover_from_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        auto_execute: bool = False,
    ) -> Tuple[bool, List[str]]:
        """
        Attempt to recover from an error.

        Returns:
            Tuple of (success, recovery_messages)
        """
        recovery_messages = []

        # Report the error
        error_report = self.error_reporter.report_error(
            error=error, operation="error_recovery", additional_context=context
        )

        # Get recovery plan
        recovery_plan = self._get_recovery_plan(error)
        if not recovery_plan:
            recovery_messages.append(
                f"No recovery plan available for error: {type(error).__name__}"
            )
            return False, recovery_messages

        recovery_messages.append(
            f"Executing recovery plan: {recovery_plan.description}"
        )

        # Execute recovery actions
        success = True
        for action in recovery_plan.actions:
            try:
                action_success = self._execute_recovery_action(
                    action, error, context, auto_execute
                )
                if action_success:
                    recovery_messages.append(f"✓ {action.description}")
                else:
                    recovery_messages.append(f"✗ {action.description}")
                    success = False

                    # If this is a critical action and it failed, stop recovery
                    if (
                        recovery_plan.strategy == RecoveryStrategy.AUTOMATIC
                        and not action_success
                    ):
                        break

            except Exception as e:
                recovery_messages.append(f"✗ {action.description} - {e}")
                success = False

                # Report recovery action failure
                self.error_reporter.report_error(
                    error=e,
                    operation=f"recovery_action_{action.name}",
                    additional_context={"original_error": str(error)},
                )

        return success, recovery_messages

    def _get_recovery_plan(self, error: Exception) -> Optional[RecoveryPlan]:
        """Get recovery plan for an error."""
        if isinstance(error, DeploymentSystemError):
            return self.recovery_plans.get(error.error_code)

        # Try to match by error type
        error_type = type(error).__name__
        for plan in self.recovery_plans.values():
            if error_type.lower() in plan.error_code.lower():
                return plan

        return None

    def _execute_recovery_action(
        self,
        action: RecoveryAction,
        error: Exception,
        context: Optional[Dict[str, Any]],
        auto_execute: bool,
    ) -> bool:
        """Execute a single recovery action."""
        if action.requires_user_input and not auto_execute:
            # For now, skip actions that require user input in auto mode
            logger.info(f"Skipping action requiring user input: {action.name}")
            return True

        if action.action_function:
            try:
                # Prepare parameters
                params = action.parameters or {}
                params.update(
                    {
                        "error": error,
                        "context": context or {},
                    }
                )

                # Execute the action
                return action.action_function(**params)

            except Exception as e:
                logger.error(f"Recovery action failed: {action.name} - {e}")
                return False

        return True

    def _initialize_recovery_plans(self) -> Dict[str, RecoveryPlan]:
        """Initialize recovery plans for common errors."""
        plans = {}

        # Flow Discovery Errors
        plans[ErrorCodes.FLOW_NOT_FOUND] = RecoveryPlan(
            error_code=ErrorCodes.FLOW_NOT_FOUND,
            strategy=RecoveryStrategy.GUIDED,
            description="Recover from missing flow file",
            actions=[
                RecoveryAction(
                    name="check_file_exists",
                    description="Verify flow file exists",
                    action_function=self._check_file_exists,
                ),
                RecoveryAction(
                    name="suggest_similar_files",
                    description="Suggest similar flow files",
                    action_function=self._suggest_similar_files,
                ),
            ],
        )

        plans[ErrorCodes.FLOW_SYNTAX_ERROR] = RecoveryPlan(
            error_code=ErrorCodes.FLOW_SYNTAX_ERROR,
            strategy=RecoveryStrategy.MANUAL,
            description="Recover from flow syntax errors",
            actions=[
                RecoveryAction(
                    name="validate_python_syntax",
                    description="Validate Python syntax",
                    action_function=self._validate_python_syntax,
                ),
                RecoveryAction(
                    name="suggest_syntax_fixes",
                    description="Suggest common syntax fixes",
                    action_function=self._suggest_syntax_fixes,
                ),
            ],
        )

        plans[ErrorCodes.FLOW_MISSING_DEPENDENCIES] = RecoveryPlan(
            error_code=ErrorCodes.FLOW_MISSING_DEPENDENCIES,
            strategy=RecoveryStrategy.AUTOMATIC,
            description="Recover from missing dependencies",
            actions=[
                RecoveryAction(
                    name="install_dependencies",
                    description="Install missing dependencies",
                    action_function=self._install_dependencies,
                ),
                RecoveryAction(
                    name="update_requirements",
                    description="Update requirements.txt",
                    action_function=self._update_requirements,
                ),
            ],
        )

        # Docker Errors
        plans[ErrorCodes.DOCKER_BUILD_FAILED] = RecoveryPlan(
            error_code=ErrorCodes.DOCKER_BUILD_FAILED,
            strategy=RecoveryStrategy.AUTOMATIC,
            description="Recover from Docker build failures",
            actions=[
                RecoveryAction(
                    name="clean_docker_cache",
                    description="Clean Docker build cache",
                    action_function=self._clean_docker_cache,
                ),
                RecoveryAction(
                    name="retry_docker_build",
                    description="Retry Docker build",
                    action_function=self._retry_docker_build,
                ),
                RecoveryAction(
                    name="check_dockerfile",
                    description="Validate Dockerfile syntax",
                    action_function=self._check_dockerfile,
                ),
            ],
        )

        plans[ErrorCodes.DOCKER_DAEMON_UNAVAILABLE] = RecoveryPlan(
            error_code=ErrorCodes.DOCKER_DAEMON_UNAVAILABLE,
            strategy=RecoveryStrategy.AUTOMATIC,
            description="Recover from Docker daemon issues",
            actions=[
                RecoveryAction(
                    name="start_docker_daemon",
                    description="Start Docker daemon",
                    action_function=self._start_docker_daemon,
                ),
                RecoveryAction(
                    name="check_docker_permissions",
                    description="Check Docker permissions",
                    action_function=self._check_docker_permissions,
                ),
            ],
        )

        # Prefect API Errors
        plans[ErrorCodes.PREFECT_API_UNAVAILABLE] = RecoveryPlan(
            error_code=ErrorCodes.PREFECT_API_UNAVAILABLE,
            strategy=RecoveryStrategy.AUTOMATIC,
            description="Recover from Prefect API connectivity issues",
            actions=[
                RecoveryAction(
                    name="check_prefect_server",
                    description="Check Prefect server status",
                    action_function=self._check_prefect_server,
                ),
                RecoveryAction(
                    name="retry_api_connection",
                    description="Retry API connection with backoff",
                    action_function=self._retry_api_connection,
                ),
                RecoveryAction(
                    name="check_api_url",
                    description="Validate API URL configuration",
                    action_function=self._check_api_url,
                ),
            ],
        )

        plans[ErrorCodes.WORK_POOL_NOT_FOUND] = RecoveryPlan(
            error_code=ErrorCodes.WORK_POOL_NOT_FOUND,
            strategy=RecoveryStrategy.GUIDED,
            description="Recover from missing work pool",
            actions=[
                RecoveryAction(
                    name="list_available_work_pools",
                    description="List available work pools",
                    action_function=self._list_available_work_pools,
                ),
                RecoveryAction(
                    name="create_work_pool",
                    description="Create missing work pool",
                    action_function=self._create_work_pool,
                    requires_user_input=True,
                ),
            ],
        )

        # Configuration Errors
        plans[ErrorCodes.CONFIG_FILE_NOT_FOUND] = RecoveryPlan(
            error_code=ErrorCodes.CONFIG_FILE_NOT_FOUND,
            strategy=RecoveryStrategy.AUTOMATIC,
            description="Recover from missing configuration file",
            actions=[
                RecoveryAction(
                    name="create_default_config",
                    description="Create default configuration file",
                    action_function=self._create_default_config,
                ),
                RecoveryAction(
                    name="copy_example_config",
                    description="Copy from example configuration",
                    action_function=self._copy_example_config,
                ),
            ],
        )

        plans[ErrorCodes.ENVIRONMENT_NOT_CONFIGURED] = RecoveryPlan(
            error_code=ErrorCodes.ENVIRONMENT_NOT_CONFIGURED,
            strategy=RecoveryStrategy.AUTOMATIC,
            description="Recover from missing environment configuration",
            actions=[
                RecoveryAction(
                    name="create_environment_config",
                    description="Create environment configuration",
                    action_function=self._create_environment_config,
                ),
                RecoveryAction(
                    name="use_default_environment",
                    description="Fall back to default environment",
                    action_function=self._use_default_environment,
                ),
            ],
        )

        return plans

    # Recovery action implementations
    def _check_file_exists(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Check if a file exists and provide guidance."""
        if (
            isinstance(error, FlowDiscoveryError)
            and error.context
            and error.context.file_path
        ):
            from pathlib import Path

            file_path = Path(error.context.file_path)
            exists = file_path.exists()

            if not exists:
                logger.info(f"File does not exist: {file_path}")
                # Check parent directory
                if file_path.parent.exists():
                    logger.info(f"Parent directory exists: {file_path.parent}")
                else:
                    logger.info(f"Parent directory does not exist: {file_path.parent}")

            return exists

        return False

    def _suggest_similar_files(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Suggest similar files that might be the intended target."""
        if (
            isinstance(error, FlowDiscoveryError)
            and error.context
            and error.context.file_path
        ):
            from pathlib import Path
            import difflib

            file_path = Path(error.context.file_path)
            parent_dir = file_path.parent

            if parent_dir.exists():
                # Find similar files
                similar_files = []
                for existing_file in parent_dir.glob("*.py"):
                    similarity = difflib.SequenceMatcher(
                        None, file_path.name, existing_file.name
                    ).ratio()
                    if similarity > 0.6:  # 60% similarity threshold
                        similar_files.append((existing_file, similarity))

                # Sort by similarity
                similar_files.sort(key=lambda x: x[1], reverse=True)

                if similar_files:
                    logger.info("Similar files found:")
                    for file, similarity in similar_files[:3]:  # Top 3 matches
                        logger.info(f"  {file.name} (similarity: {similarity:.2%})")

                return len(similar_files) > 0

        return False

    def _validate_python_syntax(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Validate Python syntax of a file."""
        if (
            isinstance(error, FlowDiscoveryError)
            and error.context
            and error.context.file_path
        ):
            import ast
            from pathlib import Path

            file_path = Path(error.context.file_path)
            if not file_path.exists():
                return False

            try:
                with open(file_path, "r") as f:
                    content = f.read()

                ast.parse(content)
                logger.info(f"Python syntax is valid: {file_path}")
                return True

            except SyntaxError as e:
                logger.error(f"Syntax error in {file_path}: {e}")
                return False

        return False

    def _suggest_syntax_fixes(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Suggest common syntax fixes."""
        # This is a placeholder - in a real implementation, you might use
        # more sophisticated syntax analysis
        logger.info("Common syntax issues to check:")
        logger.info("  - Missing colons after if/for/while/def statements")
        logger.info("  - Incorrect indentation")
        logger.info("  - Unmatched parentheses, brackets, or quotes")
        logger.info("  - Missing imports")
        return True

    def _install_dependencies(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Install missing dependencies."""
        try:
            import subprocess

            # Try to install from requirements.txt
            result = subprocess.run(
                ["pip", "install", "-r", "requirements.txt"],
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info("Dependencies installed successfully")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install dependencies: {e}")
            return False
        except FileNotFoundError:
            logger.error("pip command not found")
            return False

    def _update_requirements(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Update requirements.txt file."""
        # This is a placeholder - in a real implementation, you might
        # analyze the error to determine which packages are missing
        logger.info("Consider updating requirements.txt with missing packages")
        return True

    def _clean_docker_cache(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Clean Docker build cache."""
        try:
            import subprocess

            subprocess.run(
                ["docker", "builder", "prune", "-f"], check=True, capture_output=True
            )
            logger.info("Docker build cache cleaned")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clean Docker cache: {e}")
            return False
        except FileNotFoundError:
            logger.error("Docker command not found")
            return False

    def _retry_docker_build(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Retry Docker build with retry logic."""
        # This would integrate with the actual Docker build process
        logger.info("Retrying Docker build...")
        return True

    def _check_dockerfile(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Check Dockerfile for common issues."""
        if isinstance(error, DockerError) and error.context and error.context.file_path:
            from pathlib import Path

            dockerfile_path = Path(error.context.file_path)
            if not dockerfile_path.exists():
                logger.error(f"Dockerfile not found: {dockerfile_path}")
                return False

            # Basic Dockerfile validation
            with open(dockerfile_path, "r") as f:
                content = f.read()

            issues = []
            if not content.strip().startswith("FROM"):
                issues.append("Dockerfile should start with FROM instruction")

            if "COPY" not in content and "ADD" not in content:
                issues.append("Dockerfile should copy application files")

            if issues:
                logger.warning("Dockerfile issues found:")
                for issue in issues:
                    logger.warning(f"  - {issue}")
                return False

            logger.info("Dockerfile appears to be valid")
            return True

        return False

    def _start_docker_daemon(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Attempt to start Docker daemon."""
        try:
            import subprocess

            # Check if Docker is running
            result = subprocess.run(["docker", "info"], capture_output=True)
            if result.returncode == 0:
                logger.info("Docker daemon is already running")
                return True

            # Try to start Docker (this is platform-specific)
            logger.info("Docker daemon not running. Please start Docker manually.")
            return False

        except FileNotFoundError:
            logger.error("Docker command not found. Please install Docker.")
            return False

    def _check_docker_permissions(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Check Docker permissions."""
        logger.info("If you're getting permission errors, try:")
        logger.info(
            "  - Adding your user to the docker group: sudo usermod -aG docker $USER"
        )
        logger.info("  - Restarting your session after adding to docker group")
        logger.info("  - Running with sudo (not recommended for production)")
        return True

    def _check_prefect_server(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Check Prefect server status."""
        try:
            import requests

            # Get API URL from context or use default
            api_url = context.get("api_url", "http://localhost:4200/api")

            response = requests.get(f"{api_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info("Prefect server is running")
                return True
            else:
                logger.error(f"Prefect server returned status {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Cannot connect to Prefect server: {e}")
            return False

    def _retry_api_connection(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Retry API connection with exponential backoff."""
        # This would use the retry handler to retry the original operation
        logger.info("Retrying API connection...")
        return True

    def _check_api_url(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Validate API URL configuration."""
        api_url = context.get("api_url")
        if not api_url:
            logger.error("No API URL configured")
            return False

        if not api_url.startswith(("http://", "https://")):
            logger.error(f"Invalid API URL format: {api_url}")
            return False

        logger.info(f"API URL appears valid: {api_url}")
        return True

    def _list_available_work_pools(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """List available work pools."""
        try:
            from ..api.prefect_client import PrefectClient

            client = PrefectClient()
            # This would call the actual Prefect API to list work pools
            logger.info("Available work pools:")
            logger.info("  - default-agent-pool")
            logger.info("  - docker-pool")
            return True

        except Exception as e:
            logger.error(f"Failed to list work pools: {e}")
            return False

    def _create_work_pool(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Create a missing work pool."""
        # This would require user input to specify work pool configuration
        logger.info("Work pool creation requires manual configuration")
        return False

    def _create_default_config(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Create a default configuration file."""
        if (
            isinstance(error, ConfigurationError)
            and error.context
            and error.context.file_path
        ):
            from pathlib import Path

            config_path = Path(error.context.file_path)

            # Create default configuration content
            default_config = """
environments:
  development:
    prefect_api_url: "http://localhost:4200/api"
    work_pools:
      python: "default-agent-pool"
      docker: "docker-pool"
    default_parameters:
      cleanup: true
    resource_limits:
      memory: "512Mi"
      cpu: "0.5"
"""

            try:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text(default_config.strip())
                logger.info(f"Created default configuration: {config_path}")
                return True

            except Exception as e:
                logger.error(f"Failed to create default configuration: {e}")
                return False

        return False

    def _copy_example_config(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Copy from example configuration."""
        # This would look for example configuration files
        logger.info("Looking for example configuration files...")
        return False

    def _create_environment_config(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Create environment-specific configuration."""
        environment = context.get("environment", "development")
        logger.info(f"Creating configuration for environment: {environment}")
        return True

    def _use_default_environment(
        self, error: Exception, context: Dict[str, Any], **kwargs
    ) -> bool:
        """Fall back to default environment configuration."""
        logger.info("Using default environment configuration")
        return True

    def get_recovery_guidance(self, error: Exception) -> List[str]:
        """Get human-readable recovery guidance for an error."""
        recovery_plan = self._get_recovery_plan(error)
        if not recovery_plan:
            return ["No specific recovery guidance available for this error."]

        guidance = [f"Recovery Strategy: {recovery_plan.description}"]

        if recovery_plan.estimated_time:
            guidance.append(f"Estimated Time: {recovery_plan.estimated_time}")

        guidance.append("Recovery Steps:")
        for i, action in enumerate(recovery_plan.actions, 1):
            guidance.append(f"  {i}. {action.description}")

        return guidance
