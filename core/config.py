"""
Configuration settings for the RPA solution.
"""

from pathlib import Path

# Base paths
PROJECT_ROOT = Path(__file__).parent.parent
# RPA1 directories
RPA1_DATA_DIR = PROJECT_ROOT / "flows" / "rpa1" / "data"
RPA1_OUTPUT_DIR = PROJECT_ROOT / "flows" / "rpa1" / "output"

# RPA2 directories  
RPA2_DATA_DIR = PROJECT_ROOT / "flows" / "rpa2" / "data"
RPA2_OUTPUT_DIR = PROJECT_ROOT / "flows" / "rpa2" / "output"

# Backward compatibility (deprecated)
DATA_DIR = RPA1_DATA_DIR
OUTPUT_DIR = RPA1_OUTPUT_DIR
LOGS_DIR = PROJECT_ROOT / "logs"

# Default settings
DEFAULT_CLEANUP = True
DEFAULT_OUTPUT_FORMAT = "json"

# File patterns
CSV_EXTENSION = ".csv"
JSON_EXTENSION = ".json"
REPORT_PREFIX = "sales_report_"

# Sample data configuration
SAMPLE_PRODUCTS = [
    {"product": "Widget A", "quantity": 100, "price": 10.50, "date": "2024-01-15"},
    {"product": "Widget B", "quantity": 75, "price": 15.75, "date": "2024-01-16"},
    {"product": "Widget C", "quantity": 200, "price": 8.25, "date": "2024-01-17"},
    {"product": "Widget A", "quantity": 150, "price": 10.50, "date": "2024-01-18"},
    {"product": "Widget B", "quantity": 50, "price": 15.75, "date": "2024-01-19"},
]

