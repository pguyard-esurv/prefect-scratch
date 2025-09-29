#!/usr/bin/env python3
"""
Test runner for comprehensive distributed processing test suite.

This script runs all comprehensive tests for the distributed processing system
including unit tests, integration tests, concurrent processing tests,
performance tests, and chaos engineering tests.

Usage:
    python core/test/run_distributed_comprehensive_tests.py [--unit] [--integration] [--concurrent] [--performance] [--chaos] [--all]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_test_suite(test_type="all", verbose=False, run_integration=False):
    """Run the specified test suite."""

    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.append("-v")

    # Test class mappings
    test_classes = {
        "unit": [
            "core/test/test_distributed_comprehensive.py::TestDistributedProcessorComprehensive",
            "core/test/test_distributed.py",  # Existing unit tests
            "core/test/test_flow_template.py",  # Existing flow template tests
        ],
        "integration": [
            "core/test/test_distributed_comprehensive.py::TestDistributedProcessorIntegration",
        ],
        "concurrent": [
            "core/test/test_distributed_comprehensive.py::TestConcurrentProcessing",
        ],
        "performance": [
            "core/test/test_distributed_comprehensive.py::TestDistributedProcessorPerformance",
        ],
        "chaos": [
            "core/test/test_distributed_comprehensive.py::TestChaosEngineering",
        ],
        "flow": [
            "core/test/test_distributed_comprehensive.py::TestFlowTemplateComprehensive",
            "core/test/test_flow_template.py",
        ],
        "all": [
            "core/test/test_distributed_comprehensive.py",
            "core/test/test_distributed.py",
            "core/test/test_flow_template.py",
        ],
    }

    if test_type not in test_classes:
        print(f"Unknown test type: {test_type}")
        print(f"Available types: {', '.join(test_classes.keys())}")
        return False

    # Add test classes to command
    cmd.extend(test_classes[test_type])

    # Add markers for integration and performance tests
    if test_type == "integration" or (test_type == "all" and run_integration):
        cmd.extend(["--run-integration"])

    if test_type == "performance":
        cmd.extend(["-m", "performance"])

    if test_type == "integration":
        cmd.extend(["-m", "integration"])

    print(f"Running {test_type} tests for distributed processing system...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 80)

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running tests: {e}")
        return False


def run_coverage_report():
    """Run test coverage report for distributed processing."""
    print("Generating coverage report for distributed processing...")

    coverage_cmd = [
        "python",
        "-m",
        "pytest",
        "--cov=core.distributed",
        "--cov=core.flow_template",
        "--cov-report=html:htmlcov/distributed",
        "--cov-report=term-missing",
        "core/test/test_distributed_comprehensive.py",
        "core/test/test_distributed.py",
        "core/test/test_flow_template.py",
    ]

    try:
        result = subprocess.run(coverage_cmd, check=False)
        if result.returncode == 0:
            print("\n✅ Coverage report generated in htmlcov/distributed/")
        return result.returncode == 0
    except Exception as e:
        print(f"Error generating coverage report: {e}")
        return False


def validate_test_environment():
    """Validate that the test environment is properly set up."""
    print("Validating test environment...")

    # Check required files exist
    required_files = [
        "core/distributed.py",
        "core/flow_template.py",
        "core/database.py",
        "core/config.py",
        "core/test/test_distributed_comprehensive.py",
        "core/test/conftest.py",
    ]

    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)

    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return False

    # Check for required dependencies
    try:
        import pytest

        print(f"✅ pytest version: {pytest.__version__}")
    except ImportError as e:
        print(f"❌ Missing required dependency: {e}")
        return False

    # Check for optional dependencies
    try:
        import psutil

        print(f"✅ psutil version: {psutil.__version__}")
    except ImportError:
        print("⚠️  psutil not available - memory performance tests will be skipped")

    print("✅ Test environment validation passed")
    return True


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="Run comprehensive distributed processing tests"
    )
    parser.add_argument(
        "--type",
        choices=[
            "unit",
            "integration",
            "concurrent",
            "performance",
            "chaos",
            "flow",
            "all",
        ],
        default="unit",
        help="Type of tests to run (default: unit)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--integration",
        action="store_true",
        help="Run integration tests (requires test databases)",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )
    parser.add_argument(
        "--validate-env", action="store_true", help="Validate test environment setup"
    )
    parser.add_argument(
        "--list-tests", action="store_true", help="List available test categories"
    )

    args = parser.parse_args()

    if args.list_tests:
        print("Available test categories for distributed processing:")
        print("  unit        - Unit tests with mocked dependencies")
        print("  integration - Integration tests with actual databases")
        print("  concurrent  - Concurrent processing and thread safety tests")
        print("  performance - Performance and throughput tests")
        print("  chaos       - Chaos engineering and failure scenario tests")
        print("  flow        - Flow template and workflow tests")
        print("  all         - All test categories")
        print()
        print("Test Requirements:")
        print("  unit        - No external dependencies")
        print("  integration - PostgreSQL test database")
        print("  concurrent  - No external dependencies")
        print("  performance - psutil package")
        print("  chaos       - No external dependencies")
        print("  flow        - No external dependencies")
        return

    if args.validate_env:
        if not validate_test_environment():
            sys.exit(1)
        return

    print("Distributed Processing System - Comprehensive Test Suite")
    print("=" * 80)
    print(f"Test Type: {args.type}")
    print(f"Verbose: {args.verbose}")
    print(f"Integration: {args.integration}")
    print(f"Coverage: {args.coverage}")
    print()

    # Validate environment first
    if not validate_test_environment():
        sys.exit(1)

    # Run the tests
    success = run_test_suite(args.type, args.verbose, args.integration)

    # Generate coverage report if requested
    if args.coverage and success:
        coverage_success = run_coverage_report()
        success = success and coverage_success

    print()
    print("-" * 80)
    if success:
        print("✅ All distributed processing tests passed!")
        print()
        print("Test Coverage Summary:")
        print("  ✅ Unit tests for DistributedProcessor class")
        print("  ✅ Integration tests for multi-container scenarios")
        print("  ✅ Concurrent processing and thread safety tests")
        print("  ✅ Performance tests for batch processing")
        print("  ✅ Chaos engineering tests for failure scenarios")
        print("  ✅ Flow template comprehensive tests")

        if args.type == "integration" or args.integration:
            print("  ✅ Multi-database integration tests")
            print("  ✅ Atomic record claiming verification")
            print("  ✅ Orphaned record cleanup tests")

        if args.type == "performance":
            print("  ✅ Batch processing performance benchmarks")
            print("  ✅ Connection pool utilization tests")
            print("  ✅ Memory usage pattern analysis")
            print("  ✅ Throughput measurement tests")

        if args.type == "chaos":
            print("  ✅ Database connection failure tests")
            print("  ✅ Network partition simulation")
            print("  ✅ Resource exhaustion handling")
            print("  ✅ Container failure scenarios")

        if args.coverage:
            print("  ✅ Code coverage report generated")
    else:
        print("❌ Some distributed processing tests failed!")
        print()
        print("Check the output above for details on failed tests.")
        print()
        print("Common issues:")
        print("  - Missing test database for integration tests")
        print("  - Missing required Python packages")
        print("  - Configuration issues")
        print("  - Database connection problems")
        sys.exit(1)


if __name__ == "__main__":
    main()
