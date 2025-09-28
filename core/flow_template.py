"""
Distributed flow template for standardized distributed processing patterns.

This module provides a reusable template for creating distributed Prefect flows
that use the DistributedProcessor for atomic record claiming and processing.
It includes module-level instances for performance optimization and standardized
error handling patterns.
"""

from typing import Any, Optional

from prefect import flow, get_run_logger, task

from core.config import ConfigManager
from core.database import DatabaseManager
from core.distributed import DistributedProcessor

# Module-level instances for performance optimization
# These are initialized once when the module is imported and reused across flow runs
config_manager = ConfigManager()
rpa_db_manager = DatabaseManager("rpa_db")
source_db_manager = DatabaseManager("SurveyHub")
processor = DistributedProcessor(rpa_db_manager, source_db_manager, config_manager)


@flow(name="distributed-processing-template")
def distributed_processing_flow(
    flow_name: str,
    batch_size: Optional[int] = None,
    business_logic_func: Optional[callable] = None
) -> dict[str, Any]:
    """
    Distributed processing flow template with health checks and record claiming.

    This template provides a standardized pattern for distributed flows that:
    1. Performs mandatory database health checks with fail-fast behavior
    2. Claims available records in batches using atomic operations
    3. Processes records in parallel using Prefect's .map() operation
    4. Generates comprehensive processing summaries

    Args:
        flow_name: Name of the flow for record claiming and logging
        batch_size: Maximum number of records to claim and process (uses config default if None)
        business_logic_func: Optional custom business logic function for processing records

    Returns:
        Dictionary containing processing summary with counts and status information

    Raises:
        RuntimeError: If database health check fails (fail-fast behavior)
        ValueError: If flow_name is empty or batch_size is invalid

    Example:
        # Basic usage with default business logic
        result = distributed_processing_flow("survey_processor", batch_size=50)

        # Usage with custom business logic
        def custom_logic(payload):
            return {"processed": True, "score": payload.get("rating", 0)}

        result = distributed_processing_flow(
            "custom_processor",
            batch_size=25,
            business_logic_func=custom_logic
        )
    """
    logger = get_run_logger()

    # Validate input parameters
    if not flow_name or not isinstance(flow_name, str):
        raise ValueError("flow_name must be a non-empty string")

    # Use configured default batch size if not provided
    if batch_size is None:
        batch_size = processor.config["default_batch_size"]
    elif not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError("batch_size must be a positive integer")

    logger.info(f"Starting distributed processing flow '{flow_name}' with batch_size: {batch_size}")

    # 1. Mandatory database health check with fail-fast behavior
    logger.info("Performing database health check before processing")
    health_status = processor.health_check()

    if health_status["status"] == "unhealthy":
        error_msg = f"Database health check failed: {health_status.get('error', 'Unknown error')}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    elif health_status["status"] == "degraded":
        logger.warning(f"Database health check shows degraded status: {health_status}")
    else:
        logger.info("Database health check passed - all systems healthy")

    # 2. Claim records from processing queue with retry logic
    logger.info(f"Claiming batch of {batch_size} records for flow '{flow_name}'")
    records = processor.claim_records_batch_with_retry(flow_name, batch_size)

    if not records:
        logger.info(f"No records available for processing in flow '{flow_name}'")
        return {
            "flow_name": flow_name,
            "batch_size": batch_size,
            "records_claimed": 0,
            "records_processed": 0,
            "records_completed": 0,
            "records_failed": 0,
            "message": "No records to process"
        }

    logger.info(f"Successfully claimed {len(records)} records for processing")

    # 3. Process records using Prefect .map() for parallel processing
    logger.info("Starting parallel record processing")

    if business_logic_func:
        # Use custom business logic function
        results = process_record_with_status_custom.map(records, business_logic_func=business_logic_func)
    else:
        # Use default business logic
        results = process_record_with_status.map(records)

    # 4. Generate processing summary
    summary = generate_processing_summary(results, flow_name, batch_size, len(records))

    logger.info(f"Distributed processing flow '{flow_name}' completed: {summary}")

    return summary


@task(name="process-record-with-status", retries=0)
def process_record_with_status(record: dict[str, Any]) -> dict[str, Any]:
    """
    Process individual record with status management and error handling.

    This task handles individual record processing with proper error isolation.
    Failed records are marked as failed without affecting other records in the batch.
    No Prefect-level retries are used to avoid conflicts with database retry logic.

    Args:
        record: Record dictionary containing id, payload, retry_count, and created_at

    Returns:
        Dictionary containing processing result with record_id, status, and result/error

    Note:
        This task does not re-raise exceptions to prevent Prefect retries from
        conflicting with the database-level retry counting mechanism.
    """
    logger = get_run_logger()
    record_id = record['id']

    logger.info(f"Processing record {record_id}")

    try:
        # Default business logic - can be overridden by custom implementations
        result = process_default_business_logic(record['payload'])

        # Mark record as completed in database with retry logic
        processor.mark_record_completed_with_retry(record_id, result)

        logger.info(f"Successfully processed record {record_id}")

        return {
            "record_id": record_id,
            "status": "completed",
            "result": result
        }

    except Exception as e:
        # Mark record as failed in database with retry logic
        error_message = str(e)
        processor.mark_record_failed_with_retry(record_id, error_message)

        logger.error(f"Failed to process record {record_id}: {error_message}")

        return {
            "record_id": record_id,
            "status": "failed",
            "error": error_message
        }
        # Note: Not re-raising to prevent Prefect retries conflicting with DB retry logic


@task(name="process-record-with-status-custom", retries=0)
def process_record_with_status_custom(
    record: dict[str, Any],
    business_logic_func: callable
) -> dict[str, Any]:
    """
    Process individual record with custom business logic and status management.

    This task allows injection of custom business logic while maintaining
    the same error handling and status management patterns as the default task.

    Args:
        record: Record dictionary containing id, payload, retry_count, and created_at
        business_logic_func: Custom function to process the record payload

    Returns:
        Dictionary containing processing result with record_id, status, and result/error
    """
    logger = get_run_logger()
    record_id = record['id']

    logger.info(f"Processing record {record_id} with custom business logic")

    try:
        # Use custom business logic function
        result = business_logic_func(record['payload'])

        # Mark record as completed in database with retry logic
        processor.mark_record_completed_with_retry(record_id, result)

        logger.info(f"Successfully processed record {record_id} with custom logic")

        return {
            "record_id": record_id,
            "status": "completed",
            "result": result
        }

    except Exception as e:
        # Mark record as failed in database with retry logic
        error_message = str(e)
        processor.mark_record_failed_with_retry(record_id, error_message)

        logger.error(f"Failed to process record {record_id} with custom logic: {error_message}")

        return {
            "record_id": record_id,
            "status": "failed",
            "error": error_message
        }


def process_default_business_logic(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Default business logic for record processing.

    This is a placeholder implementation that can be overridden by specific flows.
    It demonstrates the expected input/output pattern for business logic functions.

    Args:
        payload: Record payload data to process

    Returns:
        Dictionary containing processing results

    Example:
        payload = {"survey_id": 1001, "customer_id": "CUST001"}
        result = process_default_business_logic(payload)
        # Returns: {"processed": True, "survey_id": 1001, "timestamp": "..."}
    """
    # Default implementation - just marks as processed with timestamp
    import datetime

    return {
        "processed": True,
        "original_payload": payload,
        "processed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "processor_instance": processor.instance_id
    }


@task(name="generate-processing-summary")
def generate_processing_summary(
    results: list[dict[str, Any]],
    flow_name: str,
    batch_size: int,
    records_claimed: int
) -> dict[str, Any]:
    """
    Generate comprehensive processing summary from task results.

    Analyzes the results from parallel record processing and creates a summary
    with counts, success rates, and error information for monitoring and logging.

    Args:
        results: List of processing results from process_record_with_status tasks
        flow_name: Name of the flow for identification
        batch_size: Original batch size requested
        records_claimed: Actual number of records claimed

    Returns:
        Dictionary containing comprehensive processing summary
    """
    logger = get_run_logger()

    # Initialize counters
    completed_count = 0
    failed_count = 0
    errors = []

    # Analyze results
    for result in results:
        if result["status"] == "completed":
            completed_count += 1
        elif result["status"] == "failed":
            failed_count += 1
            errors.append({
                "record_id": result["record_id"],
                "error": result["error"]
            })

    # Calculate success rate
    total_processed = completed_count + failed_count
    success_rate = (completed_count / total_processed * 100) if total_processed > 0 else 0

    # Build summary
    summary = {
        "flow_name": flow_name,
        "batch_size": batch_size,
        "records_claimed": records_claimed,
        "records_processed": total_processed,
        "records_completed": completed_count,
        "records_failed": failed_count,
        "success_rate_percent": round(success_rate, 2),
        "processor_instance": processor.instance_id,
        "errors": errors[:10] if errors else [],  # Limit to first 10 errors
        "error_count": len(errors)
    }

    logger.info(
        f"Processing summary for '{flow_name}': "
        f"{completed_count}/{total_processed} successful "
        f"({success_rate:.1f}% success rate)"
    )

    if failed_count > 0:
        logger.warning(f"{failed_count} records failed processing in flow '{flow_name}'")

    return summary


# Utility functions for flow template usage

def create_custom_distributed_flow(
    flow_name: str,
    business_logic_func: callable,
    default_batch_size: int = 100
) -> callable:
    """
    Factory function to create custom distributed flows with specific business logic.

    This utility helps create specialized distributed flows while maintaining
    the standardized template pattern and error handling.

    Args:
        flow_name: Name for the custom flow
        business_logic_func: Custom business logic function
        default_batch_size: Default batch size for the flow

    Returns:
        Configured flow function ready for deployment

    Example:
        def survey_logic(payload):
            return {"satisfaction_score": payload.get("rating", 0) * 2}

        survey_flow = create_custom_distributed_flow(
            "survey_processor",
            survey_logic,
            default_batch_size=50
        )
    """
    @flow(name=f"distributed-{flow_name}")
    def custom_flow(batch_size: int = default_batch_size) -> dict[str, Any]:
        return distributed_processing_flow(
            flow_name=flow_name,
            batch_size=batch_size,
            business_logic_func=business_logic_func
        )

    return custom_flow


def get_processor_health() -> dict[str, Any]:
    """
    Get current health status of the distributed processor.

    Convenience function for health monitoring and diagnostics.

    Returns:
        Dictionary containing current health status
    """
    return processor.health_check()


def get_queue_status(flow_name: Optional[str] = None) -> dict[str, Any]:
    """
    Get current queue status for monitoring.

    Convenience function for operational monitoring of queue depth and status.

    Args:
        flow_name: Optional flow name to filter results

    Returns:
        Dictionary containing queue status information
    """
    return processor.get_queue_status(flow_name)
