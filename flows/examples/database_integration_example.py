"""
Example flow demonstrating DatabaseManager integration with multiple databases.

This example shows how to:
1. Use DatabaseManager with multiple databases (PostgreSQL and SQL Server)
2. Perform health checks before processing
3. Execute queries and transactions across different databases
4. Handle errors and logging in production-ready flows
5. Integrate migration management into flow execution
"""

import json
from datetime import datetime
from typing import Any

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from core.database import DatabaseManager


@task
def perform_database_health_checks(database_names: list[str]) -> dict[str, Any]:
    """
    Perform health checks on all required databases before processing.

    Args:
        database_names: List of database names to check

    Returns:
        Dictionary with health check results for each database

    Raises:
        RuntimeError: If any critical database is unhealthy
    """
    logger = get_run_logger()
    logger.info(f"Performing health checks on {len(database_names)} databases")

    health_results = {}
    unhealthy_databases = []

    for db_name in database_names:
        try:
            with DatabaseManager(db_name) as db:
                health_status = db.health_check()
                health_results[db_name] = health_status

                if health_status["status"] == "unhealthy":
                    unhealthy_databases.append(db_name)
                    logger.error(f"Database '{db_name}' is unhealthy: {health_status.get('error', 'Unknown error')}")
                elif health_status["status"] == "degraded":
                    logger.warning(f"Database '{db_name}' is degraded (response time: {health_status.get('response_time_ms', 'unknown')}ms)")
                else:
                    logger.info(f"Database '{db_name}' is healthy (response time: {health_status.get('response_time_ms', 'unknown')}ms)")

        except Exception as e:
            logger.error(f"Health check failed for database '{db_name}': {e}")
            health_results[db_name] = {
                "status": "unhealthy",
                "error": str(e),
                "database_name": db_name
            }
            unhealthy_databases.append(db_name)

    # Fail fast if critical databases are unhealthy
    if unhealthy_databases:
        error_msg = f"Critical databases are unhealthy: {', '.join(unhealthy_databases)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info("All database health checks passed")
    return health_results


@task
def run_database_migrations(database_names: list[str]) -> dict[str, Any]:
    """
    Run pending migrations on specified databases.

    Args:
        database_names: List of database names to migrate

    Returns:
        Dictionary with migration results for each database
    """
    logger = get_run_logger()
    logger.info(f"Running migrations on {len(database_names)} databases")

    migration_results = {}

    for db_name in database_names:
        try:
            with DatabaseManager(db_name) as db:
                # Check migration status before running
                status_before = db.get_migration_status()
                logger.info(f"Database '{db_name}' current version: {status_before.get('current_version', 'None')}")

                # Run migrations
                db.run_migrations()

                # Check status after running
                status_after = db.get_migration_status()

                migration_results[db_name] = {
                    "before": status_before,
                    "after": status_after,
                    "success": True
                }

                logger.info(f"Migrations completed for database '{db_name}'. New version: {status_after.get('current_version', 'None')}")

        except Exception as e:
            logger.error(f"Migration failed for database '{db_name}': {e}")
            migration_results[db_name] = {
                "success": False,
                "error": str(e)
            }
            # Continue with other databases even if one fails

    return migration_results


@task
def fetch_survey_data_from_source(survey_hub_db: str) -> list[dict[str, Any]]:
    """
    Fetch survey data from the source database (SQL Server).

    Args:
        survey_hub_db: Name of the survey hub database

    Returns:
        List of survey records
    """
    logger = get_run_logger()

    # Mock query - in real implementation this would query actual SurveyHub tables

    try:
        with DatabaseManager(survey_hub_db):
            logger.info(f"Fetching survey data from '{survey_hub_db}'")

            # In a real scenario, this would be a proper SurveyHub query
            # For demo purposes, we'll create mock data
            surveys = []
            for i in range(1, 11):
                surveys.append({
                    'survey_id': f'SURV-{i:03d}',
                    'customer_id': f'CUST-{i:03d}',
                    'customer_name': ['Alice Johnson', 'Bob Smith', 'Charlie Brown'][i % 3],
                    'survey_type': 'Customer Satisfaction' if i % 2 == 1 else 'Product Feedback',
                    'survey_date': datetime.now().isoformat()
                })

            logger.info(f"Fetched {len(surveys)} survey records from '{survey_hub_db}'")
            return surveys

    except Exception as e:
        logger.error(f"Failed to fetch survey data from '{survey_hub_db}': {e}")
        raise


@task
def process_and_store_surveys(surveys: list[dict[str, Any]], target_db: str) -> dict[str, Any]:
    """
    Process survey data and store results in the target database.

    Args:
        surveys: List of survey records to process
        target_db: Name of the target database for storing results

    Returns:
        Processing summary statistics
    """
    logger = get_run_logger()
    logger.info(f"Processing {len(surveys)} surveys for storage in '{target_db}'")

    processed_count = 0
    failed_count = 0
    processing_start = datetime.now()

    try:
        with DatabaseManager(target_db) as db:
            # Process surveys in batches using transactions
            batch_size = 5
            for i in range(0, len(surveys), batch_size):
                batch = surveys[i:i + batch_size]

                try:
                    # Prepare batch insert queries
                    queries = []
                    for survey in batch:
                        # Simulate processing logic
                        processing_status = 'completed' if survey['survey_id'][-1] != '3' else 'failed'
                        processing_duration = 1000 + (int(survey['survey_id'][-3:]) * 100)

                        query = """
                        INSERT INTO processed_surveys
                        (survey_id, customer_id, customer_name, survey_type, processing_status,
                         processed_at, processing_duration_ms, flow_run_id)
                        VALUES (:survey_id, :customer_id, :customer_name, :survey_type,
                                :processing_status, :processed_at, :processing_duration_ms, :flow_run_id)
                        """

                        params = {
                            'survey_id': survey['survey_id'],
                            'customer_id': survey['customer_id'],
                            'customer_name': survey['customer_name'],
                            'survey_type': survey['survey_type'],
                            'processing_status': processing_status,
                            'processed_at': datetime.now(),
                            'processing_duration_ms': processing_duration,
                            'flow_run_id': f'example-flow-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
                        }

                        queries.append((query, params))

                    # Execute batch as transaction
                    db.execute_transaction(queries)
                    processed_count += len(batch)
                    logger.info(f"Processed batch {i//batch_size + 1}: {len(batch)} surveys")

                except Exception as batch_error:
                    logger.error(f"Failed to process batch {i//batch_size + 1}: {batch_error}")
                    failed_count += len(batch)

            processing_end = datetime.now()
            processing_duration = (processing_end - processing_start).total_seconds() * 1000

            # Log execution summary to flow_execution_logs
            log_query = """
            INSERT INTO flow_execution_logs
            (flow_name, flow_run_id, database_name, execution_start, execution_end,
             execution_duration_ms, status, records_processed, records_successful,
             records_failed, database_operations, metadata)
            VALUES (:flow_name, :flow_run_id, :database_name, :execution_start,
                    :execution_end, :execution_duration_ms, :status, :records_processed,
                    :records_successful, :records_failed, :database_operations, :metadata)
            """

            log_params = {
                'flow_name': 'database-integration-example',
                'flow_run_id': f'example-flow-{datetime.now().strftime("%Y%m%d-%H%M%S")}',
                'database_name': target_db,
                'execution_start': processing_start,
                'execution_end': processing_end,
                'execution_duration_ms': int(processing_duration),
                'status': 'completed' if failed_count == 0 else 'partial_failure',
                'records_processed': len(surveys),
                'records_successful': processed_count,
                'records_failed': failed_count,
                'database_operations': len(surveys) + 1,  # +1 for this log entry
                'metadata': json.dumps({
                    'batch_size': batch_size,
                    'source_database': 'SurveyHub',
                    'target_database': target_db
                })
            }

            db.execute_query(log_query, log_params)

            summary = {
                'total_surveys': len(surveys),
                'processed_successfully': processed_count,
                'failed': failed_count,
                'processing_duration_ms': int(processing_duration),
                'batch_size': batch_size
            }

            logger.info(f"Survey processing completed: {processed_count} successful, {failed_count} failed")
            return summary

    except Exception as e:
        logger.error(f"Failed to process surveys in '{target_db}': {e}")
        raise


@task
def generate_processing_report(processing_summary: dict[str, Any], target_db: str) -> dict[str, Any]:
    """
    Generate a comprehensive processing report with database statistics.

    Args:
        processing_summary: Summary from survey processing
        target_db: Database to query for additional statistics

    Returns:
        Complete processing report
    """
    logger = get_run_logger()

    try:
        with DatabaseManager(target_db) as db:
            # Get processing statistics
            stats_query = """
            SELECT
                processing_status,
                COUNT(*) as count,
                AVG(processing_duration_ms) as avg_duration_ms,
                MIN(processing_duration_ms) as min_duration_ms,
                MAX(processing_duration_ms) as max_duration_ms
            FROM processed_surveys
            WHERE processed_at >= NOW() - INTERVAL '1 hour'
            GROUP BY processing_status
            """

            stats_results = db.execute_query(stats_query)

            # Get recent flow execution metrics
            flow_stats_query = """
            SELECT
                flow_name,
                COUNT(*) as execution_count,
                AVG(execution_duration_ms) as avg_execution_duration_ms,
                SUM(records_processed) as total_records_processed,
                SUM(records_successful) as total_records_successful,
                SUM(records_failed) as total_records_failed
            FROM flow_execution_logs
            WHERE execution_start >= NOW() - INTERVAL '24 hours'
            GROUP BY flow_name
            """

            flow_stats = db.execute_query(flow_stats_query)

            report = {
                'processing_summary': processing_summary,
                'database_statistics': stats_results,
                'flow_execution_metrics': flow_stats,
                'report_generated_at': datetime.now().isoformat(),
                'database_name': target_db
            }

            logger.info(f"Generated processing report with {len(stats_results)} status categories and {len(flow_stats)} flow metrics")
            return report

    except Exception as e:
        logger.error(f"Failed to generate processing report from '{target_db}': {e}")
        raise


@flow(
    name="database-integration-example",
    task_runner=ConcurrentTaskRunner(),
    description="Example flow demonstrating DatabaseManager integration with multiple databases"
)
def database_integration_example_flow(
    source_database: str = "SurveyHub",
    target_database: str = "rpa_db",
    run_migrations: bool = True,
    health_check_required: bool = True
) -> dict[str, Any]:
    """
    Example flow showing comprehensive DatabaseManager usage.

    This flow demonstrates:
    1. Health checking multiple databases
    2. Running migrations before processing
    3. Reading from one database (SQL Server)
    4. Processing and writing to another database (PostgreSQL)
    5. Comprehensive error handling and logging
    6. Transaction management and batch processing

    Args:
        source_database: Name of source database (default: SurveyHub)
        target_database: Name of target database (default: rpa_db)
        run_migrations: Whether to run migrations before processing
        health_check_required: Whether health checks are required

    Returns:
        Dictionary containing complete processing results and metrics
    """
    logger = get_run_logger()
    logger.info("Starting database integration example flow")

    databases_to_check = [source_database, target_database]

    try:
        # Step 1: Health checks (if required)
        health_results = None
        if health_check_required:
            logger.info("Step 1: Performing database health checks")
            health_results = perform_database_health_checks(databases_to_check)
        else:
            logger.info("Step 1: Skipping health checks (not required)")

        # Step 2: Run migrations (if requested)
        migration_results = None
        if run_migrations:
            logger.info("Step 2: Running database migrations")
            migration_results = run_database_migrations([target_database])  # Only migrate target DB
        else:
            logger.info("Step 2: Skipping migrations (not requested)")

        # Step 3: Fetch data from source database
        logger.info(f"Step 3: Fetching survey data from '{source_database}'")
        survey_data = fetch_survey_data_from_source(source_database)

        # Step 4: Process and store data in target database
        logger.info(f"Step 4: Processing and storing data in '{target_database}'")
        processing_summary = process_and_store_surveys(survey_data, target_database)

        # Step 5: Generate comprehensive report
        logger.info("Step 5: Generating processing report")
        final_report = generate_processing_report(processing_summary, target_database)

        # Compile complete results
        complete_results = {
            'flow_execution': {
                'status': 'completed',
                'execution_time': datetime.now().isoformat(),
                'source_database': source_database,
                'target_database': target_database
            },
            'health_checks': health_results,
            'migrations': migration_results,
            'processing_report': final_report
        }

        logger.info("Database integration example flow completed successfully")
        return complete_results

    except Exception as e:
        logger.error(f"Database integration example flow failed: {e}")

        # Return error information for debugging
        error_results = {
            'flow_execution': {
                'status': 'failed',
                'error': str(e),
                'execution_time': datetime.now().isoformat(),
                'source_database': source_database,
                'target_database': target_database
            },
            'health_checks': health_results,
            'migrations': migration_results if 'migration_results' in locals() else None
        }

        # Re-raise the exception after logging
        raise RuntimeError(f"Flow execution failed: {e}") from e


if __name__ == "__main__":
    # Run the example flow
    try:
        result = database_integration_example_flow()
        print("\n" + "="*50)
        print("DATABASE INTEGRATION EXAMPLE COMPLETED")
        print("="*50)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"\nFlow execution failed: {e}")
