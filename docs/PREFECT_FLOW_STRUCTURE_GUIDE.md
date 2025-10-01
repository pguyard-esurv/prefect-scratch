# Prefect Flow Structure Guidelines and Naming Conventions

## Overview

This guide establishes standards for organizing, structuring, and naming Prefect flows to ensure consistency, maintainability, and compatibility with the deployment system.

## Directory Structure

### Standard Flow Organization

```
flows/
├── {flow_category}/
│   ├── __init__.py
│   ├── workflow.py              # Main flow definition
│   ├── Dockerfile              # Container configuration (optional)
│   ├── requirements.txt        # Python dependencies
│   ├── .env.development        # Development environment variables
│   ├── .env.staging           # Staging environment variables
│   ├── .env.production        # Production environment variables
│   ├── config/
│   │   ├── flow_config.yaml   # Flow-specific configuration
│   │   └── parameters.yaml    # Default parameters
│   ├── data/                  # Input data directory
│   ├── output/                # Output data directory
│   ├── test/
│   │   ├── __init__.py
│   │   ├── test_workflow.py   # Flow unit tests
│   │   └── test_integration.py # Integration tests
│   └── docs/
│       ├── README.md          # Flow documentation
│       └── architecture.md    # Technical details
```

### Example Structure

```
flows/
├── rpa1/                      # RPA Process 1
│   ├── workflow.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.development
│   ├── .env.production
│   └── data/
├── rpa2/                      # RPA Process 2
│   ├── workflow.py
│   ├── Dockerfile
│   └── requirements.txt
├── data_processing/           # Data Processing Flows
│   ├── etl_workflow.py
│   ├── validation_workflow.py
│   └── config/
└── monitoring/                # Monitoring Flows
    ├── health_check.py
    └── performance_monitor.py
```

## Flow Naming Conventions

### Flow Names

Use descriptive, kebab-case names that clearly indicate the flow's purpose:

**Format:** `{category}-{purpose}-{environment}`

**Examples:**

- `rpa1-survey-processing-dev`
- `data-etl-customer-orders-prod`
- `monitoring-health-check-staging`

### Flow Categories

Standard categories for organizing flows:

- **rpa**: Robotic Process Automation flows
- **etl**: Extract, Transform, Load data processing
- **monitoring**: System and application monitoring
- **reporting**: Report generation and distribution
- **integration**: Third-party system integrations
- **maintenance**: System maintenance and cleanup

### Deployment Names

**Format:** `{flow_name}-{deployment_type}-{environment}`

**Examples:**

- `rpa1-survey-processing-python-dev`
- `rpa1-survey-processing-docker-prod`
- `data-etl-orders-python-staging`

## Flow Code Structure

### Basic Flow Template

```python
"""
Flow: {Flow Name}
Description: {Brief description of what the flow does}
Author: {Author name}
Created: {Date}
"""

from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
from typing import Dict, List, Optional, Any
import os
from pathlib import Path

# Configuration and constants
FLOW_NAME = "rpa1-survey-processing"
FLOW_VERSION = "1.0.0"
DEFAULT_BATCH_SIZE = 100

@task(name="validate-input", retries=2, retry_delay_seconds=30)
def validate_input_data(input_path: str) -> bool:
    """
    Validate input data before processing.

    Args:
        input_path: Path to input data

    Returns:
        bool: True if validation passes

    Raises:
        ValueError: If input data is invalid
    """
    logger = get_run_logger()
    logger.info(f"Validating input data at {input_path}")

    # Validation logic here
    if not Path(input_path).exists():
        raise ValueError(f"Input path does not exist: {input_path}")

    return True

@task(name="process-batch", retries=3, retry_delay_seconds=60)
def process_data_batch(batch_data: List[Dict], batch_id: int) -> Dict[str, Any]:
    """
    Process a batch of data.

    Args:
        batch_data: List of data records to process
        batch_id: Unique identifier for this batch

    Returns:
        Dict containing processing results
    """
    logger = get_run_logger()
    logger.info(f"Processing batch {batch_id} with {len(batch_data)} records")

    # Processing logic here
    results = {
        "batch_id": batch_id,
        "records_processed": len(batch_data),
        "success": True,
        "errors": []
    }

    return results

@task(name="save-results", retries=2)
def save_processing_results(results: List[Dict], output_path: str) -> str:
    """
    Save processing results to output location.

    Args:
        results: List of processing results
        output_path: Path to save results

    Returns:
        str: Path to saved results file
    """
    logger = get_run_logger()
    logger.info(f"Saving {len(results)} results to {output_path}")

    # Save logic here
    output_file = Path(output_path) / f"results_{datetime.now().isoformat()}.json"

    return str(output_file)

@flow(
    name=FLOW_NAME,
    version=FLOW_VERSION,
    description="Process survey data using RPA automation",
    task_runner=ConcurrentTaskRunner(),
    retries=1,
    retry_delay_seconds=300
)
def rpa1_survey_processing_flow(
    input_path: str = "/app/flows/rpa1/data",
    output_path: str = "/app/flows/rpa1/output",
    batch_size: int = DEFAULT_BATCH_SIZE,
    cleanup: bool = True,
    use_distributed: bool = False
) -> Dict[str, Any]:
    """
    Main flow for processing survey data.

    Args:
        input_path: Path to input data directory
        output_path: Path to output directory
        batch_size: Number of records to process per batch
        cleanup: Whether to cleanup temporary files
        use_distributed: Whether to use distributed processing

    Returns:
        Dict containing flow execution summary
    """
    logger = get_run_logger()
    logger.info(f"Starting {FLOW_NAME} v{FLOW_VERSION}")

    # Flow execution logic
    try:
        # 1. Validate inputs
        validation_result = validate_input_data(input_path)

        # 2. Process data in batches
        batch_results = []
        for batch_id in range(10):  # Example batch processing
            batch_data = []  # Load batch data
            result = process_data_batch(batch_data, batch_id)
            batch_results.append(result)

        # 3. Save results
        output_file = save_processing_results(batch_results, output_path)

        # 4. Return summary
        summary = {
            "flow_name": FLOW_NAME,
            "version": FLOW_VERSION,
            "batches_processed": len(batch_results),
            "output_file": output_file,
            "success": True
        }

        logger.info(f"Flow completed successfully: {summary}")
        return summary

    except Exception as e:
        logger.error(f"Flow failed with error: {str(e)}")
        raise

# Entry point for testing
if __name__ == "__main__":
    # Local testing
    result = rpa1_survey_processing_flow()
    print(f"Flow result: {result}")
```

### Required Flow Elements

Every flow must include:

1. **Flow Decorator**: `@flow()` with proper configuration
2. **Flow Name**: Consistent with naming conventions
3. **Version**: Semantic versioning (e.g., "1.0.0")
4. **Description**: Clear description of flow purpose
5. **Parameters**: Well-defined input parameters with defaults
6. **Logging**: Proper use of Prefect logger
7. **Error Handling**: Try/catch blocks and proper error propagation
8. **Return Value**: Structured return value with execution summary

### Task Structure Guidelines

```python
@task(
    name="descriptive-task-name",
    description="Clear description of task purpose",
    retries=3,
    retry_delay_seconds=60,
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=1)
)
def example_task(param1: str, param2: int = 100) -> Dict[str, Any]:
    """
    Detailed docstring explaining task purpose, parameters, and return value.

    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2 with default value

    Returns:
        Dict containing task results

    Raises:
        ValueError: When input validation fails
        ConnectionError: When external service is unavailable
    """
    logger = get_run_logger()

    # Task implementation
    pass
```

## Configuration Management

### Flow Configuration File

Create `config/flow_config.yaml` for each flow:

```yaml
# Flow Configuration
flow:
  name: "rpa1-survey-processing"
  version: "1.0.0"
  description: "Process survey data using RPA automation"

# Default Parameters
parameters:
  batch_size: 100
  timeout_seconds: 3600
  max_retries: 3
  cleanup: true

# Environment-specific overrides
environments:
  development:
    parameters:
      batch_size: 10
      cleanup: true
      debug: true

  staging:
    parameters:
      batch_size: 50
      cleanup: true
      debug: false

  production:
    parameters:
      batch_size: 1000
      cleanup: false
      debug: false

# Resource requirements
resources:
  memory: "512Mi"
  cpu: "0.5"

# Dependencies
dependencies:
  python_packages:
    - "pandas>=1.5.0"
    - "requests>=2.28.0"
    - "sqlalchemy>=1.4.0"

  system_packages:
    - "curl"
    - "jq"

# Scheduling
schedule:
  cron: "0 2 * * *" # Daily at 2 AM
  timezone: "UTC"
```

### Environment Variables

Use environment-specific `.env` files:

**.env.development:**

```bash
# Development Environment
PREFECT_API_URL=http://localhost:4200/api
DATABASE_URL=postgresql://dev_user:dev_pass@localhost:5432/dev_db
LOG_LEVEL=DEBUG
BATCH_SIZE=10
CLEANUP_ENABLED=true
```

**.env.production:**

```bash
# Production Environment
PREFECT_API_URL=http://prod-prefect:4200/api
DATABASE_URL=postgresql://prod_user:prod_pass@prod-db:5432/prod_db
LOG_LEVEL=INFO
BATCH_SIZE=1000
CLEANUP_ENABLED=false
```

## Docker Configuration

### Dockerfile Template

```dockerfile
# Multi-stage build for efficiency
FROM python:3.9-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.9-slim as runtime

# Create non-root user
RUN groupadd -r flowuser && useradd -r -g flowuser flowuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/flowuser/.local

# Set up application directory
WORKDIR /app
COPY . /app/

# Set ownership and permissions
RUN chown -R flowuser:flowuser /app
USER flowuser

# Add local packages to PATH
ENV PATH=/home/flowuser/.local/bin:$PATH
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "-m", "flows.rpa1.workflow"]
```

### Requirements.txt Structure

```txt
# Core Prefect
prefect>=2.10.0

# Data Processing
pandas>=1.5.0
numpy>=1.21.0
sqlalchemy>=1.4.0

# HTTP and API
requests>=2.28.0
httpx>=0.24.0

# Utilities
pydantic>=1.10.0
pyyaml>=6.0
python-dotenv>=0.19.0

# Development (optional)
pytest>=7.0.0
black>=22.0.0
flake8>=4.0.0

# Flow-specific dependencies
# Add your specific requirements here
```

## Testing Guidelines

### Unit Test Structure

```python
"""
Unit tests for RPA1 Survey Processing Flow
"""

import pytest
from unittest.mock import Mock, patch
from prefect.testing.utilities import prefect_test_harness
from flows.rpa1.workflow import (
    rpa1_survey_processing_flow,
    validate_input_data,
    process_data_batch,
    save_processing_results
)

class TestRPA1SurveyProcessing:
    """Test suite for RPA1 survey processing flow"""

    def setup_method(self):
        """Set up test fixtures"""
        self.test_input_path = "/tmp/test_input"
        self.test_output_path = "/tmp/test_output"
        self.test_batch_data = [{"id": 1, "data": "test"}]

    def test_validate_input_data_success(self):
        """Test successful input validation"""
        with patch("pathlib.Path.exists", return_value=True):
            result = validate_input_data(self.test_input_path)
            assert result is True

    def test_validate_input_data_failure(self):
        """Test input validation failure"""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(ValueError):
                validate_input_data(self.test_input_path)

    def test_process_data_batch(self):
        """Test batch processing"""
        result = process_data_batch(self.test_batch_data, 1)

        assert result["batch_id"] == 1
        assert result["records_processed"] == 1
        assert result["success"] is True

    @patch("flows.rpa1.workflow.save_processing_results")
    @patch("flows.rpa1.workflow.process_data_batch")
    @patch("flows.rpa1.workflow.validate_input_data")
    def test_flow_execution(self, mock_validate, mock_process, mock_save):
        """Test complete flow execution"""
        # Setup mocks
        mock_validate.return_value = True
        mock_process.return_value = {"batch_id": 1, "success": True}
        mock_save.return_value = "/tmp/results.json"

        # Execute flow
        with prefect_test_harness():
            result = rpa1_survey_processing_flow(
                input_path=self.test_input_path,
                output_path=self.test_output_path,
                batch_size=10
            )

        # Verify results
        assert result["success"] is True
        assert result["flow_name"] == "rpa1-survey-processing"
```

### Integration Test Structure

```python
"""
Integration tests for RPA1 Survey Processing Flow
"""

import pytest
from prefect.testing.utilities import prefect_test_harness
from flows.rpa1.workflow import rpa1_survey_processing_flow

class TestRPA1Integration:
    """Integration test suite"""

    @pytest.mark.integration
    def test_end_to_end_flow(self):
        """Test complete flow with real data"""
        with prefect_test_harness():
            result = rpa1_survey_processing_flow(
                input_path="test/fixtures/sample_data",
                output_path="test/output",
                batch_size=5
            )

        assert result["success"] is True
        assert result["batches_processed"] > 0
```

## Documentation Standards

### Flow README Template

````markdown
# {Flow Name}

## Overview

Brief description of what this flow does and its purpose.

## Parameters

| Parameter  | Type | Default     | Description        |
| ---------- | ---- | ----------- | ------------------ |
| input_path | str  | "/app/data" | Path to input data |
| batch_size | int  | 100         | Records per batch  |
| cleanup    | bool | true        | Enable cleanup     |

## Environment Variables

| Variable     | Required | Description                |
| ------------ | -------- | -------------------------- |
| DATABASE_URL | Yes      | Database connection string |
| API_KEY      | Yes      | External API key           |

## Dependencies

- pandas>=1.5.0
- requests>=2.28.0
- Custom package requirements

## Usage

### Local Development

```bash
python -m flows.rpa1.workflow
```
````

### Docker

```bash
docker build -t rpa1-flow .
docker run rpa1-flow
```

### Prefect Deployment

```bash
make deploy-python FLOW=rpa1
```

## Testing

```bash
pytest flows/rpa1/test/
```

## Troubleshooting

Common issues and solutions specific to this flow.

```

## Validation and Compliance

### Pre-deployment Checklist

- [ ] Flow follows naming conventions
- [ ] All required decorators present (@flow, @task)
- [ ] Proper error handling implemented
- [ ] Logging configured correctly
- [ ] Parameters have appropriate defaults
- [ ] Documentation is complete
- [ ] Tests are written and passing
- [ ] Environment files are configured
- [ ] Docker configuration is valid (if applicable)
- [ ] Dependencies are properly specified

### Automated Validation

The deployment system automatically validates:

1. **Flow Structure**: Presence of @flow decorator
2. **Naming Conventions**: Compliance with naming standards
3. **Dependencies**: Availability of required packages
4. **Configuration**: Valid environment and parameter configuration
5. **Docker**: Valid Dockerfile and build process

### Manual Review Points

Before deploying flows, manually review:

1. **Business Logic**: Correctness of processing logic
2. **Performance**: Resource usage and optimization
3. **Security**: Proper handling of sensitive data
4. **Monitoring**: Adequate logging and error reporting
5. **Documentation**: Completeness and accuracy

## Migration Guide

### Updating Existing Flows

When updating existing flows to follow these guidelines:

1. **Backup**: Create backup of existing flow
2. **Rename**: Update flow and file names to follow conventions
3. **Restructure**: Organize files according to standard structure
4. **Update Code**: Add required decorators and error handling
5. **Test**: Verify flow works with new structure
6. **Deploy**: Use deployment system to redeploy

### Version Management

Use semantic versioning for flows:

- **Major (1.0.0)**: Breaking changes to flow interface
- **Minor (1.1.0)**: New features, backward compatible
- **Patch (1.1.1)**: Bug fixes, no interface changes

## Best Practices Summary

1. **Consistency**: Follow naming and structure conventions
2. **Documentation**: Document all flows, parameters, and dependencies
3. **Testing**: Write comprehensive unit and integration tests
4. **Error Handling**: Implement proper error handling and logging
5. **Configuration**: Use environment-specific configuration
6. **Security**: Follow security best practices for sensitive data
7. **Performance**: Optimize for resource usage and execution time
8. **Monitoring**: Include adequate logging and monitoring
9. **Maintenance**: Keep dependencies updated and code clean
10. **Deployment**: Use the deployment system for consistent deployments
```
