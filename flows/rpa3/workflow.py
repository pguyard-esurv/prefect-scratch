"""
RPA3 Workflow - Concurrent Data Processing Demo using .map()

This workflow demonstrates Prefect's .map() function for concurrent processing
of customer orders from a CSV file. It shows how to:
- Process multiple records concurrently
- Handle individual record validation
- Perform concurrent API calls
- Aggregate results from parallel operations
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from core.config import ConfigManager

# Distributed processing imports (lazy loaded to maintain backward compatibility)
try:
    from core.database import DatabaseManager
    from core.distributed import DistributedProcessor

    DISTRIBUTED_AVAILABLE = True
except ImportError:
    DISTRIBUTED_AVAILABLE = False


@task
def create_customer_orders_data() -> str:
    """Create sample customer orders CSV data for processing."""
    logger = get_run_logger()

    # Create data directory
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(exist_ok=True)

    # Sample customer orders data
    orders = [
        {
            "order_id": "ORD-001",
            "customer_id": "CUST-001",
            "customer_name": "Alice Johnson",
            "product": "Premium Widget A",
            "quantity": 2,
            "unit_price": 25.50,
            "order_date": "2024-01-15",
            "priority": "high",
            "region": "North",
        },
        {
            "order_id": "ORD-002",
            "customer_id": "CUST-002",
            "customer_name": "Bob Smith",
            "product": "Standard Widget B",
            "quantity": 5,
            "unit_price": 15.75,
            "order_date": "2024-01-15",
            "priority": "medium",
            "region": "South",
        },
        {
            "order_id": "ORD-003",
            "customer_id": "CUST-003",
            "customer_name": "Charlie Brown",
            "product": "Budget Widget C",
            "quantity": 10,
            "unit_price": 8.99,
            "order_date": "2024-01-16",
            "priority": "low",
            "region": "East",
        },
        {
            "order_id": "ORD-004",
            "customer_id": "CUST-004",
            "customer_name": "Diana Prince",
            "product": "Premium Widget A",
            "quantity": 1,
            "unit_price": 25.50,
            "order_date": "2024-01-16",
            "priority": "high",
            "region": "West",
        },
        {
            "order_id": "ORD-005",
            "customer_id": "CUST-005",
            "customer_name": "Eve Wilson",
            "product": "Standard Widget B",
            "quantity": 3,
            "unit_price": 15.75,
            "order_date": "2024-01-17",
            "priority": "medium",
            "region": "North",
        },
        {
            "order_id": "ORD-006",
            "customer_id": "CUST-006",
            "customer_name": "Frank Miller",
            "product": "Budget Widget C",
            "quantity": 8,
            "unit_price": 8.99,
            "order_date": "2024-01-17",
            "priority": "low",
            "region": "South",
        },
        {
            "order_id": "ORD-007",
            "customer_id": "CUST-007",
            "customer_name": "Grace Lee",
            "product": "Premium Widget A",
            "quantity": 4,
            "unit_price": 25.50,
            "order_date": "2024-01-18",
            "priority": "high",
            "region": "East",
        },
        {
            "order_id": "ORD-008",
            "customer_id": "CUST-008",
            "customer_name": "Henry Davis",
            "product": "Standard Widget B",
            "quantity": 6,
            "unit_price": 15.75,
            "order_date": "2024-01-18",
            "priority": "medium",
            "region": "West",
        },
    ]

    # Create CSV file
    csv_file = data_dir / "customer_orders.csv"

    with open(csv_file, "w", newline="") as f:
        fieldnames = orders[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(orders)

    logger.info(f"Created customer orders data file: {csv_file}")
    return str(csv_file)


@task
def load_orders_from_csv(file_path: str) -> list[dict[str, Any]]:
    """Load customer orders from CSV file."""
    logger = get_run_logger()

    orders = []
    with open(file_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert string values to appropriate types
            row["quantity"] = int(row["quantity"])
            row["unit_price"] = float(row["unit_price"])
            orders.append(row)

    logger.info(f"Loaded {len(orders)} orders from {file_path}")
    return orders


@task
def validate_order(order: dict[str, Any]) -> dict[str, Any]:
    """
    Validate a single customer order.

    This task demonstrates individual record processing with .map()
    """
    logger = get_run_logger()

    order_id = order["order_id"]
    validation_result = {
        "order_id": order_id,
        "valid": True,
        "errors": [],
        "warnings": [],
    }

    # Validate required fields
    if not order.get("customer_name") or order["customer_name"].strip() == "":
        validation_result["valid"] = False
        validation_result["errors"].append("Missing customer name")

    if not order.get("product") or order["product"].strip() == "":
        validation_result["valid"] = False
        validation_result["errors"].append("Missing product name")

    # Validate quantity
    if order.get("quantity", 0) <= 0:
        validation_result["valid"] = False
        validation_result["errors"].append("Invalid quantity")
    elif order.get("quantity", 0) > 100:
        validation_result["warnings"].append("Large quantity order")

    # Validate price
    if order.get("unit_price", 0) <= 0:
        validation_result["valid"] = False
        validation_result["errors"].append("Invalid unit price")

    # Validate priority
    valid_priorities = ["low", "medium", "high"]
    if order.get("priority") not in valid_priorities:
        validation_result["warnings"].append(
            f"Unknown priority: {order.get('priority')}"
        )

    logger.info(
        f"Validated order {order_id}: {'Valid' if validation_result['valid'] else 'Invalid'}"
    )
    return validation_result


@task
def calculate_order_totals(order: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate totals for a single order.

    This task demonstrates data transformation with .map()
    """
    logger = get_run_logger()

    order_id = order["order_id"]
    quantity = order["quantity"]
    unit_price = order["unit_price"]

    # Calculate totals
    subtotal = quantity * unit_price

    # Apply regional tax rates (mock)
    tax_rates = {"North": 0.08, "South": 0.07, "East": 0.09, "West": 0.08}
    region = order.get("region", "North")
    tax_rate = tax_rates.get(region, 0.08)
    tax_amount = subtotal * tax_rate

    # Apply priority-based discounts
    discount_rates = {"low": 0.0, "medium": 0.05, "high": 0.10}
    priority = order.get("priority", "medium")
    discount_rate = discount_rates.get(priority, 0.0)
    discount_amount = subtotal * discount_rate

    total = subtotal + tax_amount - discount_amount

    result = {
        "order_id": order_id,
        "subtotal": round(subtotal, 2),
        "tax_amount": round(tax_amount, 2),
        "discount_amount": round(discount_amount, 2),
        "total": round(total, 2),
        "tax_rate": tax_rate,
        "discount_rate": discount_rate,
    }

    logger.info(f"Calculated totals for order {order_id}: ${total:.2f}")
    return result


@task
def check_inventory_availability(order: dict[str, Any]) -> dict[str, Any]:
    """
    Check inventory availability for a single order.

    This task simulates an API call with .map()
    """
    logger = get_run_logger()

    order_id = order["order_id"]
    product = order["product"]
    quantity = order["quantity"]

    # Simulate inventory check (mock API call)
    # In real scenario, this would call an external inventory API
    import time

    time.sleep(0.1)  # Simulate API delay

    # Mock inventory data
    inventory = {
        "Premium Widget A": 50,
        "Standard Widget B": 100,
        "Budget Widget C": 200,
    }

    available = inventory.get(product, 0)
    in_stock = available >= quantity

    result = {
        "order_id": order_id,
        "product": product,
        "requested_quantity": quantity,
        "available_quantity": available,
        "in_stock": in_stock,
        "shortage": max(0, quantity - available) if not in_stock else 0,
    }

    status = "Available" if in_stock else f"Shortage of {result['shortage']} units"
    logger.info(f"Inventory check for order {order_id}: {status}")
    return result


@task
def process_order_fulfillment(
    order: dict[str, Any],
    validation: dict[str, Any],
    totals: dict[str, Any],
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """
    Process order fulfillment for a single order.

    This task combines results from multiple mapped operations
    """
    logger = get_run_logger()

    order_id = order["order_id"]

    # Determine fulfillment status
    if not validation["valid"]:
        status = "Rejected - Validation Failed"
    elif not inventory["in_stock"]:
        status = "Pending - Insufficient Inventory"
    else:
        status = "Approved - Ready for Fulfillment"

    result = {
        "order_id": order_id,
        "customer_name": order["customer_name"],
        "product": order["product"],
        "quantity": order["quantity"],
        "total_amount": totals["total"],
        "status": status,
        "validation_errors": validation["errors"],
        "validation_warnings": validation["warnings"],
        "inventory_shortage": inventory["shortage"],
        "processed_at": datetime.now().isoformat(),
    }

    logger.info(f"Processed fulfillment for order {order_id}: {status}")
    return result


@task
def generate_processing_summary(
    fulfillment_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate summary of all processed orders."""
    logger = get_run_logger()

    total_orders = len(fulfillment_results)
    approved_orders = len([r for r in fulfillment_results if "Approved" in r["status"]])
    rejected_orders = len([r for r in fulfillment_results if "Rejected" in r["status"]])
    pending_orders = len([r for r in fulfillment_results if "Pending" in r["status"]])

    total_revenue = sum(
        r["total_amount"] for r in fulfillment_results if "Approved" in r["status"]
    )

    # Group by product
    product_summary = {}
    for result in fulfillment_results:
        product = result["product"]
        if product not in product_summary:
            product_summary[product] = {
                "total_orders": 0,
                "total_quantity": 0,
                "total_revenue": 0,
            }

        product_summary[product]["total_orders"] += 1
        product_summary[product]["total_quantity"] += result["quantity"]
        if "Approved" in result["status"]:
            product_summary[product]["total_revenue"] += result["total_amount"]

    summary = {
        "total_orders": total_orders,
        "approved_orders": approved_orders,
        "rejected_orders": rejected_orders,
        "pending_orders": pending_orders,
        "approval_rate": round(approved_orders / total_orders * 100, 2)
        if total_orders > 0
        else 0,
        "total_revenue": round(total_revenue, 2),
        "product_breakdown": product_summary,
        "generated_at": datetime.now().isoformat(),
    }

    logger.info(
        f"Generated processing summary: {approved_orders}/{total_orders} orders approved"
    )
    return summary


@task
def save_fulfillment_report(
    summary: dict[str, Any], fulfillment_results: list[dict[str, Any]]
) -> str:
    """Save detailed fulfillment report to JSON file."""
    logger = get_run_logger()

    # Create output directory
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Generate report
    report = {"summary": summary, "order_details": fulfillment_results}

    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = output_dir / f"fulfillment_report_{timestamp}.json"

    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Saved fulfillment report: {report_file}")
    return str(report_file)


@flow(
    name="rpa3-concurrent-processing",
    task_runner=ConcurrentTaskRunner(),
    description="RPA3: Concurrent data processing demo using .map() function",
)
def rpa3_workflow(
    max_workers: Optional[int] = None,
    use_distributed: Optional[bool] = None,
    batch_size: Optional[int] = None,
) -> dict[str, Any]:
    """
    RPA3 workflow demonstrating concurrent processing with .map().

    This workflow shows how to:
    1. Process multiple records concurrently
    2. Validate each record independently
    3. Calculate totals for each record
    4. Check inventory for each record
    5. Combine results from parallel operations

    Args:
        max_workers: Maximum number of concurrent workers (for standard processing)
        use_distributed: Whether to use distributed processing (overrides config)
        batch_size: Batch size for distributed processing (overrides config)

    Returns:
        Dictionary containing the processing summary
    """
    logger = get_run_logger()
    logger.info("Starting RPA3: Concurrent Data Processing Demo")

    # Get configuration
    config = ConfigManager("rpa3")
    max_concurrent = max_workers or config.get_variable("max_concurrent_tasks", 10)
    timeout = config.get_variable("timeout", 60)

    # Distributed processing configuration
    config_use_distributed = (
        config.get_variable("use_distributed_processing", "false").lower() == "true"
    )
    config_distributed_batch_size = int(
        config.get_variable("distributed_batch_size", 10)
    )

    # Override with parameters if provided
    final_use_distributed = (
        use_distributed if use_distributed is not None else config_use_distributed
    )
    final_batch_size = (
        batch_size if batch_size is not None else config_distributed_batch_size
    )

    logger.info(f"Environment: {config.environment}")
    logger.info(f"Max concurrent tasks: {max_concurrent}")
    logger.info(f"Timeout: {timeout} seconds")
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

    # Note: In a real implementation, you would need to recreate the task runner
    # with the new max_workers value. For this demo, we'll log the setting.
    if max_concurrent != 10:  # Default value
        logger.info(f"Concurrency limit set to {max_concurrent} (configuration-based)")

    # Choose processing mode
    if final_use_distributed:
        return _run_distributed_rpa3_workflow(final_batch_size, logger)
    else:
        return _run_standard_rpa3_workflow(logger)


def _run_standard_rpa3_workflow(logger) -> dict[str, Any]:
    """Run the standard (non-distributed) RPA3 workflow."""
    logger.info("Running standard RPA3 workflow")

    # Step 1: Create sample data
    logger.info("Step 1: Creating sample customer orders data")
    orders_file = create_customer_orders_data()

    try:
        # Step 2: Load orders from CSV
        logger.info("Step 2: Loading orders from CSV")
        orders = load_orders_from_csv(orders_file)

        # Step 3: Process orders concurrently using .map()
        logger.info(f"Step 3: Processing {len(orders)} orders concurrently")

        # Validate all orders concurrently
        validation_results = validate_order.map(orders)

        # Calculate totals for all orders concurrently
        totals_results = calculate_order_totals.map(orders)

        # Check inventory for all orders concurrently
        inventory_results = check_inventory_availability.map(orders)

        # Step 4: Combine results and process fulfillment
        logger.info("Step 4: Processing order fulfillment")
        fulfillment_results = process_order_fulfillment.map(
            orders, validation_results, totals_results, inventory_results
        )

        # Step 5: Generate summary
        logger.info("Step 5: Generating processing summary")
        summary = generate_processing_summary(fulfillment_results)

        # Step 6: Save report
        logger.info("Step 6: Saving fulfillment report")
        report_file = save_fulfillment_report(summary, fulfillment_results)

        logger.info("RPA3 Workflow completed successfully")
        logger.info(f"Report saved to: {report_file}")

        return summary

    finally:
        # Cleanup
        try:
            Path(orders_file).unlink()
            logger.info(f"Cleaned up temporary file: {orders_file}")
        except FileNotFoundError:
            logger.warning(f"File not found for cleanup: {orders_file}")


def _run_distributed_rpa3_workflow(batch_size: int, logger) -> dict[str, Any]:
    """Run the distributed RPA3 workflow."""
    logger.info("Running distributed RPA3 workflow")

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
    flow_name = "rpa3_concurrent_processing"
    records = processor.claim_records_batch(flow_name, batch_size)

    if not records:
        logger.info("No records available for distributed processing")
        return {
            "flow_name": flow_name,
            "records_processed": 0,
            "message": "No records to process",
        }

    # Process records using .map()
    results = process_rpa3_record.map(records)

    # Generate summary
    completed_count = sum(1 for r in results if r["status"] == "completed")
    failed_count = sum(1 for r in results if r["status"] == "failed")

    # Aggregate order processing results
    total_orders = sum(
        r.get("result", {}).get("total_orders", 0)
        for r in results
        if r["status"] == "completed"
    )
    approved_orders = sum(
        r.get("result", {}).get("approved_orders", 0)
        for r in results
        if r["status"] == "completed"
    )

    summary = {
        "flow_name": flow_name,
        "records_processed": len(records),
        "records_completed": completed_count,
        "records_failed": failed_count,
        "success_rate": (completed_count / len(records) * 100) if records else 0,
        "total_orders": total_orders,
        "approved_orders": approved_orders,
        "approval_rate": (approved_orders / total_orders * 100)
        if total_orders > 0
        else 0,
        "processor_instance": processor.instance_id,
    }

    logger.info(
        f"Distributed RPA3 workflow completed: {completed_count}/{len(records)} successful"
    )
    return summary


@task(name="process-rpa3-record", retries=0)
def process_rpa3_record(record: dict[str, Any]) -> dict[str, Any]:
    """Process individual RPA3 record with distributed processing."""
    logger = get_run_logger()
    record_id = record["id"]
    payload = record["payload"]

    logger.info(f"Processing RPA3 record {record_id}")

    try:
        # Initialize processor for status updates
        rpa_db_manager = DatabaseManager("rpa_db")
        processor = DistributedProcessor(rpa_db_manager)

        # Process the record using standard RPA3 logic
        # Extract orders data from payload
        orders_data = payload.get("orders", [])

        if not orders_data:
            raise ValueError("No orders data found in payload")

        # Process each order through the standard pipeline
        validation_results = []
        totals_results = []
        inventory_results = []

        for order in orders_data:
            validation_results.append(validate_order.fn(order))
            totals_results.append(calculate_order_totals.fn(order))
            inventory_results.append(check_inventory_availability.fn(order))

        # Process fulfillment
        fulfillment_results = []
        for i, order in enumerate(orders_data):
            fulfillment_result = process_order_fulfillment.fn(
                order, validation_results[i], totals_results[i], inventory_results[i]
            )
            fulfillment_results.append(fulfillment_result)

        # Generate summary
        summary = generate_processing_summary.fn(fulfillment_results)

        # Save report
        report_file = save_fulfillment_report.fn(summary, fulfillment_results)

        # Prepare result
        result = {
            "summary": summary,
            "report_file": str(report_file),
            "processed_at": datetime.now().isoformat(),
        }

        # Mark as completed
        processor.mark_record_completed(record_id, result)

        logger.info(f"Successfully processed RPA3 record {record_id}")
        return {"record_id": record_id, "status": "completed", "result": summary}

    except Exception as e:
        # Mark as failed
        error_message = str(e)
        try:
            processor.mark_record_failed(record_id, error_message)
        except Exception:
            pass  # Don't fail if we can't update status

        logger.error(f"Failed to process RPA3 record {record_id}: {error_message}")
        return {"record_id": record_id, "status": "failed", "error": error_message}


if __name__ == "__main__":
    # Run the workflow
    result = rpa3_workflow()
    print(f"\nRPA3 Workflow completed! Summary: {result}")
