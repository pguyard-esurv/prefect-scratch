"""
Unit tests for distributed processing monitoring utilities.

Tests the monitoring, diagnostic, and maintenance utilities to ensure they
provide accurate operational visibility and function correctly under various
scenarios.
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from core.monitoring import (
    _analyze_orphaned_records,
    _analyze_processing_performance,
    _assess_queue_health,
    _calculate_performance_metrics,
    _count_orphaned_records,
    _count_resettable_failed_records,
    _generate_queue_alerts,
    _generate_queue_recommendations,
    distributed_processing_diagnostics,
    distributed_queue_monitoring,
    distributed_system_maintenance,
    processing_performance_monitoring,
)


class TestDistributedQueueMonitoring:
    """Test distributed queue monitoring functionality."""

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_queue_monitoring_basic(self, mock_processor_class, mock_db_manager_class):
        """Test basic queue monitoring functionality."""
        # Setup mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.get_queue_status.return_value = {
            "total_records": 100,
            "pending_records": 20,
            "processing_records": 5,
            "completed_records": 70,
            "failed_records": 5,
            "flow_name": None,
            "by_flow": {
                "test_flow": {
                    "pending": 10,
                    "processing": 2,
                    "completed": 35,
                    "failed": 3,
                    "total": 50
                }
            }
        }
        mock_processor_class.return_value = mock_processor

        # Execute monitoring
        result = distributed_queue_monitoring.fn(
            flow_names=["test_flow"],
            include_detailed_metrics=True
        )

        # Verify results
        assert "monitoring_timestamp" in result
        assert result["processor_instance_id"] == "test-instance-123"
        assert "overall_queue_status" in result
        assert "flow_specific_metrics" in result
        assert "queue_health_assessment" in result
        assert "operational_alerts" in result
        assert "recommendations" in result

        # Verify processor was called correctly
        mock_processor.get_queue_status.assert_called()

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_queue_monitoring_with_alerts(self, mock_processor_class, mock_db_manager_class):
        """Test queue monitoring with high failure rates generating alerts."""
        # Setup mocks with high failure rate
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.get_queue_status.return_value = {
            "total_records": 100,
            "pending_records": 10,
            "processing_records": 5,
            "completed_records": 60,
            "failed_records": 25,  # High failure rate (25%)
            "flow_name": None,
            "by_flow": {}
        }
        mock_processor_class.return_value = mock_processor

        # Execute monitoring
        result = distributed_queue_monitoring.fn()

        # Verify alerts are generated for high failure rate
        alerts = result["operational_alerts"]
        assert len(alerts) > 0
        assert any("failure rate" in alert.lower() for alert in alerts)

        # Verify health assessment reflects issues
        health_assessment = result["queue_health_assessment"]
        assert health_assessment["queue_health"] in ["critical", "degraded"]

    def test_assess_queue_health_healthy(self):
        """Test queue health assessment for healthy queue."""
        overall_status = {
            "total_records": 100,
            "pending_records": 20,
            "processing_records": 10,
            "failed_records": 5
        }
        flow_metrics = {}

        assessment = _assess_queue_health(overall_status, flow_metrics)

        assert assessment["queue_health"] == "healthy"
        assert assessment["health_score"] == 90
        assert assessment["failed_rate_percent"] == 5.0

    def test_assess_queue_health_critical(self):
        """Test queue health assessment for critical queue."""
        overall_status = {
            "total_records": 100,
            "pending_records": 10,
            "processing_records": 5,
            "failed_records": 25  # 25% failure rate
        }
        flow_metrics = {}

        assessment = _assess_queue_health(overall_status, flow_metrics)

        assert assessment["queue_health"] == "critical"
        assert assessment["health_score"] == 25
        assert assessment["failed_rate_percent"] == 25.0

    def test_assess_queue_health_idle(self):
        """Test queue health assessment for idle queue."""
        overall_status = {
            "total_records": 0,
            "pending_records": 0,
            "processing_records": 0,
            "failed_records": 0
        }
        flow_metrics = {}

        assessment = _assess_queue_health(overall_status, flow_metrics)

        assert assessment["queue_health"] == "idle"
        assert assessment["health_score"] == 100

    def test_generate_queue_alerts(self):
        """Test queue alert generation."""
        overall_status = {
            "total_records": 100,
            "pending_records": 1500,  # High backlog
            "processing_records": 150,  # Many processing
            "failed_records": 25  # High failure rate
        }
        flow_metrics = {
            "problematic_flow": {
                "total_records": 50,
                "failed_records": 30  # 60% failure rate
            }
        }

        alerts = _generate_queue_alerts(overall_status, flow_metrics)

        assert len(alerts) >= 3  # Should have multiple alerts
        assert any("failure rate" in alert.lower() for alert in alerts)
        assert any("backlog" in alert.lower() for alert in alerts)
        assert any("processing state" in alert.lower() for alert in alerts)
        assert any("problematic_flow" in alert for alert in alerts)

    def test_generate_queue_recommendations(self):
        """Test queue recommendation generation."""
        overall_status = {
            "total_records": 100,
            "pending_records": 600,  # High backlog
            "processing_records": 60,  # Many processing
            "failed_records": 15
        }
        queue_assessment = {
            "queue_health": "degraded",
            "failed_rate_percent": 15.0,
            "processing_rate_percent": 60.0
        }

        recommendations = _generate_queue_recommendations(overall_status, queue_assessment)

        assert len(recommendations) > 0
        assert any("investigate" in rec.lower() for rec in recommendations)


class TestDistributedProcessingDiagnostics:
    """Test distributed processing diagnostics functionality."""

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_diagnostics_basic(self, mock_processor_class, mock_db_manager_class):
        """Test basic diagnostics functionality."""
        # Setup mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.health_check.return_value = {
            "status": "healthy",
            "databases": {"rpa_db": {"status": "healthy"}}
        }
        mock_processor.get_queue_status.return_value = {
            "total_records": 50,
            "pending_records": 10,
            "processing_records": 5,
            "failed_records": 2
        }
        mock_processor_class.return_value = mock_processor

        # Mock orphaned records analysis
        with patch('core.monitoring._analyze_orphaned_records') as mock_orphaned:
            mock_orphaned.return_value = {
                "total_orphaned_records": 0,
                "analysis_timestamp": datetime.now().isoformat() + "Z"
            }

            with patch('core.monitoring._analyze_processing_performance') as mock_performance:
                mock_performance.return_value = {
                    "total_processed": 100,
                    "avg_processing_time_minutes": 5.0
                }

                # Execute diagnostics
                result = distributed_processing_diagnostics.fn(
                    flow_name="test_flow",
                    include_orphaned_analysis=True,
                    include_performance_analysis=True
                )

        # Verify results
        assert "diagnostic_timestamp" in result
        assert result["processor_instance_id"] == "test-instance-123"
        assert result["target_flow"] == "test_flow"
        assert "system_health" in result
        assert "queue_diagnostics" in result
        assert "orphaned_records_analysis" in result
        assert "performance_analysis" in result
        assert "issues_found" in result
        assert "recommendations" in result

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_diagnostics_with_issues(self, mock_processor_class, mock_db_manager_class):
        """Test diagnostics with system issues detected."""
        # Setup mocks with issues
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.health_check.return_value = {
            "status": "degraded",
            "error": "High response time"
        }
        mock_processor.get_queue_status.return_value = {
            "total_records": 100,
            "failed_records": 25  # High failure rate
        }
        mock_processor_class.return_value = mock_processor

        # Mock orphaned records analysis with issues
        with patch('core.monitoring._analyze_orphaned_records') as mock_orphaned:
            mock_orphaned.return_value = {
                "total_orphaned_records": 15,  # Orphaned records found
                "analysis_timestamp": datetime.now().isoformat() + "Z"
            }

            with patch('core.monitoring._analyze_processing_performance') as mock_performance:
                mock_performance.return_value = {
                    "total_processed": 50,
                    "avg_processing_time_minutes": 65.0  # High processing time
                }

                # Execute diagnostics
                result = distributed_processing_diagnostics.fn()

        # Verify issues are detected
        issues = result["issues_found"]
        assert len(issues) > 0
        assert any("health" in issue.lower() for issue in issues)
        assert any("orphaned" in issue.lower() for issue in issues)
        assert any("processing time" in issue.lower() for issue in issues)

    def test_analyze_orphaned_records(self):
        """Test orphaned records analysis."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.return_value = [
            {
                "flow_name": "test_flow",
                "orphaned_count": 5,
                "oldest_claim": datetime.now() - timedelta(hours=3),
                "newest_claim": datetime.now() - timedelta(hours=1),
                "avg_hours_stuck": 2.5
            }
        ]

        result = _analyze_orphaned_records(mock_processor, "test_flow")

        assert result["total_orphaned_records"] == 5
        assert len(result["orphaned_by_flow"]) == 1
        assert result["oldest_orphaned_hours"] == 2.5

    def test_analyze_orphaned_records_error(self):
        """Test orphaned records analysis with database error."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.side_effect = Exception("Database error")

        result = _analyze_orphaned_records(mock_processor, None)

        assert result["total_orphaned_records"] == 0
        assert "error" in result
        assert "Database error" in result["error"]

    def test_analyze_processing_performance(self):
        """Test processing performance analysis."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.return_value = [
            {
                "flow_name": "test_flow",
                "total_processed": 100,
                "completed_count": 90,
                "failed_count": 10,
                "avg_processing_minutes": 5.5,
                "first_completion": datetime.now() - timedelta(hours=2),
                "last_completion": datetime.now()
            }
        ]

        result = _analyze_processing_performance(mock_processor, "test_flow")

        assert result["total_processed"] == 100
        assert result["total_completed"] == 90
        assert result["success_rate_percent"] == 90.0
        assert result["avg_processing_time_minutes"] == 5.5


class TestProcessingPerformanceMonitoring:
    """Test processing performance monitoring functionality."""

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_performance_monitoring_basic(self, mock_processor_class, mock_db_manager_class):
        """Test basic performance monitoring functionality."""
        # Setup mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.get_queue_status.return_value = {
            "by_flow": {"test_flow": {"total": 50}}
        }
        mock_processor_class.return_value = mock_processor

        # Mock performance calculation functions
        with patch('core.monitoring._calculate_performance_metrics') as mock_calc:
            mock_calc.return_value = {
                "total_processed": 100,
                "completed_count": 90,
                "failed_count": 10,
                "success_rate_percent": 90.0,
                "avg_processing_rate_per_hour": 50.0
            }

            with patch('core.monitoring._analyze_processing_errors') as mock_errors:
                mock_errors.return_value = {
                    "total_errors": 10,
                    "unique_error_types": 3
                }

                with patch('core.monitoring._analyze_performance_trends') as mock_trends:
                    mock_trends.return_value = {
                        "hourly_trends": {},
                        "trend_summary": {"total_hours_analyzed": 24}
                    }

                    # Execute performance monitoring
                    result = processing_performance_monitoring.fn(
                        flow_names=["test_flow"],
                        time_window_hours=24,
                        include_error_analysis=True
                    )

        # Verify results
        assert "monitoring_timestamp" in result
        assert result["time_window_hours"] == 24
        assert result["processor_instance_id"] == "test-instance-123"
        assert "overall_metrics" in result
        assert "flow_specific_metrics" in result
        assert "error_analysis" in result
        assert "performance_trends" in result
        assert "alerts" in result
        assert "recommendations" in result

    def test_calculate_performance_metrics(self):
        """Test performance metrics calculation."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.return_value = [
            {
                "total_processed": 100,
                "completed_count": 85,
                "failed_count": 15,
                "avg_processing_minutes": 8.5,
                "first_claim": datetime.now() - timedelta(hours=6),
                "last_update": datetime.now()
            }
        ]

        start_time = datetime.now() - timedelta(hours=6)
        end_time = datetime.now()

        result = _calculate_performance_metrics(mock_processor, "test_flow", start_time, end_time)

        assert result["flow_name"] == "test_flow"
        assert result["total_processed"] == 100
        assert result["completed_count"] == 85
        assert result["failed_count"] == 15
        assert result["success_rate_percent"] == 85.0
        assert result["avg_processing_time_minutes"] == 8.5
        assert result["avg_processing_rate_per_hour"] > 0

    def test_calculate_performance_metrics_no_data(self):
        """Test performance metrics calculation with no data."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.return_value = []

        start_time = datetime.now() - timedelta(hours=6)
        end_time = datetime.now()

        result = _calculate_performance_metrics(mock_processor, "test_flow", start_time, end_time)

        assert result["flow_name"] == "test_flow"
        assert result["total_processed"] == 0
        assert result["completed_count"] == 0
        assert result["failed_count"] == 0
        assert result["success_rate_percent"] == 0
        assert result["avg_processing_rate_per_hour"] == 0


class TestDistributedSystemMaintenance:
    """Test distributed system maintenance functionality."""

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_maintenance_cleanup_dry_run(self, mock_processor_class, mock_db_manager_class):
        """Test maintenance cleanup in dry run mode."""
        # Setup mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.get_queue_status.return_value = {
            "total_records": 100,
            "pending_records": 20,
            "processing_records": 10,
            "failed_records": 5
        }
        mock_processor_class.return_value = mock_processor

        # Mock count functions for dry run
        with patch('core.monitoring._count_orphaned_records') as mock_count:
            mock_count.return_value = 8

            # Execute maintenance in dry run mode
            result = distributed_system_maintenance.fn(
                cleanup_orphaned_records=True,
                reset_failed_records=False,
                dry_run=True
            )

        # Verify dry run results
        assert result["dry_run"] is True
        assert "cleanup_orphaned_records" in result["operations_performed"]
        assert result["cleanup_results"]["dry_run"] is True
        assert result["cleanup_results"]["orphaned_records_found"] == 8
        assert result["cleanup_results"]["records_cleaned"] == 0

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_maintenance_cleanup_actual(self, mock_processor_class, mock_db_manager_class):
        """Test actual maintenance cleanup."""
        # Setup mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.get_queue_status.return_value = {
            "total_records": 100,
            "pending_records": 20,
            "processing_records": 10,
            "failed_records": 5
        }
        mock_processor.cleanup_orphaned_records.return_value = 8
        mock_processor_class.return_value = mock_processor

        # Execute actual maintenance
        result = distributed_system_maintenance.fn(
            cleanup_orphaned_records=True,
            reset_failed_records=False,
            orphaned_timeout_hours=2,
            dry_run=False
        )

        # Verify actual cleanup results
        assert result["dry_run"] is False
        assert "cleanup_orphaned_records" in result["operations_performed"]
        assert result["cleanup_results"]["dry_run"] is False
        assert result["cleanup_results"]["records_cleaned"] == 8
        assert result["cleanup_results"]["timeout_hours"] == 2

        # Verify processor method was called
        mock_processor.cleanup_orphaned_records.assert_called_once_with(2)

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_maintenance_failed_reset(self, mock_processor_class, mock_db_manager_class):
        """Test failed record reset maintenance."""
        # Setup mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.get_queue_status.return_value = {
            "by_flow": {
                "flow1": {"failed": 10},
                "flow2": {"failed": 5}
            }
        }
        mock_processor.reset_failed_records.side_effect = [7, 3]  # Return values for each flow
        mock_processor_class.return_value = mock_processor

        # Execute maintenance with failed record reset
        result = distributed_system_maintenance.fn(
            cleanup_orphaned_records=False,
            reset_failed_records=True,
            max_retries=3,
            dry_run=False
        )

        # Verify reset results
        assert "reset_failed_records" in result["operations_performed"]
        assert result["reset_results"]["total_records_reset"] == 10
        assert len(result["reset_results"]["flow_results"]) == 2

        # Verify processor methods were called
        assert mock_processor.reset_failed_records.call_count == 2

    def test_count_orphaned_records(self):
        """Test counting orphaned records."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.return_value = [{"count": 12}]

        count = _count_orphaned_records(mock_processor, 2)

        assert count == 12
        mock_processor.rpa_db.execute_query.assert_called_once()

    def test_count_orphaned_records_error(self):
        """Test counting orphaned records with database error."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.side_effect = Exception("Database error")

        count = _count_orphaned_records(mock_processor, 2)

        assert count == 0

    def test_count_resettable_failed_records(self):
        """Test counting resettable failed records."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.return_value = [{"count": 5}]

        count = _count_resettable_failed_records(mock_processor, "test_flow", 3)

        assert count == 5
        mock_processor.rpa_db.execute_query.assert_called_once()

    def test_count_resettable_failed_records_error(self):
        """Test counting resettable failed records with database error."""
        mock_processor = Mock()
        mock_processor.rpa_db.execute_query.side_effect = Exception("Database error")

        count = _count_resettable_failed_records(mock_processor, "test_flow", 3)

        assert count == 0


class TestMonitoringErrorHandling:
    """Test error handling in monitoring utilities."""

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_queue_monitoring_database_error(self, mock_processor_class, mock_db_manager_class):
        """Test queue monitoring with database connection error."""
        # Setup mocks to raise exception
        mock_db_manager_class.side_effect = Exception("Database connection failed")

        # Execute monitoring and expect RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            distributed_queue_monitoring.fn()

        assert "Database connection failed" in str(exc_info.value)

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_diagnostics_processor_error(self, mock_processor_class, mock_db_manager_class):
        """Test diagnostics with processor initialization error."""
        # Setup mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor_class.side_effect = Exception("Processor initialization failed")

        # Execute diagnostics and expect RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            distributed_processing_diagnostics.fn()

        assert "Processor initialization failed" in str(exc_info.value)

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_maintenance_partial_failure(self, mock_processor_class, mock_db_manager_class):
        """Test maintenance with partial operation failure."""
        # Setup mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor.get_queue_status.return_value = {"total_records": 50}
        mock_processor.cleanup_orphaned_records.side_effect = Exception("Cleanup failed")
        mock_processor_class.return_value = mock_processor

        # Execute maintenance and expect RuntimeError
        with pytest.raises(RuntimeError) as exc_info:
            distributed_system_maintenance.fn(
                cleanup_orphaned_records=True,
                dry_run=False
            )

        assert "Cleanup failed" in str(exc_info.value)


class TestMonitoringIntegration:
    """Integration tests for monitoring utilities."""

    @patch('core.monitoring.DatabaseManager')
    @patch('core.monitoring.DistributedProcessor')
    def test_full_monitoring_workflow(self, mock_processor_class, mock_db_manager_class):
        """Test complete monitoring workflow integration."""
        # Setup comprehensive mocks
        mock_db_manager = Mock()
        mock_db_manager_class.return_value = mock_db_manager

        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"

        # Mock queue status
        mock_processor.get_queue_status.return_value = {
            "total_records": 100,
            "pending_records": 15,
            "processing_records": 8,
            "completed_records": 70,
            "failed_records": 7,
            "by_flow": {
                "flow1": {"total": 60, "failed": 4},
                "flow2": {"total": 40, "failed": 3}
            }
        }

        # Mock health check
        mock_processor.health_check.return_value = {
            "status": "healthy",
            "databases": {"rpa_db": {"status": "healthy"}}
        }

        mock_processor_class.return_value = mock_processor

        # Mock analysis functions
        with patch('core.monitoring._analyze_orphaned_records') as mock_orphaned:
            mock_orphaned.return_value = {"total_orphaned_records": 2}

            with patch('core.monitoring._analyze_processing_performance') as mock_perf:
                mock_perf.return_value = {"avg_processing_time_minutes": 8.0}

                # Execute queue monitoring
                queue_result = distributed_queue_monitoring.fn(
                    flow_names=["flow1", "flow2"],
                    include_detailed_metrics=True
                )

                # Execute diagnostics
                diag_result = distributed_processing_diagnostics.fn(
                    include_orphaned_analysis=True,
                    include_performance_analysis=True
                )

        # Verify integration results
        assert queue_result["overall_queue_status"]["total_records"] == 100
        assert "flow1" in queue_result["flow_specific_metrics"]
        assert "flow2" in queue_result["flow_specific_metrics"]

        assert diag_result["system_health"]["status"] == "healthy"
        assert diag_result["orphaned_records_analysis"]["total_orphaned_records"] == 2

        # Verify both use same processor instance
        assert queue_result["processor_instance_id"] == diag_result["processor_instance_id"]


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
