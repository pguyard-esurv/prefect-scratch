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
