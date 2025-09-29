#!/usr/bin/env python3
"""
Script to run all example flows demonstrating DatabaseManager integration.

This script provides a convenient way to execute all example flows and see
their results. It's useful for:
1. Testing the example implementations
2. Demonstrating DatabaseManager capabilities
3. Validating flow integration patterns
4. Troubleshooting database connectivity
"""

import sys
from datetime import datetime
from typing import Any

from flows.examples.concurrent_database_processing import (
    concurrent_database_processing_flow,
)
from flows.examples.database_integration_example import (
    database_integration_example_flow,
)
from flows.examples.health_check_integration import health_check_integration_flow
from flows.examples.production_error_handling import production_error_handling_flow


def print_separator(title: str):
    """Print a formatted separator with title."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def print_result_summary(result: dict[str, Any], flow_name: str):
    """Print a summary of flow execution results."""
    print(f"\n{flow_name} Results:")
    print("-" * 40)

    # Extract key information based on flow type
    if "flow_execution" in result:
        flow_exec = result["flow_execution"]
        print(f"Status: {flow_exec.get('status', 'unknown')}")
        print(f"Execution Time: {flow_exec.get('execution_time', 'unknown')}")

        if "database_name" in flow_exec:
            print(f"Database: {flow_exec['database_name']}")
        if "source_database" in flow_exec and "target_database" in flow_exec:
            print(f"Source DB: {flow_exec['source_database']}")
            print(f"Target DB: {flow_exec['target_database']}")

    # Print specific metrics based on flow type
    if "execution_metrics" in result:
        metrics = result["execution_metrics"]
        print(f"Total Orders: {metrics.get('total_orders', 0)}")
        print(f"Successful: {metrics.get('successful_orders', 0)}")
        print(f"Avg Processing Time: {metrics.get('avg_processing_time_ms', 0)}ms")

    if "error_handling" in result:
        error_handling = result["error_handling"]
        print(f"Total Operations: {error_handling.get('total_operations', 0)}")
        print(
            f"Successful Operations: {error_handling.get('successful_operations', 0)}"
        )
        print(f"Failed Operations: {error_handling.get('failed_operations', 0)}")

    if "health_checks" in result and result["health_checks"]:
        print("Health Check Results:")
        for db_name, health_data in result["health_checks"].items():
            status = health_data.get("overall_status", "unknown")
            print(f"  {db_name}: {status}")


def run_database_integration_example():
    """Run the database integration example flow."""
    print_separator("DATABASE INTEGRATION EXAMPLE")

    try:
        result = database_integration_example_flow(
            source_database="rpa_db",
            target_database="rpa_db",
            run_migrations=True,
            health_check_required=True,
        )

        print_result_summary(result, "Database Integration Example")
        print("\n✅ Database Integration Example completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Database Integration Example failed: {e}")
        return False


def run_concurrent_processing_example():
    """Run the concurrent database processing example flow."""
    print_separator("CONCURRENT DATABASE PROCESSING EXAMPLE")

    try:
        result = concurrent_database_processing_flow(
            database_name="rpa_db", max_concurrent_tasks=4
        )

        print_result_summary(result, "Concurrent Database Processing")
        print("\n✅ Concurrent Database Processing Example completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Concurrent Database Processing Example failed: {e}")
        return False


def run_health_check_integration_example():
    """Run the health check integration example flow."""
    print_separator("HEALTH CHECK INTEGRATION EXAMPLE")

    try:
        result = health_check_integration_flow(
            target_databases=["rpa_db"],
            minimum_health_level="degraded",
            perform_trend_analysis=True,
            fail_on_prerequisites=False,
        )

        print_result_summary(result, "Health Check Integration")

        # Print recommendations
        if "recommendations" in result:
            print("\nRecommendations:")
            for i, recommendation in enumerate(result["recommendations"], 1):
                print(f"  {i}. {recommendation}")

        print("\n✅ Health Check Integration Example completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Health Check Integration Example failed: {e}")
        return False


def run_production_error_handling_example():
    """Run the production error handling example flow."""
    print_separator("PRODUCTION ERROR HANDLING EXAMPLE")

    try:
        result = production_error_handling_flow(
            primary_database="rpa_db",
            fallback_database=None,
            simulate_errors=True,  # Enable error simulation for demonstration
            enable_circuit_breaker=True,
        )

        print_result_summary(result, "Production Error Handling")

        # Print error handling details
        if "errors_logged" in result and result["errors_logged"]:
            print(f"\nErrors Logged: {len(result['errors_logged'])}")

        print("\n✅ Production Error Handling Example completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Production Error Handling Example failed: {e}")
        return False


def main():
    """Run all example flows and provide summary."""
    print_separator("DATABASEMANAGER EXAMPLE FLOWS DEMONSTRATION")
    print("This script demonstrates various DatabaseManager integration patterns")
    print("including health checks, concurrent processing, error handling, and more.")
    print(f"\nExecution started at: {datetime.now().isoformat()}")

    # Track results
    results = {
        "database_integration": False,
        "concurrent_processing": False,
        "health_check_integration": False,
        "production_error_handling": False,
    }

    # Run each example flow
    results["database_integration"] = run_database_integration_example()
    results["concurrent_processing"] = run_concurrent_processing_example()
    results["health_check_integration"] = run_health_check_integration_example()
    results["production_error_handling"] = run_production_error_handling_example()

    # Print final summary
    print_separator("EXECUTION SUMMARY")

    successful_flows = sum(results.values())
    total_flows = len(results)

    print(f"Execution completed at: {datetime.now().isoformat()}")
    print(f"Results: {successful_flows}/{total_flows} flows completed successfully")
    print()

    for flow_name, success in results.items():
        status = "✅ SUCCESS" if success else "❌ FAILED"
        print(f"  {flow_name.replace('_', ' ').title()}: {status}")

    if successful_flows == total_flows:
        print("\n🎉 All example flows completed successfully!")
        print("DatabaseManager integration examples are working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total_flows - successful_flows} flow(s) failed.")
        print("Check the error messages above for troubleshooting information.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
