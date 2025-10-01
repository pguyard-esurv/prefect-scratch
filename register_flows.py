#!/usr/bin/env python3
"""
Register flows with Prefect server
"""

import os

from flows.rpa1.workflow import rpa1_workflow
from flows.rpa2.workflow import rpa2_workflow
from flows.rpa3.workflow import rpa3_workflow


def main():
    """Register flows with Prefect server"""
    print("🚀 Registering flows with Prefect server...")
    print("📊 Flows will appear in the Prefect UI at http://localhost:4200")
    print()

    # Set the Prefect API URL
    os.environ["PREFECT_API_URL"] = "http://localhost:4200/api"

    # Run each flow once to register it
    print("📦 Running RPA1 flow...")
    rpa1_workflow()
    print("✅ RPA1 flow registered")

    print("📦 Running RPA2 flow...")
    rpa2_workflow()
    print("✅ RPA2 flow registered")

    print("📦 Running RPA3 flow...")
    rpa3_workflow()
    print("✅ RPA3 flow registered")

    print("\n🎉 All flows registered successfully!")
    print("📊 Check the Prefect UI at http://localhost:4200 to see your flows")

if __name__ == "__main__":
    main()
