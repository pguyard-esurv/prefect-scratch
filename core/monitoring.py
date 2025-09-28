"""
Monitoring and operational utilities for distributed processing system.

This module provides comprehensive monitoring, diagnostic, and operational
utilities specifically designed for the distributed processing system.
It includes queue monitoring, performance tracking, diagnostic tools,
and operational maintenance utilities.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from prefect import get_run_logger, task

from core.database import DatabaseManager
from core.distributed import DistributedProcessor


def _get_logger():
    """Get logger with fallback for non-Prefect contexts."""
    try:
        return get_run_logger()
    except Exception:
        # Fallback to standard logging when not in Prefect context
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger


@task(name="distributed-queue-monitoring")
def distributed_queue_monitoring(
    flow_names: Optional[list[str]] = None,
    include_detailed_metrics: bool = True
) -> dict[str, Any]:
    """
    Monitor distributed processing queue status and metrics.

    Provides comprehensive visibility into processing queue status including
    record counts by status, flow-specific metrics, and operational insights
    for queue management and capacity planning.

    Args:
        flow_names: Optional list of specific flows to monitor (monitors all if None)
        include_detailed_metrics: Whether to include detailed per-flow metrics

    Returns:
        Dictionary containing comprehensive queue monitoring data

    Requirements: 6.2, 6.3, 6.5
    """
    logger = _get_logger()

    logger.info("Starting distributed processing queue monitoring")

    try:
        # Initialize distributed processor for queue monitoring
        rpa_db_manager = DatabaseManager("rpa_db")
        processor = DistributedProcessor(rpa_db_manager)

        monitoring_data = {
            "monitoring_timestamp": datetime.now().isoformat() + "Z",
            "processor_instance_id": processor.instance_id,
            "overall_queue_status": {},
            "flow_specific_metrics": {},
            "queue_health_assessment": {},
            "operational_alerts": [],
            "recommendations": []
        }

        # Get overall queue status
        overall_status = processor.get_queue_status()
        monitoring_data["overall_queue_status"] = overall_status

        # Get flow-specific metrics if requested
        if include_detailed_metrics and flow_names:
            for flow_name in flow_names:
                flow_status = processor.get_queue_status(flow_name)
                monitoring_data["flow_specific_metrics"][flow_name] = flow_status
        elif include_detailed_metrics:
            # Get metrics for all flows found in by_flow breakdown
            by_flow_data = overall_status.get("by_flow", {})
            for flow_name in by_flow_data.keys():
                flow_status = processor.get_queue_status(flow_name)
                monitoring_data["flow_specific_metrics"][flow_name] = flow_status

        # Assess queue health and generate alerts
        queue_assessment = _assess_queue_health(overall_status, monitoring_data["flow_specific_metrics"])
        monitoring_data["queue_health_assessment"] = queue_assessment

        # Generate operational alerts
        alerts = _generate_queue_alerts(overall_status, monitoring_data["flow_specific_metrics"])
        monitoring_data["operational_alerts"] = alerts

        # Generate recommendations
        recommendations = _generate_queue_recommendations(overall_status, queue_assessment)
        monitoring_data["recommendations"] = recommendations

        # Log summary
        total_records = overall_status.get("total_records", 0)
        pending_records = overall_status.get("pending_records", 0)
        processing_records = overall_status.get("processing_records", 0)
        failed_records = overall_status.get("failed_records", 0)

        logger.info(
            f"Queue monitoring complete: {total_records} total records "
            f"({pending_records} pending, {processing_records} processing, {failed_records} failed)"
        )

        if alerts:
            logger.warning(f"Generated {len(alerts)} operational alerts")

        return monitoring_data

    except Exception as e:
        error_msg = f"Distributed queue monitoring failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


@task(name="distributed-processing-diagnostics")
def distributed_processing_diagnostics(
    flow_name: Optional[str] = None,
    include_orphaned_analysis: bool = True,
    include_performance_analysis: bool = True
) -> dict[str, Any]:
    """
    Perform comprehensive diagnostics for distributed processing issues.

    Provides detailed diagnostic information to help troubleshoot processing
    issues including orphaned records, performance bottlenecks, and system
    health problems specific to distributed processing.

    Args:
        flow_name: Optional specific flow to diagnose (diagnoses all if None)
        include_orphaned_analysis: Whether to analyze orphaned records
        include_performance_analysis: Whether to include performance diagnostics

    Returns:
        Dictionary containing comprehensive diagnostic information

    Requirements: 6.1, 6.3, 6.4, 6.5
    """
    logger = _get_logger()

    logger.info(f"Starting distributed processing diagnostics for flow: {flow_name or 'all flows'}")

    try:
        # Initialize components
        rpa_db_manager = DatabaseManager("rpa_db")
        processor = DistributedProcessor(rpa_db_manager)

        diagnostics = {
            "diagnostic_timestamp": datetime.now().isoformat() + "Z",
            "processor_instance_id": processor.instance_id,
            "target_flow": flow_name,
            "system_health": {},
            "queue_diagnostics": {},
            "orphaned_records_analysis": {},
            "performance_analysis": {},
            "database_diagnostics": {},
            "issues_found": [],
            "recommendations": []
        }

        # System health check
        logger.info("Performing system health diagnostics")
        health_status = processor.health_check()
        diagnostics["system_health"] = health_status

        if health_status["status"] != "healthy":
            diagnostics["issues_found"].append(
                f"System health is {health_status['status']}: {health_status.get('error', 'Unknown issue')}"
            )

        # Queue diagnostics
        logger.info("Analyzing queue status and metrics")
        queue_status = processor.get_queue_status(flow_name)
        diagnostics["queue_diagnostics"] = queue_status

        # Orphaned records analysis
        if include_orphaned_analysis:
            logger.info("Analyzing orphaned records")
            orphaned_analysis = _analyze_orphaned_records(processor, flow_name)
            diagnostics["orphaned_records_analysis"] = orphaned_analysis

            if orphaned_analysis.get("total_orphaned_records", 0) > 0:
                diagnostics["issues_found"].append(
                    f"Found {orphaned_analysis['total_orphaned_records']} orphaned records"
                )

        # Performance analysis
        if include_performance_analysis:
            logger.info("Performing performance analysis")
            performance_analysis = _analyze_processing_performance(processor, flow_name)
            diagnostics["performance_analysis"] = performance_analysis

            # Check for performance issues
            if performance_analysis.get("avg_processing_time_minutes", 0) > 60:
                diagnostics["issues_found"].append(
                    "High average processing time detected (>60 minutes)"
                )

        # Database-specific diagnostics
        logger.info("Running database diagnostics")
        db_diagnostics = rpa_db_manager.health_check()
        diagnostics["database_diagnostics"] = db_diagnostics

        # Generate recommendations based on findings
        recommendations = _generate_diagnostic_recommendations(diagnostics)
        diagnostics["recommendations"] = recommendations

        # Log diagnostic summary
        issues_count = len(diagnostics["issues_found"])
        if issues_count > 0:
            logger.warning(f"Diagnostics found {issues_count} issues requiring attention")
            for issue in diagnostics["issues_found"]:
                logger.warning(f"  - {issue}")
        else:
            logger.info("Diagnostics completed - no critical issues found")

        return diagnostics

    except Exception as e:
        error_msg = f"Distributed processing diagnostics failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


@task(name="processing-performance-monitoring")
def processing_performance_monitoring(
    flow_names: Optional[list[str]] = None,
    time_window_hours: int = 24,
    include_error_analysis: bool = True
) -> dict[str, Any]:
    """
    Monitor processing performance and error rates for distributed flows.

    Tracks processing rates, success rates, error patterns, and performance
    trends over time to provide insights into system efficiency and identify
    potential bottlenecks or issues.

    Args:
        flow_names: Optional list of flows to monitor (monitors all if None)
        time_window_hours: Time window for performance analysis in hours
        include_error_analysis: Whether to include detailed error analysis

    Returns:
        Dictionary containing performance metrics and analysis

    Requirements: 6.2, 6.3, 6.5
    """
    logger = _get_logger()

    logger.info(f"Starting processing performance monitoring (window: {time_window_hours}h)")

    try:
        # Initialize components
        rpa_db_manager = DatabaseManager("rpa_db")
        processor = DistributedProcessor(rpa_db_manager)

        performance_data = {
            "monitoring_timestamp": datetime.now().isoformat() + "Z",
            "time_window_hours": time_window_hours,
            "processor_instance_id": processor.instance_id,
            "overall_metrics": {},
            "flow_specific_metrics": {},
            "error_analysis": {},
            "performance_trends": {},
            "alerts": [],
            "recommendations": []
        }

        # Calculate time window
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_window_hours)

        # Get overall performance metrics
        logger.info("Calculating overall performance metrics")
        overall_metrics = _calculate_performance_metrics(processor, None, start_time, end_time)
        performance_data["overall_metrics"] = overall_metrics

        # Get flow-specific metrics
        if flow_names:
            target_flows = flow_names
        else:
            # Get all flows from queue status
            queue_status = processor.get_queue_status()
            target_flows = list(queue_status.get("by_flow", {}).keys())

        logger.info(f"Analyzing performance for {len(target_flows)} flows")
        for flow_name in target_flows:
            flow_metrics = _calculate_performance_metrics(processor, flow_name, start_time, end_time)
            performance_data["flow_specific_metrics"][flow_name] = flow_metrics

        # Error analysis
        if include_error_analysis:
            logger.info("Performing error analysis")
            error_analysis = _analyze_processing_errors(processor, target_flows, start_time, end_time)
            performance_data["error_analysis"] = error_analysis

        # Performance trend analysis
        logger.info("Analyzing performance trends")
        trend_analysis = _analyze_performance_trends(processor, target_flows, start_time, end_time)
        performance_data["performance_trends"] = trend_analysis

        # Generate performance alerts
        alerts = _generate_performance_alerts(overall_metrics, performance_data["flow_specific_metrics"])
        performance_data["alerts"] = alerts

        # Generate recommendations
        recommendations = _generate_performance_recommendations(
            overall_metrics, performance_data["flow_specific_metrics"], error_analysis
        )
        performance_data["recommendations"] = recommendations

        # Log performance summary
        total_processed = overall_metrics.get("total_processed", 0)
        success_rate = overall_metrics.get("success_rate_percent", 0)
        avg_processing_rate = overall_metrics.get("avg_processing_rate_per_hour", 0)

        logger.info(
            f"Performance monitoring complete: {total_processed} records processed, "
            f"{success_rate:.1f}% success rate, {avg_processing_rate:.1f} records/hour"
        )

        if alerts:
            logger.warning(f"Generated {len(alerts)} performance alerts")

        return performance_data

    except Exception as e:
        error_msg = f"Processing performance monitoring failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


@task(name="distributed-system-maintenance")
def distributed_system_maintenance(
    cleanup_orphaned_records: bool = True,
    reset_failed_records: bool = False,
    orphaned_timeout_hours: int = 2,
    max_retries: int = 3,
    dry_run: bool = False
) -> dict[str, Any]:
    """
    Perform maintenance operations on the distributed processing system.

    Executes routine maintenance tasks including orphaned record cleanup,
    failed record reset, and system optimization to keep the distributed
    processing system running efficiently.

    Args:
        cleanup_orphaned_records: Whether to clean up orphaned records
        reset_failed_records: Whether to reset failed records for retry
        orphaned_timeout_hours: Hours after which records are considered orphaned
        max_retries: Maximum retry count for failed record reset
        dry_run: If True, only report what would be done without making changes

    Returns:
        Dictionary containing maintenance operation results

    Requirements: 6.1, 6.2, 6.3, 6.4
    """
    logger = _get_logger()

    logger.info(f"Starting distributed system maintenance (dry_run: {dry_run})")

    try:
        # Initialize components
        rpa_db_manager = DatabaseManager("rpa_db")
        processor = DistributedProcessor(rpa_db_manager)

        maintenance_results = {
            "maintenance_timestamp": datetime.now().isoformat() + "Z",
            "processor_instance_id": processor.instance_id,
            "dry_run": dry_run,
            "operations_performed": [],
            "cleanup_results": {},
            "reset_results": {},
            "before_status": {},
            "after_status": {},
            "recommendations": []
        }

        # Get initial queue status
        logger.info("Getting initial queue status")
        initial_status = processor.get_queue_status()
        maintenance_results["before_status"] = initial_status

        # Orphaned records cleanup
        if cleanup_orphaned_records:
            logger.info(f"Cleaning up orphaned records (timeout: {orphaned_timeout_hours}h)")

            if dry_run:
                # Simulate cleanup by counting orphaned records
                orphaned_count = _count_orphaned_records(processor, orphaned_timeout_hours)
                maintenance_results["cleanup_results"] = {
                    "operation": "cleanup_orphaned_records",
                    "dry_run": True,
                    "orphaned_records_found": orphaned_count,
                    "records_cleaned": 0,
                    "message": f"Would clean up {orphaned_count} orphaned records"
                }
            else:
                cleaned_count = processor.cleanup_orphaned_records(orphaned_timeout_hours)
                maintenance_results["cleanup_results"] = {
                    "operation": "cleanup_orphaned_records",
                    "dry_run": False,
                    "records_cleaned": cleaned_count,
                    "timeout_hours": orphaned_timeout_hours
                }

            maintenance_results["operations_performed"].append("cleanup_orphaned_records")

        # Failed records reset
        if reset_failed_records:
            logger.info(f"Resetting failed records (max_retries: {max_retries})")

            # Get all flows with failed records
            queue_status = processor.get_queue_status()
            flows_with_failures = []

            for flow_name, flow_data in queue_status.get("by_flow", {}).items():
                if flow_data.get("failed", 0) > 0:
                    flows_with_failures.append(flow_name)

            reset_results = {}
            total_reset = 0

            for flow_name in flows_with_failures:
                if dry_run:
                    # Count failed records that would be reset
                    failed_count = _count_resettable_failed_records(processor, flow_name, max_retries)
                    reset_results[flow_name] = {
                        "dry_run": True,
                        "failed_records_found": failed_count,
                        "records_reset": 0,
                        "message": f"Would reset {failed_count} failed records"
                    }
                else:
                    reset_count = processor.reset_failed_records(flow_name, max_retries)
                    reset_results[flow_name] = {
                        "dry_run": False,
                        "records_reset": reset_count,
                        "max_retries": max_retries
                    }
                    total_reset += reset_count

            maintenance_results["reset_results"] = {
                "operation": "reset_failed_records",
                "flows_processed": flows_with_failures,
                "flow_results": reset_results,
                "total_records_reset": total_reset
            }

            maintenance_results["operations_performed"].append("reset_failed_records")

        # Get final queue status
        logger.info("Getting final queue status")
        final_status = processor.get_queue_status()
        maintenance_results["after_status"] = final_status

        # Generate maintenance recommendations
        recommendations = _generate_maintenance_recommendations(
            initial_status, final_status, maintenance_results
        )
        maintenance_results["recommendations"] = recommendations

        # Log maintenance summary
        operations_count = len(maintenance_results["operations_performed"])
        if dry_run:
            logger.info(f"Maintenance dry run completed: {operations_count} operations simulated")
        else:
            logger.info(f"Maintenance completed: {operations_count} operations performed")

            if cleanup_orphaned_records:
                cleaned = maintenance_results["cleanup_results"].get("records_cleaned", 0)
                logger.info(f"  - Cleaned up {cleaned} orphaned records")

            if reset_failed_records:
                reset_total = maintenance_results["reset_results"].get("total_records_reset", 0)
                logger.info(f"  - Reset {reset_total} failed records for retry")

        return maintenance_results

    except Exception as e:
        error_msg = f"Distributed system maintenance failed: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


# Helper functions for monitoring and diagnostics

def _assess_queue_health(overall_status: dict[str, Any], flow_metrics: dict[str, Any]) -> dict[str, Any]:
    """Assess overall queue health based on metrics."""
    total_records = overall_status.get("total_records", 0)
    overall_status.get("pending_records", 0)
    processing_records = overall_status.get("processing_records", 0)
    failed_records = overall_status.get("failed_records", 0)

    # Calculate health indicators
    if total_records == 0:
        queue_health = "idle"
        health_score = 100
    else:
        failed_rate = (failed_records / total_records) * 100
        processing_rate = (processing_records / total_records) * 100

        if failed_rate > 20:
            queue_health = "critical"
            health_score = 25
        elif failed_rate > 10:
            queue_health = "degraded"
            health_score = 50
        elif processing_rate > 80:
            queue_health = "overloaded"
            health_score = 60
        else:
            queue_health = "healthy"
            health_score = 90

    return {
        "queue_health": queue_health,
        "health_score": health_score,
        "total_records": total_records,
        "failed_rate_percent": (failed_records / total_records * 100) if total_records > 0 else 0,
        "processing_rate_percent": (processing_records / total_records * 100) if total_records > 0 else 0,
        "assessment_timestamp": datetime.now().isoformat() + "Z"
    }


def _generate_queue_alerts(overall_status: dict[str, Any], flow_metrics: dict[str, Any]) -> list[str]:
    """Generate operational alerts based on queue status."""
    alerts = []

    total_records = overall_status.get("total_records", 0)
    pending_records = overall_status.get("pending_records", 0)
    processing_records = overall_status.get("processing_records", 0)
    failed_records = overall_status.get("failed_records", 0)

    # High failure rate alert
    if total_records > 0:
        failed_rate = (failed_records / total_records) * 100
        if failed_rate > 20:
            alerts.append(f"CRITICAL: High failure rate ({failed_rate:.1f}%) - {failed_records} failed records")
        elif failed_rate > 10:
            alerts.append(f"WARNING: Elevated failure rate ({failed_rate:.1f}%) - {failed_records} failed records")

    # High processing backlog alert
    if pending_records > 1000:
        alerts.append(f"WARNING: Large processing backlog - {pending_records} pending records")

    # Stuck processing records alert
    if processing_records > 100:
        alerts.append(f"WARNING: Many records in processing state - {processing_records} records (check for orphaned records)")

    # Flow-specific alerts
    for flow_name, flow_data in flow_metrics.items():
        flow_failed = flow_data.get("failed_records", 0)
        flow_total = flow_data.get("total_records", 0)

        if flow_total > 0 and flow_failed > 0:
            flow_failed_rate = (flow_failed / flow_total) * 100
            if flow_failed_rate > 50:
                alerts.append(f"CRITICAL: Flow '{flow_name}' has high failure rate ({flow_failed_rate:.1f}%)")

    return alerts


def _generate_queue_recommendations(overall_status: dict[str, Any], queue_assessment: dict[str, Any]) -> list[str]:
    """Generate operational recommendations based on queue analysis."""
    recommendations = []

    queue_health = queue_assessment.get("queue_health", "unknown")
    queue_assessment.get("failed_rate_percent", 0)
    queue_assessment.get("processing_rate_percent", 0)

    if queue_health == "critical":
        recommendations.append("URGENT: Investigate high failure rates and resolve underlying issues")
        recommendations.append("Consider pausing new record ingestion until issues are resolved")

    elif queue_health == "degraded":
        recommendations.append("Investigate causes of record failures and implement fixes")
        recommendations.append("Monitor error patterns and consider adjusting retry logic")

    elif queue_health == "overloaded":
        recommendations.append("Consider scaling up processing capacity (more containers)")
        recommendations.append("Review batch sizes and processing efficiency")

    if overall_status.get("processing_records", 0) > 50:
        recommendations.append("Check for orphaned records and run cleanup maintenance")

    if overall_status.get("pending_records", 0) > 500:
        recommendations.append("Consider increasing processing capacity to handle backlog")

    if not recommendations:
        recommendations.append("Queue is operating normally - continue monitoring")

    return recommendations


def _analyze_orphaned_records(processor: DistributedProcessor, flow_name: Optional[str]) -> dict[str, Any]:
    """Analyze orphaned records in the processing queue."""
    try:
        # Query for potentially orphaned records (processing for > 1 hour)
        query = """
        SELECT
            flow_name,
            COUNT(*) as orphaned_count,
            MIN(claimed_at) as oldest_claim,
            MAX(claimed_at) as newest_claim,
            AVG(EXTRACT(EPOCH FROM (NOW() - claimed_at))/3600) as avg_hours_stuck
        FROM processing_queue
        WHERE status = 'processing'
        AND claimed_at < NOW() - INTERVAL '1 hour'
        """

        if flow_name:
            query += " AND flow_name = :flow_name"
            params = {"flow_name": flow_name}
        else:
            params = {}

        query += " GROUP BY flow_name ORDER BY orphaned_count DESC"

        results = processor.rpa_db.execute_query(query, params)

        total_orphaned = sum(row["orphaned_count"] for row in results)

        return {
            "analysis_timestamp": datetime.now().isoformat() + "Z",
            "total_orphaned_records": total_orphaned,
            "orphaned_by_flow": results,
            "oldest_orphaned_hours": max(row["avg_hours_stuck"] for row in results) if results else 0
        }

    except Exception as e:
        return {
            "analysis_timestamp": datetime.now().isoformat() + "Z",
            "error": f"Failed to analyze orphaned records: {e}",
            "total_orphaned_records": 0
        }


def _analyze_processing_performance(processor: DistributedProcessor, flow_name: Optional[str]) -> dict[str, Any]:
    """Analyze processing performance metrics."""
    try:
        # Query for processing performance over last 24 hours
        query = """
        SELECT
            flow_name,
            COUNT(*) as total_processed,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
            AVG(EXTRACT(EPOCH FROM (completed_at - claimed_at))/60) as avg_processing_minutes,
            MIN(completed_at) as first_completion,
            MAX(completed_at) as last_completion
        FROM processing_queue
        WHERE (status = 'completed' OR status = 'failed')
        AND completed_at >= NOW() - INTERVAL '24 hours'
        """

        if flow_name:
            query += " AND flow_name = :flow_name"
            params = {"flow_name": flow_name}
        else:
            params = {}

        query += " GROUP BY flow_name ORDER BY total_processed DESC"

        results = processor.rpa_db.execute_query(query, params)

        if results:
            total_processed = sum(row["total_processed"] for row in results)
            total_completed = sum(row["completed_count"] for row in results)
            avg_processing_time = sum(row["avg_processing_minutes"] or 0 for row in results) / len(results)
        else:
            total_processed = 0
            total_completed = 0
            avg_processing_time = 0

        return {
            "analysis_timestamp": datetime.now().isoformat() + "Z",
            "time_window_hours": 24,
            "total_processed": total_processed,
            "total_completed": total_completed,
            "success_rate_percent": (total_completed / total_processed * 100) if total_processed > 0 else 0,
            "avg_processing_time_minutes": round(avg_processing_time, 2),
            "performance_by_flow": results
        }

    except Exception as e:
        return {
            "analysis_timestamp": datetime.now().isoformat() + "Z",
            "error": f"Failed to analyze processing performance: {e}",
            "total_processed": 0
        }


def _calculate_performance_metrics(
    processor: DistributedProcessor,
    flow_name: Optional[str],
    start_time: datetime,
    end_time: datetime
) -> dict[str, Any]:
    """Calculate detailed performance metrics for a time window."""
    try:
        # Base query for performance metrics
        query = """
        SELECT
            COUNT(*) as total_processed,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
            COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_count,
            AVG(EXTRACT(EPOCH FROM (COALESCE(completed_at, updated_at) - claimed_at))/60) as avg_processing_minutes,
            MIN(claimed_at) as first_claim,
            MAX(COALESCE(completed_at, updated_at)) as last_update
        FROM processing_queue
        WHERE claimed_at >= :start_time AND claimed_at <= :end_time
        """

        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }

        if flow_name:
            query += " AND flow_name = :flow_name"
            params["flow_name"] = flow_name

        results = processor.rpa_db.execute_query(query, params)

        if results and results[0]["total_processed"]:
            result = results[0]
            total_processed = result["total_processed"]
            completed_count = result["completed_count"]
            failed_count = result["failed_count"]
            avg_processing_minutes = result["avg_processing_minutes"] or 0

            # Calculate processing rate per hour
            time_window_hours = (end_time - start_time).total_seconds() / 3600
            processing_rate_per_hour = total_processed / time_window_hours if time_window_hours > 0 else 0

            return {
                "flow_name": flow_name,
                "time_window": {
                    "start_time": start_time.isoformat() + "Z",
                    "end_time": end_time.isoformat() + "Z",
                    "duration_hours": round(time_window_hours, 2)
                },
                "total_processed": total_processed,
                "completed_count": completed_count,
                "failed_count": failed_count,
                "success_rate_percent": round((completed_count / total_processed * 100), 2),
                "avg_processing_time_minutes": round(avg_processing_minutes, 2),
                "avg_processing_rate_per_hour": round(processing_rate_per_hour, 2)
            }
        else:
            return {
                "flow_name": flow_name,
                "time_window": {
                    "start_time": start_time.isoformat() + "Z",
                    "end_time": end_time.isoformat() + "Z",
                    "duration_hours": round((end_time - start_time).total_seconds() / 3600, 2)
                },
                "total_processed": 0,
                "completed_count": 0,
                "failed_count": 0,
                "success_rate_percent": 0,
                "avg_processing_time_minutes": 0,
                "avg_processing_rate_per_hour": 0
            }

    except Exception as e:
        return {
            "flow_name": flow_name,
            "error": f"Failed to calculate performance metrics: {e}",
            "total_processed": 0
        }


def _analyze_processing_errors(
    processor: DistributedProcessor,
    flow_names: list[str],
    start_time: datetime,
    end_time: datetime
) -> dict[str, Any]:
    """Analyze error patterns in processing."""
    try:
        # Query for error analysis
        query = """
        SELECT
            flow_name,
            error_message,
            COUNT(*) as error_count,
            MIN(updated_at) as first_occurrence,
            MAX(updated_at) as last_occurrence
        FROM processing_queue
        WHERE status = 'failed'
        AND updated_at >= :start_time AND updated_at <= :end_time
        AND error_message IS NOT NULL
        """

        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }

        if flow_names:
            placeholders = ", ".join(f":flow_{i}" for i in range(len(flow_names)))
            query += f" AND flow_name IN ({placeholders})"
            for i, flow_name in enumerate(flow_names):
                params[f"flow_{i}"] = flow_name

        query += " GROUP BY flow_name, error_message ORDER BY error_count DESC LIMIT 20"

        results = processor.rpa_db.execute_query(query, params)

        # Group errors by flow
        errors_by_flow = {}
        total_errors = 0

        for row in results:
            flow_name = row["flow_name"]
            if flow_name not in errors_by_flow:
                errors_by_flow[flow_name] = []

            errors_by_flow[flow_name].append({
                "error_message": row["error_message"],
                "error_count": row["error_count"],
                "first_occurrence": row["first_occurrence"],
                "last_occurrence": row["last_occurrence"]
            })
            total_errors += row["error_count"]

        return {
            "analysis_timestamp": datetime.now().isoformat() + "Z",
            "time_window": {
                "start_time": start_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z"
            },
            "total_errors": total_errors,
            "unique_error_types": len(results),
            "errors_by_flow": errors_by_flow,
            "top_errors": results[:10]  # Top 10 most frequent errors
        }

    except Exception as e:
        return {
            "analysis_timestamp": datetime.now().isoformat() + "Z",
            "error": f"Failed to analyze processing errors: {e}",
            "total_errors": 0
        }


def _analyze_performance_trends(
    processor: DistributedProcessor,
    flow_names: list[str],
    start_time: datetime,
    end_time: datetime
) -> dict[str, Any]:
    """Analyze performance trends over time."""
    try:
        # Query for hourly performance trends
        query = """
        SELECT
            DATE_TRUNC('hour', claimed_at) as hour,
            flow_name,
            COUNT(*) as records_processed,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
            AVG(EXTRACT(EPOCH FROM (COALESCE(completed_at, updated_at) - claimed_at))/60) as avg_processing_minutes
        FROM processing_queue
        WHERE claimed_at >= :start_time AND claimed_at <= :end_time
        """

        params = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }

        if flow_names:
            placeholders = ", ".join(f":flow_{i}" for i in range(len(flow_names)))
            query += f" AND flow_name IN ({placeholders})"
            for i, flow_name in enumerate(flow_names):
                params[f"flow_{i}"] = flow_name

        query += " GROUP BY DATE_TRUNC('hour', claimed_at), flow_name ORDER BY hour DESC"

        results = processor.rpa_db.execute_query(query, params)

        # Calculate trend metrics
        hourly_totals = {}
        for row in results:
            hour = row["hour"].isoformat() if row["hour"] else "unknown"
            if hour not in hourly_totals:
                hourly_totals[hour] = {
                    "total_processed": 0,
                    "total_completed": 0,
                    "avg_processing_time": 0,
                    "flows": {}
                }

            hourly_totals[hour]["total_processed"] += row["records_processed"]
            hourly_totals[hour]["total_completed"] += row["completed_count"]
            hourly_totals[hour]["flows"][row["flow_name"]] = {
                "processed": row["records_processed"],
                "completed": row["completed_count"],
                "avg_processing_minutes": row["avg_processing_minutes"]
            }

        return {
            "analysis_timestamp": datetime.now().isoformat() + "Z",
            "time_window": {
                "start_time": start_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z"
            },
            "hourly_trends": hourly_totals,
            "trend_summary": {
                "total_hours_analyzed": len(hourly_totals),
                "peak_hour_processing": max(
                    (hour_data["total_processed"] for hour_data in hourly_totals.values()),
                    default=0
                )
            }
        }

    except Exception as e:
        return {
            "analysis_timestamp": datetime.now().isoformat() + "Z",
            "error": f"Failed to analyze performance trends: {e}",
            "hourly_trends": {}
        }


def _generate_performance_alerts(overall_metrics: dict[str, Any], flow_metrics: dict[str, Any]) -> list[str]:
    """Generate performance-based alerts."""
    alerts = []

    # Overall performance alerts
    overall_success_rate = overall_metrics.get("success_rate_percent", 100)
    if overall_success_rate < 80:
        alerts.append(f"CRITICAL: Low overall success rate ({overall_success_rate:.1f}%)")
    elif overall_success_rate < 90:
        alerts.append(f"WARNING: Reduced overall success rate ({overall_success_rate:.1f}%)")

    overall_processing_rate = overall_metrics.get("avg_processing_rate_per_hour", 0)
    if overall_processing_rate < 10:
        alerts.append(f"WARNING: Low processing rate ({overall_processing_rate:.1f} records/hour)")

    # Flow-specific alerts
    for flow_name, metrics in flow_metrics.items():
        flow_success_rate = metrics.get("success_rate_percent", 100)
        if flow_success_rate < 70:
            alerts.append(f"CRITICAL: Flow '{flow_name}' has very low success rate ({flow_success_rate:.1f}%)")

        flow_processing_time = metrics.get("avg_processing_time_minutes", 0)
        if flow_processing_time > 30:
            alerts.append(f"WARNING: Flow '{flow_name}' has high processing time ({flow_processing_time:.1f} minutes)")

    return alerts


def _generate_performance_recommendations(
    overall_metrics: dict[str, Any],
    flow_metrics: dict[str, Any],
    error_analysis: dict[str, Any]
) -> list[str]:
    """Generate performance improvement recommendations."""
    recommendations = []

    # Overall performance recommendations
    overall_success_rate = overall_metrics.get("success_rate_percent", 100)
    if overall_success_rate < 90:
        recommendations.append("Investigate and resolve causes of processing failures")

    overall_processing_rate = overall_metrics.get("avg_processing_rate_per_hour", 0)
    if overall_processing_rate < 50:
        recommendations.append("Consider optimizing processing logic or increasing container capacity")

    # Error pattern recommendations
    total_errors = error_analysis.get("total_errors", 0)
    if total_errors > 100:
        recommendations.append("High error volume detected - review error patterns and implement fixes")

    # Flow-specific recommendations
    slow_flows = []
    failing_flows = []

    for flow_name, metrics in flow_metrics.items():
        if metrics.get("avg_processing_time_minutes", 0) > 15:
            slow_flows.append(flow_name)
        if metrics.get("success_rate_percent", 100) < 80:
            failing_flows.append(flow_name)

    if slow_flows:
        recommendations.append(f"Optimize processing logic for slow flows: {', '.join(slow_flows)}")

    if failing_flows:
        recommendations.append(f"Investigate failure causes for flows: {', '.join(failing_flows)}")

    if not recommendations:
        recommendations.append("Performance is within acceptable ranges - continue monitoring")

    return recommendations


def _generate_diagnostic_recommendations(diagnostics: dict[str, Any]) -> list[str]:
    """Generate recommendations based on diagnostic findings."""
    recommendations = []

    # System health recommendations
    system_health = diagnostics.get("system_health", {})
    if system_health.get("status") == "unhealthy":
        recommendations.append("URGENT: Resolve database connectivity issues before processing")
    elif system_health.get("status") == "degraded":
        recommendations.append("Address database performance issues to improve processing efficiency")

    # Orphaned records recommendations
    orphaned_analysis = diagnostics.get("orphaned_records_analysis", {})
    orphaned_count = orphaned_analysis.get("orphaned_count", 0)
    if orphaned_count > 10:
        recommendations.append(f"Run maintenance to clean up {orphaned_count} orphaned records")

    # Performance recommendations
    performance_analysis = diagnostics.get("performance_analysis", {})
    avg_processing_time = performance_analysis.get("avg_processing_time_minutes", 0)
    if avg_processing_time > 30:
        recommendations.append("Investigate causes of high processing times and optimize business logic")

    # Queue health recommendations
    queue_diagnostics = diagnostics.get("queue_diagnostics", {})
    failed_records = queue_diagnostics.get("failed_records", 0)
    if failed_records > 50:
        recommendations.append("High number of failed records - investigate error patterns and implement fixes")

    if not recommendations:
        recommendations.append("System diagnostics show normal operation - continue monitoring")

    return recommendations


def _count_orphaned_records(processor: DistributedProcessor, timeout_hours: int) -> int:
    """Count orphaned records without cleaning them up."""
    try:
        query = """
        SELECT COUNT(*) as count
        FROM processing_queue
        WHERE status = 'processing'
        AND claimed_at < NOW() - INTERVAL ':timeout_hours hours'
        """

        results = processor.rpa_db.execute_query(query, {"timeout_hours": timeout_hours})
        return results[0]["count"] if results else 0

    except Exception:
        return 0


def _count_resettable_failed_records(processor: DistributedProcessor, flow_name: str, max_retries: int) -> int:
    """Count failed records that would be reset."""
    try:
        query = """
        SELECT COUNT(*) as count
        FROM processing_queue
        WHERE flow_name = :flow_name
        AND status = 'failed'
        AND retry_count < :max_retries
        """

        results = processor.rpa_db.execute_query(query, {
            "flow_name": flow_name,
            "max_retries": max_retries
        })
        return results[0]["count"] if results else 0

    except Exception:
        return 0


def _generate_maintenance_recommendations(
    before_status: dict[str, Any],
    after_status: dict[str, Any],
    maintenance_results: dict[str, Any]
) -> list[str]:
    """Generate recommendations based on maintenance results."""
    recommendations = []

    # Check if maintenance was effective
    before_failed = before_status.get("failed_records", 0)
    after_failed = after_status.get("failed_records", 0)
    before_processing = before_status.get("processing_records", 0)
    after_processing = after_status.get("processing_records", 0)

    if before_failed > after_failed:
        reduction = before_failed - after_failed
        recommendations.append(f"Successfully reduced failed records by {reduction}")

    if before_processing > after_processing:
        reduction = before_processing - after_processing
        recommendations.append(f"Successfully reduced stuck processing records by {reduction}")

    # Ongoing maintenance recommendations
    if after_failed > 100:
        recommendations.append("Consider investigating root causes of persistent failures")

    if after_processing > 50:
        recommendations.append("Monitor for new orphaned records and schedule regular cleanup")

    # Schedule recommendations
    cleanup_results = maintenance_results.get("cleanup_results", {})
    if cleanup_results.get("records_cleaned", 0) > 0:
        recommendations.append("Schedule regular orphaned record cleanup (every 2-4 hours)")

    reset_results = maintenance_results.get("reset_results", {})
    if reset_results.get("total_records_reset", 0) > 0:
        recommendations.append("Monitor reset records for recurring failures")

    if not recommendations:
        recommendations.append("Maintenance completed successfully - system is operating normally")

    return recommendations
