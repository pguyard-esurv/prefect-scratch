"""
CLI Utilities

Utility functions for the command-line interface.
"""

import json
from typing import Any


class CLIUtils:
    """Utility functions for CLI operations."""

    @staticmethod
    def format_json(data: Any, indent: int = 2) -> str:
        """Format data as JSON string."""
        return json.dumps(data, indent=indent, default=str)

    @staticmethod
    def print_table(headers: list, rows: list) -> None:
        """Print data in table format."""
        if not rows:
            print("No data to display")
            return

        # Calculate column widths
        widths = [len(str(header)) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))

        # Print header
        header_row = " | ".join(
            str(headers[i]).ljust(widths[i]) for i in range(len(headers))
        )
        print(header_row)
        print("-" * len(header_row))

        # Print rows
        for row in rows:
            data_row = " | ".join(str(row[i]).ljust(widths[i]) for i in range(len(row)))
            print(data_row)

    @staticmethod
    def print_validation_results(results: list) -> None:
        """Print validation results in a readable format."""
        for result in results:
            if result.get("is_valid"):
                print(f"✓ {result['name']}: Valid")
            else:
                print(f"✗ {result['name']}: Invalid")
                for error in result.get("errors", []):
                    print(f"  - {error}")

    @staticmethod
    def confirm_action(message: str) -> bool:
        """Ask for user confirmation."""
        response = input(f"{message} (y/N): ").strip().lower()
        return response in ["y", "yes"]
