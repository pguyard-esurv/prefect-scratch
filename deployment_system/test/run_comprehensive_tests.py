#!/usr/bin/env python3
"""
Comprehensive test runner for the deployment system.

Runs all tests with proper categorization, reporting, and coverage analysis.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


class TestRunner:
    """Comprehensive test runner for deployment system."""

    def __init__(self, test_dir: Optional[Path] = None):
        """Initialize test runner."""
        self.test_dir = test_dir or Path(__file__).parent
        self.project_root = self.test_dir.parent.parent
        self.coverage_dir = self.project_root / "htmlcov"

    def run_unit_tests(self, verbose: bool = False) -> int:
        """Run unit tests."""
        print("🧪 Running unit tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-m",
            "unit",
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_integration_tests(self, verbose: bool = False) -> int:
        """Run integration tests."""
        print("🔗 Running integration tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-m",
            "integration",
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_e2e_tests(self, verbose: bool = False) -> int:
        """Run end-to-end tests."""
        print("🎯 Running end-to-end tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-m",
            "e2e",
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_all_tests(self, verbose: bool = False, coverage: bool = False) -> int:
        """Run all tests."""
        print("🚀 Running all tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        if coverage:
            cmd.extend(
                [
                    "--cov=deployment_system",
                    "--cov-report=html",
                    "--cov-report=term-missing",
                    f"--cov-report=html:{self.coverage_dir}",
                ]
            )

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_specific_test(self, test_pattern: str, verbose: bool = False) -> int:
        """Run specific test by pattern."""
        print(f"🎯 Running tests matching: {test_pattern}")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-k",
            test_pattern,
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_fast_tests(self, verbose: bool = False) -> int:
        """Run fast tests (excluding slow tests)."""
        print("⚡ Running fast tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-m",
            "not slow",
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_docker_tests(self, verbose: bool = False) -> int:
        """Run Docker-related tests."""
        print("🐳 Running Docker tests...")

        # Check if Docker is available
        try:
            subprocess.run(
                ["docker", "--version"], check=True, capture_output=True, timeout=5
            )
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            print("❌ Docker not available, skipping Docker tests")
            return 0

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-m",
            "docker",
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_prefect_tests(self, verbose: bool = False) -> int:
        """Run Prefect API tests."""
        print("🌊 Running Prefect API tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-m",
            "prefect",
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_performance_tests(self, verbose: bool = False) -> int:
        """Run performance tests."""
        print("📊 Running performance tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "-k",
            "performance",
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_validation_tests(self, verbose: bool = False) -> int:
        """Run validation system tests."""
        print("✅ Running validation tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir / "test_validation_system.py"),
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_discovery_tests(self, verbose: bool = False) -> int:
        """Run flow discovery tests."""
        print("🔍 Running flow discovery tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir / "test_flow_discovery.py"),
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def run_builder_tests(self, verbose: bool = False) -> int:
        """Run deployment builder tests."""
        print("🏗️ Running deployment builder tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir / "test_deployment_builder.py"),
            "--tb=short",
        ]

        if verbose:
            cmd.append("-v")

        return subprocess.run(cmd, cwd=self.project_root).returncode

    def check_test_coverage(self) -> None:
        """Check test coverage and generate report."""
        print("📈 Generating coverage report...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "--cov=deployment_system",
            "--cov-report=html",
            "--cov-report=term-missing",
            f"--cov-report=html:{self.coverage_dir}",
            "--cov-fail-under=80",  # Require 80% coverage
        ]

        result = subprocess.run(cmd, cwd=self.project_root)

        if result.returncode == 0:
            print(f"✅ Coverage report generated: {self.coverage_dir}/index.html")
        else:
            print("❌ Coverage check failed")

        return result.returncode

    def lint_tests(self) -> int:
        """Lint test files."""
        print("🧹 Linting test files...")

        # Check if ruff is available
        try:
            subprocess.run(["ruff", "--version"], check=True, capture_output=True)

            cmd = ["ruff", "check", str(self.test_dir)]
            result = subprocess.run(cmd, cwd=self.project_root)

            if result.returncode == 0:
                print("✅ Test files pass linting")
            else:
                print("❌ Test files have linting issues")

            return result.returncode

        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Ruff not available, skipping linting")
            return 0

    def format_tests(self) -> int:
        """Format test files."""
        print("🎨 Formatting test files...")

        # Check if black is available
        try:
            subprocess.run(["black", "--version"], check=True, capture_output=True)

            cmd = ["black", str(self.test_dir)]
            result = subprocess.run(cmd, cwd=self.project_root)

            if result.returncode == 0:
                print("✅ Test files formatted")
            else:
                print("❌ Test file formatting failed")

            return result.returncode

        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️ Black not available, skipping formatting")
            return 0

    def validate_test_structure(self) -> bool:
        """Validate test structure and completeness."""
        print("🔍 Validating test structure...")

        required_test_files = [
            "test_flow_discovery.py",
            "test_deployment_builder.py",
            "test_prefect_api_integration.py",
            "test_end_to_end_workflows.py",
            "test_validation_system.py",
            "test_utilities.py",
            "conftest.py",
        ]

        missing_files = []
        for test_file in required_test_files:
            if not (self.test_dir / test_file).exists():
                missing_files.append(test_file)

        if missing_files:
            print(f"❌ Missing test files: {', '.join(missing_files)}")
            return False

        print("✅ All required test files present")
        return True

    def run_test_suite(self, suite_name: str, verbose: bool = False) -> int:
        """Run a specific test suite."""
        suites = {
            "unit": self.run_unit_tests,
            "integration": self.run_integration_tests,
            "e2e": self.run_e2e_tests,
            "fast": self.run_fast_tests,
            "docker": self.run_docker_tests,
            "prefect": self.run_prefect_tests,
            "performance": self.run_performance_tests,
            "validation": self.run_validation_tests,
            "discovery": self.run_discovery_tests,
            "builder": self.run_builder_tests,
        }

        if suite_name not in suites:
            print(f"❌ Unknown test suite: {suite_name}")
            print(f"Available suites: {', '.join(suites.keys())}")
            return 1

        return suites[suite_name](verbose)

    def generate_test_report(self) -> None:
        """Generate comprehensive test report."""
        print("📊 Generating test report...")

        report_file = self.project_root / "test_report.html"

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.test_dir),
            "--html=" + str(report_file),
            "--self-contained-html",
            "--tb=short",
        ]

        result = subprocess.run(cmd, cwd=self.project_root)

        if result.returncode == 0:
            print(f"✅ Test report generated: {report_file}")
        else:
            print("❌ Test report generation failed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for deployment system"
    )

    parser.add_argument(
        "command",
        choices=[
            "all",
            "unit",
            "integration",
            "e2e",
            "fast",
            "docker",
            "prefect",
            "performance",
            "validation",
            "discovery",
            "builder",
            "coverage",
            "lint",
            "format",
            "validate",
            "report",
        ],
        help="Test command to run",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    parser.add_argument(
        "-c",
        "--coverage",
        action="store_true",
        help="Include coverage analysis (for 'all' command)",
    )

    parser.add_argument("-k", "--pattern", help="Run tests matching pattern")

    parser.add_argument("--test-dir", type=Path, help="Test directory path")

    args = parser.parse_args()

    # Initialize test runner
    runner = TestRunner(args.test_dir)

    # Validate test structure first
    if not runner.validate_test_structure():
        print("❌ Test structure validation failed")
        return 1

    # Run the requested command
    exit_code = 0

    if args.command == "all":
        exit_code = runner.run_all_tests(args.verbose, args.coverage)
    elif args.command == "coverage":
        exit_code = runner.check_test_coverage()
    elif args.command == "lint":
        exit_code = runner.lint_tests()
    elif args.command == "format":
        exit_code = runner.format_tests()
    elif args.command == "validate":
        success = runner.validate_test_structure()
        exit_code = 0 if success else 1
    elif args.command == "report":
        runner.generate_test_report()
        exit_code = 0
    elif args.pattern:
        exit_code = runner.run_specific_test(args.pattern, args.verbose)
    else:
        exit_code = runner.run_test_suite(args.command, args.verbose)

    # Print summary
    if exit_code == 0:
        print("✅ Tests completed successfully")
    else:
        print("❌ Tests failed")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
