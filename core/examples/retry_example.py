#!/usr/bin/env python3
"""
Example demonstrating DatabaseManager retry functionality.

This example shows how to use the retry-enabled methods for resilient
database operations that can handle transient failures automatically.
"""

from core.database import DatabaseManager


def demonstrate_retry_functionality():
    """Demonstrate various retry-enabled database operations."""

    print("=== DatabaseManager Retry Functionality Demo ===\n")

    # Example 1: Basic query with retry
    print("1. Execute query with retry (handles connection issues)")
    try:
        with DatabaseManager("rpa_db") as db:
            # This will retry automatically on transient failures
            results = db.execute_query_with_retry(
                "SELECT COUNT(*) as total FROM processed_surveys",
                max_attempts=3,
                min_wait=1.0,
                max_wait=5.0,
            )
            print(f"   Query results: {results}")
    except Exception as e:
        print(f"   Query failed after retries: {e}")

    print()

    # Example 2: Query with timeout and retry
    print("2. Execute query with timeout and retry")
    try:
        with DatabaseManager("rpa_db") as db:
            # Combines timeout control with retry logic
            results = db.execute_query_with_timeout_and_retry(
                "SELECT * FROM processed_surveys LIMIT 5",
                timeout=30,
                max_attempts=2,
                min_wait=0.5,
                max_wait=3.0,
            )
            print(f"   Query results count: {len(results)}")
    except Exception as e:
        print(f"   Query with timeout failed: {e}")

    print()

    # Example 3: Transaction with retry
    print("3. Execute transaction with retry")
    try:
        with DatabaseManager("rpa_db") as db:
            queries = [
                (
                    "INSERT INTO processed_surveys (survey_id, status) VALUES (:id, :status)",
                    {"id": "test_001", "status": "processed"},
                ),
                (
                    "UPDATE processed_surveys SET processed_at = NOW() WHERE survey_id = :id",
                    {"id": "test_001"},
                ),
            ]

            results = db.execute_transaction_with_retry(
                queries, max_attempts=2, min_wait=1.0, max_wait=8.0
            )
            print(f"   Transaction completed, results: {len(results)} operations")
    except Exception as e:
        print(f"   Transaction failed: {e}")

    print()

    # Example 4: Health check with retry
    print("4. Health check with retry")
    try:
        with DatabaseManager("rpa_db") as db:
            health_status = db.health_check_with_retry(
                max_attempts=2, min_wait=0.5, max_wait=3.0
            )
            print(f"   Health status: {health_status['status']}")
            print(f"   Connection: {health_status['connection']}")
            print(f"   Response time: {health_status.get('response_time_ms', 'N/A')}ms")
    except Exception as e:
        print(f"   Health check failed: {e}")

    print()

    # Example 5: Migration with retry
    print("5. Run migrations with retry")
    try:
        with DatabaseManager("rpa_db") as db:
            db.run_migrations_with_retry(max_attempts=2, min_wait=2.0, max_wait=10.0)
            print("   Migrations completed successfully")
    except Exception as e:
        print(f"   Migration failed: {e}")

    print()

    # Example 6: Demonstrating error classification
    print("6. Error classification examples")
    from sqlalchemy.exc import DisconnectionError, OperationalError

    from core.database import _is_transient_error

    # Transient errors (will trigger retry)
    transient_errors = [
        DisconnectionError("Connection lost", None, None),
        OperationalError("Connection timeout", None, None),
        Exception("connection refused"),
        Exception("network error occurred"),
    ]

    # Non-transient errors (will not trigger retry)
    permanent_errors = [
        ValueError("Invalid SQL syntax"),
        Exception("Permission denied"),
        Exception("Table does not exist"),
    ]

    print("   Transient errors (will retry):")
    for error in transient_errors:
        is_transient = _is_transient_error(error)
        print(f"     {type(error).__name__}: {error} -> {is_transient}")

    print("   Permanent errors (will not retry):")
    for error in permanent_errors:
        is_transient = _is_transient_error(error)
        print(f"     {type(error).__name__}: {error} -> {is_transient}")


def demonstrate_custom_retry_configuration():
    """Show how to customize retry behavior for different scenarios."""

    print("\n=== Custom Retry Configuration Examples ===\n")

    # Conservative retry for critical operations
    print("1. Conservative retry (few attempts, longer waits)")
    try:
        with DatabaseManager("rpa_db") as db:
            results = db.execute_query_with_retry(
                "SELECT 1 as test",
                max_attempts=2,  # Only 2 attempts
                min_wait=3.0,  # Wait at least 3 seconds
                max_wait=15.0,  # Up to 15 seconds between retries
            )
            print(f"   Conservative retry result: {results}")
    except Exception as e:
        print(f"   Conservative retry failed: {e}")

    print()

    # Aggressive retry for non-critical operations
    print("2. Aggressive retry (many attempts, short waits)")
    try:
        with DatabaseManager("rpa_db") as db:
            results = db.execute_query_with_retry(
                "SELECT 1 as test",
                max_attempts=5,  # More attempts
                min_wait=0.1,  # Very short initial wait
                max_wait=2.0,  # Short maximum wait
            )
            print(f"   Aggressive retry result: {results}")
    except Exception as e:
        print(f"   Aggressive retry failed: {e}")

    print()

    # Health check optimized retry
    print("3. Health check optimized retry")
    try:
        with DatabaseManager("rpa_db") as db:
            health_status = db.health_check_with_retry(
                max_attempts=2,  # Quick failure detection
                min_wait=0.2,  # Very fast retry
                max_wait=1.0,  # Don't wait too long for health checks
            )
            print(f"   Health check result: {health_status['status']}")
    except Exception as e:
        print(f"   Health check retry failed: {e}")


if __name__ == "__main__":
    print("DatabaseManager Retry Logic Examples")
    print("=" * 50)
    print()
    print("Note: These examples require a configured database.")
    print("Make sure your environment configuration is set up properly.")
    print()

    try:
        demonstrate_retry_functionality()
        demonstrate_custom_retry_configuration()

        print("\n=== Demo Complete ===")
        print("The retry functionality provides:")
        print("- Automatic retry on transient database errors")
        print("- Configurable retry attempts and backoff timing")
        print("- Smart error classification to avoid retrying permanent errors")
        print("- Exponential backoff to reduce load during outages")
        print("- Comprehensive logging for troubleshooting")

    except Exception as e:
        print(f"\nDemo failed with error: {e}")
        print("This is expected if database configuration is not set up.")
