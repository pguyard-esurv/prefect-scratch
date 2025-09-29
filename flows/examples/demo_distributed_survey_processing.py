#!/usr/bin/env python3
"""
Demonstration script for distributed survey processing functionality.

This script demonstrates the key components of the distributed survey processing
system without requiring database connections. It shows:

1. Survey record preparation
2. Business logic processing
3. Data validation and transformation
4. Error handling patterns

Run this script to see the distributed processing functionality in action.
"""

from unittest.mock import MagicMock

# Import the functions we want to demonstrate
from flows.examples.distributed_survey_processing import (
    prepare_survey_records_for_queue,
    process_survey_business_logic,
)


def mock_logger():
    """Create a mock logger for demonstration."""
    logger = MagicMock()
    logger.info = lambda msg: print(f"INFO: {msg}")
    logger.warning = lambda msg: print(f"WARNING: {msg}")
    logger.error = lambda msg: print(f"ERROR: {msg}")
    logger.debug = lambda msg: print(f"DEBUG: {msg}")
    return logger


def demo_survey_record_preparation():
    """Demonstrate survey record preparation functionality."""
    print("\n" + "=" * 60)
    print("DEMO: Survey Record Preparation")
    print("=" * 60)

    # Mock the Prefect logger
    import flows.examples.distributed_survey_processing as dsp

    original_get_run_logger = dsp.get_run_logger
    dsp.get_run_logger = mock_logger

    try:
        # Prepare sample survey records
        print("\n1. Preparing 5 sample survey records...")
        records = prepare_survey_records_for_queue(survey_count=5)

        print(f"\nGenerated {len(records)} survey records:")
        for i, record in enumerate(records, 1):
            payload = record["payload"]
            print(f"\nRecord {i}:")
            print(f"  Survey ID: {payload['survey_id']}")
            print(f"  Customer: {payload['customer_name']} ({payload['customer_id']})")
            print(f"  Type: {payload['survey_type']}")
            print(f"  Priority: {payload['priority']}")
            print(
                f"  Satisfaction: {payload['response_data']['overall_satisfaction']}/10"
            )
            print(
                f"  NPS Score: {payload['response_data']['likelihood_to_recommend']}/10"
            )

        # Test custom priority distribution
        print("\n2. Testing custom priority distribution (80% high priority)...")
        priority_dist = {"high": 0.8, "normal": 0.15, "low": 0.05}
        high_priority_records = prepare_survey_records_for_queue(
            survey_count=10, priority_distribution=priority_dist
        )

        priorities = [r["payload"]["priority"] for r in high_priority_records]
        priority_counts = {p: priorities.count(p) for p in ["high", "normal", "low"]}
        print(f"Priority distribution: {priority_counts}")

    finally:
        # Restore original logger
        dsp.get_run_logger = original_get_run_logger


def demo_business_logic_processing():
    """Demonstrate survey business logic processing."""
    print("\n" + "=" * 60)
    print("DEMO: Business Logic Processing")
    print("=" * 60)

    # Mock the dependencies
    import flows.examples.distributed_survey_processing as dsp

    original_get_run_logger = dsp.get_run_logger
    original_rpa_db = dsp.rpa_db_manager
    original_source_db = dsp.source_db_manager

    dsp.get_run_logger = mock_logger
    dsp.rpa_db_manager = MagicMock()
    dsp.source_db_manager = None  # Simulate no source database

    try:
        # Test cases with different satisfaction levels
        test_cases = [
            {
                "name": "High Satisfaction Customer",
                "payload": {
                    "survey_id": "DEMO-001",
                    "customer_id": "CUST-001",
                    "customer_name": "Alice Johnson",
                    "survey_type": "Customer Satisfaction",
                    "customer_segment": "premium",
                    "response_data": {
                        "overall_satisfaction": 9,
                        "likelihood_to_recommend": 10,
                        "service_rating": 5,
                        "product_rating": 5,
                        "comments": "Excellent service and product quality!",
                    },
                },
            },
            {
                "name": "Medium Satisfaction Customer",
                "payload": {
                    "survey_id": "DEMO-002",
                    "customer_id": "CUST-002",
                    "customer_name": "Bob Smith",
                    "survey_type": "Product Feedback",
                    "customer_segment": "standard",
                    "response_data": {
                        "overall_satisfaction": 7,
                        "likelihood_to_recommend": 6,
                        "service_rating": 3,
                        "product_rating": 4,
                        "comments": "Good product, but service could be better.",
                    },
                },
            },
            {
                "name": "Low Satisfaction Customer",
                "payload": {
                    "survey_id": "DEMO-003",
                    "customer_id": "CUST-003",
                    "customer_name": "Charlie Brown",
                    "survey_type": "Service Quality",
                    "customer_segment": "enterprise",
                    "response_data": {
                        "overall_satisfaction": 3,
                        "likelihood_to_recommend": 2,
                        "service_rating": 2,
                        "product_rating": 1,
                        "comments": "Very disappointed with both service and product.",
                    },
                },
            },
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. Processing: {test_case['name']}")
            print("-" * 40)

            try:
                result = process_survey_business_logic(test_case["payload"])

                # Display key results
                metrics = result["satisfaction_metrics"]
                print(f"Survey ID: {result['survey_id']}")
                print(f"Customer: {result['customer_name']}")
                print(f"Processing Status: {result['processing_status']}")
                print(f"Composite Score: {metrics['composite_score']:.2f}/10")
                print(f"Weighted Score: {metrics['weighted_score']:.2f}/10")
                print(f"Satisfaction Level: {metrics['satisfaction_level'].upper()}")
                print(f"NPS Category: {metrics['nps_category'].upper()}")

                # Show the scoring breakdown
                print("\nScoring Breakdown:")
                print(f"  Overall Satisfaction: {metrics['overall_satisfaction']}/10")
                print(
                    f"  Likelihood to Recommend: {metrics['likelihood_to_recommend']}/10"
                )
                print(f"  Service Rating: {metrics['service_rating']}/5")
                print(f"  Product Rating: {metrics['product_rating']}/5")

            except Exception as e:
                print(f"Processing failed: {e}")

    finally:
        # Restore original dependencies
        dsp.get_run_logger = original_get_run_logger
        dsp.rpa_db_manager = original_rpa_db
        dsp.source_db_manager = original_source_db


def demo_error_handling():
    """Demonstrate error handling in business logic."""
    print("\n" + "=" * 60)
    print("DEMO: Error Handling")
    print("=" * 60)

    # Mock the dependencies
    import flows.examples.distributed_survey_processing as dsp

    original_get_run_logger = dsp.get_run_logger
    original_rpa_db = dsp.rpa_db_manager

    dsp.get_run_logger = mock_logger
    dsp.rpa_db_manager = MagicMock()

    try:
        # Test validation errors
        error_test_cases = [
            {
                "name": "Missing Required Fields",
                "payload": {
                    "survey_id": "ERROR-001",
                    # Missing customer_id, survey_type, response_data
                },
                "expected_error": "Missing required fields",
            },
            {
                "name": "Invalid Response Data Type",
                "payload": {
                    "survey_id": "ERROR-002",
                    "customer_id": "CUST-ERROR-002",
                    "survey_type": "Error Test",
                    "response_data": "not_a_dict",  # Should be dict
                },
                "expected_error": "response_data must be a dictionary",
            },
            {
                "name": "Missing Response Fields",
                "payload": {
                    "survey_id": "ERROR-003",
                    "customer_id": "CUST-ERROR-003",
                    "survey_type": "Error Test",
                    "response_data": {
                        "overall_satisfaction": 8
                        # Missing likelihood_to_recommend
                    },
                },
                "expected_error": "Missing required response fields",
            },
        ]

        for i, test_case in enumerate(error_test_cases, 1):
            print(f"\n{i}. Testing: {test_case['name']}")
            print("-" * 40)

            try:
                result = process_survey_business_logic(test_case["payload"])
                print(f"Unexpected success: {result}")
            except Exception as e:
                print(f"Expected error caught: {type(e).__name__}: {e}")
                if test_case["expected_error"] in str(e):
                    print("✓ Error message matches expected pattern")
                else:
                    print("✗ Error message doesn't match expected pattern")

        # Test database storage error handling
        print("\n4. Testing Database Storage Error")
        print("-" * 40)

        # Mock database to raise an exception
        dsp.rpa_db_manager.execute_query.side_effect = Exception(
            "Database connection failed"
        )

        test_payload = {
            "survey_id": "ERROR-004",
            "customer_id": "CUST-ERROR-004",
            "customer_name": "DB Error Test",
            "survey_type": "Error Test",
            "response_data": {"overall_satisfaction": 7, "likelihood_to_recommend": 8},
        }

        try:
            result = process_survey_business_logic(test_payload)
            print(f"Processing Status: {result['processing_status']}")
            if "storage_error" in result:
                print(f"Storage Error Captured: {result['storage_error']}")
                print("✓ Database error handled gracefully")
            else:
                print("✗ Database error not captured properly")
        except Exception as e:
            print(f"Unexpected exception: {e}")

    finally:
        # Restore original dependencies
        dsp.get_run_logger = original_get_run_logger
        dsp.rpa_db_manager = original_rpa_db


def demo_nps_scoring():
    """Demonstrate NPS (Net Promoter Score) category calculation."""
    print("\n" + "=" * 60)
    print("DEMO: NPS Category Calculation")
    print("=" * 60)

    # Mock the dependencies
    import flows.examples.distributed_survey_processing as dsp

    original_get_run_logger = dsp.get_run_logger
    original_rpa_db = dsp.rpa_db_manager

    dsp.get_run_logger = mock_logger
    dsp.rpa_db_manager = MagicMock()

    try:
        nps_test_cases = [
            {
                "score": 10,
                "expected": "promoter",
                "description": "Extremely likely to recommend",
            },
            {
                "score": 9,
                "expected": "promoter",
                "description": "Very likely to recommend",
            },
            {
                "score": 8,
                "expected": "passive",
                "description": "Somewhat likely to recommend",
            },
            {"score": 7, "expected": "passive", "description": "Neutral"},
            {
                "score": 6,
                "expected": "detractor",
                "description": "Unlikely to recommend",
            },
            {
                "score": 5,
                "expected": "detractor",
                "description": "Very unlikely to recommend",
            },
            {
                "score": 1,
                "expected": "detractor",
                "description": "Extremely unlikely to recommend",
            },
        ]

        print("\nNPS Category Mapping:")
        print(
            "Promoters (9-10): Loyal enthusiasts who will keep buying and refer others"
        )
        print("Passives (7-8): Satisfied but unenthusiastic customers")
        print("Detractors (0-6): Unhappy customers who can damage your brand")

        for test_case in nps_test_cases:
            payload = {
                "survey_id": f"NPS-{test_case['score']:02d}",
                "customer_id": f"CUST-NPS-{test_case['score']:02d}",
                "customer_name": f"NPS Test Customer {test_case['score']}",
                "survey_type": "NPS Test",
                "response_data": {
                    "overall_satisfaction": 8,  # Keep constant
                    "likelihood_to_recommend": test_case["score"],
                    "service_rating": 4,
                    "product_rating": 4,
                },
            }

            result = process_survey_business_logic(payload)
            metrics = result["satisfaction_metrics"]

            print(
                f"\nNPS Score {test_case['score']}/10: {test_case['expected'].upper()}"
            )
            print(f"  Description: {test_case['description']}")
            print(f"  Calculated Category: {metrics['nps_category']}")

            if metrics["nps_category"] == test_case["expected"]:
                print("  ✓ Correct NPS category")
            else:
                print("  ✗ Incorrect NPS category")

    finally:
        # Restore original dependencies
        dsp.get_run_logger = original_get_run_logger
        dsp.rpa_db_manager = original_rpa_db


def main():
    """Run all demonstrations."""
    print("DISTRIBUTED SURVEY PROCESSING DEMONSTRATION")
    print("=" * 60)
    print("This demonstration shows the key functionality of the distributed")
    print("survey processing system without requiring database connections.")

    try:
        demo_survey_record_preparation()
        demo_business_logic_processing()
        demo_nps_scoring()
        demo_error_handling()

        print("\n" + "=" * 60)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("\nKey Features Demonstrated:")
        print("✓ Survey record preparation with configurable priority distribution")
        print("✓ Comprehensive business logic with satisfaction scoring")
        print("✓ NPS (Net Promoter Score) category calculation")
        print("✓ Composite satisfaction scoring with customer segment weighting")
        print("✓ Robust error handling and validation")
        print("✓ Database storage error recovery")
        print("\nThe distributed processing system is ready for deployment!")
        print("When databases are available, the system will:")
        print("- Store records in the processing_queue table")
        print("- Use atomic record claiming to prevent duplicates")
        print("- Process records across multiple container instances")
        print("- Store results in the processed_surveys table")

    except Exception as e:
        print(f"\nDemonstration failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
