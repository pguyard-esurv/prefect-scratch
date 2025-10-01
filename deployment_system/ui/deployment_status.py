"""
Deployment Status Checker

Provides comprehensive deployment status checking and health monitoring.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from ..api.prefect_client import PrefectClient
from .ui_client import UIClient

logger = logging.getLogger(__name__)


class DeploymentStatusChecker:
    """Comprehensive deployment status checking and health monitoring."""

    def __init__(self, api_url: Optional[str] = None, ui_url: Optional[str] = None):
        self.prefect_client = PrefectClient(api_url)
        self.ui_client = UIClient(api_url, ui_url)

    async def check_deployment_health(
        self, deployment_name: str, flow_name: str
    ) -> dict[str, Any]:
        """Check comprehensive health of a deployment."""
        result = {
            "deployment_name": deployment_name,
            "flow_name": flow_name,
            "full_name": f"{flow_name}/{deployment_name}",
            "healthy": False,
            "status": "unknown",
            "checks": {
                "exists": False,
                "work_pool_valid": False,
                "ui_visible": False,
                "recent_runs": False,
                "schedule_active": False,
            },
            "details": {},
            "issues": [],
            "recommendations": [],
        }

        try:
            # Check if deployment exists
            deployment = await self.prefect_client.get_deployment_by_name(
                deployment_name, flow_name
            )

            if not deployment:
                result["status"] = "not_found"
                result["issues"].append("Deployment does not exist")
                result["recommendations"].append("Create the deployment first")
                return result

            result["checks"]["exists"] = True
            result["details"]["deployment_info"] = deployment

            # Check work pool validity
            work_pool_name = deployment.get("work_pool_name")
            if work_pool_name:
                work_pool_valid = await self.prefect_client.validate_work_pool(
                    work_pool_name
                )
                result["checks"]["work_pool_valid"] = work_pool_valid

                if not work_pool_valid:
                    result["issues"].append(
                        f"Work pool '{work_pool_name}' is not valid or not found"
                    )
                    result["recommendations"].append(
                        f"Ensure work pool '{work_pool_name}' exists and is running"
                    )
            else:
                result["issues"].append("No work pool configured")
                result["recommendations"].append(
                    "Configure a work pool for the deployment"
                )

            # Check UI visibility
            ui_check = await self.ui_client.verify_deployment_in_ui(
                deployment_name, flow_name, timeout_seconds=10
            )
            result["checks"]["ui_visible"] = ui_check["visible"]
            result["details"]["ui_check"] = ui_check

            if not ui_check["visible"]:
                result["issues"].append("Deployment not visible in UI")
                if ui_check.get("error"):
                    result["recommendations"].append(f"UI issue: {ui_check['error']}")

            # Check schedule status
            schedule = deployment.get("schedule")
            if schedule:
                result["checks"]["schedule_active"] = True
                result["details"]["schedule"] = schedule
            else:
                result["details"]["schedule"] = None

            # Check recent runs (this would require additional API calls to get flow runs)
            # For now, we'll mark this as a placeholder
            result["checks"]["recent_runs"] = None  # Would need flow run history

            # Determine overall health
            critical_checks = ["exists", "work_pool_valid"]
            important_checks = ["ui_visible"]

            critical_passed = all(result["checks"][check] for check in critical_checks)
            important_passed = all(
                result["checks"][check]
                for check in important_checks
                if result["checks"][check] is not None
            )

            if critical_passed and important_passed:
                result["healthy"] = True
                result["status"] = "healthy"
            elif critical_passed:
                result["healthy"] = False
                result["status"] = "degraded"
            else:
                result["healthy"] = False
                result["status"] = "unhealthy"

        except Exception as e:
            result["status"] = "error"
            result["issues"].append(f"Health check failed: {str(e)}")
            logger.error(
                f"Failed to check deployment health for {flow_name}/{deployment_name}: {e}"
            )

        return result

    async def check_multiple_deployments_health(
        self, deployments: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Check health of multiple deployments."""
        results = {
            "total": len(deployments),
            "healthy": 0,
            "degraded": 0,
            "unhealthy": 0,
            "errors": 0,
            "deployments": [],
            "summary": {},
        }

        for deployment_info in deployments:
            deployment_name = deployment_info.get("deployment_name")
            flow_name = deployment_info.get("flow_name")

            if not deployment_name or not flow_name:
                continue

            health_check = await self.check_deployment_health(
                deployment_name, flow_name
            )
            results["deployments"].append(health_check)

            # Update counters
            status = health_check["status"]
            if status == "healthy":
                results["healthy"] += 1
            elif status == "degraded":
                results["degraded"] += 1
            elif status == "unhealthy":
                results["unhealthy"] += 1
            elif status == "error":
                results["errors"] += 1

        # Generate summary
        results["summary"] = {
            "health_percentage": (
                (results["healthy"] / results["total"] * 100)
                if results["total"] > 0
                else 0
            ),
            "issues_found": sum(
                len(d.get("issues", [])) for d in results["deployments"]
            ),
            "recommendations_count": sum(
                len(d.get("recommendations", [])) for d in results["deployments"]
            ),
        }

        return results

    async def get_deployment_status_report(
        self, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate a comprehensive status report for deployments."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "api_connectivity": {},
            "ui_accessibility": {},
            "deployments": [],
            "summary": {},
            "system_health": {},
        }

        try:
            # Check API connectivity
            report["api_connectivity"] = await self.ui_client.check_api_connectivity()

            # Check UI accessibility
            report["ui_accessibility"] = await self.ui_client.check_ui_accessibility()

            # Get all deployments
            deployments = await self.prefect_client.list_deployments(flow_name)

            # Check health of each deployment
            deployment_health_checks = []
            for deployment in deployments:
                health_check = await self.check_deployment_health(
                    deployment["name"], deployment["flow_name"]
                )
                deployment_health_checks.append(health_check)

            report["deployments"] = deployment_health_checks

            # Generate summary
            total_deployments = len(deployment_health_checks)
            healthy_count = sum(1 for d in deployment_health_checks if d["healthy"])

            report["summary"] = {
                "total_deployments": total_deployments,
                "healthy_deployments": healthy_count,
                "unhealthy_deployments": total_deployments - healthy_count,
                "health_percentage": (
                    (healthy_count / total_deployments * 100)
                    if total_deployments > 0
                    else 0
                ),
                "api_connected": report["api_connectivity"]["connected"],
                "ui_accessible": report["ui_accessibility"]["accessible"],
            }

            # System health assessment
            system_issues = []
            if not report["api_connectivity"]["connected"]:
                system_issues.append("Prefect API not accessible")
            if not report["ui_accessibility"]["accessible"]:
                system_issues.append("Prefect UI not accessible")

            report["system_health"] = {
                "overall_healthy": len(system_issues) == 0
                and report["summary"]["health_percentage"] > 80,
                "issues": system_issues,
                "recommendations": self._generate_system_recommendations(report),
            }

        except Exception as e:
            logger.error(f"Failed to generate deployment status report: {e}")
            report["error"] = str(e)

        return report

    def _generate_system_recommendations(self, report: dict[str, Any]) -> list[str]:
        """Generate system-level recommendations based on the report."""
        recommendations = []

        if not report["api_connectivity"]["connected"]:
            recommendations.append("Check Prefect server is running and accessible")
            recommendations.append(
                "Verify PREFECT_API_URL environment variable is set correctly"
            )

        if not report["ui_accessibility"]["accessible"]:
            recommendations.append("Check Prefect UI is running and accessible")
            recommendations.append("Verify UI URL configuration")

        health_percentage = report["summary"].get("health_percentage", 0)
        if health_percentage < 50:
            recommendations.append(
                "Multiple deployments are unhealthy - check work pools and configurations"
            )
        elif health_percentage < 80:
            recommendations.append(
                "Some deployments need attention - review individual deployment health"
            )

        return recommendations

    async def wait_for_deployment_ready(
        self, deployment_name: str, flow_name: str, timeout_seconds: int = 60
    ) -> dict[str, Any]:
        """Wait for a deployment to become ready and healthy."""
        result = {
            "ready": False,
            "deployment_name": deployment_name,
            "flow_name": flow_name,
            "wait_time_seconds": 0,
            "final_status": None,
            "error": None,
        }

        start_time = asyncio.get_event_loop().time()

        try:
            while (asyncio.get_event_loop().time() - start_time) < timeout_seconds:
                health_check = await self.check_deployment_health(
                    deployment_name, flow_name
                )

                if health_check["healthy"]:
                    result["ready"] = True
                    result["wait_time_seconds"] = int(
                        asyncio.get_event_loop().time() - start_time
                    )
                    result["final_status"] = health_check
                    break

                await asyncio.sleep(2)  # Check every 2 seconds

            if not result["ready"]:
                result["error"] = (
                    f"Deployment not ready after {timeout_seconds} seconds"
                )
                result["final_status"] = await self.check_deployment_health(
                    deployment_name, flow_name
                )

        except Exception as e:
            result["error"] = f"Wait operation failed: {str(e)}"

        return result

    def run_async(self, coro):
        """Helper to run async operations in sync context."""
        return self.prefect_client.run_async(coro)
