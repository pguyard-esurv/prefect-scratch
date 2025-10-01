"""
Prefect Client

Provides a wrapper around Prefect API client for deployment operations.
"""

import asyncio
import logging
from typing import Any, Optional

from prefect import get_client
from prefect.exceptions import ObjectNotFound

logger = logging.getLogger(__name__)


class PrefectClient:
    """Wrapper around Prefect API client for deployment operations."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url
        self._client = None

    async def get_client(self):
        """Get or create Prefect client."""
        if self._client is None:
            if self.api_url:
                self._client = get_client(api_url=self.api_url)
            else:
                self._client = get_client()
        return self._client

    async def create_deployment(
        self, deployment_config: dict[str, Any]
    ) -> Optional[str]:
        """Create a deployment using Prefect API."""
        try:
            client = await self.get_client()

            # First, ensure the flow exists
            flow_name = deployment_config.get("flow_name")
            if not flow_name:
                raise ValueError("Flow name is required for deployment creation")

            # Get or create the flow
            try:
                flow = await client.read_flow_by_name(flow_name)
                logger.info(f"Found existing flow: {flow_name}")
            except ObjectNotFound:
                logger.warning(
                    f"Flow {flow_name} not found. It may need to be registered first."
                )
                return None

            # Create deployment
            deployment_data = {
                "name": deployment_config["name"],
                "flow_id": flow.id,
                "entrypoint": deployment_config.get("entrypoint"),
                "work_pool_name": deployment_config.get("work_pool_name"),
                "schedule": deployment_config.get("schedule"),
                "parameters": deployment_config.get("parameters", {}),
                "job_variables": deployment_config.get("job_variables", {}),
                "tags": deployment_config.get("tags", []),
                "description": deployment_config.get("description", ""),
                "version": deployment_config.get("version", "1.0.0"),
            }

            deployment_id = await client.create_deployment(**deployment_data)
            logger.info(
                f"Created deployment {deployment_config['name']} with ID: {deployment_id}"
            )
            return str(deployment_id)

        except Exception as e:
            logger.error(
                f"Failed to create deployment {deployment_config.get('name', 'unknown')}: {e}"
            )
            raise

    async def update_deployment(
        self, deployment_id: str, deployment_config: dict[str, Any]
    ) -> bool:
        """Update an existing deployment."""
        try:
            client = await self.get_client()

            # Get existing deployment
            deployment = await client.read_deployment(deployment_id)

            # Update deployment data
            update_data = {
                "entrypoint": deployment_config.get(
                    "entrypoint", deployment.entrypoint
                ),
                "work_pool_name": deployment_config.get(
                    "work_pool_name", deployment.work_pool_name
                ),
                "schedule": deployment_config.get("schedule", deployment.schedule),
                "parameters": deployment_config.get(
                    "parameters", deployment.parameters
                ),
                "job_variables": deployment_config.get(
                    "job_variables", deployment.job_variables
                ),
                "tags": deployment_config.get("tags", deployment.tags),
                "description": deployment_config.get(
                    "description", deployment.description
                ),
                "version": deployment_config.get("version", deployment.version),
            }

            await client.update_deployment(deployment_id, **update_data)
            logger.info(f"Updated deployment {deployment.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to update deployment {deployment_id}: {e}")
            return False

    async def delete_deployment(self, deployment_id: str) -> bool:
        """Delete a deployment."""
        try:
            client = await self.get_client()
            await client.delete_deployment(deployment_id)
            logger.info(f"Deleted deployment {deployment_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete deployment {deployment_id}: {e}")
            return False

    async def list_deployments(
        self, flow_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List deployments, optionally filtered by flow name."""
        try:
            client = await self.get_client()

            if flow_name:
                # Get deployments for specific flow
                try:
                    flow = await client.read_flow_by_name(flow_name)
                    deployments = await client.read_deployments(
                        flow_filter={"id": {"any_": [flow.id]}}
                    )
                except ObjectNotFound:
                    logger.warning(f"Flow {flow_name} not found")
                    return []
            else:
                # Get all deployments
                deployments = await client.read_deployments()

            return [
                {
                    "id": str(deployment.id),
                    "name": deployment.name,
                    "flow_name": deployment.flow_name,
                    "work_pool_name": deployment.work_pool_name,
                    "schedule": deployment.schedule,
                    "tags": deployment.tags,
                    "created": deployment.created,
                    "updated": deployment.updated,
                }
                for deployment in deployments
            ]

        except Exception as e:
            logger.error(f"Failed to list deployments: {e}")
            return []

    async def get_deployment_by_name(
        self, deployment_name: str, flow_name: str
    ) -> Optional[dict[str, Any]]:
        """Get a deployment by name and flow name."""
        try:
            client = await self.get_client()
            deployment = await client.read_deployment_by_name(
                f"{flow_name}/{deployment_name}"
            )

            return {
                "id": str(deployment.id),
                "name": deployment.name,
                "flow_name": deployment.flow_name,
                "entrypoint": deployment.entrypoint,
                "work_pool_name": deployment.work_pool_name,
                "schedule": deployment.schedule,
                "parameters": deployment.parameters,
                "job_variables": deployment.job_variables,
                "tags": deployment.tags,
                "description": deployment.description,
                "version": deployment.version,
                "created": deployment.created,
                "updated": deployment.updated,
            }

        except ObjectNotFound:
            logger.info(f"Deployment {flow_name}/{deployment_name} not found")
            return None
        except Exception as e:
            logger.error(f"Failed to get deployment {flow_name}/{deployment_name}: {e}")
            return None

    async def deployment_exists(self, deployment_name: str, flow_name: str) -> bool:
        """Check if a deployment exists."""
        deployment = await self.get_deployment_by_name(deployment_name, flow_name)
        return deployment is not None

    async def validate_work_pool(self, work_pool_name: str) -> bool:
        """Validate that a work pool exists."""
        try:
            client = await self.get_client()
            work_pool = await client.read_work_pool(work_pool_name)
            return work_pool is not None
        except ObjectNotFound:
            return False
        except Exception as e:
            logger.error(f"Failed to validate work pool {work_pool_name}: {e}")
            return False

    def run_async(self, coro):
        """Helper to run async operations in sync context."""
        try:
            # Check if we're already in an async context
            asyncio.get_running_loop()
            # If we get here, we're in an async context, which means we can't use run_until_complete
            # This should not happen in our sync context, but handle it gracefully
            raise RuntimeError(
                "Cannot run async operation from within an async context"
            )
        except RuntimeError:
            # No running loop, we're in sync context - this is expected
            # Use asyncio.run() for Python 3.7+ which handles loop creation/cleanup
            return asyncio.run(coro)
