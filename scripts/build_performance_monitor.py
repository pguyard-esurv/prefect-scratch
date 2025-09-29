#!/usr/bin/env python3
"""
Build performance monitoring and optimization tools
Monitors build times, cache efficiency, and provides optimization recommendations
"""

import argparse
import json
import logging
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [BUILD-PERF] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class BuildMetrics:
    """Build performance metrics"""

    image_name: str
    build_time: float
    cache_hits: int
    cache_misses: int
    image_size: int
    layer_count: int
    timestamp: str
    build_context_size: int
    dockerfile_lines: int
    success: bool
    error_message: Optional[str] = None


@dataclass
class PerformanceAnalysis:
    """Performance analysis results"""

    avg_build_time: float
    cache_efficiency: float
    size_trend: str
    recommendations: list[str]
    bottlenecks: list[str]


class BuildPerformanceMonitor:
    """Monitors and analyzes build performance"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.metrics_dir = self.project_root / ".build_metrics"
        self.metrics_file = self.metrics_dir / "build_metrics.json"
        self.setup_directories()

    def setup_directories(self):
        """Setup required directories"""
        self.metrics_dir.mkdir(exist_ok=True)
        logger.info(f"Metrics directory: {self.metrics_dir}")

    def measure_build_context_size(self, dockerfile_path: str) -> int:
        """Measure build context size"""
        try:
            dockerfile_dir = Path(dockerfile_path).parent
            result = subprocess.run(
                ["du", "-sb", str(dockerfile_dir)],
                capture_output=True,
                text=True,
                check=True,
            )
            return int(result.stdout.split()[0])
        except (subprocess.CalledProcessError, ValueError, IndexError):
            logger.warning("Failed to measure build context size")
            return 0

    def count_dockerfile_lines(self, dockerfile_path: str) -> int:
        """Count lines in Dockerfile"""
        try:
            with open(dockerfile_path) as f:
                return len(
                    [
                        line
                        for line in f
                        if line.strip() and not line.strip().startswith("#")
                    ]
                )
        except FileNotFoundError:
            logger.warning(f"Dockerfile not found: {dockerfile_path}")
            return 0

    def get_image_info(self, image_name: str) -> tuple[int, int]:
        """Get image size and layer count"""
        try:
            # Get image size
            size_result = subprocess.run(
                ["docker", "image", "inspect", image_name, "--format={{.Size}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            image_size = int(size_result.stdout.strip())

            # Get layer count
            layers_result = subprocess.run(
                [
                    "docker",
                    "image",
                    "inspect",
                    image_name,
                    "--format={{len .RootFS.Layers}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            layer_count = int(layers_result.stdout.strip())

            return image_size, layer_count
        except (subprocess.CalledProcessError, ValueError):
            logger.warning(f"Failed to get image info for {image_name}")
            return 0, 0

    def parse_build_log(self, log_content: str) -> tuple[int, int]:
        """Parse build log to extract cache hits and misses"""
        cache_hits = log_content.count("CACHED")

        # Count build steps (RUN, COPY, ADD, etc.)
        build_steps = (
            log_content.count("RUN ")
            + log_content.count("COPY ")
            + log_content.count("ADD ")
            + log_content.count("FROM ")
        )

        cache_misses = max(0, build_steps - cache_hits)

        return cache_hits, cache_misses

    def monitor_build(
        self, image_name: str, dockerfile_path: str, build_command: list[str]
    ) -> BuildMetrics:
        """Monitor a build process and collect metrics"""
        logger.info(f"Monitoring build for {image_name}")

        # Pre-build measurements
        build_context_size = self.measure_build_context_size(dockerfile_path)
        dockerfile_lines = self.count_dockerfile_lines(dockerfile_path)

        # Execute build with timing
        start_time = time.time()

        try:
            result = subprocess.run(
                build_command,
                capture_output=True,
                text=True,
                check=True,
                cwd=self.project_root,
            )

            build_time = time.time() - start_time
            success = True
            error_message = None

            # Parse build output
            cache_hits, cache_misses = self.parse_build_log(
                result.stdout + result.stderr
            )

            # Get image info
            image_size, layer_count = self.get_image_info(image_name)

            logger.info(f"Build completed in {build_time:.2f}s")

        except subprocess.CalledProcessError as e:
            build_time = time.time() - start_time
            success = False
            error_message = e.stderr or str(e)
            cache_hits = cache_misses = 0
            image_size = layer_count = 0

            logger.error(f"Build failed after {build_time:.2f}s: {error_message}")

        # Create metrics object
        metrics = BuildMetrics(
            image_name=image_name,
            build_time=build_time,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            image_size=image_size,
            layer_count=layer_count,
            timestamp=datetime.now().isoformat(),
            build_context_size=build_context_size,
            dockerfile_lines=dockerfile_lines,
            success=success,
            error_message=error_message,
        )

        # Store metrics
        self.store_metrics(metrics)

        return metrics

    def store_metrics(self, metrics: BuildMetrics):
        """Store build metrics to file"""
        try:
            # Load existing metrics
            if self.metrics_file.exists():
                with open(self.metrics_file) as f:
                    all_metrics = json.load(f)
            else:
                all_metrics = []

            # Add new metrics
            all_metrics.append(asdict(metrics))

            # Keep only recent metrics (last 100 builds)
            all_metrics = all_metrics[-100:]

            # Save updated metrics
            with open(self.metrics_file, "w") as f:
                json.dump(all_metrics, f, indent=2)

            logger.info(f"Metrics stored: {self.metrics_file}")

        except Exception as e:
            logger.error(f"Failed to store metrics: {e}")

    def load_metrics(self) -> list[BuildMetrics]:
        """Load stored build metrics"""
        try:
            if not self.metrics_file.exists():
                return []

            with open(self.metrics_file) as f:
                data = json.load(f)

            return [BuildMetrics(**item) for item in data]

        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")
            return []

    def analyze_performance(
        self, image_name: Optional[str] = None, days: int = 7
    ) -> PerformanceAnalysis:
        """Analyze build performance over time"""
        metrics = self.load_metrics()

        # Filter by image name if specified
        if image_name:
            metrics = [m for m in metrics if m.image_name == image_name]

        # Filter by time period
        cutoff_date = datetime.now() - timedelta(days=days)
        metrics = [
            m
            for m in metrics
            if datetime.fromisoformat(m.timestamp) > cutoff_date and m.success
        ]

        if not metrics:
            logger.warning("No metrics available for analysis")
            return PerformanceAnalysis(0, 0, "unknown", [], [])

        # Calculate statistics
        build_times = [m.build_time for m in metrics]
        avg_build_time = statistics.mean(build_times)

        # Calculate cache efficiency
        total_hits = sum(m.cache_hits for m in metrics)
        total_misses = sum(m.cache_misses for m in metrics)
        cache_efficiency = (
            (total_hits / (total_hits + total_misses)) * 100
            if (total_hits + total_misses) > 0
            else 0
        )

        # Analyze size trend
        if len(metrics) >= 2:
            recent_sizes = [m.image_size for m in metrics[-5:]]
            older_sizes = (
                [m.image_size for m in metrics[:-5]]
                if len(metrics) > 5
                else [metrics[0].image_size]
            )

            recent_avg = statistics.mean(recent_sizes)
            older_avg = statistics.mean(older_sizes)

            if recent_avg > older_avg * 1.1:
                size_trend = "increasing"
            elif recent_avg < older_avg * 0.9:
                size_trend = "decreasing"
            else:
                size_trend = "stable"
        else:
            size_trend = "insufficient_data"

        # Generate recommendations
        recommendations = self._generate_recommendations(
            metrics, avg_build_time, cache_efficiency
        )

        # Identify bottlenecks
        bottlenecks = self._identify_bottlenecks(metrics, avg_build_time)

        return PerformanceAnalysis(
            avg_build_time=avg_build_time,
            cache_efficiency=cache_efficiency,
            size_trend=size_trend,
            recommendations=recommendations,
            bottlenecks=bottlenecks,
        )

    def _generate_recommendations(
        self,
        metrics: list[BuildMetrics],
        avg_build_time: float,
        cache_efficiency: float,
    ) -> list[str]:
        """Generate optimization recommendations"""
        recommendations = []

        # Cache efficiency recommendations
        if cache_efficiency < 50:
            recommendations.append(
                "Low cache efficiency detected. Consider reordering Dockerfile instructions to maximize layer reuse."
            )

        if cache_efficiency < 30:
            recommendations.append(
                "Very low cache efficiency. Review Dockerfile structure and use .dockerignore to reduce build context."
            )

        # Build time recommendations
        if avg_build_time > 300:  # 5 minutes
            recommendations.append(
                "Long build times detected. Consider using multi-stage builds and optimizing dependency installation."
            )

        # Image size recommendations
        recent_metrics = metrics[-10:] if len(metrics) >= 10 else metrics
        avg_size = statistics.mean(m.image_size for m in recent_metrics)

        if avg_size > 2 * 1024 * 1024 * 1024:  # 2GB
            recommendations.append(
                "Large image size detected. Consider using smaller base images and removing unnecessary files."
            )

        # Layer count recommendations
        avg_layers = statistics.mean(m.layer_count for m in recent_metrics)
        if avg_layers > 20:
            recommendations.append(
                "High layer count detected. Consider combining RUN commands to reduce layers."
            )

        # Build context recommendations
        avg_context_size = statistics.mean(m.build_context_size for m in recent_metrics)
        if avg_context_size > 100 * 1024 * 1024:  # 100MB
            recommendations.append(
                "Large build context detected. Use .dockerignore to exclude unnecessary files."
            )

        return recommendations

    def _identify_bottlenecks(
        self, metrics: list[BuildMetrics], avg_build_time: float
    ) -> list[str]:
        """Identify performance bottlenecks"""
        bottlenecks = []

        # Slow builds
        slow_builds = [m for m in metrics if m.build_time > avg_build_time * 1.5]
        if len(slow_builds) > len(metrics) * 0.2:  # More than 20% of builds are slow
            bottlenecks.append("Frequent slow builds detected")

        # Cache misses
        high_miss_builds = [m for m in metrics if m.cache_misses > m.cache_hits]
        if (
            len(high_miss_builds) > len(metrics) * 0.3
        ):  # More than 30% have more misses than hits
            bottlenecks.append("High cache miss rate")

        # Large build contexts
        large_context_builds = [
            m for m in metrics if m.build_context_size > 50 * 1024 * 1024
        ]  # 50MB
        if len(large_context_builds) > len(metrics) * 0.5:
            bottlenecks.append("Large build contexts")

        return bottlenecks

    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate performance report"""
        analysis = self.analyze_performance()
        metrics = self.load_metrics()

        report_content = f"""
# Build Performance Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Summary Statistics

- **Average Build Time**: {analysis.avg_build_time:.2f} seconds
- **Cache Efficiency**: {analysis.cache_efficiency:.1f}%
- **Size Trend**: {analysis.size_trend}
- **Total Builds Analyzed**: {len(metrics)}

## Performance Analysis

### Cache Efficiency
{analysis.cache_efficiency:.1f}% of build steps used cache.

### Build Time Trends
Recent builds average {analysis.avg_build_time:.2f} seconds.

### Image Size Trends
Image sizes are {analysis.size_trend}.

## Recommendations

"""

        for i, rec in enumerate(analysis.recommendations, 1):
            report_content += f"{i}. {rec}\n"

        if analysis.bottlenecks:
            report_content += "\n## Identified Bottlenecks\n\n"
            for i, bottleneck in enumerate(analysis.bottlenecks, 1):
                report_content += f"{i}. {bottleneck}\n"

        # Recent builds table
        if metrics:
            report_content += "\n## Recent Builds\n\n"
            report_content += (
                "| Image | Build Time | Cache Efficiency | Size | Status |\n"
            )
            report_content += (
                "|-------|------------|------------------|------|--------|\n"
            )

            for metric in metrics[-10:]:  # Last 10 builds
                cache_eff = (
                    (metric.cache_hits / (metric.cache_hits + metric.cache_misses))
                    * 100
                    if (metric.cache_hits + metric.cache_misses) > 0
                    else 0
                )
                size_mb = metric.image_size / (1024 * 1024)
                status = "✅" if metric.success else "❌"

                report_content += f"| {metric.image_name} | {metric.build_time:.1f}s | {cache_eff:.1f}% | {size_mb:.1f}MB | {status} |\n"

        # Save report if output file specified
        if output_file:
            with open(output_file, "w") as f:
                f.write(report_content)
            logger.info(f"Report saved to: {output_file}")

        return report_content

    def optimize_dockerfile(self, dockerfile_path: str) -> list[str]:
        """Analyze Dockerfile and suggest optimizations"""
        suggestions = []

        try:
            with open(dockerfile_path) as f:
                lines = f.readlines()

            # Analyze Dockerfile structure
            run_commands = [
                i for i, line in enumerate(lines) if line.strip().startswith("RUN")
            ]
            copy_commands = [
                i for i, line in enumerate(lines) if line.strip().startswith("COPY")
            ]

            # Check for optimization opportunities
            if len(run_commands) > 5:
                suggestions.append(
                    "Consider combining multiple RUN commands to reduce layers"
                )

            # Check for COPY before RUN (dependency installation)
            for copy_idx in copy_commands:
                for run_idx in run_commands:
                    if copy_idx < run_idx and "requirements" in lines[copy_idx].lower():
                        suggestions.append(
                            "Good: Dependencies copied before installation for better caching"
                        )
                        break

            # Check for .dockerignore
            dockerignore_path = Path(dockerfile_path).parent / ".dockerignore"
            if not dockerignore_path.exists():
                suggestions.append(
                    "Consider adding .dockerignore to reduce build context size"
                )

            # Check for multi-stage builds
            from_commands = [line for line in lines if line.strip().startswith("FROM")]
            if len(from_commands) == 1:
                suggestions.append(
                    "Consider using multi-stage builds for smaller final images"
                )

        except FileNotFoundError:
            suggestions.append(f"Dockerfile not found: {dockerfile_path}")

        return suggestions


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Build Performance Monitor")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument(
        "--action",
        choices=["monitor", "analyze", "report", "optimize"],
        default="analyze",
        help="Action to perform",
    )
    parser.add_argument("--image", help="Image name to monitor/analyze")
    parser.add_argument("--dockerfile", help="Dockerfile path for optimization")
    parser.add_argument("--build-command", nargs="+", help="Build command to monitor")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument(
        "--days", type=int, default=7, help="Days of history to analyze"
    )

    args = parser.parse_args()

    monitor = BuildPerformanceMonitor(args.project_root)

    try:
        if args.action == "monitor":
            if not args.image or not args.build_command:
                logger.error("Image name and build command required for monitoring")
                sys.exit(1)

            dockerfile = args.dockerfile or "Dockerfile"
            metrics = monitor.monitor_build(args.image, dockerfile, args.build_command)

            print(f"Build completed: {metrics.success}")
            print(f"Build time: {metrics.build_time:.2f}s")
            print(
                f"Cache efficiency: {(metrics.cache_hits / (metrics.cache_hits + metrics.cache_misses)) * 100:.1f}%"
                if (metrics.cache_hits + metrics.cache_misses) > 0
                else "Cache efficiency: N/A"
            )

        elif args.action == "analyze":
            analysis = monitor.analyze_performance(args.image, args.days)

            print(f"Average build time: {analysis.avg_build_time:.2f}s")
            print(f"Cache efficiency: {analysis.cache_efficiency:.1f}%")
            print(f"Size trend: {analysis.size_trend}")

            if analysis.recommendations:
                print("\nRecommendations:")
                for i, rec in enumerate(analysis.recommendations, 1):
                    print(f"  {i}. {rec}")

            if analysis.bottlenecks:
                print("\nBottlenecks:")
                for i, bottleneck in enumerate(analysis.bottlenecks, 1):
                    print(f"  {i}. {bottleneck}")

        elif args.action == "report":
            report = monitor.generate_report(args.output)
            if not args.output:
                print(report)

        elif args.action == "optimize":
            if not args.dockerfile:
                logger.error("Dockerfile path required for optimization")
                sys.exit(1)

            suggestions = monitor.optimize_dockerfile(args.dockerfile)

            print("Dockerfile Optimization Suggestions:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"  {i}. {suggestion}")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
