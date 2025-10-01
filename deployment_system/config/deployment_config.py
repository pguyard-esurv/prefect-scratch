"""
Deployment Configuration Models

Defines data structures for deployment configurations.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class DeploymentConfig:
    """Configuration for a Prefect deployment."""

    flow_name: str
    deployment_name: str
    environment: str
    deployment_type: str  # "python" or "docker"
    work_pool: str
    entrypoint: str
    schedule: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    job_variables: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    version: str = "1.0.0"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.flow_name:
            raise ValueError("Flow name is required")

        if not self.deployment_name:
            raise ValueError("Deployment name is required")

        if not self.work_pool:
            raise ValueError("Work pool is required")

        if not self.entrypoint:
            raise ValueError("Entrypoint is required")

        if self.deployment_type not in ["python", "docker"]:
            raise ValueError("Deployment type must be 'python' or 'docker'")

    @property
    def full_name(self) -> str:
        """Get the full deployment name."""
        return f"{self.flow_name}/{self.deployment_name}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Prefect API."""
        return {
            "name": self.deployment_name,
            "flow_name": self.flow_name,
            "entrypoint": self.entrypoint,
            "work_pool_name": self.work_pool,
            "schedule": self.schedule,
            "parameters": self.parameters,
            "job_variables": self.job_variables,
            "tags": self.tags,
            "description": self.description,
            "version": self.version,
        }

    def add_tag(self, tag: str) -> None:
        """Add a tag to the deployment."""
        if tag not in self.tags:
            self.tags.append(tag)

    def set_parameter(self, key: str, value: Any) -> None:
        """Set a deployment parameter."""
        self.parameters[key] = value

    def set_job_variable(self, key: str, value: Any) -> None:
        """Set a job variable."""
        self.job_variables[key] = value

    def merge_parameters(self, parameters: dict[str, Any]) -> None:
        """Merge additional parameters."""
        self.parameters.update(parameters)

    def merge_job_variables(self, job_variables: dict[str, Any]) -> None:
        """Merge additional job variables."""
        if isinstance(job_variables, dict):
            self.job_variables.update(job_variables)
        else:
            # Handle case where job_variables might be a list or other type
            print(
                f"Warning: Expected dict for job_variables, got {type(job_variables)}: {job_variables}"
            )
