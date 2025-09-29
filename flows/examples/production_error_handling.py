"""
Example flow demonstrating comprehensive error handling for production-ready DatabaseManager usage.

This example shows how to:
1. Implement robust error handling and recovery strategies
2. Handle different types of database errors appropriately
3. Implement retry logic with exponential backoff
4. Provide detailed error logging and monitoring
5. Implement graceful degradation and fallback mechanisms
6. Create production-ready error handling patterns
"""

import json
import time
from datetime import datetime
from typing import Any, Optional

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from core.database import DatabaseManager


class DatabaseOperationError(Exception):
    """Custom exception for database operation errors."""

    def __init__(
        self,
        message: str,
        database_name: str,
        operation: str,
        error_type: str = "unknown",
    ):
        self.database_name = database_name
        self.operation = operation
        self.error_type = error_type
        super().__init__(message)


@task(retries=3, retry_delay_seconds=5)
def robust_database_operation(
    operation_type: str,
    database_name: str,
    query: str,
    params: Optional[dict[str, Any]] = None,
    timeout: int = 30,
    critical: bool = True,
) -> dict[str, Any]:
    """
    Perform database operation with comprehensive error handling and retry logic.

    Args:
        operation_type: Type of operation (select, insert, update, delete, transaction)
        database_name: Name of the database
        query: SQL query or list of queries for transactions
        params: Query parameters
        timeout: Operation timeout in seconds
        critical: Whether this operation is critical to flow success

    Returns:
        Dictionary with operation results and metadata

    Raises:
        DatabaseOperationError: If operation fails after retries (only for critical operations)
    """
    logger = get_run_logger()
    operation_start = time.time()

    operation_result = {
        "operation_type": operation_type,
        "database_name": database_name,
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "duration_ms": None,
        "status": "unknown",
        "results": None,
        "error": None,
        "retry_count": 0,
        "critical": critical,
    }

    try:
        logger.info(
            f"Starting {operation_type} operation on database '{database_name}' (critical: {critical})"
        )

        with DatabaseManager(database_name) as db:
            # Perform health check first for critical operations
            if critical:
                health_status = db.health_check()
                if health_status.get("status") == "unhealthy":
                    raise DatabaseOperationError(
                        f"Database '{database_name}' is unhealthy: {health_status.get('error', 'Unknown error')}",
                        database_name,
                        operation_type,
                        "health_check_failed",
                    )

            # Execute operation based on type
            if operation_type == "select":
                results = db.execute_query(query, params)
                operation_result["results"] = results
                operation_result["record_count"] = len(results)

            elif operation_type == "select_with_timeout":
                results = db.execute_query_with_timeout(query, params, timeout)
                operation_result["results"] = results
                operation_result["record_count"] = len(results)

            elif operation_type == "insert":
                db.execute_query(query, params)
                operation_result["results"] = {
                    "rows_affected": 1
                }  # Assume single insert

            elif operation_type == "update":
                db.execute_query(query, params)
                operation_result["results"] = {"operation": "update_completed"}

            elif operation_type == "transaction":
                # Query should be a list of (query, params) tuples for transactions
                if not isinstance(query, list):
                    raise ValueError(
                        "Transaction operations require a list of (query, params) tuples"
                    )

                results = db.execute_transaction(query)
                operation_result["results"] = results
                operation_result["transaction_queries"] = len(query)

            else:
                raise ValueError(f"Unsupported operation type: {operation_type}")

            # Calculate duration and set success status
            operation_end = time.time()
            operation_result["duration_ms"] = round(
                (operation_end - operation_start) * 1000, 2
            )
            operation_result["end_time"] = datetime.now().isoformat()
            operation_result["status"] = "success"

            logger.info(
                f"Operation {operation_type} completed successfully on '{database_name}' in {operation_result['duration_ms']}ms"
            )
            return operation_result

    except Exception as e:
        operation_end = time.time()
        operation_result["duration_ms"] = round(
            (operation_end - operation_start) * 1000, 2
        )
        operation_result["end_time"] = datetime.now().isoformat()
        operation_result["status"] = "error"
        operation_result["error"] = str(e)

        # Classify error type for better handling
        error_type = _classify_database_error(e)
        operation_result["error_type"] = error_type

        logger.error(
            f"Operation {operation_type} failed on '{database_name}': {e} (type: {error_type})"
        )

        # For critical operations, raise custom exception
        if critical:
            raise DatabaseOperationError(
                f"Critical {operation_type} operation failed on '{database_name}': {str(e)}",
                database_name,
                operation_type,
                error_type,
            ) from e

        # For non-critical operations, return error result without raising
        logger.warning(
            f"Non-critical operation {operation_type} failed, continuing flow execution"
        )
        return operation_result


@task
def handle_database_error_with_fallback(
    primary_database: str,
    fallback_database: Optional[str],
    operation_type: str,
    query: str,
    params: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Handle database operations with fallback to secondary database.

    Args:
        primary_database: Primary database name
        fallback_database: Fallback database name (optional)
        operation_type: Type of operation
        query: SQL query
        params: Query parameters

    Returns:
        Dictionary with operation results and fallback information
    """
    logger = get_run_logger()

    fallback_result = {
        "primary_database": primary_database,
        "fallback_database": fallback_database,
        "operation_type": operation_type,
        "primary_attempt": None,
        "fallback_attempt": None,
        "final_status": "unknown",
        "data_source": None,
    }

    # Try primary database first
    try:
        logger.info(
            f"Attempting {operation_type} on primary database '{primary_database}'"
        )

        primary_result = robust_database_operation(
            operation_type=operation_type,
            database_name=primary_database,
            query=query,
            params=params,
            critical=False,  # Don't fail immediately, we have fallback
        )

        fallback_result["primary_attempt"] = primary_result

        if primary_result["status"] == "success":
            fallback_result["final_status"] = "success"
            fallback_result["data_source"] = "primary"
            logger.info(f"Primary database operation succeeded on '{primary_database}'")
            return fallback_result

    except Exception as e:
        logger.warning(
            f"Primary database operation failed on '{primary_database}': {e}"
        )
        fallback_result["primary_attempt"] = {
            "status": "error",
            "error": str(e),
            "database_name": primary_database,
        }

    # Try fallback database if available and primary failed
    if fallback_database:
        try:
            logger.info(
                f"Attempting {operation_type} on fallback database '{fallback_database}'"
            )

            fallback_operation_result = robust_database_operation(
                operation_type=operation_type,
                database_name=fallback_database,
                query=query,
                params=params,
                critical=False,
            )

            fallback_result["fallback_attempt"] = fallback_operation_result

            if fallback_operation_result["status"] == "success":
                fallback_result["final_status"] = "success_fallback"
                fallback_result["data_source"] = "fallback"
                logger.info(
                    f"Fallback database operation succeeded on '{fallback_database}'"
                )
                return fallback_result
            else:
                logger.error(
                    f"Fallback database operation also failed on '{fallback_database}'"
                )

        except Exception as fallback_error:
            logger.error(
                f"Fallback database operation failed on '{fallback_database}': {fallback_error}"
            )
            fallback_result["fallback_attempt"] = {
                "status": "error",
                "error": str(fallback_error),
                "database_name": fallback_database,
            }

    # Both primary and fallback failed
    fallback_result["final_status"] = "failed"
    fallback_result["data_source"] = None

    logger.error(
        f"Both primary and fallback database operations failed for {operation_type}"
    )
    return fallback_result


@task
def log_error_for_monitoring(
    error_details: dict[str, Any],
    database_name: str,
    flow_name: str,
    severity: str = "error",
) -> dict[str, Any]:
    """
    Log error details to database for monitoring and alerting.

    Args:
        error_details: Dictionary containing error information
        database_name: Database name where error occurred
        flow_name: Name of the flow where error occurred
        severity: Error severity level (info, warning, error, critical)

    Returns:
        Dictionary with logging results
    """
    logger = get_run_logger()

    try:
        # Use a different database for error logging to avoid circular issues
        error_log_db = "rpa_db"  # Assume this is our primary logging database

        with DatabaseManager(error_log_db) as db:
            # Insert error log entry
            log_query = """
            INSERT INTO flow_execution_logs (
                flow_name, flow_run_id, database_name, execution_start, execution_end,
                execution_duration_ms, status, records_processed, records_successful,
                records_failed, database_operations, metadata
            ) VALUES (
                :flow_name, :flow_run_id, :database_name, :execution_start, :execution_end,
                :execution_duration_ms, :status, :records_processed, :records_successful,
                :records_failed, :database_operations, :metadata
            )
            """

            log_params = {
                "flow_name": flow_name,
                "flow_run_id": f"error-log-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "database_name": database_name,
                "execution_start": datetime.now(),
                "execution_end": datetime.now(),
                "execution_duration_ms": error_details.get("duration_ms", 0),
                "status": "error",
                "records_processed": 0,
                "records_successful": 0,
                "records_failed": 1,
                "database_operations": 1,
                "metadata": json.dumps(
                    {
                        "error_details": error_details,
                        "severity": severity,
                        "error_type": error_details.get("error_type", "unknown"),
                        "logged_at": datetime.now().isoformat(),
                    }
                ),
            }

            db.execute_query(log_query, log_params)

            logger.info(
                f"Error logged to monitoring database for flow '{flow_name}' on database '{database_name}'"
            )

            return {
                "status": "logged",
                "log_database": error_log_db,
                "severity": severity,
                "timestamp": datetime.now().isoformat(),
            }

    except Exception as log_error:
        logger.error(f"Failed to log error to monitoring database: {log_error}")

        # Fallback: at least log to Prefect logs
        logger.error(
            f"MONITORING FALLBACK - Original error details: {json.dumps(error_details, default=str)}"
        )

        return {
            "status": "fallback_logged",
            "error": str(log_error),
            "timestamp": datetime.now().isoformat(),
        }


@task
def implement_circuit_breaker(
    database_name: str,
    operation_type: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 300,
) -> dict[str, Any]:
    """
    Implement circuit breaker pattern for database operations.

    Args:
        database_name: Name of the database
        operation_type: Type of operation to check
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery

    Returns:
        Dictionary with circuit breaker status
    """
    logger = get_run_logger()

    # In a real implementation, this would use persistent storage (Redis, database, etc.)
    # For this example, we'll simulate circuit breaker logic

    circuit_status = {
        "database_name": database_name,
        "operation_type": operation_type,
        "circuit_state": "closed",  # closed, open, half_open
        "failure_count": 0,
        "last_failure_time": None,
        "can_proceed": True,
        "recommendation": "proceed",
    }

    try:
        with DatabaseManager(database_name) as db:
            # Check recent failure rate from logs
            failure_check_query = """
            SELECT
                COUNT(*) as total_operations,
                COUNT(CASE WHEN status != 'completed' THEN 1 END) as failed_operations,
                MAX(execution_start) as last_operation_time
            FROM flow_execution_logs
            WHERE database_name = :database_name
            AND execution_start >= NOW() - INTERVAL '15 minutes'
            """

            failure_stats = db.execute_query(
                failure_check_query, {"database_name": database_name}
            )

            if failure_stats:
                stats = failure_stats[0]
                total_ops = stats["total_operations"]
                failed_ops = stats["failed_operations"]

                circuit_status["failure_count"] = failed_ops
                circuit_status["total_recent_operations"] = total_ops

                # Determine circuit state
                if failed_ops >= failure_threshold:
                    circuit_status["circuit_state"] = "open"
                    circuit_status["can_proceed"] = False
                    circuit_status["recommendation"] = (
                        f"circuit_open_due_to_{failed_ops}_failures"
                    )

                    logger.warning(
                        f"Circuit breaker OPEN for database '{database_name}': {failed_ops} failures in last 15 minutes"
                    )

                elif failed_ops > 0 and total_ops > 0:
                    failure_rate = (failed_ops / total_ops) * 100
                    if failure_rate > 50:  # More than 50% failure rate
                        circuit_status["circuit_state"] = "half_open"
                        circuit_status["can_proceed"] = True
                        circuit_status["recommendation"] = (
                            f"proceed_with_caution_{failure_rate:.1f}%_failure_rate"
                        )

                        logger.warning(
                            f"Circuit breaker HALF-OPEN for database '{database_name}': {failure_rate:.1f}% failure rate"
                        )
                    else:
                        logger.info(
                            f"Circuit breaker CLOSED for database '{database_name}': {failure_rate:.1f}% failure rate (acceptable)"
                        )
                else:
                    logger.info(
                        f"Circuit breaker CLOSED for database '{database_name}': no recent failures"
                    )

            return circuit_status

    except Exception as e:
        logger.error(
            f"Circuit breaker check failed for database '{database_name}': {e}"
        )

        # Fail safe: allow operations but log the issue
        circuit_status["circuit_state"] = "unknown"
        circuit_status["can_proceed"] = True
        circuit_status["recommendation"] = "proceed_circuit_check_failed"
        circuit_status["error"] = str(e)

        return circuit_status


def _classify_database_error(error: Exception) -> str:
    """
    Classify database errors for appropriate handling.

    Args:
        error: Exception that occurred

    Returns:
        String classification of error type
    """
    error_message = str(error).lower()

    # Connection-related errors
    if any(
        keyword in error_message
        for keyword in ["connection", "connect", "network", "timeout"]
    ):
        return "connection_error"

    # Authentication/authorization errors
    if any(
        keyword in error_message
        for keyword in ["authentication", "permission", "access denied", "unauthorized"]
    ):
        return "auth_error"

    # SQL syntax or constraint errors
    if any(
        keyword in error_message
        for keyword in [
            "syntax",
            "constraint",
            "foreign key",
            "unique",
            "check constraint",
        ]
    ):
        return "sql_error"

    # Resource exhaustion
    if any(
        keyword in error_message
        for keyword in ["pool", "limit", "resource", "memory", "disk"]
    ):
        return "resource_error"

    # Transaction-related errors
    if any(
        keyword in error_message for keyword in ["transaction", "deadlock", "rollback"]
    ):
        return "transaction_error"

    # Migration-related errors
    if any(keyword in error_message for keyword in ["migration", "schema", "version"]):
        return "migration_error"

    return "unknown_error"


@flow(
    name="production-error-handling-example",
    task_runner=ConcurrentTaskRunner(),
    description="Example flow demonstrating comprehensive error handling for production DatabaseManager usage",
)
def production_error_handling_flow(
    primary_database: str = "rpa_db",
    fallback_database: Optional[str] = None,
    simulate_errors: bool = False,
    enable_circuit_breaker: bool = True,
) -> dict[str, Any]:
    """
    Demonstrate comprehensive error handling patterns for production DatabaseManager usage.

    This flow shows how to:
    1. Implement robust error handling with retries
    2. Use fallback databases for high availability
    3. Implement circuit breaker patterns
    4. Log errors for monitoring and alerting
    5. Handle different types of database errors appropriately
    6. Provide graceful degradation strategies

    Args:
        primary_database: Primary database name
        fallback_database: Fallback database name (optional)
        simulate_errors: Whether to simulate error conditions for testing
        enable_circuit_breaker: Whether to use circuit breaker pattern

    Returns:
        Dictionary containing comprehensive error handling results
    """
    logger = get_run_logger()
    logger.info("Starting production error handling example flow")

    execution_results = {
        "flow_execution": {
            "status": "unknown",
            "execution_time": datetime.now().isoformat(),
            "primary_database": primary_database,
            "fallback_database": fallback_database,
            "error_simulation": simulate_errors,
            "circuit_breaker_enabled": enable_circuit_breaker,
        },
        "operations": [],
        "error_handling": {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "fallback_operations": 0,
            "circuit_breaker_activations": 0,
        },
        "errors_logged": [],
    }

    try:
        # Step 1: Check circuit breaker status (if enabled)
        circuit_status = None
        if enable_circuit_breaker:
            logger.info("Step 1: Checking circuit breaker status")
            circuit_status = implement_circuit_breaker(primary_database, "general")

            if not circuit_status.get("can_proceed", True):
                logger.error(
                    f"Circuit breaker is OPEN for database '{primary_database}', aborting flow"
                )
                execution_results["flow_execution"]["status"] = "aborted_circuit_open"
                execution_results["circuit_breaker_status"] = circuit_status
                return execution_results

        # Step 2: Perform various database operations with error handling
        logger.info(
            "Step 2: Performing database operations with comprehensive error handling"
        )

        operations_to_test = [
            {
                "name": "health_check_query",
                "type": "select",
                "query": "SELECT 1 as health_check, NOW() as current_time",
                "params": None,
                "critical": True,
            },
            {
                "name": "count_processed_surveys",
                "type": "select",
                "query": "SELECT COUNT(*) as survey_count FROM processed_surveys WHERE processed_at >= NOW() - INTERVAL '24 hours'",
                "params": None,
                "critical": False,
            },
            {
                "name": "insert_test_record",
                "type": "insert",
                "query": """INSERT INTO flow_execution_logs
                           (flow_name, flow_run_id, database_name, execution_start, status, records_processed, metadata)
                           VALUES (:flow_name, :flow_run_id, :database_name, :execution_start, :status, :records_processed, :metadata)""",
                "params": {
                    "flow_name": "production-error-handling-example",
                    "flow_run_id": f"error-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                    "database_name": primary_database,
                    "execution_start": datetime.now(),
                    "status": "running",
                    "records_processed": 0,
                    "metadata": json.dumps(
                        {"test_operation": True, "error_simulation": simulate_errors}
                    ),
                },
                "critical": False,
            },
        ]

        # Add error simulation operations if requested
        if simulate_errors:
            operations_to_test.extend(
                [
                    {
                        "name": "simulate_syntax_error",
                        "type": "select",
                        "query": "SELECT * FROM non_existent_table_xyz",  # This will fail
                        "params": None,
                        "critical": False,
                    },
                    {
                        "name": "simulate_timeout",
                        "type": "select_with_timeout",
                        "query": "SELECT pg_sleep(2)",  # This might timeout with short timeout
                        "params": None,
                        "critical": False,
                    },
                ]
            )

        # Execute operations with error handling
        for operation in operations_to_test:
            try:
                logger.info(f"Executing operation: {operation['name']}")

                # Try primary database with fallback
                if fallback_database and not operation["critical"]:
                    # Use fallback strategy for non-critical operations
                    operation_result = handle_database_error_with_fallback(
                        primary_database=primary_database,
                        fallback_database=fallback_database,
                        operation_type=operation["type"],
                        query=operation["query"],
                        params=operation["params"],
                    )

                    if operation_result["final_status"] == "success_fallback":
                        execution_results["error_handling"]["fallback_operations"] += 1

                else:
                    # Direct operation with retry logic
                    operation_result = robust_database_operation(
                        operation_type=operation["type"],
                        database_name=primary_database,
                        query=operation["query"],
                        params=operation["params"],
                        critical=operation["critical"],
                    )

                execution_results["operations"].append(
                    {"operation_name": operation["name"], "result": operation_result}
                )

                # Update counters
                execution_results["error_handling"]["total_operations"] += 1

                if (
                    hasattr(operation_result, "get")
                    and operation_result.get("status") == "success"
                ) or (
                    hasattr(operation_result, "get")
                    and operation_result.get("final_status", "").startswith("success")
                ):
                    execution_results["error_handling"]["successful_operations"] += 1
                else:
                    execution_results["error_handling"]["failed_operations"] += 1

            except DatabaseOperationError as db_error:
                logger.error(
                    f"Critical database operation failed: {operation['name']} - {db_error}"
                )

                # Log error for monitoring
                error_log_result = log_error_for_monitoring(
                    error_details={
                        "operation_name": operation["name"],
                        "error_message": str(db_error),
                        "error_type": db_error.error_type,
                        "database_name": db_error.database_name,
                        "operation_type": db_error.operation,
                    },
                    database_name=primary_database,
                    flow_name="production-error-handling-example",
                    severity="critical",
                )

                execution_results["errors_logged"].append(error_log_result)
                execution_results["error_handling"]["total_operations"] += 1
                execution_results["error_handling"]["failed_operations"] += 1

                # For critical operations, this might abort the flow
                if operation["critical"]:
                    logger.error("Critical operation failed, aborting flow")
                    execution_results["flow_execution"]["status"] = (
                        "aborted_critical_failure"
                    )
                    return execution_results

            except Exception as general_error:
                logger.error(
                    f"Unexpected error in operation {operation['name']}: {general_error}"
                )

                # Log unexpected errors
                error_log_result = log_error_for_monitoring(
                    error_details={
                        "operation_name": operation["name"],
                        "error_message": str(general_error),
                        "error_type": "unexpected_error",
                        "database_name": primary_database,
                    },
                    database_name=primary_database,
                    flow_name="production-error-handling-example",
                    severity="error",
                )

                execution_results["errors_logged"].append(error_log_result)
                execution_results["error_handling"]["total_operations"] += 1
                execution_results["error_handling"]["failed_operations"] += 1

        # Step 3: Final circuit breaker check
        if enable_circuit_breaker:
            logger.info("Step 3: Final circuit breaker status check")
            final_circuit_status = implement_circuit_breaker(
                primary_database, "general"
            )
            execution_results["final_circuit_breaker_status"] = final_circuit_status

        # Determine final flow status
        total_ops = execution_results["error_handling"]["total_operations"]
        successful_ops = execution_results["error_handling"]["successful_operations"]

        if total_ops == 0:
            execution_results["flow_execution"]["status"] = "no_operations"
        elif successful_ops == total_ops:
            execution_results["flow_execution"]["status"] = "completed_success"
        elif successful_ops > 0:
            execution_results["flow_execution"]["status"] = "completed_partial_success"
        else:
            execution_results["flow_execution"]["status"] = "completed_all_failed"

        logger.info(
            f"Production error handling flow completed: {successful_ops}/{total_ops} operations successful"
        )
        return execution_results

    except Exception as e:
        logger.error(f"Production error handling flow failed: {e}")

        execution_results["flow_execution"]["status"] = "failed"
        execution_results["flow_execution"]["error"] = str(e)

        # Try to log this critical error
        try:
            critical_error_log = log_error_for_monitoring(
                error_details={
                    "flow_error": str(e),
                    "error_type": "flow_failure",
                    "database_name": primary_database,
                },
                database_name=primary_database,
                flow_name="production-error-handling-example",
                severity="critical",
            )
            execution_results["errors_logged"].append(critical_error_log)
        except Exception as e:
            logger.error(
                f"Failed to log critical flow error to monitoring database: {e}"
            )

        raise RuntimeError(f"Flow execution failed: {e}") from e


if __name__ == "__main__":
    # Run the production error handling example
    try:
        result = production_error_handling_flow(simulate_errors=True)
        print("\n" + "=" * 60)
        print("PRODUCTION ERROR HANDLING EXAMPLE COMPLETED")
        print("=" * 60)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"\nFlow execution failed: {e}")
