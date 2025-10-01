"""
Deployment Builder

Main orchestrator for creating and managing deployments.
"""

from typing import Any, Optional

from ..config.deployment_config import DeploymentConfig
from ..discovery.metadata import FlowMetadata
from .docker_builder import DockerDeploymentCreator
from .python_builder import PythonDeploymentCreator


class DeploymentResult:
    """Result of a deployment operation."""

    def __init__(
        self, success: bool, message: str, deployments: list[dict[str, Any]] = None
    ):
        self.success = success
        self.message = message
        self.deployments = deployments or []


class CleanupResult:
    """Result of a cleanup operation."""

    def __init__(self, success: bool, message: str, cleaned_count: int = 0):
        self.success = success
        self.message = message
        self.cleaned_count = cleaned_count


class DeploymentBuilder:
    """Main deployment builder orchestrator."""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.python_builder = PythonDeploymentCreator(config_manager)
        self.docker_builder = DockerDeploymentCreator(config_manager)

    def create_python_deployment(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> DeploymentConfig:
        """Create a Python deployment for a flow."""
        return self.python_builder.create_deployment(flow, environment)

    def create_python_deployment_dict(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> dict[str, Any]:
        """Create a Python deployment configuration as dictionary."""
        return self.python_builder.create_deployment_dict(flow, environment)

    def deploy_python_to_prefect(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> Optional[str]:
        """Create and deploy a Python deployment to Prefect."""
        return self.python_builder.deploy_to_prefect(flow, environment)

    def create_docker_deployment(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> DeploymentConfig:
        """Create a Docker deployment for a flow."""
        return self.docker_builder.create_deployment(flow, environment)

    def create_docker_deployment_dict(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> dict[str, Any]:
        """Create a Docker deployment configuration as dictionary."""
        return self.docker_builder.create_deployment_dict(flow, environment)

    def deploy_docker_to_prefect(
        self, flow: FlowMetadata, environment: str = "development"
    ) -> Optional[str]:
        """Create and deploy a Docker deployment to Prefect."""
        return self.docker_builder.deploy_to_prefect(flow, environment)

    def create_all_deployments(
        self, flows: list[FlowMetadata], environment: str = "dev"
    ) -> DeploymentResult:
        """Create both Python and Docker deployments for all flows."""
        deployments = []
        errors = []

        for flow in flows:
            try:
                # Create Python deployment if supported
                if flow.supports_python_deployment:
                    python_deployment = self.create_python_deployment(flow, environment)
                    deployments.append(python_deployment)

                # Create Docker deployment if supported
                if flow.supports_docker_deployment:
                    docker_deployment = self.create_docker_deployment(flow, environment)
                    deployments.append(docker_deployment)

            except Exception as e:
                errors.append(f"Failed to create deployments for {flow.name}: {str(e)}")

        if errors:
            return DeploymentResult(
                success=False,
                message=f"Failed to create some deployments: {'; '.join(errors)}",
                deployments=deployments,
            )

        return DeploymentResult(
            success=True,
            message=f"Successfully created {len(deployments)} deployments",
            deployments=deployments,
        )

    def create_deployments_by_type(
        self, flows: list[FlowMetadata], deployment_type: str, environment: str = "dev"
    ) -> DeploymentResult:
        """Create deployments of a specific type for all flows."""
        deployments = []
        errors = []

        for flow in flows:
            try:
                if deployment_type == "python" and flow.supports_python_deployment:
                    deployment = self.create_python_deployment(flow, environment)
                    deployments.append(deployment)
                elif deployment_type == "docker" and flow.supports_docker_deployment:
                    deployment = self.create_docker_deployment(flow, environment)
                    deployments.append(deployment)
                else:
                    errors.append(
                        f"Flow {flow.name} does not support {deployment_type} deployment"
                    )

            except Exception as e:
                errors.append(
                    f"Failed to create {deployment_type} deployment for {flow.name}: {str(e)}"
                )

        if errors:
            return DeploymentResult(
                success=False,
                message=f"Failed to create some {deployment_type} deployments: {'; '.join(errors)}",
                deployments=deployments,
            )

        return DeploymentResult(
            success=True,
            message=f"Successfully created {len(deployments)} {deployment_type} deployments",
            deployments=deployments,
        )

    def validate_deployment(
        self, deployment_config: dict[str, Any], deployment_type: str
    ) -> bool:
        """Validate a deployment configuration."""
        # Convert dict to DeploymentConfig for validation
        config = DeploymentConfig(**deployment_config)

        if deployment_type == "python":
            return self.python_builder.validate_deployment_config(config)
        elif deployment_type == "docker":
            return self.docker_builder.validate_deployment_config(config)
        else:
            return False

    def cleanup_deployments(self, pattern: Optional[str] = None) -> CleanupResult:
        """Clean up existing deployments."""
        # This is a placeholder - actual implementation would interact with Prefect API
        # to remove deployments matching the pattern

        # For now, return a success result
        return CleanupResult(
            success=True, message="Deployment cleanup completed", cleaned_count=0
        )

    def get_deployment_summary(self, flows: list[FlowMetadata]) -> dict[str, Any]:
        """Get a summary of deployment capabilities for flows."""
        summary = {
            "total_flows": len(flows),
            "python_capable": len([f for f in flows if f.supports_python_deployment]),
            "docker_capable": len([f for f in flows if f.supports_docker_deployment]),
            "both_capable": len(
                [
                    f
                    for f in flows
                    if f.supports_python_deployment and f.supports_docker_deployment
                ]
            ),
            "invalid_flows": len([f for f in flows if not f.is_valid]),
            "flows": [],
        }

        for flow in flows:
            flow_info = {
                "name": flow.name,
                "path": flow.path,
                "supports_python": flow.supports_python_deployment,
                "supports_docker": flow.supports_docker_deployment,
                "is_valid": flow.is_valid,
                "validation_errors": flow.validation_errors,
            }
            summary["flows"].append(flow_info)

        return summary
