"""
RPA1 Workflow - File processing and data transformation.
"""

from typing import Any

from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from core.tasks import (
    calculate_summary,
    cleanup_temp_files,
    create_sample_data,
    extract_data,
    generate_report,
    transform_data,
)


@flow(
    name="rpa1-file-processing",
    task_runner=ConcurrentTaskRunner(),
    description="RPA1: File processing and data transformation workflow",
)
def rpa1_workflow(cleanup: bool = True) -> dict[str, Any]:
    """
    RPA1 workflow that processes sales data files.

    Args:
        cleanup: Whether to clean up temporary files after processing

    Returns:
        Dictionary containing the summary statistics
    """
    logger = get_run_logger()
    logger.info("Starting RPA1: File Processing Workflow")

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


if __name__ == "__main__":
    # Run the workflow
    result = rpa1_workflow()
    print(f"\nRPA1 Workflow completed! Summary: {result}")
