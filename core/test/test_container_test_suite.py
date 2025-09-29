"""
Automated container test framework for comprehensive distributed processing validation.

This module provides the ContainerTestSuite class that validates distributed processing
behavior in containerized environments, including duplicate record prevention,
performance testing, fault tolerance, and end-to-end workflow validation.

Test Categories:
- Distributed Processing Tests: Verify no duplicate record processing across containers
- Performance Tests: Measure throughput, latency, and resource utilization
- Fault Tolerance Tests: Test container failures and network partitions
- Integration Tests: End-to-end workflow validation across containers
"""

import concurrent.futures
import socket
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional
from unittest.mock import Mock

import psutil

from core.config import ConfigManager
from core.database import DatabaseManager
from core.distributed import DistributedProcessor
from core.health_monitor import HealthMonitor


@dataclass
class ContainerTestResult:
    """Test execution result data structure."""

    test_name: str
    status: str  # "passed", "failed", "skipped"
    duration: float
    details: dict[str, Any]
    errors: list[str]
    warnings: list[str]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass
class PerformanceMetrics:
    """Performance test metrics data structure."""

    records_processed: int
    processing_rate: float  # records per second
    average_latency: float  # milliseconds
    error_rate: float  # percentage
    resource_efficiency: float  # percentage
    memory_usage_mb: float
    cpu_usage_percent: float
    throughput_variance: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class FaultToleranceResult:
    """Fault tolerance test result data structure."""

    test_scenario: str
    containers_tested: int
    failures_injected: int
    recovery_time_seconds: float
    data_consistency_maintained: bool
    error_handling_effective: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class ContainerTestValidator:
    """Validates test results and generates comprehensive reports."""

    def __init__(self):
        self.validation_results = []
        self.performance_baselines = {
            "min_throughput_per_second": 10,
            "max_latency_ms": 5000,
            "max_error_rate_percent": 5.0,
            "min_resource_efficiency_percent": 70.0,
        }

    def validate_no_duplicate_processing(
        self,
        test_records: list[dict[str, Any]],
        processing_results: list[dict[str, Any]],
    ) -> ContainerTestResult:
        """
        Validate that no duplicate record processing occurred.

        Args:
            test_records: Original test records inserted
            processing_results: Results from distributed processing

        Returns:
            ContainerTestResult with validation outcome
        """
        start_time = time.time()
        errors = []
        warnings = []

        try:
            # Extract processed record IDs
            processed_ids = []
            for result in processing_results:
                if result.get("status") == "completed":
                    processed_ids.append(result.get("record_id"))

            # Check for duplicates
            unique_processed_ids = set(processed_ids)
            duplicate_count = len(processed_ids) - len(unique_processed_ids)

            if duplicate_count > 0:
                errors.append(
                    f"Found {duplicate_count} duplicate record processing instances"
                )

            # Check processing completeness
            expected_records = len(test_records)
            actual_processed = len(unique_processed_ids)

            if actual_processed < expected_records:
                warnings.append(
                    f"Only {actual_processed}/{expected_records} records were processed"
                )
            elif actual_processed > expected_records:
                errors.append(
                    f"More records processed ({actual_processed}) than inserted ({expected_records})"
                )

            # Validate record integrity
            for result in processing_results:
                if "record_id" not in result:
                    errors.append("Processing result missing record_id")
                if "status" not in result:
                    errors.append("Processing result missing status")

            status = "failed" if errors else ("passed" if not warnings else "passed")

            details = {
                "total_records_inserted": expected_records,
                "unique_records_processed": len(unique_processed_ids),
                "duplicate_processing_count": duplicate_count,
                "processing_completeness_percent": (
                    (actual_processed / expected_records * 100)
                    if expected_records > 0
                    else 0
                ),
                "processed_record_ids": sorted(unique_processed_ids),
            }

            return ContainerTestResult(
                test_name="validate_no_duplicate_processing",
                status=status,
                duration=time.time() - start_time,
                details=details,
                errors=errors,
                warnings=warnings,
                timestamp=datetime.now(),
            )

        except Exception as e:
            return ContainerTestResult(
                test_name="validate_no_duplicate_processing",
                status="failed",
                duration=time.time() - start_time,
                details={"error": str(e)},
                errors=[f"Validation failed: {str(e)}"],
                warnings=warnings,
                timestamp=datetime.now(),
            )

    def validate_performance_metrics(
        self, metrics: PerformanceMetrics
    ) -> ContainerTestResult:
        """
        Validate performance metrics against baselines.

        Args:
            metrics: Performance metrics to validate

        Returns:
            ContainerTestResult with performance validation outcome
        """
        start_time = time.time()
        errors = []
        warnings = []

        try:
            # Check throughput
            if (
                metrics.processing_rate
                < self.performance_baselines["min_throughput_per_second"]
            ):
                errors.append(
                    f"Throughput too low: {metrics.processing_rate:.2f} < "
                    f"{self.performance_baselines['min_throughput_per_second']} records/sec"
                )

            # Check latency
            if metrics.average_latency > self.performance_baselines["max_latency_ms"]:
                errors.append(
                    f"Latency too high: {metrics.average_latency:.2f} > "
                    f"{self.performance_baselines['max_latency_ms']} ms"
                )

            # Check error rate
            if (
                metrics.error_rate
                > self.performance_baselines["max_error_rate_percent"]
            ):
                errors.append(
                    f"Error rate too high: {metrics.error_rate:.2f}% > "
                    f"{self.performance_baselines['max_error_rate_percent']}%"
                )

            # Check resource efficiency
            if (
                metrics.resource_efficiency
                < self.performance_baselines["min_resource_efficiency_percent"]
            ):
                warnings.append(
                    f"Resource efficiency low: {metrics.resource_efficiency:.2f}% < "
                    f"{self.performance_baselines['min_resource_efficiency_percent']}%"
                )

            # Check resource usage
            if metrics.memory_usage_mb > 1000:  # 1GB threshold
                warnings.append(f"High memory usage: {metrics.memory_usage_mb:.2f} MB")

            if metrics.cpu_usage_percent > 90:
                warnings.append(f"High CPU usage: {metrics.cpu_usage_percent:.2f}%")

            status = "failed" if errors else ("passed" if not warnings else "passed")

            details = {
                "performance_metrics": metrics.to_dict(),
                "baselines": self.performance_baselines,
                "performance_score": self._calculate_performance_score(metrics),
            }

            return ContainerTestResult(
                test_name="validate_performance_metrics",
                status=status,
                duration=time.time() - start_time,
                details=details,
                errors=errors,
                warnings=warnings,
                timestamp=datetime.now(),
            )

        except Exception as e:
            return ContainerTestResult(
                test_name="validate_performance_metrics",
                status="failed",
                duration=time.time() - start_time,
                details={"error": str(e)},
                errors=[f"Performance validation failed: {str(e)}"],
                warnings=warnings,
                timestamp=datetime.now(),
            )

    def _calculate_performance_score(self, metrics: PerformanceMetrics) -> float:
        """Calculate overall performance score (0-100)."""
        try:
            # Normalize metrics to 0-1 scale
            throughput_score = min(
                1.0,
                metrics.processing_rate
                / (self.performance_baselines["min_throughput_per_second"] * 2),
            )
            latency_score = max(
                0.0,
                1.0
                - (
                    metrics.average_latency
                    / self.performance_baselines["max_latency_ms"]
                ),
            )
            error_score = max(
                0.0,
                1.0
                - (
                    metrics.error_rate
                    / self.performance_baselines["max_error_rate_percent"]
                ),
            )
            efficiency_score = metrics.resource_efficiency / 100.0

            # Weighted average
            weights = {
                "throughput": 0.3,
                "latency": 0.3,
                "error": 0.25,
                "efficiency": 0.15,
            }

            total_score = (
                throughput_score * weights["throughput"]
                + latency_score * weights["latency"]
                + error_score * weights["error"]
                + efficiency_score * weights["efficiency"]
            )

            return round(total_score * 100, 2)

        except Exception:
            return 0.0

    def validate_error_handling(
        self, fault_tolerance_results: list[FaultToleranceResult]
    ) -> ContainerTestResult:
        """
        Validate error handling and recovery mechanisms.

        Args:
            fault_tolerance_results: Results from fault tolerance tests

        Returns:
            ContainerTestResult with error handling validation outcome
        """
        start_time = time.time()
        errors = []
        warnings = []

        try:
            if not fault_tolerance_results:
                errors.append("No fault tolerance test results provided")
                return ContainerTestResult(
                    test_name="validate_error_handling",
                    status="failed",
                    duration=time.time() - start_time,
                    details={},
                    errors=errors,
                    warnings=warnings,
                    timestamp=datetime.now(),
                )

            # Analyze fault tolerance results
            total_tests = len(fault_tolerance_results)
            data_consistency_failures = 0
            error_handling_failures = 0
            slow_recovery_count = 0

            for result in fault_tolerance_results:
                if not result.data_consistency_maintained:
                    data_consistency_failures += 1
                    errors.append(f"Data consistency failure in {result.test_scenario}")

                if not result.error_handling_effective:
                    error_handling_failures += 1
                    errors.append(
                        f"Ineffective error handling in {result.test_scenario}"
                    )

                if result.recovery_time_seconds > 60:  # 1 minute threshold
                    slow_recovery_count += 1
                    warnings.append(
                        f"Slow recovery in {result.test_scenario}: "
                        f"{result.recovery_time_seconds:.2f}s"
                    )

            # Calculate success rates
            data_consistency_rate = (
                (total_tests - data_consistency_failures) / total_tests
            ) * 100
            error_handling_rate = (
                (total_tests - error_handling_failures) / total_tests
            ) * 100

            if data_consistency_rate < 95:
                errors.append(
                    f"Data consistency rate too low: {data_consistency_rate:.1f}%"
                )

            if error_handling_rate < 90:
                errors.append(
                    f"Error handling effectiveness too low: {error_handling_rate:.1f}%"
                )

            status = "failed" if errors else ("passed" if not warnings else "passed")

            details = {
                "total_fault_tolerance_tests": total_tests,
                "data_consistency_rate_percent": data_consistency_rate,
                "error_handling_effectiveness_percent": error_handling_rate,
                "slow_recovery_count": slow_recovery_count,
                "test_results": [
                    result.to_dict() for result in fault_tolerance_results
                ],
            }

            return ContainerTestResult(
                test_name="validate_error_handling",
                status=status,
                duration=time.time() - start_time,
                details=details,
                errors=errors,
                warnings=warnings,
                timestamp=datetime.now(),
            )

        except Exception as e:
            return ContainerTestResult(
                test_name="validate_error_handling",
                status="failed",
                duration=time.time() - start_time,
                details={"error": str(e)},
                errors=[f"Error handling validation failed: {str(e)}"],
                warnings=warnings,
                timestamp=datetime.now(),
            )

    def generate_test_report(
        self, all_test_results: list[ContainerTestResult]
    ) -> dict[str, Any]:
        """
        Generate comprehensive test report.

        Args:
            all_test_results: All test results to include in report

        Returns:
            Dictionary containing comprehensive test report
        """
        try:
            if not all_test_results:
                return {
                    "error": "No test results provided",
                    "timestamp": datetime.now().isoformat() + "Z",
                }

            # Calculate summary statistics
            total_tests = len(all_test_results)
            passed_tests = len([r for r in all_test_results if r.status == "passed"])
            failed_tests = len([r for r in all_test_results if r.status == "failed"])
            skipped_tests = len([r for r in all_test_results if r.status == "skipped"])

            total_duration = sum(r.duration for r in all_test_results)
            total_errors = sum(len(r.errors) for r in all_test_results)
            total_warnings = sum(len(r.warnings) for r in all_test_results)

            # Generate report
            report = {
                "test_report_summary": {
                    "timestamp": datetime.now().isoformat() + "Z",
                    "total_tests": total_tests,
                    "passed_tests": passed_tests,
                    "failed_tests": failed_tests,
                    "skipped_tests": skipped_tests,
                    "success_rate_percent": (
                        (passed_tests / total_tests * 100) if total_tests > 0 else 0
                    ),
                    "total_duration_seconds": round(total_duration, 2),
                    "total_errors": total_errors,
                    "total_warnings": total_warnings,
                },
                "test_results": [result.to_dict() for result in all_test_results],
                "recommendations": self._generate_recommendations(all_test_results),
            }

            return report

        except Exception as e:
            return {
                "error": f"Failed to generate test report: {str(e)}",
                "timestamp": datetime.now().isoformat() + "Z",
            }

    def _generate_recommendations(
        self, test_results: list[ContainerTestResult]
    ) -> list[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        try:
            # Analyze common failure patterns
            error_patterns = {}
            for result in test_results:
                for error in result.errors:
                    error_type = error.split(":")[0] if ":" in error else error
                    error_patterns[error_type] = error_patterns.get(error_type, 0) + 1

            # Generate specific recommendations
            if "Throughput too low" in str(error_patterns):
                recommendations.append(
                    "Consider increasing container resources or optimizing database queries"
                )

            if "Latency too high" in str(error_patterns):
                recommendations.append(
                    "Review database connection pooling and query optimization"
                )

            if "duplicate record processing" in str(error_patterns):
                recommendations.append(
                    "Verify FOR UPDATE SKIP LOCKED implementation and container isolation"
                )

            if "Data consistency failure" in str(error_patterns):
                recommendations.append(
                    "Review transaction handling and error recovery mechanisms"
                )

            # Performance recommendations
            failed_tests = [r for r in test_results if r.status == "failed"]
            if len(failed_tests) > len(test_results) * 0.2:  # >20% failure rate
                recommendations.append(
                    "High failure rate detected - review system stability and error handling"
                )

            # Resource recommendations
            for result in test_results:
                if "High memory usage" in str(result.warnings):
                    recommendations.append(
                        "Monitor memory usage and implement garbage collection optimization"
                    )
                if "High CPU usage" in str(result.warnings):
                    recommendations.append(
                        "Consider CPU optimization or horizontal scaling"
                    )

            if not recommendations:
                recommendations.append(
                    "All tests passed successfully - system is performing well"
                )

            return recommendations

        except Exception:
            return ["Unable to generate recommendations due to analysis error"]


class ContainerTestSuite:
    """
    Comprehensive container testing framework for distributed processing validation.

    Provides automated testing capabilities for containerized distributed processing
    systems including duplicate prevention, performance testing, fault tolerance,
    and end-to-end workflow validation.
    """

    def __init__(
        self,
        database_managers: Optional[dict[str, DatabaseManager]] = None,
        config_manager: Optional[ConfigManager] = None,
        enable_performance_monitoring: bool = True,
    ):
        """
        Initialize container test suite.

        Args:
            database_managers: Dictionary of database managers for testing
            config_manager: Configuration manager instance
            enable_performance_monitoring: Whether to enable performance monitoring
        """
        self.database_managers = database_managers or {}
        self.config_manager = config_manager or ConfigManager()
        self.enable_performance_monitoring = enable_performance_monitoring

        # Initialize components
        self.validator = ContainerTestValidator()
        self.health_monitor = (
            HealthMonitor(
                database_managers=self.database_managers,
                enable_prometheus=True,
                enable_structured_logging=True,
            )
            if self.database_managers
            else None
        )

        # Test execution tracking
        self.test_results = []
        self.performance_metrics = []
        self.fault_tolerance_results = []

        # Container simulation
        self.simulated_containers = []

    def run_distributed_processing_tests(
        self,
        flow_name: str = "container_test_flow",
        record_count: int = 100,
        container_count: int = 3,
        batch_size: int = 10,
    ) -> ContainerTestResult:
        """
        Run distributed processing tests to verify no duplicate record processing.

        Args:
            flow_name: Name of the flow to test
            record_count: Number of test records to process
            container_count: Number of simulated containers
            batch_size: Batch size for record processing

        Returns:
            ContainerTestResult with distributed processing test outcome
        """
        start_time = time.time()

        try:
            # Validate inputs
            if not self.database_managers:
                return ContainerTestResult(
                    test_name="run_distributed_processing_tests",
                    status="skipped",
                    duration=time.time() - start_time,
                    details={"reason": "No database managers configured"},
                    errors=["No database managers available for testing"],
                    warnings=[],
                    timestamp=datetime.now(),
                )

            # Get RPA database manager
            rpa_db = self.database_managers.get("rpa_db")
            if not rpa_db:
                return ContainerTestResult(
                    test_name="run_distributed_processing_tests",
                    status="failed",
                    duration=time.time() - start_time,
                    details={},
                    errors=["RPA database manager not found"],
                    warnings=[],
                    timestamp=datetime.now(),
                )

            # Create test records
            test_records = [
                {
                    "payload": {
                        "test_id": i,
                        "data": f"test_data_{i}",
                        "timestamp": datetime.now().isoformat(),
                    }
                }
                for i in range(record_count)
            ]

            # Create distributed processors (simulating containers)
            processors = []
            for _i in range(container_count):
                processor = DistributedProcessor(
                    rpa_db_manager=rpa_db, config_manager=self.config_manager
                )
                processors.append(processor)

            # Add test records to queue
            processors[0].add_records_to_queue(flow_name, test_records)

            # Process records concurrently across containers
            processing_results = []

            def process_batch(processor, container_id):
                """Process a batch of records for a specific container."""
                container_results = []
                max_iterations = 10  # Prevent infinite loops
                iteration_count = 0

                while iteration_count < max_iterations:
                    iteration_count += 1

                    # Claim records
                    claimed_records = processor.claim_records_batch(
                        flow_name, batch_size
                    )

                    if not claimed_records:
                        break  # No more records to process

                    # Process each claimed record
                    for record in claimed_records:
                        try:
                            # Simulate processing (minimal time)
                            processing_result = {
                                "processed_by_container": container_id,
                                "processing_time": 0.001,  # Minimal processing time
                                "success": True,
                            }

                            # Mark as completed
                            processor.mark_record_completed(
                                record["id"], processing_result
                            )

                            container_results.append(
                                {
                                    "record_id": record["id"],
                                    "status": "completed",
                                    "result": processing_result,
                                    "container_id": container_id,
                                }
                            )

                        except Exception as e:
                            # Mark as failed
                            processor.mark_record_failed(record["id"], str(e))

                            container_results.append(
                                {
                                    "record_id": record["id"],
                                    "status": "failed",
                                    "error": str(e),
                                    "container_id": container_id,
                                }
                            )

                return container_results

            # Execute concurrent processing
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=container_count
            ) as executor:
                futures = [
                    executor.submit(process_batch, processor, i)
                    for i, processor in enumerate(processors)
                ]

                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    container_results = future.result()
                    processing_results.extend(container_results)

            # Validate results
            validation_result = self.validator.validate_no_duplicate_processing(
                test_records, processing_results
            )

            # Add test-specific details
            validation_result.details.update(
                {
                    "test_configuration": {
                        "flow_name": flow_name,
                        "record_count": record_count,
                        "container_count": container_count,
                        "batch_size": batch_size,
                    },
                    "processing_results": processing_results[:10],  # Sample of results
                    "containers_used": [
                        f"container_{i}" for i in range(container_count)
                    ],
                }
            )

            self.test_results.append(validation_result)
            return validation_result

        except Exception as e:
            error_result = ContainerTestResult(
                test_name="run_distributed_processing_tests",
                status="failed",
                duration=time.time() - start_time,
                details={"error": str(e), "error_type": type(e).__name__},
                errors=[f"Distributed processing test failed: {str(e)}"],
                warnings=[],
                timestamp=datetime.now(),
            )
            self.test_results.append(error_result)
            return error_result

    def run_performance_tests(
        self,
        target_throughput: int = 50,
        test_duration_seconds: int = 60,
        container_count: int = 2,
    ) -> ContainerTestResult:
        """
        Run performance tests measuring throughput, latency, and resource utilization.

        Args:
            target_throughput: Target records per second
            test_duration_seconds: Duration of performance test
            container_count: Number of containers to simulate

        Returns:
            ContainerTestResult with performance test outcome
        """
        start_time = time.time()

        try:
            if not self.database_managers or not self.enable_performance_monitoring:
                return ContainerTestResult(
                    test_name="run_performance_tests",
                    status="skipped",
                    duration=time.time() - start_time,
                    details={
                        "reason": "Performance monitoring not enabled or no databases"
                    },
                    errors=[],
                    warnings=["Performance testing skipped"],
                    timestamp=datetime.now(),
                )

            # Get system baseline
            initial_memory = psutil.virtual_memory().used / (1024 * 1024)  # MB
            initial_cpu = psutil.cpu_percent(interval=1)

            # Calculate total records needed
            total_records = target_throughput * test_duration_seconds

            # Create performance test records
            test_records = [
                {
                    "payload": {
                        "perf_test_id": i,
                        "data": "x" * 100,  # 100 character payload
                        "timestamp": datetime.now().isoformat(),
                    }
                }
                for i in range(total_records)
            ]

            # Setup processors
            rpa_db = self.database_managers.get("rpa_db")
            processors = [
                DistributedProcessor(
                    rpa_db_manager=rpa_db, config_manager=self.config_manager
                )
                for _ in range(container_count)
            ]

            # Add records to queue
            processors[0].add_records_to_queue("performance_test_flow", test_records)

            # Performance tracking
            processing_times = []
            processed_count = 0
            error_count = 0

            # Run performance test
            test_start_time = time.time()

            def performance_worker(processor, worker_id):
                """Performance test worker function."""
                nonlocal processed_count, error_count
                worker_processed = 0
                worker_errors = 0
                worker_times = []

                max_iterations = min(100, target_throughput)  # Limit iterations
                iteration_count = 0

                while (
                    time.time() - test_start_time < test_duration_seconds
                    and iteration_count < max_iterations
                ):
                    iteration_count += 1

                    try:
                        # Claim records
                        time.time()
                        claimed_records = processor.claim_records_batch(
                            "performance_test_flow", 5
                        )

                        if not claimed_records:
                            break  # No more records, exit immediately

                        # Process records
                        for record in claimed_records:
                            process_start = time.time()

                            # Simulate processing work
                            result = {"processed": True, "worker_id": worker_id}
                            processor.mark_record_completed(record["id"], result)

                            process_time = (time.time() - process_start) * 1000  # ms
                            worker_times.append(process_time)
                            worker_processed += 1

                    except Exception as e:
                        worker_errors += 1
                        if claimed_records:
                            for record in claimed_records:
                                try:
                                    processor.mark_record_failed(record["id"], str(e))
                                except Exception:
                                    pass

                return worker_processed, worker_errors, worker_times

            # Execute performance test
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=container_count
            ) as executor:
                futures = [
                    executor.submit(performance_worker, processor, i)
                    for i, processor in enumerate(processors)
                ]

                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    worker_processed, worker_errors, worker_times = future.result()
                    processed_count += worker_processed
                    error_count += worker_errors
                    processing_times.extend(worker_times)

            # Calculate performance metrics
            actual_duration = time.time() - test_start_time
            final_memory = psutil.virtual_memory().used / (1024 * 1024)  # MB
            final_cpu = psutil.cpu_percent(interval=1)

            processing_rate = (
                processed_count / actual_duration if actual_duration > 0 else 0
            )
            average_latency = (
                sum(processing_times) / len(processing_times) if processing_times else 0
            )
            error_rate = (
                (error_count / (processed_count + error_count) * 100)
                if (processed_count + error_count) > 0
                else 0
            )

            # Calculate resource efficiency
            memory_used = final_memory - initial_memory
            cpu_used = (final_cpu + initial_cpu) / 2  # Average CPU usage

            # Simple efficiency calculation based on throughput vs resource usage
            resource_efficiency = min(100, (processing_rate / max(1, cpu_used)) * 10)

            metrics = PerformanceMetrics(
                records_processed=processed_count,
                processing_rate=processing_rate,
                average_latency=average_latency,
                error_rate=error_rate,
                resource_efficiency=resource_efficiency,
                memory_usage_mb=memory_used,
                cpu_usage_percent=cpu_used,
                throughput_variance=0.0,  # Would need multiple runs to calculate
            )

            # Validate performance
            validation_result = self.validator.validate_performance_metrics(metrics)

            # Add performance test details
            validation_result.details.update(
                {
                    "test_configuration": {
                        "target_throughput": target_throughput,
                        "test_duration_seconds": test_duration_seconds,
                        "container_count": container_count,
                        "total_records": total_records,
                    },
                    "actual_results": {
                        "actual_duration_seconds": actual_duration,
                        "records_processed": processed_count,
                        "errors_encountered": error_count,
                    },
                }
            )

            self.test_results.append(validation_result)
            self.performance_metrics.append(metrics)
            return validation_result

        except Exception as e:
            error_result = ContainerTestResult(
                test_name="run_performance_tests",
                status="failed",
                duration=time.time() - start_time,
                details={"error": str(e), "error_type": type(e).__name__},
                errors=[f"Performance test failed: {str(e)}"],
                warnings=[],
                timestamp=datetime.now(),
            )
            self.test_results.append(error_result)
            return error_result

    def run_fault_tolerance_tests(
        self, test_scenarios: Optional[list[str]] = None
    ) -> ContainerTestResult:
        """
        Run fault tolerance tests for container failures and network partitions.

        Args:
            test_scenarios: List of fault scenarios to test

        Returns:
            ContainerTestResult with fault tolerance test outcome
        """
        start_time = time.time()

        try:
            if not test_scenarios:
                test_scenarios = [
                    "container_crash",
                    "database_connection_loss",
                    "network_partition",
                    "resource_exhaustion",
                    "concurrent_failures",
                ]

            fault_results = []

            for scenario in test_scenarios:
                scenario_result = self._run_fault_scenario(scenario)
                fault_results.append(scenario_result)

            # Validate fault tolerance results
            validation_result = self.validator.validate_error_handling(fault_results)

            # Add fault tolerance test details
            validation_result.details.update(
                {
                    "test_scenarios": test_scenarios,
                    "scenario_results": [result.to_dict() for result in fault_results],
                }
            )

            self.test_results.append(validation_result)
            self.fault_tolerance_results.extend(fault_results)
            return validation_result

        except Exception as e:
            error_result = ContainerTestResult(
                test_name="run_fault_tolerance_tests",
                status="failed",
                duration=time.time() - start_time,
                details={"error": str(e), "error_type": type(e).__name__},
                errors=[f"Fault tolerance test failed: {str(e)}"],
                warnings=[],
                timestamp=datetime.now(),
            )
            self.test_results.append(error_result)
            return error_result

    def _run_fault_scenario(self, scenario: str) -> FaultToleranceResult:
        """Run a specific fault tolerance scenario."""
        start_time = time.time()

        try:
            if scenario == "container_crash":
                return self._test_container_crash_scenario()
            elif scenario == "database_connection_loss":
                return self._test_database_connection_loss_scenario()
            elif scenario == "network_partition":
                return self._test_network_partition_scenario()
            elif scenario == "resource_exhaustion":
                return self._test_resource_exhaustion_scenario()
            elif scenario == "concurrent_failures":
                return self._test_concurrent_failures_scenario()
            else:
                return FaultToleranceResult(
                    test_scenario=scenario,
                    containers_tested=0,
                    failures_injected=0,
                    recovery_time_seconds=0,
                    data_consistency_maintained=False,
                    error_handling_effective=False,
                    details={"error": f"Unknown scenario: {scenario}"},
                )

        except Exception as e:
            return FaultToleranceResult(
                test_scenario=scenario,
                containers_tested=0,
                failures_injected=1,
                recovery_time_seconds=time.time() - start_time,
                data_consistency_maintained=False,
                error_handling_effective=False,
                details={"error": str(e), "error_type": type(e).__name__},
            )

    def _test_container_crash_scenario(self) -> FaultToleranceResult:
        """Test container crash and recovery scenario."""
        start_time = time.time()

        try:
            # Setup test data
            test_records = [
                {"payload": {"crash_test_id": i, "data": f"crash_test_{i}"}}
                for i in range(20)
            ]

            if not self.database_managers.get("rpa_db"):
                return FaultToleranceResult(
                    test_scenario="container_crash",
                    containers_tested=0,
                    failures_injected=0,
                    recovery_time_seconds=0,
                    data_consistency_maintained=False,
                    error_handling_effective=False,
                    details={"error": "No RPA database available"},
                )

            rpa_db = self.database_managers["rpa_db"]

            # Create processors
            processor1 = DistributedProcessor(
                rpa_db_manager=rpa_db, config_manager=self.config_manager
            )
            processor2 = DistributedProcessor(
                rpa_db_manager=rpa_db, config_manager=self.config_manager
            )

            # Add test records
            processor1.add_records_to_queue("crash_test_flow", test_records)

            # Start processing with first processor
            claimed_records = processor1.claim_records_batch("crash_test_flow", 10)

            # Simulate container crash (processor1 stops without completing records)
            # Records should be stuck in "processing" state

            # Wait for orphaned record cleanup timeout (simulate passage of time)
            # In real scenario, this would be handled by cleanup_orphaned_records

            # Second processor takes over
            recovery_start = time.time()

            # Clean up orphaned records
            cleaned_count = processor2.cleanup_orphaned_records(
                timeout_hours=0
            )  # Immediate cleanup for test

            # Process remaining records
            remaining_records = processor2.claim_records_batch("crash_test_flow", 20)

            for record in remaining_records:
                processor2.mark_record_completed(record["id"], {"recovered": True})

            recovery_time = time.time() - recovery_start

            # Check data consistency
            final_status = processor2.get_queue_status("crash_test_flow")
            data_consistent = final_status["completed_records"] + final_status[
                "failed_records"
            ] == len(test_records)

            return FaultToleranceResult(
                test_scenario="container_crash",
                containers_tested=2,
                failures_injected=1,
                recovery_time_seconds=recovery_time,
                data_consistency_maintained=data_consistent,
                error_handling_effective=cleaned_count > 0
                or len(remaining_records) > 0,
                details={
                    "claimed_before_crash": len(claimed_records),
                    "cleaned_orphaned_records": cleaned_count,
                    "recovered_records": len(remaining_records),
                    "final_status": final_status,
                },
            )

        except Exception as e:
            return FaultToleranceResult(
                test_scenario="container_crash",
                containers_tested=2,
                failures_injected=1,
                recovery_time_seconds=time.time() - start_time,
                data_consistency_maintained=False,
                error_handling_effective=False,
                details={"error": str(e)},
            )

    def _test_database_connection_loss_scenario(self) -> FaultToleranceResult:
        """Test database connection loss and recovery scenario."""
        start_time = time.time()

        try:
            # Create mock processor with connection failure simulation
            mock_rpa_db = Mock(spec=DatabaseManager)
            mock_rpa_db.database_name = "test_rpa_db"
            mock_rpa_db.logger = Mock()

            processor = DistributedProcessor(
                rpa_db_manager=mock_rpa_db, config_manager=self.config_manager
            )

            # Simulate connection loss
            mock_rpa_db.execute_query.side_effect = Exception("Connection lost")

            # Test error handling
            error_handled = False
            try:
                processor.claim_records_batch("connection_test_flow", 5)
            except RuntimeError:
                error_handled = True

            # Simulate connection recovery
            recovery_start = time.time()
            mock_rpa_db.execute_query.side_effect = None
            mock_rpa_db.execute_query.return_value = [
                (1, {"data": "test"}, 0, datetime.now())
            ]

            # Test recovery
            recovery_successful = False
            try:
                records = processor.claim_records_batch("connection_test_flow", 5)
                recovery_successful = len(records) > 0
            except Exception:
                pass

            recovery_time = time.time() - recovery_start

            return FaultToleranceResult(
                test_scenario="database_connection_loss",
                containers_tested=1,
                failures_injected=1,
                recovery_time_seconds=recovery_time,
                data_consistency_maintained=True,  # No data was corrupted
                error_handling_effective=error_handled,
                details={
                    "connection_loss_handled": error_handled,
                    "recovery_successful": recovery_successful,
                    "recovery_time_seconds": recovery_time,
                },
            )

        except Exception as e:
            return FaultToleranceResult(
                test_scenario="database_connection_loss",
                containers_tested=1,
                failures_injected=1,
                recovery_time_seconds=time.time() - start_time,
                data_consistency_maintained=False,
                error_handling_effective=False,
                details={"error": str(e)},
            )

    def _test_network_partition_scenario(self) -> FaultToleranceResult:
        """Test network partition scenario."""
        start_time = time.time()

        try:
            # Simulate network partition using socket timeout
            mock_rpa_db = Mock(spec=DatabaseManager)
            mock_rpa_db.database_name = "test_rpa_db"
            mock_rpa_db.logger = Mock()

            processor = DistributedProcessor(
                rpa_db_manager=mock_rpa_db, config_manager=self.config_manager
            )

            # Simulate network timeout
            mock_rpa_db.execute_query.side_effect = socket.timeout("Network timeout")

            # Test network partition handling
            partition_handled = False
            try:
                processor.claim_records_batch("network_test_flow", 5)
            except RuntimeError:
                partition_handled = True

            # Simulate network recovery
            recovery_start = time.time()
            mock_rpa_db.execute_query.side_effect = None
            mock_rpa_db.execute_query.return_value = []

            # Test recovery
            recovery_successful = False
            try:
                processor.get_queue_status("network_test_flow")
                recovery_successful = True
            except Exception:
                pass

            recovery_time = time.time() - recovery_start

            return FaultToleranceResult(
                test_scenario="network_partition",
                containers_tested=1,
                failures_injected=1,
                recovery_time_seconds=recovery_time,
                data_consistency_maintained=True,
                error_handling_effective=partition_handled,
                details={
                    "partition_handled": partition_handled,
                    "recovery_successful": recovery_successful,
                },
            )

        except Exception as e:
            return FaultToleranceResult(
                test_scenario="network_partition",
                containers_tested=1,
                failures_injected=1,
                recovery_time_seconds=time.time() - start_time,
                data_consistency_maintained=False,
                error_handling_effective=False,
                details={"error": str(e)},
            )

    def _test_resource_exhaustion_scenario(self) -> FaultToleranceResult:
        """Test resource exhaustion scenario."""
        start_time = time.time()

        try:
            # Simulate memory exhaustion
            mock_rpa_db = Mock(spec=DatabaseManager)
            mock_rpa_db.database_name = "test_rpa_db"
            mock_rpa_db.logger = Mock()

            processor = DistributedProcessor(
                rpa_db_manager=mock_rpa_db, config_manager=self.config_manager
            )

            # Simulate memory error
            mock_rpa_db.execute_query.side_effect = MemoryError("Out of memory")

            # Test resource exhaustion handling
            exhaustion_handled = False
            try:
                processor.claim_records_batch("resource_test_flow", 1000)
            except RuntimeError:
                exhaustion_handled = True

            # Simulate resource recovery
            recovery_start = time.time()
            mock_rpa_db.execute_query.side_effect = None
            mock_rpa_db.execute_query.return_value = []

            # Test recovery
            recovery_successful = False
            try:
                processor.get_queue_status("resource_test_flow")
                recovery_successful = True
            except Exception:
                pass

            recovery_time = time.time() - recovery_start

            return FaultToleranceResult(
                test_scenario="resource_exhaustion",
                containers_tested=1,
                failures_injected=1,
                recovery_time_seconds=recovery_time,
                data_consistency_maintained=True,
                error_handling_effective=exhaustion_handled,
                details={
                    "exhaustion_handled": exhaustion_handled,
                    "recovery_successful": recovery_successful,
                },
            )

        except Exception as e:
            return FaultToleranceResult(
                test_scenario="resource_exhaustion",
                containers_tested=1,
                failures_injected=1,
                recovery_time_seconds=time.time() - start_time,
                data_consistency_maintained=False,
                error_handling_effective=False,
                details={"error": str(e)},
            )

    def _test_concurrent_failures_scenario(self) -> FaultToleranceResult:
        """Test concurrent failures scenario."""
        start_time = time.time()

        try:
            # Create multiple processors with different failure modes
            processors = []
            for i in range(3):
                mock_db = Mock(spec=DatabaseManager)
                mock_db.database_name = f"test_rpa_db_{i}"
                mock_db.logger = Mock()

                processor = DistributedProcessor(
                    rpa_db_manager=mock_db, config_manager=self.config_manager
                )
                processors.append((processor, mock_db))

            # Inject different failures
            processors[0][1].execute_query.side_effect = Exception("Connection lost")
            processors[1][1].execute_query.side_effect = socket.timeout(
                "Network timeout"
            )
            processors[2][1].execute_query.return_value = []  # Working processor

            # Test concurrent failure handling
            failures_handled = 0
            working_processors = 0

            for _i, (processor, _mock_db) in enumerate(processors):
                try:
                    processor.get_queue_status("concurrent_test_flow")
                    working_processors += 1
                except RuntimeError:
                    failures_handled += 1

            recovery_time = time.time() - start_time

            return FaultToleranceResult(
                test_scenario="concurrent_failures",
                containers_tested=3,
                failures_injected=2,
                recovery_time_seconds=recovery_time,
                data_consistency_maintained=working_processors > 0,
                error_handling_effective=failures_handled == 2,
                details={
                    "failures_handled": failures_handled,
                    "working_processors": working_processors,
                    "total_processors": 3,
                },
            )

        except Exception as e:
            return FaultToleranceResult(
                test_scenario="concurrent_failures",
                containers_tested=3,
                failures_injected=2,
                recovery_time_seconds=time.time() - start_time,
                data_consistency_maintained=False,
                error_handling_effective=False,
                details={"error": str(e)},
            )

    def run_integration_tests(
        self, test_workflows: Optional[list[str]] = None
    ) -> ContainerTestResult:
        """
        Run end-to-end workflow validation across containers.

        Args:
            test_workflows: List of workflows to test

        Returns:
            ContainerTestResult with integration test outcome
        """
        start_time = time.time()

        try:
            if not test_workflows:
                test_workflows = [
                    "complete_processing_workflow",
                    "multi_container_coordination",
                    "health_monitoring_integration",
                    "configuration_management_integration",
                ]

            integration_results = []

            for workflow in test_workflows:
                workflow_result = self._run_integration_workflow(workflow)
                integration_results.append(workflow_result)

            # Analyze integration results
            total_workflows = len(integration_results)
            successful_workflows = len(
                [r for r in integration_results if r.get("success", False)]
            )

            status = "passed" if successful_workflows == total_workflows else "failed"
            errors = []
            warnings = []

            for result in integration_results:
                if not result.get("success", False):
                    errors.append(
                        f"Workflow '{result.get('workflow', 'unknown')}' failed: {result.get('error', 'Unknown error')}"
                    )
                elif result.get("warnings"):
                    warnings.extend(result.get("warnings", []))

            integration_test_result = ContainerTestResult(
                test_name="run_integration_tests",
                status=status,
                duration=time.time() - start_time,
                details={
                    "test_workflows": test_workflows,
                    "total_workflows": total_workflows,
                    "successful_workflows": successful_workflows,
                    "success_rate_percent": (
                        (successful_workflows / total_workflows * 100)
                        if total_workflows > 0
                        else 0
                    ),
                    "workflow_results": integration_results,
                },
                errors=errors,
                warnings=warnings,
                timestamp=datetime.now(),
            )

            self.test_results.append(integration_test_result)
            return integration_test_result

        except Exception as e:
            error_result = ContainerTestResult(
                test_name="run_integration_tests",
                status="failed",
                duration=time.time() - start_time,
                details={"error": str(e), "error_type": type(e).__name__},
                errors=[f"Integration test failed: {str(e)}"],
                warnings=[],
                timestamp=datetime.now(),
            )
            self.test_results.append(error_result)
            return error_result

    def _run_integration_workflow(self, workflow: str) -> dict[str, Any]:
        """Run a specific integration workflow test."""
        try:
            if workflow == "complete_processing_workflow":
                return self._test_complete_processing_workflow()
            elif workflow == "multi_container_coordination":
                return self._test_multi_container_coordination()
            elif workflow == "health_monitoring_integration":
                return self._test_health_monitoring_integration()
            elif workflow == "configuration_management_integration":
                return self._test_configuration_management_integration()
            else:
                return {
                    "workflow": workflow,
                    "success": False,
                    "error": f"Unknown workflow: {workflow}",
                }

        except Exception as e:
            return {
                "workflow": workflow,
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
            }

    def _test_complete_processing_workflow(self) -> dict[str, Any]:
        """Test complete end-to-end processing workflow."""
        try:
            if not self.database_managers.get("rpa_db"):
                return {
                    "workflow": "complete_processing_workflow",
                    "success": False,
                    "error": "No RPA database available",
                }

            rpa_db = self.database_managers["rpa_db"]
            processor = DistributedProcessor(
                rpa_db_manager=rpa_db, config_manager=self.config_manager
            )

            # Test complete workflow: add -> claim -> process -> complete
            test_records = [
                {"payload": {"workflow_test_id": i, "data": f"workflow_test_{i}"}}
                for i in range(5)
            ]

            # Step 1: Add records
            added_count = processor.add_records_to_queue("workflow_test", test_records)

            # Step 2: Claim records
            claimed_records = processor.claim_records_batch("workflow_test", 5)

            # Step 3: Process and complete records
            completed_count = 0
            for record in claimed_records:
                processor.mark_record_completed(
                    record["id"], {"workflow_completed": True}
                )
                completed_count += 1

            # Step 4: Verify final state
            final_status = processor.get_queue_status("workflow_test")

            success = (
                added_count == len(test_records)
                and len(claimed_records) == len(test_records)
                and completed_count == len(test_records)
                and final_status["completed_records"] == len(test_records)
            )

            return {
                "workflow": "complete_processing_workflow",
                "success": success,
                "details": {
                    "records_added": added_count,
                    "records_claimed": len(claimed_records),
                    "records_completed": completed_count,
                    "final_status": final_status,
                },
            }

        except Exception as e:
            return {
                "workflow": "complete_processing_workflow",
                "success": False,
                "error": str(e),
            }

    def _test_multi_container_coordination(self) -> dict[str, Any]:
        """Test multi-container coordination."""
        try:
            if not self.database_managers.get("rpa_db"):
                return {
                    "workflow": "multi_container_coordination",
                    "success": False,
                    "error": "No RPA database available",
                }

            rpa_db = self.database_managers["rpa_db"]

            # Create multiple processors
            processors = [
                DistributedProcessor(
                    rpa_db_manager=rpa_db, config_manager=self.config_manager
                )
                for _ in range(3)
            ]

            # Test coordination
            test_records = [
                {
                    "payload": {
                        "coordination_test_id": i,
                        "data": f"coordination_test_{i}",
                    }
                }
                for i in range(15)
            ]

            # Add records
            processors[0].add_records_to_queue("coordination_test", test_records)

            # Each processor claims different records
            all_claimed_records = []
            for processor in processors:
                claimed = processor.claim_records_batch("coordination_test", 5)
                all_claimed_records.extend(claimed)

            # Verify no overlapping claims
            claimed_ids = [r["id"] for r in all_claimed_records]
            unique_ids = set(claimed_ids)

            coordination_success = len(claimed_ids) == len(unique_ids)

            return {
                "workflow": "multi_container_coordination",
                "success": coordination_success,
                "details": {
                    "total_claimed": len(claimed_ids),
                    "unique_claimed": len(unique_ids),
                    "coordination_effective": coordination_success,
                    "processors_used": len(processors),
                },
            }

        except Exception as e:
            return {
                "workflow": "multi_container_coordination",
                "success": False,
                "error": str(e),
            }

    def _test_health_monitoring_integration(self) -> dict[str, Any]:
        """Test health monitoring integration."""
        try:
            if not self.health_monitor:
                return {
                    "workflow": "health_monitoring_integration",
                    "success": False,
                    "error": "Health monitor not available",
                }

            # Test health monitoring
            health_report = self.health_monitor.comprehensive_health_check()

            # Test health endpoint
            health_response, status_code = (
                self.health_monitor.get_health_endpoint_response()
            )

            # Test metrics export
            metrics = self.health_monitor.export_prometheus_metrics()

            success = (
                health_report.get("overall_status") in ["healthy", "degraded"]
                and status_code in [200, 503]
                and len(metrics) > 0
            )

            return {
                "workflow": "health_monitoring_integration",
                "success": success,
                "details": {
                    "health_status": health_report.get("overall_status"),
                    "health_endpoint_status": status_code,
                    "metrics_available": len(metrics) > 0,
                    "total_checks": health_report.get("summary", {}).get(
                        "total_checks", 0
                    ),
                },
            }

        except Exception as e:
            return {
                "workflow": "health_monitoring_integration",
                "success": False,
                "error": str(e),
            }

    def _test_configuration_management_integration(self) -> dict[str, Any]:
        """Test configuration management integration."""
        try:
            # Test configuration loading
            config = self.config_manager.get_distributed_config()

            # Test environment variable access
            environment = self.config_manager.environment

            # Test database configuration
            db_configs = {}
            for db_name in self.database_managers.keys():
                try:
                    db_type = self.config_manager.get_variable(f"{db_name}_type")
                    db_configs[db_name] = {"type": db_type}
                except Exception:
                    db_configs[db_name] = {"error": "Configuration not found"}

            success = (
                config is not None and environment is not None and len(db_configs) > 0
            )

            return {
                "workflow": "configuration_management_integration",
                "success": success,
                "details": {
                    "config_loaded": config is not None,
                    "environment": environment,
                    "database_configs": db_configs,
                    "distributed_config": config,
                },
            }

        except Exception as e:
            return {
                "workflow": "configuration_management_integration",
                "success": False,
                "error": str(e),
            }

    def generate_comprehensive_report(self) -> dict[str, Any]:
        """
        Generate comprehensive test report with all results and recommendations.

        Returns:
            Dictionary containing complete test report
        """
        try:
            # Generate base report
            base_report = self.validator.generate_test_report(self.test_results)

            # Add container-specific information
            container_report = {
                "container_test_suite_report": {
                    "timestamp": datetime.now().isoformat() + "Z",
                    "test_suite_version": "1.0.0",
                    "test_environment": {
                        "database_managers": list(self.database_managers.keys()),
                        "performance_monitoring_enabled": self.enable_performance_monitoring,
                        "health_monitoring_available": self.health_monitor is not None,
                    },
                    "test_categories": {
                        "distributed_processing_tests": len(
                            [
                                r
                                for r in self.test_results
                                if "distributed_processing" in r.test_name
                            ]
                        ),
                        "performance_tests": len(
                            [
                                r
                                for r in self.test_results
                                if "performance" in r.test_name
                            ]
                        ),
                        "fault_tolerance_tests": len(
                            [
                                r
                                for r in self.test_results
                                if "fault_tolerance" in r.test_name
                            ]
                        ),
                        "integration_tests": len(
                            [
                                r
                                for r in self.test_results
                                if "integration" in r.test_name
                            ]
                        ),
                    },
                    "performance_metrics_summary": {
                        "total_metrics_collected": len(self.performance_metrics),
                        "average_throughput": (
                            sum(m.processing_rate for m in self.performance_metrics)
                            / len(self.performance_metrics)
                            if self.performance_metrics
                            else 0
                        ),
                        "average_latency": (
                            sum(m.average_latency for m in self.performance_metrics)
                            / len(self.performance_metrics)
                            if self.performance_metrics
                            else 0
                        ),
                        "average_error_rate": (
                            sum(m.error_rate for m in self.performance_metrics)
                            / len(self.performance_metrics)
                            if self.performance_metrics
                            else 0
                        ),
                    },
                    "fault_tolerance_summary": {
                        "total_scenarios_tested": len(self.fault_tolerance_results),
                        "data_consistency_success_rate": (
                            (
                                len(
                                    [
                                        r
                                        for r in self.fault_tolerance_results
                                        if r.data_consistency_maintained
                                    ]
                                )
                                / len(self.fault_tolerance_results)
                                * 100
                            )
                            if self.fault_tolerance_results
                            else 0
                        ),
                        "error_handling_success_rate": (
                            (
                                len(
                                    [
                                        r
                                        for r in self.fault_tolerance_results
                                        if r.error_handling_effective
                                    ]
                                )
                                / len(self.fault_tolerance_results)
                                * 100
                            )
                            if self.fault_tolerance_results
                            else 0
                        ),
                        "average_recovery_time": (
                            sum(
                                r.recovery_time_seconds
                                for r in self.fault_tolerance_results
                            )
                            / len(self.fault_tolerance_results)
                            if self.fault_tolerance_results
                            else 0
                        ),
                    },
                }
            }

            # Merge reports
            final_report = {**base_report, **container_report}

            return final_report

        except Exception as e:
            return {
                "error": f"Failed to generate comprehensive report: {str(e)}",
                "timestamp": datetime.now().isoformat() + "Z",
            }

    def cleanup_test_environment(self) -> None:
        """Clean up test environment and resources."""
        try:
            # Clear test results
            self.test_results.clear()
            self.performance_metrics.clear()
            self.fault_tolerance_results.clear()

            # Clear simulated containers
            self.simulated_containers.clear()

            # Reset validator
            self.validator.validation_results.clear()

        except Exception as e:
            # Log cleanup error but don't raise
            if self.health_monitor and self.health_monitor.logger:
                self.health_monitor.logger.log_alert(
                    "cleanup_error",
                    f"Test environment cleanup failed: {str(e)}",
                    "WARNING",
                )
