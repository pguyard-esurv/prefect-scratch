"""
Deployment Templates

Provides template system for deployment configurations.
"""

from pathlib import Path
from string import Template
from typing import Any, Optional

import yaml


class DeploymentTemplate:
    """Template for deployment configurations with variable substitution."""

    def __init__(self, template_data: dict[str, Any]):
        self.template_data = template_data

    def render(self, variables: dict[str, Any]) -> dict[str, Any]:
        """Render template with provided variables."""
        # Flatten variables for easier substitution
        flattened_vars = self._flatten_variables(variables)
        return self._substitute_variables(self.template_data, flattened_vars)

    def _substitute_variables(self, data: Any, variables: dict[str, Any]) -> Any:
        """Recursively substitute variables in data structure."""
        if isinstance(data, dict):
            return {
                key: self._substitute_variables(value, variables)
                for key, value in data.items()
            }
        elif isinstance(data, list):
            return [self._substitute_variables(item, variables) for item in data]
        elif isinstance(data, str):
            return self._substitute_string(data, variables)
        else:
            return data

    def _flatten_variables(
        self, variables: dict[str, Any], prefix: str = ""
    ) -> dict[str, Any]:
        """Flatten nested variables for template substitution."""
        flattened = {}

        for key, value in variables.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                flattened.update(self._flatten_variables(value, full_key))
            elif hasattr(value, "__dict__"):
                # Handle objects with attributes
                obj_dict = {
                    k: v for k, v in value.__dict__.items() if not k.startswith("_")
                }
                flattened.update(self._flatten_variables(obj_dict, full_key))
            else:
                flattened[full_key] = value

        return flattened

    def _substitute_string(self, template_str: str, variables: dict[str, Any]) -> str:
        """Substitute variables in a string template."""
        try:
            # Handle special case where template_str might reference a complex object
            if template_str.startswith("${") and template_str.endswith("}"):
                var_name = template_str[2:-1]  # Remove ${ and }

                # Navigate nested variables
                parts = var_name.split(".")
                value = variables

                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    elif hasattr(value, part):
                        value = getattr(value, part)
                    else:
                        # Return original string if path not found
                        return template_str

                return value if isinstance(value, str) else str(value)
            else:
                # Use standard template substitution
                template = Template(template_str)
                return template.safe_substitute(variables)
        except (KeyError, ValueError, AttributeError):
            # Return original string if substitution fails
            return template_str

    @classmethod
    def from_file(cls, template_path: str) -> "DeploymentTemplate":
        """Load template from YAML file."""
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")

        with open(path, encoding="utf-8") as f:
            template_data = yaml.safe_load(f)

        return cls(template_data)


class TemplateManager:
    """Manages deployment templates."""

    def __init__(self, templates_dir: str = "deployment_system/templates"):
        self.templates_dir = Path(templates_dir)
        self._templates = {}
        self._load_templates()

    def _load_templates(self):
        """Load all templates from the templates directory."""
        if not self.templates_dir.exists():
            # Create templates directory if it doesn't exist
            self.templates_dir.mkdir(parents=True, exist_ok=True)

        for template_file in self.templates_dir.glob("*.yaml"):
            template_name = template_file.stem
            try:
                self._templates[template_name] = DeploymentTemplate.from_file(
                    str(template_file)
                )
            except Exception as e:
                print(f"Warning: Failed to load template {template_name}: {e}")

        # Load built-in templates if no templates found
        if not self._templates:
            self._load_builtin_templates()

    def _load_builtin_templates(self):
        """Load built-in default templates."""
        # Python deployment template
        python_template_data = self.get_default_python_template()
        self._templates["python_deployment"] = DeploymentTemplate(python_template_data)

        # Docker deployment template
        docker_template_data = self.get_default_docker_template()
        self._templates["docker_deployment"] = DeploymentTemplate(docker_template_data)

    def get_template(self, template_name: str) -> Optional[DeploymentTemplate]:
        """Get a template by name."""
        return self._templates.get(template_name)

    def render_template(
        self, template_name: str, variables: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Render a template with variables."""
        template = self.get_template(template_name)
        if template:
            return template.render(variables)
        return None

    def list_templates(self) -> list:
        """List available template names."""
        return list(self._templates.keys())

    def get_default_python_template(self) -> dict[str, Any]:
        """Get default Python deployment template."""
        return {
            "work_pool": "${environment.work_pools.python}",
            "job_variables": {
                "env": {
                    "PREFECT_API_URL": "${environment.prefect_api_url}",
                    "PYTHONPATH": "/app",
                    "ENVIRONMENT": "${environment.name}",
                    "FLOW_NAME": "${flow.name}",
                }
            },
            "parameters": "${environment.default_parameters}",
            "tags": [
                "environment:${environment.name}",
                "type:python",
                "flow:${flow.name}",
            ],
        }

    def get_default_docker_template(self) -> dict[str, Any]:
        """Get default Docker deployment template."""
        return {
            "work_pool": "${environment.work_pools.docker}",
            "job_variables": {
                "image": "${flow.name}-worker:latest",
                "env": {
                    "PREFECT_API_URL": "${environment.prefect_api_url}",
                    "PYTHONPATH": "/app",
                    "ENVIRONMENT": "${environment.name}",
                    "FLOW_NAME": "${flow.name}",
                    "CONTAINER_TYPE": "worker",
                },
                "volumes": [
                    "./flows/${flow.name}/data:/app/flows/${flow.name}/data",
                    "./flows/${flow.name}/output:/app/flows/${flow.name}/output",
                    "./logs/${flow.name}:/app/logs/${flow.name}",
                ],
                "networks": ["rpa-network"],
            },
            "parameters": "${environment.default_parameters}",
            "tags": [
                "environment:${environment.name}",
                "type:docker",
                "flow:${flow.name}",
            ],
        }
