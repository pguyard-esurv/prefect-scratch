# Testing Strategy

This document outlines the comprehensive testing strategy for the Prefect RPA Solution, following Prefect's recommended testing best practices.

## Overview

Our testing strategy implements a multi-layered approach that ensures code quality, reliability, and maintainability:

- **Unit Tests**: Test individual components with real data and minimal mocking
- **Integration Tests**: Test complete workflows with Prefect's test harness
- **Coverage Reporting**: Track and report test coverage across all modules
- **Test Isolation**: Use Prefect's ephemeral backend for proper test isolation

## Test Architecture

### Test Structure

```
├── conftest.py                    # Prefect test harness configuration
├── core/test/                     # Unit tests for core components
│   ├── test_config.py            # Configuration tests
│   └── test_tasks.py             # Task function tests
├── flows/rpa1/test/              # RPA1 workflow tests
│   ├── test_workflow.py          # Unit tests for workflow logic
│   └── test_integration.py       # Integration tests for RPA1
└── flows/rpa2/test/              # RPA2 workflow tests
    ├── test_workflow.py          # Unit tests for workflow logic
    └── test_integration.py       # Integration tests for RPA2
```

### Test Categories

#### Unit Tests (`@pytest.mark.unit`)
- Test individual functions and components
- Use real data with minimal mocking
- Focus on business logic and data processing
- Fast execution (< 10 seconds)

#### Integration Tests (`@pytest.mark.integration`)
- Test complete workflows with Prefect execution
- Use Prefect's test harness for proper context
- Verify task orchestration and flow execution
- Slower execution (~15 seconds)

## Prefect Testing Best Practices

### Test Harness Configuration

Our tests use Prefect's recommended `prefect_test_harness()` for proper test isolation:

```python
# conftest.py
import pytest
from prefect.testing.utilities import prefect_test_harness

@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    """Session-scoped fixture for Prefect test harness."""
    with prefect_test_harness():
        yield
```

### Testing Prefect Tasks

We follow Prefect's recommended approach for testing tasks:

```python
from prefect.logging import disable_run_logger

def test_extract_data():
    """Test extract_data task with real CSV data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("product,quantity,price,date\n")
        f.write("Widget A,100,10.50,2024-01-15\n")
        f.close()
        
        # Use Prefect's recommended approach
        with disable_run_logger():
            result = extract_data.fn(f.name)
            
            assert len(result) == 1
            assert result[0]["product"] == "Widget A"
```

### Testing Prefect Flows

Integration tests run actual Prefect workflows:

```python
def test_rpa1_workflow_integration(self):
    """Test RPA1 workflow with real Prefect execution."""
    # Run the actual Prefect workflow with real data
    result = rpa1_workflow(cleanup=True)
    
    # Verify workflow execution and results
    assert isinstance(result, dict)
    assert "total_records" in result
    assert "total_value" in result
    assert result["total_records"] > 0
```

## Running Tests

### Prerequisites

Ensure you have the development environment set up:

```bash
# Install development dependencies
make install-dev

# Or manually with uv
uv sync
```

### Test Commands

#### Run All Tests
```bash
make test
# Equivalent to: uv run pytest
```

#### Run Unit Tests Only
```bash
make test-unit
# Equivalent to: uv run pytest -m unit
```

#### Run Integration Tests Only
```bash
make test-integration
# Equivalent to: uv run pytest -m integration
```

#### Run Tests with Coverage
```bash
make test-coverage
# Equivalent to: uv run pytest --cov=core --cov=flows --cov-report=html --cov-report=term-missing
```

#### Run Tests in Watch Mode
```bash
make test-watch
# Equivalent to: uv run pytest-watch
```

### Running Specific Test Modules

```bash
# Run core tests only
uv run pytest core/test/ -v

# Run RPA1 workflow tests only (unit + integration)
uv run pytest flows/rpa1/test/ -v

# Run RPA2 workflow tests only (unit + integration)
uv run pytest flows/rpa2/test/ -v

# Run only unit tests
uv run pytest -m unit -v

# Run only integration tests
uv run pytest -m integration -v
```

### Running Specific Tests

```bash
# Run a specific test function
uv run pytest core/test/test_tasks.py::test_extract_data -v

# Run tests matching a pattern
uv run pytest -k "test_extract" -v

# Run tests by marker
uv run pytest -m unit -v
uv run pytest -m integration -v
```

## Test Configuration

### Pytest Configuration

The project uses `pyproject.toml` for pytest configuration:

```toml
[tool.pytest.ini_options]
testpaths = ["core/test", "flows/rpa1/test", "flows/rpa2/test", "tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
markers = [
    "unit: Unit tests for individual components",
    "integration: Integration tests for workflows",
    "slow: Slow running tests",
]
```

### Coverage Configuration

Coverage is configured to track:
- `core/` - Core business logic
- `flows/` - Workflow implementations

Coverage reports are generated in:
- Terminal output (`--cov-report=term-missing`)
- HTML format (`htmlcov/index.html`)

## Test Data Management

### Unit Test Data

Unit tests use temporary files and in-memory data:

```python
def test_extract_data():
    """Test with temporary CSV file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write("product,quantity,price,date\n")
        f.write("Widget A,100,10.50,2024-01-15\n")
        f.close()
        
        # Test with real file I/O
        with disable_run_logger():
            result = extract_data.fn(f.name)
```

### Integration Test Data

Integration tests use Prefect's test harness with real workflow execution:

```python
def test_rpa1_workflow_integration(self):
    """Test with real Prefect execution."""
    # Creates real sample data, processes it, and generates reports
    result = rpa1_workflow(cleanup=True)
```

## Test Coverage

### Current Coverage

- **Overall Coverage**: 96%
- **Core Module**: 98% (2 lines missing)
- **RPA1 Workflow**: 90% (2 lines missing)
- **RPA2 Workflow**: 91% (6 lines missing)

### Coverage Reports

Generate detailed coverage reports:

```bash
# Generate HTML coverage report
make test-coverage

# View coverage report
open htmlcov/index.html
```

### Coverage Goals

- **Minimum Coverage**: 90% for all modules
- **Target Coverage**: 95% for critical business logic
- **Exclude**: Test files, `__init__.py` files, and error handling paths

## Debugging Tests

### Verbose Output

```bash
# Run tests with verbose output
uv run pytest -v

# Run tests with extra verbose output
uv run pytest -vv

# Run tests with print statements visible
uv run pytest -s
```

### Debugging Specific Tests

```bash
# Run a single test with debugging
uv run pytest core/test/test_tasks.py::test_extract_data -v -s

# Run tests with pdb debugger
uv run pytest --pdb

# Run tests with pdb on failure
uv run pytest --pdb-failures
```

### Test Logging

Integration tests show Prefect execution logs:

```bash
# Run integration tests to see Prefect logs
make test-integration
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Install dependencies
        run: uv sync
      - name: Run tests
        run: make test
      - name: Run coverage
        run: make test-coverage
```

## Best Practices

### Writing Unit Tests

1. **Use Real Data**: Test with actual file I/O and data processing
2. **Minimal Mocking**: Only mock external dependencies, not business logic
3. **Test Edge Cases**: Include boundary conditions and error scenarios
4. **Clear Assertions**: Use descriptive assertion messages
5. **Fast Execution**: Keep unit tests under 1 second each

### Writing Integration Tests

1. **Real Prefect Execution**: Use actual Prefect workflows
2. **Test Complete Flows**: Verify end-to-end functionality
3. **Verify Results**: Check output structure and content
4. **Clean Up**: Ensure tests don't leave side effects
5. **Meaningful Names**: Use descriptive test names

### Test Maintenance

1. **Keep Tests Updated**: Update tests when code changes
2. **Remove Dead Tests**: Delete tests for removed functionality
3. **Refactor Tests**: Improve test readability and maintainability
4. **Monitor Coverage**: Track coverage trends over time
5. **Review Test Quality**: Regular code reviews of test code

## Troubleshooting

### Common Issues

#### Import Errors
```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Or use uv to run tests
uv run pytest
```

#### Prefect Context Errors
```bash
# Ensure conftest.py is in the project root
# The prefect_test_harness fixture should be automatically loaded
```

#### Coverage Issues
```bash
# Ensure pytest-cov is installed
uv add pytest-cov

# Run coverage with specific modules
uv run pytest --cov=core --cov=flows
```

#### Slow Tests
```bash
# Run only unit tests for faster feedback
make test-unit

# Use pytest-xdist for parallel execution
uv add pytest-xdist
uv run pytest -n auto
```

### Getting Help

- **Prefect Testing Docs**: https://docs.prefect.io/v3/how-to-guides/workflows/test-workflows
- **Pytest Documentation**: https://docs.pytest.org/
- **Coverage.py Documentation**: https://coverage.readthedocs.io/

## Summary

This testing strategy provides:

- **23 tests** with 96% coverage
- **Unit tests** for individual components
- **Integration tests** for complete workflows
- **Prefect best practices** for testing workflows
- **Comprehensive tooling** for test execution and reporting
- **Clear documentation** for developers

The strategy ensures code quality while maintaining fast feedback loops and comprehensive coverage of the Prefect RPA Solution.
