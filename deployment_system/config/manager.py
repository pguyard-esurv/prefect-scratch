"""
Configuration Manager

Main orchestrator for configuration management.
"""

from pathlib import Path
from typing import Any, Optional

import yaml

from ..discovery.metadata import FlowMetadata
from ..validation.validation_result import (
    ValidationError,
    ValidationResult,
    ValidationWarning,
)
from .deployment_config import DeploymentConfig
from .environments import EnvironmentConfig, ResourceLimits
from .templates import TemplateManager


class ConfigurationManager:
    """Main configuration manager for the deployment system."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.template_manager = TemplateManager()
        self._environments = {}
        self._global_config = {}
        self._flow_overrides = {}
        self._load_configuration()

    def _load_configuration(self):
        """Load all configuration from YAML files."""
        # Try to load from deployment-config.yaml first (new format)
        config_file = self.config_dir / "deployment-config.yaml"
        if not config_file.exists():
            # Fallback to deployment_config.yaml (old format)
            config_file = self.config_dir / "deployment_config.yaml"

        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config_data = yaml.safe_load(f)

                # Load environments
                environments_data = config_data.get("environments", {})
                for env_name, env_data in environments_data.items():
                    env_data["name"] = env_name
                    self._environments[env_name] = EnvironmentConfig.from_dict(env_data)

                # Load global configuration
                self._global_config = config_data.get("global_config", {})

                # Load flow-specific overrides
                self._flow_overrides = config_data.get("flow_overrides", {})

            except Exception as e:
                print(f"Warning: Failed to load deployment config: {e}")

        # Ensure default environments exist
        self._ensure_default_environments()

    def _ensure_default_environments(self):
        """Ensure default environments are available."""
        default_environments = {
            "development": {
                "name": "development",
                "prefect_api_url": "http://localhost:4200/api",
                "work_pools": {"python": "default-agent-pool", "docker": "docker-pool"},
                "default_parameters": {"cleanup": True, "use_distributed": False},
            },
            "staging": {
                "name": "staging",
                "prefect_api_url": "http://staging-prefect:4200/api",
                "work_pools": {
                    "python": "staging-agent-pool",
                    "docker": "staging-docker-pool",
                },
                "default_parameters": {"cleanup": True, "use_distributed": True},
            },
            "production": {
                "name": "production",
                "prefect_api_url": "http://prod-prefect:4200/api",
                "work_pools": {
                    "python": "prod-agent-pool",
                    "docker": "prod-docker-pool",
                },
                "default_parameters": {"cleanup": False, "use_distributed": True},
            },
        }

        for env_name, env_data in default_environments.items():
            if env_name not in self._environments:
                self._environments[env_name] = EnvironmentConfig.from_dict(env_data)

    def get_environment_config(self, environment: str) -> Optional[EnvironmentConfig]:
        """Get configuration for a specific environment."""
        return self._environments.get(environment)

    def list_environments(self) -> list[str]:
        """List available environments."""
        return list(self._environments.keys())

    def get_global_config(self) -> dict[str, Any]:
        """Get global configuration."""
        return self._global_config.copy()

    def get_flow_overrides(self, flow_name: str) -> dict[str, Any]:
        """Get flow-specific configuration overrides."""
        return self._flow_overrides.get(flow_name, {})

    def get_validation_config(self) -> dict[str, Any]:
        """Get validation configuration."""
        return self._global_config.get(
            "validation",
            {
                "strict_mode": True,
                "validate_dependencies": True,
                "validate_docker_images": True,
                "validate_work_pools": True,
            },
        )

    def generate_deployment_config(
        self, flow: FlowMetadata, deployment_type: str, environment: str = "development"
    ) -> DeploymentConfig:
        """Generate deployment configuration for a flow."""
        env_config = self.get_environment_config(environment)
        if not env_config:
            raise ValueError(f"Environment '{environment}' not found")

        # Generate deployment name
        deployment_name = f"{flow.name}-{deployment_type}-{environment}"

        # Get work pool for deployment type
        work_pool = env_config.get_work_pool(deployment_type)

        # Start with environment default parameters
        parameters = env_config.default_parameters.copy()

        # Apply flow-specific overrides
        flow_overrides = self.get_flow_overrides(flow.name)
        if "default_parameters" in flow_overrides:
            parameters.update(flow_overrides["default_parameters"])

        # Create base deployment config
        config = DeploymentConfig(
            flow_name=flow.name,
            deployment_name=deployment_name,
            environment=environment,
            deployment_type=deployment_type,
            work_pool=work_pool,
            entrypoint=f"{flow.module_path}:{flow.function_name}",
            parameters=parameters,
            tags=self._generate_tags(flow, deployment_type, environment, env_config),
            description=f"{flow.name} flow deployed as {deployment_type} in {environment}",
        )

        # Apply template if available
        template_name = f"{deployment_type}_deployment"
        template_config = self.template_manager.render_template(
            template_name,
            {"flow": flow, "environment": env_config, "flow_overrides": flow_overrides},
        )

        if template_config:
            # Merge template configuration
            if "job_variables" in template_config:
                job_vars = template_config["job_variables"]
                if isinstance(job_vars, dict):
                    config.merge_job_variables(job_vars)
                else:
                    print(f"Warning: Invalid job_variables in template: {job_vars}")

            if "parameters" in template_config:
                params = template_config["parameters"]
                if isinstance(params, dict):
                    config.merge_parameters(params)
                else:
                    print(f"Warning: Invalid parameters in template: {params}")

            if "tags" in template_config:
                tags = template_config["tags"]
                if isinstance(tags, list):
                    for tag in tags:
                        config.add_tag(str(tag))

        return config

    def _generate_tags(
        self,
        flow: FlowMetadata,
        deployment_type: str,
        environment: str,
        env_config: EnvironmentConfig,
    ) -> list[str]:
        """Generate tags for deployment."""
        tags = [
            f"environment:{environment}",
            f"type:{deployment_type}",
            f"flow:{flow.name}",
        ]

        # Add environment default tags
        if hasattr(env_config, "default_tags") and env_config.default_tags:
            tags.extend(env_config.default_tags)

        return tags

    def validate_configuration(self, config: DeploymentConfig) -> ValidationResult:
        """Validate a deployment configuration."""
        errors = []
        warnings = []
        validation_config = self.get_validation_config()

        # Validate environment exists
        if config.environment not in self._environments:
            errors.append(
                ValidationError(
                    code="INVALID_ENVIRONMENT",
                    message=f"Environment '{config.environment}' is not configured",
                    remediation=f"Add configuration for environment '{config.environment}' or use one of: {', '.join(self.list_environments())}",
                )
            )

        # Validate deployment type
        if config.deployment_type not in ["python", "docker"]:
            errors.append(
                ValidationError(
                    code="INVALID_DEPLOYMENT_TYPE",
                    message=f"Invalid deployment type: {config.deployment_type}",
                    remediation="Deployment type must be 'python' or 'docker'",
                )
            )

        # Validate required fields
        if not config.flow_name:
            errors.append(
                ValidationError(
                    code="MISSING_FLOW_NAME",
                    message="Flow name is required",
                    remediation="Provide a valid flow name",
                )
            )

        if not config.entrypoint:
            errors.append(
                ValidationError(
                    code="MISSING_ENTRYPOINT",
                    message="Entrypoint is required",
                    remediation="Provide a valid entrypoint in format 'module:function'",
                )
            )

        # Validate work pool configuration
        env_config = self.get_environment_config(config.environment)
        if env_config and validation_config.get("validate_work_pools", True):
            if config.deployment_type in env_config.work_pools:
                expected_work_pool = env_config.work_pools[config.deployment_type]
                if config.work_pool != expected_work_pool:
                    if validation_config.get("strict_mode", True):
                        errors.append(
                            ValidationError(
                                code="WORK_POOL_MISMATCH",
                                message=f"Work pool '{config.work_pool}' doesn't match environment requirement '{expected_work_pool}'",
                                remediation=f"Use work pool '{expected_work_pool}' for environment '{config.environment}'",
                            )
                        )
                    else:
                        warnings.append(
                            ValidationWarning(
                                code="WORK_POOL_MISMATCH",
                                message=f"Work pool '{config.work_pool}' doesn't match environment default '{expected_work_pool}'",
                                suggestion=f"Consider using work pool '{expected_work_pool}' for consistency",
                            )
                        )
            else:
                warnings.append(
                    ValidationWarning(
                        code="UNKNOWN_DEPLOYMENT_TYPE",
                        message=f"No work pool configured for deployment type '{config.deployment_type}' in environment '{config.environment}'",
                        suggestion=f"Add work pool configuration for '{config.deployment_type}' in environment '{config.environment}'",
                    )
                )

        # Validate entrypoint format
        if config.entrypoint and ":" not in config.entrypoint:
            errors.append(
                ValidationError(
                    code="INVALID_ENTRYPOINT_FORMAT",
                    message=f"Invalid entrypoint format: '{config.entrypoint}'",
                    remediation="Entrypoint must be in format 'module.path:function_name'",
                )
            )

        # Validate parameters
        if config.parameters and not isinstance(config.parameters, dict):
            errors.append(
                ValidationError(
                    code="INVALID_PARAMETERS",
                    message="Parameters must be a dictionary",
                    remediation="Provide parameters as a dictionary of key-value pairs",
                )
            )

        # Validate job variables
        if config.job_variables and not isinstance(config.job_variables, dict):
            errors.append(
                ValidationError(
                    code="INVALID_JOB_VARIABLES",
                    message="Job variables must be a dictionary",
                    remediation="Provide job variables as a dictionary of key-value pairs",
                )
            )

        # Validate tags
        if config.tags and not isinstance(config.tags, list):
            errors.append(
                ValidationError(
                    code="INVALID_TAGS",
                    message="Tags must be a list",
                    remediation="Provide tags as a list of strings",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_environment_config(self, environment: str) -> ValidationResult:
        """Validate an environment configuration."""
        errors = []
        warnings = []

        env_config = self.get_environment_config(environment)
        if not env_config:
            errors.append(
                ValidationError(
                    code="ENVIRONMENT_NOT_FOUND",
                    message=f"Environment '{environment}' not found",
                    remediation=f"Available environments: {', '.join(self.list_environments())}",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate required fields
        if not env_config.prefect_api_url:
            errors.append(
                ValidationError(
                    code="MISSING_PREFECT_API_URL",
                    message=f"Prefect API URL is required for environment '{environment}'",
                    remediation="Set prefect_api_url in environment configuration",
                )
            )

        # Validate work pools
        if not env_config.work_pools:
            warnings.append(
                ValidationWarning(
                    code="NO_WORK_POOLS",
                    message=f"No work pools configured for environment '{environment}'",
                    suggestion="Add work pool configurations for python and docker deployment types",
                )
            )
        else:
            required_pools = ["python", "docker"]
            for pool_type in required_pools:
                if pool_type not in env_config.work_pools:
                    warnings.append(
                        ValidationWarning(
                            code="MISSING_WORK_POOL",
                            message=f"No work pool configured for '{pool_type}' deployments in environment '{environment}'",
                            suggestion=f"Add work pool configuration for '{pool_type}' deployment type",
                        )
                    )

        # Validate resource limits
        if env_config.resource_limits:
            if not env_config.resource_limits.memory:
                warnings.append(
                    ValidationWarning(
                        code="NO_MEMORY_LIMIT",
                        message=f"No memory limit set for environment '{environment}'",
                        suggestion="Set memory limit in resource_limits configuration",
                    )
                )

            if not env_config.resource_limits.cpu:
                warnings.append(
                    ValidationWarning(
                        code="NO_CPU_LIMIT",
                        message=f"No CPU limit set for environment '{environment}'",
                        suggestion="Set CPU limit in resource_limits configuration",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_all_environments(self) -> dict[str, ValidationResult]:
        """Validate all environment configurations."""
        results = {}
        for env_name in self.list_environments():
            results[env_name] = self.validate_environment_config(env_name)
        return results

    def save_environment_config(self, environment: str, config: EnvironmentConfig):
        """Save environment configuration."""
        self._environments[environment] = config

        # Save to file
        config_file = self.config_dir / "deployment-config.yaml"
        self._save_config_file(config_file)

    def _save_config_file(self, config_file: Path):
        """Save configuration to file."""
        config_data = {
            "environments": {
                name: env.to_dict() for name, env in self._environments.items()
            },
            "global_config": self._global_config,
            "flow_overrides": self._flow_overrides,
        }

        # Ensure directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)

    def reload_configuration(self):
        """Reload configuration from files."""
        self._environments.clear()
        self._global_config.clear()
        self._flow_overrides.clear()
        self._load_configuration()

    def get_effective_resource_limits(
        self, flow_name: str, environment: str
    ) -> Optional[ResourceLimits]:
        """Get effective resource limits for a flow in an environment."""
        env_config = self.get_environment_config(environment)
        if not env_config:
            return None

        # Start with environment defaults
        resource_limits = env_config.resource_limits

        # Apply flow-specific overrides
        flow_overrides = self.get_flow_overrides(flow_name)
        if "resource_limits" in flow_overrides:
            override_limits = flow_overrides["resource_limits"]
            # Create new ResourceLimits with overrides
            resource_limits = ResourceLimits(
                memory=override_limits.get("memory", resource_limits.memory),
                cpu=override_limits.get("cpu", resource_limits.cpu),
                storage=override_limits.get("storage", resource_limits.storage),
            )

        return resource_limits
