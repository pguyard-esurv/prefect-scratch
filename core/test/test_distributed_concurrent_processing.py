"""
Concurrent processing tests for distributed processing system.

This module focuses specifically on testing concurrent processing scenarios
to verify that no duplicate record processing occurs when multiple containers
or threads are processing records simultaneously.
"""

import concurrent.futures
import random
import threading
import time
from datetime import datetime
from unittest.mock import Mock

import pytest

from core.database import DatabaseManager
from core.distributed import DistributedProcessor


class TestConcurrentRecordClaiming:
    """Test concurrent record claiming scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        # Create multiple processor instances (simulating containers)
        self.processors = [
            DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
            for _ in range(5)
        ]

    def test_no_duplicate_record_claiming(self):
        """Test that multiple processors don't claim the same records."""
        # Create a pool of available record IDs
        available_records = list(range(1, 101))  # 100 records
        claimed_records = set()
        claim_lock = threading.Lock()

        def mock_claim_query(query, params, **kwargs):
            """Mock database query that simulates atomic claiming."""
            batch_size = params.get('batch_size', 1)
            params.get('instance_id')

            with claim_lock:
                # Simulate atomic claiming - take records from available pool
                claimed_batch = []
                for _ in range(min(batch_size, len(available_records))):
                    if available_records:
                        record_id = available_records.pop(0)
                        claimed_records.add(record_id)
                        claimed_batch.append((
                            record_id,
                            {"data": f"test_{record_id}"},
                            0,
                            datetime.now()
                        ))

                return claimed_batch

        self.mock_rpa_db.execute_query.side_effect = mock_claim_query

        # Run concurrent claiming
        def claim_worker(processor):
            claimed = []
            for _ in range(10):  # Each processor tries to claim 10 times
                try:
                    records = processor.claim_records_batch("concurrent_test", 2)
                    claimed.extend([r["id"] for r in records])
                    time.sleep(0.001)  # Small delay to increase contention
                except Exception:
                    pass  # Ignore errors for this test
            return claimed

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(claim_worker, processor)
                for processor in self.processors
            ]

            results = [future.result() for future in futures]

        # Verify no duplicates across all processors
        all_claimed = []
        for result in results:
            all_claimed.extend(result)

        # Check for duplicates
        assert len(all_claimed) == len(set(all_claimed)), "Duplicate records were claimed"
        assert len(claimed_records) == len(all_claimed), "Mismatch in claimed record tracking"

    def test_concurrent_claiming_with_different_batch_sizes(self):
        """Test concurrent claiming with varying batch sizes."""
        available_records = list(range(1, 51))  # 50 records
        claimed_records = []
        claim_lock = threading.Lock()

        def mock_claim_with_batch_size(query, params, **kwargs):
            batch_size = params.get('batch_size', 1)

            with claim_lock:
                claimed_batch = []
                for _ in range(min(batch_size, len(available_records))):
                    if available_records:
                        record_id = available_records.pop(0)
                        claimed_records.append(record_id)
                        claimed_batch.append((
                            record_id,
                            {"data": f"test_{record_id}"},
                            0,
                            datetime.now()
                        ))
                return claimed_batch

        self.mock_rpa_db.execute_query.side_effect = mock_claim_with_batch_size

        # Different batch sizes for different processors
        batch_sizes = [1, 3, 5, 7, 10]

        def claim_with_batch_size(processor, batch_size):
            claimed = []
            for _ in range(5):  # 5 attempts per processor
                records = processor.claim_records_batch("batch_test", batch_size)
                claimed.extend([r["id"] for r in records])
                time.sleep(0.002)
            return claimed

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(claim_with_batch_size, self.processors[i], batch_sizes[i])
                for i in range(5)
            ]

            results = [future.result() for future in futures]

        # Verify all records were claimed exactly once
        all_claimed = []
        for result in results:
            all_claimed.extend(result)

        assert len(all_claimed) == len(set(all_claimed))
        assert len(all_claimed) == 50  # All records should be claimed

    def test_high_contention_scenario(self):
        """Test behavior under high contention with many processors."""
        # Create more processors for high contention
        processors = [
            DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
            for _ in range(20)
        ]

        available_records = list(range(1, 21))  # Only 20 records for 20 processors
        claimed_records = []
        claim_lock = threading.Lock()

        def mock_high_contention_claim(query, params, **kwargs):
            with claim_lock:
                if available_records:
                    record_id = available_records.pop(0)
                    claimed_records.append(record_id)
                    return [(record_id, {"data": f"test_{record_id}"}, 0, datetime.now())]
                return []  # No records available

        self.mock_rpa_db.execute_query.side_effect = mock_high_contention_claim

        # All processors try to claim at the same time
        def claim_single_record(processor):
            try:
                records = processor.claim_records_batch("contention_test", 1)
                return [r["id"] for r in records]
            except Exception:
                return []

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [
                executor.submit(claim_single_record, processor)
                for processor in processors
            ]

            results = [future.result() for future in futures]

        # Count successful claims
        successful_claims = [r for r in results if r]
        total_claimed = sum(len(r) for r in successful_claims)

        # Should have exactly 20 successful claims (one per record)
        assert total_claimed == 20
        assert len(successful_claims) == 20


class TestConcurrentStatusUpdates:
    """Test concurrent status update scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_concurrent_completion_updates(self):
        """Test concurrent record completion updates."""
        # Mock successful updates
        self.mock_rpa_db.execute_query.return_value = 1

        # Track update calls
        update_calls = []
        update_lock = threading.Lock()

        def track_updates(query, params, **kwargs):
            with update_lock:
                if "SET status = 'completed'" in query:
                    update_calls.append(params["record_id"])
            return 1

        self.mock_rpa_db.execute_query.side_effect = track_updates

        # Concurrent completion updates
        def complete_record(record_id):
            result = {"processed": True, "timestamp": datetime.now().isoformat()}
            self.processor.mark_record_completed(record_id, result)
            return record_id

        record_ids = list(range(1, 101))  # 100 records

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(complete_record, record_id)
                for record_id in record_ids
            ]

            completed_ids = [future.result() for future in futures]

        # Verify all updates were processed
        assert len(update_calls) == 100
        assert set(update_calls) == set(record_ids)
        assert len(completed_ids) == 100

    def test_concurrent_failure_updates(self):
        """Test concurrent record failure updates."""
        # Mock successful updates
        self.mock_rpa_db.execute_query.return_value = 1

        # Track failure updates
        failure_calls = []
        failure_lock = threading.Lock()

        def track_failures(query, params, **kwargs):
            with failure_lock:
                if "SET status = 'failed'" in query:
                    failure_calls.append({
                        "record_id": params["record_id"],
                        "error": params["error_message"]
                    })
            return 1

        self.mock_rpa_db.execute_query.side_effect = track_failures

        # Concurrent failure updates
        def fail_record(record_id):
            error_msg = f"Processing failed for record {record_id}"
            self.processor.mark_record_failed(record_id, error_msg)
            return record_id

        record_ids = list(range(1, 51))  # 50 records

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(fail_record, record_id)
                for record_id in record_ids
            ]

            [future.result() for future in futures]

        # Verify all failure updates were processed
        assert len(failure_calls) == 50
        failed_record_ids = [call["record_id"] for call in failure_calls]
        assert set(failed_record_ids) == set(record_ids)

    def test_mixed_concurrent_updates(self):
        """Test mixed concurrent completion and failure updates."""
        # Track different types of updates
        completion_calls = []
        failure_calls = []
        update_lock = threading.Lock()

        def track_mixed_updates(query, params, **kwargs):
            with update_lock:
                if "SET status = 'completed'" in query:
                    completion_calls.append(params["record_id"])
                elif "SET status = 'failed'" in query:
                    failure_calls.append(params["record_id"])
            return 1

        self.mock_rpa_db.execute_query.side_effect = track_mixed_updates

        # Mixed update operations
        def update_record(record_id, should_succeed):
            if should_succeed:
                result = {"processed": True}
                self.processor.mark_record_completed(record_id, result)
                return ("completed", record_id)
            else:
                error_msg = f"Error processing record {record_id}"
                self.processor.mark_record_failed(record_id, error_msg)
                return ("failed", record_id)

        # Create mixed workload (50% success, 50% failure)
        tasks = []
        for i in range(1, 101):
            should_succeed = i % 2 == 0
            tasks.append((i, should_succeed))

        # Shuffle to randomize execution order
        random.shuffle(tasks)

        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            futures = [
                executor.submit(update_record, record_id, should_succeed)
                for record_id, should_succeed in tasks
            ]

            results = [future.result() for future in futures]

        # Verify results
        completed_results = [r for r in results if r[0] == "completed"]
        failed_results = [r for r in results if r[0] == "failed"]

        assert len(completed_results) == 50
        assert len(failed_results) == 50
        assert len(completion_calls) == 50
        assert len(failure_calls) == 50


class TestConcurrentQueueOperations:
    """Test concurrent queue management operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_concurrent_record_addition(self):
        """Test concurrent record addition to queue."""
        # Track additions
        added_records = []
        add_lock = threading.Lock()

        def track_additions(query, params, **kwargs):
            with add_lock:
                if "INSERT INTO processing_queue" in query:
                    # Extract flow_name and count from query
                    flow_name = params.get("flow_name")
                    if flow_name:
                        added_records.append(flow_name)
            return None

        self.mock_rpa_db.execute_query.side_effect = track_additions

        # Concurrent addition operations
        def add_records_worker(worker_id):
            records = [
                {"payload": {"worker_id": worker_id, "record_id": i}}
                for i in range(10)
            ]
            flow_name = f"worker_{worker_id}_flow"
            count = self.processor.add_records_to_queue(flow_name, records)
            return (worker_id, count)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [
                executor.submit(add_records_worker, worker_id)
                for worker_id in range(8)
            ]

            results = [future.result() for future in futures]

        # Verify all workers completed successfully
        assert len(results) == 8
        for _worker_id, count in results:
            assert count == 10

    def test_concurrent_status_queries(self):
        """Test concurrent queue status queries."""
        # Mock status responses
        def mock_status_query(query, params, **kwargs):
            if "SELECT status, COUNT(*)" in query:
                return [
                    ("pending", random.randint(10, 50)),
                    ("processing", random.randint(1, 10)),
                    ("completed", random.randint(50, 200)),
                    ("failed", random.randint(0, 5))
                ]
            return []

        self.mock_rpa_db.execute_query.side_effect = mock_status_query

        # Concurrent status queries
        def status_query_worker(flow_name):
            status = self.processor.get_queue_status(flow_name)
            return status["total_records"]

        flow_names = [f"flow_{i}" for i in range(20)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(status_query_worker, flow_name)
                for flow_name in flow_names
            ]

            results = [future.result() for future in futures]

        # Verify all queries completed
        assert len(results) == 20
        assert all(isinstance(total, int) and total >= 0 for total in results)

    def test_mixed_concurrent_operations(self):
        """Test mixed concurrent operations (add, claim, status, update)."""
        # Track operation types
        operations = []
        op_lock = threading.Lock()

        def track_operations(query, params, **kwargs):
            with op_lock:
                if "INSERT INTO processing_queue" in query:
                    operations.append("add")
                elif "FOR UPDATE SKIP LOCKED" in query:
                    operations.append("claim")
                    return [(1, {"data": "test"}, 0, datetime.now())]
                elif "SELECT status, COUNT(*)" in query:
                    operations.append("status")
                    return [("pending", 10), ("processing", 2)]
                elif "SET status = 'completed'" in query:
                    operations.append("complete")
                elif "SET status = 'failed'" in query:
                    operations.append("fail")
            return 1

        self.mock_rpa_db.execute_query.side_effect = track_operations

        # Mixed operation workers
        def add_worker():
            records = [{"payload": {"data": "test"}}]
            self.processor.add_records_to_queue("mixed_test", records)
            return "add"

        def claim_worker():
            self.processor.claim_records_batch("mixed_test", 1)
            return "claim"

        def status_worker():
            self.processor.get_queue_status("mixed_test")
            return "status"

        def complete_worker():
            self.processor.mark_record_completed(1, {"processed": True})
            return "complete"

        def fail_worker():
            self.processor.mark_record_failed(2, "Test error")
            return "fail"

        # Submit mixed operations
        workers = [add_worker, claim_worker, status_worker, complete_worker, fail_worker]

        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = []
            for _ in range(30):  # 30 total operations
                worker = random.choice(workers)
                futures.append(executor.submit(worker))

            results = [future.result() for future in futures]

        # Verify operations completed
        assert len(results) == 30
        assert len(operations) >= 30  # Some operations might trigger multiple queries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
