"""Integration tests for DistributedProcessor with configuration."""

import os
from unittest.mock import MagicMock, patch

import pytest

from core.config import ConfigManager
from core.database import DatabaseManager
from core.distributed import DistributedProcessor

pytestmark = pytest.mark.integration


class TestDistributedProcessorConfigIntegration:
    """Test DistributedProcessor integration with configuration system."""

    def test_distributed_processor_initialization_with_config(self):
        """Test DistributedProcessor initialization with configuration manager."""
        # Mock DatabaseManager instances
        rpa_db_manager = MagicMock(spec=DatabaseManager)
        rpa_db_manager.logger = MagicMock()

        source_db_manager = MagicMock(spec=DatabaseManager)

        # Create config manager with test environment
        config_manager = ConfigManager("test_flow", "development")

        env_vars = {
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "75",
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_MAX_RETRIES": "5",
            "DEVELOPMENT_GLOBAL_RPA_DB_TYPE": "postgresql",
            "DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE": "sqlserver",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING": "mssql://test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            processor = DistributedProcessor(
                rpa_db_manager,
                source_db_manager,
                config_manager
            )

            assert processor.config["default_batch_size"] == 75
            assert processor.config["max_retries"] == 5
            assert processor.config_manager == config_manager

    def test_distributed_processor_config_validation_failure(self):
        """Test DistributedProcessor initialization fails with invalid config."""
        # Mock DatabaseManager instances
        rpa_db_manager = MagicMock(spec=DatabaseManager)
        rpa_db_manager.logger = MagicMock()

        config_manager = ConfigManager("test_flow", "development")

        # Invalid configuration (batch size too large)
        env_vars = {
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "2000",  # Invalid
            "DEVELOPMENT_GLOBAL_RPA_DB_TYPE": "postgresql",
            "DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError, match="Failed to load distributed processing configuration"):
                DistributedProcessor(rpa_db_manager, None, config_manager)

    def test_distributed_processor_missing_database_config(self):
        """Test DistributedProcessor initialization fails with missing database config."""
        # Mock DatabaseManager instances
        rpa_db_manager = MagicMock(spec=DatabaseManager)
        rpa_db_manager.logger = MagicMock()

        config_manager = ConfigManager("test_flow", "development")

        # Missing required database configuration
        env_vars = {
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_REQUIRED_DATABASES": "rpa_db,missing_db",
            "DEVELOPMENT_GLOBAL_RPA_DB_TYPE": "postgresql",
            "DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
            # missing_db configuration is missing
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(RuntimeError, match="Required database 'missing_db'"):
                DistributedProcessor(rpa_db_manager, None, config_manager)

    def test_distributed_processor_flow_specific_config_override(self):
        """Test that flow-specific configuration overrides work in DistributedProcessor."""
        # Mock DatabaseManager instances
        rpa_db_manager = MagicMock(spec=DatabaseManager)
        rpa_db_manager.logger = MagicMock()

        # Test with RPA1 flow-specific configuration
        config_manager = ConfigManager("rpa1", "development")

        env_vars = {
            # Global configuration
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "100",
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_MAX_RETRIES": "3",

            # RPA1-specific overrides
            "DEVELOPMENT_RPA1_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "25",
            "DEVELOPMENT_RPA1_DISTRIBUTED_PROCESSOR_MAX_RETRIES": "2",

            # Required database config
            "DEVELOPMENT_GLOBAL_RPA_DB_TYPE": "postgresql",
            "DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE": "sqlserver",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING": "mssql://test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            processor = DistributedProcessor(rpa_db_manager, None, config_manager)

            # Should use RPA1-specific values
            assert processor.config["default_batch_size"] == 25
            assert processor.config["max_retries"] == 2

    def test_distributed_processor_environment_specific_config(self):
        """Test DistributedProcessor with different environment configurations."""
        environments = [
            ("development", 50, 1),
            ("staging", 100, 2),
            ("production", 200, 4)
        ]

        for env, expected_batch_size, expected_timeout in environments:
            # Mock DatabaseManager instances
            rpa_db_manager = MagicMock(spec=DatabaseManager)
            rpa_db_manager.logger = MagicMock()

            config_manager = ConfigManager("test_flow", env)

            env_vars = {
                f"{env.upper()}_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": str(expected_batch_size),
                f"{env.upper()}_GLOBAL_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS": str(expected_timeout),
                f"{env.upper()}_GLOBAL_RPA_DB_TYPE": "postgresql",
                f"{env.upper()}_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
                f"{env.upper()}_GLOBAL_SURVEYHUB_TYPE": "sqlserver",
                f"{env.upper()}_GLOBAL_SURVEYHUB_CONNECTION_STRING": "mssql://test",
            }

            with patch.dict(os.environ, env_vars, clear=True):
                processor = DistributedProcessor(rpa_db_manager, None, config_manager)

                assert processor.config["default_batch_size"] == expected_batch_size
                assert processor.config["cleanup_timeout_hours"] == expected_timeout

    def test_distributed_processor_default_config_manager(self):
        """Test DistributedProcessor with default config manager (None provided)."""
        # Mock DatabaseManager instances
        rpa_db_manager = MagicMock(spec=DatabaseManager)
        rpa_db_manager.logger = MagicMock()

        env_vars = {
            "DEVELOPMENT_GLOBAL_RPA_DB_TYPE": "postgresql",
            "DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE": "sqlserver",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING": "mssql://test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # Should create default ConfigManager when None provided
            processor = DistributedProcessor(rpa_db_manager, None, None)

            assert processor.config_manager is not None
            assert isinstance(processor.config_manager, ConfigManager)
            assert processor.config["default_batch_size"] == 100  # Default value

    def test_distributed_processor_config_logging(self):
        """Test that DistributedProcessor logs configuration on initialization."""
        # Mock DatabaseManager instances
        rpa_db_manager = MagicMock(spec=DatabaseManager)
        mock_logger = MagicMock()
        rpa_db_manager.logger = mock_logger

        config_manager = ConfigManager("test_flow", "development")

        env_vars = {
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "150",
            "DEVELOPMENT_GLOBAL_RPA_DB_TYPE": "postgresql",
            "DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE": "sqlserver",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING": "mssql://test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            DistributedProcessor(rpa_db_manager, None, config_manager)

            # Verify that initialization was logged with config information
            mock_logger.info.assert_called()
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]

            # Should log initialization with config
            init_log = next((log for log in log_calls if "DistributedProcessor initialized" in log), None)
            assert init_log is not None
            assert "config:" in init_log

    def test_distributed_processor_config_access_methods(self):
        """Test accessing configuration through DistributedProcessor methods."""
        # Mock DatabaseManager instances
        rpa_db_manager = MagicMock(spec=DatabaseManager)
        rpa_db_manager.logger = MagicMock()

        config_manager = ConfigManager("test_flow", "development")

        env_vars = {
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "80",
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS": "3",
            "DEVELOPMENT_GLOBAL_RPA_DB_TYPE": "postgresql",
            "DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE": "sqlserver",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING": "mssql://test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            processor = DistributedProcessor(rpa_db_manager, None, config_manager)

            # Test direct config access
            assert processor.config["default_batch_size"] == 80
            assert processor.config["cleanup_timeout_hours"] == 3

            # Test config manager access
            validation_result = processor.config_manager.validate_distributed_processing_setup()
            assert validation_result["valid"] is True
            assert validation_result["config"]["default_batch_size"] == 80

    def test_distributed_processor_disabled_configuration(self):
        """Test DistributedProcessor behavior when distributed processing is disabled."""
        # Mock DatabaseManager instances
        rpa_db_manager = MagicMock(spec=DatabaseManager)
        rpa_db_manager.logger = MagicMock()

        config_manager = ConfigManager("test_flow", "development")

        env_vars = {
            "DEVELOPMENT_GLOBAL_DISTRIBUTED_PROCESSOR_ENABLED": "false",
            "DEVELOPMENT_GLOBAL_RPA_DB_TYPE": "postgresql",
            "DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE": "sqlserver",
            "DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING": "mssql://test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            processor = DistributedProcessor(rpa_db_manager, None, config_manager)

            # Should still initialize successfully but with disabled flag
            assert processor.config["enable_distributed_processing"] is False

            # Validation should show warnings
            validation_result = processor.config_manager.validate_distributed_processing_setup()
            assert validation_result["valid"] is True
            assert any("disabled" in warning for warning in validation_result["warnings"])
