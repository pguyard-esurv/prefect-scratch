"""
Configuration Validator

Provides validation utilities for deployment configurations.
"""

import sys
from pathlib import Path

import yaml

from ..validation.validation_result import (
    ValidationError,
    ValidationResult,
    ValidationWarning,
)
from .manager import ConfigurationManager


class ConfigValidator:
    """Validates deployment system configurations."""

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.manager = ConfigurationManager(config_dir)

    def validate_config_file(self, config_file: Path) -> ValidationResult:
        """Validate a configuration file."""
        errors = []
        warnings = []

        if not config_file.exists():
            errors.append(
                ValidationError(
                    code="CONFIG_FILE_NOT_FOUND",
                    message=f"Configuration file not found: {config_file}",
                    remediation=f"Create configuration file at {config_file}",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        try:
            with open(config_file, encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            errors.append(
                ValidationError(
                    code="INVALID_YAML",
                    message=f"Invalid YAML syntax in {config_file}: {e}",
                    remediation="Fix YAML syntax errors in configuration file",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
        except Exception as e:
            errors.append(
                ValidationError(
                    code="CONFIG_READ_ERROR",
                    message=f"Failed to read configuration file {config_file}: {e}",
                    remediation="Check file permissions and format",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate structure
        if not isinstance(config_data, dict):
            errors.append(
                ValidationError(
                    code="INVALID_CONFIG_STRUCTURE",
                    message="Configuration must be a YAML dictionary",
                    remediation="Ensure configuration file contains a valid YAML dictionary",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Validate required sections
        required_sections = ["environments"]
        for section in required_sections:
            if section not in config_data:
                errors.append(
                    ValidationError(
                        code="MISSING_REQUIRED_SECTION",
                        message=f"Required section '{section}' not found in configuration",
                        remediation=f"Add '{section}' section to configuration file",
                    )
                )

        # Validate environments section
        if "environments" in config_data:
            environments = config_data["environments"]
            if not isinstance(environments, dict):
                errors.append(
                    ValidationError(
                        code="INVALID_ENVIRONMENTS_SECTION",
                        message="Environments section must be a dictionary",
                        remediation="Ensure environments section contains environment configurations",
                    )
                )
            else:
                # Validate each environment
                for env_name, env_config in environments.items():
                    env_errors, env_warnings = self._validate_environment_structure(
                        env_name, env_config
                    )
                    errors.extend(env_errors)
                    warnings.extend(env_warnings)

        # Validate global_config section if present
        if "global_config" in config_data:
            global_config = config_data["global_config"]
            if not isinstance(global_config, dict):
                warnings.append(
                    ValidationWarning(
                        code="INVALID_GLOBAL_CONFIG",
                        message="Global config section should be a dictionary",
                        suggestion="Ensure global_config section contains valid configuration",
                    )
                )

        # Validate flow_overrides section if present
        if "flow_overrides" in config_data:
            flow_overrides = config_data["flow_overrides"]
            if not isinstance(flow_overrides, dict):
                warnings.append(
                    ValidationWarning(
                        code="INVALID_FLOW_OVERRIDES",
                        message="Flow overrides section should be a dictionary",
                        suggestion="Ensure flow_overrides section contains valid flow configurations",
                    )
                )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_environment_structure(
        self, env_name: str, env_config: dict
    ) -> tuple[list[ValidationError], list[ValidationWarning]]:
        """Validate the structure of an environment configuration."""
        errors = []
        warnings = []

        if not isinstance(env_config, dict):
            errors.append(
                ValidationError(
                    code="INVALID_ENVIRONMENT_CONFIG",
                    message=f"Environment '{env_name}' configuration must be a dictionary",
                    remediation=f"Ensure environment '{env_name}' contains valid configuration",
                )
            )
            return errors, warnings

        # Required fields
        required_fields = ["prefect_api_url"]
        for field in required_fields:
            if field not in env_config:
                errors.append(
                    ValidationError(
                        code="MISSING_REQUIRED_FIELD",
                        message=f"Required field '{field}' missing in environment '{env_name}'",
                        remediation=f"Add '{field}' to environment '{env_name}' configuration",
                    )
                )

        # Validate prefect_api_url format
        if "prefect_api_url" in env_config:
            api_url = env_config["prefect_api_url"]
            if not isinstance(api_url, str) or not api_url.startswith(
                ("http://", "https://")
            ):
                errors.append(
                    ValidationError(
                        code="INVALID_API_URL",
                        message=f"Invalid Prefect API URL in environment '{env_name}': {api_url}",
                        remediation="Provide a valid HTTP/HTTPS URL for prefect_api_url",
                    )
                )

        # Validate work_pools
        if "work_pools" in env_config:
            work_pools = env_config["work_pools"]
            if not isinstance(work_pools, dict):
                errors.append(
                    ValidationError(
                        code="INVALID_WORK_POOLS",
                        message=f"Work pools in environment '{env_name}' must be a dictionary",
                        remediation="Provide work pools as key-value pairs",
                    )
                )
            else:
                recommended_pools = ["python", "docker"]
                for pool_type in recommended_pools:
                    if pool_type not in work_pools:
                        warnings.append(
                            ValidationWarning(
                                code="MISSING_RECOMMENDED_WORK_POOL",
                                message=f"Recommended work pool '{pool_type}' not configured in environment '{env_name}'",
                                suggestion=f"Add work pool configuration for '{pool_type}' deployment type",
                            )
                        )

        # Validate resource_limits
        if "resource_limits" in env_config:
            resource_limits = env_config["resource_limits"]
            if not isinstance(resource_limits, dict):
                errors.append(
                    ValidationError(
                        code="INVALID_RESOURCE_LIMITS",
                        message=f"Resource limits in environment '{env_name}' must be a dictionary",
                        remediation="Provide resource limits as key-value pairs",
                    )
                )

        # Validate default_parameters
        if "default_parameters" in env_config:
            default_params = env_config["default_parameters"]
            if not isinstance(default_params, dict):
                warnings.append(
                    ValidationWarning(
                        code="INVALID_DEFAULT_PARAMETERS",
                        message=f"Default parameters in environment '{env_name}' should be a dictionary",
                        suggestion="Provide default parameters as key-value pairs",
                    )
                )

        return errors, warnings

    def validate_all_configurations(self) -> dict[str, ValidationResult]:
        """Validate all configuration files and environments."""
        results = {}

        # Validate main configuration file
        config_file = self.config_dir / "deployment-config.yaml"
        if not config_file.exists():
            config_file = self.config_dir / "deployment_config.yaml"

        results["config_file"] = self.validate_config_file(config_file)

        # Validate individual environments
        env_results = self.manager.validate_all_environments()
        results.update(env_results)

        return results

    def print_validation_results(self, results: dict[str, ValidationResult]):
        """Print validation results in a human-readable format."""
        print("Configuration Validation Results")
        print("=" * 50)

        overall_valid = True
        total_errors = 0
        total_warnings = 0

        for name, result in results.items():
            print(f"\n{name.upper()}:")
            print("-" * 30)

            if result.is_valid:
                print("✅ Valid")
            else:
                print("❌ Invalid")
                overall_valid = False

            if result.errors:
                print(f"\nErrors ({len(result.errors)}):")
                for error in result.errors:
                    print(f"  • {error.code}: {error.message}")
                    if error.remediation:
                        print(f"    → {error.remediation}")
                total_errors += len(result.errors)

            if result.warnings:
                print(f"\nWarnings ({len(result.warnings)}):")
                for warning in result.warnings:
                    print(f"  • {warning.code}: {warning.message}")
                    if hasattr(warning, "remediation") and warning.remediation:
                        print(f"    → {warning.remediation}")
                    elif hasattr(warning, "suggestion") and warning.suggestion:
                        print(f"    → {warning.suggestion}")
                total_warnings += len(result.warnings)

        print("\n" + "=" * 50)
        print(f"Overall Status: {'✅ Valid' if overall_valid else '❌ Invalid'}")
        print(f"Total Errors: {total_errors}")
        print(f"Total Warnings: {total_warnings}")

        return overall_valid


def main():
    """Main CLI entry point for configuration validation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate deployment system configuration"
    )
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Configuration directory (default: config)",
    )
    parser.add_argument(
        "--environment",
        help="Validate specific environment only",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors, suppress warnings",
    )

    args = parser.parse_args()

    validator = ConfigValidator(args.config_dir)

    if args.environment:
        # Validate specific environment
        result = validator.manager.validate_environment_config(args.environment)
        results = {args.environment: result}
    else:
        # Validate all configurations
        results = validator.validate_all_configurations()

    # Filter warnings if quiet mode
    if args.quiet:
        for result in results.values():
            result.warnings = []

    is_valid = validator.print_validation_results(results)
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
