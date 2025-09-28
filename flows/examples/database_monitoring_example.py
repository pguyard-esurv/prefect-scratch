"""
Example flow demonstrating database monitoring and operational utilities.

This example shows how to use the database monitoring tasks in real Prefect flows
for operational visibility, health checking, and performance monitoring.
"""

from typing import Optional

from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from core.tasks import (
    connection_pool_monitoring,
    database_connectivity_diagnostics,
    database_health_check,
    database_performance_monitoring,
    database_prerequisite_validation,
    multi_database_health_summary,
)


@flow(
    name="Database Health Monitoring",
    description="Comprehensive database health monitoring across all configured databases",
    task_runner=ConcurrentTaskRunner()
)
def database_health_monitoring_flow(
    database_names: Optional[list[str]] = None,
    include_performance_tests: bool = True,
    performance_threshold_ms: float = 1000.0
):
    """
    Comprehensive database health monitoring flow.

    This flow performs health checks, pool monitoring, and performance testing
    across all configured databases to provide operational visibility.

    Args:
        database_names: List of database names to monitor (defaults to common databases)
        include_performance_tests: Whether to run performance benchmarks
        performance_threshold_ms: Performance threshold for health assessment
    """
    logger = get_run_logger()

    # Default database names if not provided
    if database_names is None:
        database_names = ["rpa_db", "SurveyHub"]

    logger.info(f"Starting health monitoring for databases: {database_names}")

    # Step 1: Multi-database health summary
    health_summary = multi_database_health_summary(database_names)

    # Step 2: Individual database health checks (concurrent)
    health_checks = []
    for db_name in database_names:
        health_check = database_health_check(db_name, include_retry=True)
        health_checks.append(health_check)

    # Step 3: Connection pool monitoring (concurrent)
    pool_monitoring_results = []
    for db_name in database_names:
        pool_status = connection_pool_monitoring(db_name)
        pool_monitoring_results.append(pool_status)

    # Step 4: Performance monitoring (if enabled)
    performance_results = []
    if include_performance_tests:
        for db_name in database_names:
            perf_result = database_performance_monitoring(
                db_name,
                test_queries=[
                    "SELECT 1 as health_test",
                    "SELECT COUNT(*) FROM information_schema.tables"
                ],
                iterations=3
            )
            performance_results.append(perf_result)

    # Compile monitoring report
    monitoring_report = {
        "monitoring_timestamp": health_summary["summary_timestamp"],
        "overall_health": health_summary,
        "individual_health_checks": health_checks,
        "pool_monitoring": pool_monitoring_results,
        "performance_results": performance_results if include_performance_tests else None
    }

    # Log summary
    overall_status = health_summary["overall_status"]
    healthy_count = health_summary["status_breakdown"]["healthy"]
    total_count = health_summary["database_count"]

    logger.info(
        f"Health monitoring complete: {overall_status} overall status, "
        f"{healthy_count}/{total_count} databases healthy"
    )

    return monitoring_report


@flow(
    name="Database Prerequisite Validation",
    description="Validate database prerequisites before flow execution"
)
def database_prerequisite_flow(
    database_names: Optional[list[str]] = None,
    check_migrations: bool = True,
    performance_threshold_ms: float = 1000.0,
    fail_on_validation_error: bool = True
):
    """
    Database prerequisite validation flow for startup checks.

    This flow validates that all required databases are ready for operation
    before allowing other flows to proceed with data processing.

    Args:
        database_names: List of database names to validate
        check_migrations: Whether to check migration status
        performance_threshold_ms: Maximum acceptable response time
        fail_on_validation_error: Whether to fail flow if validation fails
    """
    logger = get_run_logger()

    if database_names is None:
        database_names = ["rpa_db", "SurveyHub"]

    logger.info(f"Validating prerequisites for databases: {database_names}")

    # Perform prerequisite validation
    validation_result = database_prerequisite_validation(
        database_names=database_names,
        check_migrations=check_migrations,
        performance_threshold_ms=performance_threshold_ms
    )

    # Check validation results
    overall_status = validation_result["overall_status"]
    failed_count = validation_result["summary"]["failed"]
    warning_count = validation_result["summary"]["warnings"]

    if overall_status == "failed" and fail_on_validation_error:
        error_msg = f"Database prerequisite validation failed for {failed_count} database(s)"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    elif warning_count > 0:
        logger.warning(f"Database prerequisite validation completed with {warning_count} warning(s)")
    else:
        logger.info("All database prerequisites validated successfully")

    return validation_result


@flow(
    name="Database Diagnostics",
    description="Comprehensive database connectivity diagnostics"
)
def database_diagnostics_flow(database_name: str):
    """
    Comprehensive database diagnostics flow for troubleshooting.

    This flow performs detailed diagnostics on a specific database to help
    troubleshoot connectivity issues and performance problems.

    Args:
        database_name: Name of the database to diagnose
    """
    logger = get_run_logger()

    logger.info(f"Running comprehensive diagnostics for database '{database_name}'")

    # Step 1: Basic health check
    health_result = database_health_check(database_name, include_retry=False)

    # Step 2: Detailed connectivity diagnostics
    diagnostics_result = database_connectivity_diagnostics(database_name)

    # Step 3: Connection pool analysis
    pool_result = connection_pool_monitoring(database_name)

    # Step 4: Performance analysis
    performance_result = database_performance_monitoring(
        database_name,
        test_queries=[
            "SELECT 1 as simple_test",
            "SELECT COUNT(*) FROM information_schema.tables",
            "SELECT version() as db_version"  # Database-specific version query
        ],
        iterations=5
    )

    # Compile diagnostic report
    diagnostic_report = {
        "database_name": database_name,
        "diagnostic_timestamp": diagnostics_result["diagnostic_timestamp"],
        "health_check": health_result,
        "connectivity_diagnostics": diagnostics_result,
        "pool_analysis": pool_result,
        "performance_analysis": performance_result
    }

    # Generate summary and recommendations
    recommendations = []

    # Health-based recommendations
    if health_result["status"] == "unhealthy":
        recommendations.append("CRITICAL: Database is unhealthy - immediate attention required")
    elif health_result["status"] == "degraded":
        recommendations.append("WARNING: Database performance is degraded")

    # Pool-based recommendations
    if pool_result["pool_health"] == "high":
        recommendations.append("Consider increasing connection pool size")

    # Performance-based recommendations
    perf_rating = performance_result["overall_assessment"]["performance_rating"]
    if perf_rating == "poor":
        recommendations.append("CRITICAL: Poor database performance detected")
    elif perf_rating == "acceptable":
        recommendations.append("Database performance is acceptable but could be improved")

    # Connectivity-based recommendations
    recommendations.extend(diagnostics_result.get("recommendations", []))

    diagnostic_report["summary_recommendations"] = recommendations

    # Log diagnostic summary
    logger.info(
        f"Diagnostics complete for '{database_name}': "
        f"Health={health_result['status']}, "
        f"Pool={pool_result['pool_health']}, "
        f"Performance={perf_rating}"
    )

    if recommendations:
        logger.warning(f"Diagnostic recommendations: {'; '.join(recommendations)}")

    return diagnostic_report


@flow(
    name="Operational Database Monitoring",
    description="Continuous operational monitoring for production environments"
)
def operational_monitoring_flow(
    database_names: Optional[list[str]] = None,
    monitoring_interval_minutes: int = 15,
    alert_thresholds: Optional[dict] = None
):
    """
    Operational monitoring flow for production database oversight.

    This flow provides continuous monitoring capabilities suitable for
    production environments with configurable alerting thresholds.

    Args:
        database_names: List of database names to monitor
        monitoring_interval_minutes: How often to run monitoring (for scheduling)
        alert_thresholds: Custom alert thresholds for various metrics
    """
    logger = get_run_logger()

    if database_names is None:
        database_names = ["rpa_db", "SurveyHub"]

    # Default alert thresholds
    if alert_thresholds is None:
        alert_thresholds = {
            "response_time_ms": 2000.0,
            "pool_utilization_percent": 80.0,
            "connection_failure_threshold": 1
        }

    logger.info(f"Starting operational monitoring for {len(database_names)} databases")

    # Collect monitoring data
    monitoring_data = {
        "monitoring_timestamp": None,
        "databases": {},
        "alerts": [],
        "metrics_summary": {}
    }

    # Get comprehensive health summary
    health_summary = multi_database_health_summary(database_names)
    monitoring_data["monitoring_timestamp"] = health_summary["summary_timestamp"]

    # Collect detailed metrics for each database
    for db_name in database_names:
        db_metrics = {
            "database_name": db_name,
            "health": None,
            "pool_status": None,
            "alerts": []
        }

        try:
            # Health check
            health_result = database_health_check(db_name, include_retry=True)
            db_metrics["health"] = health_result

            # Pool monitoring
            pool_result = connection_pool_monitoring(db_name)
            db_metrics["pool_status"] = pool_result

            # Check alert thresholds
            response_time = health_result.get("response_time_ms", 0)
            if response_time and response_time > alert_thresholds["response_time_ms"]:
                alert = f"High response time for {db_name}: {response_time}ms"
                db_metrics["alerts"].append(alert)
                monitoring_data["alerts"].append(alert)

            pool_utilization = pool_result.get("utilization_percent", 0)
            if pool_utilization > alert_thresholds["pool_utilization_percent"]:
                alert = f"High pool utilization for {db_name}: {pool_utilization}%"
                db_metrics["alerts"].append(alert)
                monitoring_data["alerts"].append(alert)

            if not health_result.get("connection", False):
                alert = f"Connection failure for {db_name}: {health_result.get('error', 'Unknown error')}"
                db_metrics["alerts"].append(alert)
                monitoring_data["alerts"].append(alert)

        except Exception as e:
            error_alert = f"Monitoring failed for {db_name}: {e}"
            db_metrics["alerts"].append(error_alert)
            monitoring_data["alerts"].append(error_alert)
            logger.error(error_alert)

        monitoring_data["databases"][db_name] = db_metrics

    # Generate metrics summary
    total_alerts = len(monitoring_data["alerts"])
    healthy_dbs = sum(1 for db_data in monitoring_data["databases"].values()
                     if db_data.get("health") and db_data.get("health", {}).get("status") == "healthy")

    monitoring_data["metrics_summary"] = {
        "total_databases": len(database_names),
        "healthy_databases": healthy_dbs,
        "total_alerts": total_alerts,
        "overall_status": "healthy" if total_alerts == 0 else "alert"
    }

    # Log operational summary
    logger.info(
        f"Operational monitoring complete: "
        f"{healthy_dbs}/{len(database_names)} databases healthy, "
        f"{total_alerts} alerts generated"
    )

    if total_alerts > 0:
        logger.warning(f"Active alerts: {'; '.join(monitoring_data['alerts'])}")

    return monitoring_data


# Example usage and testing functions
if __name__ == "__main__":
    # Example: Run health monitoring
    print("Running database health monitoring example...")

    try:
        result = database_health_monitoring_flow(
            database_names=["rpa_db"],
            include_performance_tests=True
        )
        print(f"Health monitoring completed: {result['overall_health']['overall_status']}")
    except Exception as e:
        print(f"Health monitoring failed: {e}")

    # Example: Run prerequisite validation
    print("\nRunning prerequisite validation example...")

    try:
        result = database_prerequisite_flow(
            database_names=["rpa_db"],
            fail_on_validation_error=False
        )
        print(f"Prerequisite validation: {result['overall_status']}")
    except Exception as e:
        print(f"Prerequisite validation failed: {e}")

    # Example: Run diagnostics
    print("\nRunning database diagnostics example...")

    try:
        result = database_diagnostics_flow("rpa_db")
        recommendations = result.get("summary_recommendations", [])
        print(f"Diagnostics completed with {len(recommendations)} recommendations")
        for rec in recommendations:
            print(f"  - {rec}")
    except Exception as e:
        print(f"Diagnostics failed: {e}")
