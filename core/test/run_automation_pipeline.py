#!/usr/bin/env python3
"""
Test Automation Pipeline Runner

Main entry point for executing the comprehensive test automation pipeline
with support for different execution modes, reporting, and CI/CD integration.

Requirements: 9.3, 9.5, 9.7
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import after path modification to avoid E402
from core.config import ConfigManager  # noqa: E402
from core.database import DatabaseManager  # noqa: E402
from core.test.test_automation_pipeline import (  # noqa: E402
    AutomationPipeline,
    TrendAnalyzer,
)


def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)

    # Setup file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def setup_database_managers(
    config_manager: ConfigManager,
) -> dict[str, DatabaseManager]:
    """Setup database managers for testing"""
    database_managers = {}
    logger = logging.getLogger(__name__)

    # Try to setup RPA database
    try:
        rpa_db = DatabaseManager("rpa_db")
        # Test connectivity
        result = rpa_db.execute_query("SELECT 1 as test")
        if result and result[0].get("test") == 1:
            database_managers["rpa_db"] = rpa_db
            logger.info("✅ RPA database manager initialized successfully")
        else:
            logger.warning("⚠️  RPA database connectivity test failed")
    except Exception as e:
        logger.warning(f"⚠️  Could not initialize RPA database manager: {e}")

    # Try to setup source database if configured
    try:
        source_db = DatabaseManager("source_db")
        database_managers["source_db"] = source_db
        logger.info("✅ Source database manager initialized successfully")
    except Exception as e:
        logger.debug(f"Source database not configured or unavailable: {e}")

    return database_managers


async def run_quick_tests(pipeline: AutomationPipeline) -> dict:
    """Run quick subset of tests for fast feedback"""
    logger = logging.getLogger(__name__)

    logger.info("Running quick test suite...")

    # Execute only unit and basic integration tests
    result = await pipeline.execute_full_pipeline(
        include_chaos_tests=False, include_performance_tests=False, fail_fast=True
    )

    return {
        "mode": "quick",
        "result": result,
        "summary": {
            "status": result.status,
            "duration": result.total_duration,
            "tests": f"{result.total_passed}/{result.total_tests}",
            "categories": f"{len(result.categories_passed)}/{len(result.categories_executed)}",
        },
    }


async def run_full_pipeline(pipeline: AutomationPipeline) -> dict:
    """Run complete test pipeline including chaos tests"""
    logger = logging.getLogger(__name__)

    logger.info("Running full test automation pipeline...")

    result = await pipeline.execute_full_pipeline(
        include_chaos_tests=True, include_performance_tests=True, fail_fast=False
    )

    return {
        "mode": "full",
        "result": result,
        "summary": {
            "status": result.status,
            "duration": result.total_duration,
            "tests": f"{result.total_passed}/{result.total_tests}",
            "categories": f"{len(result.categories_passed)}/{len(result.categories_executed)}",
            "chaos_tests": f"{result.chaos_tests_passed}/{result.chaos_tests_executed}",
        },
    }


async def run_chaos_only(pipeline: AutomationPipeline) -> dict:
    """Run only chaos testing scenarios"""
    logger = logging.getLogger(__name__)

    logger.info("Running chaos testing scenarios...")

    # Execute minimal tests plus chaos
    result = await pipeline.execute_full_pipeline(
        include_chaos_tests=True, include_performance_tests=False, fail_fast=False
    )

    return {
        "mode": "chaos",
        "result": result,
        "summary": {
            "status": result.status,
            "chaos_tests": f"{result.chaos_tests_passed}/{result.chaos_tests_executed}",
            "chaos_success_rate": f"{(result.chaos_tests_passed / max(result.chaos_tests_executed, 1)) * 100:.1f}%",
        },
    }


async def run_performance_only(pipeline: AutomationPipeline) -> dict:
    """Run only performance tests"""
    logger = logging.getLogger(__name__)

    logger.info("Running performance test suite...")

    result = await pipeline.execute_full_pipeline(
        include_chaos_tests=False, include_performance_tests=True, fail_fast=False
    )

    return {
        "mode": "performance",
        "result": result,
        "summary": {
            "status": result.status,
            "duration": result.total_duration,
            "performance_metrics": result.performance_metrics,
        },
    }


def generate_reports(execution_result: dict, output_dir: str, formats: list):
    """Generate test reports in specified formats"""
    logger = logging.getLogger(__name__)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result = execution_result["result"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    generated_files = []

    # Generate JSON report
    if "json" in formats:
        json_file = output_path / f"pipeline_report_{timestamp}.json"

        # Convert result to serializable format
        report_data = {
            "execution_info": {
                "mode": execution_result["mode"],
                "timestamp": datetime.now().isoformat(),
                "summary": execution_result["summary"],
            },
            "pipeline_result": {
                "pipeline_id": result.pipeline_id,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat(),
                "total_duration": result.total_duration,
                "status": result.status,
                "categories_executed": result.categories_executed,
                "categories_passed": result.categories_passed,
                "categories_failed": result.categories_failed,
                "chaos_tests_executed": result.chaos_tests_executed,
                "chaos_tests_passed": result.chaos_tests_passed,
                "total_tests": result.total_tests,
                "total_passed": result.total_passed,
                "total_failed": result.total_failed,
                "performance_metrics": result.performance_metrics,
                "recommendations": result.recommendations,
            },
        }

        with open(json_file, "w") as f:
            json.dump(report_data, f, indent=2)

        generated_files.append(str(json_file))
        logger.info(f"📄 JSON report generated: {json_file}")

    # Generate HTML report
    if "html" in formats:
        html_file = output_path / f"pipeline_report_{timestamp}.html"

        html_content = generate_html_report(execution_result)

        with open(html_file, "w") as f:
            f.write(html_content)

        generated_files.append(str(html_file))
        logger.info(f"📄 HTML report generated: {html_file}")

    # Generate summary report
    if "summary" in formats:
        summary_file = output_path / f"pipeline_summary_{timestamp}.txt"

        summary_content = generate_summary_report(execution_result)

        with open(summary_file, "w") as f:
            f.write(summary_content)

        generated_files.append(str(summary_file))
        logger.info(f"📄 Summary report generated: {summary_file}")

    return generated_files


def generate_html_report(execution_result: dict) -> str:
    """Generate HTML report content"""
    result = execution_result["result"]
    execution_result["summary"]

    # Determine status color
    status_color = {"passed": "#28a745", "failed": "#dc3545", "partial": "#ffc107"}.get(
        result.status, "#6c757d"
    )

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Automation Pipeline Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px 8px 0 0; }}
        .header h1 {{ margin: 0; font-size: 2.5em; }}
        .header .subtitle {{ opacity: 0.9; margin-top: 10px; }}
        .content {{ padding: 30px; }}
        .status-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; color: white; font-weight: bold; background: {status_color}; }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
        .metric-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; border-left: 4px solid #007bff; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #007bff; }}
        .metric-label {{ color: #6c757d; margin-top: 5px; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ color: #495057; border-bottom: 2px solid #e9ecef; padding-bottom: 10px; }}
        .category-list {{ list-style: none; padding: 0; }}
        .category-item {{ padding: 10px; margin: 5px 0; border-radius: 5px; }}
        .category-passed {{ background: #d4edda; color: #155724; }}
        .category-failed {{ background: #f8d7da; color: #721c24; }}
        .recommendations {{ background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 5px; padding: 20px; }}
        .recommendation {{ margin: 10px 0; padding: 10px; background: white; border-radius: 3px; }}
        .footer {{ text-align: center; padding: 20px; color: #6c757d; border-top: 1px solid #e9ecef; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Test Automation Pipeline Report</h1>
            <div class="subtitle">
                Pipeline ID: {result.pipeline_id} |
                Mode: {execution_result["mode"].title()} |
                Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </div>
        </div>

        <div class="content">
            <div class="section">
                <h2>Overall Status</h2>
                <span class="status-badge">{result.status.upper()}</span>
                <p>Pipeline completed in {result.total_duration:.2f} seconds</p>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">{result.total_passed}/{result.total_tests}</div>
                    <div class="metric-label">Tests Passed</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{len(result.categories_passed)}/{len(result.categories_executed)}</div>
                    <div class="metric-label">Categories Passed</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{result.chaos_tests_passed}/{result.chaos_tests_executed}</div>
                    <div class="metric-label">Chaos Tests Passed</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{result.total_duration:.1f}s</div>
                    <div class="metric-label">Total Duration</div>
                </div>
            </div>

            <div class="section">
                <h2>Test Categories</h2>
                <ul class="category-list">
    """

    # Add category results
    for category in result.categories_executed:
        if category in result.categories_passed:
            html += f'<li class="category-item category-passed">✅ {category}</li>'
        else:
            html += f'<li class="category-item category-failed">❌ {category}</li>'

    html += """
                </ul>
            </div>
    """

    # Add recommendations if any
    if result.recommendations:
        html += """
            <div class="section">
                <h2>Recommendations</h2>
                <div class="recommendations">
        """
        for rec in result.recommendations:
            html += f'<div class="recommendation">• {rec}</div>'

        html += """
                </div>
            </div>
        """

    # Add performance metrics if available
    if result.performance_metrics:
        html += """
            <div class="section">
                <h2>Performance Metrics</h2>
                <pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto;">
        """
        html += json.dumps(result.performance_metrics, indent=2)
        html += """
                </pre>
            </div>
        """

    html += f"""
        </div>

        <div class="footer">
            <p>Generated by Container Testing System | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>
    """

    return html


def generate_summary_report(execution_result: dict) -> str:
    """Generate text summary report"""
    result = execution_result["result"]
    execution_result["summary"]

    report = f"""
TEST AUTOMATION PIPELINE SUMMARY
{'=' * 50}

Pipeline ID: {result.pipeline_id}
Execution Mode: {execution_result["mode"].title()}
Status: {result.status.upper()}
Duration: {result.total_duration:.2f} seconds
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

TEST RESULTS
{'=' * 50}
Total Tests: {result.total_tests}
Passed: {result.total_passed}
Failed: {result.total_failed}
Success Rate: {(result.total_passed / max(result.total_tests, 1)) * 100:.1f}%

CATEGORY RESULTS
{'=' * 50}
Categories Executed: {len(result.categories_executed)}
Categories Passed: {len(result.categories_passed)}
Categories Failed: {len(result.categories_failed)}

Passed Categories:
"""

    for category in result.categories_passed:
        report += f"  ✅ {category}\n"

    if result.categories_failed:
        report += "\nFailed Categories:\n"
        for category in result.categories_failed:
            report += f"  ❌ {category}\n"

    if result.chaos_tests_executed > 0:
        chaos_success_rate = (
            result.chaos_tests_passed / result.chaos_tests_executed
        ) * 100
        report += f"""
CHAOS TESTING RESULTS
{'=' * 50}
Chaos Tests Executed: {result.chaos_tests_executed}
Chaos Tests Passed: {result.chaos_tests_passed}
Chaos Success Rate: {chaos_success_rate:.1f}%
"""

    if result.recommendations:
        report += f"""
RECOMMENDATIONS
{'=' * 50}
"""
        for i, rec in enumerate(result.recommendations, 1):
            report += f"{i}. {rec}\n"

    return report


async def analyze_trends(trend_analyzer: TrendAnalyzer, days_back: int) -> dict:
    """Analyze test trends over time"""
    logger = logging.getLogger(__name__)

    logger.info(f"Analyzing test trends over the last {days_back} days...")

    trends = trend_analyzer.analyze_trends(days_back)

    if "error" in trends:
        logger.warning(f"Trend analysis failed: {trends['error']}")
        return {"status": "failed", "error": trends["error"]}

    logger.info("✅ Trend analysis completed")

    # Print summary
    print("\nTREND ANALYSIS SUMMARY")
    print("=" * 50)

    success_trend = trends.get("success_rate_trend", {})
    print(f"Success Rate Trend: {success_trend.get('trend', 'unknown')}")
    print(f"Current Success Rate: {success_trend.get('current_success_rate', 0):.1f}%")

    performance_trend = trends.get("performance_trend", {})
    print(f"Duration Trend: {performance_trend.get('duration_trend', 'unknown')}")
    print(f"Current Duration: {performance_trend.get('current_duration', 0):.1f}s")

    chaos_trend = trends.get("chaos_test_trends", {})
    if "error" not in chaos_trend:
        print(
            f"Chaos Resilience Trend: {chaos_trend.get('chaos_resilience_trend', 'unknown')}"
        )
        print(
            f"Recent Chaos Success Rate: {chaos_trend.get('recent_chaos_success_rate', 0):.1f}%"
        )

    recommendations = trends.get("recommendations", [])
    if recommendations:
        print("\nTrend Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")

    return {"status": "success", "trends": trends}


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(
        description="Test Automation Pipeline Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run quick tests for fast feedback
  python run_automation_pipeline.py --mode quick

  # Run full pipeline with all tests
  python run_automation_pipeline.py --mode full --report

  # Run only chaos tests
  python run_automation_pipeline.py --mode chaos

  # Analyze trends over last 7 days
  python run_automation_pipeline.py --analyze-trends --days-back 7

  # Generate CI configuration
  python run_automation_pipeline.py --generate-ci github
        """,
    )

    # Execution modes
    parser.add_argument(
        "--mode",
        choices=["quick", "full", "chaos", "performance"],
        default="quick",
        help="Test execution mode",
    )

    # Reporting options
    parser.add_argument(
        "--report", action="store_true", help="Generate detailed reports"
    )

    parser.add_argument(
        "--report-formats",
        nargs="+",
        choices=["json", "html", "summary"],
        default=["json", "summary"],
        help="Report formats to generate",
    )

    parser.add_argument(
        "--output-dir", default="./test_reports", help="Output directory for reports"
    )

    # Trend analysis
    parser.add_argument(
        "--analyze-trends", action="store_true", help="Analyze test trends over time"
    )

    parser.add_argument(
        "--days-back", type=int, default=30, help="Days to look back for trend analysis"
    )

    # CI/CD generation
    parser.add_argument(
        "--generate-ci",
        choices=["github", "gitlab", "jenkins"],
        help="Generate CI/CD configuration for specified platform",
    )

    # Logging options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument("--log-file", help="Log file path")

    # Execution options
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop on first critical failure"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose, args.log_file)
    logger = logging.getLogger(__name__)

    try:
        # Handle CI generation
        if args.generate_ci:
            logger.info(f"Generating {args.generate_ci} CI configuration...")

            # Create a temporary pipeline to generate config
            pipeline = AutomationPipeline()
            config = pipeline.generate_ci_config(args.generate_ci)

            # Write to appropriate file
            filename_map = {
                "github": ".github/workflows/test-pipeline.yml",
                "gitlab": ".gitlab-ci.yml",
                "jenkins": "Jenkinsfile",
            }

            config_file = Path(filename_map[args.generate_ci])
            config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, "w") as f:
                f.write(config)

            logger.info(f"✅ CI configuration generated: {config_file}")
            return 0

        # Handle trend analysis
        if args.analyze_trends:
            trend_analyzer = TrendAnalyzer()
            result = asyncio.run(analyze_trends(trend_analyzer, args.days_back))

            if result["status"] == "failed":
                logger.error("Trend analysis failed")
                return 1

            return 0

        # Initialize configuration and database managers
        logger.info("Initializing test environment...")

        config_manager = ConfigManager()
        database_managers = setup_database_managers(config_manager)

        if not database_managers:
            logger.warning(
                "⚠️  No database managers available - some tests may be skipped"
            )

        # Initialize pipeline
        pipeline = AutomationPipeline(database_managers, config_manager)

        # Execute based on mode
        logger.info(f"Starting pipeline execution in {args.mode} mode...")

        if args.mode == "quick":
            execution_result = asyncio.run(run_quick_tests(pipeline))
        elif args.mode == "full":
            execution_result = asyncio.run(run_full_pipeline(pipeline))
        elif args.mode == "chaos":
            execution_result = asyncio.run(run_chaos_only(pipeline))
        elif args.mode == "performance":
            execution_result = asyncio.run(run_performance_only(pipeline))

        # Print summary
        result = execution_result["result"]
        summary = execution_result["summary"]

        print(f"\n{'=' * 60}")
        print("PIPELINE EXECUTION COMPLETED")
        print(f"{'=' * 60}")
        print(f"Status: {result.status.upper()}")
        print(f"Duration: {result.total_duration:.2f} seconds")
        print(f"Tests: {summary['tests']}")
        print(f"Categories: {summary['categories']}")

        if "chaos_tests" in summary:
            print(f"Chaos Tests: {summary['chaos_tests']}")

        if result.recommendations:
            print("\nRecommendations:")
            for i, rec in enumerate(result.recommendations, 1):
                print(f"  {i}. {rec}")

        # Generate reports if requested
        if args.report:
            logger.info("Generating reports...")
            report_files = generate_reports(
                execution_result, args.output_dir, args.report_formats
            )

            print("\nReports generated:")
            for report_file in report_files:
                print(f"  📄 {report_file}")

        # Determine exit code
        if result.status == "failed":
            logger.error("❌ Pipeline failed")
            return 1
        elif result.status == "partial":
            logger.warning("⚠️  Pipeline completed with some failures")
            return 2
        else:
            logger.info("✅ Pipeline completed successfully")
            return 0

    except KeyboardInterrupt:
        logger.warning("Pipeline execution interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
