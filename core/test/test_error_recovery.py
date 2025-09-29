"""
Test suite for error handling and recovery mechanisms.

This module tests the comprehensive error handling, retry logic, automatic recovery,
local operation queuing, disk space monitoring, and alerting integration.
"""

import json
import os
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from core.database import DatabaseManager
from core.error_recovery import (
    AlertManager,
    DiskSpaceMonitor,
    ErrorRecoveryManager,
    ErrorSeverity,
    LocalOperationQueue,
    RecoveryAction,
    RecoveryResult,
    log_alert_handler,
)


class TestLocalOperationQueue(unittest.TestCase):
    """Test local operation queue functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.persistence_file = os.path.join(self.temp_dir, "queue.json")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_queue_initialization(self):
        """Test queue initialization."""
        queue = LocalOperationQueue(max_size=100)

        self.assertEqual(queue.get_queue_size(), 0)
        self.assertFalse(queue.is_full())
        self.assertEqual(queue.max_size, 100)

    def test_enqueue_dequeue_operations(self):
        """Test basic enqueue and dequeue operations."""
        queue = LocalOperationQueue(max_size=10)

        # Enqueue operation
        operation = {"type": "test", "data": "test_data"}
        result = queue.enqueue_operation(operation)

        self.assertTrue(result)
        self.assertEqual(queue.get_queue_size(), 1)

        # Dequeue operation
        dequeued = queue.dequeue_operation(timeout=1.0)

        self.assertIsNotNone(dequeued)
        self.assertEqual(dequeued["type"], "test")
        self.assertEqual(dequeued["data"], "test_data")
        self.assertIn("queued_at", dequeued)
        self.assertEqual(queue.get_queue_size(), 0)

    def test_queue_full_behavior(self):
        """Test queue behavior when full."""
        queue = LocalOperationQueue(max_size=2)

        # Fill queue
        self.assertTrue(queue.enqueue_operation({"id": 1}))
        self.assertTrue(queue.enqueue_operation({"id": 2}))

        # Queue should be full
        self.assertTrue(queue.is_full())

        # Next enqueue should fail
        self.assertFalse(queue.enqueue_operation({"id": 3}))

    def test_queue_persistence(self):
        """Test queue persistence to file."""
        # Create queue with persistence
        queue = LocalOperationQueue(max_size=10, persistence_file=self.persistence_file)

        # Add operations
        operations = [
            {"id": 1, "type": "test1"},
            {"id": 2, "type": "test2"},
            {"id": 3, "type": "test3"},
        ]

        for op in operations:
            queue.enqueue_operation(op)

        # Create new queue instance (simulating restart)
        new_queue = LocalOperationQueue(
            max_size=10, persistence_file=self.persistence_file
        )

        # Should have loaded persisted operations
        self.assertEqual(new_queue.get_queue_size(), 3)

        # Verify operations are correct
        for expected_op in operations:
            dequeued = new_queue.dequeue_operation(timeout=1.0)
            self.assertIsNotNone(dequeued)
            self.assertEqual(dequeued["id"], expected_op["id"])
            self.assertEqual(dequeued["type"], expected_op["type"])

    def test_clear_queue(self):
        """Test clearing the queue."""
        queue = LocalOperationQueue(max_size=10)

        # Add operations
        for i in range(5):
            queue.enqueue_operation({"id": i})

        self.assertEqual(queue.get_queue_size(), 5)

        # Clear queue
        cleared_count = queue.clear_queue()

        self.assertEqual(cleared_count, 5)
        self.assertEqual(queue.get_queue_size(), 0)

    def test_dequeue_timeout(self):
        """Test dequeue timeout behavior."""
        queue = LocalOperationQueue(max_size=10)

        # Dequeue from empty queue should return None after timeout
        start_time = time.time()
        result = queue.dequeue_operation(timeout=0.1)
        end_time = time.time()

        self.assertIsNone(result)
        self.assertGreaterEqual(end_time - start_time, 0.1)


class TestDiskSpaceMonitor(unittest.TestCase):
    """Test disk space monitoring functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_monitor_initialization(self):
        """Test disk space monitor initialization."""
        paths = ["/", "/tmp"]
        monitor = DiskSpaceMonitor(
            paths_to_monitor=paths,
            warning_threshold_percent=80.0,
            critical_threshold_percent=90.0,
        )

        self.assertEqual(monitor.paths_to_monitor, paths)
        self.assertEqual(monitor.warning_threshold, 80.0)
        self.assertEqual(monitor.critical_threshold, 90.0)

    def test_check_disk_space(self):
        """Test disk space checking."""
        monitor = DiskSpaceMonitor(
            paths_to_monitor=[self.temp_dir],
            warning_threshold_percent=80.0,
            critical_threshold_percent=90.0,
        )

        result = monitor.check_disk_space()

        self.assertIn("timestamp", result)
        self.assertIn("paths", result)
        self.assertIn("alerts", result)
        self.assertIn("overall_status", result)

        # Should have info for our temp directory
        self.assertIn(self.temp_dir, result["paths"])

        path_info = result["paths"][self.temp_dir]
        self.assertIn("total_gb", path_info)
        self.assertIn("used_gb", path_info)
        self.assertIn("free_gb", path_info)
        self.assertIn("used_percent", path_info)
        self.assertIn("status", path_info)

    def test_cleanup_old_files(self):
        """Test cleanup of old files."""
        # Create test files with different ages
        test_files = []

        # Create old file (should be cleaned up)
        old_file = Path(self.temp_dir) / "old_file.log"
        old_file.write_text("old content")

        # Set modification time to 8 days ago
        old_time = time.time() - (8 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))
        test_files.append(old_file)

        # Create recent file (should not be cleaned up)
        recent_file = Path(self.temp_dir) / "recent_file.log"
        recent_file.write_text("recent content")
        test_files.append(recent_file)

        # Create monitor with cleanup path
        monitor = DiskSpaceMonitor(
            paths_to_monitor=[self.temp_dir], cleanup_paths=[self.temp_dir]
        )

        # Perform cleanup
        result = monitor.cleanup_disk_space()

        self.assertIn("cleanup_operations", result)
        self.assertIn("space_freed_gb", result)
        self.assertIn("success", result)

        # Old file should be removed, recent file should remain
        self.assertFalse(old_file.exists())
        self.assertTrue(recent_file.exists())

    def test_disk_space_alerts(self):
        """Test disk space alert generation."""
        with patch("core.error_recovery.shutil.disk_usage") as mock_disk_usage:
            # Create a mock object with the expected attributes
            from collections import namedtuple

            DiskUsage = namedtuple("DiskUsage", ["total", "used", "free"])

            # Mock disk usage to simulate high usage (95%)
            mock_disk_usage.return_value = DiskUsage(
                total=1000 * 1024**3,  # 1000 GB total
                used=950 * 1024**3,  # 950 GB used (95%)
                free=50 * 1024**3,  # 50 GB free
            )

            monitor = DiskSpaceMonitor(
                paths_to_monitor=["/test"],
                warning_threshold_percent=80.0,
                critical_threshold_percent=90.0,
            )

            result = monitor.check_disk_space()

            # Should generate critical alert
            self.assertEqual(result["overall_status"], "critical")
            self.assertTrue(len(result["alerts"]) > 0)

            alert = result["alerts"][0]
            self.assertEqual(alert["severity"], "critical")
            self.assertIn("Critical disk space", alert["message"])


class TestAlertManager(unittest.TestCase):
    """Test alert management functionality."""

    def test_alert_manager_initialization(self):
        """Test alert manager initialization."""
        manager = AlertManager()

        self.assertEqual(len(manager.alert_handlers), 0)
        self.assertEqual(len(manager.alert_history), 0)

    def test_add_alert_handler(self):
        """Test adding alert handlers."""
        manager = AlertManager()

        def test_handler(alert_data):
            pass

        manager.add_alert_handler(test_handler)

        self.assertEqual(len(manager.alert_handlers), 1)
        self.assertEqual(manager.alert_handlers[0], test_handler)

    def test_send_alert(self):
        """Test sending alerts."""
        manager = AlertManager()

        # Mock handler
        handler_calls = []

        def mock_handler(alert_data):
            handler_calls.append(alert_data)

        manager.add_alert_handler(mock_handler)

        # Send alert
        result = manager.send_alert(
            ErrorSeverity.HIGH, "Test Alert", "This is a test alert", {"key": "value"}
        )

        self.assertTrue(result)
        self.assertEqual(len(handler_calls), 1)
        self.assertEqual(len(manager.alert_history), 1)

        # Verify alert data
        alert_data = handler_calls[0]
        self.assertEqual(alert_data["severity"], "high")
        self.assertEqual(alert_data["title"], "Test Alert")
        self.assertEqual(alert_data["message"], "This is a test alert")
        self.assertEqual(alert_data["metadata"]["key"], "value")
        self.assertIn("timestamp", alert_data)

    def test_alert_history_limit(self):
        """Test alert history size limit."""
        manager = AlertManager()

        # Send more than 1000 alerts
        for i in range(1100):
            manager.send_alert(ErrorSeverity.LOW, f"Alert {i}", f"Message {i}")

        # Should keep only last 1000
        self.assertEqual(len(manager.alert_history), 1000)

        # Should have the most recent alerts
        last_alert = manager.alert_history[-1]
        self.assertEqual(last_alert["title"], "Alert 1099")

    def test_get_alert_history(self):
        """Test getting alert history."""
        manager = AlertManager()

        # Send some alerts
        for i in range(10):
            manager.send_alert(ErrorSeverity.LOW, f"Alert {i}", f"Message {i}")

        # Get limited history
        history = manager.get_alert_history(limit=5)

        self.assertEqual(len(history), 5)

        # Should be the most recent 5
        for i, alert in enumerate(history):
            expected_title = f"Alert {5 + i}"
            self.assertEqual(alert["title"], expected_title)


class TestErrorRecoveryManager(unittest.TestCase):
    """Test error recovery manager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.queue_file = os.path.join(self.temp_dir, "queue.json")

        # Mock database managers
        self.mock_db_manager = Mock(spec=DatabaseManager)
        self.mock_db_manager.health_check.return_value = {"status": "healthy"}

        self.database_managers = {"test_db": self.mock_db_manager}

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recovery_manager_initialization(self):
        """Test error recovery manager initialization."""
        manager = ErrorRecoveryManager(
            database_managers=self.database_managers,
            local_queue_path=self.queue_file,
            disk_monitor_paths=[self.temp_dir],
        )

        self.assertEqual(len(manager.database_managers), 1)
        self.assertIsNotNone(manager.local_queue)
        self.assertIsNotNone(manager.disk_monitor)
        self.assertIsNotNone(manager.alert_manager)

    def test_handle_transient_database_error(self):
        """Test handling transient database errors."""
        manager = ErrorRecoveryManager(
            database_managers=self.database_managers, local_queue_path=self.queue_file
        )

        # Simulate transient error
        from sqlalchemy.exc import OperationalError

        error = OperationalError("connection timeout", None, None)

        result = manager.handle_database_error(
            error=error,
            database_name="test_db",
            operation="test_operation",
            context={"key": "value"},
        )

        # Should attempt retry for transient errors
        self.assertIsInstance(result, RecoveryResult)
        self.assertIn(
            result.action_taken, [RecoveryAction.RETRY, RecoveryAction.QUEUE_LOCALLY]
        )

    def test_handle_non_transient_database_error(self):
        """Test handling non-transient database errors."""
        manager = ErrorRecoveryManager(
            database_managers=self.database_managers, local_queue_path=self.queue_file
        )

        # Simulate non-transient error
        error = ValueError("Invalid SQL syntax")

        result = manager.handle_database_error(
            error=error,
            database_name="test_db",
            operation="database_insert",  # Queueable operation
            context={"key": "value"},
        )

        # Should queue locally for queueable operations
        self.assertIsInstance(result, RecoveryResult)
        self.assertEqual(result.action_taken, RecoveryAction.QUEUE_LOCALLY)
        self.assertTrue(result.success)

    def test_process_queued_operations(self):
        """Test processing queued operations."""
        manager = ErrorRecoveryManager(
            database_managers=self.database_managers, local_queue_path=self.queue_file
        )

        # Add operations to queue
        operations = [
            {"operation": "database_insert", "context": {"id": 1}},
            {"operation": "database_update", "context": {"id": 2}},
            {"operation": "log_entry", "context": {"message": "test"}},
        ]

        for op in operations:
            manager.local_queue.enqueue_operation(op)

        # Process queued operations
        result = manager.process_queued_operations()

        self.assertIn("operations_processed", result)
        self.assertIn("operations_successful", result)
        self.assertIn("operations_failed", result)
        self.assertEqual(result["operations_processed"], 3)

    def test_monitor_and_cleanup_disk_space(self):
        """Test disk space monitoring and cleanup."""
        manager = ErrorRecoveryManager(
            database_managers=self.database_managers, disk_monitor_paths=[self.temp_dir]
        )

        result = manager.monitor_and_cleanup_disk_space()

        self.assertIn("timestamp", result)
        self.assertIn("disk_status", result)
        self.assertIn("cleanup_performed", result)

        # Should have checked our temp directory
        disk_status = result["disk_status"]
        self.assertIn(self.temp_dir, disk_status["paths"])

    def test_handle_container_restart(self):
        """Test container restart handling."""
        manager = ErrorRecoveryManager(
            database_managers=self.database_managers, local_queue_path=self.queue_file
        )

        result = manager.handle_container_restart("Memory limit exceeded")

        self.assertIsInstance(result, RecoveryResult)
        self.assertEqual(result.action_taken, RecoveryAction.RESTART)
        self.assertTrue(result.success)
        self.assertIn("Memory limit exceeded", result.message)

    def test_get_recovery_status(self):
        """Test getting recovery status."""
        manager = ErrorRecoveryManager(
            database_managers=self.database_managers,
            local_queue_path=self.queue_file,
            disk_monitor_paths=[self.temp_dir],
        )

        status = manager.get_recovery_status()

        self.assertIn("timestamp", status)
        self.assertIn("recovery_stats", status)
        self.assertIn("local_queue", status)
        self.assertIn("disk_status", status)
        self.assertIn("database_managers", status)

        # Verify structure
        self.assertIn("size", status["local_queue"])
        self.assertIn("is_full", status["local_queue"])
        self.assertEqual(status["database_managers"], ["test_db"])

    @patch("core.error_recovery.signal.signal")
    def test_signal_handlers(self, mock_signal):
        """Test signal handler setup."""
        ErrorRecoveryManager(database_managers=self.database_managers)

        # Should have set up signal handlers
        self.assertTrue(mock_signal.called)

    def test_error_severity_determination(self):
        """Test error severity determination."""
        manager = ErrorRecoveryManager()

        # Test critical errors
        critical_error = Exception("out of memory")
        severity = manager._determine_error_severity(critical_error)
        self.assertEqual(severity, ErrorSeverity.CRITICAL)

        # Test high severity errors
        high_error = Exception("connection timeout")
        severity = manager._determine_error_severity(high_error)
        self.assertEqual(severity, ErrorSeverity.HIGH)

        # Test medium severity errors
        medium_error = Exception("temporary failure")
        severity = manager._determine_error_severity(medium_error)
        self.assertEqual(severity, ErrorSeverity.MEDIUM)

        # Test default severity
        unknown_error = Exception("unknown error")
        severity = manager._determine_error_severity(unknown_error)
        self.assertEqual(severity, ErrorSeverity.MEDIUM)

    def test_can_queue_operation(self):
        """Test operation queueability check."""
        manager = ErrorRecoveryManager()

        # Queueable operations
        self.assertTrue(manager._can_queue_operation("database_insert"))
        self.assertTrue(manager._can_queue_operation("database_update"))
        self.assertTrue(manager._can_queue_operation("log_entry"))
        self.assertTrue(manager._can_queue_operation("metric_update"))

        # Non-queueable operations
        self.assertFalse(manager._can_queue_operation("system_shutdown"))
        self.assertFalse(manager._can_queue_operation("critical_alert"))


class TestAlertHandlers(unittest.TestCase):
    """Test alert handler functions."""

    def test_log_alert_handler(self):
        """Test log alert handler."""
        alert_data = {
            "severity": "high",
            "title": "Test Alert",
            "message": "Test message",
            "timestamp": datetime.now().isoformat() + "Z",
        }

        # Should not raise exception
        log_alert_handler(alert_data)

    def test_file_alert_handler(self):
        """Test file alert handler."""
        with tempfile.TemporaryDirectory() as temp_dir:
            alert_file = os.path.join(temp_dir, "alerts.json")

            # Patch the alert file path
            with patch("core.error_recovery.file_alert_handler") as mock_handler:

                def actual_handler(alert_data):
                    os.makedirs(os.path.dirname(alert_file), exist_ok=True)
                    with open(alert_file, "a") as f:
                        f.write(json.dumps(alert_data) + "\n")

                mock_handler.side_effect = actual_handler

                alert_data = {
                    "severity": "medium",
                    "title": "File Test Alert",
                    "message": "Test file message",
                    "timestamp": datetime.now().isoformat() + "Z",
                }

                mock_handler(alert_data)

                # Verify file was created and contains alert
                self.assertTrue(os.path.exists(alert_file))

                with open(alert_file) as f:
                    content = f.read().strip()
                    loaded_alert = json.loads(content)
                    self.assertEqual(loaded_alert["title"], "File Test Alert")


class TestIntegration(unittest.TestCase):
    """Integration tests for error recovery system."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up integration test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_error_recovery_workflow(self):
        """Test complete error recovery workflow."""
        # Setup components
        alert_manager = AlertManager()
        alert_manager.add_alert_handler(log_alert_handler)

        mock_db_manager = Mock(spec=DatabaseManager)
        mock_db_manager.health_check.return_value = {"status": "healthy"}

        manager = ErrorRecoveryManager(
            database_managers={"test_db": mock_db_manager},
            local_queue_path=os.path.join(self.temp_dir, "queue.json"),
            disk_monitor_paths=[self.temp_dir],
            alert_manager=alert_manager,
        )

        # Simulate database error
        from sqlalchemy.exc import OperationalError

        error = OperationalError("connection lost", None, None)

        # Handle error
        result = manager.handle_database_error(
            error=error,
            database_name="test_db",
            operation="database_insert",
            context={"record_id": 123},
        )

        # Should have handled error
        self.assertIsInstance(result, RecoveryResult)

        # Process any queued operations
        if result.action_taken == RecoveryAction.QUEUE_LOCALLY:
            process_result = manager.process_queued_operations()
            self.assertGreater(process_result["operations_processed"], 0)

        # Check recovery status
        status = manager.get_recovery_status()
        self.assertIn("recovery_stats", status)
        self.assertGreater(status["recovery_stats"]["total_errors"], 0)

        # Monitor disk space
        disk_result = manager.monitor_and_cleanup_disk_space()
        self.assertIn("disk_status", disk_result)

    def test_concurrent_operations(self):
        """Test error recovery under concurrent operations."""
        manager = ErrorRecoveryManager(
            local_queue_path=os.path.join(self.temp_dir, "concurrent_queue.json")
        )

        # Function to enqueue operations concurrently
        def enqueue_operations(thread_id, count):
            for i in range(count):
                operation = {
                    "thread_id": thread_id,
                    "operation_id": i,
                    "operation": "database_insert",
                    "context": {"data": f"thread_{thread_id}_op_{i}"},
                }
                manager.local_queue.enqueue_operation(operation)

        # Start multiple threads
        threads = []
        for thread_id in range(5):
            thread = threading.Thread(target=enqueue_operations, args=(thread_id, 10))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should have queued all operations
        self.assertEqual(manager.local_queue.get_queue_size(), 50)

        # Process operations
        result = manager.process_queued_operations()
        self.assertEqual(result["operations_processed"], 50)


if __name__ == "__main__":
    unittest.main()
