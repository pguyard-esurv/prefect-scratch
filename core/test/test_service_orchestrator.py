"""
Unit tests for ServiceOrchestrator class.

Tests service orchestration functionality including database connection waiting,
Prefect server health checks, service dependency management, and health monitoring.
"""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from core.container_config import ContainerConfigManager, ServiceDependency
from core.service_orchestrator import HealthStatus, ServiceOrchestrator


class TestServiceOrchestrator:
    """Test cases for ServiceOrchestrator class."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock container configuration manager."""
        config_manager = Mock(spec=ContainerConfigManager)
        config_manager.flow_name = "test_flow"
        config_manager.environment = "test"
        config_manager.load_container_config.return_value = {
            "databases": {
                "test_db": {
                    "name": "test_db",
                    "connection_string": "postgresql://test:test@localhost:5432/test",
                    "database_type": "postgresql",
                }
            },
            "services": [
                ServiceDependency(
                    service_name="test_service",
                    health_endpoint="http://localhost:8080/health",
                    timeout=30,
                    retry_attempts=3,
                    required=True,
                )
            ],
        }
        config_manager.get_config.return_value = "http://localhost:4200"
        config_manager._get_container_config.return_value = (
            "http://localhost:4200/health"
        )
        return config_manager

    @pytest.fixture
    def orchestrator(self, mock_config_manager):
        """Create a ServiceOrchestrator instance with mocked dependencies."""
        return ServiceOrchestrator(config_manager=mock_config_manager)

    def test_init_with_config_manager(self, mock_config_manager):
        """Test ServiceOrchestrator initialization with config manager."""
        orchestrator = ServiceOrchestrator(config_manager=mock_config_manager)

        assert orchestrator.config_manager == mock_config_manager
        assert orchestrator.flow_name == "test_flow"
        assert orchestrator.environment == "test"
        assert orchestrator._database_managers == {}

    def test_init_without_config_manager(self):
        """Test ServiceOrchestrator initialization without config manager."""
        with patch("core.service_orchestrator.ContainerConfigManager") as mock_cm_class:
            mock_cm = Mock()
            mock_cm.flow_name = "default_flow"
            mock_cm.environment = "development"
            mock_cm_class.return_value = mock_cm

            orchestrator = ServiceOrchestrator(
                flow_name="test_flow", environment="test"
            )

            mock_cm_class.assert_called_once_with("test_flow", "test")
            assert orchestrator.config_manager == mock_cm

    @patch("core.service_orchestrator.DatabaseManager")
    def test_wait_for_database_success(
        self, mock_db_manager_class, orchestrator, mock_config_manager
    ):
        """Test successful database wait."""
        # Setup mock database manager
        mock_db_manager = Mock()
        mock_db_manager.health_check.return_value = {
            "status": "healthy",
            "connection": True,
            "query_test": True,
        }
        mock_db_manager_class.return_value = mock_db_manager

        # Test database wait
        result = orchestrator.wait_for_database("test_db", timeout=10)

        assert result is True
        mock_db_manager_class.assert_called_once_with("test_db")
        mock_db_manager.health_check.assert_called()

    @patch("core.service_orchestrator.DatabaseManager")
    def test_wait_for_database_timeout(
        self, mock_db_manager_class, orchestrator, mock_config_manager
    ):
        """Test database wait timeout."""
        # Setup mock database manager that always returns unhealthy
        mock_db_manager = Mock()
        mock_db_manager.health_check.return_value = {
            "status": "unhealthy",
            "connection": False,
            "error": "Connection refused",
        }
        mock_db_manager_class.return_value = mock_db_manager

        # Test database wait with short timeout
        with patch("time.sleep"):  # Speed up the test
            result = orchestrator.wait_for_database("test_db", timeout=1)

        assert result is False

    @patch("core.service_orchestrator.DatabaseManager")
    def test_wait_for_database_invalid_config(
        self, mock_db_manager_class, orchestrator, mock_config_manager
    ):
        """Test database wait with invalid configuration."""
        # Configure mock to return empty databases
        mock_config_manager.load_container_config.return_value = {"databases": {}}

        # Test database wait with non-existent database
        with pytest.raises(
            RuntimeError,
            match="Database wait failed: Database 'nonexistent_db' not found in configuration",
        ):
            orchestrator.wait_for_database("nonexistent_db", timeout=10)

    @patch("requests.get")
    def test_wait_for_prefect_server_success(
        self, mock_get, orchestrator, mock_config_manager
    ):
        """Test successful Prefect server wait."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ready"}
        mock_get.return_value = mock_response

        # Test Prefect server wait
        result = orchestrator.wait_for_prefect_server(timeout=10)

        assert result is True
        mock_get.assert_called_with("http://localhost:4200/health", timeout=10)

    @patch("requests.get")
    def test_wait_for_prefect_server_timeout(
        self, mock_get, orchestrator, mock_config_manager
    ):
        """Test Prefect server wait timeout."""
        # Setup mock to raise connection error
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        # Test Prefect server wait with short timeout
        with patch("time.sleep"):  # Speed up the test
            result = orchestrator.wait_for_prefect_server(timeout=1)

        assert result is False

    @patch("requests.get")
    def test_wait_for_prefect_server_no_config(
        self, mock_get, orchestrator, mock_config_manager
    ):
        """Test Prefect server wait with missing configuration."""
        # Configure mock to return None for Prefect URL
        mock_config_manager.get_config.return_value = None
        mock_config_manager._get_container_config.return_value = None

        # Test Prefect server wait
        with pytest.raises(
            RuntimeError,
            match="Prefect server wait failed: Prefect server URL not configured",
        ):
            orchestrator.wait_for_prefect_server(timeout=10)

    @patch("core.service_orchestrator.DatabaseManager")
    @patch("requests.get")
    def test_validate_service_health_all_healthy(
        self, mock_get, mock_db_manager_class, orchestrator, mock_config_manager
    ):
        """Test service health validation when all services are healthy."""
        # Setup mock database manager
        mock_db_manager = Mock()
        mock_db_manager.health_check.return_value = {
            "status": "healthy",
            "connection": True,
            "query_test": True,
            "response_time_ms": 50.0,
        }
        mock_db_manager_class.return_value = mock_db_manager

        # Setup mock HTTP response for services
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Test service health validation
        result = orchestrator.validate_service_health()

        assert result.overall_status == "healthy"
        assert "test_db" in result.databases
        assert "test_service" in result.services
        assert "prefect" in result.services
        assert result.databases["test_db"].status == "healthy"
        assert result.services["test_service"].status == "healthy"

    @patch("core.service_orchestrator.DatabaseManager")
    @patch("requests.get")
    def test_validate_service_health_degraded(
        self, mock_get, mock_db_manager_class, orchestrator, mock_config_manager
    ):
        """Test service health validation with degraded services."""
        # Setup mock database manager with degraded status
        mock_db_manager = Mock()
        mock_db_manager.health_check.return_value = {
            "status": "degraded",
            "connection": True,
            "query_test": False,
            "error": "Slow response time",
        }
        mock_db_manager_class.return_value = mock_db_manager

        # Setup mock HTTP response for services
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Test service health validation
        result = orchestrator.validate_service_health()

        assert result.overall_status == "degraded"
        assert result.databases["test_db"].status == "degraded"

    @patch("core.service_orchestrator.DatabaseManager")
    @patch("requests.get")
    def test_validate_service_health_unhealthy(
        self, mock_get, mock_db_manager_class, orchestrator, mock_config_manager
    ):
        """Test service health validation with unhealthy services."""
        # Setup mock database manager with unhealthy status
        mock_db_manager = Mock()
        mock_db_manager.health_check.return_value = {
            "status": "unhealthy",
            "connection": False,
            "error": "Connection refused",
        }
        mock_db_manager_class.return_value = mock_db_manager

        # Setup mock HTTP response for services (connection error)
        mock_get.side_effect = requests.ConnectionError("Service unavailable")

        # Test service health validation
        result = orchestrator.validate_service_health()

        assert result.overall_status == "unhealthy"
        assert result.databases["test_db"].status == "unhealthy"
        assert result.services["test_service"].status == "unhealthy"

    @patch("requests.get")
    def test_check_service_health_success(self, mock_get, orchestrator):
        """Test individual service health check success."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        service = ServiceDependency(
            service_name="test_service",
            health_endpoint="http://localhost:8080/health",
            timeout=30,
            retry_attempts=3,
            required=True,
        )

        # Test service health check
        result = orchestrator._check_service_health(service)

        assert result.status == "healthy"
        assert result.details["service_name"] == "test_service"
        assert result.details["status_code"] == 200
        assert result.details["required"] is True

    @patch("requests.get")
    def test_check_service_health_client_error(self, mock_get, orchestrator):
        """Test service health check with client error."""
        # Setup mock response with 404 status
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        service = ServiceDependency(
            service_name="test_service",
            health_endpoint="http://localhost:8080/health",
            timeout=30,
            retry_attempts=3,
            required=True,
        )

        # Test service health check
        result = orchestrator._check_service_health(service)

        assert result.status == "degraded"
        assert result.details["status_code"] == 404

    @patch("requests.get")
    def test_check_service_health_server_error(self, mock_get, orchestrator):
        """Test service health check with server error."""
        # Setup mock response with 500 status
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        service = ServiceDependency(
            service_name="test_service",
            health_endpoint="http://localhost:8080/health",
            timeout=30,
            retry_attempts=3,
            required=True,
        )

        # Test service health check
        result = orchestrator._check_service_health(service)

        assert result.status == "unhealthy"
        assert result.details["status_code"] == 500

    @patch("requests.get")
    def test_check_service_health_connection_error(self, mock_get, orchestrator):
        """Test service health check with connection error."""
        # Setup mock to raise connection error
        mock_get.side_effect = requests.ConnectionError("Connection refused")

        service = ServiceDependency(
            service_name="test_service",
            health_endpoint="http://localhost:8080/health",
            timeout=30,
            retry_attempts=3,
            required=True,
        )

        # Test service health check
        result = orchestrator._check_service_health(service)

        assert result.status == "unhealthy"
        assert "Connection refused" in result.message
        assert "error" in result.details

    @patch("requests.get")
    def test_check_prefect_health_success(
        self, mock_get, orchestrator, mock_config_manager
    ):
        """Test Prefect health check success."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ready"}
        mock_get.return_value = mock_response

        # Test Prefect health check
        result = orchestrator._check_prefect_health()

        assert result.status == "healthy"
        assert "ready" in result.message
        assert result.details["status_code"] == 200
        assert result.details["health_data"]["status"] == "ready"

    @patch("requests.get")
    def test_check_prefect_health_non_json_response(
        self, mock_get, orchestrator, mock_config_manager
    ):
        """Test Prefect health check with non-JSON response."""
        # Setup mock response that raises JSON decode error
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_get.return_value = mock_response

        # Test Prefect health check
        result = orchestrator._check_prefect_health()

        assert result.status == "healthy"
        assert "responding" in result.message
        assert result.details["status_code"] == 200
        assert "health_data" not in result.details

    def test_handle_service_failure(self, orchestrator):
        """Test service failure handling."""
        # Add a cached health status
        orchestrator._health_cache["service_test"] = HealthStatus(
            status="healthy",
            message="Test",
            details={},
            timestamp=datetime.now(timezone.utc),
            check_duration=0.1,
        )

        # Test service failure handling
        error = ConnectionError("Service unavailable")
        orchestrator.handle_service_failure("test", error)

        # Verify cache was cleared
        assert "service_test" not in orchestrator._health_cache

    @patch("core.service_orchestrator.DatabaseManager")
    @patch("requests.get")
    def test_wait_for_all_dependencies_success(
        self, mock_get, mock_db_manager_class, orchestrator, mock_config_manager
    ):
        """Test waiting for all dependencies successfully."""
        # Setup mock database manager
        mock_db_manager = Mock()
        mock_db_manager.health_check.return_value = {
            "status": "healthy",
            "connection": True,
            "query_test": True,
        }
        mock_db_manager_class.return_value = mock_db_manager

        # Setup mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Test waiting for all dependencies
        result = orchestrator.wait_for_all_dependencies(timeout=30)

        assert result is True

    @patch("core.service_orchestrator.DatabaseManager")
    def test_wait_for_all_dependencies_database_failure(
        self, mock_db_manager_class, orchestrator, mock_config_manager
    ):
        """Test waiting for all dependencies with database failure."""
        # Setup mock database manager that fails
        mock_db_manager = Mock()
        mock_db_manager.health_check.return_value = {
            "status": "unhealthy",
            "connection": False,
            "error": "Connection refused",
        }
        mock_db_manager_class.return_value = mock_db_manager

        # Test waiting for all dependencies with short timeout
        with patch("time.sleep"):  # Speed up the test
            result = orchestrator.wait_for_all_dependencies(timeout=1)

        assert result is False

    def test_determine_overall_status_all_healthy(self, orchestrator):
        """Test overall status determination with all healthy services."""
        services_health = {
            "service1": HealthStatus(
                "healthy", "OK", {"required": True}, datetime.now(timezone.utc), 0.1
            )
        }
        databases_health = {
            "db1": HealthStatus(
                "healthy", "OK", {"required": True}, datetime.now(timezone.utc), 0.1
            )
        }

        status = orchestrator._determine_overall_status(
            services_health, databases_health
        )
        assert status == "healthy"

    def test_determine_overall_status_degraded(self, orchestrator):
        """Test overall status determination with degraded services."""
        services_health = {
            "service1": HealthStatus(
                "degraded", "Slow", {"required": True}, datetime.now(timezone.utc), 0.1
            )
        }
        databases_health = {
            "db1": HealthStatus(
                "healthy", "OK", {"required": True}, datetime.now(timezone.utc), 0.1
            )
        }

        status = orchestrator._determine_overall_status(
            services_health, databases_health
        )
        assert status == "degraded"

    def test_determine_overall_status_unhealthy_required(self, orchestrator):
        """Test overall status determination with unhealthy required services."""
        services_health = {
            "service1": HealthStatus(
                "unhealthy", "Down", {"required": True}, datetime.now(timezone.utc), 0.1
            )
        }
        databases_health = {
            "db1": HealthStatus(
                "healthy", "OK", {"required": True}, datetime.now(timezone.utc), 0.1
            )
        }

        status = orchestrator._determine_overall_status(
            services_health, databases_health
        )
        assert status == "unhealthy"

    def test_determine_overall_status_unhealthy_optional(self, orchestrator):
        """Test overall status determination with unhealthy optional services."""
        services_health = {
            "service1": HealthStatus(
                "unhealthy",
                "Down",
                {"required": False},
                datetime.now(timezone.utc),
                0.1,
            )
        }
        databases_health = {
            "db1": HealthStatus(
                "healthy", "OK", {"required": True}, datetime.now(timezone.utc), 0.1
            )
        }

        status = orchestrator._determine_overall_status(
            services_health, databases_health
        )
        assert (
            status == "healthy"
        )  # Optional service failure doesn't affect overall status


class TestServiceOrchestratorIntegration:
    """Integration tests for ServiceOrchestrator with real configuration."""

    @pytest.fixture
    def real_config_manager(self):
        """Create a real ContainerConfigManager for integration tests."""
        return ContainerConfigManager(flow_name="test_flow", environment="test")

    def test_integration_with_real_config(self, real_config_manager):
        """Test ServiceOrchestrator with real configuration manager."""
        orchestrator = ServiceOrchestrator(config_manager=real_config_manager)

        assert orchestrator.config_manager == real_config_manager
        assert orchestrator.flow_name == "test_flow"
        assert orchestrator.environment == "test"

    @patch.dict(
        "os.environ",
        {
            "CONTAINER_DATABASE_REQUIRED": "test_db",
            "CONTAINER_DATABASE_TEST_DB_CONNECTION_STRING": "postgresql://test:test@localhost:5432/test",
            "CONTAINER_DATABASE_TEST_DB_TYPE": "postgresql",
            "CONTAINER_SERVICE_REQUIRED": "test_service",
            "CONTAINER_SERVICE_TEST_SERVICE_HEALTH_ENDPOINT": "http://localhost:8080/health",
        },
    )
    def test_integration_load_config_from_environment(self, real_config_manager):
        """Test loading configuration from environment variables."""
        orchestrator = ServiceOrchestrator(config_manager=real_config_manager)

        # Load configuration
        config = orchestrator.config_manager.load_container_config()

        # Verify database configuration
        assert "test_db" in config["databases"]
        db_config = config["databases"]["test_db"]
        assert (
            db_config.connection_string == "postgresql://test:test@localhost:5432/test"
        )
        assert db_config.database_type == "postgresql"

        # Verify service configuration
        services = config["services"]
        assert len(services) > 0
        service = next((s for s in services if s.service_name == "test_service"), None)
        assert service is not None
        assert service.health_endpoint == "http://localhost:8080/health"
