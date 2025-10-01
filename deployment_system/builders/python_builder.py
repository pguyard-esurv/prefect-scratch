"""
Python Deployment Builder

Creates native Python deployments for Prefect flows.
"""

import logging
from typing import Any, Optional

from ..api.deployment_api import DeploymentAPI
from ..config.deployment_config import DeploymentConfig
from ..discovery.metadata import FlowMetadata
from ..validation.validation_result import ValidationResult
from .base_builder import BaseDeploymentBuilder

logger = logging.getLogger(__name__)


class PythonDeploymentCreator(BaseDeploymentBuilder):
    """Creates native Python deployments for Prefect flows."""

    def __init__(self, config_manager=None, api_url: Optional[str] = None):
        super().__init__(config_manager)
        self.deployment_api = DeploymentAPI(api_url)

    def get_deployment_type(self) -> str:
        """Get the deployment type identifier."""
        return "python"

    def create_deployment(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> DeploymentConfig:
        """Create a Python deployment configuration."""
        if not flow.supports_python_deployment:
            raise ValueError(f"Flow {flow.name} does not support Python deployment")

        # Generate deployment configuration using config manager
        if self.config_manager:
            config = self.config_manager.generate_deployment_config(
                flow, "python", environment
            )
        else:
            # Fallback to manual configuration
            config = self._create_fallback_config(flow, environment)

        # Add Python-specific enhancements
        self._enhance_python_config(config, flow, environment)

        return config

    def create_deployment_dict(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> dict[str, Any]:
        """Create a Python deployment configuration as dictionary."""
        config = self.create_deployment(flow, environment)
        return config.to_dict()

    def deploy_to_prefect(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> Optional[str]:
        """Create and deploy a Python deployment to Prefect."""
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
                    f"Successfully deployed Python deployment for {flow.name} to {environment}"
                )
                return deployment_id
            else:
                logger.error(f"Failed to deploy Python deployment for {flow.name}")
                return None

        except Exception as e:
            logger.error(f"Failed to deploy Python deployment for {flow.name}: {e}")
            raise

    def validate_deployment_config(self, config: DeploymentConfig) -> ValidationResult:
        """Validate a Python deployment configuration."""
        from ..validation.validation_result import ValidationError

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
        if config.deployment_type != "python":
            errors.append(
                ValidationError(
                    code="INVALID_DEPLOYMENT_TYPE",
                    message=f"Expected deployment type 'python', got '{config.deployment_type}'",
                    remediation="Set deployment_type to 'python'",
                )
            )

        # Validate work pool exists (if API is available)
        if config.work_pool:
            try:
                if not self.deployment_api.validate_work_pool(config.work_pool):
                    warnings.append(
                        ValidationError(
                            code="WORK_POOL_NOT_FOUND",
                            message=f"Work pool '{config.work_pool}' may not exist",
                            remediation=f"Ensure work pool '{config.work_pool}' is created in Prefect",
                        )
                    )
            except Exception as e:
                warnings.append(
                    ValidationError(
                        code="WORK_POOL_VALIDATION_FAILED",
                        message=f"Could not validate work pool '{config.work_pool}': {e}",
                        remediation="Check Prefect server connectivity and work pool configuration",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _create_fallback_config(
        self, flow: FlowMetadata, environment: str
    ) -> DeploymentConfig:
        """Create fallback configuration when config manager is not available."""
        deployment_name = self._generate_deployment_name(flow, environment)

        return DeploymentConfig(
            flow_name=flow.name,
            deployment_name=deployment_name,
            environment=environment,
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint=f"{flow.module_path}:{flow.function_name}",
            parameters={},
            job_variables={
                "env": {
                    "PYTHONPATH": "/app",
                    "PREFECT_LOGGING_LEVEL": "INFO",
                    "ENVIRONMENT": environment.upper(),
                    "FLOW_NAME": flow.name,
                }
            },
            tags=[
                f"environment:{environment}",
                "type:python",
                f"flow:{flow.name}",
            ],
            description=f"{flow.name} flow deployed as Python in {environment}",
        )

    def _enhance_python_config(
        self, config: DeploymentConfig, flow: FlowMetadata, environment: str
    ):
        """Enhance deployment configuration with Python-specific settings."""
        # Ensure job_variables has env section
        if "env" not in config.job_variables:
            config.job_variables["env"] = {}

        # Add Python-specific environment variables
        python_env_vars = {
            "PYTHONPATH": "/app",
            "PREFECT_LOGGING_LEVEL": "INFO",
            "ENVIRONMENT": environment.upper(),
            "FLOW_NAME": flow.name,
            "DEPLOYMENT_TYPE": "python",
        }

        config.job_variables["env"].update(python_env_vars)

        # Add Python dependencies if available
        if flow.dependencies:
            config.job_variables["pip_install_requirements"] = flow.dependencies

        # Add flow-specific environment files
        if flow.env_files:
            config.job_variables["env_files"] = flow.env_files

        # Add Python-specific tags
        config.add_tag("runtime:python")
        if flow.dependencies:
            config.add_tag("has-dependencies")

    def get_deployment_template(self) -> dict[str, Any]:
        """Get the default Python deployment template."""
        return {
            "work_pool": "${environment.work_pools.python}",
            "job_variables": {
                "env": {
                    "PREFECT_API_URL": "${environment.prefect_api_url}",
                    "PYTHONPATH": "/app",
                    "PREFECT_LOGGING_LEVEL": "INFO",
                    "ENVIRONMENT": "${environment.name}",
                    "FLOW_NAME": "${flow.name}",
                    "DEPLOYMENT_TYPE": "python",
                }
            },
            "parameters": "${environment.default_parameters}",
            "tags": [
                "environment:${environment.name}",
                "type:python",
                "flow:${flow.name}",
                "runtime:python",
            ],
        }
