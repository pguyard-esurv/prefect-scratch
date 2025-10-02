"""
Test utilities for mocking Prefect API and Docker operations.

Provides reusable mocks, fixtures, and utilities for testing the deployment system.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, List, Optional, Any

import pytest

from deployment_system.config.deployment_config import DeploymentConfig
from deployment_system.discovery.metadata import FlowMetadata
from deployment_system.validation.validation_result import (
    ValidationResult,
    ValidationError,
    ValidationWarning,
)


class MockPrefectClient:
    """Mock Prefect client for testing."""

    def __init__(self, api_url: str = "http://localhost:4200/api"):
        self.api_url = api_url
        self.deployments = {}
        self.work_pools = {"default-agent-pool", "docker-pool", "test-pool"}
        self.flows = {}
        self.is_connected = True

    async def create_deployment(self, deployment_data: Dict[str, Any]) -> Mock:
        """Mock deployment creation."""
        deployment_id = f"deployment-{len(self.deployments) + 1}"
        deployment = Mock()
        deployment.id = deployment_id
        deployment.name = deployment_data["name"]
        deployment.flow_name = deployment_data["flow_name"]
        deployment.entrypoint = deployment_data["entrypoint"]
        deployment.work_pool_name = deployment_data["work_pool_name"]
        deployment.parameters = deployment_data.get("parameters", {})
        deployment.job_variables = deployment_data.get("job_variables", {})
        deployment.tags = deployment_data.get("tags", [])
        deployment.description = deployment_data.get("description", "")

        self.deployments[deployment_id] = deployment
        return deployment

    async def update_deployment(
        self, deployment_id: str, updates: Dict[str, Any]
    ) -> Mock:
        """Mock deployment update."""
        if deployment_id not in self.deployments:
            raise Exception(f"Deployment {deployment_id} not found")

        deployment = self.deployments[deployment_id]
        for key, value in updates.items():
            setattr(deployment, key, value)

        return deployment

    async def read_deployment(self, deployment_id: str) -> Mock:
        """Mock deployment read."""
        if deployment_id not in self.deployments:
            raise Exception(f"Deployment {deployment_id} not found")
        return self.deployments[deployment_id]

    async def read_deployments(self, **filters) -> List[Mock]:
        """Mock deployments listing."""
        deployments = list(self.deployments.values())

        # Apply filters
        if "flow_name" in filters:
            deployments = [
                d for d in deployments if d.flow_name == filters["flow_name"]
            ]
        if "name_pattern" in filters:
            pattern = filters["name_pattern"]
            deployments = [d for d in deployments if pattern in d.name]

        return deployments

    async def delete_deployment(self, deployment_id: str) -> None:
        """Mock deployment deletion."""
        if deployment_id not in self.deployments:
            raise Exception(f"Deployment {deployment_id} not found")
        del self.deployments[deployment_id]

    async def read_work_pool(self, work_pool_name: str) -> Mock:
        """Mock work pool read."""
        if work_pool_name not in self.work_pools:
            raise Exception(f"Work pool {work_pool_name} not found")

        work_pool = Mock()
        work_pool.name = work_pool_name
        work_pool.type = "process" if "agent" in work_pool_name else "docker"
        return work_pool

    async def hello(self) -> Dict[str, str]:
        """Mock API hello endpoint."""
        if not self.is_connected:
            raise Exception("API not available")
        return {"message": "Hello from Prefect!"}

    def set_connected(self, connected: bool):
        """Set connection status for testing."""
        self.is_connected = connected

    def add_work_pool(self, name: str):
        """Add work pool for testing."""
        self.work_pools.add(name)

    def remove_work_pool(self, name: str):
        """Remove work pool for testing."""
        self.work_pools.discard(name)

    def clear_deployments(self):
        """Clear all deployments for testing."""
        self.deployments.clear()


class MockDockerClient:
    """Mock Docker client for testing."""

    def __init__(self):
        self.images = set()
        self.containers = {}
        self.is_available = True
        self.build_failures = set()

    def build_image(self, dockerfile_path: str, context_path: str, tag: str) -> bool:
        """Mock Docker image build."""
        if not self.is_available:
            raise Exception("Docker not available")

        if tag in self.build_failures:
            raise Exception(f"Build failed for {tag}")

        self.images.add(tag)
        return True

    def image_exists(self, tag: str) -> bool:
        """Mock Docker image existence check."""
        return tag in self.images

    def pull_image(self, tag: str) -> bool:
        """Mock Docker image pull."""
        if not self.is_available:
            raise Exception("Docker not available")

        self.images.add(tag)
        return True

    def run_container(self, image: str, **kwargs) -> str:
        """Mock Docker container run."""
        if not self.is_available:
            raise Exception("Docker not available")

        if image not in self.images:
            raise Exception(f"Image {image} not found")

        container_id = f"container-{len(self.containers) + 1}"
        self.containers[container_id] = {"image": image, "status": "running", **kwargs}
        return container_id

    def stop_container(self, container_id: str) -> bool:
        """Mock Docker container stop."""
        if container_id in self.containers:
            self.containers[container_id]["status"] = "stopped"
            return True
        return False

    def set_available(self, available: bool):
        """Set Docker availability for testing."""
        self.is_available = available

    def add_image(self, tag: str):
        """Add image for testing."""
        self.images.add(tag)

    def set_build_failure(self, tag: str):
        """Set build failure for specific tag."""
        self.build_failures.add(tag)

    def clear_build_failures(self):
        """Clear all build failures."""
        self.build_failures.clear()


class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def create_flow_metadata(
        name: str = "test-flow",
        supports_docker: bool = False,
        is_valid: bool = True,
        **kwargs,
    ) -> FlowMetadata:
        """Create FlowMetadata for testing."""
        defaults = {
            "path": f"/app/flows/{name}/workflow.py",
            "module_path": f"flows.{name.replace('-', '_')}.workflow",
            "function_name": f"{name.replace('-', '_')}_function",
            "dependencies": ["prefect>=2.0.0"],
            "dockerfile_path": (
                f"/app/flows/{name}/Dockerfile" if supports_docker else None
            ),
            "env_files": [f".env.development"],
            "is_valid": is_valid,
            "validation_errors": [] if is_valid else ["Test validation error"],
            "metadata": {"description": f"Test flow {name}"},
        }
        defaults.update(kwargs)

        return FlowMetadata(name=name, **defaults)

    @staticmethod
    def create_deployment_config(
        flow_name: str = "test-flow",
        deployment_type: str = "python",
        environment: str = "development",
        **kwargs,
    ) -> DeploymentConfig:
        """Create DeploymentConfig for testing."""
        defaults = {
            "deployment_name": f"{flow_name}-{deployment_type}-{environment}",
            "work_pool": (
                "default-agent-pool" if deployment_type == "python" else "docker-pool"
            ),
            "entrypoint": f"flows.{flow_name.replace('-', '_')}.workflow:{flow_name.replace('-', '_')}_function",
            "parameters": {"test_param": "test_value"},
            "job_variables": {"env": {"ENVIRONMENT": environment.upper()}},
            "tags": [f"env:{environment}", f"type:{deployment_type}"],
            "description": f"Test {deployment_type} deployment for {flow_name}",
        }
        defaults.update(kwargs)

        return DeploymentConfig(
            flow_name=flow_name,
            deployment_type=deployment_type,
            environment=environment,
            **defaults,
        )

    @staticmethod
    def create_validation_result(
        is_valid: bool = True, error_count: int = 0, warning_count: int = 0
    ) -> ValidationResult:
        """Create ValidationResult for testing."""
        errors = []
        warnings = []

        for i in range(error_count):
            errors.append(
                ValidationError(
                    code=f"TEST_ERROR_{i}",
                    message=f"Test error {i}",
                    remediation=f"Fix test error {i}",
                )
            )

        for i in range(warning_count):
            warnings.append(
                ValidationWarning(
                    code=f"TEST_WARNING_{i}",
                    message=f"Test warning {i}",
                    suggestion=f"Consider fixing test warning {i}",
                )
            )

        return ValidationResult(
            is_valid=is_valid and error_count == 0, errors=errors, warnings=warnings
        )

    @staticmethod
    def create_project_structure(base_dir: Path) -> Dict[str, Path]:
        """Create a complete project structure for testing."""
        # Create flows directory
        flows_dir = base_dir / "flows"
        flows_dir.mkdir(exist_ok=True)

        # Create config directory
        config_dir = base_dir / "config"
        config_dir.mkdir(exist_ok=True)

        # Create sample flows
        flow_dirs = {}

        # Python-only flow
        python_flow_dir = flows_dir / "python_flow"
        python_flow_dir.mkdir(exist_ok=True)

        python_workflow = python_flow_dir / "workflow.py"
        python_workflow.write_text(
            """
from prefect import flow, task

@task
def python_task():
    return "Python task result"

@flow(name="python_flow", description="Python-only flow")
def python_flow():
    result = python_task()
    return result
"""
        )

        python_env = python_flow_dir / ".env.development"
        python_env.write_text("PYTHON_CONFIG=development")

        flow_dirs["python_flow"] = python_flow_dir

        # Docker-capable flow
        docker_flow_dir = flows_dir / "docker_flow"
        docker_flow_dir.mkdir(exist_ok=True)

        docker_workflow = docker_flow_dir / "workflow.py"
        docker_workflow.write_text(
            """
from prefect import flow, task

@task
def docker_task():
    return "Docker task result"

@flow(name="docker_flow", description="Docker-capable flow")
def docker_flow():
    result = docker_task()
    return result
"""
        )

        docker_dockerfile = docker_flow_dir / "Dockerfile"
        docker_dockerfile.write_text(
            """
FROM python:3.11-slim
WORKDIR /app
COPY . .
CMD ["python", "-m", "prefect", "worker", "start"]
"""
        )

        docker_env = docker_flow_dir / ".env.development"
        docker_env.write_text("DOCKER_CONFIG=development")

        flow_dirs["docker_flow"] = docker_flow_dir

        # Configuration files
        deployment_config = config_dir / "deployment_config.yaml"
        deployment_config.write_text(
            """
environments:
  development:
    prefect_api_url: "http://localhost:4200/api"
    work_pools:
      python: "default-agent-pool"
      docker: "docker-pool"
    default_parameters:
      debug: true
    resource_limits:
      memory: "512Mi"
      cpu: "0.5"
    default_tags:
      - "env:development"

  production:
    prefect_api_url: "http://prod-prefect:4200/api"
    work_pools:
      python: "prod-agent-pool"
      docker: "prod-docker-pool"
    default_parameters:
      debug: false
    resource_limits:
      memory: "2Gi"
      cpu: "2.0"
    default_tags:
      - "env:production"
"""
        )

        return {
            "flows_dir": flows_dir,
            "config_dir": config_dir,
            "deployment_config": deployment_config,
            **flow_dirs,
        }


# Pytest fixtures
@pytest.fixture
def mock_prefect_client():
    """Provide a mock Prefect client."""
    return MockPrefectClient()


@pytest.fixture
def mock_docker_client():
    """Provide a mock Docker client."""
    return MockDockerClient()


@pytest.fixture
def sample_flows():
    """Provide sample flow metadata for testing."""
    return [
        TestDataFactory.create_flow_metadata("python-flow", supports_docker=False),
        TestDataFactory.create_flow_metadata("docker-flow", supports_docker=True),
        TestDataFactory.create_flow_metadata("invalid-flow", is_valid=False),
    ]


@pytest.fixture
def sample_deployment_configs():
    """Provide sample deployment configurations for testing."""
    return [
        TestDataFactory.create_deployment_config("test-flow-1", "python"),
        TestDataFactory.create_deployment_config("test-flow-2", "docker"),
    ]


@pytest.fixture
def temp_project_structure():
    """Provide a temporary project structure for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        base_path = Path(temp_dir)
        structure = TestDataFactory.create_project_structure(base_path)
        yield structure


@pytest.fixture
def mock_prefect_api():
    """Mock the entire Prefect API integration."""
    with patch("deployment_system.api.prefect_client.get_client") as mock_get_client:
        mock_client = MockPrefectClient()
        mock_get_client.return_value = mock_client

        with patch(
            "deployment_system.api.deployment_api.DeploymentAPI"
        ) as mock_api_class:
            mock_api = Mock()
            mock_api.check_api_connectivity.return_value = True
            mock_api.validate_work_pool.return_value = True
            mock_api.create_or_update_deployment.side_effect = (
                lambda config: f"deployment-{config.flow_name}"
            )
            mock_api.get_deployment.return_value = Mock(
                id="test-deployment", name="test-deployment"
            )
            mock_api.list_deployments.return_value = []
            mock_api.delete_deployment.return_value = True
            mock_api_class.return_value = mock_api

            yield mock_api


@pytest.fixture
def mock_docker_operations():
    """Mock Docker operations."""
    with patch("subprocess.run") as mock_run:
        # Mock successful Docker operations by default
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""

        yield mock_run


class MockValidationMixin:
    """Mixin for mocking validation operations."""

    @staticmethod
    def mock_successful_validation():
        """Mock successful validation."""
        return ValidationResult(is_valid=True, errors=[], warnings=[])

    @staticmethod
    def mock_failed_validation(error_message: str = "Validation failed"):
        """Mock failed validation."""
        return ValidationResult(
            is_valid=False,
            errors=[
                ValidationError("VALIDATION_ERROR", error_message, "Fix the error")
            ],
            warnings=[],
        )

    @staticmethod
    def mock_validation_with_warnings(warning_message: str = "Validation warning"):
        """Mock validation with warnings."""
        return ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[
                ValidationWarning(
                    "VALIDATION_WARNING", warning_message, "Consider fixing"
                )
            ],
        )


class TestAssertions:
    """Custom assertions for testing deployment system."""

    @staticmethod
    def assert_deployment_config_valid(config: DeploymentConfig):
        """Assert that deployment configuration is valid."""
        assert config.flow_name, "Flow name is required"
        assert config.deployment_name, "Deployment name is required"
        assert config.environment, "Environment is required"
        assert config.deployment_type in ["python", "docker"], "Invalid deployment type"
        assert config.work_pool, "Work pool is required"
        assert config.entrypoint, "Entrypoint is required"

    @staticmethod
    def assert_flow_metadata_valid(flow: FlowMetadata):
        """Assert that flow metadata is valid."""
        assert flow.name, "Flow name is required"
        assert flow.path, "Flow path is required"
        assert flow.module_path, "Module path is required"
        assert flow.function_name, "Function name is required"

    @staticmethod
    def assert_validation_result_structure(result: ValidationResult):
        """Assert that validation result has proper structure."""
        assert hasattr(
            result, "is_valid"
        ), "ValidationResult must have is_valid attribute"
        assert hasattr(result, "errors"), "ValidationResult must have errors attribute"
        assert hasattr(
            result, "warnings"
        ), "ValidationResult must have warnings attribute"
        assert isinstance(result.errors, list), "Errors must be a list"
        assert isinstance(result.warnings, list), "Warnings must be a list"

    @staticmethod
    def assert_deployment_result_success(result, expected_count: Optional[int] = None):
        """Assert that deployment result indicates success."""
        assert (
            result.success
        ), f"Deployment should succeed, but got errors: {result.errors}"
        if expected_count is not None:
            assert (
                len(result.deployments) == expected_count
            ), f"Expected {expected_count} deployments, got {len(result.deployments)}"

    @staticmethod
    def assert_flows_discovered(flows: List[FlowMetadata], expected_names: List[str]):
        """Assert that expected flows were discovered."""
        discovered_names = [f.name for f in flows]
        for expected_name in expected_names:
            assert (
                expected_name in discovered_names
            ), f"Expected flow '{expected_name}' not discovered"


# Context managers for testing
class MockEnvironment:
    """Context manager for mocking the entire deployment environment."""

    def __init__(self, prefect_available: bool = True, docker_available: bool = True):
        self.prefect_available = prefect_available
        self.docker_available = docker_available
        self.patches = []

    def __enter__(self):
        # Mock Prefect API
        if self.prefect_available:
            prefect_patch = patch("deployment_system.api.prefect_client.get_client")
            mock_get_client = prefect_patch.start()
            mock_get_client.return_value = MockPrefectClient()
            self.patches.append(prefect_patch)
        else:
            prefect_patch = patch("deployment_system.api.prefect_client.get_client")
            mock_get_client = prefect_patch.start()
            mock_get_client.side_effect = Exception("Prefect API not available")
            self.patches.append(prefect_patch)

        # Mock Docker operations
        if self.docker_available:
            docker_patch = patch("subprocess.run")
            mock_run = docker_patch.start()
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            self.patches.append(docker_patch)
        else:
            docker_patch = patch("subprocess.run")
            mock_run = docker_patch.start()
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Docker not available"
            self.patches.append(docker_patch)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for patch_obj in self.patches:
            patch_obj.stop()


# Performance testing utilities
class PerformanceTimer:
    """Simple performance timer for testing."""

    def __init__(self):
        self.start_time = None
        self.end_time = None

    def __enter__(self):
        import time

        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time

        self.end_time = time.time()

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    def assert_under_threshold(self, threshold_seconds: float):
        """Assert that operation completed under threshold."""
        assert (
            self.elapsed < threshold_seconds
        ), f"Operation took {self.elapsed:.2f}s, expected under {threshold_seconds}s"


# Test data generators
def generate_large_flow_set(count: int = 100) -> List[FlowMetadata]:
    """Generate a large set of flows for performance testing."""
    flows = []
    for i in range(count):
        supports_docker = i % 3 == 0  # Every third flow supports Docker
        is_valid = i % 10 != 9  # Every tenth flow is invalid

        flow = TestDataFactory.create_flow_metadata(
            name=f"flow-{i:03d}", supports_docker=supports_docker, is_valid=is_valid
        )
        flows.append(flow)

    return flows


def generate_complex_deployment_configs(flow_count: int = 50) -> List[DeploymentConfig]:
    """Generate complex deployment configurations for testing."""
    configs = []
    environments = ["development", "staging", "production"]
    deployment_types = ["python", "docker"]

    for i in range(flow_count):
        for env in environments:
            for dep_type in deployment_types:
                if dep_type == "docker" and i % 3 != 0:
                    continue  # Skip Docker for flows that don't support it

                config = TestDataFactory.create_deployment_config(
                    flow_name=f"flow-{i:03d}",
                    deployment_type=dep_type,
                    environment=env,
                    parameters={"batch_size": 100 + i, "timeout": 300 + i * 10},
                    job_variables={
                        "env": {
                            "FLOW_ID": str(i),
                            "ENVIRONMENT": env.upper(),
                            "DEPLOYMENT_TYPE": dep_type.upper(),
                        }
                    },
                )
                configs.append(config)

    return configs
