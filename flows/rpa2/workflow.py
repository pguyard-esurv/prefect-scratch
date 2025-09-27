"""
RPA2 Workflow - Simple data validation and reporting.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner


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
def rpa2_workflow() -> dict[str, Any]:
    """
    RPA2 workflow that validates data and generates reports.

    Returns:
        Dictionary containing the validation results
    """
    logger = get_run_logger()
    logger.info("Starting RPA2: Data Validation Workflow")

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


if __name__ == "__main__":
    # Run the workflow
    result = rpa2_workflow()
    print(f"\nRPA2 Workflow completed! Results: {result}")
