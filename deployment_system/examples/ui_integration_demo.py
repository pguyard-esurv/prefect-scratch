#!/usr/bin/env python3
"""
UI Integration Demo

Demonstrates the UI integration and verification capabilities.
"""

import asyncio
import os

from deployment_system.ui import (
    DeploymentStatusChecker,
    TroubleshootingUtilities,
    UIClient,
    UIValidator,
)


async def demo_ui_integration():
    """Demonstrate UI integration capabilities."""
    print("🚀 Prefect UI Integration Demo")
    print("=" * 50)

    # Use environment variables or defaults
    api_url = os.getenv("PREFECT_API_URL", "http://localhost:4200/api")
    ui_url = os.getenv("PREFECT_UI_URL", "http://localhost:4200")

    print(f"API URL: {api_url}")
    print(f"UI URL: {ui_url}")
    print()

    # Initialize components
    ui_client = UIClient(api_url, ui_url)
    status_checker = DeploymentStatusChecker(api_url, ui_url)
    UIValidator(api_url, ui_url)
    troubleshooter = TroubleshootingUtilities(api_url, ui_url)

    try:
        # 1. Check API connectivity
        print("1️⃣ Checking API Connectivity...")
        api_check = await ui_client.check_api_connectivity()
        print(f"   Connected: {'✅' if api_check['connected'] else '❌'}")
        if api_check["connected"]:
            print(f"   Response Time: {api_check['response_time_ms']}ms")
        else:
            print(f"   Error: {api_check['error']}")
        print()

        # 2. Check UI accessibility
        print("2️⃣ Checking UI Accessibility...")
        ui_check = await ui_client.check_ui_accessibility()
        print(f"   Accessible: {'✅' if ui_check['accessible'] else '❌'}")
        if ui_check["accessible"]:
            print(f"   Response Time: {ui_check['response_time_ms']}ms")
            print(f"   Status Code: {ui_check['status_code']}")
        else:
            print(f"   Error: {ui_check['error']}")
        print()

        # 3. List deployments with UI status
        print("3️⃣ Listing Deployments with UI Status...")
        deployments = await ui_client.list_deployments_with_ui_status()
        if deployments:
            print(f"   Found {len(deployments)} deployments:")
            for deployment in deployments[:3]:  # Show first 3
                ui_accessible = "✅" if deployment.get("ui_accessible") else "❌"
                print(
                    f"   • {deployment['flow_name']}/{deployment['name']} - UI: {ui_accessible}"
                )
        else:
            print("   No deployments found")
        print()

        # 4. Generate status report
        print("4️⃣ Generating Status Report...")
        report = await status_checker.get_deployment_status_report()
        summary = report["summary"]
        print(f"   Total Deployments: {summary['total_deployments']}")
        print(
            f"   Healthy: {summary['healthy_deployments']} ({summary['health_percentage']:.1f}%)"
        )
        print(f"   API Connected: {'✅' if summary['api_connected'] else '❌'}")
        print(f"   UI Accessible: {'✅' if summary['ui_accessible'] else '❌'}")
        print()

        # 5. Run connectivity troubleshooting
        print("5️⃣ Running Connectivity Troubleshooting...")
        diagnosis = await troubleshooter.diagnose_connectivity_issues()
        severity_icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
        severity = diagnosis["severity"]
        print(
            f"   Overall Severity: {severity_icons.get(severity, 'ℹ️')} {severity.upper()}"
        )

        if diagnosis.get("recommendations"):
            print("   Top Recommendations:")
            for rec in diagnosis["recommendations"][:3]:
                print(f"   • {rec}")
        print()

        # 6. Test specific deployment if available
        if deployments:
            deployment = deployments[0]
            deployment_name = deployment["name"]
            flow_name = deployment["flow_name"]

            print(f"6️⃣ Testing Specific Deployment: {flow_name}/{deployment_name}")

            # Check deployment health
            health = await status_checker.check_deployment_health(
                deployment_name, flow_name
            )
            print(
                f"   Health Status: {'✅' if health['healthy'] else '❌'} {health['status'].upper()}"
            )

            # Verify UI presence
            ui_verification = await ui_client.verify_deployment_in_ui(
                deployment_name, flow_name, timeout_seconds=5
            )
            print(f"   UI Visible: {'✅' if ui_verification['visible'] else '❌'}")

            # Get UI URL
            ui_url_result = await ui_client.get_deployment_ui_url(
                deployment_name, flow_name
            )
            if ui_url_result:
                print(f"   UI URL: {ui_url_result}")
            print()

        print("✅ Demo completed successfully!")

    except Exception as e:
        print(f"❌ Demo failed with error: {e}")

        # Run troubleshooting on error
        print("\n🔧 Running troubleshooting...")
        try:
            diagnosis = await troubleshooter.diagnose_connectivity_issues()
            print(f"Diagnosis severity: {diagnosis['severity']}")
            if diagnosis.get("recommendations"):
                print("Recommendations:")
                for rec in diagnosis["recommendations"][:3]:
                    print(f"  • {rec}")
        except Exception as troubleshoot_error:
            print(f"Troubleshooting also failed: {troubleshoot_error}")

    finally:
        # Clean up
        await ui_client.close()


def main():
    """Run the demo."""
    print("Starting Prefect UI Integration Demo...")
    print("Make sure Prefect server is running on http://localhost:4200")
    print()

    try:
        asyncio.run(demo_ui_integration())
    except KeyboardInterrupt:
        print("\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n💥 Demo failed: {e}")


if __name__ == "__main__":
    main()
