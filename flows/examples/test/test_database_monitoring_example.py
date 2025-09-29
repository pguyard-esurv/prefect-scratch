"""
Tests for database monitoring example flows.

These tests verify that the example monitoring flows work correctly
with mocked database connections and provide expected functionality.
"""

import pytest
from prefect.logging import disable_run_logger

from flows.examples.database_monitoring_example import (
    database_diagnostics_flow,
    database_health_monitoring_flow,
    database_prerequisite_flow,
    operational_monitoring_flow,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def mock_monitoring_tasks(mocker):
    """Mock all the monitoring tasks used in the example flows."""

    # Mock multi_database_health_summary
    mock_health_summary = mocker.patch(
        "flows.examples.database_monitoring_example.multi_database_health_summary"
    )
    mock_health_summary.return_value = {
        "summary_timestamp": "2024-01-15T10:30:00Z",
        "overall_status": "healthy",
        "database_count": 2,
        "status_breakdown": {"healthy": 2, "degraded": 0, "unhealthy": 0},
    }

    # Mock database_health_check
    mock_health_check = mocker.patch(
        "flows.examples.database_monitoring_example.database_health_check"
    )
    mock_health_check.return_value = {
        "database_name": "test_db",
        "status": "healthy",
        "connection": True,
        "response_time_ms": 45.2,
    }

    # Mock connection_pool_monitoring
    mock_pool_monitoring = mocker.patch(
        "flows.examples.database_monitoring_example.connection_pool_monitoring"
    )
    mock_pool_monitoring.return_value = {
        "database_name": "test_db",
        "pool_health": "optimal",
        "utilization_percent": 25.0,
    }

    # Mock database_performance_monitoring
    mock_performance = mocker.patch(
        "flows.examples.database_monitoring_example.database_performance_monitoring"
    )
    mock_performance.return_value = {
        "database_name": "test_db",
        "overall_assessment": {"performance_rating": "excellent"},
    }

    # Mock database_prerequisite_validation
    mock_prerequisite = mocker.patch(
        "flows.examples.database_monitoring_example.database_prerequisite_validation"
    )
    mock_prerequisite.return_value = {
        "overall_status": "passed",
        "summary": {"total_databases": 2, "passed": 2, "failed": 0, "warnings": 0},
    }

    # Mock database_connectivity_diagnostics
    mock_diagnostics = mocker.patch(
        "flows.examples.database_monitoring_example.database_connectivity_diagnostics"
    )
    mock_diagnostics.return_value = {
        "database_name": "test_db",
        "diagnostic_timestamp": "2024-01-15T10:30:00Z",
        "recommendations": ["All systems operational"],
    }

    return {
        "health_summary": mock_health_summary,
        "health_check": mock_health_check,
        "pool_monitoring": mock_pool_monitoring,
        "performance": mock_performance,
        "prerequisite": mock_prerequisite,
        "diagnostics": mock_diagnostics,
    }


def test_database_health_monitoring_flow(mock_monitoring_tasks):
    """Test the database health monitoring flow."""

    with disable_run_logger():
        result = database_health_monitoring_flow(
            database_names=["test_db1", "test_db2"],
            include_performance_tests=True,
            performance_threshold_ms=1000.0,
        )

    # Verify flow structure
    assert "monitoring_timestamp" in result
    assert "overall_health" in result
    assert "individual_health_checks" in result
    assert "pool_monitoring" in result
    assert "performance_results" in result

    # Verify tasks were called
    mock_monitoring_tasks["health_summary"].assert_called_once_with(
        ["test_db1", "test_db2"]
    )
    assert mock_monitoring_tasks["health_check"].call_count == 2
    assert mock_monitoring_tasks["pool_monitoring"].call_count == 2
    assert mock_monitoring_tasks["performance"].call_count == 2


def test_database_health_monitoring_flow_no_performance(mock_monitoring_tasks):
    """Test the database health monitoring flow without performance tests."""

    with disable_run_logger():
        result = database_health_monitoring_flow(
            database_names=["test_db"], include_performance_tests=False
        )

    # Verify performance tests were skipped
    assert result["performance_results"] is None
    mock_monitoring_tasks["performance"].assert_not_called()


def test_database_prerequisite_flow_success(mock_monitoring_tasks):
    """Test database prerequisite validation flow with successful validation."""

    with disable_run_logger():
        result = database_prerequisite_flow(
            database_names=["test_db1", "test_db2"],
            check_migrations=True,
            performance_threshold_ms=1000.0,
            fail_on_validation_error=True,
        )

    # Verify result structure
    assert result["overall_status"] == "passed"
    assert result["summary"]["total_databases"] == 2

    # Verify task was called with correct parameters
    mock_monitoring_tasks["prerequisite"].assert_called_once_with(
        database_names=["test_db1", "test_db2"],
        check_migrations=True,
        performance_threshold_ms=1000.0,
    )


def test_database_prerequisite_flow_failure(mock_monitoring_tasks):
    """Test database prerequisite validation flow with validation failure."""

    # Mock failed validation
    mock_monitoring_tasks["prerequisite"].return_value = {
        "overall_status": "failed",
        "summary": {"total_databases": 1, "passed": 0, "failed": 1, "warnings": 0},
    }

    with disable_run_logger():
        # Should raise RuntimeError when fail_on_validation_error=True
        with pytest.raises(
            RuntimeError, match="Database prerequisite validation failed"
        ):
            database_prerequisite_flow(
                database_names=["test_db"], fail_on_validation_error=True
            )


def test_database_prerequisite_flow_no_fail_on_error(mock_monitoring_tasks):
    """Test database prerequisite validation flow without failing on error."""

    # Mock failed validation
    mock_monitoring_tasks["prerequisite"].return_value = {
        "overall_status": "failed",
        "summary": {"total_databases": 1, "passed": 0, "failed": 1, "warnings": 0},
    }

    with disable_run_logger():
        # Should not raise exception when fail_on_validation_error=False
        result = database_prerequisite_flow(
            database_names=["test_db"], fail_on_validation_error=False
        )

    assert result["overall_status"] == "failed"


def test_database_diagnostics_flow(mock_monitoring_tasks):
    """Test database diagnostics flow."""

    with disable_run_logger():
        result = database_diagnostics_flow("test_db")

    # Verify result structure
    assert result["database_name"] == "test_db"
    assert "diagnostic_timestamp" in result
    assert "health_check" in result
    assert "connectivity_diagnostics" in result
    assert "pool_analysis" in result
    assert "performance_analysis" in result
    assert "summary_recommendations" in result

    # Verify all diagnostic tasks were called
    mock_monitoring_tasks["health_check"].assert_called_once_with(
        "test_db", include_retry=False
    )
    mock_monitoring_tasks["diagnostics"].assert_called_once_with("test_db")
    mock_monitoring_tasks["pool_monitoring"].assert_called_once_with("test_db")
    mock_monitoring_tasks["performance"].assert_called_once()


def test_database_diagnostics_flow_with_issues(mock_monitoring_tasks):
    """Test database diagnostics flow with detected issues."""

    # Mock unhealthy database
    mock_monitoring_tasks["health_check"].return_value = {
        "database_name": "test_db",
        "status": "unhealthy",
        "connection": False,
    }

    # Mock poor performance
    mock_monitoring_tasks["performance"].return_value = {
        "database_name": "test_db",
        "overall_assessment": {"performance_rating": "poor"},
    }

    # Mock high pool utilization
    mock_monitoring_tasks["pool_monitoring"].return_value = {
        "database_name": "test_db",
        "pool_health": "high",
        "utilization_percent": 90.0,
    }

    with disable_run_logger():
        result = database_diagnostics_flow("test_db")

    # Verify recommendations include detected issues
    recommendations = result["summary_recommendations"]
    assert any("CRITICAL: Database is unhealthy" in rec for rec in recommendations)
    assert any("CRITICAL: Poor database performance" in rec for rec in recommendations)
    assert any(
        "Consider increasing connection pool size" in rec for rec in recommendations
    )


def test_operational_monitoring_flow(mock_monitoring_tasks):
    """Test operational monitoring flow."""

    with disable_run_logger():
        result = operational_monitoring_flow(
            database_names=["test_db1", "test_db2"],
            monitoring_interval_minutes=15,
            alert_thresholds={
                "response_time_ms": 2000.0,
                "pool_utilization_percent": 80.0,
                "connection_failure_threshold": 1,
            },
        )

    # Verify result structure
    assert "monitoring_timestamp" in result
    assert "databases" in result
    assert "alerts" in result
    assert "metrics_summary" in result

    # Verify metrics summary
    summary = result["metrics_summary"]
    assert summary["total_databases"] == 2
    assert summary["healthy_databases"] == 2
    assert summary["total_alerts"] == 0
    assert summary["overall_status"] == "healthy"


def test_operational_monitoring_flow_with_alerts(mock_monitoring_tasks):
    """Test operational monitoring flow with alerts generated."""

    # Mock high response time
    mock_monitoring_tasks["health_check"].return_value = {
        "database_name": "test_db",
        "status": "degraded",
        "connection": True,
        "response_time_ms": 3000.0,  # Exceeds threshold
    }

    # Mock high pool utilization
    mock_monitoring_tasks["pool_monitoring"].return_value = {
        "database_name": "test_db",
        "pool_health": "high",
        "utilization_percent": 85.0,  # Exceeds threshold
    }

    with disable_run_logger():
        result = operational_monitoring_flow(
            database_names=["test_db"],
            alert_thresholds={
                "response_time_ms": 2000.0,
                "pool_utilization_percent": 80.0,
                "connection_failure_threshold": 1,
            },
        )

    # Verify alerts were generated
    assert len(result["alerts"]) == 2  # Response time and pool utilization
    assert result["metrics_summary"]["total_alerts"] == 2
    assert result["metrics_summary"]["overall_status"] == "alert"

    # Check specific alerts
    alerts = result["alerts"]
    assert any("High response time" in alert for alert in alerts)
    assert any("High pool utilization" in alert for alert in alerts)


def test_operational_monitoring_flow_connection_failure(mock_monitoring_tasks):
    """Test operational monitoring flow with connection failure."""

    # Mock connection failure
    mock_monitoring_tasks["health_check"].return_value = {
        "database_name": "test_db",
        "status": "unhealthy",
        "connection": False,
        "error": "Connection refused",
    }

    with disable_run_logger():
        result = operational_monitoring_flow(database_names=["test_db"])

    # Verify connection failure alert
    assert len(result["alerts"]) == 1
    assert "Connection failure" in result["alerts"][0]
    assert "Connection refused" in result["alerts"][0]


def test_operational_monitoring_flow_with_exception(mock_monitoring_tasks):
    """Test operational monitoring flow when monitoring tasks raise exceptions."""

    # Mock task exception
    mock_monitoring_tasks["health_check"].side_effect = Exception("Database error")

    with disable_run_logger():
        result = operational_monitoring_flow(database_names=["test_db"])

    # Verify exception is handled gracefully
    assert len(result["alerts"]) == 1
    assert "Monitoring failed for test_db" in result["alerts"][0]
    assert "Database error" in result["alerts"][0]


def test_operational_monitoring_flow_default_databases(mock_monitoring_tasks):
    """Test operational monitoring flow with default database names."""

    with disable_run_logger():
        result = operational_monitoring_flow()  # No database_names provided

    # Should use default databases
    assert result["metrics_summary"]["total_databases"] == 2

    # Verify tasks were called for default databases
    mock_monitoring_tasks["health_summary"].assert_called_once_with(
        ["rpa_db", "SurveyHub"]
    )


def test_operational_monitoring_flow_custom_thresholds(mock_monitoring_tasks):
    """Test operational monitoring flow with custom alert thresholds."""

    custom_thresholds = {
        "response_time_ms": 500.0,  # Stricter threshold
        "pool_utilization_percent": 60.0,  # Stricter threshold
        "connection_failure_threshold": 0,  # No tolerance for failures
    }

    # Mock response time that exceeds custom threshold
    mock_monitoring_tasks["health_check"].return_value = {
        "database_name": "test_db",
        "status": "healthy",
        "connection": True,
        "response_time_ms": 750.0,  # Exceeds custom threshold
    }

    with disable_run_logger():
        result = operational_monitoring_flow(
            database_names=["test_db"], alert_thresholds=custom_thresholds
        )

    # Should generate alert with custom threshold
    assert len(result["alerts"]) == 1
    assert "High response time" in result["alerts"][0]
    assert "750.0ms" in result["alerts"][0]
