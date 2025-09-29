# Docker Compose Container Testing System

This document provides comprehensive instructions for setting up and managing the container testing environment using Docker Compose.

## Overview

The Docker Compose orchestration provides:

- **PostgreSQL Database**: Primary database for RPA processing
- **External SurveyHub Integration**: Connection to external SQL Server database
- **Prefect Server**: Workflow orchestration and monitoring
- **RPA Flow Workers**: Containerized flow execution (RPA1, RPA2, RPA3)
- **Health Monitoring**: Comprehensive health checks and metrics
- **Development Tools**: Hot reloading, debugging, and testing support

## Quick Start

### 1. Initial Setup

```bash
# Run the setup script to initialize the environment
./scripts/setup_docker_environment.sh

# Review and modify environment variables if needed
nano .env
```

### 2. Start Services

```bash
# Start basic services
./scripts/manage_containers.sh start

# Or use docker-compose directly
docker-compose up -d
```

### 3. Check Status

```bash
# Check service status
./scripts/manage_containers.sh status

# Check health
./scripts/manage_containers.sh health
```

## Service Architecture

### Core Services

| Service        | Port | Description                       |
| -------------- | ---- | --------------------------------- |
| postgres       | 5432 | Primary PostgreSQL database       |
| prefect-server | 4200 | Prefect workflow server           |
| rpa1-worker    | -    | RPA1 file processing worker       |
| rpa2-worker    | -    | RPA2 data validation worker       |
| rpa3-worker    | -    | RPA3 concurrent processing worker |

### Optional Services (Profiles)

| Profile      | Services      | Description                             |
| ------------ | ------------- | --------------------------------------- |
| load-testing | rpa1-worker-2 | Additional RPA1 worker for load testing |
| monitoring   | prometheus    | Prometheus monitoring stack             |
| debug        | All workers   | Debug mode with remote debugging        |
| testing      | test-runner   | Automated test execution                |

## Configuration

### Environment Variables

The system uses environment variables for configuration. Key variables include:

```bash
# Database Configuration
POSTGRES_PASSWORD=rpa_dev_password_secure_123
PREFECT_DB_PASSWORD=prefect_dev_password_secure_789

# External SurveyHub Database (SQL Server)
SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://username:password@server:port/database?driver=ODBC+Driver+17+for+SQL+Server

# Flow Configuration
RPA1_BATCH_SIZE=25
RPA2_BATCH_SIZE=75
RPA3_BATCH_SIZE=150

# Resource Limits
CONTAINER_MEMORY_LIMIT_RPA1=512M
CONTAINER_CPU_LIMIT_RPA1=0.5
```

### Container-Specific Configuration

Each container uses the `CONTAINER_` prefix for environment variables:

- `CONTAINER_ENVIRONMENT`: Environment name (development/staging/production)
- `CONTAINER_FLOW_NAME`: Flow identifier
- `CONTAINER_RPA_DB_CONNECTION_STRING`: Database connection string
- `CONTAINER_SURVEYHUB_CONNECTION_STRING`: External SurveyHub SQL Server connection string
- `CONTAINER_PREFECT_API_URL`: Prefect server API URL

### External SurveyHub Configuration

The SurveyHub database is an external SQL Server instance. Configure the connection string in your environment:

```bash
# Example SurveyHub connection string for SQL Server
SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://username:password@server:port/database?driver=ODBC+Driver+17+for+SQL+Server

# For development/testing, you can leave it empty to skip SurveyHub operations
SURVEYHUB_CONNECTION_STRING=
```

**Note**: The containers will handle missing SurveyHub connections gracefully, allowing development and testing without requiring access to the external SQL Server.

## Service Dependencies

The system implements proper service dependencies:

```mermaid
graph TB
    postgres[PostgreSQL]
    surveyhub[External SurveyHub SQL Server]
    prefect[Prefect Server]
    rpa1[RPA1 Worker]
    rpa2[RPA2 Worker]
    rpa3[RPA3 Worker]

    postgres --> prefect
    postgres --> rpa1
    postgres --> rpa2
    postgres --> rpa3
    surveyhub -.-> rpa1
    surveyhub -.-> rpa2
    surveyhub -.-> rpa3
    prefect --> rpa1
    prefect --> rpa2
    prefect --> rpa3
```

## Health Checks

All services include comprehensive health checks:

### Database Health Checks

- Connection validation
- Query response time
- Connection pool status

### Application Health Checks

- Flow-specific validation
- Configuration verification
- Dependency connectivity

### Resource Health Checks

- Memory usage monitoring
- CPU utilization tracking
- Disk space validation

## Volume Management

### Persistent Volumes

| Volume          | Purpose             | Location          |
| --------------- | ------------------- | ----------------- |
| postgres_data   | PostgreSQL data     | ./data/postgres   |
| prefect_data    | Prefect server data | ./data/prefect    |
| prometheus_data | Monitoring data     | ./data/prometheus |

### Development Volumes

| Volume      | Purpose           | Location                         |
| ----------- | ----------------- | -------------------------------- |
| Flow data   | Input/output data | ./flows/_/data, ./flows/_/output |
| Logs        | Service logs      | ./logs/\*                        |
| Source code | Hot reloading     | ./core, ./flows/\*               |

## Network Configuration

The system uses a custom bridge network (`rpa-network`) with:

- **Subnet**: 172.20.0.0/16
- **Service Discovery**: Automatic DNS resolution between services
- **Isolation**: Network isolation from other Docker networks
- **Communication**: Inter-service communication on internal network

## Management Commands

### Basic Operations

```bash
# Start services
./scripts/manage_containers.sh start

# Stop services
./scripts/manage_containers.sh stop

# Restart services
./scripts/manage_containers.sh restart

# Check status
./scripts/manage_containers.sh status

# View logs
./scripts/manage_containers.sh logs [service]
```

### Development Operations

```bash
# Start with monitoring
./scripts/manage_containers.sh start monitoring

# Start in debug mode
./scripts/manage_containers.sh debug rpa1-worker

# Open shell in container
./scripts/manage_containers.sh shell rpa1-worker

# Execute command in container
./scripts/manage_containers.sh exec rpa1-worker python --version
```

### Maintenance Operations

```bash
# Rebuild images
./scripts/manage_containers.sh build

# Rebuild specific service
./scripts/manage_containers.sh rebuild rpa1-worker

# Clean environment
./scripts/manage_containers.sh clean

# Reset entire environment
./scripts/manage_containers.sh reset
```

## Development Workflow

### Hot Reloading

Development mode supports hot reloading:

1. Start services in development mode
2. Modify source code in `./core` or `./flows/*`
3. Changes are automatically reflected in containers

### Debugging

Debug mode provides remote debugging capabilities:

```bash
# Start service in debug mode
./scripts/manage_containers.sh debug rpa1-worker

# Connect debugger to localhost:5678 (RPA1)
# Connect debugger to localhost:5679 (RPA2)
# Connect debugger to localhost:5680 (RPA3)
```

### Testing

Run automated tests in containerized environment:

```bash
# Run all tests
./scripts/manage_containers.sh test

# Run specific test category
docker-compose --profile testing exec test-runner python -m pytest core/test/test_distributed.py -v
```

## Monitoring and Observability

### Prometheus Metrics

When using the monitoring profile:

- **Prometheus UI**: http://localhost:9090
- **Metrics Endpoint**: Each service exposes metrics on port 8000
- **Health Endpoint**: Each service exposes health on port 8080

### Log Aggregation

Logs are collected in structured JSON format:

```bash
# View aggregated logs
./scripts/manage_containers.sh logs

# View specific service logs
./scripts/manage_containers.sh logs rpa1-worker

# Follow logs in real-time
docker-compose logs -f rpa1-worker
```

## Troubleshooting

### Common Issues

#### Services Won't Start

```bash
# Check Docker daemon
docker info

# Check configuration
docker-compose config

# Check resource availability
docker system df
```

#### Database Connection Issues

```bash
# Check database health
./scripts/manage_containers.sh health

# Check database logs
./scripts/manage_containers.sh logs postgres

# Test database connection
docker-compose exec postgres psql -U rpa_user -d rpa_db -c "SELECT 1;"
```

#### Performance Issues

```bash
# Check resource usage
docker stats

# Check container health
./scripts/manage_containers.sh health

# Review monitoring metrics
# Open http://localhost:9090 (if monitoring profile is active)
```

### Health Check Failures

```bash
# Check specific service health
docker-compose exec rpa1-worker python /app/scripts/health_check.py --flow=rpa1

# Check service logs for errors
./scripts/manage_containers.sh logs rpa1-worker

# Restart unhealthy service
./scripts/manage_containers.sh restart rpa1-worker
```

## Security Considerations

### Container Security

- **Non-root execution**: All application containers run as non-root user (uid 1000)
- **Resource limits**: CPU and memory limits prevent resource exhaustion
- **Network isolation**: Services communicate on isolated network
- **Secret management**: Sensitive data managed through environment variables

### Database Security

- **Authentication**: SCRAM-SHA-256 authentication for PostgreSQL
- **Network access**: Database access restricted to container network
- **Data encryption**: Connections use encrypted protocols where possible

## Production Considerations

### Resource Allocation

Adjust resource limits based on workload:

```yaml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: "1.0"
    reservations:
      memory: 512M
      cpus: "0.5"
```

### Scaling

Scale services horizontally:

```bash
# Scale RPA1 workers
docker-compose up -d --scale rpa1-worker=3

# Use load-testing profile for additional workers
docker-compose --profile load-testing up -d
```

### Backup and Recovery

```bash
# Backup PostgreSQL data
docker-compose exec postgres pg_dump -U rpa_user rpa_db > backup.sql

# Backup volumes
docker run --rm -v rpa_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
```

## Integration with CI/CD

### Automated Testing

```bash
# Run in CI environment
docker-compose --profile testing up -d
docker-compose exec test-runner python -m pytest --junitxml=test-results.xml
docker-compose down -v
```

### Image Building

```bash
# Build and tag images for registry
docker build -f Dockerfile.base -t registry.example.com/rpa-base:${VERSION} .
docker build -f Dockerfile.flow1 -t registry.example.com/rpa-flow1:${VERSION} .
```

This Docker Compose setup provides a robust, scalable, and maintainable container testing environment that supports development, testing, and production deployment scenarios.
