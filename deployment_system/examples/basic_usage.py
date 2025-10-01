#!/usr/bin/env python3
"""
Basic Usage Example

Demonstrates basic usage of the deployment system.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from deployment_system import ConfigurationManager, DeploymentBuilder, FlowDiscovery


def main():
    """Demonstrate basic deployment system usage."""
    print("Deployment System Basic Usage Example")
    print("=" * 50)

    # Initialize components
    print("\n1. Initializing components...")
    discovery = FlowDiscovery()
    config_manager = ConfigurationManager()
    builder = DeploymentBuilder(config_manager)

    # Discover flows
    print("\n2. Discovering flows...")
    flows = discovery.discover_flows()
    print(f"Found {len(flows)} flows:")

    for flow in flows:
        status = "✓" if flow.is_valid else "✗"
        python_support = "✓" if flow.supports_python_deployment else "✗"
        docker_support = "✓" if flow.supports_docker_deployment else "✗"

        print(f"  {status} {flow.name}")
        print(f"    Path: {flow.path}")
        print(f"    Python: {python_support} | Docker: {docker_support}")

        if not flow.is_valid and flow.validation_errors:
            for error in flow.validation_errors[:2]:  # Show first 2 errors
                print(f"    Error: {error}")

    # Show environments
    print("\n3. Available environments:")
    environments = config_manager.list_environments()
    for env in environments:
        print(f"  - {env}")

    # Get deployment summary
    print("\n4. Deployment capabilities:")
    summary = builder.get_deployment_summary(flows)
    print(f"  Total flows: {summary['total_flows']}")
    print(f"  Python capable: {summary['python_capable']}")
    print(f"  Docker capable: {summary['docker_capable']}")
    print(f"  Both capable: {summary['both_capable']}")
    print(f"  Invalid flows: {summary['invalid_flows']}")

    print("\n5. Example deployment creation:")
    valid_flows = [f for f in flows if f.is_valid]
    if valid_flows:
        example_flow = valid_flows[0]
        print(f"  Creating Python deployment for: {example_flow.name}")

        try:
            deployment_config = builder.create_python_deployment(
                example_flow, "development"
            )
            print(f"  ✓ Created deployment: {deployment_config['name']}")
            print(f"  ✓ Work pool: {deployment_config['work_pool']}")
            print(f"  ✓ Entrypoint: {deployment_config['entrypoint']}")
        except Exception as e:
            print(f"  ✗ Failed to create deployment: {e}")
    else:
        print("  No valid flows found for deployment creation")

    print("\n" + "=" * 50)
    print("Example completed successfully!")


if __name__ == "__main__":
    main()
