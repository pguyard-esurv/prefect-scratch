"""Tests for configuration module."""

from pathlib import Path

import pytest

from core.config import (
    CSV_EXTENSION,
    DATA_DIR,
    DEFAULT_CLEANUP,
    DEFAULT_OUTPUT_FORMAT,
    JSON_EXTENSION,
    LOGS_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
    REPORT_PREFIX,
    SAMPLE_PRODUCTS,
)

pytestmark = pytest.mark.unit


def test_project_root():
    """Test that PROJECT_ROOT is correctly set."""
    assert isinstance(PROJECT_ROOT, Path)
    assert PROJECT_ROOT.name == "prefect_scratch"


def test_directory_paths():
    """Test that directory paths are correctly configured."""
    assert DATA_DIR == PROJECT_ROOT / "flows" / "rpa1" / "data"
    assert OUTPUT_DIR == PROJECT_ROOT / "flows" / "rpa1" / "output"
    assert LOGS_DIR == PROJECT_ROOT / "logs"


def test_default_settings():
    """Test default configuration values."""
    assert DEFAULT_CLEANUP is True
    assert DEFAULT_OUTPUT_FORMAT == "json"


def test_file_patterns():
    """Test file pattern constants."""
    assert CSV_EXTENSION == ".csv"
    assert JSON_EXTENSION == ".json"
    assert REPORT_PREFIX == "sales_report_"


def test_sample_products():
    """Test sample products configuration."""
    assert isinstance(SAMPLE_PRODUCTS, list)
    assert len(SAMPLE_PRODUCTS) == 5

    # Check that all products have required fields
    required_fields = {"product", "quantity", "price", "date"}
    for product in SAMPLE_PRODUCTS:
        assert all(field in product for field in required_fields)
        assert isinstance(product["quantity"], int)
        assert isinstance(product["price"], (int, float))
        assert product["quantity"] > 0
        assert product["price"] > 0
