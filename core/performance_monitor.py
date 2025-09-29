"""
Performance monitoring and optimization system for container environments.

This module provides comprehensive performance monitoring capabilities including
resource usage tracking, bottleneck detection, optimization recommendations,
connection pooling management, and performance benchmarking for container efficiency.
"""

import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import psutil

from core.database import DatabaseManager
from core.health_monitor import HealthMonitor, StructuredLogger


class PerformanceLevel(Enum):
    """Performance level enumeration."""

    OPTIMAL = "optimal"
    GOOD = "good"
    DEGRADED = "degraded"
    POOR = "poor"


@dataclass
class ResourceMetrics:
    """Resource usage metrics data structure."""

    timestamp: datetime
    cpu_usage_percent: float
    cpu_cores: int
    memory_usage_mb: float
    memory_limit_mb: float
    memory_usage_percent: float
    disk_usage_mb: float
    disk_available_mb: float
    disk_usage_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_bytes_sent: float
    network_bytes_recv: float
    network_connections: int
    load_average: tuple[float, float, float]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat() + "Z"
        result["load_average"] = list(self.load_average)
        return result


@dataclass
class DatabasePerformanceMetrics:
    """Database performance metrics data structure."""

    database_name: str
    connection_pool_size: int
    active_connections: int
    idle_connections: int
    connection_usage_percent: float
    avg_query_time_ms: float
    slow_queries_count: int
    deadlocks_count: int
    cache_hit_ratio: float
    transactions_per_second: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class PerformanceBottleneck:
    """Performance bottleneck identification."""

    component: str
    severity: str  # "critical", "high", "medium", "low"
    description: str
    current_value: float
    threshold_value: float
    impact: str
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation."""

    category: str  # "resource", "database", "application", "configuration"
    priority: str  # "critical", "high", "medium", "low"
    title: str
    description: str
    expected_impact: str
    implementation_effort: str  # "low", "medium", "high"
    actions: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class ConnectionPoolManager:
    """Manages database connection pooling optimization."""

    def __init__(self, database_managers: dict[str, DatabaseManager]):
        """
        Initialize connection pool manager.

        Args:
            database_managers: Dictionary of database managers to optimize
        """
        self.database_managers = database_managers
        self.logger = StructuredLogger("connection_pool_manager")
        self._pool_stats_cache = {}
        self._cache_ttl = 30  # seconds

    def get_pool_statistics(self, db_name: str) -> dict[str, Any]:
        """
        Get connection pool statistics for a database.

        Args:
            db_name: Name of the database

        Returns:
            Dictionary containing pool statistics
        """
        try:
            if db_name not in self.database_managers:
                return {"error": f"Database '{db_name}' not found"}

            db_manager = self.database_managers[db_name]
            engine = db_manager.db_engine

            # Get pool statistics
            pool = engine.pool
            pool_stats = {
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
            }

            # Calculate utilization
            total_capacity = pool_stats["pool_size"] + pool_stats["overflow"]
            active_connections = pool_stats["checked_out"]

            pool_stats.update(
                {
                    "total_capacity": total_capacity,
                    "active_connections": active_connections,
                    "utilization_percent": (
                        (active_connections / total_capacity * 100)
                        if total_capacity > 0
                        else 0
                    ),
                    "available_connections": total_capacity - active_connections,
                }
            )

            # Get database-level connection info
            try:
                db_connections = db_manager.execute_query(
                    """
                    SELECT
                        count(*) as total_connections,
                        count(CASE WHEN state = 'active' THEN 1 END) as active_db_connections,
                        count(CASE WHEN state = 'idle' THEN 1 END) as idle_db_connections,
                        count(CASE WHEN state = 'idle in transaction' THEN 1 END) as idle_in_transaction
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                """
                )

                if db_connections:
                    pool_stats.update(
                        {
                            "database_total_connections": db_connections[0][
                                "total_connections"
                            ],
                            "database_active_connections": db_connections[0][
                                "active_db_connections"
                            ],
                            "database_idle_connections": db_connections[0][
                                "idle_db_connections"
                            ],
                            "database_idle_in_transaction": db_connections[0][
                                "idle_in_transaction"
                            ],
                        }
                    )
            except Exception as e:
                pool_stats["database_query_error"] = str(e)

            return pool_stats

        except Exception as e:
            return {"error": f"Failed to get pool statistics: {str(e)}"}

    def optimize_pool_configuration(
        self, db_name: str, workload_pattern: str = "balanced"
    ) -> dict[str, Any]:
        """
        Optimize connection pool configuration based on workload patterns.

        Args:
            db_name: Name of the database
            workload_pattern: Type of workload ("read_heavy", "write_heavy", "balanced", "burst")

        Returns:
            Dictionary containing optimization recommendations
        """
        try:
            pool_stats = self.get_pool_statistics(db_name)

            if "error" in pool_stats:
                return pool_stats

            current_utilization = pool_stats.get("utilization_percent", 0)
            current_pool_size = pool_stats.get("pool_size", 0)

            recommendations = []

            # Analyze current utilization
            if current_utilization > 90:
                recommendations.append(
                    {
                        "type": "increase_pool_size",
                        "current_size": current_pool_size,
                        "recommended_size": min(current_pool_size + 5, 50),
                        "reason": "High pool utilization detected",
                    }
                )
            elif current_utilization < 20 and current_pool_size > 5:
                recommendations.append(
                    {
                        "type": "decrease_pool_size",
                        "current_size": current_pool_size,
                        "recommended_size": max(current_pool_size - 2, 5),
                        "reason": "Low pool utilization detected",
                    }
                )

            # Workload-specific recommendations
            workload_recommendations = self._get_workload_specific_recommendations(
                workload_pattern, pool_stats
            )
            recommendations.extend(workload_recommendations)

            return {
                "database": db_name,
                "workload_pattern": workload_pattern,
                "current_stats": pool_stats,
                "recommendations": recommendations,
                "optimization_timestamp": datetime.now().isoformat() + "Z",
            }

        except Exception as e:
            return {"error": f"Failed to optimize pool configuration: {str(e)}"}

    def _get_workload_specific_recommendations(
        self, workload_pattern: str, pool_stats: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Get workload-specific optimization recommendations."""
        recommendations = []

        if workload_pattern == "read_heavy":
            recommendations.append(
                {
                    "type": "read_optimization",
                    "suggestion": "Consider read replicas and connection pooling for read queries",
                    "pool_timeout": "Increase pool timeout for read operations",
                    "connection_lifetime": "Longer connection lifetime for stable read workloads",
                }
            )

        elif workload_pattern == "write_heavy":
            recommendations.append(
                {
                    "type": "write_optimization",
                    "suggestion": "Optimize for write throughput with smaller pool size",
                    "pool_timeout": "Shorter pool timeout to handle write contention",
                    "connection_lifetime": "Shorter connection lifetime to prevent lock buildup",
                }
            )

        elif workload_pattern == "burst":
            recommendations.append(
                {
                    "type": "burst_optimization",
                    "suggestion": "Configure overflow connections for burst handling",
                    "pool_timeout": "Aggressive timeout settings for burst scenarios",
                    "monitoring": "Enhanced monitoring for burst detection",
                }
            )

        return recommendations


class PerformanceMonitor:
    """
    Comprehensive performance monitoring and optimization system.

    Provides resource usage tracking, bottleneck detection, optimization
    recommendations, and performance benchmarking capabilities.
    """

    def __init__(
        self,
        database_managers: Optional[dict[str, DatabaseManager]] = None,
        health_monitor: Optional[HealthMonitor] = None,
        enable_detailed_monitoring: bool = True,
    ):
        """
        Initialize performance monitor.

        Args:
            database_managers: Dictionary of database managers to monitor
            health_monitor: Health monitor instance for integration
            enable_detailed_monitoring: Whether to enable detailed performance tracking
        """
        self.database_managers = database_managers or {}
        self.health_monitor = health_monitor
        self.enable_detailed_monitoring = enable_detailed_monitoring

        # Initialize components
        self.logger = StructuredLogger("performance_monitor")
        self.connection_pool_manager = ConnectionPoolManager(self.database_managers)

        # Performance tracking
        self._metrics_history = []
        self._max_history_size = 1000
        self._baseline_metrics = None

        # Thresholds for bottleneck detection
        self.thresholds = {
            "cpu_usage_percent": 80.0,
            "memory_usage_percent": 85.0,
            "disk_usage_percent": 90.0,
            "disk_io_mb_per_sec": 100.0,
            "network_mb_per_sec": 50.0,
            "connection_pool_utilization": 80.0,
            "avg_query_time_ms": 1000.0,
            "load_average_per_core": 2.0,
        }

        # Initialize baseline
        self._establish_baseline()

    def _establish_baseline(self):
        """Establish performance baseline for comparison."""
        try:
            baseline_metrics = self.collect_resource_metrics()
            self._baseline_metrics = baseline_metrics

            self.logger.log_metrics(
                {
                    "event": "baseline_established",
                    "baseline_metrics": baseline_metrics.to_dict(),
                }
            )

        except Exception as e:
            self.logger.log_alert(
                "baseline_error",
                f"Failed to establish performance baseline: {str(e)}",
                "WARNING",
            )

    def collect_resource_metrics(self) -> ResourceMetrics:
        """
        Collect comprehensive resource usage metrics.

        Returns:
            ResourceMetrics with current system resource usage
        """
        try:
            # CPU metrics - use shorter interval for faster collection
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_cores = psutil.cpu_count()

            # Memory metrics
            memory = psutil.virtual_memory()
            memory_usage_mb = (memory.total - memory.available) / (1024 * 1024)
            memory_limit_mb = self._get_memory_limit()
            memory_usage_percent = (memory_usage_mb / memory_limit_mb) * 100

            # Disk metrics
            disk = psutil.disk_usage("/")
            disk_usage_mb = (disk.total - disk.free) / (1024 * 1024)
            disk_available_mb = disk.free / (1024 * 1024)
            disk_usage_percent = (disk.used / disk.total) * 100

            # Disk I/O metrics - handle potential permission issues
            try:
                disk_io = psutil.disk_io_counters()
                disk_io_read_mb = disk_io.read_bytes / (1024 * 1024) if disk_io else 0
                disk_io_write_mb = disk_io.write_bytes / (1024 * 1024) if disk_io else 0
            except (PermissionError, AttributeError):
                disk_io_read_mb = 0.0
                disk_io_write_mb = 0.0

            # Network metrics - handle potential permission issues
            try:
                network_io = psutil.net_io_counters()
                network_bytes_sent = network_io.bytes_sent if network_io else 0
                network_bytes_recv = network_io.bytes_recv if network_io else 0
            except (PermissionError, AttributeError):
                network_bytes_sent = 0.0
                network_bytes_recv = 0.0

            # Network connections - handle potential permission issues
            try:
                network_connections = len(psutil.net_connections())
            except (PermissionError, AttributeError):
                network_connections = 0

            # Load average
            try:
                load_avg = os.getloadavg()
            except (OSError, AttributeError):
                load_avg = (0.0, 0.0, 0.0)

            return ResourceMetrics(
                timestamp=datetime.now(),
                cpu_usage_percent=round(cpu_percent, 2),
                cpu_cores=cpu_cores,
                memory_usage_mb=round(memory_usage_mb, 2),
                memory_limit_mb=round(memory_limit_mb, 2),
                memory_usage_percent=round(memory_usage_percent, 2),
                disk_usage_mb=round(disk_usage_mb, 2),
                disk_available_mb=round(disk_available_mb, 2),
                disk_usage_percent=round(disk_usage_percent, 2),
                disk_io_read_mb=round(disk_io_read_mb, 2),
                disk_io_write_mb=round(disk_io_write_mb, 2),
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                network_connections=network_connections,
                load_average=load_avg,
            )

        except Exception as e:
            self.logger.log_alert(
                "metrics_collection_error",
                f"Failed to collect resource metrics: {str(e)}",
                "ERROR",
            )
            # Return default metrics on error
            return ResourceMetrics(
                timestamp=datetime.now(),
                cpu_usage_percent=0.0,
                cpu_cores=1,
                memory_usage_mb=0.0,
                memory_limit_mb=1024.0,
                memory_usage_percent=0.0,
                disk_usage_mb=0.0,
                disk_available_mb=0.0,
                disk_usage_percent=0.0,
                disk_io_read_mb=0.0,
                disk_io_write_mb=0.0,
                network_bytes_sent=0.0,
                network_bytes_recv=0.0,
                network_connections=0,
                load_average=(0.0, 0.0, 0.0),
            )

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

    def collect_database_performance_metrics(
        self, db_name: str
    ) -> DatabasePerformanceMetrics:
        """
        Collect database-specific performance metrics.

        Args:
            db_name: Name of the database to monitor

        Returns:
            DatabasePerformanceMetrics with database performance data
        """
        try:
            if db_name not in self.database_managers:
                raise ValueError(f"Database '{db_name}' not found in managers")

            db_manager = self.database_managers[db_name]

            # Get connection pool statistics
            pool_stats = self.connection_pool_manager.get_pool_statistics(db_name)

            # Get database performance metrics
            perf_query = """
            SELECT
                (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections,
                (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as total_connections,
                (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND state = 'active') as active_connections,
                (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND state = 'idle') as idle_connections,
                (SELECT COALESCE(avg(query_time_ms), 0) FROM (
                    SELECT EXTRACT(EPOCH FROM (now() - query_start)) * 1000 as query_time_ms
                    FROM pg_stat_activity
                    WHERE datname = current_database() AND state = 'active' AND query_start IS NOT NULL
                ) q) as avg_query_time_ms,
                (SELECT count(*) FROM pg_stat_activity
                 WHERE datname = current_database() AND state = 'active'
                 AND EXTRACT(EPOCH FROM (now() - query_start)) > 30) as slow_queries_count
            """

            perf_results = db_manager.execute_query(perf_query)

            if perf_results:
                result = perf_results[0]

                # Calculate connection usage percentage
                max_connections = result.get("max_connections", 100)
                total_connections = result.get("total_connections", 0)
                connection_usage_percent = (
                    (total_connections / max_connections * 100)
                    if max_connections > 0
                    else 0
                )

                # Get additional statistics
                stats_query = """
                SELECT
                    COALESCE(deadlocks, 0) as deadlocks_count,
                    COALESCE(blks_hit::float / NULLIF(blks_hit + blks_read, 0) * 100, 0) as cache_hit_ratio,
                    COALESCE(xact_commit + xact_rollback, 0) as total_transactions
                FROM pg_stat_database
                WHERE datname = current_database()
                """

                stats_results = db_manager.execute_query(stats_query)
                stats = stats_results[0] if stats_results else {}

                return DatabasePerformanceMetrics(
                    database_name=db_name,
                    connection_pool_size=pool_stats.get("pool_size", 0),
                    active_connections=result.get("active_connections", 0),
                    idle_connections=result.get("idle_connections", 0),
                    connection_usage_percent=round(connection_usage_percent, 2),
                    avg_query_time_ms=round(result.get("avg_query_time_ms", 0), 2),
                    slow_queries_count=result.get("slow_queries_count", 0),
                    deadlocks_count=stats.get("deadlocks_count", 0),
                    cache_hit_ratio=round(stats.get("cache_hit_ratio", 0), 2),
                    transactions_per_second=0.0,  # Would need time-based calculation
                )

        except Exception as e:
            self.logger.log_alert(
                "database_metrics_error",
                f"Failed to collect database metrics for '{db_name}': {str(e)}",
                "ERROR",
            )

            # Return default metrics on error
            return DatabasePerformanceMetrics(
                database_name=db_name,
                connection_pool_size=0,
                active_connections=0,
                idle_connections=0,
                connection_usage_percent=0.0,
                avg_query_time_ms=0.0,
                slow_queries_count=0,
                deadlocks_count=0,
                cache_hit_ratio=0.0,
                transactions_per_second=0.0,
            )

    def detect_performance_bottlenecks(self) -> list[PerformanceBottleneck]:
        """
        Detect performance bottlenecks based on current metrics.

        Returns:
            List of identified performance bottlenecks
        """
        bottlenecks = []

        try:
            # Collect current metrics
            resource_metrics = self.collect_resource_metrics()

            # CPU bottleneck detection
            if (
                resource_metrics.cpu_usage_percent
                > self.thresholds["cpu_usage_percent"]
            ):
                severity = (
                    "critical" if resource_metrics.cpu_usage_percent > 95 else "high"
                )
                bottlenecks.append(
                    PerformanceBottleneck(
                        component="cpu",
                        severity=severity,
                        description=f"High CPU usage detected: {resource_metrics.cpu_usage_percent}%",
                        current_value=resource_metrics.cpu_usage_percent,
                        threshold_value=self.thresholds["cpu_usage_percent"],
                        impact="Application response time degradation, potential request queuing",
                        recommendations=[
                            "Scale horizontally by adding more container instances",
                            "Optimize CPU-intensive operations and algorithms",
                            "Review and optimize database queries",
                            "Consider CPU resource limits adjustment",
                        ],
                    )
                )

            # Memory bottleneck detection
            if (
                resource_metrics.memory_usage_percent
                > self.thresholds["memory_usage_percent"]
            ):
                severity = (
                    "critical" if resource_metrics.memory_usage_percent > 95 else "high"
                )
                bottlenecks.append(
                    PerformanceBottleneck(
                        component="memory",
                        severity=severity,
                        description=f"High memory usage detected: {resource_metrics.memory_usage_percent}%",
                        current_value=resource_metrics.memory_usage_percent,
                        threshold_value=self.thresholds["memory_usage_percent"],
                        impact="Risk of OOM kills, garbage collection pressure, performance degradation",
                        recommendations=[
                            "Increase container memory limits",
                            "Optimize memory usage in application code",
                            "Review connection pool sizes",
                            "Implement memory leak detection and monitoring",
                        ],
                    )
                )

            # Disk usage bottleneck detection
            if (
                resource_metrics.disk_usage_percent
                > self.thresholds["disk_usage_percent"]
            ):
                severity = (
                    "critical" if resource_metrics.disk_usage_percent > 95 else "high"
                )
                bottlenecks.append(
                    PerformanceBottleneck(
                        component="disk_space",
                        severity=severity,
                        description=f"High disk usage detected: {resource_metrics.disk_usage_percent}%",
                        current_value=resource_metrics.disk_usage_percent,
                        threshold_value=self.thresholds["disk_usage_percent"],
                        impact="Risk of application failures, log rotation issues, database growth problems",
                        recommendations=[
                            "Implement log rotation and cleanup policies",
                            "Archive or delete old data",
                            "Increase disk space allocation",
                            "Monitor disk growth trends",
                        ],
                    )
                )

            # Load average bottleneck detection
            load_per_core = (
                resource_metrics.load_average[0] / resource_metrics.cpu_cores
            )
            if load_per_core > self.thresholds["load_average_per_core"]:
                severity = "high" if load_per_core > 3.0 else "medium"
                bottlenecks.append(
                    PerformanceBottleneck(
                        component="system_load",
                        severity=severity,
                        description=f"High system load detected: {load_per_core:.2f} per core",
                        current_value=load_per_core,
                        threshold_value=self.thresholds["load_average_per_core"],
                        impact="System responsiveness degradation, increased latency",
                        recommendations=[
                            "Investigate processes causing high load",
                            "Optimize I/O operations",
                            "Consider load balancing across multiple instances",
                            "Review system resource allocation",
                        ],
                    )
                )

            # Database bottleneck detection
            for db_name in self.database_managers.keys():
                db_metrics = self.collect_database_performance_metrics(db_name)

                # Connection pool utilization
                pool_utilization = self.connection_pool_manager.get_pool_statistics(
                    db_name
                ).get("utilization_percent", 0)
                if pool_utilization > self.thresholds["connection_pool_utilization"]:
                    severity = "critical" if pool_utilization > 95 else "high"
                    bottlenecks.append(
                        PerformanceBottleneck(
                            component=f"database_pool_{db_name}",
                            severity=severity,
                            description=f"High connection pool utilization for {db_name}: {pool_utilization}%",
                            current_value=pool_utilization,
                            threshold_value=self.thresholds[
                                "connection_pool_utilization"
                            ],
                            impact="Connection timeouts, request queuing, application blocking",
                            recommendations=[
                                "Increase connection pool size",
                                "Optimize query performance to reduce connection hold time",
                                "Implement connection pooling best practices",
                                "Review connection timeout settings",
                            ],
                        )
                    )

                # Query performance
                if db_metrics.avg_query_time_ms > self.thresholds["avg_query_time_ms"]:
                    severity = (
                        "high" if db_metrics.avg_query_time_ms > 5000 else "medium"
                    )
                    bottlenecks.append(
                        PerformanceBottleneck(
                            component=f"database_queries_{db_name}",
                            severity=severity,
                            description=f"Slow query performance for {db_name}: {db_metrics.avg_query_time_ms}ms avg",
                            current_value=db_metrics.avg_query_time_ms,
                            threshold_value=self.thresholds["avg_query_time_ms"],
                            impact="Increased response times, connection pool exhaustion, user experience degradation",
                            recommendations=[
                                "Analyze and optimize slow queries",
                                "Add appropriate database indexes",
                                "Review query execution plans",
                                "Consider query result caching",
                            ],
                        )
                    )

            # Log bottleneck detection results
            if bottlenecks:
                self.logger.log_alert(
                    "performance_bottlenecks_detected",
                    f"Detected {len(bottlenecks)} performance bottlenecks",
                    "WARNING",
                )

                for bottleneck in bottlenecks:
                    self.logger.log_metrics(
                        {
                            "event": "bottleneck_detected",
                            "bottleneck": bottleneck.to_dict(),
                        }
                    )

            return bottlenecks

        except Exception as e:
            self.logger.log_alert(
                "bottleneck_detection_error",
                f"Failed to detect performance bottlenecks: {str(e)}",
                "ERROR",
            )
            return []

    def generate_optimization_recommendations(
        self, bottlenecks: Optional[list[PerformanceBottleneck]] = None
    ) -> list[OptimizationRecommendation]:
        """
        Generate optimization recommendations based on performance analysis.

        Args:
            bottlenecks: Optional list of bottlenecks to base recommendations on

        Returns:
            List of optimization recommendations
        """
        if bottlenecks is None:
            bottlenecks = self.detect_performance_bottlenecks()

        recommendations = []

        try:
            # Collect current metrics for analysis
            resource_metrics = self.collect_resource_metrics()

            # Resource-based recommendations
            if resource_metrics.memory_usage_percent > 70:
                recommendations.append(
                    OptimizationRecommendation(
                        category="resource",
                        priority=(
                            "high"
                            if resource_metrics.memory_usage_percent > 85
                            else "medium"
                        ),
                        title="Memory Usage Optimization",
                        description="High memory usage detected, optimization recommended",
                        expected_impact="Reduced memory pressure, improved stability, better performance",
                        implementation_effort="medium",
                        actions=[
                            "Review and optimize memory-intensive operations",
                            "Implement object pooling for frequently used objects",
                            "Optimize database connection pool sizes",
                            "Add memory monitoring and alerting",
                            "Consider increasing container memory limits",
                        ],
                    )
                )

            if resource_metrics.cpu_usage_percent > 60:
                recommendations.append(
                    OptimizationRecommendation(
                        category="resource",
                        priority=(
                            "high"
                            if resource_metrics.cpu_usage_percent > 80
                            else "medium"
                        ),
                        title="CPU Usage Optimization",
                        description="Elevated CPU usage detected, optimization opportunities available",
                        expected_impact="Improved response times, better throughput, reduced latency",
                        implementation_effort="medium",
                        actions=[
                            "Profile application to identify CPU hotspots",
                            "Optimize algorithms and data structures",
                            "Implement asynchronous processing where appropriate",
                            "Consider horizontal scaling",
                            "Review and optimize database queries",
                        ],
                    )
                )

            # Database-specific recommendations
            for db_name in self.database_managers.keys():
                db_metrics = self.collect_database_performance_metrics(db_name)
                pool_stats = self.connection_pool_manager.get_pool_statistics(db_name)

                if db_metrics.avg_query_time_ms > 500:
                    recommendations.append(
                        OptimizationRecommendation(
                            category="database",
                            priority=(
                                "high"
                                if db_metrics.avg_query_time_ms > 2000
                                else "medium"
                            ),
                            title=f"Database Query Optimization - {db_name}",
                            description=f"Slow query performance detected (avg: {db_metrics.avg_query_time_ms}ms)",
                            expected_impact="Faster query execution, reduced connection hold time, improved throughput",
                            implementation_effort="medium",
                            actions=[
                                "Identify and optimize slow queries using EXPLAIN ANALYZE",
                                "Add missing database indexes",
                                "Review query patterns and optimize joins",
                                "Implement query result caching",
                                "Consider database-specific optimizations",
                            ],
                        )
                    )

                if pool_stats.get("utilization_percent", 0) > 60:
                    recommendations.append(
                        OptimizationRecommendation(
                            category="database",
                            priority="medium",
                            title=f"Connection Pool Optimization - {db_name}",
                            description=f"Connection pool utilization at {pool_stats.get('utilization_percent', 0)}%",
                            expected_impact="Better connection management, reduced timeouts, improved scalability",
                            implementation_effort="low",
                            actions=[
                                "Review and adjust connection pool size",
                                "Optimize connection timeout settings",
                                "Implement connection health checks",
                                "Monitor connection pool metrics",
                                "Consider connection pooling strategies",
                            ],
                        )
                    )

            # Configuration-based recommendations
            if resource_metrics.load_average[0] / resource_metrics.cpu_cores > 1.5:
                recommendations.append(
                    OptimizationRecommendation(
                        category="configuration",
                        priority="medium",
                        title="System Load Optimization",
                        description="High system load detected, configuration tuning recommended",
                        expected_impact="Better system responsiveness, improved stability",
                        implementation_effort="low",
                        actions=[
                            "Review container resource limits",
                            "Optimize I/O operations and patterns",
                            "Implement proper error handling and retries",
                            "Consider load balancing strategies",
                            "Monitor system metrics continuously",
                        ],
                    )
                )

            # Application-level recommendations
            if len(bottlenecks) > 3:
                recommendations.append(
                    OptimizationRecommendation(
                        category="application",
                        priority="high",
                        title="Comprehensive Performance Review",
                        description="Multiple performance bottlenecks detected, comprehensive review needed",
                        expected_impact="Overall performance improvement, better user experience",
                        implementation_effort="high",
                        actions=[
                            "Conduct comprehensive performance profiling",
                            "Review application architecture for optimization opportunities",
                            "Implement performance monitoring and alerting",
                            "Establish performance baselines and SLAs",
                            "Create performance optimization roadmap",
                        ],
                    )
                )

            # Sort recommendations by priority
            priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            recommendations.sort(key=lambda x: priority_order.get(x.priority, 3))

            # Log recommendations
            self.logger.log_metrics(
                {
                    "event": "optimization_recommendations_generated",
                    "recommendations_count": len(recommendations),
                    "recommendations": [rec.to_dict() for rec in recommendations],
                }
            )

            return recommendations

        except Exception as e:
            self.logger.log_alert(
                "recommendation_generation_error",
                f"Failed to generate optimization recommendations: {str(e)}",
                "ERROR",
            )
            return []

    def optimize_resource_allocation(
        self, workload_pattern: str = "balanced"
    ) -> dict[str, Any]:
        """
        Optimize resource allocation based on workload patterns.

        Args:
            workload_pattern: Type of workload pattern to optimize for

        Returns:
            Dictionary containing optimization results and recommendations
        """
        try:
            current_metrics = self.collect_resource_metrics()
            bottlenecks = self.detect_performance_bottlenecks()

            optimization_results = {
                "timestamp": datetime.now().isoformat() + "Z",
                "workload_pattern": workload_pattern,
                "current_metrics": current_metrics.to_dict(),
                "bottlenecks": [b.to_dict() for b in bottlenecks],
                "resource_optimizations": {},
                "database_optimizations": {},
                "recommendations": [],
            }

            # Resource allocation optimizations
            resource_opts = self._optimize_resource_allocation(
                current_metrics, workload_pattern
            )
            optimization_results["resource_optimizations"] = resource_opts

            # Database connection pool optimizations
            db_opts = {}
            for db_name in self.database_managers.keys():
                db_opt = self.connection_pool_manager.optimize_pool_configuration(
                    db_name, workload_pattern
                )
                db_opts[db_name] = db_opt
            optimization_results["database_optimizations"] = db_opts

            # Generate comprehensive recommendations
            recommendations = self.generate_optimization_recommendations(bottlenecks)
            optimization_results["recommendations"] = [
                rec.to_dict() for rec in recommendations
            ]

            # Log optimization results
            self.logger.log_metrics(
                {
                    "event": "resource_allocation_optimized",
                    "workload_pattern": workload_pattern,
                    "optimizations_applied": len(resource_opts),
                    "recommendations_generated": len(recommendations),
                }
            )

            return optimization_results

        except Exception as e:
            self.logger.log_alert(
                "resource_optimization_error",
                f"Failed to optimize resource allocation: {str(e)}",
                "ERROR",
            )
            return {"error": str(e)}

    def _optimize_resource_allocation(
        self, metrics: ResourceMetrics, workload_pattern: str
    ) -> dict[str, Any]:
        """Optimize resource allocation based on current metrics and workload pattern."""
        optimizations = {}

        # Memory optimization
        if metrics.memory_usage_percent > 80:
            optimizations["memory"] = {
                "current_usage_percent": metrics.memory_usage_percent,
                "recommended_action": "increase_limit",
                "suggested_limit_mb": int(metrics.memory_limit_mb * 1.3),
                "reason": "High memory usage detected",
            }
        elif metrics.memory_usage_percent < 30:
            optimizations["memory"] = {
                "current_usage_percent": metrics.memory_usage_percent,
                "recommended_action": "decrease_limit",
                "suggested_limit_mb": int(metrics.memory_limit_mb * 0.8),
                "reason": "Low memory usage detected",
            }

        # CPU optimization based on workload pattern
        if workload_pattern == "cpu_intensive":
            optimizations["cpu"] = {
                "current_usage_percent": metrics.cpu_usage_percent,
                "recommended_action": "increase_cpu_allocation",
                "suggested_cpu_cores": metrics.cpu_cores + 1,
                "reason": "CPU-intensive workload pattern",
            }
        elif workload_pattern == "io_intensive":
            optimizations["cpu"] = {
                "current_usage_percent": metrics.cpu_usage_percent,
                "recommended_action": "optimize_io_operations",
                "suggested_actions": [
                    "async_io",
                    "batch_operations",
                    "connection_pooling",
                ],
                "reason": "I/O-intensive workload pattern",
            }

        return optimizations

    def run_performance_benchmark(self, duration_seconds: int = 60) -> dict[str, Any]:
        """
        Run performance benchmark to establish baseline and measure efficiency.

        Args:
            duration_seconds: Duration of benchmark in seconds

        Returns:
            Dictionary containing benchmark results
        """
        try:
            benchmark_results = {
                "start_time": datetime.now().isoformat() + "Z",
                "duration_seconds": duration_seconds,
                "metrics_samples": [],
                "database_performance": {},
                "performance_summary": {},
                "efficiency_score": 0.0,
            }

            self.logger.log_metrics(
                {
                    "event": "performance_benchmark_started",
                    "duration_seconds": duration_seconds,
                }
            )

            # Collect baseline metrics
            start_time = time.time()
            sample_interval = min(5, duration_seconds // 10)  # At least 10 samples

            while time.time() - start_time < duration_seconds:
                # Collect resource metrics
                metrics = self.collect_resource_metrics()
                benchmark_results["metrics_samples"].append(metrics.to_dict())

                # Collect database metrics
                for db_name in self.database_managers.keys():
                    if db_name not in benchmark_results["database_performance"]:
                        benchmark_results["database_performance"][db_name] = []

                    db_metrics = self.collect_database_performance_metrics(db_name)
                    benchmark_results["database_performance"][db_name].append(
                        db_metrics.to_dict()
                    )

                time.sleep(sample_interval)

            # Calculate performance summary
            benchmark_results["performance_summary"] = (
                self._calculate_benchmark_summary(
                    benchmark_results["metrics_samples"],
                    benchmark_results["database_performance"],
                )
            )

            # Calculate efficiency score
            benchmark_results["efficiency_score"] = self._calculate_efficiency_score(
                benchmark_results["performance_summary"]
            )

            benchmark_results["end_time"] = datetime.now().isoformat() + "Z"

            self.logger.log_metrics(
                {
                    "event": "performance_benchmark_completed",
                    "duration_seconds": duration_seconds,
                    "samples_collected": len(benchmark_results["metrics_samples"]),
                    "efficiency_score": benchmark_results["efficiency_score"],
                }
            )

            return benchmark_results

        except Exception as e:
            self.logger.log_alert(
                "benchmark_error", f"Performance benchmark failed: {str(e)}", "ERROR"
            )
            return {"error": str(e)}

    def _calculate_benchmark_summary(
        self, metrics_samples: list[dict], db_performance: dict
    ) -> dict[str, Any]:
        """Calculate summary statistics from benchmark samples."""
        if not metrics_samples:
            return {}

        # Resource metrics summary
        cpu_values = [sample["cpu_usage_percent"] for sample in metrics_samples]
        memory_values = [sample["memory_usage_percent"] for sample in metrics_samples]
        disk_values = [sample["disk_usage_percent"] for sample in metrics_samples]

        resource_summary = {
            "cpu": {
                "avg": sum(cpu_values) / len(cpu_values),
                "min": min(cpu_values),
                "max": max(cpu_values),
                "std_dev": self._calculate_std_dev(cpu_values),
            },
            "memory": {
                "avg": sum(memory_values) / len(memory_values),
                "min": min(memory_values),
                "max": max(memory_values),
                "std_dev": self._calculate_std_dev(memory_values),
            },
            "disk": {
                "avg": sum(disk_values) / len(disk_values),
                "min": min(disk_values),
                "max": max(disk_values),
                "std_dev": self._calculate_std_dev(disk_values),
            },
        }

        # Database performance summary
        db_summary = {}
        for db_name, db_samples in db_performance.items():
            if db_samples:
                query_times = [sample["avg_query_time_ms"] for sample in db_samples]
                connection_usage = [
                    sample["connection_usage_percent"] for sample in db_samples
                ]

                db_summary[db_name] = {
                    "avg_query_time_ms": {
                        "avg": sum(query_times) / len(query_times),
                        "min": min(query_times),
                        "max": max(query_times),
                    },
                    "connection_usage_percent": {
                        "avg": sum(connection_usage) / len(connection_usage),
                        "min": min(connection_usage),
                        "max": max(connection_usage),
                    },
                }

        return {
            "resource_metrics": resource_summary,
            "database_metrics": db_summary,
            "sample_count": len(metrics_samples),
        }

    def _calculate_std_dev(self, values: list[float]) -> float:
        """Calculate standard deviation of values."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance**0.5

    def _calculate_efficiency_score(self, performance_summary: dict) -> float:
        """Calculate overall efficiency score based on performance metrics."""
        try:
            resource_metrics = performance_summary.get("resource_metrics", {})

            # Base efficiency on resource utilization and stability
            cpu_avg = resource_metrics.get("cpu", {}).get("avg", 0)
            memory_avg = resource_metrics.get("memory", {}).get("avg", 0)

            cpu_std = resource_metrics.get("cpu", {}).get("std_dev", 0)
            memory_std = resource_metrics.get("memory", {}).get("std_dev", 0)

            # Efficiency score calculation (0-100)
            # Optimal utilization: 60-80% CPU, 70-85% memory
            # Lower standard deviation indicates better stability

            cpu_efficiency = 100 - abs(70 - cpu_avg) - (cpu_std * 2)
            memory_efficiency = 100 - abs(77.5 - memory_avg) - (memory_std * 2)

            # Stability bonus for low standard deviation
            stability_bonus = max(0, 20 - (cpu_std + memory_std))

            overall_efficiency = (
                cpu_efficiency + memory_efficiency + stability_bonus
            ) / 3

            return max(0, min(100, overall_efficiency))

        except Exception:
            return 0.0

    def get_performance_report(self) -> dict[str, Any]:
        """
        Generate comprehensive performance report.

        Returns:
            Dictionary containing complete performance analysis
        """
        try:
            report = {
                "timestamp": datetime.now().isoformat() + "Z",
                "resource_metrics": {},
                "database_metrics": {},
                "bottlenecks": [],
                "recommendations": [],
                "performance_level": PerformanceLevel.GOOD.value,
                "efficiency_score": 0.0,
                "summary": {},
            }

            # Collect current metrics
            resource_metrics = self.collect_resource_metrics()
            report["resource_metrics"] = resource_metrics.to_dict()

            # Collect database metrics
            for db_name in self.database_managers.keys():
                db_metrics = self.collect_database_performance_metrics(db_name)
                report["database_metrics"][db_name] = db_metrics.to_dict()

            # Detect bottlenecks
            bottlenecks = self.detect_performance_bottlenecks()
            report["bottlenecks"] = [b.to_dict() for b in bottlenecks]

            # Generate recommendations
            recommendations = self.generate_optimization_recommendations(bottlenecks)
            report["recommendations"] = [rec.to_dict() for rec in recommendations]

            # Determine performance level
            report["performance_level"] = self._determine_performance_level(
                resource_metrics, bottlenecks
            ).value

            # Calculate efficiency score
            if self._baseline_metrics:
                report["efficiency_score"] = self._calculate_current_efficiency_score(
                    resource_metrics, self._baseline_metrics
                )

            # Generate summary
            report["summary"] = {
                "total_bottlenecks": len(bottlenecks),
                "critical_bottlenecks": len(
                    [b for b in bottlenecks if b.severity == "critical"]
                ),
                "high_priority_recommendations": len(
                    [r for r in recommendations if r.priority == "high"]
                ),
                "overall_health": "good" if len(bottlenecks) < 3 else "needs_attention",
            }

            # Log performance report
            self.logger.log_metrics(
                {
                    "event": "performance_report_generated",
                    "performance_level": report["performance_level"],
                    "bottlenecks_count": len(bottlenecks),
                    "recommendations_count": len(recommendations),
                    "efficiency_score": report["efficiency_score"],
                }
            )

            return report

        except Exception as e:
            self.logger.log_alert(
                "performance_report_error",
                f"Failed to generate performance report: {str(e)}",
                "ERROR",
            )
            return {"error": str(e)}

    def _determine_performance_level(
        self, metrics: ResourceMetrics, bottlenecks: list[PerformanceBottleneck]
    ) -> PerformanceLevel:
        """Determine overall performance level based on metrics and bottlenecks."""
        critical_bottlenecks = [b for b in bottlenecks if b.severity == "critical"]
        high_bottlenecks = [b for b in bottlenecks if b.severity == "high"]

        if critical_bottlenecks:
            return PerformanceLevel.POOR
        elif len(high_bottlenecks) > 2:
            return PerformanceLevel.DEGRADED
        elif metrics.cpu_usage_percent < 60 and metrics.memory_usage_percent < 70:
            return PerformanceLevel.OPTIMAL
        else:
            return PerformanceLevel.GOOD

    def _calculate_current_efficiency_score(
        self, current: ResourceMetrics, baseline: ResourceMetrics
    ) -> float:
        """Calculate efficiency score compared to baseline."""
        try:
            # Compare current metrics to baseline
            cpu_ratio = current.cpu_usage_percent / max(baseline.cpu_usage_percent, 1)
            memory_ratio = current.memory_usage_percent / max(
                baseline.memory_usage_percent, 1
            )

            # Efficiency improves when ratios are close to 1.0
            cpu_efficiency = 100 - abs(1.0 - cpu_ratio) * 50
            memory_efficiency = 100 - abs(1.0 - memory_ratio) * 50

            return (cpu_efficiency + memory_efficiency) / 2

        except Exception:
            return 50.0  # Default neutral score
