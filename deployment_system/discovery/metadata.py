"""
Flow Metadata Models

Defines data structures for storing flow information and metadata.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FlowMetadata:
    """Metadata for a discovered Prefect flow."""

    name: str  # Flow name from @flow decorator
    path: str  # Absolute path to flow file
    module_path: str  # Python module path (e.g., flows.rpa1.workflow)
    function_name: str  # Flow function name
    dependencies: list[str] = field(default_factory=list)  # Python dependencies
    dockerfile_path: Optional[str] = None  # Path to Dockerfile if exists
    env_files: list[str] = field(default_factory=list)  # Environment files (.env.*)
    is_valid: bool = True  # Validation status
    validation_errors: list[str] = field(
        default_factory=list
    )  # Validation error messages
    metadata: dict[str, Any] = field(
        default_factory=dict
    )  # Additional metadata from flow decorator

    def __post_init__(self):
        """Validate metadata after initialization."""
        if not self.name:
            self.is_valid = False
            self.validation_errors.append("Flow name is required")

        if not self.path:
            self.is_valid = False
            self.validation_errors.append("Flow path is required")

        if not self.module_path:
            self.is_valid = False
            self.validation_errors.append("Module path is required")

        if not self.function_name:
            self.is_valid = False
            self.validation_errors.append("Function name is required")

    @property
    def has_dockerfile(self) -> bool:
        """Check if flow has an associated Dockerfile."""
        return self.dockerfile_path is not None

    @property
    def supports_docker_deployment(self) -> bool:
        """Check if flow supports Docker deployment."""
        return self.has_dockerfile and self.is_valid

    @property
    def supports_python_deployment(self) -> bool:
        """Check if flow supports Python deployment."""
        return self.is_valid

    def add_validation_error(self, error: str) -> None:
        """Add a validation error and mark as invalid."""
        self.validation_errors.append(error)
        self.is_valid = False

    def get_deployment_name(
        self, deployment_type: str, environment: str = "dev"
    ) -> str:
        """Generate a deployment name for this flow."""
        return f"{self.name}-{deployment_type}-{environment}"
