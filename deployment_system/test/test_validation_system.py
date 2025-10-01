"""
Tests for the comprehensive validation system.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from deployment_system.config.deployment_config import DeploymentConfig
from deployment_system.discovery.metadata import FlowMetadata
from deployment_system.validation.comprehensive_validator import ComprehensiveValidator
from deployment_system.validation.deployment_validator import DeploymentValidator
from deployment_system.validation.docker_validator import DockerValidator
from deployment_system.validation.flow_validator import FlowValidator
from deployment_system.validation.validation_result import (
    ValidationError,
    ValidationResult,
    ValidationWarning,
)


class TestValidationResult:
    """Test ValidationResult functionality."""

    def test_validation_result_creation(self):
        """Test creating validation results."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        assert result.is_valid
        assert not result.has_errors
        assert not result.has_warnings
        assert result.error_count == 0
        assert result.warning_count == 0

    def test_validation_result_with_errors(self):
        """Test validation result with errors."""
        error = ValidationError(
            code="TEST_ERROR",
            message="Test error message",
            remediation="Fix the test error",
        )
        result = ValidationResult(is_valid=False, errors=[error], warnings=[])

        assert not result.is_valid
        assert result.has_errors
        assert result.error_count == 1
        assert result.get_summary() == "Invalid: 1 error(s), 0 warning(s)"

    def test_validation_result_merge(self):
        """Test merging validation results."""
        result1 = ValidationResult(is_valid=True, errors=[], warnings=[])
        result2 = ValidationResult(
            is_valid=False,
            errors=[ValidationError("ERROR", "Test error", remediation="Fix it")],
            warnings=[
                ValidationWarning("WARNING", "Test warning", suggestion="Consider this")
            ],
        )

        result1.merge(result2)

        assert not result1.is_valid
        assert result1.error_count == 1
        assert result1.warning_count == 1


class TestFlowValidator:
    """Test FlowValidator functionality."""

    def test_validate_flow_syntax_valid(self):
        """Test validating valid Python syntax."""
        validator = FlowValidator()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
from prefect import flow

@flow
def test_flow():
    return "Hello, World!"
"""
            )
            f.flush()

            result = validator.validate_flow_syntax(f.name)
            assert result.is_valid
            assert not result.has_errors

    def test_validate_flow_syntax_invalid(self):
        """Test validating invalid Python syntax."""
        validator = FlowValidator()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
from prefect import flow

@flow
def test_flow(
    return "Invalid syntax"
"""
            )
            f.flush()

            result = validator.validate_flow_syntax(f.name)
            assert not result.is_valid
            assert result.has_errors
            assert any(error.code == "SYNTAX_ERROR" for error in result.errors)

    def test_validate_flow_dependencies(self):
        """Test validating flow dependencies."""
        validator = FlowValidator()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
from prefect import flow
import nonexistent_module

@flow
def test_flow():
    return "Hello, World!"
"""
            )
            f.flush()

            result = validator.validate_flow_dependencies(f.name)
            # Should have warnings about unresolved imports
            assert result.has_warnings or result.has_errors

    def test_validate_flow_structure(self):
        """Test validating flow structure."""
        validator = FlowValidator()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
from prefect import flow, task

@task
def my_task():
    return "task result"

@flow
def test_flow():
    result = my_task()
    return result
"""
            )
            f.flush()

            result = validator.validate_flow_structure(f.name)
            assert result.is_valid


class TestDeploymentValidator:
    """Test DeploymentValidator functionality."""

    def test_validate_valid_python_deployment(self):
        """Test validating valid Python deployment configuration."""
        validator = DeploymentValidator()

        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        result = validator.validate_deployment_config(config)
        assert result.is_valid

    def test_validate_valid_docker_deployment(self):
        """Test validating valid Docker deployment configuration."""
        validator = DeploymentValidator()

        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint="flows.test.workflow:test_flow",
            job_variables={"image": "test-flow:latest"},
        )

        result = validator.validate_deployment_config(config)
        assert result.is_valid

    def test_validate_missing_required_fields(self):
        """Test validation with missing required fields."""
        validator = DeploymentValidator()

        config = DeploymentConfig(
            flow_name="",  # Missing required field
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        result = validator.validate_deployment_config(config)
        assert not result.is_valid
        assert any(error.code == "MISSING_REQUIRED_FIELD" for error in result.errors)

    def test_validate_invalid_entrypoint(self):
        """Test validation with invalid entrypoint format."""
        validator = DeploymentValidator()

        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint="invalid_entrypoint_format",  # Missing colon
        )

        result = validator.validate_deployment_config(config)
        assert not result.is_valid
        assert any(error.code == "INVALID_ENTRYPOINT_FORMAT" for error in result.errors)

    def test_validate_invalid_schedule(self):
        """Test validation with invalid schedule."""
        validator = DeploymentValidator()

        config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint="flows.test.workflow:test_flow",
            schedule="invalid cron format",
        )

        result = validator.validate_deployment_config(config)
        # Should have errors or warnings about invalid schedule
        assert result.has_errors or result.has_warnings


class TestDockerValidator:
    """Test DockerValidator functionality."""

    def test_validate_dockerfile_valid(self):
        """Test validating valid Dockerfile."""
        validator = DockerValidator()

        with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False) as f:
            f.write(
                """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "main.py"]
"""
            )
            f.flush()

            result = validator.validate_dockerfile(f.name)
            assert result.is_valid

    def test_validate_dockerfile_missing_from(self):
        """Test validating Dockerfile missing FROM instruction."""
        validator = DockerValidator()

        with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False) as f:
            f.write(
                """
WORKDIR /app
COPY . .
CMD ["python", "main.py"]
"""
            )
            f.flush()

            result = validator.validate_dockerfile(f.name)
            assert not result.is_valid
            assert any(
                error.code == "DOCKERFILE_MISSING_FROM" for error in result.errors
            )

    def test_validate_dockerfile_not_found(self):
        """Test validating non-existent Dockerfile."""
        validator = DockerValidator()

        result = validator.validate_dockerfile("/nonexistent/Dockerfile")
        assert not result.is_valid
        assert any(error.code == "DOCKERFILE_NOT_FOUND" for error in result.errors)

    @patch("subprocess.run")
    def test_validate_docker_image_exists(self, mock_run):
        """Test validating Docker image existence."""
        validator = DockerValidator()

        # Mock successful docker inspect
        mock_run.return_value.returncode = 0
        result = validator.validate_docker_image_exists("test-image:latest")
        assert result.is_valid

        # Mock failed docker inspect
        mock_run.return_value.returncode = 1
        result = validator.validate_docker_image_exists("nonexistent-image:latest")
        assert result.has_warnings

    @patch("subprocess.run")
    def test_validate_docker_build(self, mock_run):
        """Test validating Docker build process."""
        validator = DockerValidator()

        with tempfile.TemporaryDirectory() as temp_dir:
            dockerfile_path = Path(temp_dir) / "Dockerfile"
            dockerfile_path.write_text("FROM python:3.11-slim\n")

            # Mock successful docker info and build
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""

            result = validator.validate_docker_build(
                str(dockerfile_path), temp_dir, "test-image:latest"
            )
            assert result.is_valid


class TestComprehensiveValidator:
    """Test ComprehensiveValidator functionality."""

    def test_validate_flow_for_deployment(self):
        """Test comprehensive flow and deployment validation."""
        validator = ComprehensiveValidator()

        # Create mock flow metadata
        flow_metadata = FlowMetadata(
            name="test-flow",
            path="/tmp/test_flow.py",
            module_path="flows.test.workflow",
            function_name="test_flow",
            dependencies=[],
            dockerfile_path=None,
            env_files=[],
            is_valid=True,
            validation_errors=[],
            metadata={},
        )

        # Create deployment config
        deployment_config = DeploymentConfig(
            flow_name="test-flow",
            deployment_name="test-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint="flows.test.workflow:test_flow",
        )

        # Mock the flow file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                """
from prefect import flow

@flow
def test_flow():
    return "Hello, World!"
"""
            )
            f.flush()
            flow_metadata.path = f.name

            result = validator.validate_flow_for_deployment(
                flow_metadata, deployment_config
            )
            # Should be valid or have only warnings
            assert result.is_valid or not result.has_errors

    def test_validate_multiple_deployments(self):
        """Test validating multiple deployments."""
        validator = ComprehensiveValidator()

        # Create test deployments
        deployments = []
        for i in range(2):
            flow_metadata = FlowMetadata(
                name=f"test-flow-{i}",
                path=f"/tmp/test_flow_{i}.py",
                module_path=f"flows.test.workflow_{i}",
                function_name=f"test_flow_{i}",
                dependencies=[],
                dockerfile_path=None,
                env_files=[],
                is_valid=True,
                validation_errors=[],
                metadata={},
            )

            deployment_config = DeploymentConfig(
                flow_name=f"test-flow-{i}",
                deployment_name=f"test-deployment-{i}",
                environment="development",
                deployment_type="python",
                work_pool="default-agent-pool",
                entrypoint=f"flows.test.workflow_{i}:test_flow_{i}",
            )

            deployments.append((flow_metadata, deployment_config))

        results = validator.validate_multiple_deployments(deployments)
        assert len(results) == 2
        assert all(isinstance(result, ValidationResult) for result in results.values())

    def test_generate_validation_report(self):
        """Test generating validation report."""
        validator = ComprehensiveValidator()

        # Create mock validation results
        results = {
            "test-flow/deployment": ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[
                    ValidationWarning(
                        "TEST_WARNING", "Test warning", suggestion="Test suggestion"
                    )
                ],
            ),
            "test-flow-2/deployment": ValidationResult(
                is_valid=False,
                errors=[
                    ValidationError(
                        "TEST_ERROR", "Test error", remediation="Fix the error"
                    )
                ],
                warnings=[],
            ),
        }

        report = validator.generate_validation_report(results)

        assert "# Deployment Validation Report" in report
        assert "Total deployments: 2" in report
        assert "Valid deployments: 1" in report
        assert "TEST_WARNING" in report
        assert "TEST_ERROR" in report


@pytest.fixture
def sample_flow_file():
    """Create a sample flow file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
from prefect import flow, task

@task
def sample_task():
    return "task result"

@flow
def sample_flow():
    result = sample_task()
    return result
"""
        )
        f.flush()
        yield f.name


@pytest.fixture
def sample_dockerfile():
    """Create a sample Dockerfile for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False) as f:
        f.write(
            """
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "-m", "prefect", "worker", "start", "--pool", "default"]
"""
        )
        f.flush()
        yield f.name


class TestIntegrationValidation:
    """Integration tests for the validation system."""

    def test_end_to_end_validation(self, sample_flow_file):
        """Test end-to-end validation workflow."""
        validator = ComprehensiveValidator()

        # Create flow metadata
        flow_metadata = FlowMetadata(
            name="sample-flow",
            path=sample_flow_file,
            module_path="flows.sample.workflow",
            function_name="sample_flow",
            dependencies=["prefect"],
            dockerfile_path=None,
            env_files=[],
            is_valid=True,
            validation_errors=[],
            metadata={},
        )

        # Create deployment config
        deployment_config = DeploymentConfig(
            flow_name="sample-flow",
            deployment_name="sample-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint="flows.sample.workflow:sample_flow",
        )

        # Validate
        result = validator.validate_flow_for_deployment(
            flow_metadata, deployment_config
        )

        # Should be valid or have only warnings
        if not result.is_valid:
            print("Validation errors:")
            for error in result.errors:
                print(f"  - {error}")

        assert result.is_valid or not result.has_errors

    def test_docker_deployment_validation(self, sample_flow_file, sample_dockerfile):
        """Test Docker deployment validation."""
        validator = ComprehensiveValidator()

        # Create flow metadata with Dockerfile
        flow_metadata = FlowMetadata(
            name="sample-flow",
            path=sample_flow_file,
            module_path="flows.sample.workflow",
            function_name="sample_flow",
            dependencies=["prefect"],
            dockerfile_path=sample_dockerfile,
            env_files=[],
            is_valid=True,
            validation_errors=[],
            metadata={},
        )

        # Create Docker deployment config
        deployment_config = DeploymentConfig(
            flow_name="sample-flow",
            deployment_name="sample-docker-deployment",
            environment="development",
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint="flows.sample.workflow:sample_flow",
            job_variables={
                "image": "sample-flow:latest",
                "env": {"PREFECT_API_URL": "http://localhost:4200/api"},
            },
        )

        # Validate
        result = validator.validate_flow_for_deployment(
            flow_metadata, deployment_config
        )

        # Should be valid or have only warnings (Docker image might not exist)
        if not result.is_valid:
            print("Docker validation errors:")
            for error in result.errors:
                print(f"  - {error}")

        # At minimum, should not have critical errors
        critical_errors = [
            e
            for e in result.errors
            if e.code not in ["DOCKER_IMAGE_NOT_FOUND", "DOCKER_NOT_AVAILABLE"]
        ]
        assert len(critical_errors) == 0
