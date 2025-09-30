# Container Testing System Troubleshooting Guide

## Overview

This guide provides comprehensive troubleshooting information for common issues encountered with the Container Testing System. It includes diagnostic procedures, common problems, and their solutions.

## Table of Contents

1. [Quick Diagnostic Checklist](#quick-diagnostic-checklist)
2. [Container Startup Issues](#container-startup-issues)
3. [Configuration Problems](#configuration-problems)
4. [Database Connectivity Issues](#database-connectivity-issues)
5. [Service Orchestration Problems](#service-orchestration-problems)
6. [Performance Issues](#performance-issues)
7. [Test Execution Problems](#test-execution-problems)
8. [Build and Deployment Issues](#build-and-deployment-issues)
9. [Network and Communication Issues](#network-and-communication-issues)
10. [Resource and Memory Issues](#resource-and-memory-issues)
11. [Security and Permission Issues](#security-and-permission-issues)
12. [Monitoring and Logging Issues](#monitoring-and-logging-issues)

## Quick Diagnostic Checklist

Before diving into specific issues, run this quick diagnostic checklist:

```bash
# 1. Check container status
docker-compose ps

# 2. Check system resources
docker stats --no-stream

# 3. Check logs for errors
docker-compose logs --tail=50

# 4. Verify network connectivity
docker network ls
docker network inspect rpa_default

# 5. Check database connectivity
docker exec postgres pg_isready

# 6. Verify environment configuration
docker exec rpa-flow1 env | grep CONTAINER_

# 7. Check health endpoints
curl -f http://localhost:8080/health || echo "Health check failed"
```

## Container Startup Issues

### Problem: Container Fails to Start

**Symptoms:**

- Container exits immediately after startup
- "Exited (1)" status in `docker-compose ps`
- Error messages in container logs

**Diagnostic Steps:**

```bash
# Check container logs
docker logs <container_name>

# Check exit code
docker inspect <container_name> | jq '.[0].State.ExitCode'

# Run container interactively for debugging
docker run -it --rm <image_name> /bin/bash
```

**Common Causes and Solutions:**

1. **Missing Environment Variables**

   ```bash
   # Check required variables
   docker exec <container> env | grep CONTAINER_

   # Solution: Add missing variables to .env files
   echo "CONTAINER_DATABASE_RPA_DB_URL=postgresql://..." >> flows/rpa1/.env.development
   ```

2. **Invalid Configuration**

   ```bash
   # Validate configuration
   docker exec <container> python -c "from core.container_config import ContainerConfigManager; ContainerConfigManager().validate_container_environment()"

   # Solution: Fix configuration errors reported
   ```

3. **Permission Issues**

   ```bash
   # Check file permissions
   docker exec <container> ls -la /app

   # Solution: Ensure proper ownership
   docker exec <container> chown -R appuser:appuser /app
   ```

### Problem: Container Starts but Becomes Unhealthy

**Symptoms:**

- Container shows "unhealthy" status
- Health check endpoints return errors
- Application not responding

**Diagnostic Steps:**

```bash
# Check health status
docker inspect <container> | jq '.[0].State.Health'

# Test health endpoint manually
curl -v http://localhost:8080/health

# Check application logs
docker logs <container> | grep -E "(ERROR|FATAL|health)"
```

**Solutions:**

1. **Database Connection Issues**

   ```bash
   # Test database connectivity
   docker exec <container> python -c "from core.database import get_database_manager; get_database_manager().test_connection()"
   ```

2. **Service Dependencies Not Ready**
   ```bash
   # Check service dependencies
   docker exec <container> python -c "from core.service_orchestrator import ServiceOrchestrator; ServiceOrchestrator().validate_service_health()"
   ```

## Configuration Problems

### Problem: Environment Variables Not Loading

**Symptoms:**

- Configuration validation failures
- Default values being used instead of environment values
- "Configuration not found" errors

**Diagnostic Steps:**

```bash
# Check environment variable loading
docker exec <container> python -c "
import os
from core.container_config import ContainerConfigManager
config = ContainerConfigManager()
print('Environment variables:', {k:v for k,v in os.environ.items() if k.startswith('CONTAINER_')})
print('Loaded config:', config.load_container_config())
"
```

**Solutions:**

1. **Incorrect Variable Names**

   ```bash
   # Verify variable naming convention
   # Correct: CONTAINER_DATABASE_RPA_DB_URL
   # Incorrect: DATABASE_RPA_DB_URL
   ```

2. **Environment File Not Loaded**

   ```bash
   # Check if .env file exists and is readable
   docker exec <container> cat /app/flows/rpa1/.env.development

   # Ensure docker-compose loads the file
   # In docker-compose.yml:
   env_file:
     - flows/rpa1/.env.development
   ```

### Problem: Configuration Validation Failures

**Symptoms:**

- "Invalid configuration" errors at startup
- Missing required configuration sections
- Type validation errors

**Diagnostic Steps:**

```bash
# Run configuration validation manually
docker exec <container> python -c "
from core.container_config import ContainerConfigManager
config = ContainerConfigManager()
try:
    result = config.validate_container_environment()
    print('Validation result:', result)
except Exception as e:
    print('Validation error:', e)
"
```

**Solutions:**

1. **Missing Required Fields**

   ```bash
   # Add required configuration
   CONTAINER_FLOW_NAME=rpa1
   CONTAINER_ENVIRONMENT=development
   CONTAINER_DATABASE_RPA_DB_URL=postgresql://user:pass@host:port/db
   ```

2. **Invalid Configuration Format**
   ```bash
   # Ensure proper URL format for database connections
   # Correct: postgresql://user:pass@host:port/database
   # Incorrect: postgres://user@host/database (missing password)
   ```

## Database Connectivity Issues

### Problem: Cannot Connect to Database

**Symptoms:**

- "Connection refused" errors
- Database timeout errors
- "Database not available" messages

**Diagnostic Steps:**

```bash
# Test database connectivity from container
docker exec <container> python -c "
import psycopg2
try:
    conn = psycopg2.connect('postgresql://user:pass@postgres:5432/rpa_db')
    print('Database connection successful')
    conn.close()
except Exception as e:
    print('Database connection failed:', e)
"

# Check database container status
docker-compose ps postgres

# Test network connectivity
docker exec <container> ping postgres
docker exec <container> telnet postgres 5432
```

**Solutions:**

1. **Database Container Not Running**

   ```bash
   # Start database container
   docker-compose up -d postgres

   # Check database logs
   docker logs postgres
   ```

2. **Incorrect Connection String**

   ```bash
   # Verify connection parameters
   # Host should be service name in docker-compose (e.g., 'postgres')
   # Port should be internal port (5432, not mapped port)
   CONTAINER_DATABASE_RPA_DB_URL=postgresql://postgres:password@postgres:5432/rpa_db
   ```

3. **Database Not Ready**

   ```bash
   # Wait for database to be ready
   docker exec postgres pg_isready -U postgres

   # Check database initialization
   docker exec postgres psql -U postgres -c "\l"
   ```

### Problem: Database Connection Pool Exhaustion

**Symptoms:**

- "Connection pool exhausted" errors
- Slow database operations
- Timeout errors under load

**Diagnostic Steps:**

```bash
# Check active connections
docker exec postgres psql -U postgres -c "
SELECT count(*) as active_connections,
       state,
       application_name
FROM pg_stat_activity
WHERE state = 'active'
GROUP BY state, application_name;
"

# Monitor connection pool metrics
docker exec <container> python -c "
from core.database import get_database_manager
db = get_database_manager()
print('Pool status:', db.get_pool_status())
"
```

**Solutions:**

1. **Increase Pool Size**

   ```bash
   # Adjust pool configuration
   CONTAINER_DATABASE_POOL_SIZE=30
   CONTAINER_DATABASE_MAX_OVERFLOW=50
   ```

2. **Fix Connection Leaks**
   ```bash
   # Ensure proper connection cleanup in code
   # Use context managers or try/finally blocks
   ```

## Service Orchestration Problems

### Problem: Services Start in Wrong Order

**Symptoms:**

- Application containers start before database is ready
- Dependency validation failures
- Intermittent startup failures

**Diagnostic Steps:**

```bash
# Check service dependencies in docker-compose.yml
grep -A 5 "depends_on:" docker-compose.yml

# Check service health
docker exec <container> python -c "
from core.service_orchestrator import ServiceOrchestrator
orchestrator = ServiceOrchestrator()
print('Service health:', orchestrator.validate_service_health())
"
```

**Solutions:**

1. **Add Proper Dependencies**

   ```yaml
   # In docker-compose.yml
   services:
     rpa-flow1:
       depends_on:
         postgres:
           condition: service_healthy
         prefect-server:
           condition: service_started
   ```

2. **Implement Startup Delays**
   ```bash
   # Add startup delay in container
   CONTAINER_STARTUP_DELAY=30
   ```

### Problem: Health Check Failures

**Symptoms:**

- Services marked as unhealthy
- Health endpoints returning errors
- Dependency validation failures

**Diagnostic Steps:**

```bash
# Test health endpoints manually
curl -f http://localhost:8080/health/detailed

# Check health check configuration
docker inspect <container> | jq '.[0].Config.Healthcheck'

# Monitor health check logs
docker logs <container> | grep health
```

**Solutions:**

1. **Adjust Health Check Timeouts**

   ```yaml
   # In docker-compose.yml
   healthcheck:
     test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
     interval: 30s
     timeout: 10s
     retries: 3
     start_period: 60s
   ```

2. **Fix Health Check Implementation**
   ```python
   # Ensure health check endpoint is properly implemented
   # Check core/health_monitor.py for implementation details
   ```

## Performance Issues

### Problem: Slow Processing Performance

**Symptoms:**

- Low processing throughput
- High response times
- Resource utilization issues

**Diagnostic Steps:**

```bash
# Monitor resource usage
docker stats --no-stream

# Check processing metrics
docker exec <container> python -c "
from core.performance_monitor import PerformanceMonitor
monitor = PerformanceMonitor()
print('Performance metrics:', monitor.get_current_metrics())
"

# Analyze processing bottlenecks
docker logs <container> | grep -E "(processing|performance|slow)"
```

**Solutions:**

1. **Increase Resource Limits**

   ```yaml
   # In docker-compose.yml
   deploy:
     resources:
       limits:
         cpus: "4.0"
         memory: 4G
   ```

2. **Optimize Database Queries**

   ```bash
   # Enable query logging
   CONTAINER_DATABASE_LOG_QUERIES=true

   # Analyze slow queries
   docker exec postgres psql -U postgres -c "
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   ORDER BY mean_time DESC
   LIMIT 10;
   "
   ```

3. **Tune Connection Pool**
   ```bash
   # Optimize pool settings
   CONTAINER_DATABASE_POOL_SIZE=50
   CONTAINER_DATABASE_POOL_TIMEOUT=30
   ```

### Problem: Memory Leaks

**Symptoms:**

- Continuously increasing memory usage
- Out of memory errors
- Container restarts due to memory limits

**Diagnostic Steps:**

```bash
# Monitor memory usage over time
docker stats <container>

# Check for memory leaks in application
docker exec <container> python -c "
import gc
import psutil
import os
process = psutil.Process(os.getpid())
print('Memory usage:', process.memory_info())
print('GC stats:', gc.get_stats())
"
```

**Solutions:**

1. **Enable Memory Profiling**

   ```bash
   # Add memory profiling
   CONTAINER_ENABLE_MEMORY_PROFILING=true
   ```

2. **Implement Proper Cleanup**
   ```python
   # Ensure proper resource cleanup in code
   # Use context managers and explicit cleanup
   ```

## Test Execution Problems

### Problem: Tests Fail Intermittently

**Symptoms:**

- Tests pass sometimes, fail other times
- Race conditions in test execution
- Inconsistent test results

**Diagnostic Steps:**

```bash
# Run tests multiple times
for i in {1..5}; do
    echo "Test run $i"
    python core/test/run_container_tests.py --category integration
done

# Check for race conditions
python core/test/run_container_tests.py --parallel=false

# Analyze test logs
docker logs <container> | grep -E "(test|assertion|error)"
```

**Solutions:**

1. **Add Test Synchronization**

   ```python
   # Use proper test synchronization
   # Add delays or wait conditions for async operations
   ```

2. **Isolate Test Data**
   ```bash
   # Ensure test data isolation
   CONTAINER_TEST_DATABASE_ISOLATION=true
   ```

### Problem: Test Data Setup Issues

**Symptoms:**

- Tests fail due to missing test data
- Database state inconsistencies
- Test data conflicts

**Diagnostic Steps:**

```bash
# Check test data setup
python core/test/run_test_data_validation.py

# Verify database state
docker exec postgres psql -U postgres -d rpa_db -c "
SELECT table_name,
       (SELECT count(*) FROM information_schema.tables t2 WHERE t2.table_name = t1.table_name) as row_count
FROM information_schema.tables t1
WHERE table_schema = 'public';
"
```

**Solutions:**

1. **Reset Test Database**

   ```bash
   # Clean and reinitialize test database
   python core/test/run_test_data_validation.py --reset
   ```

2. **Fix Test Data Scripts**
   ```bash
   # Verify test data initialization scripts
   ls -la core/migrations/rpa_db/
   ```

## Build and Deployment Issues

### Problem: Build Failures

**Symptoms:**

- Docker build commands fail
- Missing dependencies in images
- Build cache issues

**Diagnostic Steps:**

```bash
# Build with verbose output
docker build --no-cache --progress=plain -f Dockerfile.base -t rpa-base .

# Check build logs
docker build -f Dockerfile.base -t rpa-base . 2>&1 | tee build.log

# Verify base image
docker run --rm rpa-base python --version
```

**Solutions:**

1. **Clear Build Cache**

   ```bash
   # Clear Docker build cache
   docker builder prune -a

   # Rebuild from scratch
   ./scripts/build_all.sh --no-cache
   ```

2. **Fix Dependency Issues**

   ```bash
   # Update requirements
   uv pip compile requirements.in --output-file requirements.txt

   # Verify dependencies
   docker run --rm rpa-base pip list
   ```

### Problem: Deployment Failures

**Symptoms:**

- Containers fail to start after deployment
- Configuration mismatches
- Service unavailability

**Diagnostic Steps:**

```bash
# Check deployment status
docker-compose ps

# Verify configuration
docker-compose config

# Check service logs
docker-compose logs --tail=100
```

**Solutions:**

1. **Validate Configuration**

   ```bash
   # Test configuration before deployment
   docker-compose -f docker-compose.yml config --quiet
   ```

2. **Rolling Deployment**
   ```bash
   # Deploy services one by one
   docker-compose up -d postgres
   sleep 30
   docker-compose up -d prefect-server
   sleep 30
   docker-compose up -d rpa-flow1 rpa-flow2 rpa-flow3
   ```

## Network and Communication Issues

### Problem: Inter-Container Communication Failures

**Symptoms:**

- Services cannot reach each other
- DNS resolution failures
- Connection timeouts

**Diagnostic Steps:**

```bash
# Check network configuration
docker network ls
docker network inspect rpa_default

# Test connectivity between containers
docker exec rpa-flow1 ping postgres
docker exec rpa-flow1 nslookup postgres

# Check port accessibility
docker exec rpa-flow1 telnet postgres 5432
```

**Solutions:**

1. **Verify Network Configuration**

   ```yaml
   # Ensure services are on same network
   networks:
     default:
       name: rpa_default
   ```

2. **Use Service Names for Communication**
   ```bash
   # Use docker-compose service names as hostnames
   # Correct: postgres:5432
   # Incorrect: localhost:5432
   ```

### Problem: External Network Access Issues

**Symptoms:**

- Cannot reach external services
- DNS resolution failures for external hosts
- Firewall or proxy issues

**Diagnostic Steps:**

```bash
# Test external connectivity
docker exec <container> ping 8.8.8.8
docker exec <container> nslookup google.com

# Check DNS configuration
docker exec <container> cat /etc/resolv.conf

# Test HTTP connectivity
docker exec <container> curl -v https://httpbin.org/get
```

**Solutions:**

1. **Configure DNS**

   ```yaml
   # In docker-compose.yml
   services:
     rpa-flow1:
       dns:
         - 8.8.8.8
         - 8.8.4.4
   ```

2. **Proxy Configuration**
   ```bash
   # Set proxy environment variables
   HTTP_PROXY=http://proxy:8080
   HTTPS_PROXY=http://proxy:8080
   ```

## Resource and Memory Issues

### Problem: Out of Memory Errors

**Symptoms:**

- Container killed due to memory limits
- "OOMKilled" status
- Application crashes with memory errors

**Diagnostic Steps:**

```bash
# Check memory usage
docker stats --no-stream

# Check container memory limits
docker inspect <container> | jq '.[0].HostConfig.Memory'

# Monitor memory usage over time
watch -n 5 'docker stats --no-stream'
```

**Solutions:**

1. **Increase Memory Limits**

   ```yaml
   # In docker-compose.yml
   deploy:
     resources:
       limits:
         memory: 4G
       reservations:
         memory: 2G
   ```

2. **Optimize Memory Usage**

   ```bash
   # Enable memory optimization
   CONTAINER_MEMORY_OPTIMIZATION=true

   # Tune garbage collection
   PYTHONHASHSEED=0
   ```

### Problem: CPU Throttling

**Symptoms:**

- High CPU wait times
- Slow processing performance
- CPU usage at limit

**Diagnostic Steps:**

```bash
# Monitor CPU usage
docker stats --no-stream

# Check CPU throttling
docker exec <container> cat /sys/fs/cgroup/cpu/cpu.stat

# Analyze CPU-intensive processes
docker exec <container> top
```

**Solutions:**

1. **Increase CPU Limits**

   ```yaml
   # In docker-compose.yml
   deploy:
     resources:
       limits:
         cpus: "4.0"
   ```

2. **Optimize CPU Usage**

   ```bash
   # Enable CPU optimization
   CONTAINER_CPU_OPTIMIZATION=true

   # Use async processing where appropriate
   ```

## Security and Permission Issues

### Problem: Permission Denied Errors

**Symptoms:**

- Cannot write to mounted volumes
- File access denied errors
- Database connection permission errors

**Diagnostic Steps:**

```bash
# Check file permissions
docker exec <container> ls -la /app

# Check user context
docker exec <container> id

# Check volume mounts
docker inspect <container> | jq '.[0].Mounts'
```

**Solutions:**

1. **Fix File Ownership**

   ```bash
   # Set proper ownership
   sudo chown -R 1000:1000 ./logs
   sudo chown -R 1000:1000 ./data
   ```

2. **Use Proper User in Container**
   ```dockerfile
   # In Dockerfile
   USER appuser:appuser
   ```

### Problem: Security Validation Failures

**Symptoms:**

- Security scanner alerts
- Vulnerability warnings
- Non-compliant configurations

**Diagnostic Steps:**

```bash
# Run security validation
python core/test/run_security_validation.py

# Scan container images
./scripts/security_scanner.sh

# Check security configuration
docker exec <container> python -c "
from core.security_validator import SecurityValidator
validator = SecurityValidator()
print('Security status:', validator.validate_security_configuration())
"
```

**Solutions:**

1. **Update Base Images**

   ```bash
   # Update to latest secure base images
   docker pull python:3.11-slim
   ./scripts/build_base_image.sh
   ```

2. **Fix Security Issues**
   ```bash
   # Apply security patches
   ./scripts/security_scanner.sh --fix
   ```

## Monitoring and Logging Issues

### Problem: Missing or Incomplete Logs

**Symptoms:**

- No logs appearing in expected locations
- Incomplete log information
- Log rotation issues

**Diagnostic Steps:**

```bash
# Check log configuration
docker logs <container>

# Verify log file locations
docker exec <container> ls -la /app/logs/

# Check log rotation
docker exec <container> ls -la /var/log/
```

**Solutions:**

1. **Configure Proper Logging**

   ```bash
   # Set log level
   CONTAINER_LOG_LEVEL=DEBUG

   # Enable structured logging
   CONTAINER_LOG_FORMAT=json
   ```

2. **Fix Log Rotation**
   ```yaml
   # In docker-compose.yml
   logging:
     driver: "json-file"
     options:
       max-size: "100m"
       max-file: "5"
   ```

### Problem: Monitoring Metrics Not Available

**Symptoms:**

- Health endpoints not responding
- Metrics not exported
- Monitoring dashboards empty

**Diagnostic Steps:**

```bash
# Test metrics endpoints
curl http://localhost:8080/metrics

# Check monitoring configuration
docker exec <container> python -c "
from core.performance_monitor import PerformanceMonitor
monitor = PerformanceMonitor()
print('Monitoring status:', monitor.get_monitoring_status())
"
```

**Solutions:**

1. **Enable Metrics Export**

   ```bash
   # Enable Prometheus metrics
   CONTAINER_ENABLE_METRICS=true
   CONTAINER_METRICS_PORT=8080
   ```

2. **Configure Monitoring Stack**
   ```bash
   # Start monitoring services
   docker-compose -f docker-compose.yml -f monitoring/docker-compose.monitoring.yml up -d
   ```

## Emergency Procedures

### Complete System Reset

If all else fails, perform a complete system reset:

```bash
# 1. Stop all containers
docker-compose down -v

# 2. Remove all containers and images
docker system prune -a --volumes

# 3. Rebuild everything
./scripts/build_all.sh --no-cache

# 4. Reset database
rm -rf data/postgres
docker-compose up -d postgres

# 5. Wait for database initialization
sleep 60

# 6. Start all services
docker-compose up -d

# 7. Run validation tests
python core/test/run_container_tests.py --category smoke
```

### Data Recovery

If data corruption occurs:

```bash
# 1. Stop containers
docker-compose stop

# 2. Backup current data
cp -r data/postgres data/postgres.backup.$(date +%Y%m%d_%H%M%S)

# 3. Restore from backup
# (Restore from your backup solution)

# 4. Restart services
docker-compose up -d

# 5. Validate data integrity
python core/test/run_test_data_validation.py
```

## Getting Help

If you continue to experience issues:

1. **Check the logs** - Most issues are revealed in the container logs
2. **Review configuration** - Ensure all environment variables are properly set
3. **Test connectivity** - Verify network and database connectivity
4. **Run diagnostics** - Use the diagnostic commands provided in this guide
5. **Consult documentation** - Review the main documentation and operational guides
6. **Contact support** - Reach out to the development team with specific error messages and diagnostic output

For additional resources:

- [Container Testing System Documentation](CONTAINER_TESTING_SYSTEM.md)
- [Performance Tuning Guide](CONTAINER_PERFORMANCE_TUNING.md)
- [Operational Runbooks](CONTAINER_OPERATIONAL_RUNBOOKS.md)
- [Developer Guide](CONTAINER_DEVELOPMENT_GUIDE.md)
