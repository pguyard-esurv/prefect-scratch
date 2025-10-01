"""
Flow Validator

Validates flow structure and dependencies - comprehensive validation module.
"""

import ast
import importlib.util
import sys
from pathlib import Path

from .validation_result import ValidationError, ValidationResult, ValidationWarning


class FlowValidator:
    """Comprehensive flow validator for validation module."""

    def __init__(self):
        self.required_imports = {"prefect"}
        self.common_dependencies = {
            "pandas",
            "numpy",
            "requests",
            "sqlalchemy",
            "psycopg2",
            "docker",
            "pydantic",
            "asyncio",
            "logging",
        }

    def validate_flow_syntax(self, file_path: str) -> ValidationResult:
        """Validate Python syntax of a flow file."""
        errors = []
        warnings = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
            ast.parse(content)
        except SyntaxError as e:
            errors.append(
                ValidationError(
                    code="SYNTAX_ERROR",
                    message=f"Syntax error: {e.msg}",
                    file_path=file_path,
                    line_number=e.lineno,
                    remediation="Fix the syntax error in the Python file",
                )
            )
        except Exception as e:
            errors.append(
                ValidationError(
                    code="PARSE_ERROR",
                    message=f"Failed to parse file: {str(e)}",
                    file_path=file_path,
                    remediation="Ensure the file is a valid Python file",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_flow_dependencies(self, file_path: str) -> ValidationResult:
        """Validate flow dependencies and imports."""
        errors = []
        warnings = []

        try:
            # Parse the file to extract imports
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)
            imports = self._extract_imports(tree)

            # Check for required Prefect imports
            if "prefect" not in imports:
                errors.append(
                    ValidationError(
                        code="MISSING_PREFECT_IMPORT",
                        message="Missing required 'prefect' import",
                        file_path=file_path,
                        remediation="Add 'from prefect import flow' or 'import prefect'",
                    )
                )

            # Validate that imports can be resolved
            missing_deps = self._check_import_availability(imports)
            for dep in missing_deps:
                if dep in self.common_dependencies:
                    errors.append(
                        ValidationError(
                            code="MISSING_DEPENDENCY",
                            message=f"Required dependency '{dep}' is not available",
                            file_path=file_path,
                            remediation=f"Install dependency with: pip install {dep}",
                        )
                    )
                else:
                    warnings.append(
                        ValidationWarning(
                            code="UNRESOLVED_IMPORT",
                            message=f"Import '{dep}' could not be resolved",
                            file_path=file_path,
                            suggestion=f"Ensure '{dep}' is installed or available in PYTHONPATH",
                        )
                    )

            # Check for potential circular imports
            circular_imports = self._detect_circular_imports(file_path, imports)
            for circular in circular_imports:
                warnings.append(
                    ValidationWarning(
                        code="POTENTIAL_CIRCULAR_IMPORT",
                        message=f"Potential circular import detected: {circular}",
                        file_path=file_path,
                        suggestion="Review import structure to avoid circular dependencies",
                    )
                )

        except Exception as e:
            errors.append(
                ValidationError(
                    code="DEPENDENCY_VALIDATION_ERROR",
                    message=f"Failed to validate dependencies: {str(e)}",
                    file_path=file_path,
                    remediation="Ensure the file is readable and contains valid Python code",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

    def validate_flow_structure(self, file_path: str) -> ValidationResult:
        """Validate flow structure and best practices."""
        errors = []
        warnings = []

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            # Find flow functions
            flow_functions = self._find_flow_functions(tree)

            if not flow_functions:
                errors.append(
                    ValidationError(
                        code="NO_FLOW_FUNCTIONS",
                        message="No functions with @flow decorator found",
                        file_path=file_path,
                        remediation="Add at least one function decorated with @flow",
                    )
                )

            # Validate each flow function
            for func_name, func_node in flow_functions.items():
                func_errors, func_warnings = self._validate_flow_function(
                    func_name, func_node, file_path
                )
                errors.extend(func_errors)
                warnings.extend(func_warnings)

            # Check for task functions
            task_functions = self._find_task_functions(tree)
            if not task_functions and flow_functions:
                warnings.append(
                    ValidationWarning(
                        code="NO_TASK_FUNCTIONS",
                        message="No @task decorated functions found",
                        file_path=file_path,
                        suggestion="Consider breaking flow logic into reusable tasks",
                    )
                )

        except Exception as e:
            errors.append(
                ValidationError(
                    code="STRUCTURE_VALIDATION_ERROR",
                    message=f"Failed to validate flow structure: {str(e)}",
                    file_path=file_path,
                    remediation="Ensure the file contains valid Python code with proper flow structure",
                )
            )

        return ValidationResult(
            is_valid=len(errors) == 0, errors=errors, warnings=warnings
        )

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

    def _check_import_availability(self, imports: set[str]) -> list[str]:
        """Check if imports are available in the current environment."""
        missing = []

        for imp in imports:
            if imp in sys.builtin_module_names:
                continue

            try:
                spec = importlib.util.find_spec(imp)
                if spec is None:
                    missing.append(imp)
            except (ImportError, ModuleNotFoundError, ValueError):
                missing.append(imp)

        return missing

    def _detect_circular_imports(self, file_path: str, imports: set[str]) -> list[str]:
        """Detect potential circular imports."""
        circular = []
        file_module = Path(file_path).stem

        # Simple heuristic: check if any import might reference back to this module
        for imp in imports:
            if file_module in imp or imp in file_module:
                circular.append(imp)

        return circular

    def _find_flow_functions(self, tree: ast.AST) -> dict[str, ast.FunctionDef]:
        """Find all functions decorated with @flow."""
        flow_functions = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if self._is_flow_decorator(decorator):
                        flow_functions[node.name] = node
                        break

        return flow_functions

    def _find_task_functions(self, tree: ast.AST) -> dict[str, ast.FunctionDef]:
        """Find all functions decorated with @task."""
        task_functions = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if self._is_task_decorator(decorator):
                        task_functions[node.name] = node
                        break

        return task_functions

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

    def _is_task_decorator(self, decorator: ast.AST) -> bool:
        """Check if a decorator is a Prefect @task decorator."""
        if isinstance(decorator, ast.Name):
            return decorator.id == "task"
        elif isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Name):
                return decorator.func.id == "task"
            elif isinstance(decorator.func, ast.Attribute):
                return decorator.func.attr == "task"
        return False

    def _validate_flow_function(
        self, func_name: str, func_node: ast.FunctionDef, file_path: str
    ) -> tuple[list[ValidationError], list[ValidationWarning]]:
        """Validate a specific flow function."""
        errors = []
        warnings = []

        # Check function signature
        if len(func_node.args.args) > 0:
            # Flow functions can have parameters, but warn about complexity
            if len(func_node.args.args) > 5:
                warnings.append(
                    ValidationWarning(
                        code="COMPLEX_FLOW_SIGNATURE",
                        message=f"Flow function '{func_name}' has many parameters ({len(func_node.args.args)})",
                        file_path=file_path,
                        suggestion="Consider using a configuration object or reducing parameters",
                    )
                )

        # Check for return statement
        has_return = any(isinstance(node, ast.Return) for node in ast.walk(func_node))
        if not has_return:
            warnings.append(
                ValidationWarning(
                    code="NO_RETURN_STATEMENT",
                    message=f"Flow function '{func_name}' has no return statement",
                    file_path=file_path,
                    suggestion="Consider returning a result for better flow tracking",
                )
            )

        # Check function length (complexity)
        if len(func_node.body) > 50:
            warnings.append(
                ValidationWarning(
                    code="COMPLEX_FLOW_FUNCTION",
                    message=f"Flow function '{func_name}' is very long ({len(func_node.body)} statements)",
                    file_path=file_path,
                    suggestion="Consider breaking the flow into smaller tasks",
                )
            )

        return errors, warnings
