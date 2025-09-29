"""
Example demonstrating the comprehensive health monitoring system.

This example shows how to set up and use the health monitoring system
with database health checks, resource monitoring, Prometheus metrics,
and HTTP endpoints for load balancer integration.
"""

import logging
import os
import time
from datetime import datetime

from core.database import DatabaseManager
from core.health_monitor import HealthMonitor, HealthStatus
from core.health_server import create_health_server


def setup_logging():
    """Set up structured logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",  # Use raw format for structured JSON logs
    )


def create_health_monitor_with_databases():
    """Create a health monitor with configured database managers."""
    database_managers = {}

    # Add RPA database if configured
    if os.getenv("CONTAINER_DATABASE_RPA_DB_HOST"):
        try:
            print("Initializing RPA database manager...")
            rpa_db = DatabaseManager("rpa_db")
            database_managers["rpa_db"] = rpa_db
            print("✓ RPA database manager initialized")
        except Exception as e:
            print(f"⚠ Could not initialize RPA database: {e}")

    # Add SurveyHub database if configured
    if os.getenv("CONTAINER_DATABASE_SURVEYHUB_HOST"):
        try:
            print("Initializing SurveyHub database manager...")
            survey_db = DatabaseManager("SurveyHub")
            database_managers["SurveyHub"] = survey_db
            print("✓ SurveyHub database manager initialized")
        except Exception as e:
            print(f"⚠ Could not initialize SurveyHub database: {e}")

    if not database_managers:
        print("⚠ No database managers configured - using mock setup for demo")

    # Create health monitor
    health_monitor = HealthMonitor(
        database_managers=database_managers,
        enable_prometheus=True,
        enable_structured_logging=True,
    )

    print(f"✓ Health monitor created with {len(database_managers)} database(s)")
    return health_monitor


def demonstrate_health_checks(health_monitor):
    """Demonstrate various health check capabilities."""
    print("\n" + "=" * 60)
    print("HEALTH CHECK DEMONSTRATIONS")
    print("=" * 60)

    # 1. Database health checks
    print("\n1. Database Health Checks:")
    print("-" * 30)

    for db_name in health_monitor.database_managers.keys():
        print(f"\nChecking database: {db_name}")
        result = health_monitor.check_database_health(db_name)

        status_emoji = {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.DEGRADED: "⚠️",
            HealthStatus.UNHEALTHY: "❌",
        }

        print(f"  Status: {status_emoji[result.status]} {result.status.value}")
        print(f"  Message: {result.message}")
        print(f"  Duration: {result.check_duration:.3f}s")

        if "response_time_ms" in result.details:
            print(f"  Response Time: {result.details['response_time_ms']:.2f}ms")

    # 2. Application health check
    print("\n2. Application Health Check:")
    print("-" * 30)

    app_result = health_monitor.check_application_health()
    status_emoji = {
        HealthStatus.HEALTHY: "✅",
        HealthStatus.DEGRADED: "⚠️",
        HealthStatus.UNHEALTHY: "❌",
    }

    print(f"  Status: {status_emoji[app_result.status]} {app_result.status.value}")
    print(f"  Message: {app_result.message}")
    print(f"  Duration: {app_result.check_duration:.3f}s")

    if app_result.details.get("issues"):
        print("  Issues found:")
        for issue in app_result.details["issues"]:
            print(f"    - {issue}")

    # 3. Resource monitoring
    print("\n3. Resource Status:")
    print("-" * 30)

    resource_status = health_monitor.get_resource_status()
    print(f"  CPU Usage: {resource_status.cpu_usage_percent:.1f}%")
    print(
        f"  Memory Usage: {resource_status.memory_usage_mb:.1f}MB / {resource_status.memory_limit_mb:.1f}MB ({resource_status.memory_usage_percent:.1f}%)"
    )
    print(f"  Disk Usage: {resource_status.disk_usage_percent:.1f}%")
    print(f"  Network Connections: {resource_status.network_connections}")
    print(
        f"  Load Average: {resource_status.load_average[0]:.2f}, {resource_status.load_average[1]:.2f}, {resource_status.load_average[2]:.2f}"
    )

    # 4. Comprehensive health check
    print("\n4. Comprehensive Health Check:")
    print("-" * 30)

    health_report = health_monitor.comprehensive_health_check()

    overall_emoji = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌"}

    print(
        f"  Overall Status: {overall_emoji[health_report['overall_status']]} {health_report['overall_status']}"
    )
    print(f"  Total Checks: {health_report['summary']['total_checks']}")
    print(f"  Healthy: {health_report['summary']['healthy_checks']}")
    print(f"  Degraded: {health_report['summary']['degraded_checks']}")
    print(f"  Unhealthy: {health_report['summary']['unhealthy_checks']}")
    print(f"  Check Duration: {health_report['check_duration_ms']:.2f}ms")


def demonstrate_prometheus_metrics(health_monitor):
    """Demonstrate Prometheus metrics export."""
    print("\n" + "=" * 60)
    print("PROMETHEUS METRICS DEMONSTRATION")
    print("=" * 60)

    # Update metrics by running health checks
    health_monitor.comprehensive_health_check()

    # Export Prometheus format
    prometheus_output = health_monitor.export_prometheus_metrics()

    print("\nPrometheus Metrics Output:")
    print("-" * 30)
    print(
        prometheus_output[:500] + "..."
        if len(prometheus_output) > 500
        else prometheus_output
    )

    # Get metrics as dictionary
    metrics_dict = health_monitor.get_metrics_dict()

    print("\nMetrics Summary:")
    print(f"  Total Metrics: {metrics_dict.get('total_metrics', 0)}")
    print(f"  Last Update: {metrics_dict.get('last_update', 'N/A')}")


def demonstrate_health_endpoints(health_monitor):
    """Demonstrate health endpoints for load balancer integration."""
    print("\n" + "=" * 60)
    print("HEALTH ENDPOINTS DEMONSTRATION")
    print("=" * 60)

    # 1. Basic health endpoint
    print("\n1. Health Endpoint Response:")
    print("-" * 30)

    response, status_code = health_monitor.get_health_endpoint_response()
    print(f"  HTTP Status: {status_code}")
    print(f"  Response: {response}")

    # 2. Start health server (in background for demo)
    print("\n2. Starting Health Server:")
    print("-" * 30)

    try:
        health_server = create_health_server(
            health_monitor=health_monitor, host="127.0.0.1", port=8080
        )

        # Start in background
        health_server.start_in_background()

        print("✓ Health server started on http://127.0.0.1:8080")
        print("\nAvailable endpoints:")
        print("  - GET /health - Basic health check")
        print("  - GET /health/ready - Readiness check")
        print("  - GET /health/live - Liveness check")
        print("  - GET /health/detailed - Detailed health report")
        print("  - GET /metrics - Prometheus metrics")

        # Give server time to start
        time.sleep(1)

        # Test endpoints with requests if available
        try:
            import requests

            print("\n3. Testing Endpoints:")
            print("-" * 30)

            endpoints = [
                ("/health", "Basic health check"),
                ("/health/ready", "Readiness check"),
                ("/health/live", "Liveness check"),
                ("/metrics", "Prometheus metrics"),
            ]

            for endpoint, description in endpoints:
                try:
                    response = requests.get(
                        f"http://127.0.0.1:8080{endpoint}", timeout=2
                    )
                    print(f"  {endpoint}: {response.status_code} - {description}")
                except Exception as e:
                    print(f"  {endpoint}: Error - {e}")

        except ImportError:
            print("\n  (Install 'requests' library to test HTTP endpoints)")

        # Stop server
        health_server.stop()
        print("\n✓ Health server stopped")

    except Exception as e:
        print(f"❌ Could not start health server: {e}")


def demonstrate_structured_logging(health_monitor):
    """Demonstrate structured JSON logging."""
    print("\n" + "=" * 60)
    print("STRUCTURED LOGGING DEMONSTRATION")
    print("=" * 60)

    print("\nStructured logs will appear in JSON format:")
    print("-" * 50)

    # Trigger some health checks to generate structured logs
    health_monitor.check_application_health()

    if health_monitor.database_managers:
        db_name = list(health_monitor.database_managers.keys())[0]
        health_monitor.check_database_health(db_name)

    # Log some metrics
    if health_monitor.logger:
        health_monitor.logger.log_metrics(
            {
                "demo_metric": 42.5,
                "timestamp": datetime.now().isoformat(),
                "example": "structured_logging_demo",
            }
        )

        health_monitor.logger.log_alert(
            "demo_alert", "This is a demonstration alert", "INFO"
        )

    print("\n✓ Structured logs generated (see above)")


def main():
    """Main demonstration function."""
    print("🏥 COMPREHENSIVE HEALTH MONITORING SYSTEM DEMO")
    print("=" * 60)

    # Set up logging
    setup_logging()

    # Create health monitor
    health_monitor = create_health_monitor_with_databases()

    # Run demonstrations
    try:
        demonstrate_health_checks(health_monitor)
        demonstrate_prometheus_metrics(health_monitor)
        demonstrate_health_endpoints(health_monitor)
        demonstrate_structured_logging(health_monitor)

        print("\n" + "=" * 60)
        print("✅ HEALTH MONITORING DEMO COMPLETED SUCCESSFULLY")
        print("=" * 60)

        print("\nNext steps:")
        print("- Configure database connections via environment variables")
        print("- Deploy health server in your container environment")
        print("- Configure load balancer to use /health endpoint")
        print("- Set up Prometheus to scrape /metrics endpoint")
        print("- Configure log aggregation for structured JSON logs")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    main()
