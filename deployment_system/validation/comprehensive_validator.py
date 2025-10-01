"""
Comprehensive Validator

Orchestrates all validation components for complete deployment validation.
"""

from pathlib import Path

from ..config.deployment_config import DeploymentConfig
from ..discovery.metadata import FlowMetadata
from .deployment_validator import DeploymentValidator
from .docker_validator import DockerValidator
from .flow_validator import FlowValidator
from .validation_result import ValidationError, ValidationResult, ValidationWarning


class ComprehensiveValidator:
    """Orchestrates comprehensive validation for deployment system."""

    def __init__(self):
        self.flow_validator = FlowValidator()
        self.deployment_validator = DeploymentValidator()
        self.docker_validator = DockerValidator()

    def validate_flow_for_deployment(
        self, flow_metadata: FlowMetadata, deployment_config: DeploymentConfig
    ) -> ValidationResult:
        """Perform comprehensive validation for a flow and its deployment configuration."""
        errors = []
        warnings = []

        # Flow structure validation
        flow_structure_result = self.flow_validator.validate_flow_structure(
            flow_metadata.path
        )
        errors.extend(flow_structure_result.errors)
        warnings.extend(flow_structure_result.warnings)

        # Flow dependencies validation
        flow_deps_result = self.flow_validator.validate_flow_dependencies(
            flow_metadata.path
        )
        errors.extend(flow_deps_result.errors)
        warnings.extend(flow_deps_result.warnings)

        # Deployment configuration validation
        deployment_result = self.deployment_validator.validate_deployment_config(
            deployment_config
        )
        errors.extend(deployment_result.errors)
        warnings.extend(deployment_result.warnings)

        # Docker-specific validation for container deployments
        if deployment_config.deployment_type == "docker":
            docker_result = self._validate_docker_deployment(
                flow_metadata, deployment_config
            )
            errors.extend(docker_result.errors)
            warnings.extend(docker_result.warnings)

        # Cross-validation between flow and deployment
        cross_validation_result = self._validate_flow_deployment_compatibility(
            flow_metadata, deployment_config
        )
        errors.extend(cross_validation_result.errors)
        warnings.extend(cross_validation_result.warnings)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_deployment_readiness(
        self, flow_metadata: FlowMetadata, deployment_config: DeploymentConfig
    ) -> ValidationResult:
        """Validate that a deployment is ready for execution."""
        errors = []
        warnings = []

        # Basic validation first
        basic_result = self.validate_flow_for_deployment(
            flow_metadata, deployment_config
        )
        errors.extend(basic_result.errors)
        warnings.extend(basic_result.warnings)

        # If basic validation fails, don't proceed with readiness checks
        if basic_result.has_errors:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Environment readiness validation
        env_result = self._validate_environment_readiness(deployment_config)
        errors.extend(env_result.errors)
        warnings.extend(env_result.warnings)

        # Docker readiness validation for container deployments
        if deployment_config.deployment_type == "docker":
            docker_readiness_result = self._validate_docker_readiness(
                flow_metadata, deployment_config
            )
            errors.extend(docker_readiness_result.errors)
            warnings.extend(docker_readiness_result.warnings)

        # Prefect server connectivity validation
        prefect_result = self._validate_prefect_connectivity(deployment_config)
        errors.extend(prefect_result.errors)
        warnings.extend(prefect_result.warnings)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_multiple_deployments(
        self, deployments: list[tuple[FlowMetadata, DeploymentConfig]]
    ) -> dict[str, ValidationResult]:
        """Validate multiple deployments and check for conflicts."""
        results = {}
        deployment_names = set()
        work_pools = {}

        for flow_metadata, deployment_config in deployments:
            deployment_key = f"{flow_metadata.name}/{deployment_config.deployment_name}"

            # Individual deployment validation
            result = self.validate_flow_for_deployment(flow_metadata, deployment_config)

            # Check for naming conflicts
            if deployment_key in deployment_names:
                result.add_error(
                    ValidationError(
                        code="DUPLICATE_DEPLOYMENT_NAME",
                        message=f"Duplicate deployment name: {deployment_key}",
                        remediation="Use unique deployment names across all flows",
                    )
                )
            deployment_names.add(deployment_key)

            # Track work pool usage
            work_pool = deployment_config.work_pool
            if work_pool not in work_pools:
                work_pools[work_pool] = []
            work_pools[work_pool].append(deployment_key)

            results[deployment_key] = result

        # Check work pool distribution
        for work_pool, deployments_list in work_pools.items():
            if len(deployments_list) > 10:  # Arbitrary threshold
                for deployment_key in deployments_list:
                    results[deployment_key].add_warning(
                        ValidationWarning(
                            code="WORK_POOL_OVERLOAD",
                            message=f"Work pool '{work_pool}' has many deployments ({len(deployments_list)})",
                            suggestion="Consider distributing deployments across multiple work pools",
                        )
                    )

        return results

    def generate_validation_report(
        self, validation_results: dict[str, ValidationResult]
    ) -> str:
        """Generate a comprehensive validation report."""
        report_lines = []
        report_lines.append("# Deployment Validation Report")
        report_lines.append("")

        total_deployments = len(validation_results)
        valid_deployments = sum(
            1 for result in validation_results.values() if result.is_valid
        )
        total_errors = sum(result.error_count for result in validation_results.values())
        total_warnings = sum(
            result.warning_count for result in validation_results.values()
        )

        # Summary
        report_lines.append("## Summary")
        report_lines.append(f"- Total deployments: {total_deployments}")
        report_lines.append(f"- Valid deployments: {valid_deployments}")
        report_lines.append(
            f"- Invalid deployments: {total_deployments - valid_deployments}"
        )
        report_lines.append(f"- Total errors: {total_errors}")
        report_lines.append(f"- Total warnings: {total_warnings}")
        report_lines.append("")

        # Detailed results
        report_lines.append("## Detailed Results")
        report_lines.append("")

        for deployment_name, result in validation_results.items():
            status = "✅ VALID" if result.is_valid else "❌ INVALID"
            report_lines.append(f"### {deployment_name} - {status}")
            report_lines.append("")

            if result.has_errors:
                report_lines.append("**Errors:**")
                for error in result.errors:
                    report_lines.append(f"- [{error.code}] {error.message}")
                    if error.remediation:
                        report_lines.append(f"  - *Remediation:* {error.remediation}")
                report_lines.append("")

            if result.has_warnings:
                report_lines.append("**Warnings:**")
                for warning in result.warnings:
                    report_lines.append(f"- [{warning.code}] {warning.message}")
                    if warning.suggestion:
                        report_lines.append(f"  - *Suggestion:* {warning.suggestion}")
                report_lines.append("")

        # Remediation guide
        if total_errors > 0:
            report_lines.append("## Remediation Guide")
            report_lines.append("")

            # Collect unique error codes and their remediations
            error_remediations = {}
            for result in validation_results.values():
                for error in result.errors:
                    if error.code not in error_remediations and error.remediation:
                        error_remediations[error.code] = error.remediation

            for error_code, remediation in error_remediations.items():
                report_lines.append(f"**{error_code}:** {remediation}")
                report_lines.append("")

        return "\n".join(report_lines)

    def _validate_docker_deployment(
        self, flow_metadata: FlowMetadata, deployment_config: DeploymentConfig
    ) -> ValidationResult:
        """Validate Docker-specific aspects of deployment."""
        errors = []
        warnings = []

        # Dockerfile validation
        if flow_metadata.dockerfile_path:
            dockerfile_result = self.docker_validator.validate_dockerfile(
                flow_metadata.dockerfile_path
            )
            errors.extend(dockerfile_result.errors)
            warnings.extend(dockerfile_result.warnings)
        else:
            errors.append(
                ValidationError(
                    code="MISSING_DOCKERFILE",
                    message=f"Docker deployment requires Dockerfile for flow: {flow_metadata.name}",
                    remediation="Create a Dockerfile in the flow directory",
                )
            )

        # Docker Compose integration validation
        compose_result = self.docker_validator.validate_docker_compose_integration(
            flow_metadata.name
        )
        warnings.extend(compose_result.warnings)

        # Job variables validation for Docker
        if "image" in deployment_config.job_variables:
            image_name = deployment_config.job_variables["image"]
            image_result = self.docker_validator.validate_docker_image_exists(
                image_name
            )
            warnings.extend(image_result.warnings)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_flow_deployment_compatibility(
        self, flow_metadata: FlowMetadata, deployment_config: DeploymentConfig
    ) -> ValidationResult:
        """Validate compatibility between flow and deployment configuration."""
        errors = []
        warnings = []

        # Check entrypoint matches flow
        if deployment_config.entrypoint:
            module_path, function_name = deployment_config.entrypoint.split(":", 1)

            # Check if function name matches flow metadata
            if (
                flow_metadata.function_name
                and function_name != flow_metadata.function_name
            ):
                warnings.append(
                    ValidationWarning(
                        code="ENTRYPOINT_FUNCTION_MISMATCH",
                        message=f"Entrypoint function '{function_name}' doesn't match flow function '{flow_metadata.function_name}'",
                        suggestion="Ensure entrypoint function name matches the actual flow function",
                    )
                )

            # Check if module path is reasonable for flow path
            expected_module = flow_metadata.module_path
            if expected_module and module_path != expected_module:
                warnings.append(
                    ValidationWarning(
                        code="ENTRYPOINT_MODULE_MISMATCH",
                        message=f"Entrypoint module '{module_path}' doesn't match expected '{expected_module}'",
                        suggestion="Ensure entrypoint module path matches the flow file location",
                    )
                )

        # Check deployment name conventions
        if not deployment_config.deployment_name.startswith(flow_metadata.name):
            warnings.append(
                ValidationWarning(
                    code="DEPLOYMENT_NAME_CONVENTION",
                    message=f"Deployment name '{deployment_config.deployment_name}' doesn't start with flow name '{flow_metadata.name}'",
                    suggestion="Consider using flow name as prefix for deployment name",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_environment_readiness(
        self, deployment_config: DeploymentConfig
    ) -> ValidationResult:
        """Validate environment readiness for deployment."""
        errors = []
        warnings = []

        # Check for environment-specific configuration files
        env_files = [
            f".env.{deployment_config.environment}",
            f"config/{deployment_config.environment}.yaml",
            f"config/{deployment_config.environment}.json",
        ]

        env_file_found = False
        for env_file in env_files:
            if Path(env_file).exists():
                env_file_found = True
                break

        if not env_file_found:
            warnings.append(
                ValidationWarning(
                    code="NO_ENVIRONMENT_CONFIG",
                    message=f"No environment-specific configuration found for '{deployment_config.environment}'",
                    suggestion=f"Create configuration file for {deployment_config.environment} environment",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_docker_readiness(
        self, flow_metadata: FlowMetadata, deployment_config: DeploymentConfig
    ) -> ValidationResult:
        """Validate Docker readiness for deployment."""
        errors = []
        warnings = []

        # Check if Docker image exists or can be built
        if "image" in deployment_config.job_variables:
            image_name = deployment_config.job_variables["image"]

            # Check if image exists
            image_result = self.docker_validator.validate_docker_image_exists(
                image_name
            )

            # If image doesn't exist, check if it can be built
            if image_result.has_warnings and flow_metadata.dockerfile_path:
                build_result = self.docker_validator.validate_docker_build(
                    flow_metadata.dockerfile_path,
                    str(Path(flow_metadata.path).parent),
                    image_name,
                )
                errors.extend(build_result.errors)
                warnings.extend(build_result.warnings)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_prefect_connectivity(
        self, deployment_config: DeploymentConfig
    ) -> ValidationResult:
        """Validate Prefect server connectivity."""
        errors = []
        warnings = []

        # This is a placeholder for Prefect connectivity validation
        # In a real implementation, this would check:
        # - Prefect server accessibility
        # - Work pool existence
        # - Authentication status

        warnings.append(
            ValidationWarning(
                code="PREFECT_CONNECTIVITY_NOT_CHECKED",
                message="Prefect server connectivity not validated",
                suggestion="Ensure Prefect server is accessible and work pools are configured",
            )
        )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )
