"""
Error Handling CLI Commands

Provides CLI commands for error reporting, recovery, and rollback operations.
"""

import click
import json
from pathlib import Path
from typing import Optional

from ..error_handling import (
    ErrorReporter,
    RecoveryManager,
    RollbackManager,
    get_global_reporter,
    get_global_rollback_manager,
)


@click.group()
def error():
    """Error handling and recovery commands."""
    pass


@error.command()
@click.option(
    "--format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format",
)
@click.option("--limit", type=int, default=10, help="Number of recent errors to show")
def summary(format: str, limit: int):
    """Show error summary and recent errors."""
    reporter = get_global_reporter()
    summary_data = reporter.get_error_summary()

    if format == "json":
        click.echo(json.dumps(summary_data, indent=2))
    else:
        click.echo("=" * 50)
        click.echo("ERROR SUMMARY")
        click.echo("=" * 50)
        click.echo(f"Total Errors: {summary_data['total_errors']}")

        if summary_data["by_category"]:
            click.echo("\nBy Category:")
            for category, count in summary_data["by_category"].items():
                click.echo(f"  {category}: {count}")

        if summary_data["by_severity"]:
            click.echo("\nBy Severity:")
            for severity, count in summary_data["by_severity"].items():
                click.echo(f"  {severity}: {count}")

        if summary_data["recent_errors"]:
            click.echo(f"\nRecent Errors (last {limit}):")
            for error_info in summary_data["recent_errors"][-limit:]:
                click.echo(f"  [{error_info['timestamp']}] {error_info['error']}")


@error.command()
@click.option("--output", type=click.Path(), help="Output file path")
def export(output: Optional[str]):
    """Export comprehensive error report."""
    reporter = get_global_reporter()

    if not output:
        output = (
            f"error_report_{reporter.error_history[0].timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            if reporter.error_history
            else "error_report.json"
        )

    output_path = Path(output)
    reporter.export_error_report(output_path)
    click.echo(f"Error report exported to: {output_path}")


@error.command()
def clear():
    """Clear error history."""
    reporter = get_global_reporter()
    count = len(reporter.error_history)
    reporter.clear_history()
    click.echo(f"Cleared {count} errors from history")


@error.command()
@click.argument("error_type")
def guidance(error_type: str):
    """Get recovery guidance for a specific error type."""
    recovery_manager = RecoveryManager()

    # Create a mock error to get guidance
    try:
        from ..error_handling.error_types import (
            DeploymentSystemError,
            ErrorCategory,
            ErrorSeverity,
        )

        mock_error = DeploymentSystemError(
            message=f"Mock error for guidance: {error_type}",
            error_code=error_type.upper(),
            category=ErrorCategory.DEPLOYMENT,
            severity=ErrorSeverity.MEDIUM,
        )

        guidance = recovery_manager.get_recovery_guidance(mock_error)

        click.echo(f"Recovery Guidance for {error_type}:")
        click.echo("=" * 40)
        for line in guidance:
            click.echo(line)

    except Exception as e:
        click.echo(f"Could not get guidance for {error_type}: {e}")


@click.group()
def recovery():
    """Recovery and rollback commands."""
    pass


@recovery.command()
@click.option("--plan-id", help="Specific rollback plan ID")
@click.option(
    "--auto-execute", is_flag=True, help="Automatically execute recovery actions"
)
def execute(plan_id: Optional[str], auto_execute: bool):
    """Execute recovery or rollback operations."""
    rollback_manager = get_global_rollback_manager()

    if plan_id:
        # Execute specific rollback plan
        try:
            success = rollback_manager.execute_rollback(plan_id)
            if success:
                click.echo(f"✓ Rollback plan {plan_id} executed successfully")
            else:
                click.echo(f"✗ Rollback plan {plan_id} failed")
        except Exception as e:
            click.echo(f"✗ Error executing rollback plan {plan_id}: {e}")
    else:
        # Show available rollback plans
        plans = rollback_manager.get_rollback_plans()
        if not plans:
            click.echo("No rollback plans available")
            return

        click.echo("Available Rollback Plans:")
        for plan in plans:
            status_icon = (
                "✓"
                if plan.status.value == "completed"
                else "✗" if plan.status.value == "failed" else "⏳"
            )
            click.echo(
                f"  {status_icon} {plan.plan_id}: {plan.description} ({plan.status.value})"
            )


@recovery.command()
def list():
    """List all rollback plans."""
    rollback_manager = get_global_rollback_manager()
    plans = rollback_manager.get_rollback_plans()

    if not plans:
        click.echo("No rollback plans found")
        return

    click.echo("Rollback Plans:")
    click.echo("-" * 80)

    for plan in plans:
        status_icon = {
            "completed": "✓",
            "failed": "✗",
            "in_progress": "⏳",
            "pending": "⏸",
        }.get(plan.status.value, "?")

        click.echo(f"{status_icon} {plan.plan_id}")
        click.echo(f"   Description: {plan.description}")
        click.echo(f"   Status: {plan.status.value}")
        click.echo(f"   Created: {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if plan.executed_at:
            click.echo(f"   Executed: {plan.executed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo(f"   Operations: {len(plan.operations)}")
        click.echo()


@recovery.command()
@click.option("--days", type=int, default=30, help="Clean up plans older than N days")
def cleanup(days: int):
    """Clean up old rollback plans."""
    rollback_manager = get_global_rollback_manager()
    removed_count = rollback_manager.cleanup_old_plans(days)
    click.echo(f"Cleaned up {removed_count} rollback plans older than {days} days")


@recovery.command()
@click.argument("plan_id")
def details(plan_id: str):
    """Show detailed information about a rollback plan."""
    rollback_manager = get_global_rollback_manager()

    plan = rollback_manager.rollback_plans.get(plan_id)
    if not plan:
        click.echo(f"Rollback plan not found: {plan_id}")
        return

    click.echo(f"Rollback Plan: {plan.plan_id}")
    click.echo("=" * 50)
    click.echo(f"Description: {plan.description}")
    click.echo(f"Status: {plan.status.value}")
    click.echo(f"Created: {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    if plan.executed_at:
        click.echo(f"Executed: {plan.executed_at.strftime('%Y-%m-%d %H:%M:%S')}")

    click.echo(f"\nOperations ({len(plan.operations)}):")
    click.echo("-" * 30)

    for i, operation in enumerate(plan.operations, 1):
        status_icon = {
            "completed": "✓",
            "failed": "✗",
            "in_progress": "⏳",
            "pending": "⏸",
            "skipped": "⏭",
        }.get(operation.status.value, "?")

        click.echo(f"{i}. {status_icon} {operation.description}")
        click.echo(f"   Type: {operation.operation_type.value}")
        click.echo(f"   Status: {operation.status.value}")
        if operation.error_message:
            click.echo(f"   Error: {operation.error_message}")
        click.echo()


# Add commands to main CLI groups
def register_error_commands(cli_group):
    """Register error handling commands with the main CLI."""
    cli_group.add_command(error)
    cli_group.add_command(recovery)
