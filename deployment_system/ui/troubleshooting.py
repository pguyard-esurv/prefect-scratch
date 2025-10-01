"""
Troubleshooting Utilities

Provides utilities for diagnosing and troubleshooting UI connectivity and deployment visibility issues.
"""

import logging
import socket
from typing import Any, Optional
from urllib.parse import urlparse

from .deployment_status import DeploymentStatusChecker
from .ui_client import UIClient

logger = logging.getLogger(__name__)


class TroubleshootingUtilities:
    """Utilities for diagnosing and troubleshooting UI and deployment issues."""

    def __init__(self, api_url: Optional[str] = None, ui_url: Optional[str] = None):
        self.api_url = api_url
        self.ui_url = ui_url
        self.ui_client = UIClient(api_url, ui_url)
        self.status_checker = DeploymentStatusChecker(api_url, ui_url)

    async def diagnose_connectivity_issues(self) -> dict[str, Any]:
        """Comprehensive diagnosis of connectivity issues."""
        diagnosis = {
            "timestamp": None,
            "api_diagnosis": {},
            "ui_diagnosis": {},
            "network_diagnosis": {},
            "recommendations": [],
            "severity": "info",  # info, warning, error, critical
        }

        try:
            from datetime import datetime

            diagnosis["timestamp"] = datetime.now().isoformat()

            # Diagnose API connectivity
            diagnosis["api_diagnosis"] = await self._diagnose_api_connectivity()

            # Diagnose UI connectivity
            diagnosis["ui_diagnosis"] = await self._diagnose_ui_connectivity()

            # Diagnose network issues
            diagnosis["network_diagnosis"] = await self._diagnose_network_issues()

            # Generate recommendations and determine severity
            diagnosis["recommendations"] = self._generate_connectivity_recommendations(
                diagnosis
            )
            diagnosis["severity"] = self._determine_severity(diagnosis)

        except Exception as e:
            logger.error(f"Failed to diagnose connectivity issues: {e}")
            diagnosis["error"] = str(e)
            diagnosis["severity"] = "error"

        return diagnosis

    async def _diagnose_api_connectivity(self) -> dict[str, Any]:
        """Diagnose API connectivity issues."""
        diagnosis = {
            "configured": False,
            "reachable": False,
            "responding": False,
            "authenticated": False,
            "api_url": self.api_url,
            "issues": [],
            "details": {},
        }

        try:
            # Check if API URL is configured
            if not self.api_url:
                diagnosis["issues"].append("API URL not configured")
                return diagnosis

            diagnosis["configured"] = True
            diagnosis["details"]["parsed_url"] = urlparse(self.api_url)

            # Check network reachability
            parsed = urlparse(self.api_url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)

            try:
                sock = socket.create_connection((host, port), timeout=10)
                sock.close()
                diagnosis["reachable"] = True
            except Exception as e:
                diagnosis["issues"].append(f"Network unreachable: {str(e)}")
                return diagnosis

            # Check API response
            api_check = await self.ui_client.check_api_connectivity()
            diagnosis["responding"] = api_check["connected"]
            diagnosis["details"]["api_check"] = api_check

            if not api_check["connected"]:
                diagnosis["issues"].append(
                    f"API not responding: {api_check.get('error', 'Unknown error')}"
                )
            else:
                diagnosis["authenticated"] = (
                    True  # If we can connect, we're authenticated
                )

        except Exception as e:
            diagnosis["issues"].append(f"API diagnosis failed: {str(e)}")

        return diagnosis

    async def _diagnose_ui_connectivity(self) -> dict[str, Any]:
        """Diagnose UI connectivity issues."""
        diagnosis = {
            "configured": False,
            "reachable": False,
            "responding": False,
            "ui_url": self.ui_url,
            "issues": [],
            "details": {},
        }

        try:
            # Check if UI URL is configured
            if not self.ui_url:
                diagnosis["issues"].append(
                    "UI URL not configured or could not be derived"
                )
                return diagnosis

            diagnosis["configured"] = True
            diagnosis["details"]["parsed_url"] = urlparse(self.ui_url)

            # Check network reachability
            parsed = urlparse(self.ui_url)
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)

            try:
                sock = socket.create_connection((host, port), timeout=10)
                sock.close()
                diagnosis["reachable"] = True
            except Exception as e:
                diagnosis["issues"].append(f"UI network unreachable: {str(e)}")
                return diagnosis

            # Check UI response
            ui_check = await self.ui_client.check_ui_accessibility()
            diagnosis["responding"] = ui_check["accessible"]
            diagnosis["details"]["ui_check"] = ui_check

            if not ui_check["accessible"]:
                diagnosis["issues"].append(
                    f"UI not responding: {ui_check.get('error', 'Unknown error')}"
                )

        except Exception as e:
            diagnosis["issues"].append(f"UI diagnosis failed: {str(e)}")

        return diagnosis

    async def _diagnose_network_issues(self) -> dict[str, Any]:
        """Diagnose network-level issues."""
        diagnosis = {
            "dns_resolution": {},
            "port_connectivity": {},
            "ssl_issues": {},
            "issues": [],
        }

        try:
            # Test DNS resolution for API
            if self.api_url:
                api_parsed = urlparse(self.api_url)
                diagnosis["dns_resolution"]["api"] = await self._test_dns_resolution(
                    api_parsed.hostname
                )

            # Test DNS resolution for UI
            if self.ui_url:
                ui_parsed = urlparse(self.ui_url)
                diagnosis["dns_resolution"]["ui"] = await self._test_dns_resolution(
                    ui_parsed.hostname
                )

            # Test port connectivity
            if self.api_url:
                api_parsed = urlparse(self.api_url)
                port = api_parsed.port or (443 if api_parsed.scheme == "https" else 80)
                diagnosis["port_connectivity"]["api"] = (
                    await self._test_port_connectivity(api_parsed.hostname, port)
                )

            if self.ui_url:
                ui_parsed = urlparse(self.ui_url)
                port = ui_parsed.port or (443 if ui_parsed.scheme == "https" else 80)
                diagnosis["port_connectivity"]["ui"] = (
                    await self._test_port_connectivity(ui_parsed.hostname, port)
                )

        except Exception as e:
            diagnosis["issues"].append(f"Network diagnosis failed: {str(e)}")

        return diagnosis

    async def _test_dns_resolution(self, hostname: str) -> dict[str, Any]:
        """Test DNS resolution for a hostname."""
        result = {"resolved": False, "ip_addresses": [], "error": None}

        try:
            import socket

            ip_addresses = socket.gethostbyname_ex(hostname)[2]
            result["resolved"] = True
            result["ip_addresses"] = ip_addresses
        except Exception as e:
            result["error"] = str(e)

        return result

    async def _test_port_connectivity(self, hostname: str, port: int) -> dict[str, Any]:
        """Test port connectivity."""
        result = {"connected": False, "response_time_ms": None, "error": None}

        try:
            import time

            start_time = time.time()
            sock = socket.create_connection((hostname, port), timeout=10)
            sock.close()
            result["connected"] = True
            result["response_time_ms"] = int((time.time() - start_time) * 1000)
        except Exception as e:
            result["error"] = str(e)

        return result

    def _generate_connectivity_recommendations(
        self, diagnosis: dict[str, Any]
    ) -> list[str]:
        """Generate recommendations based on connectivity diagnosis."""
        recommendations = []

        api_diag = diagnosis.get("api_diagnosis", {})
        ui_diag = diagnosis.get("ui_diagnosis", {})
        network_diag = diagnosis.get("network_diagnosis", {})

        # API recommendations
        if not api_diag.get("configured"):
            recommendations.append("Configure PREFECT_API_URL environment variable")
        elif not api_diag.get("reachable"):
            recommendations.append("Check network connectivity to Prefect API server")
            recommendations.append(
                "Verify firewall settings allow outbound connections"
            )
        elif not api_diag.get("responding"):
            recommendations.append("Check if Prefect server is running")
            recommendations.append("Verify API URL is correct")

        # UI recommendations
        if not ui_diag.get("configured"):
            recommendations.append(
                "Configure UI URL or ensure it can be derived from API URL"
            )
        elif not ui_diag.get("reachable"):
            recommendations.append("Check network connectivity to Prefect UI server")
        elif not ui_diag.get("responding"):
            recommendations.append("Check if Prefect UI is running")
            recommendations.append("Verify UI URL is correct")

        # Network recommendations
        dns_issues = []
        for service, dns_result in network_diag.get("dns_resolution", {}).items():
            if not dns_result.get("resolved"):
                dns_issues.append(service)

        if dns_issues:
            recommendations.append(
                f"DNS resolution failed for {', '.join(dns_issues)} - check DNS settings"
            )

        port_issues = []
        for service, port_result in network_diag.get("port_connectivity", {}).items():
            if not port_result.get("connected"):
                port_issues.append(service)

        if port_issues:
            recommendations.append(
                f"Port connectivity failed for {', '.join(port_issues)} - check firewall/proxy settings"
            )

        return recommendations

    def _determine_severity(self, diagnosis: dict[str, Any]) -> str:
        """Determine the severity level of issues."""
        api_diag = diagnosis.get("api_diagnosis", {})
        ui_diag = diagnosis.get("ui_diagnosis", {})

        # Critical: API not working at all
        if not api_diag.get("configured") or not api_diag.get("responding"):
            return "critical"

        # Error: UI not working
        if not ui_diag.get("responding"):
            return "error"

        # Warning: Network issues but services responding
        if api_diag.get("issues") or ui_diag.get("issues"):
            return "warning"

        return "info"

    async def diagnose_deployment_visibility_issues(
        self, deployment_name: str, flow_name: str
    ) -> dict[str, Any]:
        """Diagnose why a specific deployment is not visible in UI."""
        diagnosis = {
            "deployment_name": deployment_name,
            "flow_name": flow_name,
            "full_name": f"{flow_name}/{deployment_name}",
            "issues_found": [],
            "checks_performed": {},
            "recommendations": [],
            "severity": "info",
        }

        try:
            # Check if deployment exists in API
            deployment = await self.ui_client.prefect_client.get_deployment_by_name(
                deployment_name, flow_name
            )

            diagnosis["checks_performed"]["api_exists"] = deployment is not None

            if not deployment:
                diagnosis["issues_found"].append(
                    "Deployment does not exist in Prefect API"
                )
                diagnosis["recommendations"].append("Create the deployment first")
                diagnosis["severity"] = "critical"
                return diagnosis

            # Check work pool validity
            work_pool_name = deployment.get("work_pool_name")
            if work_pool_name:
                work_pool_valid = (
                    await self.ui_client.prefect_client.validate_work_pool(
                        work_pool_name
                    )
                )
                diagnosis["checks_performed"]["work_pool_valid"] = work_pool_valid

                if not work_pool_valid:
                    diagnosis["issues_found"].append(
                        f"Work pool '{work_pool_name}' is invalid or not found"
                    )
                    diagnosis["recommendations"].append(
                        f"Create or fix work pool '{work_pool_name}'"
                    )
                    diagnosis["severity"] = "error"
            else:
                diagnosis["issues_found"].append("No work pool configured")
                diagnosis["recommendations"].append(
                    "Configure a work pool for the deployment"
                )
                diagnosis["severity"] = "error"

            # Check UI accessibility
            ui_check = await self.ui_client.check_ui_accessibility()
            diagnosis["checks_performed"]["ui_accessible"] = ui_check["accessible"]

            if not ui_check["accessible"]:
                diagnosis["issues_found"].append(
                    f"UI not accessible: {ui_check.get('error')}"
                )
                diagnosis["recommendations"].append("Fix UI connectivity issues")
                diagnosis["severity"] = "error"

            # Check deployment metadata
            metadata_issues = self._check_deployment_metadata_issues(deployment)
            if metadata_issues:
                diagnosis["issues_found"].extend(metadata_issues)
                diagnosis["recommendations"].append("Fix deployment metadata issues")
                if diagnosis["severity"] == "info":
                    diagnosis["severity"] = "warning"

            # Check UI visibility
            visibility_check = await self.ui_client.verify_deployment_in_ui(
                deployment_name, flow_name, timeout_seconds=10
            )
            diagnosis["checks_performed"]["ui_visible"] = visibility_check["visible"]

            if not visibility_check["visible"]:
                diagnosis["issues_found"].append(
                    "Deployment not visible in UI despite existing in API"
                )
                diagnosis["recommendations"].append(
                    "Wait longer for UI sync or restart Prefect services"
                )
                if diagnosis["severity"] == "info":
                    diagnosis["severity"] = "warning"

        except Exception as e:
            diagnosis["issues_found"].append(f"Diagnosis failed: {str(e)}")
            diagnosis["severity"] = "error"

        return diagnosis

    def _check_deployment_metadata_issues(
        self, deployment: dict[str, Any]
    ) -> list[str]:
        """Check for deployment metadata issues that might affect UI visibility."""
        issues = []

        # Check for empty or invalid names
        if not deployment.get("name", "").strip():
            issues.append("Deployment name is empty")

        # Check for very long names that might cause UI issues
        if len(deployment.get("name", "")) > 100:
            issues.append(
                "Deployment name is very long and might cause UI display issues"
            )

        # Check for invalid characters
        name = deployment.get("name", "")
        if any(char in name for char in ["/", "\\", "<", ">", ":", '"', "|", "?", "*"]):
            issues.append("Deployment name contains invalid characters")

        return issues

    async def run_comprehensive_troubleshooting(
        self, deployment_name: Optional[str] = None, flow_name: Optional[str] = None
    ) -> dict[str, Any]:
        """Run comprehensive troubleshooting for the entire system or specific deployment."""
        report = {
            "timestamp": None,
            "scope": "system" if not deployment_name else "deployment",
            "connectivity_diagnosis": {},
            "deployment_diagnosis": {},
            "system_recommendations": [],
            "overall_severity": "info",
        }

        try:
            from datetime import datetime

            report["timestamp"] = datetime.now().isoformat()

            # Always run connectivity diagnosis
            report["connectivity_diagnosis"] = await self.diagnose_connectivity_issues()

            # Run deployment-specific diagnosis if requested
            if deployment_name and flow_name:
                report["deployment_diagnosis"] = (
                    await self.diagnose_deployment_visibility_issues(
                        deployment_name, flow_name
                    )
                )

            # Generate system-level recommendations
            report["system_recommendations"] = (
                self._generate_system_troubleshooting_recommendations(report)
            )

            # Determine overall severity
            severities = [report["connectivity_diagnosis"].get("severity", "info")]
            if report["deployment_diagnosis"]:
                severities.append(
                    report["deployment_diagnosis"].get("severity", "info")
                )

            severity_order = {"info": 0, "warning": 1, "error": 2, "critical": 3}
            report["overall_severity"] = max(
                severities, key=lambda x: severity_order.get(x, 0)
            )

        except Exception as e:
            logger.error(f"Comprehensive troubleshooting failed: {e}")
            report["error"] = str(e)
            report["overall_severity"] = "error"

        return report

    def _generate_system_troubleshooting_recommendations(
        self, report: dict[str, Any]
    ) -> list[str]:
        """Generate system-level troubleshooting recommendations."""
        recommendations = []

        connectivity_severity = report["connectivity_diagnosis"].get("severity", "info")

        if connectivity_severity == "critical":
            recommendations.append(
                "CRITICAL: Fix API connectivity before proceeding with deployments"
            )
            recommendations.extend(
                report["connectivity_diagnosis"].get("recommendations", [])
            )
        elif connectivity_severity == "error":
            recommendations.append(
                "ERROR: Fix UI connectivity issues for full functionality"
            )
            recommendations.extend(
                report["connectivity_diagnosis"].get("recommendations", [])
            )

        if report.get("deployment_diagnosis"):
            deployment_severity = report["deployment_diagnosis"].get("severity", "info")
            if deployment_severity in ["error", "critical"]:
                recommendations.append("Fix deployment-specific issues identified")
                recommendations.extend(
                    report["deployment_diagnosis"].get("recommendations", [])
                )

        # General recommendations
        recommendations.extend(
            [
                "Verify all Prefect services are running (server, UI, workers)",
                "Check network connectivity and firewall settings",
                "Ensure environment variables are properly configured",
                "Review Prefect server logs for additional error details",
            ]
        )

        return recommendations

    def run_async(self, coro):
        """Helper to run async operations in sync context."""
        return self.ui_client.run_async(coro)
