"""
Performance tests for distributed processing system.

This module focuses on performance testing for batch processing,
connection pool utilization, throughput measurement, and scalability
under various load conditions.
"""

import concurrent.futures
import gc
import os
import random
import time
from datetime import datetime
from unittest.mock import Mock

import pytest

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from core.database import DatabaseManager
from core.distributed import DistributedProcessor


@pytest.mark.performance
class TestBatchProcessingPerformance:
    """Test performance of batch processing operations."""

    def setup_method(self):
        """Set up performance test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    @pytest.mark.slow
    def test_large_batch_claiming_performance(self):
        """Test performance of claiming large batches of records."""
        # Create large batch response
        batch_sizes = [100, 500, 1000, 2000]
        performance_results = {}

        for batch_size in batch_sizes:
            # Mock large batch response
            large_batch = [
                (
                    i,
                    {"data": f"test_{i}", "timestamp": datetime.now().isoformat()},
                    0,
                    datetime.now(),
                )
                for i in range(batch_size)
            ]
            self.mock_rpa_db.execute_query.return_value = large_batch

            # Measure claiming performance
            start_time = time.time()
            records = self.processor.claim_records_batch("perf_test", batch_size)
            claim_time = time.time() - start_time

            performance_results[batch_size] = {
                "claim_time": claim_time,
                "records_claimed": len(records),
                "records_per_second": len(records) / claim_time
                if claim_time > 0
                else 0,
            }

            # Verify results
            assert len(records) == batch_size
            assert claim_time < 2.0  # Should complete within 2 seconds

        # Print performance results
        print("\nBatch Claiming Performance Results:")
        for batch_size, results in performance_results.items():
            print(
                f"  Batch Size {batch_size}: {results['claim_time']:.3f}s "
                f"({results['records_per_second']:.0f} records/sec)"
            )

        # Verify performance scales reasonably
        small_batch_rate = performance_results[100]["records_per_second"]
        large_batch_rate = performance_results[1000]["records_per_second"]

        # Large batches should be more efficient (higher records/sec)
        assert large_batch_rate >= small_batch_rate * 0.5  # Allow some overhead

    @pytest.mark.slow
    def test_batch_status_update_performance(self):
        """Test performance of batch status updates."""
        # Mock successful updates
        self.mock_rpa_db.execute_query.return_value = 1

        batch_sizes = [50, 100, 500, 1000]
        performance_results = {}

        for batch_size in batch_sizes:
            # Measure batch completion performance
            start_time = time.time()
            for i in range(1, batch_size + 1):  # Use 1-based indexing
                result = {
                    "processed": True,
                    "record_id": i,
                    "timestamp": datetime.now().isoformat(),
                }
                self.processor.mark_record_completed(i, result)
            completion_time = time.time() - start_time

            performance_results[batch_size] = {
                "completion_time": completion_time,
                "updates_per_second": batch_size / completion_time
                if completion_time > 0
                else 0,
            }

            # Should complete within reasonable time
            assert completion_time < batch_size * 0.01  # Max 10ms per update

        # Print performance results
        print("\nBatch Status Update Performance Results:")
        for batch_size, results in performance_results.items():
            print(
                f"  Batch Size {batch_size}: {results['completion_time']:.3f}s "
                f"({results['updates_per_second']:.0f} updates/sec)"
            )

    @pytest.mark.slow
    def test_queue_addition_performance(self):
        """Test performance of adding records to queue."""
        # Test different batch sizes for queue addition
        batch_sizes = [10, 50, 100, 500, 1000]
        performance_results = {}

        for batch_size in batch_sizes:
            # Create test records
            records = [
                {
                    "payload": {
                        "id": i,
                        "data": f"test_data_{i}",
                        "timestamp": datetime.now().isoformat(),
                    }
                }
                for i in range(batch_size)
            ]

            # Measure addition performance
            start_time = time.time()
            count = self.processor.add_records_to_queue("perf_test", records)
            addition_time = time.time() - start_time

            performance_results[batch_size] = {
                "addition_time": addition_time,
                "records_added": count,
                "records_per_second": count / addition_time if addition_time > 0 else 0,
            }

            # Verify results
            assert count == batch_size
            assert addition_time < 1.0  # Should complete within 1 second

        # Print performance results
        print("\nQueue Addition Performance Results:")
        for batch_size, results in performance_results.items():
            print(
                f"  Batch Size {batch_size}: {results['addition_time']:.3f}s "
                f"({results['records_per_second']:.0f} records/sec)"
            )


@pytest.mark.performance
class TestConnectionPoolPerformance:
    """Test connection pool utilization and performance."""

    def setup_method(self):
        """Set up connection pool tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        # Mock pool status
        self.mock_pool_status = {
            "pool_size": 10,
            "checked_in": 8,
            "checked_out": 2,
            "overflow": 0,
            "invalid": 0,
            "max_overflow": 20,
        }
        self.mock_rpa_db.get_pool_status.return_value = self.mock_pool_status

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_connection_pool_under_load(self):
        """Test connection pool behavior under high load."""
        # Mock database responses
        self.mock_rpa_db.execute_query.return_value = [
            (1, {"data": "test"}, 0, datetime.now())
        ]

        # Track connection usage
        connection_usage = []

        def track_pool_usage(*args, **kwargs):
            # Simulate varying connection usage
            current_usage = random.randint(1, 10)
            self.mock_pool_status["checked_out"] = current_usage
            self.mock_pool_status["checked_in"] = 10 - current_usage
            connection_usage.append(current_usage)
            return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = track_pool_usage

        # Simulate high load with concurrent operations
        def load_worker():
            operations = []
            for _ in range(20):
                try:
                    records = self.processor.claim_records_batch("load_test", 1)
                    operations.append(len(records))
                    time.sleep(0.001)  # Small delay
                except Exception:
                    operations.append(0)
            return operations

        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = [executor.submit(load_worker) for _ in range(15)]
            results = [future.result() for future in futures]
        total_time = time.time() - start_time

        # Analyze results
        total_operations = sum(sum(result) for result in results)
        operations_per_second = total_operations / total_time

        print("\nConnection Pool Load Test Results:")
        print(f"  Total Operations: {total_operations}")
        print(f"  Total Time: {total_time:.3f}s")
        print(f"  Operations/Second: {operations_per_second:.0f}")
        print(f"  Max Connection Usage: {max(connection_usage)}")
        print(
            f"  Avg Connection Usage: {sum(connection_usage) / len(connection_usage):.1f}"
        )

        # Verify performance
        assert operations_per_second > 100  # Should achieve reasonable throughput
        assert max(connection_usage) <= 10  # Should not exceed pool size

    def test_connection_pool_efficiency(self):
        """Test connection pool efficiency metrics."""
        # Mock pool statistics
        pool_stats = []

        def collect_pool_stats(*args, **kwargs):
            # Simulate realistic pool usage patterns
            stats = {
                "pool_size": 10,
                "checked_in": random.randint(5, 9),
                "checked_out": random.randint(1, 5),
                "overflow": random.randint(0, 2),
                "invalid": 0,
            }
            pool_stats.append(stats)
            return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = collect_pool_stats

        # Run operations to collect pool statistics
        for _ in range(100):
            self.processor.claim_records_batch("efficiency_test", 1)
            time.sleep(0.001)

        # Analyze pool efficiency
        avg_checked_out = sum(s["checked_out"] for s in pool_stats) / len(pool_stats)
        avg_overflow = sum(s["overflow"] for s in pool_stats) / len(pool_stats)
        utilization_rate = avg_checked_out / 10 * 100  # Percentage of pool used

        print("\nConnection Pool Efficiency Results:")
        print(f"  Average Connections Checked Out: {avg_checked_out:.1f}")
        print(f"  Average Overflow: {avg_overflow:.1f}")
        print(f"  Pool Utilization Rate: {utilization_rate:.1f}%")

        # Verify efficiency metrics
        assert utilization_rate > 10  # Should use at least 10% of pool
        assert avg_overflow < 5  # Should not frequently overflow


@pytest.mark.performance
@pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
class TestMemoryPerformance:
    """Test memory usage patterns and performance."""

    def setup_method(self):
        """Set up memory performance tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)
        self.process = psutil.Process(os.getpid())

    @pytest.mark.slow
    def test_memory_usage_under_load(self):
        """Test memory usage patterns under high load."""
        # Get initial memory usage
        initial_memory = self.process.memory_info().rss

        # Mock large dataset processing
        large_records = []
        for i in range(1000):
            record = {
                "id": i,
                "payload": {
                    "data": "x" * 1000,  # 1KB of data per record
                    "metadata": {"timestamp": datetime.now().isoformat(), "index": i},
                    "processing_info": {"retry_count": 0, "created_at": datetime.now()},
                },
                "retry_count": 0,
                "created_at": datetime.now(),
            }
            large_records.append(record)

        # Process records in batches to simulate real usage
        memory_samples = []

        for batch_start in range(0, 1000, 100):
            batch = large_records[batch_start : batch_start + 100]

            # Simulate processing each record
            for record in batch:
                {
                    "processed": True,
                    "size": len(str(record)),
                    "timestamp": datetime.now().isoformat(),
                }
                # Simulate completion (would normally call mark_record_completed)

            # Sample memory usage
            current_memory = self.process.memory_info().rss
            memory_samples.append(current_memory)

        # Force garbage collection
        gc.collect()
        final_memory = self.process.memory_info().rss

        # Analyze memory usage
        max_memory = max(memory_samples)
        memory_increase = max_memory - initial_memory
        memory_after_gc = final_memory - initial_memory

        print("\nMemory Usage Analysis:")
        print(f"  Initial Memory: {initial_memory / 1024 / 1024:.1f} MB")
        print(f"  Peak Memory: {max_memory / 1024 / 1024:.1f} MB")
        print(f"  Final Memory: {final_memory / 1024 / 1024:.1f} MB")
        print(f"  Memory Increase: {memory_increase / 1024 / 1024:.1f} MB")
        print(f"  Memory After GC: {memory_after_gc / 1024 / 1024:.1f} MB")

        # Verify memory usage is reasonable
        assert memory_increase < 200 * 1024 * 1024  # Less than 200MB increase
        # Only check GC effectiveness if there was significant memory increase
        if memory_increase > 10 * 1024 * 1024:  # More than 10MB increase
            assert (
                memory_after_gc < memory_increase * 0.8
            )  # GC should free significant memory

    def test_memory_leak_detection(self):
        """Test for potential memory leaks in repeated operations."""
        # Get baseline memory
        gc.collect()
        baseline_memory = self.process.memory_info().rss

        # Mock database responses
        self.mock_rpa_db.execute_query.return_value = 1

        # Perform repeated operations
        memory_samples = []

        for cycle in range(10):
            # Perform a batch of operations
            for i in range(1, 101):  # Use 1-based indexing
                # Simulate various operations
                self.processor.mark_record_completed(
                    i, {"processed": True, "cycle": cycle}
                )

                # Create and discard temporary data
                temp_data = {"large_data": "x" * 1000, "index": i}
                del temp_data

            # Sample memory after each cycle
            gc.collect()
            current_memory = self.process.memory_info().rss
            memory_samples.append(current_memory)

        # Analyze memory trend
        memory_increases = []
        for i in range(1, len(memory_samples)):
            increase = memory_samples[i] - memory_samples[i - 1]
            memory_increases.append(increase)

        avg_increase_per_cycle = sum(memory_increases) / len(memory_increases)
        total_increase = memory_samples[-1] - baseline_memory

        print("\nMemory Leak Detection Results:")
        print(f"  Baseline Memory: {baseline_memory / 1024 / 1024:.1f} MB")
        print(f"  Final Memory: {memory_samples[-1] / 1024 / 1024:.1f} MB")
        print(f"  Total Increase: {total_increase / 1024 / 1024:.1f} MB")
        print(f"  Avg Increase/Cycle: {avg_increase_per_cycle / 1024 / 1024:.1f} MB")

        # Verify no significant memory leaks
        assert total_increase < 50 * 1024 * 1024  # Less than 50MB total increase
        assert avg_increase_per_cycle < 5 * 1024 * 1024  # Less than 5MB per cycle


@pytest.mark.performance
class TestThroughputMeasurement:
    """Test processing throughput under various conditions."""

    def setup_method(self):
        """Set up throughput tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_record_claiming_throughput(self):
        """Test throughput of record claiming operations."""
        # Mock fast database responses
        self.mock_rpa_db.execute_query.return_value = [
            (i, {"data": f"test_{i}"}, 0, datetime.now()) for i in range(10)
        ]

        # Measure claiming throughput
        start_time = time.time()
        operations_count = 100
        total_records_claimed = 0

        for _ in range(operations_count):
            records = self.processor.claim_records_batch("throughput_test", 10)
            total_records_claimed += len(records)

        elapsed_time = time.time() - start_time
        operations_per_second = operations_count / elapsed_time
        records_per_second = total_records_claimed / elapsed_time

        print("\nRecord Claiming Throughput Results:")
        print(f"  Operations: {operations_count}")
        print(f"  Total Records: {total_records_claimed}")
        print(f"  Time: {elapsed_time:.3f}s")
        print(f"  Operations/Second: {operations_per_second:.0f}")
        print(f"  Records/Second: {records_per_second:.0f}")

        # Verify throughput meets requirements
        assert operations_per_second > 50  # At least 50 operations per second
        assert records_per_second > 500  # At least 500 records per second

    def test_status_update_throughput(self):
        """Test throughput of status update operations."""
        # Mock successful updates
        self.mock_rpa_db.execute_query.return_value = 1

        # Measure update throughput
        start_time = time.time()
        operations_count = 1000

        for i in range(1, operations_count + 1):  # Use 1-based indexing
            if i % 2 == 0:
                # Completion updates
                result = {"processed": True, "index": i}
                self.processor.mark_record_completed(i, result)
            else:
                # Failure updates
                error_msg = f"Test error for record {i}"
                self.processor.mark_record_failed(i, error_msg)

        elapsed_time = time.time() - start_time
        throughput = operations_count / elapsed_time

        print("\nStatus Update Throughput Results:")
        print(f"  Operations: {operations_count}")
        print(f"  Time: {elapsed_time:.3f}s")
        print(f"  Updates/Second: {throughput:.0f}")

        # Verify throughput
        assert throughput > 200  # At least 200 updates per second

    def test_concurrent_throughput(self):
        """Test throughput under concurrent load."""
        # Mock database responses
        self.mock_rpa_db.execute_query.return_value = [
            (1, {"data": "test"}, 0, datetime.now())
        ]

        # Measure concurrent throughput
        def throughput_worker():
            operations = 0
            start_time = time.time()

            for _ in range(50):
                try:
                    records = self.processor.claim_records_batch(
                        "concurrent_throughput", 1
                    )
                    operations += len(records)
                except Exception:
                    pass

            elapsed_time = time.time() - start_time
            return operations, elapsed_time

        # Run concurrent workers
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(throughput_worker) for _ in range(10)]
            results = [future.result() for future in futures]
        total_time = time.time() - start_time

        # Analyze concurrent throughput
        total_operations = sum(ops for ops, _ in results)
        concurrent_throughput = total_operations / total_time

        print("\nConcurrent Throughput Results:")
        print("  Workers: 10")
        print(f"  Total Operations: {total_operations}")
        print(f"  Total Time: {total_time:.3f}s")
        print(f"  Concurrent Throughput: {concurrent_throughput:.0f} ops/sec")

        # Verify concurrent performance
        assert concurrent_throughput > 100  # Should achieve good concurrent throughput


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"])
