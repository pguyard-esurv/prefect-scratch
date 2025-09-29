"""
Unit tests for the health monitoring system.

Tests cover database health checks, application health checks, resource monitoring,
Prometheus metrics export, and structured logging functionality.
"""

import json
import os
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

from core.database import DatabaseManager
from core.health_monitor import (
    HealthCheckResult,
    HealthMonitor,
    HealthStatus,
    PrometheusMetrics,
    ResourceStatus,
    StructuredLogger,
)


class TestHealthCheckResult(unittest.TestCase):
    """Test HealthCheckResult data structure."""

    def test_health_check_result_creation(self):
        """Test creating a HealthCheckResult."""
        timestamp = datetime.now()
        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="Test message",
            details={"key": "value"},
            timestamp=timestamp,
            check_duration=1.5,
        )

        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertEqual(result.message, "Test message")
        self.assertEqual(result.details, {"key": "value"})
        self.assertEqual(result.timestamp, timestamp)
        self.assertEqual(result.check_duration, 1.5)

    def test_health_check_result_to_dict(self):
        """Test converting HealthCheckResult to dictionary."""
        timestamp = datetime.now()
        result = HealthCheckResult(
            status=HealthStatus.DEGRADED,
            message="Test message",
            details={"error": "test error"},
            timestamp=timestamp,
            check_duration=2.0,
        )

        result_dict = result.to_dict()

        self.assertEqual(result_dict["status"], "degraded")
        self.assertEqual(result_dict["message"], "Test message")
        self.assertEqual(result_dict["details"], {"error": "test error"})
        self.assertEqual(result_dict["timestamp"], timestamp.isoformat() + "Z")
        self.assertEqual(result_dict["check_duration"], 2.0)


class TestResourceStatus(unittest.TestCase):
    """Test ResourceStatus data structure."""

    def test_resource_status_creation(self):
        """Test creating a ResourceStatus."""
        status = ResourceStatus(
            cpu_usage_percent=50.5,
            memory_usage_mb=1024.0,
            memory_limit_mb=2048.0,
            memory_usage_percent=50.0,
            disk_usage_mb=5000.0,
            disk_available_mb=10000.0,
            disk_usage_percent=33.3,
            network_connections=25,
            load_average=(1.0, 1.5, 2.0),
        )

        self.assertEqual(status.cpu_usage_percent, 50.5)
        self.assertEqual(status.memory_usage_mb, 1024.0)
        self.assertEqual(status.memory_limit_mb, 2048.0)
        self.assertEqual(status.memory_usage_percent, 50.0)
        self.assertEqual(status.disk_usage_mb, 5000.0)
        self.assertEqual(status.disk_available_mb, 10000.0)
        self.assertEqual(status.disk_usage_percent, 33.3)
        self.assertEqual(status.network_connections, 25)
        self.assertEqual(status.load_average, (1.0, 1.5, 2.0))

    def test_resource_status_to_dict(self):
        """Test converting ResourceStatus to dictionary."""
        status = ResourceStatus(
            cpu_usage_percent=75.0,
            memory_usage_mb=1500.0,
            memory_limit_mb=2048.0,
            memory_usage_percent=73.2,
            disk_usage_mb=8000.0,
            disk_available_mb=2000.0,
            disk_usage_percent=80.0,
            network_connections=50,
            load_average=(2.5, 2.0, 1.5),
        )

        status_dict = status.to_dict()

        self.assertEqual(status_dict["cpu_usage_percent"], 75.0)
        self.assertEqual(status_dict["memory_usage_mb"], 1500.0)
        self.assertEqual(status_dict["load_average"], [2.5, 2.0, 1.5])


class TestStructuredLogger(unittest.TestCase):
    """Test structured JSON logging functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.logger = StructuredLogger("test_logger")

    @patch("core.health_monitor.logging.getLogger")
    def test_structured_logger_initialization(self, mock_get_logger):
        """Test StructuredLogger initialization."""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        StructuredLogger("test")

        mock_get_logger.assert_called_once_with("test")
        mock_logger.addHandler.assert_called_once()
        mock_logger.setLevel.assert_called_once()

    @patch("core.health_monitor.logging.getLogger")
    def test_log_health_check(self, mock_get_logger):
        """Test logging health check results."""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        logger = StructuredLogger("test")

        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="Test check",
            details={"test": "data"},
            timestamp=datetime.now(),
            check_duration=1.0,
        )

        logger.log_health_check("test_component", result)

        # Verify info was called with JSON string
        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])

        self.assertEqual(logged_data["component"], "health_monitor")
        self.assertEqual(logged_data["event_type"], "health_check")
        self.assertEqual(logged_data["check_component"], "test_component")
        self.assertEqual(logged_data["status"], "healthy")
        self.assertEqual(logged_data["message"], "Test check")

    @patch("core.health_monitor.logging.getLogger")
    def test_log_metrics(self, mock_get_logger):
        """Test logging metrics."""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        logger = StructuredLogger("test")

        metrics = {"cpu_usage": 50.0, "memory_usage": 1024}
        logger.log_metrics(metrics)

        mock_logger.info.assert_called_once()
        logged_data = json.loads(mock_logger.info.call_args[0][0])

        self.assertEqual(logged_data["event_type"], "metrics")
        self.assertEqual(logged_data["metrics"], metrics)

    @patch("core.health_monitor.logging.getLogger")
    def test_log_alert(self, mock_get_logger):
        """Test logging alerts."""
        mock_logger = Mock()
        mock_logger.handlers = []
        mock_get_logger.return_value = mock_logger

        logger = StructuredLogger("test")

        logger.log_alert("high_cpu", "CPU usage is high", "CRITICAL")

        mock_logger.warning.assert_called_once()
        logged_data = json.loads(mock_logger.warning.call_args[0][0])

        self.assertEqual(logged_data["event_type"], "alert")
        self.assertEqual(logged_data["alert_type"], "high_cpu")
        self.assertEqual(logged_data["message"], "CPU usage is high")
        self.assertEqual(logged_data["level"], "CRITICAL")


class TestPrometheusMetrics(unittest.TestCase):
    """Test Prometheus metrics functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.metrics = PrometheusMetrics()

    def test_update_gauge(self):
        """Test updating gauge metrics."""
        self.metrics.update_gauge("test_gauge", 42.5)

        self.assertIn("test_gauge", self.metrics.metrics)
        self.assertEqual(self.metrics.metrics["test_gauge"]["type"], "gauge")
        self.assertEqual(self.metrics.metrics["test_gauge"]["value"], 42.5)

    def test_update_gauge_with_labels(self):
        """Test updating gauge metrics with labels."""
        self.metrics.update_gauge(
            "test_gauge", 100.0, {"service": "test", "env": "dev"}
        )

        # Labels are sorted alphabetically, so check for the actual key
        actual_keys = list(self.metrics.metrics.keys())
        self.assertEqual(len(actual_keys), 1)

        key = actual_keys[0]
        self.assertTrue(key.startswith("test_gauge{"))
        self.assertIn('env="dev"', key)
        self.assertIn('service="test"', key)
        self.assertEqual(self.metrics.metrics[key]["value"], 100.0)

    def test_increment_counter(self):
        """Test incrementing counter metrics."""
        self.metrics.increment_counter("test_counter", 5.0)
        self.assertEqual(self.metrics.metrics["test_counter"]["value"], 5.0)

        self.metrics.increment_counter("test_counter", 3.0)
        self.assertEqual(self.metrics.metrics["test_counter"]["value"], 8.0)

    def test_increment_counter_with_labels(self):
        """Test incrementing counter metrics with labels."""
        self.metrics.increment_counter("requests_total", 1.0, {"method": "GET"})
        self.metrics.increment_counter("requests_total", 2.0, {"method": "GET"})

        expected_key = 'requests_total{method="GET"}'
        self.assertEqual(self.metrics.metrics[expected_key]["value"], 3.0)

    def test_export_prometheus_format(self):
        """Test exporting metrics in Prometheus format."""
        self.metrics.update_gauge("cpu_usage", 75.5)
        self.metrics.increment_counter("requests_total", 100)

        prometheus_output = self.metrics.export_prometheus_format()

        self.assertIn("# TYPE cpu_usage gauge", prometheus_output)
        self.assertIn("cpu_usage 75.5", prometheus_output)
        self.assertIn("# TYPE requests_total counter", prometheus_output)
        self.assertIn("requests_total 100", prometheus_output)

    def test_get_metrics_dict(self):
        """Test getting metrics as dictionary."""
        self.metrics.update_gauge("test_metric", 50.0)

        metrics_dict = self.metrics.get_metrics_dict()

        self.assertIn("metrics", metrics_dict)
        self.assertIn("last_update", metrics_dict)
        self.assertIn("total_metrics", metrics_dict)
        self.assertEqual(metrics_dict["total_metrics"], 1)


class TestHealthMonitor(unittest.TestCase):
    """Test HealthMonitor main functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_manager = Mock(spec=DatabaseManager)
        self.database_managers = {"test_db": self.mock_db_manager}
        self.health_monitor = HealthMonitor(
            database_managers=self.database_managers,
            enable_prometheus=True,
            enable_structured_logging=True,
        )

    @patch("core.health_monitor.psutil.virtual_memory")
    def test_get_memory_limit_system_fallback(self, mock_virtual_memory):
        """Test getting memory limit with system fallback."""
        mock_memory = Mock()
        mock_memory.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_virtual_memory.return_value = mock_memory

        monitor = HealthMonitor()
        memory_limit = monitor._get_memory_limit()

        self.assertEqual(memory_limit, 8 * 1024)  # 8GB in MB

    def test_check_database_health_success(self):
        """Test successful database health check."""
        # Mock successful database query
        self.mock_db_manager.execute_query.return_value = [{"health_check": 1}]

        result = self.health_monitor.check_database_health("test_db")

        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertIn("test_db", result.message)
        self.assertIn("response_time_ms", result.details)
        self.mock_db_manager.execute_query.assert_called()

    def test_check_database_health_slow_response(self):
        """Test database health check with slow response."""

        # Mock slow database response
        def slow_query(*args, **kwargs):
            return [{"health_check": 1}]

        self.mock_db_manager.execute_query.side_effect = slow_query

        # Mock time.time to simulate slow response (>1000ms for degraded)
        with patch("time.time") as mock_time:
            # Provide enough values for all time.time() calls
            mock_time.side_effect = [
                0,
                0.001,
                1.5,
                1.5,
                1.5,
                1.5,
                1.5,
            ]  # 1500ms response time
            result = self.health_monitor.check_database_health("test_db")

        # Should be degraded due to high response time (mocked as 5000ms)
        self.assertEqual(result.status, HealthStatus.DEGRADED)

    def test_check_database_health_connection_failure(self):
        """Test database health check with connection failure."""
        self.mock_db_manager.execute_query.side_effect = Exception("Connection failed")

        result = self.health_monitor.check_database_health("test_db")

        self.assertEqual(result.status, HealthStatus.UNHEALTHY)
        self.assertIn("Connection failed", result.message)
        self.assertIn("error", result.details)

    def test_check_database_health_unknown_database(self):
        """Test database health check for unknown database."""
        result = self.health_monitor.check_database_health("unknown_db")

        self.assertEqual(result.status, HealthStatus.UNHEALTHY)
        self.assertIn("not configured", result.message)

    @patch.dict(
        os.environ,
        {
            "CONTAINER_DATABASE_RPA_DB_HOST": "localhost",
            "CONTAINER_DATABASE_RPA_DB_NAME": "test_db",
        },
    )
    @patch("core.health_monitor.HealthMonitor.get_resource_status")
    @patch("core.health_monitor.HealthMonitor.check_database_health")
    def test_check_application_health_success(
        self, mock_db_health, mock_resource_status
    ):
        """Test successful application health check."""
        # Mock healthy database
        mock_db_health.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="DB healthy",
            details={},
            timestamp=datetime.now(),
            check_duration=0.1,
        )

        # Mock normal resource usage
        mock_resource_status.return_value = ResourceStatus(
            cpu_usage_percent=50.0,
            memory_usage_mb=1024.0,
            memory_limit_mb=2048.0,
            memory_usage_percent=50.0,
            disk_usage_mb=5000.0,
            disk_available_mb=5000.0,
            disk_usage_percent=50.0,
            network_connections=10,
            load_average=(1.0, 1.0, 1.0),
        )

        result = self.health_monitor.check_application_health()

        self.assertEqual(result.status, HealthStatus.HEALTHY)
        self.assertIn("environment_check", result.details)
        self.assertIn("database_health", result.details)
        self.assertIn("resource_status", result.details)

    @patch.dict(os.environ, {}, clear=True)
    def test_check_application_health_missing_env_vars(self):
        """Test application health check with missing environment variables."""
        result = self.health_monitor.check_application_health()

        self.assertEqual(result.status, HealthStatus.UNHEALTHY)
        self.assertIn("Missing environment variables", result.message)
        self.assertIn("missing_vars", result.details["environment_check"])

    @patch("core.health_monitor.psutil.cpu_percent")
    @patch("core.health_monitor.psutil.virtual_memory")
    @patch("core.health_monitor.psutil.disk_usage")
    @patch("core.health_monitor.psutil.net_connections")
    @patch("core.health_monitor.os.getloadavg")
    def test_get_resource_status(
        self, mock_loadavg, mock_net_conn, mock_disk, mock_memory, mock_cpu
    ):
        """Test getting resource status."""
        # Mock system resource calls
        mock_cpu.return_value = 75.5

        mock_memory_obj = Mock()
        mock_memory_obj.total = 2 * 1024 * 1024 * 1024  # 2GB
        mock_memory_obj.available = 1 * 1024 * 1024 * 1024  # 1GB available
        mock_memory.return_value = mock_memory_obj

        mock_disk_obj = Mock()
        mock_disk_obj.total = 100 * 1024 * 1024 * 1024  # 100GB
        mock_disk_obj.used = 50 * 1024 * 1024 * 1024  # 50GB used
        mock_disk_obj.free = 50 * 1024 * 1024 * 1024  # 50GB free
        mock_disk.return_value = mock_disk_obj

        mock_net_conn.return_value = [Mock()] * 25  # 25 connections
        mock_loadavg.return_value = (1.5, 2.0, 2.5)

        resource_status = self.health_monitor.get_resource_status()

        self.assertEqual(resource_status.cpu_usage_percent, 75.5)
        self.assertEqual(resource_status.memory_usage_mb, 1024.0)  # 1GB in MB
        self.assertEqual(resource_status.disk_usage_percent, 50.0)
        self.assertEqual(resource_status.network_connections, 25)
        self.assertEqual(resource_status.load_average, (1.5, 2.0, 2.5))

    @patch("core.health_monitor.HealthMonitor.check_application_health")
    @patch("core.health_monitor.HealthMonitor.check_database_health")
    @patch("core.health_monitor.HealthMonitor.get_resource_status")
    def test_comprehensive_health_check(
        self, mock_resource, mock_db_health, mock_app_health
    ):
        """Test comprehensive health check."""
        # Mock healthy application
        mock_app_health.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="App healthy",
            details={},
            timestamp=datetime.now(),
            check_duration=0.1,
        )

        # Mock healthy database
        mock_db_health.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="DB healthy",
            details={},
            timestamp=datetime.now(),
            check_duration=0.1,
        )

        # Mock resource status
        mock_resource.return_value = ResourceStatus(
            cpu_usage_percent=50.0,
            memory_usage_mb=1024.0,
            memory_limit_mb=2048.0,
            memory_usage_percent=50.0,
            disk_usage_mb=5000.0,
            disk_available_mb=5000.0,
            disk_usage_percent=50.0,
            network_connections=10,
            load_average=(1.0, 1.0, 1.0),
        )

        health_report = self.health_monitor.comprehensive_health_check()

        self.assertEqual(health_report["overall_status"], "healthy")
        self.assertIn("checks", health_report)
        self.assertIn("resource_status", health_report)
        self.assertIn("summary", health_report)
        self.assertEqual(health_report["summary"]["healthy_checks"], 2)  # app + db
        self.assertEqual(health_report["summary"]["unhealthy_checks"], 0)

    def test_get_health_endpoint_response_healthy(self):
        """Test health endpoint response for healthy system."""
        with patch.object(
            self.health_monitor, "comprehensive_health_check"
        ) as mock_health:
            mock_health.return_value = {
                "overall_status": "healthy",
                "timestamp": "2023-01-01T00:00:00Z",
                "checks": {
                    "application": {"status": "healthy"},
                    "database_test_db": {"status": "healthy"},
                },
            }

            response, status_code = self.health_monitor.get_health_endpoint_response()

            self.assertEqual(status_code, 200)
            self.assertEqual(response["status"], "healthy")
            self.assertIn("checks", response)

    def test_get_health_endpoint_response_unhealthy(self):
        """Test health endpoint response for unhealthy system."""
        with patch.object(
            self.health_monitor, "comprehensive_health_check"
        ) as mock_health:
            mock_health.return_value = {
                "overall_status": "unhealthy",
                "timestamp": "2023-01-01T00:00:00Z",
                "checks": {
                    "application": {"status": "unhealthy"},
                    "database_test_db": {"status": "healthy"},
                },
            }

            response, status_code = self.health_monitor.get_health_endpoint_response()

            self.assertEqual(status_code, 503)
            self.assertEqual(response["status"], "unhealthy")

    def test_export_prometheus_metrics(self):
        """Test exporting Prometheus metrics."""
        with (
            patch.object(self.health_monitor, "get_resource_status"),
            patch.object(self.health_monitor, "comprehensive_health_check"),
        ):
            prometheus_output = self.health_monitor.export_prometheus_metrics()

            self.assertIsInstance(prometheus_output, str)
            # Should contain some metric type definitions
            self.assertTrue(len(prometheus_output) > 0)

    def test_get_metrics_dict(self):
        """Test getting metrics as dictionary."""
        with patch.object(self.health_monitor, "get_resource_status"):
            metrics_dict = self.health_monitor.get_metrics_dict()

            self.assertIn("metrics", metrics_dict)
            self.assertIn("last_update", metrics_dict)

    def test_health_monitor_without_prometheus(self):
        """Test health monitor with Prometheus disabled."""
        monitor = HealthMonitor(enable_prometheus=False)

        self.assertIsNone(monitor.metrics)

        prometheus_output = monitor.export_prometheus_metrics()
        self.assertIn("not enabled", prometheus_output)

        metrics_dict = monitor.get_metrics_dict()
        self.assertIn("error", metrics_dict)

    def test_health_monitor_without_structured_logging(self):
        """Test health monitor with structured logging disabled."""
        monitor = HealthMonitor(enable_structured_logging=False)

        self.assertIsNone(monitor.logger)


if __name__ == "__main__":
    unittest.main()
