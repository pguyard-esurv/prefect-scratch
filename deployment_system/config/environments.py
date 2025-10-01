"""
Environment Configuration Models

Defines data structures for environment-specific configurations.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ResourceLimits:
    """Resource limits for deployments."""

    memory: str = "512Mi"
    cpu: str = "0.5"
    storage: Optional[str] = None

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary."""
        result = {"memory": self.memory, "cpu": self.cpu}
        if self.storage:
            result["storage"] = self.storage
        return result


@dataclass
class WorkPoolConfig:
    """Configuration for a work pool."""

    name: str
    type: str = "process"  # process, docker, kubernetes, etc.
    concurrency_limit: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"name": self.name, "type": self.type}
        if self.concurrency_limit:
            result["concurrency_limit"] = self.concurrency_limit
        return result


@dataclass
class EnvironmentConfig:
    """Environment-specific configuration."""

    name: str
    prefect_api_url: str
    work_pools: dict[str, str] = field(default_factory=dict)
    default_parameters: dict[str, Any] = field(default_factory=dict)
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    docker_registry: Optional[str] = None
    image_pull_policy: str = "IfNotPresent"

    def __post_init__(self):
        """Set default work pools if not provided."""
        if not self.work_pools:
            self.work_pools = {"python": "default-agent-pool", "docker": "docker-pool"}

    def get_work_pool(self, deployment_type: str) -> str:
        """Get work pool for deployment type."""
        return self.work_pools.get(deployment_type, "default-agent-pool")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "prefect_api_url": self.prefect_api_url,
            "work_pools": self.work_pools,
            "default_parameters": self.default_parameters,
            "resource_limits": self.resource_limits.to_dict(),
            "docker_registry": self.docker_registry,
            "image_pull_policy": self.image_pull_policy,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EnvironmentConfig":
        """Create from dictionary."""
        resource_limits_data = data.get("resource_limits", {})
        resource_limits = ResourceLimits(**resource_limits_data)

        return cls(
            name=data["name"],
            prefect_api_url=data["prefect_api_url"],
            work_pools=data.get("work_pools", {}),
            default_parameters=data.get("default_parameters", {}),
            resource_limits=resource_limits,
            docker_registry=data.get("docker_registry"),
            image_pull_policy=data.get("image_pull_policy", "IfNotPresent"),
        )
