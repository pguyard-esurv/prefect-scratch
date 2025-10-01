"""
Tests for UI Integration System

Tests for UI client, validator, status checker, and troubleshooting utilities.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deployment_system.ui import (
    DeploymentStatusChecker,
    TroubleshootingUtilities,
    UIClient,
    UIValidator,
)


class TestUIClient:
    """Test UI Client functionality."""

    @pytest.fixture
    def ui_client(self):
        return UIClient("http://localhost:4200/api", "http://localhost:4200")

    @pytest.fixture
    def mock_prefect_client(self):
        with patch("deployment_system.ui.ui_client.PrefectClient") as mock:
            yield mock

    def test_derive_ui_url(self, ui_client):
        """Test UI URL derivation from API URL."""
        # Test normal API URL
        ui_url = ui_client._derive_ui_url("http://localhost:4200/api")
        assert ui_url == "http://localhost:4200"

        # Test API URL without /api suffix
        ui_url = ui_client._derive_ui_url("http://localhost:4200")
        assert ui_url == "http://localhost:4200"

        # Test None API URL
        ui_url = ui_client._derive_ui_url(None)
        assert ui_url is None

    @pytest.mark.asyncio
    async def test_check_api_connectivity_success(self, ui_client, mock_prefect_client):
        """Test successful API connectivity check."""
        mock_client = AsyncMock()
        mock_client.read_flows.return_value = []
        mock_prefect_client.return_value.get_client.return_value = mock_client

        with patch("time.time", side_effect=[0, 0.1]):  # 100ms response time
            result = await ui_client.check_api_connectivity()

        assert result["connected"] is True
        assert result["response_time_ms"] == 100
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_check_api_connectivity_failure(self, ui_client, mock_prefect_client):
        """Test failed API connectivity check."""
        mock_client = AsyncMock()
        mock_client.read_flows.side_effect = Exception("Connection failed")
        mock_prefect_client.return_value.get_client.return_value = mock_client

        result = await ui_client.check_api_connectivity()

        assert result["connected"] is False
        assert "Connection failed" in result["error"]

    @pytest.mark.asyncio
    async def test_check_ui_accessibility_success(self, ui_client):
        """Test successful UI accessibility check."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client

            with patch("time.time", side_effect=[0, 0.05]):  # 50ms response time
                result = await ui_client.check_ui_accessibility()

        assert result["accessible"] is True
        assert result["status_code"] == 200
        assert result["response_time_ms"] == 50

    @pytest.mark.asyncio
    async def test_verify_deployment_in_ui_success(
        self, ui_client, mock_prefect_client
    ):
        """Test successful deployment verification in UI."""
        mock_deployment = {
            "id": "test-id",
            "name": "test-deployment",
            "updated": "2023-01-01T00:00:00Z",
        }

        mock_prefect_client.return_value.get_deployment_by_name.return_value = (
            mock_deployment
        )

        with patch.object(ui_client, "check_ui_accessibility") as mock_ui_check:
            mock_ui_check.return_value = {"accessible": True}

            result = await ui_client.verify_deployment_in_ui(
                "test-deployment", "test-flow"
            )

        assert result["visible"] is True
        assert result["api_exists"] is True
        assert result["ui_accessible"] is True

    @pytest.mark.asyncio
    async def test_verify_deployment_in_ui_not_found(
        self, ui_client, mock_prefect_client
    ):
        """Test deployment verification when deployment not found."""
        mock_prefect_client.return_value.get_deployment_by_name.return_value = None

        result = await ui_client.verify_deployment_in_ui("test-deployment", "test-flow")

        assert result["visible"] is False
        assert result["api_exists"] is False
        assert "Deployment not found via API" in result["error"]

    @pytest.mark.asyncio
    async def test_get_deployment_ui_url(self, ui_client, mock_prefect_client):
        """Test getting deployment UI URL."""
        mock_deployment = {"id": "test-id"}
        mock_prefect_client.return_value.get_deployment_by_name.return_value = (
            mock_deployment
        )

        url = await ui_client.get_deployment_ui_url("test-deployment", "test-flow")

        assert url == "http://localhost:4200/deployments/deployment/test-id"


class TestDeploymentStatusChecker:
    """Test Deployment Status Checker functionality."""

    @pytest.fixture
    def status_checker(self):
        return DeploymentStatusChecker("http://localhost:4200/api")

    @pytest.fixture
    def mock_clients(self):
        with (
            patch(
                "deployment_system.ui.deployment_status.PrefectClient"
            ) as mock_prefect,
            patch("deployment_system.ui.deployment_status.UIClient") as mock_ui,
        ):
            yield mock_prefect, mock_ui

    @pytest.mark.asyncio
    async def test_check_deployment_health_healthy(self, status_checker, mock_clients):
        """Test healthy deployment health check."""
        mock_prefect, mock_ui = mock_clients

        mock_deployment = {
            "id": "test-id",
            "name": "test-deployment",
            "work_pool_name": "test-pool",
            "schedule": None,
        }

        mock_prefect.return_value.get_deployment_by_name.return_value = mock_deployment
        mock_prefect.return_value.validate_work_pool.return_value = True
        mock_ui.return_value.verify_deployment_in_ui.return_value = {"visible": True}

        result = await status_checker.check_deployment_health(
            "test-deployment", "test-flow"
        )

        assert result["healthy"] is True
        assert result["status"] == "healthy"
        assert result["checks"]["exists"] is True
        assert result["checks"]["work_pool_valid"] is True
        assert result["checks"]["ui_visible"] is True

    @pytest.mark.asyncio
    async def test_check_deployment_health_not_found(
        self, status_checker, mock_clients
    ):
        """Test health check for non-existent deployment."""
        mock_prefect, _ = mock_clients
        mock_prefect.return_value.get_deployment_by_name.return_value = None

        result = await status_checker.check_deployment_health(
            "test-deployment", "test-flow"
        )

        assert result["healthy"] is False
        assert result["status"] == "not_found"
        assert "Deployment does not exist" in result["issues"]

    @pytest.mark.asyncio
    async def test_check_deployment_health_invalid_work_pool(
        self, status_checker, mock_clients
    ):
        """Test health check with invalid work pool."""
        mock_prefect, mock_ui = mock_clients

        mock_deployment = {
            "id": "test-id",
            "name": "test-deployment",
            "work_pool_name": "invalid-pool",
            "schedule": None,
        }

        mock_prefect.return_value.get_deployment_by_name.return_value = mock_deployment
        mock_prefect.return_value.validate_work_pool.return_value = False
        mock_ui.return_value.verify_deployment_in_ui.return_value = {"visible": True}

        result = await status_checker.check_deployment_health(
            "test-deployment", "test-flow"
        )

        assert result["healthy"] is False
        assert result["status"] == "unhealthy"
        assert any(
            "Work pool 'invalid-pool' is not valid" in issue
            for issue in result["issues"]
        )

    @pytest.mark.asyncio
    async def test_wait_for_deployment_ready_success(self, status_checker):
        """Test waiting for deployment to become ready - success case."""
        with patch.object(status_checker, "check_deployment_health") as mock_health:
            mock_health.return_value = {"healthy": True}

            result = await status_checker.wait_for_deployment_ready(
                "test-deployment", "test-flow", timeout_seconds=5
            )

        assert result["ready"] is True
        assert result["wait_time_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_wait_for_deployment_ready_timeout(self, status_checker):
        """Test waiting for deployment to become ready - timeout case."""
        with patch.object(status_checker, "check_deployment_health") as mock_health:
            mock_health.return_value = {"healthy": False}

            result = await status_checker.wait_for_deployment_ready(
                "test-deployment", "test-flow", timeout_seconds=1
            )

        assert result["ready"] is False
        assert "not ready after 1 seconds" in result["error"]


class TestUIValidator:
    """Test UI Validator functionality."""

    @pytest.fixture
    def ui_validator(self):
        return UIValidator("http://localhost:4200/api")

    @pytest.fixture
    def mock_clients(self):
        with (
            patch("deployment_system.ui.ui_validator.UIClient") as mock_ui,
            patch(
                "deployment_system.ui.ui_validator.DeploymentStatusChecker"
            ) as mock_status,
        ):
            yield mock_ui, mock_status

    @pytest.mark.asyncio
    async def test_validate_deployment_ui_presence_valid(
        self, ui_validator, mock_clients
    ):
        """Test valid deployment UI presence validation."""
        mock_ui, _ = mock_clients

        mock_deployment = {
            "name": "test-deployment",
            "flow_name": "test-flow",
            "work_pool_name": "test-pool",
            "description": "Test deployment",
            "tags": ["test"],
        }

        mock_ui.return_value.prefect_client.get_deployment_by_name.return_value = (
            mock_deployment
        )
        mock_ui.return_value.check_ui_accessibility.return_value = {"accessible": True}
        mock_ui.return_value.verify_deployment_in_ui.return_value = {"visible": True}
        mock_ui.return_value.get_deployment_ui_url.return_value = (
            "http://localhost:4200/deployments/test"
        )

        result = await ui_validator.validate_deployment_ui_presence(
            "test-deployment", "test-flow"
        )

        assert result["valid"] is True
        assert result["checks"]["api_exists"] is True
        assert result["checks"]["ui_accessible"] is True
        assert result["checks"]["ui_visible"] is True
        assert result["checks"]["metadata_correct"] is True

    @pytest.mark.asyncio
    async def test_validate_deployment_ui_presence_not_found(
        self, ui_validator, mock_clients
    ):
        """Test deployment UI presence validation when deployment not found."""
        mock_ui, _ = mock_clients
        mock_ui.return_value.prefect_client.get_deployment_by_name.return_value = None

        result = await ui_validator.validate_deployment_ui_presence(
            "test-deployment", "test-flow"
        )

        assert result["valid"] is False
        assert result["checks"]["api_exists"] is False
        assert "Deployment not found via API" in result["issues"]

    def test_validate_deployment_metadata_valid(self, ui_validator):
        """Test valid deployment metadata validation."""
        deployment = {
            "name": "test-deployment",
            "flow_name": "test-flow",
            "work_pool_name": "test-pool",
            "description": "Valid description",
            "tags": ["tag1", "tag2"],
        }

        issues = ui_validator._validate_deployment_metadata(deployment)

        assert len(issues) == 0

    def test_validate_deployment_metadata_invalid(self, ui_validator):
        """Test invalid deployment metadata validation."""
        deployment = {
            "name": "",  # Empty name
            "flow_name": "test-flow",
            "work_pool_name": "",  # Empty work pool
            "description": "x" * 600,  # Too long description
            "tags": ["tag"] * 25,  # Too many tags
        }

        issues = ui_validator._validate_deployment_metadata(deployment)

        assert len(issues) > 0
        assert any("name is empty" in issue for issue in issues)
        assert any("Description is too long" in issue for issue in issues)
        assert any("Too many tags" in issue for issue in issues)

    @pytest.mark.asyncio
    async def test_validate_deployment_configuration_for_ui_valid(self, ui_validator):
        """Test valid deployment configuration validation for UI."""
        config = {
            "name": "test-deployment",
            "description": "Test deployment",
            "tags": ["test"],
            "work_pool_name": "test-pool",
        }

        result = await ui_validator.validate_deployment_configuration_for_ui(config)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    @pytest.mark.asyncio
    async def test_validate_deployment_configuration_for_ui_invalid(self, ui_validator):
        """Test invalid deployment configuration validation for UI."""
        config = {
            "name": "",  # Missing name
            "description": "x" * 600,  # Too long description
            "tags": ["tag"] * 15,  # Too many tags
            "work_pool_name": "",  # Missing work pool
        }

        result = await ui_validator.validate_deployment_configuration_for_ui(config)

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert len(result["warnings"]) > 0


class TestTroubleshootingUtilities:
    """Test Troubleshooting Utilities functionality."""

    @pytest.fixture
    def troubleshooter(self):
        return TroubleshootingUtilities("http://localhost:4200/api")

    @pytest.fixture
    def mock_clients(self):
        with (
            patch("deployment_system.ui.troubleshooting.UIClient") as mock_ui,
            patch(
                "deployment_system.ui.troubleshooting.DeploymentStatusChecker"
            ) as mock_status,
        ):
            yield mock_ui, mock_status

    @pytest.mark.asyncio
    async def test_diagnose_api_connectivity_success(
        self, troubleshooter, mock_clients
    ):
        """Test successful API connectivity diagnosis."""
        mock_ui, _ = mock_clients
        mock_ui.return_value.check_api_connectivity.return_value = {
            "connected": True,
            "response_time_ms": 100,
        }

        with patch("socket.create_connection") as mock_socket:
            mock_socket.return_value.close.return_value = None

            diagnosis = await troubleshooter._diagnose_api_connectivity()

        assert diagnosis["configured"] is True
        assert diagnosis["reachable"] is True
        assert diagnosis["responding"] is True
        assert diagnosis["authenticated"] is True

    @pytest.mark.asyncio
    async def test_diagnose_api_connectivity_unreachable(
        self, troubleshooter, mock_clients
    ):
        """Test API connectivity diagnosis when network unreachable."""
        with patch("socket.create_connection") as mock_socket:
            mock_socket.side_effect = ConnectionError("Network unreachable")

            diagnosis = await troubleshooter._diagnose_api_connectivity()

        assert diagnosis["configured"] is True
        assert diagnosis["reachable"] is False
        assert any("Network unreachable" in issue for issue in diagnosis["issues"])

    @pytest.mark.asyncio
    async def test_diagnose_deployment_visibility_issues_not_found(
        self, troubleshooter, mock_clients
    ):
        """Test deployment visibility diagnosis when deployment not found."""
        mock_ui, _ = mock_clients
        mock_ui.return_value.prefect_client.get_deployment_by_name.return_value = None

        diagnosis = await troubleshooter.diagnose_deployment_visibility_issues(
            "test-deployment", "test-flow"
        )

        assert diagnosis["severity"] == "critical"
        assert "Deployment does not exist in Prefect API" in diagnosis["issues_found"]
        assert "Create the deployment first" in diagnosis["recommendations"]

    @pytest.mark.asyncio
    async def test_diagnose_deployment_visibility_issues_invalid_work_pool(
        self, troubleshooter, mock_clients
    ):
        """Test deployment visibility diagnosis with invalid work pool."""
        mock_ui, _ = mock_clients

        mock_deployment = {"id": "test-id", "work_pool_name": "invalid-pool"}

        mock_ui.return_value.prefect_client.get_deployment_by_name.return_value = (
            mock_deployment
        )
        mock_ui.return_value.prefect_client.validate_work_pool.return_value = False
        mock_ui.return_value.check_ui_accessibility.return_value = {"accessible": True}

        diagnosis = await troubleshooter.diagnose_deployment_visibility_issues(
            "test-deployment", "test-flow"
        )

        assert diagnosis["severity"] == "error"
        assert any(
            "Work pool 'invalid-pool' is invalid" in issue
            for issue in diagnosis["issues_found"]
        )

    def test_determine_severity_critical(self, troubleshooter):
        """Test severity determination for critical issues."""
        diagnosis = {
            "api_diagnosis": {"configured": False, "responding": False},
            "ui_diagnosis": {"responding": True},
        }

        severity = troubleshooter._determine_severity(diagnosis)

        assert severity == "critical"

    def test_determine_severity_error(self, troubleshooter):
        """Test severity determination for error level issues."""
        diagnosis = {
            "api_diagnosis": {"configured": True, "responding": True},
            "ui_diagnosis": {"responding": False},
        }

        severity = troubleshooter._determine_severity(diagnosis)

        assert severity == "error"

    def test_determine_severity_warning(self, troubleshooter):
        """Test severity determination for warning level issues."""
        diagnosis = {
            "api_diagnosis": {
                "configured": True,
                "responding": True,
                "issues": ["Minor issue"],
            },
            "ui_diagnosis": {"responding": True},
        }

        severity = troubleshooter._determine_severity(diagnosis)

        assert severity == "warning"

    def test_determine_severity_info(self, troubleshooter):
        """Test severity determination for info level (no issues)."""
        diagnosis = {
            "api_diagnosis": {"configured": True, "responding": True, "issues": []},
            "ui_diagnosis": {"responding": True, "issues": []},
        }

        severity = troubleshooter._determine_severity(diagnosis)

        assert severity == "info"

    @pytest.mark.asyncio
    async def test_test_dns_resolution_success(self, troubleshooter):
        """Test successful DNS resolution."""
        with patch("socket.gethostbyname_ex") as mock_dns:
            mock_dns.return_value = ("localhost", [], ["127.0.0.1"])

            result = await troubleshooter._test_dns_resolution("localhost")

        assert result["resolved"] is True
        assert "127.0.0.1" in result["ip_addresses"]

    @pytest.mark.asyncio
    async def test_test_dns_resolution_failure(self, troubleshooter):
        """Test failed DNS resolution."""
        with patch("socket.gethostbyname_ex") as mock_dns:
            mock_dns.side_effect = Exception("Name resolution failed")

            result = await troubleshooter._test_dns_resolution("invalid.host")

        assert result["resolved"] is False
        assert "Name resolution failed" in result["error"]

    @pytest.mark.asyncio
    async def test_test_port_connectivity_success(self, troubleshooter):
        """Test successful port connectivity."""
        with (
            patch("socket.create_connection") as mock_socket,
            patch("time.time", side_effect=[0, 0.05]),
        ):
            mock_socket.return_value.close.return_value = None

            result = await troubleshooter._test_port_connectivity("localhost", 80)

        assert result["connected"] is True
        assert result["response_time_ms"] == 50

    @pytest.mark.asyncio
    async def test_test_port_connectivity_failure(self, troubleshooter):
        """Test failed port connectivity."""
        with patch("socket.create_connection") as mock_socket:
            mock_socket.side_effect = ConnectionError("Connection refused")

            result = await troubleshooter._test_port_connectivity("localhost", 80)

        assert result["connected"] is False
        assert "Connection refused" in result["error"]


class TestUIIntegrationCLI:
    """Test UI Integration CLI commands."""

    @pytest.fixture
    def mock_ui_cli(self):
        with (
            patch("deployment_system.cli.ui_commands.UIClient"),
            patch("deployment_system.cli.ui_commands.UIValidator"),
            patch("deployment_system.cli.ui_commands.DeploymentStatusChecker"),
            patch("deployment_system.cli.ui_commands.TroubleshootingUtilities"),
        ):
            from deployment_system.cli.ui_commands import UICLI

            yield UICLI()

    def test_check_ui_connectivity_success(self, mock_ui_cli):
        """Test successful UI connectivity check via CLI."""
        mock_ui_cli.ui_client.run_async.return_value = {
            "connected": True,
            "accessible": True,
        }

        result = mock_ui_cli.check_ui_connectivity()

        assert result["success"] is True
        assert result["overall_status"] == "healthy"

    def test_check_ui_connectivity_failure(self, mock_ui_cli):
        """Test failed UI connectivity check via CLI."""
        mock_ui_cli.ui_client.run_async.side_effect = Exception("Connection failed")

        result = mock_ui_cli.check_ui_connectivity()

        assert result["success"] is False
        assert "Connection failed" in result["error"]

    def test_verify_deployment_in_ui_success(self, mock_ui_cli):
        """Test successful deployment verification via CLI."""
        mock_ui_cli.ui_client.run_async.return_value = {
            "visible": True,
            "api_exists": True,
            "ui_accessible": True,
        }

        result = mock_ui_cli.verify_deployment_in_ui("test-deployment", "test-flow")

        assert result["success"] is True
        assert result["visible"] is True

    def test_verify_deployment_in_ui_not_visible(self, mock_ui_cli):
        """Test deployment verification when not visible via CLI."""
        mock_ui_cli.ui_client.run_async.return_value = {
            "visible": False,
            "error": "Deployment not found",
        }

        result = mock_ui_cli.verify_deployment_in_ui("test-deployment", "test-flow")

        assert result["success"] is True
        assert result["visible"] is False

    def test_check_deployment_health_healthy(self, mock_ui_cli):
        """Test healthy deployment health check via CLI."""
        mock_ui_cli.status_checker.run_async.return_value = {
            "healthy": True,
            "status": "healthy",
        }

        result = mock_ui_cli.check_deployment_health("test-deployment", "test-flow")

        assert result["success"] is True
        assert result["healthy"] is True

    def test_troubleshoot_connectivity_success(self, mock_ui_cli):
        """Test successful connectivity troubleshooting via CLI."""
        mock_ui_cli.troubleshooter.run_async.return_value = {
            "severity": "info",
            "recommendations": [],
        }

        result = mock_ui_cli.troubleshoot_connectivity()

        assert result["success"] is True
        assert result["severity"] == "info"

    def test_format_connectivity_report_healthy(self, mock_ui_cli):
        """Test formatting healthy connectivity report."""
        report = {
            "success": True,
            "api_connectivity": {
                "connected": True,
                "api_url": "http://localhost:4200/api",
            },
            "ui_accessibility": {"accessible": True, "ui_url": "http://localhost:4200"},
            "overall_status": "healthy",
        }

        formatted = mock_ui_cli.format_connectivity_report(report)

        assert "✅" in formatted
        assert "UI Connectivity Check" in formatted
        assert "HEALTHY" in formatted

    def test_format_connectivity_report_unhealthy(self, mock_ui_cli):
        """Test formatting unhealthy connectivity report."""
        report = {
            "success": True,
            "api_connectivity": {"connected": False, "error": "Connection refused"},
            "ui_accessibility": {"accessible": False, "error": "Timeout"},
            "overall_status": "unhealthy",
        }

        formatted = mock_ui_cli.format_connectivity_report(report)

        assert "❌" in formatted
        assert "Connection refused" in formatted
        assert "Timeout" in formatted

    def test_format_deployment_health_healthy(self, mock_ui_cli):
        """Test formatting healthy deployment health report."""
        health_result = {
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

        formatted = mock_ui_cli.format_deployment_health(health_result)

        assert "✅" in formatted
        assert "test-flow/test-deployment" in formatted
        assert "HEALTHY" in formatted

    def test_format_deployment_health_unhealthy(self, mock_ui_cli):
        """Test formatting unhealthy deployment health report."""
        health_result = {
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
                "issues": ["Work pool invalid", "Not visible in UI"],
                "recommendations": ["Fix work pool", "Check UI connectivity"],
            },
        }

        formatted = mock_ui_cli.format_deployment_health(health_result)

        assert "❌" in formatted
        assert "Work pool invalid" in formatted
        assert "Fix work pool" in formatted
