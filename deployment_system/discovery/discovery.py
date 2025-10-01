"""
Flow Discovery

Main orchestrator for flow discovery and validation.
"""


from ..validation.validation_result import ValidationResult
from .flow_scanner import FlowScanner
from .flow_validator import FlowValidator
from .metadata import FlowMetadata


class FlowDiscovery:
    """Main flow discovery orchestrator."""

    def __init__(self, base_path: str = "flows"):
        self.scanner = FlowScanner(base_path)
        self.validator = FlowValidator()

    def discover_flows(self, validate: bool = True) -> list[FlowMetadata]:
        """Discover all flows in the repository."""
        flows = self.scanner.scan_flows()

        if validate:
            for flow in flows:
                if flow.is_valid:  # Only validate flows that passed initial scanning
                    validation_result = self.validator.validate_flow(flow)
                    if not validation_result.is_valid:
                        flow.is_valid = False
                        flow.validation_errors.extend(
                            [error.message for error in validation_result.errors]
                        )

        return flows

    def discover_valid_flows(self) -> list[FlowMetadata]:
        """Discover only valid flows."""
        all_flows = self.discover_flows(validate=True)
        return [flow for flow in all_flows if flow.is_valid]

    def validate_flow(self, flow_path: str) -> ValidationResult:
        """Validate a specific flow file."""
        # Create minimal metadata for validation
        flow_metadata = FlowMetadata(
            name="temp", path=flow_path, module_path="temp", function_name="temp"
        )

        return self.validator.validate_flow(flow_metadata)

    def get_flow_dependencies(self, flow_metadata: FlowMetadata) -> list[str]:
        """Get dependencies for a specific flow."""
        dependencies = []

        # Add basic Prefect dependency
        dependencies.append("prefect")

        # Analyze imports from the flow file
        try:
            import_deps = self._analyze_imports(flow_metadata.path)
            dependencies.extend(import_deps)
        except Exception:
            # If import analysis fails, continue with basic dependencies
            pass

        # Add any dependencies from flow metadata
        if flow_metadata.dependencies:
            dependencies.extend(flow_metadata.dependencies)

        return list(set(dependencies))  # Remove duplicates

    def _analyze_imports(self, file_path: str) -> list[str]:
        """Analyze imports in a Python file to extract dependencies."""
        import ast

        dependencies = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        # Get the top-level package name
                        package = alias.name.split(".")[0]
                        if package not in [
                            "os",
                            "sys",
                            "json",
                            "datetime",
                            "pathlib",
                            "typing",
                        ]:
                            dependencies.append(package)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        # Get the top-level package name
                        package = node.module.split(".")[0]
                        if package not in [
                            "os",
                            "sys",
                            "json",
                            "datetime",
                            "pathlib",
                            "typing",
                        ]:
                            dependencies.append(package)

        except Exception:
            # If parsing fails, return empty list
            pass

        return dependencies

    def get_flows_by_type(self, flows: list[FlowMetadata]) -> dict:
        """Categorize flows by deployment type support."""
        return {
            "python_only": [
                f
                for f in flows
                if f.supports_python_deployment and not f.supports_docker_deployment
            ],
            "docker_only": [
                f
                for f in flows
                if f.supports_docker_deployment and not f.supports_python_deployment
            ],
            "both": [
                f
                for f in flows
                if f.supports_python_deployment and f.supports_docker_deployment
            ],
            "invalid": [f for f in flows if not f.is_valid],
        }
