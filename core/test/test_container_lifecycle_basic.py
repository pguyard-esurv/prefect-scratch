"""
Basic Container Lifecycle Tests

Simple, focused tests for container lifecycle functionality without complex scenarios
that might hang in CI environments.
"""

import os
import unittest
from unittest.mock import Mock, patch

from core.container_lifecycle_manager import (
    ContainerLifecycleManager,
    ContainerState,
    DependencyCheck,
    LifecycleEvent,
    RestartPolicy,
    StartupValidationResult,
)


class TestContainerLifecycleBasic(unittest.TestCase):
    """Basic container lifecycle tests"""

    def setUp(self):
        """Set up test environment"""
        self.container_id = "test-container"
        self.flow_name = "test-flow"

        # Mock environment variables
        self.env_patcher = patch.dict(
            os.environ,
            {
                "CONTAINER_FLOW_NAME": self.flow_name,
                "CONTAINER_ENVIRONMENT": "test",
                "CONTAINER_RPA_DB_CONNECTION_STRING": "postgresql://test:test@localhost:5432/test_db",
            },
        )
        self.env_patcher.start()

        # Mock config manager
        self.mock_config_manager = Mock()
        self.mock_config_manager.load_container_config.return_value = {
            "databases": {"rpa_db": {}},
            "services": [],
        }

    def tearDown(self):
        """Clean up test environment"""
        self.env_patcher.stop()

    def test_initialization(self):
        """Test basic initialization"""
        lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=self.mock_config_manager,
        )

        self.assertEqual(lifecycle_manager.container_id, self.container_id)
        self.assertEqual(lifecycle_manager.flow_name, self.flow_name)
        self.assertEqual(lifecycle_manager.state, ContainerState.INITIALIZING)

    def test_startup_validation_success(self):
        """Test successful startup validation"""
        lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=self.mock_config_manager,
        )

        with (
            patch("os.path.exists", return_value=True),
            patch("psutil.disk_usage") as mock_disk_usage,
        ):

            mock_disk_usage.return_value = Mock(free=10 * 1024**3, total=100 * 1024**3)

            result = lifecycle_manager.validate_startup_environment()

            self.assertTrue(result.success)
            self.assertGreater(len(result.checks_passed), 0)

    def test_dependency_check_addition(self):
        """Test adding dependency checks"""
        lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=self.mock_config_manager,
        )

        check = DependencyCheck(
            name="test_service",
            check_function=lambda: True,
            timeout_seconds=30,
            required=True,
        )

        lifecycle_manager.add_dependency_check(check)

        self.assertIn(check, lifecycle_manager.dependency_checks)

    def test_restart_policy_logic(self):
        """Test restart policy logic"""
        lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=self.mock_config_manager,
        )

        # Test ALWAYS policy
        lifecycle_manager.restart_config.policy = RestartPolicy.ALWAYS
        lifecycle_manager.state = ContainerState.STOPPED
        self.assertTrue(lifecycle_manager.should_restart())

        # Test NO policy
        lifecycle_manager.restart_config.policy = RestartPolicy.NO
        lifecycle_manager.state = ContainerState.FAILED
        self.assertFalse(lifecycle_manager.should_restart())

    def test_event_recording(self):
        """Test lifecycle event recording"""
        lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=self.mock_config_manager,
        )

        initial_count = len(lifecycle_manager.event_history)

        lifecycle_manager._record_event(
            LifecycleEvent.STARTUP_INITIATED, details={"test": "data"}
        )

        self.assertEqual(len(lifecycle_manager.event_history), initial_count + 1)

        event = lifecycle_manager.event_history[-1]
        self.assertEqual(event.event, LifecycleEvent.STARTUP_INITIATED)
        self.assertEqual(event.details["test"], "data")

    def test_metrics_collection(self):
        """Test basic metrics collection"""
        lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=self.mock_config_manager,
        )

        lifecycle_manager.metrics.successful_startups = 1
        lifecycle_manager.metrics.failed_startups = 0

        metrics = lifecycle_manager.get_lifecycle_metrics()

        self.assertEqual(metrics["container_id"], self.container_id)
        self.assertEqual(metrics["flow_name"], self.flow_name)
        self.assertEqual(metrics["metrics"]["successful_startups"], 1)
        self.assertEqual(metrics["metrics"]["failed_startups"], 0)

    def test_cleanup_handlers(self):
        """Test cleanup handler management"""
        lifecycle_manager = ContainerLifecycleManager(
            container_id=self.container_id,
            flow_name=self.flow_name,
            config_manager=self.mock_config_manager,
        )

        cleanup_called = False

        def test_cleanup():
            nonlocal cleanup_called
            cleanup_called = True

        lifecycle_manager.add_cleanup_handler(test_cleanup)

        self.assertEqual(len(lifecycle_manager.cleanup_handlers), 1)

        # Test cleanup execution
        lifecycle_manager.cleanup_handlers[0]()
        self.assertTrue(cleanup_called)


if __name__ == "__main__":
    unittest.main()
