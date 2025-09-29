#!/usr/bin/env python3
"""
Multi-Database Processing Example

This example demonstrates how to use the DistributedProcessor's multi-database
processing functionality to read from one database (SurveyHub) and write to
another (rpa_db).

This implements the pattern described in requirements 3.2, 3.3, and 3.4:
- 3.2: Use DatabaseManager("SurveyHub") for SQL Server queries
- 3.3: Use DatabaseManager("rpa_db") for PostgreSQL operations
- 3.4: Use appropriate DatabaseManager instance for target database

Usage:
    python core/examples/multi_database_processing_example.py
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core.database import DatabaseManager
from core.distributed import DistributedProcessor


def create_sample_survey_data():
    """Create sample survey data for demonstration."""
    return [
        {
            "survey_id": "SURV-DEMO-001",
            "customer_name": "Alice Johnson",
            "flow_run_id": "demo-flow-001",
        },
        {
            "survey_id": "SURV-DEMO-002",
            "customer_name": "Bob Smith",
            "flow_run_id": "demo-flow-002",
        },
        {
            "survey_id": "SURV-DEMO-003",
            "customer_name": "Charlie Brown",
            "flow_run_id": "demo-flow-003",
        },
    ]


def demonstrate_multi_database_processing():
    """
    Demonstrate multi-database processing pattern.

    Note: This example uses mock data since we don't have actual
    SurveyHub database connections in the test environment.
    """
    print("=== Multi-Database Processing Example ===\n")

    try:
        # Initialize DatabaseManager instances
        # In a real environment, these would connect to actual databases
        print("1. Initializing DatabaseManager instances...")

        # rpa_db for PostgreSQL operations (queue and results)
        rpa_db_manager = DatabaseManager("rpa_db")
        print(f"   - rpa_db: {rpa_db_manager.database_name}")

        # SurveyHub for SQL Server operations (source data)
        # Note: In test environment, this may not have actual connection
        try:
            source_db_manager = DatabaseManager("SurveyHub")
            print(f"   - SurveyHub: {source_db_manager.database_name}")
        except Exception as e:
            print(f"   - SurveyHub: Not available in test environment ({e})")
            print("   - Using mock source database for demonstration")
            source_db_manager = None

        # Initialize DistributedProcessor with both databases
        print("\n2. Creating DistributedProcessor...")
        processor = DistributedProcessor(
            rpa_db_manager=rpa_db_manager, source_db_manager=source_db_manager
        )
        print(f"   - Instance ID: {processor.instance_id}")
        print(f"   - RPA DB: {processor.rpa_db.database_name}")
        print(
            f"   - Source DB: {processor.source_db.database_name if processor.source_db else 'None'}"
        )

        # Demonstrate health check
        print("\n3. Performing health check...")
        health_status = processor.health_check()
        print(f"   - Overall Status: {health_status['status']}")
        print(f"   - RPA DB Status: {health_status['databases']['rpa_db']['status']}")
        if "source_db" in health_status["databases"]:
            print(
                f"   - Source DB Status: {health_status['databases']['source_db']['status']}"
            )

        # Demonstrate multi-database processing (if source DB available)
        if processor.source_db:
            print("\n4. Demonstrating multi-database processing...")
            sample_surveys = create_sample_survey_data()

            for survey_payload in sample_surveys:
                try:
                    print(f"\n   Processing survey: {survey_payload['survey_id']}")

                    # This would normally:
                    # 1. Read from SurveyHub (SQL Server)
                    # 2. Transform the data
                    # 3. Write to rpa_db (PostgreSQL)
                    result = processor.process_survey_logic(survey_payload)

                    print(f"   - Customer: {result['customer_name']}")
                    print(
                        f"   - Satisfaction Score: {result.get('satisfaction_score', 'N/A')}"
                    )
                    print(f"   - Status: {result['processing_status']}")
                    print(f"   - Duration: {result['processing_duration_ms']}ms")

                except Exception as e:
                    print(f"   - Error processing {survey_payload['survey_id']}: {e}")
        else:
            print("\n4. Multi-database processing not available (no source database)")
            print("   In a real environment with SurveyHub connection:")
            print("   - Would read survey data from SQL Server")
            print("   - Would transform and calculate satisfaction scores")
            print("   - Would store results in PostgreSQL")

        # Demonstrate queue management
        print("\n5. Demonstrating queue management...")
        queue_status = processor.get_queue_status()
        print(f"   - Total records in queue: {queue_status['total_records']}")
        print(f"   - Pending: {queue_status['pending_records']}")
        print(f"   - Processing: {queue_status['processing_records']}")
        print(f"   - Completed: {queue_status['completed_records']}")
        print(f"   - Failed: {queue_status['failed_records']}")

        print("\n=== Example completed successfully! ===")

    except Exception as e:
        print(f"\nError during demonstration: {e}")
        print("This is expected in test environments without full database setup.")
        return False

    return True


def demonstrate_business_logic():
    """Demonstrate the business logic components separately."""
    print("\n=== Business Logic Demonstration ===\n")

    # Create a processor for demonstration (without actual DB connections)
    from unittest.mock import Mock

    from core.database import DatabaseManager

    mock_rpa_db = Mock(spec=DatabaseManager)
    mock_rpa_db.database_name = "mock_rpa_db"
    mock_rpa_db.logger = Mock()

    mock_source_db = Mock(spec=DatabaseManager)
    mock_source_db.database_name = "mock_surveyhub"

    processor = DistributedProcessor(
        rpa_db_manager=mock_rpa_db, source_db_manager=mock_source_db
    )

    # Demonstrate satisfaction score calculation
    print("1. Satisfaction Score Calculation Examples:")

    test_cases = [
        {
            "survey_type": "Customer Satisfaction",
            "response_data": {"overall_satisfaction": 8.5},
            "description": "Customer Satisfaction with overall rating",
        },
        {
            "survey_type": "Product Feedback",
            "response_data": {"product_rating": 7.0, "recommendation_likelihood": 9.0},
            "description": "Product Feedback with weighted scoring",
        },
        {
            "survey_type": "Market Research",
            "response_data": {"interest_level": 6.5},
            "description": "Market Research with interest level",
        },
        {
            "survey_type": "Unknown Type",
            "response_data": {"rating1": 8.0, "rating2": 7.0, "rating3": 9.0},
            "description": "Unknown survey type with multiple ratings",
        },
    ]

    for case in test_cases:
        score = processor._calculate_satisfaction_score(
            case["response_data"], case["survey_type"]
        )
        print(f"   - {case['description']}: {score}")

    # Demonstrate data transformation
    print("\n2. Data Transformation Example:")

    sample_survey_data = {
        "survey_id": "SURV-TRANSFORM-001",
        "customer_id": "CUST-001",
        "response_data": {"overall_satisfaction": 8.7, "service_rating": 9.0},
        "survey_type": "Customer Satisfaction",
    }

    sample_payload = {
        "customer_name": "Demo Customer",
        "flow_run_id": "demo-transform-001",
    }

    transformed = processor._transform_survey_data(sample_survey_data, sample_payload)

    print(f"   - Survey ID: {transformed['survey_id']}")
    print(f"   - Customer: {transformed['customer_name']}")
    print(f"   - Satisfaction Score: {transformed['satisfaction_score']}")
    print(f"   - Processing Status: {transformed['processing_status']}")
    print(f"   - Flow Run ID: {transformed['flow_run_id']}")

    print("\n=== Business Logic demonstration completed! ===")


if __name__ == "__main__":
    print("Multi-Database Processing Example")
    print("=" * 50)

    # Run the main demonstration
    success = demonstrate_multi_database_processing()

    # Always run the business logic demonstration
    demonstrate_business_logic()

    if success:
        print("\n✅ Example completed successfully!")
        print("\nKey Features Demonstrated:")
        print("- Multi-database initialization (rpa_db + SurveyHub)")
        print("- Health monitoring across multiple databases")
        print("- Survey data processing with business logic")
        print("- Satisfaction score calculation algorithms")
        print("- Queue management and status reporting")
        print("- Error handling for missing data and database failures")
    else:
        print("\n⚠️  Example completed with limitations due to test environment")
        print("In a production environment with full database connections:")
        print("- Would demonstrate actual cross-database operations")
        print("- Would show real survey data processing workflows")
        print("- Would include performance metrics and monitoring")
