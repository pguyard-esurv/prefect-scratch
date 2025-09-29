# noqa: E501
"""
RPA2 Workflow - Simple data validation and reporting.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from core.config import rpa2_config

# Distributed processing imports (lazy loaded to maintain backward compatibility)
try:
    from core.database import DatabaseManager
    from core.distributed import DistributedProcessor

    DISTRIBUTED_AVAILABLE = True
except ImportError:
    DISTRIBUTED_AVAILABLE = False


@task
def create_validation_data() -> str:
    """Create sample data for validation."""
    logger = get_run_logger()

    # Create data directory
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    # Create sample validation data
    validation_file = data_dir / "validation_data.json"
    sample_data = {
        "users": [
            {"id": 1, "name": "Alice", "email": "alice@example.com", "active": True},
            {"id": 2, "name": "Bob", "email": "bob@example.com", "active": False},
            {
                "id": 3,
                "name": "Charlie",
                "email": "charlie@example.com",
                "active": True,
            },
            {"id": 4, "name": "Diana", "email": "invalid-email", "active": True},
            {"id": 5, "name": "", "email": "eve@example.com", "active": True},
        ],
        "created_at": datetime.now().isoformat(),
    }

    with open(validation_file, "w") as f:
        json.dump(sample_data, f, indent=2)

    logger.info(f"Created validation data file: {validation_file}")
    return str(validation_file)


@task
def validate_users(users: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate user data and return validation results."""
    logger = get_run_logger()

    validation_results = {
        "total_users": len(users),
        "valid_users": 0,
        "invalid_users": 0,
        "issues": [],
    }

    for user in users:
        is_valid = True
        user_issues = []

        # Check required fields
        if not user.get("name") or user["name"].strip() == "":
            is_valid = False
            user_issues.append("Missing or empty name")

        # Check email format (simple validation)
        email = user.get("email", "")
        if "@" not in email or "." not in email.split("@")[-1]:
            is_valid = False
            user_issues.append("Invalid email format")

        # Check ID is positive
        if not isinstance(user.get("id"), int) or user["id"] <= 0:
            is_valid = False
            user_issues.append("Invalid or missing ID")

        if is_valid:
            validation_results["valid_users"] += 1
        else:
            validation_results["invalid_users"] += 1
            validation_results["issues"].append(
                {"user_id": user.get("id"), "issues": user_issues}
            )

    logger.info(
        f"Validation complete: {validation_results['valid_users']} valid, {validation_results['invalid_users']} invalid"
    )
    return validation_results


@task
def generate_validation_report(validation_results: dict[str, Any]) -> str:
    """Generate a validation report."""
    logger = get_run_logger()

    # Create output directory
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Generate report file
    report_file = (
        output_dir
        / f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )

    with open(report_file, "w") as f:
        json.dump(validation_results, f, indent=2)

    logger.info(f"Generated validation report: {report_file}")
    return str(report_file)


@flow(
    name="rpa2-validation",
    task_runner=ConcurrentTaskRunner(),
    description="RPA2: Data validation and reporting workflow",
)
def rpa2_workflow(
    use_distributed: Optional[bool] = None, batch_size: Optional[int] = None
) -> dict[str, Any]:
    """
    RPA2 workflow that validates data and generates reports.

    Args:
        use_distributed: Whether to use distributed processing (overrides config)
        batch_size: Batch size for distributed processing (overrides config)

    Returns:
        Dictionary containing the validation results
    """
    logger = get_run_logger()
    logger.info("Starting RPA2: Data Validation Workflow")

    # Get environment-specific configuration
    validation_strict = rpa2_config.get_variable("validation_strict", "true")
    max_retries = rpa2_config.get_variable("max_retries", 3)
    timeout = rpa2_config.get_variable("timeout", 30)
    cleanup_temp_files = rpa2_config.get_variable("cleanup_temp_files", "true")

    # Distributed processing configuration
    config_use_distributed = (
        rpa2_config.get_variable("use_distributed_processing", "false").lower()
        == "true"
    )
    config_distributed_batch_size = int(
        rpa2_config.get_variable("distributed_batch_size", 10)
    )

    # Override with parameters if provided
    final_use_distributed = (
        use_distributed if use_distributed is not None else config_use_distributed
    )
    final_batch_size = (
        batch_size if batch_size is not None else config_distributed_batch_size
    )

    logger.info(f"Environment: {rpa2_config.environment}")
    logger.info(f"Validation strict mode: {validation_strict}")
    logger.info(f"Max retries: {max_retries}")
    logger.info(f"Timeout: {timeout} seconds")
    logger.info(f"Cleanup temp files: {cleanup_temp_files}")
    logger.info(
        f"Distributed processing: {'Enabled' if final_use_distributed else 'Disabled'}"
    )
    if final_use_distributed:
        logger.info(f"Distributed batch size: {final_batch_size}")

    # Check distributed processing availability
    if final_use_distributed and not DISTRIBUTED_AVAILABLE:
        logger.warning(
            "Distributed processing requested but not available. Falling back to standard processing."
        )
        final_use_distributed = False

    # Choose processing mode
    if final_use_distributed:
        return _run_distributed_rpa2_workflow(
            final_batch_size, validation_strict, logger
        )
    else:
        return _run_standard_rpa2_workflow(logger)


def _run_standard_rpa2_workflow(logger) -> dict[str, Any]:
    """Run the standard (non-distributed) RPA2 workflow."""
    logger.info("Running standard RPA2 workflow")

    # Step 1: Create validation data
    data_file = create_validation_data()

    try:
        # Step 2: Load and validate data
        with open(data_file) as f:
            data = json.load(f)

        validation_results = validate_users(data["users"])

        # Step 3: Generate report
        generate_validation_report(validation_results)

        logger.info("RPA2 Workflow completed successfully")
        return validation_results

    finally:
        # Cleanup
        try:
            Path(data_file).unlink()
            logger.info(f"Cleaned up temporary file: {data_file}")
        except FileNotFoundError:
            logger.warning(f"File not found for cleanup: {data_file}")


def _run_distributed_rpa2_workflow(
    batch_size: int, validation_strict: str, logger
) -> dict[str, Any]:
    """Run the distributed RPA2 workflow."""
    logger.info("Running distributed RPA2 workflow")

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
    flow_name = "rpa2_validation"
    records = processor.claim_records_batch(flow_name, batch_size)

    if not records:
        logger.info("No records available for distributed processing")
        return {
            "flow_name": flow_name,
            "records_processed": 0,
            "message": "No records to process",
        }

    # Process records using .map()
    results = process_rpa2_record.map(records, validation_strict=validation_strict)

    # Generate summary
    completed_count = sum(1 for r in results if r["status"] == "completed")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    # Aggregate validation results
    total_valid = sum(
        r.get("result", {}).get("valid_users", 0)
        for r in results
        if r["status"] == "completed"
    )
    total_invalid = sum(
        r.get("result", {}).get("invalid_users", 0)
        for r in results
        if r["status"] == "completed"
    )

    summary = {
        "flow_name": flow_name,
        "records_processed": len(records),
        "records_completed": completed_count,
        "records_failed": failed_count,
        "success_rate": (completed_count / len(records) * 100) if records else 0,
        "total_valid_users": total_valid,
        "total_invalid_users": total_invalid,
        "processor_instance": processor.instance_id,
    }

    logger.info(
        f"Distributed RPA2 workflow completed: {completed_count}/{len(records)} successful"
    )
    return summary


@task(name="process-rpa2-record", retries=0)
def process_rpa2_record(
    record: dict[str, Any], validation_strict: str = "true"
) -> dict[str, Any]:
    """Process individual RPA2 record with distributed processing."""
    logger = get_run_logger()
    record_id = record["id"]
    payload = record["payload"]

    logger.info(f"Processing RPA2 record {record_id}")

    try:
        # Initialize processor for status updates
        rpa_db_manager = DatabaseManager("rpa_db")
        processor = DistributedProcessor(rpa_db_manager)

        # Process the record using standard RPA2 logic
        # Extract users data from payload
        users_data = payload.get("users", [])

        if not users_data:
            raise ValueError("No users data found in payload")

        # Validate users
        validation_results = validate_users(users_data)

        # Generate report
        report_file = generate_validation_report(validation_results)

        # Prepare result
        result = {
            "validation_results": validation_results,
            "report_file": str(report_file),
            "processed_at": datetime.now().isoformat(),
        }

        # Mark as completed
        processor.mark_record_completed(record_id, result)

        logger.info(f"Successfully processed RPA2 record {record_id}")
        return {
            "record_id": record_id,
            "status": "completed",
            "result": validation_results,
        }

    except Exception as e:
        # Mark as failed
        error_message = str(e)
        try:
            processor.mark_record_failed(record_id, error_message)
        except Exception:
            pass  # Don't fail if we can't update status

        logger.error(f"Failed to process RPA2 record {record_id}: {error_message}")
        return {"record_id": record_id, "status": "failed", "error": error_message}


if __name__ == "__main__":
    # Run the workflow
    result = rpa2_workflow()
    print(f"\nRPA2 Workflow completed! Results: {result}")
