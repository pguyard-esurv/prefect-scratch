#!/usr/bin/env python3
"""
Validation System Demo

Demonstrates the comprehensive deployment validation system.
"""

import tempfile
from pathlib import Path

from ..config.deployment_config import DeploymentConfig
from ..discovery.metadata import FlowMetadata
from .comprehensive_validator import ComprehensiveValidator


def create_sample_flow() -> str:
    """Create a sample flow file for demonstration."""
    flow_content = '''
from prefect import flow, task
import pandas as pd
import requests

@task
def fetch_data():
    """Fetch some data."""
    response = requests.get("https://api.example.com/data")
    return response.json()

@task
def process_data(data):
    """Process the data."""
    df = pd.DataFrame(data)
    return df.describe()

@flow(name="sample-data-processing")
def sample_flow():
    """Sample data processing flow."""
    data = fetch_data()
    result = process_data(data)
    return result
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(flow_content)
        return f.name


def create_sample_dockerfile() -> str:
    """Create a sample Dockerfile for demonstration."""
    dockerfile_content = """
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PREFECT_API_URL=http://prefect-server:4200/api

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

# Run the Prefect worker
CMD ["python", "-m", "prefect", "worker", "start", "--pool", "docker-pool"]
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix="", delete=False) as f:
        f.write(dockerfile_content)
        return f.name


def demo_flow_validation():
    """Demonstrate flow validation."""
    print("🔍 Flow Validation Demo")
    print("=" * 50)

    validator = ComprehensiveValidator()
    flow_file = create_sample_flow()

    try:
        # Test syntax validation
        print("\n1. Testing Flow Syntax Validation...")
        syntax_result = validator.flow_validator.validate_flow_syntax(flow_file)
        print(f"   Syntax Valid: {syntax_result.is_valid}")
        if syntax_result.has_errors:
            for error in syntax_result.errors:
                print(f"   ❌ {error}")

        # Test dependency validation
        print("\n2. Testing Flow Dependencies Validation...")
        deps_result = validator.flow_validator.validate_flow_dependencies(flow_file)
        print(f"   Dependencies Valid: {deps_result.is_valid}")
        if deps_result.has_warnings:
            for warning in deps_result.warnings:
                print(f"   ⚠️  {warning}")

        # Test structure validation
        print("\n3. Testing Flow Structure Validation...")
        structure_result = validator.flow_validator.validate_flow_structure(flow_file)
        print(f"   Structure Valid: {structure_result.is_valid}")
        if structure_result.has_warnings:
            for warning in structure_result.warnings:
                print(f"   ⚠️  {warning}")

    finally:
        Path(flow_file).unlink(missing_ok=True)


def demo_deployment_validation():
    """Demonstrate deployment configuration validation."""
    print("\n\n🚀 Deployment Configuration Validation Demo")
    print("=" * 50)

    validator = ComprehensiveValidator()

    # Test valid Python deployment
    print("\n1. Testing Valid Python Deployment...")
    python_config = DeploymentConfig(
        flow_name="sample-flow",
        deployment_name="sample-python-deployment",
        environment="development",
        deployment_type="python",
        work_pool="default-agent-pool",
        entrypoint="flows.sample.workflow:sample_flow",
        schedule="0 9 * * 1-5",  # Weekdays at 9 AM
        parameters={"env": "dev", "debug": True},
        tags=["data-processing", "development"],
    )

    python_result = validator.deployment_validator.validate_deployment_config(
        python_config
    )
    print(f"   Python Deployment Valid: {python_result.is_valid}")
    if python_result.has_warnings:
        for warning in python_result.warnings:
            print(f"   ⚠️  {warning}")

    # Test valid Docker deployment
    print("\n2. Testing Valid Docker Deployment...")
    docker_config = DeploymentConfig(
        flow_name="sample-flow",
        deployment_name="sample-docker-deployment",
        environment="production",
        deployment_type="docker",
        work_pool="docker-pool",
        entrypoint="flows.sample.workflow:sample_flow",
        job_variables={
            "image": "sample-flow:latest",
            "env": {
                "PREFECT_API_URL": "http://prefect-server:4200/api",
                "LOG_LEVEL": "INFO",
            },
            "volumes": ["./data:/app/data", "./logs:/app/logs"],
            "networks": ["rpa-network"],
        },
        parameters={"env": "prod", "batch_size": 1000},
    )

    docker_result = validator.deployment_validator.validate_deployment_config(
        docker_config
    )
    print(f"   Docker Deployment Valid: {docker_result.is_valid}")
    if docker_result.has_warnings:
        for warning in docker_result.warnings:
            print(f"   ⚠️  {warning}")

    # Test invalid deployment
    print("\n3. Testing Invalid Deployment Configuration...")
    try:
        invalid_config = DeploymentConfig(
            flow_name="invalid-flow",  # Use valid name to avoid __post_init__ error
            deployment_name="invalid-deployment",
            environment="unknown-env",
            deployment_type="invalid-type",  # Invalid type
            work_pool="",  # Invalid: empty work pool
            entrypoint="invalid_entrypoint_format",  # Invalid: no colon
            schedule="invalid cron format",  # Invalid schedule
        )

        invalid_result = validator.deployment_validator.validate_deployment_config(
            invalid_config
        )
        print(f"   Invalid Deployment Valid: {invalid_result.is_valid}")
        if invalid_result.has_errors:
            for error in invalid_result.errors:
                print(f"   ❌ {error}")
    except ValueError as e:
        print(f"   ❌ Configuration creation failed (as expected): {e}")


def demo_docker_validation():
    """Demonstrate Docker validation."""
    print("\n\n🐳 Docker Validation Demo")
    print("=" * 50)

    validator = ComprehensiveValidator()
    dockerfile_path = create_sample_dockerfile()

    try:
        # Test Dockerfile validation
        print("\n1. Testing Dockerfile Validation...")
        dockerfile_result = validator.docker_validator.validate_dockerfile(
            dockerfile_path
        )
        print(f"   Dockerfile Valid: {dockerfile_result.is_valid}")
        if dockerfile_result.has_warnings:
            for warning in dockerfile_result.warnings:
                print(f"   ⚠️  {warning}")

        # Test Docker image validation
        print("\n2. Testing Docker Image Validation...")
        image_result = validator.docker_validator.validate_docker_image_exists(
            "nonexistent-image:latest"
        )
        print(f"   Image Exists: {image_result.is_valid}")
        if image_result.has_warnings:
            for warning in image_result.warnings:
                print(f"   ⚠️  {warning}")

        # Test Docker Compose integration
        print("\n3. Testing Docker Compose Integration...")
        compose_result = validator.docker_validator.validate_docker_compose_integration(
            "sample-flow"
        )
        print(f"   Compose Integration Valid: {compose_result.is_valid}")
        if compose_result.has_warnings:
            for warning in compose_result.warnings:
                print(f"   ⚠️  {warning}")

    finally:
        Path(dockerfile_path).unlink(missing_ok=True)


def demo_comprehensive_validation():
    """Demonstrate comprehensive validation."""
    print("\n\n🎯 Comprehensive Validation Demo")
    print("=" * 50)

    validator = ComprehensiveValidator()
    flow_file = create_sample_flow()
    dockerfile_path = create_sample_dockerfile()

    try:
        # Create flow metadata
        flow_metadata = FlowMetadata(
            name="sample-flow",
            path=flow_file,
            module_path="flows.sample.workflow",
            function_name="sample_flow",
            dependencies=["prefect", "pandas", "requests"],
            dockerfile_path=dockerfile_path,
            env_files=[".env.development"],
            is_valid=True,
            validation_errors=[],
            metadata={"description": "Sample data processing flow"},
        )

        # Create deployment configurations
        python_config = DeploymentConfig(
            flow_name="sample-flow",
            deployment_name="sample-python-deployment",
            environment="development",
            deployment_type="python",
            work_pool="default-agent-pool",
            entrypoint="flows.sample.workflow:sample_flow",
        )

        docker_config = DeploymentConfig(
            flow_name="sample-flow",
            deployment_name="sample-docker-deployment",
            environment="production",
            deployment_type="docker",
            work_pool="docker-pool",
            entrypoint="flows.sample.workflow:sample_flow",
            job_variables={"image": "sample-flow:latest"},
        )

        # Test comprehensive validation
        print("\n1. Testing Python Deployment Comprehensive Validation...")
        python_result = validator.validate_flow_for_deployment(
            flow_metadata, python_config
        )
        print(f"   Overall Valid: {python_result.is_valid}")
        print(
            f"   Errors: {python_result.error_count}, Warnings: {python_result.warning_count}"
        )

        print("\n2. Testing Docker Deployment Comprehensive Validation...")
        docker_result = validator.validate_flow_for_deployment(
            flow_metadata, docker_config
        )
        print(f"   Overall Valid: {docker_result.is_valid}")
        print(
            f"   Errors: {docker_result.error_count}, Warnings: {docker_result.warning_count}"
        )

        # Test multiple deployments validation
        print("\n3. Testing Multiple Deployments Validation...")
        deployments = [(flow_metadata, python_config), (flow_metadata, docker_config)]

        multiple_results = validator.validate_multiple_deployments(deployments)
        print(f"   Validated {len(multiple_results)} deployments")

        for deployment_name, result in multiple_results.items():
            status = "✅" if result.is_valid else "❌"
            print(f"   {status} {deployment_name}: {result.get_summary()}")

        # Generate validation report
        print("\n4. Generating Validation Report...")
        report = validator.generate_validation_report(multiple_results)
        print("   Report generated successfully!")
        print(f"   Report length: {len(report)} characters")

        # Show a snippet of the report
        print("\n   Report snippet:")
        lines = report.split("\n")[:10]
        for line in lines:
            print(f"   {line}")
        if len(report.split("\n")) > 10:
            print("   ...")

    finally:
        Path(flow_file).unlink(missing_ok=True)
        Path(dockerfile_path).unlink(missing_ok=True)


def main():
    """Run all validation demos."""
    print("🎉 Deployment Validation System Demo")
    print("=" * 60)
    print("This demo showcases the comprehensive validation capabilities")
    print("of the Prefect deployment system.")

    try:
        demo_flow_validation()
        demo_deployment_validation()
        demo_docker_validation()
        demo_comprehensive_validation()

        print("\n\n✅ All validation demos completed successfully!")
        print("\nThe validation system provides:")
        print("• Flow syntax and structure validation")
        print("• Dependency checking and resolution")
        print("• Deployment configuration validation")
        print("• Docker setup and build validation")
        print("• Comprehensive cross-validation")
        print("• Detailed error reporting with remediation steps")
        print("• Multiple deployment conflict detection")
        print("• Validation report generation")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
