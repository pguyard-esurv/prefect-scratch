"""
HTTP server for health monitoring endpoints.

Provides HTTP endpoints for health checks and Prometheus metrics export
to support load balancer integration and monitoring systems.
"""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

from core.health_monitor import HealthMonitor


class HealthHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for health monitoring endpoints."""

    def __init__(self, health_monitor: HealthMonitor, *args, **kwargs):
        self.health_monitor = health_monitor
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests for health endpoints."""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path

            if path == "/health":
                self._handle_health_check()
            elif path == "/health/ready":
                self._handle_readiness_check()
            elif path == "/health/live":
                self._handle_liveness_check()
            elif path == "/metrics":
                self._handle_metrics()
            elif path == "/health/detailed":
                self._handle_detailed_health()
            else:
                self._send_error(404, "Not Found")

        except Exception as e:
            logging.error(f"Error handling health request: {e}")
            self._send_error(500, "Internal Server Error")

    def _handle_health_check(self):
        """Handle basic health check endpoint."""
        try:
            response, status_code = self.health_monitor.get_health_endpoint_response()
            self._send_json_response(response, status_code)
        except Exception as e:
            logging.error(f"Health check failed: {e}")
            self._send_error(503, "Service Unavailable")

    def _handle_readiness_check(self):
        """Handle readiness check (can accept traffic)."""
        try:
            health_report = self.health_monitor.comprehensive_health_check()

            # Ready if overall status is healthy or degraded
            overall_status = health_report["overall_status"]
            if overall_status in ["healthy", "degraded"]:
                status_code = 200
                response = {"status": "ready", "timestamp": health_report["timestamp"]}
            else:
                status_code = 503
                response = {
                    "status": "not_ready",
                    "timestamp": health_report["timestamp"],
                    "reason": "System is unhealthy",
                }

            self._send_json_response(response, status_code)

        except Exception as e:
            logging.error(f"Readiness check failed: {e}")
            self._send_error(503, "Service Unavailable")

    def _handle_liveness_check(self):
        """Handle liveness check (process is alive)."""
        try:
            # Simple liveness check - just verify the process is responding
            response = {
                "status": "alive",
                "timestamp": self.health_monitor.comprehensive_health_check()[
                    "timestamp"
                ],
            }
            self._send_json_response(response, 200)

        except Exception as e:
            logging.error(f"Liveness check failed: {e}")
            self._send_error(503, "Service Unavailable")

    def _handle_metrics(self):
        """Handle Prometheus metrics endpoint."""
        try:
            metrics_output = self.health_monitor.export_prometheus_metrics()

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(metrics_output)))
            self.end_headers()
            self.wfile.write(metrics_output.encode("utf-8"))

        except Exception as e:
            logging.error(f"Metrics export failed: {e}")
            self._send_error(500, "Internal Server Error")

    def _handle_detailed_health(self):
        """Handle detailed health check with full report."""
        try:
            health_report = self.health_monitor.comprehensive_health_check()
            self._send_json_response(health_report, 200)

        except Exception as e:
            logging.error(f"Detailed health check failed: {e}")
            self._send_error(500, "Internal Server Error")

    def _send_json_response(self, data: dict[str, Any], status_code: int = 200):
        """Send JSON response."""
        json_data = json.dumps(data, indent=2)

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(json_data)))
        self.end_headers()
        self.wfile.write(json_data.encode("utf-8"))

    def _send_error(self, status_code: int, message: str):
        """Send error response."""
        error_response = {
            "error": message,
            "status_code": status_code,
            "timestamp": self.health_monitor.comprehensive_health_check().get(
                "timestamp", ""
            ),
        }
        self._send_json_response(error_response, status_code)

    def log_message(self, format, *args):
        """Override to use structured logging."""
        # Suppress default HTTP server logging or customize as needed
        pass


class HealthServer:
    """HTTP server for health monitoring endpoints."""

    def __init__(
        self, health_monitor: HealthMonitor, host: str = "0.0.0.0", port: int = 8080
    ):
        """
        Initialize health server.

        Args:
            health_monitor: HealthMonitor instance
            host: Server host address
            port: Server port
        """
        self.health_monitor = health_monitor
        self.host = host
        self.port = port
        self.server = None

        # Create handler class with health monitor
        def handler_factory(*args, **kwargs):
            return HealthHTTPHandler(self.health_monitor, *args, **kwargs)

        self.handler_class = handler_factory

    def start(self):
        """Start the health server."""
        try:
            self.server = HTTPServer((self.host, self.port), self.handler_class)
            logging.info(f"Health server starting on {self.host}:{self.port}")

            # Log available endpoints
            endpoints = [
                "/health - Basic health check",
                "/health/ready - Readiness check",
                "/health/live - Liveness check",
                "/health/detailed - Detailed health report",
                "/metrics - Prometheus metrics",
            ]

            for endpoint in endpoints:
                logging.info(f"  Available endpoint: {endpoint}")

            self.server.serve_forever()

        except Exception as e:
            logging.error(f"Failed to start health server: {e}")
            raise

    def stop(self):
        """Stop the health server."""
        if self.server:
            logging.info("Stopping health server")
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def start_in_background(self):
        """Start the health server in a background thread."""
        import threading

        def run_server():
            try:
                self.start()
            except Exception as e:
                logging.error(f"Health server error: {e}")

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        logging.info(f"Health server started in background on {self.host}:{self.port}")
        return thread


def create_health_server(
    health_monitor: HealthMonitor, host: str = "0.0.0.0", port: int = 8080
) -> HealthServer:
    """
    Create and configure a health server.

    Args:
        health_monitor: HealthMonitor instance
        host: Server host address
        port: Server port

    Returns:
        Configured HealthServer instance
    """
    return HealthServer(health_monitor, host, port)


if __name__ == "__main__":
    # Example usage
    import os

    from core.database import DatabaseManager

    # Create health monitor with database managers
    database_managers = {}

    # Add RPA database if configured
    if os.getenv("CONTAINER_DATABASE_RPA_DB_HOST"):
        try:
            rpa_db = DatabaseManager("rpa_db")
            database_managers["rpa_db"] = rpa_db
        except Exception as e:
            logging.warning(f"Could not initialize RPA database: {e}")

    # Create health monitor
    health_monitor = HealthMonitor(
        database_managers=database_managers,
        enable_prometheus=True,
        enable_structured_logging=True,
    )

    # Create and start server
    server = create_health_server(health_monitor)

    try:
        server.start()
    except KeyboardInterrupt:
        logging.info("Shutting down health server")
        server.stop()
