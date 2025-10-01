"""
Deployment API

High-level API for deployment operations.
"""

import logging
from typing import Any, Optional

from ..config.deployment_config import DeploymentConfig
from .prefect_client import PrefectClient

logger = logging.getLogger(__name__)


class DeploymentAPI:
    """High-level API for deployment operations."""

    def __init__(self, api_url: Optional[str] = None):
        self.client = PrefectClient(api_url)

    def create_deployment(self, config: DeploymentConfig) -> Optional[str]:
        """Create a deployment from configuration."""
        try:
            deployment_dict = config.to_dict()
            return self.client.run_async(self.client.create_deployment(deployment_dict))
        except Exception as e:
            logger.error(f"Failed to create deployment {config.full_name}: {e}")
            return None

    def update_deployment(self, deployment_id: str, config: DeploymentConfig) -> bool:
        """Update an existing deployment."""
        try:
            deployment_dict = config.to_dict()
            return self.client.run_async(
                self.client.update_deployment(deployment_id, deployment_dict)
            )
        except Exception as e:
            logger.error(f"Failed to update deployment {config.full_name}: {e}")
            return False

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
