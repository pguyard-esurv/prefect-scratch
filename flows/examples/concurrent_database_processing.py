"""
Example flow demonstrating concurrent database operations using Prefect .map() with DatabaseManager.

This example shows how to:
1. Process multiple records concurrently using .map()
2. Use DatabaseManager safely in concurrent tasks
3. Handle database operations across multiple concurrent executions
4. Implement proper error handling for concurrent database operations
5. Monitor and log concurrent database performance
"""

import json
import time
from datetime import datetime
from typing import Any, Optional

from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from core.database import DatabaseManager


@task
def validate_and_process_order(
    order_data: dict[str, Any], database_name: str
) -> dict[str, Any]:
    """
    Validate and process a single order using DatabaseManager.

    This task demonstrates safe DatabaseManager usage in concurrent execution.
    Each task gets its own DatabaseManager instance and connection.

    Args:
        order_data: Dictionary containing order information
        database_name: Name of the database to use

    Returns:
        Dictionary with processing results
    """
    logger = get_run_logger()
    order_id = order_data.get("order_id", "unknown")

    start_time = time.time()

    try:
        logger.info(f"Processing order {order_id} in concurrent task")

        with DatabaseManager(database_name) as db:
            # Step 1: Validate order data
            validation_errors = []

            if not order_data.get("customer_name"):
                validation_errors.append("Missing customer name")
            if not order_data.get("product"):
                validation_errors.append("Missing product")
            if order_data.get("quantity", 0) <= 0:
                validation_errors.append("Invalid quantity")
            if order_data.get("unit_price", 0) <= 0:
                validation_errors.append("Invalid unit price")

            if validation_errors:
                logger.warning(
                    f"Order {order_id} validation failed: {validation_errors}"
                )
                return {
                    "order_id": order_id,
                    "status": "validation_failed",
                    "errors": validation_errors,
                    "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                }

            # Step 2: Calculate order totals
            quantity = order_data["quantity"]
            unit_price = order_data["unit_price"]
            subtotal = quantity * unit_price

            # Apply regional tax rates
            tax_rates = {"North": 0.08, "South": 0.07, "East": 0.09, "West": 0.08}
            region = order_data.get("region", "North")
            tax_rate = tax_rates.get(region, 0.08)
            tax_amount = subtotal * tax_rate

            # Apply priority-based discounts
            discount_rates = {"low": 0.0, "medium": 0.05, "high": 0.10}
            priority = order_data.get("priority", "medium")
            discount_rate = discount_rates.get(priority, 0.0)
            discount_amount = subtotal * discount_rate

            total_amount = subtotal + tax_amount - discount_amount

            # Step 3: Check if order already exists (simulate duplicate check)
            check_query = "SELECT COUNT(*) as count FROM customer_orders WHERE order_id = :order_id"
            existing_orders = db.execute_query(check_query, {"order_id": order_id})

            if existing_orders[0]["count"] > 0:
                logger.warning(f"Order {order_id} already exists, skipping insert")
                return {
                    "order_id": order_id,
                    "status": "duplicate",
                    "message": "Order already exists",
                    "processing_time_ms": round((time.time() - start_time) * 1000, 2),
                }

            # Step 4: Insert order into database
            insert_query = """
            INSERT INTO customer_orders (
                order_id, customer_id, customer_name, product, quantity, unit_price,
                subtotal, tax_amount, discount_amount, total_amount, order_date,
                priority, region, fulfillment_status, processed_by_flow
            ) VALUES (
                :order_id, :customer_id, :customer_name, :product, :quantity, :unit_price,
                :subtotal, :tax_amount, :discount_amount, :total_amount, :order_date,
                :priority, :region, :fulfillment_status, :processed_by_flow
            )
            """

            insert_params = {
                "order_id": order_id,
                "customer_id": order_data.get(
                    "customer_id", f"CUST-{order_id.split('-')[1]}"
                ),
                "customer_name": order_data["customer_name"],
                "product": order_data["product"],
                "quantity": quantity,
                "unit_price": unit_price,
                "subtotal": round(subtotal, 2),
                "tax_amount": round(tax_amount, 2),
                "discount_amount": round(discount_amount, 2),
                "total_amount": round(total_amount, 2),
                "order_date": order_data.get("order_date", datetime.now().date()),
                "priority": priority,
                "region": region,
                "fulfillment_status": "pending",
                "processed_by_flow": "concurrent-database-processing",
            }

            db.execute_query(insert_query, insert_params)

            processing_time = round((time.time() - start_time) * 1000, 2)

            logger.info(
                f"Order {order_id} processed successfully in {processing_time}ms"
            )

            return {
                "order_id": order_id,
                "status": "success",
                "total_amount": round(total_amount, 2),
                "tax_amount": round(tax_amount, 2),
                "discount_amount": round(discount_amount, 2),
                "processing_time_ms": processing_time,
            }

    except Exception as e:
        processing_time = round((time.time() - start_time) * 1000, 2)
        logger.error(f"Failed to process order {order_id}: {e}")

        return {
            "order_id": order_id,
            "status": "error",
            "error": str(e),
            "processing_time_ms": processing_time,
        }


@task
def check_inventory_concurrent(
    product_info: dict[str, Any], database_name: str
) -> dict[str, Any]:
    """
    Check inventory for a product concurrently.

    This simulates an inventory check that might involve database queries
    and demonstrates concurrent database access patterns.

    Args:
        product_info: Dictionary with product and quantity information
        database_name: Name of the database to use

    Returns:
        Dictionary with inventory check results
    """
    logger = get_run_logger()
    product = product_info.get("product", "unknown")
    requested_quantity = product_info.get("quantity", 0)

    start_time = time.time()

    try:
        logger.info(
            f"Checking inventory for {product} (quantity: {requested_quantity})"
        )

        with DatabaseManager(database_name) as db:
            # Simulate inventory lookup with database query
            # In real scenario, this would query actual inventory tables

            # Mock inventory data based on product type
            inventory_query = """
            SELECT
                :product as product,
                CASE
                    WHEN :product LIKE '%Premium%' THEN 50
                    WHEN :product LIKE '%Standard%' THEN 100
                    WHEN :product LIKE '%Budget%' THEN 200
                    ELSE 75
                END as available_quantity
            """

            inventory_result = db.execute_query(inventory_query, {"product": product})
            available_quantity = inventory_result[0]["available_quantity"]

            # Simulate some processing delay
            time.sleep(0.1)

            in_stock = available_quantity >= requested_quantity
            shortage = (
                max(0, requested_quantity - available_quantity) if not in_stock else 0
            )

            processing_time = round((time.time() - start_time) * 1000, 2)

            result = {
                "product": product,
                "requested_quantity": requested_quantity,
                "available_quantity": available_quantity,
                "in_stock": in_stock,
                "shortage": shortage,
                "processing_time_ms": processing_time,
            }

            status = "Available" if in_stock else f"Shortage of {shortage} units"
            logger.info(
                f"Inventory check for {product}: {status} (processed in {processing_time}ms)"
            )

            return result

    except Exception as e:
        processing_time = round((time.time() - start_time) * 1000, 2)
        logger.error(f"Inventory check failed for {product}: {e}")

        return {
            "product": product,
            "requested_quantity": requested_quantity,
            "error": str(e),
            "processing_time_ms": processing_time,
            "in_stock": False,
        }


@task
def update_order_status_concurrent(
    order_result: dict[str, Any], inventory_result: dict[str, Any], database_name: str
) -> dict[str, Any]:
    """
    Update order status based on processing and inventory results.

    This task demonstrates how to combine results from multiple concurrent
    operations and perform follow-up database operations.

    Args:
        order_result: Result from order processing
        inventory_result: Result from inventory check
        database_name: Name of the database to use

    Returns:
        Dictionary with final order status
    """
    logger = get_run_logger()
    order_id = order_result.get("order_id", "unknown")

    start_time = time.time()

    try:
        logger.info(f"Updating status for order {order_id}")

        with DatabaseManager(database_name) as db:
            # Determine final status based on processing and inventory results
            if order_result.get("status") != "success":
                final_status = "rejected"
                status_reason = (
                    f"Processing failed: {order_result.get('error', 'Unknown error')}"
                )
            elif not inventory_result.get("in_stock", False):
                final_status = "pending"
                status_reason = f"Insufficient inventory: {inventory_result.get('shortage', 0)} units short"
            else:
                final_status = "approved"
                status_reason = "Order approved and ready for fulfillment"

            # Update order status in database (only if order was successfully created)
            if order_result.get("status") == "success":
                update_query = """
                UPDATE customer_orders
                SET fulfillment_status = :status, updated_at = :updated_at
                WHERE order_id = :order_id
                """

                update_params = {
                    "status": final_status,
                    "updated_at": datetime.now(),
                    "order_id": order_id,
                }

                db.execute_query(update_query, update_params)

                logger.info(f"Updated order {order_id} status to '{final_status}'")

            processing_time = round((time.time() - start_time) * 1000, 2)

            return {
                "order_id": order_id,
                "final_status": final_status,
                "status_reason": status_reason,
                "order_processing": order_result,
                "inventory_check": inventory_result,
                "processing_time_ms": processing_time,
            }

    except Exception as e:
        processing_time = round((time.time() - start_time) * 1000, 2)
        logger.error(f"Failed to update status for order {order_id}: {e}")

        return {
            "order_id": order_id,
            "final_status": "error",
            "status_reason": f"Status update failed: {str(e)}",
            "error": str(e),
            "processing_time_ms": processing_time,
        }


@task
def log_concurrent_execution_metrics(
    processing_results: list[dict[str, Any]], database_name: str
) -> dict[str, Any]:
    """
    Log metrics from concurrent execution to database.

    Args:
        processing_results: List of results from concurrent processing
        database_name: Name of the database to use

    Returns:
        Dictionary with execution metrics
    """
    logger = get_run_logger()

    try:
        with DatabaseManager(database_name) as db:
            # Calculate metrics
            total_orders = len(processing_results)
            successful_orders = len(
                [r for r in processing_results if r.get("final_status") == "approved"]
            )
            pending_orders = len(
                [r for r in processing_results if r.get("final_status") == "pending"]
            )
            rejected_orders = len(
                [
                    r
                    for r in processing_results
                    if r.get("final_status") in ["rejected", "error"]
                ]
            )

            # Calculate processing times
            processing_times = [
                r.get("processing_time_ms", 0)
                for r in processing_results
                if r.get("processing_time_ms") is not None
            ]

            avg_processing_time = (
                sum(processing_times) / len(processing_times) if processing_times else 0
            )
            max_processing_time = max(processing_times) if processing_times else 0
            min_processing_time = min(processing_times) if processing_times else 0

            # Log execution summary
            log_query = """
            INSERT INTO flow_execution_logs (
                flow_name, flow_run_id, database_name, execution_start, execution_end,
                execution_duration_ms, status, records_processed, records_successful,
                records_failed, database_operations, metadata
            ) VALUES (
                :flow_name, :flow_run_id, :database_name, :execution_start, :execution_end,
                :execution_duration_ms, :status, :records_processed, :records_successful,
                :records_failed, :database_operations, :metadata
            )
            """

            execution_end = datetime.now()
            execution_start = (
                execution_end  # Approximate, in real scenario would track actual start
            )

            log_params = {
                "flow_name": "concurrent-database-processing",
                "flow_run_id": f"concurrent-flow-{execution_end.strftime('%Y%m%d-%H%M%S')}",
                "database_name": database_name,
                "execution_start": execution_start,
                "execution_end": execution_end,
                "execution_duration_ms": int(max_processing_time),  # Approximate
                "status": "completed",
                "records_processed": total_orders,
                "records_successful": successful_orders,
                "records_failed": rejected_orders,
                "database_operations": total_orders
                * 3,  # Estimate: insert + update + inventory check per order
                "metadata": json.dumps(
                    {
                        "concurrent_execution": True,
                        "avg_processing_time_ms": round(avg_processing_time, 2),
                        "max_processing_time_ms": max_processing_time,
                        "min_processing_time_ms": min_processing_time,
                        "pending_orders": pending_orders,
                        "approved_orders": successful_orders,
                        "rejected_orders": rejected_orders,
                    }
                ),
            }

            db.execute_query(log_query, log_params)

            metrics = {
                "total_orders": total_orders,
                "successful_orders": successful_orders,
                "pending_orders": pending_orders,
                "rejected_orders": rejected_orders,
                "avg_processing_time_ms": round(avg_processing_time, 2),
                "max_processing_time_ms": max_processing_time,
                "min_processing_time_ms": min_processing_time,
                "logged_at": execution_end.isoformat(),
            }

            logger.info(
                f"Logged concurrent execution metrics: {successful_orders}/{total_orders} orders approved"
            )
            return metrics

    except Exception as e:
        logger.error(f"Failed to log concurrent execution metrics: {e}")
        raise


@flow(
    name="concurrent-database-processing",
    task_runner=ConcurrentTaskRunner(),
    description="Example flow demonstrating concurrent database operations using .map()",
)
def concurrent_database_processing_flow(
    database_name: str = "rpa_db", max_concurrent_tasks: Optional[int] = None
) -> dict[str, Any]:
    """
    Demonstrate concurrent database processing using Prefect .map() with DatabaseManager.

    This flow shows how to:
    1. Process multiple orders concurrently using .map()
    2. Perform concurrent inventory checks
    3. Update order statuses based on combined results
    4. Handle database operations safely in concurrent tasks
    5. Log and monitor concurrent execution performance

    Args:
        database_name: Name of the database to use (default: rpa_db)
        max_concurrent_tasks: Maximum number of concurrent tasks (optional)

    Returns:
        Dictionary containing processing results and metrics
    """
    logger = get_run_logger()
    logger.info("Starting concurrent database processing flow")

    # Sample order data for concurrent processing
    sample_orders = [
        {
            "order_id": "CONC-001",
            "customer_name": "Alice Johnson",
            "product": "Premium Widget A",
            "quantity": 2,
            "unit_price": 25.50,
            "priority": "high",
            "region": "North",
            "order_date": "2024-01-20",
        },
        {
            "order_id": "CONC-002",
            "customer_name": "Bob Smith",
            "product": "Standard Widget B",
            "quantity": 5,
            "unit_price": 15.75,
            "priority": "medium",
            "region": "South",
            "order_date": "2024-01-20",
        },
        {
            "order_id": "CONC-003",
            "customer_name": "Charlie Brown",
            "product": "Budget Widget C",
            "quantity": 10,
            "unit_price": 8.99,
            "priority": "low",
            "region": "East",
            "order_date": "2024-01-20",
        },
        {
            "order_id": "CONC-004",
            "customer_name": "Diana Prince",
            "product": "Premium Widget A",
            "quantity": 1,
            "unit_price": 25.50,
            "priority": "high",
            "region": "West",
            "order_date": "2024-01-20",
        },
        {
            "order_id": "CONC-005",
            "customer_name": "Eve Wilson",
            "product": "Standard Widget B",
            "quantity": 3,
            "unit_price": 15.75,
            "priority": "medium",
            "region": "North",
            "order_date": "2024-01-20",
        },
        {
            "order_id": "CONC-006",
            "customer_name": "Frank Miller",
            "product": "Budget Widget C",
            "quantity": 8,
            "unit_price": 8.99,
            "priority": "low",
            "region": "South",
            "order_date": "2024-01-20",
        },
    ]

    try:
        logger.info(f"Processing {len(sample_orders)} orders concurrently")

        if max_concurrent_tasks:
            logger.info(f"Concurrency limit: {max_concurrent_tasks} tasks")

        # Step 1: Process all orders concurrently using .map()
        logger.info("Step 1: Processing orders concurrently")
        order_results = validate_and_process_order.map(
            sample_orders, [database_name] * len(sample_orders)
        )

        # Step 2: Check inventory for all products concurrently
        logger.info("Step 2: Checking inventory concurrently")
        inventory_results = check_inventory_concurrent.map(
            sample_orders,  # Contains product and quantity info
            [database_name] * len(sample_orders),
        )

        # Step 3: Update order statuses based on combined results
        logger.info("Step 3: Updating order statuses")
        final_results = update_order_status_concurrent.map(
            order_results, inventory_results, [database_name] * len(sample_orders)
        )

        # Step 4: Log execution metrics
        logger.info("Step 4: Logging execution metrics")
        execution_metrics = log_concurrent_execution_metrics(
            final_results, database_name
        )

        # Compile complete results
        complete_results = {
            "flow_execution": {
                "status": "completed",
                "execution_time": datetime.now().isoformat(),
                "database_name": database_name,
                "concurrent_tasks": len(sample_orders),
                "max_concurrent_limit": max_concurrent_tasks,
            },
            "processing_results": final_results,
            "execution_metrics": execution_metrics,
            "summary": {
                "total_orders": len(sample_orders),
                "successful_processing": len(
                    [r for r in order_results if r.get("status") == "success"]
                ),
                "inventory_available": len(
                    [r for r in inventory_results if r.get("in_stock", False)]
                ),
                "final_approved": execution_metrics.get("successful_orders", 0),
            },
        }

        logger.info("Concurrent database processing flow completed successfully")
        return complete_results

    except Exception as e:
        logger.error(f"Concurrent database processing flow failed: {e}")
        raise RuntimeError(f"Flow execution failed: {e}") from e


if __name__ == "__main__":
    # Run the concurrent processing example
    try:
        result = concurrent_database_processing_flow()
        print("\n" + "=" * 60)
        print("CONCURRENT DATABASE PROCESSING EXAMPLE COMPLETED")
        print("=" * 60)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        print(f"\nFlow execution failed: {e}")
