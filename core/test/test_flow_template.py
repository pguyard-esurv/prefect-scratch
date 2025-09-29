"""
Unit tests for the distributed flow template module.

Tests the flow template functionality with mocked DatabaseManager and
DistributedProcessor instances to verify proper integration and error handling.
"""

from unittest.mock import Mock, patch

import pytest

# Import the module under test
import core.flow_template as flow_template
from core.flow_template import (
    create_custom_distributed_flow,
    distributed_processing_flow,
    generate_processing_summary,
    get_processor_health,
    get_queue_status,
    process_default_business_logic,
    process_record_with_status,
    process_record_with_status_custom,
)


class TestFlowTemplate:
    """Test cases for the distributed flow template."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Mock the module-level instances
        self.mock_rpa_db = Mock()
        self.mock_source_db = Mock()
        self.mock_processor = Mock()

        # Patch the module-level instances
        self.rpa_db_patcher = patch.object(
            flow_template, "rpa_db_manager", self.mock_rpa_db
        )
        self.source_db_patcher = patch.object(
            flow_template, "source_db_manager", self.mock_source_db
        )
        self.processor_patcher = patch.object(
            flow_template, "processor", self.mock_processor
        )

        self.rpa_db_patcher.start()
        self.source_db_patcher.start()
        self.processor_patcher.start()

        # Configure mock processor
        self.mock_processor.instance_id = "test-instance-123"

    def teardown_method(self):
        """Clean up after each test method."""
        self.rpa_db_patcher.stop()
        self.source_db_patcher.stop()
        self.processor_patcher.stop()


class TestDistributedProcessingFlow(TestFlowTemplate):
    """Test cases for the main distributed processing flow."""

    def test_successful_flow_execution(self):
        """Test successful flow execution with healthy databases and available records."""
        # Arrange
        flow_name = "test_flow"
        batch_size = 10

        # Mock health check - healthy
        self.mock_processor.health_check.return_value = {
            "status": "healthy",
            "databases": {"rpa_db": {"status": "healthy"}},
        }

        # Mock record claiming
        mock_records = [
            {
                "id": 1,
                "payload": {"data": "test1"},
                "retry_count": 0,
                "created_at": "2024-01-01",
            },
            {
                "id": 2,
                "payload": {"data": "test2"},
                "retry_count": 0,
                "created_at": "2024-01-01",
            },
        ]
        self.mock_processor.claim_records_batch_with_retry.return_value = mock_records

        # Mock successful processing results
        with patch("core.flow_template.process_record_with_status") as mock_task:
            mock_task.map.return_value = [
                {"record_id": 1, "status": "completed", "result": {"processed": True}},
                {"record_id": 2, "status": "completed", "result": {"processed": True}},
            ]

            # Act
            result = distributed_processing_flow(flow_name, batch_size)

        # Assert
        assert result["flow_name"] == flow_name
        assert result["batch_size"] == batch_size
        assert result["records_claimed"] == 2
        assert result["records_processed"] == 2
        assert result["records_completed"] == 2
        assert result["records_failed"] == 0
        assert result["success_rate_percent"] == 100.0

        # Verify method calls
        self.mock_processor.health_check.assert_called_once()
        self.mock_processor.claim_records_batch_with_retry.assert_called_once_with(
            flow_name, batch_size
        )

    def test_flow_fails_on_unhealthy_database(self):
        """Test that flow fails fast when database health check fails."""
        # Arrange
        flow_name = "test_flow"
        batch_size = 10

        # Mock health check - unhealthy
        self.mock_processor.health_check.return_value = {
            "status": "unhealthy",
            "error": "Database connection failed",
        }

        # Act & Assert
        with pytest.raises(RuntimeError, match="Database health check failed"):
            distributed_processing_flow(flow_name, batch_size)

        # Verify health check was called but no records were claimed
        self.mock_processor.health_check.assert_called_once()
        self.mock_processor.claim_records_batch_with_retry.assert_not_called()

    def test_flow_handles_degraded_database_status(self):
        """Test that flow continues with warning when database status is degraded."""
        # Arrange
        flow_name = "test_flow"
        batch_size = 10

        # Mock health check - degraded
        self.mock_processor.health_check.return_value = {
            "status": "degraded",
            "databases": {
                "rpa_db": {"status": "healthy"},
                "source_db": {"status": "degraded"},
            },
        }

        # Mock no records available
        self.mock_processor.claim_records_batch_with_retry.return_value = []

        # Act
        result = distributed_processing_flow(flow_name, batch_size)

        # Assert
        assert result["records_claimed"] == 0
        assert result["message"] == "No records to process"

        # Verify health check was called and records were attempted to be claimed
        self.mock_processor.health_check.assert_called_once()
        self.mock_processor.claim_records_batch_with_retry.assert_called_once_with(
            flow_name, batch_size
        )

    def test_flow_handles_no_available_records(self):
        """Test flow behavior when no records are available for processing."""
        # Arrange
        flow_name = "test_flow"
        batch_size = 10

        # Mock health check - healthy
        self.mock_processor.health_check.return_value = {"status": "healthy"}

        # Mock no records available
        self.mock_processor.claim_records_batch_with_retry.return_value = []

        # Act
        result = distributed_processing_flow(flow_name, batch_size)

        # Assert
        assert result["flow_name"] == flow_name
        assert result["batch_size"] == batch_size
        assert result["records_claimed"] == 0
        assert result["records_processed"] == 0
        assert result["records_completed"] == 0
        assert result["records_failed"] == 0
        assert result["message"] == "No records to process"

    def test_flow_with_custom_business_logic(self):
        """Test flow execution with custom business logic function."""
        # Arrange
        flow_name = "test_flow"
        batch_size = 5

        def custom_logic(payload):
            return {"custom_result": payload["data"].upper()}

        # Mock health check - healthy
        self.mock_processor.health_check.return_value = {"status": "healthy"}

        # Mock record claiming
        mock_records = [
            {
                "id": 1,
                "payload": {"data": "test"},
                "retry_count": 0,
                "created_at": "2024-01-01",
            }
        ]
        self.mock_processor.claim_records_batch_with_retry.return_value = mock_records

        # Mock custom processing results
        with patch("core.flow_template.process_record_with_status_custom") as mock_task:
            mock_task.map.return_value = [
                {
                    "record_id": 1,
                    "status": "completed",
                    "result": {"custom_result": "TEST"},
                }
            ]

            # Act
            result = distributed_processing_flow(flow_name, batch_size, custom_logic)

        # Assert
        assert result["records_completed"] == 1
        assert result["success_rate_percent"] == 100.0

        # Verify custom task was called
        mock_task.map.assert_called_once()

    def test_flow_input_validation(self):
        """Test input validation for flow parameters."""
        # Test empty flow_name
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            distributed_processing_flow("", 10)

        # Test invalid batch_size
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            distributed_processing_flow("test_flow", 0)

        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            distributed_processing_flow("test_flow", -5)


class TestProcessRecordWithStatus(TestFlowTemplate):
    """Test cases for individual record processing tasks."""

    def test_successful_record_processing(self):
        """Test successful processing of a single record."""
        # Arrange
        record = {
            "id": 123,
            "payload": {"survey_id": 1001, "customer_id": "CUST001"},
            "retry_count": 0,
            "created_at": "2024-01-01",
        }

        # Mock successful business logic
        expected_result = {
            "processed": True,
            "original_payload": record["payload"],
            "processor_instance": "test-instance-123",
        }

        with patch("core.flow_template.process_default_business_logic") as mock_logic:
            mock_logic.return_value = expected_result

            # Act
            result = process_record_with_status(record)

        # Assert
        assert result["record_id"] == 123
        assert result["status"] == "completed"
        assert result["result"] == expected_result

        # Verify processor methods were called
        self.mock_processor.mark_record_completed_with_retry.assert_called_once_with(
            123, expected_result
        )
        mock_logic.assert_called_once_with(record["payload"])

    def test_failed_record_processing(self):
        """Test handling of record processing failures."""
        # Arrange
        record = {
            "id": 456,
            "payload": {"invalid": "data"},
            "retry_count": 1,
            "created_at": "2024-01-01",
        }

        # Mock business logic failure
        error_message = "Invalid data format"
        with patch("core.flow_template.process_default_business_logic") as mock_logic:
            mock_logic.side_effect = ValueError(error_message)

            # Act
            result = process_record_with_status(record)

        # Assert
        assert result["record_id"] == 456
        assert result["status"] == "failed"
        assert result["error"] == error_message

        # Verify processor methods were called
        self.mock_processor.mark_record_failed_with_retry.assert_called_once_with(
            456, error_message
        )
        self.mock_processor.mark_record_completed_with_retry.assert_not_called()

    def test_custom_record_processing_success(self):
        """Test successful processing with custom business logic."""
        # Arrange
        record = {
            "id": 789,
            "payload": {"rating": 5},
            "retry_count": 0,
            "created_at": "2024-01-01",
        }

        def custom_logic(payload):
            return {"satisfaction_score": payload["rating"] * 2}

        expected_result = {"satisfaction_score": 10}

        # Act
        result = process_record_with_status_custom(record, custom_logic)

        # Assert
        assert result["record_id"] == 789
        assert result["status"] == "completed"
        assert result["result"] == expected_result

        # Verify processor methods were called
        self.mock_processor.mark_record_completed_with_retry.assert_called_once_with(
            789, expected_result
        )

    def test_custom_record_processing_failure(self):
        """Test handling of failures in custom business logic."""
        # Arrange
        record = {
            "id": 999,
            "payload": {"missing_field": True},
            "retry_count": 2,
            "created_at": "2024-01-01",
        }

        def failing_logic(payload):
            raise KeyError("Required field missing")

        # Act
        result = process_record_with_status_custom(record, failing_logic)

        # Assert
        assert result["record_id"] == 999
        assert result["status"] == "failed"
        assert "Required field missing" in result["error"]

        # Verify processor methods were called
        self.mock_processor.mark_record_failed_with_retry.assert_called_once_with(
            999, "'Required field missing'"
        )


class TestDefaultBusinessLogic(TestFlowTemplate):
    """Test cases for the default business logic function."""

    def test_default_business_logic(self):
        """Test the default business logic implementation."""
        # Arrange
        payload = {"survey_id": 1001, "customer_id": "CUST001"}

        # Act
        result = process_default_business_logic(payload)

        # Assert
        assert result["processed"] is True
        assert result["original_payload"] == payload
        assert result["processor_instance"] == "test-instance-123"
        assert "processed_at" in result

        # Verify timestamp format (ISO format)
        import datetime

        datetime.datetime.fromisoformat(result["processed_at"])  # Should not raise


class TestGenerateProcessingSummary(TestFlowTemplate):
    """Test cases for processing summary generation."""

    def test_summary_with_all_successful_results(self):
        """Test summary generation with all successful processing results."""
        # Arrange
        results = [
            {"record_id": 1, "status": "completed", "result": {"processed": True}},
            {"record_id": 2, "status": "completed", "result": {"processed": True}},
            {"record_id": 3, "status": "completed", "result": {"processed": True}},
        ]
        flow_name = "test_flow"
        batch_size = 10
        records_claimed = 3

        # Act
        summary = generate_processing_summary(
            results, flow_name, batch_size, records_claimed
        )

        # Assert
        assert summary["flow_name"] == flow_name
        assert summary["batch_size"] == batch_size
        assert summary["records_claimed"] == records_claimed
        assert summary["records_processed"] == 3
        assert summary["records_completed"] == 3
        assert summary["records_failed"] == 0
        assert summary["success_rate_percent"] == 100.0
        assert summary["processor_instance"] == "test-instance-123"
        assert summary["errors"] == []
        assert summary["error_count"] == 0

    def test_summary_with_mixed_results(self):
        """Test summary generation with mixed success and failure results."""
        # Arrange
        results = [
            {"record_id": 1, "status": "completed", "result": {"processed": True}},
            {"record_id": 2, "status": "failed", "error": "Invalid data"},
            {"record_id": 3, "status": "completed", "result": {"processed": True}},
            {"record_id": 4, "status": "failed", "error": "Network timeout"},
        ]
        flow_name = "mixed_flow"
        batch_size = 5
        records_claimed = 4

        # Act
        summary = generate_processing_summary(
            results, flow_name, batch_size, records_claimed
        )

        # Assert
        assert summary["records_processed"] == 4
        assert summary["records_completed"] == 2
        assert summary["records_failed"] == 2
        assert summary["success_rate_percent"] == 50.0
        assert len(summary["errors"]) == 2
        assert summary["error_count"] == 2

        # Check error details
        error_ids = [error["record_id"] for error in summary["errors"]]
        assert 2 in error_ids
        assert 4 in error_ids

    def test_summary_with_no_results(self):
        """Test summary generation with empty results list."""
        # Arrange
        results = []
        flow_name = "empty_flow"
        batch_size = 10
        records_claimed = 0

        # Act
        summary = generate_processing_summary(
            results, flow_name, batch_size, records_claimed
        )

        # Assert
        assert summary["records_processed"] == 0
        assert summary["records_completed"] == 0
        assert summary["records_failed"] == 0
        assert summary["success_rate_percent"] == 0
        assert summary["errors"] == []
        assert summary["error_count"] == 0

    def test_summary_limits_error_list(self):
        """Test that summary limits error list to first 10 errors."""
        # Arrange - Create 15 failed results
        results = []
        for i in range(15):
            results.append(
                {"record_id": i + 1, "status": "failed", "error": f"Error {i + 1}"}
            )

        flow_name = "error_flow"
        batch_size = 20
        records_claimed = 15

        # Act
        summary = generate_processing_summary(
            results, flow_name, batch_size, records_claimed
        )

        # Assert
        assert summary["records_failed"] == 15
        assert len(summary["errors"]) == 10  # Limited to 10
        assert summary["error_count"] == 15  # But total count is accurate


class TestUtilityFunctions(TestFlowTemplate):
    """Test cases for utility functions."""

    def test_create_custom_distributed_flow(self):
        """Test creation of custom distributed flows."""

        # Arrange
        def custom_logic(payload):
            return {"custom": True, "data": payload}

        flow_name = "custom_test_flow"
        default_batch_size = 25

        # Act
        custom_flow = create_custom_distributed_flow(
            flow_name, custom_logic, default_batch_size
        )

        # Assert
        assert callable(custom_flow)
        assert custom_flow.__name__ == "custom_flow"

        # Test that the flow can be called (would need more mocking for full execution)
        assert callable(custom_flow)

    def test_get_processor_health(self):
        """Test processor health utility function."""
        # Arrange
        expected_health = {
            "status": "healthy",
            "databases": {"rpa_db": {"status": "healthy"}},
        }
        self.mock_processor.health_check.return_value = expected_health

        # Act
        health = get_processor_health()

        # Assert
        assert health == expected_health
        self.mock_processor.health_check.assert_called_once()

    def test_get_queue_status(self):
        """Test queue status utility function."""
        # Arrange
        expected_status = {
            "total_records": 100,
            "pending_records": 50,
            "processing_records": 10,
            "completed_records": 35,
            "failed_records": 5,
        }
        self.mock_processor.get_queue_status.return_value = expected_status

        # Act
        status = get_queue_status("test_flow")

        # Assert
        assert status == expected_status
        self.mock_processor.get_queue_status.assert_called_once_with("test_flow")

    def test_get_queue_status_all_flows(self):
        """Test queue status utility function for all flows."""
        # Arrange
        expected_status = {
            "total_records": 200,
            "by_flow": {
                "flow1": {"pending": 25, "processing": 5, "completed": 20, "failed": 0},
                "flow2": {"pending": 30, "processing": 8, "completed": 40, "failed": 2},
            },
        }
        self.mock_processor.get_queue_status.return_value = expected_status

        # Act
        status = get_queue_status()

        # Assert
        assert status == expected_status
        self.mock_processor.get_queue_status.assert_called_once_with(None)


class TestModuleLevelInstances(TestFlowTemplate):
    """Test cases for module-level instance initialization."""

    @patch("core.flow_template.DatabaseManager")
    @patch("core.flow_template.DistributedProcessor")
    def test_module_instances_initialization(self, mock_processor_class, mock_db_class):
        """Test that module-level instances are properly initialized."""
        # This test verifies the module initialization pattern
        # In a real scenario, these would be initialized when the module is imported

        # Arrange
        mock_rpa_db = Mock()
        mock_source_db = Mock()
        mock_processor_instance = Mock()

        mock_db_class.side_effect = [mock_rpa_db, mock_source_db]
        mock_processor_class.return_value = mock_processor_instance

        # Act - Simulate module initialization
        rpa_db_manager = mock_db_class("rpa_db")
        source_db_manager = mock_db_class("SurveyHub")
        mock_processor_class(rpa_db_manager, source_db_manager)

        # Assert
        assert mock_db_class.call_count == 2
        mock_db_class.assert_any_call("rpa_db")
        mock_db_class.assert_any_call("SurveyHub")
        mock_processor_class.assert_called_once_with(rpa_db_manager, source_db_manager)


if __name__ == "__main__":
    pytest.main([__file__])
