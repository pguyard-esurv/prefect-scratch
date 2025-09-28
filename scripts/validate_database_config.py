#!/usr/bin/env python3
"""
Database Configuration Validation Script

This script provides comprehensive validation and troubleshooting for database
configuration in the RPA system. It checks configuration files, validates
connection strings, tests connectivity, and provides detailed reports.

Usage:
    python scripts/validate_database_config.py                    # Full report
    python scripts/validate_database_config.py --database rpa_db  # Specific database
    python scripts/validate_database_config.py --fix-common       # Attempt fixes
    python scripts/validate_database_config.py --environment staging  # Environment
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import after path setup to avoid import errors
from core.config import ConfigManager  # noqa: E402
from core.database_config_validator import (  # noqa: E402
    generate_configuration_report,
    test_database_connectivity,
    validate_all_database_configurations,
    validate_database_config,
)


def check_environment_setup():
    """Check basic environment setup and requirements."""
    print("🔍 Checking Environment Setup")
    print("=" * 50)

    issues = []

    # Check Python version
    python_version = sys.version_info
    if python_version < (3, 8):
        issues.append(
            f"❌ Python version {python_version.major}.{python_version.minor} "
            f"is too old. Requires Python 3.8+")
    else:
        print(f"✅ Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")  # noqa: E501

    # Check required packages
    required_packages = [
        ('sqlalchemy', 'SQLAlchemy'),
        ('psycopg2', 'PostgreSQL driver'),
        ('pyodbc', 'SQL Server driver'),
        ('pyway', 'Migration tool'),
        ('tenacity', 'Retry logic'),
        ('dotenv', 'Environment file support')
    ]

    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✅ {description}: Available")
        except ImportError:
            issues.append(f"❌ {description}: Missing package '{package}'")

    # Check environment variable
    prefect_env = os.getenv('PREFECT_ENVIRONMENT')
    if prefect_env:
        print(f"✅ PREFECT_ENVIRONMENT: {prefect_env}")
    else:
        issues.append("⚠️  PREFECT_ENVIRONMENT not set, using default 'development'")

    # Check .env files
    config_manager = ConfigManager()
    env_file = project_root / "core" / "envs" / f".env.{config_manager.environment}"
    if env_file.exists():
        print(f"✅ Environment file: {env_file}")
    else:
        issues.append(f"❌ Environment file missing: {env_file}")

    if issues:
        print("\n🚨 Issues Found:")
        for issue in issues:
            print(f"  {issue}")
        return False
    else:
        print("\n✅ Environment setup looks good!")
        return True


def check_odbc_drivers():
    """Check available ODBC drivers for SQL Server."""
    print("\n🔍 Checking ODBC Drivers")
    print("=" * 50)

    try:
        import pyodbc
        drivers = pyodbc.drivers()

        sql_server_drivers = [d for d in drivers if 'SQL Server' in d]

        if sql_server_drivers:
            print("✅ SQL Server ODBC drivers found:")
            for driver in sql_server_drivers:
                print(f"  - {driver}")
        else:
            print("❌ No SQL Server ODBC drivers found")
            print("   Install ODBC Driver 17 or 18 for SQL Server")
            print("   https://docs.microsoft.com/en-us/sql/connect/odbc/"
                  "download-odbc-driver-for-sql-server")

        return len(sql_server_drivers) > 0

    except ImportError:
        print("❌ pyodbc not available - cannot check ODBC drivers")
        return False
    except Exception as e:
        print(f"❌ Error checking ODBC drivers: {e}")
        return False


def suggest_fixes(validation_results):
    """Suggest fixes for common configuration issues."""
    print("\n🔧 Suggested Fixes")
    print("=" * 50)

    fixes_suggested = False

    for db_name, result in validation_results.items():
        if not result['valid']:
            print(f"\nDatabase: {db_name}")
            print("-" * 30)

            for error in result['errors']:
                fixes_suggested = True

                if "Missing database type" in error:
                    env = ConfigManager().environment.upper()
                    print(f"💡 Add to core/envs/.env.{ConfigManager().environment}:")
                    print(f"   {env}_GLOBAL_{db_name.upper()}_TYPE=postgresql")
                    print("   # or")
                    print(f"   {env}_GLOBAL_{db_name.upper()}_TYPE=sqlserver")

                elif "Missing connection string" in error:
                    env = ConfigManager().environment.upper()
                    print(f"💡 Add to core/envs/.env.{ConfigManager().environment}:")
                    print(f"   {env}_GLOBAL_{db_name.upper()}_CONNECTION_STRING="
                          "postgresql://user:pass@host:5432/db")
                    print("   # or")
                    print(f"   {env}_GLOBAL_{db_name.upper()}_CONNECTION_STRING="
                          "mssql+pyodbc://user:pass@host:1433/db?"
                          "driver=ODBC+Driver+17+for+SQL+Server")

                elif "must start with 'postgresql://'" in error:
                    print("💡 Fix PostgreSQL connection string format:")
                    print("   Correct: postgresql://username:password@hostname:5432/database")
                    print("   With SSL: postgresql://username:password@hostname:5432/"
                          "database?sslmode=require")

                elif "must start with 'mssql+pyodbc://'" in error:
                    print("💡 Fix SQL Server connection string format:")
                    print("   Correct: mssql+pyodbc://username:password@hostname:1433/"
                          "database?driver=ODBC+Driver+17+for+SQL+Server")

                elif "missing required 'driver' parameter" in error:
                    print("💡 Add ODBC driver parameter to SQL Server connection string:")
                    print("   Add: ?driver=ODBC+Driver+17+for+SQL+Server")
                    print("   Or:  ?driver=ODBC+Driver+18+for+SQL+Server")

                elif "Pool size must be" in error:
                    env = ConfigManager().environment.upper()
                    print(f"💡 Fix pool size in core/envs/.env.{ConfigManager().environment}:")
                    print(f"   {env}_GLOBAL_{db_name.upper()}_POOL_SIZE=5")

                elif "Invalid database type" in error:
                    print("💡 Use supported database type:")
                    print("   Supported: postgresql, sqlserver")

    if not fixes_suggested:
        print("✅ No common issues found that can be automatically fixed")


def create_example_config():
    """Create example configuration files."""
    print("\n📝 Creating Example Configuration")
    print("=" * 50)

    config_manager = ConfigManager()
    env_file = project_root / "core" / "envs" / f".env.{config_manager.environment}"
    example_file = project_root / "core" / "envs" / f".env.{config_manager.environment}.example"  # noqa: E501

    env_upper = config_manager.environment.upper()
    env_title = config_manager.environment.title()

    example_content = f"""# Example Database Configuration for {env_title} Environment
# Copy this file to .env.{config_manager.environment} and update with your actual values

# RPA Database (PostgreSQL)
{env_upper}_GLOBAL_RPA_DB_TYPE=postgresql
{env_upper}_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://rpa_user:your_password@localhost:5432/rpa_{config_manager.environment}
{env_upper}_GLOBAL_RPA_DB_POOL_SIZE=5
{env_upper}_GLOBAL_RPA_DB_MAX_OVERFLOW=10
{env_upper}_GLOBAL_RPA_DB_TIMEOUT=30

# SurveyHub Database (SQL Server - Read Only)
{env_upper}_GLOBAL_SURVEYHUB_TYPE=sqlserver
{env_upper}_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://survey_user:your_password@localhost:1433/SurveyHub_{env_title}?driver=ODBC+Driver+17+for+SQL+Server
{env_upper}_GLOBAL_SURVEYHUB_POOL_SIZE=3
{env_upper}_GLOBAL_SURVEYHUB_MAX_OVERFLOW=5
{env_upper}_GLOBAL_SURVEYHUB_TIMEOUT=30

# Global Database Settings
{env_upper}_GLOBAL_DATABASE_RETRY_ATTEMPTS=3
{env_upper}_GLOBAL_DATABASE_RETRY_MIN_WAIT=1
{env_upper}_GLOBAL_DATABASE_RETRY_MAX_WAIT=10
"""

    try:
        with open(example_file, 'w') as f:
            f.write(example_content)
        print(f"✅ Created example configuration: {example_file}")

        if not env_file.exists():
            print("💡 Copy example to active config:")
            print(f"   cp {example_file} {env_file}")

    except Exception as e:
        print(f"❌ Failed to create example configuration: {e}")


def main():
    """Main validation script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate and troubleshoot database configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_database_config.py                    # Full validation report
  python scripts/validate_database_config.py --database rpa_db  # Validate specific database
  python scripts/validate_database_config.py --environment staging  # Use staging environment
  python scripts/validate_database_config.py --check-setup      # Check basic setup only
  python scripts/validate_database_config.py --create-example   # Create example config files
        """
    )

    parser.add_argument(
        "--database",
        help="Specific database to validate"
    )
    parser.add_argument(
        "--environment",
        help="Environment to use (overrides PREFECT_ENVIRONMENT)"
    )
    parser.add_argument(
        "--check-setup",
        action="store_true",
        help="Check basic environment setup only"
    )
    parser.add_argument(
        "--create-example",
        action="store_true",
        help="Create example configuration files"
    )
    parser.add_argument(
        "--suggest-fixes",
        action="store_true",
        help="Suggest fixes for configuration issues"
    )
    parser.add_argument(
        "--no-connectivity",
        action="store_true",
        help="Skip connectivity testing"
    )

    args = parser.parse_args()

    # Set environment if specified
    if args.environment:
        os.environ['PREFECT_ENVIRONMENT'] = args.environment

    print("🔧 Database Configuration Validator")
    print("=" * 60)

    # Check basic setup
    setup_ok = check_environment_setup()

    if args.check_setup:
        check_odbc_drivers()
        return 0 if setup_ok else 1

    if args.create_example:
        create_example_config()
        return 0

    if not setup_ok:
        print("\n❌ Basic setup issues found. "
              "Fix these first before validating database configuration.")
        return 1

    # Check ODBC drivers
    check_odbc_drivers()

    try:
        if args.database:
            # Validate specific database
            print(f"\n🔍 Validating Database: {args.database}")
            print("=" * 60)

            config_manager = ConfigManager()
            result = validate_database_config(args.database, config_manager)

            if result['valid']:
                print("✅ Configuration: VALID")

                if not args.no_connectivity:
                    print("\n🔌 Testing Connectivity...")
                    connectivity = test_database_connectivity(args.database, config_manager)
                    if connectivity['connected']:
                        response_time = connectivity['response_time_ms']
                        print(f"✅ Connection: SUCCESS ({response_time:.1f}ms)")
                    else:
                        print("❌ Connection: FAILED")
                        print(f"   Error: {connectivity['error']}")
                        return 1
            else:
                print("❌ Configuration: INVALID")
                print("\nErrors:")
                for error in result['errors']:
                    print(f"  ❌ {error}")

                if args.suggest_fixes:
                    suggest_fixes({args.database: result})

                return 1

            if result['warnings']:
                print("\nWarnings:")
                for warning in result['warnings']:
                    print(f"  ⚠️  {warning}")

        else:
            # Generate full report
            print("\n📊 Full Configuration Report")
            print("=" * 60)

            report = generate_configuration_report()
            print(report)

            # Check if there are any issues
            validation_results = validate_all_database_configurations()
            has_issues = any(
                not result['valid'] for result in validation_results.values()
            )

            if has_issues and args.suggest_fixes:
                suggest_fixes(validation_results)

            return 1 if has_issues else 0

    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
