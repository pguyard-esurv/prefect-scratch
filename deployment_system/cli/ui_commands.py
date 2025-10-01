"""
UI CLI Commands

Command-line interface for UI integration and verification.
"""

import logging
from typing import Any, Optional

from ..ui import (
    DeploymentStatusChecker,
    TroubleshootingUtilities,
    UIClient,
    UIValidator,
)

logger = logging.getLogger(__name__)


class UICLI:
    """Command-line interface for UI integration and verification."""

    def __init__(self, api_url: Optional[str] = None, ui_url: Optional[str] = None):
        self.ui_client = UIClient(api_url, ui_url)
        self.ui_validator = UIValidator(api_url, ui_url)
        self.status_checker = DeploymentStatusChecker(api_url, ui_url)
        self.troubleshooter = TroubleshootingUtilities(api_url, ui_url)

    def check_ui_connectivity(self) -> dict[str, Any]:
        """Check Prefect UI connectivity and accessibility."""
        try:
            api_check = self.ui_client.run_async(
                self.ui_client.check_api_connectivity()
            )
            ui_check = self.ui_client.run_async(self.ui_client.check_ui_accessibility())

            return {
                "success": True,
                "api_connectivity": api_check,
                "ui_accessibility": ui_check,
                "overall_status": (
                    "healthy"
                    if api_check["connected"] and ui_check["accessible"]
                    else "unhealthy"
                ),
            }
        except Exception as e:
            logger.error(f"Failed to check UI connectivity: {e}")
            return {"success": False, "error": str(e)}

    def verify_deployment_in_ui(
        self, deployment_name: str, flow_name: str, timeout_seconds: int = 30
    ) -> dict[str, Any]:
        """Verify that a specific deployment appears in the Prefect UI."""
        try:
            result = self.ui_client.run_async(
                self.ui_client.verify_deployment_in_ui(
                    deployment_name, flow_name, timeout_seconds
                )
            )

            return {
                "success": True,
                "verification_result": result,
                "visible": result["visible"],
                "ui_url": self.ui_client.run_async(
                    self.ui_client.get_deployment_ui_url(deployment_name, flow_name)
                ),
            }
        except Exception as e:
            logger.error(f"Failed to verify deployment in UI: {e}")
            return {"success": False, "error": str(e)}

    def check_deployment_health(
        self, deployment_name: str, flow_name: str
    ) -> dict[str, Any]:
        """Check comprehensive health of a deployment."""
        try:
            health_result = self.status_checker.run_async(
                self.status_checker.check_deployment_health(deployment_name, flow_name)
            )

            return {
                "success": True,
                "health_result": health_result,
                "healthy": health_result["healthy"],
                "status": health_result["status"],
            }
        except Exception as e:
            logger.error(f"Failed to check deployment health: {e}")
            return {"success": False, "error": str(e)}

    def get_deployment_status_report(
        self, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate comprehensive deployment status report."""
        try:
            report = self.status_checker.run_async(
                self.status_checker.get_deployment_status_report(flow_name)
            )

            return {"success": True, "report": report}
        except Exception as e:
            logger.error(f"Failed to generate status report: {e}")
            return {"success": False, "error": str(e)}

    def validate_deployments_ui(
        self, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Validate deployment visibility and correctness in UI."""
        try:
            # Get list of deployments to validate
            deployments = self.ui_client.run_async(
                self.ui_client.prefect_client.list_deployments(flow_name)
            )

            # Convert to format expected by validator
            deployment_list = [
                {"deployment_name": d["name"], "flow_name": d["flow_name"]}
                for d in deployments
            ]

            validation_result = self.ui_validator.run_async(
                self.ui_validator.validate_multiple_deployments_ui(deployment_list)
            )

            return {
                "success": True,
                "validation_result": validation_result,
                "total_deployments": validation_result["total"],
                "valid_deployments": validation_result["valid"],
                "invalid_deployments": validation_result["invalid"],
            }
        except Exception as e:
            logger.error(f"Failed to validate deployments UI: {e}")
            return {"success": False, "error": str(e)}

    def generate_ui_validation_report(
        self, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Generate comprehensive UI validation report."""
        try:
            report = self.ui_validator.run_async(
                self.ui_validator.generate_ui_validation_report(flow_name)
            )

            return {"success": True, "report": report}
        except Exception as e:
            logger.error(f"Failed to generate UI validation report: {e}")
            return {"success": False, "error": str(e)}

    def troubleshoot_connectivity(self) -> dict[str, Any]:
        """Run comprehensive connectivity troubleshooting."""
        try:
            diagnosis = self.troubleshooter.run_async(
                self.troubleshooter.diagnose_connectivity_issues()
            )

            return {
                "success": True,
                "diagnosis": diagnosis,
                "severity": diagnosis["severity"],
            }
        except Exception as e:
            logger.error(f"Failed to troubleshoot connectivity: {e}")
            return {"success": False, "error": str(e)}

    def troubleshoot_deployment_visibility(
        self, deployment_name: str, flow_name: str
    ) -> dict[str, Any]:
        """Troubleshoot why a specific deployment is not visible in UI."""
        try:
            diagnosis = self.troubleshooter.run_async(
                self.troubleshooter.diagnose_deployment_visibility_issues(
                    deployment_name, flow_name
                )
            )

            return {
                "success": True,
                "diagnosis": diagnosis,
                "severity": diagnosis["severity"],
            }
        except Exception as e:
            logger.error(f"Failed to troubleshoot deployment visibility: {e}")
            return {"success": False, "error": str(e)}

    def run_comprehensive_troubleshooting(
        self, deployment_name: Optional[str] = None, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Run comprehensive troubleshooting for system or specific deployment."""
        try:
            report = self.troubleshooter.run_async(
                self.troubleshooter.run_comprehensive_troubleshooting(
                    deployment_name, flow_name
                )
            )

            return {
                "success": True,
                "report": report,
                "severity": report["overall_severity"],
            }
        except Exception as e:
            logger.error(f"Failed to run comprehensive troubleshooting: {e}")
            return {"success": False, "error": str(e)}

    def wait_for_deployment_ready(
        self, deployment_name: str, flow_name: str, timeout_seconds: int = 60
    ) -> dict[str, Any]:
        """Wait for a deployment to become ready and healthy."""
        try:
            result = self.status_checker.run_async(
                self.status_checker.wait_for_deployment_ready(
                    deployment_name, flow_name, timeout_seconds
                )
            )

            return {"success": True, "wait_result": result, "ready": result["ready"]}
        except Exception as e:
            logger.error(f"Failed to wait for deployment ready: {e}")
            return {"success": False, "error": str(e)}

    def list_deployments_with_ui_status(
        self, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """List all deployments with their UI visibility status."""
        try:
            deployments = self.ui_client.run_async(
                self.ui_client.list_deployments_with_ui_status(flow_name)
            )

            return {
                "success": True,
                "deployments": deployments,
                "total_count": len(deployments),
            }
        except Exception as e:
            logger.error(f"Failed to list deployments with UI status: {e}")
            return {"success": False, "error": str(e)}

    def get_deployment_ui_url(
        self, deployment_name: str, flow_name: str
    ) -> dict[str, Any]:
        """Get the direct URL to a deployment in the Prefect UI."""
        try:
            ui_url = self.ui_client.run_async(
                self.ui_client.get_deployment_ui_url(deployment_name, flow_name)
            )

            return {
                "success": True,
                "ui_url": ui_url,
                "deployment_name": deployment_name,
                "flow_name": flow_name,
            }
        except Exception as e:
            logger.error(f"Failed to get deployment UI URL: {e}")
            return {"success": False, "error": str(e)}

    # Utility methods for formatted output
    def format_connectivity_report(self, report: dict[str, Any]) -> str:
        """Format connectivity report for console output."""
        if not report.get("success"):
            return f"❌ Error: {report.get('error', 'Unknown error')}"

        api_status = "✅" if report["api_connectivity"]["connected"] else "❌"
        ui_status = "✅" if report["ui_accessibility"]["accessible"] else "❌"

        output = [
            "🔍 UI Connectivity Check",
            f"  API Connection: {api_status} {report['api_connectivity'].get('api_url', 'N/A')}",
            f"  UI Accessibility: {ui_status} {report['ui_accessibility'].get('ui_url', 'N/A')}",
            f"  Overall Status: {report['overall_status'].upper()}",
        ]

        if not report["api_connectivity"]["connected"]:
            output.append(
                f"  API Error: {report['api_connectivity'].get('error', 'Unknown')}"
            )

        if not report["ui_accessibility"]["accessible"]:
            output.append(
                f"  UI Error: {report['ui_accessibility'].get('error', 'Unknown')}"
            )

        return "\n".join(output)

    def format_deployment_health(self, health_result: dict[str, Any]) -> str:
        """Format deployment health result for console output."""
        if not health_result.get("success"):
            return f"❌ Error: {health_result.get('error', 'Unknown error')}"

        health = health_result["health_result"]
        status_icon = "✅" if health["healthy"] else "❌"

        output = [
            f"🏥 Deployment Health: {health['full_name']}",
            f"  Status: {status_icon} {health['status'].upper()}",
            f"  Exists: {'✅' if health['checks']['exists'] else '❌'}",
            f"  Work Pool Valid: {'✅' if health['checks']['work_pool_valid'] else '❌'}",
            f"  UI Visible: {'✅' if health['checks']['ui_visible'] else '❌'}",
        ]

        if health["issues"]:
            output.append("  Issues:")
            for issue in health["issues"]:
                output.append(f"    • {issue}")

        if health["recommendations"]:
            output.append("  Recommendations:")
            for rec in health["recommendations"]:
                output.append(f"    • {rec}")

        return "\n".join(output)

    def format_troubleshooting_report(self, report: dict[str, Any]) -> str:
        """Format troubleshooting report for console output."""
        if not report.get("success"):
            return f"❌ Error: {report.get('error', 'Unknown error')}"

        diagnosis = report["diagnosis"] if "diagnosis" in report else report["report"]
        severity_icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
        severity = diagnosis.get("severity", "info")

        output = [
            f"{severity_icons.get(severity, 'ℹ️')} Troubleshooting Report ({severity.upper()})",
            f"  Timestamp: {diagnosis.get('timestamp', 'N/A')}",
        ]

        if "connectivity_diagnosis" in diagnosis:
            conn_diag = diagnosis["connectivity_diagnosis"]
            output.extend(
                [
                    "  🔗 Connectivity:",
                    f"    API: {'✅' if conn_diag.get('api_diagnosis', {}).get('responding') else '❌'}",
                    f"    UI: {'✅' if conn_diag.get('ui_diagnosis', {}).get('responding') else '❌'}",
                ]
            )

        if diagnosis.get("recommendations"):
            output.append("  💡 Recommendations:")
            for rec in diagnosis["recommendations"][:5]:  # Limit to top 5
                output.append(f"    • {rec}")

        return "\n".join(output)
