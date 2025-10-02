"""
Pytest configuration and shared fixtures for deployment system tests.

Provides common fixtures, configuration, and test utilities.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Configure asyncio for pytest
pytest_plugins = ("pytest_asyncio",)

# Add deployment_system to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from deployment_system.test.test_utilities import (
    MockPrefectClient,
    MockDockerClient,
    TestDataFactory,
    MockEnvironment,
)


# Test configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "docker: mark test as requiring Docker")
    config.addinivalue_line("markers", "prefect: mark test as requiring Prefect API")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file names
        if "test_flow_discovery" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_deployment_builder" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "test_prefect_api_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.prefect)
        elif "test_docker_integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.docker)
        elif "test_end_to_end" in item.nodeid:
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.slow)
        elif "test_validation_system" in item.nodeid:
            item.add_marker(pytest.mark.unit)


# Environment fixtures
@pytest.fixture(scope="session")
def test_environment():
    """Set up test environment variables."""
    original_env = os.environ.copy()

    # Set test environment variables
    os.environ.update(
        {
            "PREFECT_API_URL": "http://localhost:4200/api",
            "ENVIRONMENT": "test",
            "PYTHONPATH": "/app",
            "LOG_LEVEL": "DEBUG",
        }
    )

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_workspace():
    """Provide a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        yield workspace


@pytest.fixture
def sample_project(temp_workspace):
    """Create a complete sample project structure."""
    return TestDataFactory.create_project_structure(temp_workspace)


# Mock fixtures
@pytest.fixture
def mock_prefect_client():
    """Provide a mock Prefect client."""
    return MockPrefectClient()


@pytest.fixture
def mock_docker_client():
    """Provide a mock Docker client."""
    return MockDockerClient()


@pytest.fixture
def mock_prefect_environment():
    """Mock the entire Prefect environment."""
    with MockEnvironment(prefect_available=True, docker_available=True) as env:
        yield env


@pytest.fixture
def mock_offline_environment():
    """Mock an offline environment (no Prefect or Docker)."""
    with MockEnvironment(prefect_available=False, docker_available=False) as env:
        yield env


# Data fixtures
@pytest.fixture
def sample_flows():
    """Provide sample flow metadata."""
    return [
        TestDataFactory.create_flow_metadata("sample-flow-1", supports_docker=False),
        TestDataFactory.create_flow_metadata("sample-flow-2", supports_docker=True),
        TestDataFactory.create_flow_metadata("sample-flow-3", supports_docker=True),
    ]


@pytest.fixture
def invalid_flows():
    """Provide invalid flow metadata for error testing."""
    return [
        TestDataFactory.create_flow_metadata("invalid-flow-1", is_valid=False),
        TestDataFactory.create_flow_metadata("invalid-flow-2", is_valid=False),
    ]


@pytest.fixture
def mixed_flows(sample_flows, invalid_flows):
    """Provide a mix of valid and invalid flows."""
    return sample_flows + invalid_flows


@pytest.fixture
def sample_deployment_configs():
    """Provide sample deployment configurations."""
    return [
        TestDataFactory.create_deployment_config("flow-1", "python", "development"),
        TestDataFactory.create_deployment_config("flow-2", "docker", "development"),
        TestDataFactory.create_deployment_config("flow-3", "python", "production"),
    ]


# Component fixtures
@pytest.fixture
def flow_discovery():
    """Provide a FlowDiscovery instance."""
    from deployment_system.discovery.discovery import FlowDiscovery

    return FlowDiscovery()


@pytest.fixture
def deployment_builder():
    """Provide a DeploymentBuilder instance."""
    from deployment_system.builders.deployment_builder import DeploymentBuilder

    return DeploymentBuilder()


@pytest.fixture
def config_manager(sample_project):
    """Provide a ConfigurationManager instance."""
    from deployment_system.config.manager import ConfigurationManager

    return ConfigurationManager(str(sample_project["config_dir"]))


@pytest.fixture
def comprehensive_validator():
    """Provide a ComprehensiveValidator instance."""
    from deployment_system.validation.comprehensive_validator import (
        ComprehensiveValidator,
    )

    return ComprehensiveValidator()


# Performance testing fixtures
@pytest.fixture
def large_flow_set():
    """Provide a large set of flows for performance testing."""
    from deployment_system.test.test_utilities import generate_large_flow_set

    return generate_large_flow_set(50)  # Smaller set for CI


@pytest.fixture
def performance_threshold():
    """Provide performance thresholds for testing."""
    return {
        "flow_discovery": 5.0,  # seconds
        "deployment_creation": 10.0,  # seconds
        "validation": 3.0,  # seconds
    }


# Skip conditions
def pytest_runtest_setup(item):
    """Set up test run conditions and skip tests based on markers."""
    # Skip Docker tests if Docker is not available
    if item.get_closest_marker("docker"):
        try:
            import subprocess

            result = subprocess.run(
                ["docker", "--version"], capture_output=True, timeout=5
            )
            if result.returncode != 0:
                pytest.skip("Docker not available")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Docker not available")

    # Skip Prefect tests if running in CI without Prefect server
    if item.get_closest_marker("prefect"):
        if os.environ.get("CI") and not os.environ.get("PREFECT_SERVER_AVAILABLE"):
            pytest.skip("Prefect server not available in CI")

    # Skip slow tests if SKIP_SLOW is set
    if item.get_closest_marker("slow"):
        if os.environ.get("SKIP_SLOW"):
            pytest.skip("Skipping slow tests")


# Test reporting
@pytest.fixture(autouse=True)
def test_logging(caplog):
    """Configure test logging."""
    import logging

    caplog.set_level(logging.DEBUG)
    yield caplog


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Clean up after each test."""
    yield

    # Clean up any temporary files or state
    # This runs after each test
    pass


# Session-scoped fixtures for expensive setup
@pytest.fixture(scope="session")
def test_database():
    """Set up test database (if needed)."""
    # This would set up a test database for integration tests
    # For now, we'll just yield None since we're mocking
    yield None


@pytest.fixture(scope="session")
def test_prefect_server():
    """Set up test Prefect server (if needed)."""
    # This would set up a test Prefect server for integration tests
    # For now, we'll just yield None since we're mocking
    yield None


# Parametrized fixtures for testing multiple scenarios
@pytest.fixture(params=["development", "staging", "production"])
def environment_name(request):
    """Parametrized fixture for testing different environments."""
    return request.param


@pytest.fixture(params=["python", "docker"])
def deployment_type(request):
    """Parametrized fixture for testing different deployment types."""
    return request.param


@pytest.fixture(params=[True, False])
def docker_support(request):
    """Parametrized fixture for testing with/without Docker support."""
    return request.param


# Custom assertions
class TestAssertions:
    """Custom assertions for deployment system tests."""

    @staticmethod
    def assert_flow_valid(flow):
        """Assert that a flow is valid."""
        assert flow.name, "Flow must have a name"
        assert flow.path, "Flow must have a path"
        assert flow.module_path, "Flow must have a module path"
        assert flow.function_name, "Flow must have a function name"
        assert flow.is_valid, "Flow must be valid"

    @staticmethod
    def assert_deployment_valid(deployment):
        """Assert that a deployment configuration is valid."""
        assert deployment.flow_name, "Deployment must have a flow name"
        assert deployment.deployment_name, "Deployment must have a deployment name"
        assert deployment.environment, "Deployment must have an environment"
        assert deployment.deployment_type in [
            "python",
            "docker",
        ], "Invalid deployment type"
        assert deployment.work_pool, "Deployment must have a work pool"
        assert deployment.entrypoint, "Deployment must have an entrypoint"

    @staticmethod
    def assert_validation_result(result, should_be_valid=True):
        """Assert validation result properties."""
        if should_be_valid:
            assert (
                result.is_valid or not result.has_errors
            ), "Validation should pass or have only warnings"
        else:
            assert not result.is_valid, "Validation should fail"
            assert result.has_errors, "Failed validation should have errors"


@pytest.fixture
def assertions():
    """Provide custom assertions."""
    return TestAssertions


# Test data persistence (for debugging)
@pytest.fixture
def persist_test_data():
    """Persist test data for debugging (when enabled)."""
    persist = os.environ.get("PERSIST_TEST_DATA", "false").lower() == "true"

    if persist:
        test_data_dir = Path("test_data_output")
        test_data_dir.mkdir(exist_ok=True)
        yield test_data_dir
    else:
        yield None


# Timeout fixture for long-running tests
@pytest.fixture
def test_timeout():
    """Provide test timeout configuration."""
    return {
        "unit": 30,  # seconds
        "integration": 120,  # seconds
        "e2e": 300,  # seconds
    }


# Error injection for testing error handling
@pytest.fixture
def error_injector():
    """Provide error injection utilities for testing error handling."""

    class ErrorInjector:
        def __init__(self):
            self.active_errors = {}

        def inject_error(self, component, error_type, error_message="Injected error"):
            """Inject an error for a specific component."""
            self.active_errors[component] = (error_type, error_message)

        def clear_error(self, component):
            """Clear injected error for a component."""
            self.active_errors.pop(component, None)

        def clear_all_errors(self):
            """Clear all injected errors."""
            self.active_errors.clear()

        def should_raise_error(self, component):
            """Check if an error should be raised for a component."""
            return component in self.active_errors

        def get_error(self, component):
            """Get the error to raise for a component."""
            if component in self.active_errors:
                error_type, error_message = self.active_errors[component]
                return error_type(error_message)
            return None

    return ErrorInjector()


# Test metrics collection
@pytest.fixture(autouse=True)
def collect_test_metrics(request):
    """Collect test metrics for analysis."""
    import time

    start_time = time.time()
    yield
    end_time = time.time()

    # Store metrics (could be sent to monitoring system)
    test_name = request.node.name
    duration = end_time - start_time

    # For now, just store in a simple way
    if not hasattr(request.config, "_test_metrics"):
        request.config._test_metrics = []

    request.config._test_metrics.append(
        {
            "test_name": test_name,
            "duration": duration,
            "status": (
                "passed"
                if not hasattr(request.node, "rep_call") or request.node.rep_call.passed
                else "failed"
            ),
        }
    )


def pytest_sessionfinish(session, exitstatus):
    """Handle session finish to report metrics."""
    if hasattr(session.config, "_test_metrics"):
        metrics = session.config._test_metrics
        total_tests = len(metrics)
        total_duration = sum(m["duration"] for m in metrics)
        passed_tests = len([m for m in metrics if m["status"] == "passed"])

        print(f"\n=== Test Metrics ===")
        print(f"Total tests: {total_tests}")
        print(f"Passed tests: {passed_tests}")
        print(f"Total duration: {total_duration:.2f}s")
        print(f"Average duration: {total_duration/total_tests:.2f}s")

        # Find slowest tests
        slowest = sorted(metrics, key=lambda x: x["duration"], reverse=True)[:5]
        print(f"\nSlowest tests:")
        for test in slowest:
            print(f"  {test['test_name']}: {test['duration']:.2f}s")
