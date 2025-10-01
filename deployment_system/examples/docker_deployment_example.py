"""
Docker Deployment Example

Demonstrates how to use the Docker deployment builder to create containerized deployments.
"""

import logging
from pathlib import Path

from deployment_system.builders.docker_builder import DockerDeploymentCreator
from deployment_system.discovery.metadata import FlowMetadata
from deployment_system.validation.docker_validator import DockerValidator

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_sample_flow_metadata() -> FlowMetadata:
    """Create sample flow metadata for demonstration."""
    return FlowMetadata(
        name="rpa1",
        path="/app/flows/rpa1/workflow.py",
        module_path="flows.rpa1.workflow",
        function_name="rpa1_flow",
        dockerfile_path="/app/flows/rpa1/Dockerfile",
        env_files=[
            "/app/flows/rpa1/.env.development",
            "/app/flows/rpa1/.env.production",
        ],
        dependencies=["pandas>=1.5.0", "requests>=2.28.0", "sqlalchemy>=1.4.0"],
    )


def demonstrate_docker_deployment_creation():
    """Demonstrate creating Docker deployments."""
    logger.info("=== Docker Deployment Creation Demo ===")

    # Create Docker deployment builder
    docker_builder = DockerDeploymentCreator()

    # Create sample flow metadata
    flow = create_sample_flow_metadata()
    logger.info(f"Created flow metadata for: {flow.name}")
    logger.info(f"  - Supports Docker: {flow.supports_docker_deployment}")
    logger.info(f"  - Dockerfile path: {flow.dockerfile_path}")

    # Create deployment for different environments
    environments = ["development", "staging", "production"]

    for env in environments:
        logger.info(f"\n--- Creating {env} deployment ---")

        try:
            # Create deployment configuration
            config = docker_builder.create_deployment(flow, env)

            logger.info(f"Deployment name: {config.deployment_name}")
            logger.info(f"Work pool: {config.work_pool}")
            logger.info(f"Docker image: {config.job_variables.get('image', 'N/A')}")
            logger.info(
                f"Environment variables: {len(config.job_variables.get('env', {}))}"
            )
            logger.info(
                f"Volume mounts: {len(config.job_variables.get('volumes', []))}"
            )
            logger.info(f"Tags: {config.tags}")

            # Validate the configuration
            validation_result = docker_builder.validate_deployment_config(config)
            logger.info(
                f"Validation: {'✓ Valid' if validation_result.is_valid else '✗ Invalid'}"
            )

            if validation_result.errors:
                for error in validation_result.errors:
                    logger.error(f"  Error: {error.message}")

            if validation_result.warnings:
                for warning in validation_result.warnings:
                    logger.warning(f"  Warning: {warning.message}")

        except Exception as e:
            logger.error(f"Failed to create {env} deployment: {e}")


def demonstrate_docker_validation():
    """Demonstrate Docker validation capabilities."""
    logger.info("\n=== Docker Validation Demo ===")

    docker_validator = DockerValidator()
    docker_builder = DockerDeploymentCreator()

    # Test Dockerfile validation
    dockerfile_paths = [
        "flows/rpa1/Dockerfile",
        "flows/rpa2/Dockerfile",
        "flows/rpa3/Dockerfile",
    ]

    for dockerfile_path in dockerfile_paths:
        logger.info(f"\n--- Validating {dockerfile_path} ---")

        if Path(dockerfile_path).exists():
            result = docker_validator.validate_dockerfile(dockerfile_path)
            logger.info(
                f"Dockerfile validation: {'✓ Valid' if result.is_valid else '✗ Invalid'}"
            )

            for error in result.errors:
                logger.error(f"  Error: {error.message}")
            for warning in result.warnings:
                logger.warning(f"  Warning: {warning.message}")
        else:
            logger.warning(f"  Dockerfile not found: {dockerfile_path}")

    # Test Docker image validation
    test_images = [
        "rpa1-worker:latest",
        "rpa2-worker:latest",
        "rpa3-worker:latest",
        "nonexistent-image:latest",
    ]

    for image in test_images:
        logger.info(f"\n--- Validating image {image} ---")
        result = docker_builder.validate_docker_image(image)

        logger.info(
            f"Image validation: {'✓ Valid' if result.is_valid else '✗ Invalid'}"
        )
        for warning in result.warnings:
            logger.warning(f"  Warning: {warning.message}")


def demonstrate_docker_compose_integration():
    """Demonstrate Docker Compose integration validation."""
    logger.info("\n=== Docker Compose Integration Demo ===")

    docker_validator = DockerValidator()

    # Test flows for Docker Compose integration
    test_flows = ["rpa1", "rpa2", "rpa3"]

    for flow_name in test_flows:
        logger.info(f"\n--- Checking {flow_name} Docker Compose integration ---")

        result = docker_validator.validate_docker_compose_integration(
            flow_name, "docker-compose.yml"
        )

        logger.info(
            f"Docker Compose integration: {'✓ Valid' if result.is_valid else '✗ Invalid'}"
        )

        for warning in result.warnings:
            logger.warning(f"  Warning: {warning.message}")


def demonstrate_deployment_templates():
    """Demonstrate Docker deployment templates."""
    logger.info("\n=== Docker Deployment Templates Demo ===")

    docker_builder = DockerDeploymentCreator()

    # Get deployment template
    template = docker_builder.get_deployment_template()

    logger.info("Docker deployment template structure:")
    logger.info(f"  - Work pool: {template.get('work_pool', 'N/A')}")
    logger.info(
        f"  - Job variables keys: {list(template.get('job_variables', {}).keys())}"
    )
    logger.info(f"  - Parameters: {template.get('parameters', 'N/A')}")
    logger.info(f"  - Tags: {template.get('tags', [])}")

    # Show resource limits for different environments
    environments = ["development", "staging", "production"]

    logger.info("\nResource limits by environment:")
    for env in environments:
        resources = docker_builder._get_resource_limits(env)
        logger.info(f"  {env}:")
        logger.info(f"    Memory: {resources['memory']}")
        logger.info(f"    CPU: {resources['cpus']}")


def main():
    """Run all Docker deployment demonstrations."""
    logger.info("Docker Deployment Builder Example")
    logger.info("=" * 50)

    try:
        demonstrate_docker_deployment_creation()
        demonstrate_docker_validation()
        demonstrate_docker_compose_integration()
        demonstrate_deployment_templates()

        logger.info("\n" + "=" * 50)
        logger.info("Docker deployment demonstration completed successfully!")

    except Exception as e:
        logger.error(f"Demonstration failed: {e}")
        raise


if __name__ == "__main__":
    main()
