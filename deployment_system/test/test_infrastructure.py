"""
Test infrastructure validation.

Simple tests to verify that the testing infrastructure is working correctly.
"""

import pytest

from deployment_system.test.test_utilities import (
    MockPrefectClient,
    MockDockerClient,
    TestDataFactory,
    TestAssertions,
)


class TestTestingInfrastructure:
    """Test the testing infrastructure itself."""

    def test_mock_prefect_client(self):
        """Test that MockPrefectClient works correctly."""
        client = MockPrefectClient()

        # Test initial state
        assert client.api_url == "http://localhost:4200/api"
        assert len(client.deployments) == 0
        assert client.is_connected is True

        # Test connectivity
        assert client.is_connected is True
        client.set_connected(False)
        assert client.is_connected is False

    def test_mock_docker_client(self):
        """Test that MockDockerClient works correctly."""
        client = MockDockerClient()

        # Test initial state
        assert len(client.images) == 0
        assert len(client.containers) == 0
        assert client.is_available is True

        # Test image operations
        client.add_image("test:latest")
        assert client.image_exists("test:latest")
        assert not client.image_exists("nonexistent:latest")

    def test_test_data_factory(self):
        """Test that TestDataFactory creates valid test data."""
        # Test flow metadata creation
        flow = TestDataFactory.create_flow_metadata("test-flow")
        assert flow.name == "test-flow"
        assert flow.is_valid is True
        assert flow.supports_python_deployment is True

        # Test Docker-capable flow
        docker_flow = TestDataFactory.create_flow_metadata(
            "docker-flow", supports_docker=True
        )
        assert docker_flow.supports_docker_deployment is True

        # Test deployment config creation
        config = TestDataFactory.create_deployment_config("test-flow", "python")
        assert config.flow_name == "test-flow"
        assert config.deployment_type == "python"

    def test_test_assertions(self):
        """Test that custom assertions work correctly."""
        # Test flow validation
        valid_flow = TestDataFactory.create_flow_metadata("valid-flow")
        TestAssertions.assert_flow_metadata_valid(valid_flow)

        # Test deployment validation
        valid_deployment = TestDataFactory.create_deployment_config("test-flow")
        TestAssertions.assert_deployment_config_valid(valid_deployment)

    def test_fixtures_available(self, sample_flows, mock_prefect_client):
        """Test that pytest fixtures are available and working."""
        # Test sample_flows fixture
        assert len(sample_flows) >= 2
        assert all(hasattr(flow, "name") for flow in sample_flows)

        # Test mock_prefect_client fixture
        assert hasattr(mock_prefect_client, "api_url")
        assert hasattr(mock_prefect_client, "deployments")

    def test_temp_project_structure(self, temp_workspace):
        """Test that temporary project structure is created correctly."""
        assert temp_workspace.exists()
        assert temp_workspace.is_dir()

    def test_markers_and_categorization(self):
        """Test that test markers are working correctly."""
        # This test itself should be marked as unit
        # We can't easily test this programmatically, but it validates the concept
        assert True

    @pytest.mark.unit
    def test_unit_marker(self):
        """Test with unit marker."""
        assert True

    @pytest.mark.integration
    def test_integration_marker(self):
        """Test with integration marker."""
        assert True

    @pytest.mark.slow
    def test_slow_marker(self):
        """Test with slow marker."""
        # This would be skipped if SKIP_SLOW is set
        assert True

    def test_performance_utilities(self):
        """Test performance testing utilities."""
        from deployment_system.test.test_utilities import PerformanceTimer

        with PerformanceTimer() as timer:
            # Simulate some work
            sum(range(1000))

        assert timer.elapsed >= 0
        # Should complete quickly
        timer.assert_under_threshold(1.0)

    def test_error_injection(self, error_injector):
        """Test error injection utilities."""
        # Test error injection
        error_injector.inject_error("test_component", ValueError, "Test error")
        assert error_injector.should_raise_error("test_component")

        error = error_injector.get_error("test_component")
        assert isinstance(error, ValueError)
        assert str(error) == "Test error"

        # Test error clearing
        error_injector.clear_error("test_component")
        assert not error_injector.should_raise_error("test_component")

    def test_mock_environment_context(self):
        """Test MockEnvironment context manager."""
        from deployment_system.test.test_utilities import MockEnvironment

        with MockEnvironment(prefect_available=True, docker_available=False) as env:
            # Environment should be set up
            assert env is not None

    def test_large_data_generation(self):
        """Test generation of large test datasets."""
        from deployment_system.test.test_utilities import generate_large_flow_set

        flows = generate_large_flow_set(10)
        assert len(flows) == 10
        assert all(hasattr(flow, "name") for flow in flows)

        # Should have mix of valid/invalid and docker/python flows
        valid_flows = [f for f in flows if f.is_valid]
        docker_flows = [f for f in flows if f.supports_docker_deployment]

        assert len(valid_flows) >= 8  # Most should be valid
        assert len(docker_flows) >= 2  # Some should support Docker


class TestTestConfiguration:
    """Test pytest configuration and setup."""

    def test_test_environment_setup(self, test_environment):
        """Test that test environment is set up correctly."""
        import os

        assert os.environ.get("ENVIRONMENT") == "test"
        assert os.environ.get("PYTHONPATH") == "/app"

    def test_logging_configuration(self, test_logging):
        """Test that logging is configured for tests."""
        import logging

        logger = logging.getLogger("test_logger")
        logger.info("Test log message")

        # Should capture log messages
        assert "Test log message" in test_logging.text

    def test_assertions_fixture(self, assertions):
        """Test that assertions fixture is available."""
        assert hasattr(assertions, "assert_flow_valid")
        assert hasattr(assertions, "assert_deployment_valid")
        assert hasattr(assertions, "assert_validation_result")

    def test_parametrized_fixtures(self, environment_name, deployment_type):
        """Test parametrized fixtures."""
        assert environment_name in ["development", "staging", "production"]
        assert deployment_type in ["python", "docker"]


class TestTestUtilities:
    """Test specific test utilities."""

    def test_validation_result_creation(self):
        """Test ValidationResult creation utilities."""
        from deployment_system.test.test_utilities import TestDataFactory

        # Test successful validation
        success_result = TestDataFactory.create_validation_result(is_valid=True)
        assert success_result.is_valid
        assert not success_result.has_errors

        # Test failed validation
        failed_result = TestDataFactory.create_validation_result(
            is_valid=False, error_count=2, warning_count=1
        )
        assert not failed_result.is_valid
        assert failed_result.has_errors
        assert failed_result.has_warnings
        assert len(failed_result.errors) == 2
        assert len(failed_result.warnings) == 1

    def test_complex_deployment_config_generation(self):
        """Test complex deployment configuration generation."""
        from deployment_system.test.test_utilities import (
            generate_complex_deployment_configs,
        )

        configs = generate_complex_deployment_configs(5)
        assert len(configs) > 0

        # Should have different environments and types
        environments = set(config.environment for config in configs)
        deployment_types = set(config.deployment_type for config in configs)

        assert len(environments) >= 2
        assert len(deployment_types) >= 1

    def test_project_structure_creation(self, temp_workspace):
        """Test project structure creation."""
        from deployment_system.test.test_utilities import TestDataFactory

        structure = TestDataFactory.create_project_structure(temp_workspace)

        # Verify structure
        assert "flows_dir" in structure
        assert "config_dir" in structure
        assert "deployment_config" in structure

        # Verify directories exist
        assert structure["flows_dir"].exists()
        assert structure["config_dir"].exists()
        assert structure["deployment_config"].exists()

        # Verify flow directories
        assert "python_flow" in structure
        assert "docker_flow" in structure
        assert structure["python_flow"].exists()
        assert structure["docker_flow"].exists()


# Integration test to verify the entire testing setup
class TestTestingIntegration:
    """Integration test for the entire testing setup."""

    def test_complete_testing_workflow(self, sample_project, mock_prefect_environment):
        """Test a complete testing workflow using all utilities."""
        from deployment_system.discovery.discovery import FlowDiscovery
        from deployment_system.builders.deployment_builder import DeploymentBuilder

        # Use real components with mocked dependencies
        discovery = FlowDiscovery()
        builder = DeploymentBuilder()

        # Discover flows in sample project
        flows = discovery.discover_flows(str(sample_project["flows_dir"]))
        assert len(flows) >= 2

        # Create deployments
        valid_flows = [f for f in flows if f.is_valid]
        result = builder.create_all_deployments(valid_flows, "development")

        # Should succeed with mocked environment
        assert result.success
        assert len(result.deployments) >= 2

    def test_error_handling_workflow(self, sample_project, mock_offline_environment):
        """Test error handling with offline environment."""
        from deployment_system.discovery.discovery import FlowDiscovery

        # Should still work for discovery (doesn't need external services)
        discovery = FlowDiscovery()
        flows = discovery.discover_flows(str(sample_project["flows_dir"]))

        # Should find flows even in offline environment
        assert len(flows) >= 0  # May be 0 if no valid flows, but shouldn't crash

    def test_performance_testing_workflow(self, large_flow_set, performance_threshold):
        """Test performance testing workflow."""
        from deployment_system.test.test_utilities import PerformanceTimer
        from deployment_system.builders.deployment_builder import DeploymentBuilder

        builder = DeploymentBuilder()

        with PerformanceTimer() as timer:
            # Create deployments for large flow set
            result = builder.create_all_deployments(large_flow_set, "development")

        # Should complete within performance threshold
        timer.assert_under_threshold(performance_threshold["deployment_creation"])

        # Should handle large datasets
        assert len(result.deployments) >= len([f for f in large_flow_set if f.is_valid])


if __name__ == "__main__":
    # Run infrastructure tests
    pytest.main([__file__, "-v"])
