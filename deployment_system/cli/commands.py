"""
CLI Commands

Command-line interface for the deployment system.
"""

from ..builders import DeploymentBuilder
from ..config import ConfigurationManager
from ..discovery import FlowDiscovery


class DeploymentCLI:
    """Command-line interface for deployment management."""

    def __init__(self):
        self.discovery = FlowDiscovery()
        self.config_manager = ConfigurationManager()
        self.builder = DeploymentBuilder(self.config_manager)

    def discover_flows(self) -> list[dict]:
        """Discover and return flow information."""
        flows = self.discovery.discover_flows()
        return [
            {
                "name": flow.name,
                "path": flow.path,
                "supports_python": flow.supports_python_deployment,
                "supports_docker": flow.supports_docker_deployment,
                "is_valid": flow.is_valid,
                "errors": flow.validation_errors,
            }
            for flow in flows
        ]

    def build_deployments(self, environment: str = "development") -> dict:
        """Build all deployments for an environment."""
        flows = self.discovery.discover_valid_flows()
        result = self.builder.create_all_deployments(flows, environment)

        return {
            "success": result.success,
            "message": result.message,
            "deployment_count": len(result.deployments),
        }

    def list_environments(self) -> list[str]:
        """List available environments."""
        return self.config_manager.list_environments()

    def get_deployment_summary(self) -> dict:
        """Get deployment capability summary."""
        flows = self.discovery.discover_flows()
        return self.builder.get_deployment_summary(flows)

    def deploy_python_deployments(self, environment: str = "development") -> dict:
        """Deploy Python deployments to Prefect."""
        flows = self.discovery.discover_valid_flows()
        python_flows = [f for f in flows if f.supports_python_deployment]

        result = self.builder.create_deployments_by_type(
            python_flows, "python", environment
        )

        return {
            "success": result.success,
            "message": result.message,
            "deployment_count": len(result.deployments),
        }

    def deploy_docker_deployments(self, environment: str = "development") -> dict:
        """Deploy Docker deployments to Prefect."""
        flows = self.discovery.discover_valid_flows()
        docker_flows = [f for f in flows if f.supports_docker_deployment]

        result = self.builder.create_deployments_by_type(
            docker_flows, "docker", environment
        )

        return {
            "success": result.success,
            "message": result.message,
            "deployment_count": len(result.deployments),
        }

    def deploy_all_deployments(self, environment: str = "development") -> dict:
        """Deploy all deployments to Prefect."""
        flows = self.discovery.discover_valid_flows()
        result = self.builder.create_all_deployments(flows, environment)

        return {
            "success": result.success,
            "message": result.message,
            "deployment_count": len(result.deployments),
        }

    def clean_deployments(self, pattern: str = None) -> dict:
        """Clean up existing deployments."""
        result = self.builder.cleanup_deployments(pattern)

        return {
            "success": result.success,
            "message": result.message,
            "cleaned_count": result.cleaned_count,
        }

    def validate_flows(self) -> list[dict]:
        """Validate all discovered flows."""
        flows = self.discovery.discover_flows()
        return [
            {
                "name": flow.name,
                "is_valid": flow.is_valid,
                "errors": flow.validation_errors,
            }
            for flow in flows
        ]
