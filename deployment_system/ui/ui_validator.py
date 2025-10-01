"""
UI Validator

Validates deployment visibility and correctness in Prefect UI.
"""

import logging
from typing import Any, Optional

from .deployment_status import DeploymentStatusChecker
from .ui_client import UIClient

logger = logging.getLogger(__name__)


class UIValidator:
    """Validates deployment visibility and correctness in Prefect UI."""

    def __init__(self, api_url: Optional[str] = None, ui_url: Optional[str] = None):
        self.ui_client = UIClient(api_url, ui_url)
        self.status_checker = DeploymentStatusChecker(api_url, ui_url)

    async def validate_deployment_ui_presence(
        self, deployment_name: str, flow_name: str
    ) -> dict[str, Any]:
        """Validate that a deployment is properly visible in the UI."""
        result = {
            "deployment_name": deployment_name,
            "flow_name": flow_name,
            "full_name": f"{flow_name}/{deployment_name}",
            "valid": False,
            "checks": {
                "api_exists": False,
                "ui_accessible": False,
                "ui_visible": False,
                "metadata_correct": False,
            },
            "metadata": {},
            "issues": [],
            "ui_url": None,
        }

        try:
            # Check API existence
            deployment = await self.ui_client.prefect_client.get_deployment_by_name(
                deployment_name, flow_name
            )

            if deployment:
                result["checks"]["api_exists"] = True
                result["metadata"] = deployment
            else:
                result["issues"].append("Deployment not found via API")
                return result

            # Check UI accessibility
            ui_check = await self.ui_client.check_ui_accessibility()
            result["checks"]["ui_accessible"] = ui_check["accessible"]

            if not ui_check["accessible"]:
                result["issues"].append(
                    f"UI not accessible: {ui_check.get('error', 'Unknown error')}"
                )
                return result

            # Check UI visibility
            visibility_check = await self.ui_client.verify_deployment_in_ui(
                deployment_name, flow_name
            )
            result["checks"]["ui_visible"] = visibility_check["visible"]

            if not visibility_check["visible"]:
                result["issues"].append(
                    f"Deployment not visible in UI: {visibility_check.get('error', 'Unknown error')}"
                )

            # Get UI URL
            result["ui_url"] = await self.ui_client.get_deployment_ui_url(
                deployment_name, flow_name
            )

            # Validate metadata correctness
            metadata_issues = self._validate_deployment_metadata(deployment)
            if metadata_issues:
                result["issues"].extend(metadata_issues)
            else:
                result["checks"]["metadata_correct"] = True

            # Overall validation
            result["valid"] = all(result["checks"].values())

        except Exception as e:
            result["issues"].append(f"Validation failed: {str(e)}")
            logger.error(
                f"Failed to validate deployment UI presence for {flow_name}/{deployment_name}: {e}"
            )

        return result

    def _validate_deployment_metadata(self, deployment: dict[str, Any]) -> list[str]:
        """Validate deployment metadata for UI display."""
        issues = []

        # Check required fields
        required_fields = ["name", "flow_name", "work_pool_name"]
        for field in required_fields:
            if not deployment.get(field):
                issues.append(f"Missing required field: {field}")

        # Check name format
        name = deployment.get("name", "")
        if not name or len(name.strip()) == 0:
            issues.append("Deployment name is empty")
        elif len(name) > 100:
            issues.append("Deployment name is too long (>100 characters)")

        # Check description
        description = deployment.get("description", "")
        if len(description) > 500:
            issues.append("Description is too long (>500 characters)")

        # Check tags
        tags = deployment.get("tags", [])
        if tags and not isinstance(tags, list):
            issues.append("Tags must be a list")
        elif tags and len(tags) > 20:
            issues.append("Too many tags (>20)")

        return issues

    async def validate_multiple_deployments_ui(
        self, deployments: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Validate UI presence for multiple deployments."""
        result = {
            "total": len(deployments),
            "valid": 0,
            "invalid": 0,
            "deployments": [],
            "summary": {"common_issues": {}, "ui_accessibility": None},
        }

        # Check UI accessibility once
        ui_check = await self.ui_client.check_ui_accessibility()
        result["summary"]["ui_accessibility"] = ui_check

        issue_counts = {}

        for deployment_info in deployments:
            deployment_name = deployment_info.get("deployment_name")
            flow_name = deployment_info.get("flow_name")

            if not deployment_name or not flow_name:
                continue

            validation = await self.validate_deployment_ui_presence(
                deployment_name, flow_name
            )
            result["deployments"].append(validation)

            if validation["valid"]:
                result["valid"] += 1
            else:
                result["invalid"] += 1

                # Count common issues
                for issue in validation["issues"]:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1

        # Identify common issues (affecting >25% of deployments)
        threshold = max(1, len(deployments) * 0.25)
        result["summary"]["common_issues"] = {
            issue: count for issue, count in issue_counts.items() if count >= threshold
        }

        return result

    async def validate_deployment_configuration_for_ui(
        self, deployment_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate deployment configuration for optimal UI display."""
        result = {"valid": True, "warnings": [], "errors": [], "recommendations": []}

        # Check deployment name
        name = deployment_config.get("name", "")
        if not name:
            result["errors"].append("Deployment name is required")
            result["valid"] = False
        elif len(name) > 100:
            result["warnings"].append(
                "Deployment name is very long and may be truncated in UI"
            )
        elif not name.replace("-", "").replace("_", "").isalnum():
            result["warnings"].append(
                "Deployment name contains special characters that may not display well"
            )

        # Check description
        description = deployment_config.get("description", "")
        if not description:
            result["recommendations"].append(
                "Add a description for better UI visibility"
            )
        elif len(description) > 500:
            result["warnings"].append(
                "Description is very long and may be truncated in UI"
            )

        # Check tags
        tags = deployment_config.get("tags", [])
        if not tags:
            result["recommendations"].append("Add tags for better organization in UI")
        elif len(tags) > 10:
            result["warnings"].append("Many tags may clutter the UI display")

        # Check work pool
        work_pool = deployment_config.get("work_pool_name")
        if not work_pool:
            result["errors"].append(
                "Work pool is required for deployment to appear in UI"
            )
            result["valid"] = False

        # Check schedule format
        schedule = deployment_config.get("schedule")
        if schedule:
            # Basic validation - more detailed validation would require parsing the schedule
            if isinstance(schedule, str) and len(schedule) > 200:
                result["warnings"].append("Schedule string is very long")

        return result

    async def generate_ui_validation_report(
        self, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate comprehensive UI validation report."""
        report = {
            "timestamp": None,
            "ui_accessibility": {},
            "api_connectivity": {},
            "deployments": [],
            "summary": {},
            "recommendations": [],
        }

        try:
            from datetime import datetime

            report["timestamp"] = datetime.now().isoformat()

            # Check system accessibility
            report["ui_accessibility"] = await self.ui_client.check_ui_accessibility()
            report["api_connectivity"] = await self.ui_client.check_api_connectivity()

            # Get deployments
            deployments = await self.ui_client.prefect_client.list_deployments(
                flow_name
            )

            # Validate each deployment
            validation_results = []
            for deployment in deployments:
                validation = await self.validate_deployment_ui_presence(
                    deployment["name"], deployment["flow_name"]
                )
                validation_results.append(validation)

            report["deployments"] = validation_results

            # Generate summary
            total = len(validation_results)
            valid = sum(1 for v in validation_results if v["valid"])

            report["summary"] = {
                "total_deployments": total,
                "valid_deployments": valid,
                "invalid_deployments": total - valid,
                "validation_percentage": (valid / total * 100) if total > 0 else 0,
                "ui_accessible": report["ui_accessibility"]["accessible"],
                "api_connected": report["api_connectivity"]["connected"],
            }

            # Generate recommendations
            report["recommendations"] = self._generate_ui_recommendations(report)

        except Exception as e:
            logger.error(f"Failed to generate UI validation report: {e}")
            report["error"] = str(e)

        return report

    def _generate_ui_recommendations(self, report: dict[str, Any]) -> list[str]:
        """Generate UI-specific recommendations."""
        recommendations = []

        if not report["ui_accessibility"]["accessible"]:
            recommendations.append(
                "Fix UI accessibility issues before validating deployments"
            )

        if not report["api_connectivity"]["connected"]:
            recommendations.append(
                "Fix API connectivity issues before validating deployments"
            )

        validation_percentage = report["summary"].get("validation_percentage", 0)
        if validation_percentage < 50:
            recommendations.append(
                "Many deployments have UI visibility issues - check work pools and deployment configurations"
            )
        elif validation_percentage < 80:
            recommendations.append(
                "Some deployments need UI optimization - review individual validation results"
            )

        # Check for common issues across deployments
        all_issues = []
        for deployment in report["deployments"]:
            all_issues.extend(deployment.get("issues", []))

        issue_counts = {}
        for issue in all_issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1

        # Recommend fixes for common issues
        for issue, count in issue_counts.items():
            if count >= len(report["deployments"]) * 0.3:  # Affects 30% or more
                if "not visible in UI" in issue:
                    recommendations.append(
                        "Multiple deployments not visible - check UI sync and work pool status"
                    )
                elif "metadata" in issue.lower():
                    recommendations.append(
                        "Multiple deployments have metadata issues - review deployment configurations"
                    )

        return recommendations

    def run_async(self, coro):
        """Helper to run async operations in sync context."""
        return self.ui_client.run_async(coro)
