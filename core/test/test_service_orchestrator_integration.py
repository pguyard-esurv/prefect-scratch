"""
Integration tests for ServiceOrchestrator service dependency management and failure scenarios.

These tests validate the ServiceOrchestrator's ability to handle real-world scenarios
including service failures, network issues, timeout handling, and recovery mechanisms.
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import Mock, patch

import pytest

from core.container_config import ContainerConfigManager, ServiceDependency
from core.service_orchestrator import ServiceOrchestrator


class MockHealthServer:
    """Mock HTTP server for testing service health endpoints."""

    def __init__(self, port: int = 8080, initial_status: int = 200):
        self.port = port
        self.status_code = initial_status
        self.response_data = {"status": "ready"}
        self.request_count = 0
        self.server = None
        self.thread = None

    def start(self):
        """Start the mock server in a separate thread."""

        class Handler(BaseHTTPRequestHandler):
            def do_GET(handler_self):
                self.request_count += 1
                handler_self.send_response(self.status_code)
                handler_self.send_header("Content-type", "application/json")
                handler_self.end_headers()

                if self.status_code == 200:
                    import json

                    response = json.dumps(self.response_data).encode()
                    handler_self.wfile.write(response)

            def log_message(handler_self, format, *args):
                # Suppress server logs during tests
                pass

        self.server = HTTPServer(("localhost", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()

        # Wait for server to start
        time.sleep(0.1)

    def stop(self):
        """Stop the mock server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)

    def set_status(self, status_code: int, response_data: dict = None):
        """Change the server's response status and data."""
        self.status_code = status_code
        if response_data:
            self.response_data = response_data


class TestServiceOrchestratorFailureScenarios:
    """Test service orchestrator failure scenarios and recovery."""

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock configuration manager for testing."""
        config_manager = Mock(spec=ContainerConfigManager)
        config_manager.flow_name = "test_flow"
        config_manager.environment = "test"
        config_manager.get_config.return_value = "http://localhost:4200"
        config_manager._get_container_config.return_value = (
            "http://localhost:4200/health"
        )
        return config_manager

    @pytest.fixture
    def orchestrator_with_mock_config(self, mock_config_manager):
        """Create orchestrator with mock configuration."""
        return ServiceOrchestrator(config_manager=mock_config_manager)

    def test_service_dependency_timeout_scenario(
        self, orchestrator_with_mock_config, mock_config_manager
    ):
        """Test service dependency timeout handling."""
        # Configure mock to return service that will timeout
        mock_config_manager.load_container_config.return_value = {
            "databases": {},
            "services": [
                ServiceDependency(
                    service_name="slow_service",
                    health_endpoint="http://localhost:9999/health",  # Non-existent port
                    timeout=1,  # Short timeout
                    retry_attempts=2,
                    required=True,
                )
            ],
        }

        # Test waiting for dependencies with timeout
        start_time = time.time()
        result = orchestrator_with_mock_config.wait_for_all_dependencies(timeout=5)
        elapsed = time.time() - start_time

        assert result is False
        assert elapsed < 10  # Should fail quickly due to timeout

    @patch("requests.get")
    def test_service_intermittent_failure_recovery(
        self, mock_get, orchestrator_with_mock_config, mock_config_manager
    ):
        """Test recovery from intermittent service failures."""
        # Configure mock to use the test server
        mock_config_manager.load_container_config.return_value = {
            "databases": {},
            "services": [
                ServiceDependency(
                    service_name="intermittent_service",
                    health_endpoint="http://localhost:8081/health",
                    timeout=5,
                    retry_attempts=3,
                    required=True,
                )
            ],
        }

        # Mock responses for different calls
        call_count = 0

        def mock_get_side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1

            mock_response = Mock()

            if "localhost:4200" in url:
                # Prefect health check - always succeed
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "ready"}
            elif "localhost:8081" in url:
                # Intermittent service - fail first, then succeed
                if call_count <= 2:
                    mock_response.status_code = 500
                else:
                    mock_response.status_code = 200
                    mock_response.json.return_value = {"status": "ready"}
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "ready"}

            return mock_response

        mock_get.side_effect = mock_get_side_effect

        # First health check should fail
        health_status = orchestrator_with_mock_config.validate_service_health()
        assert health_status.overall_status == "unhealthy"
        assert health_status.services["intermittent_service"].status == "unhealthy"

        # Clear health cache to force fresh check
        orchestrator_with_mock_config._health_cache.clear()

        # Second health check should succeed (service recovered)
        health_status = orchestrator_with_mock_config.validate_service_health()
        assert health_status.overall_status == "healthy"
        assert health_status.services["intermittent_service"].status == "healthy"

    @patch("requests.get")
    def test_partial_service_failure_degraded_status(
        self, mock_get, orchestrator_with_mock_config, mock_config_manager
    ):
        """Test handling of partial service failures resulting in degraded status."""
        # Configure mock with mixed service health
        mock_config_manager.load_container_config.return_value = {
            "databases": {},
            "services": [
                ServiceDependency(
                    service_name="healthy_service",
                    health_endpoint="http://localhost:8082/health",
                    timeout=5,
                    retry_attempts=1,
                    required=False,  # Optional service
                ),
                ServiceDependency(
                    service_name="unhealthy_service",
                    health_endpoint="http://localhost:8083/health",
                    timeout=5,
                    retry_attempts=1,
                    required=False,  # Optional service
                ),
            ],
        }

        # Mock responses for different services
        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()

            if "localhost:4200" in url:
                # Prefect health check - succeed
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "ready"}
            elif "localhost:8082" in url:
                # Healthy service
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "ready"}
            elif "localhost:8083" in url:
                # Unhealthy service
                mock_response.status_code = 500
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "ready"}

            return mock_response

        mock_get.side_effect = mock_get_side_effect

        # Health check should show mixed results
        health_status = orchestrator_with_mock_config.validate_service_health()

        # Overall status should be healthy because unhealthy service is optional
        # and Prefect is healthy
        assert health_status.overall_status == "healthy"
        assert health_status.services["healthy_service"].status == "healthy"
        assert health_status.services["unhealthy_service"].status == "unhealthy"

    @patch("requests.get")
    def test_required_vs_optional_service_failure_impact(
        self, mock_get, orchestrator_with_mock_config, mock_config_manager
    ):
        """Test impact of required vs optional service failures on overall status."""

        # Mock responses for different services
        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()

            if "localhost:4200" in url:
                # Prefect health check - succeed
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "ready"}
            elif "localhost:8084" in url:
                # Healthy service
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "ready"}
            elif "localhost:8085" in url:
                # Unhealthy service
                mock_response.status_code = 500
            else:
                mock_response.status_code = 200
                mock_response.json.return_value = {"status": "ready"}

            return mock_response

        mock_get.side_effect = mock_get_side_effect

        # Test with required service failure
        mock_config_manager.load_container_config.return_value = {
            "databases": {},
            "services": [
                ServiceDependency(
                    service_name="healthy_service",
                    health_endpoint="http://localhost:8084/health",
                    timeout=5,
                    retry_attempts=1,
                    required=False,
                ),
                ServiceDependency(
                    service_name="required_unhealthy_service",
                    health_endpoint="http://localhost:8085/health",
                    timeout=5,
                    retry_attempts=1,
                    required=True,  # Required service
                ),
            ],
        }

        health_status = orchestrator_with_mock_config.validate_service_health()

        # Overall status should be unhealthy due to required service failure
        assert health_status.overall_status == "unhealthy"
        assert health_status.services["healthy_service"].status == "healthy"
        assert (
            health_status.services["required_unhealthy_service"].status == "unhealthy"
        )

        # Now test with only optional service failure
        mock_config_manager.load_container_config.return_value = {
            "databases": {},
            "services": [
                ServiceDependency(
                    service_name="healthy_service",
                    health_endpoint="http://localhost:8084/health",
                    timeout=5,
                    retry_attempts=1,
                    required=True,
                ),
                ServiceDependency(
                    service_name="optional_unhealthy_service",
                    health_endpoint="http://localhost:8085/health",
                    timeout=5,
                    retry_attempts=1,
                    required=False,  # Optional service
                ),
            ],
        }

        health_status = orchestrator_with_mock_config.validate_service_health()

        # Overall status should be healthy because only optional service failed
        # and Prefect is healthy
        assert health_status.overall_status == "healthy"

    @patch("core.service_orchestrator.DatabaseManager")
    def test_database_connection_retry_with_exponential_backoff(
        self, mock_db_manager_class, orchestrator_with_mock_config, mock_config_manager
    ):
        """Test database connection retry with exponential backoff."""
        # Configure mock database
        mock_config_manager.load_container_config.return_value = {
            "databases": {
                "retry_db": {
                    "name": "retry_db",
                    "connection_string": "postgresql://test:test@localhost:5432/test",
                    "database_type": "postgresql",
                }
            },
            "services": [],
        }

        # Setup mock database manager that fails initially then succeeds
        mock_db_manager = Mock()
        call_count = 0

        def health_check_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return {
                    "status": "unhealthy",
                    "connection": False,
                    "error": "Connection refused",
                }
            else:
                return {"status": "healthy", "connection": True, "query_test": True}

        mock_db_manager.health_check.side_effect = health_check_side_effect
        mock_db_manager_class.return_value = mock_db_manager

        # Test database wait with retry
        start_time = time.time()
        result = orchestrator_with_mock_config.wait_for_database("retry_db", timeout=30)
        elapsed = time.time() - start_time

        assert result is True
        assert call_count >= 3  # Should have retried at least twice
        assert elapsed > 2  # Should have waited due to exponential backoff

    def test_health_check_caching_behavior(self, mock_config_manager):
        """Test health check result caching behavior."""
        # Create orchestrator with short cache TTL for faster testing
        orchestrator = ServiceOrchestrator(
            config_manager=mock_config_manager, cache_ttl=1
        )

        # Start a mock server
        server = MockHealthServer(port=8086, initial_status=200)
        server.start()

        try:
            # Configure mock with a service
            mock_config_manager.load_container_config.return_value = {
                "databases": {},
                "services": [
                    ServiceDependency(
                        service_name="cached_service",
                        health_endpoint="http://localhost:8086/health",
                        timeout=5,
                        retry_attempts=1,
                        required=True,
                    )
                ],
            }

            # First health check
            health_status1 = orchestrator.validate_service_health()
            initial_request_count = server.request_count

            # Second health check immediately after (should use cache)
            health_status2 = orchestrator.validate_service_health()
            cached_request_count = server.request_count

            # Verify caching worked (no additional requests)
            assert cached_request_count == initial_request_count
            assert health_status1.services["cached_service"].status == "healthy"
            assert health_status2.services["cached_service"].status == "healthy"

            # Wait for cache to expire and check again (only 1.1 seconds now)
            time.sleep(1.1)  # Cache TTL is 1 second
            orchestrator.validate_service_health()
            expired_request_count = server.request_count

            # Verify cache expired (additional request made)
            assert expired_request_count > cached_request_count

        finally:
            server.stop()

    def test_service_failure_handling_and_cache_clearing(
        self, orchestrator_with_mock_config
    ):
        """Test service failure handling and cache clearing."""
        # Add a cached health status
        from datetime import datetime, timezone

        from core.service_orchestrator import HealthStatus

        cached_health = HealthStatus(
            status="healthy",
            message="Service is healthy",
            details={"service_name": "test_service"},
            timestamp=datetime.now(timezone.utc),
            check_duration=0.1,
        )
        orchestrator_with_mock_config._health_cache["service_test_service"] = (
            cached_health
        )

        # Verify cache contains the entry
        assert "service_test_service" in orchestrator_with_mock_config._health_cache

        # Handle service failure
        error = ConnectionError("Service connection failed")
        orchestrator_with_mock_config.handle_service_failure("test_service", error)

        # Verify cache was cleared
        assert "service_test_service" not in orchestrator_with_mock_config._health_cache

    @patch("requests.get")
    def test_prefect_server_health_check_with_different_response_formats(
        self, mock_get, orchestrator_with_mock_config, mock_config_manager
    ):
        """Test Prefect server health check with different response formats."""
        # Test with JSON response containing status
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ready", "version": "2.0.0"}
        mock_get.return_value = mock_response

        health_status = orchestrator_with_mock_config._check_prefect_health()
        assert health_status.status == "healthy"
        assert "ready" in health_status.message
        assert health_status.details["health_data"]["status"] == "ready"

        # Test with JSON response without status field
        mock_response.json.return_value = {"version": "2.0.0", "uptime": 3600}
        health_status = orchestrator_with_mock_config._check_prefect_health()
        assert health_status.status == "healthy"
        assert "responding" in health_status.message

        # Test with non-JSON response
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        health_status = orchestrator_with_mock_config._check_prefect_health()
        assert health_status.status == "healthy"
        assert "responding" in health_status.message
        assert "health_data" not in health_status.details

        # Test with error status code
        mock_response.status_code = 503
        mock_response.json.side_effect = None
        mock_response.json.return_value = {"error": "Service unavailable"}
        health_status = orchestrator_with_mock_config._check_prefect_health()
        assert health_status.status == "unhealthy"
        assert "503" in health_status.message

    @patch("requests.get")
    def test_concurrent_health_checks(
        self, mock_get, orchestrator_with_mock_config, mock_config_manager
    ):
        """Test concurrent health checks don't interfere with each other."""
        # Configure multiple services
        services = []
        for i, port in enumerate([8087, 8088, 8089]):
            services.append(
                ServiceDependency(
                    service_name=f"concurrent_service_{i}",
                    health_endpoint=f"http://localhost:{port}/health",
                    timeout=5,
                    retry_attempts=1,
                    required=True,
                )
            )

        mock_config_manager.load_container_config.return_value = {
            "databases": {},
            "services": services,
        }

        # Mock all services to be healthy
        def mock_get_side_effect(url, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ready"}
            return mock_response

        mock_get.side_effect = mock_get_side_effect

        # Perform concurrent health checks
        import concurrent.futures

        def check_health():
            return orchestrator_with_mock_config.validate_service_health()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(check_health) for _ in range(3)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        # Verify all checks succeeded
        for result in results:
            assert result.overall_status == "healthy"
            assert len(result.services) == 4  # 3 configured + 1 prefect
            for i in range(3):
                service_name = f"concurrent_service_{i}"
                assert service_name in result.services
                assert result.services[service_name].status == "healthy"

    def test_service_orchestrator_startup_sequence(
        self, orchestrator_with_mock_config, mock_config_manager
    ):
        """Test complete service orchestrator startup sequence."""
        # Start mock servers for dependencies
        db_server = MockHealthServer(port=8090, initial_status=200)
        service_server = MockHealthServer(port=8091, initial_status=200)
        prefect_server = MockHealthServer(port=8092, initial_status=200)

        db_server.start()
        service_server.start()
        prefect_server.start()

        try:
            # Configure complete environment
            mock_config_manager.load_container_config.return_value = {
                "databases": {
                    "startup_db": {
                        "name": "startup_db",
                        "connection_string": "postgresql://test:test@localhost:5432/test",
                        "database_type": "postgresql",
                    }
                },
                "services": [
                    ServiceDependency(
                        service_name="startup_service",
                        health_endpoint="http://localhost:8091/health",
                        timeout=10,
                        retry_attempts=3,
                        required=True,
                    )
                ],
            }

            # Override Prefect URL to use our mock server
            mock_config_manager.get_config.return_value = "http://localhost:8092"
            mock_config_manager._get_container_config.return_value = (
                "http://localhost:8092/health"
            )

            # Mock database manager for startup sequence
            with patch(
                "core.service_orchestrator.DatabaseManager"
            ) as mock_db_manager_class:
                mock_db_manager = Mock()
                mock_db_manager.health_check.return_value = {
                    "status": "healthy",
                    "connection": True,
                    "query_test": True,
                    "response_time_ms": 50.0,
                }
                mock_db_manager_class.return_value = mock_db_manager

                # Test complete startup sequence
                start_time = time.time()

                # 1. Wait for all dependencies
                deps_ready = orchestrator_with_mock_config.wait_for_all_dependencies(
                    timeout=30
                )
                assert deps_ready is True

                # 2. Validate service health
                health_status = orchestrator_with_mock_config.validate_service_health()
                assert health_status.overall_status == "healthy"

                # 3. Verify all components are healthy
                assert "startup_db" in health_status.databases
                assert health_status.databases["startup_db"].status == "healthy"
                assert "startup_service" in health_status.services
                assert health_status.services["startup_service"].status == "healthy"
                assert "prefect" in health_status.services
                assert health_status.services["prefect"].status == "healthy"

                elapsed = time.time() - start_time
                assert (
                    elapsed < 10
                )  # Should complete quickly when all services are healthy

        finally:
            db_server.stop()
            service_server.stop()
            prefect_server.stop()
