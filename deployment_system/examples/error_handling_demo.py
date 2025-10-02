"""
Error Handling and Recovery Demo

Demonstrates the comprehensive error handling, retry logic, rollback capabilities,
and recovery mechanisms in the deployment system.
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

from ..error_handling import (
    DeploymentError,
    FlowDiscoveryError,
    DockerError,
    PrefectAPIError,
    ErrorContext,
    ErrorCodes,
    RetryHandler,
    RetryPolicies,
    ErrorReporter,
    RollbackManager,
    RecoveryManager,
    OperationType,
    get_global_reporter,
    get_global_rollback_manager,
)
from ..discovery.flow_scanner import FlowScanner
from ..builders.docker_builder import DockerDeploymentCreator
from ..api.deployment_api import DeploymentAPI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ErrorHandlingDemo:
    """Demonstrates error handling capabilities."""

    def __init__(self):
        self.error_reporter = ErrorReporter()
        self.rollback_manager = RollbackManager()
        self.recovery_manager = RecoveryManager(
            error_reporter=self.error_reporter, rollback_manager=self.rollback_manager
        )
        self.retry_handler = RetryHandler(RetryPolicies.STANDARD_RETRY)

    def demo_flow_discovery_errors(self):
        """Demonstrate flow discovery error handling."""
        print("\n" + "=" * 60)
        print("DEMO: Flow Discovery Error Handling")
        print("=" * 60)

        # Test with non-existent directory
        scanner = FlowScanner(base_path="nonexistent_flows")

        try:
            flows = scanner.scan_flows()
            print(f"Scanned flows: {len(flows)}")
        except FlowDiscoveryError as e:
            print(f"Caught FlowDiscoveryError: {e.message}")
            print(f"Error Code: {e.error_code}")
            print(f"Remediation: {e.remediation}")

            # Get recovery guidance
            guidance = self.recovery_manager.get_recovery_guidance(e)
            print("\nRecovery Guidance:")
            for line in guidance:
                print(f"  {line}")

    def demo_docker_build_errors(self):
        """Demonstrate Docker build error handling."""
        print("\n" + "=" * 60)
        print("DEMO: Docker Build Error Handling")
        print("=" * 60)

        # Create a mock flow metadata with invalid Dockerfile
        from ..discovery.metadata import FlowMetadata

        mock_flow = FlowMetadata(
            name="test_flow",
            path="/fake/path/test_flow.py",
            module_path="test_flow",
            function_name="test_function",
            dockerfile_path="/nonexistent/Dockerfile",
        )

        builder = DockerDeploymentCreator()

        try:
            success = builder.build_docker_image(mock_flow)
            print(f"Build result: {success}")
        except DockerError as e:
            print(f"Caught DockerError: {e.message}")
            print(f"Error Code: {e.error_code}")
            print(f"Remediation: {e.remediation}")

            # Attempt recovery
            success, messages = self.recovery_manager.recover_from_error(
                e, auto_execute=True
            )
            print(f"\nRecovery attempt: {'Success' if success else 'Failed'}")
            for message in messages:
                print(f"  {message}")

    def demo_retry_logic(self):
        """Demonstrate retry logic with different scenarios."""
        print("\n" + "=" * 60)
        print("DEMO: Retry Logic")
        print("=" * 60)

        # Simulate a flaky operation that succeeds after retries
        attempt_count = 0

        def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            print(f"  Attempt {attempt_count}")

            if attempt_count < 3:
                raise ConnectionError("Temporary network issue")
            return f"Success after {attempt_count} attempts"

        try:
            result = self.retry_handler.retry(flaky_operation)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Failed after retries: {e}")

        # Reset for next demo
        attempt_count = 0

        # Simulate operation that always fails
        def always_failing_operation():
            nonlocal attempt_count
            attempt_count += 1
            print(f"  Attempt {attempt_count} (will fail)")
            raise ValueError("This operation always fails")

        print("\nTesting non-retryable error:")
        try:
            result = self.retry_handler.retry(always_failing_operation)
        except ValueError as e:
            print(f"Immediately failed (non-retryable): {e}")

    def demo_rollback_operations(self):
        """Demonstrate rollback capabilities."""
        print("\n" + "=" * 60)
        print("DEMO: Rollback Operations")
        print("=" * 60)

        # Start a transaction
        plan_id = self.rollback_manager.start_transaction("Demo deployment operation")
        print(f"Started rollback transaction: {plan_id}")

        # Simulate operations with rollback
        operations_performed = []

        try:
            # Operation 1: Create deployment
            print("  Performing operation 1: Create deployment")
            deployment_id = "demo_deployment_123"
            operations_performed.append("create_deployment")

            self.rollback_manager.add_rollback_operation(
                operation_type=OperationType.DEPLOYMENT_CREATE,
                description=f"Delete deployment {deployment_id}",
                rollback_data={"deployment_id": deployment_id},
            )

            # Operation 2: Build Docker image
            print("  Performing operation 2: Build Docker image")
            image_name = "demo_image:latest"
            operations_performed.append("build_image")

            self.rollback_manager.add_rollback_operation(
                operation_type=OperationType.DOCKER_IMAGE_BUILD,
                description=f"Remove Docker image {image_name}",
                rollback_data={"image_name": image_name},
            )

            # Simulate failure on operation 3
            print("  Performing operation 3: Update configuration (will fail)")
            raise Exception("Configuration update failed")

        except Exception as e:
            print(f"  Operation failed: {e}")
            print("  Executing rollback...")

            # Execute rollback
            success = self.rollback_manager.execute_rollback(plan_id)
            print(f"  Rollback {'succeeded' if success else 'failed'}")

            # Show rollback plan details
            plan = self.rollback_manager.rollback_plans[plan_id]
            print(f"  Rollback plan status: {plan.status.value}")
            for i, op in enumerate(plan.operations, 1):
                print(f"    {i}. {op.description} - {op.status.value}")

    def demo_comprehensive_error_workflow(self):
        """Demonstrate complete error handling workflow."""
        print("\n" + "=" * 60)
        print("DEMO: Comprehensive Error Workflow")
        print("=" * 60)

        # Simulate a complex deployment operation that fails
        context = ErrorContext(
            flow_name="demo_flow",
            deployment_name="demo_deployment",
            environment="development",
            operation="comprehensive_deployment",
        )

        # Start rollback transaction
        plan_id = self.rollback_manager.start_transaction(
            "Comprehensive deployment demo"
        )

        try:
            # Step 1: Validate flow
            print("  Step 1: Validating flow...")
            # Simulate validation failure
            raise FlowDiscoveryError(
                "Flow validation failed: missing dependencies",
                error_code=ErrorCodes.FLOW_MISSING_DEPENDENCIES,
                context=context,
                remediation="Install missing dependencies from requirements.txt",
            )

        except FlowDiscoveryError as e:
            # Report the error
            print(f"  Error occurred: {e.message}")
            error_report = self.error_reporter.report_error(
                error=e,
                operation="comprehensive_deployment",
                additional_context={"step": "flow_validation"},
            )

            # Attempt automated recovery
            print("  Attempting automated recovery...")
            success, recovery_messages = self.recovery_manager.recover_from_error(
                e, context={"flow_path": "/demo/flow.py"}, auto_execute=True
            )

            print(f"  Recovery {'succeeded' if success else 'failed'}")
            for message in recovery_messages:
                print(f"    {message}")

            # Execute rollback if recovery failed
            if not success:
                print("  Executing rollback due to recovery failure...")
                rollback_success = self.rollback_manager.execute_rollback(plan_id)
                print(f"  Rollback {'succeeded' if rollback_success else 'failed'}")

        # Show error summary
        print("\n  Error Summary:")
        summary = self.error_reporter.get_error_summary()
        print(f"    Total errors: {summary['total_errors']}")
        for category, count in summary["by_category"].items():
            print(f"    {category}: {count}")

    def demo_error_reporting(self):
        """Demonstrate error reporting capabilities."""
        print("\n" + "=" * 60)
        print("DEMO: Error Reporting")
        print("=" * 60)

        # Generate various types of errors
        errors = [
            FlowDiscoveryError(
                "Flow file not found",
                error_code=ErrorCodes.FLOW_NOT_FOUND,
                context=ErrorContext(
                    flow_name="missing_flow", file_path="/missing/flow.py"
                ),
            ),
            DockerError(
                "Docker build failed",
                error_code=ErrorCodes.DOCKER_BUILD_FAILED,
                context=ErrorContext(flow_name="docker_flow", file_path="Dockerfile"),
            ),
            PrefectAPIError(
                "API connection timeout",
                error_code=ErrorCodes.PREFECT_API_UNAVAILABLE,
                context=ErrorContext(operation="create_deployment"),
            ),
        ]

        # Report all errors
        for i, error in enumerate(errors, 1):
            print(f"  Reporting error {i}: {error.message}")
            self.error_reporter.report_error(
                error=error, operation=f"demo_operation_{i}"
            )

        # Show formatted error messages
        print("\n  User-friendly error messages:")
        for error in errors:
            formatted = self.error_reporter.format_user_friendly_error(error)
            print(f"    {formatted}")

        # Print error summary
        print("\n  Error Summary:")
        self.error_reporter.print_error_summary()

    async def demo_async_retry(self):
        """Demonstrate async retry functionality."""
        print("\n" + "=" * 60)
        print("DEMO: Async Retry Logic")
        print("=" * 60)

        attempt_count = 0

        async def async_flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            print(f"  Async attempt {attempt_count}")

            if attempt_count < 3:
                raise ConnectionError("Async network issue")

            # Simulate async work
            await asyncio.sleep(0.1)
            return f"Async success after {attempt_count} attempts"

        try:
            result = await self.retry_handler.async_retry(async_flaky_operation)
            print(f"Async result: {result}")
        except Exception as e:
            print(f"Async operation failed: {e}")

    def run_all_demos(self):
        """Run all error handling demos."""
        print("🚀 Starting Error Handling and Recovery Demo")
        print("This demo showcases the comprehensive error handling system")

        try:
            # Run synchronous demos
            self.demo_flow_discovery_errors()
            self.demo_docker_build_errors()
            self.demo_retry_logic()
            self.demo_rollback_operations()
            self.demo_comprehensive_error_workflow()
            self.demo_error_reporting()

            # Run async demo
            asyncio.run(self.demo_async_retry())

            print("\n" + "=" * 60)
            print("DEMO COMPLETE")
            print("=" * 60)
            print("✅ All error handling demos completed successfully!")
            print("\nKey features demonstrated:")
            print("  • Comprehensive error types with context")
            print("  • Retry logic with exponential backoff")
            print("  • Rollback capabilities for failed operations")
            print("  • Automated recovery workflows")
            print("  • Detailed error reporting and logging")
            print("  • User-friendly error messages")
            print("  • Async retry support")

        except Exception as e:
            print(f"\n❌ Demo failed with error: {e}")

            # Use our own error handling for demo failures
            demo_error = DeploymentError(
                f"Error handling demo failed: {str(e)}",
                error_code="DEMO_FAILURE",
                context=ErrorContext(operation="run_demos"),
                remediation="Check demo setup and dependencies",
            )

            formatted_error = self.error_reporter.format_user_friendly_error(demo_error)
            print(f"\n{formatted_error}")


def main():
    """Run the error handling demo."""
    demo = ErrorHandlingDemo()
    demo.run_all_demos()


if __name__ == "__main__":
    main()
