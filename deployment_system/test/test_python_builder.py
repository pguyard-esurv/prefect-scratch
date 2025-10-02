"""
Tests for Python Deployment Builder

Tests the PythonDeploymentCreator functionality.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Add deployment_system to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from deployment_system.builders.python_builder import PythonDeploymentCreator
from deployment_system.config.deployment_config import DeploymentConfig
from deployment_system.config.manager import ConfigurationManager
from deployment_system.discovery.metadata import FlowMetadata
from deployment_system.validation.validation_result import (
    ValidationResult,
)


@pytest.fixture
def sample_flow():
    """Create a sample flow metadata for testing."""
    return FlowMetadata(
        name="test-flow",
        path="/app/flows/test/workflow.py",
        module_path="flows.test.workflow",
        function_name="test_flow",
        dependencies=["pandas>=1.5.0", "requests>=2.28.0"],
        env_files=[".env.development"],
        is_valid=True,
        validation_errors=[],
        metadata={"description": "Test flow"},
    )


@pytest.fixture
def invalid_flow():
    """Create an invalid flow metadata for testing."""
    return FlowMetadata(
        name="invalid-flow",
        path="/app/flows/invalid/workflow.py",
        module_path="flows.invalid.workflow",
        function_name="invalid_flow",
        is_valid=False,
        validation_errors=["Missing required decorator"],
    )


@pytest.fixture
def config_manager():
    """Create a mock configuration manager."""
    manager = Mock(spec=ConfigurationManager)

    # Mock environment config
    env_config = Mock()
    env_config.work_pools = {"python": "test-agent-pool"}
    env_config.default_parameters = {"cleanup": True, "debug": False}
    env_config.prefect_api_url = "http://localhost:4200/api"

    manager.get_environment_config.return_value = env_config
    manager.generate_deployment_config.return_value = DeploymentConfig(
        flow_name="test-flow",
        deployment_name="test-flow-python-development",
        environment="development",
        deployment_type="python",
        work_pool="test-agent-pool",
        entrypoint="flows.test.workflow:test_flow",
        parameters={"cleanup": True, "debug": False},
        tags=["environment:development", "type:python", "flow:test-flow"],
    )

    return manager


class TestPythonDeploymentCreator:
    """Test cases for PythonDeploymentCreator."""

    def test_get_deployment_type(self):
        """Test that deployment type is correctly returned."""
        creator = PythonDeploymentCreator()
        assert creator.get_deployment_type() == "python"

    def test_create_deployment_with_config_manager(self, sample_flow, config_manager):
        """Test creating deployment with configuration manager."""
        creator = PythonDeploymentCreator(config_manager)

        config = creator.create_deployment(sample_flow, "development")

        assert isinstance(config, DeploymentConfig)
        assert config.flow_name == "test-flow"
        assert config.deployment_type == "python"
        assert config.environment == "development"
        assert config.entrypoint == "flows.test.workflow:test_flow"

        # Verify config manager was called
        config_manager.generate_deployment_config.assert_called_once_with(
            sample_flow, "python", "development"
        )

    def test_create_deployment_without_config_manager(self, sample_flow):
        """Test creating deployment without configuration manager (fallback)."""
        creator = PythonDeploymentCreator()

        config = creator.create_deployment(sample_flow, "development")

        assert isinstance(config, DeploymentConfig)
        assert config.flow_name == "test-flow"
        assert config.deployment_type == "python"
        assert config.environment == "development"
        assert config.entrypoint == "flows.test.workflow:test_flow"
        assert config.work_pool == "default-agent-pool"

    def test_create_deployment_invalid_flow(self, invalid_flow):
        """Test creating deployment with invalid flow raises error."""
        creator = PythonDeploymentCreator()

        with pytest.raises(ValueError, match="does not support Python deployment"):
            creator.create_deployment(invalid_flow, "development")

    def test_create_deployment_dict(self, sample_flow, config_manager):
        """Test creating deployment as dictionary."""
        creator = PythonDeploymentCreator(config_manager)

        deployment_dict = creator.create_deployment_dict(sample_flow, "development")

        assert isinstance(deployment_dict, dict)
        assert "name" in deployment_dict
        assert "flow_name" in deployment_dict
        assert "entrypoint" in deployment_dict
        assert "work_pool_name" in deployment_dict

    def test_validate_deployment_config_valid(self, config_manager):
        """Test validation of valid deployment configuration."""
        creator = PythonDeploymentCreator(config_manager)

        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="test-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        # Mock API validation
        creator.deployment_api.validate_work_pool = Mock(return_value=True)

        result = creator.validate_deployment_config(config)

        assert isinstance(result, ValidationResult)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_deployment_config_missing_fields(self):
        """Test validation with missing required fields."""
        creator = PythonDeploymentCreator()

        config = DeploymentConfig(
            flow_name="",  # Missing flow name
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="",  # Missing work pool
            entrypoint="",  # Missing entrypoint
        )

        result = creator.validate_deployment_config(config)

        assert not result.is_valid
        assert len(result.errors) >= 3  # At least 3 errors for missing fields

    def test_validate_deployment_config_invalid_entrypoint(self):
        """Test validation with invalid entrypoint format."""
        creator = PythonDeploymentCreator()

        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="test-pool",
            entrypoint="invalid_entrypoint_format",  # Missing colon
        )

        result = creator.validate_deployment_config(config)

        assert not result.is_valid
        error_codes = [error.code for error in result.errors]
        assert "INVALID_ENTRYPOINT_FORMAT" in error_codes

    def test_validate_deployment_config_wrong_type(self):
        """Test validation with wrong deployment type."""
        creator = PythonDeploymentCreator()

        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="docker",  # Wrong type
            work_pool="test-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        result = creator.validate_deployment_config(config)

        assert not result.is_valid
        error_codes = [error.code for error in result.errors]
        assert "INVALID_DEPLOYMENT_TYPE" in error_codes

    @patch("deployment_system.builders.python_builder.logger")
    def test_deploy_to_prefect_success(self, mock_logger, sample_flow, config_manager):
        """Test successful deployment to Prefect."""
        creator = PythonDeploymentCreator(config_manager)

        # Mock successful API call
        creator.deployment_api.create_or_update_deployment = Mock(
            return_value="deployment-123"
        )

        deployment_id = creator.deploy_to_prefect(sample_flow, "development")

        assert deployment_id == "deployment-123"
        mock_logger.info.assert_called()

    @patch("deployment_system.builders.python_builder.logger")
    def test_deploy_to_prefect_validation_failure(self, mock_logger, sample_flow):
        """Test deployment failure due to validation errors."""
        creator = PythonDeploymentCreator()

        # Create invalid flow that will fail validation
        invalid_flow = FlowMetadata(
            name="",  # Invalid name
            path="/app/flows/test/workflow.py",
            module_path="flows.test.workflow",
            function_name="test_flow",
            is_valid=True,  # Still marked as valid for Python deployment support
        )

        with pytest.raises(ValueError, match="does not support Python deployment"):
            creator.deploy_to_prefect(invalid_flow, "development")

    def test_enhance_python_config(self, sample_flow):
        """Test enhancement of Python configuration."""
        creator = PythonDeploymentCreator()

        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="test-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        creator._enhance_python_config(config, sample_flow, "development")

        # Check environment variables were added
        assert "env" in config.job_variables
        assert config.job_variables["env"]["PYTHONPATH"] == "/app"
        assert config.job_variables["env"]["ENVIRONMENT"] == "DEVELOPMENT"
        assert config.job_variables["env"]["FLOW_NAME"] == "test-flow"

        # Check dependencies were added
        assert (
            config.job_variables["pip_install_requirements"] == sample_flow.dependencies
        )

        # Check env files were added
        assert config.job_variables["env_files"] == sample_flow.env_files

        # Check tags were added
        assert "runtime:python" in config.tags

    def test_get_deployment_template(self):
        """Test getting deployment template."""
        creator = PythonDeploymentCreator()

        template = creator.get_deployment_template()

        assert isinstance(template, dict)
        assert "work_pool" in template
        assert "job_variables" in template
        assert "parameters" in template
        assert "tags" in template

    def test_create_fallback_config(self, sample_flow):
        """Test creating fallback configuration."""
        creator = PythonDeploymentCreator()

        config = creator._create_fallback_config(sample_flow, "development")

        assert isinstance(config, DeploymentConfig)
        assert config.flow_name == "test-flow"
        assert config.deployment_type == "python"
        assert config.environment == "development"
        assert config.work_pool == "default-agent-pool"
        assert config.entrypoint == "flows.test.workflow:test_flow"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
