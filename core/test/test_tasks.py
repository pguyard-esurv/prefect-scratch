"""Unit tests for Prefect task functions.

These tests use Prefect's recommended testing approach with prefect_test_harness
and disable_run_logger for proper test isolation and cleaner test code.
"""

import json
import tempfile
from pathlib import Path

import pytest
from prefect.logging import disable_run_logger

pytestmark = pytest.mark.unit

from core.tasks import (
    calculate_summary,
    create_directory,
    extract_data,
    generate_report,
    transform_data,
    validate_file_exists,
)


def test_extract_data():
    """Test extract_data task with real CSV data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("product,quantity,price,date\n")
        f.write("Widget A,100,10.50,2024-01-15\n")
        f.write("Widget B,75,15.75,2024-01-16\n")
        f.close()
        
        # Use Prefect's recommended approach for testing tasks
        with disable_run_logger():
            result = extract_data.fn(f.name)
            
            assert len(result) == 2
            assert result[0]["product"] == "Widget A"
            assert result[0]["quantity"] == 100
            assert result[0]["price"] == 10.50
            assert result[1]["product"] == "Widget B"
            assert result[1]["quantity"] == 75
            assert result[1]["price"] == 15.75


def test_transform_data():
    """Test transform_data task with real data transformation."""
    test_data = [
        {"product": "Widget A", "quantity": 100, "price": 10.50, "date": "2024-01-15"},
        {"product": "Widget B", "quantity": 75, "price": 15.75, "date": "2024-01-16"},
    ]
    
    # Use Prefect's recommended approach for testing tasks
    with disable_run_logger():
        result = transform_data.fn(test_data)
        
        assert len(result) == 2
        assert result[0]["total_value"] == 1050.0  # 100 * 10.50
        assert result[1]["total_value"] == 1181.25  # 75 * 15.75
        assert "processed_at" in result[0]
        assert "processed_at" in result[1]


def test_calculate_summary():
    """Test calculate_summary task with real summary calculations."""
    test_data = [
        {"product": "Widget A", "quantity": 100, "price": 10.50, "total_value": 1050.0},
        {"product": "Widget B", "quantity": 75, "price": 15.75, "total_value": 1181.25},
        {"product": "Widget A", "quantity": 50, "price": 10.50, "total_value": 525.0},
    ]
    
    # Use Prefect's recommended approach for testing tasks
    with disable_run_logger():
        result = calculate_summary.fn(test_data)
        
        assert result["total_records"] == 3
        assert result["total_quantity"] == 225  # 100 + 75 + 50
        assert result["total_value"] == 2756.25  # 1050 + 1181.25 + 525
        assert result["average_price"] == 12.25  # (10.50 + 15.75 + 10.50) / 3
        
        # Check product breakdown
        assert "Widget A" in result["product_breakdown"]
        assert "Widget B" in result["product_breakdown"]
        assert result["product_breakdown"]["Widget A"]["quantity"] == 150
        assert result["product_breakdown"]["Widget A"]["total_value"] == 1575.0


def test_generate_report():
    """Test generate_report task with real file I/O operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        summary = {
            "total_records": 2,
            "total_value": 1000.0,
            "generated_at": "2024-01-15T10:00:00"
        }
        
        # Use Prefect's recommended approach for testing tasks
        with disable_run_logger():
            result = generate_report.fn(summary, temp_dir)
            
            # Check that file was created
            assert Path(result).exists()
            
            # Check file contents
            with open(result) as f:
                saved_data = json.load(f)
                assert saved_data["total_records"] == 2
                assert saved_data["total_value"] == 1000.0


def test_create_directory():
    """Test create_directory task with real directory operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        new_dir = Path(temp_dir) / "test_subdir"
        
        # Use Prefect's recommended approach for testing tasks
        with disable_run_logger():
            result = create_directory.fn(str(new_dir))
            
            assert Path(result).exists()
            assert Path(result).is_dir()


def test_validate_file_exists():
    """Test validate_file_exists task with real file validation."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content")
        f.close()
        
        # Use Prefect's recommended approach for testing tasks
        with disable_run_logger():
            assert validate_file_exists.fn(f.name) is True
            assert validate_file_exists.fn("non_existing_file.txt") is False
