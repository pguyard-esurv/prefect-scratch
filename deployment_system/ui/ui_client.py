"""
UI Client

Provides utilities for interacting with Prefect UI and checking deployment visibility.
"""

import asyncio
import logging
import time
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx

from ..api.prefect_client import PrefectClient

logger = logging.getLogger(__name__)


class UIClient:
    """Client for interacting with Prefect UI and verifying deployment visibility."""

    def __init__(self, api_url: Optional[str] = None, ui_url: Optional[str] = None):
        self.api_url = api_url
        self.ui_url = ui_url or self._derive_ui_url(api_url)
        self.prefect_client = PrefectClient(api_url)
        self._http_client = None

    def _derive_ui_url(self, api_url: Optional[str]) -> Optional[str]:
        """Derive UI URL from API URL."""
        if not api_url:
            return None

        try:
            parsed = urlparse(api_url)
            # Remove /api suffix if present
            path = parsed.path.rstrip("/api")
            ui_url = f"{parsed.scheme}://{parsed.netloc}{path}"
            return ui_url
        except Exception as e:
            logger.warning(f"Could not derive UI URL from API URL {api_url}: {e}")
            return None

    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self):
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def check_api_connectivity(self) -> dict[str, Any]:
        """Check connectivity to Prefect API."""
        result = {
            "connected": False,
            "api_url": self.api_url,
            "response_time_ms": None,
            "version": None,
            "error": None,
        }

        try:
            start_time = time.time()
            client = await self.prefect_client.get_client()

            # Try to get server version/info
            try:
                # This is a simple API call to test connectivity
                await client.read_flows(limit=1)
                result["connected"] = True
                result["response_time_ms"] = int((time.time() - start_time) * 1000)

                # Try to get version info if available
                try:
                    http_client = await self.get_http_client()
                    if self.api_url:
                        version_url = urljoin(self.api_url.rstrip("/"), "/health")
                        response = await http_client.get(version_url)
                        if response.status_code == 200:
                            health_data = response.json()
                            result["version"] = health_data.get("version")
                except Exception:
                    # Version info is optional
                    pass

            except Exception as e:
                result["error"] = f"API call failed: {str(e)}"

        except Exception as e:
            result["error"] = f"Connection failed: {str(e)}"

        return result

    async def check_ui_accessibility(self) -> dict[str, Any]:
        """Check if Prefect UI is accessible."""
        result = {
            "accessible": False,
            "ui_url": self.ui_url,
            "response_time_ms": None,
            "status_code": None,
            "error": None,
        }

        if not self.ui_url:
            result["error"] = "UI URL not configured"
            return result

        try:
            start_time = time.time()
            http_client = await self.get_http_client()

            response = await http_client.get(self.ui_url)
            result["status_code"] = response.status_code
            result["response_time_ms"] = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                result["accessible"] = True
            else:
                result["error"] = f"HTTP {response.status_code}"

        except Exception as e:
            result["error"] = f"Request failed: {str(e)}"

        return result

    async def verify_deployment_in_ui(
        self, deployment_name: str, flow_name: str, timeout_seconds: int = 30
    ) -> dict[str, Any]:
        """Verify that a deployment appears in the Prefect UI."""
        result = {
            "visible": False,
            "deployment_name": deployment_name,
            "flow_name": flow_name,
            "full_name": f"{flow_name}/{deployment_name}",
            "api_exists": False,
            "ui_accessible": False,
            "wait_time_seconds": 0,
            "error": None,
        }

        try:
            # First check if deployment exists via API
            deployment = await self.prefect_client.get_deployment_by_name(
                deployment_name, flow_name
            )

            if not deployment:
                result["error"] = "Deployment not found via API"
                return result

            result["api_exists"] = True

            # Check UI accessibility
            ui_check = await self.check_ui_accessibility()
            result["ui_accessible"] = ui_check["accessible"]

            if not result["ui_accessible"]:
                result["error"] = (
                    f"UI not accessible: {ui_check.get('error', 'Unknown error')}"
                )
                return result

            # Wait for deployment to appear in UI (deployments may take time to sync)
            start_time = time.time()
            while time.time() - start_time < timeout_seconds:
                # Check if deployment is visible via API (this is the best we can do
                # without actually parsing the UI HTML/JavaScript)
                current_deployment = await self.prefect_client.get_deployment_by_name(
                    deployment_name, flow_name
                )

                if current_deployment and current_deployment.get("updated"):
                    # If deployment exists and has been updated, it should be visible
                    result["visible"] = True
                    result["wait_time_seconds"] = int(time.time() - start_time)
                    break

                await asyncio.sleep(1)

            if not result["visible"]:
                result["error"] = (
                    f"Deployment not visible after {timeout_seconds} seconds"
                )

        except Exception as e:
            result["error"] = f"Verification failed: {str(e)}"

        return result

    async def get_deployment_ui_url(
        self, deployment_name: str, flow_name: str
    ) -> Optional[str]:
        """Get the direct URL to a deployment in the Prefect UI."""
        if not self.ui_url:
            return None

        try:
            deployment = await self.prefect_client.get_deployment_by_name(
                deployment_name, flow_name
            )

            if deployment:
                deployment_id = deployment["id"]
                return urljoin(
                    self.ui_url.rstrip("/"), f"/deployments/deployment/{deployment_id}"
                )

        except Exception as e:
            logger.error(f"Failed to get deployment UI URL: {e}")

        return None

    async def list_deployments_with_ui_status(
        self, flow_name: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List deployments with their UI visibility status."""
        deployments = []

        try:
            api_deployments = await self.prefect_client.list_deployments(flow_name)

            for deployment in api_deployments:
                deployment_info = {
                    **deployment,
                    "ui_url": await self.get_deployment_ui_url(
                        deployment["name"], deployment["flow_name"]
                    ),
                    "ui_accessible": False,
                }

                # Check if UI is accessible for this deployment
                ui_check = await self.check_ui_accessibility()
                deployment_info["ui_accessible"] = ui_check["accessible"]

                deployments.append(deployment_info)

        except Exception as e:
            logger.error(f"Failed to list deployments with UI status: {e}")

        return deployments

    def run_async(self, coro):
        """Helper to run async operations in sync context."""
        return self.prefect_client.run_async(coro)
