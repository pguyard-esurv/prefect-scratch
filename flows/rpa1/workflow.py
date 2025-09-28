"""
RPA1 Workflow - File processing and data transformation.
"""

from typing import Any, Optional

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from core.config import rpa1_config
from core.tasks import (
    calculate_summary,
    cleanup_temp_files,
    create_sample_data,
    extract_data,
    generate_report,
    transform_data,
)

# Distributed processing imports (lazy loaded to maintain backward compatibility)
try:
    from core.database import DatabaseManager
    from core.distributed import DistributedProcessor
    DISTRIBUTED_AVAILABLE = True
except ImportError:
    DISTRIBUTED_AVAILABLE = False


@flow(
    name="rpa1-file-processing",
    task_runner=ConcurrentTaskRunner(),
    description="RPA1: File processing and data transformation workflow",
)
def rpa1_workflow(
    cleanup: bool = True,
    use_distributed: Optional[bool] = None,
    batch_size: Optional[int] = None
) -> dict[str, Any]:
    """
    RPA1 workflow that processes sales data files.

    Args:
        cleanup: Whether to clean up temporary files after processing
        use_distributed: Whether to use distributed processing (overrides config)
        batch_size: Batch size for distributed processing (overrides config)

    Returns:
        Dictionary containing the summary statistics
    """
    logger = get_run_logger()
    logger.info("Starting RPA1: File Processing Workflow")

    # Get environment-specific configuration
    config_batch_size = rpa1_config.get_variable("batch_size", 1000)
    timeout = rpa1_config.get_variable("timeout", 60)
    output_format = rpa1_config.get_variable("output_format", "json")
    api_key = rpa1_config.get_secret("api_key", "default-key")

    # Distributed processing configuration
    config_use_distributed = rpa1_config.get_variable("use_distributed_processing", "false").lower() == "true"
    config_distributed_batch_size = int(rpa1_config.get_variable("distributed_batch_size", 10))

    # Override with parameters if provided
    final_use_distributed = use_distributed if use_distributed is not None else config_use_distributed
    final_batch_size = batch_size if batch_size is not None else config_distributed_batch_size

    logger.info(f"Environment: {rpa1_config.environment}")
    logger.info(f"Processing batch size: {config_batch_size}")
    logger.info(f"Timeout: {timeout} seconds")
    logger.info(f"Output format: {output_format}")
    logger.info(f"API key configured: {'Yes' if api_key else 'No'}")
    logger.info(f"Distributed processing: {'Enabled' if final_use_distributed else 'Disabled'}")
    if final_use_distributed:
        logger.info(f"Distributed batch size: {final_batch_size}")

    # Check distributed processing availability
    if final_use_distributed and not DISTRIBUTED_AVAILABLE:
        logger.warning("Distributed processing requested but not available. Falling back to standard processing.")
        final_use_distributed = False

    # Choose processing mode
    if final_use_distributed:
        return _run_distributed_rpa1_workflow(final_batch_size, cleanup, logger)
    else:
        return _run_standard_rpa1_workflow(cleanup, logger)


def _run_standard_rpa1_workflow(cleanup: bool, logger) -> dict[str, Any]:
    """Run the standard (non-distributed) RPA1 workflow."""
    logger.info("Running standard RPA1 workflow")

    # Step 1: Create sample data
    sample_file = create_sample_data()

    try:
        # Step 2: Extract data
        raw_data = extract_data(sample_file)

        # Step 3: Transform data
        transformed_data = transform_data(raw_data)

        # Step 4: Calculate summary
        summary = calculate_summary(transformed_data)

        # Step 5: Generate report
        generate_report(summary)

        logger.info("RPA1 Workflow completed successfully")
        return summary

    finally:
        # Step 6: Cleanup (if requested)
        if cleanup:
            cleanup_temp_files(sample_file)


def _run_distributed_rpa1_workflow(batch_size: int, cleanup: bool, logger) -> dict[str, Any]:
    """Run the distributed RPA1 workflow."""
    logger.info("Running distributed RPA1 workflow")

    # Initialize distributed processor
    rpa_db_manager = DatabaseManager("rpa_db")
    processor = DistributedProcessor(rpa_db_manager)

    # Perform health check
    health_status = processor.health_check()
    if health_status["status"] == "unhealthy":
        error_msg = f"Database health check failed: {health_status.get('error', 'Unknown error')}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # Claim records from processing queue
    flow_name = "rpa1_file_processing"
    records = processor.claim_records_batch(flow_name, batch_size)

    if not records:
        logger.info("No records available for distributed processing")
        return {
            "flow_name": flow_name,
            "records_processed": 0,
            "message": "No records to process"
        }

    # Process records using .map()
    results = process_rpa1_record.map(records, cleanup=cleanup)

    # Generate summary
    completed_count = sum(1 for r in results if r["status"] == "completed")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    summary = {
        "flow_name": flow_name,
        "records_processed": len(records),
        "records_completed": completed_count,
        "records_failed": failed_count,
        "success_rate": (completed_count / len(records) * 100) if records else 0,
        "processor_instance": processor.instance_id
    }

    logger.info(f"Distributed RPA1 workflow completed: {completed_count}/{len(records)} successful")
    return summary


@task(name="process-rpa1-record", retries=0)
def process_rpa1_record(record: dict[str, Any], cleanup: bool = True) -> dict[str, Any]:
    """Process individual RPA1 record with distributed processing."""
    logger = get_run_logger()
    record_id = record['id']
    record['payload']

    logger.info(f"Processing RPA1 record {record_id}")

    try:
        # Initialize processor for status updates
        rpa_db_manager = DatabaseManager("rpa_db")
        processor = DistributedProcessor(rpa_db_manager)

        # Process the record using standard RPA1 logic
        # Create sample data based on payload
        sample_file = create_sample_data()

        try:
            # Extract and transform data
            raw_data = extract_data(sample_file)
            transformed_data = transform_data(raw_data)
            summary = calculate_summary(transformed_data)

            # Generate report
            generate_report(summary)

            # Prepare result
            result = {
                "summary": summary,
                "processed_at": logger.extra.get("timestamp", "unknown"),
                "file_processed": str(sample_file)
            }

            # Mark as completed
            processor.mark_record_completed(record_id, result)

            logger.info(f"Successfully processed RPA1 record {record_id}")
            return {"record_id": record_id, "status": "completed", "result": result}

        finally:
            # Cleanup if requested
            if cleanup:
                cleanup_temp_files(sample_file)

    except Exception as e:
        # Mark as failed
        error_message = str(e)
        try:
            processor.mark_record_failed(record_id, error_message)
        except Exception:
            pass  # Don't fail if we can't update status

        logger.error(f"Failed to process RPA1 record {record_id}: {error_message}")
        return {"record_id": record_id, "status": "failed", "error": error_message}


if __name__ == "__main__":
    # Run the workflow
    result = rpa1_workflow()
    print(f"\nRPA1 Workflow completed! Summary: {result}")
