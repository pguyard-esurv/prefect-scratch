#!/usr/bin/env python3
"""
Error Recovery Monitor Service.

This service monitors the error recovery system across all containers,
provides metrics export, and handles system-wide error recovery coordination.
"""

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import DatabaseManager
from core.error_recovery import AlertManager, ErrorRecoveryManager
from core.health_monitor import HealthMonitor


class MetricsHandler(BaseHTTPRequestHandler):
    """HTTP handler for metrics endpoint."""

    def __init__(self, monitor_service, *args, **kwargs):
        self.monitor_service = monitor_service
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/metrics":
            self._handle_metrics()
        elif self.path == "/health":
            self._handle_health()
        elif self.path == "/status":
            self._handle_status()
        else:
            self._handle_not_found()

    def _handle_metrics(self):
        """Handle metrics endpoint."""
        try:
            metrics = self.monitor_service.get_prometheus_metrics()

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(metrics.encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(f"Error generating metrics: {e}".encode())

    def _handle_health(self):
        """Handle health endpoint."""
        try:
            health_status = self.monitor_service.get_health_status()

            status_code = 200 if health_status["overall_status"] == "healthy" else 503

            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(health_status, indent=2).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_response = {"error": str(e), "status": "error"}
            self.wfile.write(json.dumps(error_response).encode("utf-8"))

    def _handle_status(self):
        """Handle status endpoint."""
        try:
            status = self.monitor_service.get_detailed_status()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status, indent=2).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            error_response = {"error": str(e), "status": "error"}
            self.wfile.write(json.dumps(error_response).encode("utf-8"))

    def _handle_not_found(self):
        """Handle 404 responses."""
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        """Override to use our logger."""
        pass  # Suppress default logging


class ErrorRecoveryMonitorService:
    """Service for monitoring error recovery across containers."""

    def __init__(self):
        """Initialize the monitor service."""
        self.logger = self._setup_logging()

        # Configuration
        self.flows_to_monitor = self._get_flows_to_monitor()
        self.monitor_interval = int(os.getenv("CONTAINER_MONITOR_INTERVAL", "60"))
        self.metrics_port = int(os.getenv("CONTAINER_METRICS_PORT", "9090"))

        # Initialize components
        self.database_managers = {}
        self.health_monitor = None
        self.error_recovery_manager = None
        self.metrics_server = None
        self.shutdown_requested = False

        # Monitoring data
        self.monitoring_data = {
            "flows": {},
            "system": {},
            "alerts": [],
            "last_update": None,
        }

        self.logger.info(
            f"Error Recovery Monitor initialized for flows: {self.flows_to_monitor}"
        )

    def _setup_logging(self) -> logging.Logger:
        """Setup structured logging."""
        logger = logging.getLogger("error_recovery_monitor")

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                '"component": "error_recovery_monitor", "message": "%(message)s"}'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)

        return logger

    def _get_flows_to_monitor(self) -> list[str]:
        """Get list of flows to monitor from environment."""
        flows_env = os.getenv("CONTAINER_MONITOR_FLOWS", "rpa1,rpa2,rpa3")
        return [flow.strip() for flow in flows_env.split(",") if flow.strip()]

    def initialize_components(self) -> bool:
        """Initialize monitoring components."""
        try:
            # Initialize database managers
            self.database_managers["rpa_db"] = DatabaseManager("rpa_db")

            # Initialize health monitor
            self.health_monitor = HealthMonitor(
                database_managers=self.database_managers,
                enable_prometheus=True,
                enable_structured_logging=True,
            )

            # Initialize error recovery manager
            alert_manager = AlertManager()
            self.error_recovery_manager = ErrorRecoveryManager(
                database_managers=self.database_managers,
                local_queue_path="/app/data/monitor_queue.json",
                disk_monitor_paths=["/", "/app", "/tmp"],
                alert_manager=alert_manager,
            )

            self.logger.info("Monitor components initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            return False

    def start_metrics_server(self):
        """Start HTTP server for metrics endpoint."""
        try:

            def handler_factory(*args, **kwargs):
                return MetricsHandler(self, *args, **kwargs)

            self.metrics_server = HTTPServer(
                ("0.0.0.0", self.metrics_port), handler_factory
            )

            # Start server in separate thread
            server_thread = threading.Thread(
                target=self.metrics_server.serve_forever, daemon=True
            )
            server_thread.start()

            self.logger.info(f"Metrics server started on port {self.metrics_port}")

        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")

    def monitor_flow_error_recovery(self, flow_name: str) -> dict[str, Any]:
        """Monitor error recovery for a specific flow."""
        flow_data = {
            "flow_name": flow_name,
            "timestamp": datetime.now().isoformat() + "Z",
            "status": "unknown",
            "queue_status": {},
            "alerts": [],
            "recovery_stats": {},
            "disk_status": {},
        }

        try:
            # Check if flow data directory exists
            flow_data_dir = Path(f"/app/data/{flow_name}")
            flow_logs_dir = Path(f"/app/logs/{flow_name}")

            if not flow_data_dir.exists():
                flow_data["status"] = "no_data_directory"
                flow_data["alerts"].append(
                    {
                        "severity": "warning",
                        "message": f"Data directory not found for flow {flow_name}",
                    }
                )
                return flow_data

            # Check for queue file
            queue_file = flow_data_dir / f"{flow_name}_queue.json"
            if queue_file.exists():
                try:
                    with open(queue_file) as f:
                        queue_data = json.load(f)

                    flow_data["queue_status"] = {
                        "queue_size": len(queue_data),
                        "oldest_operation": None,
                        "newest_operation": None,
                    }

                    if queue_data:
                        # Find oldest and newest operations
                        timestamps = [
                            op.get("queued_at")
                            for op in queue_data
                            if op.get("queued_at")
                        ]
                        if timestamps:
                            flow_data["queue_status"]["oldest_operation"] = min(
                                timestamps
                            )
                            flow_data["queue_status"]["newest_operation"] = max(
                                timestamps
                            )

                    # Alert if queue is large
                    if len(queue_data) > 100:
                        flow_data["alerts"].append(
                            {
                                "severity": "warning",
                                "message": f"Large queue size for flow {flow_name}: {len(queue_data)} operations",
                            }
                        )

                except Exception as e:
                    flow_data["alerts"].append(
                        {
                            "severity": "error",
                            "message": f"Failed to read queue file for flow {flow_name}: {e}",
                        }
                    )

            # Check for alert files
            alert_file = flow_logs_dir / "alerts.json"
            if alert_file.exists():
                try:
                    recent_alerts = []
                    cutoff_time = datetime.now() - timedelta(hours=1)

                    with open(alert_file) as f:
                        for line in f:
                            try:
                                alert = json.loads(line.strip())
                                alert_time = datetime.fromisoformat(
                                    alert.get("timestamp", "").replace("Z", "+00:00")
                                )
                                if alert_time > cutoff_time:
                                    recent_alerts.append(alert)
                            except Exception:
                                continue

                    flow_data["recent_alerts_count"] = len(recent_alerts)

                    # Include critical alerts
                    critical_alerts = [
                        alert
                        for alert in recent_alerts
                        if alert.get("severity") == "critical"
                    ]
                    if critical_alerts:
                        flow_data["alerts"].extend(
                            critical_alerts[:5]
                        )  # Last 5 critical alerts

                except Exception as e:
                    flow_data["alerts"].append(
                        {
                            "severity": "error",
                            "message": f"Failed to read alert file for flow {flow_name}: {e}",
                        }
                    )

            # Check disk usage for flow directories
            try:
                data_usage = sum(
                    f.stat().st_size for f in flow_data_dir.rglob("*") if f.is_file()
                )
                logs_usage = (
                    sum(
                        f.stat().st_size
                        for f in flow_logs_dir.rglob("*")
                        if f.is_file()
                    )
                    if flow_logs_dir.exists()
                    else 0
                )

                flow_data["disk_status"] = {
                    "data_usage_mb": round(data_usage / (1024 * 1024), 2),
                    "logs_usage_mb": round(logs_usage / (1024 * 1024), 2),
                    "total_usage_mb": round(
                        (data_usage + logs_usage) / (1024 * 1024), 2
                    ),
                }

                # Alert if usage is high
                total_mb = flow_data["disk_status"]["total_usage_mb"]
                if total_mb > 1000:  # 1GB
                    flow_data["alerts"].append(
                        {
                            "severity": "warning",
                            "message": f"High disk usage for flow {flow_name}: {total_mb:.1f} MB",
                        }
                    )

            except Exception as e:
                flow_data["alerts"].append(
                    {
                        "severity": "error",
                        "message": f"Failed to check disk usage for flow {flow_name}: {e}",
                    }
                )

            # Determine overall status
            if any(
                alert.get("severity") == "critical" for alert in flow_data["alerts"]
            ):
                flow_data["status"] = "critical"
            elif any(
                alert.get("severity") in ["error", "warning"]
                for alert in flow_data["alerts"]
            ):
                flow_data["status"] = "degraded"
            else:
                flow_data["status"] = "healthy"

        except Exception as e:
            flow_data["status"] = "error"
            flow_data["alerts"].append(
                {
                    "severity": "error",
                    "message": f"Failed to monitor flow {flow_name}: {e}",
                }
            )

        return flow_data

    def monitor_system_health(self) -> dict[str, Any]:
        """Monitor overall system health."""
        system_data = {
            "timestamp": datetime.now().isoformat() + "Z",
            "database_health": {},
            "resource_status": {},
            "error_recovery_status": {},
            "overall_status": "unknown",
        }

        try:
            # Database health
            if self.health_monitor:
                health_report = self.health_monitor.comprehensive_health_check()
                system_data["database_health"] = health_report

            # Error recovery status
            if self.error_recovery_manager:
                recovery_status = self.error_recovery_manager.get_recovery_status()
                system_data["error_recovery_status"] = recovery_status

            # Determine overall status
            db_status = system_data["database_health"].get("overall_status", "unknown")

            if db_status == "unhealthy":
                system_data["overall_status"] = "critical"
            elif db_status == "degraded":
                system_data["overall_status"] = "degraded"
            else:
                system_data["overall_status"] = "healthy"

        except Exception as e:
            system_data["overall_status"] = "error"
            system_data["error"] = str(e)

        return system_data

    def run_monitoring_cycle(self):
        """Run a single monitoring cycle."""
        try:
            self.logger.info("Starting monitoring cycle")

            # Monitor each flow
            for flow_name in self.flows_to_monitor:
                flow_data = self.monitor_flow_error_recovery(flow_name)
                self.monitoring_data["flows"][flow_name] = flow_data

                # Log flow status
                status = flow_data["status"]
                alert_count = len(flow_data["alerts"])

                if status == "critical":
                    self.logger.error(
                        f"Flow {flow_name} status: {status} ({alert_count} alerts)"
                    )
                elif status in ["degraded", "warning"]:
                    self.logger.warning(
                        f"Flow {flow_name} status: {status} ({alert_count} alerts)"
                    )
                else:
                    self.logger.info(f"Flow {flow_name} status: {status}")

            # Monitor system health
            system_data = self.monitor_system_health()
            self.monitoring_data["system"] = system_data

            # Update timestamp
            self.monitoring_data["last_update"] = datetime.now().isoformat() + "Z"

            # Log overall status
            overall_status = system_data["overall_status"]
            flow_statuses = [
                data["status"] for data in self.monitoring_data["flows"].values()
            ]

            critical_flows = sum(1 for status in flow_statuses if status == "critical")
            degraded_flows = sum(1 for status in flow_statuses if status == "degraded")

            self.logger.info(
                f"Monitoring cycle complete. System: {overall_status}, "
                f"Flows: {len(flow_statuses)} total, {critical_flows} critical, {degraded_flows} degraded"
            )

        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}")

    def get_prometheus_metrics(self) -> str:
        """Generate Prometheus metrics."""
        metrics_lines = []

        try:
            # System metrics
            system_data = self.monitoring_data.get("system", {})

            # Database health metric
            db_health = system_data.get("database_health", {})
            overall_status = db_health.get("overall_status", "unknown")
            health_value = 1 if overall_status == "healthy" else 0

            metrics_lines.append(
                "# HELP error_recovery_system_health System health status"
            )
            metrics_lines.append("# TYPE error_recovery_system_health gauge")
            metrics_lines.append(
                f'error_recovery_system_health{{status="{overall_status}"}} {health_value}'
            )

            # Flow metrics
            for flow_name, flow_data in self.monitoring_data.get("flows", {}).items():
                flow_status = flow_data.get("status", "unknown")
                flow_health_value = 1 if flow_status == "healthy" else 0

                metrics_lines.append(
                    f"# HELP error_recovery_flow_health Flow health status for {flow_name}"
                )
                metrics_lines.append("# TYPE error_recovery_flow_health gauge")
                metrics_lines.append(
                    f'error_recovery_flow_health{{flow="{flow_name}",status="{flow_status}"}} {flow_health_value}'
                )

                # Queue size metric
                queue_status = flow_data.get("queue_status", {})
                queue_size = queue_status.get("queue_size", 0)

                metrics_lines.append(
                    f"# HELP error_recovery_queue_size Queue size for {flow_name}"
                )
                metrics_lines.append("# TYPE error_recovery_queue_size gauge")
                metrics_lines.append(
                    f'error_recovery_queue_size{{flow="{flow_name}"}} {queue_size}'
                )

                # Alert count metric
                alert_count = len(flow_data.get("alerts", []))

                metrics_lines.append(
                    f"# HELP error_recovery_alert_count Alert count for {flow_name}"
                )
                metrics_lines.append("# TYPE error_recovery_alert_count gauge")
                metrics_lines.append(
                    f'error_recovery_alert_count{{flow="{flow_name}"}} {alert_count}'
                )

                # Disk usage metric
                disk_status = flow_data.get("disk_status", {})
                disk_usage = disk_status.get("total_usage_mb", 0)

                metrics_lines.append(
                    f"# HELP error_recovery_disk_usage_mb Disk usage in MB for {flow_name}"
                )
                metrics_lines.append("# TYPE error_recovery_disk_usage_mb gauge")
                metrics_lines.append(
                    f'error_recovery_disk_usage_mb{{flow="{flow_name}"}} {disk_usage}'
                )

            # Recovery statistics
            recovery_status = system_data.get("error_recovery_status", {})
            recovery_stats = recovery_status.get("recovery_stats", {})

            for stat_name, stat_value in recovery_stats.items():
                if isinstance(stat_value, (int, float)):
                    metrics_lines.append(
                        f"# HELP error_recovery_{stat_name} Error recovery statistic"
                    )
                    metrics_lines.append(f"# TYPE error_recovery_{stat_name} counter")
                    metrics_lines.append(f"error_recovery_{stat_name} {stat_value}")

        except Exception as e:
            self.logger.error(f"Error generating Prometheus metrics: {e}")
            metrics_lines.append(f"# Error generating metrics: {e}")

        return "\n".join(metrics_lines) + "\n"

    def get_health_status(self) -> dict[str, Any]:
        """Get health status for health endpoint."""
        system_data = self.monitoring_data.get("system", {})
        flows_data = self.monitoring_data.get("flows", {})

        # Determine overall health
        system_status = system_data.get("overall_status", "unknown")
        flow_statuses = [data.get("status", "unknown") for data in flows_data.values()]

        if system_status == "critical" or "critical" in flow_statuses:
            overall_status = "critical"
        elif system_status == "degraded" or "degraded" in flow_statuses:
            overall_status = "degraded"
        elif system_status == "healthy" and all(
            status == "healthy" for status in flow_statuses
        ):
            overall_status = "healthy"
        else:
            overall_status = "unknown"

        return {
            "overall_status": overall_status,
            "system_status": system_status,
            "flow_statuses": {
                flow_name: data.get("status", "unknown")
                for flow_name, data in flows_data.items()
            },
            "timestamp": datetime.now().isoformat() + "Z",
            "last_update": self.monitoring_data.get("last_update"),
        }

    def get_detailed_status(self) -> dict[str, Any]:
        """Get detailed status information."""
        return {
            "service": "error_recovery_monitor",
            "version": "1.0.0",
            "monitoring_data": self.monitoring_data,
            "configuration": {
                "flows_monitored": self.flows_to_monitor,
                "monitor_interval": self.monitor_interval,
                "metrics_port": self.metrics_port,
            },
        }

    def run(self):
        """Run the monitoring service."""
        try:
            self.logger.info("Starting Error Recovery Monitor Service")

            # Initialize components
            if not self.initialize_components():
                self.logger.error("Failed to initialize components")
                return 1

            # Start metrics server
            self.start_metrics_server()

            # Main monitoring loop
            while not self.shutdown_requested:
                try:
                    self.run_monitoring_cycle()
                    time.sleep(self.monitor_interval)

                except KeyboardInterrupt:
                    self.logger.info("Received interrupt signal")
                    break
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {e}")
                    time.sleep(10)  # Wait before retrying

            self.logger.info("Error Recovery Monitor Service stopped")
            return 0

        except Exception as e:
            self.logger.error(f"Fatal error in monitor service: {e}")
            return 1


def main():
    """Main entry point."""
    service = ErrorRecoveryMonitorService()
    return service.run()


if __name__ == "__main__":
    sys.exit(main())
