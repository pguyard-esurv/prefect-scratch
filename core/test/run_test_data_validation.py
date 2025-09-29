#!/usr/bin/env python3
"""
Comprehensive test data validation runner.

This script provides a command-line interface for running test data management
and validation workflows. It integrates DataManager and ResultValidator to
provide complete test lifecycle management.

Usage:
    python run_test_data_validation.py --scenario survey_processing --records 100
    python run_test_data_validation.py --all-scenarios --cleanup
    python run_test_data_validation.py --status
"""

import argparse
import sys
import time
from typing import Optional

from core.config import ConfigManager
from core.database import DatabaseManager
from core.test.test_data_manager import DataManager, DataScenarios
from core.test.test_validator import ResultValidator


class TestDataValidationRunner:
    """Comprehensive test data validation runner."""

    def __init__(self):
        """Initialize the test runner."""
        self.config_manager = ConfigManager()
        self.database_managers = self._initialize_database_managers()
        self.data_manager = DataManager(self.database_managers)
        self.validator = ResultValidator(self.database_managers)
        self.scenarios = DataScenarios()

    def _initialize_database_managers(self) -> dict[str, DatabaseManager]:
        """Initialize database managers."""
        try:
            database_managers = {}

            # Initialize RPA database manager
            try:
                rpa_db = DatabaseManager("rpa_db")
                database_managers["rpa_db"] = rpa_db
                print("✓ RPA database manager initialized")
            except Exception as e:
                print(f"✗ Failed to initialize RPA database manager: {e}")

            return database_managers

        except Exception as e:
            print(f"✗ Failed to initialize database managers: {e}")
            return {}

    def run_scenario_validation(
        self,
        scenario_name: str,
        record_count: Optional[int] = None,
        cleanup_after: bool = True,
    ) -> dict[str, any]:
        """
        Run validation for a specific scenario.

        Args:
            scenario_name: Name of the scenario to run
            record_count: Number of records to generate (optional)
            cleanup_after: Whether to cleanup after validation

        Returns:
            Dictionary with validation results
        """
        print(f"\n🚀 Running scenario validation: {scenario_name}")
        start_time = time.time()

        try:
            # Get scenario
            scenario = self._get_scenario(scenario_name, record_count)
            if not scenario:
                return {"error": f"Unknown scenario: {scenario_name}"}

            print(f"📊 Initializing test data ({scenario.record_count} records)...")

            # Initialize test data
            init_result = self.data_manager.initialize_test_scenario(scenario)
            if init_result["status"] != "success":
                return {
                    "error": f"Failed to initialize scenario: {init_result.get('error')}"
                }

            print(f"✓ Test data initialized in {init_result['duration_seconds']:.2f}s")

            # Simulate test execution (in real usage, this would be actual test execution)
            print("🔄 Simulating test execution...")
            test_results = self._simulate_test_execution(scenario)

            print(f"✓ Simulated processing of {len(test_results)} records")

            # Validate results
            print("🔍 Validating test results...")
            validation_result = self.validator.validate_test_results(
                scenario, test_results
            )

            print(f"✓ Validation completed: {validation_result.status}")
            if validation_result.errors:
                print(f"⚠️  Errors found: {len(validation_result.errors)}")
                for error in validation_result.errors[:3]:  # Show first 3 errors
                    print(f"   - {error}")

            if validation_result.warnings:
                print(f"⚠️  Warnings: {len(validation_result.warnings)}")

            # Generate report
            print("📋 Generating validation report...")
            report = self.validator.generate_comprehensive_report(
                f"Scenario Validation - {scenario_name}", [validation_result]
            )

            # Cleanup if requested
            if cleanup_after:
                print("🧹 Cleaning up test data...")
                cleanup_result = self.data_manager.cleanup_test_data([scenario_name])
                if cleanup_result["cleanup_summary"]["successful_cleanups"] > 0:
                    print("✓ Test data cleaned up")

            total_duration = time.time() - start_time
            print(f"✅ Scenario validation completed in {total_duration:.2f}s")

            return {
                "scenario_name": scenario_name,
                "status": "success",
                "validation_result": validation_result.to_dict(),
                "validation_result_obj": validation_result,  # Keep original object for export
                "report": report.to_dict(),
                "total_duration": total_duration,
            }

        except Exception as e:
            error_msg = f"Scenario validation failed: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}

    def run_all_scenarios(self, cleanup_after: bool = True) -> dict[str, any]:
        """
        Run validation for all available scenarios.

        Args:
            cleanup_after: Whether to cleanup after validation

        Returns:
            Dictionary with all validation results
        """
        print("\n🚀 Running validation for all scenarios")
        start_time = time.time()

        scenario_configs = [
            ("survey_processing", 50),
            ("order_processing", 75),
            ("high_volume_processing", 200),
            ("error_handling", 30),
        ]

        all_results = []
        validation_results = []

        for scenario_name, record_count in scenario_configs:
            print(f"\n--- Running {scenario_name} ---")

            try:
                # Get scenario
                scenario = self._get_scenario(scenario_name, record_count)

                # Initialize and run
                init_result = self.data_manager.initialize_test_scenario(scenario)
                if init_result["status"] != "success":
                    print(f"❌ Failed to initialize {scenario_name}")
                    continue

                # Simulate and validate
                test_results = self._simulate_test_execution(scenario)
                validation_result = self.validator.validate_test_results(
                    scenario, test_results
                )
                validation_results.append(validation_result)

                all_results.append(
                    {
                        "scenario": scenario_name,
                        "status": validation_result.status,
                        "records_processed": validation_result.records_processed,
                        "errors": len(validation_result.errors),
                        "warnings": len(validation_result.warnings),
                    }
                )

                print(f"✓ {scenario_name}: {validation_result.status}")

            except Exception as e:
                print(f"❌ {scenario_name} failed: {e}")
                all_results.append(
                    {"scenario": scenario_name, "status": "error", "error": str(e)}
                )

        # Generate comprehensive report
        if validation_results:
            print("\n📋 Generating comprehensive report...")
            comprehensive_report = self.validator.generate_comprehensive_report(
                "All Scenarios Validation", validation_results
            )
        else:
            comprehensive_report = None

        # Cleanup if requested
        if cleanup_after:
            print("\n🧹 Cleaning up all test data...")
            cleanup_result = self.data_manager.cleanup_test_data()
            print(
                f"✓ Cleaned up {cleanup_result['cleanup_summary']['successful_cleanups']} scenarios"
            )

        total_duration = time.time() - start_time

        # Summary
        successful = len([r for r in all_results if r.get("status") == "passed"])
        failed = len([r for r in all_results if r.get("status") in ["failed", "error"]])

        print("\n📊 Summary:")
        print(f"   Total scenarios: {len(all_results)}")
        print(f"   Successful: {successful}")
        print(f"   Failed: {failed}")
        print(f"   Total duration: {total_duration:.2f}s")

        return {
            "status": "success",
            "total_scenarios": len(all_results),
            "successful_scenarios": successful,
            "failed_scenarios": failed,
            "scenario_results": all_results,
            "comprehensive_report": (
                comprehensive_report.to_dict() if comprehensive_report else None
            ),
            "total_duration": total_duration,
        }

    def get_test_data_status(self) -> dict[str, any]:
        """Get current test data status."""
        print("\n📊 Retrieving test data status...")

        try:
            status = self.data_manager.get_test_data_status()

            print("Current test data status:")
            print(
                f"   Initialized scenarios: {status.get('initialized_scenarios', [])}"
            )
            print(
                f"   Survey test records: {status.get('survey_test_records', 'unknown')}"
            )
            print(
                f"   Order test records: {status.get('order_test_records', 'unknown')}"
            )

            queue_status = status.get("queue_status", {})
            if queue_status and queue_status != "unknown":
                print("   Queue status:")
                for key, count in queue_status.items():
                    print(f"     {key}: {count}")

            return status

        except Exception as e:
            error_msg = f"Failed to get test data status: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}

    def cleanup_all_test_data(self) -> dict[str, any]:
        """Clean up all test data."""
        print("\n🧹 Cleaning up all test data...")

        try:
            # Reset entire test environment
            reset_result = self.data_manager.reset_test_environment()

            if reset_result["reset_status"] == "success":
                print("✓ All test data cleaned up successfully")
            else:
                print(f"❌ Cleanup failed: {reset_result.get('error')}")

            return reset_result

        except Exception as e:
            error_msg = f"Failed to cleanup test data: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}

    def export_validation_report(
        self, validation_results: list, output_path: str, format: str = "json"
    ) -> bool:
        """Export validation report to file."""
        try:
            if not validation_results:
                print("❌ No validation results to export")
                return False

            # Generate report
            report = self.validator.generate_comprehensive_report(
                "Exported Validation Report", validation_results
            )

            # Export report
            success = self.validator.export_report(report, output_path, format)

            if success:
                print(f"✓ Report exported to {output_path}")
            else:
                print(f"❌ Failed to export report to {output_path}")

            return success

        except Exception as e:
            print(f"❌ Export failed: {e}")
            return False

    def _get_scenario(self, scenario_name: str, record_count: Optional[int]):
        """Get scenario by name with optional record count override."""
        if scenario_name == "survey_processing":
            return self.scenarios.survey_processing_scenario(record_count or 100)
        elif scenario_name == "order_processing":
            return self.scenarios.order_processing_scenario(record_count or 150)
        elif scenario_name == "high_volume_processing":
            return self.scenarios.high_volume_scenario(record_count or 1000)
        elif scenario_name == "error_handling":
            return self.scenarios.error_handling_scenario(record_count or 50)
        else:
            return None

    def _simulate_test_execution(self, scenario) -> list[dict[str, any]]:
        """
        Simulate test execution results.

        In real usage, this would be replaced with actual test execution
        that processes the initialized test data.
        """
        import random

        test_results = []

        for i in range(1, scenario.record_count + 1):
            # Simulate different outcomes based on scenario
            if scenario.name == "error_handling":
                # Error handling scenario should have some failures
                if i % 5 == 0:  # 20% failure rate
                    result = {
                        "record_id": i,
                        "status": "failed",
                        "error": f"Simulated error for record {i}",
                        "processing_time_ms": random.randint(500, 2000),
                    }
                else:
                    result = {
                        "record_id": i,
                        "status": "completed",
                        "result": {"processed": True, "score": random.randint(80, 100)},
                        "processing_time_ms": random.randint(800, 1500),
                    }
            else:
                # Normal scenarios - mostly successful
                if random.random() < 0.05:  # 5% failure rate
                    result = {
                        "record_id": i,
                        "status": "failed",
                        "error": f"Random failure for record {i}",
                        "processing_time_ms": random.randint(1000, 3000),
                    }
                else:
                    result = {
                        "record_id": i,
                        "status": "completed",
                        "result": {"processed": True, "data": f"result_{i}"},
                        "processing_time_ms": random.randint(500, 2000),
                    }

            test_results.append(result)

        return test_results


def main():
    """Main entry point for the test data validation runner."""
    parser = argparse.ArgumentParser(
        description="Test Data Validation Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scenario survey_processing --records 100
  %(prog)s --all-scenarios --cleanup
  %(prog)s --status
  %(prog)s --cleanup-all
        """,
    )

    parser.add_argument(
        "--scenario",
        choices=[
            "survey_processing",
            "order_processing",
            "high_volume_processing",
            "error_handling",
        ],
        help="Run validation for specific scenario",
    )

    parser.add_argument(
        "--records",
        type=int,
        help="Number of records to generate (overrides scenario default)",
    )

    parser.add_argument(
        "--all-scenarios", action="store_true", help="Run validation for all scenarios"
    )

    parser.add_argument(
        "--status", action="store_true", help="Show current test data status"
    )

    parser.add_argument(
        "--cleanup", action="store_true", help="Cleanup test data after validation"
    )

    parser.add_argument(
        "--cleanup-all", action="store_true", help="Cleanup all test data"
    )

    parser.add_argument("--export", help="Export validation report to file")

    parser.add_argument(
        "--format",
        choices=["json", "html"],
        default="json",
        help="Export format (default: json)",
    )

    parser.add_argument(
        "--no-cleanup", action="store_true", help="Skip cleanup after validation"
    )

    args = parser.parse_args()

    # Initialize runner
    try:
        runner = TestDataValidationRunner()
    except Exception as e:
        print(f"❌ Failed to initialize test runner: {e}")
        sys.exit(1)

    # Execute requested action
    try:
        if args.status:
            runner.get_test_data_status()

        elif args.cleanup_all:
            runner.cleanup_all_test_data()

        elif args.all_scenarios:
            cleanup_after = not args.no_cleanup
            result = runner.run_all_scenarios(cleanup_after=cleanup_after)

            if args.export:
                # Export would need validation results from the run
                print("💾 Export functionality available - report generated in memory")

        elif args.scenario:
            cleanup_after = args.cleanup or not args.no_cleanup
            result = runner.run_scenario_validation(
                args.scenario, args.records, cleanup_after=cleanup_after
            )

            if args.export and "validation_result" in result:
                # Create validation result object for export
                # Use the original validation result object for export
                if "validation_result_obj" in result:
                    validation_result = result["validation_result_obj"]
                    runner.export_validation_report(
                        [validation_result], args.export, args.format
                    )

        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
