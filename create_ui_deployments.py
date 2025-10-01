#!/usr/bin/env python3
"""
Create deployments that can be run from the Prefect UI
"""

import os

from prefect import serve

from flows.rpa1.workflow import rpa1_workflow
from flows.rpa2.workflow import rpa2_workflow
from flows.rpa3.workflow import rpa3_workflow


def create_deployments():
    """Create deployments by serving flows"""
    print("🚀 Creating deployments for UI execution...")
    print("📊 Deployments will appear in the Prefect UI at http://localhost:4200")
    print("🔧 Press Ctrl+C to stop serving")
    print()

    # Set the Prefect API URL
    os.environ["PREFECT_API_URL"] = "http://localhost:4200/api"

    try:
        # Use serve() to create deployments - this is the correct way in Prefect 3.x
        serve(
            rpa1_workflow,
            rpa2_workflow,
            rpa3_workflow,
            limit=10
        )

    except KeyboardInterrupt:
        print("\n🛑 Stopped serving deployments")
    except Exception as e:
        print(f"❌ Error creating deployments: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_deployments()
