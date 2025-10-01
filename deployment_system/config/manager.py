"""
Configuration Manager

Main orchestrator for configuration management.
"""

from pathlib import Path
from typing import Optional

import yaml

from ..discovery.metadata import FlowMetadata
from ..validation.validation_result import ValidationError, ValidationResult
from .deployment_config import DeploymentConfig
from .environments import EnvironmentConfig
from .templates import TemplateManager


class ConfigurationManager:
    """Main configuration manager for the deployment system."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.template_manager = TemplateManager()
        self._environments = {}
        self._load_environments()

    def _load_environments(self):
        """Load environment configurations."""
        # Load from deployment_config.yaml if it exists
        config_file = self.config_dir / "deployment_config.yaml"
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config_data = yaml.safe_load(f)

                environments_data = config_data.get("environments", {})
                for env_name, env_data in environments_data.items():
                    env_data["name"] = env_name
                    self._environments[env_name] = EnvironmentConfig.from_dict(env_data)

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

    def list_environments(self) -> list:
        """List available environments."""
        return list(self._environments.keys())

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

        # Create base deployment config
        config = DeploymentConfig(
            flow_name=flow.name,
            deployment_name=deployment_name,
            environment=environment,
            deployment_type=deployment_type,
            work_pool=work_pool,
            entrypoint=f"{flow.module_path}:{flow.function_name}",
            parameters=env_config.default_parameters.copy(),
            tags=[
                f"environment:{environment}",
                f"type:{deployment_type}",
                f"flow:{flow.name}",
            ],
            description=f"{flow.name} flow deployed as {deployment_type} in {environment}",
        )

        # Apply template if available
        template_name = f"{deployment_type}_deployment"
        template_config = self.template_manager.render_template(
            template_name, {"flow": flow, "environment": env_config}
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

        return config

    def validate_configuration(self, config: DeploymentConfig) -> ValidationResult:
        """Validate a deployment configuration."""
        errors = []
        warnings = []

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

        # Validate work pool exists in environment
        env_config = self.get_environment_config(config.environment)
        if env_config and config.deployment_type in env_config.work_pools:
            expected_work_pool = env_config.work_pools[config.deployment_type]
            if config.work_pool != expected_work_pool:
                warnings.append(
                    ValidationError(
                        code="WORK_POOL_MISMATCH",
                        message=f"Work pool '{config.work_pool}' doesn't match environment default '{expected_work_pool}'",
                        remediation=f"Consider using work pool '{expected_work_pool}' for consistency",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def save_environment_config(self, environment: str, config: EnvironmentConfig):
        """Save environment configuration."""
        self._environments[environment] = config

        # Save to file
        config_file = self.config_dir / "deployment_config.yaml"
        self._save_config_file(config_file)

    def _save_config_file(self, config_file: Path):
        """Save configuration to file."""
        config_data = {
            "environments": {
                name: env.to_dict() for name, env in self._environments.items()
            }
        }

        # Ensure directory exists
        config_file.parent.mkdir(parents=True, exist_ok=True)

        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
