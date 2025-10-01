#!/usr/bin/env python3
"""
Run flows to register them and show how to use the UI
"""

import os

from flows.rpa1.workflow import rpa1_workflow
from flows.rpa2.workflow import rpa2_workflow
from flows.rpa3.workflow import rpa3_workflow


def main():
    """Run flows to register them with Prefect server"""
    print("🚀 Running flows to register them with Prefect server...")
    print("📊 Flows will be available in the Prefect UI at http://localhost:4200")
    print()

    # Set the Prefect API URL
    os.environ["PREFECT_API_URL"] = "http://localhost:4200/api"

    try:
        print("📦 Running RPA1 workflow...")
        result1 = rpa1_workflow()
        print(f"✅ RPA1 completed: {result1}")
        print()

        print("📦 Running RPA2 workflow...")
        result2 = rpa2_workflow()
        print(f"✅ RPA2 completed: {result2}")
        print()

        print("📦 Running RPA3 workflow...")
        result3 = rpa3_workflow()
        print(f"✅ RPA3 completed: {result3}")
        print()

        print("🎉 All flows registered and executed successfully!")
        print("📊 Check the Prefect UI at http://localhost:4200")
        print()
        print("🔧 How to run flows from the UI:")
        print("1. Go to http://localhost:4200")
        print("2. Click on 'Flows' in the left sidebar")
        print("3. Click on any flow (rpa1-file-processing, rpa2-validation, rpa3-concurrent-processing)")
        print("4. Look for a 'Run' button or 'Quick Run' option")
        print("5. Click 'Run' to execute the flow")
        print()
        print("💡 If you don't see a Run button, the flows are registered but may need deployments.")
        print("   You can always run them using: make run-rpa1, make run-rpa2, make run-rpa3")

    except Exception as e:
        print(f"❌ Error running flows: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
