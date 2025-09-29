"""
Test data management and validation system for container testing.

This module provides comprehensive test data management capabilities including
database initialization with realistic test scenarios, test data cleanup and reset
functionality, and test result validation and reporting.

Key Components:
- DataManager: Manages test data lifecycle and database initialization
- TestValidator: Validates test results and generates comprehensive reports
- DataScenarios: Provides realistic test data scenarios for different workflows
"""

import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from core.database import DatabaseManager


@dataclass
class DataScenario:
    """Test data scenario configuration."""

    name: str
    description: str
    record_count: int
    data_generator: callable
    expected_outcomes: dict[str, Any]
    cleanup_queries: list[str]


@dataclass
class ValidationResult:
    """Test validation result data structure."""

    test_name: str
    scenario_name: str
    status: str  # "passed", "failed", "skipped"
    duration: float
    records_processed: int
    expected_count: int
    validation_details: dict[str, Any]
    errors: list[str]
    warnings: list[str]
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        return result


class DataScenarios:
    """Provides realistic test data scenarios for different workflows."""

    @staticmethod
    def survey_processing_scenario(record_count: int = 100) -> DataScenario:
        """Generate survey processing test scenario."""

        def generate_survey_data():
            """Generate realistic survey data."""
            survey_types = [
                "Customer Satisfaction",
                "Product Feedback",
                "Market Research",
                "Employee Survey",
            ]

            records = []
            for i in range(record_count):
                record = {
                    "survey_id": f"SURV-{i + 1:04d}",
                    "customer_id": f"CUST-{random.randint(1, 1000):04d}",
                    "customer_name": f"Customer {i + 1}",
                    "survey_type": random.choice(survey_types),
                    "processing_status": "pending",  # All start as pending
                    "processed_at": None,
                    "processing_duration_ms": None,
                    "flow_run_id": f"test-flow-{i + 1}",
                    "error_message": None,
                    "created_at": datetime.now()
                    - timedelta(minutes=random.randint(1, 60)),
                }
                records.append(record)

            return records

        return DataScenario(
            name="survey_processing",
            description="Survey processing workflow with realistic customer data",
            record_count=record_count,
            data_generator=generate_survey_data,
            expected_outcomes={
                "completion_rate_min": 0.85,  # At least 85% should complete
                "processing_time_max_ms": 5000,  # Max 5 seconds per record
                "duplicate_processing": 0,  # No duplicates allowed
                "data_integrity": True,  # All data should be preserved
            },
            cleanup_queries=[
                "DELETE FROM processed_surveys WHERE survey_id LIKE 'SURV-%'",
                "DELETE FROM processing_queue WHERE flow_name = 'survey_processing'",
            ],
        )

    @staticmethod
    def order_processing_scenario(record_count: int = 150) -> DataScenario:
        """Generate order processing test scenario."""

        def generate_order_data():
            """Generate realistic order data."""
            products = [
                "Premium Widget A",
                "Standard Widget B",
                "Budget Widget C",
                "Deluxe Widget D",
            ]
            priorities = ["low", "medium", "high", "urgent"]
            regions = ["North", "South", "East", "West", "Central"]

            records = []
            for i in range(record_count):
                quantity = random.randint(1, 10)
                unit_price = round(random.uniform(5.99, 99.99), 2)
                subtotal = round(quantity * unit_price, 2)
                tax_rate = 0.08
                tax_amount = round(subtotal * tax_rate, 2)
                discount_rate = random.choice([0, 0.05, 0.10, 0.15])
                discount_amount = round(subtotal * discount_rate, 2)
                total_amount = round(subtotal + tax_amount - discount_amount, 2)

                record = {
                    "order_id": f"ORD-{i + 1:04d}",
                    "customer_id": f"CUST-{random.randint(1, 500):04d}",
                    "customer_name": f"Customer {i + 1}",
                    "product": random.choice(products),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "subtotal": subtotal,
                    "tax_amount": tax_amount,
                    "discount_amount": discount_amount,
                    "total_amount": total_amount,
                    "order_date": (
                        datetime.now() - timedelta(days=random.randint(0, 30))
                    ).date(),
                    "priority": random.choice(priorities),
                    "region": random.choice(regions),
                    "fulfillment_status": "pending",  # All start as pending
                    "processed_by_flow": None,
                    "created_at": datetime.now()
                    - timedelta(minutes=random.randint(1, 120)),
                }
                records.append(record)

            return records

        return DataScenario(
            name="order_processing",
            description="Order processing workflow with realistic e-commerce data",
            record_count=record_count,
            data_generator=generate_order_data,
            expected_outcomes={
                "completion_rate_min": 0.90,  # At least 90% should complete
                "processing_time_max_ms": 3000,  # Max 3 seconds per record
                "duplicate_processing": 0,  # No duplicates allowed
                "data_integrity": True,  # All data should be preserved
                "financial_accuracy": True,  # Financial calculations must be correct
            },
            cleanup_queries=[
                "DELETE FROM customer_orders WHERE order_id LIKE 'ORD-%'",
                "DELETE FROM processing_queue WHERE flow_name = 'order_processing'",
            ],
        )

    @staticmethod
    def high_volume_scenario(record_count: int = 1000) -> DataScenario:
        """Generate high-volume processing test scenario."""

        def generate_high_volume_data():
            """Generate high-volume test data."""
            records = []
            for i in range(record_count):
                record = {
                    "payload": {
                        "id": i + 1,
                        "batch_id": f"BATCH-{(i // 100) + 1:03d}",
                        "data": f"high_volume_data_{i + 1}",
                        "size": random.randint(100, 1000),
                        "priority": random.choice(["low", "medium", "high"]),
                        "timestamp": datetime.now().isoformat(),
                    }
                }
                records.append(record)

            return records

        return DataScenario(
            name="high_volume_processing",
            description="High-volume processing test for performance validation",
            record_count=record_count,
            data_generator=generate_high_volume_data,
            expected_outcomes={
                "completion_rate_min": 0.95,  # At least 95% should complete
                "processing_time_max_ms": 2000,  # Max 2 seconds per record
                "throughput_min_per_sec": 50,  # Minimum 50 records per second
                "duplicate_processing": 0,  # No duplicates allowed
                "memory_efficiency": True,  # Memory usage should be stable
            },
            cleanup_queries=[
                "DELETE FROM processing_queue WHERE flow_name = 'high_volume_processing'"
            ],
        )

    @staticmethod
    def error_handling_scenario(record_count: int = 50) -> DataScenario:
        """Generate error handling test scenario."""

        def generate_error_prone_data():
            """Generate data designed to test error handling."""
            records = []
            for i in range(record_count):
                # Intentionally create some problematic records
                error_type = None
                if i % 10 == 0:  # 10% invalid data
                    error_type = "invalid_format"
                elif i % 15 == 0:  # Some timeout scenarios
                    error_type = "timeout_simulation"
                elif i % 20 == 0:  # Some validation errors
                    error_type = "validation_error"

                record = {
                    "payload": {
                        "id": i + 1,
                        "data": f"error_test_data_{i + 1}",
                        "error_type": error_type,
                        "should_fail": error_type is not None,
                        "retry_count": 0,
                        "timestamp": datetime.now().isoformat(),
                    }
                }
                records.append(record)

            return records

        return DataScenario(
            name="error_handling",
            description="Error handling and recovery test scenario",
            record_count=record_count,
            data_generator=generate_error_prone_data,
            expected_outcomes={
                "completion_rate_min": 0.70,  # 70% should complete (30% designed to fail)
                "error_handling_rate": 1.0,  # All errors should be handled gracefully
                "retry_mechanism": True,  # Retry mechanism should work
                "data_consistency": True,  # Failed records should not corrupt data
            },
            cleanup_queries=[
                "DELETE FROM processing_queue WHERE flow_name = 'error_handling'"
            ],
        )


class DataManager:
    """Manages test data lifecycle and database initialization."""

    def __init__(self, database_managers: dict[str, DatabaseManager]):
        """
        Initialize test data manager.

        Args:
            database_managers: Dictionary of database managers
        """
        self.database_managers = database_managers
        self.scenarios = DataScenarios()
        self.initialized_scenarios = []

    def initialize_test_scenario(self, scenario: DataScenario) -> dict[str, Any]:
        """
        Initialize a test scenario with data.

        Args:
            scenario: Test scenario to initialize

        Returns:
            Dictionary with initialization results
        """
        start_time = time.time()

        try:
            # Generate test data
            test_data = scenario.data_generator()

            # Get RPA database manager
            rpa_db = self.database_managers.get("rpa_db")
            if not rpa_db:
                raise ValueError("RPA database manager not found")

            # Initialize data based on scenario type
            if scenario.name == "survey_processing":
                self._initialize_survey_data(rpa_db, test_data)
            elif scenario.name == "order_processing":
                self._initialize_order_data(rpa_db, test_data)
            elif scenario.name in ["high_volume_processing", "error_handling"]:
                self._initialize_queue_data(rpa_db, scenario.name, test_data)
            else:
                raise ValueError(f"Unknown scenario type: {scenario.name}")

            # Track initialized scenario
            self.initialized_scenarios.append(scenario.name)

            duration = time.time() - start_time

            return {
                "scenario_name": scenario.name,
                "status": "success",
                "records_created": len(test_data),
                "duration_seconds": round(duration, 2),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            duration = time.time() - start_time
            return {
                "scenario_name": scenario.name,
                "status": "failed",
                "error": str(e),
                "duration_seconds": round(duration, 2),
                "timestamp": datetime.now().isoformat(),
            }

    def _initialize_survey_data(
        self, rpa_db: DatabaseManager, test_data: list[dict]
    ) -> None:
        """Initialize survey processing test data."""
        # Insert survey records
        for record in test_data:
            query = """
            INSERT INTO processed_surveys (
                survey_id, customer_id, customer_name, survey_type,
                processing_status, processed_at, processing_duration_ms,
                flow_run_id, error_message, created_at, updated_at
            ) VALUES (
                :survey_id, :customer_id, :customer_name, :survey_type,
                :processing_status, :processed_at, :processing_duration_ms,
                :flow_run_id, :error_message, :created_at, :created_at
            )
            """
            rpa_db.execute_query(query, record)

    def _initialize_order_data(
        self, rpa_db: DatabaseManager, test_data: list[dict]
    ) -> None:
        """Initialize order processing test data."""
        # Insert order records
        for record in test_data:
            query = """
            INSERT INTO customer_orders (
                order_id, customer_id, customer_name, product, quantity,
                unit_price, subtotal, tax_amount, discount_amount, total_amount,
                order_date, priority, region, fulfillment_status, processed_by_flow,
                created_at, updated_at
            ) VALUES (
                :order_id, :customer_id, :customer_name, :product, :quantity,
                :unit_price, :subtotal, :tax_amount, :discount_amount, :total_amount,
                :order_date, :priority, :region, :fulfillment_status, :processed_by_flow,
                :created_at, :created_at
            )
            """
            rpa_db.execute_query(query, record)

    def _initialize_queue_data(
        self, rpa_db: DatabaseManager, flow_name: str, test_data: list[dict]
    ) -> None:
        """Initialize processing queue test data."""
        # Insert records into processing queue
        for record in test_data:
            query = """
            INSERT INTO processing_queue (
                flow_name, payload, status, retry_count, created_at
            ) VALUES (
                :flow_name, :payload, 'pending', 0, NOW()
            )
            """
            params = {"flow_name": flow_name, "payload": json.dumps(record["payload"])}
            rpa_db.execute_query(query, params)

    def cleanup_test_data(
        self, scenario_names: Optional[list[str]] = None
    ) -> dict[str, Any]:
        """
        Clean up test data for specified scenarios.

        Args:
            scenario_names: List of scenario names to clean up. If None, clean all.

        Returns:
            Dictionary with cleanup results
        """
        start_time = time.time()
        cleanup_results = {}

        try:
            rpa_db = self.database_managers.get("rpa_db")
            if not rpa_db:
                raise ValueError("RPA database manager not found")

            # Determine scenarios to clean
            scenarios_to_clean = scenario_names or self.initialized_scenarios

            # Get all available scenarios
            all_scenarios = [
                self.scenarios.survey_processing_scenario(),
                self.scenarios.order_processing_scenario(),
                self.scenarios.high_volume_scenario(),
                self.scenarios.error_handling_scenario(),
            ]

            for scenario in all_scenarios:
                if scenario.name in scenarios_to_clean:
                    scenario_start = time.time()

                    try:
                        # Execute cleanup queries
                        for query in scenario.cleanup_queries:
                            rpa_db.execute_query(query)

                        # Remove from initialized scenarios
                        if scenario.name in self.initialized_scenarios:
                            self.initialized_scenarios.remove(scenario.name)

                        cleanup_results[scenario.name] = {
                            "status": "success",
                            "duration_seconds": round(time.time() - scenario_start, 2),
                        }

                    except Exception as e:
                        cleanup_results[scenario.name] = {
                            "status": "failed",
                            "error": str(e),
                            "duration_seconds": round(time.time() - scenario_start, 2),
                        }

            total_duration = time.time() - start_time

            return {
                "cleanup_summary": {
                    "total_scenarios": len(cleanup_results),
                    "successful_cleanups": len(
                        [
                            r
                            for r in cleanup_results.values()
                            if r["status"] == "success"
                        ]
                    ),
                    "failed_cleanups": len(
                        [r for r in cleanup_results.values() if r["status"] == "failed"]
                    ),
                    "total_duration_seconds": round(total_duration, 2),
                    "timestamp": datetime.now().isoformat(),
                },
                "scenario_results": cleanup_results,
            }

        except Exception as e:
            return {
                "cleanup_summary": {
                    "status": "failed",
                    "error": str(e),
                    "duration_seconds": round(time.time() - start_time, 2),
                    "timestamp": datetime.now().isoformat(),
                },
                "scenario_results": cleanup_results,
            }

    def reset_test_environment(self) -> dict[str, Any]:
        """
        Reset the entire test environment to a clean state.

        Returns:
            Dictionary with reset results
        """
        start_time = time.time()

        try:
            # Clean up all test data
            cleanup_result = self.cleanup_test_data()

            # Reset processing queue
            rpa_db = self.database_managers.get("rpa_db")
            if rpa_db:
                # Reset any orphaned records
                reset_queries = [
                    "UPDATE processing_queue SET status = 'pending', claimed_at = NULL, claimed_by = NULL WHERE status = 'processing'",
                    "DELETE FROM processing_queue WHERE flow_name LIKE '%test%'",
                    "DELETE FROM flow_execution_logs WHERE flow_name LIKE '%test%'",
                ]

                for query in reset_queries:
                    try:
                        rpa_db.execute_query(query)
                    except Exception as e:
                        # Log but don't fail on individual query errors
                        print(f"Warning: Reset query failed: {e}")

            duration = time.time() - start_time

            return {
                "reset_status": "success",
                "cleanup_result": cleanup_result,
                "duration_seconds": round(duration, 2),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "reset_status": "failed",
                "error": str(e),
                "duration_seconds": round(time.time() - start_time, 2),
                "timestamp": datetime.now().isoformat(),
            }

    def get_test_data_status(self) -> dict[str, Any]:
        """
        Get current test data status across all scenarios.

        Returns:
            Dictionary with test data status information
        """
        try:
            rpa_db = self.database_managers.get("rpa_db")
            if not rpa_db:
                return {"error": "RPA database manager not found"}

            # Check various test data tables
            status = {
                "initialized_scenarios": self.initialized_scenarios,
                "timestamp": datetime.now().isoformat(),
            }

            # Check processed_surveys
            try:
                survey_count = rpa_db.execute_query(
                    "SELECT COUNT(*) as count FROM processed_surveys WHERE survey_id LIKE 'SURV-%'"
                )
                status["survey_test_records"] = (
                    survey_count[0]["count"] if survey_count else 0
                )
            except Exception:
                status["survey_test_records"] = "unknown"

            # Check customer_orders
            try:
                order_count = rpa_db.execute_query(
                    "SELECT COUNT(*) as count FROM customer_orders WHERE order_id LIKE 'ORD-%'"
                )
                status["order_test_records"] = (
                    order_count[0]["count"] if order_count else 0
                )
            except Exception:
                status["order_test_records"] = "unknown"

            # Check processing_queue
            try:
                queue_status = rpa_db.execute_query(
                    "SELECT flow_name, status, COUNT(*) as count FROM processing_queue GROUP BY flow_name, status"
                )
                status["queue_status"] = (
                    {
                        f"{row['flow_name']}_{row['status']}": row["count"]
                        for row in queue_status
                    }
                    if queue_status
                    else {}
                )
            except Exception:
                status["queue_status"] = "unknown"

            return status

        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
