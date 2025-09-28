"""Simplified tests for distributed processing configuration."""

from unittest.mock import patch

import pytest

from core.config import ConfigManager

pytestmark = pytest.mark.unit


class TestDistributedProcessingConfigSimple:
    """Test distributed processing configuration functionality."""

    def test_get_distributed_config_with_mocked_values(self):
        """Test getting distributed config with mocked configuration values."""
        config_manager = ConfigManager()

        # Mock the get_config method to return our test values
        def mock_get_config(key, default=None):
            config_map = {
                "DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "75",
                "DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS": "2",
                "DISTRIBUTED_PROCESSOR_MAX_RETRIES": "4",
                "DISTRIBUTED_PROCESSOR_HEALTH_CHECK_INTERVAL": "600",
                "DISTRIBUTED_PROCESSOR_ENABLED": "true",
                "DISTRIBUTED_PROCESSOR_REQUIRED_DATABASES": "rpa_db,custom_db",
                "RPA_DB_TYPE": "postgresql",
                "RPA_DB_CONNECTION_STRING": "postgresql://test",
                "CUSTOM_DB_TYPE": "postgresql",
                "CUSTOM_DB_CONNECTION_STRING": "postgresql://test",
            }
            return config_map.get(key, default)

        with patch.object(config_manager, 'get_config', side_effect=mock_get_config):
            config = config_manager.get_distributed_config()

            assert config["default_batch_size"] == 75
            assert config["cleanup_timeout_hours"] == 2
            assert config["max_retries"] == 4
            assert config["health_check_interval"] == 600
            assert config["enable_distributed_processing"] is True
            assert config["required_databases"] == ["rpa_db", "custom_db"]

    def test_get_int_config_validation(self):
        """Test integer configuration validation."""
        config_manager = ConfigManager()

        # Test valid integer (default when no config)
        with patch.object(config_manager, 'get_config', return_value=None):
            assert config_manager._get_int_config("TEST_KEY", 10) == 10

        # Test string conversion
        with patch.object(config_manager, 'get_config', return_value="50"):
            assert config_manager._get_int_config("TEST_KEY", 10) == 50

        # Test zero value (invalid)
        with patch.object(config_manager, 'get_config', return_value="0"):
            with pytest.raises(ValueError, match="must be positive"):
                config_manager._get_int_config("TEST_KEY", 10)

        # Test negative value (invalid)
        with patch.object(config_manager, 'get_config', return_value="-5"):
            with pytest.raises(ValueError, match="must be positive"):
                config_manager._get_int_config("TEST_KEY", 10)

        # Test invalid string
        with patch.object(config_manager, 'get_config', return_value="invalid"):
            with pytest.raises(ValueError, match="must be an integer"):
                config_manager._get_int_config("TEST_KEY", 10)

    def test_get_bool_config_validation(self):
        """Test boolean configuration validation."""
        config_manager = ConfigManager()

        # Test valid boolean (default when no config)
        with patch.object(config_manager, 'get_config', return_value=None):
            assert config_manager._get_bool_config("TEST_KEY", True) is True

        # Test true values
        true_values = ["true", "1", "yes", "on", "enabled", "TRUE", "Yes", "ON"]
        for value in true_values:
            with patch.object(config_manager, 'get_config', return_value=value):
                assert config_manager._get_bool_config("TEST_KEY", False) is True

        # Test false values
        false_values = ["false", "0", "no", "off", "disabled", "FALSE", "No", "OFF"]
        for value in false_values:
            with patch.object(config_manager, 'get_config', return_value=value):
                assert config_manager._get_bool_config("TEST_KEY", True) is False

        # Test invalid string
        with patch.object(config_manager, 'get_config', return_value="maybe"):
            with pytest.raises(ValueError, match="must be a boolean value"):
                config_manager._get_bool_config("TEST_KEY", True)

    def test_validate_distributed_config_batch_size(self):
        """Test batch size validation."""
        config_manager = ConfigManager()

        # Test invalid batch sizes
        invalid_configs = [
            {"default_batch_size": 0, "cleanup_timeout_hours": 1, "max_retries": 3, "health_check_interval": 300},
            {"default_batch_size": -1, "cleanup_timeout_hours": 1, "max_retries": 3, "health_check_interval": 300},
            {"default_batch_size": 1001, "cleanup_timeout_hours": 1, "max_retries": 3, "health_check_interval": 300},
        ]

        for config in invalid_configs:
            config["required_databases"] = ["rpa_db"]
            with pytest.raises(ValueError, match="default_batch_size must be between 1 and 1000"):
                config_manager._validate_distributed_config(config)

    def test_validate_distributed_config_timeout_hours(self):
        """Test timeout hours validation."""
        config_manager = ConfigManager()

        # Test invalid timeout hours
        invalid_configs = [
            {"default_batch_size": 100, "cleanup_timeout_hours": 0, "max_retries": 3, "health_check_interval": 300},
            {"default_batch_size": 100, "cleanup_timeout_hours": -1, "max_retries": 3, "health_check_interval": 300},
            {"default_batch_size": 100, "cleanup_timeout_hours": 25, "max_retries": 3, "health_check_interval": 300},
        ]

        for config in invalid_configs:
            config["required_databases"] = ["rpa_db"]
            with pytest.raises(ValueError, match="cleanup_timeout_hours must be between 1 and 24"):
                config_manager._validate_distributed_config(config)

    def test_validate_distributed_config_max_retries(self):
        """Test max retries validation."""
        config_manager = ConfigManager()

        # Test invalid max retries
        invalid_configs = [
            {"default_batch_size": 100, "cleanup_timeout_hours": 1, "max_retries": 0, "health_check_interval": 300},
            {"default_batch_size": 100, "cleanup_timeout_hours": 1, "max_retries": -1, "health_check_interval": 300},
            {"default_batch_size": 100, "cleanup_timeout_hours": 1, "max_retries": 11, "health_check_interval": 300},
        ]

        for config in invalid_configs:
            config["required_databases"] = ["rpa_db"]
            with pytest.raises(ValueError, match="max_retries must be between 1 and 10"):
                config_manager._validate_distributed_config(config)

    def test_validate_distributed_config_health_check_interval(self):
        """Test health check interval validation."""
        config_manager = ConfigManager()

        # Test invalid health check intervals
        invalid_configs = [
            {"default_batch_size": 100, "cleanup_timeout_hours": 1, "max_retries": 3, "health_check_interval": 59},
            {"default_batch_size": 100, "cleanup_timeout_hours": 1, "max_retries": 3, "health_check_interval": 3601},
        ]

        for config in invalid_configs:
            config["required_databases"] = ["rpa_db"]
            with pytest.raises(ValueError, match="health_check_interval must be between 60 and 3600 seconds"):
                config_manager._validate_distributed_config(config)

    def test_configuration_type_conversion_edge_cases(self):
        """Test edge cases in configuration type conversion."""
        config_manager = ConfigManager()

        # Test boolean edge cases with whitespace
        with patch.object(config_manager, 'get_config', return_value="  TRUE  "):
            assert config_manager._get_bool_config("TEST_BOOL", False) is True

        # Test integer edge cases - minimum valid value
        with patch.object(config_manager, 'get_config', return_value="1"):
            assert config_manager._get_int_config("TEST_INT", 10) == 1

        # Test empty string handling (should use default)
        with patch.object(config_manager, 'get_config', return_value=""):
            assert config_manager._get_int_config("TEST_EMPTY", 10) == 10

    def test_validate_distributed_processing_setup_failure(self):
        """Test distributed processing setup validation failure."""
        config_manager = ConfigManager()

        # Mock invalid configuration
        def mock_get_config(key, default=None):
            config_map = {
                "DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "0",  # Invalid
                "DISTRIBUTED_PROCESSOR_REQUIRED_DATABASES": "missing_db",
            }
            return config_map.get(key, default)

        with patch.object(config_manager, 'get_config', side_effect=mock_get_config):
            result = config_manager.validate_distributed_processing_setup()

            assert result["valid"] is False
            assert len(result["errors"]) > 0
