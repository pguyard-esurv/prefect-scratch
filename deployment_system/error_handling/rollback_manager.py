"""
Rollback Manager

Provides rollback capabilities for failed deployments with state tracking
and recovery mechanisms.
"""

import logging
import json
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum

from .error_types import DeploymentError, RecoveryError, ErrorContext
from .error_reporter import ErrorReporter

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of operations that can be rolled back."""

    DEPLOYMENT_CREATE = "deployment_create"
    DEPLOYMENT_UPDATE = "deployment_update"
    DEPLOYMENT_DELETE = "deployment_delete"
    DOCKER_IMAGE_BUILD = "docker_image_build"
    DOCKER_IMAGE_PUSH = "docker_image_push"
    CONFIG_UPDATE = "config_update"
    FILE_OPERATION = "file_operation"


class OperationStatus(Enum):
    """Status of rollback operations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RollbackOperation:
    """Represents a single rollback operation."""

    operation_id: str
    operation_type: OperationType
    description: str
    rollback_function: Optional[Callable] = None
    rollback_data: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    status: OperationStatus = OperationStatus.PENDING
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["operation_type"] = self.operation_type.value
        data["status"] = self.status.value
        data["timestamp"] = self.timestamp.isoformat() if self.timestamp else None
        # Remove non-serializable function
        data.pop("rollback_function", None)
        return data


@dataclass
class RollbackPlan:
    """Represents a complete rollback plan."""

    plan_id: str
    description: str
    operations: List[RollbackOperation]
    created_at: datetime
    executed_at: Optional[datetime] = None
    status: OperationStatus = OperationStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "plan_id": self.plan_id,
            "description": self.description,
            "operations": [op.to_dict() for op in self.operations],
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "status": self.status.value,
        }


class RollbackManager:
    """Manages rollback operations for deployment failures."""

    def __init__(
        self,
        state_file: Optional[Path] = None,
        error_reporter: Optional[ErrorReporter] = None,
    ):
        self.state_file = state_file or Path("deployment_rollback_state.json")
        self.error_reporter = error_reporter or ErrorReporter()
        self.rollback_plans: Dict[str, RollbackPlan] = {}
        self.current_plan: Optional[RollbackPlan] = None

        # Load existing state
        self._load_state()

    def start_transaction(self, description: str) -> str:
        """Start a new rollback transaction."""
        plan_id = f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.current_plan = RollbackPlan(
            plan_id=plan_id,
            description=description,
            operations=[],
            created_at=datetime.now(),
        )

        self.rollback_plans[plan_id] = self.current_plan
        self._save_state()

        logger.info(f"Started rollback transaction: {plan_id} - {description}")
        return plan_id

    def add_rollback_operation(
        self,
        operation_type: OperationType,
        description: str,
        rollback_function: Optional[Callable] = None,
        rollback_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a rollback operation to the current transaction."""
        if not self.current_plan:
            raise RecoveryError(
                "No active rollback transaction. Call start_transaction() first.",
                error_code="NO_ACTIVE_TRANSACTION",
            )

        operation_id = (
            f"{self.current_plan.plan_id}_op_{len(self.current_plan.operations) + 1}"
        )

        operation = RollbackOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            description=description,
            rollback_function=rollback_function,
            rollback_data=rollback_data,
        )

        self.current_plan.operations.append(operation)
        self._save_state()

        logger.debug(f"Added rollback operation: {operation_id} - {description}")
        return operation_id

    def commit_transaction(self) -> None:
        """Commit the current transaction (operations succeeded)."""
        if not self.current_plan:
            return

        self.current_plan.status = OperationStatus.COMPLETED
        self.current_plan.executed_at = datetime.now()

        # Mark all operations as completed
        for operation in self.current_plan.operations:
            operation.status = OperationStatus.COMPLETED

        logger.info(f"Committed rollback transaction: {self.current_plan.plan_id}")
        self.current_plan = None
        self._save_state()

    def execute_rollback(self, plan_id: Optional[str] = None) -> bool:
        """Execute rollback operations for a specific plan or current transaction."""
        if plan_id:
            plan = self.rollback_plans.get(plan_id)
            if not plan:
                raise RecoveryError(
                    f"Rollback plan not found: {plan_id}",
                    error_code="ROLLBACK_PLAN_NOT_FOUND",
                )
        else:
            plan = self.current_plan
            if not plan:
                raise RecoveryError(
                    "No active rollback transaction to execute",
                    error_code="NO_ACTIVE_TRANSACTION",
                )

        logger.info(f"Executing rollback plan: {plan.plan_id} - {plan.description}")
        plan.status = OperationStatus.IN_PROGRESS
        plan.executed_at = datetime.now()

        success_count = 0
        failure_count = 0

        # Execute operations in reverse order (LIFO)
        for operation in reversed(plan.operations):
            if operation.status == OperationStatus.COMPLETED:
                # Skip already completed operations
                operation.status = OperationStatus.SKIPPED
                continue

            try:
                operation.status = OperationStatus.IN_PROGRESS
                self._execute_single_rollback(operation)
                operation.status = OperationStatus.COMPLETED
                success_count += 1

                logger.info(f"Rollback operation completed: {operation.description}")

            except Exception as e:
                operation.status = OperationStatus.FAILED
                operation.error_message = str(e)
                failure_count += 1

                logger.error(
                    f"Rollback operation failed: {operation.description} - {e}"
                )

                # Report the error
                self.error_reporter.report_error(
                    error=RecoveryError(
                        f"Rollback operation failed: {operation.description}",
                        error_code="ROLLBACK_OPERATION_FAILED",
                        context=ErrorContext(operation=operation.description),
                        cause=e,
                    ),
                    operation=f"rollback_{operation.operation_type.value}",
                )

        # Update plan status
        if failure_count == 0:
            plan.status = OperationStatus.COMPLETED
            logger.info(f"Rollback plan completed successfully: {plan.plan_id}")
        else:
            plan.status = OperationStatus.FAILED
            logger.error(
                f"Rollback plan completed with failures: {plan.plan_id} "
                f"({success_count} succeeded, {failure_count} failed)"
            )

        self._save_state()
        return failure_count == 0

    def _execute_single_rollback(self, operation: RollbackOperation) -> None:
        """Execute a single rollback operation."""
        if operation.rollback_function:
            # Execute custom rollback function
            if operation.rollback_data:
                operation.rollback_function(**operation.rollback_data)
            else:
                operation.rollback_function()

        elif operation.operation_type == OperationType.DEPLOYMENT_CREATE:
            # Rollback deployment creation by deleting it
            self._rollback_deployment_create(operation)

        elif operation.operation_type == OperationType.DEPLOYMENT_UPDATE:
            # Rollback deployment update by restoring previous version
            self._rollback_deployment_update(operation)

        elif operation.operation_type == OperationType.DOCKER_IMAGE_BUILD:
            # Rollback Docker image build by removing the image
            self._rollback_docker_image_build(operation)

        elif operation.operation_type == OperationType.FILE_OPERATION:
            # Rollback file operations
            self._rollback_file_operation(operation)

        else:
            logger.warning(
                f"No rollback handler for operation type: {operation.operation_type}"
            )

    def _rollback_deployment_create(self, operation: RollbackOperation) -> None:
        """Rollback deployment creation."""
        if not operation.rollback_data:
            raise RecoveryError("No rollback data for deployment creation")

        deployment_id = operation.rollback_data.get("deployment_id")
        if not deployment_id:
            raise RecoveryError("No deployment ID in rollback data")

        # Import here to avoid circular imports
        from ..api.deployment_api import DeploymentAPI

        api = DeploymentAPI()
        success = api.delete_deployment(deployment_id)

        if not success:
            raise RecoveryError(f"Failed to delete deployment: {deployment_id}")

    def _rollback_deployment_update(self, operation: RollbackOperation) -> None:
        """Rollback deployment update."""
        if not operation.rollback_data:
            raise RecoveryError("No rollback data for deployment update")

        deployment_id = operation.rollback_data.get("deployment_id")
        previous_config = operation.rollback_data.get("previous_config")

        if not deployment_id or not previous_config:
            raise RecoveryError("Incomplete rollback data for deployment update")

        # Import here to avoid circular imports
        from ..api.deployment_api import DeploymentAPI
        from ..config.deployment_config import DeploymentConfig

        api = DeploymentAPI()
        config = DeploymentConfig.from_dict(previous_config)
        success = api.update_deployment(deployment_id, config)

        if not success:
            raise RecoveryError(
                f"Failed to rollback deployment update: {deployment_id}"
            )

    def _rollback_docker_image_build(self, operation: RollbackOperation) -> None:
        """Rollback Docker image build."""
        if not operation.rollback_data:
            raise RecoveryError("No rollback data for Docker image build")

        image_name = operation.rollback_data.get("image_name")
        if not image_name:
            raise RecoveryError("No image name in rollback data")

        # Remove the Docker image
        import subprocess

        try:
            subprocess.run(
                ["docker", "rmi", image_name], check=True, capture_output=True
            )
        except subprocess.CalledProcessError as e:
            raise RecoveryError(f"Failed to remove Docker image {image_name}: {e}")

    def _rollback_file_operation(self, operation: RollbackOperation) -> None:
        """Rollback file operations."""
        if not operation.rollback_data:
            raise RecoveryError("No rollback data for file operation")

        operation_type = operation.rollback_data.get("type")
        file_path = operation.rollback_data.get("file_path")

        if operation_type == "create" and file_path:
            # Remove created file
            Path(file_path).unlink(missing_ok=True)

        elif operation_type == "update" and file_path:
            # Restore previous content
            previous_content = operation.rollback_data.get("previous_content")
            if previous_content is not None:
                Path(file_path).write_text(previous_content)

        elif operation_type == "delete" and file_path:
            # Restore deleted file
            previous_content = operation.rollback_data.get("previous_content")
            if previous_content is not None:
                Path(file_path).write_text(previous_content)

    def get_rollback_plans(self) -> List[RollbackPlan]:
        """Get all rollback plans."""
        return list(self.rollback_plans.values())

    def get_failed_plans(self) -> List[RollbackPlan]:
        """Get rollback plans that failed."""
        return [
            plan
            for plan in self.rollback_plans.values()
            if plan.status == OperationStatus.FAILED
        ]

    def cleanup_old_plans(self, days: int = 30) -> int:
        """Clean up rollback plans older than specified days."""
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

        plans_to_remove = []
        for plan_id, plan in self.rollback_plans.items():
            if (
                plan.created_at < cutoff_date
                and plan.status == OperationStatus.COMPLETED
            ):
                plans_to_remove.append(plan_id)

        for plan_id in plans_to_remove:
            del self.rollback_plans[plan_id]

        if plans_to_remove:
            self._save_state()

        return len(plans_to_remove)

    def _save_state(self) -> None:
        """Save rollback state to file."""
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Save state
            state_data = {
                "rollback_plans": {
                    plan_id: plan.to_dict()
                    for plan_id, plan in self.rollback_plans.items()
                },
                "current_plan_id": (
                    self.current_plan.plan_id if self.current_plan else None
                ),
                "last_updated": datetime.now().isoformat(),
            }

            with open(self.state_file, "w") as f:
                json.dump(state_data, f, indent=2)

        except Exception as e:
            logger.warning(f"Failed to save rollback state: {e}")

    def _load_state(self) -> None:
        """Load rollback state from file."""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file, "r") as f:
                state_data = json.load(f)

            # Load rollback plans
            for plan_id, plan_data in state_data.get("rollback_plans", {}).items():
                operations = []
                for op_data in plan_data.get("operations", []):
                    operation = RollbackOperation(
                        operation_id=op_data["operation_id"],
                        operation_type=OperationType(op_data["operation_type"]),
                        description=op_data["description"],
                        rollback_data=op_data.get("rollback_data"),
                        timestamp=(
                            datetime.fromisoformat(op_data["timestamp"])
                            if op_data.get("timestamp")
                            else None
                        ),
                        status=OperationStatus(op_data["status"]),
                        error_message=op_data.get("error_message"),
                    )
                    operations.append(operation)

                plan = RollbackPlan(
                    plan_id=plan_data["plan_id"],
                    description=plan_data["description"],
                    operations=operations,
                    created_at=datetime.fromisoformat(plan_data["created_at"]),
                    executed_at=(
                        datetime.fromisoformat(plan_data["executed_at"])
                        if plan_data.get("executed_at")
                        else None
                    ),
                    status=OperationStatus(plan_data["status"]),
                )

                self.rollback_plans[plan_id] = plan

            # Set current plan if specified
            current_plan_id = state_data.get("current_plan_id")
            if current_plan_id and current_plan_id in self.rollback_plans:
                self.current_plan = self.rollback_plans[current_plan_id]

        except Exception as e:
            logger.warning(f"Failed to load rollback state: {e}")


# Global rollback manager instance
_global_rollback_manager: Optional[RollbackManager] = None


def get_global_rollback_manager() -> RollbackManager:
    """Get or create global rollback manager instance."""
    global _global_rollback_manager
    if _global_rollback_manager is None:
        _global_rollback_manager = RollbackManager()
    return _global_rollback_manager
