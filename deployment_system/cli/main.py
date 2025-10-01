#!/usr/bin/env python3
"""
Deployment System CLI

Main command-line interface for the deployment system.
"""

import argparse
import sys

from .commands import DeploymentCLI
from .utils import CLIUtils


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Prefect Deployment System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Discover flows command
    discover_parser = subparsers.add_parser(
        "discover-flows", help="Discover and list all available flows"
    )
    discover_parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format (default: table)",
    )

    # Build deployments command
    build_parser = subparsers.add_parser(
        "build-deployments", help="Build deployments for all flows"
    )
    build_parser.add_argument(
        "--environment",
        "-e",
        default="development",
        help="Target environment (default: development)",
    )
    build_parser.add_argument(
        "--type",
        choices=["python", "docker", "all"],
        default="all",
        help="Deployment type to build (default: all)",
    )

    # Deploy commands
    deploy_python_parser = subparsers.add_parser(
        "deploy-python", help="Deploy Python-based deployments"
    )
    deploy_python_parser.add_argument(
        "--environment",
        "-e",
        default="development",
        help="Target environment (default: development)",
    )

    deploy_docker_parser = subparsers.add_parser(
        "deploy-containers", help="Deploy container-based deployments"
    )
    deploy_docker_parser.add_argument(
        "--environment",
        "-e",
        default="development",
        help="Target environment (default: development)",
    )

    deploy_all_parser = subparsers.add_parser(
        "deploy-all", help="Deploy all deployments (Python and Docker)"
    )
    deploy_all_parser.add_argument(
        "--environment",
        "-e",
        default="development",
        help="Target environment (default: development)",
    )

    # Clean deployments command
    clean_parser = subparsers.add_parser(
        "clean-deployments", help="Remove existing deployments"
    )
    clean_parser.add_argument(
        "--pattern", help="Pattern to match deployments for removal"
    )
    clean_parser.add_argument(
        "--confirm", action="store_true", help="Skip confirmation prompt"
    )

    # Environment-specific deployment commands
    for env in ["dev", "staging", "prod"]:
        env_parser = subparsers.add_parser(
            f"deploy-{env}", help=f"Deploy to {env} environment"
        )
        env_parser.add_argument(
            "--type",
            choices=["python", "docker", "all"],
            default="all",
            help="Deployment type (default: all)",
        )

    # Validation commands
    validate_parser = subparsers.add_parser(
        "validate-deployments", help="Validate deployment configurations"
    )
    validate_parser.add_argument(
        "--environment",
        "-e",
        default="development",
        help="Target environment (default: development)",
    )

    # Status commands
    subparsers.add_parser("status", help="Show deployment system status")

    # UI Integration commands
    subparsers.add_parser(
        "check-ui", help="Check Prefect UI connectivity and accessibility"
    )

    verify_ui_parser = subparsers.add_parser(
        "verify-deployment-ui", help="Verify specific deployment appears in UI"
    )
    verify_ui_parser.add_argument(
        "--deployment-name", required=True, help="Deployment name to verify"
    )
    verify_ui_parser.add_argument(
        "--flow-name", required=True, help="Flow name for the deployment"
    )
    verify_ui_parser.add_argument(
        "--timeout", type=int, default=30, help="Timeout in seconds (default: 30)"
    )

    health_parser = subparsers.add_parser(
        "check-deployment-health", help="Check health of specific deployment"
    )
    health_parser.add_argument(
        "--deployment-name", required=True, help="Deployment name to check"
    )
    health_parser.add_argument(
        "--flow-name", required=True, help="Flow name for the deployment"
    )

    subparsers.add_parser(
        "deployment-status-report",
        help="Generate comprehensive deployment status report",
    )

    validate_ui_parser = subparsers.add_parser(
        "validate-ui", help="Validate all deployments visibility in UI"
    )
    validate_ui_parser.add_argument(
        "--flow-name", help="Validate deployments for specific flow only"
    )

    subparsers.add_parser("troubleshoot-ui", help="Run UI connectivity troubleshooting")

    troubleshoot_deployment_parser = subparsers.add_parser(
        "troubleshoot-deployment", help="Troubleshoot specific deployment visibility"
    )
    troubleshoot_deployment_parser.add_argument(
        "--deployment-name", required=True, help="Deployment name to troubleshoot"
    )
    troubleshoot_deployment_parser.add_argument(
        "--flow-name", required=True, help="Flow name for the deployment"
    )

    wait_ready_parser = subparsers.add_parser(
        "wait-deployment-ready", help="Wait for deployment to become ready"
    )
    wait_ready_parser.add_argument(
        "--deployment-name", required=True, help="Deployment name to wait for"
    )
    wait_ready_parser.add_argument(
        "--flow-name", required=True, help="Flow name for the deployment"
    )
    wait_ready_parser.add_argument(
        "--timeout", type=int, default=60, help="Timeout in seconds (default: 60)"
    )

    list_ui_parser = subparsers.add_parser(
        "list-deployments-ui", help="List all deployments with UI status"
    )
    list_ui_parser.add_argument(
        "--flow-name", help="List deployments for specific flow only"
    )

    get_url_parser = subparsers.add_parser(
        "get-deployment-url", help="Get UI URL for specific deployment"
    )
    get_url_parser.add_argument(
        "--deployment-name", required=True, help="Deployment name"
    )
    get_url_parser.add_argument(
        "--flow-name", required=True, help="Flow name for the deployment"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        cli = DeploymentCLI()
        return execute_command(cli, args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def execute_command(cli: DeploymentCLI, args) -> int:
    """Execute the specified command."""

    if args.command == "discover-flows":
        return cmd_discover_flows(cli, args)
    elif args.command == "build-deployments":
        return cmd_build_deployments(cli, args)
    elif args.command == "deploy-python":
        return cmd_deploy_python(cli, args)
    elif args.command == "deploy-containers":
        return cmd_deploy_containers(cli, args)
    elif args.command == "deploy-all":
        return cmd_deploy_all(cli, args)
    elif args.command == "clean-deployments":
        return cmd_clean_deployments(cli, args)
    elif args.command.startswith("deploy-") and args.command.endswith(
        ("dev", "staging", "prod")
    ):
        return cmd_deploy_environment(cli, args)
    elif args.command == "validate-deployments":
        return cmd_validate_deployments(cli, args)
    elif args.command == "status":
        return cmd_status(cli, args)
    elif args.command == "check-ui":
        return cmd_check_ui(cli, args)
    elif args.command == "verify-deployment-ui":
        return cmd_verify_deployment_ui(cli, args)
    elif args.command == "check-deployment-health":
        return cmd_check_deployment_health(cli, args)
    elif args.command == "deployment-status-report":
        return cmd_deployment_status_report(cli, args)
    elif args.command == "validate-ui":
        return cmd_validate_ui(cli, args)
    elif args.command == "troubleshoot-ui":
        return cmd_troubleshoot_ui(cli, args)
    elif args.command == "troubleshoot-deployment":
        return cmd_troubleshoot_deployment(cli, args)
    elif args.command == "wait-deployment-ready":
        return cmd_wait_deployment_ready(cli, args)
    elif args.command == "list-deployments-ui":
        return cmd_list_deployments_ui(cli, args)
    elif args.command == "get-deployment-url":
        return cmd_get_deployment_url(cli, args)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1


def cmd_discover_flows(cli: DeploymentCLI, args) -> int:
    """Execute discover-flows command."""
    flows = cli.discover_flows()

    if args.format == "json":
        print(CLIUtils.format_json(flows))
    else:
        print(f"Discovered {len(flows)} flows:\n")

        headers = ["Name", "Path", "Python", "Docker", "Valid", "Errors"]
        rows = []

        for flow in flows:
            rows.append(
                [
                    flow["name"],
                    flow["path"],
                    "✓" if flow["supports_python"] else "✗",
                    "✓" if flow["supports_docker"] else "✗",
                    "✓" if flow["is_valid"] else "✗",
                    len(flow["errors"]),
                ]
            )

        CLIUtils.print_table(headers, rows)

        # Show validation errors if any
        invalid_flows = [f for f in flows if not f["is_valid"]]
        if invalid_flows:
            print("\nValidation Errors:")
            CLIUtils.print_validation_results(invalid_flows)

    return 0


def cmd_build_deployments(cli: DeploymentCLI, args) -> int:
    """Execute build-deployments command."""
    print(f"Building deployments for environment: {args.environment}")

    result = cli.build_deployments(args.environment)

    if result["success"]:
        print(f"✓ {result['message']}")
        print(f"Created {result['deployment_count']} deployments")
        return 0
    else:
        print(f"✗ {result['message']}", file=sys.stderr)
        return 1


def cmd_deploy_python(cli: DeploymentCLI, args) -> int:
    """Execute deploy-python command."""
    print(f"Deploying Python deployments to environment: {args.environment}")

    result = cli.deploy_python_deployments(args.environment)

    if result["success"]:
        print(f"✓ {result['message']}")
        print(f"Deployed {result['deployment_count']} Python deployments")
        return 0
    else:
        print(f"✗ {result['message']}", file=sys.stderr)
        return 1


def cmd_deploy_containers(cli: DeploymentCLI, args) -> int:
    """Execute deploy-containers command."""
    print(f"Deploying container deployments to environment: {args.environment}")

    result = cli.deploy_docker_deployments(args.environment)

    if result["success"]:
        print(f"✓ {result['message']}")
        print(f"Deployed {result['deployment_count']} container deployments")
        return 0
    else:
        print(f"✗ {result['message']}", file=sys.stderr)
        return 1


def cmd_deploy_all(cli: DeploymentCLI, args) -> int:
    """Execute deploy-all command."""
    print(f"Deploying all deployments to environment: {args.environment}")

    result = cli.deploy_all_deployments(args.environment)

    if result["success"]:
        print(f"✓ {result['message']}")
        print(f"Deployed {result['deployment_count']} deployments")
        return 0
    else:
        print(f"✗ {result['message']}", file=sys.stderr)
        return 1


def cmd_clean_deployments(cli: DeploymentCLI, args) -> int:
    """Execute clean-deployments command."""
    if not args.confirm:
        if not CLIUtils.confirm_action("Are you sure you want to clean deployments?"):
            print("Operation cancelled")
            return 0

    print("Cleaning deployments...")

    result = cli.clean_deployments(args.pattern)

    if result["success"]:
        print(f"✓ {result['message']}")
        print(f"Cleaned {result['cleaned_count']} deployments")
        return 0
    else:
        print(f"✗ {result['message']}", file=sys.stderr)
        return 1


def cmd_deploy_environment(cli: DeploymentCLI, args) -> int:
    """Execute environment-specific deployment command."""
    # Extract environment from command name (deploy-dev -> dev)
    env = args.command.split("-")[1]
    env_map = {"dev": "development", "staging": "staging", "prod": "production"}
    environment = env_map.get(env, env)

    print(f"Deploying to {environment} environment")

    # Use the deployment type if specified, otherwise deploy all
    deployment_type = getattr(args, "type", "all")

    if deployment_type == "python":
        result = cli.deploy_python_deployments(environment)
    elif deployment_type == "docker":
        result = cli.deploy_docker_deployments(environment)
    else:
        result = cli.deploy_all_deployments(environment)

    if result["success"]:
        print(f"✓ {result['message']}")
        print(f"Deployed {result['deployment_count']} deployments to {environment}")
        return 0
    else:
        print(f"✗ {result['message']}", file=sys.stderr)
        return 1


def cmd_validate_deployments(cli: DeploymentCLI, args) -> int:
    """Execute validate-deployments command."""
    print(f"Validating deployments for environment: {args.environment}")

    flows = cli.discover_flows()
    invalid_flows = [f for f in flows if not f["is_valid"]]

    if invalid_flows:
        print(f"Found {len(invalid_flows)} invalid flows:")
        CLIUtils.print_validation_results(invalid_flows)
        return 1
    else:
        print("✓ All flows are valid")
        return 0


def cmd_status(cli: DeploymentCLI, args) -> int:
    """Execute status command."""
    summary = cli.get_deployment_summary()

    print("Deployment System Status:")
    print(f"  Total flows: {summary.get('total_flows', 0)}")
    print(f"  Python capable: {summary.get('python_capable', 0)}")
    print(f"  Docker capable: {summary.get('docker_capable', 0)}")
    print(f"  Both capable: {summary.get('both_capable', 0)}")
    print(f"  Invalid flows: {summary.get('invalid_flows', 0)}")

    environments = cli.list_environments()
    print(f"  Available environments: {', '.join(environments)}")

    return 0


def cmd_check_ui(cli: DeploymentCLI, args) -> int:
    """Execute check-ui command."""
    print("Checking Prefect UI connectivity...")

    result = cli.check_ui_connectivity()

    if result["success"]:
        print(cli.ui_cli.format_connectivity_report(result))
        return 0 if result["overall_status"] == "healthy" else 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_verify_deployment_ui(cli: DeploymentCLI, args) -> int:
    """Execute verify-deployment-ui command."""
    print(f"Verifying deployment {args.flow_name}/{args.deployment_name} in UI...")

    result = cli.verify_deployment_in_ui(
        args.deployment_name, args.flow_name, args.timeout
    )

    if result["success"]:
        if result["visible"]:
            print("✓ Deployment is visible in UI")
            if result.get("ui_url"):
                print(f"  URL: {result['ui_url']}")
            return 0
        else:
            print("✗ Deployment not visible in UI")
            verification = result["verification_result"]
            if verification.get("error"):
                print(f"  Error: {verification['error']}")
            return 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_check_deployment_health(cli: DeploymentCLI, args) -> int:
    """Execute check-deployment-health command."""
    print(f"Checking health of deployment {args.flow_name}/{args.deployment_name}...")

    result = cli.check_deployment_health(args.deployment_name, args.flow_name)

    if result["success"]:
        print(cli.ui_cli.format_deployment_health(result))
        return 0 if result["healthy"] else 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_deployment_status_report(cli: DeploymentCLI, args) -> int:
    """Execute deployment-status-report command."""
    print("Generating deployment status report...")

    result = cli.get_deployment_status_report()

    if result["success"]:
        report = result["report"]
        summary = report["summary"]

        print("\n📊 Deployment Status Report")
        print(f"  Timestamp: {report['timestamp']}")
        print(f"  Total Deployments: {summary['total_deployments']}")
        print(
            f"  Healthy: {summary['healthy_deployments']} ({summary['health_percentage']:.1f}%)"
        )
        print(f"  Unhealthy: {summary['unhealthy_deployments']}")
        print(f"  API Connected: {'✅' if summary['api_connected'] else '❌'}")
        print(f"  UI Accessible: {'✅' if summary['ui_accessible'] else '❌'}")

        if report["system_health"]["issues"]:
            print("\n⚠️  System Issues:")
            for issue in report["system_health"]["issues"]:
                print(f"    • {issue}")

        if report["system_health"]["recommendations"]:
            print("\n💡 Recommendations:")
            for rec in report["system_health"]["recommendations"][:5]:
                print(f"    • {rec}")

        return 0 if report["system_health"]["overall_healthy"] else 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_validate_ui(cli: DeploymentCLI, args) -> int:
    """Execute validate-ui command."""
    flow_name = getattr(args, "flow_name", None)
    print(
        f"Validating deployments UI visibility{f' for flow {flow_name}' if flow_name else ''}..."
    )

    result = cli.validate_deployments_ui(flow_name)

    if result["success"]:
        validation = result["validation_result"]
        print("\n🔍 UI Validation Results")
        print(f"  Total Deployments: {validation['total']}")
        print(f"  Valid: {validation['valid']}")
        print(f"  Invalid: {validation['invalid']}")

        if validation["summary"]["common_issues"]:
            print("\n⚠️  Common Issues:")
            for issue, count in validation["summary"]["common_issues"].items():
                print(f"    • {issue} ({count} deployments)")

        return 0 if validation["invalid"] == 0 else 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_troubleshoot_ui(cli: DeploymentCLI, args) -> int:
    """Execute troubleshoot-ui command."""
    print("Running UI connectivity troubleshooting...")

    result = cli.troubleshoot_connectivity()

    if result["success"]:
        print(cli.ui_cli.format_troubleshooting_report(result))
        return 0 if result["severity"] in ["info", "warning"] else 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_troubleshoot_deployment(cli: DeploymentCLI, args) -> int:
    """Execute troubleshoot-deployment command."""
    print(f"Troubleshooting deployment {args.flow_name}/{args.deployment_name}...")

    result = cli.troubleshoot_deployment_visibility(
        args.deployment_name, args.flow_name
    )

    if result["success"]:
        diagnosis = result["diagnosis"]
        severity_icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
        severity = diagnosis["severity"]

        print(
            f"\n{severity_icons.get(severity, 'ℹ️')} Deployment Troubleshooting ({severity.upper()})"
        )
        print(f"  Deployment: {diagnosis['full_name']}")

        if diagnosis["issues_found"]:
            print("  Issues Found:")
            for issue in diagnosis["issues_found"]:
                print(f"    • {issue}")

        if diagnosis["recommendations"]:
            print("  Recommendations:")
            for rec in diagnosis["recommendations"]:
                print(f"    • {rec}")

        return 0 if severity in ["info", "warning"] else 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_wait_deployment_ready(cli: DeploymentCLI, args) -> int:
    """Execute wait-deployment-ready command."""
    print(
        f"Waiting for deployment {args.flow_name}/{args.deployment_name} to become ready..."
    )

    result = cli.wait_for_deployment_ready(
        args.deployment_name, args.flow_name, args.timeout
    )

    if result["success"]:
        wait_result = result["wait_result"]
        if wait_result["ready"]:
            print(
                f"✓ Deployment ready after {wait_result['wait_time_seconds']} seconds"
            )
            return 0
        else:
            print(f"✗ Deployment not ready after {args.timeout} seconds")
            if wait_result.get("error"):
                print(f"  Error: {wait_result['error']}")
            return 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_list_deployments_ui(cli: DeploymentCLI, args) -> int:
    """Execute list-deployments-ui command."""
    flow_name = getattr(args, "flow_name", None)
    print(
        f"Listing deployments with UI status{f' for flow {flow_name}' if flow_name else ''}..."
    )

    result = cli.list_deployments_with_ui_status(flow_name)

    if result["success"]:
        deployments = result["deployments"]

        if not deployments:
            print("No deployments found")
            return 0

        print(f"\n📋 Deployments ({result['total_count']} total)")

        headers = ["Flow", "Deployment", "UI Accessible", "Created", "UI URL"]
        rows = []

        for deployment in deployments:
            ui_accessible = "✅" if deployment.get("ui_accessible") else "❌"
            ui_url = deployment.get("ui_url", "N/A")
            if len(ui_url) > 50:
                ui_url = ui_url[:47] + "..."

            rows.append(
                [
                    deployment["flow_name"],
                    deployment["name"],
                    ui_accessible,
                    (
                        deployment.get("created", "N/A")[:10]
                        if deployment.get("created")
                        else "N/A"
                    ),
                    ui_url,
                ]
            )

        CLIUtils.print_table(headers, rows)
        return 0
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


def cmd_get_deployment_url(cli: DeploymentCLI, args) -> int:
    """Execute get-deployment-url command."""
    result = cli.get_deployment_ui_url(args.deployment_name, args.flow_name)

    if result["success"]:
        if result["ui_url"]:
            print(f"🔗 UI URL for {args.flow_name}/{args.deployment_name}:")
            print(f"   {result['ui_url']}")
            return 0
        else:
            print(f"✗ No UI URL available for {args.flow_name}/{args.deployment_name}")
            return 1
    else:
        print(f"✗ Error: {result.get('error', 'Unknown error')}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
