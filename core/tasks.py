"""
Shared RPA tasks that can be reused across different flows.
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from prefect import get_run_logger, task

from .config import DATA_DIR, OUTPUT_DIR, SAMPLE_PRODUCTS


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
