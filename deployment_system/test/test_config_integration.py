"""
Integration Tests for Configuration Management

Tests integration between configuration management and other deployment system components.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from deployment_system.config.manager import ConfigurationManager
from deployment_system.discovery.metadata import FlowMetadata


class TestConfigurationIntegration:
    """Test configuration integration with other components."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def create_test_config(self):
        """Create a test configuration file."""
        config_data = {
            "environments": {
                "integration_test": {
                    "name": "integration_test",
                    "prefect_api_url": "http://localhost:4200/api",
                    "work_pools": {
                        "python": "integration-python-pool",
                        "docker": "integration-docker-pool",
                    },
                    "default_parameters": {
                        "test_mode": True,
                        "integration_test": True,
                        "timeout": 600,
                    },
                    "resource_limits": {
                        "memory": "2Gi",
                        "cpu": "2.0",
                        "storage": "10Gi",
                    },
                    "default_tags": ["env:integration", "test:enabled"],
                }
            },
            "global_config": {
                "validation": {
                    "strict_mode": False,  # More lenient for testing
                    "validate_dependencies": False,
                    "validate_docker_images": False,
                    "validate_work_pools": False,
                }
            },
            "flow_overrides": {
                "integration_flow": {
                    "resource_limits": {"memory": "4Gi", "cpu": "4.0"},
                    "default_parameters": {
                        "integration_batch_size": 500,
                        "integration_workers": 8,
                    },
                }
            },
        }

        config_file = self.config_dir / "deployment-config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return config_file

    def test_config_deployment_generation(self):
        """Test configuration integration with deployment generation."""
        self.create_test_config()
        config_manager = ConfigurationManager(str(self.config_dir))

        # Create test flow metadata
        flow = FlowMetadata(
            name="integration_flow",
            path="/test/integration_flow.py",
            module_path="test.integration_flow",
            function_name="integration_function",
            dependencies=["requests", "pandas"],
            dockerfile_path=None,
            env_files=[".env.integration"],
            is_valid=True,
            validation_errors=[],
            metadata={"description": "Integration test flow"},
        )

        # Generate deployment config using configuration manager
        deployment_config = config_manager.generate_deployment_config(
            flow, "python", "integration_test"
        )

        # Verify configuration is correctly generated
        assert deployment_config.flow_name == "integration_flow"
        assert deployment_config.deployment_type == "python"
        assert deployment_config.environment == "integration_test"
        assert deployment_config.work_pool == "integration-python-pool"
        assert (
            deployment_config.entrypoint == "test.integration_flow:integration_function"
        )

        # Verify environment parameters are applied
        assert deployment_config.parameters["test_mode"] is True
        assert deployment_config.parameters["integration_test"] is True
        assert deployment_config.parameters["timeout"] == 600

        # Verify flow overrides are applied
        assert deployment_config.parameters["integration_batch_size"] == 500
        assert deployment_config.parameters["integration_workers"] == 8

        # Verify tags are correctly set
        expected_tags = [
            "environment:integration_test",
            "type:python",
            "flow:integration_flow",
            "env:integration",
            "test:enabled",
        ]
        for tag in expected_tags:
            assert tag in deployment_config.tags

    def test_effective_resource_limits_integration(self):
        """Test effective resource limits with flow overrides."""
        self.create_test_config()
        config_manager = ConfigurationManager(str(self.config_dir))

        # Test flow with overrides
        limits = config_manager.get_effective_resource_limits(
            "integration_flow", "integration_test"
        )
        assert limits.memory == "4Gi"  # From flow override
        assert limits.cpu == "4.0"  # From flow override

        # Test flow without overrides
        limits = config_manager.get_effective_resource_limits(
            "other_flow", "integration_test"
        )
        assert limits.memory == "2Gi"  # From environment default
        assert limits.cpu == "2.0"  # From environment default
        assert limits.storage == "10Gi"  # From environment default

    def test_validation_with_lenient_config(self):
        """Test validation with lenient global configuration."""
        self.create_test_config()
        config_manager = ConfigurationManager(str(self.config_dir))

        # Create deployment config that would normally fail strict validation
        flow = FlowMetadata(
            name="test_flow",
            path="/test/path",
            module_path="test.flow",
            function_name="test_function",
            dependencies=[],
            dockerfile_path=None,
            env_files=[],
            is_valid=True,
            validation_errors=[],
            metadata={},
        )

        deployment_config = config_manager.generate_deployment_config(
            flow, "python", "integration_test"
        )

        # Override work pool to test lenient validation
        deployment_config.work_pool = "different-pool"

        result = config_manager.validate_configuration(deployment_config)

        # Should pass because strict_mode is False
        assert result.is_valid
        # May or may not have warnings depending on configuration
        # The important thing is that it passes validation

    def test_template_integration_with_config(self):
        """Test template system integration with configuration."""
        self.create_test_config()
        config_manager = ConfigurationManager(str(self.config_dir))

        flow = FlowMetadata(
            name="template_test_flow",
            path="/test/template_flow.py",
            module_path="test.template_flow",
            function_name="template_function",
            dependencies=["numpy"],
            dockerfile_path=None,
            env_files=[".env.template"],
            is_valid=True,
            validation_errors=[],
            metadata={},
        )

        # Generate deployment config (this uses templates internally)
        deployment_config = config_manager.generate_deployment_config(
            flow, "python", "integration_test"
        )

        # Verify template variables were substituted correctly
        assert deployment_config.work_pool == "integration-python-pool"

        # Check that job variables were set from template
        if deployment_config.job_variables:
            env_vars = deployment_config.job_variables.get("env", {})
            assert env_vars.get("PREFECT_API_URL") == "http://localhost:4200/api"
            assert env_vars.get("ENVIRONMENT") == "integration_test"
            assert env_vars.get("FLOW_NAME") == "template_test_flow"

    def test_configuration_reload(self):
        """Test configuration reloading functionality."""
        config_file = self.create_test_config()
        config_manager = ConfigurationManager(str(self.config_dir))

        # Verify initial configuration
        env_config = config_manager.get_environment_config("integration_test")
        assert env_config.default_parameters["timeout"] == 600

        # Modify configuration file
        with open(config_file) as f:
            config_data = yaml.safe_load(f)

        config_data["environments"]["integration_test"]["default_parameters"][
            "timeout"
        ] = 1200

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Reload configuration
        config_manager.reload_configuration()

        # Verify configuration was reloaded
        env_config = config_manager.get_environment_config("integration_test")
        assert env_config.default_parameters["timeout"] == 1200

    def test_multiple_environment_deployment_configs(self):
        """Test generating deployment configs for multiple environments."""
        self.create_test_config()
        config_manager = ConfigurationManager(str(self.config_dir))

        flow = FlowMetadata(
            name="multi_env_flow",
            path="/test/multi_env_flow.py",
            module_path="test.multi_env_flow",
            function_name="multi_env_function",
            dependencies=[],
            dockerfile_path=None,
            env_files=[],
            is_valid=True,
            validation_errors=[],
            metadata={},
        )

        # Generate configs for different environments
        environments = ["development", "integration_test"]
        configs = {}

        for env in environments:
            if config_manager.get_environment_config(env):
                configs[env] = config_manager.generate_deployment_config(
                    flow, "python", env
                )

        # Verify each config has correct environment-specific settings
        assert len(configs) == 2

        # Development config
        dev_config = configs["development"]
        assert dev_config.environment == "development"
        assert dev_config.work_pool == "default-agent-pool"
        # Check for any development-specific parameters
        assert "cleanup" in dev_config.parameters

        # Integration test config
        int_config = configs["integration_test"]
        assert int_config.environment == "integration_test"
        assert int_config.work_pool == "integration-python-pool"
        assert int_config.parameters["test_mode"] is True


if __name__ == "__main__":
    pytest.main([__file__])
