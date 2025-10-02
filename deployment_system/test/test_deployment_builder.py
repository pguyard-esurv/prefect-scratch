"""
Unit tests for deployment builder components.

Tests the DeploymentBuilder, BaseBuilder, and related functionality.
"""

from unittest.mock import Mock, patch

import pytest

from deployment_system.builders.base_builder import BaseDeploymentBuilder
from deployment_system.builders.deployment_builder import DeploymentBuilder
from deployment_system.builders.docker_builder import DockerDeploymentCreator
from deployment_system.builders.python_builder import PythonDeploymentCreator
from deployment_system.config.deployment_config import DeploymentConfig
from deployment_system.discovery.metadata import FlowMetadata
from deployment_system.validation.validation_result import ValidationResult


class TestBaseDeploymentBuilder:
    """Test BaseDeploymentBuilder abstract functionality."""

    def test_base_builder_abstract_methods(self):
        """Test that BaseDeploymentBuilder cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseDeploymentBuilder()

    def test_base_builder_subclass_implementation(self):
        """Test that subclasses must implement abstract methods."""

        class IncompleteBuilder(BaseDeploymentBuilder):
            pass

        with pytest.raises(TypeError):
            IncompleteBuilder()

        class CompleteBuilder(BaseDeploymentBuilder):
            def get_deployment_type(self):
                return "test"

            def create_deployment(self, flow_metadata, environment):
                return {
                    "name": f"{flow_metadata.name}-test-{environment}",
                    "flow_name": flow_metadata.name,
                    "entrypoint": f"{flow_metadata.module_path}:{flow_metadata.function_name}",
                }

            def validate_deployment_config(self, config):
                return ValidationResult(is_valid=True, errors=[], warnings=[])

        # Should work without errors
        builder = CompleteBuilder()
        assert builder.get_deployment_type() == "test"


class TestDeploymentBuilder:
    """Test DeploymentBuilder orchestrator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.deployment_builder = DeploymentBuilder()

        # Create sample flows
        self.python_flow = FlowMetadata(
            name="python-flow",
            path="/app/flows/python/workflow.py",
            module_path="flows.python.workflow",
            function_name="python_flow",
            dependencies=["prefect>=2.0.0"],
            dockerfile_path=None,
            env_files=[".env.development"],
            is_valid=True,
            validation_errors=[],
            metadata={},
        )

        self.docker_flow = FlowMetadata(
            name="docker-flow",
            path="/app/flows/docker/workflow.py",
            module_path="flows.docker.workflow",
            function_name="docker_flow",
            dependencies=["prefect>=2.0.0"],
            dockerfile_path="/app/flows/docker/Dockerfile",
            env_files=[".env.development"],
            is_valid=True,
            validation_errors=[],
            metadata={},
        )

        self.invalid_flow = FlowMetadata(
            name="invalid-flow",
            path="/app/flows/invalid/workflow.py",
            module_path="flows.invalid.workflow",
            function_name="invalid_flow",
            dependencies=[],
            dockerfile_path=None,
            env_files=[],
            is_valid=False,
            validation_errors=["Syntax error"],
            metadata={},
        )

    def test_deployment_builder_initialization(self):
        """Test DeploymentBuilder initialization."""
        builder = DeploymentBuilder()

        assert hasattr(builder, "python_builder")
        assert hasattr(builder, "docker_builder")
        assert isinstance(builder.python_builder, PythonDeploymentCreator)
        assert isinstance(builder.docker_builder, DockerDeploymentCreator)

    def test_create_python_deployment(self):
        """Test creating Python deployment."""
        config = self.deployment_builder.create_python_deployment(
            self.python_flow, "development"
        )

        assert isinstance(config, DeploymentConfig)
        assert config.flow_name == "python-flow"
        assert config.deployment_type == "python"
        assert config.environment == "development"

    def test_create_docker_deployment(self):
        """Test creating Docker deployment."""
        config = self.deployment_builder.create_docker_deployment(
            self.docker_flow, "development"
        )

        assert isinstance(config, DeploymentConfig)
        assert config.flow_name == "docker-flow"
        assert config.deployment_type == "docker"
        assert config.environment == "development"

    def test_create_docker_deployment_unsupported_flow(self):
        """Test creating Docker deployment for flow without Docker support."""
        with pytest.raises(ValueError, match="does not support Docker deployment"):
            self.deployment_builder.create_docker_deployment(
                self.python_flow, "development"
            )

    def test_create_python_deployment_invalid_flow(self):
        """Test creating Python deployment for invalid flow."""
        with pytest.raises(ValueError, match="does not support Python deployment"):
            self.deployment_builder.create_python_deployment(
                self.invalid_flow, "development"
            )

    def test_create_all_deployments_single_flow(self):
        """Test creating all deployments for a single flow."""
        flows = [self.docker_flow]

        result = self.deployment_builder.create_all_deployments(flows, "development")

        assert result.success is True
        assert len(result.deployments) == 2  # Python + Docker

        deployment_types = [dep.deployment_type for dep in result.deployments]
        assert "python" in deployment_types
        assert "docker" in deployment_types

    def test_create_all_deployments_multiple_flows(self):
        """Test creating all deployments for multiple flows."""
        flows = [self.python_flow, self.docker_flow]

        result = self.deployment_builder.create_all_deployments(flows, "development")

        assert result.success is True
        # python_flow: Python only, docker_flow: Python + Docker
        assert len(result.deployments) == 3

    def test_create_all_deployments_with_invalid_flow(self):
        """Test creating deployments with invalid flows."""
        flows = [self.python_flow, self.invalid_flow]

        result = self.deployment_builder.create_all_deployments(flows, "development")

        # Should succeed for valid flows, skip invalid ones
        assert len(result.deployments) == 1  # Only python_flow

    def test_create_deployments_by_type_python(self):
        """Test creating only Python deployments."""
        flows = [self.python_flow, self.docker_flow]

        result = self.deployment_builder.create_deployments_by_type(
            flows, "python", "development"
        )

        assert result.success is True
        assert len(result.deployments) == 2  # Both flows support Python
        assert all(dep.deployment_type == "python" for dep in result.deployments)

    def test_create_deployments_by_type_docker(self):
        """Test creating only Docker deployments."""
        flows = [self.python_flow, self.docker_flow]

        result = self.deployment_builder.create_deployments_by_type(
            flows, "docker", "development"
        )

        # Should succeed for docker_flow, fail for python_flow
        assert not result.success
        assert len(result.deployments) == 1  # Only docker_flow
        assert result.deployments[0].deployment_type == "docker"

    def test_create_deployments_by_type_invalid_type(self):
        """Test creating deployments with invalid type."""
        flows = [self.python_flow]

        # The actual implementation doesn't raise an error for invalid types,
        # it just returns a result with errors
        result = self.deployment_builder.create_deployments_by_type(
            flows, "invalid", "development"
        )
        assert not result.success

    def test_get_deployment_summary(self):
        """Test getting deployment summary."""
        flows = [self.python_flow, self.docker_flow, self.invalid_flow]

        summary = self.deployment_builder.get_deployment_summary(flows)

        assert summary["total_flows"] == 3
        assert summary["python_capable"] == 2  # python_flow, docker_flow
        assert summary["docker_capable"] == 1  # docker_flow only
        assert summary["both_capable"] == 1  # docker_flow only
        assert summary["invalid_flows"] == 1  # invalid_flow

        # Check individual flow info
        flow_infos = {flow["name"]: flow for flow in summary["flows"]}

        assert flow_infos["python-flow"]["supports_python"] is True
        assert flow_infos["python-flow"]["supports_docker"] is False

        assert flow_infos["docker-flow"]["supports_python"] is True
        assert flow_infos["docker-flow"]["supports_docker"] is True

        assert flow_infos["invalid-flow"]["supports_python"] is False
        assert flow_infos["invalid-flow"]["supports_docker"] is False

    @patch.object(PythonDeploymentCreator, "deploy_to_prefect")
    def test_deploy_python_to_prefect(self, mock_deploy):
        """Test deploying Python deployment to Prefect."""
        mock_deploy.return_value = "deployment-123"

        result = self.deployment_builder.deploy_python_to_prefect(
            self.python_flow, "development"
        )

        assert result == "deployment-123"
        mock_deploy.assert_called_once_with(self.python_flow, "development")

    @patch.object(DockerDeploymentCreator, "deploy_to_prefect")
    def test_deploy_docker_to_prefect(self, mock_deploy):
        """Test deploying Docker deployment to Prefect."""
        mock_deploy.return_value = "deployment-456"

        result = self.deployment_builder.deploy_docker_to_prefect(
            self.docker_flow, "development"
        )

        assert result == "deployment-456"
        mock_deploy.assert_called_once_with(self.docker_flow, "development")

    # Note: deploy_all_to_prefect method doesn't exist in actual implementation
    # These tests would need to be implemented if the method is added

    def test_create_deployment_dict_python(self):
        """Test creating Python deployment as dictionary."""
        deployment_dict = self.deployment_builder.create_python_deployment_dict(
            self.python_flow, "development"
        )

        assert isinstance(deployment_dict, dict)
        assert deployment_dict["flow_name"] == "python-flow"
        assert "entrypoint" in deployment_dict
        assert "work_pool_name" in deployment_dict

    def test_create_deployment_dict_docker(self):
        """Test creating Docker deployment as dictionary."""
        deployment_dict = self.deployment_builder.create_docker_deployment_dict(
            self.docker_flow, "development"
        )

        assert isinstance(deployment_dict, dict)
        assert deployment_dict["flow_name"] == "docker-flow"
        assert "entrypoint" in deployment_dict
        assert "work_pool_name" in deployment_dict

    # Note: validate_deployment_configs and get_supported_deployment_types
    # methods don't exist in actual implementation

    def test_builder_configuration_with_config_manager(self):
        """Test DeploymentBuilder with configuration manager."""
        mock_config_manager = Mock()

        builder = DeploymentBuilder(config_manager=mock_config_manager)

        assert builder.python_builder.config_manager == mock_config_manager
        assert builder.docker_builder.config_manager == mock_config_manager


class TestDeploymentResult:
    """Test DeploymentResult model."""

    def test_deployment_result_success(self):
        """Test successful deployment result."""
        from deployment_system.builders.deployment_builder import DeploymentResult

        deployments = [
            DeploymentConfig(
                flow_name="test-flow",
                deployment_name="test-deployment",
                environment="development",
                deployment_type="python",
                work_pool="test-pool",
                entrypoint="flows.test.workflow:test_flow",
            )
        ]

        result = DeploymentResult(
            success=True,
            message="Test success",
            deployments=deployments,
        )

        assert result.success is True
        assert len(result.deployments) == 1

    def test_deployment_result_failure(self):
        """Test failed deployment result."""
        from deployment_system.builders.deployment_builder import DeploymentResult

        result = DeploymentResult(
            success=False,
            message="Deployment failed; Configuration invalid",
            deployments=[],
        )

        assert result.success is False
        assert len(result.deployments) == 0

    def test_deployment_result_partial_success(self):
        """Test partial success deployment result."""
        from deployment_system.builders.deployment_builder import DeploymentResult

        deployments = [
            DeploymentConfig(
                flow_name="successful-flow",
                deployment_name="successful-deployment",
                environment="development",
                deployment_type="python",
                work_pool="test-pool",
                entrypoint="flows.successful.workflow:successful_flow",
            )
        ]

        result = DeploymentResult(
            success=False,  # Overall failure due to some errors
            message="One deployment failed",
            deployments=deployments,
        )

        assert result.success is False
        assert len(result.deployments) == 1  # Some succeeded


@pytest.fixture
def sample_flows():
    """Create sample flows for testing."""
    return [
        FlowMetadata(
            name="python-only-flow",
            path="/app/flows/python_only/workflow.py",
            module_path="flows.python_only.workflow",
            function_name="python_only_flow",
            dependencies=["prefect>=2.0.0"],
            dockerfile_path=None,
            env_files=[".env.development"],
            is_valid=True,
            validation_errors=[],
            metadata={},
        ),
        FlowMetadata(
            name="docker-capable-flow",
            path="/app/flows/docker_capable/workflow.py",
            module_path="flows.docker_capable.workflow",
            function_name="docker_capable_flow",
            dependencies=["prefect>=2.0.0", "pandas>=1.5.0"],
            dockerfile_path="/app/flows/docker_capable/Dockerfile",
            env_files=[".env.development", ".env.production"],
            is_valid=True,
            validation_errors=[],
            metadata={"description": "Docker-capable flow"},
        ),
        FlowMetadata(
            name="invalid-flow",
            path="/app/flows/invalid/workflow.py",
            module_path="flows.invalid.workflow",
            function_name="invalid_flow",
            dependencies=[],
            dockerfile_path=None,
            env_files=[],
            is_valid=False,
            validation_errors=["Missing @flow decorator"],
            metadata={},
        ),
    ]


class TestDeploymentBuilderIntegration:
    """Integration tests for DeploymentBuilder."""

    def test_end_to_end_deployment_creation(self, sample_flows):
        """Test complete deployment creation workflow."""
        builder = DeploymentBuilder()

        result = builder.create_all_deployments(sample_flows, "development")

        # Should create deployments for valid flows
        valid_flows = [f for f in sample_flows if f.is_valid]
        expected_deployments = sum(
            1 + (1 if f.supports_docker_deployment else 0) for f in valid_flows
        )

        assert len(result.deployments) == expected_deployments
        assert result.success is True

    def test_deployment_type_filtering(self, sample_flows):
        """Test filtering deployments by type."""
        builder = DeploymentBuilder()

        # Test Python deployments only
        python_result = builder.create_deployments_by_type(
            sample_flows, "python", "development"
        )

        valid_flows = [f for f in sample_flows if f.is_valid]
        assert len(python_result.deployments) == len(valid_flows)

        # Test Docker deployments only
        docker_result = builder.create_deployments_by_type(
            sample_flows, "docker", "development"
        )

        docker_capable_flows = [f for f in valid_flows if f.supports_docker_deployment]
        assert len(docker_result.deployments) == len(docker_capable_flows)

    def test_deployment_summary_accuracy(self, sample_flows):
        """Test accuracy of deployment summary."""
        builder = DeploymentBuilder()

        summary = builder.get_deployment_summary(sample_flows)

        assert summary["total_flows"] == len(sample_flows)

        valid_flows = [f for f in sample_flows if f.is_valid]
        assert summary["python_capable"] == len(valid_flows)

        docker_flows = [f for f in valid_flows if f.supports_docker_deployment]
        assert summary["docker_capable"] == len(docker_flows)

        both_capable = [f for f in valid_flows if f.supports_docker_deployment]
        assert summary["both_capable"] == len(both_capable)

    # Note: deploy_all_to_prefect method doesn't exist in actual implementation
