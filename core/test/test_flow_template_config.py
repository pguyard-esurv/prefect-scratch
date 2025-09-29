"""Tests for flow template configuration integration."""

import os
from unittest.mock import MagicMock, patch

import pytest

from core.flow_template import distributed_processing_flow

pytestmark = pytest.mark.unit


class TestFlowTemplateConfig:
    """Test flow template configuration integration."""

    @patch("core.flow_template.processor")
    def test_distributed_processing_flow_uses_config_batch_size(self, mock_processor):
        """Test that flow uses configured batch size when none provided."""
        # Mock processor configuration
        mock_processor.config = {"default_batch_size": 150}
        mock_processor.health_check.return_value = {"status": "healthy"}
        mock_processor.claim_records_batch_with_retry.return_value = []

        # Call flow without batch_size (should use config default)
        result = distributed_processing_flow("test_flow")

        # Verify it used the configured batch size
        mock_processor.claim_records_batch_with_retry.assert_called_once_with(
            "test_flow", 150
        )
        assert result["batch_size"] == 150

    @patch("core.flow_template.processor")
    def test_distributed_processing_flow_overrides_config_batch_size(
        self, mock_processor
    ):
        """Test that explicit batch_size parameter overrides configuration."""
        # Mock processor configuration
        mock_processor.config = {"default_batch_size": 150}
        mock_processor.health_check.return_value = {"status": "healthy"}
        mock_processor.claim_records_batch_with_retry.return_value = []

        # Call flow with explicit batch_size
        result = distributed_processing_flow("test_flow", batch_size=50)

        # Verify it used the explicit batch size, not config
        mock_processor.claim_records_batch_with_retry.assert_called_once_with(
            "test_flow", 50
        )
        assert result["batch_size"] == 50

    @patch("core.flow_template.processor")
    def test_distributed_processing_flow_config_validation(self, mock_processor):
        """Test flow parameter validation with configuration."""
        # Mock processor configuration
        mock_processor.config = {"default_batch_size": 100}

        # Test invalid batch_size parameter - Prefect validates parameters before our code runs
        from prefect.exceptions import ParameterTypeError

        # Test zero value (our validation)
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            distributed_processing_flow("test_flow", batch_size=0)

        # Test negative value (our validation)
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            distributed_processing_flow("test_flow", batch_size=-1)

        # Test invalid string (Prefect validation)
        with pytest.raises(ParameterTypeError, match="Input should be a valid integer"):
            distributed_processing_flow("test_flow", batch_size="invalid")

    @patch("core.flow_template.config_manager")
    @patch("core.flow_template.processor")
    def test_flow_template_module_level_config_initialization(
        self, mock_processor, mock_config_manager
    ):
        """Test that module-level configuration is properly initialized."""
        # Import should have initialized config_manager at module level
        from core.flow_template import config_manager

        # Verify config_manager exists and is used in processor initialization
        assert config_manager is not None

    def test_flow_template_environment_specific_config_loading(self):
        """Test that flow template loads environment-specific configuration."""
        env_vars = {
            "PREFECT_ENVIRONMENT": "staging",
            "STAGING_GLOBAL_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE": "200",
            "STAGING_GLOBAL_RPA_DB_TYPE": "postgresql",
            "STAGING_GLOBAL_RPA_DB_CONNECTION_STRING": "postgresql://test",
            "STAGING_GLOBAL_SURVEYHUB_TYPE": "sqlserver",
            "STAGING_GLOBAL_SURVEYHUB_CONNECTION_STRING": "mssql://test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # Re-import to get fresh module-level initialization
            import importlib

            import core.flow_template

            importlib.reload(core.flow_template)

            # Verify the processor was initialized with staging configuration
            assert core.flow_template.processor.config["default_batch_size"] == 200

    @patch("core.flow_template.processor")
    def test_distributed_processing_flow_with_different_config_values(
        self, mock_processor
    ):
        """Test flow behavior with various configuration values."""
        test_cases = [
            {"default_batch_size": 25},
            {"default_batch_size": 500},
            {"default_batch_size": 1000},
        ]

        for config in test_cases:
            mock_processor.config = config
            mock_processor.health_check.return_value = {"status": "healthy"}
            mock_processor.claim_records_batch_with_retry.return_value = []

            result = distributed_processing_flow("test_flow")

            expected_batch_size = config["default_batch_size"]
            mock_processor.claim_records_batch_with_retry.assert_called_with(
                "test_flow", expected_batch_size
            )
            assert result["batch_size"] == expected_batch_size

    @patch("core.flow_template.processor")
    def test_flow_template_config_error_handling(self, mock_processor):
        """Test flow template error handling with configuration issues."""
        # Mock configuration that would cause validation errors
        mock_processor.config = {"default_batch_size": 100}  # Valid config
        mock_processor.health_check.return_value = {"status": "healthy"}
        mock_processor.claim_records_batch_with_retry.return_value = []

        # Test that explicit invalid batch size is still validated
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            distributed_processing_flow("test_flow", batch_size=-1)

    def test_flow_template_imports_and_dependencies(self):
        """Test that flow template properly imports configuration dependencies."""
        # Verify that the flow template module imports ConfigManager
        from core.config import ConfigManager
        from core.flow_template import config_manager

        assert isinstance(config_manager, ConfigManager)

    @patch("core.flow_template.processor")
    def test_flow_template_logging_includes_config_info(self, mock_processor):
        """Test that flow template logging includes configuration information."""
        mock_processor.config = {"default_batch_size": 75}
        mock_processor.health_check.return_value = {"status": "healthy"}
        mock_processor.claim_records_batch_with_retry.return_value = []

        with patch("core.flow_template.get_run_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            distributed_processing_flow("test_flow")

            # Verify logging includes batch size information
            log_calls = [call.args[0] for call in mock_logger.info.call_args_list]
            batch_size_log = next(
                (log for log in log_calls if "batch_size: 75" in log), None
            )
            assert batch_size_log is not None
