"""
Database configuration validation utilities.

This module provides utilities to validate database configuration settings
and test connectivity before using DatabaseManager in production.
"""

import os
import re
from typing import Any, Optional
from urllib.parse import urlparse

from core.config import ConfigManager


class DatabaseConfigurationError(Exception):
    """Raised when database configuration is invalid."""
    pass


def validate_connection_string(connection_string: str, db_type: str) -> list[str]:
    """
    Validate connection string format for the specified database type.

    Args:
        connection_string: Database connection string to validate
        db_type: Database type ('postgresql' or 'sqlserver')

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    if not connection_string:
        errors.append("Connection string is empty")
        return errors

    try:
        parsed = urlparse(connection_string)
    except Exception as e:
        errors.append(f"Invalid URL format: {e}")
        return errors

    # Validate based on database type
    if db_type == "postgresql":
        if not parsed.scheme or parsed.scheme not in ["postgresql", "postgres"]:
            errors.append(f"PostgreSQL connection string must start with 'postgresql://' or 'postgres://', got '{parsed.scheme}://'")

        if not parsed.hostname:
            errors.append("PostgreSQL connection string missing hostname")

        if not parsed.path or parsed.path == "/":
            errors.append("PostgreSQL connection string missing database name")

        # Check for common PostgreSQL parameters
        if parsed.query:
            valid_params = {
                'sslmode', 'connect_timeout', 'application_name', 'search_path',
                'client_encoding', 'timezone', 'statement_timeout'
            }
            query_params = dict(param.split('=') for param in parsed.query.split('&') if '=' in param)
            invalid_params = set(query_params.keys()) - valid_params
            if invalid_params:
                errors.append(f"Unknown PostgreSQL parameters: {', '.join(invalid_params)}")

    elif db_type == "sqlserver":
        if not parsed.scheme or not parsed.scheme.startswith("mssql"):
            errors.append(f"SQL Server connection string must start with 'mssql+pyodbc://', got '{parsed.scheme}://'")

        if not parsed.hostname:
            errors.append("SQL Server connection string missing hostname")

        if not parsed.path or parsed.path == "/":
            errors.append("SQL Server connection string missing database name")

        # Check for required ODBC driver parameter
        if parsed.query:
            query_params = dict(param.split('=') for param in parsed.query.split('&') if '=' in param)
            if 'driver' not in query_params:
                errors.append("SQL Server connection string missing required 'driver' parameter")
            else:
                driver = query_params['driver'].replace('+', ' ')
                if 'ODBC Driver' not in driver:
                    errors.append(f"Invalid ODBC driver: {driver}")

    else:
        errors.append(f"Unsupported database type: {db_type}")

    return errors


def validate_database_config(database_name: str, config_manager: Optional[ConfigManager] = None) -> dict[str, Any]:
    """
    Validate configuration for a specific database.

    Args:
        database_name: Name of the database to validate
        config_manager: ConfigManager instance (creates new if None)

    Returns:
        Dictionary with validation results:
        {
            'valid': bool,
            'errors': List[str],
            'warnings': List[str],
            'config': Dict[str, Any]
        }
    """
    if config_manager is None:
        config_manager = ConfigManager()

    result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'config': {}
    }

    # Check required configuration
    db_type = config_manager.get_variable(f"{database_name}_type")
    connection_string = config_manager.get_secret(f"{database_name}_connection_string")

    if not db_type:
        result['errors'].append(f"Missing database type for '{database_name}'")
        result['valid'] = False
    else:
        result['config']['type'] = db_type

        # Validate database type
        if db_type not in ['postgresql', 'sqlserver']:
            result['errors'].append(f"Invalid database type '{db_type}' for '{database_name}'. Must be 'postgresql' or 'sqlserver'")
            result['valid'] = False

    if not connection_string:
        result['errors'].append(f"Missing connection string for '{database_name}'")
        result['valid'] = False
    else:
        result['config']['connection_string'] = connection_string

        # Validate connection string format
        if db_type:
            conn_errors = validate_connection_string(connection_string, db_type)
            result['errors'].extend(conn_errors)
            if conn_errors:
                result['valid'] = False

    # Check optional configuration with defaults
    pool_size = config_manager.get_variable(f"{database_name}_pool_size", "5")
    max_overflow = config_manager.get_variable(f"{database_name}_max_overflow", "10")
    timeout = config_manager.get_variable(f"{database_name}_timeout", "30")

    try:
        pool_size_int = int(pool_size)
        if pool_size_int < 1:
            result['errors'].append(f"Pool size must be >= 1, got {pool_size_int}")
            result['valid'] = False
        elif pool_size_int > 50:
            result['warnings'].append(f"Pool size {pool_size_int} is very high, consider reducing")
        result['config']['pool_size'] = pool_size_int
    except ValueError:
        result['errors'].append(f"Invalid pool size '{pool_size}', must be an integer")
        result['valid'] = False

    try:
        max_overflow_int = int(max_overflow)
        if max_overflow_int < 0:
            result['errors'].append(f"Max overflow must be >= 0, got {max_overflow_int}")
            result['valid'] = False
        elif max_overflow_int > 100:
            result['warnings'].append(f"Max overflow {max_overflow_int} is very high, consider reducing")
        result['config']['max_overflow'] = max_overflow_int
    except ValueError:
        result['errors'].append(f"Invalid max overflow '{max_overflow}', must be an integer")
        result['valid'] = False

    try:
        timeout_int = int(timeout)
        if timeout_int < 1:
            result['errors'].append(f"Timeout must be >= 1, got {timeout_int}")
            result['valid'] = False
        elif timeout_int > 300:
            result['warnings'].append(f"Timeout {timeout_int} seconds is very high")
        result['config']['timeout'] = timeout_int
    except ValueError:
        result['errors'].append(f"Invalid timeout '{timeout}', must be an integer")
        result['valid'] = False

    return result


def validate_all_database_configurations(config_manager: Optional[ConfigManager] = None) -> dict[str, dict[str, Any]]:
    """
    Validate configuration for all configured databases.

    Args:
        config_manager: ConfigManager instance (creates new if None)

    Returns:
        Dictionary mapping database names to validation results
    """
    if config_manager is None:
        config_manager = ConfigManager()

    # Discover configured databases by looking for _TYPE environment variables
    environment = config_manager.environment.upper()
    database_names = set()

    for key, _value in os.environ.items():
        if key.startswith(f"{environment}_GLOBAL_") and key.endswith("_TYPE"):
            # Extract database name from environment variable
            # Format: {ENVIRONMENT}_GLOBAL_{DATABASE_NAME}_TYPE
            parts = key.split("_")
            if len(parts) >= 4:
                db_name = "_".join(parts[2:-1]).lower()  # Join middle parts and lowercase
                database_names.add(db_name)

    results = {}
    for db_name in database_names:
        results[db_name] = validate_database_config(db_name, config_manager)

    return results


def test_database_connectivity(database_name: str, config_manager: Optional[ConfigManager] = None) -> dict[str, Any]:
    """
    Test actual database connectivity for a configured database.

    Args:
        database_name: Name of the database to test
        config_manager: ConfigManager instance (creates new if None)

    Returns:
        Dictionary with connectivity test results:
        {
            'connected': bool,
            'error': str or None,
            'response_time_ms': float or None
        }
    """
    import time

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import SQLAlchemyError

    if config_manager is None:
        config_manager = ConfigManager()

    result = {
        'connected': False,
        'error': None,
        'response_time_ms': None
    }

    try:
        # Get connection configuration
        db_type = config_manager.get_variable(f"{database_name}_type")
        connection_string = config_manager.get_secret(f"{database_name}_connection_string")

        if not db_type or not connection_string:
            result['error'] = f"Missing configuration for database '{database_name}'"
            return result

        # Create engine with minimal pool for testing
        engine = create_engine(
            connection_string,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True
        )

        # Test connection with timing
        start_time = time.time()

        with engine.connect() as conn:
            # Execute a simple test query
            if db_type == "postgresql":
                conn.execute(text("SELECT 1"))
            elif db_type == "sqlserver":
                conn.execute(text("SELECT 1"))
            else:
                result['error'] = f"Unsupported database type: {db_type}"
                return result

        end_time = time.time()
        result['response_time_ms'] = (end_time - start_time) * 1000
        result['connected'] = True

        # Clean up
        engine.dispose()

    except SQLAlchemyError as e:
        result['error'] = f"Database connection failed: {str(e)}"
    except Exception as e:
        result['error'] = f"Unexpected error: {str(e)}"

    return result


def generate_configuration_report(config_manager: Optional[ConfigManager] = None) -> str:
    """
    Generate a comprehensive configuration validation report.

    Args:
        config_manager: ConfigManager instance (creates new if None)

    Returns:
        Formatted report string
    """
    if config_manager is None:
        config_manager = ConfigManager()

    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("DATABASE CONFIGURATION VALIDATION REPORT")
    report_lines.append("=" * 60)
    report_lines.append(f"Environment: {config_manager.environment}")
    report_lines.append("")

    # Validate all configurations
    validation_results = validate_all_database_configurations(config_manager)

    if not validation_results:
        report_lines.append("❌ No database configurations found")
        report_lines.append("")
        report_lines.append("Expected environment variables:")
        report_lines.append(f"  {config_manager.environment.upper()}_GLOBAL_{{DATABASE_NAME}}_TYPE")
        report_lines.append(f"  {config_manager.environment.upper()}_GLOBAL_{{DATABASE_NAME}}_CONNECTION_STRING")
        return "\n".join(report_lines)

    overall_valid = True

    for db_name, result in validation_results.items():
        report_lines.append(f"Database: {db_name}")
        report_lines.append("-" * 40)

        if result['valid']:
            report_lines.append("✅ Configuration: VALID")
        else:
            report_lines.append("❌ Configuration: INVALID")
            overall_valid = False

        # Show configuration details
        if result['config']:
            report_lines.append("Configuration:")
            for key, value in result['config'].items():
                if key == 'connection_string':
                    # Mask password in connection string for security
                    masked_value = mask_connection_string_password(value)
                    report_lines.append(f"  {key}: {masked_value}")
                else:
                    report_lines.append(f"  {key}: {value}")

        # Show errors
        if result['errors']:
            report_lines.append("Errors:")
            for error in result['errors']:
                report_lines.append(f"  ❌ {error}")

        # Show warnings
        if result['warnings']:
            report_lines.append("Warnings:")
            for warning in result['warnings']:
                report_lines.append(f"  ⚠️  {warning}")

        # Test connectivity if configuration is valid
        if result['valid']:
            report_lines.append("Testing connectivity...")
            connectivity = test_database_connectivity(db_name, config_manager)
            if connectivity['connected']:
                response_time = connectivity['response_time_ms']
                report_lines.append(f"✅ Connection: SUCCESS ({response_time:.1f}ms)")
            else:
                report_lines.append(f"❌ Connection: FAILED - {connectivity['error']}")
                overall_valid = False

        report_lines.append("")

    # Summary
    report_lines.append("=" * 60)
    if overall_valid:
        report_lines.append("✅ OVERALL STATUS: ALL DATABASES CONFIGURED AND ACCESSIBLE")
    else:
        report_lines.append("❌ OVERALL STATUS: CONFIGURATION OR CONNECTIVITY ISSUES FOUND")
    report_lines.append("=" * 60)

    return "\n".join(report_lines)


def mask_connection_string_password(connection_string: str) -> str:
    """
    Mask password in connection string for secure logging.

    Args:
        connection_string: Database connection string

    Returns:
        Connection string with password masked
    """
    # Pattern to match password in connection string
    password_pattern = r'(:\/\/[^:]+:)([^@]+)(@)'

    def mask_password(match):
        return f"{match.group(1)}{'*' * len(match.group(2))}{match.group(3)}"

    return re.sub(password_pattern, mask_password, connection_string)


def main():
    """Command-line interface for configuration validation."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate database configuration")
    parser.add_argument(
        "--database",
        help="Specific database to validate (validates all if not specified)"
    )
    parser.add_argument(
        "--environment",
        help="Environment to use (overrides PREFECT_ENVIRONMENT)"
    )
    parser.add_argument(
        "--test-connectivity",
        action="store_true",
        help="Test actual database connectivity"
    )

    args = parser.parse_args()

    # Set environment if specified
    if args.environment:
        os.environ['PREFECT_ENVIRONMENT'] = args.environment

    config_manager = ConfigManager()

    if args.database:
        # Validate specific database
        print(f"Validating database: {args.database}")
        print("=" * 50)

        result = validate_database_config(args.database, config_manager)

        if result['valid']:
            print("✅ Configuration: VALID")
        else:
            print("❌ Configuration: INVALID")

        if result['errors']:
            print("\nErrors:")
            for error in result['errors']:
                print(f"  ❌ {error}")

        if result['warnings']:
            print("\nWarnings:")
            for warning in result['warnings']:
                print(f"  ⚠️  {warning}")

        if args.test_connectivity and result['valid']:
            print("\nTesting connectivity...")
            connectivity = test_database_connectivity(args.database, config_manager)
            if connectivity['connected']:
                response_time = connectivity['response_time_ms']
                print(f"✅ Connection: SUCCESS ({response_time:.1f}ms)")
            else:
                print(f"❌ Connection: FAILED - {connectivity['error']}")

    else:
        # Generate full report
        report = generate_configuration_report(config_manager)
        print(report)


if __name__ == "__main__":
    main()
