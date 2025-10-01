"""
Deployment Validator

Validates deployment configurations and settings.
"""

from ..config.deployment_config import DeploymentConfig
from .validation_result import ValidationError, ValidationResult


class DeploymentValidator:
    """Validates deployment configurations."""

    def __init__(self):
        self.required_fields = {
            "python": ["name", "entrypoint", "work_pool"],
            "docker": ["name", "entrypoint", "work_pool", "job_variables"],
        }

    def validate_deployment_config(self, config: DeploymentConfig) -> ValidationResult:
        """Validate a deployment configuration."""
        errors = []
        warnings = []

        # Validate required fields
        deployment_type = config.deployment_type
        required = self.required_fields.get(deployment_type, [])

        for field in required:
            if not hasattr(config, field) or not getattr(config, field):
                errors.append(
                    ValidationError(
                        code="MISSING_REQUIRED_FIELD",
                        message=f"Required field '{field}' is missing or empty",
                        remediation=f"Provide a value for {field}",
                    )
                )

        # Validate entrypoint format
        if hasattr(config, "entrypoint") and config.entrypoint:
            if ":" not in config.entrypoint:
                errors.append(
                    ValidationError(
                        code="INVALID_ENTRYPOINT_FORMAT",
                        message="Entrypoint must be in format 'module:function'",
                        remediation="Use format like 'flows.rpa1.workflow:main_flow'",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )
