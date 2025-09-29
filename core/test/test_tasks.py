"""Unit tests for Prefect task functions.

These tests use Prefect's recommended testing approach with prefect_test_harness
and disable_run_logger for proper test isolation and cleaner test code.
"""

import json
import tempfile
from pathlib import Path

import pytest
from prefect.logging import disable_run_logger

from core.tasks import (
    calculate_summary,
    connection_pool_monitoring,
    create_directory,
    database_connectivity_diagnostics,
    database_health_check,
    database_performance_monitoring,
    database_prerequisite_validation,
    extract_data,
    generate_report,
    multi_database_health_summary,
    transform_data,
    validate_file_exists,
)

pytestmark = pytest.mark.unit


def test_extract_data():
    """Test extract_data task with real CSV data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("product,quantity,price,date\n")
        f.write("Widget A,100,10.50,2024-01-15\n")
        f.write("Widget B,75,15.75,2024-01-16\n")
        f.close()

        # Use Prefect's recommended approach for testing tasks
        with disable_run_logger():
            result = extract_data.fn(f.name)

            assert len(result) == 2
            assert result[0]["product"] == "Widget A"
            assert result[0]["quantity"] == 100
            assert result[0]["price"] == 10.50
            assert result[1]["product"] == "Widget B"
            assert result[1]["quantity"] == 75
            assert result[1]["price"] == 15.75


def test_transform_data():
    """Test transform_data task with real data transformation."""
    test_data = [
        {"product": "Widget A", "quantity": 100, "price": 10.50, "date": "2024-01-15"},
        {"product": "Widget B", "quantity": 75, "price": 15.75, "date": "2024-01-16"},
    ]

    # Use Prefect's recommended approach for testing tasks
    with disable_run_logger():
        result = transform_data.fn(test_data)

        assert len(result) == 2
        assert result[0]["total_value"] == 1050.0  # 100 * 10.50
        assert result[1]["total_value"] == 1181.25  # 75 * 15.75
        assert "processed_at" in result[0]
        assert "processed_at" in result[1]


def test_calculate_summary():
    """Test calculate_summary task with real summary calculations."""
    test_data = [
        {"product": "Widget A", "quantity": 100, "price": 10.50, "total_value": 1050.0},
        {"product": "Widget B", "quantity": 75, "price": 15.75, "total_value": 1181.25},
        {"product": "Widget A", "quantity": 50, "price": 10.50, "total_value": 525.0},
    ]

    # Use Prefect's recommended approach for testing tasks
    with disable_run_logger():
        result = calculate_summary.fn(test_data)

        assert result["total_records"] == 3
        assert result["total_quantity"] == 225  # 100 + 75 + 50
        assert result["total_value"] == 2756.25  # 1050 + 1181.25 + 525
        assert result["average_price"] == 12.25  # (10.50 + 15.75 + 10.50) / 3

        # Check product breakdown
        assert "Widget A" in result["product_breakdown"]
        assert "Widget B" in result["product_breakdown"]
        assert result["product_breakdown"]["Widget A"]["quantity"] == 150
        assert result["product_breakdown"]["Widget A"]["total_value"] == 1575.0


def test_generate_report():
    """Test generate_report task with real file I/O operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        summary = {
            "total_records": 2,
            "total_value": 1000.0,
            "generated_at": "2024-01-15T10:00:00",
        }

        # Use Prefect's recommended approach for testing tasks
        with disable_run_logger():
            result = generate_report.fn(summary, temp_dir)

            # Check that file was created
            assert Path(result).exists()

            # Check file contents
            with open(result) as f:
                saved_data = json.load(f)
                assert saved_data["total_records"] == 2
                assert saved_data["total_value"] == 1000.0


def test_create_directory():
    """Test create_directory task with real directory operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        new_dir = Path(temp_dir) / "test_subdir"

        # Use Prefect's recommended approach for testing tasks
        with disable_run_logger():
            result = create_directory.fn(str(new_dir))

            assert Path(result).exists()
            assert Path(result).is_dir()


def test_validate_file_exists():
    """Test validate_file_exists task with real file validation."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content")
        f.close()

        # Use Prefect's recommended approach for testing tasks
        with disable_run_logger():
            assert validate_file_exists.fn(f.name) is True
            assert validate_file_exists.fn("non_existing_file.txt") is False


# Database Monitoring Task Tests


@pytest.fixture
def mock_database_manager(mocker):
    """Create a mock DatabaseManager for testing."""
    mock_db = mocker.MagicMock()

    # Mock health check response
    mock_db.health_check.return_value = {
        "database_name": "test_db",
        "status": "healthy",
        "connection": True,
        "query_test": True,
        "migration_status": {"current_version": "V003", "pending_migrations": []},
        "response_time_ms": 45.2,
        "timestamp": "2024-01-15T10:30:00Z",
    }

    # Mock health check with retry
    mock_db.health_check_with_retry.return_value = mock_db.health_check.return_value

    # Mock pool status response
    mock_db.get_pool_status.return_value = {
        "database_name": "test_db",
        "pool_size": 5,
        "checked_in": 3,
        "checked_out": 2,
        "overflow": 0,
        "invalid": 0,
        "total_connections": 5,
        "max_connections": 15,
        "utilization_percent": 13.33,
        "timestamp": "2024-01-15T10:30:00Z",
        "pool_class": "QueuePool",
    }

    # Mock migration status
    mock_db.get_migration_status.return_value = {
        "database_name": "test_db",
        "migration_directory": "/path/to/migrations",
        "current_version": "V003",
        "pending_migrations": [],
        "total_applied": 3,
    }

    # Mock query execution
    mock_db.execute_query.return_value = [{"test": 1}]

    return mock_db


def test_database_health_check_healthy(mocker, mock_database_manager):
    """Test database health check task with healthy database."""
    # Mock DatabaseManager constructor and context manager
    mock_database_manager.__enter__.return_value = mock_database_manager
    mock_database_manager.__exit__.return_value = None
    mocker.patch("core.tasks.DatabaseManager", return_value=mock_database_manager)

    with disable_run_logger():
        result = database_health_check.fn("test_db", include_retry=False)

    assert result["database_name"] == "test_db"
    assert result["status"] == "healthy"
    assert result["connection"] is True
    assert result["query_test"] is True
    assert result["response_time_ms"] == 45.2
    assert "migration_status" in result


def test_database_health_check_with_retry(mocker, mock_database_manager):
    """Test database health check task with retry enabled."""
    mock_database_manager.__enter__.return_value = mock_database_manager
    mock_database_manager.__exit__.return_value = None
    mocker.patch("core.tasks.DatabaseManager", return_value=mock_database_manager)

    with disable_run_logger():
        result = database_health_check.fn("test_db", include_retry=True)

    assert result["database_name"] == "test_db"
    assert result["status"] == "healthy"
    mock_database_manager.health_check_with_retry.assert_called_once()


def test_database_health_check_unhealthy(mocker):
    """Test database health check task with unhealthy database."""
    mock_db = mocker.MagicMock()
    mock_db.__enter__.return_value = mock_db
    mock_db.__exit__.return_value = None
    mock_db.health_check_with_retry.return_value = {
        "database_name": "test_db",
        "status": "unhealthy",
        "connection": False,
        "query_test": False,
        "migration_status": None,
        "response_time_ms": None,
        "timestamp": "2024-01-15T10:30:00Z",
        "error": "Connection failed",
    }

    mocker.patch("core.tasks.DatabaseManager", return_value=mock_db)

    with disable_run_logger():
        result = database_health_check.fn("test_db")

    assert result["database_name"] == "test_db"
    assert result["status"] == "unhealthy"
    assert result["connection"] is False
    assert result["error"] == "Connection failed"


def test_database_health_check_exception(mocker):
    """Test database health check task when exception occurs."""
    mocker.patch("core.tasks.DatabaseManager", side_effect=Exception("Database error"))

    with disable_run_logger():
        result = database_health_check.fn("test_db")

    assert result["database_name"] == "test_db"
    assert result["status"] == "unhealthy"
    assert result["connection"] is False
    assert "Database error" in result["error"]
    assert result["task_execution_error"] is True


def test_connection_pool_monitoring(mocker, mock_database_manager):
    """Test connection pool monitoring task."""
    mock_database_manager.__enter__.return_value = mock_database_manager
    mock_database_manager.__exit__.return_value = None
    mocker.patch("core.tasks.DatabaseManager", return_value=mock_database_manager)

    with disable_run_logger():
        result = connection_pool_monitoring.fn("test_db")

    assert result["database_name"] == "test_db"
    assert result["pool_size"] == 5
    assert result["checked_out"] == 2
    assert result["utilization_percent"] == 13.33
    assert result["pool_health"] == "optimal"
    assert "recommendation" in result
    assert "overflow_analysis" in result


def test_connection_pool_monitoring_high_utilization(mocker):
    """Test connection pool monitoring with high utilization."""
    mock_db = mocker.MagicMock()
    mock_db.__enter__.return_value = mock_db
    mock_db.__exit__.return_value = None
    mock_db.get_pool_status.return_value = {
        "database_name": "test_db",
        "pool_size": 5,
        "checked_in": 0,
        "checked_out": 12,
        "overflow": 7,
        "invalid": 0,
        "total_connections": 12,
        "max_connections": 15,
        "utilization_percent": 80.0,
        "timestamp": "2024-01-15T10:30:00Z",
        "pool_class": "QueuePool",
    }

    mocker.patch("core.tasks.DatabaseManager", return_value=mock_db)

    with disable_run_logger():
        result = connection_pool_monitoring.fn("test_db")

    assert result["pool_health"] == "high"
    assert "increasing pool_size" in result["recommendation"]
    assert "7 overflow connections" in result["overflow_analysis"]


def test_database_prerequisite_validation_success(mocker, mock_database_manager):
    """Test database prerequisite validation with successful validation."""
    mock_database_manager.__enter__.return_value = mock_database_manager
    mock_database_manager.__exit__.return_value = None
    mocker.patch("core.tasks.DatabaseManager", return_value=mock_database_manager)

    with disable_run_logger():
        result = database_prerequisite_validation.fn(
            ["test_db1", "test_db2"],
            check_migrations=True,
            performance_threshold_ms=1000.0,
        )

    assert result["overall_status"] == "passed"
    assert result["summary"]["total_databases"] == 2
    assert result["summary"]["passed"] == 2
    assert result["summary"]["failed"] == 0

    for db_name in ["test_db1", "test_db2"]:
        db_result = result["databases"][db_name]
        assert db_result["status"] == "passed"
        assert db_result["connectivity"] is True
        assert db_result["performance_ok"] is True
        assert db_result["migrations_ok"] is True


def test_database_prerequisite_validation_with_warnings(mocker):
    """Test database prerequisite validation with performance warnings."""
    mock_db = mocker.MagicMock()
    mock_db.__enter__.return_value = mock_db
    mock_db.__exit__.return_value = None
    mock_db.health_check.return_value = {
        "database_name": "test_db",
        "status": "degraded",
        "connection": True,
        "query_test": True,
        "response_time_ms": 1500.0,  # Exceeds threshold
        "timestamp": "2024-01-15T10:30:00Z",
    }
    mock_db.get_migration_status.return_value = {
        "pending_migrations": [{"filename": "V004__new_migration.sql"}]
    }

    mocker.patch("core.tasks.DatabaseManager", return_value=mock_db)

    with disable_run_logger():
        result = database_prerequisite_validation.fn(
            ["test_db"], check_migrations=True, performance_threshold_ms=1000.0
        )

    assert result["overall_status"] == "passed"  # Still passes but with warnings
    assert result["summary"]["warnings"] == 1

    db_result = result["databases"]["test_db"]
    assert db_result["status"] == "warning"
    assert db_result["connectivity"] is True
    assert db_result["performance_ok"] is False
    assert db_result["migrations_ok"] is False
    assert len(db_result["warnings"]) == 2  # Performance and migration warnings


def test_database_prerequisite_validation_failure(mocker):
    """Test database prerequisite validation with connection failure."""
    mock_db = mocker.MagicMock()
    mock_db.__enter__.return_value = mock_db
    mock_db.__exit__.return_value = None
    mock_db.health_check.return_value = {
        "database_name": "test_db",
        "status": "unhealthy",
        "connection": False,
        "query_test": False,
        "error": "Connection refused",
        "timestamp": "2024-01-15T10:30:00Z",
    }

    mocker.patch("core.tasks.DatabaseManager", return_value=mock_db)

    with disable_run_logger():
        result = database_prerequisite_validation.fn(["test_db"])

    assert result["overall_status"] == "failed"
    assert result["summary"]["failed"] == 1

    db_result = result["databases"]["test_db"]
    assert db_result["status"] == "failed"
    assert db_result["connectivity"] is False
    assert "Connection refused" in db_result["issues"][0]


def test_database_connectivity_diagnostics(mocker, mock_database_manager):
    """Test database connectivity diagnostics task."""
    # Mock configuration validation - it's imported from database module
    mocker.patch(
        "core.database.validate_database_configuration",
        return_value={"test_db": {"valid": True, "configuration": "ok"}},
    )

    mock_database_manager.__enter__.return_value = mock_database_manager
    mock_database_manager.__exit__.return_value = None
    mocker.patch("core.tasks.DatabaseManager", return_value=mock_database_manager)

    with disable_run_logger():
        result = database_connectivity_diagnostics.fn("test_db")

    assert result["database_name"] == "test_db"
    assert "configuration" in result
    assert "connectivity" in result
    assert "performance" in result
    assert "recommendations" in result

    assert result["connectivity"]["connection_successful"] is True
    assert result["connectivity"]["query_test_successful"] is True
    assert result["performance"]["connection_efficiency"] == "good"


def test_database_connectivity_diagnostics_config_invalid(mocker):
    """Test database connectivity diagnostics with invalid configuration."""
    mocker.patch(
        "core.database.validate_database_configuration",
        return_value={
            "test_db": {"valid": False, "error": "Missing connection string"}
        },
    )

    with disable_run_logger():
        result = database_connectivity_diagnostics.fn("test_db")

    assert result["database_name"] == "test_db"
    assert result["configuration"]["valid"] is False
    assert "Fix configuration issues" in result["recommendations"][0]


def test_database_performance_monitoring(mocker, mock_database_manager):
    """Test database performance monitoring task."""
    mock_database_manager.__enter__.return_value = mock_database_manager
    mock_database_manager.__exit__.return_value = None
    mocker.patch("core.tasks.DatabaseManager", return_value=mock_database_manager)

    test_queries = ["SELECT 1", "SELECT COUNT(*) FROM test_table"]

    with disable_run_logger():
        result = database_performance_monitoring.fn(
            "test_db", test_queries=test_queries, iterations=2
        )

    assert result["database_name"] == "test_db"
    assert result["test_configuration"]["iterations"] == 2
    assert result["test_configuration"]["test_queries_count"] == 2

    assert "connection_metrics" in result
    assert "query_performance" in result
    assert "pool_efficiency" in result
    assert "overall_assessment" in result

    # Check that queries were executed
    assert "query_1" in result["query_performance"]
    assert "query_2" in result["query_performance"]

    # Check performance assessment
    assert result["overall_assessment"]["performance_rating"] in [
        "excellent",
        "good",
        "acceptable",
        "poor",
    ]


def test_database_performance_monitoring_default_queries(mocker, mock_database_manager):
    """Test database performance monitoring with default queries."""
    mock_database_manager.__enter__.return_value = mock_database_manager
    mock_database_manager.__exit__.return_value = None
    mocker.patch("core.tasks.DatabaseManager", return_value=mock_database_manager)

    with disable_run_logger():
        result = database_performance_monitoring.fn("test_db", iterations=1)

    assert result["test_configuration"]["test_queries_count"] == 2  # Default queries
    assert "query_1" in result["query_performance"]
    assert "query_2" in result["query_performance"]


def test_multi_database_health_summary(mocker):
    """Test multi-database health summary task."""

    # Mock the database_health_check task function
    def mock_health_check(db_name, include_retry=False):
        if db_name == "healthy_db":
            return {
                "database_name": db_name,
                "status": "healthy",
                "connection": True,
                "response_time_ms": 50.0,
                "error": None,
            }
        elif db_name == "degraded_db":
            return {
                "database_name": db_name,
                "status": "degraded",
                "connection": True,
                "response_time_ms": 2000.0,
                "error": None,
            }
        else:  # unhealthy_db
            return {
                "database_name": db_name,
                "status": "unhealthy",
                "connection": False,
                "response_time_ms": None,
                "error": "Connection failed",
            }

    mocker.patch.object(database_health_check, "fn", side_effect=mock_health_check)

    database_names = ["healthy_db", "degraded_db", "unhealthy_db"]

    with disable_run_logger():
        result = multi_database_health_summary.fn(database_names)

    assert result["database_count"] == 3
    assert result["overall_status"] == "unhealthy"  # Worst case determines overall

    assert result["status_breakdown"]["healthy"] == 1
    assert result["status_breakdown"]["degraded"] == 1
    assert result["status_breakdown"]["unhealthy"] == 1

    # Check individual database results
    assert result["databases"]["healthy_db"]["status"] == "healthy"
    assert result["databases"]["degraded_db"]["status"] == "degraded"
    assert result["databases"]["unhealthy_db"]["status"] == "unhealthy"

    # Check alerts
    assert len(result["alerts"]) == 2  # One for degraded, one for unhealthy
    assert any("degraded" in alert for alert in result["alerts"])
    assert any("unhealthy" in alert for alert in result["alerts"])

    # Check recommendations
    assert (
        len(result["recommendations"]) == 2
    )  # Investigate unhealthy and monitor degraded


def test_multi_database_health_summary_all_healthy(mocker):
    """Test multi-database health summary with all databases healthy."""

    def mock_healthy_check(db_name, include_retry=False):
        return {
            "database_name": db_name,
            "status": "healthy",
            "connection": True,
            "response_time_ms": 50.0,
            "error": None,
        }

    mocker.patch.object(database_health_check, "fn", side_effect=mock_healthy_check)

    database_names = ["db1", "db2", "db3"]

    with disable_run_logger():
        result = multi_database_health_summary.fn(database_names)

    assert result["overall_status"] == "healthy"
    assert result["status_breakdown"]["healthy"] == 3
    assert result["status_breakdown"]["degraded"] == 0
    assert result["status_breakdown"]["unhealthy"] == 0
    assert len(result["alerts"]) == 0
    assert "All databases are healthy" in result["recommendations"]
