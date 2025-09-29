#!/usr/bin/env python3
"""
Performance testing and benchmarking runner script.

This script runs comprehensive performance tests and benchmarks for the
container testing system, including unit tests, integration tests, and
efficiency benchmarking.
"""

import argparse
import os
import sys
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import after path modification to avoid E402
from core.database import DatabaseManager  # noqa: E402
from core.test.performance_benchmarks import ContainerEfficiencyBenchmark  # noqa: E402


def setup_test_environment():
    """Setup test environment for performance testing."""
    print("Setting up test environment...")

    # Create test output directories
    os.makedirs("performance_test_results", exist_ok=True)
    os.makedirs("benchmark_results", exist_ok=True)

    print("Test environment setup complete.")


def run_unit_tests():
    """Run performance monitor unit tests."""
    print("\n" + "=" * 60)
    print("RUNNING PERFORMANCE MONITOR UNIT TESTS")
    print("=" * 60)

    import subprocess

    try:
        # Run pytest on performance monitor tests
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "core/test/test_performance_monitor.py",
                "-v",
                "--tb=short",
            ],
            capture_output=True,
            text=True,
            cwd=project_root,
        )

        print("STDOUT:")
        print(result.stdout)

        if result.stderr:
            print("STDERR:")
            print(result.stderr)

        if result.returncode == 0:
            print("✅ Unit tests PASSED")
            return True
        else:
            print("❌ Unit tests FAILED")
            return False

    except Exception as e:
        print(f"❌ Failed to run unit tests: {str(e)}")
        return False


def run_performance_benchmarks(database_managers=None):
    """Run comprehensive performance benchmarks."""
    print("\n" + "=" * 60)
    print("RUNNING PERFORMANCE BENCHMARKS")
    print("=" * 60)

    try:
        # Initialize benchmark suite
        benchmark = ContainerEfficiencyBenchmark(
            database_managers=database_managers, output_dir="benchmark_results"
        )

        print("Starting comprehensive performance benchmark...")
        start_time = time.time()

        # Run benchmark
        results = benchmark.run_comprehensive_benchmark()

        end_time = time.time()
        duration = end_time - start_time

        if "error" in results:
            print(f"❌ Benchmark failed: {results['error']}")
            return False

        print(f"✅ Benchmark completed successfully in {duration:.2f} seconds")

        # Print summary
        print_benchmark_summary(results)

        return True

    except Exception as e:
        print(f"❌ Benchmark failed with exception: {str(e)}")
        return False


def print_benchmark_summary(results):
    """Print benchmark summary to console."""
    print("\n" + "-" * 50)
    print("BENCHMARK SUMMARY")
    print("-" * 50)

    # Basic info
    info = results.get("benchmark_info", {})
    print(f"Duration: {info.get('total_duration_seconds', 0):.2f} seconds")

    # Resource collection performance
    collection = results.get("resource_collection_benchmark", {})
    if collection and "performance_stats" in collection:
        stats = collection["performance_stats"]
        throughput = collection.get("throughput", {})

        print("\nResource Collection Performance:")
        print(f"  Mean Time: {stats.get('mean_time_ms', 0):.2f} ms")
        print(f"  P95 Time: {stats.get('p95_time_ms', 0):.2f} ms")
        print(
            f"  Throughput: {throughput.get('collections_per_second', 0):.2f} ops/sec"
        )
        print(f"  Efficiency Score: {collection.get('efficiency_score', 0):.1f}%")

    # Bottleneck detection performance
    detection = results.get("bottleneck_detection_benchmark", {})
    if detection and "performance_stats" in detection:
        stats = detection["performance_stats"]

        print("\nBottleneck Detection Performance:")
        print(f"  Mean Time: {stats.get('mean_time_ms', 0):.2f} ms")
        print(f"  P95 Time: {stats.get('p95_time_ms', 0):.2f} ms")
        print(f"  Efficiency Score: {detection.get('efficiency_score', 0):.1f}%")

    # Efficiency analysis
    efficiency = results.get("efficiency_analysis", {})
    resource_eff = efficiency.get("resource_efficiency", {})
    if resource_eff:
        print("\nResource Efficiency:")
        print(f"  CPU Efficiency: {resource_eff.get('cpu_efficiency', 0):.1f}%")
        print(f"  Memory Efficiency: {resource_eff.get('memory_efficiency', 0):.1f}%")
        print(f"  Overall Score: {resource_eff.get('overall_resource_score', 0):.1f}%")

    # Stress test results
    stress = results.get("stress_test_results", {})
    stability = stress.get("stability_analysis", {})
    if stability:
        print("\nStability Analysis:")
        print(
            f"  Overall Stability Score: {stability.get('overall_stability_score', 0):.1f}%"
        )
        print(f"  Stability Level: {stability.get('stability_level', 'unknown')}")

    # Recommendations
    recommendations = results.get("recommendations", [])
    if recommendations:
        print("\nTop Recommendations:")
        for i, rec in enumerate(recommendations[:3], 1):
            print(
                f"  {i}. {rec.get('title', 'N/A')} ({rec.get('priority', 'N/A')} priority)"
            )


def run_integration_tests():
    """Run integration tests with actual database connections."""
    print("\n" + "=" * 60)
    print("RUNNING INTEGRATION TESTS")
    print("=" * 60)

    try:
        # Try to initialize database managers for testing
        database_managers = {}

        # Check if we can connect to test databases
        try:
            from core.config import ConfigManager

            config_manager = ConfigManager()

            # Try to get database configuration
            db_config = config_manager.get_database_config("rpa_db")
            if db_config:
                print(
                    "Found database configuration, initializing test database manager..."
                )
                database_managers["rpa_db"] = DatabaseManager("rpa_db")

                # Test basic connectivity
                result = database_managers["rpa_db"].execute_query("SELECT 1 as test")
                if result and result[0].get("test") == 1:
                    print("✅ Database connectivity test passed")
                else:
                    print(
                        "⚠️  Database connectivity test failed, using mock for integration tests"
                    )
                    database_managers = {}
            else:
                print(
                    "⚠️  No database configuration found, using mock for integration tests"
                )

        except Exception as e:
            print(
                f"⚠️  Database setup failed: {str(e)}, using mock for integration tests"
            )
            database_managers = {}

        # Run integration benchmark with available databases
        success = run_performance_benchmarks(database_managers)

        if success:
            print("✅ Integration tests completed successfully")
        else:
            print("❌ Integration tests failed")

        return success

    except Exception as e:
        print(f"❌ Integration tests failed: {str(e)}")
        return False


def run_quick_performance_check():
    """Run a quick performance check for development."""
    print("\n" + "=" * 60)
    print("RUNNING QUICK PERFORMANCE CHECK")
    print("=" * 60)

    try:
        from core.performance_monitor import PerformanceMonitor

        # Initialize performance monitor
        monitor = PerformanceMonitor(enable_detailed_monitoring=True)

        print("Testing resource collection performance...")
        start_time = time.time()

        # Test resource collection
        for i in range(10):
            metrics = monitor.collect_resource_metrics()
            if i == 0:
                print(
                    f"  Sample metrics: CPU {metrics.cpu_usage_percent}%, Memory {metrics.memory_usage_percent}%"
                )

        collection_time = (time.time() - start_time) / 10 * 1000  # ms per collection
        print(f"  Average collection time: {collection_time:.2f} ms")

        print("Testing bottleneck detection...")
        start_time = time.time()

        bottlenecks = monitor.detect_performance_bottlenecks()
        detection_time = (time.time() - start_time) * 1000  # ms

        print(f"  Detection time: {detection_time:.2f} ms")
        print(f"  Bottlenecks found: {len(bottlenecks)}")

        print("Testing optimization recommendations...")
        start_time = time.time()

        recommendations = monitor.generate_optimization_recommendations()
        optimization_time = (time.time() - start_time) * 1000  # ms

        print(f"  Optimization time: {optimization_time:.2f} ms")
        print(f"  Recommendations generated: {len(recommendations)}")

        # Performance thresholds for quick check
        if collection_time > 20:
            print("⚠️  Resource collection is slower than expected")
        if detection_time > 100:
            print("⚠️  Bottleneck detection is slower than expected")
        if optimization_time > 200:
            print("⚠️  Optimization is slower than expected")

        print("✅ Quick performance check completed")
        return True

    except Exception as e:
        print(f"❌ Quick performance check failed: {str(e)}")
        return False


def main():
    """Main function to run performance tests."""
    parser = argparse.ArgumentParser(description="Run performance tests and benchmarks")
    parser.add_argument(
        "--test-type",
        choices=["unit", "integration", "benchmark", "quick", "all"],
        default="all",
        help="Type of tests to run",
    )
    parser.add_argument(
        "--output-dir",
        default="performance_test_results",
        help="Output directory for test results",
    )

    args = parser.parse_args()

    print("Container Performance Testing Suite")
    print("=" * 60)
    print(f"Test Type: {args.test_type}")
    print(f"Output Directory: {args.output_dir}")

    # Setup environment
    setup_test_environment()

    # Track results
    results = {}

    # Run tests based on type
    if args.test_type in ["unit", "all"]:
        results["unit_tests"] = run_unit_tests()

    if args.test_type in ["quick", "all"]:
        results["quick_check"] = run_quick_performance_check()

    if args.test_type in ["integration", "all"]:
        results["integration_tests"] = run_integration_tests()

    if args.test_type in ["benchmark", "all"]:
        results["benchmarks"] = run_performance_benchmarks()

    # Print final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n🎉 All tests passed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed. Check the output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
