"""
Example flow demonstrating health check integration for flow prerequisite validation.

This example shows how to:
1. Perform comprehensive health checks before flow execution
2. Validate database prerequisites and dependencies
3. Handle different health check scenarios (healthy, degraded, unhealthy)
4. Implement health check monitoring and alerting
5. Create reusable health check tasks for production flows
"""

import json
from datetime import datetime
from typing import Any, Optional

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from core.database import DatabaseManager


@task
def comprehensive_database_health_check(database_name: str) -> dict[str, Any]:
    """
    Perform comprehensive health check on a database including advanced diagnostics.

    Args:
        database_name: Name of the database to check

    Returns:
        Dictionary with detailed health check results
    """
    logger = get_run_logger()
    logger.info(f"Performing comprehensive health check on database '{database_name}'")

    try:
        with DatabaseManager(database_name) as db:
            # Get basic health check
            health_status = db.health_check()

            # Get connection pool status
            pool_status = db.get_pool_status()

            # Get migration status
            migration_status = db.get_migration_status()

            # Perform additional diagnostic queries
            diagnostic_results = {}

            # Check table counts (if database is healthy enough)
            if health_status.get('connection', False):
                try:
                    # Check if we have expected tables
                    table_check_query = """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                    """

                    tables = db.execute_query(table_check_query)
                    diagnostic_results['available_tables'] = [t['table_name'] for t in tables]
                    diagnostic_results['table_count'] = len(tables)

                    # Check record counts for key tables
                    if 'processed_surveys' in diagnostic_results['available_tables']:
                        survey_count_query = "SELECT COUNT(*) as count FROM processed_surveys"
                        survey_count = db.execute_query(survey_count_query)
                        diagnostic_results['processed_surveys_count'] = survey_count[0]['count']

                    if 'customer_orders' in diagnostic_results['available_tables']:
                        orders_count_query = "SELECT COUNT(*) as count FROM customer_orders"
                        orders_count = db.execute_query(orders_count_query)
                        diagnostic_results['customer_orders_count'] = orders_count[0]['count']

                    if 'flow_execution_logs' in diagnostic_results['available_tables']:
                        logs_count_query = "SELECT COUNT(*) as count FROM flow_execution_logs WHERE execution_start >= NOW() - INTERVAL '24 hours'"
                        logs_count = db.execute_query(logs_count_query)
                        diagnostic_results['recent_flow_executions'] = logs_count[0]['count']

                except Exception as diag_error:
                    logger.warning(f"Diagnostic queries failed for '{database_name}': {diag_error}")
                    diagnostic_results['diagnostic_error'] = str(diag_error)

            # Compile comprehensive results
            comprehensive_results = {
                'database_name': database_name,
                'timestamp': datetime.now().isoformat(),
                'basic_health': health_status,
                'connection_pool': pool_status,
                'migration_status': migration_status,
                'diagnostics': diagnostic_results,
                'overall_status': _determine_overall_health_status(health_status, pool_status, migration_status)
            }

            logger.info(f"Comprehensive health check completed for '{database_name}': {comprehensive_results['overall_status']}")
            return comprehensive_results

    except Exception as e:
        logger.error(f"Comprehensive health check failed for '{database_name}': {e}")
        return {
            'database_name': database_name,
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'critical_failure',
            'error': str(e),
            'basic_health': {'status': 'unhealthy', 'error': str(e)},
            'connection_pool': None,
            'migration_status': None,
            'diagnostics': {}
        }


@task
def validate_flow_prerequisites(
    required_databases: list[str],
    required_tables: Optional[dict[str, list[str]]] = None,
    minimum_health_level: str = "healthy"
) -> dict[str, Any]:
    """
    Validate that all flow prerequisites are met before execution.

    Args:
        required_databases: List of database names that must be available
        required_tables: Optional dict mapping database names to required table lists
        minimum_health_level: Minimum acceptable health level (healthy, degraded, unhealthy)

    Returns:
        Dictionary with prerequisite validation results

    Raises:
        RuntimeError: If critical prerequisites are not met
    """
    logger = get_run_logger()
    logger.info(f"Validating flow prerequisites for {len(required_databases)} databases")

    validation_results = {
        'validation_timestamp': datetime.now().isoformat(),
        'required_databases': required_databases,
        'required_tables': required_tables or {},
        'minimum_health_level': minimum_health_level,
        'database_results': {},
        'overall_status': 'unknown',
        'critical_issues': [],
        'warnings': []
    }

    health_level_priority = {'healthy': 3, 'degraded': 2, 'unhealthy': 1, 'critical_failure': 0}
    min_priority = health_level_priority.get(minimum_health_level, 3)

    critical_failures = []
    warnings = []

    for db_name in required_databases:
        try:
            logger.info(f"Validating prerequisites for database '{db_name}'")

            # Get comprehensive health check
            health_results = comprehensive_database_health_check(db_name)
            validation_results['database_results'][db_name] = health_results

            # Check health level
            db_status = health_results.get('overall_status', 'critical_failure')
            db_priority = health_level_priority.get(db_status, 0)

            if db_priority < min_priority:
                critical_failures.append(f"Database '{db_name}' health level '{db_status}' below minimum '{minimum_health_level}'")
            elif db_status == 'degraded':
                warnings.append(f"Database '{db_name}' is degraded but meets minimum requirements")

            # Check required tables if specified
            if required_tables and db_name in required_tables:
                required_table_list = required_tables[db_name]
                available_tables = health_results.get('diagnostics', {}).get('available_tables', [])

                missing_tables = [table for table in required_table_list if table not in available_tables]
                if missing_tables:
                    critical_failures.append(f"Database '{db_name}' missing required tables: {missing_tables}")
                else:
                    logger.info(f"All required tables present in database '{db_name}': {required_table_list}")

            # Check migration status
            migration_status = health_results.get('migration_status', {})
            pending_migrations = migration_status.get('pending_migrations', [])
            if pending_migrations:
                warnings.append(f"Database '{db_name}' has {len(pending_migrations)} pending migrations")

        except Exception as e:
            logger.error(f"Prerequisite validation failed for database '{db_name}': {e}")
            critical_failures.append(f"Failed to validate database '{db_name}': {str(e)}")
            validation_results['database_results'][db_name] = {
                'database_name': db_name,
                'overall_status': 'critical_failure',
                'error': str(e)
            }

    # Determine overall validation status
    validation_results['critical_issues'] = critical_failures
    validation_results['warnings'] = warnings

    if critical_failures:
        validation_results['overall_status'] = 'failed'
        logger.error(f"Flow prerequisite validation failed: {len(critical_failures)} critical issues")
        for issue in critical_failures:
            logger.error(f"  - {issue}")
    else:
        validation_results['overall_status'] = 'passed'
        logger.info("All flow prerequisites validated successfully")

        if warnings:
            logger.warning(f"Validation passed with {len(warnings)} warnings:")
            for warning in warnings:
                logger.warning(f"  - {warning}")

    return validation_results


@task
def monitor_database_health_trends(database_names: list[str], hours_back: int = 24) -> dict[str, Any]:
    """
    Monitor database health trends over time using historical execution logs.

    Args:
        database_names: List of database names to monitor
        hours_back: Number of hours of history to analyze

    Returns:
        Dictionary with health trend analysis
    """
    logger = get_run_logger()
    logger.info(f"Monitoring health trends for {len(database_names)} databases over {hours_back} hours")

    trend_results = {
        'analysis_timestamp': datetime.now().isoformat(),
        'hours_analyzed': hours_back,
        'database_trends': {},
        'overall_trends': {
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'avg_response_time_ms': 0,
            'health_degradation_events': 0
        }
    }

    total_executions = 0
    successful_executions = 0
    failed_executions = 0
    all_response_times = []

    for db_name in database_names:
        try:
            with DatabaseManager(db_name) as db:
                # Query execution logs for trends
                trend_query = """
                SELECT
                    DATE_TRUNC('hour', execution_start) as hour,
                    COUNT(*) as execution_count,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as successful_count,
                    COUNT(CASE WHEN status != 'completed' THEN 1 END) as failed_count,
                    AVG(execution_duration_ms) as avg_duration_ms,
                    AVG(CAST(metadata->>'health_check_response_time_ms' AS DECIMAL)) as avg_health_response_ms
                FROM flow_execution_logs
                WHERE database_name = :database_name
                AND execution_start >= NOW() - INTERVAL ':hours_back hours'
                GROUP BY DATE_TRUNC('hour', execution_start)
                ORDER BY hour DESC
                """

                trend_data = db.execute_query(trend_query, {
                    'database_name': db_name,
                    'hours_back': hours_back
                })

                # Calculate database-specific metrics
                db_total_executions = sum(row['execution_count'] for row in trend_data)
                db_successful_executions = sum(row['successful_count'] for row in trend_data)
                db_failed_executions = sum(row['failed_count'] for row in trend_data)

                db_response_times = [
                    row['avg_health_response_ms'] for row in trend_data
                    if row['avg_health_response_ms'] is not None
                ]

                db_avg_response_time = sum(db_response_times) / len(db_response_times) if db_response_times else 0

                # Detect health degradation (response times > 1000ms)
                degradation_events = len([rt for rt in db_response_times if rt > 1000])

                trend_results['database_trends'][db_name] = {
                    'total_executions': db_total_executions,
                    'successful_executions': db_successful_executions,
                    'failed_executions': db_failed_executions,
                    'success_rate': (db_successful_executions / db_total_executions * 100) if db_total_executions > 0 else 0,
                    'avg_response_time_ms': round(db_avg_response_time, 2),
                    'degradation_events': degradation_events,
                    'hourly_data': trend_data
                }

                # Aggregate for overall trends
                total_executions += db_total_executions
                successful_executions += db_successful_executions
                failed_executions += db_failed_executions
                all_response_times.extend(db_response_times)

                logger.info(f"Database '{db_name}' trends: {db_successful_executions}/{db_total_executions} successful, avg response: {db_avg_response_time:.2f}ms")

        except Exception as e:
            logger.error(f"Failed to analyze trends for database '{db_name}': {e}")
            trend_results['database_trends'][db_name] = {
                'error': str(e),
                'total_executions': 0,
                'successful_executions': 0,
                'failed_executions': 0
            }

    # Calculate overall trends
    trend_results['overall_trends'] = {
        'total_executions': total_executions,
        'successful_executions': successful_executions,
        'failed_executions': failed_executions,
        'overall_success_rate': (successful_executions / total_executions * 100) if total_executions > 0 else 0,
        'avg_response_time_ms': round(sum(all_response_times) / len(all_response_times), 2) if all_response_times else 0,
        'health_degradation_events': sum(
            db_trends.get('degradation_events', 0)
            for db_trends in trend_results['database_trends'].values()
            if isinstance(db_trends, dict) and 'degradation_events' in db_trends
        )
    }

    logger.info(f"Overall health trends: {successful_executions}/{total_executions} successful executions")
    return trend_results


def _determine_overall_health_status(health_status: dict, pool_status: dict, migration_status: dict) -> str:
    """
    Determine overall health status based on multiple factors.

    Args:
        health_status: Basic health check results
        pool_status: Connection pool status
        migration_status: Migration status

    Returns:
        Overall health status string
    """
    basic_status = health_status.get('status', 'unhealthy')

    # Check for critical issues
    if basic_status == 'unhealthy':
        return 'critical_failure'

    # Check pool utilization
    if pool_status:
        pool_utilization = pool_status.get('utilization_percentage', 0)
        if pool_utilization > 90:
            return 'degraded'  # High pool utilization

    # Check for pending migrations
    if migration_status:
        pending_migrations = migration_status.get('pending_migrations', [])
        if len(pending_migrations) > 5:
            return 'degraded'  # Many pending migrations

    return basic_status


@flow(
    name="health-check-integration-example",
    task_runner=ConcurrentTaskRunner(),
    description="Example flow demonstrating health check integration for prerequisite validation"
)
def health_check_integration_flow(
    target_databases: Optional[list[str]] = None,
    minimum_health_level: str = "healthy",
    perform_trend_analysis: bool = True,
    fail_on_prerequisites: bool = True
) -> dict[str, Any]:
    """
    Demonstrate comprehensive health check integration for flow prerequisite validation.

    This flow shows how to:
    1. Perform comprehensive health checks on multiple databases
    2. Validate flow prerequisites before execution
    3. Monitor database health trends over time
    4. Handle different health scenarios appropriately
    5. Provide detailed health reporting for operations teams

    Args:
        target_databases: List of databases to check (default: ['rpa_db', 'SurveyHub'])
        minimum_health_level: Minimum acceptable health level
        perform_trend_analysis: Whether to perform trend analysis
        fail_on_prerequisites: Whether to fail if prerequisites aren't met

    Returns:
        Dictionary containing comprehensive health check results
    """
    logger = get_run_logger()
    logger.info("Starting health check integration example flow")

    # Default databases if not specified
    if target_databases is None:
        target_databases = ['rpa_db']  # Only use rpa_db as SurveyHub might not be configured

    # Define required tables for each database
    required_tables = {
        'rpa_db': ['processed_surveys', 'customer_orders', 'flow_execution_logs'],
        'SurveyHub': []  # Read-only database, no specific table requirements
    }

    try:
        # Step 1: Perform comprehensive health checks on all databases
        logger.info(f"Step 1: Performing comprehensive health checks on {len(target_databases)} databases")
        health_check_results = {}

        for db_name in target_databases:
            health_check_results[db_name] = comprehensive_database_health_check(db_name)

        # Step 2: Validate flow prerequisites
        logger.info("Step 2: Validating flow prerequisites")
        prerequisite_results = validate_flow_prerequisites(
            required_databases=target_databases,
            required_tables=required_tables,
            minimum_health_level=minimum_health_level
        )

        # Step 3: Monitor health trends (if requested)
        trend_results = None
        if perform_trend_analysis:
            logger.info("Step 3: Analyzing database health trends")
            trend_results = monitor_database_health_trends(target_databases, hours_back=24)
        else:
            logger.info("Step 3: Skipping trend analysis (not requested)")

        # Step 4: Determine if flow should proceed
        can_proceed = prerequisite_results.get('overall_status') == 'passed'

        if not can_proceed and fail_on_prerequisites:
            error_msg = f"Flow prerequisites not met: {len(prerequisite_results.get('critical_issues', []))} critical issues"
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        elif not can_proceed:
            logger.warning("Flow prerequisites not met, but continuing due to fail_on_prerequisites=False")
        else:
            logger.info("All flow prerequisites validated successfully, flow can proceed")

        # Compile comprehensive results
        complete_results = {
            'flow_execution': {
                'status': 'completed',
                'execution_time': datetime.now().isoformat(),
                'can_proceed': can_proceed,
                'databases_checked': target_databases,
                'minimum_health_level': minimum_health_level
            },
            'health_checks': health_check_results,
            'prerequisite_validation': prerequisite_results,
            'trend_analysis': trend_results,
            'recommendations': _generate_health_recommendations(
                health_check_results,
                prerequisite_results,
                trend_results
            )
        }

        logger.info("Health check integration flow completed successfully")
        return complete_results

    except Exception as e:
        logger.error(f"Health check integration flow failed: {e}")
        raise RuntimeError(f"Flow execution failed: {e}") from e


def _generate_health_recommendations(
    health_results: dict[str, Any],
    prerequisite_results: dict[str, Any],
    trend_results: Optional[dict[str, Any]]
) -> list[str]:
    """
    Generate operational recommendations based on health check results.

    Args:
        health_results: Health check results
        prerequisite_results: Prerequisite validation results
        trend_results: Trend analysis results (optional)

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Check for unhealthy databases
    for db_name, health_data in health_results.items():
        status = health_data.get('overall_status', 'unknown')

        if status == 'critical_failure':
            recommendations.append(f"CRITICAL: Database '{db_name}' requires immediate attention - connection failed")
        elif status == 'degraded':
            response_time = health_data.get('basic_health', {}).get('response_time_ms', 0)
            if response_time > 1000:
                recommendations.append(f"WARNING: Database '{db_name}' has slow response times ({response_time}ms) - investigate performance")

        # Check pool utilization
        pool_data = health_data.get('connection_pool', {})
        utilization = pool_data.get('utilization_percentage', 0)
        if utilization > 80:
            recommendations.append(f"WARNING: Database '{db_name}' connection pool utilization is high ({utilization}%) - consider increasing pool size")

        # Check pending migrations
        migration_data = health_data.get('migration_status', {})
        pending_migrations = migration_data.get('pending_migrations', [])
        if len(pending_migrations) > 0:
            recommendations.append(f"INFO: Database '{db_name}' has {len(pending_migrations)} pending migrations - schedule maintenance window")

    # Check trend analysis
    if trend_results:
        overall_trends = trend_results.get('overall_trends', {})
        success_rate = overall_trends.get('overall_success_rate', 100)

        if success_rate < 95:
            recommendations.append(f"WARNING: Overall success rate is {success_rate:.1f}% - investigate recent failures")

        degradation_events = overall_trends.get('health_degradation_events', 0)
        if degradation_events > 5:
            recommendations.append(f"WARNING: {degradation_events} health degradation events detected in last 24 hours - monitor database performance")

    # Check critical issues
    critical_issues = prerequisite_results.get('critical_issues', [])
    if critical_issues:
        recommendations.append(f"CRITICAL: {len(critical_issues)} prerequisite failures must be resolved before production deployment")

    if not recommendations:
        recommendations.append("INFO: All health checks passed - systems are operating normally")

    return recommendations


if __name__ == "__main__":
    # Run the health check integration example
    try:
        result = health_check_integration_flow()
        print("\n" + "="*60)
        print("HEALTH CHECK INTEGRATION EXAMPLE COMPLETED")
        print("="*60)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"\nFlow execution failed: {e}")
