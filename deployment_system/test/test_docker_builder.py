"""
Tests for Docker Deployment Builder

Tests the Docker deployment creation and validation functionality.
"""

from unittest.mock import Mock, patch

import pytest

from deployment_system.builders.docker_builder import DockerDeploymentCreator
from deployment_system.config.deployment_config import DeploymentConfig
from deployment_system.discovery.metadata import FlowMetadata
from deployment_system.validation.validation_result import (
    ValidationError,
    ValidationResult,
)


class TestDockerDeploymentCreator:
    """Test cases for DockerDeploymentCreator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.docker_builder = DockerDeploymentCreator()

        # Create a mock flow with Docker support
        self.mock_flow = FlowMetadata(
            name="test_flow",
            path="/app/flows/test_flow/workflow.py",
            module_path="flows.test_flow.workflow",
            function_name="test_flow_function",
            dockerfile_path="/app/flows/test_flow/Dockerfile",
            env_files=["/app/flows/test_flow/.env.development"],
            dependencies=["pandas", "requests"],
        )

    def test_get_deployment_type(self):
        """Test deployment type identifier."""
        assert self.docker_builder.get_deployment_type() == "docker"

    def test_create_deployment_basic(self):
        """Test basic Docker deployment creation."""
        config = self.docker_builder.create_deployment(self.mock_flow, "development")

        assert isinstance(config, DeploymentConfig)
        assert config.flow_name == "test_flow"
        assert config.deployment_type == "docker"
        assert config.environment == "development"
        assert "test_flow-worker:latest" in config.job_variables.get("image", "")

    def test_create_deployment_dict(self):
        """Test Docker deployment creation as dictionary."""
        config_dict = self.docker_builder.create_deployment_dict(
            self.mock_flow, "development"
        )

        assert isinstance(config_dict, dict)
        assert config_dict["flow_name"] == "test_flow"
        assert "job_variables" in config_dict

    def test_validate_deployment_config_valid(self):
        """Test validation of valid Docker deployment configuration."""
        config = DeploymentConfig(
            flow_name="test_flow",
            deployment_name="test_flow-docker-development",
            environment="development",
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint="flows.test_flow.workflow:test_flow_function",
            job_variables={
                "image": "test_flow-worker:latest",
                "env": {"PREFECT_API_URL": "http://localhost:4200/api"},
            },
        )

        result = self.docker_builder.validate_deployment_config(config)
        assert result.is_valid

    def test_validate_deployment_config_missing_image(self):
        """Test validation fails when Docker image is missing."""
        config = DeploymentConfig(
            flow_name="test_flow",
            deployment_name="test_flow-docker-development",
            environment="development",
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint="flows.test_flow.workflow:test_flow_function",
            job_variables={},  # Missing image
        )

        result = self.docker_builder.validate_deployment_config(config)
        assert not result.is_valid
        assert any(error.code == "MISSING_DOCKER_IMAGE" for error in result.errors)

    def test_validate_deployment_config_invalid_entrypoint(self):
        """Test validation fails with invalid entrypoint format."""
        config = DeploymentConfig(
            flow_name="test_flow",
            deployment_name="test_flow-docker-development",
            environment="development",
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint="invalid_entrypoint_format",  # Missing colon
            job_variables={"image": "test_flow-worker:latest"},
        )

        result = self.docker_builder.validate_deployment_config(config)
        assert not result.is_valid
        assert any(error.code == "INVALID_ENTRYPOINT_FORMAT" for error in result.errors)

    @patch("subprocess.run")
    def test_validate_docker_image_exists(self, mock_subprocess):
        """Test Docker image validation when image exists."""
        mock_subprocess.return_value.returncode = 0

        result = self.docker_builder.validate_docker_image("test_flow-worker:latest")
        assert result.is_valid

    @patch("subprocess.run")
    def test_validate_docker_image_not_found(self, mock_subprocess):
        """Test Docker image validation when image doesn't exist."""
        mock_subprocess.return_value.returncode = 1

        result = self.docker_builder.validate_docker_image("nonexistent:latest")
        assert result.is_valid  # Should be valid but with warnings
        assert len(result.warnings) > 0
        assert any(
            warning.code == "DOCKER_IMAGE_NOT_FOUND" for warning in result.warnings
        )

    @patch("subprocess.run")
    @patch("pathlib.Path.exists")
    def test_build_docker_image_success(self, mock_exists, mock_subprocess):
        """Test successful Docker image building."""
        mock_exists.return_value = True  # Mock Dockerfile exists
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stderr = ""

        # Mock Dockerfile validation
        with patch.object(
            self.docker_builder.docker_validator, "validate_dockerfile"
        ) as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True, errors=[], warnings=[]
            )

            result = self.docker_builder.build_docker_image(
                self.mock_flow, "test_flow-worker:latest"
            )
            assert result is True

    @patch("subprocess.run")
    def test_build_docker_image_failure(self, mock_subprocess):
        """Test Docker image building failure."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = "Build failed"

        # Mock Dockerfile validation
        with patch.object(
            self.docker_builder.docker_validator, "validate_dockerfile"
        ) as mock_validate:
            mock_validate.return_value = ValidationResult(
                is_valid=True, errors=[], warnings=[]
            )

            result = self.docker_builder.build_docker_image(
                self.mock_flow, "test_flow-worker:latest"
            )
            assert result is False

    def test_enhance_docker_config(self):
        """Test Docker configuration enhancement."""
        config = DeploymentConfig(
            flow_name="test_flow",
            deployment_name="test_flow-docker-development",
            environment="development",
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint="flows.test_flow.workflow:test_flow_function",
            job_variables={},
        )

        self.docker_builder._enhance_docker_config(
            config, self.mock_flow, "development"
        )

        # Check that Docker-specific configurations were added
        assert "image" in config.job_variables
        assert "env" in config.job_variables
        assert "volumes" in config.job_variables
        assert "networks" in config.job_variables
        assert "resources" in config.job_variables
        assert "healthcheck" in config.job_variables

        # Check environment variables
        env_vars = config.job_variables["env"]
        assert env_vars["DEPLOYMENT_TYPE"] == "docker"
        assert env_vars["FLOW_NAME"] == "test_flow"
        assert env_vars["ENVIRONMENT"] == "DEVELOPMENT"

    def test_get_resource_limits(self):
        """Test resource limit configuration for different environments."""
        dev_resources = self.docker_builder._get_resource_limits("development")
        staging_resources = self.docker_builder._get_resource_limits("staging")
        prod_resources = self.docker_builder._get_resource_limits("production")

        # Development should have lower limits
        assert dev_resources["memory"] == "512M"
        assert dev_resources["cpus"] == "0.5"

        # Production should have higher limits
        assert prod_resources["memory"] == "2G"
        assert prod_resources["cpus"] == "2.0"

        # Staging should be in between
        assert staging_resources["memory"] == "1G"
        assert staging_resources["cpus"] == "1.0"

    def test_get_deployment_template(self):
        """Test deployment template structure."""
        template = self.docker_builder.get_deployment_template()

        assert isinstance(template, dict)
        assert "work_pool" in template
        assert "job_variables" in template
        assert "parameters" in template
        assert "tags" in template

        # Check job_variables structure
        job_vars = template["job_variables"]
        assert "image" in job_vars
        assert "env" in job_vars
        assert "volumes" in job_vars
        assert "networks" in job_vars

    def test_flow_without_dockerfile(self):
        """Test handling of flow without Dockerfile."""
        flow_without_docker = FlowMetadata(
            name="python_only_flow",
            path="/app/flows/python_only/workflow.py",
            module_path="flows.python_only.workflow",
            function_name="python_flow_function",
            dockerfile_path=None,  # No Dockerfile
        )

        with pytest.raises(ValueError, match="does not support Docker deployment"):
            self.docker_builder.create_deployment(flow_without_docker, "development")

    @patch.object(DockerDeploymentCreator, "validate_deployment_config")
    @patch.object(DockerDeploymentCreator, "create_deployment")
    def test_deploy_to_prefect_success(self, mock_create, mock_validate):
        """Test successful deployment to Prefect."""
        # Mock configuration creation
        mock_config = Mock(spec=DeploymentConfig)
        mock_create.return_value = mock_config

        # Mock validation success
        mock_validate.return_value = ValidationResult(
            is_valid=True, errors=[], warnings=[]
        )

        # Mock API success
        with patch.object(
            self.docker_builder.deployment_api, "create_or_update_deployment"
        ) as mock_api:
            mock_api.return_value = "deployment-123"

            result = self.docker_builder.deploy_to_prefect(
                self.mock_flow, "development"
            )
            assert result == "deployment-123"

    @patch.object(DockerDeploymentCreator, "validate_deployment_config")
    @patch.object(DockerDeploymentCreator, "create_deployment")
    def test_deploy_to_prefect_validation_failure(self, mock_create, mock_validate):
        """Test deployment failure due to validation errors."""
        # Mock configuration creation
        mock_config = Mock(spec=DeploymentConfig)
        mock_create.return_value = mock_config

        # Mock validation failure
        validation_error = ValidationError(
            code="TEST_ERROR",
            message="Test validation error",
            remediation="Fix the test error",
        )
        mock_validate.return_value = ValidationResult(
            is_valid=False, errors=[validation_error], warnings=[]
        )

        with pytest.raises(ValueError, match="Invalid deployment configuration"):
            self.docker_builder.deploy_to_prefect(self.mock_flow, "development")
