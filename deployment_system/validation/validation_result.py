"""
Validation Result Models

Defines data structures for validation results and errors.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationError:
    """Represents a validation error."""

    code: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    remediation: str = ""

    def __str__(self) -> str:
        """String representation of the error."""
        location = ""
        if self.file_path:
            location = f" in {self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"

        return f"[{self.code}] {self.message}{location}"


@dataclass
class ValidationWarning:
    """Represents a validation warning."""

    code: str
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    suggestion: str = ""

    def __str__(self) -> str:
        """String representation of the warning."""
        location = ""
        if self.file_path:
            location = f" in {self.file_path}"
            if self.line_number:
                location += f":{self.line_number}"

        return f"[{self.code}] {self.message}{location}"


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    is_valid: bool
    errors: list[ValidationError]
    warnings: list[ValidationWarning]

    def __post_init__(self):
        """Ensure lists are initialized."""
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    @property
    def error_count(self) -> int:
        """Get the number of errors."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Get the number of warnings."""
        return len(self.warnings)

    def add_error(self, error: ValidationError) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: ValidationWarning) -> None:
        """Add a warning to the result."""
        self.warnings.append(warning)

    def merge(self, other: "ValidationResult") -> None:
        """Merge another validation result into this one."""
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        if other.has_errors:
            self.is_valid = False

    def get_summary(self) -> str:
        """Get a summary of the validation result."""
        if self.is_valid:
            if self.has_warnings:
                return f"Valid with {self.warning_count} warning(s)"
            else:
                return "Valid"
        else:
            return (
                f"Invalid: {self.error_count} error(s), {self.warning_count} warning(s)"
            )

    def get_error_messages(self) -> list[str]:
        """Get all error messages."""
        return [str(error) for error in self.errors]

    def get_warning_messages(self) -> list[str]:
        """Get all warning messages."""
        return [str(warning) for warning in self.warnings]
