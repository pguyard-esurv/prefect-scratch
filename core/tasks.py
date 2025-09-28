"""
Shared RPA tasks that can be reused across different flows.
"""
# ruff: noqa: E501
# flake8: noqa: E501

import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from prefect import get_run_logger, task

from .config import DATA_DIR, OUTPUT_DIR, SAMPLE_PRODUCTS
from .database import DatabaseManager


@task
def create_sample_data() -> str:
    """Create sample data files for processing."""
    logger = get_run_logger()

    # Create data directory
    DATA_DIR.mkdir(exist_ok=True)

    # Create sample CSV data
    csv_file = DATA_DIR / "sales_data.csv"

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SAMPLE_PRODUCTS[0].keys())
        writer.writeheader()
        writer.writerows(SAMPLE_PRODUCTS)

    logger.info(f"Created sample data file: {csv_file}")
    return str(csv_file)


@task
def extract_data(file_path: str) -> list[dict[str, Any]]:
    """Extract data from CSV file."""
    logger = get_run_logger()

    data = []
    with open(file_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert string values to appropriate types
            row["quantity"] = int(row["quantity"])
            row["price"] = float(row["price"])
            data.append(row)

    logger.info(f"Extracted {len(data)} records from {file_path}")
    return data


@task
def transform_data(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Transform data by calculating totals and adding metadata."""
    logger = get_run_logger()

    transformed_data = []
    for record in data:
        # Calculate total value for each record
        record["total_value"] = record["quantity"] * record["price"]
        record["processed_at"] = datetime.now().isoformat()
        transformed_data.append(record)

    logger.info(f"Transformed {len(transformed_data)} records")
    return transformed_data


@task
def calculate_summary(data: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate summary statistics."""
    logger = get_run_logger()

    total_quantity = sum(record["quantity"] for record in data)
    total_value = sum(record["total_value"] for record in data)
    avg_price = sum(record["price"] for record in data) / len(data)

    # Group by product
    product_summary = {}
    for record in data:
        product = record["product"]
        if product not in product_summary:
            product_summary[product] = {"quantity": 0, "total_value": 0}
        product_summary[product]["quantity"] += record["quantity"]
        product_summary[product]["total_value"] += record["total_value"]

    summary = {
        "total_records": len(data),
        "total_quantity": total_quantity,
        "total_value": round(total_value, 2),
        "average_price": round(avg_price, 2),
        "product_breakdown": product_summary,
        "generated_at": datetime.now().isoformat(),
    }

    logger.info(
        f"Calculated summary: {summary['total_records']} records, ${summary['total_value']} total value"
    )
    return summary


@task
def generate_report(summary: dict[str, Any], output_dir: str = None) -> str:
    """Generate a JSON report."""
    logger = get_run_logger()

    # Use default output directory if not specified
    if output_dir is None:
        output_path = OUTPUT_DIR
    else:
        output_path = Path(output_dir)

    # Create output directory
    output_path.mkdir(exist_ok=True)

    # Generate report file
    report_file = (
        output_path / f"sales_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(report_file, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Generated report: {report_file}")
    return str(report_file)


@task
def cleanup_temp_files(file_path: str) -> None:
    """Clean up temporary files."""
    logger = get_run_logger()

    try:
        os.remove(file_path)
        logger.info(f"Cleaned up temporary file: {file_path}")
    except FileNotFoundError:
        logger.warning(f"File not found for cleanup: {file_path}")


@task
def create_directory(path: str) -> str:
    """Create a directory if it doesn't exist."""
    logger = get_run_logger()

    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Created directory: {dir_path}")
    return str(dir_path)


@task
def validate_file_exists(file_path: str) -> bool:
    """Validate that a file exists."""
    logger = get_run_logger()

    exists = Path(file_path).exists()
    if exists:
        logger.info(f"File exists: {file_path}")
    else:
        logger.warning(f"File not found: {file_path}")

    return exists


# Database Monitoring and Operational Utilities

@task
def database_health_check(database_name: str, include_retry: bool = True) -> dict[str, Any]:
    """
    Perform comprehensive database health check that can be used across multiple flows.

    This task provides a standardized way to check database health including
    connectivity, query execution, migration status, and performance metrics.

    Args:
        database_name: Name of the database to check
        include_retry: Whether to use retry logic for transient failures

    Returns:
        Dictionary containing comprehensive health check results

    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5
    """
    logger = get_run_logger()

    logger.info(f"Starting health check for database '{database_name}'")

    try:
        with DatabaseManager(database_name) as db:
            if include_retry:
                health_result = db.health_check_with_retry()
            else:
                health_result = db.health_check()

            # Log health status
            status = health_result.get("status", "unknown")
            response_time = health_result.get("response_time_ms", 0)

            if status == "healthy":
                logger.info(
                    f"Database '{database_name}' is healthy "
                    f"(response time: {response_time}ms)"
                )
            elif status == "degraded":
                logger.warning(
                    f"Database '{database_name}' is degraded "
                    f"(response time: {response_time}ms)"
                )
            else:
                logger.error(
                    f"Database '{database_name}' is unhealthy: "
                    f"{health_result.get('error', 'Unknown error')}"
                )

            return health_result

    except Exception as e:
        error_msg = f"Health check failed for database '{database_name}': {e}"
        logger.error(error_msg)

        # Return unhealthy status instead of raising exception
        return {
            "database_name": database_name,
            "status": "unhealthy",
            "connection": False,
            "query_test": False,
            "migration_status": None,
            "response_time_ms": None,
            "timestamp": datetime.now().isoformat() + "Z",
            "error": error_msg,
            "task_execution_error": True
        }


@task
def connection_pool_monitoring(database_name: str) -> dict[str, Any]:
    """
    Monitor connection pool status and metrics for operational visibility.

    Provides detailed information about connection pool utilization,
    performance metrics, and resource usage patterns.

    Args:
        database_name: Name of the database to monitor

    Returns:
        Dictionary containing connection pool metrics and analysis

    Requirements: 6.1, 6.2, 6.5
    """
    logger = get_run_logger()

    logger.info(f"Monitoring connection pool for database '{database_name}'")

    try:
        with DatabaseManager(database_name) as db:
            pool_status = db.get_pool_status()

            # Add analysis and recommendations
            utilization = pool_status.get("utilization_percent", 0)
            checked_out = pool_status.get("checked_out", 0)
            max_connections = pool_status.get("max_connections", 0)
            overflow = pool_status.get("overflow", 0)

            # Determine pool health
            if utilization < 50:
                pool_health = "optimal"
                recommendation = "Pool utilization is healthy"
            elif utilization < 80:
                pool_health = "moderate"
                recommendation = "Monitor pool usage, consider increasing pool size if sustained"
            else:
                pool_health = "high"
                recommendation = "High pool utilization detected, consider increasing pool_size or max_overflow"

            # Add overflow analysis
            if overflow > 0:
                overflow_analysis = f"Using {overflow} overflow connections beyond base pool"
            else:
                overflow_analysis = "No overflow connections in use"

            # Enhanced monitoring result
            monitoring_result = {
                **pool_status,
                "pool_health": pool_health,
                "recommendation": recommendation,
                "overflow_analysis": overflow_analysis,
                "monitoring_timestamp": datetime.now().isoformat() + "Z"
            }

            logger.info(
                f"Pool monitoring for '{database_name}': "
                f"{checked_out}/{max_connections} connections "
                f"({utilization}% utilization, {pool_health})"
            )

            return monitoring_result

    except Exception as e:
        error_msg = f"Connection pool monitoring failed for database '{database_name}': {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


@task
def database_prerequisite_validation(
    database_names: list[str],
    check_migrations: bool = True,
    performance_threshold_ms: float = 1000.0
) -> dict[str, Any]:
    """
    Validate database prerequisites for flow startup checks.

    Performs comprehensive validation of database readiness including
    connectivity, migration status, and performance benchmarks before
    allowing flows to proceed with data operations.

    Args:
        database_names: List of database names to validate
        check_migrations: Whether to validate migration status
        performance_threshold_ms: Maximum acceptable response time in milliseconds

    Returns:
        Dictionary containing validation results for all databases

    Requirements: 6.1, 6.2, 6.3, 6.4
    """
    logger = get_run_logger()

    logger.info(f"Validating database prerequisites for {len(database_names)} databases")

    validation_results = {
        "overall_status": "passed",
        "validation_timestamp": datetime.now().isoformat() + "Z",
        "databases": {},
        "summary": {
            "total_databases": len(database_names),
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }
    }

    for database_name in database_names:
        logger.info(f"Validating prerequisites for database '{database_name}'")

        db_validation = {
            "database_name": database_name,
            "status": "failed",
            "connectivity": False,
            "performance_ok": False,
            "migrations_ok": False,
            "issues": [],
            "warnings": []
        }

        try:
            with DatabaseManager(database_name) as db:
                # Test 1: Basic connectivity and health
                health_result = db.health_check()
                db_validation["connectivity"] = health_result.get("connection", False)

                if not db_validation["connectivity"]:
                    db_validation["issues"].append(
                        f"Database connectivity failed: {health_result.get('error', 'Unknown error')}"
                    )

                # Test 2: Performance validation
                response_time = health_result.get("response_time_ms", float('inf'))
                db_validation["performance_ok"] = response_time <= performance_threshold_ms

                if not db_validation["performance_ok"]:
                    if response_time == float('inf'):
                        db_validation["issues"].append("Could not measure response time")
                    else:
                        db_validation["warnings"].append(
                            f"Response time ({response_time}ms) exceeds threshold ({performance_threshold_ms}ms)"
                        )

                # Test 3: Migration status validation
                if check_migrations:
                    try:
                        migration_status = db.get_migration_status()
                        pending_migrations = migration_status.get("pending_migrations", [])

                        if pending_migrations:
                            db_validation["warnings"].append(
                                f"Found {len(pending_migrations)} pending migrations"
                            )
                            db_validation["migrations_ok"] = False
                        else:
                            db_validation["migrations_ok"] = True

                    except Exception as migration_error:
                        db_validation["issues"].append(
                            f"Migration status check failed: {migration_error}"
                        )
                        db_validation["migrations_ok"] = False
                else:
                    db_validation["migrations_ok"] = True  # Skip migration check

                # Determine overall database status
                if (db_validation["connectivity"] and
                    db_validation["performance_ok"] and
                    db_validation["migrations_ok"]):
                    db_validation["status"] = "passed"
                    validation_results["summary"]["passed"] += 1
                elif db_validation["connectivity"] and not db_validation["issues"]:
                    db_validation["status"] = "warning"
                    validation_results["summary"]["warnings"] += 1
                else:
                    db_validation["status"] = "failed"
                    validation_results["summary"]["failed"] += 1
                    validation_results["overall_status"] = "failed"

        except Exception as e:
            db_validation["issues"].append(f"Validation error: {e}")
            db_validation["status"] = "failed"
            validation_results["summary"]["failed"] += 1
            validation_results["overall_status"] = "failed"

            logger.error(f"Prerequisite validation failed for database '{database_name}': {e}")

        validation_results["databases"][database_name] = db_validation

        # Log individual database result
        if db_validation["status"] == "passed":
            logger.info(f"Database '{database_name}' passed prerequisite validation")
        elif db_validation["status"] == "warning":
            logger.warning(f"Database '{database_name}' passed with warnings: {db_validation['warnings']}")
        else:
            logger.error(f"Database '{database_name}' failed prerequisite validation: {db_validation['issues']}")

    # Log overall results
    summary = validation_results["summary"]
    logger.info(
        f"Prerequisite validation complete: "
        f"{summary['passed']} passed, {summary['warnings']} warnings, {summary['failed']} failed"
    )

    return validation_results


@task
def database_connectivity_diagnostics(database_name: str) -> dict[str, Any]:
    """
    Perform comprehensive database connectivity diagnostics for troubleshooting.

    Provides detailed diagnostic information to help troubleshoot database
    connectivity issues including configuration validation, network tests,
    and detailed error analysis.

    Args:
        database_name: Name of the database to diagnose

    Returns:
        Dictionary containing comprehensive diagnostic information

    Requirements: 6.1, 6.4, 6.5
    """
    logger = get_run_logger()

    logger.info(f"Running connectivity diagnostics for database '{database_name}'")

    diagnostics = {
        "database_name": database_name,
        "diagnostic_timestamp": datetime.now().isoformat() + "Z",
        "configuration": {},
        "connectivity": {},
        "performance": {},
        "recommendations": []
    }

    try:
        # Configuration diagnostics
        from .database import validate_database_configuration
        config_validation = validate_database_configuration(database_name)
        diagnostics["configuration"] = config_validation.get(database_name, {})

        if not diagnostics["configuration"].get("valid", False):
            diagnostics["recommendations"].append(
                "Fix configuration issues before testing connectivity"
            )
            return diagnostics

        # Connectivity diagnostics
        with DatabaseManager(database_name) as db:
            # Test basic connectivity
            start_time = time.time()
            health_result = db.health_check()
            end_time = time.time()

            diagnostics["connectivity"] = {
                "connection_successful": health_result.get("connection", False),
                "query_test_successful": health_result.get("query_test", False),
                "total_time_ms": round((end_time - start_time) * 1000, 2),
                "response_time_ms": health_result.get("response_time_ms"),
                "error": health_result.get("error")
            }

            # Pool diagnostics
            if diagnostics["connectivity"]["connection_successful"]:
                pool_status = db.get_pool_status()
                diagnostics["performance"] = {
                    "pool_status": pool_status,
                    "pool_utilization": pool_status.get("utilization_percent", 0),
                    "connection_efficiency": "good" if pool_status.get("utilization_percent", 0) < 80 else "concerning"
                }

                # Performance recommendations
                response_time = diagnostics["connectivity"]["response_time_ms"]
                if response_time and response_time > 1000:
                    diagnostics["recommendations"].append(
                        f"High response time ({response_time}ms) - check network latency and database load"
                    )

                utilization = pool_status.get("utilization_percent", 0)
                if utilization > 80:
                    diagnostics["recommendations"].append(
                        "High connection pool utilization - consider increasing pool_size"
                    )
            else:
                diagnostics["recommendations"].append(
                    "Connection failed - check network connectivity and credentials"
                )

                # Analyze error for specific recommendations
                error = diagnostics["connectivity"]["error"]
                if error:
                    error_lower = error.lower()
                    if "connection refused" in error_lower:
                        diagnostics["recommendations"].append(
                            "Connection refused - verify database server is running and accessible"
                        )
                    elif "authentication" in error_lower or "login" in error_lower:
                        diagnostics["recommendations"].append(
                            "Authentication failed - verify username and password"
                        )
                    elif "timeout" in error_lower:
                        diagnostics["recommendations"].append(
                            "Connection timeout - check network connectivity and firewall settings"
                        )
                    elif "database" in error_lower and "not exist" in error_lower:
                        diagnostics["recommendations"].append(
                            "Database does not exist - verify database name in connection string"
                        )

        logger.info(f"Connectivity diagnostics completed for database '{database_name}'")

    except Exception as e:
        error_msg = f"Diagnostics failed for database '{database_name}': {e}"
        logger.error(error_msg)

        diagnostics["connectivity"]["error"] = error_msg
        diagnostics["recommendations"].append(
            "Diagnostic execution failed - check DatabaseManager configuration"
        )

    return diagnostics


@task
def database_performance_monitoring(
    database_name: str,
    test_queries: Optional[list[str]] = None,
    iterations: int = 3
) -> dict[str, Any]:
    """
    Collect performance monitoring and metrics for database operations.

    Executes performance tests including query execution times, connection
    pool efficiency, and resource utilization to provide operational insights.

    Args:
        database_name: Name of the database to monitor
        test_queries: Optional list of queries to benchmark (uses default if None)
        iterations: Number of iterations for performance tests

    Returns:
        Dictionary containing performance metrics and analysis

    Requirements: 6.1, 6.2, 6.5
    """
    logger = get_run_logger()

    logger.info(f"Starting performance monitoring for database '{database_name}'")

    # Default test queries if none provided
    if test_queries is None:
        test_queries = [
            "SELECT 1 as simple_test",
            "SELECT COUNT(*) as count_test FROM information_schema.tables",
        ]

    performance_metrics = {
        "database_name": database_name,
        "monitoring_timestamp": datetime.now().isoformat() + "Z",
        "test_configuration": {
            "iterations": iterations,
            "test_queries_count": len(test_queries)
        },
        "connection_metrics": {},
        "query_performance": {},
        "pool_efficiency": {},
        "overall_assessment": {}
    }

    try:
        with DatabaseManager(database_name) as db:
            # Connection performance metrics
            connection_times = []
            for _i in range(iterations):
                start_time = time.time()
                health_result = db.health_check()
                end_time = time.time()

                if health_result.get("connection", False):
                    connection_times.append((end_time - start_time) * 1000)

            if connection_times:
                performance_metrics["connection_metrics"] = {
                    "avg_connection_time_ms": round(sum(connection_times) / len(connection_times), 2),
                    "min_connection_time_ms": round(min(connection_times), 2),
                    "max_connection_time_ms": round(max(connection_times), 2),
                    "successful_connections": len(connection_times),
                    "total_attempts": iterations
                }

            # Query performance metrics
            query_metrics = {}
            for query_idx, query in enumerate(test_queries):
                query_times = []
                successful_executions = 0

                for i in range(iterations):
                    try:
                        start_time = time.time()
                        db.execute_query(query)
                        end_time = time.time()

                        query_times.append((end_time - start_time) * 1000)
                        successful_executions += 1

                    except Exception as query_error:
                        logger.warning(f"Query {query_idx + 1} failed on iteration {i + 1}: {query_error}")

                if query_times:
                    query_metrics[f"query_{query_idx + 1}"] = {
                        "query": query[:50] + "..." if len(query) > 50 else query,
                        "avg_execution_time_ms": round(sum(query_times) / len(query_times), 2),
                        "min_execution_time_ms": round(min(query_times), 2),
                        "max_execution_time_ms": round(max(query_times), 2),
                        "successful_executions": successful_executions,
                        "total_attempts": iterations,
                        "success_rate": round((successful_executions / iterations) * 100, 2)
                    }

            performance_metrics["query_performance"] = query_metrics

            # Pool efficiency metrics
            pool_status = db.get_pool_status()
            performance_metrics["pool_efficiency"] = {
                "current_utilization": pool_status.get("utilization_percent", 0),
                "pool_size": pool_status.get("pool_size", 0),
                "max_connections": pool_status.get("max_connections", 0),
                "checked_out": pool_status.get("checked_out", 0),
                "overflow_connections": pool_status.get("overflow", 0),
                "efficiency_rating": "excellent" if pool_status.get("utilization_percent", 0) < 50 else
                                   "good" if pool_status.get("utilization_percent", 0) < 80 else "concerning"
            }

            # Overall assessment
            avg_connection_time = performance_metrics["connection_metrics"].get("avg_connection_time_ms", 0)
            avg_query_times = [
                metrics.get("avg_execution_time_ms", 0)
                for metrics in query_metrics.values()
            ]
            avg_query_time = sum(avg_query_times) / len(avg_query_times) if avg_query_times else 0

            # Performance assessment
            if avg_connection_time < 100 and avg_query_time < 50:
                performance_rating = "excellent"
            elif avg_connection_time < 500 and avg_query_time < 200:
                performance_rating = "good"
            elif avg_connection_time < 1000 and avg_query_time < 1000:
                performance_rating = "acceptable"
            else:
                performance_rating = "poor"

            performance_metrics["overall_assessment"] = {
                "performance_rating": performance_rating,
                "avg_connection_time_ms": avg_connection_time,
                "avg_query_time_ms": round(avg_query_time, 2),
                "recommendations": []
            }

            # Add recommendations based on performance
            recommendations = performance_metrics["overall_assessment"]["recommendations"]

            if avg_connection_time > 500:
                recommendations.append("High connection times detected - check network latency")

            if avg_query_time > 200:
                recommendations.append("Slow query performance - consider query optimization")

            if pool_status.get("utilization_percent", 0) > 80:
                recommendations.append("High pool utilization - consider increasing pool size")

            if not recommendations:
                recommendations.append("Performance is within acceptable ranges")

        logger.info(
            f"Performance monitoring completed for database '{database_name}': "
            f"{performance_metrics['overall_assessment']['performance_rating']} performance"
        )

    except Exception as e:
        error_msg = f"Performance monitoring failed for database '{database_name}': {e}"
        logger.error(error_msg)

        performance_metrics["overall_assessment"] = {
            "performance_rating": "error",
            "error": error_msg,
            "recommendations": ["Fix connectivity issues before performance monitoring"]
        }

    return performance_metrics


@task
def multi_database_health_summary(database_names: list[str]) -> dict[str, Any]:
    """
    Generate comprehensive health summary across multiple databases.

    Provides a consolidated view of health status across all configured
    databases for operational dashboards and monitoring systems.

    Args:
        database_names: List of database names to include in summary

    Returns:
        Dictionary containing consolidated health summary

    Requirements: 6.1, 6.2, 6.3, 6.5
    """
    logger = get_run_logger()

    logger.info(f"Generating health summary for {len(database_names)} databases")

    summary = {
        "summary_timestamp": datetime.now().isoformat() + "Z",
        "overall_status": "healthy",
        "database_count": len(database_names),
        "status_breakdown": {
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0
        },
        "databases": {},
        "alerts": [],
        "recommendations": []
    }

    for database_name in database_names:
        try:
            # Get health status for each database
            health_result = database_health_check.fn(database_name, include_retry=False)

            status = health_result.get("status", "unhealthy")
            summary["databases"][database_name] = {
                "status": status,
                "response_time_ms": health_result.get("response_time_ms"),
                "connection": health_result.get("connection", False),
                "error": health_result.get("error")
            }

            # Update status breakdown
            summary["status_breakdown"][status] += 1

            # Generate alerts for unhealthy databases
            if status == "unhealthy":
                summary["alerts"].append(
                    f"Database '{database_name}' is unhealthy: {health_result.get('error', 'Unknown error')}"
                )
                summary["overall_status"] = "unhealthy"
            elif status == "degraded":
                summary["alerts"].append(
                    f"Database '{database_name}' is degraded (response time: {health_result.get('response_time_ms', 'unknown')}ms)"
                )
                if summary["overall_status"] == "healthy":
                    summary["overall_status"] = "degraded"

        except Exception as e:
            logger.error(f"Failed to get health status for database '{database_name}': {e}")

            summary["databases"][database_name] = {
                "status": "unhealthy",
                "response_time_ms": None,
                "connection": False,
                "error": f"Health check failed: {e}"
            }

            summary["status_breakdown"]["unhealthy"] += 1
            summary["alerts"].append(f"Database '{database_name}' health check failed: {e}")
            summary["overall_status"] = "unhealthy"

    # Generate recommendations
    if summary["status_breakdown"]["unhealthy"] > 0:
        summary["recommendations"].append(
            f"Investigate {summary['status_breakdown']['unhealthy']} unhealthy database(s)"
        )

    if summary["status_breakdown"]["degraded"] > 0:
        summary["recommendations"].append(
            f"Monitor {summary['status_breakdown']['degraded']} degraded database(s) for performance issues"
        )

    if summary["status_breakdown"]["healthy"] == len(database_names):
        summary["recommendations"].append("All databases are healthy")

    logger.info(
        f"Health summary complete: {summary['overall_status']} overall status, "
        f"{summary['status_breakdown']['healthy']} healthy, "
        f"{summary['status_breakdown']['degraded']} degraded, "
        f"{summary['status_breakdown']['unhealthy']} unhealthy"
    )

    return summary
