"""
Example flow demonstrating distributed processing monitoring and operational utilities.

This example shows how to use the monitoring tasks for operational visibility,
health checking, diagnostics, and maintenance of the distributed processing system.
"""

from typing import Optional

from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from core.monitoring import (
    distributed_processing_diagnostics,
    distributed_queue_monitoring,
    distributed_system_maintenance,
    processing_performance_monitoring,
)


@flow(
    name="Distributed Processing Health Monitoring",
    description="Comprehensive health monitoring for distributed processing system",
    task_runner=ConcurrentTaskRunner()
)
def distributed_health_monitoring_flow(
    flow_names: Optional[list[str]] = None,
    include_performance_analysis: bool = True,
    performance_window_hours: int = 24
) -> dict:
    """
    Comprehensive health monitoring flow for distributed processing system.

    This flow performs complete health assessment including queue monitoring,
    system diagnostics, and performance analysis to provide operational
    visibility into the distributed processing system.

    Args:
        flow_names: Optional list of specific flows to monitor
        include_performance_analysis: Whether to include performance metrics
        performance_window_hours: Time window for performance analysis

    Returns:
        Dictionary containing comprehensive monitoring results
    """
    logger = get_run_logger()

    logger.info("Starting comprehensive distributed processing health monitoring")

    monitoring_results = {
        "monitoring_timestamp": None,
        "queue_monitoring": {},
        "system_diagnostics": {},
        "performance_analysis": {},
        "overall_health_assessment": {},
        "recommendations": [],
        "alerts": []
    }

    try:
        # Step 1: Queue Monitoring
        logger.info("Step 1: Monitoring distributed processing queue")
        queue_status = distributed_queue_monitoring(
            flow_names=flow_names,
            include_detailed_metrics=True
        )
        monitoring_results["queue_monitoring"] = queue_status
        monitoring_results["monitoring_timestamp"] = queue_status["monitoring_timestamp"]

        # Step 2: System Diagnostics
        logger.info("Step 2: Running system diagnostics")
        diagnostics = distributed_processing_diagnostics(
            flow_name=None,  # Diagnose all flows
            include_orphaned_analysis=True,
            include_performance_analysis=True
        )
        monitoring_results["system_diagnostics"] = diagnostics

        # Step 3: Performance Analysis (if requested)
        if include_performance_analysis:
            logger.info(f"Step 3: Analyzing performance over {performance_window_hours} hours")
            performance = processing_performance_monitoring(
                flow_names=flow_names,
                time_window_hours=performance_window_hours,
                include_error_analysis=True
            )
            monitoring_results["performance_analysis"] = performance
        else:
            logger.info("Step 3: Skipping performance analysis (not requested)")

        # Step 4: Overall Health Assessment
        logger.info("Step 4: Generating overall health assessment")
        health_assessment = _generate_overall_health_assessment(
            queue_status, diagnostics, monitoring_results.get("performance_analysis")
        )
        monitoring_results["overall_health_assessment"] = health_assessment

        # Step 5: Consolidate Recommendations and Alerts
        logger.info("Step 5: Consolidating recommendations and alerts")
        all_recommendations = []
        all_alerts = []

        # Collect recommendations from all sources
        all_recommendations.extend(queue_status.get("recommendations", []))
        all_recommendations.extend(diagnostics.get("recommendations", []))
        if monitoring_results.get("performance_analysis"):
            all_recommendations.extend(
                monitoring_results["performance_analysis"].get("recommendations", [])
            )

        # Collect alerts from all sources
        all_alerts.extend(queue_status.get("operational_alerts", []))
        if monitoring_results.get("performance_analysis"):
            all_alerts.extend(
                monitoring_results["performance_analysis"].get("alerts", [])
            )

        # Add diagnostic issues as alerts
        diagnostic_issues = diagnostics.get("issues_found", [])
        for issue in diagnostic_issues:
            all_alerts.append(f"DIAGNOSTIC: {issue}")

        monitoring_results["recommendations"] = list(set(all_recommendations))  # Remove duplicates
        monitoring_results["alerts"] = all_alerts

        # Log summary
        overall_status = health_assessment["overall_status"]
        alert_count = len(all_alerts)
        recommendation_count = len(monitoring_results["recommendations"])

        logger.info(
            f"Health monitoring complete: {overall_status} status, "
            f"{alert_count} alerts, {recommendation_count} recommendations"
        )

        if alert_count > 0:
            logger.warning(f"ALERTS DETECTED ({alert_count}):")
            for alert in all_alerts[:5]:  # Log first 5 alerts
                logger.warning(f"  - {alert}")
            if alert_count > 5:
                logger.warning(f"  ... and {alert_count - 5} more alerts")

        return monitoring_results

    except Exception as e:
        logger.error(f"Distributed health monitoring failed: {e}")
        raise RuntimeError(f"Health monitoring execution failed: {e}") from e


@flow(
    name="Distributed Processing Diagnostics",
    description="Detailed diagnostics for troubleshooting distributed processing issues"
)
def distributed_diagnostics_flow(
    target_flow: Optional[str] = None,
    include_maintenance_recommendations: bool = True
) -> dict:
    """
    Detailed diagnostics flow for troubleshooting distributed processing issues.

    This flow performs comprehensive diagnostics to help identify and resolve
    issues with the distributed processing system including orphaned records,
    performance bottlenecks, and system health problems.

    Args:
        target_flow: Optional specific flow to diagnose (diagnoses all if None)
        include_maintenance_recommendations: Whether to include maintenance suggestions

    Returns:
        Dictionary containing detailed diagnostic information and recommendations
    """
    logger = get_run_logger()

    logger.info(f"Starting detailed diagnostics for flow: {target_flow or 'all flows'}")

    diagnostic_results = {
        "diagnostic_timestamp": None,
        "target_flow": target_flow,
        "system_diagnostics": {},
        "queue_analysis": {},
        "maintenance_recommendations": {},
        "troubleshooting_guide": {},
        "next_steps": []
    }

    try:
        # Step 1: Comprehensive System Diagnostics
        logger.info("Step 1: Running comprehensive system diagnostics")
        diagnostics = distributed_processing_diagnostics(
            flow_name=target_flow,
            include_orphaned_analysis=True,
            include_performance_analysis=True
        )
        diagnostic_results["system_diagnostics"] = diagnostics
        diagnostic_results["diagnostic_timestamp"] = diagnostics["diagnostic_timestamp"]

        # Step 2: Detailed Queue Analysis
        logger.info("Step 2: Performing detailed queue analysis")
        queue_analysis = distributed_queue_monitoring(
            flow_names=[target_flow] if target_flow else None,
            include_detailed_metrics=True
        )
        diagnostic_results["queue_analysis"] = queue_analysis

        # Step 3: Maintenance Recommendations
        if include_maintenance_recommendations:
            logger.info("Step 3: Generating maintenance recommendations")
            maintenance_recommendations = _generate_maintenance_recommendations(
                diagnostics, queue_analysis
            )
            diagnostic_results["maintenance_recommendations"] = maintenance_recommendations
        else:
            logger.info("Step 3: Skipping maintenance recommendations")

        # Step 4: Troubleshooting Guide
        logger.info("Step 4: Generating troubleshooting guide")
        troubleshooting_guide = _generate_troubleshooting_guide(
            diagnostics, queue_analysis
        )
        diagnostic_results["troubleshooting_guide"] = troubleshooting_guide

        # Step 5: Next Steps Recommendations
        logger.info("Step 5: Determining next steps")
        next_steps = _determine_next_steps(diagnostics, queue_analysis)
        diagnostic_results["next_steps"] = next_steps

        # Log diagnostic summary
        issues_found = len(diagnostics.get("issues_found", []))
        system_health = diagnostics.get("system_health", {}).get("status", "unknown")
        queue_health = queue_analysis.get("queue_health_assessment", {}).get("queue_health", "unknown")

        logger.info(
            f"Diagnostics complete: {issues_found} issues found, "
            f"system health: {system_health}, queue health: {queue_health}"
        )

        if issues_found > 0:
            logger.warning("Issues requiring attention:")
            for issue in diagnostics["issues_found"]:
                logger.warning(f"  - {issue}")

        return diagnostic_results

    except Exception as e:
        logger.error(f"Distributed diagnostics failed: {e}")
        raise RuntimeError(f"Diagnostics execution failed: {e}") from e


@flow(
    name="Distributed Processing Maintenance",
    description="Automated maintenance operations for distributed processing system"
)
def distributed_maintenance_flow(
    perform_cleanup: bool = True,
    perform_failed_reset: bool = False,
    cleanup_timeout_hours: int = 2,
    max_retries: int = 3,
    dry_run: bool = False
) -> dict:
    """
    Automated maintenance flow for distributed processing system.

    This flow performs routine maintenance operations including orphaned record
    cleanup, failed record reset, and system optimization to keep the distributed
    processing system running efficiently.

    Args:
        perform_cleanup: Whether to clean up orphaned records
        perform_failed_reset: Whether to reset failed records for retry
        cleanup_timeout_hours: Hours after which records are considered orphaned
        max_retries: Maximum retry count for failed record reset
        dry_run: If True, only report what would be done without making changes

    Returns:
        Dictionary containing maintenance operation results and recommendations
    """
    logger = get_run_logger()

    logger.info(f"Starting distributed processing maintenance (dry_run: {dry_run})")

    maintenance_results = {
        "maintenance_timestamp": None,
        "dry_run": dry_run,
        "pre_maintenance_status": {},
        "maintenance_operations": {},
        "post_maintenance_status": {},
        "maintenance_summary": {},
        "recommendations": []
    }

    try:
        # Step 1: Pre-maintenance Assessment
        logger.info("Step 1: Assessing system status before maintenance")
        pre_status = distributed_queue_monitoring(include_detailed_metrics=True)
        maintenance_results["pre_maintenance_status"] = pre_status

        # Step 2: Perform Maintenance Operations
        logger.info("Step 2: Performing maintenance operations")
        maintenance_ops = distributed_system_maintenance(
            cleanup_orphaned_records=perform_cleanup,
            reset_failed_records=perform_failed_reset,
            orphaned_timeout_hours=cleanup_timeout_hours,
            max_retries=max_retries,
            dry_run=dry_run
        )
        maintenance_results["maintenance_operations"] = maintenance_ops
        maintenance_results["maintenance_timestamp"] = maintenance_ops["maintenance_timestamp"]

        # Step 3: Post-maintenance Assessment
        logger.info("Step 3: Assessing system status after maintenance")
        post_status = distributed_queue_monitoring(include_detailed_metrics=True)
        maintenance_results["post_maintenance_status"] = post_status

        # Step 4: Generate Maintenance Summary
        logger.info("Step 4: Generating maintenance summary")
        maintenance_summary = _generate_maintenance_summary(
            pre_status, post_status, maintenance_ops
        )
        maintenance_results["maintenance_summary"] = maintenance_summary

        # Step 5: Generate Recommendations
        logger.info("Step 5: Generating post-maintenance recommendations")
        recommendations = maintenance_ops.get("recommendations", [])
        maintenance_results["recommendations"] = recommendations

        # Log maintenance summary
        operations_performed = len(maintenance_ops.get("operations_performed", []))

        if dry_run:
            logger.info(f"Maintenance dry run completed: {operations_performed} operations simulated")
        else:
            logger.info(f"Maintenance completed: {operations_performed} operations performed")

        # Log specific results
        if perform_cleanup:
            cleanup_results = maintenance_ops.get("cleanup_results", {})
            if dry_run:
                found_count = cleanup_results.get("orphaned_records_found", 0)
                logger.info(f"  - Would clean up {found_count} orphaned records")
            else:
                cleaned_count = cleanup_results.get("records_cleaned", 0)
                logger.info(f"  - Cleaned up {cleaned_count} orphaned records")

        if perform_failed_reset:
            reset_results = maintenance_ops.get("reset_results", {})
            total_reset = reset_results.get("total_records_reset", 0)
            if dry_run:
                logger.info("  - Would reset failed records for retry")
            else:
                logger.info(f"  - Reset {total_reset} failed records for retry")

        return maintenance_results

    except Exception as e:
        logger.error(f"Distributed maintenance failed: {e}")
        raise RuntimeError(f"Maintenance execution failed: {e}") from e


@flow(
    name="Distributed Processing Performance Analysis",
    description="Comprehensive performance analysis for distributed processing system"
)
def distributed_performance_analysis_flow(
    analysis_window_hours: int = 24,
    include_trend_analysis: bool = True,
    generate_optimization_report: bool = True
) -> dict:
    """
    Comprehensive performance analysis flow for distributed processing system.

    This flow analyzes processing performance, identifies bottlenecks, and provides
    optimization recommendations for the distributed processing system.

    Args:
        analysis_window_hours: Time window for performance analysis
        include_trend_analysis: Whether to include trend analysis
        generate_optimization_report: Whether to generate optimization recommendations

    Returns:
        Dictionary containing performance analysis and optimization recommendations
    """
    logger = get_run_logger()

    logger.info(f"Starting performance analysis (window: {analysis_window_hours}h)")

    analysis_results = {
        "analysis_timestamp": None,
        "analysis_window_hours": analysis_window_hours,
        "performance_metrics": {},
        "trend_analysis": {},
        "bottleneck_analysis": {},
        "optimization_report": {},
        "recommendations": []
    }

    try:
        # Step 1: Performance Metrics Collection
        logger.info("Step 1: Collecting performance metrics")
        performance_metrics = processing_performance_monitoring(
            flow_names=None,  # Analyze all flows
            time_window_hours=analysis_window_hours,
            include_error_analysis=True
        )
        analysis_results["performance_metrics"] = performance_metrics
        analysis_results["analysis_timestamp"] = performance_metrics["monitoring_timestamp"]

        # Step 2: Trend Analysis (if requested)
        if include_trend_analysis:
            logger.info("Step 2: Performing trend analysis")
            trend_analysis = _perform_trend_analysis(performance_metrics)
            analysis_results["trend_analysis"] = trend_analysis
        else:
            logger.info("Step 2: Skipping trend analysis")

        # Step 3: Bottleneck Analysis
        logger.info("Step 3: Analyzing performance bottlenecks")
        bottleneck_analysis = _analyze_performance_bottlenecks(performance_metrics)
        analysis_results["bottleneck_analysis"] = bottleneck_analysis

        # Step 4: Optimization Report (if requested)
        if generate_optimization_report:
            logger.info("Step 4: Generating optimization report")
            optimization_report = _generate_optimization_report(
                performance_metrics, bottleneck_analysis
            )
            analysis_results["optimization_report"] = optimization_report
        else:
            logger.info("Step 4: Skipping optimization report")

        # Step 5: Consolidate Recommendations
        logger.info("Step 5: Consolidating optimization recommendations")
        all_recommendations = []
        all_recommendations.extend(performance_metrics.get("recommendations", []))
        if analysis_results.get("optimization_report"):
            all_recommendations.extend(
                analysis_results["optimization_report"].get("recommendations", [])
            )

        analysis_results["recommendations"] = list(set(all_recommendations))

        # Log analysis summary
        overall_success_rate = performance_metrics.get("overall_metrics", {}).get("success_rate_percent", 0)
        processing_rate = performance_metrics.get("overall_metrics", {}).get("avg_processing_rate_per_hour", 0)
        alert_count = len(performance_metrics.get("alerts", []))

        logger.info(
            f"Performance analysis complete: {overall_success_rate:.1f}% success rate, "
            f"{processing_rate:.1f} records/hour, {alert_count} performance alerts"
        )

        if alert_count > 0:
            logger.warning("Performance alerts detected:")
            for alert in performance_metrics.get("alerts", [])[:3]:
                logger.warning(f"  - {alert}")

        return analysis_results

    except Exception as e:
        logger.error(f"Performance analysis failed: {e}")
        raise RuntimeError(f"Performance analysis execution failed: {e}") from e


# Helper functions for analysis and reporting

def _generate_overall_health_assessment(
    queue_status: dict,
    diagnostics: dict,
    performance_analysis: Optional[dict] = None
) -> dict:
    """Generate overall health assessment from monitoring data."""

    # Collect health indicators
    queue_health = queue_status.get("queue_health_assessment", {}).get("queue_health", "unknown")
    system_health = diagnostics.get("system_health", {}).get("status", "unknown")
    issues_count = len(diagnostics.get("issues_found", []))

    # Performance indicators
    if performance_analysis:
        success_rate = performance_analysis.get("overall_metrics", {}).get("success_rate_percent", 100)
        processing_rate = performance_analysis.get("overall_metrics", {}).get("avg_processing_rate_per_hour", 0)
    else:
        success_rate = 100
        processing_rate = 0

    # Determine overall status
    if system_health == "unhealthy" or queue_health == "critical" or issues_count > 5:
        overall_status = "critical"
    elif (system_health == "degraded" or queue_health == "degraded" or
          success_rate < 90 or issues_count > 2):
        overall_status = "degraded"
    elif queue_health == "idle" and processing_rate == 0:
        overall_status = "idle"
    else:
        overall_status = "healthy"

    return {
        "overall_status": overall_status,
        "health_indicators": {
            "queue_health": queue_health,
            "system_health": system_health,
            "issues_count": issues_count,
            "success_rate_percent": success_rate,
            "processing_rate_per_hour": processing_rate
        },
        "assessment_timestamp": queue_status.get("monitoring_timestamp")
    }


def _generate_maintenance_recommendations(diagnostics: dict, queue_analysis: dict) -> dict:
    """Generate maintenance recommendations based on diagnostics."""

    recommendations = {
        "immediate_actions": [],
        "scheduled_maintenance": [],
        "optimization_opportunities": [],
        "monitoring_adjustments": []
    }

    # Immediate actions based on issues
    issues = diagnostics.get("issues_found", [])
    for issue in issues:
        if "orphaned" in issue.lower():
            recommendations["immediate_actions"].append("Run orphaned record cleanup")
        elif "connectivity" in issue.lower():
            recommendations["immediate_actions"].append("Investigate database connectivity issues")
        elif "performance" in issue.lower():
            recommendations["immediate_actions"].append("Investigate performance bottlenecks")

    # Scheduled maintenance based on queue status
    queue_health = queue_analysis.get("queue_health_assessment", {})
    failed_records = queue_analysis.get("overall_queue_status", {}).get("failed_records", 0)

    if failed_records > 50:
        recommendations["scheduled_maintenance"].append("Schedule failed record analysis and reset")

    if queue_health.get("queue_health") == "overloaded":
        recommendations["scheduled_maintenance"].append("Plan capacity scaling")

    # Optimization opportunities
    orphaned_analysis = diagnostics.get("orphaned_records_analysis", {})
    if orphaned_analysis.get("total_orphaned_records", 0) > 0:
        recommendations["optimization_opportunities"].append("Optimize processing timeout settings")

    # Monitoring adjustments
    if len(issues) > 3:
        recommendations["monitoring_adjustments"].append("Increase monitoring frequency")

    return recommendations


def _generate_troubleshooting_guide(diagnostics: dict, queue_analysis: dict) -> dict:
    """Generate troubleshooting guide based on current issues."""

    guide = {
        "current_issues": [],
        "diagnostic_steps": [],
        "resolution_steps": [],
        "escalation_criteria": []
    }

    # Identify current issues
    issues = diagnostics.get("issues_found", [])
    alerts = queue_analysis.get("operational_alerts", [])

    guide["current_issues"] = issues + alerts

    # Generate diagnostic steps based on issues
    if any("orphaned" in issue.lower() for issue in issues):
        guide["diagnostic_steps"].append("Check container logs for crashes or hangs")
        guide["diagnostic_steps"].append("Verify processing timeout configuration")
        guide["resolution_steps"].append("Run orphaned record cleanup maintenance")

    if any("connectivity" in issue.lower() for issue in issues):
        guide["diagnostic_steps"].append("Test database connectivity manually")
        guide["diagnostic_steps"].append("Check connection pool utilization")
        guide["resolution_steps"].append("Restart database connections or increase pool size")

    # Escalation criteria
    system_health = diagnostics.get("system_health", {}).get("status")
    if system_health == "unhealthy":
        guide["escalation_criteria"].append("System health is unhealthy - escalate immediately")

    if len(issues) > 5:
        guide["escalation_criteria"].append("Multiple critical issues detected - escalate to senior team")

    return guide


def _determine_next_steps(diagnostics: dict, queue_analysis: dict) -> list:
    """Determine recommended next steps based on analysis."""

    next_steps = []

    # Based on system health
    system_health = diagnostics.get("system_health", {}).get("status")
    if system_health == "unhealthy":
        next_steps.append("URGENT: Resolve database connectivity issues")
    elif system_health == "degraded":
        next_steps.append("Investigate and resolve database performance issues")

    # Based on queue health
    queue_health = queue_analysis.get("queue_health_assessment", {}).get("queue_health")
    if queue_health == "critical":
        next_steps.append("URGENT: Investigate high failure rates")
    elif queue_health == "overloaded":
        next_steps.append("Scale up processing capacity")

    # Based on specific issues
    issues = diagnostics.get("issues_found", [])
    if any("orphaned" in issue.lower() for issue in issues):
        next_steps.append("Run maintenance to clean up orphaned records")

    # Default next step
    if not next_steps:
        next_steps.append("Continue monitoring - system appears healthy")

    return next_steps


def _generate_maintenance_summary(pre_status: dict, post_status: dict, maintenance_ops: dict) -> dict:
    """Generate summary of maintenance operations and their impact."""

    # Extract key metrics
    pre_metrics = pre_status.get("overall_queue_status", {})
    post_metrics = post_status.get("overall_queue_status", {})

    summary = {
        "operations_performed": maintenance_ops.get("operations_performed", []),
        "metrics_comparison": {
            "before": {
                "total_records": pre_metrics.get("total_records", 0),
                "pending_records": pre_metrics.get("pending_records", 0),
                "processing_records": pre_metrics.get("processing_records", 0),
                "failed_records": pre_metrics.get("failed_records", 0)
            },
            "after": {
                "total_records": post_metrics.get("total_records", 0),
                "pending_records": post_metrics.get("pending_records", 0),
                "processing_records": post_metrics.get("processing_records", 0),
                "failed_records": post_metrics.get("failed_records", 0)
            }
        },
        "improvements": {},
        "effectiveness_assessment": "unknown"
    }

    # Calculate improvements
    before = summary["metrics_comparison"]["before"]
    after = summary["metrics_comparison"]["after"]

    summary["improvements"] = {
        "processing_records_reduced": before["processing_records"] - after["processing_records"],
        "failed_records_reduced": before["failed_records"] - after["failed_records"],
        "total_records_change": after["total_records"] - before["total_records"]
    }

    # Assess effectiveness
    processing_improvement = summary["improvements"]["processing_records_reduced"]
    failed_improvement = summary["improvements"]["failed_records_reduced"]

    if processing_improvement > 0 or failed_improvement > 0:
        summary["effectiveness_assessment"] = "effective"
    elif processing_improvement == 0 and failed_improvement == 0:
        summary["effectiveness_assessment"] = "no_change"
    else:
        summary["effectiveness_assessment"] = "needs_investigation"

    return summary


def _perform_trend_analysis(performance_metrics: dict) -> dict:
    """Perform trend analysis on performance metrics."""

    # Extract trend data from performance metrics
    trends = performance_metrics.get("performance_trends", {})
    hourly_trends = trends.get("hourly_trends", {})

    if not hourly_trends:
        return {"error": "No trend data available"}

    # Calculate trend indicators
    hours = list(hourly_trends.keys())
    processing_rates = [hourly_trends[hour]["total_processed"] for hour in hours]

    trend_analysis = {
        "analysis_period": {
            "start_hour": min(hours) if hours else None,
            "end_hour": max(hours) if hours else None,
            "total_hours": len(hours)
        },
        "processing_trends": {
            "peak_hour_processing": max(processing_rates) if processing_rates else 0,
            "min_hour_processing": min(processing_rates) if processing_rates else 0,
            "avg_hour_processing": sum(processing_rates) / len(processing_rates) if processing_rates else 0
        },
        "trend_direction": "stable"  # Simplified - could implement more sophisticated trend detection
    }

    return trend_analysis


def _analyze_performance_bottlenecks(performance_metrics: dict) -> dict:
    """Analyze performance bottlenecks from metrics."""

    bottlenecks = {
        "identified_bottlenecks": [],
        "performance_indicators": {},
        "recommendations": []
    }

    # Analyze overall metrics
    overall_metrics = performance_metrics.get("overall_metrics", {})
    success_rate = overall_metrics.get("success_rate_percent", 100)
    processing_rate = overall_metrics.get("avg_processing_rate_per_hour", 0)
    avg_processing_time = overall_metrics.get("avg_processing_time_minutes", 0)

    bottlenecks["performance_indicators"] = {
        "success_rate": success_rate,
        "processing_rate": processing_rate,
        "avg_processing_time": avg_processing_time
    }

    # Identify bottlenecks
    if success_rate < 90:
        bottlenecks["identified_bottlenecks"].append("High failure rate")
        bottlenecks["recommendations"].append("Investigate error patterns and fix root causes")

    if processing_rate < 50:
        bottlenecks["identified_bottlenecks"].append("Low processing throughput")
        bottlenecks["recommendations"].append("Consider scaling up or optimizing processing logic")

    if avg_processing_time > 15:
        bottlenecks["identified_bottlenecks"].append("High processing latency")
        bottlenecks["recommendations"].append("Profile and optimize business logic performance")

    return bottlenecks


def _generate_optimization_report(performance_metrics: dict, bottleneck_analysis: dict) -> dict:
    """Generate optimization report with specific recommendations."""

    report = {
        "optimization_opportunities": [],
        "performance_targets": {},
        "implementation_priorities": [],
        "recommendations": []
    }

    # Identify optimization opportunities
    bottlenecks = bottleneck_analysis.get("identified_bottlenecks", [])

    if "High failure rate" in bottlenecks:
        report["optimization_opportunities"].append({
            "area": "Error Handling",
            "description": "Improve error handling and retry logic",
            "expected_impact": "Increase success rate by 5-10%"
        })

    if "Low processing throughput" in bottlenecks:
        report["optimization_opportunities"].append({
            "area": "Capacity Scaling",
            "description": "Increase container instances or optimize batch sizes",
            "expected_impact": "Increase throughput by 50-100%"
        })

    if "High processing latency" in bottlenecks:
        report["optimization_opportunities"].append({
            "area": "Performance Optimization",
            "description": "Optimize business logic and database queries",
            "expected_impact": "Reduce processing time by 20-40%"
        })

    # Set performance targets
    current_success_rate = performance_metrics.get("overall_metrics", {}).get("success_rate_percent", 100)
    current_processing_rate = performance_metrics.get("overall_metrics", {}).get("avg_processing_rate_per_hour", 0)

    report["performance_targets"] = {
        "target_success_rate": max(95, current_success_rate + 5),
        "target_processing_rate": max(100, current_processing_rate * 1.5),
        "target_processing_time_minutes": 10
    }

    # Implementation priorities
    if bottlenecks:
        report["implementation_priorities"] = [
            "Address critical bottlenecks first",
            "Implement monitoring for new optimizations",
            "Test changes in staging environment",
            "Roll out optimizations gradually"
        ]

    # Consolidate recommendations
    report["recommendations"] = bottleneck_analysis.get("recommendations", [])

    return report


# Example usage and testing functions
if __name__ == "__main__":
    # Example: Run health monitoring
    print("Running distributed processing health monitoring example...")

    try:
        result = distributed_health_monitoring_flow(
            include_performance_analysis=True,
            performance_window_hours=6
        )

        overall_status = result["overall_health_assessment"]["overall_status"]
        alert_count = len(result["alerts"])

        print(f"Health monitoring completed: {overall_status} status")
        print(f"Alerts: {alert_count}")

        if alert_count > 0:
            print("Top alerts:")
            for alert in result["alerts"][:3]:
                print(f"  - {alert}")

    except Exception as e:
        print(f"Health monitoring failed: {e}")

    # Example: Run diagnostics
    print("\nRunning distributed processing diagnostics example...")

    try:
        result = distributed_diagnostics_flow(
            include_maintenance_recommendations=True
        )

        issues_count = len(result["system_diagnostics"].get("issues_found", []))
        next_steps = result["next_steps"]

        print(f"Diagnostics completed: {issues_count} issues found")
        print("Next steps:")
        for step in next_steps:
            print(f"  - {step}")

    except Exception as e:
        print(f"Diagnostics failed: {e}")

    # Example: Run maintenance (dry run)
    print("\nRunning distributed processing maintenance example (dry run)...")

    try:
        result = distributed_maintenance_flow(
            perform_cleanup=True,
            perform_failed_reset=False,
            dry_run=True
        )

        operations = result["maintenance_operations"].get("operations_performed", [])
        effectiveness = result["maintenance_summary"]["effectiveness_assessment"]

        print(f"Maintenance dry run completed: {len(operations)} operations")
        print(f"Effectiveness assessment: {effectiveness}")

    except Exception as e:
        print(f"Maintenance failed: {e}")
