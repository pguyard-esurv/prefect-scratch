#!/usr/bin/env python3
"""
Set up Docker work pool and build images for RPA flows
"""

import os
import subprocess


def main():
    """Set up Docker infrastructure"""
    print("🚀 Setting up Docker infrastructure...")
    print()

    # Set the Prefect API URL
    os.environ["PREFECT_API_URL"] = "http://localhost:4200/api"

    try:
        # Create Docker work pool using CLI
        print("📦 Creating Docker work pool...")
        subprocess.run(
            ["prefect", "work-pool", "create", "docker-pool", "--type", "docker"],
            check=True,
            text=True,
            input="y\n"  # Automatically answer yes to any prompts
        )
        print("✅ Docker work pool created")

        # Build Docker images
        print("\n📦 Building Docker images...")

        # Build RPA1 image
        print("Building RPA1 image...")
        subprocess.run(
            ["docker", "build", "-t", "rpa1-worker:latest", "-f", "flows/rpa1/Dockerfile", "."],
            check=True
        )
        print("✅ RPA1 image built")

        # Build RPA2 image
        print("\nBuilding RPA2 image...")
        subprocess.run(
            ["docker", "build", "-t", "rpa2-worker:latest", "-f", "flows/rpa2/Dockerfile", "."],
            check=True
        )
        print("✅ RPA2 image built")

        # Build RPA3 image
        print("\nBuilding RPA3 image...")
        subprocess.run(
            ["docker", "build", "-t", "rpa3-worker:latest", "-f", "flows/rpa3/Dockerfile", "."],
            check=True
        )
        print("✅ RPA3 image built")

        print("\n🎉 Docker setup completed successfully!")
        print("📊 You can now create Docker deployments for your flows")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
