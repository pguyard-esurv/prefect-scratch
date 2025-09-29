#!/usr/bin/env python3
"""
Integration test script for error recovery mechanisms.

This script demonstrates the error recovery functionality including:
- Database error handling with retry logic
- Local operation queuing during network partitions
- Disk space monitoring and cleanup
- Alerting integration
- Container restart handling
"""

import logging
import os
import sys
import tempfile
import time
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.error_recovery import (
    AlertManager,
    ErrorRecoveryManager,
    ErrorSeverity,
    log_alert_handler,
)


def setup_logging():
    """Setup logging for the integration test."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    return logging.getLogger(__name__)


def test_database_error_recovery(
    recovery_manager: ErrorRecoveryManager, logger: logging.Logger
):
    """Test database error recovery mechanisms."""
    logger.info("Testing database error recovery...")

    # Simulate transient database error
    from sqlalchemy.exc import OperationalError

    transient_error = OperationalError("connection timeout", None, None)

    result = recovery_manager.handle_database_error(
        error=transient_error,
        database_name="rpa_db",
        operation="database_insert",
        context={"record_id": 123, "data": "test_data"},
    )

    logger.info(
        f"Transient error recovery result: {result.action_taken.value} - {result.message}"
    )

    # Simulate non-transient database error
    non_transient_error = ValueError("Invalid SQL syntax")

    result = recovery_manager.handle_database_error(
        error=non_transient_error,
        database_name="rpa_db",
        operation="database_update",
        context={"record_id": 456, "data": "test_update"},
    )

    logger.info(
        f"Non-transient error recovery result: {result.action_taken.value} - {result.message}"
    )

    return True


def test_local_queue_operations(
    recovery_manager: ErrorRecoveryManager, logger: logging.Logger
):
    """Test local operation queuing functionality."""
    logger.info("Testing local operation queuing...")

    # Add some operations to the local queue
    operations = [
        {"operation": "database_insert", "context": {"id": 1, "data": "test1"}},
        {"operation": "database_update", "context": {"id": 2, "data": "test2"}},
        {"operation": "log_entry", "context": {"message": "test log entry"}},
    ]

    for op in operations:
        success = recovery_manager.local_queue.enqueue_operation(op)
        logger.info(
            f"Queued operation {op['operation']}: {'success' if success else 'failed'}"
        )

    # Process queued operations
    result = recovery_manager.process_queued_operations()

    logger.info(
        f"Processed {result['operations_processed']} operations: "
        f"{result['operations_successful']} successful, "
        f"{result['operations_failed']} failed"
    )

    return True


def test_disk_space_monitoring(
    recovery_manager: ErrorRecoveryManager, logger: logging.Logger
):
    """Test disk space monitoring and cleanup."""
    logger.info("Testing disk space monitoring...")

    # Monitor disk space
    result = recovery_manager.monitor_and_cleanup_disk_space()

    logger.info(f"Disk monitoring result: {result['disk_status']['overall_status']}")

    if result["cleanup_performed"]:
        logger.info("Disk cleanup was performed")
    else:
        logger.info("No disk cleanup needed")

    # Log disk status for each monitored path
    for path, status in result["disk_status"]["paths"].items():
        if "error" not in status:
            logger.info(
                f"Path {path}: {status['used_percent']:.1f}% used "
                f"({status['used_gb']:.1f}GB / {status['total_gb']:.1f}GB)"
            )
        else:
            logger.warning(f"Path {path}: Error - {status['error']}")

    return True


def test_alerting_system(
    recovery_manager: ErrorRecoveryManager, logger: logging.Logger
):
    """Test alerting system functionality."""
    logger.info("Testing alerting system...")

    # Send alerts of different severities
    alert_tests = [
        (
            ErrorSeverity.LOW,
            "Test Low Severity Alert",
            "This is a low severity test alert",
        ),
        (
            ErrorSeverity.MEDIUM,
            "Test Medium Severity Alert",
            "This is a medium severity test alert",
        ),
        (
            ErrorSeverity.HIGH,
            "Test High Severity Alert",
            "This is a high severity test alert",
        ),
        (
            ErrorSeverity.CRITICAL,
            "Test Critical Alert",
            "This is a critical test alert",
        ),
    ]

    for severity, title, message in alert_tests:
        success = recovery_manager.alert_manager.send_alert(
            severity=severity,
            title=title,
            message=message,
            metadata={"test": True, "component": "integration_test"},
        )

        logger.info(
            f"Sent {severity.value} alert: {'success' if success else 'failed'}"
        )

    # Get alert history
    history = recovery_manager.alert_manager.get_alert_history(limit=10)
    logger.info(f"Alert history contains {len(history)} recent alerts")

    return True


def test_container_restart_handling(
    recovery_manager: ErrorRecoveryManager, logger: logging.Logger
):
    """Test container restart handling."""
    logger.info("Testing container restart handling...")

    # Simulate container restart
    result = recovery_manager.handle_container_restart(
        "Integration test restart simulation"
    )

    logger.info(
        f"Container restart handling: {result.action_taken.value} - {result.message}"
    )

    return True


def test_recovery_status_monitoring(
    recovery_manager: ErrorRecoveryManager, logger: logging.Logger
):
    """Test recovery status monitoring."""
    logger.info("Testing recovery status monitoring...")

    # Get recovery status
    status = recovery_manager.get_recovery_status()

    logger.info("Recovery System Status:")
    logger.info(f"  Total errors: {status['recovery_stats']['total_errors']}")
    logger.info(
        f"  Successful recoveries: {status['recovery_stats']['successful_recoveries']}"
    )
    logger.info(f"  Failed recoveries: {status['recovery_stats']['failed_recoveries']}")
    logger.info(f"  Local queue size: {status['local_queue']['size']}")
    logger.info(f"  Database managers: {status['database_managers']}")

    return True


def main():
    """Main integration test function."""
    logger = setup_logging()
    logger.info("Starting Error Recovery Integration Test")

    # Create temporary directory for test files
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Setup alert manager with handlers
            alert_manager = AlertManager()
            alert_manager.add_alert_handler(log_alert_handler)

            # Add file alert handler with temp directory
            alert_file = os.path.join(temp_dir, "test_alerts.json")

            def temp_file_alert_handler(alert_data):
                """Temporary file alert handler for testing."""
                import json

                os.makedirs(os.path.dirname(alert_file), exist_ok=True)
                with open(alert_file, "a") as f:
                    f.write(json.dumps(alert_data) + "\n")

            alert_manager.add_alert_handler(temp_file_alert_handler)

            # Initialize error recovery manager
            recovery_manager = ErrorRecoveryManager(
                database_managers={},  # No real database managers for this test
                local_queue_path=os.path.join(temp_dir, "test_queue.json"),
                disk_monitor_paths=[temp_dir, "/tmp"],
                alert_manager=alert_manager,
            )

            logger.info("Error recovery manager initialized")

            # Run integration tests
            tests = [
                ("Database Error Recovery", test_database_error_recovery),
                ("Local Queue Operations", test_local_queue_operations),
                ("Disk Space Monitoring", test_disk_space_monitoring),
                ("Alerting System", test_alerting_system),
                ("Container Restart Handling", test_container_restart_handling),
                ("Recovery Status Monitoring", test_recovery_status_monitoring),
            ]

            passed_tests = 0
            total_tests = len(tests)

            for test_name, test_func in tests:
                try:
                    logger.info(f"\n--- Running Test: {test_name} ---")

                    success = test_func(recovery_manager, logger)

                    if success:
                        logger.info(f"✓ {test_name} PASSED")
                        passed_tests += 1
                    else:
                        logger.error(f"✗ {test_name} FAILED")

                except Exception as e:
                    logger.error(f"✗ {test_name} FAILED with exception: {e}")

                # Small delay between tests
                time.sleep(0.5)

            # Final summary
            logger.info("\n--- Integration Test Summary ---")
            logger.info(f"Tests passed: {passed_tests}/{total_tests}")

            if passed_tests == total_tests:
                logger.info("🎉 All integration tests PASSED!")

                # Check if alert file was created
                if os.path.exists(alert_file):
                    with open(alert_file) as f:
                        alert_count = len(f.readlines())
                    logger.info(
                        f"📝 Generated {alert_count} test alerts in {alert_file}"
                    )

                return 0
            else:
                logger.error(
                    f"❌ {total_tests - passed_tests} integration tests FAILED!"
                )
                return 1

        except Exception as e:
            logger.error(f"Integration test setup failed: {e}")
            return 1


if __name__ == "__main__":
    sys.exit(main())
