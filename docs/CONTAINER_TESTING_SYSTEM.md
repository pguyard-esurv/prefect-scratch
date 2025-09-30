# Container Testing System Documentation

## Overview

The Container Testing System provides a robust, production-ready testing framework for distributed processing workflows. It implements a two-stage build process, comprehensive health monitoring, automated validation, and operational management capabilities.

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Architecture](#system-architecture)
3. [Setup and Installation](#setup-and-installation)
4. [Configuration Management](#configuration-management)
5. [Development Workflow](#development-workflow)
6. [Testing Framework](#testing-framework)
7. [Monitoring and Health Checks](#monitoring-and-health-checks)
8. [Security Configuration](#security-configuration)
9. [Performance Optimization](#performance-optimization)
10. [Troubleshooting](#troubleshooting)

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ with uv package manager
- PostgreSQL database access
- Prefect server (optional for local development)

### Basic Setup

1. **Build the base image:**

   ```bash
   ./scripts/build_base_image.sh
   ```

2. **Build flow images:**

   ```bash
   ./scripts/build_flow_images.sh
   ```

3. **Start the system:**

   ```bash
   docker-compose up -d
   ```

4. **Run tests:**
   ```bash
   python core/test/run_container_tests.py
   ```

## System Architecture

### Two-Stage Build Process

The system uses a two-stage build approach for optimal performance:

**Stage 1: Base Image (`rpa-base`)**

- System dependencies (gcc, curl, etc.)
- Python environment with uv
- Core modules from `core/` directory
- Monitoring and health check tools
- Non-root user security setup

**Stage 2: Flow Images**

- Built FROM the base image
- Contains only flow-specific code
- Rapid rebuild capability
- Minimal layer additions

### Container Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RPA1 Worker   │    │   RPA2 Worker   │    │   RPA3 Worker   │
│                 │    │                 │    │                 │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Flow Logic  │ │    │ │ Flow Logic  │ │    │ │ Flow Logic  │ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │ Base Image  │ │    │ │ Base Image  │ │    │ │ Base Image  │ │
│ │ - Core      │ │    │ │ - Core      │ │    │ │ - Core      │ │
│ │ - Health    │ │    │ │ - Health    │ │    │ │ - Health    │ │
│ │ - Monitoring│ │    │ │ - Monitoring│ │    │ │ - Monitoring│ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   Database      │
                    └─────────────────┘
```

## Setup and Installation

### Environment Configuration

1. **Create environment files:**

   ```bash
   # Copy example files
   cp flows/rpa1/.env.development.example flows/rpa1/.env.development
   cp flows/rpa2/.env.development.example flows/rpa2/.env.development
   cp flows/rpa3/.env.development.example flows/rpa3/.env.development
   ```

2. **Configure database connections:**

   ```bash
   # Set database URLs in environment files
   CONTAINER_DATABASE_RPA_DB_URL=postgresql://user:pass@postgres:5432/rpa_db
   CONTAINER_DATABASE_SURVEY_HUB_URL=postgresql://user:pass@postgres:5432/survey_hub
   ```

3. **Set container-specific variables:**
   ```bash
   CONTAINER_FLOW_NAME=rpa1
   CONTAINER_ENVIRONMENT=development
   CONTAINER_LOG_LEVEL=INFO
   ```

### Build Process

#### Manual Build

```bash
# Build base image
docker build -f Dockerfile.base -t rpa-base:latest .

# Build flow images
docker build -f Dockerfile.flow1 -t rpa-flow1:latest .
docker build -f Dockerfile.flow2 -t rpa-flow2:latest .
docker build -f Dockerfile.flow3 -t rpa-flow3:latest .
```

#### Automated Build

```bash
# Build all images with optimization
./scripts/build_all.sh

# Selective rebuild based on changes
./scripts/selective_rebuild.sh
```

### Docker Compose Setup

The system includes multiple Docker Compose configurations:

- `docker-compose.yml` - Production configuration
- `docker-compose.override.yml` - Development overrides
- `docker-compose.error-recovery.yml` - Error recovery testing

## Configuration Management

### Environment Variable Mapping

The system automatically maps `CONTAINER_` prefixed variables:

```bash
CONTAINER_DATABASE_RPA_DB_URL → config.database.rpa_db.url
CONTAINER_FLOW_NAME → config.flow.name
CONTAINER_LOG_LEVEL → config.logging.level
```

### Configuration Validation

All configurations are validated at startup:

```python
# Example configuration validation
from core.container_config import ContainerConfigManager

config_manager = ContainerConfigManager()
if not config_manager.validate_container_environment():
    raise ConfigurationError("Invalid container configuration")
```

### Service Dependencies

Containers automatically wait for dependencies:

- Database connectivity validation
- Prefect server health checks
- External service availability

## Development Workflow

### Hot Reloading

Development mode supports hot reloading:

```bash
# Start with development overrides
docker-compose -f docker-compose.yml -f docker-compose.override.yml up

# Code changes automatically reload containers
```

### Debugging Access

Access container internals for debugging:

```bash
# Execute shell in running container
docker exec -it rpa-flow1 /bin/bash

# View logs
docker logs -f rpa-flow1

# Access database
docker exec -it postgres psql -U postgres -d rpa_db
```

### Fast Iteration Cycle

1. **Code Change Detection:**

   ```bash
   # Automatic detection and rebuild
   ./scripts/selective_rebuild.sh
   ```

2. **Targeted Testing:**

   ```bash
   # Test specific flow
   python core/test/run_container_tests.py --flow rpa1
   ```

3. **Performance Feedback:**
   ```bash
   # Quick performance check
   python scripts/build_performance_monitor.py
   ```

## Testing Framework

### Test Categories

1. **Unit Tests** - Component validation
2. **Integration Tests** - Service interaction
3. **System Tests** - End-to-end workflows
4. **Performance Tests** - Load and throughput
5. **Chaos Tests** - Failure scenarios

### Running Tests

```bash
# Complete test suite
python core/test/run_container_tests.py

# Specific test categories
python core/test/run_container_tests.py --category integration
python core/test/run_container_tests.py --category performance

# Distributed processing validation
python core/test/run_distributed_comprehensive_tests.py
```

### Test Configuration

```json
{
  "test_config": {
    "database_reset": true,
    "parallel_execution": true,
    "performance_thresholds": {
      "processing_rate": 100,
      "error_rate": 0.01
    }
  }
}
```

## Monitoring and Health Checks

### Health Endpoints

Each container exposes health endpoints:

```bash
# Container health
curl http://localhost:8080/health

# Detailed health information
curl http://localhost:8080/health/detailed
```

### Metrics Export

Prometheus-compatible metrics:

```bash
# Metrics endpoint
curl http://localhost:8080/metrics
```

### Structured Logging

JSON-formatted logs for aggregation:

```json
{
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "INFO",
  "service": "rpa1",
  "message": "Processing completed",
  "metrics": {
    "records_processed": 100,
    "duration_ms": 1500
  }
}
```

## Security Configuration

### Non-Root Execution

All containers run as non-root users:

```dockerfile
# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser
```

### Secret Management

Secure handling of sensitive configuration:

```bash
# Use Docker secrets
docker secret create db_password /path/to/password.txt

# Environment variable injection
CONTAINER_DATABASE_PASSWORD_FILE=/run/secrets/db_password
```

### Network Security

Container network isolation:

```yaml
# docker-compose.yml
networks:
  app-network:
    driver: bridge
    internal: true
  db-network:
    driver: bridge
```

## Performance Optimization

### Resource Limits

Configure appropriate resource limits:

```yaml
# docker-compose.yml
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
```

### Connection Pooling

Optimize database connections:

```python
# Database configuration
DATABASE_CONFIG = {
    "pool_size": 20,
    "max_overflow": 30,
    "pool_timeout": 30,
    "pool_recycle": 3600
}
```

### Build Optimization

Maximize build cache efficiency:

```bash
# Layer caching optimization
./scripts/build_cache_manager.sh

# Multi-stage build benefits
docker build --target base -t rpa-base .
docker build --target flow1 -t rpa-flow1 .
```

## Troubleshooting

### Common Issues

1. **Container Startup Failures**

   - Check environment variable configuration
   - Verify database connectivity
   - Review dependency health

2. **Performance Issues**

   - Monitor resource usage
   - Check connection pool settings
   - Analyze processing bottlenecks

3. **Test Failures**
   - Verify test data setup
   - Check service dependencies
   - Review error logs

### Diagnostic Commands

```bash
# System health check
docker-compose ps
docker-compose logs

# Resource usage
docker stats

# Network connectivity
docker network ls
docker network inspect <network_name>

# Database connectivity
docker exec postgres pg_isready
```

### Log Analysis

```bash
# Structured log analysis
docker logs rpa-flow1 | jq '.level == "ERROR"'

# Performance metrics
docker logs rpa-flow1 | jq '.metrics.processing_rate'

# Error patterns
docker logs rpa-flow1 | grep -E "(ERROR|FATAL)"
```

## Best Practices

### Development

1. **Use development overrides** for local development
2. **Implement proper health checks** for all services
3. **Follow the two-stage build process** for efficiency
4. **Use structured logging** for better observability
5. **Implement graceful shutdown** handling

### Testing

1. **Run tests in isolated environments**
2. **Use realistic test data**
3. **Validate distributed processing behavior**
4. **Monitor performance metrics**
5. **Test failure scenarios**

### Operations

1. **Monitor resource usage** continuously
2. **Implement proper alerting**
3. **Use rolling deployments**
4. **Maintain configuration validation**
5. **Plan for disaster recovery**

## Next Steps

1. Review the [Troubleshooting Guide](CONTAINER_TROUBLESHOOTING_GUIDE.md)
2. Check [Performance Tuning Guide](CONTAINER_PERFORMANCE_TUNING.md)
3. Read [Operational Runbooks](CONTAINER_OPERATIONAL_RUNBOOKS.md)
4. Follow [Developer Best Practices](CONTAINER_DEVELOPMENT_GUIDE.md)

For additional support, refer to the specific guides mentioned above or contact the development team.
