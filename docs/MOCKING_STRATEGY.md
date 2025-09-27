# Mocking Strategy for Prefect Workflows

This document outlines comprehensive mocking strategies for testing Prefect workflows, covering various scenarios from simple data mocking to complex database interactions and API calls.

## Table of Contents

- [Overview](#overview)
- [Basic Mocking Patterns](#basic-mocking-patterns)
- [Data Source Mocking](#data-source-mocking)
- [Database Call Mocking](#database-call-mocking)
- [API Call Mocking](#api-call-mocking)
- [File System Mocking](#file-system-mocking)
- [Error Scenario Mocking](#error-scenario-mocking)
- [Advanced Mocking Techniques](#advanced-mocking-techniques)
- [Best Practices](#best-practices)
- [Common Pitfalls](#common-pitfalls)

## Overview

Mocking in Prefect workflows allows you to:
- **Test Real Workflow Logic**: Run actual Prefect flows with controlled data
- **Isolate Components**: Test individual parts without external dependencies
- **Control Test Data**: Use predictable, repeatable test data
- **Test Error Scenarios**: Simulate failures and edge cases
- **Speed Up Tests**: Avoid slow external API calls and database queries

### When to Mock vs When Not to Mock

**Mock These:**
- External API calls
- Database queries
- File system operations
- Network requests
- External service calls

**Don't Mock These:**
- Business logic functions
- Data transformation logic
- Prefect task orchestration
- Core workflow logic

## Basic Mocking Patterns

### Simple Data Source Mocking

```python
"""Basic pattern: Mock data source, run real workflow."""

import pytest
from unittest.mock import patch

from flows.my_workflow import my_flow

pytestmark = pytest.mark.integration


def test_workflow_with_mocked_data():
    """Test workflow with mocked data source."""
    # Define fake data
    fake_data = [
        {"id": 1, "name": "Alice", "value": 100},
        {"id": 2, "name": "Bob", "value": 200},
    ]
    
    # Mock the data source
    with patch('flows.my_workflow.fetch_data') as mock_fetch:
        mock_fetch.return_value = fake_data
        
        # Run the REAL Prefect workflow
        result = my_flow()
        
        # Verify results
        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        
        # Verify mock was called
        mock_fetch.assert_called_once()
```

### Mocking Multiple Dependencies

```python
def test_workflow_with_multiple_mocks():
    """Test workflow with multiple mocked dependencies."""
    fake_data = [{"id": 1, "name": "Test"}]
    fake_config = {"api_url": "https://test.api.com"}
    
    # Mock multiple dependencies
    with patch('flows.my_workflow.fetch_data') as mock_fetch, \
         patch('flows.my_workflow.get_config') as mock_config:
        
        mock_fetch.return_value = fake_data
        mock_config.return_value = fake_config
        
        result = my_flow()
        
        # Verify all mocks were used
        mock_fetch.assert_called_once()
        mock_config.assert_called_once()
```

## Data Source Mocking

### CSV File Mocking

```python
def test_workflow_with_csv_data():
    """Test workflow that processes CSV data."""
    import tempfile
    import csv
    
    # Create fake CSV data
    fake_data = [
        {"product": "Widget A", "quantity": 100, "price": 10.50},
        {"product": "Widget B", "quantity": 75, "price": 15.75},
    ]
    
    # Create temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.DictWriter(f, fieldnames=fake_data[0].keys())
        writer.writeheader()
        writer.writerows(fake_data)
        fake_csv_path = f.name
    
    # Mock the file creation
    with patch('flows.my_workflow.create_data_file') as mock_create:
        mock_create.return_value = fake_csv_path
        
        result = my_workflow()
        
        # Verify processing
        assert result["total_records"] == 2
        assert result["total_value"] == 2062.5
```

### JSON Data Mocking

```python
def test_workflow_with_json_data():
    """Test workflow that processes JSON data."""
    fake_json_data = {
        "users": [
            {"id": 1, "name": "Alice", "active": True},
            {"id": 2, "name": "Bob", "active": False},
        ],
        "metadata": {"version": "1.0", "created": "2024-01-01"}
    }
    
    with patch('flows.my_workflow.fetch_json_data') as mock_fetch:
        mock_fetch.return_value = fake_json_data
        
        result = my_workflow()
        
        assert result["active_users"] == 1
        assert result["total_users"] == 2
```

## Database Call Mocking

### Simple Database Mocking

```python
def test_workflow_with_database_calls():
    """Test workflow with database interactions."""
    fake_records = [
        {"id": 1, "name": "Alice", "email": "alice@example.com"},
        {"id": 2, "name": "Bob", "email": "bob@example.com"},
    ]
    
    fake_db_responses = {
        1: {"status": "processed", "user_id": 1, "result": "success"},
        2: {"status": "processed", "user_id": 2, "result": "success"},
    }
    
    with patch('flows.my_workflow.fetch_users') as mock_fetch, \
         patch('flows.my_workflow.update_user') as mock_update:
        
        mock_fetch.return_value = fake_records
        
        # Mock database responses based on input
        def mock_db_response(user):
            return fake_db_responses[user["id"]]
        
        mock_update.side_effect = mock_db_response
        
        result = my_workflow()
        
        # Verify database was called for each user
        assert mock_update.call_count == 2
        assert all(r["status"] == "processed" for r in result)
```

### Database Mocking with .map()

```python
def test_workflow_with_map_and_database():
    """Test workflow using .map() with individual database calls."""
    fake_records = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
        {"id": 3, "name": "Charlie"},
    ]
    
    with patch('flows.my_workflow.fetch_data') as mock_fetch, \
         patch('flows.my_workflow.process_record') as mock_process:
        
        mock_fetch.return_value = fake_records
        
        # Mock individual record processing
        def mock_process_record(record):
            return {
                "id": record["id"],
                "name": record["name"],
                "processed_at": "2024-01-01T10:00:00",
                "status": "success"
            }
        
        mock_process.side_effect = mock_process_record
        
        # Run workflow (this will call process_record.map())
        result = my_workflow()
        
        # Verify all records were processed
        assert len(result) == 3
        assert mock_process.call_count == 3
```

### Database Error Mocking

```python
def test_workflow_with_database_errors():
    """Test workflow behavior when database calls fail."""
    fake_records = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
    
    with patch('flows.my_workflow.fetch_data') as mock_fetch, \
         patch('flows.my_workflow.update_database') as mock_update:
        
        mock_fetch.return_value = fake_records
        
        # Mock database to fail for specific records
        def mock_db_with_errors(record):
            if record["id"] == 1:
                raise Exception("Database connection failed")
            return {"status": "success", "id": record["id"]}
        
        mock_update.side_effect = mock_db_with_errors
        
        # Test error handling
        try:
            result = my_workflow()
            # If workflow handles errors gracefully
            assert len(result) == 1  # Only successful records
        except Exception as e:
            # If workflow fails on first error
            assert "Database connection failed" in str(e)
```

## API Call Mocking

### HTTP API Mocking

```python
def test_workflow_with_api_calls():
    """Test workflow that makes HTTP API calls."""
    import requests
    from unittest.mock import Mock
    
    fake_api_response = {
        "status": "success",
        "data": [
            {"id": 1, "name": "API User 1"},
            {"id": 2, "name": "API User 2"},
        ]
    }
    
    with patch('flows.my_workflow.requests.get') as mock_get:
        # Mock the API response
        mock_response = Mock()
        mock_response.json.return_value = fake_api_response
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        result = my_workflow()
        
        # Verify API was called
        mock_get.assert_called_once()
        assert result["user_count"] == 2
```

### Multiple API Calls Mocking

```python
def test_workflow_with_multiple_apis():
    """Test workflow that calls multiple APIs."""
    with patch('flows.my_workflow.call_api_1') as mock_api1, \
         patch('flows.my_workflow.call_api_2') as mock_api2:
        
        mock_api1.return_value = {"data": [{"id": 1, "name": "User 1"}]}
        mock_api2.return_value = {"permissions": ["read", "write"]}
        
        result = my_workflow()
        
        # Verify both APIs were called
        mock_api1.assert_called_once()
        mock_api2.assert_called_once()
        
        # Verify combined results
        assert result["user"]["name"] == "User 1"
        assert "read" in result["permissions"]
```

## File System Mocking

### File Operations Mocking

```python
def test_workflow_with_file_operations():
    """Test workflow that performs file operations."""
    from unittest.mock import mock_open, patch
    
    fake_file_content = "line1\nline2\nline3\n"
    
    with patch('builtins.open', mock_open(read_data=fake_file_content)):
        result = my_workflow()
        
        assert result["line_count"] == 3
```

### Directory Operations Mocking

```python
def test_workflow_with_directory_operations():
    """Test workflow that works with directories."""
    from unittest.mock import patch, MagicMock
    
    fake_files = ["file1.txt", "file2.txt", "file3.txt"]
    
    with patch('flows.my_workflow.os.listdir') as mock_listdir, \
         patch('flows.my_workflow.os.path.isfile') as mock_isfile:
        
        mock_listdir.return_value = fake_files
        mock_isfile.return_value = True
        
        result = my_workflow()
        
        assert result["file_count"] == 3
```

## Error Scenario Mocking

### Network Timeout Mocking

```python
def test_workflow_with_network_timeout():
    """Test workflow behavior when network calls timeout."""
    import requests
    
    with patch('flows.my_workflow.requests.get') as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")
        
        try:
            result = my_workflow()
            # If workflow handles timeouts gracefully
            assert result["status"] == "timeout_handled"
        except requests.exceptions.Timeout:
            # If workflow propagates the timeout
            pass
```

### Partial Failure Mocking

```python
def test_workflow_with_partial_failures():
    """Test workflow when some operations fail."""
    fake_data = [{"id": 1}, {"id": 2}, {"id": 3}]
    
    with patch('flows.my_workflow.fetch_data') as mock_fetch, \
         patch('flows.my_workflow.process_item') as mock_process:
        
        mock_fetch.return_value = fake_data
        
        # Mock to fail for specific items
        def mock_process_with_failures(item):
            if item["id"] == 2:
                raise Exception("Processing failed")
            return {"id": item["id"], "status": "success"}
        
        mock_process.side_effect = mock_process_with_failures
        
        result = my_workflow()
        
        # Verify partial success
        successful_items = [r for r in result if r["status"] == "success"]
        assert len(successful_items) == 2
```

## Advanced Mocking Techniques

### Context Manager Mocking

```python
def test_workflow_with_context_managers():
    """Test workflow that uses context managers."""
    from unittest.mock import patch, MagicMock
    
    with patch('flows.my_workflow.DatabaseConnection') as mock_db_class:
        # Mock the context manager
        mock_db = MagicMock()
        mock_db_class.return_value.__enter__.return_value = mock_db
        mock_db.query.return_value = [{"id": 1, "name": "Test"}]
        
        result = my_workflow()
        
        # Verify database was used
        mock_db.query.assert_called_once()
```

### Async Function Mocking

```python
def test_workflow_with_async_calls():
    """Test workflow that makes async calls."""
    import asyncio
    from unittest.mock import AsyncMock, patch
    
    async def mock_async_function():
        return {"data": "async_result"}
    
    with patch('flows.my_workflow.async_function', new_callable=AsyncMock) as mock_async:
        mock_async.return_value = {"data": "async_result"}
        
        result = my_workflow()
        
        assert result["async_data"] == "async_result"
```

### Mock with Side Effects

```python
def test_workflow_with_side_effects():
    """Test workflow with mocked functions that have side effects."""
    call_count = 0
    
    def mock_with_side_effect():
        nonlocal call_count
        call_count += 1
        return f"result_{call_count}"
    
    with patch('flows.my_workflow.some_function') as mock_func:
        mock_func.side_effect = mock_with_side_effect
        
        result = my_workflow()
        
        assert call_count == 3  # Function was called 3 times
        assert "result_3" in result
```

## Best Practices

### 1. Mock at the Right Level

```python
# ✅ Good: Mock the external dependency
with patch('flows.my_workflow.database_query') as mock_db:
    mock_db.return_value = fake_data

# ❌ Bad: Mock the Prefect task itself
with patch('flows.my_workflow.process_data') as mock_process:
    mock_process.return_value = fake_result
```

### 2. Use Realistic Test Data

```python
# ✅ Good: Realistic data
fake_users = [
    {"id": 1, "name": "Alice Johnson", "email": "alice@company.com", "active": True},
    {"id": 2, "name": "Bob Smith", "email": "bob@company.com", "active": False},
]

# ❌ Bad: Unrealistic data
fake_users = [
    {"id": 1, "name": "Test", "email": "test", "active": True},
]
```

### 3. Test Error Scenarios

```python
# ✅ Good: Test both success and failure
def test_workflow_success():
    # Test normal operation
    
def test_workflow_failure():
    # Test error handling
```

### 4. Verify Mock Interactions

```python
# ✅ Good: Verify mocks were called correctly
mock_db.assert_called_once_with(expected_params)
assert mock_api.call_count == 3

# ❌ Bad: Don't verify mock usage
# Just check the result
```

### 5. Use Descriptive Mock Names

```python
# ✅ Good: Descriptive names
with patch('flows.my_workflow.fetch_user_data') as mock_fetch_users:

# ❌ Bad: Generic names
with patch('flows.my_workflow.get_data') as mock_get:
```

## Common Pitfalls

### 1. Mocking Too Much

```python
# ❌ Bad: Mocking business logic
with patch('flows.my_workflow.calculate_total') as mock_calc:
    mock_calc.return_value = 1000

# ✅ Good: Mock external dependencies only
with patch('flows.my_workflow.fetch_prices') as mock_fetch:
    mock_fetch.return_value = [10, 20, 30]
```

### 2. Incorrect Mock Paths

```python
# ❌ Bad: Wrong import path
with patch('my_workflow.database_call') as mock_db:  # Wrong path

# ✅ Good: Correct import path
with patch('flows.my_workflow.database_call') as mock_db:  # Correct path
```

### 3. Not Cleaning Up Mocks

```python
# ❌ Bad: Mocks persist between tests
def test_1():
    with patch('flows.my_workflow.api_call') as mock_api:
        mock_api.return_value = "test"

def test_2():
    # Mock from test_1 might still be active
    pass

# ✅ Good: Each test has its own mocks
def test_1():
    with patch('flows.my_workflow.api_call') as mock_api:
        mock_api.return_value = "test"

def test_2():
    with patch('flows.my_workflow.api_call') as mock_api:
        mock_api.return_value = "different_test"
```

### 4. Overly Complex Mocks

```python
# ❌ Bad: Overly complex mock setup
def test_workflow():
    with patch('flows.my_workflow.api1') as mock1, \
         patch('flows.my_workflow.api2') as mock2, \
         patch('flows.my_workflow.api3') as mock3, \
         patch('flows.my_workflow.api4') as mock4:
        # 50 lines of mock configuration...

# ✅ Good: Simple, focused mocks
def test_workflow():
    with patch('flows.my_workflow.main_api') as mock_api:
        mock_api.return_value = fake_data
        result = my_workflow()
```

## Summary

Effective mocking in Prefect workflows involves:

1. **Mocking external dependencies** (APIs, databases, file systems)
2. **Using realistic test data** that mirrors production data
3. **Testing both success and error scenarios**
4. **Verifying mock interactions** to ensure correct usage
5. **Keeping mocks simple and focused** on specific concerns

By following these strategies, you can create comprehensive, reliable tests that verify your Prefect workflows work correctly while remaining fast and maintainable.
