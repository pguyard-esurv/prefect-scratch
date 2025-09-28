#!/usr/bin/env python3
"""
Environment setup script for Prefect RPA solution.

This script sets up environment-specific configuration using Prefect's
secrets and variables system. It creates a hierarchical configuration
structure that supports:

- Environment-specific settings (development, staging, production)
- Flow-specific overrides within each environment
- Global fallback configuration

Usage:
    python scripts/setup_environments.py <environment>

Environments:
    development  - Local development environment
    staging      - Staging environment for testing
    production   - Production environment
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from prefect.blocks.system import Secret
from prefect.variables import Variable


def load_env_config(environment: str, flow_name: str = None):
    """Load configuration from .env files."""
    project_root = Path(__file__).parent.parent

    # Load global .env file
    global_env_file = project_root / "core" / "envs" / f".env.{environment}"
    if global_env_file.exists():
        load_dotenv(global_env_file)
        print(f"📁 Loaded global config: {global_env_file}")
    else:
        print(f"⚠️  Global .env file not found: {global_env_file}")

    # Load flow-specific .env file
    if flow_name:
        flow_env_file = project_root / "flows" / flow_name / f".env.{environment}"
        if flow_env_file.exists():
            load_dotenv(flow_env_file, override=True)
            print(f"📁 Loaded flow config: {flow_env_file}")
        else:
            print(f"⚠️  Flow .env file not found: {flow_env_file}")


def setup_development():
    """Set up development environment configuration from .env files."""
    print("🔧 Setting up development environment from .env files...")

    # Load global config
    load_env_config("development")

    # Set global secrets from .env
    global_api_key = os.getenv("GLOBAL_API_KEY", "dev-api-key-123")
    global_db_password = os.getenv("GLOBAL_DB_PASSWORD", "dev-db-password")
    global_external_token = os.getenv("GLOBAL_EXTERNAL_API_TOKEN", "dev-external-token")

    Secret(value=global_api_key).save("development-global-api-key", overwrite=True)
    Secret(value=global_db_password).save(
        "development-global-db-password", overwrite=True
    )
    Secret(value=global_external_token).save(
        "development-global-external-api-token", overwrite=True
    )

    # Set global variables from .env
    Variable.set(
        "development_global_database_url",
        os.getenv("GLOBAL_DATABASE_URL", "sqlite:///dev.db"),
        overwrite=True,
    )
    Variable.set(
        "development_global_log_level",
        os.getenv("GLOBAL_LOG_LEVEL", "DEBUG"),
        overwrite=True,
    )
    Variable.set(
        "development_global_debug_mode",
        os.getenv("GLOBAL_DEBUG_MODE", "true"),
        overwrite=True,
    )
    Variable.set(
        "development_global_max_retries",
        os.getenv("GLOBAL_MAX_RETRIES", "1"),
        overwrite=True,
    )
    Variable.set(
        "development_global_timeout", os.getenv("GLOBAL_TIMEOUT", "30"), overwrite=True
    )

    # Set up each flow
    for flow in ["rpa1", "rpa2", "rpa3"]:
        setup_flow_config("development", flow)

    print("✅ Development environment configured from .env files!")


def setup_flow_config(environment: str, flow_name: str):
    """Set up flow-specific configuration from .env files."""
    load_env_config(environment, flow_name)

    # Flow-specific secrets
    flow_api_key = os.getenv(f"{environment.upper()}_{flow_name.upper()}_API_KEY")
    if flow_api_key:
        Secret(value=flow_api_key).save(
            f"{environment}-{flow_name}-api-key", overwrite=True
        )

    # Flow-specific variables
    flow_vars = [
        "batch_size",
        "timeout",
        "cleanup_temp_files",
        "output_format",
        "validation_strict",
        "max_retries",
        "max_concurrent_tasks",
    ]

    for var in flow_vars:
        env_key = f"{environment.upper()}_{flow_name.upper()}_{var.upper()}"
        value = os.getenv(env_key)
        if value is not None:
            var_name = f"{environment}_{flow_name}_{var}"
            Variable.set(var_name, value, overwrite=True)


def setup_staging():
    """Set up staging environment configuration from .env files."""
    print("🔧 Setting up staging environment from .env files...")

    # Load global config
    load_env_config("staging")

    # Set global secrets from .env
    global_api_key = os.getenv("GLOBAL_API_KEY", "staging-api-key-456")
    global_db_password = os.getenv("GLOBAL_DB_PASSWORD", "staging-db-password")
    global_external_token = os.getenv(
        "GLOBAL_EXTERNAL_API_TOKEN", "staging-external-token"
    )

    Secret(value=global_api_key).save("staging-global-api-key", overwrite=True)
    Secret(value=global_db_password).save("staging-global-db-password", overwrite=True)
    Secret(value=global_external_token).save(
        "staging-global-external-api-token", overwrite=True
    )

    # Set global variables from .env
    Variable.set(
        "staging_global_database_url",
        os.getenv(
            "GLOBAL_DATABASE_URL", "postgresql://staging:pass@staging-db:5432/rpa"
        ),
        overwrite=True,
    )
    Variable.set(
        "staging_global_log_level",
        os.getenv("GLOBAL_LOG_LEVEL", "INFO"),
        overwrite=True,
    )
    Variable.set(
        "staging_global_debug_mode",
        os.getenv("GLOBAL_DEBUG_MODE", "false"),
        overwrite=True,
    )
    Variable.set(
        "staging_global_max_retries",
        os.getenv("GLOBAL_MAX_RETRIES", "3"),
        overwrite=True,
    )
    Variable.set(
        "staging_global_timeout", os.getenv("GLOBAL_TIMEOUT", "60"), overwrite=True
    )

    # Set up each flow
    for flow in ["rpa1", "rpa2", "rpa3"]:
        setup_flow_config("staging", flow)

    print("✅ Staging environment configured from .env files!")


def setup_production():
    """Set up production environment configuration from .env files."""
    print("🔧 Setting up production environment from .env files...")

    # Load global config
    load_env_config("production")

    # Set global secrets from .env
    global_api_key = os.getenv("GLOBAL_API_KEY", "prod-api-key-789")
    global_db_password = os.getenv("GLOBAL_DB_PASSWORD", "prod-db-password")
    global_external_token = os.getenv(
        "GLOBAL_EXTERNAL_API_TOKEN", "prod-external-token"
    )

    Secret(value=global_api_key).save("production-global-api-key", overwrite=True)
    Secret(value=global_db_password).save(
        "production-global-db-password", overwrite=True
    )
    Secret(value=global_external_token).save(
        "production-global-external-api-token", overwrite=True
    )

    # Set global variables from .env
    Variable.set(
        "production_global_database_url",
        os.getenv("GLOBAL_DATABASE_URL", "postgresql://prod:pass@prod-db:5432/rpa"),
        overwrite=True,
    )
    Variable.set(
        "production_global_log_level",
        os.getenv("GLOBAL_LOG_LEVEL", "WARNING"),
        overwrite=True,
    )
    Variable.set(
        "production_global_debug_mode",
        os.getenv("GLOBAL_DEBUG_MODE", "false"),
        overwrite=True,
    )
    Variable.set(
        "production_global_max_retries",
        os.getenv("GLOBAL_MAX_RETRIES", "5"),
        overwrite=True,
    )
    Variable.set(
        "production_global_timeout", os.getenv("GLOBAL_TIMEOUT", "120"), overwrite=True
    )

    # Set up each flow
    for flow in ["rpa1", "rpa2", "rpa3"]:
        setup_flow_config("production", flow)

    print("✅ Production environment configured from .env files!")


def list_configurations():
    """List all current configurations."""
    print("📋 Current configurations:")
    print("\n🔐 Secrets:")

    # List secrets (this is a simplified version - in practice you'd need to query the backend)
    secret_names = [
        "development-global-api-key",
        "development-global-db-password",
        "development-rpa1-api-key",
        "staging-global-api-key",
        "staging-global-db-password",
        "staging-rpa1-api-key",
        "production-global-api-key",
        "production-global-db-password",
        "production-rpa1-api-key",
    ]

    for secret_name in secret_names:
        try:
            Secret.load(secret_name)
            print(f"  ✅ {secret_name}")
        except ValueError:
            print(f"  ❌ {secret_name} (not found)")

    print("\n📊 Variables:")
    variable_names = [
        "development_global_database_url",
        "development_global_log_level",
        "development_rpa1_batch_size",
        "staging_global_database_url",
        "staging_global_log_level",
        "staging_rpa1_batch_size",
        "production_global_database_url",
        "production_global_log_level",
        "production_rpa1_batch_size",
    ]

    for var_name in variable_names:
        try:
            value = Variable.get(var_name)
            print(f"  ✅ {var_name} = {value}")
        except ValueError:
            print(f"  ❌ {var_name} (not found)")


def main():
    """Main function to handle command line arguments."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/setup_environments.py <command>")
        print("\nCommands:")
        print("  development  - Set up development environment")
        print("  staging      - Set up staging environment")
        print("  production   - Set up production environment")
        print("  list         - List current configurations")
        print("\nExample:")
        print("  python scripts/setup_environments.py development")
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "development":
        setup_development()
    elif command == "staging":
        setup_staging()
    elif command == "production":
        setup_production()
    elif command == "list":
        list_configurations()
    else:
        print(f"❌ Unknown command: {command}")
        print("Available commands: development, staging, production, list")
        sys.exit(1)


if __name__ == "__main__":
    main()
