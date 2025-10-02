"""
Tests for Error Handling and Recovery System

Tests comprehensive error handling, retry logic, rollback capabilities,
and recovery mechanisms.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from deployment_system.error_handling import (
    DeploymentSystemError,
    FlowDiscoveryError,
    ValidationError,
    ConfigurationError,
    DockerError,
    PrefectAPIError,
    DeploymentError,
    RecoveryError,
    ErrorContext,
    ErrorSeverity,
    ErrorCategory,
    ErrorCodes,
    RetryHandler,
    RetryPolicy,
    RetryStrategy,
    RetryPolicies,
    ErrorReporter,
    RollbackManager,
    RecoveryManager,
    OperationType,
    OperationStatus,
)


class TestErrorTypes:
    """Test custom error types and error context."""

    def test_deployment_system_error_creation(self):
        """Test creating deployment system errors with context."""
        context = ErrorContext(
            flow_name="test_flow",
            deployment_name="test_deployment",
            environment="development",
            file_path="/path/to/file.py",
            line_number=42,
        )

        error = DeploymentSystemError(
            message="Test error message",
            error_code="TEST_ERROR",
            category=ErrorCategory.DEPLOYMENT,
            severity=ErrorSeverity.HIGH,
            context=context,
            remediation="Fix the test error",
        )

        assert error.message == "Test error message"
        assert error.error_code == "TEST_ERROR"
        assert error.category == ErrorCategory.DEPLOYMENT
        assert error.severity == ErrorSeverity.HIGH
        assert error.context.flow_name == "test_flow"
        assert error.remediation == "Fix the test error"

    def test_error_to_dict(self):
        """Test converting error to dictionary."""
        context = ErrorContext(flow_name="test_flow")
        error = FlowDiscoveryError(
            message="Flow not found",
            error_code=ErrorCodes.FLOW_NOT_FOUND,
            context=context,
        )

        error_dict = error.to_dict()

        assert error_dict["error_code"] == ErrorCodes.FLOW_NOT_FOUND
        assert error_dict["message"] == "Flow not found"
        assert error_dict["category"] == ErrorCategory.FLOW_DISCOVERY.value
        assert error_dict["context"]["flow_name"] == "test_flow"

    def test_specific_error_types(self):
        """Test specific error type creation."""
        # Docker Error
        docker_error = DockerError(
            message="Docker build failed", context=ErrorContext(file_path="Dockerfile")
        )
        assert docker_error.category == ErrorCategory.DOCKER

        # Prefect API Error
        api_error = PrefectAPIError(
            message="API connection failed",
            context=ErrorContext(operation="create_deployment"),
        )
        assert api_error.category == ErrorCategory.PREFECT_API

        # Configuration Error
        config_error = ConfigurationError(
            message="Config file not found",
            context=ErrorContext(file_path="config.yaml"),
        )
        assert config_error.category == ErrorCategory.CONFIGURATION


class TestRetryHandler:
    """Test retry logic and policies."""

    def test_retry_policy_creation(self):
        """Test creating retry policies."""
        policy = RetryPolicy(
            max_attempts=5, base_delay=2.0, strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )

        assert policy.max_attempts == 5
        assert policy.base_delay == 2.0
        assert policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF

    def test_retry_handler_success(self):
        """Test successful operation without retries."""
        handler = RetryHandler(RetryPolicies.QUICK_RETRY)

        def successful_operation():
            return "success"

        result = handler.retry(successful_operation)
        assert result == "success"

    def test_retry_handler_with_retryable_exception(self):
        """Test retry with retryable exception."""
        handler = RetryHandler(RetryPolicies.QUICK_RETRY)

        call_count = 0

        def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Network error")
            return "success"

        result = handler.retry(failing_operation)
        assert result == "success"
        assert call_count == 3

    def test_retry_handler_with_non_retryable_exception(self):
        """Test immediate failure with non-retryable exception."""
        handler = RetryHandler(RetryPolicies.QUICK_RETRY)

        def failing_operation():
            raise ValueError("Invalid input")

        with pytest.raises(ValueError):
            handler.retry(failing_operation)

    def test_retry_handler_max_attempts_exceeded(self):
        """Test failure after max attempts exceeded."""
        policy = RetryPolicy(max_attempts=2, base_delay=0.1)
        handler = RetryHandler(policy)

        def always_failing_operation():
            raise ConnectionError("Always fails")

        with pytest.raises(ConnectionError):
            handler.retry(always_failing_operation)

    def test_delay_calculation(self):
        """Test delay calculation for different strategies."""
        handler = RetryHandler()

        # Test exponential backoff
        handler.policy.strategy = RetryStrategy.EXPONENTIAL_BACKOFF
        handler.policy.base_delay = 1.0
        handler.policy.backoff_multiplier = 2.0
        handler.policy.jitter = False

        assert handler.calculate_delay(1) == 1.0
        assert handler.calculate_delay(2) == 2.0
        assert handler.calculate_delay(3) == 4.0

        # Test fixed delay
        handler.policy.strategy = RetryStrategy.FIXED_DELAY
        assert handler.calculate_delay(1) == 1.0
        assert handler.calculate_delay(5) == 1.0

    @pytest.mark.asyncio
    async def test_async_retry(self):
        """Test async retry functionality."""
        handler = RetryHandler(RetryPolicies.QUICK_RETRY)

        call_count = 0

        async def async_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Network error")
            return "async_success"

        result = await handler.async_retry(async_operation)
        assert result == "async_success"
        assert call_count == 2


class TestErrorReporter:
    """Test error reporting and logging."""

    def test_error_reporter_creation(self):
        """Test creating error reporter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            report_file = Path(temp_dir) / "errors.json"
            reporter = ErrorReporter(report_file=report_file)

            assert reporter.report_file == report_file
            assert reporter.error_history == []

    def test_report_error(self):
        """Test reporting an error."""
        reporter = ErrorReporter()

        error = FlowDiscoveryError(
            message="Test error", context=ErrorContext(flow_name="test_flow")
        )

        report = reporter.report_error(error, operation="test_operation")

        assert len(reporter.error_history) == 1
        assert report.error == error
        assert report.operation == "test_operation"

    def test_error_summary(self):
        """Test getting error summary."""
        reporter = ErrorReporter()

        # Add some errors
        reporter.report_error(FlowDiscoveryError("Flow error"), operation="scan_flows")
        reporter.report_error(DockerError("Docker error"), operation="build_image")

        summary = reporter.get_error_summary()

        assert summary["total_errors"] == 2
        assert summary["by_category"]["flow_discovery"] == 1
        assert summary["by_category"]["docker"] == 1

    def test_user_friendly_error_formatting(self):
        """Test user-friendly error message formatting."""
        reporter = ErrorReporter()

        error = DeploymentError(
            message="Deployment failed",
            context=ErrorContext(
                flow_name="test_flow", deployment_name="test_deployment"
            ),
            remediation="Check configuration",
        )

        formatted = reporter.format_user_friendly_error(error)

        assert "❌ Deployment failed" in formatted
        assert "Flow: test_flow" in formatted
        assert "Deployment: test_deployment" in formatted
        assert "💡 Solution: Check configuration" in formatted

    def test_export_error_report(self):
        """Test exporting error report to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            reporter = ErrorReporter()

            # Add an error
            reporter.report_error(FlowDiscoveryError("Test error"), operation="test")

            # Export report
            export_path = Path(temp_dir) / "export.json"
            reporter.export_error_report(export_path)

            # Verify export
            assert export_path.exists()
            with open(export_path) as f:
                data = json.load(f)

            assert "generated_at" in data
            assert "summary" in data
            assert "errors" in data
            assert len(data["errors"]) == 1


class TestRollbackManager:
    """Test rollback capabilities."""

    def test_rollback_manager_creation(self):
        """Test creating rollback manager."""
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "rollback_state.json"
            manager = RollbackManager(state_file=state_file)

            assert manager.state_file == state_file
            assert manager.rollback_plans == {}
            assert manager.current_plan is None

    def test_start_transaction(self):
        """Test starting rollback transaction."""
        manager = RollbackManager()

        plan_id = manager.start_transaction("Test transaction")

        assert manager.current_plan is not None
        assert manager.current_plan.plan_id == plan_id
        assert manager.current_plan.description == "Test transaction"
        assert plan_id in manager.rollback_plans

    def test_add_rollback_operation(self):
        """Test adding rollback operations."""
        manager = RollbackManager()

        plan_id = manager.start_transaction("Test transaction")

        op_id = manager.add_rollback_operation(
            operation_type=OperationType.DEPLOYMENT_CREATE,
            description="Delete test deployment",
            rollback_data={"deployment_id": "test_id"},
        )

        assert len(manager.current_plan.operations) == 1
        operation = manager.current_plan.operations[0]
        assert operation.operation_id == op_id
        assert operation.operation_type == OperationType.DEPLOYMENT_CREATE
        assert operation.rollback_data["deployment_id"] == "test_id"

    def test_commit_transaction(self):
        """Test committing transaction."""
        manager = RollbackManager()

        plan_id = manager.start_transaction("Test transaction")
        manager.add_rollback_operation(
            operation_type=OperationType.DEPLOYMENT_CREATE, description="Test operation"
        )

        manager.commit_transaction()

        assert manager.current_plan is None
        plan = manager.rollback_plans[plan_id]
        assert plan.status == OperationStatus.COMPLETED
        assert plan.operations[0].status == OperationStatus.COMPLETED

    def test_execute_rollback(self):
        """Test executing rollback operations."""
        manager = RollbackManager()

        # Mock rollback function
        rollback_called = False

        def mock_rollback():
            nonlocal rollback_called
            rollback_called = True

        plan_id = manager.start_transaction("Test transaction")
        manager.add_rollback_operation(
            operation_type=OperationType.DEPLOYMENT_CREATE,
            description="Test rollback",
            rollback_function=mock_rollback,
        )

        success = manager.execute_rollback(plan_id)

        assert success
        assert rollback_called
        plan = manager.rollback_plans[plan_id]
        assert plan.status == OperationStatus.COMPLETED

    def test_rollback_with_failure(self):
        """Test rollback execution with failures."""
        manager = RollbackManager()

        def failing_rollback():
            raise Exception("Rollback failed")

        plan_id = manager.start_transaction("Test transaction")
        manager.add_rollback_operation(
            operation_type=OperationType.DEPLOYMENT_CREATE,
            description="Failing rollback",
            rollback_function=failing_rollback,
        )

        success = manager.execute_rollback(plan_id)

        assert not success
        plan = manager.rollback_plans[plan_id]
        assert plan.status == OperationStatus.FAILED
        assert plan.operations[0].status == OperationStatus.FAILED

    def test_cleanup_old_plans(self):
        """Test cleaning up old rollback plans."""
        manager = RollbackManager()

        # Create and commit a plan
        plan_id = manager.start_transaction("Old plan")
        manager.commit_transaction()

        # Manually set old date
        plan = manager.rollback_plans[plan_id]
        plan.created_at = datetime(2020, 1, 1)

        removed_count = manager.cleanup_old_plans(days=30)

        assert removed_count == 1
        assert plan_id not in manager.rollback_plans


class TestRecoveryManager:
    """Test recovery workflows and automated remediation."""

    def test_recovery_manager_creation(self):
        """Test creating recovery manager."""
        manager = RecoveryManager()

        assert manager.retry_handler is not None
        assert manager.error_reporter is not None
        assert manager.rollback_manager is not None
        assert len(manager.recovery_plans) > 0

    def test_get_recovery_plan(self):
        """Test getting recovery plan for error."""
        manager = RecoveryManager()

        error = FlowDiscoveryError(
            message="Flow not found", error_code=ErrorCodes.FLOW_NOT_FOUND
        )

        plan = manager._get_recovery_plan(error)

        assert plan is not None
        assert plan.error_code == ErrorCodes.FLOW_NOT_FOUND
        assert len(plan.actions) > 0

    def test_recovery_guidance(self):
        """Test getting recovery guidance."""
        manager = RecoveryManager()

        error = DockerError(
            message="Docker build failed", error_code=ErrorCodes.DOCKER_BUILD_FAILED
        )

        guidance = manager.get_recovery_guidance(error)

        assert len(guidance) > 0
        assert "Recovery Strategy" in guidance[0]
        assert "Recovery Steps:" in guidance

    @patch("subprocess.run")
    def test_recovery_action_execution(self, mock_subprocess):
        """Test executing recovery actions."""
        manager = RecoveryManager()

        # Mock successful subprocess call
        mock_subprocess.return_value = Mock(returncode=0)

        error = FlowDiscoveryError(
            message="Missing dependencies",
            error_code=ErrorCodes.FLOW_MISSING_DEPENDENCIES,
        )

        success, messages = manager.recover_from_error(error, auto_execute=True)

        assert isinstance(success, bool)
        assert isinstance(messages, list)
        assert len(messages) > 0

    def test_file_existence_check(self):
        """Test file existence recovery action."""
        manager = RecoveryManager()

        with tempfile.NamedTemporaryFile() as temp_file:
            error = FlowDiscoveryError(
                message="File not found", context=ErrorContext(file_path=temp_file.name)
            )

            result = manager._check_file_exists(error, {})
            assert result is True

        # Test with non-existent file
        error = FlowDiscoveryError(
            message="File not found",
            context=ErrorContext(file_path="/nonexistent/file.py"),
        )

        result = manager._check_file_exists(error, {})
        assert result is False


class TestIntegration:
    """Integration tests for error handling system."""

    def test_end_to_end_error_handling(self):
        """Test complete error handling workflow."""
        # Create components
        reporter = ErrorReporter()
        rollback_manager = RollbackManager()
        recovery_manager = RecoveryManager(
            error_reporter=reporter, rollback_manager=rollback_manager
        )

        # Simulate an error scenario
        error = DeploymentError(
            message="Deployment creation failed",
            error_code=ErrorCodes.DEPLOYMENT_CREATE_FAILED,
            context=ErrorContext(
                flow_name="test_flow", deployment_name="test_deployment"
            ),
        )

        # Report error
        report = reporter.report_error(error, operation="create_deployment")

        # Start rollback transaction
        plan_id = rollback_manager.start_transaction("Failed deployment cleanup")
        rollback_manager.add_rollback_operation(
            operation_type=OperationType.DEPLOYMENT_CREATE,
            description="Clean up failed deployment",
        )

        # Get recovery guidance
        guidance = recovery_manager.get_recovery_guidance(error)

        # Verify workflow
        assert len(reporter.error_history) == 1
        assert plan_id in rollback_manager.rollback_plans
        assert len(guidance) > 0
        assert report.error == error

    def test_retry_with_rollback(self):
        """Test retry logic combined with rollback."""
        rollback_manager = RollbackManager()
        retry_handler = RetryHandler(RetryPolicies.QUICK_RETRY)

        # Start transaction
        plan_id = rollback_manager.start_transaction("Test operation")

        call_count = 0

        def operation_with_rollback():
            nonlocal call_count
            call_count += 1

            # Add rollback operation on first call
            if call_count == 1:
                rollback_manager.add_rollback_operation(
                    operation_type=OperationType.DEPLOYMENT_CREATE,
                    description="Rollback test operation",
                )

            # Fail on first two attempts
            if call_count < 3:
                raise ConnectionError("Temporary failure")

            # Succeed on third attempt
            rollback_manager.commit_transaction()
            return "success"

        result = retry_handler.retry(operation_with_rollback)

        assert result == "success"
        assert call_count == 3

        # Verify rollback plan was committed
        plan = rollback_manager.rollback_plans[plan_id]
        assert plan.status == OperationStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__])
