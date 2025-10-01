"""
Validation CLI

Command-line interface for deployment validation system.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from ..config.deployment_config import DeploymentConfig
from ..discovery.flow_scanner import FlowScanner
from .comprehensive_validator import ComprehensiveValidator
from .validation_result import ValidationResult


class ValidationCLI:
    """Command-line interface for validation operations."""

    def __init__(self):
        self.validator = ComprehensiveValidator()
        self.scanner = FlowScanner()

    def validate_flow(self, flow_path: str, output_format: str = "text") -> int:
        """Validate a single flow file."""
        try:
            # Scan the flow
            flows = self.scanner.scan_file(flow_path)
            if not flows:
                print(f"No flows found in {flow_path}", file=sys.stderr)
                return 1

            flow_metadata = flows[0]

            # Validate flow structure and dependencies
            structure_result = self.validator.flow_validator.validate_flow_structure(
                flow_path
            )
            deps_result = self.validator.flow_validator.validate_flow_dependencies(
                flow_path
            )

            # Combine results
            combined_result = ValidationResult(is_valid=True, errors=[], warnings=[])
            combined_result.merge(structure_result)
            combined_result.merge(deps_result)

            # Output results
            self._output_result(
                f"Flow: {flow_metadata.name}", combined_result, output_format
            )

            return 0 if combined_result.is_valid else 1

        except Exception as e:
            print(f"Error validating flow: {e}", file=sys.stderr)
            return 1

    def validate_deployment(
        self, flow_path: str, deployment_config_path: str, output_format: str = "text"
    ) -> int:
        """Validate a deployment configuration."""
        try:
            # Load flow metadata
            flows = self.scanner.scan_file(flow_path)
            if not flows:
                print(f"No flows found in {flow_path}", file=sys.stderr)
                return 1

            flow_metadata = flows[0]

            # Load deployment configuration
            deployment_config = self._load_deployment_config(deployment_config_path)
            if not deployment_config:
                return 1

            # Validate deployment
            result = self.validator.validate_flow_for_deployment(
                flow_metadata, deployment_config
            )

            # Output results
            deployment_name = (
                f"{flow_metadata.name}/{deployment_config.deployment_name}"
            )
            self._output_result(f"Deployment: {deployment_name}", result, output_format)

            return 0 if result.is_valid else 1

        except Exception as e:
            print(f"Error validating deployment: {e}", file=sys.stderr)
            return 1

    def validate_all_flows(
        self, flows_dir: str = "flows", output_format: str = "text"
    ) -> int:
        """Validate all flows in a directory."""
        try:
            # Discover all flows
            flows = self.scanner.scan_directory(flows_dir)
            if not flows:
                print(f"No flows found in {flows_dir}", file=sys.stderr)
                return 1

            results = {}
            for flow_metadata in flows:
                # Validate each flow
                structure_result = (
                    self.validator.flow_validator.validate_flow_structure(
                        flow_metadata.path
                    )
                )
                deps_result = self.validator.flow_validator.validate_flow_dependencies(
                    flow_metadata.path
                )

                # Combine results
                combined_result = ValidationResult(
                    is_valid=True, errors=[], warnings=[]
                )
                combined_result.merge(structure_result)
                combined_result.merge(deps_result)

                results[flow_metadata.name] = combined_result

            # Output results
            self._output_multiple_results(
                "Flow Validation Results", results, output_format
            )

            # Return error code if any validation failed
            return 0 if all(result.is_valid for result in results.values()) else 1

        except Exception as e:
            print(f"Error validating flows: {e}", file=sys.stderr)
            return 1

    def validate_docker_setup(self, flow_path: str, output_format: str = "text") -> int:
        """Validate Docker setup for a flow."""
        try:
            # Load flow metadata
            flows = self.scanner.scan_file(flow_path)
            if not flows:
                print(f"No flows found in {flow_path}", file=sys.stderr)
                return 1

            flow_metadata = flows[0]

            # Validate Docker components
            results = {}

            if flow_metadata.dockerfile_path:
                dockerfile_result = self.validator.docker_validator.validate_dockerfile(
                    flow_metadata.dockerfile_path
                )
                results["Dockerfile"] = dockerfile_result

                # Validate build process
                build_result = self.validator.docker_validator.validate_docker_build(
                    flow_metadata.dockerfile_path,
                    str(Path(flow_metadata.path).parent),
                    f"{flow_metadata.name}-worker:latest",
                )
                results["Docker Build"] = build_result
            else:
                print(
                    f"No Dockerfile found for flow: {flow_metadata.name}",
                    file=sys.stderr,
                )
                return 1

            # Validate Docker Compose integration
            compose_result = (
                self.validator.docker_validator.validate_docker_compose_integration(
                    flow_metadata.name
                )
            )
            results["Docker Compose"] = compose_result

            # Output results
            self._output_multiple_results(
                f"Docker Validation: {flow_metadata.name}", results, output_format
            )

            return 0 if all(result.is_valid for result in results.values()) else 1

        except Exception as e:
            print(f"Error validating Docker setup: {e}", file=sys.stderr)
            return 1

    def generate_validation_report(
        self, flows_dir: str = "flows", output_file: Optional[str] = None
    ) -> int:
        """Generate comprehensive validation report."""
        try:
            # Discover all flows
            flows = self.scanner.scan_directory(flows_dir)
            if not flows:
                print(f"No flows found in {flows_dir}", file=sys.stderr)
                return 1

            # Validate all flows
            results = {}
            for flow_metadata in flows:
                # Create a basic deployment config for validation
                deployment_config = DeploymentConfig(
                    flow_name=flow_metadata.name,
                    deployment_name=f"{flow_metadata.name}-deployment",
                    environment="development",
                    deployment_type="python",
                    work_pool="default-agent-pool",
                    entrypoint=f"{flow_metadata.module_path}:{flow_metadata.function_name}",
                )

                # Validate flow and deployment
                result = self.validator.validate_flow_for_deployment(
                    flow_metadata, deployment_config
                )
                results[f"{flow_metadata.name}/default"] = result

            # Generate report
            report = self.validator.generate_validation_report(results)

            # Output report
            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(report)
                print(f"Validation report written to: {output_file}")
            else:
                print(report)

            return 0

        except Exception as e:
            print(f"Error generating validation report: {e}", file=sys.stderr)
            return 1

    def _load_deployment_config(self, config_path: str) -> Optional[DeploymentConfig]:
        """Load deployment configuration from file."""
        try:
            config_file = Path(config_path)
            if not config_file.exists():
                print(f"Configuration file not found: {config_path}", file=sys.stderr)
                return None

            with open(config_file, encoding="utf-8") as f:
                if config_file.suffix.lower() == ".json":
                    config_data = json.load(f)
                else:
                    # Assume YAML
                    import yaml

                    config_data = yaml.safe_load(f)

            return DeploymentConfig(**config_data)

        except Exception as e:
            print(f"Error loading configuration: {e}", file=sys.stderr)
            return None

    def _output_result(
        self, title: str, result: ValidationResult, output_format: str
    ) -> None:
        """Output validation result in specified format."""
        if output_format == "json":
            output = {
                "title": title,
                "is_valid": result.is_valid,
                "error_count": result.error_count,
                "warning_count": result.warning_count,
                "errors": [
                    {
                        "code": error.code,
                        "message": error.message,
                        "file_path": error.file_path,
                        "line_number": error.line_number,
                        "remediation": error.remediation,
                    }
                    for error in result.errors
                ],
                "warnings": [
                    {
                        "code": warning.code,
                        "message": warning.message,
                        "file_path": warning.file_path,
                        "line_number": warning.line_number,
                        "suggestion": warning.suggestion,
                    }
                    for warning in result.warnings
                ],
            }
            print(json.dumps(output, indent=2))
        else:
            # Text format
            status = "✅ VALID" if result.is_valid else "❌ INVALID"
            print(f"\n{title} - {status}")
            print(f"Errors: {result.error_count}, Warnings: {result.warning_count}")

            if result.has_errors:
                print("\nErrors:")
                for error in result.errors:
                    print(f"  [{error.code}] {error.message}")
                    if error.remediation:
                        print(f"    → {error.remediation}")

            if result.has_warnings:
                print("\nWarnings:")
                for warning in result.warnings:
                    print(f"  [{warning.code}] {warning.message}")
                    if warning.suggestion:
                        print(f"    → {warning.suggestion}")

    def _output_multiple_results(
        self, title: str, results: dict[str, ValidationResult], output_format: str
    ) -> None:
        """Output multiple validation results."""
        if output_format == "json":
            output = {"title": title, "results": {}}
            for name, result in results.items():
                output["results"][name] = {
                    "is_valid": result.is_valid,
                    "error_count": result.error_count,
                    "warning_count": result.warning_count,
                    "errors": [str(error) for error in result.errors],
                    "warnings": [str(warning) for warning in result.warnings],
                }
            print(json.dumps(output, indent=2))
        else:
            # Text format
            print(f"\n{title}")
            print("=" * len(title))

            for name, result in results.items():
                status = "✅ VALID" if result.is_valid else "❌ INVALID"
                print(f"\n{name} - {status}")

                if result.has_errors or result.has_warnings:
                    print(
                        f"  Errors: {result.error_count}, Warnings: {result.warning_count}"
                    )

                    for error in result.errors:
                        print(f"  ❌ {error}")

                    for warning in result.warnings:
                        print(f"  ⚠️  {warning}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Deployment Validation CLI")
    parser.add_argument(
        "--format", choices=["text", "json"], default="text", help="Output format"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Flow validation
    flow_parser = subparsers.add_parser("flow", help="Validate a single flow")
    flow_parser.add_argument("path", help="Path to flow file")

    # Deployment validation
    deploy_parser = subparsers.add_parser("deployment", help="Validate a deployment")
    deploy_parser.add_argument("flow_path", help="Path to flow file")
    deploy_parser.add_argument("config_path", help="Path to deployment configuration")

    # All flows validation
    all_parser = subparsers.add_parser("all-flows", help="Validate all flows")
    all_parser.add_argument("--flows-dir", default="flows", help="Flows directory")

    # Docker validation
    docker_parser = subparsers.add_parser("docker", help="Validate Docker setup")
    docker_parser.add_argument("flow_path", help="Path to flow file")

    # Report generation
    report_parser = subparsers.add_parser("report", help="Generate validation report")
    report_parser.add_argument("--flows-dir", default="flows", help="Flows directory")
    report_parser.add_argument("--output", help="Output file for report")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    cli = ValidationCLI()

    if args.command == "flow":
        return cli.validate_flow(args.path, args.format)
    elif args.command == "deployment":
        return cli.validate_deployment(args.flow_path, args.config_path, args.format)
    elif args.command == "all-flows":
        return cli.validate_all_flows(args.flows_dir, args.format)
    elif args.command == "docker":
        return cli.validate_docker_setup(args.flow_path, args.format)
    elif args.command == "report":
        return cli.generate_validation_report(args.flows_dir, args.output)

    return 1


if __name__ == "__main__":
    sys.exit(main())
