#!/usr/bin/env python3
"""
Container Test Framework Runner

This script demonstrates how to use the ContainerTestSuite to run comprehensive
distributed processing validation tests. It can be used for manual testing,
CI/CD integration, or operational validation.

Usage:
    python core/test/run_container_tests.py [--config CONFIG_FILE] [--output OUTPUT_FILE]
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.config import ConfigManager
from core.database import DatabaseManager
from core.test.test_container_test_suite import ContainerTestSuite


def setup_database_managers(
    config_manager: ConfigManager,
) -> dict[str, DatabaseManager]:
    """
    Set up database managers for testing.

    Args:
        config_manager: Configuration manager instance

    Returns:
        Dictionary of database managers
    """
    database_managers = {}

    try:
        # Try to create RPA database manager
        rpa_db = DatabaseManager("rpa_db")
        database_managers["rpa_db"] = rpa_db
        print("✓ RPA database manager created successfully")
    except Exception as e:
        print(f"⚠ Could not create RPA database manager: {e}")

    try:
        # Try to create source database manager if configured
        source_db = DatabaseManager("source_db")
        database_managers["source_db"] = source_db
        print("✓ Source database manager created successfully")
    except Exception as e:
        print(f"⚠ Could not create source database manager: {e}")

    return database_managers


def run_comprehensive_container_tests(
    database_managers: dict[str, DatabaseManager],
    config_manager: ConfigManager,
    test_config: dict[str, Any],
) -> dict[str, Any]:
    """
    Run comprehensive container tests.

    Args:
        database_managers: Dictionary of database managers
        config_manager: Configuration manager instance
        test_config: Test configuration parameters

    Returns:
        Comprehensive test report
    """
    print("\n" + "=" * 60)
    print("CONTAINER TEST FRAMEWORK - COMPREHENSIVE VALIDATION")
    print("=" * 60)

    # Initialize test suite
    test_suite = ContainerTestSuite(
        database_managers=database_managers,
        config_manager=config_manager,
        enable_performance_monitoring=True,
    )

    print(f"✓ Test suite initialized with {len(database_managers)} database managers")

    # Test 1: Distributed Processing Tests
    print("\n1. Running Distributed Processing Tests...")
    print("-" * 40)

    distributed_result = test_suite.run_distributed_processing_tests(
        flow_name=test_config.get("flow_name", "container_validation_flow"),
        record_count=test_config.get("record_count", 50),
        container_count=test_config.get("container_count", 3),
        batch_size=test_config.get("batch_size", 10),
    )

    print(f"   Status: {distributed_result.status.upper()}")
    print(f"   Duration: {distributed_result.duration:.2f}s")
    if distributed_result.errors:
        print(f"   Errors: {len(distributed_result.errors)}")
        for error in distributed_result.errors[:3]:  # Show first 3 errors
            print(f"     - {error}")
    if distributed_result.warnings:
        print(f"   Warnings: {len(distributed_result.warnings)}")

    # Test 2: Performance Tests
    print("\n2. Running Performance Tests...")
    print("-" * 40)

    performance_result = test_suite.run_performance_tests(
        target_throughput=test_config.get("target_throughput", 30),
        test_duration_seconds=test_config.get("performance_duration", 30),
        container_count=test_config.get("performance_containers", 2),
    )

    print(f"   Status: {performance_result.status.upper()}")
    print(f"   Duration: {performance_result.duration:.2f}s")
    if performance_result.errors:
        print(f"   Errors: {len(performance_result.errors)}")
    if performance_result.warnings:
        print(f"   Warnings: {len(performance_result.warnings)}")

    # Test 3: Fault Tolerance Tests
    print("\n3. Running Fault Tolerance Tests...")
    print("-" * 40)

    fault_scenarios = test_config.get(
        "fault_scenarios",
        ["container_crash", "database_connection_loss", "network_partition"],
    )

    fault_result = test_suite.run_fault_tolerance_tests(test_scenarios=fault_scenarios)

    print(f"   Status: {fault_result.status.upper()}")
    print(f"   Duration: {fault_result.duration:.2f}s")
    print(f"   Scenarios tested: {len(fault_scenarios)}")
    if fault_result.errors:
        print(f"   Errors: {len(fault_result.errors)}")
    if fault_result.warnings:
        print(f"   Warnings: {len(fault_result.warnings)}")

    # Test 4: Integration Tests
    print("\n4. Running Integration Tests...")
    print("-" * 40)

    integration_workflows = test_config.get(
        "integration_workflows",
        [
            "complete_processing_workflow",
            "multi_container_coordination",
            "health_monitoring_integration",
        ],
    )

    integration_result = test_suite.run_integration_tests(
        test_workflows=integration_workflows
    )

    print(f"   Status: {integration_result.status.upper()}")
    print(f"   Duration: {integration_result.duration:.2f}s")
    print(f"   Workflows tested: {len(integration_workflows)}")
    if integration_result.errors:
        print(f"   Errors: {len(integration_result.errors)}")
    if integration_result.warnings:
        print(f"   Warnings: {len(integration_result.warnings)}")

    # Generate comprehensive report
    print("\n5. Generating Comprehensive Report...")
    print("-" * 40)

    report = test_suite.generate_comprehensive_report()

    # Print summary
    summary = report.get("test_report_summary", {})
    print(f"   Total tests: {summary.get('total_tests', 0)}")
    print(f"   Passed: {summary.get('passed_tests', 0)}")
    print(f"   Failed: {summary.get('failed_tests', 0)}")
    print(f"   Success rate: {summary.get('success_rate_percent', 0):.1f}%")
    print(f"   Total duration: {summary.get('total_duration_seconds', 0):.2f}s")

    # Print recommendations
    recommendations = report.get("recommendations", [])
    if recommendations:
        print("\n   Recommendations:")
        for i, rec in enumerate(recommendations[:5], 1):  # Show first 5
            print(f"     {i}. {rec}")

    # Cleanup
    test_suite.cleanup_test_environment()

    return report


def save_report(report: dict[str, Any], output_file: str) -> None:
    """
    Save test report to file.

    Args:
        report: Test report dictionary
        output_file: Output file path
    """
    try:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n✓ Test report saved to: {output_path}")

    except Exception as e:
        print(f"\n⚠ Failed to save report: {e}")


def load_test_config(config_file: str) -> dict[str, Any]:
    """
    Load test configuration from file.

    Args:
        config_file: Configuration file path

    Returns:
        Test configuration dictionary
    """
    try:
        with open(config_file) as f:
            config = json.load(f)
        print(f"✓ Test configuration loaded from: {config_file}")
        return config
    except Exception as e:
        print(f"⚠ Could not load config file {config_file}: {e}")
        print("Using default configuration...")
        return {}


def main():
    """Main function to run container tests."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive container test framework validation"
    )
    parser.add_argument(
        "--config", type=str, help="Test configuration file (JSON format)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="container_test_report.json",
        help="Output file for test report (default: container_test_report.json)",
    )
    parser.add_argument(
        "--quick", action="store_true", help="Run quick tests with reduced parameters"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    print("Container Test Framework Runner")
    print("=" * 50)

    # Load configuration
    if args.config:
        test_config = load_test_config(args.config)
    else:
        test_config = {}

    # Apply quick test settings if requested
    if args.quick:
        test_config.update(
            {
                "record_count": 20,
                "container_count": 2,
                "batch_size": 5,
                "target_throughput": 15,
                "performance_duration": 10,
                "performance_containers": 1,
                "fault_scenarios": ["container_crash", "database_connection_loss"],
                "integration_workflows": ["complete_processing_workflow"],
            }
        )
        print("✓ Quick test mode enabled")

    # Initialize configuration manager
    try:
        config_manager = ConfigManager()
        print(
            f"✓ Configuration manager initialized (environment: {config_manager.environment})"
        )
    except Exception as e:
        print(f"✗ Failed to initialize configuration manager: {e}")
        return 1

    # Setup database managers
    database_managers = setup_database_managers(config_manager)

    if not database_managers:
        print("\n✗ No database managers available - cannot run tests")
        print("Please ensure database configuration is properly set up")
        return 1

    # Run comprehensive tests
    try:
        start_time = time.time()

        report = run_comprehensive_container_tests(
            database_managers=database_managers,
            config_manager=config_manager,
            test_config=test_config,
        )

        total_time = time.time() - start_time

        print("\n" + "=" * 60)
        print("TEST EXECUTION COMPLETED")
        print("=" * 60)
        print(f"Total execution time: {total_time:.2f}s")

        # Save report
        save_report(report, args.output)

        # Determine exit code based on test results
        summary = report.get("test_report_summary", {})
        failed_tests = summary.get("failed_tests", 0)

        if failed_tests > 0:
            print(f"\n⚠ {failed_tests} test(s) failed - see report for details")
            return 1
        else:
            print("\n✓ All tests passed successfully!")
            return 0

    except KeyboardInterrupt:
        print("\n\n⚠ Test execution interrupted by user")
        return 130
    except Exception as e:
        print(f"\n✗ Test execution failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
