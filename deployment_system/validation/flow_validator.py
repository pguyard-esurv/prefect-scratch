"""
Flow Validator

Validates flow structure and dependencies - validation module version.
"""

# This is a placeholder to avoid circular imports
# The actual flow validation logic is in discovery/flow_validator.py
# This module can be used for additional flow validation that doesn't
# depend on FlowMetadata

from .validation_result import ValidationError, ValidationResult


class FlowValidator:
    """Base flow validator for validation module."""

    def __init__(self):
        pass

    def validate_flow_syntax(self, file_path: str) -> ValidationResult:
        """Validate Python syntax of a flow file."""
        import ast

        errors = []

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

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=[])
