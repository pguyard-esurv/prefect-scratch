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

import sys
from pathlib import Path

from prefect.blocks.system import Secret
from prefect.variables import Variable


def setup_development():
    """Set up development environment configuration."""
    print("🔧 Setting up development environment...")
    
    # Development secrets
    Secret(value="dev-api-key-123").save("development-global-api-key", overwrite=True)
    Secret(value="dev-db-password").save("development-global-db-password", overwrite=True)
    Secret(value="dev-external-api-token").save("development-global-external-api-token", overwrite=True)
    
    # Development variables
    Variable.set("development_global_database_url", "sqlite:///dev.db", overwrite=True)
    Variable.set("development_global_log_level", "DEBUG", overwrite=True)
    Variable.set("development_global_debug_mode", "true", overwrite=True)
    Variable.set("development_global_max_retries", "1", overwrite=True)
    Variable.set("development_global_timeout", "30", overwrite=True)
    
    # RPA1 development overrides
    Secret(value="dev-rpa1-specific-key").save("development-rpa1-api-key", overwrite=True)
    Variable.set("development_rpa1_batch_size", "100", overwrite=True)
    Variable.set("development_rpa1_timeout", "30", overwrite=True)
    Variable.set("development_rpa1_cleanup_temp_files", "true", overwrite=True)
    Variable.set("development_rpa1_output_format", "json", overwrite=True)
    
    # RPA2 development overrides
    Variable.set("development_rpa2_validation_strict", "false", overwrite=True)
    Variable.set("development_rpa2_max_retries", "1", overwrite=True)
    Variable.set("development_rpa2_timeout", "15", overwrite=True)
    Variable.set("development_rpa2_cleanup_temp_files", "true", overwrite=True)
    
    # RPA3 development overrides
    Variable.set("development_rpa3_max_concurrent_tasks", "5", overwrite=True)
    Variable.set("development_rpa3_timeout", "30", overwrite=True)
    Variable.set("development_rpa3_cleanup_temp_files", "true", overwrite=True)
    
    print("✅ Development environment configured successfully!")


def setup_staging():
    """Set up staging environment configuration."""
    print("🔧 Setting up staging environment...")
    
    # Staging secrets
    Secret(value="staging-api-key-456").save("staging-global-api-key", overwrite=True)
    Secret(value="staging-db-password").save("staging-global-db-password", overwrite=True)
    Secret(value="staging-external-api-token").save("staging-global-external-api-token", overwrite=True)
    
    # Staging variables
    Variable.set("staging_global_database_url", "postgresql://staging:pass@staging-db:5432/rpa", overwrite=True)
    Variable.set("staging_global_log_level", "INFO", overwrite=True)
    Variable.set("staging_global_debug_mode", "false", overwrite=True)
    Variable.set("staging_global_max_retries", "3", overwrite=True)
    Variable.set("staging_global_timeout", "60", overwrite=True)
    
    # RPA1 staging overrides
    Secret(value="staging-rpa1-specific-key").save("staging-rpa1-api-key", overwrite=True)
    Variable.set("staging_rpa1_batch_size", "500", overwrite=True)
    Variable.set("staging_rpa1_timeout", "60", overwrite=True)
    Variable.set("staging_rpa1_cleanup_temp_files", "true", overwrite=True)
    Variable.set("staging_rpa1_output_format", "json", overwrite=True)
    
    # RPA2 staging overrides
    Variable.set("staging_rpa2_validation_strict", "true", overwrite=True)
    Variable.set("staging_rpa2_max_retries", "3", overwrite=True)
    Variable.set("staging_rpa2_timeout", "30", overwrite=True)
    Variable.set("staging_rpa2_cleanup_temp_files", "true", overwrite=True)
    
    # RPA3 staging overrides
    Variable.set("staging_rpa3_max_concurrent_tasks", "8", overwrite=True)
    Variable.set("staging_rpa3_timeout", "60", overwrite=True)
    Variable.set("staging_rpa3_cleanup_temp_files", "true", overwrite=True)
    
    print("✅ Staging environment configured successfully!")


def setup_production():
    """Set up production environment configuration."""
    print("🔧 Setting up production environment...")
    
    # Production secrets
    Secret(value="prod-api-key-789").save("production-global-api-key", overwrite=True)
    Secret(value="prod-db-password").save("production-global-db-password", overwrite=True)
    Secret(value="prod-external-api-token").save("production-global-external-api-token", overwrite=True)
    
    # Production variables
    Variable.set("production_global_database_url", "postgresql://prod:pass@prod-db:5432/rpa", overwrite=True)
    Variable.set("production_global_log_level", "WARNING", overwrite=True)
    Variable.set("production_global_debug_mode", "false", overwrite=True)
    Variable.set("production_global_max_retries", "5", overwrite=True)
    Variable.set("production_global_timeout", "120", overwrite=True)
    
    # RPA1 production overrides
    Secret(value="prod-rpa1-specific-key").save("production-rpa1-api-key", overwrite=True)
    Variable.set("production_rpa1_batch_size", "1000", overwrite=True)
    Variable.set("production_rpa1_timeout", "120", overwrite=True)
    Variable.set("production_rpa1_cleanup_temp_files", "true", overwrite=True)
    Variable.set("production_rpa1_output_format", "json", overwrite=True)
    
    # RPA2 production overrides
    Variable.set("production_rpa2_validation_strict", "true", overwrite=True)
    Variable.set("production_rpa2_max_retries", "5", overwrite=True)
    Variable.set("production_rpa2_timeout", "60", overwrite=True)
    Variable.set("production_rpa2_cleanup_temp_files", "true", overwrite=True)
    
    # RPA3 production overrides
    Variable.set("production_rpa3_max_concurrent_tasks", "15", overwrite=True)
    Variable.set("production_rpa3_timeout", "120", overwrite=True)
    Variable.set("production_rpa3_cleanup_temp_files", "true", overwrite=True)
    
    print("✅ Production environment configured successfully!")


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
            secret = Secret.load(secret_name)
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
