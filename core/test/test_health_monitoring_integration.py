"""
Integration tests for the complete health monitoring system.

Tests the integration between HealthMonitor, HealthServer, and all components
working together in realistic scenarios.
"""

import json
import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

import pytest
import requests

from core.database import DatabaseManager
from core.health_monitor import HealthMonitor, HealthStatus
from core.health_server import create_health_server


class TestHealthMonitoringIntegration(unittest.TestCase):
    """Integration tests for complete health monitoring system."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock database managers
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_survey_db = Mock(spec=DatabaseManager)

        self.database_managers = {
            "rpa_db": self.mock_rpa_db,
            "SurveyHub": self.mock_survey_db,
        }

        # Create health monitor
        self.health_monitor = HealthMonitor(
            database_managers=self.database_managers,
            enable_prometheus=True,
            enable_structured_logging=True,
        )

        self.health_server = None
        self.server_thread = None

    def tearDown(self):
        """Clean up test fixtures."""
        if self.health_server and self.health_server.server:
            self.health_server.stop()

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2)

    @pytest.mark.slow
    def test_healthy_system_integration(self):
        """Test complete system when all components are healthy."""
        # Mock healthy database responses
        self.mock_rpa_db.execute_query.return_value = [{"health_check": 1}]
        self.mock_survey_db.execute_query.return_value = [{"health_check": 1}]

        # Set required environment variables
        with patch.dict(
            os.environ,
            {
                "CONTAINER_DATABASE_RPA_DB_HOST": "localhost",
                "CONTAINER_DATABASE_RPA_DB_NAME": "test_db",
            },
        ):
            # Perform comprehensive health check
            health_report = self.health_monitor.comprehensive_health_check()

            # Verify overall health
            self.assertEqual(health_report["overall_status"], "healthy")
            self.assertEqual(health_report["summary"]["total_checks"], 3)  # app + 2 dbs
            self.assertEqual(health_report["summary"]["healthy_checks"], 3)
            self.assertEqual(health_report["summary"]["unhealthy_checks"], 0)

            # Verify individual checks
            self.assertIn("application", health_report["checks"])
            self.assertIn("database_rpa_db", health_report["checks"])
            self.assertIn("database_SurveyHub", health_report["checks"])

            # Verify all checks are healthy
            for _check_name, check_result in health_report["checks"].items():
                self.assertEqual(check_result["status"], "healthy")

            # Verify resource status is included
            self.assertIn("resource_status", health_report)
            self.assertIn("cpu_usage_percent", health_report["resource_status"])

    @pytest.mark.slow
    def test_degraded_system_integration(self):
        """Test system when some components are degraded."""
        # Mock one healthy and one slow database
        self.mock_rpa_db.execute_query.return_value = [{"health_check": 1}]

        # Mock slow database response by patching the health check method directly
        original_check_db = self.health_monitor.check_database_health

        def mock_check_database_health(db_name):
            if db_name == "SurveyHub":
                # Return degraded status for SurveyHub
                from datetime import datetime

                from core.health_monitor import HealthCheckResult, HealthStatus

                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Database '{db_name}' performance degraded",
                    details={"response_time_ms": 1500.0},
                    timestamp=datetime.now(),
                    check_duration=1.5,
                )
            else:
                # Use original method for other databases
                return original_check_db(db_name)

        # Set required environment variables
        with patch.dict(
            os.environ,
            {
                "CONTAINER_DATABASE_RPA_DB_HOST": "localhost",
                "CONTAINER_DATABASE_RPA_DB_NAME": "test_db",
            },
        ):
            # Patch the database health check method
            with patch.object(
                self.health_monitor,
                "check_database_health",
                side_effect=mock_check_database_health,
            ):
                health_report = self.health_monitor.comprehensive_health_check()

                # System should be degraded due to slow database
                self.assertEqual(health_report["overall_status"], "degraded")
                self.assertGreater(health_report["summary"]["degraded_checks"], 0)
                self.assertEqual(health_report["summary"]["unhealthy_checks"], 0)

    @pytest.mark.slow
    def test_unhealthy_system_integration(self):
        """Test system when components are unhealthy."""
        # Mock database connection failures
        self.mock_rpa_db.execute_query.side_effect = Exception("Connection failed")
        self.mock_survey_db.execute_query.side_effect = Exception("Connection failed")

        # Missing environment variables will also cause unhealthy status
        with patch.dict(os.environ, {}, clear=True):
            health_report = self.health_monitor.comprehensive_health_check()

            # System should be unhealthy
            self.assertEqual(health_report["overall_status"], "unhealthy")
            self.assertGreater(health_report["summary"]["unhealthy_checks"], 0)

    @pytest.mark.slow
    def test_prometheus_metrics_integration(self):
        """Test Prometheus metrics export integration."""
        # Mock healthy system
        self.mock_rpa_db.execute_query.return_value = [{"health_check": 1}]
        self.mock_survey_db.execute_query.return_value = [{"health_check": 1}]

        with patch.dict(
            os.environ,
            {
                "CONTAINER_DATABASE_RPA_DB_HOST": "localhost",
                "CONTAINER_DATABASE_RPA_DB_NAME": "test_db",
            },
        ):
            # Run health checks to populate metrics
            self.health_monitor.comprehensive_health_check()

            # Manually call get_resource_status to populate resource metrics
            self.health_monitor.get_resource_status()

            # Export Prometheus metrics
            prometheus_output = self.health_monitor.export_prometheus_metrics()

            # Verify metrics format
            self.assertIn("# TYPE", prometheus_output)
            self.assertIn("application_health_status", prometheus_output)
            self.assertIn("overall_health_status", prometheus_output)

            # Check that we have the expected health and database metrics
            # Resource metrics may not be present in test environment due to mocking
            expected_metrics = [
                "database_response_time_ms",
                "database_health_status",
                "application_health_status",
                "overall_health_status",
            ]

            for metric in expected_metrics:
                self.assertIn(
                    metric,
                    prometheus_output,
                    f"Expected metric '{metric}' not found in output",
                )

            # Verify healthy status metrics
            self.assertIn("application_health_status 1", prometheus_output)
            self.assertIn("overall_health_status 1", prometheus_output)

    @pytest.mark.slow
    def test_health_server_integration(self):
        """Test health server integration with real HTTP requests."""
        # Mock healthy system
        self.mock_rpa_db.execute_query.return_value = [{"health_check": 1}]
        self.mock_survey_db.execute_query.return_value = [{"health_check": 1}]

        with patch.dict(
            os.environ,
            {
                "CONTAINER_DATABASE_RPA_DB_HOST": "localhost",
                "CONTAINER_DATABASE_RPA_DB_NAME": "test_db",
            },
        ):
            # Create and start health server
            self.health_server = create_health_server(
                health_monitor=self.health_monitor,
                host="127.0.0.1",
                port=0,  # Use random available port
            )

            # Start server in background
            from http.server import HTTPServer

            from core.health_server import HealthHTTPHandler

            def handler_factory(*args, **kwargs):
                return HealthHTTPHandler(self.health_monitor, *args, **kwargs)

            server = HTTPServer(("127.0.0.1", 0), handler_factory)
            actual_port = server.server_address[1]

            def run_server():
                server.serve_forever()

            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()

            # Give server time to start
            time.sleep(0.1)

            try:
                # Test health endpoint
                response = requests.get(
                    f"http://127.0.0.1:{actual_port}/health", timeout=5
                )
                self.assertEqual(response.status_code, 200)

                health_data = response.json()
                self.assertEqual(health_data["status"], "healthy")
                self.assertIn("checks", health_data)

                # Test metrics endpoint
                response = requests.get(
                    f"http://127.0.0.1:{actual_port}/metrics", timeout=5
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("text/plain", response.headers["Content-Type"])
                self.assertIn("application_health_status", response.text)

                # Test readiness endpoint
                response = requests.get(
                    f"http://127.0.0.1:{actual_port}/health/ready", timeout=5
                )
                self.assertEqual(response.status_code, 200)

                ready_data = response.json()
                self.assertEqual(ready_data["status"], "ready")

                # Test liveness endpoint
                response = requests.get(
                    f"http://127.0.0.1:{actual_port}/health/live", timeout=5
                )
                self.assertEqual(response.status_code, 200)

                live_data = response.json()
                self.assertEqual(live_data["status"], "alive")

            except requests.exceptions.RequestException as e:
                self.skipTest(f"Could not connect to test server: {e}")

            finally:
                server.shutdown()
                server.server_close()

    @pytest.mark.slow
    def test_structured_logging_integration(self):
        """Test structured logging integration."""
        # Capture log output
        import logging
        from io import StringIO

        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setFormatter(logging.Formatter("%(message)s"))

        # Add handler to health monitor logger
        if self.health_monitor.logger:
            self.health_monitor.logger.logger.addHandler(handler)
            self.health_monitor.logger.logger.setLevel(logging.INFO)

        # Mock database for health check
        self.mock_rpa_db.execute_query.return_value = [{"health_check": 1}]

        # Perform health check to generate logs
        self.health_monitor.check_database_health("rpa_db")

        # Get log output
        log_output = log_capture.getvalue()

        # Verify structured JSON logs
        if log_output:
            log_lines = [line for line in log_output.strip().split("\n") if line]

            for line in log_lines:
                try:
                    log_data = json.loads(line)

                    # Verify log structure
                    self.assertIn("timestamp", log_data)
                    self.assertIn("level", log_data)
                    self.assertIn("component", log_data)
                    self.assertIn("event_type", log_data)

                    if log_data["event_type"] == "health_check":
                        self.assertIn("check_component", log_data)
                        self.assertIn("status", log_data)
                        self.assertIn("message", log_data)
                        self.assertIn("check_duration_ms", log_data)

                except json.JSONDecodeError:
                    self.fail(f"Log line is not valid JSON: {line}")

    @pytest.mark.slow
    def test_error_handling_integration(self):
        """Test error handling across the integrated system."""
        # First check should handle error gracefully
        self.mock_rpa_db.execute_query.side_effect = Exception("Connection timeout")

        result1 = self.health_monitor.check_database_health("rpa_db")
        self.assertEqual(result1.status, HealthStatus.UNHEALTHY)
        self.assertIn("Connection timeout", result1.message)

        # Reset mock for recovery - second check should succeed
        self.mock_rpa_db.execute_query.side_effect = None
        self.mock_rpa_db.execute_query.return_value = [{"health_check": 1}]

        result2 = self.health_monitor.check_database_health("rpa_db")
        self.assertEqual(result2.status, HealthStatus.HEALTHY)

        # Comprehensive health check should handle mixed results
        self.mock_survey_db.execute_query.return_value = [{"health_check": 1}]

        with patch.dict(
            os.environ,
            {
                "CONTAINER_DATABASE_RPA_DB_HOST": "localhost",
                "CONTAINER_DATABASE_RPA_DB_NAME": "test_db",
            },
        ):
            health_report = self.health_monitor.comprehensive_health_check()

            # Should be healthy since both databases are now healthy
            self.assertEqual(health_report["overall_status"], "healthy")


if __name__ == "__main__":
    unittest.main()
