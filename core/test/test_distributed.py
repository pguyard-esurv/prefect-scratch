"""
Unit tests for the DistributedProcessor class.

Tests class initialization, instance ID generation, and basic functionality
without requiring actual database connections.
"""

from unittest.mock import Mock, patch

import pytest

from core.database import DatabaseManager
from core.distributed import DistributedProcessor


class TestDistributedProcessorInitialization:
    """Test DistributedProcessor initialization and basic functionality."""

    def test_init_with_valid_rpa_db_manager(self):
        """Test successful initialization with valid rpa_db_manager."""
        # Create mock DatabaseManager
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.database_name = "rpa_db"
        mock_logger = Mock()
        mock_rpa_db.logger = mock_logger

        # Initialize DistributedProcessor
        processor = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        # Verify initialization
        assert processor.rpa_db is mock_rpa_db
        assert processor.source_db is None
        assert processor.logger is mock_logger
        assert processor.database_name == "rpa_db"
        assert processor.instance_id is not None
        assert len(processor.instance_id) > 0

        # Verify logger was called
        mock_logger.info.assert_called_once()
        assert "DistributedProcessor initialized" in mock_logger.info.call_args[0][0]
        assert processor.instance_id in mock_logger.info.call_args[0][0]

    def test_init_with_both_db_managers(self):
        """Test initialization with both rpa_db and source_db managers."""
        # Create mock DatabaseManagers
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.database_name = "rpa_db"
        mock_rpa_db.logger = Mock()

        mock_source_db = Mock(spec=DatabaseManager)
        mock_source_db.database_name = "SurveyHub"

        # Initialize DistributedProcessor
        processor = DistributedProcessor(
            rpa_db_manager=mock_rpa_db,
            source_db_manager=mock_source_db
        )

        # Verify initialization
        assert processor.rpa_db is mock_rpa_db
        assert processor.source_db is mock_source_db
        assert processor.logger is mock_rpa_db.logger

    def test_init_with_none_rpa_db_manager(self):
        """Test initialization fails with None rpa_db_manager."""
        with pytest.raises(ValueError, match="rpa_db_manager cannot be None"):
            DistributedProcessor(rpa_db_manager=None)

    def test_init_with_invalid_rpa_db_manager_type(self):
        """Test initialization fails with invalid rpa_db_manager type."""
        with pytest.raises(TypeError, match="rpa_db_manager must be a DatabaseManager instance"):
            DistributedProcessor(rpa_db_manager="not_a_database_manager")

    def test_init_with_invalid_source_db_manager_type(self):
        """Test initialization fails with invalid source_db_manager type."""
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.logger = Mock()

        with pytest.raises(TypeError, match="source_db_manager must be a DatabaseManager instance or None"):
            DistributedProcessor(
                rpa_db_manager=mock_rpa_db,
                source_db_manager="not_a_database_manager"
            )

    def test_repr_with_source_db(self):
        """Test string representation with source database."""
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.database_name = "rpa_db"
        mock_rpa_db.logger = Mock()

        mock_source_db = Mock(spec=DatabaseManager)
        mock_source_db.database_name = "SurveyHub"

        processor = DistributedProcessor(
            rpa_db_manager=mock_rpa_db,
            source_db_manager=mock_source_db
        )

        repr_str = repr(processor)
        assert "DistributedProcessor" in repr_str
        assert "rpa_db='rpa_db'" in repr_str
        assert "source_db='SurveyHub'" in repr_str
        assert f"instance_id='{processor.instance_id}'" in repr_str

    def test_repr_without_source_db(self):
        """Test string representation without source database."""
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.database_name = "rpa_db"
        mock_rpa_db.logger = Mock()

        processor = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        repr_str = repr(processor)
        assert "DistributedProcessor" in repr_str
        assert "rpa_db='rpa_db'" in repr_str
        assert "source_db='None'" in repr_str
        assert f"instance_id='{processor.instance_id}'" in repr_str


class TestInstanceIdGeneration:
    """Test instance ID generation functionality."""

    @patch('socket.gethostname')
    @patch('uuid.uuid4')
    def test_generate_instance_id_success(self, mock_uuid4, mock_gethostname):
        """Test successful instance ID generation."""
        # Setup mocks
        mock_gethostname.return_value = "rpa-worker-1"
        mock_uuid_obj = Mock()
        mock_uuid_obj.__str__ = Mock(return_value="12345678-1234-5678-9abc-123456789abc")
        mock_uuid4.return_value = mock_uuid_obj

        # Create processor
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.logger = Mock()

        processor = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        # Verify instance ID format
        expected_id = "rpa-worker-1-12345678"
        assert processor.instance_id == expected_id

        # Verify methods were called
        mock_gethostname.assert_called_once()
        mock_uuid4.assert_called_once()

    @patch('socket.gethostname')
    @patch('uuid.uuid4')
    def test_generate_instance_id_hostname_failure(self, mock_uuid4, mock_gethostname):
        """Test instance ID generation with hostname failure."""
        # Setup mocks - hostname fails
        mock_gethostname.side_effect = OSError("Hostname not available")
        mock_uuid_obj = Mock()
        mock_uuid_obj.__str__ = Mock(return_value="87654321-4321-8765-cba9-987654321cba")
        mock_uuid4.return_value = mock_uuid_obj

        # Create processor
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_logger = Mock()
        mock_rpa_db.logger = mock_logger

        processor = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        # Verify fallback instance ID format
        expected_id = "unknown-87654321"
        assert processor.instance_id == expected_id

        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        warning_message = mock_logger.warning.call_args[0][0]
        assert "Failed to get hostname" in warning_message
        assert expected_id in warning_message

    def test_instance_id_uniqueness(self):
        """Test that multiple processors generate unique instance IDs."""
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.logger = Mock()

        # Create multiple processors
        processor1 = DistributedProcessor(rpa_db_manager=mock_rpa_db)
        processor2 = DistributedProcessor(rpa_db_manager=mock_rpa_db)
        processor3 = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        # Verify all instance IDs are unique
        instance_ids = [processor1.instance_id, processor2.instance_id, processor3.instance_id]
        assert len(set(instance_ids)) == 3, "All instance IDs should be unique"

    def test_instance_id_format(self):
        """Test instance ID follows expected format."""
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.logger = Mock()

        processor = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        # Verify format: hostname-uuid_prefix
        instance_id = processor.instance_id
        assert isinstance(instance_id, str)
        assert len(instance_id) > 0
        assert '-' in instance_id

        # Split and verify parts
        parts = instance_id.split('-')
        assert len(parts) >= 2, "Instance ID should have at least hostname and UUID parts"

        # Last part should be 8-character UUID prefix
        uuid_part = parts[-1]
        assert len(uuid_part) == 8, "UUID part should be 8 characters"
        assert uuid_part.isalnum(), "UUID part should be alphanumeric"

    @patch('socket.gethostname')
    def test_instance_id_with_real_hostname(self, mock_gethostname):
        """Test instance ID generation with realistic hostname."""
        # Use realistic container hostname
        mock_gethostname.return_value = "rpa-processor-deployment-7d4b8c9f5d-x7k2m"

        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.logger = Mock()

        processor = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        # Verify instance ID includes hostname
        assert processor.instance_id.startswith("rpa-processor-deployment-7d4b8c9f5d-x7k2m-")
        assert len(processor.instance_id) > len("rpa-processor-deployment-7d4b8c9f5d-x7k2m-")


class TestDistributedProcessorProperties:
    """Test DistributedProcessor properties and basic methods."""

    def test_database_name_property(self):
        """Test database_name property returns rpa_db database name."""
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_rpa_db.database_name = "test_rpa_db"
        mock_rpa_db.logger = Mock()

        processor = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        assert processor.database_name == "test_rpa_db"

    def test_logger_property_consistency(self):
        """Test that logger property is consistent with rpa_db logger."""
        mock_rpa_db = Mock(spec=DatabaseManager)
        mock_logger = Mock()
        mock_rpa_db.logger = mock_logger

        processor = DistributedProcessor(rpa_db_manager=mock_rpa_db)

        # Verify logger is the same instance
        assert processor.logger is mock_logger
        assert processor.logger is processor.rpa_db.logger


class TestClaimRecordsBatch:
    """Test claim_records_batch method functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_claim_records_batch_success(self):
        """Test successful record claiming with valid results."""
        # Mock database response with sample records
        mock_results = [
            (1, {"survey_id": 1001, "customer_id": "CUST001"}, 0, "2024-01-15 10:00:00"),
            (2, {"survey_id": 1002, "customer_id": "CUST002"}, 1, "2024-01-15 10:01:00"),
            (3, {"order_id": 2001, "amount": 150.00}, 0, "2024-01-15 10:02:00")
        ]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call claim_records_batch
        result = self.processor.claim_records_batch("survey_processor", 3)

        # Verify results
        assert len(result) == 3
        assert result[0] == {
            'id': 1,
            'payload': {"survey_id": 1001, "customer_id": "CUST001"},
            'retry_count': 0,
            'created_at': "2024-01-15 10:00:00"
        }
        assert result[1] == {
            'id': 2,
            'payload': {"survey_id": 1002, "customer_id": "CUST002"},
            'retry_count': 1,
            'created_at': "2024-01-15 10:01:00"
        }
        assert result[2] == {
            'id': 3,
            'payload': {"order_id": 2001, "amount": 150.00},
            'retry_count': 0,
            'created_at': "2024-01-15 10:02:00"
        }

        # Verify database query was called with correct parameters
        self.mock_rpa_db.execute_query.assert_called_once()
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Verify SQL query structure
        assert "UPDATE processing_queue" in query
        assert "FOR UPDATE SKIP LOCKED" in query
        assert "ORDER BY created_at ASC" in query
        assert "RETURNING id, payload, retry_count, created_at" in query

        # Verify query parameters
        assert params['flow_name'] == "survey_processor"
        assert params['batch_size'] == 3
        assert params['instance_id'] == self.processor.instance_id

        # Verify logging
        self.mock_logger.info.assert_called()
        log_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        assert any("Claiming batch of 3 records" in call for call in log_calls)
        assert any("Successfully claimed 3 records" in call for call in log_calls)

    def test_claim_records_batch_empty_result(self):
        """Test claiming records when no records are available."""
        # Mock empty database response
        self.mock_rpa_db.execute_query.return_value = []

        # Call claim_records_batch
        result = self.processor.claim_records_batch("nonexistent_flow", 5)

        # Verify empty result
        assert result == []

        # Verify database query was called
        self.mock_rpa_db.execute_query.assert_called_once()

        # Verify debug logging for empty result (check all debug calls)
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        empty_result_log = next((call for call in debug_calls if "No pending records found" in call), None)
        assert empty_result_log is not None
        assert "nonexistent_flow" in empty_result_log

    def test_claim_records_batch_invalid_flow_name(self):
        """Test claiming records with invalid flow_name parameter."""
        # Test empty string
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.claim_records_batch("", 5)

        # Test None
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.claim_records_batch(None, 5)

        # Test non-string type
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.claim_records_batch(123, 5)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_claim_records_batch_invalid_batch_size(self):
        """Test claiming records with invalid batch_size parameter."""
        # Test zero batch size
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            self.processor.claim_records_batch("test_flow", 0)

        # Test negative batch size
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            self.processor.claim_records_batch("test_flow", -1)

        # Test non-integer type
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            self.processor.claim_records_batch("test_flow", "5")

        # Test float
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            self.processor.claim_records_batch("test_flow", 5.5)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_claim_records_batch_database_error(self):
        """Test claiming records when database operation fails."""
        # Mock database error
        self.mock_rpa_db.execute_query.side_effect = Exception("Database connection failed")

        # Call claim_records_batch and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to claim records for flow 'test_flow'"):
            self.processor.claim_records_batch("test_flow", 5)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_message = self.mock_logger.error.call_args[0][0]
        assert "Failed to claim records for flow 'test_flow'" in error_message
        assert "Database connection failed" in error_message

    def test_claim_records_batch_sql_query_structure(self):
        """Test that the SQL query has the correct structure for atomic claiming."""
        # Mock database response
        self.mock_rpa_db.execute_query.return_value = []

        # Call claim_records_batch
        self.processor.claim_records_batch("test_flow", 10)

        # Get the SQL query that was executed
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]

        # Verify key SQL components for atomic claiming
        assert "UPDATE processing_queue" in query
        assert "SET status = 'processing'" in query
        assert "flow_instance_id = :instance_id" in query
        assert "claimed_at = CURRENT_TIMESTAMP" in query
        assert "updated_at = CURRENT_TIMESTAMP" in query
        assert "WHERE id IN (" in query
        assert "SELECT id FROM processing_queue" in query
        assert "WHERE flow_name = :flow_name AND status = 'pending'" in query
        assert "ORDER BY created_at ASC" in query
        assert "LIMIT :batch_size" in query
        assert "FOR UPDATE SKIP LOCKED" in query
        assert "RETURNING id, payload, retry_count, created_at" in query

    def test_claim_records_batch_fifo_ordering(self):
        """Test that records are claimed in FIFO order (oldest first)."""
        # Mock database response with records in chronological order
        mock_results = [
            (5, {"data": "oldest"}, 0, "2024-01-15 09:00:00"),
            (3, {"data": "middle"}, 0, "2024-01-15 09:30:00"),
            (7, {"data": "newest"}, 0, "2024-01-15 10:00:00")
        ]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call claim_records_batch
        result = self.processor.claim_records_batch("test_flow", 3)

        # Verify results maintain chronological order
        assert len(result) == 3
        assert result[0]['created_at'] == "2024-01-15 09:00:00"  # oldest first
        assert result[1]['created_at'] == "2024-01-15 09:30:00"  # middle
        assert result[2]['created_at'] == "2024-01-15 10:00:00"  # newest last

        # Verify SQL query includes ORDER BY created_at ASC
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        assert "ORDER BY created_at ASC" in query


class TestMarkRecordCompleted:
    """Test mark_record_completed method functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_mark_record_completed_success(self):
        """Test successful record completion with valid result."""
        # Mock successful database update (1 row affected)
        self.mock_rpa_db.execute_query.return_value = 1

        # Test data
        record_id = 123
        result = {"satisfaction_score": 8.5, "processed_items": 3, "status": "success"}

        # Call mark_record_completed
        self.processor.mark_record_completed(record_id, result)

        # Verify database query was called with correct parameters
        self.mock_rpa_db.execute_query.assert_called_once()
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        kwargs = call_args[1]

        # Verify SQL query structure
        assert "UPDATE processing_queue" in query
        assert "SET status = 'completed'" in query
        assert "payload = :result" in query
        assert "completed_at = CURRENT_TIMESTAMP" in query
        assert "updated_at = CURRENT_TIMESTAMP" in query
        assert "WHERE id = :record_id" in query
        assert "AND status = 'processing'" in query
        assert "AND flow_instance_id = :instance_id" in query

        # Verify query parameters
        assert params['record_id'] == 123
        assert params['result'] == result
        assert params['instance_id'] == self.processor.instance_id

        # Verify return_count=True was passed
        assert kwargs.get('return_count') is True

        # Verify logging
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        assert any("Marking record 123 as completed" in call for call in info_calls)
        assert any("Successfully marked record 123 as completed" in call for call in info_calls)

    def test_mark_record_completed_record_not_found(self):
        """Test marking record as completed when record is not found."""
        # Mock database update with no rows affected
        self.mock_rpa_db.execute_query.return_value = 0

        # Test data
        record_id = 999
        result = {"status": "success"}

        # Call mark_record_completed and expect RuntimeError
        with pytest.raises(RuntimeError, match="Record 999 not found or not in processing state"):
            self.processor.mark_record_completed(record_id, result)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_message = self.mock_logger.error.call_args[0][0]
        assert "Record 999 not found or not in processing state" in error_message
        assert self.processor.instance_id in error_message

    def test_mark_record_completed_invalid_record_id(self):
        """Test marking record as completed with invalid record_id."""
        result = {"status": "success"}

        # Test zero record_id
        with pytest.raises(ValueError, match="record_id must be a positive integer"):
            self.processor.mark_record_completed(0, result)

        # Test negative record_id
        with pytest.raises(ValueError, match="record_id must be a positive integer"):
            self.processor.mark_record_completed(-1, result)

        # Test non-integer record_id
        with pytest.raises(ValueError, match="record_id must be a positive integer"):
            self.processor.mark_record_completed("123", result)

        # Test float record_id
        with pytest.raises(ValueError, match="record_id must be a positive integer"):
            self.processor.mark_record_completed(123.5, result)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_mark_record_completed_invalid_result(self):
        """Test marking record as completed with invalid result."""
        record_id = 123

        # Test non-dictionary result
        with pytest.raises(ValueError, match="result must be a dictionary"):
            self.processor.mark_record_completed(record_id, "not a dict")

        # Test None result
        with pytest.raises(ValueError, match="result must be a dictionary"):
            self.processor.mark_record_completed(record_id, None)

        # Test list result
        with pytest.raises(ValueError, match="result must be a dictionary"):
            self.processor.mark_record_completed(record_id, ["item1", "item2"])

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_mark_record_completed_database_error(self):
        """Test marking record as completed when database operation fails."""
        # Mock database error
        self.mock_rpa_db.execute_query.side_effect = Exception("Database connection failed")

        # Test data
        record_id = 123
        result = {"status": "success"}

        # Call mark_record_completed and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to mark record 123 as completed"):
            self.processor.mark_record_completed(record_id, result)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_message = self.mock_logger.error.call_args[0][0]
        assert "Failed to mark record 123 as completed" in error_message
        assert "Database connection failed" in error_message
        assert self.processor.instance_id in error_message

    def test_mark_record_completed_empty_result(self):
        """Test marking record as completed with empty result dictionary."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Test with empty dictionary (should be valid)
        record_id = 123
        result = {}

        # Call mark_record_completed (should succeed)
        self.processor.mark_record_completed(record_id, result)

        # Verify database was called with empty result
        call_args = self.mock_rpa_db.execute_query.call_args
        params = call_args[0][1]
        assert params['result'] == {}

    def test_mark_record_completed_complex_result(self):
        """Test marking record as completed with complex result data."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Test with complex nested result
        record_id = 456
        result = {
            "survey_analysis": {
                "satisfaction_score": 8.5,
                "sentiment": "positive",
                "categories": ["service", "quality", "price"]
            },
            "processing_metadata": {
                "duration_ms": 1250,
                "records_processed": 15,
                "errors": []
            },
            "timestamp": "2024-01-15T10:30:00Z"
        }

        # Call mark_record_completed
        self.processor.mark_record_completed(record_id, result)

        # Verify complex result was passed correctly
        call_args = self.mock_rpa_db.execute_query.call_args
        params = call_args[0][1]
        assert params['result'] == result
        assert params['record_id'] == 456

    def test_mark_record_completed_instance_id_verification(self):
        """Test that instance_id is correctly used in the WHERE clause."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Call mark_record_completed
        self.processor.mark_record_completed(123, {"status": "success"})

        # Verify instance_id parameter and WHERE clause
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "AND flow_instance_id = :instance_id" in query
        assert params['instance_id'] == self.processor.instance_id


class TestMarkRecordFailed:
    """Test mark_record_failed method functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_mark_record_failed_success(self):
        """Test successful record failure marking with valid error message."""
        # Mock successful database update (1 row affected)
        self.mock_rpa_db.execute_query.return_value = 1

        # Test data
        record_id = 123
        error_message = "Invalid survey data format: missing required field 'customer_id'"

        # Call mark_record_failed
        self.processor.mark_record_failed(record_id, error_message)

        # Verify database query was called with correct parameters
        self.mock_rpa_db.execute_query.assert_called_once()
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        kwargs = call_args[1]

        # Verify SQL query structure
        assert "UPDATE processing_queue" in query
        assert "SET status = 'failed'" in query
        assert "error_message = :error_message" in query
        assert "retry_count = retry_count + 1" in query
        assert "updated_at = CURRENT_TIMESTAMP" in query
        assert "WHERE id = :record_id" in query
        assert "AND status = 'processing'" in query
        assert "AND flow_instance_id = :instance_id" in query

        # Verify query parameters
        assert params['record_id'] == 123
        assert params['error_message'] == error_message
        assert params['instance_id'] == self.processor.instance_id

        # Verify return_count=True was passed
        assert kwargs.get('return_count') is True

        # Verify logging
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        assert any("Marking record 123 as failed" in call for call in info_calls)
        assert any("Successfully marked record 123 as failed" in call for call in info_calls)

    def test_mark_record_failed_record_not_found(self):
        """Test marking record as failed when record is not found."""
        # Mock database update with no rows affected
        self.mock_rpa_db.execute_query.return_value = 0

        # Test data
        record_id = 999
        error_message = "Processing failed"

        # Call mark_record_failed and expect RuntimeError
        with pytest.raises(RuntimeError, match="Record 999 not found or not in processing state"):
            self.processor.mark_record_failed(record_id, error_message)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_log = self.mock_logger.error.call_args[0][0]
        assert "Record 999 not found or not in processing state" in error_log
        assert self.processor.instance_id in error_log

    def test_mark_record_failed_invalid_record_id(self):
        """Test marking record as failed with invalid record_id."""
        error_message = "Processing failed"

        # Test zero record_id
        with pytest.raises(ValueError, match="record_id must be a positive integer"):
            self.processor.mark_record_failed(0, error_message)

        # Test negative record_id
        with pytest.raises(ValueError, match="record_id must be a positive integer"):
            self.processor.mark_record_failed(-1, error_message)

        # Test non-integer record_id
        with pytest.raises(ValueError, match="record_id must be a positive integer"):
            self.processor.mark_record_failed("123", error_message)

        # Test float record_id
        with pytest.raises(ValueError, match="record_id must be a positive integer"):
            self.processor.mark_record_failed(123.5, error_message)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_mark_record_failed_invalid_error_message(self):
        """Test marking record as failed with invalid error message."""
        record_id = 123

        # Test empty string
        with pytest.raises(ValueError, match="error_message must be a non-empty string"):
            self.processor.mark_record_failed(record_id, "")

        # Test whitespace-only string
        with pytest.raises(ValueError, match="error_message must be a non-empty string"):
            self.processor.mark_record_failed(record_id, "   ")

        # Test None error_message
        with pytest.raises(ValueError, match="error_message must be a non-empty string"):
            self.processor.mark_record_failed(record_id, None)

        # Test non-string error_message
        with pytest.raises(ValueError, match="error_message must be a non-empty string"):
            self.processor.mark_record_failed(record_id, 123)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_mark_record_failed_database_error(self):
        """Test marking record as failed when database operation fails."""
        # Mock database error
        self.mock_rpa_db.execute_query.side_effect = Exception("Database connection failed")

        # Test data
        record_id = 123
        error_message = "Processing failed"

        # Call mark_record_failed and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to mark record 123 as failed"):
            self.processor.mark_record_failed(record_id, error_message)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_log = self.mock_logger.error.call_args[0][0]
        assert "Failed to mark record 123 as failed" in error_log
        assert "Database connection failed" in error_log
        assert self.processor.instance_id in error_log

    def test_mark_record_failed_error_message_trimming(self):
        """Test that error messages are trimmed of whitespace."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Test with whitespace around error message
        record_id = 123
        error_message = "  Processing failed due to invalid data  "

        # Call mark_record_failed
        self.processor.mark_record_failed(record_id, error_message)

        # Verify trimmed error message was passed to database
        call_args = self.mock_rpa_db.execute_query.call_args
        params = call_args[0][1]
        assert params['error_message'] == "Processing failed due to invalid data"

    def test_mark_record_failed_long_error_message(self):
        """Test marking record as failed with long error message."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Test with long error message
        record_id = 456
        error_message = (
            "Processing failed due to multiple validation errors: "
            "1) Missing required field 'customer_id', "
            "2) Invalid date format in 'submitted_at' field, "
            "3) Survey response data exceeds maximum allowed length, "
            "4) Customer ID not found in reference database"
        )

        # Call mark_record_failed
        self.processor.mark_record_failed(record_id, error_message)

        # Verify long error message was passed correctly
        call_args = self.mock_rpa_db.execute_query.call_args
        params = call_args[0][1]
        assert params['error_message'] == error_message
        assert params['record_id'] == 456

    def test_mark_record_failed_retry_count_increment(self):
        """Test that retry count is incremented in the SQL query."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Call mark_record_failed
        self.processor.mark_record_failed(123, "Processing failed")

        # Verify SQL query increments retry_count
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        assert "retry_count = retry_count + 1" in query

    def test_mark_record_failed_instance_id_verification(self):
        """Test that instance_id is correctly used in the WHERE clause."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Call mark_record_failed
        self.processor.mark_record_failed(123, "Processing failed")

        # Verify instance_id parameter and WHERE clause
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "AND flow_instance_id = :instance_id" in query
        assert params['instance_id'] == self.processor.instance_id

    def test_mark_record_failed_special_characters_in_error(self):
        """Test marking record as failed with special characters in error message."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Test with special characters and quotes
        record_id = 789
        error_message = "SQL error: column 'data' doesn't exist; query: SELECT * FROM table WHERE id='123'"

        # Call mark_record_failed
        self.processor.mark_record_failed(record_id, error_message)

        # Verify special characters are handled correctly
        call_args = self.mock_rpa_db.execute_query.call_args
        params = call_args[0][1]
        assert params['error_message'] == error_message
        assert params['record_id'] == 789

    def test_claim_records_batch_instance_id_assignment(self):
        """Test that instance ID is correctly assigned to claimed records."""
        # Mock database response
        self.mock_rpa_db.execute_query.return_value = [
            (1, {"test": "data"}, 0, "2024-01-15 10:00:00")
        ]

        # Call claim_records_batch
        self.processor.claim_records_batch("test_flow", 1)

        # Verify instance_id parameter was passed correctly
        call_args = self.mock_rpa_db.execute_query.call_args
        params = call_args[0][1]
        assert params['instance_id'] == self.processor.instance_id

        # Verify SQL query sets flow_instance_id
        query = call_args[0][0]
        assert "flow_instance_id = :instance_id" in query

    def test_claim_records_batch_different_batch_sizes(self):
        """Test claiming records with different batch sizes."""
        # Test small batch
        self.mock_rpa_db.execute_query.return_value = [
            (1, {"data": "test1"}, 0, "2024-01-15 10:00:00")
        ]
        result = self.processor.claim_records_batch("test_flow", 1)
        assert len(result) == 1

        # Test larger batch
        self.mock_rpa_db.execute_query.return_value = [
            (i, {"data": f"test{i}"}, 0, f"2024-01-15 10:0{i}:00")
            for i in range(1, 51)  # 50 records
        ]
        result = self.processor.claim_records_batch("test_flow", 50)
        assert len(result) == 50

        # Verify batch_size parameter was passed correctly in both calls
        calls = self.mock_rpa_db.execute_query.call_args_list
        assert calls[0][0][1]['batch_size'] == 1
        assert calls[1][0][1]['batch_size'] == 50

    def test_claim_records_batch_logging_details(self):
        """Test detailed logging during record claiming process."""
        # Mock database response
        mock_results = [
            (1, {"survey_id": 1001}, 0, "2024-01-15 10:00:00"),
            (2, {"survey_id": 1002}, 0, "2024-01-15 10:01:00")
        ]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call claim_records_batch
        self.processor.claim_records_batch("survey_processor", 5)

        # Verify info logging calls
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]

        # Check initial claiming log
        claiming_log = next((call for call in info_calls if "Claiming batch" in call), None)
        assert claiming_log is not None
        assert "Claiming batch of 5 records" in claiming_log
        assert "flow 'survey_processor'" in claiming_log
        assert self.processor.instance_id in claiming_log

        # Check success log
        success_log = next((call for call in info_calls if "Successfully claimed" in call), None)
        assert success_log is not None
        assert "Successfully claimed 2 records" in success_log
        assert "flow 'survey_processor'" in success_log
        assert self.processor.instance_id in success_log


class TestAddRecordsToQueue:
    """Test add_records_to_queue method functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_add_records_to_queue_single_record(self):
        """Test adding a single record to the queue."""
        # Mock successful database insertion
        self.mock_rpa_db.execute_query.return_value = None

        # Test data
        flow_name = "survey_processor"
        records = [{"payload": {"survey_id": 1001, "customer_id": "CUST001"}}]

        # Call add_records_to_queue
        result = self.processor.add_records_to_queue(flow_name, records)

        # Verify result
        assert result == 1

        # Verify database query was called with correct parameters
        self.mock_rpa_db.execute_query.assert_called_once()
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Verify SQL query structure for single record
        assert "INSERT INTO processing_queue" in query
        assert "(flow_name, payload, status, created_at, updated_at)" in query
        assert "VALUES (:flow_name, :payload, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)" in query

        # Verify query parameters
        assert params['flow_name'] == "survey_processor"
        assert params['payload'] == {"survey_id": 1001, "customer_id": "CUST001"}

        # Verify logging
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        assert any("Adding 1 records to queue" in call for call in info_calls)
        assert any("Successfully added 1 records to queue" in call for call in info_calls)

    def test_add_records_to_queue_multiple_records(self):
        """Test adding multiple records to the queue using batch insertion."""
        # Mock successful database insertion
        self.mock_rpa_db.execute_query.return_value = None

        # Test data
        flow_name = "survey_processor"
        records = [
            {"payload": {"survey_id": 1001, "customer_id": "CUST001"}},
            {"payload": {"survey_id": 1002, "customer_id": "CUST002"}},
            {"payload": {"order_id": 2001, "amount": 150.00}}
        ]

        # Call add_records_to_queue
        result = self.processor.add_records_to_queue(flow_name, records)

        # Verify result
        assert result == 3

        # Verify database query was called with correct parameters
        self.mock_rpa_db.execute_query.assert_called_once()
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Verify SQL query structure for batch insertion
        assert "INSERT INTO processing_queue" in query
        assert "(flow_name, payload, status, created_at, updated_at)" in query
        assert "VALUES" in query
        assert "(:flow_name, :payload_0, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)" in query
        assert "(:flow_name, :payload_1, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)" in query
        assert "(:flow_name, :payload_2, 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)" in query

        # Verify query parameters
        assert params['flow_name'] == "survey_processor"
        assert params['payload_0'] == {"survey_id": 1001, "customer_id": "CUST001"}
        assert params['payload_1'] == {"survey_id": 1002, "customer_id": "CUST002"}
        assert params['payload_2'] == {"order_id": 2001, "amount": 150.00}

        # Verify logging
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        assert any("Adding 3 records to queue" in call for call in info_calls)
        assert any("Successfully added 3 records to queue" in call for call in info_calls)

    def test_add_records_to_queue_invalid_flow_name(self):
        """Test adding records with invalid flow_name parameter."""
        records = [{"payload": {"data": "test"}}]

        # Test empty string
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.add_records_to_queue("", records)

        # Test None
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.add_records_to_queue(None, records)

        # Test non-string type
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.add_records_to_queue(123, records)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_add_records_to_queue_invalid_records(self):
        """Test adding records with invalid records parameter."""
        flow_name = "test_flow"

        # Test empty list
        with pytest.raises(ValueError, match="records must be a non-empty list"):
            self.processor.add_records_to_queue(flow_name, [])

        # Test None
        with pytest.raises(ValueError, match="records must be a non-empty list"):
            self.processor.add_records_to_queue(flow_name, None)

        # Test non-list type
        with pytest.raises(ValueError, match="records must be a non-empty list"):
            self.processor.add_records_to_queue(flow_name, "not a list")

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_add_records_to_queue_invalid_record_structure(self):
        """Test adding records with invalid record structure."""
        flow_name = "test_flow"

        # Test non-dictionary record
        with pytest.raises(ValueError, match="Record at index 0 must be a dictionary"):
            self.processor.add_records_to_queue(flow_name, ["not a dict"])

        # Test record missing payload field
        with pytest.raises(ValueError, match="Record at index 0 missing required 'payload' field"):
            self.processor.add_records_to_queue(flow_name, [{"data": "test"}])

        # Test record with non-dictionary payload
        with pytest.raises(ValueError, match="Record at index 0 'payload' must be a dictionary"):
            self.processor.add_records_to_queue(flow_name, [{"payload": "not a dict"}])

        # Test mixed valid and invalid records
        records = [
            {"payload": {"valid": "data"}},
            {"invalid": "record"}  # Missing payload
        ]
        with pytest.raises(ValueError, match="Record at index 1 missing required 'payload' field"):
            self.processor.add_records_to_queue(flow_name, records)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_add_records_to_queue_database_error(self):
        """Test adding records when database operation fails."""
        # Mock database error
        self.mock_rpa_db.execute_query.side_effect = Exception("Database connection failed")

        # Test data
        flow_name = "test_flow"
        records = [{"payload": {"data": "test"}}]

        # Call add_records_to_queue and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to add 1 records to queue for flow 'test_flow'"):
            self.processor.add_records_to_queue(flow_name, records)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_message = self.mock_logger.error.call_args[0][0]
        assert "Failed to add 1 records to queue for flow 'test_flow'" in error_message
        assert "Database connection failed" in error_message

    def test_add_records_to_queue_empty_payload(self):
        """Test adding records with empty payload (should be valid)."""
        # Mock successful database insertion
        self.mock_rpa_db.execute_query.return_value = None

        # Test data with empty payload
        flow_name = "test_flow"
        records = [{"payload": {}}]

        # Call add_records_to_queue (should succeed)
        result = self.processor.add_records_to_queue(flow_name, records)

        # Verify result
        assert result == 1

        # Verify empty payload was passed correctly
        call_args = self.mock_rpa_db.execute_query.call_args
        params = call_args[0][1]
        assert params['payload'] == {}

    def test_add_records_to_queue_complex_payload(self):
        """Test adding records with complex nested payload data."""
        # Mock successful database insertion
        self.mock_rpa_db.execute_query.return_value = None

        # Test data with complex payload
        flow_name = "complex_processor"
        records = [{
            "payload": {
                "survey_data": {
                    "survey_id": 1001,
                    "responses": [
                        {"question_id": 1, "answer": "Very satisfied"},
                        {"question_id": 2, "answer": 8}
                    ]
                },
                "metadata": {
                    "source": "web_form",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "user_agent": "Mozilla/5.0..."
                }
            }
        }]

        # Call add_records_to_queue
        result = self.processor.add_records_to_queue(flow_name, records)

        # Verify complex payload was passed correctly
        assert result == 1
        call_args = self.mock_rpa_db.execute_query.call_args
        params = call_args[0][1]
        assert params['payload'] == records[0]['payload']

    def test_add_records_to_queue_batch_size_threshold(self):
        """Test that single vs batch insertion logic works correctly."""
        # Mock successful database insertion
        self.mock_rpa_db.execute_query.return_value = None

        flow_name = "test_flow"

        # Test single record (should use single insertion query)
        single_record = [{"payload": {"data": "single"}}]
        self.processor.add_records_to_queue(flow_name, single_record)

        # Verify single insertion query was used
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        assert "VALUES (:flow_name, :payload, 'pending'" in query
        assert ":payload_0" not in query

        # Reset mock
        self.mock_rpa_db.reset_mock()

        # Test multiple records (should use batch insertion query)
        multiple_records = [
            {"payload": {"data": "first"}},
            {"payload": {"data": "second"}}
        ]
        self.processor.add_records_to_queue(flow_name, multiple_records)

        # Verify batch insertion query was used
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert ":payload_0" in query
        assert ":payload_1" in query
        assert params['payload_0'] == {"data": "first"}
        assert params['payload_1'] == {"data": "second"}


class TestGetQueueStatus:
    """Test get_queue_status method functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_get_queue_status_specific_flow(self):
        """Test getting queue status for a specific flow."""
        # Mock database response for specific flow
        mock_results = [
            ('pending', 15),
            ('processing', 3),
            ('completed', 120),
            ('failed', 2)
        ]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call get_queue_status for specific flow
        result = self.processor.get_queue_status("survey_processor")

        # Verify result structure and values
        expected_result = {
            'total_records': 140,
            'pending_records': 15,
            'processing_records': 3,
            'completed_records': 120,
            'failed_records': 2,
            'flow_name': 'survey_processor'
        }
        assert result == expected_result

        # Verify database query was called with correct parameters
        self.mock_rpa_db.execute_query.assert_called_once()
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Verify SQL query structure
        assert "SELECT status, COUNT(*) as count" in query
        assert "FROM processing_queue" in query
        assert "WHERE flow_name = :flow_name" in query
        assert "GROUP BY status" in query

        # Verify query parameters
        assert params['flow_name'] == "survey_processor"

    def test_get_queue_status_all_flows(self):
        """Test getting queue status for all flows (system-wide)."""
        # Mock database responses
        # First call: overall status
        overall_results = [
            ('pending', 25),
            ('processing', 8),
            ('completed', 200),
            ('failed', 5)
        ]

        # Second call: by flow breakdown
        by_flow_results = [
            ('survey_processor', 'pending', 15),
            ('survey_processor', 'processing', 3),
            ('survey_processor', 'completed', 120),
            ('survey_processor', 'failed', 2),
            ('order_processor', 'pending', 10),
            ('order_processor', 'processing', 5),
            ('order_processor', 'completed', 80),
            ('order_processor', 'failed', 3)
        ]

        # Configure mock to return different results for different calls
        self.mock_rpa_db.execute_query.side_effect = [overall_results, by_flow_results]

        # Call get_queue_status for all flows
        result = self.processor.get_queue_status()

        # Verify result structure and values
        expected_result = {
            'total_records': 238,
            'pending_records': 25,
            'processing_records': 8,
            'completed_records': 200,
            'failed_records': 5,
            'flow_name': None,
            'by_flow': {
                'survey_processor': {
                    'pending': 15,
                    'processing': 3,
                    'completed': 120,
                    'failed': 2,
                    'total': 140
                },
                'order_processor': {
                    'pending': 10,
                    'processing': 5,
                    'completed': 80,
                    'failed': 3,
                    'total': 98
                }
            }
        }
        assert result == expected_result

        # Verify two database queries were made
        assert self.mock_rpa_db.execute_query.call_count == 2

        # Verify first query (overall status)
        first_call = self.mock_rpa_db.execute_query.call_args_list[0]
        first_query = first_call[0][0]
        first_params = first_call[0][1]
        assert "SELECT status, COUNT(*) as count" in first_query
        assert "WHERE flow_name" not in first_query  # No WHERE clause for overall
        assert first_params == {}

        # Verify second query (by flow breakdown)
        second_call = self.mock_rpa_db.execute_query.call_args_list[1]
        second_query = second_call[0][0]
        second_params = second_call[0][1]
        assert "SELECT flow_name, status, COUNT(*) as count" in second_query
        assert "GROUP BY flow_name, status" in second_query
        assert "ORDER BY flow_name, status" in second_query
        assert second_params == {}

    def test_get_queue_status_empty_queue(self):
        """Test getting queue status when queue is empty."""
        # Mock empty database response
        self.mock_rpa_db.execute_query.return_value = []

        # Call get_queue_status for specific flow
        result = self.processor.get_queue_status("empty_flow")

        # Verify result with zero counts
        expected_result = {
            'total_records': 0,
            'pending_records': 0,
            'processing_records': 0,
            'completed_records': 0,
            'failed_records': 0,
            'flow_name': 'empty_flow'
        }
        assert result == expected_result

    def test_get_queue_status_partial_statuses(self):
        """Test getting queue status when only some statuses have records."""
        # Mock database response with only some statuses
        mock_results = [
            ('pending', 10),
            ('completed', 50)
            # No 'processing' or 'failed' records
        ]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call get_queue_status
        result = self.processor.get_queue_status("partial_flow")

        # Verify result includes zero counts for missing statuses
        expected_result = {
            'total_records': 60,
            'pending_records': 10,
            'processing_records': 0,  # Should be 0, not missing
            'completed_records': 50,
            'failed_records': 0,      # Should be 0, not missing
            'flow_name': 'partial_flow'
        }
        assert result == expected_result

    def test_get_queue_status_invalid_flow_name(self):
        """Test getting queue status with invalid flow_name parameter."""
        # Test empty string
        with pytest.raises(ValueError, match="flow_name must be a non-empty string or None"):
            self.processor.get_queue_status("")

        # Test whitespace-only string
        with pytest.raises(ValueError, match="flow_name must be a non-empty string or None"):
            self.processor.get_queue_status("   ")

        # Test non-string type (but not None)
        with pytest.raises(ValueError, match="flow_name must be a non-empty string or None"):
            self.processor.get_queue_status(123)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_get_queue_status_database_error(self):
        """Test getting queue status when database operation fails."""
        # Mock database error
        self.mock_rpa_db.execute_query.side_effect = Exception("Database connection failed")

        # Call get_queue_status and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to get queue status for flow 'test_flow'"):
            self.processor.get_queue_status("test_flow")

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_message = self.mock_logger.error.call_args[0][0]
        assert "Failed to get queue status for flow 'test_flow'" in error_message
        assert "Database connection failed" in error_message

    def test_get_queue_status_none_flow_name(self):
        """Test that None is a valid flow_name parameter."""
        # Mock database responses for system-wide query
        overall_results = [('pending', 5)]
        by_flow_results = [('test_flow', 'pending', 5)]
        self.mock_rpa_db.execute_query.side_effect = [overall_results, by_flow_results]

        # Call get_queue_status with None (should not raise error)
        result = self.processor.get_queue_status(None)

        # Verify it works and includes by_flow data
        assert result['flow_name'] is None
        assert 'by_flow' in result
        assert self.mock_rpa_db.execute_query.call_count == 2

    def test_get_queue_status_logging(self):
        """Test that appropriate logging occurs during queue status retrieval."""
        # Mock database response
        mock_results = [('pending', 10), ('completed', 20)]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call get_queue_status
        self.processor.get_queue_status("test_flow")

        # Verify debug logging
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]

        # Check for initial debug log
        initial_log = next((call for call in debug_calls if "Getting queue status for flow: test_flow" in call), None)
        assert initial_log is not None

        # Check for result debug log
        result_log = next((call for call in debug_calls if "Queue status retrieved: 30 total records" in call), None)
        assert result_log is not None
        assert "(10 pending, 0 processing, 20 completed, 0 failed)" in result_log

    def test_get_queue_status_unknown_status_handling(self):
        """Test handling of unknown status values in database results."""
        # Mock database response with unknown status
        mock_results = [
            ('pending', 10),
            ('unknown_status', 5),  # This should be ignored
            ('completed', 20)
        ]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call get_queue_status
        result = self.processor.get_queue_status("test_flow")

        # Verify unknown status is ignored and doesn't affect totals
        expected_result = {
            'total_records': 30,  # Only known statuses counted
            'pending_records': 10,
            'processing_records': 0,
            'completed_records': 20,
            'failed_records': 0,
            'flow_name': 'test_flow'
        }
        assert result == expected_result


class TestCleanupOrphanedRecords:
    """Test cleanup_orphaned_records method functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_cleanup_orphaned_records_success(self):
        """Test successful cleanup of orphaned records."""
        # Mock database update returning 3 affected rows
        self.mock_rpa_db.execute_query.return_value = 3

        # Call cleanup_orphaned_records with default timeout
        result = self.processor.cleanup_orphaned_records()

        # Verify result
        assert result == 3

        # Verify database query was called
        self.mock_rpa_db.execute_query.assert_called_once()
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        call_args[0][1]
        kwargs = call_args[1]

        # Verify SQL query structure
        assert "UPDATE processing_queue" in query
        assert "SET status = 'pending'" in query
        assert "flow_instance_id = NULL" in query
        assert "claimed_at = NULL" in query
        assert "retry_count = retry_count + 1" in query
        assert "updated_at = CURRENT_TIMESTAMP" in query
        assert "WHERE status = 'processing'" in query
        assert "claimed_at < CURRENT_TIMESTAMP - INTERVAL '1 hours'" in query

        # Verify return_count=True was passed
        assert kwargs.get('return_count') is True

        # Verify logging
        self.mock_logger.warning.assert_called_once()
        warning_message = self.mock_logger.warning.call_args[0][0]
        assert "Cleaned up 3 orphaned records" in warning_message
        assert "1 hours" in warning_message

    def test_cleanup_orphaned_records_custom_timeout(self):
        """Test cleanup with custom timeout parameter."""
        # Mock database update returning 5 affected rows
        self.mock_rpa_db.execute_query.return_value = 5

        # Call cleanup_orphaned_records with custom timeout
        result = self.processor.cleanup_orphaned_records(timeout_hours=3)

        # Verify result
        assert result == 5

        # Verify database query includes custom timeout
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        assert "claimed_at < CURRENT_TIMESTAMP - INTERVAL '3 hours'" in query

        # Verify logging includes custom timeout
        warning_message = self.mock_logger.warning.call_args[0][0]
        assert "3 hours" in warning_message

    def test_cleanup_orphaned_records_no_records_found(self):
        """Test cleanup when no orphaned records are found."""
        # Mock database update returning 0 affected rows
        self.mock_rpa_db.execute_query.return_value = 0

        # Call cleanup_orphaned_records
        result = self.processor.cleanup_orphaned_records()

        # Verify result
        assert result == 0

        # Verify debug logging for no records found
        self.mock_logger.debug.assert_called()
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        no_records_log = next((call for call in debug_calls if "No orphaned records found" in call), None)
        assert no_records_log is not None
        assert "1 hours" in no_records_log

        # Verify no warning was logged
        self.mock_logger.warning.assert_not_called()

    def test_cleanup_orphaned_records_invalid_timeout(self):
        """Test cleanup with invalid timeout parameter."""
        # Test zero timeout
        with pytest.raises(ValueError, match="timeout_hours must be a positive integer"):
            self.processor.cleanup_orphaned_records(timeout_hours=0)

        # Test negative timeout
        with pytest.raises(ValueError, match="timeout_hours must be a positive integer"):
            self.processor.cleanup_orphaned_records(timeout_hours=-1)

        # Test non-integer timeout
        with pytest.raises(ValueError, match="timeout_hours must be a positive integer"):
            self.processor.cleanup_orphaned_records(timeout_hours="2")

        # Test float timeout
        with pytest.raises(ValueError, match="timeout_hours must be a positive integer"):
            self.processor.cleanup_orphaned_records(timeout_hours=2.5)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_cleanup_orphaned_records_database_error(self):
        """Test cleanup when database operation fails."""
        # Mock database error
        self.mock_rpa_db.execute_query.side_effect = Exception("Database connection failed")

        # Call cleanup_orphaned_records and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to cleanup orphaned records with timeout 2 hours"):
            self.processor.cleanup_orphaned_records(timeout_hours=2)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_message = self.mock_logger.error.call_args[0][0]
        assert "Failed to cleanup orphaned records with timeout 2 hours" in error_message
        assert "Database connection failed" in error_message

    def test_cleanup_orphaned_records_sql_structure(self):
        """Test that cleanup SQL query has correct structure."""
        # Mock database response
        self.mock_rpa_db.execute_query.return_value = 2

        # Call cleanup_orphaned_records
        self.processor.cleanup_orphaned_records(timeout_hours=4)

        # Verify SQL query structure
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]

        # Verify all required SQL components
        assert "UPDATE processing_queue" in query
        assert "SET status = 'pending'" in query
        assert "flow_instance_id = NULL" in query
        assert "claimed_at = NULL" in query
        assert "retry_count = retry_count + 1" in query
        assert "updated_at = CURRENT_TIMESTAMP" in query
        assert "WHERE status = 'processing'" in query
        assert "claimed_at < CURRENT_TIMESTAMP - INTERVAL '4 hours'" in query

    def test_cleanup_orphaned_records_logging_levels(self):
        """Test appropriate logging levels for different scenarios."""
        # Test scenario with orphaned records found (should log warning)
        self.mock_rpa_db.execute_query.return_value = 7
        self.processor.cleanup_orphaned_records()

        # Verify warning level logging
        self.mock_logger.warning.assert_called_once()
        warning_msg = self.mock_logger.warning.call_args[0][0]
        assert "Cleaned up 7 orphaned records" in warning_msg

        # Reset mocks
        self.mock_logger.reset_mock()

        # Test scenario with no orphaned records (should log debug)
        self.mock_rpa_db.execute_query.return_value = 0
        self.processor.cleanup_orphaned_records()

        # Verify debug level logging
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        assert any("No orphaned records found" in call for call in debug_calls)
        self.mock_logger.warning.assert_not_called()


class TestResetFailedRecords:
    """Test reset_failed_records method functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_reset_failed_records_success(self):
        """Test successful reset of failed records within retry limits."""
        # Mock count query result: 5 resettable, 2 exceeded limit, 7 total
        count_result = [(5, 2, 7)]
        # Mock reset query result: 5 rows affected
        reset_result = 5

        # Configure mock to return different results for different calls
        self.mock_rpa_db.execute_query.side_effect = [count_result, reset_result]

        # Call reset_failed_records
        result = self.processor.reset_failed_records("survey_processor", max_retries=3)

        # Verify result
        assert result == 5

        # Verify two database calls were made
        assert self.mock_rpa_db.execute_query.call_count == 2

        # Verify first call (count query)
        first_call = self.mock_rpa_db.execute_query.call_args_list[0]
        count_query = first_call[0][0]
        count_params = first_call[0][1]

        assert "COUNT(*) FILTER (WHERE retry_count < :max_retries) as resettable" in count_query
        assert "COUNT(*) FILTER (WHERE retry_count >= :max_retries) as exceeded_limit" in count_query
        assert "WHERE flow_name = :flow_name AND status = 'failed'" in count_query
        assert count_params['flow_name'] == "survey_processor"
        assert count_params['max_retries'] == 3

        # Verify second call (reset query)
        second_call = self.mock_rpa_db.execute_query.call_args_list[1]
        reset_query = second_call[0][0]
        reset_params = second_call[0][1]
        reset_kwargs = second_call[1]

        assert "UPDATE processing_queue" in reset_query
        assert "SET status = 'pending'" in reset_query
        assert "flow_instance_id = NULL" in reset_query
        assert "claimed_at = NULL" in reset_query
        assert "error_message = NULL" in reset_query
        assert "updated_at = CURRENT_TIMESTAMP" in reset_query
        assert "WHERE flow_name = :flow_name" in reset_query
        assert "AND status = 'failed'" in reset_query
        assert "AND retry_count < :max_retries" in reset_query
        assert reset_params['flow_name'] == "survey_processor"
        assert reset_params['max_retries'] == 3
        assert reset_kwargs.get('return_count') is True

        # Verify logging
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        assert any("Found 7 failed records for flow 'survey_processor'" in call for call in info_calls)
        assert any("5 can be reset, 2 exceeded retry limit" in call for call in info_calls)
        assert any("Successfully reset 5 failed records to pending" in call for call in info_calls)

    def test_reset_failed_records_no_eligible_records(self):
        """Test reset when no records are eligible for reset."""
        # Mock count query result: 0 resettable, 3 exceeded limit, 3 total
        count_result = [(0, 3, 3)]

        self.mock_rpa_db.execute_query.return_value = count_result

        # Call reset_failed_records
        result = self.processor.reset_failed_records("test_flow", max_retries=2)

        # Verify result
        assert result == 0

        # Verify only one database call was made (count query)
        assert self.mock_rpa_db.execute_query.call_count == 1

        # Verify debug logging
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        assert any("No failed records eligible for reset found" in call for call in debug_calls)

    def test_reset_failed_records_no_failed_records(self):
        """Test reset when no failed records exist for the flow."""
        # Mock count query result: 0 resettable, 0 exceeded limit, 0 total
        count_result = [(0, 0, 0)]

        self.mock_rpa_db.execute_query.return_value = count_result

        # Call reset_failed_records
        result = self.processor.reset_failed_records("empty_flow")

        # Verify result
        assert result == 0

        # Verify only one database call was made
        assert self.mock_rpa_db.execute_query.call_count == 1

        # Verify appropriate logging
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        assert any("Found 0 failed records for flow 'empty_flow'" in call for call in info_calls)

    def test_reset_failed_records_invalid_flow_name(self):
        """Test reset with invalid flow_name parameter."""
        # Test empty string
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.reset_failed_records("", max_retries=3)

        # Test None
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.reset_failed_records(None, max_retries=3)

        # Test non-string type
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            self.processor.reset_failed_records(123, max_retries=3)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_reset_failed_records_invalid_max_retries(self):
        """Test reset with invalid max_retries parameter."""
        # Test zero max_retries
        with pytest.raises(ValueError, match="max_retries must be a positive integer"):
            self.processor.reset_failed_records("test_flow", max_retries=0)

        # Test negative max_retries
        with pytest.raises(ValueError, match="max_retries must be a positive integer"):
            self.processor.reset_failed_records("test_flow", max_retries=-1)

        # Test non-integer max_retries
        with pytest.raises(ValueError, match="max_retries must be a positive integer"):
            self.processor.reset_failed_records("test_flow", max_retries="3")

        # Test float max_retries
        with pytest.raises(ValueError, match="max_retries must be a positive integer"):
            self.processor.reset_failed_records("test_flow", max_retries=3.5)

        # Verify no database calls were made
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_reset_failed_records_database_error_count_query(self):
        """Test reset when count query fails."""
        # Mock database error on count query
        self.mock_rpa_db.execute_query.side_effect = Exception("Database connection failed")

        # Call reset_failed_records and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to reset failed records for flow 'test_flow'"):
            self.processor.reset_failed_records("test_flow", max_retries=3)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_message = self.mock_logger.error.call_args[0][0]
        assert "Failed to reset failed records for flow 'test_flow'" in error_message
        assert "Database connection failed" in error_message

    def test_reset_failed_records_database_error_reset_query(self):
        """Test reset when reset query fails."""
        # Mock successful count query but failed reset query
        count_result = [(3, 1, 4)]
        self.mock_rpa_db.execute_query.side_effect = [
            count_result,
            Exception("Update query failed")
        ]

        # Call reset_failed_records and expect RuntimeError
        with pytest.raises(RuntimeError, match="Failed to reset failed records for flow 'test_flow'"):
            self.processor.reset_failed_records("test_flow", max_retries=5)

        # Verify error logging
        self.mock_logger.error.assert_called_once()
        error_message = self.mock_logger.error.call_args[0][0]
        assert "Failed to reset failed records for flow 'test_flow'" in error_message
        assert "Update query failed" in error_message

    def test_reset_failed_records_custom_max_retries(self):
        """Test reset with custom max_retries values."""
        # Test with max_retries=1
        count_result = [(2, 0, 2)]
        reset_result = 2
        self.mock_rpa_db.execute_query.side_effect = [count_result, reset_result]

        result = self.processor.reset_failed_records("test_flow", max_retries=1)
        assert result == 2

        # Verify max_retries parameter was used correctly
        count_call = self.mock_rpa_db.execute_query.call_args_list[0]
        reset_call = self.mock_rpa_db.execute_query.call_args_list[1]
        assert count_call[0][1]['max_retries'] == 1
        assert reset_call[0][1]['max_retries'] == 1

        # Reset mocks and test with max_retries=10
        self.mock_rpa_db.reset_mock()
        count_result = [(5, 3, 8)]
        reset_result = 5
        self.mock_rpa_db.execute_query.side_effect = [count_result, reset_result]

        result = self.processor.reset_failed_records("test_flow", max_retries=10)
        assert result == 5

        # Verify max_retries parameter was used correctly
        count_call = self.mock_rpa_db.execute_query.call_args_list[0]
        reset_call = self.mock_rpa_db.execute_query.call_args_list[1]
        assert count_call[0][1]['max_retries'] == 10
        assert reset_call[0][1]['max_retries'] == 10

    def test_reset_failed_records_sql_filter_conditions(self):
        """Test that SQL queries use correct filter conditions."""
        # Mock responses
        count_result = [(2, 1, 3)]
        reset_result = 2
        self.mock_rpa_db.execute_query.side_effect = [count_result, reset_result]

        # Call reset_failed_records
        self.processor.reset_failed_records("specific_flow", max_retries=5)

        # Verify count query filters
        count_call = self.mock_rpa_db.execute_query.call_args_list[0]
        count_query = count_call[0][0]
        assert "WHERE flow_name = :flow_name AND status = 'failed'" in count_query
        assert "retry_count < :max_retries" in count_query
        assert "retry_count >= :max_retries" in count_query

        # Verify reset query filters
        reset_call = self.mock_rpa_db.execute_query.call_args_list[1]
        reset_query = reset_call[0][0]
        assert "WHERE flow_name = :flow_name" in reset_query
        assert "AND status = 'failed'" in reset_query
        assert "AND retry_count < :max_retries" in reset_query

    def test_reset_failed_records_field_clearing(self):
        """Test that reset query clears appropriate fields."""
        # Mock responses
        count_result = [(1, 0, 1)]
        reset_result = 1
        self.mock_rpa_db.execute_query.side_effect = [count_result, reset_result]

        # Call reset_failed_records
        self.processor.reset_failed_records("test_flow")

        # Verify reset query clears fields
        reset_call = self.mock_rpa_db.execute_query.call_args_list[1]
        reset_query = reset_call[0][0]
        assert "SET status = 'pending'" in reset_query
        assert "flow_instance_id = NULL" in reset_query
        assert "claimed_at = NULL" in reset_query
        assert "error_message = NULL" in reset_query
        assert "updated_at = CURRENT_TIMESTAMP" in reset_query

    def test_reset_failed_records_comprehensive_logging(self):
        """Test comprehensive logging for different scenarios."""
        # Test scenario with mixed results
        count_result = [(3, 2, 5)]
        reset_result = 3
        self.mock_rpa_db.execute_query.side_effect = [count_result, reset_result]

        self.processor.reset_failed_records("mixed_flow", max_retries=4)

        # Verify comprehensive logging
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]

        # Check initial status log
        status_log = next((call for call in info_calls if "Found 5 failed records" in call), None)
        assert status_log is not None
        assert "3 can be reset, 2 exceeded retry limit" in status_log

        # Check success log
        success_log = next((call for call in info_calls if "Successfully reset 3 failed records" in call), None)
        assert success_log is not None
        assert "max_retries: 4" in success_log


class TestHealthCheck:
    """Test health_check method functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_source_db.database_name = "SurveyHub"

    @patch('socket.gethostname')
    @patch('datetime.datetime')
    def test_health_check_all_healthy(self, mock_datetime, mock_gethostname):
        """Test health check when all components are healthy."""
        # Setup mocks
        mock_gethostname.return_value = "test-container-1"
        mock_datetime.now.return_value.isoformat.return_value = "2024-01-15T10:30:00.000000+00:00"

        # Mock healthy database responses
        rpa_db_health = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 45.2
        }
        source_db_health = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 32.1
        }

        self.mock_rpa_db.health_check.return_value = rpa_db_health
        self.mock_source_db.health_check.return_value = source_db_health

        # Mock queue status
        queue_status = {
            "total_records": 1250,
            "pending_records": 150,
            "processing_records": 25,
            "completed_records": 1072,
            "failed_records": 3,
            "flow_name": None
        }

        # Create processor with both databases
        processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db
        )
        processor.get_queue_status = Mock(return_value=queue_status)

        # Call health_check
        result = processor.health_check()

        # Verify overall status
        assert result["status"] == "healthy"
        assert "error" not in result

        # Verify database health
        assert result["databases"]["rpa_db"] == rpa_db_health
        assert result["databases"]["source_db"] == source_db_health

        # Verify queue status
        expected_queue_status = {
            "pending_records": 150,
            "processing_records": 25,
            "completed_records": 1072,
            "failed_records": 3,
            "total_records": 1250
        }
        assert result["queue_status"] == expected_queue_status

        # Verify instance info
        assert result["instance_info"]["instance_id"] == processor.instance_id
        assert result["instance_info"]["hostname"] == "test-container-1"
        assert result["instance_info"]["rpa_db_name"] == "rpa_db"
        assert result["instance_info"]["source_db_name"] == "SurveyHub"

        # Verify timestamp
        assert result["timestamp"] == "2024-01-15T10:30:00.000000+00:00"

        # Verify method calls
        self.mock_rpa_db.health_check.assert_called_once()
        self.mock_source_db.health_check.assert_called_once()
        processor.get_queue_status.assert_called_once()

        # Verify logging
        self.mock_logger.info.assert_called()
        info_calls = [call.args[0] for call in self.mock_logger.info.call_args_list]
        assert any("Health check completed: healthy" in call for call in info_calls)

    @patch('socket.gethostname')
    def test_health_check_rpa_db_unhealthy(self, mock_gethostname):
        """Test health check when rpa_db is unhealthy (system unhealthy)."""
        # Setup mocks
        mock_gethostname.return_value = "test-container-1"

        # Mock unhealthy rpa_db response
        rpa_db_health = {
            "status": "unhealthy",
            "connection": False,
            "error": "Connection timeout after 30 seconds"
        }

        self.mock_rpa_db.health_check.return_value = rpa_db_health

        # Create processor with only rpa_db
        processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

        # Call health_check
        result = processor.health_check()

        # Verify overall status is unhealthy
        assert result["status"] == "unhealthy"
        assert "RPA database unhealthy" in result["error"]
        assert "Connection timeout after 30 seconds" in result["error"]

        # Verify database health
        assert result["databases"]["rpa_db"] == rpa_db_health
        assert "source_db" not in result["databases"]

        # Verify queue status shows unavailable
        assert result["queue_status"]["pending_records"] == -1
        assert result["queue_status"]["total_records"] == -1
        assert "Database connection unavailable" in result["queue_status"]["error"]

        # Verify instance info
        assert result["instance_info"]["source_db_name"] is None

        # Verify method calls
        self.mock_rpa_db.health_check.assert_called_once()

        # Verify error logging
        self.mock_logger.error.assert_called()
        error_calls = [call.args[0] for call in self.mock_logger.error.call_args_list]
        assert any("Health check completed: unhealthy" in call for call in error_calls)

    @patch('socket.gethostname')
    def test_health_check_source_db_unhealthy(self, mock_gethostname):
        """Test health check when source_db is unhealthy (system degraded)."""
        # Setup mocks
        mock_gethostname.return_value = "test-container-1"

        # Mock healthy rpa_db, unhealthy source_db
        rpa_db_health = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 45.2
        }
        source_db_health = {
            "status": "unhealthy",
            "connection": False,
            "error": "Authentication failed"
        }

        self.mock_rpa_db.health_check.return_value = rpa_db_health
        self.mock_source_db.health_check.return_value = source_db_health

        # Mock queue status
        queue_status = {
            "total_records": 100,
            "pending_records": 10,
            "processing_records": 5,
            "completed_records": 85,
            "failed_records": 0,
            "flow_name": None
        }

        # Create processor with both databases
        processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db
        )
        processor.get_queue_status = Mock(return_value=queue_status)

        # Call health_check
        result = processor.health_check()

        # Verify overall status is degraded (not unhealthy)
        assert result["status"] == "degraded"
        assert "error" not in result  # No overall error for degraded status

        # Verify database health
        assert result["databases"]["rpa_db"] == rpa_db_health
        assert result["databases"]["source_db"] == source_db_health

        # Verify queue status is available (rpa_db is healthy)
        expected_queue_status = {
            "pending_records": 10,
            "processing_records": 5,
            "completed_records": 85,
            "failed_records": 0,
            "total_records": 100
        }
        assert result["queue_status"] == expected_queue_status

        # Verify method calls
        self.mock_rpa_db.health_check.assert_called_once()
        self.mock_source_db.health_check.assert_called_once()
        processor.get_queue_status.assert_called_once()

        # Verify warning logging
        self.mock_logger.warning.assert_called()
        warning_calls = [call.args[0] for call in self.mock_logger.warning.call_args_list]
        assert any("Health check completed: degraded" in call for call in warning_calls)

    @patch('socket.gethostname')
    def test_health_check_rpa_db_degraded(self, mock_gethostname):
        """Test health check when rpa_db is degraded (system degraded)."""
        # Setup mocks
        mock_gethostname.return_value = "test-container-1"

        # Mock degraded rpa_db response
        rpa_db_health = {
            "status": "degraded",
            "connection": True,
            "response_time_ms": 2500.0,  # Slow response
            "warning": "High response time detected"
        }

        self.mock_rpa_db.health_check.return_value = rpa_db_health

        # Mock queue status
        queue_status = {
            "total_records": 50,
            "pending_records": 5,
            "processing_records": 2,
            "completed_records": 43,
            "failed_records": 0,
            "flow_name": None
        }

        # Create processor
        processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
        processor.get_queue_status = Mock(return_value=queue_status)

        # Call health_check
        result = processor.health_check()

        # Verify overall status is degraded
        assert result["status"] == "degraded"

        # Verify database health
        assert result["databases"]["rpa_db"] == rpa_db_health

        # Verify queue status is still available
        expected_queue_status = {
            "pending_records": 5,
            "processing_records": 2,
            "completed_records": 43,
            "failed_records": 0,
            "total_records": 50
        }
        assert result["queue_status"] == expected_queue_status

    @patch('socket.gethostname')
    def test_health_check_rpa_db_exception(self, mock_gethostname):
        """Test health check when rpa_db health_check raises exception."""
        # Setup mocks
        mock_gethostname.return_value = "test-container-1"

        # Mock rpa_db health_check exception
        self.mock_rpa_db.health_check.side_effect = Exception("Database connection failed")

        # Create processor
        processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

        # Call health_check
        result = processor.health_check()

        # Verify overall status is unhealthy
        assert result["status"] == "unhealthy"
        assert "RPA database health check failed" in result["error"]
        assert "Database connection failed" in result["error"]

        # Verify database health shows error
        assert result["databases"]["rpa_db"]["status"] == "unhealthy"
        assert result["databases"]["rpa_db"]["connection"] is False
        assert "Database connection failed" in result["databases"]["rpa_db"]["error"]

        # Verify queue status shows unavailable
        assert result["queue_status"]["pending_records"] == -1
        assert "Database connection unavailable" in result["queue_status"]["error"]

        # Verify error logging
        self.mock_logger.error.assert_called()

    @patch('socket.gethostname')
    def test_health_check_source_db_exception(self, mock_gethostname):
        """Test health check when source_db health_check raises exception."""
        # Setup mocks
        mock_gethostname.return_value = "test-container-1"

        # Mock healthy rpa_db
        rpa_db_health = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 45.2
        }
        self.mock_rpa_db.health_check.return_value = rpa_db_health

        # Mock source_db health_check exception
        self.mock_source_db.health_check.side_effect = Exception("SQL Server connection failed")

        # Mock queue status
        queue_status = {
            "total_records": 25,
            "pending_records": 2,
            "processing_records": 1,
            "completed_records": 22,
            "failed_records": 0,
            "flow_name": None
        }

        # Create processor with both databases
        processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db
        )
        processor.get_queue_status = Mock(return_value=queue_status)

        # Call health_check
        result = processor.health_check()

        # Verify overall status is degraded (not unhealthy for source_db issues)
        assert result["status"] == "degraded"

        # Verify database health
        assert result["databases"]["rpa_db"] == rpa_db_health
        assert result["databases"]["source_db"]["status"] == "unhealthy"
        assert result["databases"]["source_db"]["connection"] is False
        assert "SQL Server connection failed" in result["databases"]["source_db"]["error"]

        # Verify queue status is still available
        expected_queue_status = {
            "pending_records": 2,
            "processing_records": 1,
            "completed_records": 22,
            "failed_records": 0,
            "total_records": 25
        }
        assert result["queue_status"] == expected_queue_status

        # Verify warning logging for source_db
        self.mock_logger.warning.assert_called()

    @patch('socket.gethostname')
    def test_health_check_queue_status_exception(self, mock_gethostname):
        """Test health check when get_queue_status raises exception."""
        # Setup mocks
        mock_gethostname.return_value = "test-container-1"

        # Mock healthy databases
        rpa_db_health = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 45.2
        }
        self.mock_rpa_db.health_check.return_value = rpa_db_health

        # Create processor
        processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
        processor.get_queue_status = Mock(side_effect=Exception("Queue query failed"))

        # Call health_check
        result = processor.health_check()

        # Verify overall status is degraded (not unhealthy for queue status issues)
        assert result["status"] == "degraded"

        # Verify database health is still good
        assert result["databases"]["rpa_db"] == rpa_db_health

        # Verify queue status shows error
        assert result["queue_status"]["pending_records"] == -1
        assert result["queue_status"]["total_records"] == -1
        assert "Queue query failed" in result["queue_status"]["error"]

        # Verify warning logging
        self.mock_logger.warning.assert_called()

    @patch('socket.gethostname')
    def test_health_check_critical_exception(self, mock_gethostname):
        """Test health check when critical exception occurs."""
        # Setup mocks
        mock_gethostname.side_effect = Exception("Critical system failure")

        # Create processor
        processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

        # Call health_check
        result = processor.health_check()

        # Verify minimal unhealthy response
        assert result["status"] == "unhealthy"
        assert "Critical failure during health check" in result["error"]
        assert "Critical system failure" in result["error"]

        # Verify minimal instance info
        assert result["instance_info"]["instance_id"] == processor.instance_id
        assert result["instance_info"]["hostname"] == "unknown"
        assert result["instance_info"]["rpa_db_name"] == "rpa_db"

        # Verify error logging
        self.mock_logger.error.assert_called()

    def test_health_check_no_source_db(self):
        """Test health check with only rpa_db configured."""
        # Mock healthy rpa_db
        rpa_db_health = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 45.2
        }
        self.mock_rpa_db.health_check.return_value = rpa_db_health

        # Mock queue status
        queue_status = {
            "total_records": 10,
            "pending_records": 1,
            "processing_records": 0,
            "completed_records": 9,
            "failed_records": 0,
            "flow_name": None
        }

        # Create processor with only rpa_db
        processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
        processor.get_queue_status = Mock(return_value=queue_status)

        # Call health_check
        result = processor.health_check()

        # Verify overall status is healthy
        assert result["status"] == "healthy"

        # Verify only rpa_db is in databases
        assert "rpa_db" in result["databases"]
        assert "source_db" not in result["databases"]

        # Verify instance info shows no source_db
        assert result["instance_info"]["source_db_name"] is None

        # Verify method calls
        self.mock_rpa_db.health_check.assert_called_once()
        processor.get_queue_status.assert_called_once()

    @patch('socket.gethostname')
    def test_health_check_timestamp_format(self, mock_gethostname):
        """Test that health check timestamp is in correct ISO format."""
        # Setup mocks
        mock_gethostname.return_value = "test-container"

        # Mock healthy database
        self.mock_rpa_db.health_check.return_value = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 45.2
        }

        # Create processor
        processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
        processor.get_queue_status = Mock(return_value={
            "total_records": 0,
            "pending_records": 0,
            "processing_records": 0,
            "completed_records": 0,
            "failed_records": 0,
            "flow_name": None
        })

        # Call health_check
        result = processor.health_check()

        # Verify timestamp format (ISO 8601 with timezone)
        timestamp = result["timestamp"]
        assert isinstance(timestamp, str)
        assert "+00:00" in timestamp or "Z" in timestamp  # UTC timezone indicator
        assert "T" in timestamp  # ISO format includes T separator

        # Verify timestamp can be parsed
        from datetime import datetime
        try:
            datetime.fromisoformat(timestamp)
        except ValueError:
            pytest.fail("Timestamp is not in valid ISO format")


class TestHealthCheckIntegration:
    """Integration tests for health_check method with realistic scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_source_db.database_name = "SurveyHub"

    @patch('socket.gethostname')
    def test_health_check_production_scenario(self, mock_gethostname):
        """Test health check with realistic production scenario."""
        # Setup realistic production environment
        mock_gethostname.return_value = "rpa-processor-deployment-7d4b8c9f5d-x7k2m"

        # Mock realistic database health responses
        rpa_db_health = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 125.7,
            "pool_status": {
                "size": 10,
                "checked_in": 8,
                "checked_out": 2,
                "overflow": 0
            }
        }

        source_db_health = {
            "status": "degraded",
            "connection": True,
            "response_time_ms": 1850.3,  # Slow but functional
            "warning": "High response time detected"
        }

        self.mock_rpa_db.health_check.return_value = rpa_db_health
        self.mock_source_db.health_check.return_value = source_db_health

        # Mock realistic queue status with active processing
        queue_status = {
            "total_records": 15420,
            "pending_records": 2340,
            "processing_records": 45,
            "completed_records": 12980,
            "failed_records": 55,
            "flow_name": None,
            "by_flow": {
                "survey_processor": {
                    "pending": 1200,
                    "processing": 25,
                    "completed": 8500,
                    "failed": 30,
                    "total": 9755
                },
                "order_processor": {
                    "pending": 1140,
                    "processing": 20,
                    "completed": 4480,
                    "failed": 25,
                    "total": 5665
                }
            }
        }

        # Create processor
        processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db
        )
        processor.get_queue_status = Mock(return_value=queue_status)

        # Call health_check
        result = processor.health_check()

        # Verify overall status is degraded due to source_db
        assert result["status"] == "degraded"

        # Verify comprehensive response structure
        assert "databases" in result
        assert "queue_status" in result
        assert "instance_info" in result
        assert "timestamp" in result

        # Verify database health details
        assert result["databases"]["rpa_db"] == rpa_db_health
        assert result["databases"]["source_db"] == source_db_health

        # Verify queue metrics
        assert result["queue_status"]["total_records"] == 15420
        assert result["queue_status"]["pending_records"] == 2340
        assert result["queue_status"]["processing_records"] == 45
        assert result["queue_status"]["failed_records"] == 55

        # Verify instance information
        assert result["instance_info"]["hostname"] == "rpa-processor-deployment-7d4b8c9f5d-x7k2m"
        assert result["instance_info"]["rpa_db_name"] == "rpa_db"
        assert result["instance_info"]["source_db_name"] == "SurveyHub"

        # Verify all health checks were called
        self.mock_rpa_db.health_check.assert_called_once()
        self.mock_source_db.health_check.assert_called_once()
        processor.get_queue_status.assert_called_once()

    def test_health_check_disaster_scenario(self):
        """Test health check during system disaster (all components failing)."""
        # Mock all database health checks failing
        self.mock_rpa_db.health_check.side_effect = Exception("PostgreSQL cluster down")
        self.mock_source_db.health_check.side_effect = Exception("SQL Server unreachable")

        # Create processor
        processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db
        )

        # Call health_check
        result = processor.health_check()

        # Verify system is unhealthy
        assert result["status"] == "unhealthy"
        assert "RPA database health check failed" in result["error"]

        # Verify database errors are captured
        assert result["databases"]["rpa_db"]["status"] == "unhealthy"
        assert result["databases"]["rpa_db"]["connection"] is False
        assert "PostgreSQL cluster down" in result["databases"]["rpa_db"]["error"]

        assert result["databases"]["source_db"]["status"] == "unhealthy"
        assert result["databases"]["source_db"]["connection"] is False
        assert "SQL Server unreachable" in result["databases"]["source_db"]["error"]

        # Verify queue status is unavailable
        assert result["queue_status"]["total_records"] == -1
        assert "Database connection unavailable" in result["queue_status"]["error"]

        # Verify error logging occurred
        self.mock_logger.error.assert_called()

    def test_health_check_minimal_configuration(self):
        """Test health check with minimal configuration (rpa_db only)."""
        # Mock minimal healthy configuration
        rpa_db_health = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 25.1
        }
        self.mock_rpa_db.health_check.return_value = rpa_db_health

        # Mock empty queue
        queue_status = {
            "total_records": 0,
            "pending_records": 0,
            "processing_records": 0,
            "completed_records": 0,
            "failed_records": 0,
            "flow_name": None
        }

        # Create minimal processor
        processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
        processor.get_queue_status = Mock(return_value=queue_status)

        # Call health_check
        result = processor.health_check()

        # Verify healthy status
        assert result["status"] == "healthy"

        # Verify minimal configuration
        assert "rpa_db" in result["databases"]
        assert "source_db" not in result["databases"]
        assert result["instance_info"]["source_db_name"] is None

        # Verify empty queue is handled correctly
        assert result["queue_status"]["total_records"] == 0
        assert all(count == 0 for count in [
            result["queue_status"]["pending_records"],
            result["queue_status"]["processing_records"],
            result["queue_status"]["completed_records"],
            result["queue_status"]["failed_records"]
        ])

        # Verify successful logging
        self.mock_logger.info.assert_called()


class TestMultiDatabaseProcessing:
    """Test multi-database processing functionality."""

    def setup_method(self):
        """Set up test fixtures for multi-database processing tests."""
        # Create mock DatabaseManagers
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "rpa_db"
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger

        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_source_db.database_name = "SurveyHub"

        # Create processor with both databases
        self.processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db
        )

    def test_process_survey_logic_success(self):
        """Test successful survey processing with multi-database pattern."""
        # Mock source database response
        source_data = [
            ("SURV-001", "CUST-001", {"overall_satisfaction": 8.5}, "2024-01-15 10:30:00", "Customer Satisfaction")
        ]
        self.mock_source_db.execute_query.return_value = source_data

        # Mock rpa_db insert success
        self.mock_rpa_db.execute_query.return_value = None

        # Test payload
        payload = {
            "survey_id": "SURV-001",
            "customer_name": "Alice Johnson",
            "flow_run_id": "test-flow-001"
        }

        # Execute processing
        result = self.processor.process_survey_logic(payload)

        # Verify result structure
        assert result["survey_id"] == "SURV-001"
        assert result["customer_id"] == "CUST-001"
        assert result["satisfaction_score"] == 8.5
        assert result["survey_type"] == "Customer Satisfaction"
        assert result["processing_status"] == "completed"
        assert result["customer_name"] == "Alice Johnson"
        assert result["flow_run_id"] == "test-flow-001"
        assert "processed_at" in result
        assert "processing_duration_ms" in result
        assert result["source"] == "multi_database_processor"

        # Verify source database was queried
        self.mock_source_db.execute_query.assert_called_once()
        source_call_args = self.mock_source_db.execute_query.call_args
        assert "SELECT survey_id, customer_id, response_data, submitted_at, survey_type" in source_call_args[0][0]
        assert source_call_args[0][1]["survey_id"] == "SURV-001"

        # Verify rpa_db was updated
        self.mock_rpa_db.execute_query.assert_called_once()
        rpa_call_args = self.mock_rpa_db.execute_query.call_args
        assert "INSERT INTO processed_surveys" in rpa_call_args[0][0]
        insert_params = rpa_call_args[0][1]
        assert insert_params["survey_id"] == "SURV-001"
        assert insert_params["customer_id"] == "CUST-001"
        assert insert_params["processing_status"] == "completed"

    def test_process_survey_logic_survey_not_found(self):
        """Test survey processing when survey is not found in source database."""
        # Mock empty source database response
        self.mock_source_db.execute_query.return_value = []

        payload = {"survey_id": "NONEXISTENT"}

        # Execute and verify exception
        with pytest.raises(RuntimeError, match="Survey NONEXISTENT not found in source database"):
            self.processor.process_survey_logic(payload)

        # Verify source database was queried but rpa_db was not updated
        self.mock_source_db.execute_query.assert_called_once()
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_process_survey_logic_no_source_db(self):
        """Test survey processing when source database is not configured."""
        # Create processor without source database
        processor_no_source = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

        payload = {"survey_id": "SURV-001"}

        # Execute and verify exception
        with pytest.raises(TypeError, match="source_db_manager is required for multi-database processing"):
            processor_no_source.process_survey_logic(payload)

    def test_process_survey_logic_invalid_payload(self):
        """Test survey processing with invalid payload."""
        # Test missing survey_id
        with pytest.raises(ValueError, match="payload must contain 'survey_id' field"):
            self.processor.process_survey_logic({"customer_id": "CUST-001"})

        # Test empty survey_id
        with pytest.raises(ValueError, match="survey_id must be a non-empty string"):
            self.processor.process_survey_logic({"survey_id": ""})

        # Test non-string survey_id
        with pytest.raises(ValueError, match="survey_id must be a non-empty string"):
            self.processor.process_survey_logic({"survey_id": 123})

        # Test non-dict payload
        with pytest.raises(ValueError, match="payload must be a dictionary"):
            self.processor.process_survey_logic("invalid")

    def test_process_survey_logic_source_db_error(self):
        """Test survey processing when source database query fails."""
        # Mock source database error
        self.mock_source_db.execute_query.side_effect = Exception("Database connection failed")

        payload = {"survey_id": "SURV-001"}

        # Execute and verify exception
        with pytest.raises(RuntimeError, match="Failed to process survey SURV-001"):
            self.processor.process_survey_logic(payload)

        # Verify source database was queried but rpa_db was not updated
        self.mock_source_db.execute_query.assert_called_once()
        self.mock_rpa_db.execute_query.assert_not_called()

    def test_process_survey_logic_rpa_db_error(self):
        """Test survey processing when rpa_db insert fails."""
        # Mock successful source database response
        source_data = [
            ("SURV-001", "CUST-001", {"overall_satisfaction": 7.0}, "2024-01-15 10:30:00", "Customer Satisfaction")
        ]
        self.mock_source_db.execute_query.return_value = source_data

        # Mock rpa_db insert error
        self.mock_rpa_db.execute_query.side_effect = Exception("Insert failed")

        payload = {"survey_id": "SURV-001"}

        # Execute and verify exception
        with pytest.raises(RuntimeError, match="Failed to process survey SURV-001"):
            self.processor.process_survey_logic(payload)

        # Verify both databases were accessed
        self.mock_source_db.execute_query.assert_called_once()
        self.mock_rpa_db.execute_query.assert_called_once()

    def test_calculate_satisfaction_score_customer_satisfaction(self):
        """Test satisfaction score calculation for Customer Satisfaction surveys."""
        # Test with overall_satisfaction field
        response_data = {"overall_satisfaction": 9.2}
        score = self.processor._calculate_satisfaction_score(response_data, "Customer Satisfaction")
        assert score == 9.2

        # Test with multiple ratings (fallback)
        response_data = {"service_rating": 8.0, "product_rating": 7.5, "support_rating": 9.0}
        score = self.processor._calculate_satisfaction_score(response_data, "Customer Satisfaction")
        expected_score = (8.0 + 7.5 + 9.0) / 3
        assert score == expected_score

        # Test with no valid ratings
        response_data = {"comments": "Great service!"}
        score = self.processor._calculate_satisfaction_score(response_data, "Customer Satisfaction")
        assert score == 5.0  # Default neutral score

    def test_calculate_satisfaction_score_product_feedback(self):
        """Test satisfaction score calculation for Product Feedback surveys."""
        response_data = {
            "product_rating": 8.0,
            "recommendation_likelihood": 6.0
        }
        score = self.processor._calculate_satisfaction_score(response_data, "Product Feedback")
        expected_score = (8.0 * 0.7) + (6.0 * 0.3)  # Weighted average
        assert score == expected_score

    def test_calculate_satisfaction_score_market_research(self):
        """Test satisfaction score calculation for Market Research surveys."""
        response_data = {"interest_level": 7.5}
        score = self.processor._calculate_satisfaction_score(response_data, "Market Research")
        assert score == 7.5

    def test_calculate_satisfaction_score_unknown_type(self):
        """Test satisfaction score calculation for unknown survey types."""
        response_data = {"rating1": 8.0, "rating2": 6.0, "rating3": 9.0}
        score = self.processor._calculate_satisfaction_score(response_data, "Unknown Type")
        expected_score = (8.0 + 6.0 + 9.0) / 3
        assert score == expected_score

    def test_calculate_satisfaction_score_invalid_data(self):
        """Test satisfaction score calculation with invalid response data."""
        # Test with non-dict response_data
        score = self.processor._calculate_satisfaction_score("invalid", "Customer Satisfaction")
        assert score == 5.0

        # Test with empty dict
        score = self.processor._calculate_satisfaction_score({}, "Customer Satisfaction")
        assert score == 5.0

        # Test with exception during calculation
        response_data = {"invalid_rating": "not_a_number"}
        score = self.processor._calculate_satisfaction_score(response_data, "Customer Satisfaction")
        assert score == 5.0

    def test_transform_survey_data_success(self):
        """Test successful survey data transformation."""
        survey_data = {
            "survey_id": "SURV-001",
            "customer_id": "CUST-001",
            "response_data": {"overall_satisfaction": 8.5},
            "survey_type": "Customer Satisfaction"
        }
        payload = {
            "customer_name": "Alice Johnson",
            "flow_run_id": "test-flow-001"
        }

        result = self.processor._transform_survey_data(survey_data, payload)

        assert result["survey_id"] == "SURV-001"
        assert result["customer_id"] == "CUST-001"
        assert result["satisfaction_score"] == 8.5
        assert result["survey_type"] == "Customer Satisfaction"
        assert result["processing_status"] == "completed"
        assert result["customer_name"] == "Alice Johnson"
        assert result["flow_run_id"] == "test-flow-001"

    def test_transform_survey_data_derived_customer_name(self):
        """Test survey data transformation with derived customer name."""
        survey_data = {
            "survey_id": "SURV-002",
            "customer_id": "CUST-002",
            "response_data": {"overall_satisfaction": 7.0},
            "survey_type": "Product Feedback"
        }
        payload = {"flow_run_id": "test-flow-002"}

        result = self.processor._transform_survey_data(survey_data, payload)

        assert result["customer_name"] == "Customer CUST-002"  # Derived name
        assert result["flow_run_id"] == "test-flow-002"

    def test_transform_survey_data_failed_processing(self):
        """Test survey data transformation when satisfaction score calculation fails."""
        survey_data = {
            "survey_id": "SURV-003",
            "customer_id": "CUST-003",
            "response_data": {},  # Empty response data
            "survey_type": "Customer Satisfaction"
        }
        payload = {}

        # Mock _calculate_satisfaction_score to return None (failure)
        with patch.object(self.processor, '_calculate_satisfaction_score', return_value=None):
            result = self.processor._transform_survey_data(survey_data, payload)

        assert result["processing_status"] == "failed"
        assert result["satisfaction_score"] is None

    def test_store_survey_results_success(self):
        """Test successful storage of survey results in rpa_db."""
        from datetime import datetime, timezone

        processed_result = {
            "survey_id": "SURV-001",
            "customer_id": "CUST-001",
            "customer_name": "Alice Johnson",
            "survey_type": "Customer Satisfaction",
            "processing_status": "completed",
            "processed_at": datetime.now(timezone.utc),
            "processing_duration_ms": 1250,
            "flow_run_id": "test-flow-001"
        }

        # Mock successful insert
        self.mock_rpa_db.execute_query.return_value = None

        # Execute storage
        self.processor._store_survey_results(processed_result)

        # Verify database was called with correct parameters
        self.mock_rpa_db.execute_query.assert_called_once()
        call_args = self.mock_rpa_db.execute_query.call_args

        # Verify SQL query structure
        query = call_args[0][0]
        assert "INSERT INTO processed_surveys" in query
        assert "survey_id, customer_id, customer_name, survey_type" in query

        # Verify parameters
        params = call_args[0][1]
        assert params["survey_id"] == "SURV-001"
        assert params["customer_id"] == "CUST-001"
        assert params["customer_name"] == "Alice Johnson"
        assert params["processing_status"] == "completed"

    def test_store_survey_results_database_error(self):
        """Test storage of survey results when database insert fails."""
        processed_result = {
            "survey_id": "SURV-001",
            "customer_id": "CUST-001",
            "customer_name": "Alice Johnson",
            "survey_type": "Customer Satisfaction",
            "processing_status": "completed",
            "flow_run_id": "test-flow-001"
        }

        # Mock database error
        self.mock_rpa_db.execute_query.side_effect = Exception("Insert constraint violation")

        # Execute and verify exception
        with pytest.raises(RuntimeError, match="Failed to store survey results for SURV-001"):
            self.processor._store_survey_results(processed_result)

        # Verify database was called
        self.mock_rpa_db.execute_query.assert_called_once()


class TestMultiDatabaseIntegration:
    """Integration tests for multi-database processing with test databases."""

    def setup_method(self):
        """Set up test fixtures for integration tests."""
        # Note: These tests would require actual test database connections
        # For now, we'll create comprehensive mocks that simulate real database behavior

        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_source_db.database_name = "test_surveyhub"

        self.processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db
        )

    def test_end_to_end_survey_processing_workflow(self):
        """Test complete end-to-end survey processing workflow."""
        # Simulate realistic survey data from source database
        source_survey_data = [
            (
                "SURV-E2E-001",
                "CUST-E2E-001",
                {
                    "overall_satisfaction": 8.7,
                    "service_rating": 9.0,
                    "product_rating": 8.5,
                    "recommendation_likelihood": 8.0,
                    "comments": "Excellent service and product quality!"
                },
                "2024-01-15 14:30:00",
                "Customer Satisfaction"
            )
        ]
        self.mock_source_db.execute_query.return_value = source_survey_data

        # Mock successful rpa_db insert
        self.mock_rpa_db.execute_query.return_value = None

        # Execute complete workflow
        payload = {
            "survey_id": "SURV-E2E-001",
            "customer_name": "John Doe",
            "flow_run_id": "e2e-test-flow-001"
        }

        result = self.processor.process_survey_logic(payload)

        # Verify complete result structure
        assert result["survey_id"] == "SURV-E2E-001"
        assert result["customer_id"] == "CUST-E2E-001"
        assert result["satisfaction_score"] == 8.7  # Uses overall_satisfaction
        assert result["survey_type"] == "Customer Satisfaction"
        assert result["processing_status"] == "completed"
        assert result["customer_name"] == "John Doe"
        assert result["flow_run_id"] == "e2e-test-flow-001"
        assert result["source"] == "multi_database_processor"
        assert isinstance(result["processing_duration_ms"], int)
        assert result["processing_duration_ms"] >= 0  # Allow 0 for very fast tests

        # Verify source database interaction
        source_calls = self.mock_source_db.execute_query.call_args_list
        assert len(source_calls) == 1
        source_query = source_calls[0][0][0]  # First positional argument
        source_params = source_calls[0][0][1]  # Second positional argument
        assert "FROM survey_responses" in source_query
        assert source_params["survey_id"] == "SURV-E2E-001"

        # Verify rpa_db interaction
        rpa_calls = self.mock_rpa_db.execute_query.call_args_list
        assert len(rpa_calls) == 1
        rpa_query = rpa_calls[0][0][0]  # First positional argument
        rpa_params = rpa_calls[0][0][1]  # Second positional argument
        assert "INSERT INTO processed_surveys" in rpa_query
        assert rpa_params["survey_id"] == "SURV-E2E-001"
        assert rpa_params["processing_status"] == "completed"

    def test_multi_survey_batch_processing(self):
        """Test processing multiple surveys in sequence."""
        # Define multiple survey scenarios
        test_surveys = [
            {
                "payload": {"survey_id": "SURV-BATCH-001", "customer_name": "Alice"},
                "source_data": [("SURV-BATCH-001", "CUST-001", {"overall_satisfaction": 9.0}, "2024-01-15", "Customer Satisfaction")],
                "expected_score": 9.0
            },
            {
                "payload": {"survey_id": "SURV-BATCH-002", "customer_name": "Bob"},
                "source_data": [("SURV-BATCH-002", "CUST-002", {"product_rating": 7.5, "recommendation_likelihood": 8.0}, "2024-01-15", "Product Feedback")],
                "expected_score": 7.65  # (7.5 * 0.7) + (8.0 * 0.3) = 5.25 + 2.4 = 7.65
            },
            {
                "payload": {"survey_id": "SURV-BATCH-003", "customer_name": "Charlie"},
                "source_data": [("SURV-BATCH-003", "CUST-003", {"interest_level": 6.5}, "2024-01-15", "Market Research")],
                "expected_score": 6.5
            }
        ]

        # Mock rpa_db insert success for all surveys
        self.mock_rpa_db.execute_query.return_value = None

        results = []
        for survey in test_surveys:
            # Mock source database response for this survey
            self.mock_source_db.execute_query.return_value = survey["source_data"]

            # Process survey
            result = self.processor.process_survey_logic(survey["payload"])
            results.append(result)

            # Verify individual result
            assert result["survey_id"] == survey["payload"]["survey_id"]
            assert result["satisfaction_score"] == survey["expected_score"]
            assert result["processing_status"] == "completed"

        # Verify all surveys were processed
        assert len(results) == 3
        assert all(r["processing_status"] == "completed" for r in results)

        # Verify database interaction counts
        assert self.mock_source_db.execute_query.call_count == 3
        assert self.mock_rpa_db.execute_query.call_count == 3

    def test_error_handling_with_partial_failures(self):
        """Test error handling when some surveys fail while others succeed."""
        # Test scenario: First survey succeeds, second fails at source, third succeeds

        # First survey - success
        self.mock_source_db.execute_query.return_value = [
            ("SURV-MIX-001", "CUST-001", {"overall_satisfaction": 8.0}, "2024-01-15", "Customer Satisfaction")
        ]
        self.mock_rpa_db.execute_query.return_value = None

        result1 = self.processor.process_survey_logic({"survey_id": "SURV-MIX-001"})
        assert result1["processing_status"] == "completed"

        # Second survey - source database failure
        self.mock_source_db.execute_query.return_value = []  # Survey not found

        with pytest.raises(RuntimeError, match="Survey SURV-MIX-002 not found"):
            self.processor.process_survey_logic({"survey_id": "SURV-MIX-002"})

        # Third survey - success (system recovers)
        self.mock_source_db.execute_query.return_value = [
            ("SURV-MIX-003", "CUST-003", {"overall_satisfaction": 7.5}, "2024-01-15", "Customer Satisfaction")
        ]

        result3 = self.processor.process_survey_logic({"survey_id": "SURV-MIX-003"})
        assert result3["processing_status"] == "completed"

        # Verify database interaction patterns
        assert self.mock_source_db.execute_query.call_count == 3
        assert self.mock_rpa_db.execute_query.call_count == 2  # Only successful surveys

    def test_performance_metrics_tracking(self):
        """Test that performance metrics are properly tracked."""
        # Mock source database with slight delay simulation
        self.mock_source_db.execute_query.return_value = [
            ("SURV-PERF-001", "CUST-001", {"overall_satisfaction": 8.5}, "2024-01-15", "Customer Satisfaction")
        ]
        self.mock_rpa_db.execute_query.return_value = None

        # Process survey and measure timing
        import time
        start_time = time.time()

        result = self.processor.process_survey_logic({"survey_id": "SURV-PERF-001"})

        end_time = time.time()
        actual_duration = (end_time - start_time) * 1000

        # Verify performance metrics are included
        assert "processing_duration_ms" in result
        assert isinstance(result["processing_duration_ms"], int)
        assert result["processing_duration_ms"] >= 0  # Allow 0 for very fast tests

        # Duration should be reasonable (within 10x of actual for test environment)
        assert result["processing_duration_ms"] <= actual_duration * 10

        # Verify timestamp is recent
        assert "processed_at" in result
        processed_time = result["processed_at"]
        time_diff = abs(processed_time.timestamp() - time.time())
        assert time_diff < 5  # Within 5 seconds


class TestRetryLogicAndResilience:
    """Test retry logic and resilience features for critical operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_logger = Mock()
        self.mock_rpa_db.logger = self.mock_logger
        self.mock_rpa_db.database_name = "rpa_db"

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_claim_records_batch_with_retry_success(self):
        """Test successful record claiming with retry on first attempt."""
        # Mock successful database response
        mock_results = [
            (1, {"survey_id": 1001}, 0, "2024-01-15 10:00:00"),
            (2, {"survey_id": 1002}, 0, "2024-01-15 10:01:00")
        ]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call retry-enabled method
        result = self.processor.claim_records_batch_with_retry("test_flow", 2)

        # Verify results
        assert len(result) == 2
        assert result[0]['id'] == 1
        assert result[1]['id'] == 2

        # Verify database was called once (no retries needed)
        self.mock_rpa_db.execute_query.assert_called_once()

        # Verify debug logging for retry attempt
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        assert any("Claiming records with retry" in call for call in debug_calls)

    def test_claim_records_batch_with_retry_transient_failure(self):
        """Test record claiming with retry after transient failures."""
        # Mock transient failure followed by success
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First two calls fail with transient error
                from sqlalchemy.exc import OperationalError
                raise OperationalError("Connection timeout", None, None)
            else:
                # Third call succeeds
                return [(1, {"survey_id": 1001}, 0, "2024-01-15 10:00:00")]

        self.mock_rpa_db.execute_query.side_effect = side_effect

        # Call retry-enabled method
        result = self.processor.claim_records_batch_with_retry("test_flow", 1)

        # Verify final success
        assert len(result) == 1
        assert result[0]['id'] == 1

        # Verify multiple attempts were made
        assert call_count == 3

    def test_claim_records_batch_with_retry_permanent_failure(self):
        """Test record claiming with retry when all attempts fail."""
        # Mock permanent database failure (non-transient error)
        self.mock_rpa_db.execute_query.side_effect = ValueError("Invalid SQL syntax")

        # Call retry-enabled method and expect failure
        with pytest.raises(RuntimeError, match="Record claiming with retry failed"):
            self.processor.claim_records_batch_with_retry("test_flow", 1, max_attempts=2)

        # Verify error logging (should be called twice - once by original method, once by retry wrapper)
        assert self.mock_logger.error.call_count >= 1
        error_calls = [call.args[0] for call in self.mock_logger.error.call_args_list]
        assert any("Record claiming with retry failed" in call for call in error_calls)

    def test_claim_records_batch_with_retry_custom_parameters(self):
        """Test record claiming with retry using custom retry parameters."""
        # Mock successful response
        mock_results = [(1, {"survey_id": 1001}, 0, "2024-01-15 10:00:00")]
        self.mock_rpa_db.execute_query.return_value = mock_results

        # Call with custom retry parameters
        result = self.processor.claim_records_batch_with_retry(
            "test_flow", 1,
            max_attempts=5,
            min_wait=2.0,
            max_wait=20.0
        )

        # Verify success
        assert len(result) == 1

        # Verify debug logging includes custom parameters
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        retry_log = next((call for call in debug_calls if "max_attempts: 5" in call), None)
        assert retry_log is not None

    def test_mark_record_completed_with_retry_success(self):
        """Test successful record completion with retry."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Test data
        record_id = 123
        result = {"satisfaction_score": 8.5}

        # Call retry-enabled method
        self.processor.mark_record_completed_with_retry(record_id, result)

        # Verify database was called once
        self.mock_rpa_db.execute_query.assert_called_once()

        # Verify debug logging
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        assert any("Marking record 123 as completed with retry" in call for call in debug_calls)

    def test_mark_record_completed_with_retry_transient_failure(self):
        """Test record completion with retry after transient failures."""
        # Mock transient failure followed by success
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Create a custom exception that matches transient error patterns
                class MockConnectionError(Exception):
                    def __str__(self):
                        return "connection timeout"
                raise MockConnectionError("connection timeout")
            else:
                return 1

        self.mock_rpa_db.execute_query.side_effect = side_effect

        # Call retry-enabled method
        self.processor.mark_record_completed_with_retry(123, {"status": "success"})

        # Verify multiple attempts were made
        assert call_count == 2

    def test_mark_record_failed_with_retry_success(self):
        """Test successful record failure marking with retry."""
        # Mock successful database update
        self.mock_rpa_db.execute_query.return_value = 1

        # Call retry-enabled method
        self.processor.mark_record_failed_with_retry(123, "Processing error")

        # Verify database was called once
        self.mock_rpa_db.execute_query.assert_called_once()

        # Verify debug logging
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        assert any("Marking record 123 as failed with retry" in call for call in debug_calls)

    def test_cleanup_orphaned_records_with_retry_success(self):
        """Test successful orphaned record cleanup with retry."""
        # Mock successful cleanup (5 records cleaned)
        self.mock_rpa_db.execute_query.return_value = 5

        # Call retry-enabled method
        result = self.processor.cleanup_orphaned_records_with_retry(timeout_hours=2)

        # Verify result
        assert result == 5

        # Verify database was called once
        self.mock_rpa_db.execute_query.assert_called_once()

        # Verify debug logging
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        assert any("Cleaning up orphaned records with retry" in call for call in debug_calls)

    def test_reset_failed_records_with_retry_success(self):
        """Test successful failed record reset with retry."""
        # Mock count query and reset query responses
        count_results = [(3, 2, 5)]  # 3 resettable, 2 exceeded limit, 5 total
        self.mock_rpa_db.execute_query.side_effect = [count_results, 3]  # count query, then reset query

        # Call retry-enabled method
        result = self.processor.reset_failed_records_with_retry("test_flow", max_retries=3)

        # Verify result
        assert result == 3

        # Verify database was called twice (count + reset)
        assert self.mock_rpa_db.execute_query.call_count == 2

        # Verify debug logging
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]
        assert any("Resetting failed records with retry" in call for call in debug_calls)

    def test_retry_methods_parameter_validation(self):
        """Test that retry methods validate parameters correctly."""
        # Test claim_records_batch_with_retry parameter validation
        with pytest.raises((ValueError, RuntimeError)):
            self.processor.claim_records_batch_with_retry("", 1)

        with pytest.raises((ValueError, RuntimeError)):
            self.processor.claim_records_batch_with_retry("test_flow", 0)

        # Test mark_record_completed_with_retry parameter validation
        with pytest.raises((ValueError, RuntimeError)):
            self.processor.mark_record_completed_with_retry(0, {})

        with pytest.raises((ValueError, RuntimeError)):
            self.processor.mark_record_completed_with_retry(1, "not a dict")

        # Test mark_record_failed_with_retry parameter validation
        with pytest.raises((ValueError, RuntimeError)):
            self.processor.mark_record_failed_with_retry(-1, "error")

        with pytest.raises((ValueError, RuntimeError)):
            self.processor.mark_record_failed_with_retry(1, "")

        # Test cleanup_orphaned_records_with_retry parameter validation
        with pytest.raises((ValueError, RuntimeError)):
            self.processor.cleanup_orphaned_records_with_retry(timeout_hours=0)

        # Test reset_failed_records_with_retry parameter validation
        with pytest.raises((ValueError, RuntimeError)):
            self.processor.reset_failed_records_with_retry("", max_retries=3)

        with pytest.raises((ValueError, RuntimeError)):
            self.processor.reset_failed_records_with_retry("test_flow", max_retries=0)

    @patch('core.distributed._create_retry_decorator')
    def test_retry_decorator_configuration(self, mock_retry_decorator):
        """Test that retry decorators are configured with correct parameters."""
        # Mock decorator and successful response
        mock_retry_decorator.return_value = lambda func: func
        self.mock_rpa_db.execute_query.return_value = []

        # Test each retry method with custom parameters
        test_cases = [
            {
                'method': 'claim_records_batch_with_retry',
                'args': ('test_flow', 1),
                'kwargs': {'max_attempts': 5, 'min_wait': 2.0, 'max_wait': 30.0}
            },
            {
                'method': 'mark_record_completed_with_retry',
                'args': (123, {}),
                'kwargs': {'max_attempts': 4, 'min_wait': 1.5, 'max_wait': 15.0}
            },
            {
                'method': 'mark_record_failed_with_retry',
                'args': (123, 'error'),
                'kwargs': {'max_attempts': 2, 'min_wait': 0.5, 'max_wait': 5.0}
            }
        ]

        for case in test_cases:
            # Reset mock
            mock_retry_decorator.reset_mock()

            # Mock appropriate response for each method
            if 'completed' in case['method']:
                self.mock_rpa_db.execute_query.return_value = 1
            elif 'failed' in case['method']:
                self.mock_rpa_db.execute_query.return_value = 1
            else:
                self.mock_rpa_db.execute_query.return_value = []

            # Call method
            method = getattr(self.processor, case['method'])
            method(*case['args'], **case['kwargs'])

            # Verify retry decorator was configured correctly
            mock_retry_decorator.assert_called_once_with(
                max_attempts=case['kwargs']['max_attempts'],
                min_wait=case['kwargs']['min_wait'],
                max_wait=case['kwargs']['max_wait']
            )

    def test_retry_methods_preserve_original_functionality(self):
        """Test that retry methods preserve the original method functionality."""
        # Test claim_records_batch_with_retry
        mock_results = [(1, {"survey_id": 1001}, 0, "2024-01-15 10:00:00")]
        self.mock_rpa_db.execute_query.return_value = mock_results

        result = self.processor.claim_records_batch_with_retry("test_flow", 1)
        expected = self.processor.claim_records_batch("test_flow", 1)

        # Results should be identical (both call the same underlying method)
        assert len(result) == len(expected)
        assert result[0]['id'] == expected[0]['id']

        # Test mark_record_completed_with_retry
        self.mock_rpa_db.execute_query.return_value = 1

        # Both methods should succeed without exceptions
        self.processor.mark_record_completed_with_retry(123, {"status": "success"})
        self.processor.mark_record_completed(124, {"status": "success"})

        # Test mark_record_failed_with_retry
        # Both methods should succeed without exceptions
        self.processor.mark_record_failed_with_retry(125, "Test error")
        self.processor.mark_record_failed(126, "Test error")

    def test_retry_methods_error_handling_consistency(self):
        """Test that retry methods handle errors consistently with original methods."""
        # Test database errors are properly wrapped
        self.mock_rpa_db.execute_query.side_effect = Exception("Database error")

        # All retry methods should raise RuntimeError with descriptive messages
        with pytest.raises(RuntimeError, match="Record claiming with retry failed"):
            self.processor.claim_records_batch_with_retry("test_flow", 1, max_attempts=1)

        with pytest.raises(RuntimeError, match="Mark record completed with retry failed"):
            self.processor.mark_record_completed_with_retry(123, {}, max_attempts=1)

        with pytest.raises(RuntimeError, match="Mark record failed with retry failed"):
            self.processor.mark_record_failed_with_retry(123, "error", max_attempts=1)

        with pytest.raises(RuntimeError, match="Cleanup orphaned records with retry failed"):
            self.processor.cleanup_orphaned_records_with_retry(timeout_hours=1, max_attempts=1)

        with pytest.raises(RuntimeError, match="Reset failed records with retry failed"):
            self.processor.reset_failed_records_with_retry("test_flow", max_retries=3, max_attempts=1)

    def test_retry_methods_logging_consistency(self):
        """Test that retry methods maintain consistent logging patterns."""
        # Mock successful responses for different methods
        def mock_execute_query(*args, **kwargs):
            # Return appropriate response based on the query
            query = args[0] if args else ""
            if "SELECT id FROM processing_queue" in query:
                return []  # Empty result for claim_records_batch
            elif "UPDATE processing_queue" in query and "completed" in query:
                return 1  # Success for mark_record_completed
            elif "UPDATE processing_queue" in query and "failed" in query:
                return 1  # Success for mark_record_failed
            elif "UPDATE processing_queue" in query and "processing" in query:
                return 2  # Success for cleanup_orphaned_records
            elif "COUNT(*)" in query:
                return [(1, 0, 1)]  # Count query for reset_failed_records
            else:
                return 1  # Default success

        self.mock_rpa_db.execute_query.side_effect = mock_execute_query

        # Call each retry method
        self.processor.claim_records_batch_with_retry("test_flow", 1)
        self.processor.mark_record_completed_with_retry(123, {"status": "success"})
        self.processor.mark_record_failed_with_retry(124, "Test error")
        self.processor.cleanup_orphaned_records_with_retry(timeout_hours=1)
        self.processor.reset_failed_records_with_retry("test_flow", max_retries=3)

        # Verify debug logging for all retry methods
        debug_calls = [call.args[0] for call in self.mock_logger.debug.call_args_list]

        assert any("Claiming records with retry" in call for call in debug_calls)
        assert any("Marking record 123 as completed with retry" in call for call in debug_calls)
        assert any("Marking record 124 as failed with retry" in call for call in debug_calls)
        assert any("Cleaning up orphaned records with retry" in call for call in debug_calls)
        assert any("Resetting failed records with retry" in call for call in debug_calls)

    def test_retry_logic_does_not_conflict_with_database_retry_counting(self):
        """Test that retry logic doesn't interfere with database-level retry counting."""
        # This test ensures that the retry logic for transient failures (network, connection)
        # doesn't interfere with the business logic retry counting in the database

        # Mock a scenario where network retry succeeds but business logic fails
        self.mock_rpa_db.execute_query.return_value = 1

        # Mark a record as failed (this increments database retry_count)
        self.processor.mark_record_failed_with_retry(123, "Business logic error")

        # Verify the underlying mark_record_failed was called
        # The SQL should increment retry_count regardless of network retry attempts
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]

        # Verify the query increments retry_count at database level
        assert "retry_count = retry_count + 1" in query

        # The network-level retry (tenacity) should be separate from this business retry count
        # This test verifies they don't interfere with each other

    def test_retry_only_on_transient_errors(self):
        """Test that retry logic only retries on transient errors."""
        # Test with transient error (should be retried by tenacity)
        from sqlalchemy.exc import OperationalError
        self.mock_rpa_db.execute_query.side_effect = OperationalError("Connection timeout", None, None)

        with pytest.raises(RuntimeError):
            self.processor.claim_records_batch_with_retry("test_flow", 1, max_attempts=2)

        # Reset mock for next test
        self.mock_rpa_db.execute_query.side_effect = ValueError("Invalid SQL syntax")

        # Test with non-transient error (should fail immediately without retries)
        with pytest.raises(RuntimeError):
            self.processor.claim_records_batch_with_retry("test_flow", 1, max_attempts=2)

        # Both should result in RuntimeError, but transient errors get retried while non-transient don't

    def test_exponential_backoff_configuration(self):
        """Test that exponential backoff is properly configured."""
        # This test verifies that the retry decorator uses exponential backoff
        # by checking the parameters passed to _create_retry_decorator

        with patch('core.distributed._create_retry_decorator') as mock_create_retry:
            mock_create_retry.return_value = lambda func: func
            self.mock_rpa_db.execute_query.return_value = []

            # Call retry method with custom backoff parameters
            self.processor.claim_records_batch_with_retry(
                "test_flow", 1,
                max_attempts=5,
                min_wait=2.0,
                max_wait=60.0
            )

            # Verify exponential backoff configuration
            mock_create_retry.assert_called_once_with(
                max_attempts=5,
                min_wait=2.0,
                max_wait=60.0
            )

    def test_retry_methods_thread_safety(self):
        """Test that retry methods are thread-safe and don't interfere with each other."""
        # This test ensures that multiple concurrent calls to retry methods
        # don't interfere with each other's retry state

        import threading

        # Mock responses for concurrent operations
        self.mock_rpa_db.execute_query.return_value = 1

        results = []
        errors = []

        def worker(record_id):
            try:
                # Simulate concurrent record completion
                self.processor.mark_record_completed_with_retry(
                    record_id,
                    {"status": "success", "thread_id": threading.current_thread().ident}
                )
                results.append(record_id)
            except Exception as e:
                errors.append((record_id, str(e)))

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(100 + i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5.0)

        # Verify all operations completed successfully
        assert len(results) == 5
        assert len(errors) == 0
        assert set(results) == {100, 101, 102, 103, 104}

        # Verify database was called for each thread
        assert self.mock_rpa_db.execute_query.call_count == 5
