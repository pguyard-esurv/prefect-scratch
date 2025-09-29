# Container Lifecycle Management System

## Overview

The Container Lifecycle Management System provides comprehensive container startup validation, dependency checking, graceful shutdown handling, restart policies, health monitoring, and automatic remediation for the distributed processing framework.

## Architecture

### Core Components

1. **ContainerLifecycleManager**: Main orchestrator for container lifecycle
2. **EnhancedContainerStartup**: High-level startup script with lifecycle integration
3. **Dependency Checking**: Configurable dependency validation system
4. **Health Monitoring**: Continuous health monitoring with automatic remediation
5. **Restart Policies**: Configurable restart behavior with exponential backoff
6. **Graceful Shutdown**: Proper cleanup and resource management

### Lifecycle States

```
INITIALIZING → STARTING → RUNNING → STOPPING → STOPPED
                    ↓         ↓
                 FAILED → RESTARTING
```

## Features

### 1. Startup Validation

Comprehensive validation of container environment before startup:

- **Environment Variables**: Validates required configuration
- **Flow Name Consistency**: Ensures container matches expected flow
- **Configuration Loading**: Validates configuration file accessibility
- **Directory Structure**: Creates and validates required directories
- **Resource Limits**: Validates memory and CPU constraints
- **Disk Space**: Ensures sufficient disk space for operation

### 2. Dependency Checking

Configurable dependency validation with retry logic:

- **Database Connectivity**: Validates database connections with health checks
- **Service Dependencies**: Checks external service availability
- **Flow-Specific Dependencies**: Custom dependency checks per flow
- **Timeout and Retry**: Configurable timeout and retry intervals
- **Required vs Optional**: Distinguishes between critical and optional dependencies

### 3. Health Monitoring

Continuous health monitoring with automatic remediation:

- **Comprehensive Health Checks**: Database, application, and resource monitoring
- **Failure Detection**: Configurable failure thresholds
- **Automatic Remediation**: Memory cleanup, connection restart, disk cleanup
- **Metrics Export**: Prometheus-compatible metrics
- **Structured Logging**: JSON-formatted logs for aggregation

### 4. Restart Policies

Flexible restart policies with intelligent backoff:

- **Policy Types**: NO, ALWAYS, ON_FAILURE, UNLESS_STOPPED
- **Attempt Limits**: Configurable maximum restart attempts
- **Exponential Backoff**: Intelligent delay calculation
- **Restart Windows**: Time-based restart count reset
- **Failure Recovery**: Automatic recovery from transient failures

### 5. Graceful Shutdown

Proper cleanup and resource management:

- **Signal Handling**: SIGTERM and SIGINT signal processing
- **Cleanup Handlers**: Configurable cleanup operations
- **Timeout Management**: Graceful vs forced shutdown
- **Resource Cleanup**: Memory, files, connections, and temporary data
- **Final Metrics**: Export lifecycle metrics on shutdown

## Configuration

### Environment Variables

#### Core Configuration

```bash
# Flow identification
CONTAINER_FLOW_NAME=rpa1
CONTAINER_ENVIRONMENT=production
CONTAINER_WORKER_ID=rpa1-worker-1

# Database connections
CONTAINER_RPA_DB_CONNECTION_STRING=postgresql://user:pass@host:5432/db
CONTAINER_DATABASE_SURVEY_HUB_HOST=surveyhub.example.com

# Prefect configuration
CONTAINER_PREFECT_API_URL=http://prefect-server:4200/api
CONTAINER_PREFECT_SERVER_URL=http://prefect-server:4200

# Resource limits
CONTAINER_MAX_MEMORY_MB=512
CONTAINER_MAX_CPU_PERCENT=50
```

#### Execution Configuration

```bash
# Execution mode: daemon, single, server
CONTAINER_EXECUTION_MODE=daemon
CONTAINER_EXECUTION_INTERVAL=300

# Restart policy configuration
CONTAINER_RESTART_POLICY=on-failure
CONTAINER_MAX_RESTART_ATTEMPTS=5
CONTAINER_RESTART_DELAY_SECONDS=10
CONTAINER_RESTART_EXPONENTIAL_BACKOFF=true
CONTAINER_MAX_RESTART_DELAY_SECONDS=300
CONTAINER_RESTART_WINDOW_MINUTES=60
```

#### Flow-Specific Configuration

```bash
# RPA1 specific
CONTAINER_RPA1_BATCH_SIZE=25
CONTAINER_RPA1_MAX_RETRIES=3
CONTAINER_RPA1_TIMEOUT=300

# RPA2 specific
CONTAINER_RPA2_BATCH_SIZE=75
CONTAINER_RPA2_VALIDATION_ENDPOINT=http://validation-service:8080/validate

# RPA3 specific
CONTAINER_RPA3_CONCURRENT_WORKERS=4
CONTAINER_RPA3_BATCH_SIZE=150
```

## Usage

### Basic Usage

```python
from core.container_lifecycle_manager import ContainerLifecycleManager
from core.container_config import ContainerConfigManager

# Initialize lifecycle manager
config_manager = ContainerConfigManager("rpa1")
lifecycle_manager = ContainerLifecycleManager(
    container_id="rpa1-worker-1",
    flow_name="rpa1",
    config_manager=config_manager
)

# Perform startup
if lifecycle_manager.startup():
    print("Container started successfully")

    # Run application logic here

    # Graceful shutdown
    lifecycle_manager.graceful_shutdown()
else:
    print("Container startup failed")
```

### Enhanced Startup Script

```bash
# Run with lifecycle management and restart handling
python scripts/container_lifecycle_startup.py \
    --flow-name rpa1 \
    --mode managed \
    --log-level INFO

# Run with basic lifecycle management (no restart handling)
python scripts/container_lifecycle_startup.py \
    --flow-name rpa1 \
    --mode simple \
    --log-level DEBUG
```

### Docker Integration

```dockerfile
# Use enhanced lifecycle startup in Dockerfile
CMD ["python", "/app/scripts/container_lifecycle_startup.py", "--flow-name", "rpa1", "--mode", "managed"]
```

### Custom Dependency Checks

```python
from core.container_lifecycle_manager import DependencyCheck

# Add custom dependency check
def check_custom_service():
    # Custom validation logic
    return True

lifecycle_manager.add_dependency_check(DependencyCheck(
    name="custom_service",
    check_function=check_custom_service,
    timeout_seconds=30,
    required=True,
    description="Custom service dependency"
))
```

### Custom Cleanup Handlers

```python
def custom_cleanup():
    # Custom cleanup logic
    print("Performing custom cleanup")

lifecycle_manager.add_cleanup_handler(custom_cleanup)
```

## Flow-Specific Configurations

### RPA1 (File Processing)

**Dependencies:**

- RPA database (required)
- Input directory accessibility (required)
- Prefect server (optional)

**Cleanup:**

- File handle closure
- Output directory sync
- Temporary file cleanup

**Resource Requirements:**

- Memory: 512MB
- CPU: 50%
- Disk: Input/output directories

### RPA2 (Data Validation)

**Dependencies:**

- RPA database (required)
- Validation service endpoint (optional)
- Prefect server (optional)

**Cleanup:**

- Validation cache cleanup
- Temporary processing files
- Connection pool cleanup

**Resource Requirements:**

- Memory: 384MB
- CPU: 40%
- Disk: Validation cache

### RPA3 (Concurrent Processing)

**Dependencies:**

- RPA database (required)
- Concurrent processing resources (required)
- Prefect server (optional)

**Cleanup:**

- Worker thread termination
- Shared memory cleanup
- Processing queue cleanup

**Resource Requirements:**

- Memory: 768MB
- CPU: 75%
- Disk: Processing temporary files

## Health Monitoring

### Health Check Types

1. **Database Health**: Connection, query performance, pool status
2. **Application Health**: Environment, dependencies, resource usage
3. **Resource Health**: CPU, memory, disk, network connections

### Remediation Actions

1. **Memory Cleanup**: Garbage collection, cache clearing
2. **Database Connection Restart**: Connection pool reset
3. **Disk Cleanup**: Temporary file removal, log rotation
4. **Service Restart**: Container restart for critical failures

### Metrics Export

```json
{
  "container_health_status": 1,
  "database_response_time_ms": 45.2,
  "memory_usage_percent": 67.3,
  "cpu_usage_percent": 23.1,
  "disk_usage_percent": 45.8,
  "health_check_failures": 0,
  "restart_count": 2,
  "uptime_seconds": 3600
}
```

## Restart Policies

### Policy Types

1. **NO**: Never restart containers
2. **ALWAYS**: Always restart containers regardless of exit status
3. **ON_FAILURE**: Restart only on failure (non-zero exit)
4. **UNLESS_STOPPED**: Restart unless explicitly stopped

### Restart Logic

```python
# Exponential backoff calculation
delay = base_delay * (2 ** min(restart_count, 5))
delay = min(delay, max_delay_seconds)

# Restart window management
if time_since_last_restart > restart_window:
    restart_count = 0  # Reset count outside window
```

## Monitoring and Observability

### Structured Logging

All lifecycle events are logged in structured JSON format:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "component": "lifecycle_manager",
  "container_id": "rpa1-worker-1",
  "flow": "rpa1",
  "event": "startup_completed",
  "duration_ms": 2500,
  "details": {
    "validation_checks": 6,
    "dependencies_checked": 3,
    "health_status": "healthy"
  }
}
```

### Lifecycle Events

- `startup_initiated`: Container startup process begins
- `dependencies_ready`: All dependencies are available
- `startup_completed`: Container startup successful
- `health_check_passed`: Health check successful
- `health_check_failed`: Health check failed
- `shutdown_initiated`: Graceful shutdown begins
- `shutdown_completed`: Shutdown process finished
- `restart_initiated`: Container restart begins
- `failure_detected`: Critical failure detected
- `recovery_completed`: Automatic recovery successful

### Metrics Collection

```python
# Get lifecycle metrics
metrics = lifecycle_manager.get_lifecycle_metrics()

# Export comprehensive report
report = lifecycle_manager.export_lifecycle_report("/app/logs/lifecycle_report.json")
```

## Troubleshooting

### Common Issues

#### Startup Failures

1. **Missing Environment Variables**

   - Check required environment variables are set
   - Verify flow name consistency
   - Validate database connection strings

2. **Dependency Failures**

   - Check database connectivity
   - Verify service endpoints are accessible
   - Review dependency timeout settings

3. **Resource Issues**
   - Ensure sufficient disk space
   - Check memory and CPU limits
   - Verify directory permissions

#### Health Check Failures

1. **Database Issues**

   - Check database server status
   - Verify connection pool configuration
   - Review query performance

2. **Resource Exhaustion**

   - Monitor memory usage trends
   - Check disk space utilization
   - Review CPU usage patterns

3. **Application Issues**
   - Check application logs for errors
   - Verify configuration consistency
   - Review dependency status

#### Restart Issues

1. **Excessive Restarts**

   - Review restart policy configuration
   - Check failure root causes
   - Adjust restart window settings

2. **Restart Failures**
   - Verify startup validation passes
   - Check dependency availability
   - Review resource constraints

### Debugging Commands

```bash
# Check container lifecycle status
docker exec container-name python -c "
from core.container_lifecycle_manager import ContainerLifecycleManager
# Print current status
"

# Export lifecycle report
docker exec container-name python scripts/container_lifecycle_startup.py \
    --flow-name rpa1 --export-report /app/logs/debug_report.json

# Check health status
docker exec container-name python -c "
from core.health_monitor import HealthMonitor
monitor = HealthMonitor()
print(monitor.comprehensive_health_check())
"
```

### Log Analysis

```bash
# Filter lifecycle events
docker logs container-name | grep '"component": "lifecycle_manager"'

# Monitor health checks
docker logs container-name | grep '"event": "health_check"'

# Track restart events
docker logs container-name | grep '"event": "restart_initiated"'
```

## Best Practices

### Configuration Management

1. **Environment Variables**: Use consistent naming conventions
2. **Secrets Management**: Store sensitive data securely
3. **Configuration Validation**: Validate all configuration at startup
4. **Documentation**: Document all configuration options

### Dependency Management

1. **Timeout Configuration**: Set appropriate timeouts for dependencies
2. **Retry Logic**: Implement exponential backoff for retries
3. **Graceful Degradation**: Handle optional dependency failures gracefully
4. **Health Checks**: Implement comprehensive health checks

### Resource Management

1. **Resource Limits**: Set appropriate memory and CPU limits
2. **Cleanup Handlers**: Implement proper cleanup for all resources
3. **Monitoring**: Monitor resource usage continuously
4. **Alerting**: Set up alerts for resource exhaustion

### Error Handling

1. **Structured Logging**: Use consistent log formats
2. **Error Classification**: Distinguish between recoverable and fatal errors
3. **Automatic Recovery**: Implement automatic recovery for transient failures
4. **Escalation**: Define escalation procedures for critical failures

### Testing

1. **Unit Tests**: Test individual lifecycle components
2. **Integration Tests**: Test complete lifecycle flows
3. **Stress Tests**: Test under high load conditions
4. **Failure Tests**: Test failure scenarios and recovery

## Performance Considerations

### Startup Performance

- Optimize dependency check timeouts
- Parallelize independent validation checks
- Cache validation results where appropriate
- Minimize startup overhead

### Runtime Performance

- Optimize health check intervals
- Use efficient resource monitoring
- Implement smart remediation triggers
- Minimize logging overhead

### Shutdown Performance

- Optimize cleanup handler execution
- Set appropriate shutdown timeouts
- Prioritize critical cleanup operations
- Minimize shutdown delays

## Security Considerations

### Container Security

- Run containers as non-root users
- Implement proper file permissions
- Use minimal base images
- Regular security scanning

### Network Security

- Secure service communications
- Implement proper authentication
- Use encrypted connections
- Network segmentation

### Data Security

- Secure configuration management
- Protect sensitive environment variables
- Implement audit logging
- Data encryption at rest and in transit

## Future Enhancements

### Planned Features

1. **Advanced Health Checks**: Custom health check plugins
2. **Distributed Coordination**: Multi-container coordination
3. **Performance Optimization**: Adaptive resource management
4. **Enhanced Monitoring**: Integration with monitoring systems
5. **Automated Scaling**: Dynamic scaling based on metrics

### Integration Opportunities

1. **Kubernetes Integration**: Native Kubernetes lifecycle management
2. **Service Mesh**: Integration with service mesh technologies
3. **Observability Platforms**: Enhanced monitoring and alerting
4. **CI/CD Integration**: Automated testing and deployment
