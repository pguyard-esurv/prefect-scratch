"""
Python Deployment Example

Demonstrates how to use the Python deployment creator.
"""

import sys
from pathlib import Path

# Add deployment_system to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from deployment_system.builders.python_builder import PythonDeploymentCreator
from deployment_system.config.manager import ConfigurationManager
from deployment_system.discovery.metadata import FlowMetadata


def create_sample_flow_metadata() -> FlowMetadata:
    """Create sample flow metadata for testing."""
    return FlowMetadata(
        name="sample-flow",
        path="/app/flows/sample/workflow.py",
        module_path="flows.sample.workflow",
        function_name="sample_flow",
        dependencies=["pandas>=1.5.0", "requests>=2.28.0"],
        env_files=[".env.development"],
        is_valid=True,
        validation_errors=[],
        metadata={"description": "Sample flow for testing"},
    )


def demonstrate_python_deployment():
    """Demonstrate Python deployment creation."""
    print("=== Python Deployment Creator Example ===\n")

    # Create configuration manager
    config_manager = ConfigurationManager()

    # Create Python deployment creator
    python_creator = PythonDeploymentCreator(config_manager)

    # Create sample flow metadata
    flow = create_sample_flow_metadata()

    print(f"Creating Python deployment for flow: {flow.name}")
    print(f"Flow module path: {flow.module_path}")
    print(f"Flow dependencies: {flow.dependencies}")
    print()

    # Test different environments
    environments = ["development", "staging", "production"]

    for env in environments:
        print(f"--- {env.upper()} Environment ---")

        try:
            # Create deployment configuration
            config = python_creator.create_deployment(flow, env)

            print(f"Deployment Name: {config.deployment_name}")
            print(f"Full Name: {config.full_name}")
            print(f"Work Pool: {config.work_pool}")
            print(f"Entrypoint: {config.entrypoint}")
            print(f"Environment: {config.environment}")
            print(f"Tags: {config.tags}")
            print(f"Parameters: {config.parameters}")
            print(f"Job Variables: {config.job_variables}")

            # Validate configuration
            validation_result = python_creator.validate_deployment_config(config)
            print(
                f"Validation: {'✓ Valid' if validation_result.is_valid else '✗ Invalid'}"
            )

            if validation_result.has_errors:
                print("Errors:")
                for error in validation_result.errors:
                    print(f"  - {error}")

            if validation_result.has_warnings:
                print("Warnings:")
                for warning in validation_result.warnings:
                    print(f"  - {warning}")

            # Convert to dictionary format
            deployment_dict = config.to_dict()
            print(f"Dictionary format keys: {list(deployment_dict.keys())}")

        except Exception as e:
            print(f"Error creating deployment for {env}: {e}")

        print()

    # Demonstrate template usage
    print("--- Template Information ---")
    template = python_creator.get_deployment_template()
    print(f"Default Python template keys: {list(template.keys())}")
    print()

    # Demonstrate environment-specific parameter handling
    print("--- Environment-Specific Parameters ---")
    for env in environments:
        env_config = config_manager.get_environment_config(env)
        if env_config:
            print(f"{env}: {env_config.default_parameters}")
        else:
            print(f"{env}: No configuration found")
    print()


def demonstrate_deployment_api_integration():
    """Demonstrate Prefect API integration (without actually calling API)."""
    print("=== Prefect API Integration Example ===\n")

    # Create configuration manager and Python creator
    config_manager = ConfigurationManager()
    python_creator = PythonDeploymentCreator(config_manager)

    # Create sample flow
    flow = create_sample_flow_metadata()

    print(f"Preparing to deploy flow: {flow.name}")
    print("Note: This example shows the process without actually calling Prefect API")
    print()

    try:
        # Create deployment configuration
        config = python_creator.create_deployment(flow, "development")

        print("Deployment Configuration:")
        print(f"  Name: {config.full_name}")
        print(f"  Entrypoint: {config.entrypoint}")
        print(f"  Work Pool: {config.work_pool}")
        print(f"  Environment: {config.environment}")
        print()

        # Validate before deployment
        validation_result = python_creator.validate_deployment_config(config)

        if validation_result.is_valid:
            print("✓ Configuration is valid and ready for deployment")
            print(
                "  To deploy to Prefect, call: python_creator.deploy_to_prefect(flow, 'development')"
            )
        else:
            print("✗ Configuration has validation errors:")
            for error in validation_result.errors:
                print(f"    - {error.message}")
                print(f"      Remediation: {error.remediation}")

    except Exception as e:
        print(f"Error in deployment preparation: {e}")


if __name__ == "__main__":
    demonstrate_python_deployment()
    print("\n" + "=" * 60 + "\n")
    demonstrate_deployment_api_integration()
