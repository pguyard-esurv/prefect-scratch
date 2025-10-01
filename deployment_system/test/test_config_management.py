"""
Tests for Configuration Management System

Tests environment configuration loading, validation, and template system.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from deployment_system.config.config_validator import ConfigValidator
from deployment_system.config.environments import EnvironmentConfig, ResourceLimits
from deployment_system.config.manager import ConfigurationManager
from deployment_system.discovery.metadata import FlowMetadata


class TestConfigurationManager:
    """Test configuration manager functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def create_test_config(self):
        """Create a test configuration file."""
        config_data = {
            "environments": {
                "test": {
                    "name": "test",
                    "prefect_api_url": "http://localhost:4200/api",
                    "work_pools": {
                        "python": "test-python-pool",
                        "docker": "test-docker-pool",
                    },
                    "default_parameters": {"debug": True, "timeout": 300},
                    "resource_limits": {"memory": "1Gi", "cpu": "1.0"},
                    "default_tags": ["env:test", "tier:testing"],
                }
            },
            "global_config": {
                "validation": {"strict_mode": True, "validate_dependencies": True}
            },
            "flow_overrides": {
                "test_flow": {
                    "resource_limits": {"memory": "2Gi", "cpu": "2.0"},
                    "default_parameters": {"batch_size": 100},
                }
            },
        }

        config_file = self.config_dir / "deployment-config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return config_file

    def test_load_configuration(self):
        """Test loading configuration from YAML file."""
        self.create_test_config()
        manager = ConfigurationManager(str(self.config_dir))

        # Test environment loading
        environments = manager.list_environments()
        assert "test" in environments
        assert "development" in environments  # Default environment

        # Test environment config
        test_env = manager.get_environment_config("test")
        assert test_env is not None
        assert test_env.name == "test"
        assert test_env.prefect_api_url == "http://localhost:4200/api"
        assert test_env.work_pools["python"] == "test-python-pool"
        assert test_env.default_parameters["debug"] is True
        assert test_env.resource_limits.memory == "1Gi"
        assert "env:test" in test_env.default_tags

    def test_global_config_loading(self):
        """Test loading global configuration."""
        self.create_test_config()
        manager = ConfigurationManager(str(self.config_dir))

        global_config = manager.get_global_config()
        assert "validation" in global_config
        assert global_config["validation"]["strict_mode"] is True

        validation_config = manager.get_validation_config()
        assert validation_config["strict_mode"] is True
        assert validation_config["validate_dependencies"] is True

    def test_flow_overrides_loading(self):
        """Test loading flow-specific overrides."""
        self.create_test_config()
        manager = ConfigurationManager(str(self.config_dir))

        overrides = manager.get_flow_overrides("test_flow")
        assert "resource_limits" in overrides
        assert overrides["resource_limits"]["memory"] == "2Gi"
        assert overrides["default_parameters"]["batch_size"] == 100

        # Test non-existent flow
        empty_overrides = manager.get_flow_overrides("non_existent")
        assert empty_overrides == {}

    def test_deployment_config_generation(self):
        """Test generating deployment configuration."""
        self.create_test_config()
        manager = ConfigurationManager(str(self.config_dir))

        # Create test flow metadata
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

        # Generate deployment config
        config = manager.generate_deployment_config(flow, "python", "test")

        assert config.flow_name == "test_flow"
        assert config.deployment_type == "python"
        assert config.environment == "test"
        assert config.work_pool == "test-python-pool"
        assert config.entrypoint == "test.flow:test_function"

        # Check that flow overrides are applied
        assert config.parameters["batch_size"] == 100  # From flow override
        assert config.parameters["debug"] is True  # From environment default

        # Check tags
        assert "environment:test" in config.tags
        assert "type:python" in config.tags
        assert "flow:test_flow" in config.tags

    def test_effective_resource_limits(self):
        """Test getting effective resource limits with overrides."""
        self.create_test_config()
        manager = ConfigurationManager(str(self.config_dir))

        # Test with flow override
        limits = manager.get_effective_resource_limits("test_flow", "test")
        assert limits.memory == "2Gi"  # From override
        assert limits.cpu == "2.0"  # From override

        # Test without flow override
        limits = manager.get_effective_resource_limits("other_flow", "test")
        assert limits.memory == "1Gi"  # From environment default
        assert limits.cpu == "1.0"  # From environment default

    def test_configuration_validation(self):
        """Test configuration validation."""
        self.create_test_config()
        manager = ConfigurationManager(str(self.config_dir))

        # Create valid deployment config
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

        config = manager.generate_deployment_config(flow, "python", "test")
        result = manager.validate_configuration(config)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_environment_validation(self):
        """Test environment configuration validation."""
        self.create_test_config()
        manager = ConfigurationManager(str(self.config_dir))

        # Test valid environment
        result = manager.validate_environment_config("test")
        assert result.is_valid
        assert len(result.errors) == 0

        # Test invalid environment
        result = manager.validate_environment_config("non_existent")
        assert not result.is_valid
        assert len(result.errors) > 0
        assert result.errors[0].code == "ENVIRONMENT_NOT_FOUND"


class TestConfigValidator:
    """Test configuration validator functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def create_invalid_config(self):
        """Create an invalid configuration file."""
        config_data = {
            "environments": {
                "invalid": {
                    # Missing required prefect_api_url
                    "name": "invalid",
                    "work_pools": "not_a_dict",  # Should be dict
                }
            }
        }

        config_file = self.config_dir / "deployment-config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return config_file

    def create_valid_config(self):
        """Create a valid configuration file."""
        config_data = {
            "environments": {
                "valid": {
                    "name": "valid",
                    "prefect_api_url": "http://localhost:4200/api",
                    "work_pools": {"python": "valid-pool"},
                }
            }
        }

        config_file = self.config_dir / "deployment-config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return config_file

    def test_validate_valid_config(self):
        """Test validating a valid configuration."""
        config_file = self.create_valid_config()
        validator = ConfigValidator(str(self.config_dir))

        result = validator.validate_config_file(config_file)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_invalid_config(self):
        """Test validating an invalid configuration."""
        config_file = self.create_invalid_config()
        validator = ConfigValidator(str(self.config_dir))

        result = validator.validate_config_file(config_file)
        assert not result.is_valid
        assert len(result.errors) > 0

        # Check for specific errors
        error_codes = [error.code for error in result.errors]
        assert "MISSING_REQUIRED_FIELD" in error_codes
        assert "INVALID_WORK_POOLS" in error_codes

    def test_validate_missing_config(self):
        """Test validating a missing configuration file."""
        validator = ConfigValidator(str(self.config_dir))
        missing_file = self.config_dir / "missing.yaml"

        result = validator.validate_config_file(missing_file)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].code == "CONFIG_FILE_NOT_FOUND"

    def test_validate_invalid_yaml(self):
        """Test validating a file with invalid YAML syntax."""
        config_file = self.config_dir / "invalid.yaml"
        with open(config_file, "w") as f:
            f.write("invalid: yaml: syntax: [")

        validator = ConfigValidator(str(self.config_dir))
        result = validator.validate_config_file(config_file)

        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].code == "INVALID_YAML"


class TestEnvironmentConfig:
    """Test environment configuration model."""

    def test_environment_config_creation(self):
        """Test creating environment configuration."""
        config = EnvironmentConfig(
            name="test",
            prefect_api_url="http://localhost:4200/api",
            work_pools={"python": "test-pool"},
            default_parameters={"debug": True},
            resource_limits=ResourceLimits(memory="1Gi", cpu="1.0"),
            networks=["test-network"],
            default_tags=["env:test"],
        )

        assert config.name == "test"
        assert config.prefect_api_url == "http://localhost:4200/api"
        assert config.get_work_pool("python") == "test-pool"
        assert config.default_parameters["debug"] is True
        assert "test-network" in config.networks
        assert "env:test" in config.default_tags

    def test_environment_config_from_dict(self):
        """Test creating environment config from dictionary."""
        data = {
            "name": "test",
            "prefect_api_url": "http://localhost:4200/api",
            "work_pools": {"python": "test-pool"},
            "default_parameters": {"debug": True},
            "resource_limits": {"memory": "1Gi", "cpu": "1.0"},
            "networks": ["test-network"],
            "default_tags": ["env:test"],
        }

        config = EnvironmentConfig.from_dict(data)

        assert config.name == "test"
        assert config.prefect_api_url == "http://localhost:4200/api"
        assert config.work_pools["python"] == "test-pool"
        assert config.default_parameters["debug"] is True
        assert config.resource_limits.memory == "1Gi"
        assert "test-network" in config.networks
        assert "env:test" in config.default_tags

    def test_environment_config_to_dict(self):
        """Test converting environment config to dictionary."""
        config = EnvironmentConfig(
            name="test",
            prefect_api_url="http://localhost:4200/api",
            work_pools={"python": "test-pool"},
            default_parameters={"debug": True},
            resource_limits=ResourceLimits(memory="1Gi", cpu="1.0"),
            networks=["test-network"],
            default_tags=["env:test"],
        )

        data = config.to_dict()

        assert data["name"] == "test"
        assert data["prefect_api_url"] == "http://localhost:4200/api"
        assert data["work_pools"]["python"] == "test-pool"
        assert data["default_parameters"]["debug"] is True
        assert data["resource_limits"]["memory"] == "1Gi"
        assert "test-network" in data["networks"]
        assert "env:test" in data["default_tags"]


if __name__ == "__main__":
    pytest.main([__file__])
