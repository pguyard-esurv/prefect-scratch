# Container Development Guide

## Overview

This guide provides comprehensive information for developers working with the Container Testing System. It covers development workflows, best practices, debugging techniques, and guidelines for building, testing, and maintaining containerized applications in the distributed processing environment.

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Container Development Workflow](#container-development-workflow)
3. [Two-Stage Build Process](#two-stage-build-process)
4. [Development Best Practices](#development-best-practices)
5. [Testing Strategies](#testing-strategies)
6. [Debugging Techniques](#debugging-techniques)
7. [Performance Optimization](#performance-optimization)
8. [Security Guidelines](#security-guidelines)
9. [Code Quality Standards](#code-quality-standards)
10. [Troubleshooting Common Issues](#troubleshooting-common-issues)

## Development Environment Setup

### Prerequisites

Ensure you have the following tools installed:

```bash
# Required tools
docker --version          # Docker 20.10+
docker-compose --version  # Docker Compose 2.0+
python --version          # Python 3.11+
uv --version             # UV package manager
git --version            # Git 2.30+

# Optional but recommended
make --version           # GNU Make
curl --version           # cURL for API testing
jq --version            # JSON processor
```

### Initial Setup

```bash
# 1. Clone the repository
git clone <repository-url>
cd rpa-container-system

# 2. Set up Python environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# 3. Set up development environment files
cp flows/rpa1/.env.development.example flows/rpa1/.env.development
cp flows/rpa2/.env.development.example flows/rpa2/.env.development
cp flows/rpa3/.env.development.example flows/rpa3/.env.development

# 4. Configure development settings
vim flows/rpa1/.env.development
# Set appropriate development values

# 5. Build development images
./scripts/build_all.sh --environment development

# 6. Start development environment
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# 7. Verify setup
python core/test/run_container_tests.py --category smoke
```

### IDE Configuration

#### VS Code Setup

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["core/test", "--verbose"],
  "docker.defaultRegistryPath": "localhost:5000",
  "files.associations": {
    "*.yml": "yaml",
    "Dockerfile*": "dockerfile"
  }
}
```

Create `.vscode/launch.json` for debugging:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Container Tests",
      "type": "python",
      "request": "launch",
      "program": "core/test/run_container_tests.py",
      "args": ["--category", "unit", "--verbose"],
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}",
      "env": {
        "CONTAINER_ENVIRONMENT": "development",
        "CONTAINER_LOG_LEVEL": "DEBUG"
      }
    },
    {
      "name": "Debug Flow Workflow",
      "type": "python",
      "request": "launch",
      "program": "flows/rpa1/workflow.py",
      "console": "integratedTerminal",
      "cwd": "${workspaceFolder}"
    }
  ]
}
```

## Container Development Workflow

### Daily Development Cycle

```bash
# 1. Start development environment
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d

# 2. Check system health
curl http://localhost:8080/health
curl http://localhost:8081/health
curl http://localhost:8082/health

# 3. Make code changes
# Edit files in flows/, core/, or other directories

# 4. Test changes locally
python -m pytest core/test/test_specific_module.py -v

# 5. Rebuild affected containers (automatic with hot reload)
# Or manually: ./scripts/selective_rebuild.sh

# 6. Run integration tests
python core/test/run_container_tests.py --category integration

# 7. Commit changes
git add .
git commit -m "feat: implement new feature"
git push origin feature-branch
```

### Hot Reloading Development

The development environment supports hot reloading for faster iteration:

```yaml
# docker-compose.override.yml
version: "3.8"
services:
  rpa-flow1:
    volumes:
      - ./flows/rpa1:/app/flows/rpa1:rw
      - ./core:/app/core:rw
    environment:
      - CONTAINER_HOT_RELOAD=true
      - CONTAINER_DEBUG_MODE=true
    command: ["python", "-m", "watchdog", "flows/rpa1/workflow.py"]

  rpa-flow2:
    volumes:
      - ./flows/rpa2:/app/flows/rpa2:rw
      - ./core:/app/core:rw
    environment:
      - CONTAINER_HOT_RELOAD=true
      - CONTAINER_DEBUG_MODE=true

  rpa-flow3:
    volumes:
      - ./flows/rpa3:/app/flows/rpa3:rw
      - ./core:/app/core:rw
    environment:
      - CONTAINER_HOT_RELOAD=true
      - CONTAINER_DEBUG_MODE=true
```

### Code Change Detection

```bash
#!/bin/bash
# scripts/watch_changes.sh

# Monitor file changes and trigger rebuilds
inotifywait -m -r -e modify,create,delete \
    --include '\.(py|yml|yaml|json)$' \
    flows/ core/ scripts/ | while read path action file; do

    echo "Change detected: $path$file ($action)"

    # Determine which containers need rebuilding
    if [[ $path == *"flows/rpa1"* ]]; then
        echo "Rebuilding rpa-flow1..."
        docker-compose build rpa-flow1
        docker-compose up -d rpa-flow1
    elif [[ $path == *"flows/rpa2"* ]]; then
        echo "Rebuilding rpa-flow2..."
        docker-compose build rpa-flow2
        docker-compose up -d rpa-flow2
    elif [[ $path == *"flows/rpa3"* ]]; then
        echo "Rebuilding rpa-flow3..."
        docker-compose build rpa-flow3
        docker-compose up -d rpa-flow3
    elif [[ $path == *"core"* ]]; then
        echo "Core changes detected, rebuilding base image..."
        ./scripts/build_base_image.sh
        ./scripts/build_flow_images.sh
        docker-compose up -d
    fi

    # Run quick tests
    python core/test/run_container_tests.py --category smoke --quick
done
```

## Two-Stage Build Process

### Understanding the Build Architecture

The container system uses a two-stage build process for optimal development velocity:

```mermaid
graph TB
    subgraph "Stage 1: Base Image"
        A[System Dependencies] --> B[Python Environment]
        B --> C[Core Modules]
        C --> D[Monitoring Tools]
        D --> E[Security Setup]
    end

    subgraph "Stage 2: Flow Images"
        F[Base Image] --> G[Flow Code]
        G --> H[Flow Config]
        H --> I[Runtime Setup]
    end

    E --> F

    subgraph "Benefits"
        J[Fast Rebuilds]
        K[Cache Efficiency]
        L[Consistent Environment]
    end

    I --> J
    I --> K
    I --> L
```

### Base Image Development

```dockerfile
# Dockerfile.base
FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set up Python environment
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r requirements.txt

# Copy core modules
COPY core/ ./core/
COPY scripts/ ./scripts/

# Set up monitoring and health checks
COPY monitoring/ ./monitoring/
RUN chmod +x scripts/*.sh

# Security setup
USER appuser
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "-m", "core.health_server"]
```

### Flow Image Development

```dockerfile
# Dockerfile.flow1
FROM rpa-base:latest

# Copy flow-specific code
COPY flows/rpa1/ ./flows/rpa1/

# Set flow-specific environment
ENV CONTAINER_FLOW_NAME=rpa1
ENV CONTAINER_FLOW_PORT=8080

# Flow-specific health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start flow
CMD ["python", "flows/rpa1/workflow.py"]
```

### Build Optimization Strategies

```bash
# 1. Use build cache effectively
export DOCKER_BUILDKIT=1
docker build --cache-from rpa-base:latest -t rpa-base:new .

# 2. Parallel builds
docker build --parallel -f Dockerfile.base -t rpa-base .

# 3. Multi-platform builds (if needed)
docker buildx build --platform linux/amd64,linux/arm64 -t rpa-base .

# 4. Build with secrets (for private repositories)
docker build --secret id=pip_config,src=pip.conf -t rpa-base .
```

## Development Best Practices

### Code Organization

```
project/
├── core/                    # Shared core modules
│   ├── __init__.py
│   ├── config.py           # Configuration management
│   ├── database.py         # Database utilities
│   ├── container_config.py # Container-specific config
│   ├── health_monitor.py   # Health monitoring
│   └── test/               # Core tests
├── flows/                  # Flow-specific code
│   ├── rpa1/
│   │   ├── __init__.py
│   │   ├── workflow.py     # Main workflow logic
│   │   ├── .env.development
│   │   └── test/           # Flow-specific tests
│   ├── rpa2/
│   └── rpa3/
├── scripts/                # Build and utility scripts
├── docs/                   # Documentation
└── docker-compose*.yml    # Container orchestration
```

### Configuration Management

```python
# core/container_config.py
from dataclasses import dataclass
from typing import Dict, Optional
import os

@dataclass
class ContainerConfig:
    """Container configuration with validation"""
    flow_name: str
    environment: str
    database_urls: Dict[str, str]
    log_level: str = "INFO"
    debug_mode: bool = False

    @classmethod
    def from_environment(cls) -> 'ContainerConfig':
        """Load configuration from environment variables"""
        return cls(
            flow_name=os.getenv('CONTAINER_FLOW_NAME', ''),
            environment=os.getenv('CONTAINER_ENVIRONMENT', 'development'),
            database_urls={
                'rpa_db': os.getenv('CONTAINER_DATABASE_RPA_DB_URL', ''),
                'survey_hub': os.getenv('CONTAINER_DATABASE_SURVEY_HUB_URL', '')
            },
            log_level=os.getenv('CONTAINER_LOG_LEVEL', 'INFO'),
            debug_mode=os.getenv('CONTAINER_DEBUG_MODE', 'false').lower() == 'true'
        )

    def validate(self) -> bool:
        """Validate configuration"""
        if not self.flow_name:
            raise ValueError("CONTAINER_FLOW_NAME is required")

        for db_name, url in self.database_urls.items():
            if not url:
                raise ValueError(f"Database URL for {db_name} is required")

        return True
```

### Error Handling Patterns

```python
# core/error_handling.py
import logging
import functools
from typing import Callable, Any

logger = logging.getLogger(__name__)

def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """Decorator for retrying failed operations"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")

                    if attempt < max_attempts - 1:
                        time.sleep(delay * (2 ** attempt))  # Exponential backoff

            logger.error(f"All {max_attempts} attempts failed")
            raise last_exception

        return wrapper
    return decorator

class ContainerError(Exception):
    """Base exception for container-related errors"""
    pass

class ConfigurationError(ContainerError):
    """Configuration-related errors"""
    pass

class ServiceUnavailableError(ContainerError):
    """Service unavailability errors"""
    pass
```

### Logging Standards

```python
# core/logging_config.py
import logging
import json
import sys
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }

        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno',
                          'pathname', 'filename', 'module', 'lineno',
                          'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process',
                          'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value

        return json.dumps(log_entry)

def setup_logging(level: str = "INFO", format_type: str = "json"):
    """Set up logging configuration"""

    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(handler)

    return root_logger
```

## Testing Strategies

### Test Organization

```
core/test/
├── unit/                   # Unit tests
│   ├── test_config.py
│   ├── test_database.py
│   └── test_health_monitor.py
├── integration/            # Integration tests
│   ├── test_container_startup.py
│   ├── test_service_communication.py
│   └── test_database_integration.py
├── system/                 # System tests
│   ├── test_end_to_end.py
│   ├── test_performance.py
│   └── test_fault_tolerance.py
├── fixtures/               # Test fixtures
│   ├── test_data.py
│   └── mock_services.py
└── conftest.py            # Pytest configuration
```

### Unit Testing

```python
# core/test/unit/test_container_config.py
import pytest
import os
from unittest.mock import patch
from core.container_config import ContainerConfig, ConfigurationError

class TestContainerConfig:

    def test_from_environment_success(self):
        """Test successful configuration loading from environment"""
        env_vars = {
            'CONTAINER_FLOW_NAME': 'rpa1',
            'CONTAINER_ENVIRONMENT': 'development',
            'CONTAINER_DATABASE_RPA_DB_URL': 'postgresql://user:pass@host:5432/db',
            'CONTAINER_DATABASE_SURVEY_HUB_URL': 'postgresql://user:pass@host:5432/survey',
            'CONTAINER_LOG_LEVEL': 'DEBUG'
        }

        with patch.dict(os.environ, env_vars):
            config = ContainerConfig.from_environment()

            assert config.flow_name == 'rpa1'
            assert config.environment == 'development'
            assert config.log_level == 'DEBUG'
            assert 'rpa_db' in config.database_urls

    def test_validation_missing_flow_name(self):
        """Test validation failure with missing flow name"""
        config = ContainerConfig(
            flow_name='',
            environment='development',
            database_urls={'rpa_db': 'postgresql://user:pass@host:5432/db'}
        )

        with pytest.raises(ValueError, match="CONTAINER_FLOW_NAME is required"):
            config.validate()

    def test_validation_missing_database_url(self):
        """Test validation failure with missing database URL"""
        config = ContainerConfig(
            flow_name='rpa1',
            environment='development',
            database_urls={'rpa_db': ''}
        )

        with pytest.raises(ValueError, match="Database URL for rpa_db is required"):
            config.validate()
```

### Integration Testing

```python
# core/test/integration/test_container_startup.py
import pytest
import docker
import time
import requests
from core.test.fixtures.test_data import TestDataManager

class TestContainerStartup:

    @pytest.fixture(scope="class")
    def docker_client(self):
        """Docker client fixture"""
        return docker.from_env()

    @pytest.fixture(scope="class")
    def test_database(self):
        """Test database fixture"""
        test_data = TestDataManager()
        test_data.setup_test_database()
        yield test_data
        test_data.cleanup_test_database()

    def test_container_startup_sequence(self, docker_client, test_database):
        """Test proper container startup sequence"""

        # Start database first
        db_container = docker_client.containers.run(
            "postgres:15",
            environment={
                "POSTGRES_DB": "test_db",
                "POSTGRES_USER": "test_user",
                "POSTGRES_PASSWORD": "test_pass"
            },
            ports={'5432/tcp': 5433},
            detach=True,
            remove=True
        )

        # Wait for database to be ready
        self._wait_for_database_ready("localhost", 5433)

        # Start application container
        app_container = docker_client.containers.run(
            "rpa-flow1:latest",
            environment={
                "CONTAINER_FLOW_NAME": "rpa1",
                "CONTAINER_DATABASE_RPA_DB_URL": "postgresql://test_user:test_pass@host.docker.internal:5433/test_db"
            },
            ports={'8080/tcp': 8081},
            detach=True,
            remove=True
        )

        # Wait for application to be ready
        self._wait_for_health_check("http://localhost:8081/health")

        # Verify application is working
        response = requests.get("http://localhost:8081/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        # Cleanup
        app_container.stop()
        db_container.stop()

    def _wait_for_database_ready(self, host: str, port: int, timeout: int = 60):
        """Wait for database to be ready"""
        import psycopg2

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    user="test_user",
                    password="test_pass",
                    database="test_db"
                )
                conn.close()
                return
            except psycopg2.OperationalError:
                time.sleep(1)

        raise TimeoutError("Database did not become ready within timeout")

    def _wait_for_health_check(self, url: str, timeout: int = 60):
        """Wait for health check to pass"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(2)

        raise TimeoutError("Health check did not pass within timeout")
```

### Performance Testing

```python
# core/test/system/test_performance.py
import pytest
import time
import statistics
import concurrent.futures
from core.test.fixtures.test_data import TestDataManager

class TestPerformance:

    @pytest.fixture(scope="class")
    def performance_test_data(self):
        """Set up performance test data"""
        test_data = TestDataManager()
        test_data.create_performance_test_data(record_count=10000)
        yield test_data
        test_data.cleanup_performance_test_data()

    def test_processing_throughput(self, performance_test_data):
        """Test processing throughput meets requirements"""

        start_time = time.time()

        # Process records
        processed_count = self._process_test_records(performance_test_data)

        end_time = time.time()
        duration = end_time - start_time
        throughput = processed_count / duration

        # Assert throughput meets minimum requirement (100 records/second)
        assert throughput >= 100, f"Throughput {throughput:.2f} rps below minimum 100 rps"

    def test_concurrent_processing(self, performance_test_data):
        """Test concurrent processing performance"""

        def process_batch(batch_size: int) -> float:
            start_time = time.time()
            self._process_test_records(performance_test_data, limit=batch_size)
            return time.time() - start_time

        # Test different concurrency levels
        concurrency_levels = [1, 2, 4, 8]
        results = {}

        for concurrency in concurrency_levels:
            batch_size = 1000 // concurrency

            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(process_batch, batch_size) for _ in range(concurrency)]
                times = [future.result() for future in concurrent.futures.as_completed(futures)]

            avg_time = statistics.mean(times)
            throughput = (batch_size * concurrency) / avg_time
            results[concurrency] = throughput

        # Verify that concurrency improves performance
        assert results[4] > results[1], "Concurrency should improve performance"

    def test_memory_usage_stability(self, performance_test_data):
        """Test memory usage remains stable during processing"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Process multiple batches
        for i in range(10):
            self._process_test_records(performance_test_data, limit=1000)

            current_memory = process.memory_info().rss
            memory_growth = (current_memory - initial_memory) / initial_memory

            # Assert memory growth is reasonable (< 50%)
            assert memory_growth < 0.5, f"Memory growth {memory_growth:.2%} exceeds 50%"

    def _process_test_records(self, test_data: TestDataManager, limit: int = None) -> int:
        """Process test records and return count"""
        # Implementation would depend on your specific processing logic
        # This is a placeholder
        records = test_data.get_test_records(limit=limit)

        for record in records:
            # Simulate processing
            time.sleep(0.001)  # 1ms per record

        return len(records)
```

## Debugging Techniques

### Container Debugging

```bash
# 1. Access running container
docker exec -it rpa-flow1 /bin/bash

# 2. Check container logs
docker logs -f rpa-flow1

# 3. Monitor container resources
docker stats rpa-flow1

# 4. Inspect container configuration
docker inspect rpa-flow1

# 5. Check container processes
docker exec rpa-flow1 ps aux

# 6. Network debugging
docker exec rpa-flow1 netstat -tuln
docker exec rpa-flow1 ping postgres

# 7. File system debugging
docker exec rpa-flow1 ls -la /app
docker exec rpa-flow1 df -h
```

### Application Debugging

```python
# core/debug_utils.py
import logging
import pdb
import traceback
import sys
from typing import Any, Callable

logger = logging.getLogger(__name__)

def debug_on_error(func: Callable) -> Callable:
    """Decorator to start debugger on exception"""
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Exception in {func.__name__}: {e}")
            logger.error(traceback.format_exc())

            # Start debugger if in debug mode
            if os.getenv('CONTAINER_DEBUG_MODE', 'false').lower() == 'true':
                pdb.post_mortem()

            raise
    return wrapper

def log_function_calls(func: Callable) -> Callable:
    """Decorator to log function calls"""
    def wrapper(*args, **kwargs) -> Any:
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")

        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()

        logger.debug(f"{func.__name__} completed in {end_time - start_time:.3f}s")
        return result
    return wrapper

class DebugContext:
    """Context manager for debugging"""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        logger.debug(f"Entering debug context: {self.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        logger.debug(f"Exiting debug context: {self.name} (duration: {duration:.3f}s)")

        if exc_type:
            logger.error(f"Exception in {self.name}: {exc_val}")
            if os.getenv('CONTAINER_DEBUG_MODE', 'false').lower() == 'true':
                pdb.post_mortem(exc_tb)
```

### Remote Debugging

```python
# Enable remote debugging with debugpy
import debugpy

def setup_remote_debugging(port: int = 5678):
    """Set up remote debugging"""
    if os.getenv('CONTAINER_DEBUG_MODE', 'false').lower() == 'true':
        debugpy.listen(("0.0.0.0", port))
        print(f"Waiting for debugger to attach on port {port}...")
        debugpy.wait_for_client()
        print("Debugger attached!")

# In your main application
if __name__ == "__main__":
    setup_remote_debugging()
    # Your application code here
```

### Performance Profiling

```python
# core/profiling.py
import cProfile
import pstats
import io
from contextlib import contextmanager

@contextmanager
def profile_code(sort_by: str = 'cumulative', limit: int = 20):
    """Context manager for profiling code"""
    profiler = cProfile.Profile()
    profiler.enable()

    try:
        yield profiler
    finally:
        profiler.disable()

        # Print profile results
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats(sort_by)
        ps.print_stats(limit)

        print("Profile Results:")
        print(s.getvalue())

# Usage example
with profile_code():
    # Code to profile
    process_large_dataset()
```

## Performance Optimization

### Code Optimization Patterns

```python
# Efficient database operations
from contextlib import contextmanager
from typing import List, Dict, Any

@contextmanager
def database_batch_operation(db_manager):
    """Context manager for batch database operations"""
    connection = db_manager.get_connection()
    transaction = connection.begin()

    try:
        yield connection
        transaction.commit()
    except Exception:
        transaction.rollback()
        raise
    finally:
        connection.close()

def process_records_efficiently(records: List[Dict[str, Any]]):
    """Efficient record processing with batching"""
    batch_size = 1000

    with database_batch_operation(db_manager) as conn:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]

            # Prepare batch insert
            values = [(r['id'], r['data'], r['status']) for r in batch]

            # Execute batch insert
            conn.execute(
                "INSERT INTO processed_records (id, data, status) VALUES %s",
                values
            )

# Async processing for I/O operations
import asyncio
import aiohttp

async def process_records_async(records: List[Dict[str, Any]]):
    """Async processing for I/O-bound operations"""

    async def process_single_record(session, record):
        async with session.post('/api/process', json=record) as response:
            return await response.json()

    async with aiohttp.ClientSession() as session:
        tasks = [process_single_record(session, record) for record in records]
        results = await asyncio.gather(*tasks)
        return results

# Memory-efficient data processing
def process_large_dataset_efficiently(file_path: str):
    """Memory-efficient processing of large datasets"""

    def record_generator():
        with open(file_path, 'r') as f:
            for line in f:
                yield json.loads(line)

    # Process in chunks to manage memory
    chunk_size = 1000
    chunk = []

    for record in record_generator():
        chunk.append(record)

        if len(chunk) >= chunk_size:
            process_chunk(chunk)
            chunk = []  # Clear chunk to free memory

    # Process remaining records
    if chunk:
        process_chunk(chunk)
```

### Container Resource Optimization

```yaml
# Optimized container configuration
services:
  rpa-flow1:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "1.0"
          memory: 1G
    environment:
      # Python optimization
      - PYTHONUNBUFFERED=1
      - PYTHONHASHSEED=0
      - PYTHONDONTWRITEBYTECODE=1

      # Memory optimization
      - MALLOC_ARENA_MAX=2
      - MALLOC_MMAP_THRESHOLD_=131072

      # Application optimization
      - CONTAINER_WORKER_PROCESSES=4
      - CONTAINER_BATCH_SIZE=1000
      - CONTAINER_CONNECTION_POOL_SIZE=20
```

## Security Guidelines

### Container Security Best Practices

```dockerfile
# Security-focused Dockerfile
FROM python:3.11-slim

# Create non-root user early
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install security updates
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set secure file permissions
WORKDIR /app
COPY --chown=appuser:appuser . .

# Remove unnecessary files
RUN find /app -name "*.pyc" -delete \
    && find /app -name "__pycache__" -type d -exec rm -rf {} + \
    && rm -rf /app/.git /app/.pytest_cache

# Switch to non-root user
USER appuser

# Use specific port (not privileged)
EXPOSE 8080

# Health check with timeout
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1
```

### Secure Configuration Management

```python
# core/security.py
import os
import secrets
from cryptography.fernet import Fernet
from typing import Optional

class SecureConfigManager:
    """Secure configuration management"""

    def __init__(self):
        self.encryption_key = self._get_encryption_key()
        self.cipher = Fernet(self.encryption_key)

    def _get_encryption_key(self) -> bytes:
        """Get or generate encryption key"""
        key_file = os.getenv('CONTAINER_ENCRYPTION_KEY_FILE', '/run/secrets/encryption_key')

        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new key (for development only)
            key = Fernet.generate_key()
            print("WARNING: Using generated encryption key. Not suitable for production!")
            return key

    def encrypt_value(self, value: str) -> str:
        """Encrypt a configuration value"""
        return self.cipher.encrypt(value.encode()).decode()

    def decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a configuration value"""
        return self.cipher.decrypt(encrypted_value.encode()).decode()

    def get_secure_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get configuration value, decrypting if necessary"""
        value = os.getenv(key, default)

        if value and value.startswith('encrypted:'):
            encrypted_data = value[10:]  # Remove 'encrypted:' prefix
            return self.decrypt_value(encrypted_data)

        return value

# Usage example
secure_config = SecureConfigManager()
database_password = secure_config.get_secure_config('CONTAINER_DATABASE_PASSWORD')
```

### Input Validation

```python
# core/validation.py
import re
from typing import Any, Dict, List
from dataclasses import dataclass

@dataclass
class ValidationRule:
    """Validation rule definition"""
    field: str
    required: bool = True
    pattern: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    allowed_values: Optional[List[str]] = None

class InputValidator:
    """Input validation utility"""

    def __init__(self, rules: List[ValidationRule]):
        self.rules = {rule.field: rule for rule in rules}

    def validate(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate input data and return errors"""
        errors = {}

        for field, rule in self.rules.items():
            field_errors = []
            value = data.get(field)

            # Check required fields
            if rule.required and (value is None or value == ''):
                field_errors.append(f"{field} is required")
                continue

            if value is not None:
                str_value = str(value)

                # Check length constraints
                if rule.min_length and len(str_value) < rule.min_length:
                    field_errors.append(f"{field} must be at least {rule.min_length} characters")

                if rule.max_length and len(str_value) > rule.max_length:
                    field_errors.append(f"{field} must be at most {rule.max_length} characters")

                # Check pattern
                if rule.pattern and not re.match(rule.pattern, str_value):
                    field_errors.append(f"{field} format is invalid")

                # Check allowed values
                if rule.allowed_values and str_value not in rule.allowed_values:
                    field_errors.append(f"{field} must be one of: {', '.join(rule.allowed_values)}")

            if field_errors:
                errors[field] = field_errors

        return errors

# Usage example
validator = InputValidator([
    ValidationRule('flow_name', required=True, pattern=r'^[a-zA-Z0-9_-]+$'),
    ValidationRule('environment', required=True, allowed_values=['development', 'staging', 'production']),
    ValidationRule('database_url', required=True, pattern=r'^postgresql://.*'),
])

errors = validator.validate(input_data)
if errors:
    raise ValueError(f"Validation errors: {errors}")
```

## Code Quality Standards

### Code Formatting and Linting

```bash
# Install development tools
uv pip install black flake8 mypy isort pytest-cov

# Format code
black core/ flows/ scripts/

# Sort imports
isort core/ flows/ scripts/

# Lint code
flake8 core/ flows/ scripts/

# Type checking
mypy core/ flows/

# Run tests with coverage
pytest --cov=core --cov-report=html core/test/
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args: [core/test/unit/]
```

### Documentation Standards

```python
def process_records(
    records: List[Dict[str, Any]],
    batch_size: int = 1000,
    validate_input: bool = True
) -> ProcessingResult:
    """
    Process a list of records with optional batching and validation.

    This function processes records in batches to optimize memory usage
    and database performance. Each record is validated before processing
    if validation is enabled.

    Args:
        records: List of record dictionaries to process
        batch_size: Number of records to process in each batch (default: 1000)
        validate_input: Whether to validate input records (default: True)

    Returns:
        ProcessingResult: Object containing processing statistics and results

    Raises:
        ValueError: If records list is empty or batch_size is invalid
        ValidationError: If input validation fails
        DatabaseError: If database operations fail

    Example:
        >>> records = [{'id': 1, 'data': 'test'}]
        >>> result = process_records(records, batch_size=500)
        >>> print(f"Processed {result.success_count} records")
    """
```

## Troubleshooting Common Issues

### Build Issues

```bash
# Clear Docker cache
docker builder prune -a

# Rebuild without cache
docker build --no-cache -f Dockerfile.base -t rpa-base .

# Check for dependency conflicts
uv pip check

# Verify Python version
python --version
```

### Runtime Issues

```bash
# Check container logs
docker logs -f rpa-flow1

# Check resource usage
docker stats rpa-flow1

# Test database connectivity
docker exec rpa-flow1 python -c "
from core.database import get_database_manager
db = get_database_manager()
print('Database connection:', db.test_connection())
"

# Check environment variables
docker exec rpa-flow1 env | grep CONTAINER_
```

### Performance Issues

```bash
# Profile application
docker exec rpa-flow1 python -m cProfile -o profile.stats flows/rpa1/workflow.py

# Monitor memory usage
docker exec rpa-flow1 python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print('Memory usage:', process.memory_info())
"

# Check database performance
docker exec postgres psql -U postgres -c "
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;
"
```

## Best Practices Summary

1. **Follow the two-stage build process** for optimal development velocity
2. **Use structured logging** with JSON format for better observability
3. **Implement comprehensive error handling** with proper retry logic
4. **Write thorough tests** at unit, integration, and system levels
5. **Use configuration validation** to catch issues early
6. **Follow security best practices** for container and application security
7. **Monitor performance continuously** and optimize proactively
8. **Document code thoroughly** with clear examples and usage patterns
9. **Use consistent code formatting** and quality tools
10. **Test in container environments** that match production

For additional development support:

- [Container Testing System Documentation](CONTAINER_TESTING_SYSTEM.md)
- [Troubleshooting Guide](CONTAINER_TROUBLESHOOTING_GUIDE.md)
- [Performance Tuning Guide](CONTAINER_PERFORMANCE_TUNING.md)
- [Operational Runbooks](CONTAINER_OPERATIONAL_RUNBOOKS.md)
