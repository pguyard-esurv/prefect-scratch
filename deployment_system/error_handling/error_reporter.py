"""
Error Reporter

Provides detailed error reporting with logging, formatting, and
remediation guidance for deployment system errors.
"""

import logging
import json
import traceback
from typing import Any, Dict, List, Optional, TextIO
from datetime import datetime
from pathlib import Path

from .error_types import (
    DeploymentSystemError,
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
)

logger = logging.getLogger(__name__)


class ErrorReport:
    """Represents a comprehensive error report."""

    def __init__(
        self,
        error: Exception,
        timestamp: Optional[datetime] = None,
        operation: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ):
        self.error = error
        self.timestamp = timestamp or datetime.now()
        self.operation = operation
        self.additional_context = additional_context or {}
        self.traceback = (
            traceback.format_exc() if isinstance(error, Exception) else None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert error report to dictionary."""
        base_dict = {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "error_type": type(self.error).__name__,
            "error_message": str(self.error),
            "traceback": self.traceback,
            "additional_context": self.additional_context,
        }

        # Add deployment system error details if applicable
        if isinstance(self.error, DeploymentSystemError):
            base_dict.update(self.error.to_dict())

        return base_dict

    def to_json(self, indent: int = 2) -> str:
        """Convert error report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)


class ErrorReporter:
    """Handles error reporting, logging, and formatting."""

    def __init__(
        self,
        log_level: int = logging.ERROR,
        report_file: Optional[Path] = None,
        include_traceback: bool = True,
    ):
        self.log_level = log_level
        self.report_file = report_file
        self.include_traceback = include_traceback
        self.error_history: List[ErrorReport] = []

        # Set up logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(log_level)

    def report_error(
        self,
        error: Exception,
        operation: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
        log_error: bool = True,
        save_to_file: bool = True,
    ) -> ErrorReport:
        """Report an error with comprehensive logging and context."""
        report = ErrorReport(
            error=error, operation=operation, additional_context=additional_context
        )

        # Add to history
        self.error_history.append(report)

        # Log the error
        if log_error:
            self._log_error(report)

        # Save to file if configured
        if save_to_file and self.report_file:
            self._save_error_report(report)

        return report

    def _log_error(self, report: ErrorReport) -> None:
        """Log error with appropriate level and formatting."""
        error = report.error

        # Determine log level based on error severity
        if isinstance(error, DeploymentSystemError):
            if error.severity == ErrorSeverity.CRITICAL:
                log_level = logging.CRITICAL
            elif error.severity == ErrorSeverity.HIGH:
                log_level = logging.ERROR
            elif error.severity == ErrorSeverity.MEDIUM:
                log_level = logging.WARNING
            else:
                log_level = logging.INFO
        else:
            log_level = self.log_level

        # Format error message
        message = self._format_error_message(report)

        # Log with appropriate level
        self.logger.log(log_level, message)

        # Log traceback if enabled and available
        if self.include_traceback and report.traceback:
            self.logger.debug(f"Traceback:\n{report.traceback}")

    def _format_error_message(self, report: ErrorReport) -> str:
        """Format error message for logging."""
        error = report.error
        parts = []

        # Operation context
        if report.operation:
            parts.append(f"Operation: {report.operation}")

        # Error details
        if isinstance(error, DeploymentSystemError):
            parts.append(f"[{error.error_code}] {error.message}")

            # Add context information
            if error.context:
                context_parts = []
                if error.context.flow_name:
                    context_parts.append(f"Flow: {error.context.flow_name}")
                if error.context.deployment_name:
                    context_parts.append(f"Deployment: {error.context.deployment_name}")
                if error.context.environment:
                    context_parts.append(f"Environment: {error.context.environment}")
                if error.context.file_path:
                    context_parts.append(f"File: {error.context.file_path}")
                    if error.context.line_number:
                        context_parts[-1] += f":{error.context.line_number}"

                if context_parts:
                    parts.append(f"Context: {', '.join(context_parts)}")

            # Add remediation if available
            if error.remediation:
                parts.append(f"Remediation: {error.remediation}")
        else:
            parts.append(f"{type(error).__name__}: {error}")

        return " | ".join(parts)

    def _save_error_report(self, report: ErrorReport) -> None:
        """Save error report to file."""
        try:
            # Ensure directory exists
            self.report_file.parent.mkdir(parents=True, exist_ok=True)

            # Append to file
            with open(self.report_file, "a") as f:
                f.write(report.to_json() + "\n")

        except Exception as e:
            self.logger.warning(f"Failed to save error report to file: {e}")

    def format_user_friendly_error(self, error: Exception) -> str:
        """Format error message for end users."""
        if isinstance(error, DeploymentSystemError):
            message_parts = [f"❌ {error.message}"]

            # Add context if available
            if error.context:
                if error.context.flow_name:
                    message_parts.append(f"   Flow: {error.context.flow_name}")
                if error.context.deployment_name:
                    message_parts.append(
                        f"   Deployment: {error.context.deployment_name}"
                    )
                if error.context.environment:
                    message_parts.append(f"   Environment: {error.context.environment}")

            # Add remediation
            if error.remediation:
                message_parts.append(f"   💡 Solution: {error.remediation}")

            return "\n".join(message_parts)
        else:
            return f"❌ {type(error).__name__}: {error}"

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all reported errors."""
        if not self.error_history:
            return {"total_errors": 0, "by_category": {}, "by_severity": {}}

        by_category = {}
        by_severity = {}

        for report in self.error_history:
            error = report.error

            if isinstance(error, DeploymentSystemError):
                # Count by category
                category = error.category.value
                by_category[category] = by_category.get(category, 0) + 1

                # Count by severity
                severity = error.severity.value
                by_severity[severity] = by_severity.get(severity, 0) + 1
            else:
                # Generic error
                by_category["other"] = by_category.get("other", 0) + 1
                by_severity["unknown"] = by_severity.get("unknown", 0) + 1

        return {
            "total_errors": len(self.error_history),
            "by_category": by_category,
            "by_severity": by_severity,
            "recent_errors": [
                {
                    "timestamp": report.timestamp.isoformat(),
                    "operation": report.operation,
                    "error": str(report.error),
                }
                for report in self.error_history[-5:]  # Last 5 errors
            ],
        }

    def clear_history(self) -> None:
        """Clear error history."""
        self.error_history.clear()

    def export_error_report(self, file_path: Path) -> None:
        """Export comprehensive error report to file."""
        report_data = {
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_error_summary(),
            "errors": [report.to_dict() for report in self.error_history],
        }

        with open(file_path, "w") as f:
            json.dump(report_data, f, indent=2, default=str)

    def print_error_summary(self, file: Optional[TextIO] = None) -> None:
        """Print error summary to console or file."""
        summary = self.get_error_summary()

        print("=" * 50, file=file)
        print("ERROR SUMMARY", file=file)
        print("=" * 50, file=file)
        print(f"Total Errors: {summary['total_errors']}", file=file)

        if summary["by_category"]:
            print("\nBy Category:", file=file)
            for category, count in summary["by_category"].items():
                print(f"  {category}: {count}", file=file)

        if summary["by_severity"]:
            print("\nBy Severity:", file=file)
            for severity, count in summary["by_severity"].items():
                print(f"  {severity}: {count}", file=file)

        if summary["recent_errors"]:
            print("\nRecent Errors:", file=file)
            for error_info in summary["recent_errors"]:
                print(f"  [{error_info['timestamp']}] {error_info['error']}", file=file)

        print("=" * 50, file=file)


# Global error reporter instance
_global_reporter: Optional[ErrorReporter] = None


def get_global_reporter() -> ErrorReporter:
    """Get or create global error reporter instance."""
    global _global_reporter
    if _global_reporter is None:
        _global_reporter = ErrorReporter()
    return _global_reporter


def report_error(
    error: Exception,
    operation: Optional[str] = None,
    additional_context: Optional[Dict[str, Any]] = None,
) -> ErrorReport:
    """Convenience function to report error using global reporter."""
    return get_global_reporter().report_error(
        error=error, operation=operation, additional_context=additional_context
    )


def format_user_error(error: Exception) -> str:
    """Convenience function to format user-friendly error message."""
    return get_global_reporter().format_user_friendly_error(error)
