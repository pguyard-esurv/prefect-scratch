"""
Flow Scanner

Scans directories for Python files containing Prefect flows with comprehensive error handling.
"""

import ast
import os
import logging
from pathlib import Path
from typing import Any, Optional

from .metadata import FlowMetadata
from ..error_handling import (
    FlowDiscoveryError,
    ErrorContext,
    ErrorCodes,
    ErrorMessages,
    ErrorReporter,
    with_retry,
    RetryPolicies,
)

logger = logging.getLogger(__name__)


class FlowScanner:
    """Scans directories for Prefect flows and extracts metadata with error handling."""

    def __init__(self, base_path: str = "flows"):
        self.base_path = Path(base_path)
        self.error_reporter = ErrorReporter()

    def scan_flows(self) -> list[FlowMetadata]:
        """Scan for all flows in the base path with error handling."""
        flows = []

        if not self.base_path.exists():
            error = FlowDiscoveryError(
                f"Flow directory does not exist: {self.base_path}",
                error_code=ErrorCodes.FLOW_NOT_FOUND,
                context=ErrorContext(file_path=str(self.base_path)),
                remediation=f"Create the flows directory at {self.base_path} or specify a different path",
            )
            self.error_reporter.report_error(error, operation="scan_flows")
            return flows

        try:
            python_files = self._find_python_files()
            logger.info(f"Found {len(python_files)} Python files to scan")

            for python_file in python_files:
                try:
                    flow_metadata = self._extract_flow_metadata(python_file)
                    if flow_metadata:
                        flows.extend(flow_metadata)
                except Exception as e:
                    # Report error but continue scanning other files
                    error = FlowDiscoveryError(
                        f"Failed to scan file {python_file}: {str(e)}",
                        error_code=ErrorCodes.FLOW_SYNTAX_ERROR,
                        context=ErrorContext(file_path=str(python_file)),
                        remediation="Check file syntax and ensure it's a valid Python file",
                        cause=e,
                    )
                    self.error_reporter.report_error(error, operation="scan_flows")

                    # Create invalid flow metadata to track the error
                    invalid_flow = FlowMetadata(
                        name=python_file.stem,
                        path=str(python_file.absolute()),
                        module_path=self._get_module_path(python_file),
                        function_name="unknown",
                        is_valid=False,
                        validation_errors=[f"Failed to scan file: {str(e)}"],
                    )
                    flows.append(invalid_flow)

        except Exception as e:
            error = FlowDiscoveryError(
                f"Failed to scan flows directory: {str(e)}",
                error_code=ErrorCodes.FLOW_NOT_FOUND,
                context=ErrorContext(file_path=str(self.base_path)),
                remediation="Check directory permissions and ensure the path is accessible",
                cause=e,
            )
            self.error_reporter.report_error(error, operation="scan_flows")
            raise error

        logger.info(f"Successfully scanned {len(flows)} flows")
        return flows

    def _find_python_files(self) -> list[Path]:
        """Find all Python files in the flows directory."""
        python_files = []

        for root, dirs, files in os.walk(self.base_path):
            # Skip __pycache__ and test directories
            dirs[:] = [
                d for d in dirs if not d.startswith("__pycache__") and d != "test"
            ]

            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    python_files.append(Path(root) / file)

        return python_files

    def _extract_flow_metadata(self, file_path: Path) -> list[FlowMetadata]:
        """Extract flow metadata from a Python file with detailed error handling."""
        flows = []

        try:
            # Check if file exists and is readable
            if not file_path.exists():
                raise FlowDiscoveryError(
                    f"Flow file does not exist: {file_path}",
                    error_code=ErrorCodes.FLOW_NOT_FOUND,
                    context=ErrorContext(file_path=str(file_path)),
                    remediation="Ensure the file exists and the path is correct",
                )

            # Parse the AST to find flow decorators
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError as e:
                raise FlowDiscoveryError(
                    f"Cannot read file due to encoding issues: {file_path}",
                    error_code=ErrorCodes.FLOW_SYNTAX_ERROR,
                    context=ErrorContext(file_path=str(file_path)),
                    remediation="Ensure the file is saved with UTF-8 encoding",
                    cause=e,
                )

            try:
                tree = ast.parse(content)
            except SyntaxError as e:
                raise FlowDiscoveryError(
                    f"Python syntax error in {file_path}: {str(e)}",
                    error_code=ErrorCodes.FLOW_SYNTAX_ERROR,
                    context=ErrorContext(
                        file_path=str(file_path), line_number=e.lineno
                    ),
                    remediation="Fix the syntax error in the Python file",
                    cause=e,
                )

            # Extract flows from AST
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    flow_info = self._check_for_flow_decorator(node, file_path)
                    if flow_info:
                        flows.append(flow_info)

            # If no flows found, create a warning
            if not flows:
                logger.debug(f"No Prefect flows found in {file_path}")

        except FlowDiscoveryError:
            # Re-raise FlowDiscoveryError as-is
            raise
        except Exception as e:
            # Wrap other exceptions in FlowDiscoveryError
            raise FlowDiscoveryError(
                f"Unexpected error while processing {file_path}: {str(e)}",
                error_code=ErrorCodes.FLOW_SYNTAX_ERROR,
                context=ErrorContext(file_path=str(file_path)),
                remediation="Check file permissions and content",
                cause=e,
            )

        return flows

    def _check_for_flow_decorator(
        self, node: ast.FunctionDef, file_path: Path
    ) -> Optional[FlowMetadata]:
        """Check if a function has a @flow decorator."""
        for decorator in node.decorator_list:
            if self._is_flow_decorator(decorator):
                return self._create_flow_metadata(node, decorator, file_path)
        return None

    def _is_flow_decorator(self, decorator: ast.AST) -> bool:
        """Check if a decorator is a Prefect @flow decorator."""
        if isinstance(decorator, ast.Name):
            return decorator.id == "flow"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id == "flow"
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr == "flow"
        return False

    def _create_flow_metadata(
        self, node: ast.FunctionDef, decorator: ast.AST, file_path: Path
    ) -> FlowMetadata:
        """Create FlowMetadata from AST nodes."""
        # Extract flow name from decorator or use function name
        flow_name = self._extract_flow_name(decorator, node.name)

        # Extract decorator metadata
        decorator_metadata = self._extract_decorator_metadata(decorator)

        # Find associated files
        dockerfile_path = self._find_dockerfile(file_path)
        env_files = self._find_env_files(file_path)
        dependencies = self._find_dependencies(file_path)

        return FlowMetadata(
            name=flow_name,
            path=str(file_path.absolute()),
            module_path=self._get_module_path(file_path),
            function_name=node.name,
            dockerfile_path=dockerfile_path,
            env_files=env_files,
            dependencies=dependencies,
            metadata=decorator_metadata,
        )

    def _extract_flow_name(self, decorator: ast.AST, function_name: str) -> str:
        """Extract flow name from decorator or use function name."""
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                    return keyword.value.value
        return function_name

    def _extract_decorator_metadata(self, decorator: ast.AST) -> dict[str, Any]:
        """Extract metadata from flow decorator."""
        metadata = {}

        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if isinstance(keyword.value, ast.Constant):
                    metadata[keyword.arg] = keyword.value.value

        return metadata

    def _get_module_path(self, file_path: Path) -> str:
        """Convert file path to Python module path."""
        # Get relative path from project root
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path

        # Convert to module path
        parts = rel_path.with_suffix("").parts
        return ".".join(parts)

    def _find_dockerfile(self, flow_file: Path) -> Optional[str]:
        """Find Dockerfile in the same directory as the flow."""
        flow_dir = flow_file.parent
        dockerfile_path = flow_dir / "Dockerfile"

        if dockerfile_path.exists():
            return str(dockerfile_path.absolute())
        return None

    def _find_env_files(self, flow_file: Path) -> list[str]:
        """Find environment files in the same directory as the flow."""
        flow_dir = flow_file.parent
        env_files = []

        for file in flow_dir.glob(".env*"):
            if file.is_file():
                env_files.append(str(file.absolute()))

        return sorted(env_files)

    def _find_dependencies(self, flow_file: Path) -> list[str]:
        """Find dependencies from requirements files in the flow directory."""
        flow_dir = flow_file.parent
        dependencies = []

        # Look for requirements files
        for req_file in ["requirements.txt", "requirements-dev.txt", "pyproject.toml"]:
            req_path = flow_dir / req_file
            if req_path.exists():
                try:
                    if req_file.endswith(".txt"):
                        dependencies.extend(self._parse_requirements_txt(req_path))
                    elif req_file == "pyproject.toml":
                        dependencies.extend(self._parse_pyproject_toml(req_path))
                except Exception:
                    # If parsing fails, continue
                    pass

        return dependencies

    def _parse_requirements_txt(self, req_path: Path) -> list[str]:
        """Parse requirements.txt file."""
        dependencies = []

        try:
            with open(req_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract package name (before version specifiers)
                        package = (
                            line.split("==")[0]
                            .split(">=")[0]
                            .split("<=")[0]
                            .split("~=")[0]
                            .split("!=")[0]
                        )
                        package = package.strip()
                        if package:
                            dependencies.append(package)
        except Exception:
            pass

        return dependencies

    def _parse_pyproject_toml(self, toml_path: Path) -> list[str]:
        """Parse pyproject.toml file for dependencies."""
        dependencies = []

        try:
            # Basic TOML parsing for dependencies
            # This is a simple implementation - could be enhanced with a proper TOML parser
            with open(toml_path, encoding="utf-8") as f:
                content = f.read()

            # Look for dependencies section
            in_dependencies = False
            for line in content.split("\n"):
                line = line.strip()
                if (
                    line == "[tool.poetry.dependencies]"
                    or line == "[project.dependencies]"
                ):
                    in_dependencies = True
                    continue
                elif line.startswith("[") and in_dependencies:
                    in_dependencies = False
                    continue
                elif in_dependencies and "=" in line:
                    # Extract package name
                    package = line.split("=")[0].strip().strip('"').strip("'")
                    if package and package != "python":
                        dependencies.append(package)
        except Exception:
            pass

        return dependencies
