#!/usr/bin/env python3
"""
Fast Test Runner for Container Testing System

Provides fast feedback mechanisms for local test execution with intelligent
test selection, parallel execution, and real-time results reporting.

Requirements: 4.7, 5.4
"""

import asyncio
import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class TestResult:
    """Represents the result of a test execution"""

    test_name: str
    status: str  # "passed", "failed", "skipped", "error"
    duration: float
    output: str
    error_message: Optional[str] = None
    file_path: str = ""
    line_number: Optional[int] = None


@dataclass
class TestSuite:
    """Represents a collection of tests to run"""

    name: str
    test_files: list[str]
    markers: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    estimated_duration: float = 0.0


@dataclass
class TestExecutionConfig:
    """Configuration for test execution"""

    parallel_workers: int = 4
    timeout_seconds: int = 300
    fail_fast: bool = False
    verbose: bool = True
    coverage: bool = False
    markers: list[str] = field(default_factory=list)
    exclude_markers: list[str] = field(default_factory=list)
    test_pattern: Optional[str] = None


class TestChangeDetector:
    """Detects which tests need to be run based on code changes"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.logger = logging.getLogger(__name__)

        # Test dependency mapping
        self.test_dependencies = {
            "core/test/test_config.py": ["core/config.py"],
            "core/test/test_database.py": [
                "core/database.py",
                "core/database_config_validator.py",
            ],
            "core/test/test_distributed.py": ["core/distributed.py"],
            "core/test/test_health_monitor.py": ["core/health_monitor.py"],
            "core/test/test_monitoring.py": ["core/monitoring.py"],
            "core/test/test_service_orchestrator.py": ["core/service_orchestrator.py"],
            "core/test/test_tasks.py": ["core/tasks.py"],
            "flows/rpa1/test/test_workflow.py": ["flows/rpa1/workflow.py"],
            "flows/rpa2/test/test_workflow.py": ["flows/rpa2/workflow.py"],
            "flows/rpa3/test/test_workflow.py": ["flows/rpa3/workflow.py"],
        }

    def get_changed_files(self, since: Optional[datetime] = None) -> set[str]:
        """Get list of files changed since a specific time"""
        if since is None:
            since = datetime.now() - timedelta(minutes=30)

        changed_files = set()

        try:
            # Use git to find changed files
            result = subprocess.run(
                ["git", "diff", "--name-only", f"--since={since.isoformat()}", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode == 0:
                changed_files.update(result.stdout.strip().split("\n"))

            # Also check for unstaged changes
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if result.returncode == 0:
                changed_files.update(result.stdout.strip().split("\n"))

            # Remove empty strings
            changed_files.discard("")

        except Exception as e:
            self.logger.warning(f"Could not detect git changes: {e}")
            # Fall back to file modification time
            changed_files = self._get_recently_modified_files(since)

        return changed_files

    def _get_recently_modified_files(self, since: datetime) -> set[str]:
        """Get files modified since a specific time using filesystem timestamps"""
        changed_files = set()

        for file_path in self.project_root.rglob("*.py"):
            try:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if mtime > since:
                    changed_files.add(str(file_path.relative_to(self.project_root)))
            except Exception:
                continue

        return changed_files

    def get_affected_tests(self, changed_files: set[str]) -> set[str]:
        """Determine which tests need to be run based on changed files"""
        affected_tests = set()

        for changed_file in changed_files:
            # Direct test file changes
            if changed_file.endswith("test_*.py") or "/test_" in changed_file:
                affected_tests.add(changed_file)

            # Check dependency mapping
            for test_file, dependencies in self.test_dependencies.items():
                if changed_file in dependencies:
                    affected_tests.add(test_file)

            # Pattern-based detection
            if changed_file.startswith("core/"):
                # Core changes affect core tests
                affected_tests.update(self._find_tests_in_directory("core/test/"))

            elif changed_file.startswith("flows/"):
                # Flow changes affect corresponding flow tests
                flow_name = changed_file.split("/")[1]
                affected_tests.update(
                    self._find_tests_in_directory(f"flows/{flow_name}/test/")
                )

        return affected_tests

    def _find_tests_in_directory(self, directory: str) -> set[str]:
        """Find all test files in a directory"""
        test_files = set()
        test_dir = self.project_root / directory

        if test_dir.exists():
            for test_file in test_dir.rglob("test_*.py"):
                test_files.add(str(test_file.relative_to(self.project_root)))

        return test_files


class FastTestRunner:
    """Executes tests with fast feedback and intelligent selection"""

    def __init__(self, config: TestExecutionConfig):
        self.config = config
        self.change_detector = TestChangeDetector()
        self.logger = logging.getLogger(__name__)

        # Test suites for different categories
        self.test_suites = {
            "unit": TestSuite(
                name="Unit Tests",
                test_files=[
                    "core/test/test_config.py",
                    "core/test/test_database_config_validator.py",
                    "core/test/test_health_monitor.py",
                    "core/test/test_monitoring.py",
                ],
                markers=["unit"],
                estimated_duration=30.0,
            ),
            "integration": TestSuite(
                name="Integration Tests",
                test_files=[
                    "core/test/test_database_integration.py",
                    "core/test/test_service_orchestrator_integration.py",
                    "core/test/test_health_monitoring_integration.py",
                ],
                markers=["integration"],
                dependencies=["unit"],
                estimated_duration=120.0,
            ),
            "flow": TestSuite(
                name="Flow Tests",
                test_files=[
                    "flows/rpa1/test/test_workflow.py",
                    "flows/rpa2/test/test_workflow.py",
                    "flows/rpa3/test/test_workflow.py",
                ],
                markers=["flow"],
                dependencies=["unit"],
                estimated_duration=90.0,
            ),
            "container": TestSuite(
                name="Container Tests",
                test_files=[
                    "core/test/test_container_config.py",
                    "core/test/test_container_framework_simple.py",
                    "core/test/test_automated_container_framework.py",
                ],
                markers=["container"],
                dependencies=["unit", "integration"],
                estimated_duration=180.0,
            ),
        }

    async def run_smart_tests(self, changed_since: Optional[datetime] = None) -> dict:
        """Run tests intelligently based on recent changes"""
        start_time = time.time()

        # Detect changes and affected tests
        changed_files = self.change_detector.get_changed_files(changed_since)
        affected_tests = self.change_detector.get_affected_tests(changed_files)

        self.logger.info(f"Found {len(changed_files)} changed files")
        self.logger.info(f"Identified {len(affected_tests)} affected tests")

        if not affected_tests:
            self.logger.info("No tests affected by recent changes")
            return {
                "status": "no_tests",
                "message": "No tests affected by recent changes",
                "duration": time.time() - start_time,
            }

        # Run affected tests
        results = await self._run_test_files(list(affected_tests))

        return {
            "status": "completed",
            "changed_files": list(changed_files),
            "affected_tests": list(affected_tests),
            "results": results,
            "duration": time.time() - start_time,
        }

    async def run_test_suite(self, suite_name: str) -> dict:
        """Run a specific test suite"""
        if suite_name not in self.test_suites:
            return {"status": "error", "message": f"Unknown test suite: {suite_name}"}

        suite = self.test_suites[suite_name]

        # Check dependencies
        for dep in suite.dependencies:
            if dep in self.test_suites:
                dep_result = await self.run_test_suite(dep)
                if dep_result.get("status") != "passed":
                    return {
                        "status": "dependency_failed",
                        "message": f"Dependency {dep} failed",
                        "dependency_result": dep_result,
                    }

        # Run the suite
        results = await self._run_test_files(suite.test_files, suite.markers)

        return {
            "status": (
                "passed" if all(r.status == "passed" for r in results) else "failed"
            ),
            "suite": suite.name,
            "results": [self._test_result_to_dict(r) for r in results],
            "summary": self._generate_summary(results),
        }

    async def run_all_tests(self) -> dict:
        """Run all test suites in dependency order"""
        start_time = time.time()
        all_results = {}

        # Determine execution order based on dependencies
        execution_order = self._calculate_execution_order()

        for suite_name in execution_order:
            self.logger.info(f"Running test suite: {suite_name}")
            suite_result = await self.run_test_suite(suite_name)
            all_results[suite_name] = suite_result

            # Stop on failure if fail_fast is enabled
            if self.config.fail_fast and suite_result.get("status") != "passed":
                break

        return {
            "status": "completed",
            "suites": all_results,
            "duration": time.time() - start_time,
            "summary": self._generate_overall_summary(all_results),
        }

    async def _run_test_files(
        self, test_files: list[str], markers: list[str] = None
    ) -> list[TestResult]:
        """Run specific test files with parallel execution"""
        if not test_files:
            return []

        # Filter existing files
        existing_files = [f for f in test_files if Path(f).exists()]
        if not existing_files:
            self.logger.warning("No test files found")
            return []

        # Build pytest arguments
        pytest_args = ["-v", "--tb=short"]

        if self.config.coverage:
            pytest_args.extend(["--cov=core", "--cov-report=term-missing"])

        if markers:
            for marker in markers:
                pytest_args.extend(["-m", marker])

        if self.config.markers:
            for marker in self.config.markers:
                pytest_args.extend(["-m", marker])

        if self.config.exclude_markers:
            for marker in self.config.exclude_markers:
                pytest_args.extend(["-m", f"not {marker}"])

        if self.config.test_pattern:
            pytest_args.extend(["-k", self.config.test_pattern])

        # Add parallel execution if multiple workers
        if self.config.parallel_workers > 1 and len(existing_files) > 1:
            pytest_args.extend(["-n", str(self.config.parallel_workers)])

        # Add test files
        pytest_args.extend(existing_files)

        # Run tests
        start_time = time.time()

        try:
            # Capture pytest output
            result = subprocess.run(
                [sys.executable, "-m", "pytest"] + pytest_args,
                capture_output=True,
                text=True,
                timeout=self.config.timeout_seconds,
            )

            duration = time.time() - start_time

            # Parse results
            test_results = self._parse_pytest_output(
                result.stdout, result.stderr, duration
            )

            return test_results

        except subprocess.TimeoutExpired:
            return [
                TestResult(
                    test_name="timeout",
                    status="error",
                    duration=self.config.timeout_seconds,
                    output="",
                    error_message=f"Tests timed out after {self.config.timeout_seconds} seconds",
                )
            ]

        except Exception as e:
            return [
                TestResult(
                    test_name="execution_error",
                    status="error",
                    duration=time.time() - start_time,
                    output="",
                    error_message=str(e),
                )
            ]

    def _parse_pytest_output(
        self, stdout: str, stderr: str, duration: float
    ) -> list[TestResult]:
        """Parse pytest output to extract test results"""
        results = []

        # Simple parsing - in a real implementation, you'd use pytest's JSON report
        lines = stdout.split("\n")

        for line in lines:
            if "::" in line and any(
                status in line for status in ["PASSED", "FAILED", "SKIPPED", "ERROR"]
            ):
                parts = line.split()
                if len(parts) >= 2:
                    test_name = parts[0]
                    status_part = parts[1]

                    if "PASSED" in status_part:
                        status = "passed"
                    elif "FAILED" in status_part:
                        status = "failed"
                    elif "SKIPPED" in status_part:
                        status = "skipped"
                    else:
                        status = "error"

                    results.append(
                        TestResult(
                            test_name=test_name,
                            status=status,
                            duration=duration
                            / max(len(results) + 1, 1),  # Rough estimate
                            output=line,
                            error_message=(
                                stderr if status in ["failed", "error"] else None
                            ),
                        )
                    )

        # If no individual results found, create a summary result
        if not results:
            if "failed" in stdout.lower() or "error" in stderr.lower():
                status = "failed"
            elif "passed" in stdout.lower():
                status = "passed"
            else:
                status = "unknown"

            results.append(
                TestResult(
                    test_name="test_execution",
                    status=status,
                    duration=duration,
                    output=stdout,
                    error_message=stderr if stderr else None,
                )
            )

        return results

    def _calculate_execution_order(self) -> list[str]:
        """Calculate the order to execute test suites based on dependencies"""
        ordered = []
        remaining = set(self.test_suites.keys())

        while remaining:
            # Find suites with no unmet dependencies
            ready = []
            for suite_name in remaining:
                suite = self.test_suites[suite_name]
                if all(dep in ordered for dep in suite.dependencies):
                    ready.append(suite_name)

            if not ready:
                # Circular dependency or missing dependency
                ordered.extend(remaining)
                break

            # Add ready suites (sorted by estimated duration for optimization)
            ready.sort(key=lambda x: self.test_suites[x].estimated_duration)
            ordered.extend(ready)
            remaining -= set(ready)

        return ordered

    def _test_result_to_dict(self, result: TestResult) -> dict:
        """Convert TestResult to dictionary"""
        return {
            "test_name": result.test_name,
            "status": result.status,
            "duration": result.duration,
            "output": result.output,
            "error_message": result.error_message,
            "file_path": result.file_path,
            "line_number": result.line_number,
        }

    def _generate_summary(self, results: list[TestResult]) -> dict:
        """Generate summary statistics for test results"""
        total = len(results)
        passed = sum(1 for r in results if r.status == "passed")
        failed = sum(1 for r in results if r.status == "failed")
        skipped = sum(1 for r in results if r.status == "skipped")
        errors = sum(1 for r in results if r.status == "error")

        total_duration = sum(r.duration for r in results)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "success_rate": (passed / total * 100) if total > 0 else 0,
            "total_duration": total_duration,
            "average_duration": total_duration / total if total > 0 else 0,
        }

    def _generate_overall_summary(self, suite_results: dict) -> dict:
        """Generate overall summary across all test suites"""
        total_suites = len(suite_results)
        passed_suites = sum(
            1 for r in suite_results.values() if r.get("status") == "passed"
        )

        all_test_counts = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
        }

        total_duration = 0

        for suite_result in suite_results.values():
            if "summary" in suite_result:
                summary = suite_result["summary"]
                for key in all_test_counts:
                    all_test_counts[key] += summary.get(key, 0)
                total_duration += summary.get("total_duration", 0)

        return {
            "suites": {
                "total": total_suites,
                "passed": passed_suites,
                "failed": total_suites - passed_suites,
            },
            "tests": all_test_counts,
            "total_duration": total_duration,
            "success_rate": (
                (all_test_counts["passed"] / all_test_counts["total"] * 100)
                if all_test_counts["total"] > 0
                else 0
            ),
        }


class TestResultReporter:
    """Generates reports and notifications for test results"""

    def __init__(self, output_dir: str = "./test_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def generate_html_report(self, results: dict, filename: str = None) -> str:
        """Generate an HTML report for test results"""
        if filename is None:
            filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        report_path = self.output_dir / filename

        html_content = self._build_html_report(results)

        with open(report_path, "w") as f:
            f.write(html_content)

        self.logger.info(f"HTML report generated: {report_path}")
        return str(report_path)

    def generate_json_report(self, results: dict, filename: str = None) -> str:
        """Generate a JSON report for test results"""
        if filename is None:
            filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report_path = self.output_dir / filename

        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        self.logger.info(f"JSON report generated: {report_path}")
        return str(report_path)

    def _build_html_report(self, results: dict) -> str:
        """Build HTML content for test report"""
        # Simple HTML template - in a real implementation, you'd use a proper template engine
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Results Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                .skipped {{ color: orange; }}
                .error {{ color: darkred; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Test Results Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                <p>Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p>Status: {results.get("status", "Unknown")}</p>
                <p>Duration: {results.get("duration", 0):.2f} seconds</p>
            </div>

            {self._build_results_table(results)}
        </body>
        </html>
        """
        return html

    def _build_results_table(self, results: dict) -> str:
        """Build HTML table for test results"""
        # This is a simplified implementation
        return (
            "<p>Detailed results would be displayed here in a full implementation.</p>"
        )


async def main():
    """Main CLI interface for the fast test runner"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Fast Test Runner for Container Testing System"
    )

    parser.add_argument(
        "command",
        choices=["smart", "suite", "all", "watch"],
        help="Test execution mode",
    )
    parser.add_argument("--suite", help="Test suite name for suite command")
    parser.add_argument(
        "--since",
        type=int,
        default=30,
        help="Minutes to look back for changes (smart mode)",
    )
    parser.add_argument(
        "--parallel", type=int, default=4, help="Number of parallel workers"
    )
    parser.add_argument(
        "--timeout", type=int, default=300, help="Test timeout in seconds"
    )
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop on first failure"
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Generate coverage report"
    )
    parser.add_argument("--markers", nargs="*", help="Test markers to include")
    parser.add_argument("--exclude-markers", nargs="*", help="Test markers to exclude")
    parser.add_argument("--pattern", help="Test name pattern")
    parser.add_argument(
        "--report",
        choices=["json", "html", "both"],
        default="json",
        help="Report format",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create configuration
    config = TestExecutionConfig(
        parallel_workers=args.parallel,
        timeout_seconds=args.timeout,
        fail_fast=args.fail_fast,
        coverage=args.coverage,
        markers=args.markers or [],
        exclude_markers=args.exclude_markers or [],
        test_pattern=args.pattern,
    )

    # Create runner and reporter
    runner = FastTestRunner(config)
    reporter = TestResultReporter()

    try:
        if args.command == "smart":
            since = datetime.now() - timedelta(minutes=args.since)
            results = await runner.run_smart_tests(since)

        elif args.command == "suite":
            if not args.suite:
                print("Error: --suite required for suite command")
                return 1
            results = await runner.run_test_suite(args.suite)

        elif args.command == "all":
            results = await runner.run_all_tests()

        elif args.command == "watch":
            print("Watch mode not implemented yet")
            return 1

        # Generate reports
        if args.report in ["json", "both"]:
            json_path = reporter.generate_json_report(results)
            print(f"JSON report: {json_path}")

        if args.report in ["html", "both"]:
            html_path = reporter.generate_html_report(results)
            print(f"HTML report: {html_path}")

        # Print summary
        print(f"\nTest execution completed: {results.get('status')}")
        if "summary" in results:
            summary = results["summary"]
            print(
                f"Tests: {summary.get('total', 0)} total, "
                f"{summary.get('passed', 0)} passed, "
                f"{summary.get('failed', 0)} failed"
            )
            print(f"Duration: {results.get('duration', 0):.2f} seconds")

        # Exit with appropriate code
        if results.get("status") in ["passed", "completed", "no_tests"]:
            return 0
        else:
            return 1

    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
