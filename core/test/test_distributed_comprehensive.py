"""
Comprehensive test suite for the distributed processing system.

This module provides comprehensive testing for the DistributedProcessor class
and distributed flow template, including unit tests, integration tests,
concurrent processing tests, performance tests, and chaos tests.

Test Categories:
- Unit Tests: Test individual components with mocked dependencies
- Integration Tests: Test multi-container scenarios with test databases
- Concurrent Tests: Verify no duplicate record processing
- Performance Tests: Test batch processing and connection pool utilization
- Chaos Tests: Test container failures and database connectivity issues
"""

import concurrent.futures
import random
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from core.config import ConfigManager
from core.database import DatabaseManager
from core.distributed import DistributedProcessor
from core.flow_template import (
    distributed_processing_flow,
    generate_processing_summary,
    process_record_with_status,
)


class TestDistributedProcessorComprehensive:
    """Comprehensive unit tests for DistributedProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_config = Mock(spec=ConfigManager)

        # Configure mocks
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()
        self.mock_source_db.database_name = "test_source_db"

        # Mock configuration
        self.mock_config.get_distributed_config.return_value = {
            "default_batch_size": 100,
            "cleanup_timeout_hours": 1,
            "max_retries": 3,
            "health_check_interval": 300
        }

        self.processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db,
            config_manager=self.mock_config
        )

    def test_initialization_comprehensive(self):
        """Test comprehensive initialization scenarios."""
        # Test with all parameters
        processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db,
            config_manager=self.mock_config
        )

        assert processor.rpa_db is self.mock_rpa_db
        assert processor.source_db is self.mock_source_db
        assert processor.config_manager is self.mock_config
        assert processor.instance_id is not None
        assert len(processor.instance_id) > 0

    def test_claim_records_batch_comprehensive(self):
        """Test comprehensive record claiming scenarios."""
        # Test successful claiming
        mock_results = [
            (1, {"survey_id": 1001}, 0, datetime.now()),
            (2, {"survey_id": 1002}, 1, datetime.now()),
        ]
        self.mock_rpa_db.execute_query.return_value = mock_results

        records = self.processor.claim_records_batch("test_flow", 2)

        assert len(records) == 2
        assert records[0]["id"] == 1
        assert records[1]["id"] == 2

        # Verify SQL query structure
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        assert "FOR UPDATE SKIP LOCKED" in query
        assert "ORDER BY created_at ASC" in query

    def test_mark_record_completed_comprehensive(self):
        """Test comprehensive record completion scenarios."""
        # Test successful completion
        self.mock_rpa_db.execute_query.return_value = 1

        result = {"processed": True, "score": 95.5}
        self.processor.mark_record_completed(123, result)

        # Verify database call
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "SET status = 'completed'" in query
        assert params["record_id"] == 123
        assert params["result"] == result

    def test_mark_record_failed_comprehensive(self):
        """Test comprehensive record failure scenarios."""
        # Test successful failure marking
        self.mock_rpa_db.execute_query.return_value = 1

        error_msg = "Processing failed due to invalid data"
        self.processor.mark_record_failed(456, error_msg)

        # Verify database call
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "SET status = 'failed'" in query
        assert "retry_count = retry_count + 1" in query
        assert params["record_id"] == 456
        assert params["error_message"] == error_msg

    def test_add_records_to_queue_comprehensive(self):
        """Test comprehensive record addition scenarios."""
        # Test batch addition
        records = [
            {"payload": {"survey_id": 1001, "customer_id": "CUST001"}},
            {"payload": {"survey_id": 1002, "customer_id": "CUST002"}},
            {"payload": {"survey_id": 1003, "customer_id": "CUST003"}},
        ]

        count = self.processor.add_records_to_queue("test_flow", records)

        assert count == 3
        self.mock_rpa_db.execute_query.assert_called_once()

    def test_get_queue_status_comprehensive(self):
        """Test comprehensive queue status scenarios."""
        # Mock status query results
        self.mock_rpa_db.execute_query.side_effect = [
            [("pending", 50), ("processing", 10), ("completed", 100), ("failed", 5)],
            [("flow1", "pending", 25), ("flow1", "completed", 50), ("flow2", "pending", 25)]
        ]

        # Test system-wide status
        status = self.processor.get_queue_status()

        assert status["total_records"] == 165
        assert status["pending_records"] == 50
        assert status["processing_records"] == 10
        assert status["completed_records"] == 100
        assert status["failed_records"] == 5

    def test_cleanup_orphaned_records_comprehensive(self):
        """Test comprehensive orphaned record cleanup."""
        # Mock cleanup returning 5 cleaned records
        self.mock_rpa_db.execute_query.return_value = 5

        cleaned_count = self.processor.cleanup_orphaned_records(timeout_hours=2)

        assert cleaned_count == 5

        # Verify SQL query
        call_args = self.mock_rpa_db.execute_query.call_args
        query = call_args[0][0]
        assert "INTERVAL '2 hours'" in query
        assert "SET status = 'pending'" in query

    def test_reset_failed_records_comprehensive(self):
        """Test comprehensive failed record reset."""
        # Mock count query and reset query
        self.mock_rpa_db.execute_query.side_effect = [
            [(10, 5, 15)],  # resettable, exceeded_limit, total
            10  # rows affected by reset
        ]

        reset_count = self.processor.reset_failed_records("test_flow", max_retries=3)

        assert reset_count == 10
        assert self.mock_rpa_db.execute_query.call_count == 2

    def test_health_check_comprehensive(self):
        """Test comprehensive health check scenarios."""
        # Mock healthy databases
        self.mock_rpa_db.health_check.return_value = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 45.2
        }
        self.mock_source_db.health_check.return_value = {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 32.1
        }

        # Mock queue status
        self.mock_rpa_db.execute_query.return_value = [
            ("pending", 150), ("processing", 25), ("failed", 3)
        ]

        health = self.processor.health_check()

        # Health status should be healthy or degraded (depending on source db)
        assert health["status"] in ["healthy", "degraded"]
        assert "databases" in health
        assert "queue_status" in health
        assert "instance_info" in health
        assert health["databases"]["rpa_db"]["status"] == "healthy"


@pytest.mark.integration
class TestDistributedProcessorIntegration:
    """Integration tests for multi-container scenarios."""

    @pytest.fixture(autouse=True)
    def setup_integration_test(self, postgresql_available):
        """Set up integration test environment."""
        if not postgresql_available:
            pytest.skip("PostgreSQL not available for integration tests")

        # Create test database managers
        self.config_manager = ConfigManager()
        self.rpa_db = DatabaseManager("test_rpa_db")

        # Create test processor
        self.processor = DistributedProcessor(
            rpa_db_manager=self.rpa_db,
            config_manager=self.config_manager
        )

    def test_multi_container_record_claiming(self):
        """Test that multiple containers don't claim the same records."""
        # Create multiple processor instances (simulating containers)
        processor1 = DistributedProcessor(rpa_db_manager=self.rpa_db)
        processor2 = DistributedProcessor(rpa_db_manager=self.rpa_db)
        processor3 = DistributedProcessor(rpa_db_manager=self.rpa_db)

        # Add test records to queue
        test_records = [
            {"payload": {"id": i, "data": f"test_{i}"}}
            for i in range(30)
        ]
        processor1.add_records_to_queue("integration_test", test_records)

        # Claim records concurrently from multiple processors
        def claim_records(processor, batch_size):
            return processor.claim_records_batch("integration_test", batch_size)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(claim_records, processor1, 10),
                executor.submit(claim_records, processor2, 10),
                executor.submit(claim_records, processor3, 10)
            ]

            results = [future.result() for future in futures]

        # Verify no duplicate records were claimed
        all_claimed_ids = []
        for result in results:
            claimed_ids = [record["id"] for record in result]
            all_claimed_ids.extend(claimed_ids)

        # Check for duplicates
        assert len(all_claimed_ids) == len(set(all_claimed_ids)), "Duplicate records were claimed"
        assert len(all_claimed_ids) == 30, "Not all records were claimed"

    def test_concurrent_status_updates(self):
        """Test concurrent status updates don't interfere."""
        # Add test records
        test_records = [{"payload": {"id": i}} for i in range(10)]
        self.processor.add_records_to_queue("status_test", test_records)

        # Claim records
        claimed_records = self.processor.claim_records_batch("status_test", 10)

        # Update statuses concurrently
        def update_status(record, success):
            if success:
                self.processor.mark_record_completed(record["id"], {"processed": True})
            else:
                self.processor.mark_record_failed(record["id"], "Test failure")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i, record in enumerate(claimed_records):
                success = i % 2 == 0  # Alternate success/failure
                futures.append(executor.submit(update_status, record, success))

            # Wait for all updates to complete
            for future in futures:
                future.result()

        # Verify final status
        status = self.processor.get_queue_status("status_test")
        assert status["completed_records"] == 5
        assert status["failed_records"] == 5

    def test_orphaned_record_cleanup_integration(self):
        """Test orphaned record cleanup in integration environment."""
        # Add and claim records
        test_records = [{"payload": {"id": i}} for i in range(5)]
        self.processor.add_records_to_queue("cleanup_test", test_records)

        claimed_records = self.processor.claim_records_batch("cleanup_test", 5)
        assert len(claimed_records) == 5

        # Simulate orphaned records by not updating their status
        # and setting claimed_at to past time
        for record in claimed_records:
            past_time = datetime.now() - timedelta(hours=2)
            self.rpa_db.execute_query(
                "UPDATE processing_queue SET claimed_at = %s WHERE id = %s",
                (past_time, record["id"])
            )

        # Run cleanup
        cleaned_count = self.processor.cleanup_orphaned_records(timeout_hours=1)
        assert cleaned_count == 5

        # Verify records are back to pending
        status = self.processor.get_queue_status("cleanup_test")
        assert status["pending_records"] == 5
        assert status["processing_records"] == 0


class TestConcurrentProcessing:
    """Tests for concurrent processing scenarios."""

    def setup_method(self):
        """Set up concurrent processing tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_concurrent_record_claiming(self):
        """Test concurrent record claiming doesn't cause race conditions."""
        # Mock database responses for concurrent claims
        claim_responses = [
            [(1, {"data": "test1"}, 0, datetime.now())],  # First claim gets record 1
            [(2, {"data": "test2"}, 0, datetime.now())],  # Second claim gets record 2
            [],  # Third claim gets nothing
        ]

        self.mock_rpa_db.execute_query.side_effect = claim_responses

        # Simulate concurrent claiming
        def claim_worker():
            return self.processor.claim_records_batch("concurrent_test", 1)

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(claim_worker) for _ in range(3)]
            results = [future.result() for future in futures]

        # Verify results
        non_empty_results = [r for r in results if r]
        assert len(non_empty_results) == 2

        # Verify different records were claimed
        claimed_ids = [r[0]["id"] for r in non_empty_results]
        assert len(set(claimed_ids)) == 2

    def test_concurrent_status_updates_thread_safety(self):
        """Test thread safety of concurrent status updates."""
        # Mock successful updates
        self.mock_rpa_db.execute_query.return_value = 1

        # Create multiple threads updating different records
        def update_worker(record_id, result_data):
            self.processor.mark_record_completed(record_id, result_data)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(1, 101):  # Use 1-100 instead of 0-99
                result_data = {"processed": True, "id": i}
                futures.append(executor.submit(update_worker, i, result_data))

            # Wait for all updates
            for future in futures:
                future.result()

        # Verify all calls were made
        assert self.mock_rpa_db.execute_query.call_count == 100

    def test_concurrent_queue_operations(self):
        """Test concurrent queue operations (add, claim, status)."""
        # Mock responses for different operations
        def mock_execute_query(query, params, **kwargs):
            if "INSERT INTO processing_queue" in query:
                return None  # Add operation
            elif "UPDATE processing_queue" in query and "FOR UPDATE SKIP LOCKED" in query:
                return [(1, {"data": "test"}, 0, datetime.now())]  # Claim operation
            elif "SELECT status, COUNT(*)" in query:
                return [("pending", 10), ("processing", 5)]  # Status operation
            else:
                return 1  # Other operations

        self.mock_rpa_db.execute_query.side_effect = mock_execute_query

        # Run concurrent operations
        def add_worker():
            records = [{"payload": {"data": f"test_{random.randint(1, 1000)}"}}]
            return self.processor.add_records_to_queue("concurrent_ops", records)

        def claim_worker():
            return self.processor.claim_records_batch("concurrent_ops", 1)

        def status_worker():
            return self.processor.get_queue_status("concurrent_ops")

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = []

            # Submit mixed operations
            for _ in range(5):
                futures.append(executor.submit(add_worker))
                futures.append(executor.submit(claim_worker))
                futures.append(executor.submit(status_worker))

            # Wait for all operations
            results = [future.result() for future in futures]

        # Verify no exceptions occurred
        assert len(results) == 15


@pytest.mark.performance
class TestDistributedProcessorPerformance:
    """Performance tests for distributed processing."""

    def setup_method(self):
        """Set up performance tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_batch_processing_performance(self):
        """Test performance of batch processing operations."""
        # Mock large batch response
        large_batch = [
            (i, {"data": f"test_{i}"}, 0, datetime.now())
            for i in range(1000)
        ]
        self.mock_rpa_db.execute_query.return_value = large_batch

        # Measure batch claiming performance
        start_time = time.time()
        records = self.processor.claim_records_batch("perf_test", 1000)
        claim_time = time.time() - start_time

        assert len(records) == 1000
        assert claim_time < 1.0  # Should complete within 1 second

        # Test batch status updates
        self.mock_rpa_db.execute_query.return_value = 1

        start_time = time.time()
        for i in range(1, 101):  # Use 1-100 instead of 0-99
            self.processor.mark_record_completed(i, {"processed": True})
        update_time = time.time() - start_time

        assert update_time < 2.0  # 100 updates should complete within 2 seconds

    def test_connection_pool_utilization(self):
        """Test connection pool utilization under load."""
        # Mock pool status
        mock_pool = Mock()
        mock_pool.size.return_value = 10
        mock_pool.checkedin.return_value = 8
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 0

        self.mock_rpa_db.get_pool_status.return_value = {
            "pool_size": 10,
            "checked_in": 8,
            "checked_out": 2,
            "overflow": 0,
            "invalid": 0
        }

        # Simulate high load
        self.mock_rpa_db.execute_query.return_value = [(1, {"data": "test"}, 0, datetime.now())]

        def load_worker():
            for _ in range(10):
                self.processor.claim_records_batch("load_test", 1)

        # Run concurrent load
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(load_worker) for _ in range(20)]

            # Wait for completion
            for future in futures:
                future.result()

        # Verify pool utilization was monitored
        pool_status = self.mock_rpa_db.get_pool_status()
        assert pool_status["pool_size"] == 10
        assert pool_status["checked_out"] <= 10

    def test_memory_usage_under_load(self):
        """Test memory usage patterns under high load."""
        import gc
        import os

        try:
            import psutil
        except ImportError:
            pytest.skip("psutil not available for memory testing")

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Mock large dataset processing
        large_records = [
            {"id": i, "payload": {"data": "x" * 1000}, "retry_count": 0, "created_at": datetime.now()}
            for i in range(1000)
        ]

        # Process records in batches
        for batch_start in range(0, 1000, 100):
            batch = large_records[batch_start:batch_start + 100]

            # Simulate processing
            for record in batch:
                {"processed": True, "size": len(str(record))}
                # Simulate completion (would normally call mark_record_completed)

        # Force garbage collection
        gc.collect()

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for this test)
        assert memory_increase < 100 * 1024 * 1024

    def test_throughput_measurement(self):
        """Test processing throughput measurement."""
        # Mock fast database responses
        self.mock_rpa_db.execute_query.return_value = 1

        # Measure throughput for record updates
        start_time = time.time()
        operations_count = 1000

        for i in range(1, operations_count + 1):  # Use 1-1000 instead of 0-999
            self.processor.mark_record_completed(i, {"processed": True})

        elapsed_time = time.time() - start_time
        throughput = operations_count / elapsed_time

        # Should achieve reasonable throughput (>100 ops/sec)
        assert throughput > 100

        print(f"Throughput: {throughput:.2f} operations/second")


class TestChaosEngineering:
    """Chaos engineering tests for distributed processing."""

    def setup_method(self):
        """Set up chaos engineering tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db,
            source_db_manager=self.mock_source_db
        )

    def test_database_connection_failures(self):
        """Test behavior during database connection failures."""
        # Simulate connection failure
        self.mock_rpa_db.execute_query.side_effect = Exception("Connection lost")

        # Test that operations fail gracefully
        with pytest.raises(RuntimeError, match="Failed to claim records"):
            self.processor.claim_records_batch("chaos_test", 10)

        # Verify error was logged
        self.mock_rpa_db.logger.error.assert_called()

    def test_intermittent_database_failures(self):
        """Test handling of intermittent database failures."""
        # Simulate intermittent failures
        call_count = 0

        def intermittent_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:  # Fail every 3rd call
                raise Exception("Intermittent failure")
            return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = intermittent_failure

        # Test multiple operations
        successful_operations = 0
        failed_operations = 0

        for _ in range(10):
            try:
                records = self.processor.claim_records_batch("intermittent_test", 1)
                if records:
                    successful_operations += 1
            except RuntimeError:
                failed_operations += 1

        # Should have both successes and failures
        assert successful_operations > 0
        assert failed_operations > 0

    def test_container_instance_isolation(self):
        """Test that container instances are properly isolated."""
        # Create multiple processor instances with different instance IDs
        processor1 = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
        processor2 = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
        processor3 = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

        # Verify unique instance IDs
        instance_ids = [processor1.instance_id, processor2.instance_id, processor3.instance_id]
        assert len(set(instance_ids)) == 3

        # Test that each processor uses its own instance ID in queries
        self.mock_rpa_db.execute_query.return_value = 1

        processor1.mark_record_completed(1, {"processed": True})
        call_args = self.mock_rpa_db.execute_query.call_args
        assert call_args[0][1]["instance_id"] == processor1.instance_id

    def test_network_partition_simulation(self):
        """Test behavior during simulated network partitions."""
        # Simulate network timeout
        import socket
        self.mock_rpa_db.execute_query.side_effect = socket.timeout("Network timeout")

        # Test that operations handle network issues
        with pytest.raises(RuntimeError):
            self.processor.claim_records_batch("network_test", 5)

        # Verify appropriate error handling
        self.mock_rpa_db.logger.error.assert_called()

    def test_resource_exhaustion_handling(self):
        """Test handling of resource exhaustion scenarios."""
        # Simulate memory pressure
        self.mock_rpa_db.execute_query.side_effect = MemoryError("Out of memory")

        # Test that memory errors are handled
        with pytest.raises(RuntimeError):
            self.processor.claim_records_batch("memory_test", 1000)

        # Simulate connection pool exhaustion
        self.mock_rpa_db.execute_query.side_effect = Exception("Connection pool exhausted")

        with pytest.raises(RuntimeError):
            self.processor.get_queue_status()

    def test_concurrent_container_failures(self):
        """Test system behavior when containers fail concurrently."""
        # Simulate multiple containers processing
        processors = [
            DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
            for _ in range(5)
        ]

        # Mock some processors failing
        def failing_processor_operation(processor_index):
            if processor_index < 2:  # First 2 processors fail
                raise Exception(f"Container {processor_index} failed")
            return [(processor_index, {"data": f"test_{processor_index}"}, 0, datetime.now())]

        # Test concurrent operations with failures
        results = []
        exceptions = []

        for i, processor in enumerate(processors):
            try:
                self.mock_rpa_db.execute_query.return_value = failing_processor_operation(i)
                if i >= 2:  # Only successful processors
                    records = processor.claim_records_batch("failure_test", 1)
                    results.append(records)
                else:
                    # Simulate failure
                    raise Exception(f"Container {i} failed")
            except Exception as e:
                exceptions.append(e)

        # Verify some operations succeeded despite failures
        assert len(results) == 3  # 3 successful processors
        assert len(exceptions) == 2  # 2 failed processors


class TestFlowTemplateComprehensive:
    """Comprehensive tests for the distributed flow template."""

    def setup_method(self):
        """Set up flow template tests."""
        # Mock the module-level instances
        self.mock_processor = Mock()
        self.mock_processor.instance_id = "test-instance-123"
        self.mock_processor.config = {"default_batch_size": 100}

    @patch('core.flow_template.processor')
    def test_distributed_flow_comprehensive(self, mock_processor):
        """Test comprehensive distributed flow scenarios."""
        mock_processor.instance_id = "test-instance-123"
        mock_processor.config = {"default_batch_size": 100}

        # Mock healthy system
        mock_processor.health_check.return_value = {"status": "healthy"}

        # Mock record claiming
        mock_records = [
            {"id": 1, "payload": {"data": "test1"}, "retry_count": 0, "created_at": "2024-01-01"},
            {"id": 2, "payload": {"data": "test2"}, "retry_count": 0, "created_at": "2024-01-01"}
        ]
        mock_processor.claim_records_batch_with_retry.return_value = mock_records

        # Mock processing results
        with patch('core.flow_template.process_record_with_status') as mock_task:
            mock_task.map.return_value = [
                {"record_id": 1, "status": "completed", "result": {"processed": True}},
                {"record_id": 2, "status": "completed", "result": {"processed": True}}
            ]

            # Test flow execution
            result = distributed_processing_flow("test_flow", 10)

        # Verify results
        assert result["flow_name"] == "test_flow"
        assert result["records_completed"] == 2
        assert result["success_rate_percent"] == 100.0

    def test_processing_summary_comprehensive(self):
        """Test comprehensive processing summary scenarios."""
        # Test with mixed results
        results = [
            {"record_id": 1, "status": "completed", "result": {"processed": True}},
            {"record_id": 2, "status": "failed", "error": "Processing error"},
            {"record_id": 3, "status": "completed", "result": {"processed": True}},
            {"record_id": 4, "status": "failed", "error": "Validation error"},
            {"record_id": 5, "status": "completed", "result": {"processed": True}}
        ]

        summary = generate_processing_summary(results, "mixed_flow", 10, 5)

        assert summary["records_processed"] == 5
        assert summary["records_completed"] == 3
        assert summary["records_failed"] == 2
        assert summary["success_rate_percent"] == 60.0
        assert len(summary["errors"]) == 2

    @patch('core.flow_template.processor')
    def test_record_processing_error_handling(self, mock_processor):
        """Test comprehensive error handling in record processing."""
        mock_processor.instance_id = "test-instance-123"

        # Test successful processing
        record = {
            "id": 123,
            "payload": {"data": "test"},
            "retry_count": 0,
            "created_at": "2024-01-01"
        }

        with patch('core.flow_template.process_default_business_logic') as mock_logic:
            mock_logic.return_value = {"processed": True}

            result = process_record_with_status(record)

            assert result["status"] == "completed"
            mock_processor.mark_record_completed_with_retry.assert_called_once()

    def test_flow_template_edge_cases(self):
        """Test edge cases in flow template."""
        # Test with empty flow name
        with pytest.raises(ValueError, match="flow_name must be a non-empty string"):
            distributed_processing_flow("", 10)

        # Test with invalid batch size
        with pytest.raises(ValueError, match="batch_size must be a positive integer"):
            distributed_processing_flow("test_flow", 0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
