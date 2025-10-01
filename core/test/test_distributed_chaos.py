"""
Chaos engineering tests for distributed processing system.

This module tests the system's resilience to various failure scenarios
including database failures, network issues, container failures, and
resource exhaustion conditions.
"""

import random
import socket
import time
from datetime import datetime
from unittest.mock import Mock

import pytest

from core.database import DatabaseManager
from core.distributed import DistributedProcessor


class TestDatabaseFailureScenarios:
    """Test system behavior during database failure scenarios."""

    def setup_method(self):
        """Set up chaos engineering tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()
        self.mock_source_db.database_name = "test_source_db"

        self.processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db, source_db_manager=self.mock_source_db
        )

    def test_complete_database_failure(self):
        """Test behavior when database is completely unavailable."""
        # Simulate complete database failure
        self.mock_rpa_db.execute_query.side_effect = Exception(
            "Database server unavailable"
        )

        # Test that all operations fail gracefully
        with pytest.raises(RuntimeError, match="Failed to claim records"):
            self.processor.claim_records_batch("chaos_test", 10)

        with pytest.raises(RuntimeError, match="Failed to mark record.*as completed"):
            self.processor.mark_record_completed(1, {"processed": True})

        with pytest.raises(RuntimeError, match="Failed to mark record.*as failed"):
            self.processor.mark_record_failed(1, "Test error")

        with pytest.raises(RuntimeError, match="Failed to add.*records to queue"):
            records = [{"payload": {"data": "test"}}]
            self.processor.add_records_to_queue("chaos_test", records)

        # Verify errors were logged appropriately
        assert self.mock_rpa_db.logger.error.call_count >= 4

    def test_intermittent_database_failures(self):
        """Test handling of intermittent database connection issues."""
        # Create failure pattern: fail every 3rd call
        call_count = 0

        def intermittent_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise Exception("Intermittent connection failure")
            return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = intermittent_failure

        # Test multiple operations with intermittent failures
        successful_operations = 0
        failed_operations = 0

        for _i in range(20):
            try:
                records = self.processor.claim_records_batch("intermittent_test", 1)
                if records:
                    successful_operations += 1
            except RuntimeError:
                failed_operations += 1

        # Should have both successes and failures
        assert successful_operations > 0, "No operations succeeded"
        assert failed_operations > 0, "No operations failed as expected"

        # Failure rate should be approximately 1/3
        failure_rate = failed_operations / (successful_operations + failed_operations)
        assert 0.2 < failure_rate < 0.5, f"Unexpected failure rate: {failure_rate}"

    def test_database_timeout_scenarios(self):
        """Test handling of database timeout conditions."""
        # Simulate various timeout scenarios
        timeout_exceptions = [
            socket.timeout("Connection timeout"),
            Exception("Query timeout"),
            Exception("Lock wait timeout exceeded"),
            Exception("Connection pool timeout"),
        ]

        for timeout_exception in timeout_exceptions:
            self.mock_rpa_db.execute_query.side_effect = timeout_exception

            # Test that timeouts are handled gracefully
            with pytest.raises(RuntimeError):
                self.processor.claim_records_batch("timeout_test", 5)

            # Verify appropriate error logging
            self.mock_rpa_db.logger.error.assert_called()

    def test_database_connection_recovery(self):
        """Test system behavior during database connection recovery."""
        # Simulate database failure followed by recovery
        failure_count = 0

        def failure_then_recovery(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            if failure_count <= 5:
                raise Exception("Database connection failed")
            # After 5 failures, start succeeding
            return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = failure_then_recovery

        # Test operations during failure and recovery
        results = []
        for _i in range(10):
            try:
                records = self.processor.claim_records_batch("recovery_test", 1)
                results.append(("success", len(records)))
            except RuntimeError:
                results.append(("failure", 0))

        # Should have failures followed by successes
        failures = [r for r in results if r[0] == "failure"]
        successes = [r for r in results if r[0] == "success"]

        assert len(failures) == 5, "Expected 5 failures during outage"
        assert len(successes) == 5, "Expected 5 successes after recovery"

    def test_partial_database_functionality(self):
        """Test behavior when some database operations work but others fail."""

        def selective_failure(query, params, **kwargs):
            if "claim_records_batch" in str(query) or "FOR UPDATE SKIP LOCKED" in query:
                # Claiming works
                return [(1, {"data": "test"}, 0, datetime.now())]
            elif "SET status = 'completed'" in query:
                # Completion updates fail
                raise Exception("Update operation failed")
            elif "SET status = 'failed'" in query:
                # Failure updates work
                return 1
            else:
                # Other operations work
                return []

        self.mock_rpa_db.execute_query.side_effect = selective_failure

        # Test mixed success/failure scenario
        records = self.processor.claim_records_batch("partial_test", 1)
        assert len(records) == 1, "Claiming should work"

        # Completion should fail
        with pytest.raises(RuntimeError):
            self.processor.mark_record_completed(1, {"processed": True})

        # Failure marking should work
        self.processor.mark_record_failed(1, "Test error")  # Should not raise


class TestNetworkFailureScenarios:
    """Test system behavior during network failure scenarios."""

    def setup_method(self):
        """Set up network failure tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_network_partition_simulation(self):
        """Test behavior during simulated network partitions."""
        # Simulate various network issues
        network_exceptions = [
            socket.timeout("Network timeout"),
            socket.gaierror("Name resolution failed"),
            ConnectionError("Network unreachable"),
            OSError("Network is down"),
        ]

        for network_exception in network_exceptions:
            self.mock_rpa_db.execute_query.side_effect = network_exception

            # Test that network issues are handled appropriately
            with pytest.raises(RuntimeError):
                self.processor.claim_records_batch("network_test", 5)

            # Verify error logging
            self.mock_rpa_db.logger.error.assert_called()

    @pytest.mark.slow
    def test_slow_network_conditions(self):
        """Test behavior under slow network conditions."""

        def slow_network_response(*args, **kwargs):
            # Simulate slow network by adding delay
            time.sleep(0.1)  # 100ms delay
            return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = slow_network_response

        # Test operations under slow network
        start_time = time.time()
        records = self.processor.claim_records_batch("slow_test", 5)
        elapsed_time = time.time() - start_time

        # Should complete but take longer
        assert len(records) == 1  # Mock returns 1 record
        assert elapsed_time >= 0.1  # Should take at least 100ms due to delay

    @pytest.mark.slow
    def test_network_jitter_simulation(self):
        """Test behavior with network jitter (variable delays)."""

        def jittery_network(*args, **kwargs):
            # Random delay between 0-50ms
            delay = random.uniform(0, 0.05)
            time.sleep(delay)

            # Occasionally fail to simulate packet loss
            if random.random() < 0.1:  # 10% failure rate
                raise ConnectionError("Packet loss")

            return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = jittery_network

        # Test multiple operations with jitter
        successful_ops = 0
        failed_ops = 0
        total_time = 0

        for _ in range(50):
            start_time = time.time()
            try:
                self.processor.claim_records_batch("jitter_test", 1)
                successful_ops += 1
            except RuntimeError:
                failed_ops += 1
            total_time += time.time() - start_time

        # Should have mostly successes with some failures
        assert successful_ops > 40, "Too many failures due to jitter"
        assert failed_ops > 0, "Expected some failures due to packet loss"

        avg_time = total_time / 50
        assert avg_time > 0.01, "Operations should take some time due to jitter"


class TestContainerFailureScenarios:
    """Test system behavior during container failure scenarios."""

    def setup_method(self):
        """Set up container failure tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    @pytest.mark.slow
    def test_container_instance_isolation(self):
        """Test that container instances are properly isolated."""
        # Create multiple processor instances (simulating containers)
        processors = [
            DistributedProcessor(rpa_db_manager=self.mock_rpa_db) for _ in range(5)
        ]

        # Verify unique instance IDs
        instance_ids = [p.instance_id for p in processors]
        assert len(set(instance_ids)) == 5, "Instance IDs should be unique"

        # Test that each processor uses its own instance ID
        self.mock_rpa_db.execute_query.return_value = 1

        for i, processor in enumerate(processors):
            processor.mark_record_completed(
                i + 1, {"processed": True}
            )  # Use 1-based indexing

            # Verify the correct instance ID was used
            call_args = self.mock_rpa_db.execute_query.call_args
            assert call_args[0][1]["instance_id"] == processor.instance_id

    @pytest.mark.slow
    def test_concurrent_container_failures(self):
        """Test system behavior when multiple containers fail simultaneously."""
        # Create multiple processors
        processors = [
            DistributedProcessor(rpa_db_manager=self.mock_rpa_db) for _ in range(10)
        ]

        # Simulate some containers failing
        def container_operation(processor_index):
            if processor_index < 3:  # First 3 containers fail
                raise Exception(f"Container {processor_index} crashed")

            # Successful containers return records
            return [
                (
                    processor_index,
                    {"data": f"test_{processor_index}"},
                    0,
                    datetime.now(),
                )
            ]

        # Test operations with container failures
        results = []
        exceptions = []

        for i, processor in enumerate(processors):
            try:
                self.mock_rpa_db.execute_query.return_value = container_operation(i)
                if i >= 3:  # Only successful containers
                    records = processor.claim_records_batch("failure_test", 1)
                    results.append((i, len(records)))
                else:
                    # Simulate container failure
                    raise Exception(f"Container {i} failed")
            except Exception as e:
                exceptions.append((i, str(e)))

        # Verify partial system operation
        assert len(results) == 7, "7 containers should succeed"
        assert len(exceptions) == 3, "3 containers should fail"

        # Verify successful containers processed records
        for container_id, record_count in results:
            assert record_count == 1, (
                f"Container {container_id} should process 1 record"
            )

    @pytest.mark.slow
    def test_container_restart_simulation(self):
        """Test behavior during container restart scenarios."""
        # Simulate container lifecycle: start -> process -> crash -> restart
        container_states = ["starting", "running", "crashed", "restarting", "running"]
        state_index = 0

        def container_lifecycle(*args, **kwargs):
            nonlocal state_index
            current_state = container_states[state_index % len(container_states)]
            state_index += 1

            if current_state == "crashed":
                raise Exception("Container crashed")
            elif current_state == "starting" or current_state == "restarting":
                raise Exception("Container not ready")
            else:  # running
                return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = container_lifecycle

        # Test operations during container lifecycle
        results = []
        for _i in range(10):
            try:
                records = self.processor.claim_records_batch("restart_test", 1)
                results.append(("success", len(records)))
            except RuntimeError:
                results.append(("failure", 0))

        # Should have mix of successes and failures
        successes = [r for r in results if r[0] == "success"]
        failures = [r for r in results if r[0] == "failure"]

        assert len(successes) > 0, "Some operations should succeed"
        assert len(failures) > 0, "Some operations should fail during restarts"


class TestResourceExhaustionScenarios:
    """Test system behavior under resource exhaustion conditions."""

    def setup_method(self):
        """Set up resource exhaustion tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.processor = DistributedProcessor(rpa_db_manager=self.mock_rpa_db)

    def test_memory_exhaustion_handling(self):
        """Test handling of memory exhaustion scenarios."""
        # Simulate memory pressure
        memory_exceptions = [
            MemoryError("Out of memory"),
            Exception("Cannot allocate memory"),
            OSError("Not enough space"),
        ]

        for memory_exception in memory_exceptions:
            self.mock_rpa_db.execute_query.side_effect = memory_exception

            # Test that memory errors are handled gracefully
            with pytest.raises(RuntimeError):
                self.processor.claim_records_batch("memory_test", 1000)

            # Verify error logging
            self.mock_rpa_db.logger.error.assert_called()

    def test_connection_pool_exhaustion(self):
        """Test handling of connection pool exhaustion."""
        # Simulate connection pool exhaustion
        pool_exceptions = [
            Exception("Connection pool exhausted"),
            Exception("Too many connections"),
            Exception("Max connections reached"),
        ]

        for pool_exception in pool_exceptions:
            self.mock_rpa_db.execute_query.side_effect = pool_exception

            # Test that pool exhaustion is handled
            with pytest.raises(RuntimeError):
                self.processor.get_queue_status()

            # Verify appropriate error handling
            self.mock_rpa_db.logger.error.assert_called()

    def test_disk_space_exhaustion(self):
        """Test handling of disk space exhaustion."""
        # Simulate disk space issues
        disk_exceptions = [
            OSError("No space left on device"),
            Exception("Disk full"),
            OSError("Write failed: disk full"),
        ]

        for disk_exception in disk_exceptions:
            self.mock_rpa_db.execute_query.side_effect = disk_exception

            # Test that disk space issues are handled
            with pytest.raises(RuntimeError):
                records = [{"payload": {"data": "test"}}]
                self.processor.add_records_to_queue("disk_test", records)

    @pytest.mark.slow
    def test_cpu_exhaustion_simulation(self):
        """Test behavior under high CPU load conditions."""

        def cpu_intensive_operation(*args, **kwargs):
            # Simulate CPU-intensive operation
            start_time = time.time()
            while time.time() - start_time < 0.01:  # 10ms of CPU work
                _ = sum(i * i for i in range(1000))

            return [(1, {"data": "test"}, 0, datetime.now())]

        self.mock_rpa_db.execute_query.side_effect = cpu_intensive_operation

        # Test operations under CPU load
        start_time = time.time()
        operations_completed = 0

        # Run for 1 second
        while time.time() - start_time < 1.0:
            try:
                self.processor.claim_records_batch("cpu_test", 1)
                operations_completed += 1
            except Exception:
                pass

        # Should complete some operations despite CPU load
        assert operations_completed > 0, (
            "Should complete some operations under CPU load"
        )
        assert operations_completed < 200, "Should be slower due to CPU load"


class TestCascadingFailureScenarios:
    """Test system behavior during cascading failure scenarios."""

    def setup_method(self):
        """Set up cascading failure tests."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()
        self.mock_source_db.database_name = "test_source_db"

        self.processor = DistributedProcessor(
            rpa_db_manager=self.mock_rpa_db, source_db_manager=self.mock_source_db
        )

    def test_multi_database_failure_cascade(self):
        """Test cascading failures across multiple databases."""
        # Simulate primary database failure leading to secondary failures
        failure_cascade = {"rpa_db_failed": False, "source_db_failed": False}

        def cascading_database_failure(*args, **kwargs):
            # Primary database fails first
            if not failure_cascade["rpa_db_failed"]:
                failure_cascade["rpa_db_failed"] = True
                raise Exception("Primary database connection lost")

            # Secondary database fails after primary
            if not failure_cascade["source_db_failed"]:
                failure_cascade["source_db_failed"] = True
                raise Exception("Secondary database overloaded")

            # Both databases are down
            raise Exception("All databases unavailable")

        self.mock_rpa_db.execute_query.side_effect = cascading_database_failure
        self.mock_source_db.execute_query.side_effect = cascading_database_failure

        # Test operations during cascade
        failures = []

        for _i in range(5):
            try:
                self.processor.claim_records_batch("cascade_test", 1)
            except RuntimeError as e:
                failures.append(str(e))

        # Should have multiple failures as cascade progresses
        assert len(failures) == 5, "All operations should fail during cascade"
        assert failure_cascade["rpa_db_failed"], "Primary database should fail"
        assert failure_cascade["source_db_failed"], "Secondary database should fail"

    def test_health_check_during_failures(self):
        """Test health check behavior during various failure scenarios."""
        # Mock health check responses for different failure states
        health_scenarios = [
            {"status": "healthy"},  # Initial healthy state
            {"status": "degraded", "error": "High latency detected"},  # Degraded
            {"status": "unhealthy", "error": "Database connection failed"},  # Failed
        ]

        scenario_index = 0

        def health_check_progression():
            nonlocal scenario_index
            if scenario_index < len(health_scenarios):
                result = health_scenarios[scenario_index]
                scenario_index += 1
                return result
            return {"status": "unhealthy", "error": "System down"}

        # Mock health checks for both databases
        self.mock_rpa_db.health_check.side_effect = lambda: health_check_progression()
        self.mock_source_db.health_check.side_effect = (
            lambda: health_check_progression()
        )

        # Mock queue status for health check
        self.mock_rpa_db.execute_query.return_value = [
            ("pending", 10),
            ("processing", 2),
        ]

        # Test health checks during failure progression
        health_results = []
        for _ in range(4):
            try:
                health = self.processor.health_check()
                health_results.append(health["status"])
            except Exception:
                health_results.append("error")

        # Should show progression through different health states
        # Note: May start with degraded if source DB has issues
        assert len(set(health_results)) > 1, "Should show health state changes"
        assert "unhealthy" in health_results, "Should become unhealthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
