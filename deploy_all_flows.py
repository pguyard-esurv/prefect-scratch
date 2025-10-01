#!/usr/bin/env python3
"""
Automatically discover and deploy all flows in the codebase
"""

import importlib
import inspect
import os
import pkgutil

from prefect import Flow, serve


def discover_flows(package_path: str = "flows") -> list[tuple[str, Flow]]:
    """
    Discover all Prefect flows in the codebase.
    Returns list of (flow_name, flow_object) tuples.
    """
    flows = []

    def is_flow(obj):
        """Check if an object is a Prefect flow"""
        return hasattr(obj, "_is_flow") and obj._is_flow

    print(f"🔍 Discovering flows in {package_path}...")

    # Walk through all modules in the flows package
    package = importlib.import_module(package_path)
    for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        if not is_pkg:  # Only look at modules, not packages
            try:
                module = importlib.import_module(name)
                # Find all flow objects in the module
                for _attr_name, attr_value in inspect.getmembers(module):
                    if is_flow(attr_value):
                        flows.append((attr_value.name, attr_value))
                        print(f"✅ Found flow: {attr_value.name}")
            except Exception as e:
                print(f"⚠️  Error importing {name}: {e}")

    return flows

def main():
    """Main function to discover and deploy all flows"""
    print("🚀 Starting automatic flow deployment...")
    print("📊 Deployments will appear in the Prefect UI at http://localhost:4200")
    print()

    # Set the Prefect API URL
    os.environ["PREFECT_API_URL"] = "http://localhost:4200/api"

    try:
        # Discover all flows
        flows = discover_flows()
        print(f"\n📦 Found {len(flows)} flows to deploy")

        # Create deployments for each flow
        deployments = []
        for flow_name, flow_obj in flows:
            print(f"\n🔧 Creating deployment for {flow_name}...")
            deployment = flow_obj.to_deployment(
                name=f"{flow_name}-deployment",
                description=f"Auto-generated deployment for {flow_name}"
            )
            deployments.append(deployment)
            print(f"✅ Created deployment for {flow_name}")

        print("\n🚀 Starting deployment server...")
        print("📊 Your flows will be available at http://localhost:4200")
        print("🔧 Press Ctrl+C to stop serving")
        print("\n💡 Quick Tips:")
        print("1. View all flows: http://localhost:4200/flows")
        print("2. View deployments: http://localhost:4200/deployments")
        print("3. Monitor runs: http://localhost:4200/flow-runs")
        print("4. CLI: prefect deployment run [DEPLOYMENT_NAME]")

        # Serve all deployments
        serve(*deployments)

    except KeyboardInterrupt:
        print("\n🛑 Deployment server stopped")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
