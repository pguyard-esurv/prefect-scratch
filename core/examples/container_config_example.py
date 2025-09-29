#!/usr/bin/env python3
"""
Example usage of ContainerConfigManager for container configuration management.

This example demonstrates how to use the ContainerConfigManager to:
1. Load container configuration with CONTAINER_ prefix mapping
2. Validate container environment settings
3. Wait for service dependencies
4. Generate startup reports with recommendations

Run this example with different environment variables to see how the
configuration system responds to various scenarios.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import after path modification (required for example to work)
from core.container_config import ContainerConfigManager  # noqa: E402


def example_basic_usage():
    """Demonstrate basic ContainerConfigManager usage."""
    print("=== Basic ContainerConfigManager Usage ===")

    # Create a container config manager
    manager = ContainerConfigManager(
        flow_name="rpa1",
        environment="development",
        container_id="example-container-001",
    )

    print(f"Container ID: {manager.container_id}")
    print(f"Environment: {manager.environment}")
    print(f"Flow Name: {manager.flow_name}")

    # Load complete container configuration
    config = manager.load_container_config()

    print("\nConfiguration loaded:")
    print(f"  - Databases: {len(config['databases'])}")
    print(f"  - Services: {len(config['services'])}")
    print(f"  - Monitoring enabled: {config['monitoring']['health_check_enabled']}")
    print(f"  - Security - Run as non-root: {config['security']['run_as_non_root']}")
    print(f"  - Resources - CPU limit: {config['resources']['cpu_limit']}")


def example_container_prefix_mapping():
    """Demonstrate CONTAINER_ prefix environment variable mapping."""
    print("\n=== CONTAINER_ Prefix Mapping Example ===")

    # Set up some CONTAINER_ prefixed environment variables
    os.environ.update(
        {
            "CONTAINER_DATABASE_REQUIRED": "example_db",
            "CONTAINER_DATABASE_EXAMPLE_DB_TYPE": "postgresql",
            "CONTAINER_DATABASE_EXAMPLE_DB_CONNECTION_STRING": "postgresql://user:pass@db:5432/example",
            "CONTAINER_SERVICE_REQUIRED": "api_service",
            "CONTAINER_SERVICE_API_SERVICE_HEALTH_ENDPOINT": "http://api:8080/health",
            "CONTAINER_MONITORING_LOG_LEVEL": "DEBUG",
            "CONTAINER_SECURITY_USER_ID": "1001",
        }
    )

    manager = ContainerConfigManager()
    config = manager.load_container_config()

    print("CONTAINER_ prefixed configuration loaded:")
    if config["databases"]:
        db_name = list(config["databases"].keys())[0]
        db_config = config["databases"][db_name]
        print(f"  - Database '{db_name}': {db_config.database_type}")
        print(f"    Connection: {db_config.connection_string}")

    if config["services"]:
        service = config["services"][0]
        print(f"  - Service '{service.service_name}': {service.health_endpoint}")

    print(f"  - Log Level: {config['monitoring']['log_level']}")
    print(f"  - User ID: {config['security']['user_id']}")


def example_configuration_validation():
    """Demonstrate configuration validation with error reporting."""
    print("\n=== Configuration Validation Example ===")

    # Set up configuration with some issues
    os.environ.update(
        {
            "CONTAINER_DATABASE_REQUIRED": "test_db",
            "CONTAINER_DATABASE_TEST_DB_TYPE": "mysql",  # Unsupported type
            "CONTAINER_DATABASE_TEST_DB_CONNECTION_STRING": "invalid://connection",  # Invalid format
            "CONTAINER_SECURITY_USER_ID": "999",  # Below 1000 - warning
            "CONTAINER_RESOURCE_CPU_LIMIT": "1.0",
            "CONTAINER_RESOURCE_CPU_REQUEST": "1.5",  # Exceeds limit - error
        }
    )

    manager = ContainerConfigManager()
    validation = manager.validate_container_environment()

    print(f"Validation result: {'VALID' if validation.valid else 'INVALID'}")

    if validation.errors:
        print(f"\nErrors found ({len(validation.errors)}):")
        for i, error in enumerate(validation.errors, 1):
            print(f"  {i}. {error}")

    if validation.warnings:
        print(f"\nWarnings found ({len(validation.warnings)}):")
        for i, warning in enumerate(validation.warnings, 1):
            print(f"  {i}. {warning}")


def example_startup_report():
    """Demonstrate startup report generation."""
    print("\n=== Startup Report Example ===")

    # Set up valid configuration
    os.environ.update(
        {
            "CONTAINER_DATABASE_REQUIRED": "app_db",
            "CONTAINER_DATABASE_APP_DB_TYPE": "postgresql",
            "CONTAINER_DATABASE_APP_DB_CONNECTION_STRING": "postgresql://app:secret@db:5432/app_db",
            "CONTAINER_SERVICE_REQUIRED": "cache",
            "CONTAINER_SERVICE_CACHE_HEALTH_ENDPOINT": "http://redis:6379/ping",
            "CONTAINER_MONITORING_HEALTH_CHECK_ENABLED": "true",
            "CONTAINER_SECURITY_RUN_AS_NON_ROOT": "true",
            "CONTAINER_SECURITY_USER_ID": "1000",
        }
    )

    manager = ContainerConfigManager(flow_name="rpa2", environment="production")
    report = manager.generate_startup_report()

    print("Startup Report:")
    print(f"  - Timestamp: {report.timestamp}")
    print(f"  - Environment: {report.environment}")
    print(f"  - Flow: {report.flow_name}")
    print(f"  - Overall Status: {report.overall_status.upper()}")
    print(f"  - Startup Duration: {report.startup_duration:.2f}s")

    print(f"\nRecommendations ({len(report.recommendations)}):")
    for i, rec in enumerate(report.recommendations, 1):
        print(f"  {i}. {rec}")


def example_service_dependency_waiting():
    """Demonstrate service dependency waiting (simulation)."""
    print("\n=== Service Dependency Waiting Example ===")

    # Set up service dependencies
    os.environ.update(
        {
            "CONTAINER_SERVICE_REQUIRED": "database,cache",
            "CONTAINER_SERVICE_DATABASE_HEALTH_ENDPOINT": "http://postgres:5432/health",
            "CONTAINER_SERVICE_DATABASE_TIMEOUT": "10",
            "CONTAINER_SERVICE_CACHE_HEALTH_ENDPOINT": "http://redis:6379/ping",
            "CONTAINER_SERVICE_CACHE_TIMEOUT": "5",
        }
    )

    manager = ContainerConfigManager()
    config = manager.load_container_config()

    print("Configured service dependencies:")
    for service in config["services"]:
        print(f"  - {service.service_name}: {service.health_endpoint}")
        print(f"    Timeout: {service.timeout}s, Required: {service.required}")

    print("\nNote: In a real container environment, wait_for_dependencies() would")
    print("check these endpoints and wait for services to become healthy.")


def cleanup_example_env():
    """Clean up example environment variables."""
    keys_to_remove = [key for key in os.environ.keys() if key.startswith("CONTAINER_")]
    for key in keys_to_remove:
        del os.environ[key]


def main():
    """Run all examples."""
    print("ContainerConfigManager Examples")
    print("=" * 50)

    try:
        example_basic_usage()
        example_container_prefix_mapping()
        example_configuration_validation()
        example_startup_report()
        example_service_dependency_waiting()

        print("\n" + "=" * 50)
        print("All examples completed successfully!")

    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Clean up environment variables
        cleanup_example_env()


if __name__ == "__main__":
    main()
