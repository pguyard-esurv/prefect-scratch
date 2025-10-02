"""
Deployment API

High-level API for deployment operations with comprehensive error handling.
"""

import logging
from typing import Any, Optional

from ..config.deployment_config import DeploymentConfig
from .prefect_client import PrefectClient
from ..error_handling import (
    DeploymentError,
    PrefectAPIError,
    ErrorContext,
    ErrorCodes,
    RetryHandler,
    RetryPolicies,
    ErrorReporter,
    RollbackManager,
    OperationType,
    with_retry,
)

logger = logging.getLogger(__name__)


class DeploymentAPI:
    """High-level API for deployment operations with error handling and recovery."""

    def __init__(self, api_url: Optional[str] = None):
        self.client = PrefectClient(api_url)
        self.retry_handler = RetryHandler(RetryPolicies.NETWORK_RETRY)
        self.error_reporter = ErrorReporter()
        self.rollback_manager = RollbackManager()

    def create_deployment(self, config: DeploymentConfig) -> Optional[str]:
        """Create a deployment from configuration with error handling and rollback."""
        context = ErrorContext(
            deployment_name=config.deployment_name,
            flow_name=config.flow_name,
            environment=getattr(config, "environment", "unknown"),
            operation="create_deployment",
        )

        # Start rollback transaction
        rollback_id = self.rollback_manager.start_transaction(
            f"Create deployment {config.full_name}"
        )

        try:
            deployment_dict = config.to_dict()

            # Use retry handler for the API call
            deployment_id = self.retry_handler.retry(
                self.client.run_async, self.client.create_deployment(deployment_dict)
            )

            if deployment_id:
                # Add rollback operation for successful creation
                self.rollback_manager.add_rollback_operation(
                    operation_type=OperationType.DEPLOYMENT_CREATE,
                    description=f"Delete deployment {config.full_name}",
                    rollback_data={"deployment_id": deployment_id},
                )

                # Commit transaction on success
                self.rollback_manager.commit_transaction()
                logger.info(f"Successfully created deployment: {config.full_name}")
                return deployment_id
            else:
                raise DeploymentError(
                    f"Failed to create deployment: {config.full_name}",
                    error_code=ErrorCodes.DEPLOYMENT_CREATE_FAILED,
                    context=context,
                    remediation="Check Prefect server connectivity and deployment configuration",
                )

        except Exception as e:
            # Report error with context
            error = PrefectAPIError(
                f"Failed to create deployment {config.full_name}: {str(e)}",
                error_code=ErrorCodes.DEPLOYMENT_CREATE_FAILED,
                context=context,
                remediation="Check Prefect server status and deployment configuration",
                cause=e,
            )

            self.error_reporter.report_error(
                error=error,
                operation="create_deployment",
                additional_context={"config": config.to_dict()},
            )

            # Execute rollback
            try:
                self.rollback_manager.execute_rollback(rollback_id)
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")

            raise error

    def update_deployment(self, deployment_id: str, config: DeploymentConfig) -> bool:
        """Update an existing deployment with rollback capability."""
        context = ErrorContext(
            deployment_name=config.deployment_name,
            flow_name=config.flow_name,
            environment=getattr(config, "environment", "unknown"),
            operation="update_deployment",
        )

        # Start rollback transaction
        rollback_id = self.rollback_manager.start_transaction(
            f"Update deployment {config.full_name}"
        )

        try:
            # Get current deployment configuration for rollback
            current_deployment = self.retry_handler.retry(
                self.client.run_async,
                self.client.get_deployment_by_name(
                    config.deployment_name, config.flow_name
                ),
            )

            if current_deployment:
                # Add rollback operation with previous configuration
                self.rollback_manager.add_rollback_operation(
                    operation_type=OperationType.DEPLOYMENT_UPDATE,
                    description=f"Restore previous configuration for {config.full_name}",
                    rollback_data={
                        "deployment_id": deployment_id,
                        "previous_config": current_deployment,
                    },
                )

            # Update deployment
            deployment_dict = config.to_dict()
            success = self.retry_handler.retry(
                self.client.run_async,
                self.client.update_deployment(deployment_id, deployment_dict),
            )

            if success:
                self.rollback_manager.commit_transaction()
                logger.info(f"Successfully updated deployment: {config.full_name}")
                return True
            else:
                raise DeploymentError(
                    f"Failed to update deployment: {config.full_name}",
                    error_code=ErrorCodes.DEPLOYMENT_UPDATE_FAILED,
                    context=context,
                    remediation="Check deployment configuration and Prefect server status",
                )

        except Exception as e:
            # Report error
            error = PrefectAPIError(
                f"Failed to update deployment {config.full_name}: {str(e)}",
                error_code=ErrorCodes.DEPLOYMENT_UPDATE_FAILED,
                context=context,
                remediation="Check Prefect server status and deployment configuration",
                cause=e,
            )

            self.error_reporter.report_error(
                error=error,
                operation="update_deployment",
                additional_context={"config": config.to_dict()},
            )

            # Execute rollback
            try:
                self.rollback_manager.execute_rollback(rollback_id)
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")

            raise error

    def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment."""
        try:
            return self.client.run_async(self.client.delete_deployment(deployment_id))
        except Exception as e:
            logger.error(f"Failed to delete deployment {deployment_id}: {e}")
            return False

    def deployment_exists(self, config: DeploymentConfig) -> bool:
        """Check if a deployment exists."""
        try:
            return self.client.run_async(
                self.client.deployment_exists(config.deployment_name, config.flow_name)
            )
        except Exception as e:
            logger.error(
                f"Failed to check if deployment {config.full_name} exists: {e}"
            )
            return False

    def get_deployment(self, config: DeploymentConfig) -> Optional[dict[str, Any]]:
        """Get deployment information."""
        try:
            return self.client.run_async(
                self.client.get_deployment_by_name(
                    config.deployment_name, config.flow_name
                )
            )
        except Exception as e:
            logger.error(f"Failed to get deployment {config.full_name}: {e}")
            return None

    def list_deployments(self, flow_name: Optional[str] = None) -> list[dict[str, Any]]:
        """List deployments."""
        try:
            return self.client.run_async(self.client.list_deployments(flow_name))
        except Exception as e:
            logger.error(f"Failed to list deployments: {e}")
            return []

    def validate_work_pool(self, work_pool_name: str) -> bool:
        """Validate that a work pool exists."""
        try:
            return self.client.run_async(self.client.validate_work_pool(work_pool_name))
        except Exception as e:
            logger.error(f"Failed to validate work pool {work_pool_name}: {e}")
            return False

    def create_or_update_deployment(self, config: DeploymentConfig) -> Optional[str]:
        """Create a new deployment or update existing one."""
        try:
            # Check if deployment exists
            existing = self.get_deployment(config)

            if existing:
                # Update existing deployment
                deployment_id = existing["id"]
                success = self.update_deployment(deployment_id, config)
                if success:
                    logger.info(f"Updated existing deployment {config.full_name}")
                    return deployment_id
                else:
                    logger.error(f"Failed to update deployment {config.full_name}")
                    return None
            else:
                # Create new deployment
                deployment_id = self.create_deployment(config)
                if deployment_id:
                    logger.info(f"Created new deployment {config.full_name}")
                    return deployment_id
                else:
                    logger.error(f"Failed to create deployment {config.full_name}")
                    return None

        except Exception as e:
            logger.error(
                f"Failed to create or update deployment {config.full_name}: {e}"
            )
            return None

    def bulk_create_deployments(
        self, configs: list[DeploymentConfig]
    ) -> dict[str, Any]:
        """Create multiple deployments."""
        results = {"successful": [], "failed": [], "updated": [], "created": []}

        for config in configs:
            try:
                existing = self.get_deployment(config)
                deployment_id = self.create_or_update_deployment(config)

                if deployment_id:
                    results["successful"].append(
                        {
                            "name": config.full_name,
                            "id": deployment_id,
                            "action": "updated" if existing else "created",
                        }
                    )

                    if existing:
                        results["updated"].append(config.full_name)
                    else:
                        results["created"].append(config.full_name)
                else:
                    results["failed"].append(
                        {
                            "name": config.full_name,
                            "error": "Failed to create or update deployment",
                        }
                    )

            except Exception as e:
                results["failed"].append({"name": config.full_name, "error": str(e)})

        return results

    def cleanup_deployments(
        self, pattern: Optional[str] = None, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Clean up deployments matching pattern."""
        results = {"deleted": [], "failed": [], "total_deleted": 0}

        try:
            deployments = self.list_deployments(flow_name)

            for deployment in deployments:
                deployment_name = deployment["name"]

                # Apply pattern filter if provided
                if pattern and pattern not in deployment_name:
                    continue

                # Delete deployment
                success = self.delete_deployment(deployment["id"])

                if success:
                    results["deleted"].append(deployment_name)
                    results["total_deleted"] += 1
                else:
                    results["failed"].append(
                        {
                            "name": deployment_name,
                            "error": "Failed to delete deployment",
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to cleanup deployments: {e}")
            results["failed"].append({"name": "cleanup_operation", "error": str(e)})

        return results
