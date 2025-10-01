#!/usr/bin/env python3
"""
Build Docker images for RPA flows
"""

import subprocess


def main():
    """Build Docker images"""
    print("🚀 Building Docker images...")
    print()

    try:
        # Build RPA1 image
        print("📦 Building RPA1 image...")
        subprocess.run(
            ["docker", "build", "-t", "rpa1-worker:latest", "-f", "flows/rpa1/Dockerfile", "."],
            check=True
        )
        print("✅ RPA1 image built")

        # Build RPA2 image
        print("\n📦 Building RPA2 image...")
        subprocess.run(
            ["docker", "build", "-t", "rpa2-worker:latest", "-f", "flows/rpa2/Dockerfile", "."],
            check=True
        )
        print("✅ RPA2 image built")

        # Build RPA3 image
        print("\n📦 Building RPA3 image...")
        subprocess.run(
            ["docker", "build", "-t", "rpa3-worker:latest", "-f", "flows/rpa3/Dockerfile", "."],
            check=True
        )
        print("✅ RPA3 image built")

        print("\n🎉 All images built successfully!")
        print("📊 You can now create deployments with:")
        print("   python create_deployments.py")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
