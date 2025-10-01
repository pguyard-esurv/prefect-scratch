"""
Docker Validator

Validates Docker-related configurations and images.
"""

import subprocess
from pathlib import Path

from .validation_result import ValidationError, ValidationResult, ValidationWarning


class DockerValidator:
    """Validates Docker configurations and images."""

    def validate_dockerfile(self, dockerfile_path: str) -> ValidationResult:
        """Validate a Dockerfile."""
        errors = []
        warnings = []

        path = Path(dockerfile_path)
        if not path.exists():
            errors.append(
                ValidationError(
                    code="DOCKERFILE_NOT_FOUND",
                    message=f"Dockerfile not found: {dockerfile_path}",
                    file_path=dockerfile_path,
                    remediation="Create a Dockerfile or update the path",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        try:
            with open(path, encoding="utf-8") as f:
                content = f.read()

            lines = [line.strip() for line in content.split("\n") if line.strip()]

            # Check for FROM instruction
            if not any(line.startswith("FROM") for line in lines):
                errors.append(
                    ValidationError(
                        code="DOCKERFILE_MISSING_FROM",
                        message="Dockerfile is missing FROM instruction",
                        file_path=dockerfile_path,
                        remediation="Add a FROM instruction to specify the base image",
                    )
                )

            # Check for common best practices
            self._validate_dockerfile_best_practices(lines, warnings, dockerfile_path)

        except Exception as e:
            errors.append(
                ValidationError(
                    code="DOCKERFILE_READ_ERROR",
                    message=f"Failed to read Dockerfile: {str(e)}",
                    file_path=dockerfile_path,
                    remediation="Ensure the Dockerfile is readable",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_docker_image_exists(self, image_name: str) -> ValidationResult:
        """Validate that a Docker image exists locally."""
        errors = []
        warnings = []

        try:
            result = subprocess.run(
                ["docker", "image", "inspect", image_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                warnings.append(
                    ValidationWarning(
                        code="DOCKER_IMAGE_NOT_FOUND",
                        message=f"Docker image '{image_name}' not found locally",
                        suggestion=f"Build the image with: docker build -t {image_name} .",
                    )
                )

        except subprocess.TimeoutExpired:
            warnings.append(
                ValidationWarning(
                    code="DOCKER_INSPECT_TIMEOUT",
                    message=f"Timeout while checking Docker image '{image_name}'",
                    suggestion="Check Docker daemon status",
                )
            )
        except FileNotFoundError:
            errors.append(
                ValidationError(
                    code="DOCKER_NOT_AVAILABLE",
                    message="Docker command not found",
                    remediation="Install Docker or ensure it's in PATH",
                )
            )
        except Exception as e:
            warnings.append(
                ValidationWarning(
                    code="DOCKER_VALIDATION_ERROR",
                    message=f"Error validating Docker image '{image_name}': {e}",
                    suggestion="Check Docker configuration and image name",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_docker_compose_integration(
        self, flow_name: str, compose_file: str = "docker-compose.yml"
    ) -> ValidationResult:
        """Validate Docker Compose integration for a flow."""
        errors = []
        warnings = []

        compose_path = Path(compose_file)
        if not compose_path.exists():
            warnings.append(
                ValidationWarning(
                    code="DOCKER_COMPOSE_NOT_FOUND",
                    message=f"Docker Compose file not found: {compose_file}",
                    suggestion="Create docker-compose.yml for container orchestration",
                )
            )
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        try:
            # Check if flow service is defined in docker-compose.yml
            with open(compose_path, encoding="utf-8") as f:
                content = f.read()

            service_name = f"{flow_name}-worker"
            if service_name not in content:
                warnings.append(
                    ValidationWarning(
                        code="FLOW_SERVICE_NOT_DEFINED",
                        message=f"Service '{service_name}' not found in {compose_file}",
                        suggestion=f"Add service definition for {service_name} in docker-compose.yml",
                    )
                )

            # Check for network configuration
            if "rpa-network" not in content:
                warnings.append(
                    ValidationWarning(
                        code="NETWORK_NOT_CONFIGURED",
                        message="rpa-network not found in docker-compose.yml",
                        suggestion="Ensure rpa-network is defined for service communication",
                    )
                )

        except Exception as e:
            warnings.append(
                ValidationWarning(
                    code="DOCKER_COMPOSE_READ_ERROR",
                    message=f"Failed to read {compose_file}: {e}",
                    suggestion="Ensure docker-compose.yml is readable",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_dockerfile_best_practices(
        self, lines: list[str], warnings: list[ValidationWarning], dockerfile_path: str
    ) -> None:
        """Validate Dockerfile against best practices."""
        # Check for WORKDIR instruction
        if not any(line.startswith("WORKDIR") for line in lines):
            warnings.append(
                ValidationWarning(
                    code="DOCKERFILE_MISSING_WORKDIR",
                    message="Dockerfile is missing WORKDIR instruction",
                    file_path=dockerfile_path,
                    suggestion="Add WORKDIR instruction to set working directory",
                )
            )

        # Check for COPY or ADD instruction
        if not any(line.startswith(("COPY", "ADD")) for line in lines):
            warnings.append(
                ValidationWarning(
                    code="DOCKERFILE_MISSING_COPY",
                    message="Dockerfile is missing COPY or ADD instruction",
                    file_path=dockerfile_path,
                    suggestion="Add COPY instruction to include application files",
                )
            )

        # Check for CMD or ENTRYPOINT instruction
        if not any(line.startswith(("CMD", "ENTRYPOINT")) for line in lines):
            warnings.append(
                ValidationWarning(
                    code="DOCKERFILE_MISSING_CMD",
                    message="Dockerfile is missing CMD or ENTRYPOINT instruction",
                    file_path=dockerfile_path,
                    suggestion="Add CMD or ENTRYPOINT instruction to define container startup",
                )
            )
