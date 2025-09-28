"""
Example distributed flow implementation for survey processing.

This example demonstrates the complete distributed processing system including:
1. Sample record preparation for adding surveys to processing queue
2. Business logic for survey data transformation and scoring
3. Multi-database operations (reading from SurveyHub, writing to rpa_db)
4. Proper error handling, logging, and summary generation
5. Integration with the DistributedProcessor for atomic record claiming

This serves as a reference implementation for creating distributed flows
that prevent duplicate processing across multiple container instances.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from core.database import DatabaseManager
from core.distributed import DistributedProcessor
from core.flow_template import distributed_processing_flow

# Module-level instances for performance optimization
rpa_db_manager = DatabaseManager("rpa_db")
source_db_manager = DatabaseManager("SurveyHub")
processor = DistributedProcessor(rpa_db_manager, source_db_manager)


@task(name="prepare-survey-records")
def prepare_survey_records_for_queue(
    survey_count: int = 10,
    priority_distribution: Optional[dict[str, float]] = None
) -> list[dict[str, Any]]:
    """
    Prepare sample survey records for adding to the processing queue.

    Creates realistic survey data that would typically come from external systems
    or batch imports. This demonstrates the pattern for preparing records before
    adding them to the distributed processing queue.

    Args:
        survey_count: Number of survey records to create (default: 10)
        priority_distribution: Distribution of priorities (default: balanced)

    Returns:
        List of record dictionaries ready for queue insertion

    Example:
        records = prepare_survey_records_for_queue(survey_count=50)
        processor.add_records_to_queue("survey_processor", records)
    """
    logger = get_run_logger()

    if priority_distribution is None:
        priority_distribution = {"high": 0.2, "normal": 0.6, "low": 0.2}

    logger.info(
        f"Preparing {survey_count} survey records for processing queue"
    )

    # Sample customer data for realistic records
    customers = [
        {"id": "CUST001", "name": "Alice Johnson", "segment": "premium"},
        {"id": "CUST002", "name": "Bob Smith", "segment": "standard"},
        {"id": "CUST003", "name": "Charlie Brown", "segment": "premium"},
        {"id": "CUST004", "name": "Diana Prince", "segment": "enterprise"},
        {"id": "CUST005", "name": "Eve Wilson", "segment": "standard"},
        {"id": "CUST006", "name": "Frank Miller", "segment": "premium"},
        {"id": "CUST007", "name": "Grace Lee", "segment": "enterprise"},
        {"id": "CUST008", "name": "Henry Ford", "segment": "standard"},
        {"id": "CUST009", "name": "Ivy Chen", "segment": "premium"},
        {"id": "CUST010", "name": "Jack Ryan", "segment": "enterprise"}
    ]

    survey_types = [
        "Customer Satisfaction",
        "Product Feedback",
        "Market Research",
        "Service Quality",
        "Feature Request"
    ]

    records = []
    priorities = list(priority_distribution.keys())
    priority_weights = list(priority_distribution.values())

    for i in range(survey_count):
        # Select customer and survey type
        customer = customers[i % len(customers)]
        survey_type = survey_types[i % len(survey_types)]

        # Determine priority based on distribution
        import random
        priority = random.choices(priorities, weights=priority_weights)[0]

        # Create realistic survey payload
        survey_payload = {
            "survey_id": f"SURV-{1000 + i:04d}",
            "customer_id": customer["id"],
            "customer_name": customer["name"],
            "customer_segment": customer["segment"],
            "survey_type": survey_type,
            "priority": priority,
            "submitted_at": (
                datetime.now() - timedelta(hours=random.randint(1, 72))
            ).isoformat(),
            "response_data": {
                "overall_satisfaction": random.randint(1, 10),
                "likelihood_to_recommend": random.randint(1, 10),
                "service_rating": random.randint(1, 5),
                "product_rating": random.randint(1, 5),
                "comments": f"Sample feedback for survey {1000 + i}",
                "completion_time_seconds": random.randint(120, 600)
            },
            "metadata": {
                "source_system": "survey_portal",
                "survey_version": "v2.1",
                "device_type": random.choice(["desktop", "mobile", "tablet"]),
                "language": "en-US"
            }
        }

        # Create record for queue insertion
        record = {
            "payload": survey_payload
        }

        records.append(record)

    priority_counts = {
        p: sum(1 for r in records if r['payload']['priority'] == p)
        for p in priorities
    }
    logger.info(
        f"Prepared {len(records)} survey records with priority distribution: "
        f"{priority_counts}"
    )

    return records


@task(name="add-surveys-to-queue")
def add_surveys_to_processing_queue(
    records: list[dict[str, Any]],
    flow_name: str = "survey_processor"
) -> dict[str, Any]:
    """
    Add prepared survey records to the distributed processing queue.

    This task demonstrates the pattern for bulk insertion of records into
    the processing queue, with proper error handling and logging.

    Args:
        records: List of survey records to add to queue
        flow_name: Name of the flow that will process these records

    Returns:
        Dictionary containing insertion results and statistics

    Raises:
        RuntimeError: If queue insertion fails
    """
    logger = get_run_logger()

    try:
        logger.info(
            f"Adding {len(records)} survey records to processing queue "
            f"for flow '{flow_name}'"
        )

        # Add records to queue using DistributedProcessor
        inserted_count = processor.add_records_to_queue(flow_name, records)

        # Get updated queue status
        queue_status = processor.get_queue_status(flow_name)

        result = {
            "records_added": inserted_count,
            "flow_name": flow_name,
            "queue_status": queue_status,
            "insertion_timestamp": datetime.now().isoformat()
        }

        logger.info(
            f"Successfully added {inserted_count} records to queue. "
            f"Queue now has {queue_status['pending_records']} pending records."
        )

        return result

    except Exception as e:
        error_msg = f"Failed to add survey records to processing queue: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def process_survey_business_logic(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Business logic for survey data transformation and scoring.

    This function demonstrates realistic survey processing including:
    - Data validation and transformation
    - Satisfaction scoring algorithms
    - Customer segment analysis
    - Multi-database operations (read from SurveyHub, write to rpa_db)

    Args:
        payload: Survey payload data from processing queue

    Returns:
        Dictionary containing processed survey results

    Raises:
        ValueError: If survey data is invalid or missing required fields
        RuntimeError: If database operations fail
    """
    logger = get_run_logger()

    # Extract survey information
    survey_id = payload.get("survey_id")
    customer_id = payload.get("customer_id")
    response_data = payload.get("response_data", {})

    logger.info(f"Processing survey {survey_id} for customer {customer_id}")

    # Validate required fields
    required_fields = [
        "survey_id", "customer_id", "survey_type", "response_data"
    ]
    missing_fields = [
        field for field in required_fields if not payload.get(field)
    ]

    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    # Validate response data
    if not isinstance(response_data, dict):
        raise ValueError("response_data must be a dictionary")

    required_response_fields = [
        "overall_satisfaction", "likelihood_to_recommend"
    ]
    missing_response_fields = [
        field for field in required_response_fields
        if field not in response_data
    ]

    if missing_response_fields:
        raise ValueError(
            f"Missing required response fields: "
            f"{', '.join(missing_response_fields)}"
        )

    try:
        # Step 1: Read additional customer data from SurveyHub (if available)
        customer_data = None
        if source_db_manager:
            try:
                # In a real implementation, this would query actual SurveyHub tables
                # For demo purposes, we'll simulate the query
                logger.debug(
                    f"Fetching additional customer data for {customer_id} "
                    f"from SurveyHub"
                )

                # Simulate customer lookup (real implementation would query DB)
                customer_data = {
                    "customer_id": customer_id,
                    "account_type": payload.get("customer_segment", "standard"),
                    "registration_date": "2023-01-15",
                    "total_orders": 15,
                    "lifetime_value": 2500.00,
                    "support_tickets": 2
                }

                logger.debug(
                    f"Retrieved customer data for {customer_id}: {customer_data}"
                )

            except Exception as e:
                logger.warning(f"Could not fetch customer data from SurveyHub: {e}")
                # Continue processing without additional customer data

        # Step 2: Calculate satisfaction scores and metrics
        overall_satisfaction = response_data.get("overall_satisfaction", 0)
        likelihood_to_recommend = response_data.get("likelihood_to_recommend", 0)
        service_rating = response_data.get("service_rating", 0)
        product_rating = response_data.get("product_rating", 0)

        # Calculate Net Promoter Score (NPS) category
        if likelihood_to_recommend >= 9:
            nps_category = "promoter"
        elif likelihood_to_recommend >= 7:
            nps_category = "passive"
        else:
            nps_category = "detractor"

        # Calculate composite satisfaction score (weighted average)
        weights = {
            "overall": 0.4,
            "service": 0.3,
            "product": 0.3
        }

        # Normalize ratings to 0-10 scale
        normalized_service = (
            (service_rating / 5.0) * 10 if service_rating else 0
        )
        normalized_product = (
            (product_rating / 5.0) * 10 if product_rating else 0
        )

        composite_score = (
            (overall_satisfaction * weights["overall"]) +
            (normalized_service * weights["service"]) +
            (normalized_product * weights["product"])
        )

        # Determine satisfaction level
        if composite_score >= 8.0:
            satisfaction_level = "high"
        elif composite_score >= 6.0:
            satisfaction_level = "medium"
        else:
            satisfaction_level = "low"

        # Step 3: Analyze customer segment impact
        segment_multiplier = 1.0
        if customer_data:
            if customer_data.get("account_type") == "enterprise":
                segment_multiplier = 1.5
            elif customer_data.get("account_type") == "premium":
                segment_multiplier = 1.2

        weighted_score = composite_score * segment_multiplier

        # Step 4: Generate processing results
        processing_result = {
            "survey_id": survey_id,
            "customer_id": customer_id,
            "customer_name": payload.get("customer_name"),
            "survey_type": payload.get("survey_type"),
            "processing_status": "completed",
            "processed_at": datetime.now(),
            "processing_duration_ms": 1200,  # Simulated processing time
            "flow_run_id": (
                f"distributed-survey-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            ),
            "satisfaction_metrics": {
                "overall_satisfaction": overall_satisfaction,
                "likelihood_to_recommend": likelihood_to_recommend,
                "service_rating": service_rating,
                "product_rating": product_rating,
                "composite_score": round(composite_score, 2),
                "weighted_score": round(weighted_score, 2),
                "satisfaction_level": satisfaction_level,
                "nps_category": nps_category
            },
            "customer_analysis": customer_data,
            "processing_metadata": {
                "processor_instance": processor.instance_id,
                "processing_algorithm": "composite_scoring_v2.1",
                "data_sources": (
                    ["survey_response", "customer_profile"] if customer_data
                    else ["survey_response"]
                ),
                "quality_score": 0.95  # Simulated data quality score
            }
        }

        # Step 5: Store results in rpa_db processed_surveys table
        try:
            insert_query = """
            INSERT INTO processed_surveys
            (survey_id, customer_id, customer_name, survey_type,
             processing_status, processed_at, processing_duration_ms,
             flow_run_id, error_message)
            VALUES (:survey_id, :customer_id, :customer_name, :survey_type,
                    :processing_status, :processed_at, :processing_duration_ms,
                    :flow_run_id, :error_message)
            """

            insert_params = {
                "survey_id": processing_result["survey_id"],
                "customer_id": processing_result["customer_id"],
                "customer_name": processing_result["customer_name"],
                "survey_type": processing_result["survey_type"],
                "processing_status": processing_result["processing_status"],
                "processed_at": processing_result["processed_at"],
                "processing_duration_ms": processing_result["processing_duration_ms"],
                "flow_run_id": processing_result["flow_run_id"],
                "error_message": None
            }

            rpa_db_manager.execute_query(insert_query, insert_params)

            logger.info(
                f"Successfully processed survey {survey_id}: "
                f"satisfaction_level={satisfaction_level}, "
                f"composite_score={composite_score:.2f}, "
                f"nps_category={nps_category}"
            )

        except Exception as db_error:
            logger.error(
                f"Failed to store survey results in database: {db_error}"
            )
            # Update processing result to reflect storage failure
            processing_result["processing_status"] = "completed_with_storage_error"
            processing_result["storage_error"] = str(db_error)

        return processing_result

    except Exception as e:
        error_msg = f"Survey processing failed for {survey_id}: {e}"
        logger.error(error_msg)

        # Store failure in database for tracking
        try:
            failure_query = """
            INSERT INTO processed_surveys
            (survey_id, customer_id, customer_name, survey_type,
             processing_status, processed_at, processing_duration_ms,
             flow_run_id, error_message)
            VALUES (:survey_id, :customer_id, :customer_name, :survey_type,
                    'failed', :processed_at, :processing_duration_ms,
                    :flow_run_id, :error_message)
            """

            failure_params = {
                "survey_id": survey_id,
                "customer_id": customer_id,
                "customer_name": payload.get("customer_name"),
                "survey_type": payload.get("survey_type"),
                "processed_at": datetime.now(),
                "processing_duration_ms": 500,  # Short duration for failed processing
                "flow_run_id": (
                    f"distributed-survey-failed-"
                    f"{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                ),
                "error_message": error_msg
            }

            rpa_db_manager.execute_query(failure_query, failure_params)

        except Exception as db_error:
            logger.error(
                f"Failed to store error record in database: {db_error}"
            )

        # Re-raise the original error
        raise RuntimeError(error_msg) from e


@flow(
    name="distributed-survey-processing",
    task_runner=ConcurrentTaskRunner(),
    description="Complete distributed survey processing example with queue management"
)
def distributed_survey_processing_flow(
    batch_size: int = 10,
    prepare_sample_data: bool = True,
    sample_record_count: int = 25
) -> dict[str, Any]:
    """
    Complete distributed survey processing flow with sample data preparation.

    This flow demonstrates the complete lifecycle of distributed processing:
    1. Prepare sample survey records (optional)
    2. Add records to processing queue
    3. Process records using distributed processing template
    4. Generate comprehensive summary with metrics

    Args:
        batch_size: Number of records to process in each batch (default: 10)
        prepare_sample_data: Whether to prepare and add sample data (default: True)
        sample_record_count: Number of sample records to create (default: 25)

    Returns:
        Dictionary containing complete processing results and metrics

    Example:
        # Process existing queue
        result = distributed_survey_processing_flow(batch_size=20, prepare_sample_data=False)

        # Prepare sample data and process
        result = distributed_survey_processing_flow(
            batch_size=15,
            prepare_sample_data=True,
            sample_record_count=50
        )
    """
    logger = get_run_logger()
    flow_name = "survey_processor"

    logger.info(
        f"Starting distributed survey processing flow: "
        f"batch_size={batch_size}, prepare_sample_data={prepare_sample_data}"
    )

    try:
        # Step 1: Prepare sample data (if requested)
        preparation_result = None
        if prepare_sample_data:
            logger.info(
                f"Step 1: Preparing {sample_record_count} sample survey records"
            )

            # Prepare sample records
            sample_records = prepare_survey_records_for_queue(
                survey_count=sample_record_count
            )

            # Add records to processing queue
            preparation_result = add_surveys_to_processing_queue(
                records=sample_records,
                flow_name=flow_name
            )

            logger.info(
                f"Added {preparation_result['records_added']} records to "
                f"processing queue"
            )
        else:
            logger.info("Step 1: Skipping sample data preparation")

        # Step 2: Get initial queue status
        logger.info("Step 2: Checking initial queue status")
        initial_queue_status = processor.get_queue_status(flow_name)

        logger.info(
            f"Initial queue status: "
            f"{initial_queue_status['pending_records']} pending, "
            f"{initial_queue_status['processing_records']} processing, "
            f"{initial_queue_status['completed_records']} completed, "
            f"{initial_queue_status['failed_records']} failed"
        )

        # Step 3: Process records using distributed processing template
        logger.info(f"Step 3: Processing records with batch_size={batch_size}")

        processing_result = distributed_processing_flow(
            flow_name=flow_name,
            batch_size=batch_size,
            business_logic_func=process_survey_business_logic
        )

        # Step 4: Get final queue status
        logger.info("Step 4: Checking final queue status")
        final_queue_status = processor.get_queue_status(flow_name)

        # Step 5: Generate comprehensive summary
        logger.info("Step 5: Generating comprehensive processing summary")

        # Calculate processing metrics
        records_processed = processing_result.get("records_processed", 0)
        records_completed = processing_result.get("records_completed", 0)
        records_failed = processing_result.get("records_failed", 0)
        success_rate = processing_result.get("success_rate_percent", 0)

        # Get recent processing statistics from database
        try:
            stats_query = """
            SELECT
                processing_status,
                COUNT(*) as count,
                AVG(processing_duration_ms) as avg_duration_ms
            FROM processed_surveys
            WHERE processed_at >= NOW() - INTERVAL '1 hour'
              AND flow_run_id LIKE 'distributed-survey%'
            GROUP BY processing_status
            """

            recent_stats = rpa_db_manager.execute_query(stats_query)
            processing_stats = {
                row[0]: {"count": row[1], "avg_duration_ms": row[2]}
                for row in recent_stats
            }

        except Exception as e:
            logger.warning(f"Could not retrieve processing statistics: {e}")
            processing_stats = {}

        # Compile complete results
        complete_results = {
            "flow_execution": {
                "status": "completed",
                "flow_name": flow_name,
                "execution_time": datetime.now().isoformat(),
                "batch_size": batch_size,
                "processor_instance": processor.instance_id
            },
            "sample_data_preparation": preparation_result,
            "queue_status": {
                "initial": initial_queue_status,
                "final": final_queue_status,
                "records_processed_this_run": records_processed
            },
            "processing_results": processing_result,
            "performance_metrics": {
                "records_processed": records_processed,
                "records_completed": records_completed,
                "records_failed": records_failed,
                "success_rate_percent": success_rate,
                "processing_efficiency": {
                    "batch_utilization": (
                        (records_processed / batch_size * 100)
                        if batch_size > 0 else 0
                    ),
                    "error_rate": (
                        (records_failed / records_processed * 100)
                        if records_processed > 0 else 0
                    )
                }
            },
            "database_statistics": processing_stats,
            "system_health": processor.health_check()
        }

        logger.info(
            f"Distributed survey processing completed successfully: "
            f"{records_completed}/{records_processed} records processed "
            f"successfully ({success_rate:.1f}% success rate)"
        )

        return complete_results

    except Exception as e:
        logger.error(f"Distributed survey processing flow failed: {e}")

        # Generate error summary
        error_results = {
            "flow_execution": {
                "status": "failed",
                "error": str(e),
                "execution_time": datetime.now().isoformat(),
                "flow_name": flow_name,
                "batch_size": batch_size
            },
            "sample_data_preparation": (
                preparation_result if 'preparation_result' in locals() else None
            ),
            "system_health": processor.health_check()
        }

        # Re-raise with context
        raise RuntimeError(f"Distributed survey processing failed: {e}") from e


@task(name="cleanup-old-records")
def cleanup_old_survey_records(days_to_keep: int = 30) -> dict[str, Any]:
    """
    Cleanup old completed survey records to maintain database performance.

    This task demonstrates maintenance operations for the distributed processing system.

    Args:
        days_to_keep: Number of days of completed records to retain (default: 30)

    Returns:
        Dictionary containing cleanup results
    """
    logger = get_run_logger()

    try:
        logger.info(
            f"Cleaning up survey records older than {days_to_keep} days"
        )

        # Clean up old completed records from processing_queue
        cleanup_queue_query = f"""
        DELETE FROM processing_queue
        WHERE flow_name = 'survey_processor'
          AND status IN ('completed', 'failed')
          AND completed_at < NOW() - INTERVAL '{days_to_keep} days'
        """

        queue_deleted = rpa_db_manager.execute_query(
            cleanup_queue_query, {}, return_count=True
        )

        # Clean up old processed_surveys records
        cleanup_surveys_query = f"""
        DELETE FROM processed_surveys
        WHERE processed_at < NOW() - INTERVAL '{days_to_keep} days'
          AND processing_status IN ('completed', 'failed')
        """

        surveys_deleted = rpa_db_manager.execute_query(
            cleanup_surveys_query, {}, return_count=True
        )

        # Cleanup orphaned records
        orphaned_cleaned = processor.cleanup_orphaned_records(timeout_hours=2)

        cleanup_results = {
            "queue_records_deleted": queue_deleted,
            "survey_records_deleted": surveys_deleted,
            "orphaned_records_cleaned": orphaned_cleaned,
            "cleanup_timestamp": datetime.now().isoformat(),
            "days_retained": days_to_keep
        }

        logger.info(
            f"Cleanup completed: {queue_deleted} queue records, "
            f"{surveys_deleted} survey records, {orphaned_cleaned} orphaned records"
        )

        return cleanup_results

    except Exception as e:
        error_msg = f"Cleanup operation failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


if __name__ == "__main__":
    """
    Example usage of the distributed survey processing flow.

    This demonstrates different ways to run the flow for various scenarios.
    """
    import sys

    try:
        if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
            # Run cleanup operation
            print("Running cleanup operation...")
            cleanup_result = cleanup_old_survey_records(days_to_keep=7)
            print("\n" + "="*50)
            print("CLEANUP OPERATION COMPLETED")
            print("="*50)
            print(json.dumps(cleanup_result, indent=2, default=str))

        elif len(sys.argv) > 1 and sys.argv[1] == "process-only":
            # Process existing queue without adding sample data
            print("Processing existing queue...")
            result = distributed_survey_processing_flow(
                batch_size=15,
                prepare_sample_data=False
            )
            print("\n" + "="*50)
            print("DISTRIBUTED SURVEY PROCESSING COMPLETED")
            print("="*50)
            print(json.dumps(result, indent=2, default=str))

        else:
            # Full flow with sample data preparation
            print("Running full distributed survey processing flow...")
            result = distributed_survey_processing_flow(
                batch_size=10,
                prepare_sample_data=True,
                sample_record_count=20
            )
            print("\n" + "="*50)
            print("DISTRIBUTED SURVEY PROCESSING COMPLETED")
            print("="*50)
            print(json.dumps(result, indent=2, default=str))

    except Exception as e:
        print(f"\nFlow execution failed: {e}")
        sys.exit(1)
