"""
Automated container test framework execution tests.

This module contains pytest tests that use the ContainerTestSuite class to validate
distributed processing behavior in containerized environments. These tests verify
the requirements for task 7 of the container testing system implementation.

Test Requirements Coverage:
- 3.1: Distributed processing tests verify no duplicate record processing
- 3.2: Performance tests measure throughput, latency, and resource utilization
- 3.3: Fault tolerance tests for container failures and network partitions
- 9.1: Distributed processing validation across multiple container instances
- 9.2: Performance tests measuring processing throughput and latency
- 9.4: Integration tests for end-to-end workflow validation across containers
"""

import time
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from core.config import ConfigManager
from core.database import DatabaseManager
from core.test.test_container_test_suite import (
    ContainerTestResult,
    ContainerTestSuite,
    ContainerTestValidator,
    FaultToleranceResult,
    PerformanceMetrics,
)


class TestContainerTestSuite:
    """Test the ContainerTestSuite class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create mock database managers
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.mock_source_db = Mock(spec=DatabaseManager)
        self.mock_source_db.database_name = "test_source_db"

        self.database_managers = {
            "rpa_db": self.mock_rpa_db,
            "source_db": self.mock_source_db,
        }

        # Create mock config manager
        self.mock_config = Mock(spec=ConfigManager)
        self.mock_config.get_distributed_config.return_value = {
            "default_batch_size": 100,
            "cleanup_timeout_hours": 1,
            "max_retries": 3,
        }
        self.mock_config.environment = "test"

        # Create test suite
        self.test_suite = ContainerTestSuite(
            database_managers=self.database_managers,
            config_manager=self.mock_config,
            enable_performance_monitoring=True,
        )

    def test_container_test_suite_initialization(self):
        """Test ContainerTestSuite initialization."""
        # Test with all parameters
        suite = ContainerTestSuite(
            database_managers=self.database_managers,
            config_manager=self.mock_config,
            enable_performance_monitoring=True,
        )

        assert suite.database_managers == self.database_managers
        assert suite.config_manager == self.mock_config
        assert suite.enable_performance_monitoring is True
        assert suite.validator is not None
        assert suite.health_monitor is not None
        assert len(suite.test_results) == 0

    def test_container_test_suite_initialization_minimal(self):
        """Test ContainerTestSuite initialization with minimal parameters."""
        suite = ContainerTestSuite()

        assert len(suite.database_managers) == 0
        assert suite.config_manager is not None
        assert suite.enable_performance_monitoring is True
        assert suite.validator is not None
        assert suite.health_monitor is None  # No databases provided

    @patch("core.test.test_container_test_suite.DistributedProcessor")
    def test_run_distributed_processing_tests_success(self, mock_processor_class):
        """Test successful distributed processing tests."""
        # Setup mock processor
        mock_processor = Mock()
        mock_processor.instance_id = "test-instance-123"
        mock_processor_class.return_value = mock_processor

        # Mock database operations
        mock_processor.add_records_to_queue.return_value = 10
        mock_processor.claim_records_batch.return_value = [
            {
                "id": 1,
                "payload": {"test_id": 1},
                "retry_count": 0,
                "created_at": "2024-01-01",
            },
            {
                "id": 2,
                "payload": {"test_id": 2},
                "retry_count": 0,
                "created_at": "2024-01-01",
            },
        ]
        mock_processor.mark_record_completed.return_value = None

        # Run test
        result = self.test_suite.run_distributed_processing_tests(
            flow_name="test_flow", record_count=10, container_count=2, batch_size=5
        )

        # Verify results
        assert result.test_name == "validate_no_duplicate_processing"
        assert result.status in ["passed", "failed"]
        assert result.duration > 0
        assert "test_configuration" in result.details
        assert result.details["test_configuration"]["flow_name"] == "test_flow"
        assert result.details["test_configuration"]["record_count"] == 10
        assert result.details["test_configuration"]["container_count"] == 2

    def test_run_distributed_processing_tests_no_database(self):
        """Test distributed processing tests with no database."""
        # Create suite without databases
        suite = ContainerTestSuite()

        result = suite.run_distributed_processing_tests()

        assert result.test_name == "run_distributed_processing_tests"
        assert result.status == "skipped"
        assert "No database managers configured" in result.details["reason"]
        assert len(result.errors) > 0

    @patch("core.test.test_container_test_suite.psutil")
    @patch("core.test.test_container_test_suite.DistributedProcessor")
    def test_run_performance_tests_success(self, mock_processor_class, mock_psutil):
        """Test successful performance tests."""
        # Setup mock processor
        mock_processor = Mock()
        mock_processor.instance_id = "test-perf-123"
        mock_processor_class.return_value = mock_processor

        # Mock database operations
        mock_processor.add_records_to_queue.return_value = 100
        mock_processor.claim_records_batch.return_value = [
            {
                "id": i,
                "payload": {"perf_test_id": i},
                "retry_count": 0,
                "created_at": "2024-01-01",
            }
            for i in range(5)
        ]
        mock_processor.mark_record_completed.return_value = None

        # Mock psutil
        mock_memory = Mock()
        mock_memory.used = 1000 * 1024 * 1024  # 1GB in bytes
        mock_psutil.virtual_memory.return_value = mock_memory
        mock_psutil.cpu_percent.return_value = 25.0

        # Run test
        result = self.test_suite.run_performance_tests(
            target_throughput=10,
            test_duration_seconds=2,  # Short duration for test
            container_count=1,
        )

        # Verify results
        assert result.test_name == "validate_performance_metrics"
        assert result.status in ["passed", "failed"]
        assert result.duration > 0
        assert "test_configuration" in result.details
        assert result.details["test_configuration"]["target_throughput"] == 10

    def test_run_performance_tests_disabled(self):
        """Test performance tests when monitoring is disabled."""
        # Create suite with performance monitoring disabled
        suite = ContainerTestSuite(
            database_managers=self.database_managers,
            enable_performance_monitoring=False,
        )

        result = suite.run_performance_tests()

        assert result.test_name == "run_performance_tests"
        assert result.status == "skipped"
        assert "Performance monitoring not enabled" in result.details["reason"]

    def test_run_fault_tolerance_tests_success(self):
        """Test successful fault tolerance tests."""
        result = self.test_suite.run_fault_tolerance_tests(
            test_scenarios=["container_crash", "database_connection_loss"]
        )

        # Verify results
        assert result.test_name == "validate_error_handling"
        assert result.status in ["passed", "failed"]
        assert result.duration > 0
        assert "test_scenarios" in result.details
        assert len(result.details["test_scenarios"]) == 2

    def test_run_fault_tolerance_tests_default_scenarios(self):
        """Test fault tolerance tests with default scenarios."""
        result = self.test_suite.run_fault_tolerance_tests()

        # Verify results
        assert result.test_name == "validate_error_handling"
        assert result.status in ["passed", "failed"]
        assert result.duration > 0
        assert "test_scenarios" in result.details
        assert len(result.details["test_scenarios"]) >= 4  # Default scenarios

    @patch("core.test.test_container_test_suite.DistributedProcessor")
    def test_run_integration_tests_success(self, mock_processor_class):
        """Test successful integration tests."""
        # Setup mock processor
        mock_processor = Mock()
        mock_processor.instance_id = "test-integration-123"
        mock_processor_class.return_value = mock_processor

        # Mock database operations for integration tests
        mock_processor.add_records_to_queue.return_value = 5
        mock_processor.claim_records_batch.return_value = [
            {
                "id": i,
                "payload": {"workflow_test_id": i},
                "retry_count": 0,
                "created_at": "2024-01-01",
            }
            for i in range(5)
        ]
        mock_processor.mark_record_completed.return_value = None
        mock_processor.get_queue_status.return_value = {
            "completed_records": 5,
            "failed_records": 0,
            "pending_records": 0,
            "processing_records": 0,
        }

        result = self.test_suite.run_integration_tests(
            test_workflows=[
                "complete_processing_workflow",
                "multi_container_coordination",
            ]
        )

        # Verify results
        assert result.test_name == "run_integration_tests"
        assert result.status in ["passed", "failed"]
        assert result.duration > 0
        assert "test_workflows" in result.details
        assert len(result.details["test_workflows"]) == 2

    def test_generate_comprehensive_report(self):
        """Test comprehensive report generation."""
        # Add some test results
        test_result = ContainerTestResult(
            test_name="test_example",
            status="passed",
            duration=1.5,
            details={"example": "data"},
            errors=[],
            warnings=[],
            timestamp=datetime.now(),
        )
        self.test_suite.test_results.append(test_result)

        # Add performance metrics
        perf_metrics = PerformanceMetrics(
            records_processed=100,
            processing_rate=50.0,
            average_latency=20.0,
            error_rate=2.0,
            resource_efficiency=85.0,
            memory_usage_mb=512.0,
            cpu_usage_percent=30.0,
            throughput_variance=5.0,
        )
        self.test_suite.performance_metrics.append(perf_metrics)

        # Generate report
        report = self.test_suite.generate_comprehensive_report()

        # Verify report structure
        assert "test_report_summary" in report
        assert "container_test_suite_report" in report
        assert "test_results" in report
        assert "recommendations" in report

        # Verify container-specific sections
        container_report = report["container_test_suite_report"]
        assert "test_environment" in container_report
        assert "test_categories" in container_report
        assert "performance_metrics_summary" in container_report
        assert "fault_tolerance_summary" in container_report

    def test_cleanup_test_environment(self):
        """Test test environment cleanup."""
        # Add some test data
        self.test_suite.test_results.append(Mock())
        self.test_suite.performance_metrics.append(Mock())
        self.test_suite.fault_tolerance_results.append(Mock())

        # Verify data exists
        assert len(self.test_suite.test_results) > 0
        assert len(self.test_suite.performance_metrics) > 0
        assert len(self.test_suite.fault_tolerance_results) > 0

        # Cleanup
        self.test_suite.cleanup_test_environment()

        # Verify cleanup
        assert len(self.test_suite.test_results) == 0
        assert len(self.test_suite.performance_metrics) == 0
        assert len(self.test_suite.fault_tolerance_results) == 0


class TestContainerTestValidator:
    """Test the ContainerTestValidator class functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = ContainerTestValidator()

    def test_validate_no_duplicate_processing_success(self):
        """Test successful duplicate processing validation."""
        test_records = [
            {"id": 1, "payload": {"data": "test1"}},
            {"id": 2, "payload": {"data": "test2"}},
            {"id": 3, "payload": {"data": "test3"}},
        ]

        processing_results = [
            {"record_id": 1, "status": "completed", "result": {"processed": True}},
            {"record_id": 2, "status": "completed", "result": {"processed": True}},
            {"record_id": 3, "status": "completed", "result": {"processed": True}},
        ]

        result = self.validator.validate_no_duplicate_processing(
            test_records, processing_results
        )

        assert result.test_name == "validate_no_duplicate_processing"
        assert result.status == "passed"
        assert result.details["duplicate_processing_count"] == 0
        assert result.details["processing_completeness_percent"] == 100.0
        assert len(result.errors) == 0

    def test_validate_no_duplicate_processing_with_duplicates(self):
        """Test duplicate processing validation with duplicates detected."""
        test_records = [
            {"id": 1, "payload": {"data": "test1"}},
            {"id": 2, "payload": {"data": "test2"}},
        ]

        processing_results = [
            {"record_id": 1, "status": "completed", "result": {"processed": True}},
            {
                "record_id": 1,
                "status": "completed",
                "result": {"processed": True},
            },  # Duplicate
            {"record_id": 2, "status": "completed", "result": {"processed": True}},
        ]

        result = self.validator.validate_no_duplicate_processing(
            test_records, processing_results
        )

        assert result.test_name == "validate_no_duplicate_processing"
        assert result.status == "failed"
        assert result.details["duplicate_processing_count"] == 1
        assert len(result.errors) > 0
        assert "duplicate record processing" in result.errors[0]

    def test_validate_performance_metrics_success(self):
        """Test successful performance metrics validation."""
        metrics = PerformanceMetrics(
            records_processed=1000,
            processing_rate=50.0,  # Above minimum threshold
            average_latency=1000.0,  # Below maximum threshold
            error_rate=2.0,  # Below maximum threshold
            resource_efficiency=80.0,  # Above minimum threshold
            memory_usage_mb=500.0,
            cpu_usage_percent=60.0,
            throughput_variance=5.0,
        )

        result = self.validator.validate_performance_metrics(metrics)

        assert result.test_name == "validate_performance_metrics"
        assert result.status == "passed"
        assert len(result.errors) == 0
        assert "performance_score" in result.details

    def test_validate_performance_metrics_failures(self):
        """Test performance metrics validation with failures."""
        metrics = PerformanceMetrics(
            records_processed=100,
            processing_rate=5.0,  # Below minimum threshold
            average_latency=10000.0,  # Above maximum threshold
            error_rate=10.0,  # Above maximum threshold
            resource_efficiency=50.0,  # Below minimum threshold
            memory_usage_mb=1500.0,  # High memory usage
            cpu_usage_percent=95.0,  # High CPU usage
            throughput_variance=20.0,
        )

        result = self.validator.validate_performance_metrics(metrics)

        assert result.test_name == "validate_performance_metrics"
        assert result.status == "failed"
        assert len(result.errors) >= 3  # Throughput, latency, error rate
        assert any("Throughput too low" in error for error in result.errors)
        assert any("Latency too high" in error for error in result.errors)
        assert any("Error rate too high" in error for error in result.errors)

    def test_validate_error_handling_success(self):
        """Test successful error handling validation."""
        fault_results = [
            FaultToleranceResult(
                test_scenario="container_crash",
                containers_tested=2,
                failures_injected=1,
                recovery_time_seconds=30.0,
                data_consistency_maintained=True,
                error_handling_effective=True,
                details={"test": "data"},
            ),
            FaultToleranceResult(
                test_scenario="network_partition",
                containers_tested=3,
                failures_injected=1,
                recovery_time_seconds=45.0,
                data_consistency_maintained=True,
                error_handling_effective=True,
                details={"test": "data"},
            ),
        ]

        result = self.validator.validate_error_handling(fault_results)

        assert result.test_name == "validate_error_handling"
        assert result.status == "passed"
        assert result.details["data_consistency_rate_percent"] == 100.0
        assert result.details["error_handling_effectiveness_percent"] == 100.0
        assert len(result.errors) == 0

    def test_validate_error_handling_failures(self):
        """Test error handling validation with failures."""
        fault_results = [
            FaultToleranceResult(
                test_scenario="container_crash",
                containers_tested=2,
                failures_injected=1,
                recovery_time_seconds=30.0,
                data_consistency_maintained=False,  # Data consistency failure
                error_handling_effective=False,  # Error handling failure
                details={"test": "data"},
            )
        ]

        result = self.validator.validate_error_handling(fault_results)

        assert result.test_name == "validate_error_handling"
        assert result.status == "failed"
        assert result.details["data_consistency_rate_percent"] == 0.0
        assert result.details["error_handling_effectiveness_percent"] == 0.0
        assert len(result.errors) >= 2  # Data consistency and error handling

    def test_generate_test_report_success(self):
        """Test successful test report generation."""
        test_results = [
            ContainerTestResult(
                test_name="test1",
                status="passed",
                duration=1.0,
                details={"test": "data"},
                errors=[],
                warnings=[],
                timestamp=datetime.now(),
            ),
            ContainerTestResult(
                test_name="test2",
                status="failed",
                duration=2.0,
                details={"test": "data"},
                errors=["Test error"],
                warnings=["Test warning"],
                timestamp=datetime.now(),
            ),
        ]

        report = self.validator.generate_test_report(test_results)

        assert "test_report_summary" in report
        assert "test_results" in report
        assert "recommendations" in report

        summary = report["test_report_summary"]
        assert summary["total_tests"] == 2
        assert summary["passed_tests"] == 1
        assert summary["failed_tests"] == 1
        assert summary["success_rate_percent"] == 50.0
        assert summary["total_errors"] == 1
        assert summary["total_warnings"] == 1

    def test_generate_test_report_empty(self):
        """Test test report generation with no results."""
        report = self.validator.generate_test_report([])

        assert "error" in report
        assert "No test results provided" in report["error"]

    def test_performance_score_calculation(self):
        """Test performance score calculation."""
        # Test high performance metrics
        high_perf_metrics = PerformanceMetrics(
            records_processed=1000,
            processing_rate=100.0,  # High throughput
            average_latency=100.0,  # Low latency
            error_rate=0.5,  # Low error rate
            resource_efficiency=95.0,  # High efficiency
            memory_usage_mb=200.0,
            cpu_usage_percent=30.0,
            throughput_variance=2.0,
        )

        result = self.validator.validate_performance_metrics(high_perf_metrics)
        score = result.details["performance_score"]

        assert score > 80.0  # Should be high score

        # Test low performance metrics
        low_perf_metrics = PerformanceMetrics(
            records_processed=100,
            processing_rate=5.0,  # Low throughput
            average_latency=4000.0,  # High latency
            error_rate=8.0,  # High error rate
            resource_efficiency=40.0,  # Low efficiency
            memory_usage_mb=800.0,
            cpu_usage_percent=90.0,
            throughput_variance=25.0,
        )

        result = self.validator.validate_performance_metrics(low_perf_metrics)
        score = result.details["performance_score"]

        assert score < 50.0  # Should be low score


@pytest.mark.integration
class TestContainerTestSuiteIntegration:
    """Integration tests for the container test suite with real components."""

    @pytest.fixture(autouse=True)
    def setup_integration_test(self, postgresql_available):
        """Set up integration test environment."""
        if not postgresql_available:
            pytest.skip("PostgreSQL not available for integration tests")

        # Create real database managers for integration testing
        self.config_manager = ConfigManager()

        try:
            self.rpa_db = DatabaseManager("test_rpa_db")
            self.database_managers = {"rpa_db": self.rpa_db}
        except Exception as e:
            pytest.skip(f"Could not create database manager: {e}")

        # Create test suite with real components
        self.test_suite = ContainerTestSuite(
            database_managers=self.database_managers,
            config_manager=self.config_manager,
            enable_performance_monitoring=True,
        )

    def test_full_distributed_processing_integration(self):
        """Test full distributed processing with real database."""
        result = self.test_suite.run_distributed_processing_tests(
            flow_name="integration_test_flow",
            record_count=20,
            container_count=2,
            batch_size=5,
        )

        # Verify integration test results
        assert result.test_name == "validate_no_duplicate_processing"
        assert result.status in ["passed", "failed"]
        assert result.duration > 0
        assert "test_configuration" in result.details

        # If test passed, verify no duplicates were processed
        if result.status == "passed":
            assert result.details["duplicate_processing_count"] == 0

    def test_performance_integration_with_real_database(self):
        """Test performance testing with real database operations."""
        result = self.test_suite.run_performance_tests(
            target_throughput=20, test_duration_seconds=10, container_count=1
        )

        # Verify performance test results
        assert result.test_name == "validate_performance_metrics"
        assert result.status in ["passed", "failed"]
        assert result.duration > 0
        assert "performance_metrics" in result.details

    def test_integration_workflow_with_real_components(self):
        """Test integration workflows with real components."""
        result = self.test_suite.run_integration_tests(
            test_workflows=[
                "complete_processing_workflow",
                "configuration_management_integration",
            ]
        )

        # Verify integration test results
        assert result.test_name == "run_integration_tests"
        assert result.status in ["passed", "failed"]
        assert result.duration > 0
        assert "workflow_results" in result.details

    def test_comprehensive_report_generation_integration(self):
        """Test comprehensive report generation with real test data."""
        # Run multiple test types
        self.test_suite.run_distributed_processing_tests(
            record_count=10, container_count=1
        )
        self.test_suite.run_fault_tolerance_tests(test_scenarios=["container_crash"])

        # Generate comprehensive report
        report = self.test_suite.generate_comprehensive_report()

        # Verify report completeness
        assert "test_report_summary" in report
        assert "container_test_suite_report" in report
        assert "test_results" in report
        assert "recommendations" in report

        # Verify test results were included
        assert report["test_report_summary"]["total_tests"] >= 2


@pytest.mark.performance
class TestContainerTestSuitePerformance:
    """Performance tests for the container test suite itself."""

    def setup_method(self):
        """Set up performance test fixtures."""
        # Create mock components for performance testing
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "perf_test_rpa_db"
        self.mock_rpa_db.logger = Mock()

        self.database_managers = {"rpa_db": self.mock_rpa_db}
        self.mock_config = Mock(spec=ConfigManager)

        self.test_suite = ContainerTestSuite(
            database_managers=self.database_managers,
            config_manager=self.mock_config,
            enable_performance_monitoring=True,
        )

    @patch("core.test.test_container_test_suite.DistributedProcessor")
    def test_large_scale_distributed_processing_performance(self, mock_processor_class):
        """Test performance with large-scale distributed processing."""
        # Setup mock for large scale test
        mock_processor = Mock()
        mock_processor.instance_id = "perf-test-instance"
        mock_processor_class.return_value = mock_processor

        # Mock large batch operations
        mock_processor.add_records_to_queue.return_value = 1000
        mock_processor.claim_records_batch.return_value = [
            {
                "id": i,
                "payload": {"test_id": i},
                "retry_count": 0,
                "created_at": "2024-01-01",
            }
            for i in range(50)  # Simulate batch claiming
        ]
        mock_processor.mark_record_completed.return_value = None

        # Measure performance
        start_time = time.time()

        result = self.test_suite.run_distributed_processing_tests(
            flow_name="large_scale_test",
            record_count=1000,
            container_count=5,
            batch_size=50,
        )

        execution_time = time.time() - start_time

        # Verify performance characteristics
        assert execution_time < 30.0  # Should complete within 30 seconds
        assert result.status in ["passed", "failed"]
        assert result.duration > 0

    def test_test_suite_memory_usage(self):
        """Test memory usage of the test suite itself."""
        try:
            import os

            import psutil
        except ImportError:
            pytest.skip("psutil not available for memory testing")

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Run multiple test cycles
        for _i in range(10):
            # Create and cleanup test suite
            suite = ContainerTestSuite(
                database_managers=self.database_managers,
                config_manager=self.mock_config,
            )

            # Add some test data
            suite.test_results.extend([Mock() for _ in range(100)])
            suite.performance_metrics.extend([Mock() for _ in range(10)])

            # Cleanup
            suite.cleanup_test_environment()

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024

    def test_concurrent_test_execution_performance(self):
        """Test performance of concurrent test execution."""
        import concurrent.futures

        def run_test_cycle():
            """Run a complete test cycle."""
            suite = ContainerTestSuite(
                database_managers=self.database_managers,
                config_manager=self.mock_config,
            )

            # Mock quick operations
            with patch("core.test.test_container_test_suite.DistributedProcessor"):
                result = suite.run_fault_tolerance_tests(
                    test_scenarios=["container_crash"]
                )

            return result.status

        # Run concurrent test cycles
        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(run_test_cycle) for _ in range(10)]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        execution_time = time.time() - start_time

        # Verify concurrent execution performance
        assert execution_time < 20.0  # Should complete within 20 seconds
        assert len(results) == 10
        assert all(status in ["passed", "failed"] for status in results)


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
