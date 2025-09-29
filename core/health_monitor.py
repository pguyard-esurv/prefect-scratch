"""
Comprehensive health monitoring system for container environments.

This module provides health monitoring capabilities including database health,
application health, resource monitoring, Prometheus metrics export, and
structured JSON logging for container-based deployments.
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import psutil

from core.database import DatabaseManager


class HealthStatus(Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Health check result data structure."""

    status: HealthStatus
    message: str
    details: dict[str, Any]
    timestamp: datetime
    check_duration: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["status"] = self.status.value
        result["timestamp"] = self.timestamp.isoformat() + "Z"
        return result


@dataclass
class ResourceStatus:
    """Resource usage status information."""

    cpu_usage_percent: float
    memory_usage_mb: float
    memory_limit_mb: float
    memory_usage_percent: float
    disk_usage_mb: float
    disk_available_mb: float
    disk_usage_percent: float
    network_connections: int
    load_average: tuple[float, float, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["load_average"] = list(self.load_average)
        return result


@dataclass
class DatabaseHealthStatus:
    """Database health status information."""

    connection_status: HealthStatus
    response_time_ms: float
    active_connections: int
    max_connections: int
    connection_usage_percent: float
    query_performance: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["connection_status"] = self.connection_status.value
        return result


class StructuredLogger:
    """Structured JSON logger for health monitoring."""

    def __init__(self, name: str = "health_monitor"):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_health_check(self, component: str, result: HealthCheckResult):
        """Log health check result in structured JSON format."""
        log_data = {
            "timestamp": datetime.now().isoformat() + "Z",
            "level": "INFO",
            "component": "health_monitor",
            "event_type": "health_check",
            "check_component": component,
            "status": result.status.value,
            "message": result.message,
            "check_duration_ms": round(result.check_duration * 1000, 2),
            "details": result.details,
        }
        self.logger.info(json.dumps(log_data))

    def log_metrics(self, metrics: dict[str, Any]):
        """Log metrics in structured JSON format."""
        log_data = {
            "timestamp": datetime.now().isoformat() + "Z",
            "level": "INFO",
            "component": "health_monitor",
            "event_type": "metrics",
            "metrics": metrics,
        }
        self.logger.info(json.dumps(log_data))

    def log_alert(self, alert_type: str, message: str, severity: str = "WARNING"):
        """Log alert in structured JSON format."""
        log_data = {
            "timestamp": datetime.now().isoformat() + "Z",
            "level": severity,
            "component": "health_monitor",
            "event_type": "alert",
            "alert_type": alert_type,
            "message": message,
        }
        self.logger.warning(json.dumps(log_data))


class PrometheusMetrics:
    """Prometheus-compatible metrics exporter."""

    def __init__(self):
        self.metrics = {}
        self.last_update = datetime.now()

    def update_gauge(
        self, name: str, value: float, labels: Optional[dict[str, str]] = None
    ):
        """Update a gauge metric."""
        labels = labels or {}
        label_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
        metric_key = f"{name}{{{label_str}}}" if label_str else name

        self.metrics[metric_key] = {
            "type": "gauge",
            "value": value,
            "timestamp": time.time(),
        }

    def increment_counter(
        self, name: str, value: float = 1.0, labels: Optional[dict[str, str]] = None
    ):
        """Increment a counter metric."""
        labels = labels or {}
        label_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
        metric_key = f"{name}{{{label_str}}}" if label_str else name

        if metric_key in self.metrics:
            self.metrics[metric_key]["value"] += value
        else:
            self.metrics[metric_key] = {
                "type": "counter",
                "value": value,
                "timestamp": time.time(),
            }

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        for metric_key, metric_data in self.metrics.items():
            # Extract metric name and labels
            if "{" in metric_key:
                name, labels = metric_key.split("{", 1)
                labels = "{" + labels
            else:
                name, labels = metric_key, ""

            # Add type comment
            lines.append(f"# TYPE {name} {metric_data['type']}")

            # Add metric line
            lines.append(f"{name}{labels} {metric_data['value']}")

        return "\n".join(lines) + "\n"

    def get_metrics_dict(self) -> dict[str, Any]:
        """Get metrics as dictionary."""
        return {
            "metrics": self.metrics,
            "last_update": self.last_update.isoformat() + "Z",
            "total_metrics": len(self.metrics),
        }


class HealthMonitor:
    """Comprehensive health monitoring system for containers."""

    def __init__(
        self,
        database_managers: Optional[dict[str, DatabaseManager]] = None,
        enable_prometheus: bool = True,
        enable_structured_logging: bool = True,
    ):
        """
        Initialize health monitor.

        Args:
            database_managers: Dictionary of database managers to monitor
            enable_prometheus: Whether to enable Prometheus metrics export
            enable_structured_logging: Whether to enable structured JSON logging
        """
        self.database_managers = database_managers or {}
        self.enable_prometheus = enable_prometheus
        self.enable_structured_logging = enable_structured_logging

        # Initialize components
        self.logger = StructuredLogger() if enable_structured_logging else None
        self.metrics = PrometheusMetrics() if enable_prometheus else None

        # Health check cache
        self._health_cache = {}
        self._cache_ttl = 30  # seconds

        # Resource monitoring
        self._memory_limit_mb = self._get_memory_limit()

    def _get_memory_limit(self) -> float:
        """Get container memory limit from cgroup or system memory."""
        try:
            # Try to read from cgroup v2
            if os.path.exists("/sys/fs/cgroup/memory.max"):
                with open("/sys/fs/cgroup/memory.max") as f:
                    limit = f.read().strip()
                    if limit != "max":
                        return int(limit) / (1024 * 1024)  # Convert to MB

            # Try to read from cgroup v1
            if os.path.exists("/sys/fs/cgroup/memory/memory.limit_in_bytes"):
                with open("/sys/fs/cgroup/memory/memory.limit_in_bytes") as f:
                    limit = int(f.read().strip())
                    # Check if it's a reasonable limit (not the default huge value)
                    if limit < 9223372036854775807:  # Max int64
                        return limit / (1024 * 1024)  # Convert to MB

            # Fallback to system memory
            return psutil.virtual_memory().total / (1024 * 1024)

        except Exception:
            # Fallback to system memory
            return psutil.virtual_memory().total / (1024 * 1024)

    def check_database_health(self, db_name: str) -> HealthCheckResult:
        """
        Check database health including connectivity and performance.

        Args:
            db_name: Name of the database to check

        Returns:
            HealthCheckResult with database health information
        """
        start_time = time.time()

        try:
            if db_name not in self.database_managers:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database manager '{db_name}' not configured",
                    details={"error": "Database manager not found"},
                    timestamp=datetime.now(),
                    check_duration=time.time() - start_time,
                )

            db_manager = self.database_managers[db_name]

            # Test basic connectivity
            query_start = time.time()
            result = db_manager.execute_query("SELECT 1 as health_check")
            response_time_ms = (time.time() - query_start) * 1000

            if not result or result[0].get("health_check") != 1:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database '{db_name}' connectivity test failed",
                    details={"response_time_ms": response_time_ms},
                    timestamp=datetime.now(),
                    check_duration=time.time() - start_time,
                )

            # Get connection pool information
            connection_info = self._get_database_connection_info(db_manager)

            # Determine health status
            if response_time_ms > 5000:  # 5 seconds
                status = HealthStatus.UNHEALTHY
                message = f"Database '{db_name}' response time too high"
            elif (
                response_time_ms > 1000 or connection_info.get("usage_percent", 0) > 80
            ):
                status = HealthStatus.DEGRADED
                message = f"Database '{db_name}' performance degraded"
            else:
                status = HealthStatus.HEALTHY
                message = f"Database '{db_name}' is healthy"

            details = {
                "response_time_ms": round(response_time_ms, 2),
                "connection_info": connection_info,
            }

            result = HealthCheckResult(
                status=status,
                message=message,
                details=details,
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

            # Update metrics
            if self.metrics:
                self.metrics.update_gauge(
                    "database_response_time_ms", response_time_ms, {"database": db_name}
                )
                self.metrics.update_gauge(
                    "database_health_status",
                    1 if status == HealthStatus.HEALTHY else 0,
                    {"database": db_name},
                )

            # Log result
            if self.logger:
                self.logger.log_health_check(f"database_{db_name}", result)

            return result

        except Exception as e:
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Database '{db_name}' health check failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

            if self.logger:
                self.logger.log_health_check(f"database_{db_name}", result)

            return result

    def _get_database_connection_info(
        self, db_manager: DatabaseManager
    ) -> dict[str, Any]:
        """Get database connection pool information."""
        try:
            # Try to get connection pool stats
            pool_stats = db_manager.execute_query(
                """
                SELECT
                    count(*) as total_connections,
                    count(CASE WHEN state = 'active' THEN 1 END) as active_connections,
                    count(CASE WHEN state = 'idle' THEN 1 END) as idle_connections
                FROM pg_stat_activity
                WHERE datname = current_database()
            """
            )

            if pool_stats:
                stats = pool_stats[0]
                return {
                    "total_connections": stats.get("total_connections", 0),
                    "active_connections": stats.get("active_connections", 0),
                    "idle_connections": stats.get("idle_connections", 0),
                    "usage_percent": 0,  # Would need max_connections to calculate
                }

        except Exception:
            pass

        return {"error": "Could not retrieve connection information"}

    def check_application_health(self) -> HealthCheckResult:
        """
        Check application health including startup status and dependencies.

        Returns:
            HealthCheckResult with application health information
        """
        start_time = time.time()

        try:
            details = {}
            issues = []

            # Check environment variables
            required_env_vars = [
                "CONTAINER_DATABASE_RPA_DB_HOST",
                "CONTAINER_DATABASE_RPA_DB_NAME",
            ]

            missing_env_vars = []
            for env_var in required_env_vars:
                if not os.getenv(env_var):
                    missing_env_vars.append(env_var)

            if missing_env_vars:
                issues.append(
                    f"Missing environment variables: {', '.join(missing_env_vars)}"
                )

            details["environment_check"] = {
                "required_vars": required_env_vars,
                "missing_vars": missing_env_vars,
            }

            # Check database connectivity
            db_health_results = {}
            for db_name in self.database_managers.keys():
                db_result = self.check_database_health(db_name)
                db_health_results[db_name] = db_result.status.value
                if db_result.status != HealthStatus.HEALTHY:
                    issues.append(f"Database '{db_name}' is {db_result.status.value}")

            details["database_health"] = db_health_results

            # Check resource usage
            resource_status = self.get_resource_status()
            if resource_status.memory_usage_percent > 90:
                issues.append("High memory usage (>90%)")
            if resource_status.cpu_usage_percent > 95:
                issues.append("High CPU usage (>95%)")
            if resource_status.disk_usage_percent > 90:
                issues.append("High disk usage (>90%)")

            details["resource_status"] = resource_status.to_dict()

            # Determine overall health
            if issues:
                # Check if any databases are unhealthy (not just degraded)
                unhealthy_db_issues = [
                    issue
                    for issue in issues
                    if "Database" in issue and "unhealthy" in issue
                ]

                if missing_env_vars or unhealthy_db_issues:
                    status = HealthStatus.UNHEALTHY
                    message = f"Application health check failed: {'; '.join(issues)}"
                else:
                    status = HealthStatus.DEGRADED
                    message = f"Application health degraded: {'; '.join(issues)}"
            else:
                status = HealthStatus.HEALTHY
                message = "Application is healthy"

            details["issues"] = issues

            result = HealthCheckResult(
                status=status,
                message=message,
                details=details,
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

            # Update metrics
            if self.metrics:
                self.metrics.update_gauge(
                    "application_health_status",
                    1 if status == HealthStatus.HEALTHY else 0,
                )
                self.metrics.update_gauge("application_issues_count", len(issues))

            # Log result
            if self.logger:
                self.logger.log_health_check("application", result)

            return result

        except Exception as e:
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Application health check failed: {str(e)}",
                details={"error": str(e), "error_type": type(e).__name__},
                timestamp=datetime.now(),
                check_duration=time.time() - start_time,
            )

            if self.logger:
                self.logger.log_health_check("application", result)

            return result

    def get_resource_status(self) -> ResourceStatus:
        """
        Get current resource usage status.

        Returns:
            ResourceStatus with current resource metrics
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage_mb = (memory.total - memory.available) / (1024 * 1024)
            memory_usage_percent = (memory_usage_mb / self._memory_limit_mb) * 100

            # Disk usage
            disk = psutil.disk_usage("/")
            disk_usage_mb = (disk.total - disk.free) / (1024 * 1024)
            disk_available_mb = disk.free / (1024 * 1024)
            disk_usage_percent = (disk.used / disk.total) * 100

            # Network connections
            network_connections = len(psutil.net_connections())

            # Load average
            load_avg = os.getloadavg()

            resource_status = ResourceStatus(
                cpu_usage_percent=round(cpu_percent, 2),
                memory_usage_mb=round(memory_usage_mb, 2),
                memory_limit_mb=round(self._memory_limit_mb, 2),
                memory_usage_percent=round(memory_usage_percent, 2),
                disk_usage_mb=round(disk_usage_mb, 2),
                disk_available_mb=round(disk_available_mb, 2),
                disk_usage_percent=round(disk_usage_percent, 2),
                network_connections=network_connections,
                load_average=load_avg,
            )

            # Update metrics
            if self.metrics:
                self.metrics.update_gauge("cpu_usage_percent", cpu_percent)
                self.metrics.update_gauge("memory_usage_mb", memory_usage_mb)
                self.metrics.update_gauge("memory_usage_percent", memory_usage_percent)
                self.metrics.update_gauge("disk_usage_percent", disk_usage_percent)
                self.metrics.update_gauge("network_connections", network_connections)
                self.metrics.update_gauge("load_average_1m", load_avg[0])
                self.metrics.update_gauge("load_average_5m", load_avg[1])
                self.metrics.update_gauge("load_average_15m", load_avg[2])

            return resource_status

        except Exception:
            # Return default values on error
            return ResourceStatus(
                cpu_usage_percent=0.0,
                memory_usage_mb=0.0,
                memory_limit_mb=self._memory_limit_mb,
                memory_usage_percent=0.0,
                disk_usage_mb=0.0,
                disk_available_mb=0.0,
                disk_usage_percent=0.0,
                network_connections=0,
                load_average=(0.0, 0.0, 0.0),
            )

    def comprehensive_health_check(self) -> dict[str, Any]:
        """
        Perform comprehensive health check of all components.

        Returns:
            Dictionary with complete health status
        """
        start_time = time.time()

        health_report = {
            "timestamp": datetime.now().isoformat() + "Z",
            "overall_status": HealthStatus.HEALTHY.value,
            "checks": {},
            "resource_status": {},
            "summary": {
                "total_checks": 0,
                "healthy_checks": 0,
                "degraded_checks": 0,
                "unhealthy_checks": 0,
            },
            "check_duration_ms": 0,
        }

        try:
            # Application health check
            app_health = self.check_application_health()
            health_report["checks"]["application"] = app_health.to_dict()

            # Database health checks
            for db_name in self.database_managers.keys():
                db_health = self.check_database_health(db_name)
                health_report["checks"][f"database_{db_name}"] = db_health.to_dict()

            # Resource status
            resource_status = self.get_resource_status()
            health_report["resource_status"] = resource_status.to_dict()

            # Calculate summary
            all_checks = list(health_report["checks"].values())
            health_report["summary"]["total_checks"] = len(all_checks)

            for check in all_checks:
                status = check["status"]
                if status == HealthStatus.HEALTHY.value:
                    health_report["summary"]["healthy_checks"] += 1
                elif status == HealthStatus.DEGRADED.value:
                    health_report["summary"]["degraded_checks"] += 1
                else:
                    health_report["summary"]["unhealthy_checks"] += 1

            # Determine overall status
            if health_report["summary"]["unhealthy_checks"] > 0:
                health_report["overall_status"] = HealthStatus.UNHEALTHY.value
            elif health_report["summary"]["degraded_checks"] > 0:
                health_report["overall_status"] = HealthStatus.DEGRADED.value
            else:
                health_report["overall_status"] = HealthStatus.HEALTHY.value

            # Update overall health metric
            if self.metrics:
                overall_healthy = (
                    1
                    if health_report["overall_status"] == HealthStatus.HEALTHY.value
                    else 0
                )
                self.metrics.update_gauge("overall_health_status", overall_healthy)
                self.metrics.increment_counter("health_checks_total")

            health_report["check_duration_ms"] = round(
                (time.time() - start_time) * 1000, 2
            )

            # Log comprehensive health check
            if self.logger:
                self.logger.log_metrics(
                    {
                        "event": "comprehensive_health_check",
                        "overall_status": health_report["overall_status"],
                        "summary": health_report["summary"],
                        "duration_ms": health_report["check_duration_ms"],
                    }
                )

            return health_report

        except Exception as e:
            health_report["overall_status"] = HealthStatus.UNHEALTHY.value
            health_report["error"] = str(e)
            health_report["check_duration_ms"] = round(
                (time.time() - start_time) * 1000, 2
            )

            if self.logger:
                self.logger.log_alert(
                    "health_check_error",
                    f"Comprehensive health check failed: {str(e)}",
                    "ERROR",
                )

            return health_report

    def get_health_endpoint_response(self) -> tuple[dict[str, Any], int]:
        """
        Get health endpoint response for load balancer integration.

        Returns:
            Tuple of (response_dict, http_status_code)
        """
        health_report = self.comprehensive_health_check()

        # Determine HTTP status code
        overall_status = health_report["overall_status"]
        if overall_status == HealthStatus.HEALTHY.value:
            status_code = 200
        elif overall_status == HealthStatus.DEGRADED.value:
            status_code = 200  # Still accepting traffic but with warnings
        else:
            status_code = 503  # Service unavailable

        # Create simplified response for load balancer
        response = {
            "status": overall_status,
            "timestamp": health_report["timestamp"],
            "checks": {
                name: check["status"] for name, check in health_report["checks"].items()
            },
        }

        return response, status_code

    def export_prometheus_metrics(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            String containing Prometheus-formatted metrics
        """
        if not self.metrics:
            return "# Prometheus metrics not enabled\n"

        # Update current metrics
        self.get_resource_status()
        self.comprehensive_health_check()

        return self.metrics.export_prometheus_format()

    def get_metrics_dict(self) -> dict[str, Any]:
        """
        Get metrics as dictionary for JSON export.

        Returns:
            Dictionary containing all metrics
        """
        if not self.metrics:
            return {"error": "Metrics not enabled"}

        # Update current metrics
        self.get_resource_status()

        return self.metrics.get_metrics_dict()
