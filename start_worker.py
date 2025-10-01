#!/usr/bin/env python3
"""
Start Prefect worker for Docker work pool
"""

import os
import subprocess


def main():
    """Start Docker worker"""
    print("🚀 Starting Docker worker...")
    print("📊 Worker will process deployments from the docker-pool")
    print("🔧 Press Ctrl+C to stop the worker")
    print()

    # Set the Prefect API URL
    os.environ["PREFECT_API_URL"] = "http://localhost:4200/api"

    try:
        # Start the worker
        subprocess.run(
            ["prefect", "worker", "start", "--pool", "docker-pool"],
            check=True
        )

    except KeyboardInterrupt:
        print("\n🛑 Worker stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
