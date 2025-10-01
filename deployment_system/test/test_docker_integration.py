"""
Docker Builder Integration Tests

Tests the integration of Docker builder with the deployment system.
"""

from unittest.mock import patch

from deployment_system.builders.deployment_builder import DeploymentBuilder
from deployment_system.discovery.metadata import FlowMetadata


class TestDockerBuilderIntegration:
    """Test Docker builder integration with the deployment system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deployment_builder = DeploymentBuilder()

        # Create a mock flow with Docker support
        self.docker_flow = FlowMetadata(
            name="docker_flow",
            path="/app/flows/docker_flow/workflow.py",
            module_path="flows.docker_flow.workflow",
            function_name="docker_flow_function",
            dockerfile_path="/app/flows/docker_flow/Dockerfile",
            env_files=["/app/flows/docker_flow/.env.development"],
        )

        # Create a mock flow without Docker support
        self.python_only_flow = FlowMetadata(
            name="python_flow",
            path="/app/flows/python_flow/workflow.py",
            module_path="flows.python_flow.workflow",
            function_name="python_flow_function",
            dockerfile_path=None,  # No Docker support
        )

    def test_deployment_builder_has_docker_builder(self):
        """Test that DeploymentBuilder includes Docker builder."""
        assert hasattr(self.deployment_builder, "docker_builder")
        assert self.deployment_builder.docker_builder is not None

    def test_create_docker_deployment(self):
        """Test creating Docker deployment through DeploymentBuilder."""
        config = self.deployment_builder.create_docker_deployment(
            self.docker_flow, "development"
        )

        assert config.flow_name == "docker_flow"
        assert config.deployment_type == "docker"
        assert config.environment == "development"

    def test_create_docker_deployment_dict(self):
        """Test creating Docker deployment as dictionary."""
        config_dict = self.deployment_builder.create_docker_deployment_dict(
            self.docker_flow, "development"
        )

        assert isinstance(config_dict, dict)
        assert config_dict["flow_name"] == "docker_flow"

    def test_create_all_deployments_with_docker_flow(self):
        """Test creating all deployments for a Docker-capable flow."""
        flows = [self.docker_flow]

        result = self.deployment_builder.create_all_deployments(flows, "development")

        assert result.success
        assert len(result.deployments) == 2  # Python + Docker

        # Check that both deployment types are created
        deployment_types = [dep.deployment_type for dep in result.deployments]
        assert "python" in deployment_types
        assert "docker" in deployment_types

    def test_create_all_deployments_mixed_flows(self):
        """Test creating deployments for mixed flow types."""
        flows = [self.docker_flow, self.python_only_flow]

        result = self.deployment_builder.create_all_deployments(flows, "development")

        assert result.success
        # docker_flow: Python + Docker, python_only_flow: Python only
        assert len(result.deployments) == 3

    def test_create_deployments_by_type_docker(self):
        """Test creating only Docker deployments."""
        flows = [self.docker_flow, self.python_only_flow]

        result = self.deployment_builder.create_deployments_by_type(
            flows, "docker", "development"
        )

        # Should succeed but with errors for flows without Docker support
        assert not result.success  # Because python_only_flow doesn't support Docker
        assert len(result.deployments) == 1  # Only docker_flow
        assert result.deployments[0].deployment_type == "docker"

    def test_create_deployments_by_type_python(self):
        """Test creating only Python deployments."""
        flows = [self.docker_flow, self.python_only_flow]

        result = self.deployment_builder.create_deployments_by_type(
            flows, "python", "development"
        )

        assert result.success
        assert len(result.deployments) == 2  # Both flows support Python
        assert all(dep.deployment_type == "python" for dep in result.deployments)

    def test_get_deployment_summary_with_docker_flows(self):
        """Test deployment summary includes Docker capabilities."""
        flows = [self.docker_flow, self.python_only_flow]

        summary = self.deployment_builder.get_deployment_summary(flows)

        assert summary["total_flows"] == 2
        assert summary["python_capable"] == 2  # Both support Python
        assert summary["docker_capable"] == 1  # Only docker_flow supports Docker
        assert summary["both_capable"] == 1  # Only docker_flow supports both

        # Check individual flow info
        flow_infos = {flow["name"]: flow for flow in summary["flows"]}

        assert flow_infos["docker_flow"]["supports_docker"] is True
        assert flow_infos["docker_flow"]["supports_python"] is True

        assert flow_infos["python_flow"]["supports_docker"] is False
        assert flow_infos["python_flow"]["supports_python"] is True

    @patch.object(DeploymentBuilder, "deploy_docker_to_prefect")
    def test_deploy_docker_to_prefect_integration(self, mock_deploy):
        """Test Docker deployment to Prefect through DeploymentBuilder."""
        mock_deploy.return_value = "deployment-123"

        result = self.deployment_builder.deploy_docker_to_prefect(
            self.docker_flow, "development"
        )

        assert result == "deployment-123"
        mock_deploy.assert_called_once_with(self.docker_flow, "development")

    def test_docker_builder_type_consistency(self):
        """Test that Docker builder type is consistent."""
        docker_builder = self.deployment_builder.docker_builder

        assert docker_builder.get_deployment_type() == "docker"

        # Create a deployment and verify type
        config = docker_builder.create_deployment(self.docker_flow, "development")
        assert config.deployment_type == "docker"

    def test_docker_template_structure(self):
        """Test Docker deployment template structure."""
        docker_builder = self.deployment_builder.docker_builder
        template = docker_builder.get_deployment_template()

        # Verify template has required Docker-specific fields
        assert "work_pool" in template
        assert "job_variables" in template

        job_vars = template["job_variables"]
        assert "image" in job_vars
        assert "volumes" in job_vars
        assert "networks" in job_vars
        assert "env" in job_vars

        # Verify Docker-specific environment variables
        env_vars = job_vars["env"]
        assert "DEPLOYMENT_TYPE" in env_vars
        assert "CONTAINER_ENVIRONMENT" in env_vars
        assert "CONTAINER_FLOW_NAME" in env_vars
