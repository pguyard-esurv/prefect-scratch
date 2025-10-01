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
    subparsers.add_parser(
        "status", help="Show deployment system status"
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


if __name__ == "__main__":
    sys.exit(main())
