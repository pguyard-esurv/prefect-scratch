#!/usr/bin/env python3
"""
Deploy flows to Prefect server - makes them appear in the UI
"""

import os
import subprocess
import sys


def main():
    """Deploy all flows to the Prefect server"""
    print("🚀 Deploying flows to Prefect server...")
    print("📊 Flows will appear in the Prefect UI at http://localhost:4200")
    print()

    # Check if Prefect API URL is set
    api_url = os.getenv("PREFECT_API_URL", "http://localhost:4200/api")
    print(f"🔗 Connecting to Prefect server: {api_url}")

    try:
        # Serve flows using the flow serve command (more compatible)
        print("🚀 Starting flow server...")
        print("📊 Flows will be available at http://localhost:4200")
        print("🔧 Press Ctrl+C to stop the server")
        print()

        # Start serving all flows
        result = subprocess.run([
            "uv", "run", "prefect", "flow", "serve",
            "flows/rpa1/workflow.py:rpa1_workflow",
            "flows/rpa2/workflow.py:rpa2_workflow",
            "flows/rpa3/workflow.py:rpa3_workflow"
        ], capture_output=False, text=True)

        if result.returncode != 0:
            print(f"❌ Failed to serve flows: {result.stderr}")
        else:
            print("✅ Flows served successfully")

        print("\n🎉 All flows deployed successfully!")
        print("📊 Check the Prefect UI at http://localhost:4200 to see your flows")

    except Exception as e:
        print(f"❌ Error deploying flows: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
