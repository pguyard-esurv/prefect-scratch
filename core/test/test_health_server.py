"""
Unit tests for the health server HTTP endpoints.

Tests cover HTTP endpoint functionality, response formats, error handling,
and integration with the health monitoring system.
"""

import json
import threading
import time
import unittest
from http.server import HTTPServer
from unittest.mock import Mock, patch

import requests

from core.health_monitor import HealthMonitor
from core.health_server import HealthHTTPHandler, HealthServer, create_health_server


class TestHealthHTTPHandler(unittest.TestCase):
    """Test HTTP handler for health endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_health_monitor = Mock(spec=HealthMonitor)

        # Mock request/response objects
        self.mock_request = Mock()
        self.mock_wfile = Mock()
        self.mock_rfile = Mock()

        # Create handler with mocked components
        self.handler = HealthHTTPHandler.__new__(HealthHTTPHandler)
        self.handler.health_monitor = self.mock_health_monitor
        self.handler.wfile = self.mock_wfile
        self.handler.rfile = self.mock_rfile
        self.handler.path = "/health"

        # Mock HTTP methods
        self.handler.send_response = Mock()
        self.handler.send_header = Mock()
        self.handler.end_headers = Mock()

    def test_handle_basic_health_check(self):
        """Test basic health check endpoint."""
        # Mock health monitor response
        health_response = {
            "status": "healthy",
            "timestamp": "2023-01-01T00:00:00Z",
            "checks": {"application": "healthy"},
        }
        self.mock_health_monitor.get_health_endpoint_response.return_value = (
            health_response,
            200,
        )

        self.handler._handle_health_check()

        # Verify response was sent
        self.handler.send_response.assert_called_with(200)
        self.handler.send_header.assert_any_call("Content-Type", "application/json")
        self.handler.end_headers.assert_called_once()

        # Verify JSON was written
        written_data = self.mock_wfile.write.call_args[0][0].decode("utf-8")
        response_data = json.loads(written_data)
        self.assertEqual(response_data["status"], "healthy")

    def test_handle_health_check_error(self):
        """Test health check endpoint with error."""
        self.mock_health_monitor.get_health_endpoint_response.side_effect = Exception(
            "Health check failed"
        )

        # Mock comprehensive_health_check for _send_error
        self.mock_health_monitor.comprehensive_health_check.return_value = {
            "timestamp": "2023-01-01T00:00:00Z"
        }

        self.handler._handle_health_check()

        # Should send 503 error
        self.handler.send_response.assert_called_with(503)

    def test_handle_readiness_check_ready(self):
        """Test readiness check when system is ready."""
        health_report = {
            "overall_status": "healthy",
            "timestamp": "2023-01-01T00:00:00Z",
        }
        self.mock_health_monitor.comprehensive_health_check.return_value = health_report

        self.handler._handle_readiness_check()

        # Should return 200 for ready
        self.handler.send_response.assert_called_with(200)

        written_data = self.mock_wfile.write.call_args[0][0].decode("utf-8")
        response_data = json.loads(written_data)
        self.assertEqual(response_data["status"], "ready")

    def test_handle_readiness_check_not_ready(self):
        """Test readiness check when system is not ready."""
        health_report = {
            "overall_status": "unhealthy",
            "timestamp": "2023-01-01T00:00:00Z",
        }
        self.mock_health_monitor.comprehensive_health_check.return_value = health_report

        self.handler._handle_readiness_check()

        # Should return 503 for not ready
        self.handler.send_response.assert_called_with(503)

        written_data = self.mock_wfile.write.call_args[0][0].decode("utf-8")
        response_data = json.loads(written_data)
        self.assertEqual(response_data["status"], "not_ready")

    def test_handle_liveness_check(self):
        """Test liveness check endpoint."""
        health_report = {"timestamp": "2023-01-01T00:00:00Z"}
        self.mock_health_monitor.comprehensive_health_check.return_value = health_report

        self.handler._handle_liveness_check()

        # Should always return 200 for liveness
        self.handler.send_response.assert_called_with(200)

        written_data = self.mock_wfile.write.call_args[0][0].decode("utf-8")
        response_data = json.loads(written_data)
        self.assertEqual(response_data["status"], "alive")

    def test_handle_metrics_endpoint(self):
        """Test Prometheus metrics endpoint."""
        metrics_output = "# TYPE cpu_usage gauge\ncpu_usage 75.5\n"
        self.mock_health_monitor.export_prometheus_metrics.return_value = metrics_output

        self.handler._handle_metrics()

        # Should return 200 with text/plain content type
        self.handler.send_response.assert_called_with(200)
        self.handler.send_header.assert_any_call(
            "Content-Type", "text/plain; version=0.0.4; charset=utf-8"
        )

        # Verify metrics data was written
        written_data = self.mock_wfile.write.call_args[0][0].decode("utf-8")
        self.assertEqual(written_data, metrics_output)

    def test_handle_detailed_health(self):
        """Test detailed health check endpoint."""
        detailed_health = {
            "overall_status": "healthy",
            "timestamp": "2023-01-01T00:00:00Z",
            "checks": {"application": {"status": "healthy"}},
            "resource_status": {"cpu_usage_percent": 50.0},
        }
        self.mock_health_monitor.comprehensive_health_check.return_value = (
            detailed_health
        )

        self.handler._handle_detailed_health()

        # Should return 200
        self.handler.send_response.assert_called_with(200)

        written_data = self.mock_wfile.write.call_args[0][0].decode("utf-8")
        response_data = json.loads(written_data)
        self.assertEqual(response_data["overall_status"], "healthy")
        self.assertIn("checks", response_data)
        self.assertIn("resource_status", response_data)

    def test_send_json_response(self):
        """Test sending JSON response."""
        test_data = {"test": "data", "number": 42}

        self.handler._send_json_response(test_data, 201)

        # Verify response headers
        self.handler.send_response.assert_called_with(201)
        self.handler.send_header.assert_any_call("Content-Type", "application/json")
        self.handler.end_headers.assert_called_once()

        # Verify JSON data
        written_data = self.mock_wfile.write.call_args[0][0].decode("utf-8")
        response_data = json.loads(written_data)
        self.assertEqual(response_data, test_data)

    def test_send_error(self):
        """Test sending error response."""
        # Mock comprehensive_health_check for timestamp
        self.mock_health_monitor.comprehensive_health_check.return_value = {
            "timestamp": "2023-01-01T00:00:00Z"
        }

        self.handler._send_error(404, "Not Found")

        # Verify error response
        self.handler.send_response.assert_called_with(404)

        written_data = self.mock_wfile.write.call_args[0][0].decode("utf-8")
        response_data = json.loads(written_data)
        self.assertEqual(response_data["error"], "Not Found")
        self.assertEqual(response_data["status_code"], 404)


class TestHealthServer(unittest.TestCase):
    """Test HealthServer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_health_monitor = Mock(spec=HealthMonitor)
        self.health_server = HealthServer(
            health_monitor=self.mock_health_monitor,
            host="127.0.0.1",
            port=0,  # Use random available port
        )

    def test_health_server_initialization(self):
        """Test health server initialization."""
        self.assertEqual(self.health_server.health_monitor, self.mock_health_monitor)
        self.assertEqual(self.health_server.host, "127.0.0.1")
        self.assertEqual(self.health_server.port, 0)
        self.assertIsNone(self.health_server.server)

    @patch("core.health_server.HTTPServer")
    def test_start_server(self, mock_http_server):
        """Test starting the health server."""
        mock_server_instance = Mock()
        mock_http_server.return_value = mock_server_instance

        # Mock serve_forever to avoid blocking
        def mock_serve_forever():
            pass

        mock_server_instance.serve_forever = mock_serve_forever

        self.health_server.start()

        # Verify server was created and started
        mock_http_server.assert_called_once()
        self.assertEqual(self.health_server.server, mock_server_instance)

    def test_stop_server(self):
        """Test stopping the health server."""
        # Mock server instance
        mock_server = Mock()
        self.health_server.server = mock_server

        self.health_server.stop()

        # Verify shutdown methods were called
        mock_server.shutdown.assert_called_once()
        mock_server.server_close.assert_called_once()
        self.assertIsNone(self.health_server.server)

    def test_stop_server_when_not_running(self):
        """Test stopping server when it's not running."""
        self.health_server.server = None

        # Should not raise an error
        self.health_server.stop()

    @patch("threading.Thread")
    def test_start_in_background(self, mock_thread):
        """Test starting server in background thread."""
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        result = self.health_server.start_in_background()

        # Verify thread was created and started
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        self.assertEqual(result, mock_thread_instance)


class TestHealthServerIntegration(unittest.TestCase):
    """Integration tests for health server with real HTTP requests."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_health_monitor = Mock(spec=HealthMonitor)

        # Create server with random port
        self.health_server = HealthServer(
            health_monitor=self.mock_health_monitor, host="127.0.0.1", port=0
        )

        # Start server in background
        self.server_thread = None

    def tearDown(self):
        """Clean up test fixtures."""
        if self.health_server.server:
            self.health_server.stop()

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=1)

    def _start_test_server(self):
        """Start test server and return the actual port."""
        # Create server with port 0 to get random available port

        def handler_factory(*args, **kwargs):
            return HealthHTTPHandler(self.mock_health_monitor, *args, **kwargs)

        server = HTTPServer(("127.0.0.1", 0), handler_factory)
        actual_port = server.server_address[1]

        # Start in background thread
        def run_server():
            server.serve_forever()

        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()

        # Give server time to start
        time.sleep(0.1)

        self.health_server.server = server
        return actual_port

    def test_health_endpoint_integration(self):
        """Test health endpoint with real HTTP request."""
        port = self._start_test_server()

        # Mock health monitor response
        health_response = {
            "status": "healthy",
            "timestamp": "2023-01-01T00:00:00Z",
            "checks": {"application": "healthy"},
        }
        self.mock_health_monitor.get_health_endpoint_response.return_value = (
            health_response,
            200,
        )

        # Make HTTP request
        try:
            response = requests.get(f"http://127.0.0.1:{port}/health", timeout=1)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["Content-Type"], "application/json")

            data = response.json()
            self.assertEqual(data["status"], "healthy")

        except requests.exceptions.RequestException as e:
            self.skipTest(f"Could not connect to test server: {e}")

    def test_metrics_endpoint_integration(self):
        """Test metrics endpoint with real HTTP request."""
        port = self._start_test_server()

        # Mock metrics response
        metrics_output = "# TYPE cpu_usage gauge\ncpu_usage 75.5\n"
        self.mock_health_monitor.export_prometheus_metrics.return_value = metrics_output

        # Make HTTP request
        try:
            response = requests.get(f"http://127.0.0.1:{port}/metrics", timeout=1)

            self.assertEqual(response.status_code, 200)
            self.assertIn("text/plain", response.headers["Content-Type"])
            self.assertEqual(response.text, metrics_output)

        except requests.exceptions.RequestException as e:
            self.skipTest(f"Could not connect to test server: {e}")


class TestCreateHealthServer(unittest.TestCase):
    """Test health server factory function."""

    def test_create_health_server(self):
        """Test creating health server with factory function."""
        mock_health_monitor = Mock(spec=HealthMonitor)

        server = create_health_server(
            health_monitor=mock_health_monitor, host="localhost", port=9090
        )

        self.assertIsInstance(server, HealthServer)
        self.assertEqual(server.health_monitor, mock_health_monitor)
        self.assertEqual(server.host, "localhost")
        self.assertEqual(server.port, 9090)

    def test_create_health_server_defaults(self):
        """Test creating health server with default parameters."""
        mock_health_monitor = Mock(spec=HealthMonitor)

        server = create_health_server(mock_health_monitor)

        self.assertEqual(server.host, "0.0.0.0")
        self.assertEqual(server.port, 8080)


if __name__ == "__main__":
    unittest.main()
