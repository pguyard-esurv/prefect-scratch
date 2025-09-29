"""
Performance benchmarking suite for container efficiency testing.

This module provides comprehensive benchmarking capabilities to measure
and validate container performance, resource efficiency, and optimization
effectiveness in distributed processing environments.
"""

import json
import logging
import os
import statistics
import time
from datetime import datetime
from typing import Any, Optional

from core.database import DatabaseManager
from core.health_monitor import HealthMonitor
from core.performance_monitor import PerformanceMonitor


class ContainerEfficiencyBenchmark:
    """
    Comprehensive container efficiency benchmarking suite.

    Provides benchmarking capabilities for resource usage, performance
    optimization, and container efficiency validation.
    """

    def __init__(
        self,
        database_managers: Optional[dict[str, DatabaseManager]] = None,
        output_dir: str = "benchmark_results",
    ):
        """
        Initialize container efficiency benchmark.

        Args:
            database_managers: Dictionary of database managers for testing
            output_dir: Directory to store benchmark results
        """
        self.database_managers = database_managers or {}
        self.output_dir = output_dir

        # Initialize components
        self.health_monitor = HealthMonitor(
            database_managers=self.database_managers,
            enable_prometheus=True,
            enable_structured_logging=True,
        )

        self.performance_monitor = PerformanceMonitor(
            database_managers=self.database_managers,
            health_monitor=self.health_monitor,
            enable_detailed_monitoring=True,
        )

        # Setup logging
        self.logger = self._setup_logger()

        # Benchmark configuration
        self.benchmark_config = {
            "resource_collection_iterations": 1000,
            "bottleneck_detection_iterations": 100,
            "optimization_iterations": 50,
            "stress_test_duration": 300,  # 5 minutes
            "baseline_duration": 60,  # 1 minute
            "memory_limit_mb": 4096,
            "cpu_cores": 4,
        }

        # Results storage
        self.benchmark_results = {}

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def _setup_logger(self) -> logging.Logger:
        """Setup benchmark logger."""
        logger = logging.getLogger("container_efficiency_benchmark")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            # File handler
            file_handler = logging.FileHandler(
                os.path.join(self.output_dir, "benchmark.log")
            )
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            # Console handler
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter("%(levelname)s - %(message)s")
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        return logger

    def run_comprehensive_benchmark(self) -> dict[str, Any]:
        """
        Run comprehensive container efficiency benchmark.

        Returns:
            Dictionary containing complete benchmark results
        """
        self.logger.info("Starting comprehensive container efficiency benchmark")

        benchmark_start = time.time()

        try:
            # Initialize results structure
            self.benchmark_results = {
                "benchmark_info": {
                    "start_time": datetime.now().isoformat() + "Z",
                    "configuration": self.benchmark_config.copy(),
                    "environment": self._get_environment_info(),
                },
                "baseline_performance": {},
                "resource_collection_benchmark": {},
                "bottleneck_detection_benchmark": {},
                "optimization_benchmark": {},
                "stress_test_results": {},
                "efficiency_analysis": {},
                "recommendations": [],
            }

            # 1. Establish baseline performance
            self.logger.info("Establishing baseline performance...")
            self.benchmark_results["baseline_performance"] = (
                self._benchmark_baseline_performance()
            )

            # 2. Benchmark resource collection performance
            self.logger.info("Benchmarking resource collection performance...")
            self.benchmark_results["resource_collection_benchmark"] = (
                self._benchmark_resource_collection()
            )

            # 3. Benchmark bottleneck detection performance
            self.logger.info("Benchmarking bottleneck detection performance...")
            self.benchmark_results["bottleneck_detection_benchmark"] = (
                self._benchmark_bottleneck_detection()
            )

            # 4. Benchmark optimization performance
            self.logger.info("Benchmarking optimization performance...")
            self.benchmark_results["optimization_benchmark"] = (
                self._benchmark_optimization()
            )

            # 5. Run stress tests
            self.logger.info("Running container stress tests...")
            self.benchmark_results["stress_test_results"] = self._run_stress_tests()

            # 6. Analyze efficiency
            self.logger.info("Analyzing container efficiency...")
            self.benchmark_results["efficiency_analysis"] = self._analyze_efficiency()

            # 7. Generate recommendations
            self.logger.info("Generating optimization recommendations...")
            self.benchmark_results["recommendations"] = (
                self._generate_benchmark_recommendations()
            )

            # Finalize results
            benchmark_duration = time.time() - benchmark_start
            self.benchmark_results["benchmark_info"]["end_time"] = (
                datetime.now().isoformat() + "Z"
            )
            self.benchmark_results["benchmark_info"][
                "total_duration_seconds"
            ] = benchmark_duration

            # Save results
            self._save_benchmark_results()

            self.logger.info(
                f"Comprehensive benchmark completed in {benchmark_duration:.2f} seconds"
            )

            return self.benchmark_results

        except Exception as e:
            self.logger.error(f"Benchmark failed: {str(e)}")
            self.benchmark_results["error"] = str(e)
            return self.benchmark_results

    def _get_environment_info(self) -> dict[str, Any]:
        """Get environment information for benchmark context."""
        try:
            import psutil

            return {
                "cpu_count": psutil.cpu_count(),
                "memory_total_mb": psutil.virtual_memory().total / (1024 * 1024),
                "disk_total_gb": psutil.disk_usage("/").total / (1024 * 1024 * 1024),
                "python_version": os.sys.version,
                "platform": os.name,
                "container_memory_limit": self.performance_monitor._get_memory_limit(),
                "database_count": len(self.database_managers),
            }
        except Exception as e:
            return {"error": f"Failed to get environment info: {str(e)}"}

    def _benchmark_baseline_performance(self) -> dict[str, Any]:
        """Establish baseline performance metrics."""
        try:
            baseline_results = {
                "duration_seconds": self.benchmark_config["baseline_duration"],
                "samples": [],
                "statistics": {},
            }

            start_time = time.time()
            sample_interval = 5  # 5 seconds between samples

            while time.time() - start_time < self.benchmark_config["baseline_duration"]:
                sample_start = time.time()

                # Collect baseline metrics
                resource_metrics = self.performance_monitor.collect_resource_metrics()
                health_check = self.health_monitor.comprehensive_health_check()

                sample_duration = time.time() - sample_start

                baseline_results["samples"].append(
                    {
                        "timestamp": datetime.now().isoformat() + "Z",
                        "resource_metrics": resource_metrics.to_dict(),
                        "health_status": health_check["overall_status"],
                        "collection_time_ms": sample_duration * 1000,
                    }
                )

                time.sleep(sample_interval)

            # Calculate baseline statistics
            baseline_results["statistics"] = self._calculate_baseline_statistics(
                baseline_results["samples"]
            )

            return baseline_results

        except Exception as e:
            return {"error": f"Baseline benchmark failed: {str(e)}"}

    def _calculate_baseline_statistics(self, samples: list[dict]) -> dict[str, Any]:
        """Calculate statistics from baseline samples."""
        if not samples:
            return {}

        # Extract metrics
        cpu_values = [s["resource_metrics"]["cpu_usage_percent"] for s in samples]
        memory_values = [s["resource_metrics"]["memory_usage_percent"] for s in samples]
        collection_times = [s["collection_time_ms"] for s in samples]

        return {
            "cpu_usage": {
                "mean": statistics.mean(cpu_values),
                "median": statistics.median(cpu_values),
                "stdev": statistics.stdev(cpu_values) if len(cpu_values) > 1 else 0,
                "min": min(cpu_values),
                "max": max(cpu_values),
            },
            "memory_usage": {
                "mean": statistics.mean(memory_values),
                "median": statistics.median(memory_values),
                "stdev": (
                    statistics.stdev(memory_values) if len(memory_values) > 1 else 0
                ),
                "min": min(memory_values),
                "max": max(memory_values),
            },
            "collection_performance": {
                "mean_ms": statistics.mean(collection_times),
                "median_ms": statistics.median(collection_times),
                "stdev_ms": (
                    statistics.stdev(collection_times)
                    if len(collection_times) > 1
                    else 0
                ),
                "min_ms": min(collection_times),
                "max_ms": max(collection_times),
            },
            "sample_count": len(samples),
        }

    def _benchmark_resource_collection(self) -> dict[str, Any]:
        """Benchmark resource collection performance."""
        try:
            iterations = self.benchmark_config["resource_collection_iterations"]
            collection_times = []
            memory_usage = []

            self.logger.info(f"Running {iterations} resource collection iterations...")

            for i in range(iterations):
                start_time = time.time()

                # Collect resource metrics
                metrics = self.performance_monitor.collect_resource_metrics()

                end_time = time.time()
                collection_time = (end_time - start_time) * 1000  # Convert to ms

                collection_times.append(collection_time)
                memory_usage.append(metrics.memory_usage_percent)

                # Log progress every 100 iterations
                if (i + 1) % 100 == 0:
                    self.logger.info(
                        f"Completed {i + 1}/{iterations} resource collection iterations"
                    )

            # Calculate performance statistics
            return {
                "iterations": iterations,
                "performance_stats": {
                    "mean_time_ms": statistics.mean(collection_times),
                    "median_time_ms": statistics.median(collection_times),
                    "stdev_time_ms": (
                        statistics.stdev(collection_times)
                        if len(collection_times) > 1
                        else 0
                    ),
                    "min_time_ms": min(collection_times),
                    "max_time_ms": max(collection_times),
                    "p95_time_ms": self._calculate_percentile(collection_times, 95),
                    "p99_time_ms": self._calculate_percentile(collection_times, 99),
                },
                "throughput": {
                    "collections_per_second": 1000 / statistics.mean(collection_times),
                    "total_time_seconds": sum(collection_times) / 1000,
                },
                "efficiency_score": self._calculate_collection_efficiency_score(
                    collection_times
                ),
            }

        except Exception as e:
            return {"error": f"Resource collection benchmark failed: {str(e)}"}

    def _benchmark_bottleneck_detection(self) -> dict[str, Any]:
        """Benchmark bottleneck detection performance."""
        try:
            iterations = self.benchmark_config["bottleneck_detection_iterations"]
            detection_times = []
            bottleneck_counts = []

            self.logger.info(f"Running {iterations} bottleneck detection iterations...")

            for i in range(iterations):
                start_time = time.time()

                # Detect bottlenecks
                bottlenecks = self.performance_monitor.detect_performance_bottlenecks()

                end_time = time.time()
                detection_time = (end_time - start_time) * 1000  # Convert to ms

                detection_times.append(detection_time)
                bottleneck_counts.append(len(bottlenecks))

                # Log progress every 20 iterations
                if (i + 1) % 20 == 0:
                    self.logger.info(
                        f"Completed {i + 1}/{iterations} bottleneck detection iterations"
                    )

            return {
                "iterations": iterations,
                "performance_stats": {
                    "mean_time_ms": statistics.mean(detection_times),
                    "median_time_ms": statistics.median(detection_times),
                    "stdev_time_ms": (
                        statistics.stdev(detection_times)
                        if len(detection_times) > 1
                        else 0
                    ),
                    "min_time_ms": min(detection_times),
                    "max_time_ms": max(detection_times),
                    "p95_time_ms": self._calculate_percentile(detection_times, 95),
                    "p99_time_ms": self._calculate_percentile(detection_times, 99),
                },
                "bottleneck_analysis": {
                    "mean_bottlenecks": statistics.mean(bottleneck_counts),
                    "max_bottlenecks": max(bottleneck_counts),
                    "min_bottlenecks": min(bottleneck_counts),
                },
                "efficiency_score": self._calculate_detection_efficiency_score(
                    detection_times
                ),
            }

        except Exception as e:
            return {"error": f"Bottleneck detection benchmark failed: {str(e)}"}

    def _benchmark_optimization(self) -> dict[str, Any]:
        """Benchmark optimization performance."""
        try:
            iterations = self.benchmark_config["optimization_iterations"]
            optimization_times = []
            recommendation_counts = []

            self.logger.info(f"Running {iterations} optimization iterations...")

            for i in range(iterations):
                start_time = time.time()

                # Generate optimization recommendations
                recommendations = (
                    self.performance_monitor.generate_optimization_recommendations()
                )

                end_time = time.time()
                optimization_time = (end_time - start_time) * 1000  # Convert to ms

                optimization_times.append(optimization_time)
                recommendation_counts.append(len(recommendations))

                # Log progress every 10 iterations
                if (i + 1) % 10 == 0:
                    self.logger.info(
                        f"Completed {i + 1}/{iterations} optimization iterations"
                    )

            return {
                "iterations": iterations,
                "performance_stats": {
                    "mean_time_ms": statistics.mean(optimization_times),
                    "median_time_ms": statistics.median(optimization_times),
                    "stdev_time_ms": (
                        statistics.stdev(optimization_times)
                        if len(optimization_times) > 1
                        else 0
                    ),
                    "min_time_ms": min(optimization_times),
                    "max_time_ms": max(optimization_times),
                    "p95_time_ms": self._calculate_percentile(optimization_times, 95),
                    "p99_time_ms": self._calculate_percentile(optimization_times, 99),
                },
                "recommendation_analysis": {
                    "mean_recommendations": statistics.mean(recommendation_counts),
                    "max_recommendations": max(recommendation_counts),
                    "min_recommendations": min(recommendation_counts),
                },
                "efficiency_score": self._calculate_optimization_efficiency_score(
                    optimization_times
                ),
            }

        except Exception as e:
            return {"error": f"Optimization benchmark failed: {str(e)}"}

    def _run_stress_tests(self) -> dict[str, Any]:
        """Run container stress tests."""
        try:
            stress_duration = self.benchmark_config["stress_test_duration"]
            stress_results = {
                "duration_seconds": stress_duration,
                "cpu_stress": {},
                "memory_stress": {},
                "concurrent_operations": {},
                "stability_analysis": {},
            }

            # CPU stress test
            self.logger.info("Running CPU stress test...")
            stress_results["cpu_stress"] = self._run_cpu_stress_test(
                stress_duration // 3
            )

            # Memory stress test
            self.logger.info("Running memory stress test...")
            stress_results["memory_stress"] = self._run_memory_stress_test(
                stress_duration // 3
            )

            # Concurrent operations test
            self.logger.info("Running concurrent operations test...")
            stress_results["concurrent_operations"] = (
                self._run_concurrent_operations_test(stress_duration // 3)
            )

            # Analyze stability
            stress_results["stability_analysis"] = self._analyze_stress_stability(
                stress_results
            )

            return stress_results

        except Exception as e:
            return {"error": f"Stress tests failed: {str(e)}"}

    def _run_cpu_stress_test(self, duration: int) -> dict[str, Any]:
        """Run CPU-intensive stress test."""
        try:
            start_time = time.time()
            cpu_samples = []

            while time.time() - start_time < duration:
                # CPU-intensive operation
                sum(i * i for i in range(10000))

                # Sample metrics
                metrics = self.performance_monitor.collect_resource_metrics()
                cpu_samples.append(
                    {
                        "timestamp": time.time(),
                        "cpu_percent": metrics.cpu_usage_percent,
                        "memory_percent": metrics.memory_usage_percent,
                        "load_average": metrics.load_average[0],
                    }
                )

                time.sleep(0.1)  # Brief pause

            return {
                "duration_seconds": duration,
                "samples": len(cpu_samples),
                "peak_cpu": max(s["cpu_percent"] for s in cpu_samples),
                "avg_cpu": statistics.mean(s["cpu_percent"] for s in cpu_samples),
                "peak_load": max(s["load_average"] for s in cpu_samples),
                "stability_score": self._calculate_stability_score(
                    [s["cpu_percent"] for s in cpu_samples]
                ),
            }

        except Exception as e:
            return {"error": f"CPU stress test failed: {str(e)}"}

    def _run_memory_stress_test(self, duration: int) -> dict[str, Any]:
        """Run memory-intensive stress test."""
        try:
            start_time = time.time()
            memory_samples = []
            memory_allocations = []

            while time.time() - start_time < duration:
                # Memory-intensive operation
                data = list(range(100000))
                memory_allocations.append(data)

                # Sample metrics
                metrics = self.performance_monitor.collect_resource_metrics()
                memory_samples.append(
                    {
                        "timestamp": time.time(),
                        "memory_percent": metrics.memory_usage_percent,
                        "memory_mb": metrics.memory_usage_mb,
                    }
                )

                # Cleanup some allocations to prevent OOM
                if len(memory_allocations) > 50:
                    memory_allocations = memory_allocations[-25:]

                time.sleep(0.1)

            return {
                "duration_seconds": duration,
                "samples": len(memory_samples),
                "peak_memory_percent": max(s["memory_percent"] for s in memory_samples),
                "avg_memory_percent": statistics.mean(
                    s["memory_percent"] for s in memory_samples
                ),
                "peak_memory_mb": max(s["memory_mb"] for s in memory_samples),
                "stability_score": self._calculate_stability_score(
                    [s["memory_percent"] for s in memory_samples]
                ),
            }

        except Exception as e:
            return {"error": f"Memory stress test failed: {str(e)}"}

    def _run_concurrent_operations_test(self, duration: int) -> dict[str, Any]:
        """Run concurrent operations stress test."""
        try:
            import threading

            start_time = time.time()
            operation_counts = []
            error_counts = []

            def worker_thread():
                """Worker thread for concurrent operations."""
                operations = 0
                errors = 0

                while time.time() - start_time < duration:
                    try:
                        # Simulate concurrent operations
                        self.performance_monitor.collect_resource_metrics()
                        (
                            self.performance_monitor.detect_performance_bottlenecks()
                        )
                        operations += 2
                    except Exception:
                        errors += 1

                    time.sleep(0.01)  # Brief pause

                operation_counts.append(operations)
                error_counts.append(errors)

            # Start multiple worker threads
            threads = []
            thread_count = 4

            for _ in range(thread_count):
                thread = threading.Thread(target=worker_thread)
                thread.start()
                threads.append(thread)

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            total_operations = sum(operation_counts)
            total_errors = sum(error_counts)

            return {
                "duration_seconds": duration,
                "thread_count": thread_count,
                "total_operations": total_operations,
                "total_errors": total_errors,
                "operations_per_second": total_operations / duration,
                "error_rate_percent": (total_errors / max(total_operations, 1)) * 100,
                "concurrency_efficiency": total_operations / (thread_count * duration),
            }

        except Exception as e:
            return {"error": f"Concurrent operations test failed: {str(e)}"}

    def _analyze_stress_stability(
        self, stress_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze stability from stress test results."""
        try:
            stability_scores = []

            # Collect stability scores from individual tests
            for _test_name, test_results in stress_results.items():
                if isinstance(test_results, dict) and "stability_score" in test_results:
                    stability_scores.append(test_results["stability_score"])

            if not stability_scores:
                return {"error": "No stability scores available"}

            return {
                "overall_stability_score": statistics.mean(stability_scores),
                "min_stability_score": min(stability_scores),
                "max_stability_score": max(stability_scores),
                "stability_consistency": (
                    statistics.stdev(stability_scores)
                    if len(stability_scores) > 1
                    else 0
                ),
                "stability_level": self._classify_stability_level(
                    statistics.mean(stability_scores)
                ),
            }

        except Exception as e:
            return {"error": f"Stability analysis failed: {str(e)}"}

    def _analyze_efficiency(self) -> dict[str, Any]:
        """Analyze overall container efficiency."""
        try:
            efficiency_analysis = {
                "resource_efficiency": {},
                "performance_efficiency": {},
                "scalability_analysis": {},
                "optimization_potential": {},
            }

            # Resource efficiency analysis
            baseline_stats = self.benchmark_results.get("baseline_performance", {}).get(
                "statistics", {}
            )
            if baseline_stats:
                efficiency_analysis["resource_efficiency"] = {
                    "cpu_efficiency": self._calculate_cpu_efficiency(baseline_stats),
                    "memory_efficiency": self._calculate_memory_efficiency(
                        baseline_stats
                    ),
                    "overall_resource_score": 0.0,
                }

                # Calculate overall resource score
                cpu_eff = efficiency_analysis["resource_efficiency"]["cpu_efficiency"]
                mem_eff = efficiency_analysis["resource_efficiency"][
                    "memory_efficiency"
                ]
                efficiency_analysis["resource_efficiency"]["overall_resource_score"] = (
                    cpu_eff + mem_eff
                ) / 2

            # Performance efficiency analysis
            collection_bench = self.benchmark_results.get(
                "resource_collection_benchmark", {}
            )
            detection_bench = self.benchmark_results.get(
                "bottleneck_detection_benchmark", {}
            )

            if collection_bench and detection_bench:
                efficiency_analysis["performance_efficiency"] = {
                    "collection_efficiency": collection_bench.get(
                        "efficiency_score", 0
                    ),
                    "detection_efficiency": detection_bench.get("efficiency_score", 0),
                    "overall_performance_score": 0.0,
                }

                # Calculate overall performance score
                coll_eff = efficiency_analysis["performance_efficiency"][
                    "collection_efficiency"
                ]
                det_eff = efficiency_analysis["performance_efficiency"][
                    "detection_efficiency"
                ]
                efficiency_analysis["performance_efficiency"][
                    "overall_performance_score"
                ] = (coll_eff + det_eff) / 2

            # Scalability analysis
            stress_results = self.benchmark_results.get("stress_test_results", {})
            if stress_results:
                efficiency_analysis["scalability_analysis"] = self._analyze_scalability(
                    stress_results
                )

            # Optimization potential
            efficiency_analysis["optimization_potential"] = (
                self._calculate_optimization_potential()
            )

            return efficiency_analysis

        except Exception as e:
            return {"error": f"Efficiency analysis failed: {str(e)}"}

    def _generate_benchmark_recommendations(self) -> list[dict[str, Any]]:
        """Generate recommendations based on benchmark results."""
        recommendations = []

        try:
            # Resource efficiency recommendations
            resource_eff = self.benchmark_results.get("efficiency_analysis", {}).get(
                "resource_efficiency", {}
            )
            if resource_eff.get("cpu_efficiency", 0) < 70:
                recommendations.append(
                    {
                        "category": "resource_optimization",
                        "priority": "high",
                        "title": "CPU Efficiency Improvement",
                        "description": "CPU efficiency is below optimal levels",
                        "actions": [
                            "Review CPU-intensive operations",
                            "Implement CPU usage optimization",
                            "Consider horizontal scaling",
                        ],
                    }
                )

            if resource_eff.get("memory_efficiency", 0) < 70:
                recommendations.append(
                    {
                        "category": "resource_optimization",
                        "priority": "high",
                        "title": "Memory Efficiency Improvement",
                        "description": "Memory efficiency is below optimal levels",
                        "actions": [
                            "Optimize memory usage patterns",
                            "Implement memory pooling",
                            "Review garbage collection settings",
                        ],
                    }
                )

            # Performance recommendations
            collection_bench = self.benchmark_results.get(
                "resource_collection_benchmark", {}
            )
            if (
                collection_bench.get("performance_stats", {}).get("mean_time_ms", 0)
                > 10
            ):
                recommendations.append(
                    {
                        "category": "performance_optimization",
                        "priority": "medium",
                        "title": "Resource Collection Performance",
                        "description": "Resource collection is slower than optimal",
                        "actions": [
                            "Optimize resource collection algorithms",
                            "Implement caching for expensive operations",
                            "Review system call efficiency",
                        ],
                    }
                )

            # Stability recommendations
            stability_analysis = self.benchmark_results.get(
                "stress_test_results", {}
            ).get("stability_analysis", {})
            if stability_analysis.get("overall_stability_score", 100) < 80:
                recommendations.append(
                    {
                        "category": "stability_improvement",
                        "priority": "high",
                        "title": "System Stability Enhancement",
                        "description": "System stability under stress is below acceptable levels",
                        "actions": [
                            "Implement better error handling",
                            "Add resource limits and throttling",
                            "Improve graceful degradation",
                        ],
                    }
                )

            return recommendations

        except Exception as e:
            self.logger.error(f"Failed to generate recommendations: {str(e)}")
            return []

    def _save_benchmark_results(self):
        """Save benchmark results to files."""
        try:
            # Save JSON results
            json_file = os.path.join(self.output_dir, "benchmark_results.json")
            with open(json_file, "w") as f:
                json.dump(self.benchmark_results, f, indent=2, default=str)

            # Save summary report
            summary_file = os.path.join(self.output_dir, "benchmark_summary.txt")
            with open(summary_file, "w") as f:
                f.write(self._generate_summary_report())

            self.logger.info(f"Benchmark results saved to {self.output_dir}")

        except Exception as e:
            self.logger.error(f"Failed to save benchmark results: {str(e)}")

    def _generate_summary_report(self) -> str:
        """Generate human-readable summary report."""
        lines = []
        lines.append("Container Efficiency Benchmark Summary")
        lines.append("=" * 50)
        lines.append("")

        # Benchmark info
        info = self.benchmark_results.get("benchmark_info", {})
        lines.append(f"Start Time: {info.get('start_time', 'N/A')}")
        lines.append(f"Duration: {info.get('total_duration_seconds', 0):.2f} seconds")
        lines.append("")

        # Performance summary
        collection_bench = self.benchmark_results.get(
            "resource_collection_benchmark", {}
        )
        if collection_bench:
            perf_stats = collection_bench.get("performance_stats", {})
            lines.append("Resource Collection Performance:")
            lines.append(f"  Mean Time: {perf_stats.get('mean_time_ms', 0):.2f} ms")
            lines.append(f"  P95 Time: {perf_stats.get('p95_time_ms', 0):.2f} ms")
            lines.append(
                f"  Throughput: {collection_bench.get('throughput', {}).get('collections_per_second', 0):.2f} ops/sec"
            )
            lines.append("")

        # Efficiency analysis
        efficiency = self.benchmark_results.get("efficiency_analysis", {})
        resource_eff = efficiency.get("resource_efficiency", {})
        if resource_eff:
            lines.append("Resource Efficiency:")
            lines.append(
                f"  CPU Efficiency: {resource_eff.get('cpu_efficiency', 0):.1f}%"
            )
            lines.append(
                f"  Memory Efficiency: {resource_eff.get('memory_efficiency', 0):.1f}%"
            )
            lines.append(
                f"  Overall Score: {resource_eff.get('overall_resource_score', 0):.1f}%"
            )
            lines.append("")

        # Recommendations
        recommendations = self.benchmark_results.get("recommendations", [])
        if recommendations:
            lines.append("Key Recommendations:")
            for i, rec in enumerate(recommendations[:5], 1):  # Top 5 recommendations
                lines.append(
                    f"  {i}. {rec.get('title', 'N/A')} ({rec.get('priority', 'N/A')} priority)"
                )
            lines.append("")

        return "\n".join(lines)

    # Helper methods for calculations

    def _calculate_percentile(self, values: list[float], percentile: int) -> float:
        """Calculate percentile of values."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        return sorted_values[min(index, len(sorted_values) - 1)]

    def _calculate_collection_efficiency_score(
        self, collection_times: list[float]
    ) -> float:
        """Calculate efficiency score for resource collection."""
        if not collection_times:
            return 0.0

        mean_time = statistics.mean(collection_times)
        # Optimal collection time is under 5ms
        optimal_time = 5.0

        if mean_time <= optimal_time:
            return 100.0
        else:
            # Decrease score based on how much slower than optimal
            return max(0, 100 - ((mean_time - optimal_time) / optimal_time) * 50)

    def _calculate_detection_efficiency_score(
        self, detection_times: list[float]
    ) -> float:
        """Calculate efficiency score for bottleneck detection."""
        if not detection_times:
            return 0.0

        mean_time = statistics.mean(detection_times)
        # Optimal detection time is under 50ms
        optimal_time = 50.0

        if mean_time <= optimal_time:
            return 100.0
        else:
            return max(0, 100 - ((mean_time - optimal_time) / optimal_time) * 30)

    def _calculate_optimization_efficiency_score(
        self, optimization_times: list[float]
    ) -> float:
        """Calculate efficiency score for optimization."""
        if not optimization_times:
            return 0.0

        mean_time = statistics.mean(optimization_times)
        # Optimal optimization time is under 100ms
        optimal_time = 100.0

        if mean_time <= optimal_time:
            return 100.0
        else:
            return max(0, 100 - ((mean_time - optimal_time) / optimal_time) * 25)

    def _calculate_stability_score(self, values: list[float]) -> float:
        """Calculate stability score based on value consistency."""
        if len(values) < 2:
            return 100.0

        mean_val = statistics.mean(values)
        stdev_val = statistics.stdev(values)

        # Stability decreases with higher coefficient of variation
        if mean_val == 0:
            return 0.0

        cv = stdev_val / mean_val
        return max(0, 100 - (cv * 100))

    def _classify_stability_level(self, stability_score: float) -> str:
        """Classify stability level based on score."""
        if stability_score >= 90:
            return "excellent"
        elif stability_score >= 80:
            return "good"
        elif stability_score >= 70:
            return "acceptable"
        elif stability_score >= 60:
            return "poor"
        else:
            return "critical"

    def _calculate_cpu_efficiency(self, baseline_stats: dict[str, Any]) -> float:
        """Calculate CPU efficiency score."""
        cpu_stats = baseline_stats.get("cpu_usage", {})
        mean_cpu = cpu_stats.get("mean", 0)

        # Optimal CPU usage is 60-80%
        if 60 <= mean_cpu <= 80:
            return 100.0
        elif mean_cpu < 60:
            return 80.0 + (mean_cpu / 60) * 20  # Underutilization penalty
        else:
            return max(0, 100 - ((mean_cpu - 80) / 20) * 50)  # Overutilization penalty

    def _calculate_memory_efficiency(self, baseline_stats: dict[str, Any]) -> float:
        """Calculate memory efficiency score."""
        memory_stats = baseline_stats.get("memory_usage", {})
        mean_memory = memory_stats.get("mean", 0)

        # Optimal memory usage is 70-85%
        if 70 <= mean_memory <= 85:
            return 100.0
        elif mean_memory < 70:
            return 80.0 + (mean_memory / 70) * 20
        else:
            return max(0, 100 - ((mean_memory - 85) / 15) * 50)

    def _analyze_scalability(self, stress_results: dict[str, Any]) -> dict[str, Any]:
        """Analyze scalability from stress test results."""
        concurrent_results = stress_results.get("concurrent_operations", {})

        if not concurrent_results or "error" in concurrent_results:
            return {"error": "No concurrent operations data available"}

        concurrency_efficiency = concurrent_results.get("concurrency_efficiency", 0)
        error_rate = concurrent_results.get("error_rate_percent", 0)

        # Calculate scalability score
        scalability_score = max(
            0, 100 - error_rate * 2 - max(0, (1.0 - concurrency_efficiency) * 50)
        )

        return {
            "scalability_score": scalability_score,
            "concurrency_efficiency": concurrency_efficiency,
            "error_rate_percent": error_rate,
            "scalability_level": self._classify_scalability_level(scalability_score),
        }

    def _classify_scalability_level(self, scalability_score: float) -> str:
        """Classify scalability level based on score."""
        if scalability_score >= 90:
            return "excellent"
        elif scalability_score >= 80:
            return "good"
        elif scalability_score >= 70:
            return "acceptable"
        else:
            return "needs_improvement"

    def _calculate_optimization_potential(self) -> dict[str, Any]:
        """Calculate optimization potential based on benchmark results."""
        potential_areas = []

        # Check resource collection performance
        collection_bench = self.benchmark_results.get(
            "resource_collection_benchmark", {}
        )
        if collection_bench.get("efficiency_score", 100) < 80:
            potential_areas.append("resource_collection")

        # Check bottleneck detection performance
        detection_bench = self.benchmark_results.get(
            "bottleneck_detection_benchmark", {}
        )
        if detection_bench.get("efficiency_score", 100) < 80:
            potential_areas.append("bottleneck_detection")

        # Check resource efficiency
        efficiency = self.benchmark_results.get("efficiency_analysis", {})
        resource_eff = efficiency.get("resource_efficiency", {})
        if resource_eff.get("overall_resource_score", 100) < 80:
            potential_areas.append("resource_utilization")

        return {
            "optimization_areas": potential_areas,
            "optimization_potential_score": max(0, 100 - len(potential_areas) * 20),
            "priority_area": potential_areas[0] if potential_areas else "none",
        }


if __name__ == "__main__":
    # Example usage
    benchmark = ContainerEfficiencyBenchmark()
    results = benchmark.run_comprehensive_benchmark()
    print("Benchmark completed. Results saved to benchmark_results/")
