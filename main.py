#!/usr/bin/env python3
"""
Main entry point for the RPA solution.
"""

import sys
from typing import Any

from flows.rpa1.workflow import rpa1_workflow
from flows.rpa2.workflow import rpa2_workflow


def run_rpa1() -> dict[str, Any]:
    """Run RPA1: File processing workflow."""
    print("🤖 Starting RPA1: File Processing Workflow...")
    result = rpa1_workflow()
    print(f"✅ RPA1 completed! Summary: {result}")
    return result


def run_rpa2() -> dict[str, Any]:
    """Run RPA2: Data validation workflow."""
    print("🤖 Starting RPA2: Data Validation Workflow...")
    result = rpa2_workflow()
    print(f"✅ RPA2 completed! Results: {result}")
    return result


def run_all() -> None:
    """Run all RPA workflows."""
    print("🤖 Starting Complete RPA Solution...")

    # Run RPA1
    run_rpa1()
    print()

    # Run RPA2
    run_rpa2()
    print()

    print("🎉 All RPA workflows completed successfully!")


def main():
    """Main entry point for running RPA workflows."""
    if len(sys.argv) > 1:
        workflow = sys.argv[1].lower()

        if workflow == "rpa1":
            run_rpa1()
        elif workflow == "rpa2":
            run_rpa2()
        elif workflow == "all":
            run_all()
        else:
            print(f"❌ Unknown workflow: {workflow}")
            print("Available workflows: rpa1, rpa2, all")
            sys.exit(1)
    else:
        # Default: run all workflows
        run_all()


if __name__ == "__main__":
    main()
