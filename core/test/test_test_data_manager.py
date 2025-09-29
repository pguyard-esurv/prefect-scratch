"""
Unit tests for test data management and validation system.

This module provides comprehensive unit tests for the DataManager and
ResultValidator classes, ensuring proper functionality of test data lifecycle
management, validation logic, and report generation.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

from core.database import DatabaseManager
from core.test.test_data_manager import (
    DataManager,
    DataScenarios,
)
from core.test.test_validator import ResultValidator, ValidationResult


class TestDataScenariosClass:
    """Unit tests for DataScenarios class."""

    def test_survey_processing_scenario(self):
        """Test survey processing scenario generation."""
        scenario = DataScenarios.survey_processing_scenario(record_count=50)

        assert scenario.name == "survey_processing"
        assert scenario.record_count == 50
        assert scenario.description is not None
        assert len(scenario.cleanup_queries) > 0
        assert "completion_rate_min" in scenario.expected_outcomes

        # Test data generation
        test_data = scenario.data_generator()
        assert len(test_data) == 50

        # Verify data structure
        first_record = test_data[0]
        required_fields = ["survey_id", "customer_id", "customer_name", "survey_type"]
        for field in required_fields:
            assert field in first_record

    def test_order_processing_scenario(self):
        """Test order processing scenario generation."""
        scenario = DataScenarios.order_processing_scenario(record_count=75)

        assert scenario.name == "order_processing"
        assert scenario.record_count == 75

        # Test data generation
        test_data = scenario.data_generator()
        assert len(test_data) == 75

        # Verify financial calculations
        first_record = test_data[0]
        expected_total = (
            first_record["subtotal"]
            + first_record["tax_amount"]
            - first_record["discount_amount"]
        )
        assert abs(first_record["total_amount"] - expected_total) < 0.01

    def test_high_volume_scenario(self):
        """Test high-volume scenario generation."""
        scenario = DataScenarios.high_volume_scenario(record_count=500)

        assert scenario.name == "high_volume_processing"
        assert scenario.record_count == 500
        assert "throughput_min_per_sec" in scenario.expected_outcomes

        # Test data generation
        test_data = scenario.data_generator()
        assert len(test_data) == 500

        # Verify payload structure
        first_record = test_data[0]
        assert "payload" in first_record
        assert "id" in first_record["payload"]
        assert "batch_id" in first_record["payload"]

    def test_error_handling_scenario(self):
        """Test error handling scenario generation."""
        scenario = DataScenarios.error_handling_scenario(record_count=30)

        assert scenario.name == "error_handling"
        assert scenario.record_count == 30

        # Test data generation
        test_data = scenario.data_generator()
        assert len(test_data) == 30

        # Verify some records are designed to fail
        error_records = [
            record
            for record in test_data
            if record["payload"].get("should_fail", False)
        ]
        assert len(error_records) > 0  # Should have some error records


class TestDataManagerClass:
    """Unit tests for DataManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.execute_query.return_value = None

        self.database_managers = {"rpa_db": self.mock_rpa_db}
        self.manager = DataManager(self.database_managers)

    def test_initialization(self):
        """Test DataManager initialization."""
        assert self.manager.database_managers == self.database_managers
        assert isinstance(self.manager.scenarios, DataScenarios)
        assert self.manager.initialized_scenarios == []

    def test_initialize_survey_scenario(self):
        """Test survey scenario initialization."""
        scenario = DataScenarios.survey_processing_scenario(record_count=10)

        result = self.manager.initialize_test_scenario(scenario)

        assert result["status"] == "success"
        assert result["records_created"] == 10
        assert "survey_processing" in self.manager.initialized_scenarios

        # Verify database calls
        assert self.mock_rpa_db.execute_query.call_count == 10

    def test_initialize_order_scenario(self):
        """Test order scenario initialization."""
        scenario = DataScenarios.order_processing_scenario(record_count=5)

        result = self.manager.initialize_test_scenario(scenario)

        assert result["status"] == "success"
        assert result["records_created"] == 5
        assert "order_processing" in self.manager.initialized_scenarios

    def test_initialize_queue_scenario(self):
        """Test queue-based scenario initialization."""
        scenario = DataScenarios.high_volume_scenario(record_count=20)

        result = self.manager.initialize_test_scenario(scenario)

        assert result["status"] == "success"
        assert result["records_created"] == 20
        assert "high_volume_processing" in self.manager.initialized_scenarios

    def test_initialize_scenario_database_error(self):
        """Test scenario initialization with database error."""
        self.mock_rpa_db.execute_query.side_effect = Exception("Database error")

        scenario = DataScenarios.survey_processing_scenario(record_count=5)
        result = self.manager.initialize_test_scenario(scenario)

        assert result["status"] == "failed"
        assert "Database error" in result["error"]

    def test_initialize_scenario_no_database(self):
        """Test scenario initialization without database manager."""
        manager = DataManager({})  # No database managers

        scenario = DataScenarios.survey_processing_scenario(record_count=5)
        result = manager.initialize_test_scenario(scenario)

        assert result["status"] == "failed"
        assert "RPA database manager not found" in result["error"]

    def test_cleanup_test_data(self):
        """Test test data cleanup."""
        # Initialize some scenarios first
        self.manager.initialized_scenarios = ["survey_processing", "order_processing"]

        result = self.manager.cleanup_test_data(["survey_processing"])

        assert result["cleanup_summary"]["total_scenarios"] == 1
        assert result["cleanup_summary"]["successful_cleanups"] == 1
        assert "survey_processing" not in self.manager.initialized_scenarios
        assert "order_processing" in self.manager.initialized_scenarios

    def test_cleanup_all_test_data(self):
        """Test cleanup of all test data."""
        self.manager.initialized_scenarios = ["survey_processing", "order_processing"]

        result = self.manager.cleanup_test_data()  # No specific scenarios = all

        # The cleanup method processes scenarios that are both in initialized_scenarios
        # and exist in the predefined scenarios. Since we have 2 valid scenarios,
        # it should process both
        assert result["cleanup_summary"]["total_scenarios"] == 2
        assert len(self.manager.initialized_scenarios) == 0

    def test_cleanup_with_database_error(self):
        """Test cleanup with database error."""
        self.mock_rpa_db.execute_query.side_effect = Exception("Cleanup error")
        self.manager.initialized_scenarios = ["survey_processing"]

        result = self.manager.cleanup_test_data(["survey_processing"])

        assert result["cleanup_summary"]["failed_cleanups"] == 1
        assert result["scenario_results"]["survey_processing"]["status"] == "failed"

    def test_reset_test_environment(self):
        """Test test environment reset."""
        self.manager.initialized_scenarios = ["survey_processing"]

        result = self.manager.reset_test_environment()

        assert result["reset_status"] == "success"
        assert "cleanup_result" in result

        # Verify reset queries were called
        reset_call_count = len(
            [
                call
                for call in self.mock_rpa_db.execute_query.call_args_list
                if "UPDATE processing_queue" in str(call) or "DELETE FROM" in str(call)
            ]
        )
        assert reset_call_count > 0

    def test_get_test_data_status(self):
        """Test test data status retrieval."""
        self.manager.initialized_scenarios = ["survey_processing"]

        # Mock database responses
        self.mock_rpa_db.execute_query.side_effect = [
            [{"count": 10}],  # Survey count
            [{"count": 5}],  # Order count
            [
                {"flow_name": "test_flow", "status": "pending", "count": 3}
            ],  # Queue status
        ]

        status = self.manager.get_test_data_status()

        assert status["initialized_scenarios"] == ["survey_processing"]
        assert status["survey_test_records"] == 10
        assert status["order_test_records"] == 5
        assert "test_flow_pending" in status["queue_status"]

    def test_get_test_data_status_no_database(self):
        """Test status retrieval without database manager."""
        manager = DataManager({})

        status = manager.get_test_data_status()

        assert "error" in status
        assert "RPA database manager not found" in status["error"]


class TestResultValidatorClass:
    """Unit tests for ResultValidator class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"

        self.database_managers = {"rpa_db": self.mock_rpa_db}
        self.validator = ResultValidator(self.database_managers)

    def test_initialization(self):
        """Test ResultValidator initialization."""
        assert self.validator.database_managers == self.database_managers
        assert len(self.validator.validation_rules) > 0
        assert "min_throughput_per_second" in self.validator.performance_baselines

    def test_validate_no_duplicates_success(self):
        """Test successful duplicate validation."""
        scenario = DataScenarios.survey_processing_scenario(record_count=5)
        test_results = [
            {"record_id": 1, "status": "completed"},
            {"record_id": 2, "status": "completed"},
            {"record_id": 3, "status": "completed"},
            {"record_id": 4, "status": "failed"},
            {"record_id": 5, "status": "completed"},
        ]

        rule = self.validator.validation_rules[0]  # no_duplicate_processing rule
        result = rule.validator_function(scenario, test_results, None, None)

        assert result["passed"] is True
        assert result["details"]["duplicate_count"] == 0

    def test_validate_no_duplicates_failure(self):
        """Test duplicate validation with duplicates found."""
        scenario = DataScenarios.survey_processing_scenario(record_count=3)
        test_results = [
            {"record_id": 1, "status": "completed"},
            {"record_id": 2, "status": "completed"},
            {"record_id": 1, "status": "completed"},  # Duplicate
        ]

        rule = self.validator.validation_rules[0]  # no_duplicate_processing rule
        result = rule.validator_function(scenario, test_results, None, None)

        assert result["passed"] is False
        assert result["details"]["duplicate_count"] == 1

    def test_validate_completion_rate_success(self):
        """Test successful completion rate validation."""
        scenario = DataScenarios.survey_processing_scenario(record_count=10)
        test_results = [{"status": "completed"} for _ in range(9)] + [
            {"status": "failed"}
        ]  # 90% completion rate

        rule = self.validator.validation_rules[1]  # completion_rate rule
        result = rule.validator_function(scenario, test_results, None, 0.85)

        assert result["passed"] is True
        assert result["details"]["completion_rate"] == 0.9

    def test_validate_completion_rate_failure(self):
        """Test completion rate validation failure."""
        scenario = DataScenarios.survey_processing_scenario(record_count=10)
        test_results = [{"status": "completed"} for _ in range(5)] + [
            {"status": "failed"} for _ in range(5)
        ]  # 50% completion rate

        rule = self.validator.validation_rules[1]  # completion_rate rule
        result = rule.validator_function(scenario, test_results, None, 0.85)

        assert result["passed"] is False
        assert result["details"]["completion_rate"] == 0.5

    def test_validate_processing_time_success(self):
        """Test successful processing time validation."""
        scenario = DataScenarios.survey_processing_scenario(record_count=3)
        test_results = [
            {"status": "completed", "processing_time_ms": 1000},
            {"status": "completed", "processing_time_ms": 2000},
            {"status": "completed", "processing_time_ms": 1500},
        ]

        rule = self.validator.validation_rules[2]  # processing_time rule
        result = rule.validator_function(scenario, test_results, None, 5000)

        assert result["passed"] is True
        assert result["details"]["average_time_ms"] == 1500

    def test_validate_processing_time_failure(self):
        """Test processing time validation failure."""
        scenario = DataScenarios.survey_processing_scenario(record_count=2)
        test_results = [
            {"status": "completed", "processing_time_ms": 8000},
            {"status": "completed", "processing_time_ms": 9000},
        ]

        rule = self.validator.validation_rules[2]  # processing_time rule
        result = rule.validator_function(scenario, test_results, None, 5000)

        assert result["passed"] is False
        assert result["details"]["average_time_ms"] == 8500

    def test_validate_data_integrity_success(self):
        """Test successful data integrity validation."""
        scenario = DataScenarios.survey_processing_scenario(record_count=3)
        test_results = [
            {"record_id": 1, "status": "completed", "result": {"processed": True}},
            {"record_id": 2, "status": "failed", "error": "Processing error"},
            {"record_id": 3, "status": "completed", "result": {"processed": True}},
        ]

        rule = self.validator.validation_rules[3]  # data_integrity rule
        result = rule.validator_function(scenario, test_results, None, None)

        assert result["passed"] is True
        assert result["details"]["total_issues"] == 0

    def test_validate_data_integrity_failure(self):
        """Test data integrity validation failure."""
        scenario = DataScenarios.survey_processing_scenario(record_count=2)
        test_results = [
            {"status": "completed"},  # Missing record_id
            {"record_id": 2, "status": "invalid_status"},  # Invalid status
        ]

        rule = self.validator.validation_rules[3]  # data_integrity rule
        result = rule.validator_function(scenario, test_results, None, None)

        assert result["passed"] is False
        assert result["details"]["total_issues"] > 0

    def test_validate_error_handling_success(self):
        """Test successful error handling validation."""
        scenario = DataScenarios.error_handling_scenario(record_count=5)
        test_results = [
            {"status": "completed"},
            {"status": "completed"},
            {"status": "failed", "error": "Processing error"},
            {"status": "failed", "error_message": "Validation failed"},
            {"status": "completed"},
        ]

        rule = self.validator.validation_rules[4]  # error_handling rule
        result = rule.validator_function(scenario, test_results, None, None)

        assert result["passed"] is True
        assert result["details"]["error_handling_rate"] == 1.0

    def test_validate_resource_efficiency(self):
        """Test resource efficiency validation."""
        scenario = DataScenarios.high_volume_scenario(record_count=100)
        test_results = [{"status": "completed"} for _ in range(100)]
        performance_metrics = {
            "memory_usage_mb": 300,  # Better memory efficiency
            "cpu_usage_percent": 40,  # Better CPU efficiency
            "throughput_per_second": 75,
        }

        rule = self.validator.validation_rules[5]  # resource_efficiency rule
        result = rule.validator_function(
            scenario, test_results, performance_metrics, 0.70
        )

        assert result["passed"] is True
        assert "efficiency_score" in result["details"]

    def test_validate_test_results_comprehensive(self):
        """Test comprehensive test result validation."""
        scenario = DataScenarios.survey_processing_scenario(record_count=10)
        test_results = [
            {
                "record_id": i,
                "status": "completed",
                "processing_time_ms": 1000 + i * 100,
            }
            for i in range(1, 9)
        ] + [
            {"record_id": 9, "status": "failed", "error": "Processing error"},
            {"record_id": 10, "status": "completed", "processing_time_ms": 1500},
        ]

        validation_result = self.validator.validate_test_results(scenario, test_results)

        assert isinstance(validation_result, ValidationResult)
        assert validation_result.test_name == "validate_survey_processing"
        assert validation_result.scenario_name == "survey_processing"
        assert validation_result.records_processed == 10
        assert validation_result.expected_count == 10
        assert len(validation_result.validation_details) > 0

    def test_generate_comprehensive_report(self):
        """Test comprehensive report generation."""
        # Create sample validation results
        validation_results = [
            ValidationResult(
                test_name="test1",
                scenario_name="survey_processing",
                status="passed",
                duration=1.5,
                records_processed=100,
                expected_count=100,
                validation_details={"no_duplicate_processing": {"passed": True}},
                errors=[],
                warnings=[],
                timestamp=datetime.now(),
            ),
            ValidationResult(
                test_name="test2",
                scenario_name="order_processing",
                status="failed",
                duration=2.0,
                records_processed=50,
                expected_count=75,
                validation_details={"completion_rate": {"passed": False}},
                errors=["Completion rate too low"],
                warnings=[],
                timestamp=datetime.now(),
            ),
        ]

        performance_metrics = {"throughput_per_second": 45, "memory_usage_mb": 800}

        report = self.validator.generate_comprehensive_report(
            "Container Test Suite", validation_results, performance_metrics
        )

        assert report.test_suite_name == "Container Test Suite"
        assert report.total_tests == 2
        assert report.passed_tests == 1
        assert report.failed_tests == 1
        assert report.success_rate == 50.0
        assert len(report.recommendations) > 0
        assert "performance_grade" in report.performance_summary

    def test_export_report_json(self):
        """Test JSON report export."""
        validation_results = [
            ValidationResult(
                test_name="test1",
                scenario_name="test_scenario",
                status="passed",
                duration=1.0,
                records_processed=10,
                expected_count=10,
                validation_details={},
                errors=[],
                warnings=[],
                timestamp=datetime.now(),
            )
        ]

        report = self.validator.generate_comprehensive_report(
            "Test Suite", validation_results
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            success = self.validator.export_report(report, temp_path, "json")
            assert success is True

            # Verify file was created and contains valid JSON
            with open(temp_path) as f:
                data = json.load(f)
                assert data["test_suite_name"] == "Test Suite"
                assert data["total_tests"] == 1
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_export_report_html(self):
        """Test HTML report export."""
        validation_results = [
            ValidationResult(
                test_name="test1",
                scenario_name="test_scenario",
                status="passed",
                duration=1.0,
                records_processed=10,
                expected_count=10,
                validation_details={},
                errors=[],
                warnings=[],
                timestamp=datetime.now(),
            )
        ]

        report = self.validator.generate_comprehensive_report(
            "Test Suite", validation_results
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as f:
            temp_path = f.name

        try:
            success = self.validator.export_report(report, temp_path, "html")
            assert success is True

            # Verify file was created and contains HTML
            with open(temp_path) as f:
                content = f.read()
                assert "<html>" in content
                assert "Test Suite" in content
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestIntegrationTestDataManagement:
    """Integration tests for test data management system."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.mock_rpa_db = Mock(spec=DatabaseManager)
        self.mock_rpa_db.database_name = "test_rpa_db"
        self.mock_rpa_db.execute_query.return_value = None

        self.database_managers = {"rpa_db": self.mock_rpa_db}
        self.manager = DataManager(self.database_managers)
        self.validator = ResultValidator(self.database_managers)

    def test_full_test_lifecycle(self):
        """Test complete test data lifecycle."""
        # 1. Initialize test scenario
        scenario = DataScenarios.survey_processing_scenario(record_count=20)
        init_result = self.manager.initialize_test_scenario(scenario)
        assert init_result["status"] == "success"

        # 2. Simulate test execution results
        test_results = [
            {"record_id": i, "status": "completed", "processing_time_ms": 1000 + i * 50}
            for i in range(1, 19)
        ] + [
            {"record_id": 19, "status": "failed", "error": "Processing error"},
            {"record_id": 20, "status": "completed", "processing_time_ms": 1200},
        ]

        # 3. Validate test results
        validation_result = self.validator.validate_test_results(scenario, test_results)
        assert validation_result.status in [
            "passed",
            "failed",
        ]  # Should complete validation

        # 4. Generate report
        report = self.validator.generate_comprehensive_report(
            "Integration Test", [validation_result]
        )
        assert report.total_tests == 1

        # 5. Clean up test data
        cleanup_result = self.manager.cleanup_test_data([scenario.name])
        assert cleanup_result["cleanup_summary"]["successful_cleanups"] == 1

    def test_multiple_scenarios_workflow(self):
        """Test workflow with multiple test scenarios."""
        scenarios = [
            DataScenarios.survey_processing_scenario(record_count=10),
            DataScenarios.order_processing_scenario(record_count=15),
            DataScenarios.high_volume_scenario(record_count=50),
        ]

        validation_results = []

        # Initialize and validate each scenario
        for scenario in scenarios:
            # Initialize
            init_result = self.manager.initialize_test_scenario(scenario)
            assert init_result["status"] == "success"

            # Create mock test results
            test_results = [
                {"record_id": i, "status": "completed"}
                for i in range(1, scenario.record_count + 1)
            ]

            # Validate
            validation_result = self.validator.validate_test_results(
                scenario, test_results
            )
            validation_results.append(validation_result)

        # Generate comprehensive report
        report = self.validator.generate_comprehensive_report(
            "Multi-Scenario Test", validation_results
        )

        assert report.total_tests == 3
        assert len(report.detailed_analysis["scenario_breakdown"]) == 3

        # Clean up all scenarios
        cleanup_result = self.manager.cleanup_test_data()
        assert cleanup_result["cleanup_summary"]["successful_cleanups"] == 3

    def test_error_recovery_workflow(self):
        """Test error recovery in test data management workflow."""
        # Test scenario initialization with database error
        self.mock_rpa_db.execute_query.side_effect = Exception(
            "Database connection lost"
        )

        scenario = DataScenarios.survey_processing_scenario(record_count=5)
        init_result = self.manager.initialize_test_scenario(scenario)

        assert init_result["status"] == "failed"
        assert "Database connection lost" in init_result["error"]

        # Reset mock and test recovery
        self.mock_rpa_db.execute_query.side_effect = None
        self.mock_rpa_db.execute_query.return_value = None

        # Should work after recovery
        init_result = self.manager.initialize_test_scenario(scenario)
        assert init_result["status"] == "success"
