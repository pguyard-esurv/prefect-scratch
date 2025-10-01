#!/usr/bin/env python3
"""
Configuration Management CLI

Command-line interface for managing deployment configurations.
"""

import argparse
import sys

from ..config.config_validator import ConfigValidator
from ..config.manager import ConfigurationManager


def validate_config(args):
    """Validate configuration command."""
    validator = ConfigValidator(args.config_dir)

    if args.environment:
        # Validate specific environment
        result = validator.manager.validate_environment_config(args.environment)
        results = {args.environment: result}
    else:
        # Validate all configurations
        results = validator.validate_all_configurations()

    # Filter warnings if quiet mode
    if args.quiet:
        for result in results.values():
            result.warnings = []

    is_valid = validator.print_validation_results(results)
    return 0 if is_valid else 1


def list_environments(args):
    """List available environments command."""
    manager = ConfigurationManager(args.config_dir)
    environments = manager.list_environments()

    print("Available Environments:")
    print("=" * 30)

    if not environments:
        print("No environments configured.")
        return 1

    for env_name in environments:
        env_config = manager.get_environment_config(env_name)
        print(f"• {env_name}")
        if env_config:
            print(f"  API URL: {env_config.prefect_api_url}")
            if env_config.work_pools:
                pools = ", ".join(f"{k}:{v}" for k, v in env_config.work_pools.items())
                print(f"  Work Pools: {pools}")
        print()

    return 0


def show_environment(args):
    """Show environment details command."""
    manager = ConfigurationManager(args.config_dir)
    env_config = manager.get_environment_config(args.environment)

    if not env_config:
        print(f"Environment '{args.environment}' not found.")
        print(f"Available environments: {', '.join(manager.list_environments())}")
        return 1

    print(f"Environment: {args.environment}")
    print("=" * 50)
    print(f"Name: {env_config.name}")
    print(f"Prefect API URL: {env_config.prefect_api_url}")

    print("\nWork Pools:")
    for pool_type, pool_name in env_config.work_pools.items():
        print(f"  {pool_type}: {pool_name}")

    print("\nDefault Parameters:")
    for key, value in env_config.default_parameters.items():
        print(f"  {key}: {value}")

    print("\nResource Limits:")
    print(f"  Memory: {env_config.resource_limits.memory}")
    print(f"  CPU: {env_config.resource_limits.cpu}")
    if env_config.resource_limits.storage:
        print(f"  Storage: {env_config.resource_limits.storage}")

    if env_config.docker_registry:
        print(f"\nDocker Registry: {env_config.docker_registry}")

    print(f"Image Pull Policy: {env_config.image_pull_policy}")

    if env_config.networks:
        print(f"\nNetworks: {', '.join(env_config.networks)}")

    if env_config.default_tags:
        print(f"\nDefault Tags: {', '.join(env_config.default_tags)}")

    return 0


def show_global_config(args):
    """Show global configuration command."""
    manager = ConfigurationManager(args.config_dir)
    global_config = manager.get_global_config()

    if not global_config:
        print("No global configuration found.")
        return 1

    print("Global Configuration:")
    print("=" * 30)

    for section, config in global_config.items():
        print(f"\n{section.upper()}:")
        if isinstance(config, dict):
            for key, value in config.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {config}")

    return 0


def show_flow_overrides(args):
    """Show flow overrides command."""
    manager = ConfigurationManager(args.config_dir)

    if args.flow:
        # Show specific flow overrides
        overrides = manager.get_flow_overrides(args.flow)
        if not overrides:
            print(f"No overrides configured for flow '{args.flow}'.")
            return 1

        print(f"Flow Overrides: {args.flow}")
        print("=" * 30)

        for key, value in overrides.items():
            print(f"{key}:")
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    print(f"  {sub_key}: {sub_value}")
            else:
                print(f"  {value}")
    else:
        # Show all flow overrides
        all_overrides = manager._flow_overrides
        if not all_overrides:
            print("No flow overrides configured.")
            return 1

        print("Flow Overrides:")
        print("=" * 20)

        for flow_name, overrides in all_overrides.items():
            print(f"\n{flow_name}:")
            for key, value in overrides.items():
                print(f"  {key}:")
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        print(f"    {sub_key}: {sub_value}")
                else:
                    print(f"    {value}")

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Deployment System Configuration Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--config-dir",
        default="config",
        help="Configuration directory (default: config)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.add_argument(
        "--environment",
        help="Validate specific environment only",
    )
    validate_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors, suppress warnings",
    )
    validate_parser.set_defaults(func=validate_config)

    # List environments command
    list_parser = subparsers.add_parser(
        "list-environments", help="List available environments"
    )
    list_parser.set_defaults(func=list_environments)

    # Show environment command
    show_env_parser = subparsers.add_parser(
        "show-environment", help="Show environment details"
    )
    show_env_parser.add_argument("environment", help="Environment name to show")
    show_env_parser.set_defaults(func=show_environment)

    # Show global config command
    global_parser = subparsers.add_parser(
        "show-global", help="Show global configuration"
    )
    global_parser.set_defaults(func=show_global_config)

    # Show flow overrides command
    overrides_parser = subparsers.add_parser(
        "show-overrides", help="Show flow overrides"
    )
    overrides_parser.add_argument("--flow", help="Show overrides for specific flow")
    overrides_parser.set_defaults(func=show_flow_overrides)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        return args.func(args)
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
