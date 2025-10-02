"""
Docker Deployment Builder

Creates containerized deployments for Prefect flows with comprehensive error handling.
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

from ..api.deployment_api import DeploymentAPI
from ..config.deployment_config import DeploymentConfig
from ..discovery.metadata import FlowMetadata
from ..validation.docker_validator import DockerValidator
from ..validation.validation_result import (
    ValidationError,
    ValidationResult,
    ValidationWarning,
)
from ..error_handling import (
    DockerError,
    DeploymentError,
    ValidationError as SystemValidationError,
    ErrorContext,
    ErrorCodes,
    RetryHandler,
    RetryPolicies,
    ErrorReporter,
    RollbackManager,
    OperationType,
    with_retry,
)
from .base_builder import BaseDeploymentBuilder

logger = logging.getLogger(__name__)


class DockerDeploymentCreator(BaseDeploymentBuilder):
    """Creates containerized deployments for Prefect flows with error handling."""

    def __init__(self, config_manager=None, api_url: Optional[str] = None):
        super().__init__(config_manager)
        self.deployment_api = DeploymentAPI(api_url)
        self.docker_validator = DockerValidator()
        self.retry_handler = RetryHandler(RetryPolicies.DOCKER_RETRY)
        self.error_reporter = ErrorReporter()
        self.rollback_manager = RollbackManager()

    def get_deployment_type(self) -> str:
        """Get the deployment type identifier."""
        return "docker"

    def create_deployment(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> DeploymentConfig:
        """Create a Docker deployment configuration."""
        if not flow.supports_docker_deployment:
            raise ValueError(f"Flow {flow.name} does not support Docker deployment")

        # Generate deployment configuration using config manager
        if self.config_manager:
            config = self.config_manager.generate_deployment_config(
                flow, "docker", environment
            )
        else:
            # Fallback to manual configuration
            config = self._create_fallback_config(flow, environment)

        # Add Docker-specific enhancements
        self._enhance_docker_config(config, flow, environment)

        return config

    def create_deployment_dict(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> dict[str, Any]:
        """Create a Docker deployment configuration as dictionary."""
        config = self.create_deployment(flow, environment)
        return config.to_dict()

    def deploy_to_prefect(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> Optional[str]:
        """Create and deploy a Docker deployment to Prefect."""
        try:
            config = self.create_deployment(flow, environment)

            # Validate configuration
            validation_result = self.validate_deployment_config(config)
            if not validation_result.is_valid:
                error_messages = [error.message for error in validation_result.errors]
                raise ValueError(
                    f"Invalid deployment configuration: {'; '.join(error_messages)}"
                )

            # Deploy to Prefect
            deployment_id = self.deployment_api.create_or_update_deployment(config)

            if deployment_id:
                logger.info(
                    f"Successfully deployed Docker deployment for {flow.name} to {environment}"
                )
                return deployment_id
            else:
                logger.error(f"Failed to deploy Docker deployment for {flow.name}")
                return None

        except Exception as e:
            logger.error(f"Failed to deploy Docker deployment for {flow.name}: {e}")
            raise

    def validate_deployment_config(self, config: DeploymentConfig) -> ValidationResult:
        """Validate a Docker deployment configuration."""
        errors = []
        warnings = []

        # Validate required fields
        if not config.flow_name:
            errors.append(
                ValidationError(
                    code="MISSING_FLOW_NAME",
                    message="Flow name is required",
                    remediation="Ensure flow_name is set in the deployment configuration",
                )
            )

        if not config.entrypoint:
            errors.append(
                ValidationError(
                    code="MISSING_ENTRYPOINT",
                    message="Entrypoint is required",
                    remediation="Ensure entrypoint is set in format 'module.path:function_name'",
                )
            )

        if not config.work_pool:
            errors.append(
                ValidationError(
                    code="MISSING_WORK_POOL",
                    message="Work pool is required",
                    remediation="Ensure work_pool is set to a valid Prefect work pool",
                )
            )

        # Validate entrypoint format (module:function)
        if config.entrypoint and ":" not in config.entrypoint:
            errors.append(
                ValidationError(
                    code="INVALID_ENTRYPOINT_FORMAT",
                    message="Entrypoint must be in format 'module.path:function_name'",
                    remediation=f"Change entrypoint from '{config.entrypoint}' to include ':function_name'",
                )
            )

        # Validate deployment type
        if config.deployment_type != "docker":
            errors.append(
                ValidationError(
                    code="INVALID_DEPLOYMENT_TYPE",
                    message=f"Expected deployment type 'docker', got '{config.deployment_type}'",
                    remediation="Set deployment_type to 'docker'",
                )
            )

        # Validate Docker-specific configuration
        if "image" not in config.job_variables:
            errors.append(
                ValidationError(
                    code="MISSING_DOCKER_IMAGE",
                    message="Docker image is required in job_variables",
                    remediation="Set job_variables.image to a valid Docker image",
                )
            )

        # Validate work pool exists (if API is available)
        if config.work_pool:
            try:
                if not self.deployment_api.validate_work_pool(config.work_pool):
                    warnings.append(
                        ValidationWarning(
                            code="WORK_POOL_NOT_FOUND",
                            message=f"Work pool '{config.work_pool}' may not exist",
                            suggestion=f"Ensure work pool '{config.work_pool}' is created in Prefect",
                        )
                    )
            except Exception as e:
                warnings.append(
                    ValidationWarning(
                        code="WORK_POOL_VALIDATION_FAILED",
                        message=f"Could not validate work pool '{config.work_pool}': {e}",
                        suggestion="Check Prefect server connectivity and work pool configuration",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_docker_image(self, image_name: str) -> ValidationResult:
        """Validate that a Docker image exists or can be built."""
        errors = []
        warnings = []

        try:
            # Check if image exists locally
            result = subprocess.run(
                ["docker", "image", "inspect", image_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                warnings.append(
                    ValidationWarning(
                        code="DOCKER_IMAGE_NOT_FOUND",
                        message=f"Docker image '{image_name}' not found locally",
                        suggestion=f"Build the image with: docker build -t {image_name} .",
                    )
                )

        except subprocess.TimeoutExpired:
            warnings.append(
                ValidationWarning(
                    code="DOCKER_INSPECT_TIMEOUT",
                    message=f"Timeout while checking Docker image '{image_name}'",
                    suggestion="Check Docker daemon status",
                )
            )
        except FileNotFoundError:
            errors.append(
                ValidationError(
                    code="DOCKER_NOT_AVAILABLE",
                    message="Docker command not found",
                    remediation="Install Docker or ensure it's in PATH",
                )
            )
        except Exception as e:
            warnings.append(
                ValidationWarning(
                    code="DOCKER_VALIDATION_ERROR",
                    message=f"Error validating Docker image '{image_name}': {e}",
                    suggestion="Check Docker configuration and image name",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def build_docker_image(self, flow: FlowMetadata, tag: Optional[str] = None) -> bool:
        """Build Docker image for a flow with comprehensive error handling and rollback."""
        context = ErrorContext(flow_name=flow.name, operation="build_docker_image")

        # Start rollback transaction
        rollback_id = self.rollback_manager.start_transaction(
            f"Build Docker image for {flow.name}"
        )

        try:
            # Validate prerequisites
            if not flow.dockerfile_path:
                raise DockerError(
                    f"No Dockerfile found for flow {flow.name}",
                    error_code=ErrorCodes.DOCKERFILE_NOT_FOUND,
                    context=context,
                    remediation=f"Create a Dockerfile in the flow directory: {Path(flow.path).parent}",
                )

            dockerfile_path = Path(flow.dockerfile_path)
            context.file_path = str(dockerfile_path)

            if not dockerfile_path.exists():
                raise DockerError(
                    f"Dockerfile not found: {dockerfile_path}",
                    error_code=ErrorCodes.DOCKERFILE_NOT_FOUND,
                    context=context,
                    remediation="Ensure the Dockerfile exists at the specified path",
                )

            # Validate Dockerfile
            validation_result = self.docker_validator.validate_dockerfile(
                str(dockerfile_path)
            )
            if not validation_result.is_valid:
                error_messages = validation_result.get_error_messages()
                raise DockerError(
                    f"Invalid Dockerfile for {flow.name}: {'; '.join(error_messages)}",
                    error_code=ErrorCodes.DOCKER_BUILD_FAILED,
                    context=context,
                    remediation="Fix the Dockerfile validation errors",
                )

            # Determine image tag
            if not tag:
                tag = f"{flow.name}-worker:latest"

            # Build context is the directory containing the Dockerfile
            build_context = dockerfile_path.parent

            # Check Docker daemon availability
            try:
                subprocess.run(
                    ["docker", "info"], check=True, capture_output=True, timeout=10
                )
            except subprocess.CalledProcessError:
                raise DockerError(
                    "Docker daemon is not running or not accessible",
                    error_code=ErrorCodes.DOCKER_DAEMON_UNAVAILABLE,
                    context=context,
                    remediation="Start Docker daemon or check Docker installation",
                )
            except FileNotFoundError:
                raise DockerError(
                    "Docker command not found",
                    error_code=ErrorCodes.DOCKER_DAEMON_UNAVAILABLE,
                    context=context,
                    remediation="Install Docker or ensure it's in PATH",
                )

            logger.info(f"Building Docker image {tag} for flow {flow.name}")

            # Build with retry logic
            def build_image():
                result = subprocess.run(
                    [
                        "docker",
                        "build",
                        "-t",
                        tag,
                        "-f",
                        str(dockerfile_path),
                        str(build_context),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout
                )

                if result.returncode != 0:
                    raise DockerError(
                        f"Docker build failed: {result.stderr}",
                        error_code=ErrorCodes.DOCKER_BUILD_FAILED,
                        context=context,
                        remediation="Check Dockerfile syntax and build context",
                    )

                return result

            # Execute build with retry
            result = self.retry_handler.retry(build_image)

            # Add rollback operation to remove the built image
            self.rollback_manager.add_rollback_operation(
                operation_type=OperationType.DOCKER_IMAGE_BUILD,
                description=f"Remove Docker image {tag}",
                rollback_data={"image_name": tag},
            )

            # Commit transaction on success
            self.rollback_manager.commit_transaction()
            logger.info(f"Successfully built Docker image {tag}")
            return True

        except DockerError:
            # Re-raise DockerError as-is
            raise
        except subprocess.TimeoutExpired as e:
            error = DockerError(
                f"Timeout building Docker image {tag}",
                error_code=ErrorCodes.DOCKER_BUILD_FAILED,
                context=context,
                remediation="Increase timeout or check build complexity",
                cause=e,
            )
            self.error_reporter.report_error(error, operation="build_docker_image")

            # Execute rollback
            try:
                self.rollback_manager.execute_rollback(rollback_id)
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")

            raise error
        except Exception as e:
            error = DockerError(
                f"Unexpected error building Docker image {tag}: {str(e)}",
                error_code=ErrorCodes.DOCKER_BUILD_FAILED,
                context=context,
                remediation="Check Docker configuration and system resources",
                cause=e,
            )
            self.error_reporter.report_error(error, operation="build_docker_image")

            # Execute rollback
            try:
                self.rollback_manager.execute_rollback(rollback_id)
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")

            raise error

    def _create_fallback_config(
        self, flow: FlowMetadata, environment: str
    ) -> DeploymentConfig:
        """Create fallback configuration when config manager is not available."""
        deployment_name = self._generate_deployment_name(flow, environment)
        image_name = f"{flow.name}-worker:latest"

        return DeploymentConfig(
            flow_name=flow.name,
            deployment_name=deployment_name,
            environment=environment,
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint=f"{flow.module_path}:{flow.function_name}",
            parameters={},
            job_variables={
                "image": image_name,
                "env": {
                    "PREFECT_API_URL": "http://prefect-server:4200/api",
                    "PYTHONPATH": "/app",
                    "PREFECT_LOGGING_LEVEL": "INFO",
                    "ENVIRONMENT": environment.upper(),
                    "FLOW_NAME": flow.name,
                    "DEPLOYMENT_TYPE": "docker",
                },
                "volumes": [
                    f"./flows/{flow.name}/data:/app/flows/{flow.name}/data",
                    f"./flows/{flow.name}/output:/app/flows/{flow.name}/output",
                    f"./logs/{flow.name}:/app/logs",
                ],
                "networks": ["rpa-network"],
            },
            tags=[
                f"environment:{environment}",
                "type:docker",
                f"flow:{flow.name}",
            ],
            description=f"{flow.name} flow deployed as Docker container in {environment}",
        )

    def _enhance_docker_config(
        self, config: DeploymentConfig, flow: FlowMetadata, environment: str
    ):
        """Enhance deployment configuration with Docker-specific settings."""
        # Ensure job_variables has required Docker fields
        if "image" not in config.job_variables:
            config.job_variables["image"] = f"{flow.name}-worker:latest"

        if "env" not in config.job_variables:
            config.job_variables["env"] = {}

        # Add Docker-specific environment variables
        docker_env_vars = {
            "PREFECT_API_URL": "http://prefect-server:4200/api",
            "PYTHONPATH": "/app",
            "PREFECT_LOGGING_LEVEL": "INFO",
            "ENVIRONMENT": environment.upper(),
            "FLOW_NAME": flow.name,
            "DEPLOYMENT_TYPE": "docker",
            "CONTAINER_ENVIRONMENT": environment,
            "CONTAINER_FLOW_NAME": flow.name,
        }

        config.job_variables["env"].update(docker_env_vars)

        # Add volume mounts if not present
        if "volumes" not in config.job_variables:
            config.job_variables["volumes"] = [
                f"./flows/{flow.name}/data:/app/flows/{flow.name}/data",
                f"./flows/{flow.name}/output:/app/flows/{flow.name}/output",
                f"./logs/{flow.name}:/app/logs",
            ]

        # Add network configuration
        if "networks" not in config.job_variables:
            config.job_variables["networks"] = ["rpa-network"]

        # Add resource limits based on environment
        if "resources" not in config.job_variables:
            config.job_variables["resources"] = self._get_resource_limits(environment)

        # Add restart policy
        if "restart_policy" not in config.job_variables:
            config.job_variables["restart_policy"] = "unless-stopped"

        # Add health check configuration
        if "healthcheck" not in config.job_variables:
            config.job_variables["healthcheck"] = {
                "test": [
                    "CMD-SHELL",
                    f"uv run python /app/scripts/health_check.py --flow={flow.name} --quick-check",
                ],
                "interval": "30s",
                "timeout": "15s",
                "retries": 3,
                "start_period": "45s",
            }

        # Add flow-specific environment files
        if flow.env_files:
            config.job_variables["env_files"] = flow.env_files

        # Add Docker-specific tags
        config.add_tag("runtime:docker")
        config.add_tag("container:enabled")
        if flow.dockerfile_path:
            config.add_tag("dockerfile:available")

    def _get_resource_limits(self, environment: str) -> dict[str, Any]:
        """Get resource limits based on environment."""
        resource_configs = {
            "development": {
                "memory": "512M",
                "cpus": "0.5",
                "memory_reservation": "256M",
                "cpus_reservation": "0.25",
            },
            "staging": {
                "memory": "1G",
                "cpus": "1.0",
                "memory_reservation": "512M",
                "cpus_reservation": "0.5",
            },
            "production": {
                "memory": "2G",
                "cpus": "2.0",
                "memory_reservation": "1G",
                "cpus_reservation": "1.0",
            },
        }

        return resource_configs.get(environment, resource_configs["development"])

    def get_deployment_template(self) -> dict[str, Any]:
        """Get the default Docker deployment template."""
        return {
            "work_pool": "${environment.work_pools.docker}",
            "job_variables": {
                "image": "${flow.name}-worker:latest",
                "env": {
                    "PREFECT_API_URL": "${environment.prefect_api_url}",
                    "PYTHONPATH": "/app",
                    "PREFECT_LOGGING_LEVEL": "INFO",
                    "ENVIRONMENT": "${environment.name}",
                    "FLOW_NAME": "${flow.name}",
                    "DEPLOYMENT_TYPE": "docker",
                    "CONTAINER_ENVIRONMENT": "${environment.name}",
                    "CONTAINER_FLOW_NAME": "${flow.name}",
                },
                "volumes": [
                    "./flows/${flow.name}/data:/app/flows/${flow.name}/data",
                    "./flows/${flow.name}/output:/app/flows/${flow.name}/output",
                    "./logs/${flow.name}:/app/logs",
                ],
                "networks": ["rpa-network"],
                "resources": "${environment.resource_limits}",
                "restart_policy": "unless-stopped",
                "healthcheck": {
                    "test": [
                        "CMD-SHELL",
                        "uv run python /app/scripts/health_check.py --flow=${flow.name} --quick-check",
                    ],
                    "interval": "30s",
                    "timeout": "15s",
                    "retries": 3,
                    "start_period": "45s",
                },
            },
            "parameters": "${environment.default_parameters}",
            "tags": [
                "environment:${environment.name}",
                "type:docker",
                "flow:${flow.name}",
                "runtime:docker",
                "container:enabled",
            ],
        }
