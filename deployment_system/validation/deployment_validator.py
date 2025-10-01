"""
Deployment Validator

Validates deployment configurations and settings.
"""

import re
from pathlib import Path

from ..config.deployment_config import DeploymentConfig
from .validation_result import ValidationError, ValidationResult, ValidationWarning


class DeploymentValidator:
    """Validates deployment configurations."""

    def __init__(self):
        self.required_fields = {
            "python": ["flow_name", "deployment_name", "entrypoint", "work_pool"],
            "docker": [
                "flow_name",
                "deployment_name",
                "entrypoint",
                "work_pool",
                "job_variables",
            ],
        }
        self.valid_environments = {
            "development",
            "staging",
            "production",
            "dev",
            "prod",
        }
        self.valid_deployment_types = {"python", "docker"}

    def validate_deployment_config(self, config: DeploymentConfig) -> ValidationResult:
        """Validate a deployment configuration comprehensively."""
        errors = []
        warnings = []

        # Basic field validation
        field_result = self._validate_required_fields(config)
        errors.extend(field_result.errors)
        warnings.extend(field_result.warnings)

        # Entrypoint validation
        entrypoint_result = self._validate_entrypoint(config)
        errors.extend(entrypoint_result.errors)
        warnings.extend(entrypoint_result.warnings)

        # Work pool validation
        workpool_result = self._validate_work_pool(config)
        errors.extend(workpool_result.errors)
        warnings.extend(workpool_result.warnings)

        # Environment validation
        env_result = self._validate_environment(config)
        errors.extend(env_result.errors)
        warnings.extend(env_result.warnings)

        # Parameters validation
        params_result = self._validate_parameters(config)
        errors.extend(params_result.errors)
        warnings.extend(params_result.warnings)

        # Job variables validation (for Docker deployments)
        if config.deployment_type == "docker":
            job_vars_result = self._validate_job_variables(config)
            errors.extend(job_vars_result.errors)
            warnings.extend(job_vars_result.warnings)

        # Schedule validation
        if config.schedule:
            schedule_result = self._validate_schedule(config)
            errors.extend(schedule_result.errors)
            warnings.extend(schedule_result.warnings)

        # Tags validation
        tags_result = self._validate_tags(config)
        errors.extend(tags_result.errors)
        warnings.extend(tags_result.warnings)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_required_fields(self, config: DeploymentConfig) -> ValidationResult:
        """Validate required fields for deployment configuration."""
        errors = []
        warnings = []

        # Check deployment type
        if config.deployment_type not in self.valid_deployment_types:
            errors.append(
                ValidationError(
                    code="INVALID_DEPLOYMENT_TYPE",
                    message=f"Invalid deployment type: {config.deployment_type}",
                    remediation=f"Use one of: {', '.join(self.valid_deployment_types)}",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check required fields for deployment type
        required = self.required_fields.get(config.deployment_type, [])
        for field in required:
            if not hasattr(config, field) or not getattr(config, field):
                errors.append(
                    ValidationError(
                        code="MISSING_REQUIRED_FIELD",
                        message=f"Required field '{field}' is missing or empty",
                        remediation=f"Provide a value for {field}",
                    )
                )

        # Validate naming conventions
        if config.flow_name and not self._is_valid_name(config.flow_name):
            errors.append(
                ValidationError(
                    code="INVALID_FLOW_NAME",
                    message=f"Invalid flow name: {config.flow_name}",
                    remediation="Use alphanumeric characters, hyphens, and underscores only",
                )
            )

        if config.deployment_name and not self._is_valid_name(config.deployment_name):
            errors.append(
                ValidationError(
                    code="INVALID_DEPLOYMENT_NAME",
                    message=f"Invalid deployment name: {config.deployment_name}",
                    remediation="Use alphanumeric characters, hyphens, and underscores only",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_entrypoint(self, config: DeploymentConfig) -> ValidationResult:
        """Validate entrypoint format and accessibility."""
        errors = []
        warnings = []

        if not config.entrypoint:
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        # Check format
        if ":" not in config.entrypoint:
            errors.append(
                ValidationError(
                    code="INVALID_ENTRYPOINT_FORMAT",
                    message="Entrypoint must be in format 'module:function'",
                    remediation="Use format like 'flows.rpa1.workflow:main_flow'",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        module_path, function_name = config.entrypoint.split(":", 1)

        # Validate module path format
        if not self._is_valid_module_path(module_path):
            errors.append(
                ValidationError(
                    code="INVALID_MODULE_PATH",
                    message=f"Invalid module path: {module_path}",
                    remediation="Use valid Python module path (e.g., flows.rpa1.workflow)",
                )
            )

        # Validate function name format
        if not self._is_valid_python_identifier(function_name):
            errors.append(
                ValidationError(
                    code="INVALID_FUNCTION_NAME",
                    message=f"Invalid function name: {function_name}",
                    remediation="Use valid Python function name",
                )
            )

        # Check if module file exists (heuristic)
        module_file_path = module_path.replace(".", "/") + ".py"
        if not Path(module_file_path).exists():
            warnings.append(
                ValidationWarning(
                    code="MODULE_FILE_NOT_FOUND",
                    message=f"Module file not found: {module_file_path}",
                    suggestion="Ensure the module file exists in the expected location",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_work_pool(self, config: DeploymentConfig) -> ValidationResult:
        """Validate work pool configuration."""
        errors = []
        warnings = []

        if not config.work_pool:
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        # Check work pool name format
        if not self._is_valid_name(config.work_pool):
            errors.append(
                ValidationError(
                    code="INVALID_WORK_POOL_NAME",
                    message=f"Invalid work pool name: {config.work_pool}",
                    remediation="Use alphanumeric characters, hyphens, and underscores only",
                )
            )

        # Suggest appropriate work pools based on deployment type
        if config.deployment_type == "python" and "docker" in config.work_pool.lower():
            warnings.append(
                ValidationWarning(
                    code="MISMATCHED_WORK_POOL_TYPE",
                    message=f"Python deployment using Docker work pool: {config.work_pool}",
                    suggestion="Consider using a process-based work pool for Python deployments",
                )
            )
        elif (
            config.deployment_type == "docker"
            and "docker" not in config.work_pool.lower()
        ):
            warnings.append(
                ValidationWarning(
                    code="MISMATCHED_WORK_POOL_TYPE",
                    message=f"Docker deployment not using Docker work pool: {config.work_pool}",
                    suggestion="Consider using a Docker-based work pool for container deployments",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_environment(self, config: DeploymentConfig) -> ValidationResult:
        """Validate environment configuration."""
        errors = []
        warnings = []

        if not config.environment:
            warnings.append(
                ValidationWarning(
                    code="MISSING_ENVIRONMENT",
                    message="No environment specified",
                    suggestion="Specify environment (development, staging, production)",
                )
            )
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        if config.environment not in self.valid_environments:
            warnings.append(
                ValidationWarning(
                    code="UNKNOWN_ENVIRONMENT",
                    message=f"Unknown environment: {config.environment}",
                    suggestion=f"Consider using standard environments: {', '.join(self.valid_environments)}",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_parameters(self, config: DeploymentConfig) -> ValidationResult:
        """Validate deployment parameters."""
        errors = []
        warnings = []

        if not isinstance(config.parameters, dict):
            errors.append(
                ValidationError(
                    code="INVALID_PARAMETERS_TYPE",
                    message="Parameters must be a dictionary",
                    remediation="Provide parameters as a dictionary of key-value pairs",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check for sensitive data in parameters
        sensitive_keys = {"password", "secret", "key", "token", "api_key"}
        for param_key in config.parameters.keys():
            if any(sensitive in param_key.lower() for sensitive in sensitive_keys):
                warnings.append(
                    ValidationWarning(
                        code="SENSITIVE_DATA_IN_PARAMETERS",
                        message=f"Potentially sensitive parameter: {param_key}",
                        suggestion="Use environment variables or secrets management for sensitive data",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_job_variables(self, config: DeploymentConfig) -> ValidationResult:
        """Validate job variables for Docker deployments."""
        errors = []
        warnings = []

        if not isinstance(config.job_variables, dict):
            errors.append(
                ValidationError(
                    code="INVALID_JOB_VARIABLES_TYPE",
                    message="Job variables must be a dictionary",
                    remediation="Provide job variables as a dictionary",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Check for required Docker job variables
        if "image" not in config.job_variables:
            warnings.append(
                ValidationWarning(
                    code="MISSING_DOCKER_IMAGE",
                    message="No Docker image specified in job variables",
                    suggestion="Specify 'image' in job_variables for Docker deployments",
                )
            )

        # Validate environment variables
        if "env" in config.job_variables:
            env_vars = config.job_variables["env"]
            if isinstance(env_vars, dict):
                for env_key, _env_value in env_vars.items():
                    if not isinstance(env_key, str):
                        errors.append(
                            ValidationError(
                                code="INVALID_ENV_VAR_KEY",
                                message=f"Environment variable key must be string: {env_key}",
                                remediation="Use string keys for environment variables",
                            )
                        )

        # Validate volumes
        if "volumes" in config.job_variables:
            volumes = config.job_variables["volumes"]
            if isinstance(volumes, list):
                for volume in volumes:
                    if not isinstance(volume, str) or ":" not in volume:
                        warnings.append(
                            ValidationWarning(
                                code="INVALID_VOLUME_FORMAT",
                                message=f"Invalid volume format: {volume}",
                                suggestion="Use format 'host_path:container_path' for volumes",
                            )
                        )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_schedule(self, config: DeploymentConfig) -> ValidationResult:
        """Validate schedule configuration."""
        errors = []
        warnings = []

        if not config.schedule:
            return ValidationResult(is_valid=True, errors=errors, warnings=warnings)

        # Basic cron format validation
        if self._looks_like_cron(config.schedule):
            if not self._is_valid_cron(config.schedule):
                errors.append(
                    ValidationError(
                        code="INVALID_CRON_SCHEDULE",
                        message=f"Invalid cron schedule: {config.schedule}",
                        remediation="Use valid cron format (e.g., '0 9 * * 1-5' for weekdays at 9 AM)",
                    )
                )
        else:
            # Assume it's an interval or other format
            warnings.append(
                ValidationWarning(
                    code="UNKNOWN_SCHEDULE_FORMAT",
                    message=f"Unknown schedule format: {config.schedule}",
                    suggestion="Ensure schedule format is supported by Prefect",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_tags(self, config: DeploymentConfig) -> ValidationResult:
        """Validate deployment tags."""
        errors = []
        warnings = []

        if not isinstance(config.tags, list):
            errors.append(
                ValidationError(
                    code="INVALID_TAGS_TYPE",
                    message="Tags must be a list",
                    remediation="Provide tags as a list of strings",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        for tag in config.tags:
            if not isinstance(tag, str):
                errors.append(
                    ValidationError(
                        code="INVALID_TAG_TYPE",
                        message=f"Tag must be string: {tag}",
                        remediation="Use string values for tags",
                    )
                )
            elif not self._is_valid_tag(tag):
                warnings.append(
                    ValidationWarning(
                        code="INVALID_TAG_FORMAT",
                        message=f"Tag contains special characters: {tag}",
                        suggestion="Use alphanumeric characters and hyphens for tags",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _is_valid_name(self, name: str) -> bool:
        """Check if name follows valid naming conventions."""
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))

    def _is_valid_module_path(self, module_path: str) -> bool:
        """Check if module path is valid."""
        parts = module_path.split(".")
        return all(self._is_valid_python_identifier(part) for part in parts)

    def _is_valid_python_identifier(self, identifier: str) -> bool:
        """Check if string is a valid Python identifier."""
        return identifier.isidentifier()

    def _is_valid_tag(self, tag: str) -> bool:
        """Check if tag follows valid format."""
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", tag))

    def _looks_like_cron(self, schedule: str) -> bool:
        """Check if schedule looks like a cron expression."""
        parts = schedule.split()
        return len(parts) == 5

    def _is_valid_cron(self, cron_expr: str) -> bool:
        """Basic cron expression validation."""
        parts = cron_expr.split()
        if len(parts) != 5:
            return False

        # Basic validation for each field
        ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]

        for _i, (part, (min_val, max_val)) in enumerate(zip(parts, ranges)):
            if part == "*":
                continue
            if "/" in part:
                base, step = part.split("/", 1)
                if base != "*" and not base.isdigit():
                    return False
                if not step.isdigit():
                    return False
            elif "-" in part:
                start, end = part.split("-", 1)
                if not (start.isdigit() and end.isdigit()):
                    return False
                if not (
                    min_val <= int(start) <= max_val and min_val <= int(end) <= max_val
                ):
                    return False
            elif "," in part:
                values = part.split(",")
                for value in values:
                    if not value.isdigit() or not (min_val <= int(value) <= max_val):
                        return False
            elif part.isdigit():
                if not (min_val <= int(part) <= max_val):
                    return False
            else:
                return False

        return True
