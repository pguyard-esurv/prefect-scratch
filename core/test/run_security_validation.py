#!/usr/bin/env python3
"""
Security validation runner for container testing system.

This script provides a command-line interface for running security validation
and compliance checks on container environments. It can be used for manual
testing, CI/CD integration, and operational security monitoring.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.container_config import ContainerConfigManager
from core.security_validator import SecurityLevel, SecurityValidator


def print_banner():
    """Print security validation banner."""
    print("=" * 80)
    print("🔒 Container Security Validation System")
    print("=" * 80)
    print()


def print_security_result(result, verbose=False):
    """Print security validation result in a formatted way."""
    # Status emoji mapping
    status_emoji = {
        SecurityLevel.PASS: "✅",
        SecurityLevel.WARNING: "⚠️",
        SecurityLevel.FAIL: "❌",
    }

    emoji = status_emoji.get(result.level, "❓")
    print(f"{emoji} {result.check_name.upper()}: {result.level.value.upper()}")
    print(f"   Message: {result.message}")
    print(f"   Duration: {result.check_duration:.2f}s")

    if result.recommendations:
        print("   Recommendations:")
        for rec in result.recommendations:
            print(f"     • {rec}")

    if verbose and result.details:
        print("   Details:")
        for key, value in result.details.items():
            if isinstance(value, (dict, list)) and len(str(value)) > 100:
                print(f"     {key}: [Complex data - {len(value)} items]")
            else:
                print(f"     {key}: {value}")

    print()


def print_vulnerability_report(report, verbose=False):
    """Print vulnerability scan report."""
    if report.scan_type == "disabled":
        print("🔍 VULNERABILITY SCANNING: DISABLED")
        return

    print("🔍 VULNERABILITY SCAN RESULTS")
    print(f"   Scan Type: {report.scan_type}")
    print(f"   Total Vulnerabilities: {report.total_count}")
    print(f"   Critical: {report.critical_count}")
    print(f"   High: {report.high_count}")
    print(f"   Medium: {report.medium_count}")
    print(f"   Low: {report.low_count}")
    print(f"   Scan Duration: {report.scan_duration:.2f}s")

    if verbose and report.vulnerabilities:
        print("\n   Vulnerability Details:")
        for vuln in report.vulnerabilities[:10]:  # Limit to first 10
            severity_emoji = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }
            emoji = severity_emoji.get(vuln.get("severity", "unknown"), "⚪")
            print(
                f"     {emoji} {vuln.get('id', 'N/A')}: {vuln.get('title', 'No title')}"
            )
            if vuln.get("description"):
                print(f"        {vuln['description']}")

    print()


def print_compliance_status(compliance_status):
    """Print compliance status."""
    print("📋 COMPLIANCE STATUS")

    for area, status in compliance_status.items():
        if isinstance(status, bool):
            emoji = "✅" if status else "❌"
            status_text = "COMPLIANT" if status else "NON-COMPLIANT"
            print(f"   {emoji} {area.replace('_', ' ').title()}: {status_text}")
        else:
            print(f"   ❓ {area.replace('_', ' ').title()}: {status}")

    print()


def run_security_validation(args):
    """Run security validation with specified options."""
    print_banner()

    # Load container configuration if specified
    container_config = {}
    if args.config_file:
        try:
            with open(args.config_file) as f:
                container_config = json.load(f)
            print(f"📁 Loaded configuration from: {args.config_file}")
        except Exception as e:
            print(f"❌ Failed to load configuration file: {e}")
            return 1
    elif args.flow_name or args.environment:
        # Use ContainerConfigManager to load configuration
        try:
            config_manager = ContainerConfigManager(
                flow_name=args.flow_name, environment=args.environment
            )
            container_config = config_manager.load_container_config()
            print(
                f"📁 Loaded configuration for flow: {args.flow_name}, env: {args.environment}"
            )
        except Exception as e:
            print(f"❌ Failed to load container configuration: {e}")
            return 1

    # Create security validator
    validator = SecurityValidator(
        container_config=container_config,
        enable_vulnerability_scanning=args.enable_vuln_scan,
        enable_network_validation=args.enable_network_validation,
        log_level=args.log_level,
    )

    print("🔧 Security validation configured:")
    print(
        f"   Vulnerability Scanning: {'Enabled' if args.enable_vuln_scan else 'Disabled'}"
    )
    print(
        f"   Network Validation: {'Enabled' if args.enable_network_validation else 'Disabled'}"
    )
    print(f"   Log Level: {args.log_level}")
    print()

    # Run individual checks if specified
    if args.check_user_permissions:
        print("👤 Running user permissions validation...")
        result = validator.validate_user_permissions()
        print_security_result(result, args.verbose)

    if args.check_network_policies:
        print("🌐 Running network policies validation...")
        result = validator.validate_network_policies()
        print_security_result(result, args.verbose)

    if args.check_secret_management:
        print("🔐 Running secret management validation...")
        result = validator.validate_secret_management()
        print_security_result(result, args.verbose)

    if args.scan_vulnerabilities:
        print("🔍 Running vulnerability scan...")
        report = validator.scan_vulnerabilities()
        print_vulnerability_report(report, args.verbose)

    # Run comprehensive validation if no specific checks requested
    if not any(
        [
            args.check_user_permissions,
            args.check_network_policies,
            args.check_secret_management,
            args.scan_vulnerabilities,
        ]
    ):
        print("🔒 Running comprehensive security validation...")
        start_time = time.time()

        report = validator.comprehensive_security_validation()

        end_time = time.time()

        # Print overall status
        status_emoji = {
            SecurityLevel.PASS: "✅",
            SecurityLevel.WARNING: "⚠️",
            SecurityLevel.FAIL: "❌",
        }

        emoji = status_emoji.get(report.overall_status, "❓")
        print(f"{emoji} OVERALL SECURITY STATUS: {report.overall_status.value.upper()}")
        print(f"   Total Duration: {end_time - start_time:.2f}s")
        print()

        # Print summary
        print("📊 VALIDATION SUMMARY")
        print(f"   Total Checks: {report.summary['total_checks']}")
        print(f"   Passed: {report.summary['passed_checks']}")
        print(f"   Warnings: {report.summary['warning_checks']}")
        print(f"   Failed: {report.summary['failed_checks']}")
        print()

        # Print individual check results
        for _check_name, result in report.checks.items():
            print_security_result(result, args.verbose)

        # Print vulnerability reports
        for vuln_report in report.vulnerability_reports:
            print_vulnerability_report(vuln_report, args.verbose)

        # Print compliance status
        print_compliance_status(report.compliance_status)

        # Print recommendations
        if report.recommendations:
            print("💡 RECOMMENDATIONS")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"   {i}. {rec}")
            print()

        # Save report if requested
        if args.output_file:
            try:
                report_dict = report.to_dict()
                with open(args.output_file, "w") as f:
                    json.dump(report_dict, f, indent=2)
                print(f"💾 Security report saved to: {args.output_file}")
            except Exception as e:
                print(f"❌ Failed to save report: {e}")
                return 1

        # Return appropriate exit code
        if report.overall_status == SecurityLevel.FAIL:
            print("❌ Security validation FAILED - Critical issues found")
            return 1
        elif report.overall_status == SecurityLevel.WARNING:
            print("⚠️  Security validation completed with WARNINGS")
            return 0 if args.ignore_warnings else 1
        else:
            print("✅ Security validation PASSED")
            return 0

    return 0


def main():
    """Main entry point for security validation runner."""
    parser = argparse.ArgumentParser(
        description="Container Security Validation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run comprehensive security validation
  python run_security_validation.py

  # Run with specific flow and environment
  python run_security_validation.py --flow-name rpa1 --environment development

  # Run specific checks only
  python run_security_validation.py --check-user-permissions --check-network-policies

  # Run with vulnerability scanning enabled
  python run_security_validation.py --enable-vuln-scan

  # Save report to file
  python run_security_validation.py --output-file security_report.json

  # Run with custom configuration
  python run_security_validation.py --config-file custom_config.json
        """,
    )

    # Configuration options
    parser.add_argument(
        "--flow-name",
        help="Flow name for configuration loading (e.g., rpa1, rpa2, rpa3)",
    )
    parser.add_argument(
        "--environment",
        help="Environment name for configuration loading (e.g., development, staging, production)",
    )
    parser.add_argument("--config-file", help="Path to JSON configuration file")

    # Validation options
    parser.add_argument(
        "--check-user-permissions",
        action="store_true",
        help="Run user permissions validation only",
    )
    parser.add_argument(
        "--check-network-policies",
        action="store_true",
        help="Run network policies validation only",
    )
    parser.add_argument(
        "--check-secret-management",
        action="store_true",
        help="Run secret management validation only",
    )
    parser.add_argument(
        "--scan-vulnerabilities",
        action="store_true",
        help="Run vulnerability scan only",
    )

    # Feature toggles
    parser.add_argument(
        "--enable-vuln-scan",
        action="store_true",
        default=False,
        help="Enable vulnerability scanning (default: disabled)",
    )
    parser.add_argument(
        "--disable-network-validation",
        action="store_true",
        help="Disable network validation",
    )
    parser.add_argument(
        "--ignore-warnings",
        action="store_true",
        help="Exit with code 0 even if warnings are found",
    )

    # Output options
    parser.add_argument("--output-file", help="Save security report to JSON file")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output with detailed information",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Set network validation flag
    args.enable_network_validation = not args.disable_network_validation

    try:
        exit_code = run_security_validation(args)
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n❌ Security validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Security validation failed with error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
