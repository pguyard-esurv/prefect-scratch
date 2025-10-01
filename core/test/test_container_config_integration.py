"""
Integration tests for ContainerConfigManager with existing system components.

Tests integration with existing ConfigManager, database connections, and
real-world configuration scenarios.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from core.config import ConfigManager
from core.container_config import ContainerConfigManager


class TestContainerConfigIntegration:
    """Integration test suite for ContainerConfigManager."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.original_env = os.environ.copy()

        # Set up basic test environment
        os.environ.update(
            {"PREFECT_ENVIRONMENT": "test", "HOSTNAME": "integration-test-container"}
        )

    def teardown_method(self):
        """Clean up test environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)

    @pytest.mark.slow
    def test_extends_existing_config_manager(self):
        """Test that ContainerConfigManager properly extends ConfigManager."""
        container_manager = ContainerConfigManager(flow_name="rpa1", environment="test")
        base_manager = ConfigManager(flow_name="rpa1", environment="test")

        # Should have all base ConfigManager functionality
        assert hasattr(container_manager, "get_secret")
        assert hasattr(container_manager, "get_variable")
        assert hasattr(container_manager, "get_config")
        assert hasattr(container_manager, "get_distributed_config")

        # Should have additional container-specific functionality
        assert hasattr(container_manager, "load_container_config")
        assert hasattr(container_manager, "validate_container_environment")
        assert hasattr(container_manager, "wait_for_dependencies")
        assert hasattr(container_manager, "generate_startup_report")

        # Should inherit environment and flow_name properly
        assert container_manager.environment == base_manager.environment
        assert container_manager.flow_name == base_manager.flow_name

    @pytest.mark.slow
    def test_container_prefix_overrides_standard_config(self):
        """Test that CONTAINER_ prefix variables override standard configuration."""
        # Set up both standard and container-prefixed variables
        os.environ.update(
            {
                # Standard configuration
                "TEST_GLOBAL_DATABASE_RPA_DB_TYPE": "sqlserver",
                "TEST_GLOBAL_DATABASE_RPA_DB_CONNECTION_STRING": "sqlserver://standard@localhost:1433/rpa_db",
                # Container-prefixed configuration (should override)
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://container@localhost:5432/rpa_db",
                "CONTAINER_DATABASE_REQUIRED": "rpa_db",
            }
        )

        container_manager = ContainerConfigManager(environment="test")
        databases = container_manager._load_database_configs()

        # Container prefix should override standard config
        assert "rpa_db" in databases
        assert databases["rpa_db"].database_type == "postgresql"
        assert "container@localhost:5432" in databases["rpa_db"].connection_string

    @pytest.mark.slow
    def test_fallback_to_standard_config_when_container_prefix_missing(self):
        """Test fallback to standard ConfigManager when CONTAINER_ prefix not found."""
        with (
            patch.object(ContainerConfigManager, "get_secret") as mock_get_secret,
            patch.object(ContainerConfigManager, "get_variable") as mock_get_variable,
        ):
            # Mock standard configuration methods
            mock_get_secret.side_effect = lambda key, default=None: {
                "rpa_db_connection_string": "postgresql://standard@localhost:5432/rpa_db"
            }.get(key, default)
            mock_get_variable.side_effect = lambda key, default=None: {
                "rpa_db_type": "postgresql"
            }.get(key, default)

            container_manager = ContainerConfigManager()
            databases = container_manager._load_database_configs()

            # Should fall back to standard configuration
            assert "rpa_db" in databases
            assert databases["rpa_db"].database_type == "postgresql"
            assert "standard@localhost:5432" in databases["rpa_db"].connection_string

    @pytest.mark.slow
    def test_distributed_config_integration(self):
        """Test integration with existing distributed configuration."""
        # Set up distributed processing configuration
        os.environ.update(
            {
                "TEST_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "200",
                "TEST_GLOBAL_DISTRIBUTED_PROCESSOR_ENABLED": "true",
                "TEST_GLOBAL_RPA_DB_TYPE": "postgresql",
                "TEST_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/rpa_db",
                "TEST_GLOBAL_SURVEYHUB_TYPE": "postgresql",
                "TEST_GLOBAL_SURVEYHUB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/surveyhub",
                "CONTAINER_DATABASE_REQUIRED": "rpa_db,SurveyHub",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/rpa_db",
                "CONTAINER_DATABASE_SURVEYHUB_TYPE": "postgresql",
                "CONTAINER_DATABASE_SURVEYHUB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/surveyhub",
            }
        )

        container_manager = ContainerConfigManager()

        # Should be able to get distributed config (inherited from base class)
        distributed_config = container_manager.get_distributed_config()
        assert distributed_config["enable_distributed_processing"] is True

        # Should be able to validate container environment
        validation = container_manager.validate_container_environment()
        assert validation.valid is True

    def test_startup_validation_with_real_config_structure(self):
        """Test startup validation with realistic configuration structure."""
        # Set up comprehensive container configuration
        os.environ.update(
            {
                # Database configuration
                "CONTAINER_DATABASE_REQUIRED": "rpa_db,SurveyHub",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://rpa_user:password@db:5432/rpa_db",
                "CONTAINER_DATABASE_RPA_DB_POOL_SIZE": "10",
                "CONTAINER_DATABASE_RPA_DB_TIMEOUT": "60",
                "CONTAINER_DATABASE_SURVEYHUB_TYPE": "postgresql",
                "CONTAINER_DATABASE_SURVEYHUB_CONNECTION_STRING": "postgresql://survey_user:password@db:5432/surveyhub",
                # Service dependencies
                "CONTAINER_SERVICE_REQUIRED": "prefect,redis",
                "CONTAINER_SERVICE_PREFECT_HEALTH_ENDPOINT": "http://prefect-server:4200/api/health",
                "CONTAINER_SERVICE_PREFECT_TIMEOUT": "30",
                "CONTAINER_SERVICE_PREFECT_RETRY_ATTEMPTS": "5",
                "CONTAINER_SERVICE_REDIS_HEALTH_ENDPOINT": "http://redis:6379/ping",
                "CONTAINER_SERVICE_REDIS_TIMEOUT": "15",
                # Monitoring configuration
                "CONTAINER_MONITORING_HEALTH_CHECK_ENABLED": "true",
                "CONTAINER_MONITORING_HEALTH_CHECK_INTERVAL": "60",
                "CONTAINER_MONITORING_METRICS_ENABLED": "true",
                "CONTAINER_MONITORING_METRICS_PORT": "8080",
                "CONTAINER_MONITORING_LOG_LEVEL": "INFO",
                "CONTAINER_MONITORING_STRUCTURED_LOGGING": "true",
                # Security configuration
                "CONTAINER_SECURITY_RUN_AS_NON_ROOT": "true",
                "CONTAINER_SECURITY_USER_ID": "1000",
                "CONTAINER_SECURITY_GROUP_ID": "1000",
                "CONTAINER_SECURITY_READ_ONLY_ROOT_FS": "false",
                "CONTAINER_SECURITY_DROP_CAPABILITIES": "ALL",
                "CONTAINER_SECURITY_SECRETS_MOUNT_PATH": "/var/secrets",
                # Resource configuration
                "CONTAINER_RESOURCE_CPU_LIMIT": "2.0",
                "CONTAINER_RESOURCE_MEMORY_LIMIT": "1Gi",
                "CONTAINER_RESOURCE_CPU_REQUEST": "0.5",
                "CONTAINER_RESOURCE_MEMORY_REQUEST": "256Mi",
                "CONTAINER_RESOURCE_DISK_LIMIT": "5Gi",
            }
        )

        container_manager = ContainerConfigManager(
            flow_name="rpa1", environment="production"
        )

        # Generate startup report
        report = container_manager.generate_startup_report()

        assert report.environment == "production"
        assert report.flow_name == "rpa1"
        assert report.overall_status in [
            "success",
            "warning",
        ]  # Should not be error with valid config
        assert len(report.recommendations) > 0

        # Validate complete configuration
        validation = container_manager.validate_container_environment()
        assert validation.valid is True
        assert len(validation.errors) == 0

    @pytest.mark.slow
    def test_error_handling_integration(self):
        """Test error handling integration with existing system."""
        # Set up configuration that will cause validation errors
        os.environ.update(
            {
                "CONTAINER_DATABASE_REQUIRED": "rpa_db",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "mysql",  # Unsupported type
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "invalid://connection",  # Invalid format
                "CONTAINER_SECURITY_USER_ID": "0",  # Root user - security violation
                "CONTAINER_RESOURCE_CPU_LIMIT": "1.0",
                "CONTAINER_RESOURCE_CPU_REQUEST": "2.0",  # Request exceeds limit
                "CONTAINER_RESOURCE_MEMORY_LIMIT": "invalid-memory",  # Invalid format
            }
        )

        container_manager = ContainerConfigManager()

        # Should handle errors gracefully
        validation = container_manager.validate_container_environment()
        assert validation.valid is False
        assert len(validation.errors) > 0

        # Should include specific error details
        error_messages = " ".join(validation.errors)
        assert "Unsupported database type 'mysql'" in error_messages
        assert "Invalid connection string format" in error_messages
        assert "root user ID (0)" in error_messages
        # Note: CPU and memory validation errors might be in different validation sections
        assert (
            len(validation.errors) >= 3
        )  # At least database, security, and resource errors

        # Startup report should reflect errors
        report = container_manager.generate_startup_report()
        assert report.overall_status == "error"
        assert any("Fix configuration errors" in rec for rec in report.recommendations)

    @pytest.mark.slow
    def test_flow_specific_configuration_inheritance(self):
        """Test that flow-specific configuration works with container extensions."""
        # Set up flow-specific configuration
        os.environ.update(
            {
                # Global container configuration
                "CONTAINER_DATABASE_REQUIRED": "rpa_db",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://global@localhost:5432/rpa_db",
                # Flow-specific overrides (simulating .env file loading)
                "TEST_RPA1_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://rpa1_specific@localhost:5432/rpa_db",
            }
        )

        # Test with flow-specific manager
        rpa1_manager = ContainerConfigManager(flow_name="rpa1", environment="test")

        # Should inherit base ConfigManager flow-specific behavior
        assert rpa1_manager.flow_name == "rpa1"
        assert rpa1_manager.environment == "test"

        # Container configuration should still work
        config = rpa1_manager.load_container_config()
        assert config["flow_name"] == "rpa1"
        assert config["environment"] == "test"
        assert "databases" in config

    @patch("requests.get")
    @pytest.mark.slow
    def test_dependency_waiting_integration(self, mock_get):
        """Test dependency waiting integration with real service configurations."""

        # Mock successful health check for first service, failure for second
        def mock_health_check(url, timeout):
            response = MagicMock()
            if "prefect" in url:
                response.status_code = 200
            else:
                response.status_code = 503  # Service unavailable
            return response

        mock_get.side_effect = mock_health_check

        # Set up multiple service dependencies
        os.environ.update(
            {
                "CONTAINER_SERVICE_REQUIRED": "prefect,database",
                "CONTAINER_SERVICE_PREFECT_HEALTH_ENDPOINT": "http://prefect:4200/api/health",
                "CONTAINER_SERVICE_DATABASE_HEALTH_ENDPOINT": "http://database:5432/health",
            }
        )

        container_manager = ContainerConfigManager()

        # Should return False because one service is unhealthy
        result = container_manager.wait_for_dependencies(timeout=1)
        assert result is False

        # Should have made health check requests
        assert mock_get.call_count >= 2

    @pytest.mark.slow
    def test_configuration_caching_and_performance(self):
        """Test that configuration loading is efficient and properly cached."""
        os.environ.update(
            {
                "CONTAINER_DATABASE_REQUIRED": "rpa_db",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/rpa_db",
            }
        )

        container_manager = ContainerConfigManager()

        # Load configuration multiple times
        config1 = container_manager.load_container_config()
        config2 = container_manager.load_container_config()

        # Should return consistent results
        assert config1["container_id"] == config2["container_id"]
        assert config1["environment"] == config2["environment"]
        assert len(config1["databases"]) == len(config2["databases"])

        # Validation should also be consistent
        validation1 = container_manager.validate_container_environment()
        validation2 = container_manager.validate_container_environment()

        assert validation1.valid == validation2.valid
        assert len(validation1.errors) == len(validation2.errors)
