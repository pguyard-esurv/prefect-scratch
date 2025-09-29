#!/usr/bin/env python3
"""
Comprehensive security test runner for container testing system.

This script runs all security-related tests including unit tests, integration tests,
and compliance verification tests. It provides detailed reporting and can be used
for CI/CD integration and security validation workflows.
"""

import argparse
import json
import subprocess
import sys
import time
import unittest
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def print_banner():
    """Print test runner banner."""
    print("=" * 80)
    print("🧪 Container Security Test Suite")
    print("=" * 80)
    print()


def run_unit_tests(verbose=False):
    """Run security unit tests."""
    print("🔬 Running Security Unit Tests...")
    print("-" * 40)

    # Discover and run security unit tests
    loader = unittest.TestLoader()

    # Load specific test modules
    test_modules = [
        "test_security_validator",
    ]

    suite = unittest.TestSuite()

    for module_name in test_modules:
        try:
            module_tests = loader.loadTestsFromName(module_name)
            suite.addTests(module_tests)
        except Exception as e:
            print(f"❌ Failed to load tests from {module_name}: {e}")

    # Run tests
    runner = unittest.TextTestRunner(
        verbosity=2 if verbose else 1, stream=sys.stdout, buffer=True
    )

    result = runner.run(suite)

    # Print summary
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, "skipped") else 0

    print("\n📊 Unit Test Summary:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {total_tests - failures - errors - skipped}")
    print(f"   Failed: {failures}")
    print(f"   Errors: {errors}")
    print(f"   Skipped: {skipped}")

    success = failures == 0 and errors == 0
    print(f"   Status: {'✅ PASSED' if success else '❌ FAILED'}")
    print()

    return success


def run_integration_tests(verbose=False):
    """Run security integration tests."""
    print("🔗 Running Security Integration Tests...")
    print("-" * 40)

    # Discover and run security integration tests
    loader = unittest.TestLoader()

    # Load integration test modules
    test_modules = [
        "test_security_integration",
    ]

    suite = unittest.TestSuite()

    for module_name in test_modules:
        try:
            module_tests = loader.loadTestsFromName(module_name)
            suite.addTests(module_tests)
        except Exception as e:
            print(f"❌ Failed to load integration tests from {module_name}: {e}")

    # Run tests
    runner = unittest.TextTestRunner(
        verbosity=2 if verbose else 1, stream=sys.stdout, buffer=True
    )

    result = runner.run(suite)

    # Print summary
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, "skipped") else 0

    print("\n📊 Integration Test Summary:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {total_tests - failures - errors - skipped}")
    print(f"   Failed: {failures}")
    print(f"   Errors: {errors}")
    print(f"   Skipped: {skipped}")

    success = failures == 0 and errors == 0
    print(f"   Status: {'✅ PASSED' if success else '❌ FAILED'}")
    print()

    return success


def run_security_validation(verbose=False):
    """Run live security validation."""
    print("🔒 Running Live Security Validation...")
    print("-" * 40)

    try:
        # Run the security validation script
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "run_security_validation.py"),
            "--enable-vuln-scan",
        ]

        if verbose:
            cmd.append("--verbose")

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
        )

        print(result.stdout)

        if result.stderr:
            print("⚠️  Stderr output:")
            print(result.stderr)

        success = result.returncode == 0
        print(
            f"📊 Security Validation Status: {'✅ PASSED' if success else '❌ FAILED'}"
        )
        print()

        return success

    except subprocess.TimeoutExpired:
        print("❌ Security validation timed out")
        return False
    except Exception as e:
        print(f"❌ Security validation failed: {e}")
        return False


def run_compliance_checks(verbose=False):
    """Run security compliance checks."""
    print("📋 Running Security Compliance Checks...")
    print("-" * 40)

    try:
        from core.security_validator import SecurityValidator

        # Create validator with comprehensive settings
        validator = SecurityValidator(
            enable_vulnerability_scanning=True,
            enable_network_validation=True,
        )

        # Run comprehensive validation
        report = validator.comprehensive_security_validation()

        # Print compliance results
        print("🔍 Compliance Check Results:")

        for area, status in report.compliance_status.items():
            if isinstance(status, bool):
                emoji = "✅" if status else "❌"
                status_text = "COMPLIANT" if status else "NON-COMPLIANT"
                print(f"   {emoji} {area.replace('_', ' ').title()}: {status_text}")
            else:
                print(f"   ❓ {area.replace('_', ' ').title()}: {status}")

        # Overall compliance status
        compliance_score = sum(
            1
            for status in report.compliance_status.values()
            if isinstance(status, bool) and status
        )
        total_checks = len(
            [
                status
                for status in report.compliance_status.values()
                if isinstance(status, bool)
            ]
        )

        if total_checks > 0:
            compliance_percentage = (compliance_score / total_checks) * 100
            print(
                f"\n📊 Overall Compliance: {compliance_percentage:.1f}% ({compliance_score}/{total_checks})"
            )

        success = report.overall_status.value in ["pass", "warning"]
        print(f"   Status: {'✅ PASSED' if success else '❌ FAILED'}")
        print()

        return success

    except Exception as e:
        print(f"❌ Compliance checks failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        return False


def run_performance_tests(verbose=False):
    """Run security validation performance tests."""
    print("⚡ Running Security Performance Tests...")
    print("-" * 40)

    try:
        from core.security_validator import SecurityValidator

        # Test performance with different configurations
        test_configs = [
            {"vuln_scan": False, "network": False, "name": "Minimal"},
            {"vuln_scan": False, "network": True, "name": "Network Only"},
            {"vuln_scan": True, "network": False, "name": "Vulnerability Only"},
            {"vuln_scan": True, "network": True, "name": "Comprehensive"},
        ]

        results = []

        for config in test_configs:
            validator = SecurityValidator(
                enable_vulnerability_scanning=config["vuln_scan"],
                enable_network_validation=config["network"],
            )

            start_time = time.time()
            report = validator.comprehensive_security_validation()
            end_time = time.time()

            duration = end_time - start_time
            results.append(
                {
                    "name": config["name"],
                    "duration": duration,
                    "checks": report.summary["total_checks"],
                    "status": report.overall_status.value,
                }
            )

            print(
                f"   {config['name']}: {duration:.2f}s ({report.summary['total_checks']} checks)"
            )

        # Performance analysis
        print("\n📊 Performance Analysis:")
        fastest = min(results, key=lambda x: x["duration"])
        slowest = max(results, key=lambda x: x["duration"])

        print(f"   Fastest: {fastest['name']} ({fastest['duration']:.2f}s)")
        print(f"   Slowest: {slowest['name']} ({slowest['duration']:.2f}s)")

        # Check if any test took too long
        max_acceptable_time = 30.0  # 30 seconds
        slow_tests = [r for r in results if r["duration"] > max_acceptable_time]

        if slow_tests:
            print(f"   ⚠️  Slow tests detected (>{max_acceptable_time}s):")
            for test in slow_tests:
                print(f"      {test['name']}: {test['duration']:.2f}s")

        success = len(slow_tests) == 0
        print(f"   Status: {'✅ PASSED' if success else '⚠️  WARNINGS'}")
        print()

        return success

    except Exception as e:
        print(f"❌ Performance tests failed: {e}")
        if verbose:
            import traceback

            traceback.print_exc()
        return False


def generate_test_report(results, output_file=None):
    """Generate comprehensive test report."""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "test_results": results,
        "overall_status": "PASSED" if all(results.values()) else "FAILED",
        "summary": {
            "total_test_suites": len(results),
            "passed_suites": sum(1 for passed in results.values() if passed),
            "failed_suites": sum(1 for passed in results.values() if not passed),
        },
    }

    if output_file:
        try:
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)
            print(f"💾 Test report saved to: {output_file}")
        except Exception as e:
            print(f"❌ Failed to save test report: {e}")

    return report


def main():
    """Main entry point for security test runner."""
    parser = argparse.ArgumentParser(
        description="Container Security Test Suite Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all security tests
  python run_security_tests.py

  # Run only unit tests
  python run_security_tests.py --unit-tests-only

  # Run with verbose output
  python run_security_tests.py --verbose

  # Save test report
  python run_security_tests.py --output-file security_test_report.json

  # Run specific test suites
  python run_security_tests.py --unit-tests --integration-tests
        """,
    )

    # Test selection options
    parser.add_argument("--unit-tests", action="store_true", help="Run unit tests")
    parser.add_argument(
        "--integration-tests", action="store_true", help="Run integration tests"
    )
    parser.add_argument(
        "--security-validation",
        action="store_true",
        help="Run live security validation",
    )
    parser.add_argument(
        "--compliance-checks", action="store_true", help="Run compliance checks"
    )
    parser.add_argument(
        "--performance-tests", action="store_true", help="Run performance tests"
    )

    # Convenience options
    parser.add_argument(
        "--unit-tests-only", action="store_true", help="Run only unit tests"
    )
    parser.add_argument(
        "--integration-tests-only",
        action="store_true",
        help="Run only integration tests",
    )

    # Output options
    parser.add_argument("--output-file", help="Save test report to JSON file")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    args = parser.parse_args()

    # Determine which tests to run
    if args.unit_tests_only:
        run_tests = {"unit_tests": True}
    elif args.integration_tests_only:
        run_tests = {"integration_tests": True}
    elif any(
        [
            args.unit_tests,
            args.integration_tests,
            args.security_validation,
            args.compliance_checks,
            args.performance_tests,
        ]
    ):
        run_tests = {
            "unit_tests": args.unit_tests,
            "integration_tests": args.integration_tests,
            "security_validation": args.security_validation,
            "compliance_checks": args.compliance_checks,
            "performance_tests": args.performance_tests,
        }
    else:
        # Run all tests by default
        run_tests = {
            "unit_tests": True,
            "integration_tests": True,
            "security_validation": True,
            "compliance_checks": True,
            "performance_tests": True,
        }

    print_banner()

    start_time = time.time()
    results = {}

    try:
        # Run selected test suites
        if run_tests.get("unit_tests"):
            results["unit_tests"] = run_unit_tests(args.verbose)

        if run_tests.get("integration_tests"):
            results["integration_tests"] = run_integration_tests(args.verbose)

        if run_tests.get("security_validation"):
            results["security_validation"] = run_security_validation(args.verbose)

        if run_tests.get("compliance_checks"):
            results["compliance_checks"] = run_compliance_checks(args.verbose)

        if run_tests.get("performance_tests"):
            results["performance_tests"] = run_performance_tests(args.verbose)

        end_time = time.time()
        total_duration = end_time - start_time

        # Print overall summary
        print("=" * 80)
        print("📊 OVERALL TEST SUMMARY")
        print("=" * 80)

        passed_suites = sum(1 for passed in results.values() if passed)
        total_suites = len(results)

        for suite_name, passed in results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"   {suite_name.replace('_', ' ').title()}: {status}")

        print(f"\n   Total Duration: {total_duration:.2f}s")
        print(f"   Test Suites: {passed_suites}/{total_suites} passed")

        overall_success = all(results.values())
        overall_status = (
            "✅ ALL TESTS PASSED" if overall_success else "❌ SOME TESTS FAILED"
        )
        print(f"   Overall Status: {overall_status}")

        # Generate test report
        if args.output_file or not overall_success:
            generate_test_report(results, args.output_file)

        # Return appropriate exit code
        return 0 if overall_success else 1

    except KeyboardInterrupt:
        print("\n❌ Test execution interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
