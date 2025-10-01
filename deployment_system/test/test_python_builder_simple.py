"""
Simple test for Python Deployment Builder

Isolates and tests the core functionality.
"""

import sys
from pathlib import Path

# Add deployment_system to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from deployment_system.builders.python_builder import PythonDeploymentCreator
from deployment_system.discovery.metadata import FlowMetadata


def test_simple_python_deployment():
    """Test simple Python deployment creation without config manager."""
    print("=== Simple Python Deployment Test ===\n")

    # Create sample flow metadata
    flow = FlowMetadata(
        name="simple-test-flow",
        path="/app/flows/test/workflow.py",
        module_path="flows.test.workflow",
        function_name="test_flow",
        dependencies=["pandas>=1.5.0"],
        env_files=[".env.development"],
        is_valid=True,
        validation_errors=[],
        metadata={"description": "Simple test flow"},
    )

    print(f"Flow: {flow.name}")
    print(f"Module: {flow.module_path}")
    print(f"Function: {flow.function_name}")
    print(f"Valid: {flow.is_valid}")
    print(f"Supports Python: {flow.supports_python_deployment}")
    print()

    # Create Python deployment creator without config manager
    creator = PythonDeploymentCreator()

    try:
        # Create deployment configuration
        config = creator.create_deployment(flow, "development")

        print("✓ Successfully created deployment configuration")
        print(f"  Name: {config.deployment_name}")
        print(f"  Full Name: {config.full_name}")
        print(f"  Flow Name: {config.flow_name}")
        print(f"  Environment: {config.environment}")
        print(f"  Deployment Type: {config.deployment_type}")
        print(f"  Work Pool: {config.work_pool}")
        print(f"  Entrypoint: {config.entrypoint}")
        print(f"  Tags: {config.tags}")
        print(f"  Parameters: {config.parameters}")
        print(f"  Job Variables Keys: {list(config.job_variables.keys())}")

        if "env" in config.job_variables:
            print(
                f"  Environment Variables: {list(config.job_variables['env'].keys())}"
            )

        print()

        # Test validation
        validation_result = creator.validate_deployment_config(config)
        print(
            f"Validation Result: {'✓ Valid' if validation_result.is_valid else '✗ Invalid'}"
        )

        if validation_result.has_errors:
            print("Errors:")
            for error in validation_result.errors:
                print(f"  - [{error.code}] {error.message}")

        if validation_result.has_warnings:
            print("Warnings:")
            for warning in validation_result.warnings:
                print(f"  - [{warning.code}] {warning.message}")

        print()

        # Test dictionary conversion
        deployment_dict = config.to_dict()
        print("✓ Successfully converted to dictionary")
        print(f"  Dictionary keys: {list(deployment_dict.keys())}")

        return True

    except Exception as e:
        print(f"✗ Error creating deployment: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_simple_python_deployment()
    if success:
        print("✓ All tests passed!")
    else:
        print("✗ Tests failed!")
        sys.exit(1)
