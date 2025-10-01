"""
CLI Commands

Command-line interface for the deployment system.
"""

from ..builders import DeploymentBuilder
from ..config import ConfigurationManager
from ..discovery import FlowDiscovery
from .ui_commands import UICLI


class DeploymentCLI:
    """Command-line interface for deployment management."""

    def __init__(self, api_url=None, ui_url=None):
        self.discovery = FlowDiscovery()
        self.config_manager = ConfigurationManager()
        self.builder = DeploymentBuilder(self.config_manager)
        self.ui_cli = UICLI(api_url, ui_url)

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

    # UI Integration Commands
    def check_ui_connectivity(self) -> dict:
        """Check Prefect UI connectivity and accessibility."""
        return self.ui_cli.check_ui_connectivity()

    def verify_deployment_in_ui(
        self, deployment_name: str, flow_name: str, timeout_seconds: int = 30
    ) -> dict:
        """Verify that a specific deployment appears in the Prefect UI."""
        return self.ui_cli.verify_deployment_in_ui(
            deployment_name, flow_name, timeout_seconds
        )

    def check_deployment_health(self, deployment_name: str, flow_name: str) -> dict:
        """Check comprehensive health of a deployment."""
        return self.ui_cli.check_deployment_health(deployment_name, flow_name)

    def get_deployment_status_report(self, flow_name: str = None) -> dict:
        """Generate comprehensive deployment status report."""
        return self.ui_cli.get_deployment_status_report(flow_name)

    def validate_deployments_ui(self, flow_name: str = None) -> dict:
        """Validate deployment visibility and correctness in UI."""
        return self.ui_cli.validate_deployments_ui(flow_name)

    def troubleshoot_connectivity(self) -> dict:
        """Run comprehensive connectivity troubleshooting."""
        return self.ui_cli.troubleshoot_connectivity()

    def troubleshoot_deployment_visibility(
        self, deployment_name: str, flow_name: str
    ) -> dict:
        """Troubleshoot why a specific deployment is not visible in UI."""
        return self.ui_cli.troubleshoot_deployment_visibility(
            deployment_name, flow_name
        )

    def wait_for_deployment_ready(
        self, deployment_name: str, flow_name: str, timeout_seconds: int = 60
    ) -> dict:
        """Wait for a deployment to become ready and healthy."""
        return self.ui_cli.wait_for_deployment_ready(
            deployment_name, flow_name, timeout_seconds
        )

    def list_deployments_with_ui_status(self, flow_name: str = None) -> dict:
        """List all deployments with their UI visibility status."""
        return self.ui_cli.list_deployments_with_ui_status(flow_name)

    def get_deployment_ui_url(self, deployment_name: str, flow_name: str) -> dict:
        """Get the direct URL to a deployment in the Prefect UI."""
        return self.ui_cli.get_deployment_ui_url(deployment_name, flow_name)
