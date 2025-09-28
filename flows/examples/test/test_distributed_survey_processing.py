# noqa: E501
"""
Integration tests for distributed survey processing example.

This test suite validates the complete distributed survey processing flow
including record preparation, queue management, business logic processing,
and multi-database operations. Tests run with actual test databases to
verify end-to-end functionality.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from core.database import DatabaseManager
from core.distributed import DistributedProcessor
from flows.examples.distributed_survey_processing import (
    add_surveys_to_processing_queue,
    cleanup_old_survey_records,
    distributed_survey_processing_flow,
    prepare_survey_records_for_queue,
    process_survey_business_logic,
)


class TestDistributedSurveyProcessing:
    """Test suite for distributed survey processing functionality."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Set up test environment with clean database state."""
        # Initialize test database managers
        self.rpa_db = DatabaseManager("rpa_db")
        self.source_db = DatabaseManager("SurveyHub")
        self.processor = DistributedProcessor(self.rpa_db, self.source_db)

        # Clean up any existing test data
        self._cleanup_test_data()

        yield

        # Clean up after tests
        self._cleanup_test_data()

    def _cleanup_test_data(self):
        """Clean up test data from databases."""
        try:
            # Clean processing_queue test records
            self.rpa_db.execute_query(
                "DELETE FROM processing_queue WHERE flow_name = 'survey_processor'",
                {}
            )

            # Clean processed_surveys test records
            self.rpa_db.execute_query(
                "DELETE FROM processed_surveys WHERE survey_id LIKE 'SURV-%' "
                "OR flow_run_id LIKE '%test%'",
                {}
            )

        except Exception as e:
            print(f"Warning: Could not clean up test data: {e}")

    def test_prepare_survey_records_for_queue(self):
        """Test survey record preparation for queue insertion."""
        # Test with default parameters - call the function directly, not as a Prefect task
        from flows.examples.distributed_survey_processing import (
            prepare_survey_records_for_queue,
        )

        # Mock the Prefect logger to avoid context issues
        with patch(
            'flows.examples.distributed_survey_processing.get_run_logger'
                ) as mock_logger:
            mock_logger.return_value = MagicMock()
            records = prepare_survey_records_for_queue(survey_count=5)

        assert len(records) == 5
        assert all(isinstance(record, dict) for record in records)
        assert all("payload" in record for record in records)

        # Validate record structure
        for record in records:
            payload = record["payload"]
            assert "survey_id" in payload
            assert "customer_id" in payload
            assert "customer_name" in payload
            assert "survey_type" in payload
            assert "priority" in payload
            assert "response_data" in payload
            assert "metadata" in payload

            # Validate response data structure
            response_data = payload["response_data"]
            assert "overall_satisfaction" in response_data
            assert "likelihood_to_recommend" in response_data
            assert isinstance(response_data["overall_satisfaction"], int)
            assert 1 <= response_data["overall_satisfaction"] <= 10

    def test_prepare_survey_records_custom_priority_distribution(self):
        """Test survey record preparation with custom priority distribution."""
        priority_distribution = {"high": 0.5, "normal": 0.3, "low": 0.2}

        records = prepare_survey_records_for_queue.fn(
            survey_count=10,
            priority_distribution=priority_distribution
        )

        assert len(records) == 10

        # Check priority distribution (approximate due to randomness)
        priorities = [record["payload"]["priority"] for record in records]
        high_count = priorities.count("high")
        normal_count = priorities.count("normal")
        low_count = priorities.count("low")

        # Should have more high priority records due to distribution
        assert high_count >= normal_count
        assert high_count >= low_count

    def test_add_surveys_to_processing_queue(self):
        """Test adding survey records to the processing queue."""
        # Prepare test records
        test_records = [
            {
                "payload": {
                    "survey_id": "TEST-001",
                    "customer_id": "CUST-TEST-001",
                    "customer_name": "Test Customer 1",
                    "survey_type": "Test Survey",
                    "priority": "normal",
                    "response_data": {
                        "overall_satisfaction": 8,
                        "likelihood_to_recommend": 9
                    }
                }
            },
            {
                "payload": {
                    "survey_id": "TEST-002",
                    "customer_id": "CUST-TEST-002",
                    "customer_name": "Test Customer 2",
                    "survey_type": "Test Survey",
                    "priority": "high",
                    "response_data": {
                        "overall_satisfaction": 6,
                        "likelihood_to_recommend": 7
                    }
                }
            }
        ]

        # Add records to queue
        result = add_surveys_to_processing_queue.fn(
            records=test_records,
            flow_name="survey_processor"
        )

        assert result["records_added"] == 2
        assert result["flow_name"] == "survey_processor"
        assert "queue_status" in result
        assert "insertion_timestamp" in result

        # Verify records are in database
        queue_records = self.rpa_db.execute_query(
            "SELECT * FROM processing_queue WHERE flow_name = 'survey_processor' AND status = 'pending'",  # noqa: E501
            {}
        )

        assert len(queue_records) >= 2

    def test_process_survey_business_logic_success(self):
        """Test successful survey business logic processing."""
        test_payload = {
            "survey_id": "TEST-BL-001",
            "customer_id": "CUST-BL-001",
            "customer_name": "Business Logic Test Customer",
            "survey_type": "Customer Satisfaction",
            "customer_segment": "premium",
            "response_data": {
                "overall_satisfaction": 9,
                "likelihood_to_recommend": 10,
                "service_rating": 5,
                "product_rating": 4,
                "comments": "Excellent service!",
                "completion_time_seconds": 300
            },
            "metadata": {
                "source_system": "test_system",
                "survey_version": "v1.0"
            }
        }

        # Process the survey
        result = process_survey_business_logic(test_payload)

        # Validate processing results
        assert result["survey_id"] == "TEST-BL-001"
        assert result["customer_id"] == "CUST-BL-001"
        assert result["processing_status"] == "completed"
        assert "satisfaction_metrics" in result
        assert "customer_analysis" in result
        assert "processing_metadata" in result

        # Validate satisfaction metrics
        metrics = result["satisfaction_metrics"]
        assert metrics["overall_satisfaction"] == 9
        assert metrics["likelihood_to_recommend"] == 10
        assert metrics["nps_category"] == "promoter"  # 10 is promoter
        assert metrics["satisfaction_level"] in ["low", "medium", "high"]
        assert isinstance(metrics["composite_score"], float)

        # Verify record was stored in database
        stored_records = self.rpa_db.execute_query(
            "SELECT * FROM processed_surveys WHERE survey_id = 'TEST-BL-001'",
            {}
        )

        assert len(stored_records) == 1
        stored_record = stored_records[0]
        assert stored_record[1] == "TEST-BL-001"  # survey_id
        assert stored_record[2] == "CUST-BL-001"  # customer_id
        assert stored_record[5] == "completed"  # processing_status

    def test_process_survey_business_logic_validation_errors(self):
        """Test survey business logic with validation errors."""
        # Test missing required fields
        invalid_payload = {
            "survey_id": "TEST-INVALID-001",
            # Missing customer_id, survey_type, response_data
        }

        with pytest.raises(ValueError, match="Missing required fields"):
            process_survey_business_logic(invalid_payload)

        # Test invalid response data
        invalid_response_payload = {
            "survey_id": "TEST-INVALID-002",
            "customer_id": "CUST-INVALID-002",
            "survey_type": "Test Survey",
            "response_data": "not_a_dict"  # Should be dict
        }

        with pytest.raises(ValueError, match="response_data must be a dictionary"):
            process_survey_business_logic(invalid_response_payload)

        # Test missing response fields
        missing_response_fields_payload = {
            "survey_id": "TEST-INVALID-003",
            "customer_id": "CUST-INVALID-003",
            "survey_type": "Test Survey",
            "response_data": {
                "overall_satisfaction": 8
                # Missing likelihood_to_recommend
            }
        }

        with pytest.raises(ValueError, match="Missing required response fields"):
            process_survey_business_logic(missing_response_fields_payload)

    def test_process_survey_business_logic_nps_categories(self):
        """Test NPS category calculation in business logic."""
        base_payload = {
            "survey_id": "TEST-NPS-001",
            "customer_id": "CUST-NPS-001",
            "customer_name": "NPS Test Customer",
            "survey_type": "NPS Test",
            "response_data": {
                "overall_satisfaction": 8,
                "service_rating": 4,
                "product_rating": 4
            }
        }

        # Test promoter (9-10)
        promoter_payload = base_payload.copy()
        promoter_payload["response_data"]["likelihood_to_recommend"] = 9
        promoter_result = process_survey_business_logic(promoter_payload)
        assert promoter_result["satisfaction_metrics"]["nps_category"] == "promoter"

        # Test passive (7-8)
        passive_payload = base_payload.copy()
        passive_payload["survey_id"] = "TEST-NPS-002"
        passive_payload["response_data"]["likelihood_to_recommend"] = 7
        passive_result = process_survey_business_logic(passive_payload)
        assert passive_result["satisfaction_metrics"]["nps_category"] == "passive"

        # Test detractor (0-6)
        detractor_payload = base_payload.copy()
        detractor_payload["survey_id"] = "TEST-NPS-003"
        detractor_payload["response_data"]["likelihood_to_recommend"] = 5
        detractor_result = process_survey_business_logic(detractor_payload)
        assert detractor_result["satisfaction_metrics"]["nps_category"] == "detractor"

    @patch('flows.examples.distributed_survey_processing.source_db_manager')
    def test_process_survey_business_logic_with_source_db_error(self, mock_source_db):
        """Test business logic handling when source database is unavailable."""
        # Mock source database to raise an exception
        mock_source_db.execute_query.side_effect = Exception("Database connection failed")

        test_payload = {
            "survey_id": "TEST-DB-ERROR-001",
            "customer_id": "CUST-DB-ERROR-001",
            "customer_name": "DB Error Test Customer",
            "survey_type": "Error Test",
            "response_data": {
                "overall_satisfaction": 7,
                "likelihood_to_recommend": 8,
                "service_rating": 3,
                "product_rating": 4
            }
        }

        # Should still process successfully without source database data
        result = process_survey_business_logic(test_payload)

        assert result["survey_id"] == "TEST-DB-ERROR-001"
        assert result["processing_status"] == "completed"
        assert result["customer_analysis"] is None  # No customer data due to error

    def test_distributed_survey_processing_flow_with_sample_data(self):
        """Test complete distributed survey processing flow with sample data."""
        # Run flow with sample data preparation
        result = distributed_survey_processing_flow.fn(
            batch_size=5,
            prepare_sample_data=True,
            sample_record_count=8
        )

        # Validate flow execution results
        assert result["flow_execution"]["status"] == "completed"
        assert result["flow_execution"]["batch_size"] == 5
        assert "processor_instance" in result["flow_execution"]

        # Validate sample data preparation
        assert result["sample_data_preparation"] is not None
        assert result["sample_data_preparation"]["records_added"] == 8

        # Validate queue status
        assert "initial" in result["queue_status"]
        assert "final" in result["queue_status"]
        assert "records_processed_this_run" in result["queue_status"]

        # Validate processing results
        processing_results = result["processing_results"]
        assert "records_claimed" in processing_results
        assert "records_processed" in processing_results
        assert "records_completed" in processing_results
        assert "records_failed" in processing_results

        # Should have processed up to batch_size records
        records_processed = processing_results["records_processed"]
        assert 0 <= records_processed <= 5

        # Validate performance metrics
        assert "performance_metrics" in result
        assert "success_rate_percent" in result["performance_metrics"]

        # Validate system health
        assert "system_health" in result
        assert result["system_health"]["status"] in ["healthy", "degraded", "unhealthy"]

    def test_distributed_survey_processing_flow_process_only(self):
        """Test distributed survey processing flow without sample data preparation."""
        # First, add some test data manually
        test_records = prepare_survey_records_for_queue.fn(survey_count=3)
        add_surveys_to_processing_queue.fn(test_records, "survey_processor")

        # Run flow without sample data preparation
        result = distributed_survey_processing_flow.fn(
            batch_size=10,
            prepare_sample_data=False
        )

        # Validate flow execution
        assert result["flow_execution"]["status"] == "completed"
        assert result["sample_data_preparation"] is None  # No sample data prepared

        # Should have processed the manually added records
        processing_results = result["processing_results"]
        assert processing_results["records_processed"] >= 0

    def test_cleanup_old_survey_records(self):
        """Test cleanup of old survey records."""
        # Add some old test records
        old_timestamp = datetime.now() - timedelta(days=35)

        # Insert old processing_queue record
        self.rpa_db.execute_query(
            """INSERT INTO processing_queue
               (flow_name, payload, status, completed_at, created_at, updated_at)
               VALUES ('survey_processor', '{"test": "old_record"}', 'completed', %s, %s, %s)""",  # noqa E501
            (old_timestamp, old_timestamp, old_timestamp)
        )

        # Insert old processed_surveys record
        self.rpa_db.execute_query(
            """INSERT INTO processed_surveys
               (survey_id, customer_id, customer_name, survey_type, processing_status, processed_at)
               VALUES ('OLD-SURVEY-001', 'OLD-CUST-001', 'Old Customer', 'Old Survey', 'completed', %s)
               """,  # noqa E501
            (old_timestamp,)
        )

        # Run cleanup
        cleanup_result = cleanup_old_survey_records.fn(days_to_keep=30)

        # Validate cleanup results
        assert "queue_records_deleted" in cleanup_result
        assert "survey_records_deleted" in cleanup_result
        assert "orphaned_records_cleaned" in cleanup_result
        assert "cleanup_timestamp" in cleanup_result
        assert cleanup_result["days_retained"] == 30

        # Should have deleted at least the old records we inserted
        assert cleanup_result["queue_records_deleted"] >= 1
        assert cleanup_result["survey_records_deleted"] >= 1

    def test_concurrent_processing_no_duplicates(self):
        """Test that concurrent processing doesn't create duplicate processing."""
        # Add test records to queue
        test_records = prepare_survey_records_for_queue.fn(survey_count=10)
        add_surveys_to_processing_queue.fn(test_records, "survey_processor")

        # Simulate concurrent processing by claiming records with different instances
        processor1 = DistributedProcessor(self.rpa_db, self.source_db)
        processor2 = DistributedProcessor(self.rpa_db, self.source_db)

        # Both processors claim records simultaneously
        batch1 = processor1.claim_records_batch("survey_processor", 5)
        batch2 = processor2.claim_records_batch("survey_processor", 5)

        # Verify no overlap in claimed records
        batch1_ids = {record["id"] for record in batch1}
        batch2_ids = {record["id"] for record in batch2}

        assert len(batch1_ids.intersection(batch2_ids)) == 0, "Duplicate records claimed by different processors"  # noqa E501

        # Verify total claimed records don't exceed available records
        total_claimed = len(batch1) + len(batch2)
        assert total_claimed <= 10, "More records claimed than available"

    def test_error_handling_in_business_logic(self):
        """Test error handling when business logic fails."""
        # Create a payload that will cause processing to fail
        failing_payload = {
            "survey_id": "TEST-FAIL-001",
            "customer_id": "CUST-FAIL-001",
            "customer_name": "Failing Customer",
            "survey_type": "Failing Survey",
            "response_data": {
                "overall_satisfaction": "invalid_number",  # This will cause an error
                "likelihood_to_recommend": 8
            }
        }

        # Processing should fail and raise an exception
        with pytest.raises(RuntimeError):
            process_survey_business_logic(failing_payload)

        # Verify that a failure record was stored in the database
        failure_records = self.rpa_db.execute_query(
            "SELECT * FROM processed_surveys WHERE survey_id = 'TEST-FAIL-001' AND processing_status = 'failed'",  # noqa E501
            {}
        )

        assert len(failure_records) == 1
        failure_record = failure_records[0]
        assert failure_record[9] is not None  # error_message should not be null

    def test_queue_status_monitoring(self):
        """Test queue status monitoring functionality."""
        # Add records with different statuses
        test_records = prepare_survey_records_for_queue.fn(survey_count=5)
        add_surveys_to_processing_queue.fn(test_records, "survey_processor")

        # Claim some records (puts them in processing status)
        claimed_records = self.processor.claim_records_batch("survey_processor", 2)

        # Mark one as completed and one as failed
        if len(claimed_records) >= 2:
            self.processor.mark_record_completed(claimed_records[0]["id"], {"test": "completed"})  # noqa E501
            self.processor.mark_record_failed(claimed_records[1]["id"], "Test failure")

        # Get queue status
        queue_status = self.processor.get_queue_status("survey_processor")

        # Validate status counts
        assert queue_status["flow_name"] == "survey_processor"
        assert queue_status["total_records"] >= 5
        assert queue_status["pending_records"] >= 3  # Remaining unclaimed records
        assert queue_status["completed_records"] >= 1
        assert queue_status["failed_records"] >= 1

    def test_health_check_integration(self):
        """Test health check integration in distributed processing."""
        health_status = self.processor.health_check()

        # Validate health check structure
        assert "status" in health_status
        assert health_status["status"] in ["healthy", "degraded", "unhealthy"]
        assert "databases" in health_status
        assert "queue_status" in health_status
        assert "instance_info" in health_status

        # Validate database health
        databases = health_status["databases"]
        assert "rpa_db" in databases
        assert databases["rpa_db"]["status"] in ["healthy", "degraded", "unhealthy"]

        # Validate instance info
        instance_info = health_status["instance_info"]
        assert "instance_id" in instance_info
        assert "hostname" in instance_info


class TestDistributedSurveyProcessingEdgeCases:
    """Test edge cases and error conditions for distributed survey processing."""

    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Set up test environment."""
        self.rpa_db = DatabaseManager("rpa_db")
        self.processor = DistributedProcessor(self.rpa_db)

    def test_empty_queue_processing(self):
        """Test processing when queue is empty."""
        # Ensure queue is empty for this flow
        self.rpa_db.execute_query(
            "DELETE FROM processing_queue WHERE flow_name = 'empty_test_flow'",
            {}
        )

        # Try to process empty queue
        result = distributed_survey_processing_flow.fn(
            batch_size=10,
            prepare_sample_data=False
        )

        # Should complete successfully with no records processed
        assert result["flow_execution"]["status"] == "completed"
        processing_results = result["processing_results"]
        assert processing_results["records_processed"] == 0
        assert processing_results["records_completed"] == 0
        assert processing_results["records_failed"] == 0

    def test_large_batch_processing(self):
        """Test processing with large batch sizes."""
        # Add many records
        large_record_set = prepare_survey_records_for_queue.fn(survey_count=100)
        add_surveys_to_processing_queue.fn(large_record_set, "survey_processor")

        # Process with large batch size
        result = distributed_survey_processing_flow.fn(
            batch_size=50,
            prepare_sample_data=False
        )

        # Should process up to batch_size records
        processing_results = result["processing_results"]
        assert processing_results["records_processed"] <= 50
        assert result["flow_execution"]["status"] == "completed"

    def test_zero_batch_size_error(self):
        """Test error handling for invalid batch size."""
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            distributed_survey_processing_flow.fn(batch_size=0)

    def test_negative_sample_count_error(self):
        """Test error handling for invalid sample count."""
        with pytest.raises(ValueError):  # Should fail in prepare_survey_records_for_queue
            distributed_survey_processing_flow.fn(
                prepare_sample_data=True,
                sample_record_count=-5
            )


if __name__ == "__main__":
    """
    Run the integration tests.

    Usage:
        python -m pytest flows/examples/test/test_distributed_survey_processing.py -v
        python flows/examples/test/test_distributed_survey_processing.py  # Run directly
    """
    pytest.main([__file__, "-v", "--tb=short"])
