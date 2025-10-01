"""
Simple UI Integration Tests

Basic tests to verify UI integration functionality works.
"""

from unittest.mock import patch

import pytest

from deployment_system.cli.ui_commands import UICLI
from deployment_system.ui import (
    DeploymentStatusChecker,
    TroubleshootingUtilities,
    UIClient,
    UIValidator,
)


class TestUIIntegrationSimple:
    """Simple integration tests for UI functionality."""

    def test_ui_client_initialization(self):
        """Test UI client can be initialized."""
        client = UIClient("http://localhost:4200/api", "http://localhost:4200")
        assert client.api_url == "http://localhost:4200/api"
        assert client.ui_url == "http://localhost:4200"

    def test_ui_client_derive_url(self):
        """Test UI URL derivation."""
        client = UIClient()

        # Test with API URL
        ui_url = client._derive_ui_url("http://localhost:4200/api")
        assert ui_url == "http://localhost:4200"

        # Test with base URL
        ui_url = client._derive_ui_url("http://localhost:4200")
        assert ui_url == "http://localhost:4200"

        # Test with None
        ui_url = client._derive_ui_url(None)
        assert ui_url is None

    def test_deployment_status_checker_initialization(self):
        """Test deployment status checker can be initialized."""
        checker = DeploymentStatusChecker("http://localhost:4200/api")
        assert checker.prefect_client.api_url == "http://localhost:4200/api"

    def test_ui_validator_initialization(self):
        """Test UI validator can be initialized."""
        validator = UIValidator("http://localhost:4200/api")
        assert validator.ui_client.api_url == "http://localhost:4200/api"

    def test_troubleshooting_utilities_initialization(self):
        """Test troubleshooting utilities can be initialized."""
        troubleshooter = TroubleshootingUtilities("http://localhost:4200/api")
        assert troubleshooter.api_url == "http://localhost:4200/api"

    def test_ui_cli_initialization(self):
        """Test UI CLI can be initialized."""
        cli = UICLI("http://localhost:4200/api")
        assert cli.ui_client.api_url == "http://localhost:4200/api"

    @patch("deployment_system.ui.ui_client.get_client")
    def test_ui_client_run_async_helper(self, mock_get_client):
        """Test the run_async helper method."""
        client = UIClient()

        async def test_coro():
            return "test_result"

        # Mock the asyncio.run to avoid actual async execution in test
        with patch("asyncio.run") as mock_run:
            mock_run.return_value = "test_result"
            result = client.run_async(test_coro())
            assert result == "test_result"

    def test_ui_validator_metadata_validation(self):
        """Test deployment metadata validation."""
        validator = UIValidator()

        # Valid metadata
        valid_deployment = {
            "name": "test-deployment",
            "flow_name": "test-flow",
            "work_pool_name": "test-pool",
            "description": "Test deployment",
            "tags": ["test"],
        }

        issues = validator._validate_deployment_metadata(valid_deployment)
        assert len(issues) == 0

        # Invalid metadata
        invalid_deployment = {
            "name": "",  # Empty name
            "flow_name": "test-flow",
            "work_pool_name": "",  # Empty work pool
            "description": "x" * 600,  # Too long
            "tags": ["tag"] * 25,  # Too many tags
        }

        issues = validator._validate_deployment_metadata(invalid_deployment)
        assert len(issues) > 0

    def test_troubleshooting_severity_determination(self):
        """Test troubleshooting severity determination."""
        troubleshooter = TroubleshootingUtilities()

        # Critical case
        critical_diagnosis = {
            "api_diagnosis": {"configured": False, "responding": False},
            "ui_diagnosis": {"responding": True},
        }
        assert troubleshooter._determine_severity(critical_diagnosis) == "critical"

        # Error case
        error_diagnosis = {
            "api_diagnosis": {"configured": True, "responding": True},
            "ui_diagnosis": {"responding": False},
        }
        assert troubleshooter._determine_severity(error_diagnosis) == "error"

        # Warning case
        warning_diagnosis = {
            "api_diagnosis": {
                "configured": True,
                "responding": True,
                "issues": ["Minor issue"],
            },
            "ui_diagnosis": {"responding": True},
        }
        assert troubleshooter._determine_severity(warning_diagnosis) == "warning"

        # Info case
        info_diagnosis = {
            "api_diagnosis": {"configured": True, "responding": True, "issues": []},
            "ui_diagnosis": {"responding": True, "issues": []},
        }
        assert troubleshooter._determine_severity(info_diagnosis) == "info"

    def test_ui_cli_format_methods(self):
        """Test UI CLI formatting methods."""
        cli = UICLI()

        # Test connectivity report formatting
        healthy_report = {
            "success": True,
            "api_connectivity": {
                "connected": True,
                "api_url": "http://localhost:4200/api",
            },
            "ui_accessibility": {"accessible": True, "ui_url": "http://localhost:4200"},
            "overall_status": "healthy",
        }

        formatted = cli.format_connectivity_report(healthy_report)
        assert "✅" in formatted
        assert "UI Connectivity Check" in formatted

        # Test error report formatting
        error_report = {"success": False, "error": "Connection failed"}

        formatted = cli.format_connectivity_report(error_report)
        assert "❌" in formatted
        assert "Connection failed" in formatted

    def test_deployment_health_formatting(self):
        """Test deployment health report formatting."""
        cli = UICLI()

        # Healthy deployment
        healthy_result = {
            "success": True,
            "health_result": {
                "full_name": "test-flow/test-deployment",
                "healthy": True,
                "status": "healthy",
                "checks": {"exists": True, "work_pool_valid": True, "ui_visible": True},
                "issues": [],
                "recommendations": [],
            },
        }

        formatted = cli.format_deployment_health(healthy_result)
        assert "✅" in formatted
        assert "test-flow/test-deployment" in formatted
        assert "HEALTHY" in formatted

        # Unhealthy deployment
        unhealthy_result = {
            "success": True,
            "health_result": {
                "full_name": "test-flow/test-deployment",
                "healthy": False,
                "status": "unhealthy",
                "checks": {
                    "exists": True,
                    "work_pool_valid": False,
                    "ui_visible": False,
                },
                "issues": ["Work pool invalid"],
                "recommendations": ["Fix work pool"],
            },
        }

        formatted = cli.format_deployment_health(unhealthy_result)
        assert "❌" in formatted
        assert "Work pool invalid" in formatted
        assert "Fix work pool" in formatted

    def test_troubleshooting_report_formatting(self):
        """Test troubleshooting report formatting."""
        cli = UICLI()

        # Info level report
        info_report = {
            "success": True,
            "diagnosis": {
                "severity": "info",
                "timestamp": "2023-01-01T00:00:00Z",
                "connectivity_diagnosis": {
                    "api_diagnosis": {"responding": True},
                    "ui_diagnosis": {"responding": True},
                },
                "recommendations": ["All systems operational"],
            },
        }

        formatted = cli.format_troubleshooting_report(info_report)
        assert "ℹ️" in formatted
        assert "INFO" in formatted
        assert "All systems operational" in formatted

        # Critical level report
        critical_report = {
            "success": True,
            "diagnosis": {
                "severity": "critical",
                "timestamp": "2023-01-01T00:00:00Z",
                "connectivity_diagnosis": {
                    "api_diagnosis": {"responding": False},
                    "ui_diagnosis": {"responding": False},
                },
                "recommendations": ["Fix API connectivity", "Fix UI connectivity"],
            },
        }

        formatted = cli.format_troubleshooting_report(critical_report)
        assert "🚨" in formatted
        assert "CRITICAL" in formatted


class TestUIIntegrationMocked:
    """Test UI integration with mocked dependencies."""

    @pytest.fixture
    def mock_ui_components(self):
        """Mock all UI components."""
        with (
            patch("deployment_system.ui.ui_client.PrefectClient") as mock_prefect,
            patch("deployment_system.ui.ui_client.httpx.AsyncClient") as mock_http,
        ):
            yield mock_prefect, mock_http

    def test_ui_client_with_mocked_dependencies(self, mock_ui_components):
        """Test UI client with mocked dependencies."""
        mock_prefect, mock_http = mock_ui_components

        client = UIClient("http://localhost:4200/api")
        assert client.api_url == "http://localhost:4200/api"
        assert client.ui_url == "http://localhost:4200"

    @patch("deployment_system.cli.ui_commands.UIClient")
    @patch("deployment_system.cli.ui_commands.UIValidator")
    @patch("deployment_system.cli.ui_commands.DeploymentStatusChecker")
    @patch("deployment_system.cli.ui_commands.TroubleshootingUtilities")
    def test_ui_cli_commands_mocked(
        self, mock_troubleshooter, mock_status, mock_validator, mock_ui_client
    ):
        """Test UI CLI commands with mocked components."""
        cli = UICLI()

        # Test check_ui_connectivity
        mock_ui_client.return_value.run_async.return_value = {
            "connected": True,
            "accessible": True,
        }

        result = cli.check_ui_connectivity()
        assert result["success"] is True

        # Test verify_deployment_in_ui
        mock_ui_client.return_value.run_async.return_value = {
            "visible": True,
            "api_exists": True,
        }

        result = cli.verify_deployment_in_ui("test-deployment", "test-flow")
        assert result["success"] is True
        assert result["visible"] is True

        # Test check_deployment_health
        mock_status.return_value.run_async.return_value = {
            "healthy": True,
            "status": "healthy",
        }

        result = cli.check_deployment_health("test-deployment", "test-flow")
        assert result["success"] is True
        assert result["healthy"] is True

    def test_ui_integration_error_handling(self):
        """Test error handling in UI integration."""
        # Test UI client with invalid URL
        client = UIClient("invalid-url")
        assert client.api_url == "invalid-url"

        # Test with None URLs
        client = UIClient(None, None)
        assert client.api_url is None
        assert client.ui_url is None

        # Test CLI with error conditions
        cli = UICLI()

        # Mock an exception in UI client
        with patch.object(
            cli.ui_client, "run_async", side_effect=Exception("Test error")
        ):
            result = cli.check_ui_connectivity()
            assert result["success"] is False
            assert "Test error" in result["error"]
