"""
Flow Validator

Validates flow structure and dependencies.
"""

import ast
from pathlib import Path

from ..validation.validation_result import ValidationError, ValidationResult
from .metadata import FlowMetadata


class FlowValidator:
    """Validates Prefect flows for structure and dependencies."""

    def __init__(self):
        self.required_imports = {"prefect"}

    def validate_flow(self, flow_metadata: FlowMetadata) -> ValidationResult:
        """Validate a flow's structure and dependencies."""
        errors = []
        warnings = []

        # Basic metadata validation
        if not flow_metadata.name:
            errors.append(
                ValidationError(
                    code="MISSING_FLOW_NAME",
                    message="Flow name is missing",
                    file_path=flow_metadata.path,
                    remediation="Ensure the @flow decorator has a name parameter or the function has a valid name",
                )
            )

        # File existence validation
        if not Path(flow_metadata.path).exists():
            errors.append(
                ValidationError(
                    code="FILE_NOT_FOUND",
                    message=f"Flow file not found: {flow_metadata.path}",
                    file_path=flow_metadata.path,
                    remediation="Ensure the flow file exists and is accessible",
                )
            )
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        # Syntax validation
        syntax_errors = self._validate_syntax(flow_metadata.path)
        errors.extend(syntax_errors)

        # Import validation
        import_errors = self._validate_imports(flow_metadata.path)
        errors.extend(import_errors)

        # Flow decorator validation
        decorator_errors = self._validate_flow_decorator(flow_metadata)
        errors.extend(decorator_errors)

        # Dockerfile validation if present
        if flow_metadata.dockerfile_path:
            dockerfile_errors = self._validate_dockerfile(flow_metadata.dockerfile_path)
            errors.extend(dockerfile_errors)

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def _validate_syntax(self, file_path: str) -> list[ValidationError]:
        """Validate Python syntax of the flow file."""
        errors = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            ast.parse(content)
        except SyntaxError as e:
            errors.append(
                ValidationError(
                    code="SYNTAX_ERROR",
                    message=f"Syntax error in flow file: {e.msg}",
                    file_path=file_path,
                    line_number=e.lineno,
                    remediation="Fix the syntax error in the Python file",
                )
            )
        except Exception as e:
            errors.append(
                ValidationError(
                    code="PARSE_ERROR",
                    message=f"Failed to parse flow file: {str(e)}",
                    file_path=file_path,
                    remediation="Ensure the file is a valid Python file",
                )
            )

        return errors

    def _validate_imports(self, file_path: str) -> list[ValidationError]:
        """Validate that required imports are present."""
        errors = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            imports = self._extract_imports(tree)

            missing_imports = self.required_imports - imports
            if missing_imports:
                errors.append(
                    ValidationError(
                        code="MISSING_IMPORTS",
                        message=f"Missing required imports: {', '.join(missing_imports)}",
                        file_path=file_path,
                        remediation=f"Add the following imports: {', '.join(f'import {imp}' for imp in missing_imports)}",
                    )
                )

        except Exception as e:
            errors.append(
                ValidationError(
                    code="IMPORT_VALIDATION_ERROR",
                    message=f"Failed to validate imports: {str(e)}",
                    file_path=file_path,
                    remediation="Ensure the file can be parsed and contains valid import statements",
                )
            )

        return errors

    def _extract_imports(self, tree: ast.AST) -> set[str]:
        """Extract all imports from an AST."""
        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        return imports

    def _validate_flow_decorator(
        self, flow_metadata: FlowMetadata
    ) -> list[ValidationError]:
        """Validate the @flow decorator usage."""
        errors = []

        try:
            with open(flow_metadata.path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            # Find the function with the flow decorator
            flow_function = None
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.FunctionDef)
                    and node.name == flow_metadata.function_name
                ):
                    flow_function = node
                    break

            if not flow_function:
                errors.append(
                    ValidationError(
                        code="FLOW_FUNCTION_NOT_FOUND",
                        message=f"Flow function '{flow_metadata.function_name}' not found",
                        file_path=flow_metadata.path,
                        remediation="Ensure the flow function exists and has the correct name",
                    )
                )
                return errors

            # Check for @flow decorator
            has_flow_decorator = False
            for decorator in flow_function.decorator_list:
                if self._is_flow_decorator(decorator):
                    has_flow_decorator = True
                    break

            if not has_flow_decorator:
                errors.append(
                    ValidationError(
                        code="MISSING_FLOW_DECORATOR",
                        message=f"Function '{flow_metadata.function_name}' is missing @flow decorator",
                        file_path=flow_metadata.path,
                        remediation="Add @flow decorator to the function",
                    )
                )

        except Exception as e:
            errors.append(
                ValidationError(
                    code="DECORATOR_VALIDATION_ERROR",
                    message=f"Failed to validate flow decorator: {str(e)}",
                    file_path=flow_metadata.path,
                    remediation="Ensure the flow function is properly defined with @flow decorator",
                )
            )

        return errors

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

    def _validate_dockerfile(self, dockerfile_path: str) -> list[ValidationError]:
        """Validate Dockerfile if present."""
        errors = []

        if not Path(dockerfile_path).exists():
            errors.append(
                ValidationError(
                    code="DOCKERFILE_NOT_FOUND",
                    message=f"Dockerfile not found: {dockerfile_path}",
                    file_path=dockerfile_path,
                    remediation="Ensure the Dockerfile exists or remove the dockerfile_path reference",
                )
            )
            return errors

        try:
            with open(dockerfile_path, encoding="utf-8") as f:
                content = f.read()

            # Basic Dockerfile validation
            lines = [line.strip() for line in content.split("\n") if line.strip()]

            if not any(line.startswith("FROM") for line in lines):
                errors.append(
                    ValidationError(
                        code="DOCKERFILE_MISSING_FROM",
                        message="Dockerfile is missing FROM instruction",
                        file_path=dockerfile_path,
                        remediation="Add a FROM instruction to specify the base image",
                    )
                )

        except Exception as e:
            errors.append(
                ValidationError(
                    code="DOCKERFILE_VALIDATION_ERROR",
                    message=f"Failed to validate Dockerfile: {str(e)}",
                    file_path=dockerfile_path,
                    remediation="Ensure the Dockerfile is readable and properly formatted",
                )
            )

        return errors
