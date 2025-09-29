"""
Test validator for comprehensive test result validation and reporting.

This module provides the ResultValidator class that validates test results against
expected outcomes, generates comprehensive reports, and provides recommendations
for system improvements.

Key Features:
- Test result validation against expected outcomes
- Performance metrics validation
- Data integrity validation
- Comprehensive report generation
- Automated recommendations based on test results
"""

import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

from core.database import DatabaseManager
from core.test.test_data_manager import DataScenario, ValidationResult


@dataclass
class ValidationRule:
    """Validation rule configuration."""

    name: str
    description: str
    validator_function: callable
    severity: str  # "error", "warning", "info"
    threshold: Optional[float] = None


@dataclass
class ValidationReport:
    """Comprehensive test report data structure."""

    report_id: str
    test_suite_name: str
    execution_timestamp: datetime
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    warnings_count: int
    total_duration: float
    success_rate: float
    validation_results: list[ValidationResult]
    performance_summary: dict[str, Any]
    recommendations: list[str]
    detailed_analysis: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["execution_timestamp"] = self.execution_timestamp.isoformat()
        result["validation_results"] = [vr.to_dict() for vr in self.validation_results]
        return result


class ResultValidator:
    """Validates test results and generates comprehensive reports."""

    def __init__(self, database_managers: dict[str, DatabaseManager]):
        """
        Initialize test validator.

        Args:
            database_managers: Dictionary of database managers
        """
        self.database_managers = database_managers
        self.validation_rules = self._initialize_validation_rules()
        self.performance_baselines = self._initialize_performance_baselines()

    def _initialize_validation_rules(self) -> list[ValidationRule]:
        """Initialize validation rules for different test scenarios."""
        return [
            ValidationRule(
                name="no_duplicate_processing",
                description="Verify no duplicate record processing occurred",
                validator_function=self._validate_no_duplicates,
                severity="error",
            ),
            ValidationRule(
                name="completion_rate",
                description="Verify minimum completion rate is met",
                validator_function=self._validate_completion_rate,
                severity="error",
                threshold=0.85,
            ),
            ValidationRule(
                name="processing_time",
                description="Verify processing time is within acceptable limits",
                validator_function=self._validate_processing_time,
                severity="warning",
                threshold=5000,  # 5 seconds in milliseconds
            ),
            ValidationRule(
                name="data_integrity",
                description="Verify data integrity is maintained",
                validator_function=self._validate_data_integrity,
                severity="error",
            ),
            ValidationRule(
                name="error_handling",
                description="Verify error handling is effective",
                validator_function=self._validate_error_handling,
                severity="warning",
            ),
            ValidationRule(
                name="resource_efficiency",
                description="Verify resource usage is efficient",
                validator_function=self._validate_resource_efficiency,
                severity="info",
                threshold=0.80,
            ),
        ]

    def _initialize_performance_baselines(self) -> dict[str, Any]:
        """Initialize performance baselines for validation."""
        return {
            "min_throughput_per_second": 10,
            "max_latency_ms": 5000,
            "max_error_rate_percent": 5.0,
            "min_completion_rate": 0.85,
            "max_memory_usage_mb": 1000,
            "max_cpu_usage_percent": 90,
            "min_resource_efficiency": 0.70,
        }

    def validate_test_results(
        self,
        scenario: DataScenario,
        test_results: list[dict[str, Any]],
        performance_metrics: Optional[dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate test results against scenario expectations.

        Args:
            scenario: Test scenario configuration
            test_results: List of test execution results
            performance_metrics: Optional performance metrics

        Returns:
            ValidationResult with validation outcome
        """
        start_time = time.time()
        errors = []
        warnings = []
        validation_details = {}

        try:
            # Run validation rules
            for rule in self.validation_rules:
                try:
                    rule_result = rule.validator_function(
                        scenario, test_results, performance_metrics, rule.threshold
                    )

                    validation_details[rule.name] = rule_result

                    if not rule_result.get("passed", True):
                        message = f"{rule.description}: {rule_result.get('message', 'Validation failed')}"

                        if rule.severity == "error":
                            errors.append(message)
                        elif rule.severity == "warning":
                            warnings.append(message)

                except Exception as e:
                    error_msg = f"Validation rule '{rule.name}' failed: {str(e)}"
                    errors.append(error_msg)
                    validation_details[rule.name] = {"passed": False, "error": str(e)}

            # Determine overall status
            status = "failed" if errors else ("passed" if not warnings else "passed")

            # Calculate metrics
            records_processed = len(test_results)
            expected_count = scenario.record_count

            return ValidationResult(
                test_name=f"validate_{scenario.name}",
                scenario_name=scenario.name,
                status=status,
                duration=time.time() - start_time,
                records_processed=records_processed,
                expected_count=expected_count,
                validation_details=validation_details,
                errors=errors,
                warnings=warnings,
                timestamp=datetime.now(),
            )

        except Exception as e:
            return ValidationResult(
                test_name=f"validate_{scenario.name}",
                scenario_name=scenario.name,
                status="failed",
                duration=time.time() - start_time,
                records_processed=0,
                expected_count=scenario.record_count,
                validation_details={"error": str(e)},
                errors=[f"Validation failed: {str(e)}"],
                warnings=warnings,
                timestamp=datetime.now(),
            )

    def _validate_no_duplicates(
        self,
        scenario: DataScenario,
        test_results: list[dict[str, Any]],
        performance_metrics: Optional[dict[str, Any]],
        threshold: Optional[float],
    ) -> dict[str, Any]:
        """Validate no duplicate processing occurred."""
        try:
            # Extract processed record IDs
            processed_ids = []
            for result in test_results:
                if result.get("status") == "completed":
                    record_id = result.get("record_id") or result.get("id")
                    if record_id:
                        processed_ids.append(record_id)

            # Check for duplicates
            unique_ids = set(processed_ids)
            duplicate_count = len(processed_ids) - len(unique_ids)

            return {
                "passed": duplicate_count == 0,
                "message": (
                    f"Found {duplicate_count} duplicate processing instances"
                    if duplicate_count > 0
                    else "No duplicates found"
                ),
                "details": {
                    "total_processed": len(processed_ids),
                    "unique_processed": len(unique_ids),
                    "duplicate_count": duplicate_count,
                },
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _validate_completion_rate(
        self,
        scenario: DataScenario,
        test_results: list[dict[str, Any]],
        performance_metrics: Optional[dict[str, Any]],
        threshold: Optional[float],
    ) -> dict[str, Any]:
        """Validate completion rate meets minimum threshold."""
        try:
            min_rate = threshold or scenario.expected_outcomes.get(
                "completion_rate_min", 0.85
            )

            completed_count = len(
                [r for r in test_results if r.get("status") == "completed"]
            )
            total_count = len(test_results)

            if total_count == 0:
                return {"passed": False, "message": "No test results to validate"}

            completion_rate = completed_count / total_count

            return {
                "passed": completion_rate >= min_rate,
                "message": f"Completion rate {completion_rate:.2%} {'meets' if completion_rate >= min_rate else 'below'} minimum {min_rate:.2%}",
                "details": {
                    "completed_count": completed_count,
                    "total_count": total_count,
                    "completion_rate": completion_rate,
                    "minimum_required": min_rate,
                },
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _validate_processing_time(
        self,
        scenario: DataScenario,
        test_results: list[dict[str, Any]],
        performance_metrics: Optional[dict[str, Any]],
        threshold: Optional[float],
    ) -> dict[str, Any]:
        """Validate processing time is within acceptable limits."""
        try:
            max_time_ms = threshold or scenario.expected_outcomes.get(
                "processing_time_max_ms", 5000
            )

            # Extract processing times
            processing_times = []
            for result in test_results:
                if result.get("status") == "completed":
                    # Try different possible time fields
                    time_ms = (
                        result.get("processing_time_ms")
                        or result.get("duration_ms")
                        or (result.get("duration", 0) * 1000)  # Convert seconds to ms
                    )
                    if time_ms:
                        processing_times.append(time_ms)

            if not processing_times:
                return {
                    "passed": True,
                    "message": "No processing times available for validation",
                }

            avg_time = statistics.mean(processing_times)
            max_time = max(processing_times)

            return {
                "passed": avg_time <= max_time_ms,
                "message": f"Average processing time {avg_time:.1f}ms {'within' if avg_time <= max_time_ms else 'exceeds'} limit {max_time_ms}ms",
                "details": {
                    "average_time_ms": avg_time,
                    "max_time_ms": max_time,
                    "threshold_ms": max_time_ms,
                    "sample_count": len(processing_times),
                },
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _validate_data_integrity(
        self,
        scenario: DataScenario,
        test_results: list[dict[str, Any]],
        performance_metrics: Optional[dict[str, Any]],
        threshold: Optional[float],
    ) -> dict[str, Any]:
        """Validate data integrity is maintained."""
        try:
            # Check for data corruption indicators
            integrity_issues = []

            for result in test_results:
                # Check for missing required fields
                if not result.get("record_id") and not result.get("id"):
                    integrity_issues.append("Missing record ID")

                # Check for invalid status values
                status = result.get("status")
                if status not in ["pending", "processing", "completed", "failed"]:
                    integrity_issues.append(f"Invalid status: {status}")

                # Check for data consistency
                if result.get("status") == "completed" and not result.get("result"):
                    integrity_issues.append("Completed record missing result data")

            return {
                "passed": len(integrity_issues) == 0,
                "message": (
                    f"Found {len(integrity_issues)} data integrity issues"
                    if integrity_issues
                    else "Data integrity maintained"
                ),
                "details": {
                    "integrity_issues": integrity_issues[:10],  # Limit to first 10
                    "total_issues": len(integrity_issues),
                    "records_checked": len(test_results),
                },
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _validate_error_handling(
        self,
        scenario: DataScenario,
        test_results: list[dict[str, Any]],
        performance_metrics: Optional[dict[str, Any]],
        threshold: Optional[float],
    ) -> dict[str, Any]:
        """Validate error handling is effective."""
        try:
            failed_results = [r for r in test_results if r.get("status") == "failed"]

            # Check if failed records have proper error information
            proper_error_handling = 0
            for result in failed_results:
                if result.get("error") or result.get("error_message"):
                    proper_error_handling += 1

            error_handling_rate = (
                proper_error_handling / len(failed_results) if failed_results else 1.0
            )

            return {
                "passed": error_handling_rate
                >= 0.90,  # 90% of errors should be properly handled
                "message": f"Error handling rate: {error_handling_rate:.2%}",
                "details": {
                    "failed_records": len(failed_results),
                    "properly_handled": proper_error_handling,
                    "error_handling_rate": error_handling_rate,
                },
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    def _validate_resource_efficiency(
        self,
        scenario: DataScenario,
        test_results: list[dict[str, Any]],
        performance_metrics: Optional[dict[str, Any]],
        threshold: Optional[float],
    ) -> dict[str, Any]:
        """Validate resource usage is efficient."""
        try:
            if not performance_metrics:
                return {"passed": True, "message": "No performance metrics available"}

            min_efficiency = threshold or 0.70

            # Calculate efficiency based on available metrics
            efficiency_score = 1.0
            efficiency_factors = []

            # Memory efficiency
            memory_usage = performance_metrics.get("memory_usage_mb", 0)
            if memory_usage > 0:
                memory_efficiency = max(0, 1 - (memory_usage / 1000))  # 1GB baseline
                efficiency_factors.append(memory_efficiency)

            # CPU efficiency
            cpu_usage = performance_metrics.get("cpu_usage_percent", 0)
            if cpu_usage > 0:
                cpu_efficiency = max(0, 1 - (cpu_usage / 100))
                efficiency_factors.append(cpu_efficiency)

            # Throughput efficiency
            throughput = performance_metrics.get("throughput_per_second", 0)
            if throughput > 0:
                throughput_efficiency = min(
                    1.0, throughput / 50
                )  # 50 records/sec baseline
                efficiency_factors.append(throughput_efficiency)

            if efficiency_factors:
                efficiency_score = statistics.mean(efficiency_factors)

            return {
                "passed": efficiency_score >= min_efficiency,
                "message": f"Resource efficiency: {efficiency_score:.2%}",
                "details": {
                    "efficiency_score": efficiency_score,
                    "minimum_required": min_efficiency,
                    "efficiency_factors": efficiency_factors,
                    "performance_metrics": performance_metrics,
                },
            }

        except Exception as e:
            return {"passed": False, "error": str(e)}

    def generate_comprehensive_report(
        self,
        test_suite_name: str,
        validation_results: list[ValidationResult],
        performance_metrics: Optional[dict[str, Any]] = None,
    ) -> ValidationReport:
        """
        Generate comprehensive test report.

        Args:
            test_suite_name: Name of the test suite
            validation_results: List of validation results
            performance_metrics: Optional performance metrics

        Returns:
            ValidationReport with comprehensive analysis
        """
        try:
            # Calculate summary statistics
            total_tests = len(validation_results)
            passed_tests = len([r for r in validation_results if r.status == "passed"])
            failed_tests = len([r for r in validation_results if r.status == "failed"])
            skipped_tests = len(
                [r for r in validation_results if r.status == "skipped"]
            )

            total_warnings = sum(len(r.warnings) for r in validation_results)
            total_duration = sum(r.duration for r in validation_results)
            success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

            # Generate performance summary
            performance_summary = self._generate_performance_summary(
                validation_results, performance_metrics
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(validation_results)

            # Generate detailed analysis
            detailed_analysis = self._generate_detailed_analysis(validation_results)

            return ValidationReport(
                report_id=f"report_{int(time.time())}",
                test_suite_name=test_suite_name,
                execution_timestamp=datetime.now(),
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                skipped_tests=skipped_tests,
                warnings_count=total_warnings,
                total_duration=total_duration,
                success_rate=success_rate,
                validation_results=validation_results,
                performance_summary=performance_summary,
                recommendations=recommendations,
                detailed_analysis=detailed_analysis,
            )

        except Exception as e:
            # Return error report
            return ValidationReport(
                report_id=f"error_report_{int(time.time())}",
                test_suite_name=test_suite_name,
                execution_timestamp=datetime.now(),
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                warnings_count=0,
                total_duration=0,
                success_rate=0,
                validation_results=[],
                performance_summary={"error": str(e)},
                recommendations=[f"Report generation failed: {str(e)}"],
                detailed_analysis={"error": str(e)},
            )

    def _generate_performance_summary(
        self,
        validation_results: list[ValidationResult],
        performance_metrics: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate performance summary from validation results."""
        try:
            summary = {
                "total_records_processed": sum(
                    r.records_processed for r in validation_results
                ),
                "average_processing_time": (
                    statistics.mean([r.duration for r in validation_results])
                    if validation_results
                    else 0
                ),
                "throughput_records_per_second": 0,
            }

            # Calculate throughput
            total_records = summary["total_records_processed"]
            total_time = sum(r.duration for r in validation_results)
            if total_time > 0:
                summary["throughput_records_per_second"] = total_records / total_time

            # Add performance metrics if available
            if performance_metrics:
                summary.update(performance_metrics)

            # Performance grade
            throughput = summary["throughput_records_per_second"]
            if throughput >= 50:
                summary["performance_grade"] = "A"
            elif throughput >= 25:
                summary["performance_grade"] = "B"
            elif throughput >= 10:
                summary["performance_grade"] = "C"
            else:
                summary["performance_grade"] = "D"

            return summary

        except Exception as e:
            return {"error": str(e)}

    def _generate_recommendations(
        self, validation_results: list[ValidationResult]
    ) -> list[str]:
        """Generate recommendations based on validation results."""
        recommendations = []

        try:
            # Analyze common failure patterns
            error_patterns = {}
            for result in validation_results:
                for error in result.errors:
                    error_type = error.split(":")[0] if ":" in error else error
                    error_patterns[error_type] = error_patterns.get(error_type, 0) + 1

            # Generate specific recommendations
            if any(
                "duplicate" in error.lower()
                for result in validation_results
                for error in result.errors
            ):
                recommendations.append(
                    "Implement stronger record locking mechanisms to prevent duplicate processing"
                )

            if any(
                "completion rate" in error.lower()
                for result in validation_results
                for error in result.errors
            ):
                recommendations.append(
                    "Review error handling and retry mechanisms to improve completion rates"
                )

            if any(
                "processing time" in error.lower()
                for result in validation_results
                for error in result.errors
            ):
                recommendations.append(
                    "Optimize database queries and consider connection pooling improvements"
                )

            if any(
                "data integrity" in error.lower()
                for result in validation_results
                for error in result.errors
            ):
                recommendations.append(
                    "Implement additional data validation and consistency checks"
                )

            # Performance recommendations
            failed_tests = [r for r in validation_results if r.status == "failed"]
            if len(failed_tests) > len(validation_results) * 0.2:  # >20% failure rate
                recommendations.append(
                    "High failure rate detected - conduct thorough system stability review"
                )

            # Success recommendations
            if not recommendations:
                recommendations.append(
                    "All validations passed successfully - system is performing optimally"
                )

            return recommendations

        except Exception:
            return ["Unable to generate recommendations due to analysis error"]

    def _generate_detailed_analysis(
        self, validation_results: list[ValidationResult]
    ) -> dict[str, Any]:
        """Generate detailed analysis of validation results."""
        try:
            analysis = {
                "scenario_breakdown": {},
                "validation_rule_performance": {},
                "error_analysis": {},
                "timing_analysis": {},
            }

            # Scenario breakdown
            for result in validation_results:
                scenario = result.scenario_name
                if scenario not in analysis["scenario_breakdown"]:
                    analysis["scenario_breakdown"][scenario] = {
                        "total_tests": 0,
                        "passed": 0,
                        "failed": 0,
                        "average_duration": 0,
                    }

                breakdown = analysis["scenario_breakdown"][scenario]
                breakdown["total_tests"] += 1
                if result.status == "passed":
                    breakdown["passed"] += 1
                elif result.status == "failed":
                    breakdown["failed"] += 1

            # Calculate averages
            for scenario, breakdown in analysis["scenario_breakdown"].items():
                scenario_results = [
                    r for r in validation_results if r.scenario_name == scenario
                ]
                if scenario_results:
                    breakdown["average_duration"] = statistics.mean(
                        [r.duration for r in scenario_results]
                    )

            # Validation rule performance
            all_validation_details = {}
            for result in validation_results:
                for rule_name, rule_result in result.validation_details.items():
                    if rule_name not in all_validation_details:
                        all_validation_details[rule_name] = []
                    all_validation_details[rule_name].append(rule_result)

            for rule_name, rule_results in all_validation_details.items():
                passed_count = len([r for r in rule_results if r.get("passed", False)])
                total_count = len(rule_results)
                analysis["validation_rule_performance"][rule_name] = {
                    "pass_rate": (passed_count / total_count) if total_count > 0 else 0,
                    "total_executions": total_count,
                }

            # Error analysis
            all_errors = []
            for result in validation_results:
                all_errors.extend(result.errors)

            error_frequency = {}
            for error in all_errors:
                error_type = error.split(":")[0] if ":" in error else error
                error_frequency[error_type] = error_frequency.get(error_type, 0) + 1

            analysis["error_analysis"] = {
                "total_errors": len(all_errors),
                "unique_error_types": len(error_frequency),
                "most_common_errors": sorted(
                    error_frequency.items(), key=lambda x: x[1], reverse=True
                )[:5],
            }

            # Timing analysis
            durations = [r.duration for r in validation_results]
            if durations:
                analysis["timing_analysis"] = {
                    "average_duration": statistics.mean(durations),
                    "median_duration": statistics.median(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                    "total_duration": sum(durations),
                }

            return analysis

        except Exception as e:
            return {"error": str(e)}

    def export_report(
        self, report: ValidationReport, output_path: str, format: str = "json"
    ) -> bool:
        """
        Export test report to file.

        Args:
            report: ValidationReport to export
            output_path: Path to save the report
            format: Export format ("json" or "html")

        Returns:
            True if export successful, False otherwise
        """
        try:
            from pathlib import Path

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            if format.lower() == "json":
                with open(output_file, "w") as f:
                    json.dump(report.to_dict(), f, indent=2, default=str)
            elif format.lower() == "html":
                html_content = self._generate_html_report(report)
                with open(output_file, "w") as f:
                    f.write(html_content)
            else:
                raise ValueError(f"Unsupported format: {format}")

            return True

        except Exception as e:
            print(f"Failed to export report: {e}")
            return False

    def _generate_html_report(self, report: ValidationReport) -> str:
        """Generate HTML report content."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Test Report - {report.test_suite_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .summary {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .metric {{ text-align: center; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                .warning {{ color: orange; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Test Report: {report.test_suite_name}</h1>
                <p>Generated: {report.execution_timestamp.strftime("%Y-%m-%d %H:%M:%S")}</p>
                <p>Report ID: {report.report_id}</p>
            </div>

            <div class="summary">
                <div class="metric">
                    <h3>Total Tests</h3>
                    <p>{report.total_tests}</p>
                </div>
                <div class="metric">
                    <h3 class="passed">Passed</h3>
                    <p>{report.passed_tests}</p>
                </div>
                <div class="metric">
                    <h3 class="failed">Failed</h3>
                    <p>{report.failed_tests}</p>
                </div>
                <div class="metric">
                    <h3>Success Rate</h3>
                    <p>{report.success_rate:.1f}%</p>
                </div>
            </div>

            <h2>Recommendations</h2>
            <ul>
                {"".join(f"<li>{rec}</li>" for rec in report.recommendations)}
            </ul>

            <h2>Performance Summary</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                {"".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in report.performance_summary.items())}
            </table>

        </body>
        </html>
        """
        return html
