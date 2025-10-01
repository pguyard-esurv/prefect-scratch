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

    def validate_docker_build(
        self, dockerfile_path: str, context_path: str = None, image_name: str = None
    ) -> ValidationResult:
        """Validate Docker image build process."""
        errors = []
        warnings = []

        if context_path is None:
            context_path = str(Path(dockerfile_path).parent)

        try:
            # Check Docker daemon availability
            daemon_result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if daemon_result.returncode != 0:
                errors.append(
                    ValidationError(
                        code="DOCKER_DAEMON_UNAVAILABLE",
                        message="Docker daemon is not running or accessible",
                        remediation="Start Docker daemon or check Docker installation",
                    )
                )
                return ValidationResult(
                    is_valid=False, errors=errors, warnings=warnings
                )

            # Validate build context
            context_validation = self._validate_build_context(context_path)
            errors.extend(context_validation.errors)
            warnings.extend(context_validation.warnings)

            # Perform dry-run build validation
            if image_name:
                build_validation = self._validate_build_process(
                    dockerfile_path, context_path, image_name
                )
                errors.extend(build_validation.errors)
                warnings.extend(build_validation.warnings)

        except subprocess.TimeoutExpired:
            errors.append(
                ValidationError(
                    code="DOCKER_DAEMON_TIMEOUT",
                    message="Timeout while checking Docker daemon",
                    remediation="Check Docker daemon status and network connectivity",
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
            errors.append(
                ValidationError(
                    code="DOCKER_BUILD_VALIDATION_ERROR",
                    message=f"Error validating Docker build: {str(e)}",
                    remediation="Check Docker configuration and build context",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_docker_registry_access(
        self, image_name: str, registry_url: str = None
    ) -> ValidationResult:
        """Validate Docker registry access for image push/pull."""
        errors = []
        warnings = []

        try:
            # Check if we can pull from registry (if image exists)
            if registry_url:
                full_image_name = f"{registry_url}/{image_name}"
            else:
                full_image_name = image_name

            # Test registry connectivity
            result = subprocess.run(
                ["docker", "pull", "--dry-run", full_image_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                if "not found" in result.stderr.lower():
                    warnings.append(
                        ValidationWarning(
                            code="IMAGE_NOT_IN_REGISTRY",
                            message=f"Image '{full_image_name}' not found in registry",
                            suggestion="Build and push the image to registry before deployment",
                        )
                    )
                elif "unauthorized" in result.stderr.lower():
                    errors.append(
                        ValidationError(
                            code="REGISTRY_UNAUTHORIZED",
                            message=f"Unauthorized access to registry for '{full_image_name}'",
                            remediation="Configure Docker registry authentication",
                        )
                    )
                else:
                    warnings.append(
                        ValidationWarning(
                            code="REGISTRY_ACCESS_ERROR",
                            message=f"Error accessing registry for '{full_image_name}': {result.stderr}",
                            suggestion="Check registry URL and network connectivity",
                        )
                    )

        except subprocess.TimeoutExpired:
            warnings.append(
                ValidationWarning(
                    code="REGISTRY_TIMEOUT",
                    message=f"Timeout while checking registry access for '{image_name}'",
                    suggestion="Check network connectivity to Docker registry",
                )
            )
        except Exception as e:
            warnings.append(
                ValidationWarning(
                    code="REGISTRY_VALIDATION_ERROR",
                    message=f"Error validating registry access: {str(e)}",
                    suggestion="Check Docker registry configuration",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_build_context(self, context_path: str) -> ValidationResult:
        """Validate Docker build context."""
        errors = []
        warnings = []

        context = Path(context_path)
        if not context.exists():
            errors.append(
                ValidationError(
                    code="BUILD_CONTEXT_NOT_FOUND",
                    message=f"Build context directory not found: {context_path}",
                    remediation="Ensure the build context directory exists",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check for .dockerignore
        dockerignore = context / ".dockerignore"
        if not dockerignore.exists():
            warnings.append(
                ValidationWarning(
                    code="MISSING_DOCKERIGNORE",
                    message="No .dockerignore file found in build context",
                    suggestion="Create .dockerignore to optimize build performance",
                )
            )

        # Check context size
        try:
            context_size = sum(
                f.stat().st_size for f in context.rglob("*") if f.is_file()
            )
            if context_size > 100 * 1024 * 1024:  # 100MB
                warnings.append(
                    ValidationWarning(
                        code="LARGE_BUILD_CONTEXT",
                        message=f"Build context is large ({context_size / (1024*1024):.1f}MB)",
                        suggestion="Use .dockerignore to exclude unnecessary files",
                    )
                )
        except Exception:
            pass  # Ignore errors in size calculation

        # Check for common problematic files
        problematic_patterns = [".git", "node_modules", "__pycache__", "*.pyc", ".venv"]
        for pattern in problematic_patterns:
            if list(context.glob(pattern)):
                warnings.append(
                    ValidationWarning(
                        code="PROBLEMATIC_FILES_IN_CONTEXT",
                        message=f"Found '{pattern}' in build context",
                        suggestion=f"Add '{pattern}' to .dockerignore to improve build performance",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_build_process(
        self, dockerfile_path: str, context_path: str, image_name: str
    ) -> ValidationResult:
        """Validate the actual Docker build process."""
        errors = []
        warnings = []

        try:
            # Perform a dry-run build to check for issues
            result = subprocess.run(
                [
                    "docker",
                    "build",
                    "--dry-run",
                    "-f",
                    dockerfile_path,
                    "-t",
                    image_name,
                    context_path,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                # Parse build errors
                build_errors = self._parse_build_errors(result.stderr)
                errors.extend(build_errors)

            # Check for build warnings
            build_warnings = self._parse_build_warnings(result.stdout + result.stderr)
            warnings.extend(build_warnings)

        except subprocess.TimeoutExpired:
            errors.append(
                ValidationError(
                    code="BUILD_TIMEOUT",
                    message="Docker build validation timed out",
                    remediation="Check Dockerfile for long-running operations or increase timeout",
                )
            )
        except Exception as e:
            errors.append(
                ValidationError(
                    code="BUILD_PROCESS_ERROR",
                    message=f"Error during build validation: {str(e)}",
                    remediation="Check Docker configuration and Dockerfile syntax",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _parse_build_errors(self, stderr: str) -> list[ValidationError]:
        """Parse Docker build errors from stderr."""
        errors = []

        if "no such file or directory" in stderr.lower():
            errors.append(
                ValidationError(
                    code="BUILD_FILE_NOT_FOUND",
                    message="File or directory not found during build",
                    remediation="Check COPY/ADD instructions and ensure files exist in build context",
                )
            )

        if "invalid instruction" in stderr.lower():
            errors.append(
                ValidationError(
                    code="INVALID_DOCKERFILE_INSTRUCTION",
                    message="Invalid Dockerfile instruction",
                    remediation="Check Dockerfile syntax and instruction format",
                )
            )

        if "failed to solve" in stderr.lower():
            errors.append(
                ValidationError(
                    code="BUILD_SOLVE_FAILED",
                    message="Docker build failed to solve dependencies",
                    remediation="Check base image availability and network connectivity",
                )
            )

        return errors

    def _parse_build_warnings(self, output: str) -> list[ValidationWarning]:
        """Parse Docker build warnings from output."""
        warnings = []

        if "deprecated" in output.lower():
            warnings.append(
                ValidationWarning(
                    code="DEPRECATED_INSTRUCTION",
                    message="Dockerfile uses deprecated instructions",
                    suggestion="Update Dockerfile to use current best practices",
                )
            )

        if "cache miss" in output.lower():
            warnings.append(
                ValidationWarning(
                    code="CACHE_MISS",
                    message="Docker build cache misses detected",
                    suggestion="Optimize Dockerfile layer ordering for better caching",
                )
            )

        return warnings

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
