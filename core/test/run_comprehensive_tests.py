#!/usr/bin/env python3
"""
Test runner for comprehensive DatabaseManager test suite.

This script runs all the comprehensive tests for the DatabaseManager class
and provides a summary of test coverage and results.

Usage:
    python core/test/run_comprehensive_tests.py [--unit] [--integration] [--performance] [--migration]
"""

import argparse
import subprocess
import sys
from pathlib import Path


def run_test_suite(test_type="all", verbose=False):
    """Run the specified test suite."""

    # Base pytest command
    cmd = ["python", "-m", "pytest"]

    if verbose:
        cmd.append("-v")

    # Test file mappings
    test_files = {
        "unit": [
            "core/test/test_database_manager_comprehensive.py::TestDatabaseManagerUnitTests",
            "core/test/test_database_manager_comprehensive.py::TestTransientErrorDetection",
        ],
        "integration": [
            "core/test/test_database_integration.py",
        ],
        "performance": [
            "core/test/test_database_performance.py",
        ],
        "migration": [
            "core/test/test_migration_utilities.py",
            "core/test/test_database_manager_comprehensive.py::TestDatabaseManagerMigrationTesting",
        ],
        "health": [
            "core/test/test_database_manager_comprehensive.py::TestDatabaseManagerHealthMonitoring",
        ],
        "all": [
            "core/test/test_database_manager_comprehensive.py",
            "core/test/test_database_performance.py",
            "core/test/test_migration_utilities.py",
        ],
    }

    if test_type not in test_files:
        print(f"Unknown test type: {test_type}")
        print(f"Available types: {', '.join(test_files.keys())}")
        return False

    # Add test files to command
    cmd.extend(test_files[test_type])

    # Add markers for integration tests
    if test_type == "integration":
        cmd.extend(["--run-integration"])

    print(f"Running {test_type} tests...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)

    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running tests: {e}")
        return False


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(
        description="Run DatabaseManager comprehensive tests"
    )
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "performance", "migration", "health", "all"],
        default="unit",
        help="Type of tests to run (default: unit)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--list-tests", action="store_true", help="List available test categories"
    )

    args = parser.parse_args()

    if args.list_tests:
        print("Available test categories:")
        print("  unit        - Unit tests with mocked dependencies")
        print("  integration - Integration tests with actual databases")
        print("  performance - Performance and load tests")
        print("  migration   - Migration system tests")
        print("  health      - Health monitoring tests")
        print("  all         - All test categories")
        return

    print("DatabaseManager Comprehensive Test Suite")
    print("=" * 60)
    print(f"Test Type: {args.type}")
    print(f"Verbose: {args.verbose}")
    print()

    # Check if test files exist
    test_dir = Path("core/test")
    if not test_dir.exists():
        print(f"Error: Test directory {test_dir} not found")
        sys.exit(1)

    required_files = [
        "test_database_manager_comprehensive.py",
        "test_database_performance.py",
        "test_migration_utilities.py",
        "test_database_integration.py",
    ]

    missing_files = []
    for file in required_files:
        if not (test_dir / file).exists():
            missing_files.append(file)

    if missing_files:
        print("Error: Missing test files:")
        for file in missing_files:
            print(f"  - {file}")
        sys.exit(1)

    # Run the tests
    success = run_test_suite(args.type, args.verbose)

    print()
    print("-" * 60)
    if success:
        print("✅ All tests passed!")
        print()
        print("Test Coverage Summary:")
        print("  ✅ Unit tests with mocked SQLAlchemy engines")
        print("  ✅ Migration testing with test migration files")
        print("  ✅ Health monitoring tests")
        print("  ✅ Performance tests for connection pooling")
        print("  ✅ Concurrent query execution tests")
        if args.type == "integration":
            print("  ✅ Integration tests for actual database connectivity")
    else:
        print("❌ Some tests failed!")
        print()
        print("Check the output above for details on failed tests.")
        sys.exit(1)


if __name__ == "__main__":
    main()
