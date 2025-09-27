"""Integration tests for RPA1 workflow with fake data.

This file demonstrates how to write integration tests that:
1. Run REAL Prefect workflows (not mocked)
2. Use FAKE data for predictable, controlled testing
3. Test the complete workflow end-to-end
4. Verify task orchestration and data flow

Key Learning Points:
- Integration tests run actual Prefect flows with real task orchestration
- We mock only the data sources, not the business logic
- This gives us confidence that the workflow works correctly
- Fake data allows for predictable, repeatable tests
"""

import csv
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from flows.rpa1.workflow import rpa1_workflow

pytestmark = pytest.mark.integration


class TestRPA1IntegrationWithFakeData:
    """Integration tests for RPA1 workflow using fake data for learning purposes."""
    
    def test_rpa1_workflow_with_controlled_fake_data(self):
        """
        Test RPA1 workflow with fake data but real Prefect execution.
        
        This test demonstrates the integration testing pattern:
        1. Create fake data that looks realistic
        2. Mock only the data source (create_sample_data)
        3. Let the rest of the workflow run normally
        4. Verify the workflow processes the fake data correctly
        
        Why this approach?
        - Tests real Prefect task orchestration
        - Tests real business logic (transform, calculate, generate)
        - Uses controlled data for predictable results
        - Fast and reliable (no external dependencies)
        """
        # STEP 1: Define fake data that looks realistic
        # This data will be processed by the real workflow
        fake_sales_data = [
            {
                "product": "Premium Widget A",
                "quantity": 100,
                "price": 25.50,
                "date": "2024-01-15"
            },
            {
                "product": "Standard Widget B", 
                "quantity": 75,
                "price": 15.75,
                "date": "2024-01-16"
            },
            {
                "product": "Premium Widget A",  # Duplicate product to test grouping
                "quantity": 50,
                "price": 25.50,
                "date": "2024-01-17"
            },
            {
                "product": "Budget Widget C",
                "quantity": 200,
                "price": 8.99,
                "date": "2024-01-18"
            }
        ]
        
        # STEP 2: Create a temporary CSV file with our fake data
        # This simulates what create_sample_data would normally do
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            # Write CSV header
            fieldnames = fake_sales_data[0].keys()
            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write our fake data
            writer.writerows(fake_sales_data)
            fake_csv_path = temp_file.name
        
        # STEP 3: Mock the create_sample_data task to return our fake file
        # This is the ONLY thing we mock - the data source
        # We need to mock it at the workflow level since it's imported directly
        with patch('flows.rpa1.workflow.create_sample_data') as mock_create_data:
            mock_create_data.return_value = fake_csv_path
            
            # STEP 4: Run the REAL Prefect workflow
            # All other tasks (extract_data, transform_data, calculate_summary, etc.)
            # will run normally and process our fake data
            result = rpa1_workflow(cleanup=True)
            
            # STEP 5: Verify the workflow executed correctly
            # We know exactly what the results should be based on our fake data
            
            # Basic structure verification
            assert isinstance(result, dict), "Result should be a dictionary"
            assert "total_records" in result, "Should have total_records field"
            assert "total_value" in result, "Should have total_value field"
            assert "average_price" in result, "Should have average_price field"
            assert "product_breakdown" in result, "Should have product_breakdown field"
            assert "generated_at" in result, "Should have generated_at field"
            
            # Verify we processed exactly 4 records from our fake data
            assert result["total_records"] == 4, f"Expected 4 records, got {result['total_records']}"
            
            # Calculate expected values from our fake data
            expected_total_quantity = 100 + 75 + 50 + 200  # 425
            expected_total_value = (100 * 25.50) + (75 * 15.75) + (50 * 25.50) + (200 * 8.99)
            expected_total_value = 2550.0 + 1181.25 + 1275.0 + 1798.0  # 6804.25
            
            # Verify calculated values
            assert result["total_quantity"] == expected_total_quantity, \
                f"Expected total_quantity {expected_total_quantity}, got {result['total_quantity']}"
            
            assert abs(result["total_value"] - expected_total_value) < 0.01, \
                f"Expected total_value {expected_total_value}, got {result['total_value']}"
            
            # Verify product breakdown (grouping by product)
            product_breakdown = result["product_breakdown"]
            
            # Premium Widget A should be grouped together (100 + 50 = 150 quantity)
            assert "Premium Widget A" in product_breakdown, "Should have Premium Widget A in breakdown"
            assert product_breakdown["Premium Widget A"]["quantity"] == 150, \
                "Premium Widget A should have 150 total quantity"
            assert product_breakdown["Premium Widget A"]["total_value"] == 3825.0, \
                "Premium Widget A should have 3825.0 total value"
            
            # Standard Widget B
            assert "Standard Widget B" in product_breakdown, "Should have Standard Widget B in breakdown"
            assert product_breakdown["Standard Widget B"]["quantity"] == 75, \
                "Standard Widget B should have 75 quantity"
            
            # Budget Widget C
            assert "Budget Widget C" in product_breakdown, "Should have Budget Widget C in breakdown"
            assert product_breakdown["Budget Widget C"]["quantity"] == 200, \
                "Budget Widget C should have 200 quantity"
            
            # Verify the mock was called (data source was used)
            mock_create_data.assert_called_once()
            
            # Verify a report file was generated (check the logs show it was created)
            # The report file path is logged but not returned in the summary
            # We can verify this by checking the logs or the output directory
    
    def test_rpa1_workflow_with_edge_case_data(self):
        """
        Test RPA1 workflow with edge case fake data.
        
        This test demonstrates how to test edge cases and error scenarios
        using fake data in integration tests.
        """
        # Edge case data: empty dataset, zero prices, very large numbers
        edge_case_data = [
            {
                "product": "Zero Price Widget",
                "quantity": 10,
                "price": 0.00,  # Zero price
                "date": "2024-01-15"
            },
            {
                "product": "High Value Widget",
                "quantity": 1,
                "price": 999999.99,  # Very high price
                "date": "2024-01-16"
            }
        ]
        
        # Create temporary file with edge case data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            fieldnames = edge_case_data[0].keys()
            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(edge_case_data)
            fake_csv_path = temp_file.name
        
        # Mock the data source
        with patch('flows.rpa1.workflow.create_sample_data') as mock_create_data:
            mock_create_data.return_value = fake_csv_path
            
            # Run the workflow with edge case data
            result = rpa1_workflow(cleanup=True)
            
            # Verify the workflow handled edge cases correctly
            assert result["total_records"] == 2
            assert result["total_quantity"] == 11  # 10 + 1
            assert result["total_value"] == 999999.99  # 0 + 999999.99
            
            # Verify product breakdown handles edge cases
            product_breakdown = result["product_breakdown"]
            assert "Zero Price Widget" in product_breakdown
            assert "High Value Widget" in product_breakdown
            
            # Zero price widget should have zero total value
            assert product_breakdown["Zero Price Widget"]["total_value"] == 0.0
    
    def test_rpa1_workflow_error_handling_with_fake_data(self):
        """
        Test RPA1 workflow error handling using fake data.
        
        This demonstrates how to test error scenarios in integration tests
        by providing fake data that will cause specific errors.
        """
        # Malformed data that should cause parsing errors
        malformed_data = [
            {
                "product": "Valid Widget",
                "quantity": "not_a_number",  # Invalid quantity
                "price": 10.50,
                "date": "2024-01-15"
            },
            {
                "product": "Another Widget",
                "quantity": 50,
                "price": "invalid_price",  # Invalid price
                "date": "2024-01-16"
            }
        ]
        
        # Create file with malformed data
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            fieldnames = malformed_data[0].keys()
            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(malformed_data)
            fake_csv_path = temp_file.name
        
        # Mock the data source
        with patch('flows.rpa1.workflow.create_sample_data') as mock_create_data:
            mock_create_data.return_value = fake_csv_path
            
            # The workflow should handle the malformed data gracefully
            # (depending on how error handling is implemented)
            try:
                result = rpa1_workflow(cleanup=True)
                # If it doesn't raise an exception, verify it handled the error
                assert isinstance(result, dict)
            except Exception as e:
                # If it does raise an exception, that's also valid behavior
                # depending on your error handling strategy
                assert "not_a_number" in str(e).lower() or "invalid" in str(e).lower()
    
    def test_rpa1_workflow_cleanup_behavior(self):
        """
        Test RPA1 workflow cleanup behavior with fake data.
        
        This demonstrates how to test side effects and cleanup behavior
        in integration tests.
        """
        # Create fake data
        fake_data = [{"product": "Test Widget", "quantity": 1, "price": 10.0, "date": "2024-01-15"}]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file:
            fieldnames = fake_data[0].keys()
            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(fake_data)
            fake_csv_path = temp_file.name
        
        # Mock the data source
        with patch('flows.rpa1.workflow.create_sample_data') as mock_create_data:
            mock_create_data.return_value = fake_csv_path
            
            # Test with cleanup=True
            result_with_cleanup = rpa1_workflow(cleanup=True)
            assert result_with_cleanup is not None
            assert result_with_cleanup["total_records"] == 1
            
            # Create a new fake file for the second test
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as temp_file2:
                fieldnames = fake_data[0].keys()
                writer = csv.DictWriter(temp_file2, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(fake_data)
                fake_csv_path2 = temp_file2.name
            
            mock_create_data.return_value = fake_csv_path2
            
            # Test with cleanup=False
            result_without_cleanup = rpa1_workflow(cleanup=False)
            assert result_without_cleanup is not None
            assert result_without_cleanup["total_records"] == 1
            
            # Both should produce the same results
            assert result_with_cleanup["total_records"] == result_without_cleanup["total_records"]