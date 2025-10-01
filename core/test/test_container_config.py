"""
Unit tests for ContainerConfigManager.

Tests configuration loading, validation, error handling, and CONTAINER_ prefix
environment variable mapping functionality.
"""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from core.container_config import (
    ContainerConfigManager,
    DatabaseConfig,
    ServiceDependency,
    StartupReport,
    ValidationResult,
)


class TestContainerConfigManager:
    """Test suite for ContainerConfigManager class."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Clear any existing environment variables that might interfere
        self.original_env = os.environ.copy()

        # Set up basic test environment
        os.environ.update(
            {"PREFECT_ENVIRONMENT": "test", "HOSTNAME": "test-container-123"}
        )

    def teardown_method(self):
        """Clean up test environment after each test."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)

    @pytest.mark.slow
    def test_init_with_defaults(self):
        """Test ContainerConfigManager initialization with default values."""
        manager = ContainerConfigManager()

        assert manager.environment == "test"
        assert manager.flow_name is None
        assert manager.container_id == "test-container-123"

    @pytest.mark.slow
    def test_init_with_custom_values(self):
        """Test ContainerConfigManager initialization with custom values."""
        manager = ContainerConfigManager(
            flow_name="rpa1",
            environment="production",
            container_id="custom-container-456",
        )

        assert manager.environment == "production"
        assert manager.flow_name == "rpa1"
        assert manager.container_id == "custom-container-456"

    @pytest.mark.slow
    def test_container_config_prefix_mapping(self):
        """Test CONTAINER_ prefix environment variable mapping."""
        # Set up CONTAINER_ prefixed environment variables
        os.environ.update(
            {
                "CONTAINER_DATABASE_REQUIRED": "test_db,another_db",
                "CONTAINER_SERVICE_REQUIRED": "prefect,redis",
                "CONTAINER_MONITORING_HEALTH_CHECK_ENABLED": "true",
                "CONTAINER_SECURITY_RUN_AS_NON_ROOT": "true",
            }
        )

        manager = ContainerConfigManager()

        # Test _get_container_config method
        assert (
            manager._get_container_config("DATABASE_REQUIRED") == "test_db,another_db"
        )
        assert manager._get_container_config("SERVICE_REQUIRED") == "prefect,redis"
        assert (
            manager._get_container_config("MONITORING_HEALTH_CHECK_ENABLED") == "true"
        )
        assert manager._get_container_config("SECURITY_RUN_AS_NON_ROOT") == "true"

    @pytest.mark.slow
    def test_container_config_fallback(self):
        """Test fallback to standard configuration when CONTAINER_ prefix not found."""
        # Set up standard configuration
        with patch.object(ContainerConfigManager, "get_config") as mock_get_config:
            mock_get_config.return_value = "fallback_value"

            manager = ContainerConfigManager()
            result = manager._get_container_config("NONEXISTENT_KEY", "default")

            # Should fall back to get_config method
            mock_get_config.assert_called_once_with("NONEXISTENT_KEY", "default")
            assert result == "fallback_value"

    @pytest.mark.slow
    def test_load_database_configs_with_container_prefix(self):
        """Test loading database configurations with CONTAINER_ prefix."""
        os.environ.update(
            {
                "CONTAINER_DATABASE_REQUIRED": "rpa_db,SurveyHub",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/rpa_db",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_DATABASE_RPA_DB_POOL_SIZE": "10",
                "CONTAINER_DATABASE_RPA_DB_TIMEOUT": "60",
                "CONTAINER_DATABASE_SURVEYHUB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/surveyhub",
                "CONTAINER_DATABASE_SURVEYHUB_TYPE": "postgresql",
            }
        )

        manager = ContainerConfigManager()
        databases = manager._load_database_configs()

        assert len(databases) == 2
        assert "rpa_db" in databases
        assert "SurveyHub" in databases

        rpa_db = databases["rpa_db"]
        assert rpa_db.name == "rpa_db"
        assert (
            rpa_db.connection_string == "postgresql://user:pass@localhost:5432/rpa_db"
        )
        assert rpa_db.database_type == "postgresql"
        assert rpa_db.connection_pool_size == 10
        assert rpa_db.connection_timeout == 60

    def test_load_database_configs_fallback_to_standard(self):
        """Test loading database configurations with fallback to standard config."""
        with (
            patch.object(ContainerConfigManager, "get_secret") as mock_get_secret,
            patch.object(ContainerConfigManager, "get_variable") as mock_get_variable,
        ):
            mock_get_secret.side_effect = lambda key, default=None: {
                "rpa_db_connection_string": "postgresql://fallback@localhost:5432/rpa_db"
            }.get(key, default)

            mock_get_variable.side_effect = lambda key, default=None: {
                "rpa_db_type": "postgresql"
            }.get(key, default)

            manager = ContainerConfigManager()
            databases = manager._load_database_configs()

            assert "rpa_db" in databases
            assert (
                databases["rpa_db"].connection_string
                == "postgresql://fallback@localhost:5432/rpa_db"
            )

    def test_load_service_dependencies(self):
        """Test loading service dependency configurations."""
        os.environ.update(
            {
                "CONTAINER_SERVICE_REQUIRED": "prefect,redis",
                "CONTAINER_SERVICE_PREFECT_HEALTH_ENDPOINT": "http://prefect:4200/api/health",
                "CONTAINER_SERVICE_PREFECT_TIMEOUT": "45",
                "CONTAINER_SERVICE_PREFECT_RETRY_ATTEMPTS": "5",
                "CONTAINER_SERVICE_PREFECT_REQUIRED": "true",
                "CONTAINER_SERVICE_REDIS_HEALTH_ENDPOINT": "http://redis:6379/ping",
                "CONTAINER_SERVICE_REDIS_TIMEOUT": "30",
                "CONTAINER_SERVICE_REDIS_REQUIRED": "false",
            }
        )

        manager = ContainerConfigManager()
        services = manager._load_service_dependencies()

        assert len(services) == 2

        prefect_service = next(s for s in services if s.service_name == "prefect")
        assert prefect_service.health_endpoint == "http://prefect:4200/api/health"
        assert prefect_service.timeout == 45
        assert prefect_service.retry_attempts == 5
        assert prefect_service.required is True

        redis_service = next(s for s in services if s.service_name == "redis")
        assert redis_service.health_endpoint == "http://redis:6379/ping"
        assert redis_service.required is False

    def test_load_monitoring_config(self):
        """Test loading monitoring configuration."""
        os.environ.update(
            {
                "CONTAINER_MONITORING_HEALTH_CHECK_ENABLED": "true",
                "CONTAINER_MONITORING_HEALTH_CHECK_INTERVAL": "120",
                "CONTAINER_MONITORING_METRICS_ENABLED": "false",
                "CONTAINER_MONITORING_METRICS_PORT": "9090",
                "CONTAINER_MONITORING_LOG_LEVEL": "DEBUG",
                "CONTAINER_MONITORING_STRUCTURED_LOGGING": "true",
            }
        )

        manager = ContainerConfigManager()
        monitoring = manager._load_monitoring_config()

        assert monitoring["health_check_enabled"] is True
        assert monitoring["health_check_interval"] == 120
        assert monitoring["metrics_enabled"] is False
        assert monitoring["metrics_port"] == 9090
        assert monitoring["log_level"] == "DEBUG"
        assert monitoring["structured_logging"] is True

    def test_load_security_config(self):
        """Test loading security configuration."""
        os.environ.update(
            {
                "CONTAINER_SECURITY_RUN_AS_NON_ROOT": "true",
                "CONTAINER_SECURITY_USER_ID": "1001",
                "CONTAINER_SECURITY_GROUP_ID": "1001",
                "CONTAINER_SECURITY_READ_ONLY_ROOT_FS": "true",
                "CONTAINER_SECURITY_DROP_CAPABILITIES": "ALL,NET_ADMIN",
                "CONTAINER_SECURITY_SECRETS_MOUNT_PATH": "/etc/secrets",
            }
        )

        manager = ContainerConfigManager()
        security = manager._load_security_config()

        assert security["run_as_non_root"] is True
        assert security["user_id"] == 1001
        assert security["group_id"] == 1001
        assert security["read_only_root_filesystem"] is True
        assert security["drop_capabilities"] == ["ALL", "NET_ADMIN"]
        assert security["secrets_mount_path"] == "/etc/secrets"

    def test_load_resource_config(self):
        """Test loading resource configuration."""
        os.environ.update(
            {
                "CONTAINER_RESOURCE_CPU_LIMIT": "2.0",
                "CONTAINER_RESOURCE_MEMORY_LIMIT": "1Gi",
                "CONTAINER_RESOURCE_CPU_REQUEST": "0.5",
                "CONTAINER_RESOURCE_MEMORY_REQUEST": "256Mi",
                "CONTAINER_RESOURCE_DISK_LIMIT": "2Gi",
            }
        )

        manager = ContainerConfigManager()
        resources = manager._load_resource_config()

        assert resources["cpu_limit"] == "2.0"
        assert resources["memory_limit"] == "1Gi"
        assert resources["cpu_request"] == "0.5"
        assert resources["memory_request"] == "256Mi"
        assert resources["disk_limit"] == "2Gi"

    @pytest.mark.slow
    def test_load_container_config_complete(self):
        """Test loading complete container configuration."""
        os.environ.update(
            {
                "CONTAINER_DATABASE_REQUIRED": "rpa_db",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/rpa_db",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_SERVICE_REQUIRED": "prefect",
                "CONTAINER_SERVICE_PREFECT_HEALTH_ENDPOINT": "http://prefect:4200/api/health",
            }
        )

        manager = ContainerConfigManager(flow_name="rpa1", environment="test")
        config = manager.load_container_config()

        assert config["container_id"] == "test-container-123"
        assert config["environment"] == "test"
        assert config["flow_name"] == "rpa1"
        assert "databases" in config
        assert "services" in config
        assert "monitoring" in config
        assert "security" in config
        assert "resources" in config

    def test_validate_database_configs_valid(self):
        """Test database configuration validation with valid configurations."""
        databases = {
            "rpa_db": DatabaseConfig(
                name="rpa_db",
                connection_string="postgresql://user:pass@localhost:5432/rpa_db",
                database_type="postgresql",
                connection_pool_size=5,
                connection_timeout=30,
            )
        }

        manager = ContainerConfigManager()
        result = manager._validate_database_configs(databases)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_database_configs_invalid_connection_string(self):
        """Test database configuration validation with invalid connection string."""
        databases = {
            "rpa_db": DatabaseConfig(
                name="rpa_db",
                connection_string="invalid://connection",
                database_type="postgresql",
                connection_pool_size=5,
                connection_timeout=30,
            )
        }

        manager = ContainerConfigManager()
        result = manager._validate_database_configs(databases)

        assert result.valid is False
        assert any(
            "Invalid connection string format" in error for error in result.errors
        )

    def test_validate_database_configs_unsupported_type(self):
        """Test database configuration validation with unsupported database type."""
        databases = {
            "rpa_db": DatabaseConfig(
                name="rpa_db",
                connection_string="mysql://user:pass@localhost:3306/rpa_db",
                database_type="mysql",
                connection_pool_size=5,
                connection_timeout=30,
            )
        }

        manager = ContainerConfigManager()
        result = manager._validate_database_configs(databases)

        assert result.valid is False
        assert any(
            "Unsupported database type 'mysql'" in error for error in result.errors
        )

    def test_validate_service_dependencies_valid(self):
        """Test service dependency validation with valid configurations."""
        services = [
            ServiceDependency(
                service_name="prefect",
                health_endpoint="http://prefect:4200/api/health",
                timeout=30,
                retry_attempts=3,
                required=True,
            )
        ]

        manager = ContainerConfigManager()
        result = manager._validate_service_dependencies(services)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_validate_service_dependencies_invalid_endpoint(self):
        """Test service dependency validation with invalid health endpoint."""
        services = [
            ServiceDependency(
                service_name="prefect",
                health_endpoint="invalid-endpoint",
                timeout=30,
                retry_attempts=3,
                required=True,
            )
        ]

        manager = ContainerConfigManager()
        result = manager._validate_service_dependencies(services)

        assert result.valid is False
        assert any("Invalid health endpoint format" in error for error in result.errors)

    def test_validate_security_config_root_user_error(self):
        """Test security configuration validation with root user (error case)."""
        security = {
            "run_as_non_root": True,
            "user_id": 0,  # Root user ID
            "group_id": 1000,
            "read_only_root_filesystem": False,
            "drop_capabilities": ["ALL"],
            "secrets_mount_path": "/var/secrets",
        }

        manager = ContainerConfigManager()
        result = manager._validate_security_config(security)

        assert result.valid is False
        assert any("root user ID (0)" in error for error in result.errors)

    def test_validate_security_config_warnings(self):
        """Test security configuration validation with warning conditions."""
        security = {
            "run_as_non_root": False,  # Should generate warning
            "user_id": 500,  # Below 1000, should generate warning
            "group_id": 1000,
            "read_only_root_filesystem": False,
            "drop_capabilities": [
                "NET_ADMIN"
            ],  # Not dropping ALL, should generate warning
            "secrets_mount_path": "/var/secrets",
        }

        manager = ContainerConfigManager()
        result = manager._validate_security_config(security)

        assert result.valid is True  # No errors, just warnings
        assert len(result.warnings) >= 2  # Should have multiple warnings

    def test_validate_resource_config_cpu_request_exceeds_limit(self):
        """Test resource configuration validation with CPU request exceeding limit."""
        resources = {
            "cpu_limit": "1.0",
            "cpu_request": "2.0",  # Exceeds limit
            "memory_limit": "512Mi",
            "memory_request": "128Mi",
            "disk_limit": "1Gi",
        }

        manager = ContainerConfigManager()
        result = manager._validate_resource_config(resources)

        assert result.valid is False
        assert any(
            "CPU request" in error and "exceeds CPU limit" in error
            for error in result.errors
        )

    @pytest.mark.slow
    def test_validate_resource_config_invalid_memory_format(self):
        """Test resource configuration validation with invalid memory format."""
        resources = {
            "cpu_limit": "1.0",
            "cpu_request": "0.5",
            "memory_limit": "invalid-memory",  # Invalid format
            "memory_request": "128Mi",
            "disk_limit": "1Gi",
        }

        manager = ContainerConfigManager()
        result = manager._validate_resource_config(resources)

        assert result.valid is False
        assert any("Invalid memory limit format" in error for error in result.errors)

    @pytest.mark.slow
    def test_validate_container_environment_complete(self):
        """Test complete container environment validation."""
        # Set up valid configuration
        os.environ.update(
            {
                "CONTAINER_DATABASE_REQUIRED": "rpa_db",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/rpa_db",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_SERVICE_REQUIRED": "prefect",
                "CONTAINER_SERVICE_PREFECT_HEALTH_ENDPOINT": "http://prefect:4200/api/health",
                "CONTAINER_SECURITY_USER_ID": "1000",
                "CONTAINER_SECURITY_GROUP_ID": "1000",
                "CONTAINER_RESOURCE_CPU_LIMIT": "1.0",
                "CONTAINER_RESOURCE_CPU_REQUEST": "0.5",
                "CONTAINER_RESOURCE_MEMORY_LIMIT": "512Mi",
                "CONTAINER_RESOURCE_MEMORY_REQUEST": "128Mi",
            }
        )

        manager = ContainerConfigManager()
        result = manager.validate_container_environment()

        assert result.valid is True
        assert "config" in result.details
        assert "database_validation" in result.details
        assert "service_validation" in result.details
        assert "security_validation" in result.details
        assert "resource_validation" in result.details

    @pytest.mark.slow
    def test_validate_container_environment_with_errors(self):
        """Test container environment validation with configuration errors."""
        # Set up invalid configuration
        os.environ.update(
            {
                "CONTAINER_DATABASE_REQUIRED": "rpa_db",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "invalid://connection",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "mysql",  # Unsupported
                "CONTAINER_SECURITY_USER_ID": "0",  # Root user
                "CONTAINER_RESOURCE_CPU_LIMIT": "1.0",
                "CONTAINER_RESOURCE_CPU_REQUEST": "2.0",  # Exceeds limit
            }
        )

        manager = ContainerConfigManager()
        result = manager.validate_container_environment()

        assert result.valid is False
        assert len(result.errors) > 0

    @patch("requests.get")
    def test_wait_for_dependencies_success(self, mock_get):
        """Test waiting for dependencies with successful health checks."""
        # Mock successful health check responses
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        os.environ.update(
            {
                "CONTAINER_SERVICE_REQUIRED": "prefect",
                "CONTAINER_SERVICE_PREFECT_HEALTH_ENDPOINT": "http://prefect:4200/api/health",
            }
        )

        manager = ContainerConfigManager()
        result = manager.wait_for_dependencies(timeout=10)

        assert result is True
        mock_get.assert_called()

    @pytest.mark.slow
    @patch("requests.get")
    def test_wait_for_dependencies_timeout(self, mock_get):
        """Test waiting for dependencies with timeout."""
        # Mock failed health check responses
        mock_get.side_effect = Exception("Connection refused")

        os.environ.update(
            {
                "CONTAINER_SERVICE_REQUIRED": "prefect",
                "CONTAINER_SERVICE_PREFECT_HEALTH_ENDPOINT": "http://prefect:4200/api/health",
            }
        )

        manager = ContainerConfigManager()
        result = manager.wait_for_dependencies(timeout=1)  # Short timeout for test

        assert result is False

    def test_wait_for_dependencies_no_services(self):
        """Test waiting for dependencies when no services are configured."""
        manager = ContainerConfigManager()
        result = manager.wait_for_dependencies()

        assert result is True  # Should return True when no dependencies

    def test_generate_startup_report_success(self):
        """Test generating startup report with successful validation."""
        # Set up valid configuration
        os.environ.update(
            {
                "CONTAINER_DATABASE_REQUIRED": "rpa_db",
                "CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING": "postgresql://user:pass@localhost:5432/rpa_db",
                "CONTAINER_DATABASE_RPA_DB_TYPE": "postgresql",
                "CONTAINER_SECURITY_USER_ID": "1000",
            }
        )

        manager = ContainerConfigManager(flow_name="rpa1", environment="test")
        report = manager.generate_startup_report()

        assert isinstance(report, StartupReport)
        assert report.environment == "test"
        assert report.flow_name == "rpa1"
        assert report.overall_status in ["success", "warning", "error"]
        assert isinstance(report.startup_duration, float)
        assert isinstance(report.recommendations, list)

    def test_generate_startup_report_with_errors(self):
        """Test generating startup report with validation errors."""
        # Set up invalid configuration
        os.environ.update(
            {
                "CONTAINER_SECURITY_USER_ID": "0"  # Root user - should cause error
            }
        )

        manager = ContainerConfigManager()
        report = manager.generate_startup_report()

        assert report.overall_status == "error"
        assert len(report.recommendations) > 0
        assert any("Fix configuration errors" in rec for rec in report.recommendations)

    def test_memory_format_validation(self):
        """Test memory format validation helper method."""
        manager = ContainerConfigManager()

        # Valid formats
        assert manager._validate_memory_format("512Mi") is True
        assert manager._validate_memory_format("1Gi") is True
        assert manager._validate_memory_format("2048Ki") is True
        assert manager._validate_memory_format("1.5Gi") is True
        assert manager._validate_memory_format("100M") is True

        # Invalid formats
        assert manager._validate_memory_format("invalid") is False
        assert manager._validate_memory_format("512") is False
        assert manager._validate_memory_format("1.5.5Gi") is False

    def test_connection_string_format_validation(self):
        """Test connection string format validation helper method."""
        manager = ContainerConfigManager()

        # Valid PostgreSQL connection strings
        assert (
            manager._validate_connection_string_format(
                "postgresql://user:pass@localhost:5432/db", "postgresql"
            )
            is True
        )
        assert (
            manager._validate_connection_string_format(
                "postgres://user:pass@localhost:5432/db", "postgresql"
            )
            is True
        )

        # Valid SQL Server connection strings
        assert (
            manager._validate_connection_string_format(
                "mssql://user:pass@localhost:1433/db", "sqlserver"
            )
            is True
        )
        assert (
            manager._validate_connection_string_format(
                "sqlserver://user:pass@localhost:1433/db", "sqlserver"
            )
            is True
        )

        # Invalid connection strings
        assert (
            manager._validate_connection_string_format(
                "mysql://user:pass@localhost:3306/db", "postgresql"
            )
            is False
        )
        assert (
            manager._validate_connection_string_format(
                "invalid://connection", "postgresql"
            )
            is False
        )

    def test_generate_recommendations(self):
        """Test recommendation generation based on validation results."""
        manager = ContainerConfigManager()

        # Test with errors
        validation_with_errors = ValidationResult(
            valid=False, errors=["Configuration error"], warnings=[], details={}
        )
        recommendations = manager._generate_recommendations(validation_with_errors)
        assert any("Fix configuration errors" in rec for rec in recommendations)

        # Test with warnings
        validation_with_warnings = ValidationResult(
            valid=True, errors=[], warnings=["Configuration warning"], details={}
        )
        recommendations = manager._generate_recommendations(validation_with_warnings)
        assert any("Review configuration warnings" in rec for rec in recommendations)

        # Test with no issues
        validation_clean = ValidationResult(
            valid=True, errors=[], warnings=[], details={}
        )
        recommendations = manager._generate_recommendations(validation_clean)
        assert any("ready for deployment" in rec for rec in recommendations)


class TestDataClasses:
    """Test suite for data classes used by ContainerConfigManager."""

    def test_database_config_creation(self):
        """Test DatabaseConfig data class creation."""
        db_config = DatabaseConfig(
            name="test_db",
            connection_string="postgresql://user:pass@localhost:5432/test_db",
            database_type="postgresql",
            connection_pool_size=10,
            connection_timeout=60,
            health_check_query="SELECT 1",
            retry_config={"max_attempts": 3},
        )

        assert db_config.name == "test_db"
        assert db_config.connection_pool_size == 10
        assert db_config.retry_config["max_attempts"] == 3

    def test_service_dependency_creation(self):
        """Test ServiceDependency data class creation."""
        service = ServiceDependency(
            service_name="prefect",
            health_endpoint="http://prefect:4200/api/health",
            timeout=45,
            retry_attempts=5,
            required=True,
        )

        assert service.service_name == "prefect"
        assert service.timeout == 45
        assert service.required is True

    def test_validation_result_creation(self):
        """Test ValidationResult data class creation."""
        result = ValidationResult(
            valid=False,
            errors=["Error 1", "Error 2"],
            warnings=["Warning 1"],
            details={"key": "value"},
        )

        assert result.valid is False
        assert len(result.errors) == 2
        assert len(result.warnings) == 1
        assert result.details["key"] == "value"

    def test_startup_report_creation(self):
        """Test StartupReport data class creation."""
        validation = ValidationResult(True, [], [], {})
        report = StartupReport(
            timestamp=datetime.now(),
            environment="test",
            flow_name="rpa1",
            validation_results={"env": validation},
            overall_status="success",
            startup_duration=1.5,
            recommendations=["All good"],
        )

        assert report.environment == "test"
        assert report.flow_name == "rpa1"
        assert report.overall_status == "success"
        assert report.startup_duration == 1.5
