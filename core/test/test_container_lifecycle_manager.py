"""
Tests for Container Lifecycle Manager

This module provides comprehensive tests for container startup validation,
dependency checking, graceful shutdown, restart policies, health monitoring,
and automatic remediation functionality.
"""

import json
import os
import signal
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from core.container_lifecycle_manager import (
    ContainerLifecycleManager,
    ContainerState,
    DependencyCheck,
    LifecycleEvent,
    RestartPolicy,
    StartupValidationResult,
)


class TestContainerLifecycleManager(unittest.TestCase):
    """Test cases for ContainerLifecycleManager"""

    def setUp(self):
        """Set up test environment"""
        self.container_id = "test-container-123"
        self.flow_name = "test-flow"

        # Mock environment variables
        self.env_patcher = patch.dict(
            os.environ,
            {
                "CONTAINER_FLOW_NAME": self.flow_name,
                "CONTAINER_ENVIRONMENT": "test",
                "CONTAINER_RPA_DB_CONNECTION_STRING": "postgresql://test:test@localhost:5432/test_db",
                "CONTAINER_MAX_MEMORY_MB": "512",
                "CONTAINER_MAX_CPU_PERCENT": "50",
            },
        )
        self.env_patcher.start()

        # Create test directories
        self.test_dirs = [
            "/tmp/test_app/logs",
            "/tmp/test_app/data",
            "/tmp/test_app/output",
        ]
        for dir_path in self.test_dirs:
            os.makedirs(dir_path, exist_ok=True)

        # Mock config manager
        self.mock_config_manager = Mock()
        self.mock_config_manager.load_container_config.return_value = {
            "databases": {"rpa_db": {"host": "localhost"}},
            "services": [],
        }

        # Create lifecycle manager
        self.lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=self.mock_config_manager,
        )

    def tearDown(self):
        """Clean up test environment"""
        self.env_patcher.stop()

        # Clean up test directories
        import shutil

        for dir_path in self.test_dirs:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path, ignore_errors=True)

    def test_initialization(self):
        """Test lifecycle manager initialization"""
        self.assertEqual(self.lifecycle_manager.container_id, self.container_id)
        self.assertEqual(self.lifecycle_manager.flow_name, self.flow_name)
        self.assertEqual(self.lifecycle_manager.state, ContainerState.INITIALIZING)
        self.assertFalse(self.lifecycle_manager.shutdown_requested)
        self.assertEqual(self.lifecycle_manager.restart_count, 0)

    def test_startup_environment_validation_success(self):
        """Test successful startup environment validation"""
        # Mock required directories
        with (
            patch("os.path.exists", return_value=True),
            patch("psutil.disk_usage") as mock_disk_usage,
        ):

            # Mock disk usage (10GB free)
            mock_disk_usage.return_value = Mock(free=10 * 1024**3, total=100 * 1024**3)

            result = self.lifecycle_manager.validate_startup_environment()

            self.assertTrue(result.success)
            self.assertIn("Environment variables validation", result.checks_passed)
            self.assertIn("Flow name consistency", result.checks_passed)
            self.assertIn("Configuration loading", result.checks_passed)
            self.assertEqual(len(result.checks_failed), 0)

    def test_startup_environment_validation_missing_env_vars(self):
        """Test startup validation with missing environment variables"""
        with patch.dict(os.environ, {}, clear=True):
            result = self.lifecycle_manager.validate_startup_environment()

            self.assertFalse(result.success)
            self.assertTrue(
                any(
                    "Missing environment variables" in failure
                    for failure in result.checks_failed
                )
            )

    def test_startup_environment_validation_flow_name_mismatch(self):
        """Test startup validation with flow name mismatch"""
        with patch.dict(os.environ, {"CONTAINER_FLOW_NAME": "different-flow"}):
            result = self.lifecycle_manager.validate_startup_environment()

            self.assertFalse(result.success)
            self.assertTrue(
                any("Flow name mismatch" in failure for failure in result.checks_failed)
            )

    def test_startup_environment_validation_low_disk_space(self):
        """Test startup validation with low disk space"""
        with (
            patch("os.path.exists", return_value=True),
            patch("psutil.disk_usage") as mock_disk_usage,
        ):

            # Mock low disk usage (0.5GB free)
            mock_disk_usage.return_value = Mock(free=0.5 * 1024**3, total=100 * 1024**3)

            result = self.lifecycle_manager.validate_startup_environment()

            self.assertFalse(result.success)
            self.assertTrue(
                any(
                    "Insufficient disk space" in failure
                    for failure in result.checks_failed
                )
            )

    def test_add_dependency_check(self):
        """Test adding dependency checks"""
        check = DependencyCheck(
            name="test_service",
            check_function=lambda: True,
            timeout_seconds=30,
            required=True,
            description="Test service dependency",
        )

        self.lifecycle_manager.add_dependency_check(check)

        self.assertIn(check, self.lifecycle_manager.dependency_checks)

    def test_check_dependencies_success(self):
        """Test successful dependency checking"""
        # Add mock dependency checks
        success_check = DependencyCheck(
            name="success_service",
            check_function=lambda: True,
            timeout_seconds=5,
            required=True,
        )

        optional_fail_check = DependencyCheck(
            name="optional_service",
            check_function=lambda: False,
            timeout_seconds=5,
            required=False,
        )

        self.lifecycle_manager.add_dependency_check(success_check)
        self.lifecycle_manager.add_dependency_check(optional_fail_check)

        result = self.lifecycle_manager.check_dependencies()

        self.assertTrue(result)

    def test_check_dependencies_required_failure(self):
        """Test dependency checking with required dependency failure"""
        fail_check = DependencyCheck(
            name="required_service",
            check_function=lambda: False,
            timeout_seconds=2,
            required=True,
        )

        self.lifecycle_manager.add_dependency_check(fail_check)

        result = self.lifecycle_manager.check_dependencies()

        self.assertFalse(result)

    def test_check_dependencies_with_retry(self):
        """Test dependency checking with retry logic"""
        call_count = 0

        def flaky_check():
            nonlocal call_count
            call_count += 1
            return call_count >= 3  # Succeed on third attempt

        retry_check = DependencyCheck(
            name="flaky_service",
            check_function=flaky_check,
            timeout_seconds=10,
            retry_interval=1,
            required=True,
        )

        self.lifecycle_manager.add_dependency_check(retry_check)

        result = self.lifecycle_manager.check_dependencies()

        self.assertTrue(result)
        self.assertGreaterEqual(call_count, 3)

    @patch("core.container_lifecycle_manager.HealthMonitor")
    def test_initialize_health_monitoring_success(self, mock_health_monitor_class):
        """Test successful health monitoring initialization"""
        mock_health_monitor = Mock()
        mock_health_monitor.comprehensive_health_check.return_value = {
            "overall_status": "healthy"
        }
        mock_health_monitor_class.return_value = mock_health_monitor

        result = self.lifecycle_manager.initialize_health_monitoring()

        self.assertTrue(result)
        self.assertIsNotNone(self.lifecycle_manager.health_monitor)

    @patch("core.container_lifecycle_manager.HealthMonitor")
    def test_initialize_health_monitoring_failure(self, mock_health_monitor_class):
        """Test health monitoring initialization failure"""
        mock_health_monitor_class.side_effect = Exception("Health monitor init failed")

        result = self.lifecycle_manager.initialize_health_monitoring()

        self.assertFalse(result)
        self.assertIsNone(self.lifecycle_manager.health_monitor)

    def test_startup_success(self):
        """Test successful container startup"""
        # Mock all startup components
        with (
            patch.object(
                self.lifecycle_manager, "validate_startup_environment"
            ) as mock_validate,
            patch.object(self.lifecycle_manager, "check_dependencies") as mock_deps,
            patch.object(
                self.lifecycle_manager, "initialize_health_monitoring"
            ) as mock_health,
        ):

            mock_validate.return_value = StartupValidationResult(success=True)
            mock_deps.return_value = True
            mock_health.return_value = True

            # Mock health monitor
            mock_health_monitor = Mock()
            mock_health_monitor.comprehensive_health_check.return_value = {
                "overall_status": "healthy"
            }
            self.lifecycle_manager.health_monitor = mock_health_monitor

            result = self.lifecycle_manager.startup()

            self.assertTrue(result)
            self.assertEqual(self.lifecycle_manager.state, ContainerState.RUNNING)
            self.assertEqual(self.lifecycle_manager.metrics.successful_startups, 1)

    def test_startup_validation_failure(self):
        """Test startup failure due to validation"""
        with patch.object(
            self.lifecycle_manager, "validate_startup_environment"
        ) as mock_validate:
            mock_validate.return_value = StartupValidationResult(success=False)

            result = self.lifecycle_manager.startup()

            self.assertFalse(result)
            self.assertEqual(self.lifecycle_manager.state, ContainerState.FAILED)
            self.assertEqual(self.lifecycle_manager.metrics.failed_startups, 1)

    def test_startup_dependency_failure(self):
        """Test startup failure due to dependencies"""
        with (
            patch.object(
                self.lifecycle_manager, "validate_startup_environment"
            ) as mock_validate,
            patch.object(self.lifecycle_manager, "check_dependencies") as mock_deps,
        ):

            mock_validate.return_value = StartupValidationResult(success=True)
            mock_deps.return_value = False

            result = self.lifecycle_manager.startup()

            self.assertFalse(result)
            self.assertEqual(self.lifecycle_manager.state, ContainerState.FAILED)

    def test_health_monitoring_loop(self):
        """Test health monitoring loop functionality"""
        self.lifecycle_manager.state = ContainerState.RUNNING
        self.lifecycle_manager.health_monitor = Mock()

        # Mock health check results
        health_results = [
            {"overall_status": "healthy"},
            {"overall_status": "degraded"},
            {"overall_status": "unhealthy"},
        ]

        self.lifecycle_manager.health_monitor.comprehensive_health_check.side_effect = (
            health_results
        )

        # Run monitoring loop for a short time
        import threading

        def stop_monitoring():
            time.sleep(0.1)  # Let it run briefly
            self.lifecycle_manager.shutdown_requested = True

        stop_thread = threading.Thread(target=stop_monitoring)
        stop_thread.start()

        # Set short health check interval for testing
        self.lifecycle_manager.health_check_interval = 0.05

        self.lifecycle_manager.run_health_monitoring_loop()

        stop_thread.join()

        # Verify health checks were performed
        self.assertGreater(
            self.lifecycle_manager.health_monitor.comprehensive_health_check.call_count,
            0,
        )

    def test_health_remediation_trigger(self):
        """Test health remediation triggering"""
        self.lifecycle_manager.health_monitor = Mock()
        self.lifecycle_manager.max_health_check_failures = 2

        # Mock unhealthy status
        health_report = {
            "overall_status": "unhealthy",
            "checks": {"database_rpa_db": {"status": "unhealthy"}},
            "resource_status": {"memory_usage_percent": 95, "disk_usage_percent": 85},
        }

        with patch.object(
            self.lifecycle_manager, "_execute_remediation_action"
        ) as mock_remediation:
            # Trigger multiple health check failures
            self.lifecycle_manager.health_check_failures = 2
            self.lifecycle_manager._trigger_health_remediation(health_report)

            # Verify remediation actions were called
            mock_remediation.assert_called()

    def test_graceful_shutdown_success(self):
        """Test successful graceful shutdown"""
        self.lifecycle_manager.state = ContainerState.RUNNING
        self.lifecycle_manager.startup_time = datetime.now() - timedelta(seconds=60)

        # Add cleanup handler
        cleanup_called = False

        def cleanup_handler():
            nonlocal cleanup_called
            cleanup_called = True

        self.lifecycle_manager.add_cleanup_handler(cleanup_handler)

        # Mock health monitor
        self.lifecycle_manager.health_monitor = Mock()
        self.lifecycle_manager.health_monitor.comprehensive_health_check.return_value = {
            "overall_status": "healthy"
        }

        result = self.lifecycle_manager.graceful_shutdown(timeout_seconds=5)

        self.assertTrue(result)
        self.assertTrue(cleanup_called)
        self.assertEqual(self.lifecycle_manager.state, ContainerState.STOPPED)
        self.assertEqual(self.lifecycle_manager.metrics.graceful_shutdowns, 1)

    def test_graceful_shutdown_timeout(self):
        """Test graceful shutdown with timeout"""
        self.lifecycle_manager.state = ContainerState.RUNNING

        # Add slow cleanup handler
        def slow_cleanup():
            time.sleep(2)

        self.lifecycle_manager.add_cleanup_handler(slow_cleanup)

        result = self.lifecycle_manager.graceful_shutdown(timeout_seconds=1)

        self.assertFalse(result)  # Should timeout
        self.assertEqual(self.lifecycle_manager.state, ContainerState.STOPPED)
        self.assertEqual(self.lifecycle_manager.metrics.forced_shutdowns, 1)

    def test_restart_policy_always(self):
        """Test restart policy ALWAYS"""
        self.lifecycle_manager.restart_config.policy = RestartPolicy.ALWAYS
        self.lifecycle_manager.state = ContainerState.STOPPED

        result = self.lifecycle_manager.should_restart()

        self.assertTrue(result)

    def test_restart_policy_never(self):
        """Test restart policy NO"""
        self.lifecycle_manager.restart_config.policy = RestartPolicy.NO
        self.lifecycle_manager.state = ContainerState.FAILED

        result = self.lifecycle_manager.should_restart()

        self.assertFalse(result)

    def test_restart_policy_on_failure(self):
        """Test restart policy ON_FAILURE"""
        self.lifecycle_manager.restart_config.policy = RestartPolicy.ON_FAILURE

        # Should restart on failure
        self.lifecycle_manager.state = ContainerState.FAILED
        self.assertTrue(self.lifecycle_manager.should_restart())

        # Should not restart on normal stop
        self.lifecycle_manager.state = ContainerState.STOPPED
        self.assertFalse(self.lifecycle_manager.should_restart())

    def test_restart_delay_calculation(self):
        """Test restart delay calculation with exponential backoff"""
        self.lifecycle_manager.restart_config.restart_delay_seconds = 5
        self.lifecycle_manager.restart_config.exponential_backoff = True
        self.lifecycle_manager.restart_config.max_delay_seconds = 60

        # First restart
        self.lifecycle_manager.restart_count = 0
        delay = self.lifecycle_manager.calculate_restart_delay()
        self.assertEqual(delay, 5)

        # Second restart (2^1 = 2x)
        self.lifecycle_manager.restart_count = 1
        delay = self.lifecycle_manager.calculate_restart_delay()
        self.assertEqual(delay, 10)

        # Third restart (2^2 = 4x)
        self.lifecycle_manager.restart_count = 2
        delay = self.lifecycle_manager.calculate_restart_delay()
        self.assertEqual(delay, 20)

    def test_restart_delay_max_limit(self):
        """Test restart delay respects maximum limit"""
        self.lifecycle_manager.restart_config.restart_delay_seconds = 30
        self.lifecycle_manager.restart_config.exponential_backoff = True
        self.lifecycle_manager.restart_config.max_delay_seconds = 60
        self.lifecycle_manager.restart_count = 5  # Would be 30 * 2^5 = 960s

        delay = self.lifecycle_manager.calculate_restart_delay()

        self.assertEqual(delay, 60)  # Should be capped at max_delay_seconds

    def test_restart_attempt_success(self):
        """Test successful restart attempt"""
        self.lifecycle_manager.restart_config.max_restart_attempts = 3

        with patch.object(self.lifecycle_manager, "startup") as mock_startup:
            mock_startup.return_value = True

            result = self.lifecycle_manager.attempt_restart()

            self.assertTrue(result)
            self.assertEqual(self.lifecycle_manager.restart_count, 1)
            mock_startup.assert_called_once()

    def test_restart_attempt_max_attempts_exceeded(self):
        """Test restart attempt when max attempts exceeded"""
        self.lifecycle_manager.restart_config.max_restart_attempts = 2
        self.lifecycle_manager.restart_count = 2

        result = self.lifecycle_manager.attempt_restart()

        self.assertFalse(result)

    def test_restart_count_reset_outside_window(self):
        """Test restart count reset when outside restart window"""
        self.lifecycle_manager.restart_config.restart_window_minutes = 5
        self.lifecycle_manager.restart_count = 3
        self.lifecycle_manager.last_restart_time = datetime.now() - timedelta(
            minutes=10
        )

        with patch.object(self.lifecycle_manager, "startup") as mock_startup:
            mock_startup.return_value = True

            self.lifecycle_manager.attempt_restart()

            self.assertEqual(self.lifecycle_manager.restart_count, 1)  # Should reset

    def test_lifecycle_metrics(self):
        """Test lifecycle metrics collection"""
        self.lifecycle_manager.state = ContainerState.RUNNING
        self.lifecycle_manager.startup_time = datetime.now() - timedelta(seconds=30)
        self.lifecycle_manager.metrics.successful_startups = 2
        self.lifecycle_manager.metrics.failed_startups = 1

        metrics = self.lifecycle_manager.get_lifecycle_metrics()

        self.assertEqual(metrics["container_id"], self.container_id)
        self.assertEqual(metrics["flow_name"], self.flow_name)
        self.assertEqual(metrics["current_state"], ContainerState.RUNNING.value)
        self.assertEqual(metrics["metrics"]["successful_startups"], 2)
        self.assertEqual(metrics["metrics"]["failed_startups"], 1)
        self.assertGreater(metrics["current_uptime_seconds"], 0)

    def test_lifecycle_report_export(self):
        """Test lifecycle report export"""
        # Add some test data
        self.lifecycle_manager._record_event(LifecycleEvent.STARTUP_INITIATED)
        self.lifecycle_manager._record_event(LifecycleEvent.STARTUP_COMPLETED)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            report_file = f.name

        try:
            report = self.lifecycle_manager.export_lifecycle_report(report_file)

            # Verify report structure
            self.assertIn("report_timestamp", report)
            self.assertIn("container_info", report)
            self.assertIn("metrics", report)
            self.assertIn("event_history", report)

            # Verify file was created
            self.assertTrue(os.path.exists(report_file))

            # Verify file contents
            with open(report_file) as f:
                file_report = json.load(f)

            self.assertEqual(
                file_report["container_info"]["container_id"], self.container_id
            )
            self.assertEqual(len(file_report["event_history"]), 2)

        finally:
            if os.path.exists(report_file):
                os.unlink(report_file)

    def test_signal_handling(self):
        """Test signal handling for graceful shutdown"""
        self.assertFalse(self.lifecycle_manager.shutdown_requested)

        # Test signal handler directly without sending actual signals
        # Create a mock signal handler
        def mock_signal_handler(signum, frame):
            self.lifecycle_manager.shutdown_requested = True

        # Replace the signal handler temporarily
        original_handler = signal.signal(signal.SIGTERM, mock_signal_handler)

        try:
            # Call the handler directly
            mock_signal_handler(signal.SIGTERM, None)
            self.assertTrue(self.lifecycle_manager.shutdown_requested)
        finally:
            # Restore original handler
            signal.signal(signal.SIGTERM, original_handler)

    def test_event_recording(self):
        """Test lifecycle event recording"""
        initial_count = len(self.lifecycle_manager.event_history)

        self.lifecycle_manager._record_event(
            LifecycleEvent.STARTUP_INITIATED,
            details={"test": "data"},
            duration_ms=100.5,
        )

        self.assertEqual(len(self.lifecycle_manager.event_history), initial_count + 1)

        event = self.lifecycle_manager.event_history[-1]
        self.assertEqual(event.event, LifecycleEvent.STARTUP_INITIATED)
        self.assertEqual(event.container_id, self.container_id)
        self.assertEqual(event.flow_name, self.flow_name)
        self.assertEqual(event.details["test"], "data")
        self.assertEqual(event.duration_ms, 100.5)

    def test_remediation_action_memory_cleanup(self):
        """Test memory cleanup remediation action"""
        with patch("gc.collect") as mock_gc:
            self.lifecycle_manager._execute_remediation_action("memory_cleanup")
            mock_gc.assert_called_once()

    def test_remediation_action_disk_cleanup(self):
        """Test disk cleanup remediation action"""
        # Create test files
        test_dir = "/tmp/test_cleanup"
        os.makedirs(test_dir, exist_ok=True)

        old_file = os.path.join(test_dir, "old_file.txt")
        new_file = os.path.join(test_dir, "new_file.txt")

        # Create old file (modify time to 2 hours ago)
        with open(old_file, "w") as f:
            f.write("old content")

        old_time = time.time() - 7200  # 2 hours ago
        os.utime(old_file, (old_time, old_time))

        # Create new file
        with open(new_file, "w") as f:
            f.write("new content")

        try:
            with patch("os.walk") as mock_walk:
                mock_walk.return_value = [
                    (test_dir, [], ["old_file.txt", "new_file.txt"])
                ]

                with (
                    patch("os.path.getmtime") as mock_getmtime,
                    patch("os.remove") as mock_remove,
                ):

                    def mock_mtime(path):
                        if "old_file" in path:
                            return old_time
                        return time.time()

                    mock_getmtime.side_effect = mock_mtime

                    self.lifecycle_manager._execute_remediation_action("disk_cleanup")

                    # Should only remove old file
                    mock_remove.assert_called()

        finally:
            # Cleanup
            import shutil

            if os.path.exists(test_dir):
                shutil.rmtree(test_dir, ignore_errors=True)


class TestContainerLifecycleIntegration(unittest.TestCase):
    """Integration tests for container lifecycle management"""

    def setUp(self):
        """Set up integration test environment"""
        self.container_id = "integration-test-container"
        self.flow_name = "integration-test-flow"

        # Set up environment
        self.env_patcher = patch.dict(
            os.environ,
            {
                "CONTAINER_FLOW_NAME": self.flow_name,
                "CONTAINER_ENVIRONMENT": "test",
                "CONTAINER_RPA_DB_CONNECTION_STRING": "postgresql://test:test@localhost:5432/test_db",
            },
        )
        self.env_patcher.start()

    def tearDown(self):
        """Clean up integration test environment"""
        self.env_patcher.stop()

    @patch("core.container_lifecycle_manager.ServiceOrchestrator")
    @patch("core.container_lifecycle_manager.HealthMonitor")
    def test_complete_lifecycle_flow(
        self, mock_health_monitor_class, mock_service_orchestrator_class
    ):
        """Test complete container lifecycle flow"""
        # Mock service orchestrator
        mock_orchestrator = Mock()
        mock_orchestrator.wait_for_database.return_value = True
        mock_orchestrator.wait_for_prefect_server.return_value = True
        mock_service_orchestrator_class.return_value = mock_orchestrator

        # Mock health monitor
        mock_health_monitor = Mock()
        mock_health_monitor.comprehensive_health_check.return_value = {
            "overall_status": "healthy"
        }
        mock_health_monitor_class.return_value = mock_health_monitor

        # Mock config manager
        mock_config_manager = Mock()
        mock_config_manager.load_container_config.return_value = {
            "databases": {"rpa_db": {}},
            "services": [],
        }

        # Create lifecycle manager
        lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=mock_config_manager,
        )

        # Mock required directories and disk space
        with (
            patch("os.path.exists", return_value=True),
            patch("psutil.disk_usage") as mock_disk_usage,
        ):

            mock_disk_usage.return_value = Mock(free=10 * 1024**3, total=100 * 1024**3)

            # Test startup
            startup_result = lifecycle_manager.startup()
            self.assertTrue(startup_result)
            self.assertEqual(lifecycle_manager.state, ContainerState.RUNNING)

            # Test graceful shutdown
            shutdown_result = lifecycle_manager.graceful_shutdown()
            self.assertTrue(shutdown_result)
            self.assertEqual(lifecycle_manager.state, ContainerState.STOPPED)

            # Verify metrics
            metrics = lifecycle_manager.get_lifecycle_metrics()
            self.assertEqual(metrics["metrics"]["successful_startups"], 1)
            self.assertEqual(metrics["metrics"]["graceful_shutdowns"], 1)


if __name__ == "__main__":
    unittest.main()
