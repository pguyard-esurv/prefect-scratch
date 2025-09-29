#!/usr/bin/env python3
"""
Operational Management Test Runner

This script runs comprehensive tests for the operational management system,
including unit tests, integration tests, and validation of deployment automation.
"""

import argparse
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class OperationalTestRunner:
    """Test runner for operational management components"""

    def __init__(self):
        """Initialize the test runner"""
        self.logger = self._setup_logging()
        self.test_results: dict[str, Any] = {}

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        return logging.getLogger(__name__)

    def run_unit_tests(self) -> bool:
        """Run unit tests for operational manager"""
        self.logger.info("Running operational manager unit tests...")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "core/test/test_operational_manager.py",
                    "-v",
                    "--tb=short",
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            self.test_results["unit_tests"] = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            if result.returncode == 0:
                self.logger.info("Unit tests passed successfully")
                return True
            else:
                self.logger.error(f"Unit tests failed: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to run unit tests: {str(e)}")
            return False

    def run_integration_tests(self) -> bool:
        """Run integration tests for deployment automation"""
        self.logger.info("Running deployment automation integration tests...")

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "core/test/test_deployment_automation_integration.py",
                    "-v",
                    "--tb=short",
                ],
                capture_output=True,
                text=True,
                cwd=".",
            )

            self.test_results["integration_tests"] = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            if result.returncode == 0:
                self.logger.info("Integration tests passed successfully")
                return True
            else:
                self.logger.error(f"Integration tests failed: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to run integration tests: {str(e)}")
            return False

    def validate_deployment_scripts(self) -> bool:
        """Validate deployment automation scripts"""
        self.logger.info("Validating deployment automation scripts...")

        try:
            # Test script help functionality
            result = subprocess.run(
                [sys.executable, "scripts/deployment_automation.py", "--help"],
                capture_output=True,
                text=True,
                cwd=".",
            )

            if result.returncode != 0:
                self.logger.error("Deployment automation script help failed")
                return False

            # Validate configuration files exist
            config_files = [
                "config/deployment-config.json",
                "config/scaling-policies.json",
                "config/deployment-manifest.json",
            ]

            for config_file in config_files:
                if not Path(config_file).exists():
                    self.logger.error(f"Configuration file missing: {config_file}")
                    return False

            self.logger.info("Deployment scripts validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Failed to validate deployment scripts: {str(e)}")
            return False

    def validate_operational_runbooks(self) -> bool:
        """Validate operational runbooks and documentation"""
        self.logger.info("Validating operational runbooks...")

        try:
            runbook_file = Path("docs/OPERATIONAL_RUNBOOKS.md")

            if not runbook_file.exists():
                self.logger.error("Operational runbooks file missing")
                return False

            # Check runbook content
            content = runbook_file.read_text()

            required_sections = [
                "Deployment Operations",
                "Scaling Operations",
                "Incident Response",
                "Monitoring and Alerting",
                "Troubleshooting Guide",
                "Maintenance Procedures",
            ]

            for section in required_sections:
                if section not in content:
                    self.logger.error(
                        f"Required section missing from runbooks: {section}"
                    )
                    return False

            self.logger.info("Operational runbooks validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Failed to validate operational runbooks: {str(e)}")
            return False

    def run_configuration_validation(self) -> bool:
        """Validate configuration files"""
        self.logger.info("Validating configuration files...")

        try:
            import json

            config_files = {
                "config/deployment-config.json": self._validate_deployment_config,
                "config/scaling-policies.json": self._validate_scaling_config,
                "config/deployment-manifest.json": self._validate_manifest_config,
            }

            for config_file, validator in config_files.items():
                if not Path(config_file).exists():
                    self.logger.error(f"Configuration file missing: {config_file}")
                    return False

                try:
                    with open(config_file) as f:
                        config_data = json.load(f)

                    if not validator(config_data):
                        self.logger.error(
                            f"Configuration validation failed: {config_file}"
                        )
                        return False

                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON in {config_file}: {str(e)}")
                    return False

            self.logger.info("Configuration validation passed")
            return True

        except Exception as e:
            self.logger.error(f"Failed to validate configurations: {str(e)}")
            return False

    def _validate_deployment_config(self, config: dict) -> bool:
        """Validate deployment configuration structure"""
        required_fields = ["replicas", "rolling_update_config", "environment_variables"]

        for service_name, service_config in config.items():
            for field in required_fields:
                if field not in service_config:
                    self.logger.error(
                        f"Missing field '{field}' in service '{service_name}'"
                    )
                    return False

        return True

    def _validate_scaling_config(self, config: dict) -> bool:
        """Validate scaling configuration structure"""
        required_fields = ["min_replicas", "max_replicas", "target_cpu_utilization"]

        for service_name, scaling_config in config.items():
            for field in required_fields:
                if field not in scaling_config:
                    self.logger.error(
                        f"Missing field '{field}' in scaling config for '{service_name}'"
                    )
                    return False

            # Validate logical constraints
            if scaling_config["min_replicas"] >= scaling_config["max_replicas"]:
                self.logger.error(f"Invalid replica limits for '{service_name}'")
                return False

        return True

    def _validate_manifest_config(self, config: dict) -> bool:
        """Validate deployment manifest structure"""
        required_fields = ["deployment_order", "services"]

        for field in required_fields:
            if field not in config:
                self.logger.error(f"Missing field '{field}' in deployment manifest")
                return False

        # Validate services in deployment order exist
        for service_name in config["deployment_order"]:
            if service_name not in config["services"]:
                self.logger.error(
                    f"Service '{service_name}' in deployment_order not found in services"
                )
                return False

        return True

    def run_all_tests(self) -> bool:
        """Run all operational management tests"""
        self.logger.info("Starting comprehensive operational management tests...")

        test_functions = [
            ("Configuration Validation", self.run_configuration_validation),
            ("Unit Tests", self.run_unit_tests),
            ("Integration Tests", self.run_integration_tests),
            ("Script Validation", self.validate_deployment_scripts),
            ("Documentation Validation", self.validate_operational_runbooks),
        ]

        results = {}
        overall_success = True

        for test_name, test_function in test_functions:
            self.logger.info(f"Running {test_name}...")
            start_time = time.time()

            try:
                success = test_function()
                duration = time.time() - start_time

                results[test_name] = {"success": success, "duration": duration}

                if success:
                    self.logger.info(
                        f"{test_name} completed successfully in {duration:.2f}s"
                    )
                else:
                    self.logger.error(f"{test_name} failed after {duration:.2f}s")
                    overall_success = False

            except Exception as e:
                duration = time.time() - start_time
                self.logger.error(
                    f"{test_name} crashed after {duration:.2f}s: {str(e)}"
                )
                results[test_name] = {
                    "success": False,
                    "duration": duration,
                    "error": str(e),
                }
                overall_success = False

        # Print summary
        self.logger.info("=" * 60)
        self.logger.info("OPERATIONAL MANAGEMENT TEST SUMMARY")
        self.logger.info("=" * 60)

        for test_name, result in results.items():
            status = "PASS" if result["success"] else "FAIL"
            duration = result["duration"]
            self.logger.info(f"{test_name:.<40} {status} ({duration:.2f}s)")

        self.logger.info("=" * 60)

        if overall_success:
            self.logger.info("All operational management tests passed successfully!")
        else:
            self.logger.error("Some operational management tests failed!")

        return overall_success

    def generate_test_report(self, output_file: str = "operational_test_report.json"):
        """Generate detailed test report"""
        try:
            import json

            report = {
                "timestamp": time.time(),
                "test_results": self.test_results,
                "summary": {
                    "total_tests": len(self.test_results),
                    "passed_tests": sum(
                        1
                        for r in self.test_results.values()
                        if r.get("returncode") == 0
                    ),
                    "failed_tests": sum(
                        1
                        for r in self.test_results.values()
                        if r.get("returncode") != 0
                    ),
                },
            }

            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)

            self.logger.info(f"Test report generated: {output_file}")

        except Exception as e:
            self.logger.error(f"Failed to generate test report: {str(e)}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Operational Management Test Runner")
    parser.add_argument(
        "--test-type",
        choices=["unit", "integration", "validation", "all"],
        default="all",
        help="Type of tests to run",
    )
    parser.add_argument("--report", help="Generate test report file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    runner = OperationalTestRunner()

    success = False

    if args.test_type == "unit":
        success = runner.run_unit_tests()
    elif args.test_type == "integration":
        success = runner.run_integration_tests()
    elif args.test_type == "validation":
        success = (
            runner.run_configuration_validation()
            and runner.validate_deployment_scripts()
            and runner.validate_operational_runbooks()
        )
    elif args.test_type == "all":
        success = runner.run_all_tests()

    if args.report:
        runner.generate_test_report(args.report)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
