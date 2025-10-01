"""
Base Deployment Builder

Abstract base class for deployment builders.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..config.deployment_config import DeploymentConfig
from ..discovery.metadata import FlowMetadata


class BaseDeploymentBuilder(ABC):
    """Abstract base class for deployment builders."""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager

    @abstractmethod
    def create_deployment(
        self, flow: FlowMetadata, environment: str = "dev"
    ) -> dict[str, Any]:
        """Create a deployment configuration for the given flow."""
        pass

    @abstractmethod
    def validate_deployment_config(self, config: DeploymentConfig) -> bool:
        """Validate a deployment configuration."""
        pass

    @abstractmethod
    def get_deployment_type(self) -> str:
        """Get the deployment type identifier."""
        pass

    def _generate_deployment_name(self, flow: FlowMetadata, environment: str) -> str:
        """Generate a standardized deployment name."""
        return f"{flow.name}-{self.get_deployment_type()}-{environment}"

    def _get_base_deployment_config(
        self, flow: FlowMetadata, environment: str
    ) -> dict[str, Any]:
        """Get base deployment configuration common to all deployment types."""
        return {
            "name": self._generate_deployment_name(flow, environment),
            "flow_name": flow.name,
            "tags": [
                f"environment:{environment}",
                f"type:{self.get_deployment_type()}",
                f"flow:{flow.name}",
            ],
            "description": f"{flow.name} flow deployed as {self.get_deployment_type()} in {environment}",
            "version": "1.0.0",
            "parameters": {},
            "job_variables": {},
        }

    def _merge_environment_config(
        self, base_config: dict[str, Any], environment: str
    ) -> dict[str, Any]:
        """Merge environment-specific configuration."""
        if self.config_manager:
            env_config = self.config_manager.get_environment_config(environment)
            if env_config:
                # Merge environment-specific parameters
                if hasattr(env_config, "default_parameters"):
                    base_config["parameters"].update(env_config.default_parameters)

                # Set work pool from environment config
                if hasattr(env_config, "work_pools"):
                    deployment_type = self.get_deployment_type()
                    if deployment_type in env_config.work_pools:
                        base_config["work_pool"] = env_config.work_pools[
                            deployment_type
                        ]

        return base_config
