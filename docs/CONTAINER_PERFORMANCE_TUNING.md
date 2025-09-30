# Container Performance Tuning and Optimization Guide

## Overview

This guide provides comprehensive performance tuning and optimization recommendations for the Container Testing System. It covers resource optimization, performance monitoring, bottleneck identification, and best practices for achieving optimal performance in both development and production environments.

## Table of Contents

1. [Performance Monitoring](#performance-monitoring)
2. [Resource Optimization](#resource-optimization)
3. [Database Performance Tuning](#database-performance-tuning)
4. [Container Optimization](#container-optimization)
5. [Build Performance](#build-performance)
6. [Network Optimization](#network-optimization)
7. [Memory Management](#memory-management)
8. [CPU Optimization](#cpu-optimization)
9. [I/O Performance](#io-performance)
10. [Monitoring and Alerting](#monitoring-and-alerting)
11. [Performance Testing](#performance-testing)
12. [Troubleshooting Performance Issues](#troubleshooting-performance-issues)

## Performance Monitoring

### Key Performance Indicators (KPIs)

Monitor these critical metrics for optimal performance:

```bash
# Processing throughput
Records processed per second: > 100 rps
Average processing latency: < 100ms
Error rate: < 1%

# Resource utilization
CPU usage: < 80%
Memory usage: < 85%
Disk I/O: < 80%
Network utilization: < 70%

# Database performance
Connection pool utilization: < 80%
Query response time: < 50ms
Active connections: < 100
```

### Performance Monitoring Setup

```bash
# Enable comprehensive monitoring
CONTAINER_ENABLE_METRICS=true
CONTAINER_METRICS_PORT=8080
CONTAINER_PERFORMANCE_MONITORING=true

# Start monitoring stack
docker-compose -f docker-compose.yml -f monitoring/docker-compose.monitoring.yml up -d

# Access monitoring dashboards
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000
```

### Real-time Performance Monitoring

```bash
# Monitor container resources
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"

# Monitor application metrics
curl http://localhost:8080/metrics | grep -E "(processing_rate|error_rate|latency)"

# Monitor database performance
docker exec postgres psql -U postgres -c "
SELECT
    datname,
    numbackends as connections,
    xact_commit as commits,
    xact_rollback as rollbacks,
    blks_read,
    blks_hit,
    tup_returned,
    tup_fetched
FROM pg_stat_database
WHERE datname IN ('rpa_db', 'survey_hub');
"
```

### Performance Profiling

```python
# Enable application profiling
CONTAINER_ENABLE_PROFILING=true
CONTAINER_PROFILE_OUTPUT_DIR=/app/logs/profiles

# Generate performance profiles
python -m cProfile -o profile.stats core/test/run_container_tests.py

# Analyze profiles
python -c "
import pstats
stats = pstats.Stats('profile.stats')
stats.sort_stats('cumulative').print_stats(20)
"
```

## Resource Optimization

### Container Resource Limits

Optimize resource allocation based on workload patterns:

```yaml
# docker-compose.yml - Production settings
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
      - CONTAINER_WORKER_PROCESSES=4
      - CONTAINER_WORKER_THREADS=8

  rpa-flow2:
    deploy:
      resources:
        limits:
          cpus: "1.5"
          memory: 1.5G
        reservations:
          cpus: "0.5"
          memory: 512M

  postgres:
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 4G
        reservations:
          cpus: "1.0"
          memory: 2G
```

### Dynamic Resource Scaling

```bash
# Auto-scaling configuration
CONTAINER_AUTO_SCALING_ENABLED=true
CONTAINER_SCALE_UP_CPU_THRESHOLD=80
CONTAINER_SCALE_DOWN_CPU_THRESHOLD=30
CONTAINER_MIN_REPLICAS=1
CONTAINER_MAX_REPLICAS=5

# Manual scaling
docker-compose up --scale rpa-flow1=3 --scale rpa-flow2=2
```

### Resource Monitoring and Alerts

```bash
# Set up resource monitoring
python scripts/build_performance_monitor.py --enable-alerts

# Configure alert thresholds
CONTAINER_CPU_ALERT_THRESHOLD=85
CONTAINER_MEMORY_ALERT_THRESHOLD=90
CONTAINER_DISK_ALERT_THRESHOLD=85
```

## Database Performance Tuning

### Connection Pool Optimization

```bash
# Optimal connection pool settings
CONTAINER_DATABASE_POOL_SIZE=20
CONTAINER_DATABASE_MAX_OVERFLOW=30
CONTAINER_DATABASE_POOL_TIMEOUT=30
CONTAINER_DATABASE_POOL_RECYCLE=3600
CONTAINER_DATABASE_POOL_PRE_PING=true

# Monitor connection pool usage
docker exec <container> python -c "
from core.database import get_database_manager
db = get_database_manager()
pool_status = db.get_pool_status()
print(f'Pool size: {pool_status.size}')
print(f'Checked out: {pool_status.checked_out}')
print(f'Overflow: {pool_status.overflow}')
print(f'Utilization: {pool_status.checked_out / pool_status.size * 100:.1f}%')
"
```

### PostgreSQL Configuration Tuning

```bash
# Optimize PostgreSQL settings
# In postgresql.conf or via environment variables

# Memory settings
shared_buffers = 1GB                    # 25% of system RAM
effective_cache_size = 3GB              # 75% of system RAM
work_mem = 64MB                         # Per connection work memory
maintenance_work_mem = 256MB            # Maintenance operations

# Connection settings
max_connections = 200                   # Maximum concurrent connections
max_prepared_transactions = 200         # For distributed transactions

# Performance settings
random_page_cost = 1.1                  # SSD optimization
effective_io_concurrency = 200          # Concurrent I/O operations
max_worker_processes = 8                # Parallel processing
max_parallel_workers_per_gather = 4     # Parallel query workers

# Logging and monitoring
log_min_duration_statement = 1000       # Log slow queries (1 second)
log_checkpoints = on                    # Log checkpoint activity
log_connections = on                    # Log connections
log_disconnections = on                 # Log disconnections
```

### Query Optimization

```sql
-- Enable query statistics
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Monitor slow queries
SELECT
    query,
    calls,
    total_time,
    mean_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;

-- Analyze table statistics
ANALYZE;

-- Update table statistics automatically
ALTER TABLE processed_surveys SET (autovacuum_analyze_scale_factor = 0.05);
ALTER TABLE customer_orders SET (autovacuum_analyze_scale_factor = 0.05);
```

### Index Optimization

```sql
-- Monitor index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Create performance indexes
CREATE INDEX CONCURRENTLY idx_processed_surveys_status_created
ON processed_surveys (status, created_at)
WHERE status IN ('pending', 'processing');

CREATE INDEX CONCURRENTLY idx_customer_orders_priority_created
ON customer_orders (priority, created_at)
WHERE status = 'pending';

-- Monitor index effectiveness
SELECT
    t.tablename,
    indexname,
    c.reltuples AS num_rows,
    pg_size_pretty(pg_relation_size(quote_ident(t.tablename)::text)) AS table_size,
    pg_size_pretty(pg_relation_size(quote_ident(indexrelname)::text)) AS index_size,
    CASE WHEN indisunique THEN 'Y' ELSE 'N' END AS unique,
    idx_scan AS number_of_scans,
    idx_tup_read AS tuples_read,
    idx_tup_fetch AS tuples_fetched
FROM pg_tables t
LEFT OUTER JOIN pg_class c ON c.relname = t.tablename
LEFT OUTER JOIN (
    SELECT c.relname AS ctablename, ipg.relname AS indexname, x.indnatts AS number_of_columns,
           idx_scan, idx_tup_read, idx_tup_fetch, indexrelname, indisunique
    FROM pg_index x
    JOIN pg_class c ON c.oid = x.indrelid
    JOIN pg_class ipg ON ipg.oid = x.indexrelid
    JOIN pg_stat_user_indexes psui ON x.indexrelid = psui.indexrelid
) AS foo ON t.tablename = foo.ctablename
WHERE t.schemaname = 'public'
ORDER BY 1, 2;
```

## Container Optimization

### Image Size Optimization

```dockerfile
# Multi-stage build optimization
FROM python:3.11-slim as base

# Install system dependencies in single layer
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Use .dockerignore to exclude unnecessary files
# .dockerignore content:
__pycache__/
*.pyc
*.pyo
*.pyd
.git/
.pytest_cache/
htmlcov/
.coverage
*.log
```

### Container Startup Optimization

```bash
# Optimize container startup time
CONTAINER_STARTUP_OPTIMIZATION=true
CONTAINER_PRELOAD_MODULES=true
CONTAINER_CACHE_CONNECTIONS=true

# Parallel service initialization
CONTAINER_PARALLEL_STARTUP=true
CONTAINER_STARTUP_TIMEOUT=60
```

### Runtime Optimization

```python
# Optimize Python runtime
import os
os.environ['PYTHONUNBUFFERED'] = '1'      # Unbuffered output
os.environ['PYTHONHASHSEED'] = '0'        # Deterministic hashing
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'  # No .pyc files

# Optimize garbage collection
import gc
gc.set_threshold(700, 10, 10)  # Tune GC thresholds
```

## Build Performance

### Build Cache Optimization

```bash
# Enable BuildKit for improved caching
export DOCKER_BUILDKIT=1

# Use cache mounts for package managers
# In Dockerfile:
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt

# Multi-stage build with cache optimization
./scripts/build_cache_manager.sh --optimize

# Parallel builds
docker build --parallel -f Dockerfile.base -t rpa-base .
```

### Selective Rebuild Strategy

```bash
# Implement intelligent rebuild detection
./scripts/selective_rebuild.sh

# Build only changed components
python scripts/build_performance_monitor.py --detect-changes

# Use build cache effectively
docker build --cache-from rpa-base:latest -t rpa-base:new .
```

### Build Performance Monitoring

```bash
# Monitor build times
time docker build -f Dockerfile.base -t rpa-base .

# Analyze build layers
docker history rpa-base --format "table {{.CreatedBy}}\t{{.Size}}"

# Build performance metrics
python scripts/build_performance_monitor.py --report
```

## Network Optimization

### Container Network Configuration

```yaml
# Optimize network configuration
networks:
  app-network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: rpa-bridge
      com.docker.network.driver.mtu: 1500
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### Connection Optimization

```bash
# Optimize network connections
CONTAINER_NETWORK_KEEP_ALIVE=true
CONTAINER_CONNECTION_TIMEOUT=30
CONTAINER_READ_TIMEOUT=60
CONTAINER_MAX_CONNECTIONS_PER_HOST=20

# Enable HTTP/2 where possible
CONTAINER_HTTP2_ENABLED=true
```

### Network Monitoring

```bash
# Monitor network performance
docker exec <container> ss -tuln
docker exec <container> netstat -i

# Network latency testing
docker exec <container> ping -c 10 postgres
docker exec <container> curl -w "@curl-format.txt" -o /dev/null -s http://postgres:5432
```

## Memory Management

### Memory Optimization Settings

```bash
# Python memory optimization
PYTHONMALLOC=malloc
MALLOC_ARENA_MAX=2
MALLOC_MMAP_THRESHOLD_=131072
MALLOC_TRIM_THRESHOLD_=131072
MALLOC_TOP_PAD_=131072
MALLOC_MMAP_MAX_=65536

# Container memory settings
CONTAINER_MEMORY_OPTIMIZATION=true
CONTAINER_GC_THRESHOLD_0=700
CONTAINER_GC_THRESHOLD_1=10
CONTAINER_GC_THRESHOLD_2=10
```

### Memory Leak Detection

```python
# Enable memory profiling
import tracemalloc
tracemalloc.start()

# Memory usage monitoring
import psutil
import os

def monitor_memory():
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"RSS: {memory_info.rss / 1024 / 1024:.1f} MB")
    print(f"VMS: {memory_info.vms / 1024 / 1024:.1f} MB")

    # Get top memory consumers
    current, peak = tracemalloc.get_traced_memory()
    print(f"Current memory usage: {current / 1024 / 1024:.1f} MB")
    print(f"Peak memory usage: {peak / 1024 / 1024:.1f} MB")
```

### Memory Cleanup Strategies

```python
# Implement proper cleanup
import gc
import weakref

class MemoryManager:
    def __init__(self):
        self._cleanup_callbacks = []

    def register_cleanup(self, callback):
        self._cleanup_callbacks.append(callback)

    def cleanup(self):
        for callback in self._cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"Cleanup error: {e}")

        # Force garbage collection
        gc.collect()

    def __del__(self):
        self.cleanup()
```

## CPU Optimization

### CPU Affinity and Scheduling

```bash
# Set CPU affinity for containers
docker run --cpuset-cpus="0,1" rpa-flow1

# Optimize CPU scheduling
CONTAINER_CPU_OPTIMIZATION=true
CONTAINER_WORKER_PROCESSES=auto  # Auto-detect CPU cores
CONTAINER_WORKER_THREADS=2       # Threads per process
```

### Async Processing Optimization

```python
# Optimize async processing
import asyncio
import concurrent.futures

# Configure event loop
asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Use thread pool for CPU-intensive tasks
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

async def process_records_async(records):
    loop = asyncio.get_event_loop()
    tasks = []

    for record in records:
        task = loop.run_in_executor(executor, process_record, record)
        tasks.append(task)

    results = await asyncio.gather(*tasks)
    return results
```

### CPU Monitoring

```bash
# Monitor CPU usage patterns
docker exec <container> top -p $(pgrep python)

# CPU profiling
python -m cProfile -o cpu_profile.stats your_script.py

# Analyze CPU hotspots
python -c "
import pstats
stats = pstats.Stats('cpu_profile.stats')
stats.sort_stats('cumulative').print_stats(20)
"
```

## I/O Performance

### Disk I/O Optimization

```bash
# Optimize disk I/O
CONTAINER_IO_OPTIMIZATION=true
CONTAINER_BUFFER_SIZE=65536
CONTAINER_BATCH_SIZE=1000

# Use tmpfs for temporary files
docker run --tmpfs /tmp:rw,noexec,nosuid,size=1g rpa-flow1
```

### Database I/O Optimization

```sql
-- Optimize database I/O
-- Use COPY for bulk operations
COPY processed_surveys FROM '/tmp/data.csv' WITH (FORMAT csv, HEADER true);

-- Batch inserts
INSERT INTO processed_surveys (survey_id, status, data)
VALUES
    (1, 'completed', '{}'),
    (2, 'completed', '{}'),
    (3, 'completed', '{}');

-- Use prepared statements
PREPARE insert_survey AS
INSERT INTO processed_surveys (survey_id, status, data) VALUES ($1, $2, $3);

EXECUTE insert_survey(1, 'completed', '{}');
```

### File System Optimization

```bash
# Optimize file system performance
# Use appropriate file system for containers
# ext4 for general use, xfs for large files

# Mount options for performance
docker run -v /host/data:/container/data:rw,Z rpa-flow1

# Use bind mounts for development
docker run -v $(pwd):/app rpa-flow1
```

## Monitoring and Alerting

### Performance Metrics Collection

```python
# Custom metrics collection
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
PROCESSING_COUNTER = Counter('records_processed_total', 'Total processed records')
PROCESSING_HISTOGRAM = Histogram('processing_duration_seconds', 'Processing duration')
ACTIVE_CONNECTIONS = Gauge('database_connections_active', 'Active database connections')

# Collect metrics
@PROCESSING_HISTOGRAM.time()
def process_record(record):
    # Processing logic
    PROCESSING_COUNTER.inc()
    return result

# Start metrics server
start_http_server(8080)
```

### Alert Configuration

```yaml
# Prometheus alert rules
groups:
  - name: container_performance
    rules:
      - alert: HighCPUUsage
        expr: container_cpu_usage_percent > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"

      - alert: HighMemoryUsage
        expr: container_memory_usage_percent > 90
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High memory usage detected"

      - alert: SlowProcessing
        expr: processing_duration_seconds > 5
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "Slow processing detected"
```

### Performance Dashboards

```json
{
  "dashboard": {
    "title": "Container Performance",
    "panels": [
      {
        "title": "Processing Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(records_processed_total[5m])",
            "legendFormat": "Records/sec"
          }
        ]
      },
      {
        "title": "Resource Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "container_cpu_usage_percent",
            "legendFormat": "CPU %"
          },
          {
            "expr": "container_memory_usage_percent",
            "legendFormat": "Memory %"
          }
        ]
      }
    ]
  }
}
```

## Performance Testing

### Load Testing

```python
# Load testing script
import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor

async def load_test():
    async with aiohttp.ClientSession() as session:
        tasks = []
        start_time = time.time()

        for i in range(1000):
            task = session.post('http://localhost:8080/process',
                              json={'record_id': i})
            tasks.append(task)

        responses = await asyncio.gather(*tasks)
        end_time = time.time()

        success_count = sum(1 for r in responses if r.status == 200)
        total_time = end_time - start_time

        print(f"Processed {success_count}/1000 requests in {total_time:.2f}s")
        print(f"Rate: {success_count/total_time:.2f} requests/sec")

# Run load test
asyncio.run(load_test())
```

### Stress Testing

```bash
# Stress test with multiple containers
docker-compose up --scale rpa-flow1=5 --scale rpa-flow2=3

# Generate load
python core/test/run_performance_tests.py --load-factor=10 --duration=300

# Monitor during stress test
watch -n 1 'docker stats --no-stream'
```

### Performance Benchmarking

```python
# Benchmark different configurations
import time
import statistics

def benchmark_configuration(config):
    times = []

    for i in range(100):
        start = time.time()
        # Run test with configuration
        result = run_test_with_config(config)
        end = time.time()
        times.append(end - start)

    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times),
        'min': min(times),
        'max': max(times)
    }

# Test different configurations
configs = [
    {'workers': 2, 'threads': 4},
    {'workers': 4, 'threads': 2},
    {'workers': 1, 'threads': 8}
]

for config in configs:
    results = benchmark_configuration(config)
    print(f"Config {config}: {results}")
```

## Troubleshooting Performance Issues

### Performance Issue Diagnosis

```bash
# Quick performance check
./scripts/performance_health_check.sh

# Detailed performance analysis
python scripts/build_performance_monitor.py --analyze --detailed

# Generate performance report
python core/test/run_performance_tests.py --report-only
```

### Common Performance Problems

1. **High CPU Usage**

   ```bash
   # Identify CPU-intensive processes
   docker exec <container> top -o %CPU

   # Profile CPU usage
   python -m cProfile -s cumulative your_script.py
   ```

2. **Memory Leaks**

   ```bash
   # Monitor memory growth
   watch -n 5 'docker stats --no-stream | grep <container>'

   # Memory profiling
   python -m memory_profiler your_script.py
   ```

3. **Database Bottlenecks**

   ```sql
   -- Find slow queries
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   ORDER BY mean_time DESC LIMIT 10;

   -- Check for lock contention
   SELECT * FROM pg_stat_activity WHERE wait_event IS NOT NULL;
   ```

4. **I/O Bottlenecks**

   ```bash
   # Monitor I/O usage
   docker exec <container> iostat -x 1

   # Check disk usage
   docker exec <container> df -h
   ```

### Performance Optimization Checklist

- [ ] Resource limits properly configured
- [ ] Database connection pool optimized
- [ ] Indexes created for frequent queries
- [ ] Memory usage monitored and optimized
- [ ] CPU usage balanced across cores
- [ ] Network latency minimized
- [ ] Build cache utilized effectively
- [ ] Monitoring and alerting configured
- [ ] Performance tests automated
- [ ] Bottlenecks identified and addressed

## Best Practices Summary

1. **Monitor Continuously** - Set up comprehensive monitoring and alerting
2. **Optimize Incrementally** - Make small, measurable improvements
3. **Test Performance** - Regular performance testing and benchmarking
4. **Profile Regularly** - Use profiling tools to identify bottlenecks
5. **Scale Appropriately** - Right-size resources for workload
6. **Cache Effectively** - Use caching at multiple layers
7. **Batch Operations** - Group operations for efficiency
8. **Async Where Possible** - Use asynchronous processing for I/O
9. **Monitor Resource Usage** - Keep utilization within optimal ranges
10. **Document Changes** - Track performance improvements and regressions

For additional performance optimization support:

- [Container Testing System Documentation](CONTAINER_TESTING_SYSTEM.md)
- [Troubleshooting Guide](CONTAINER_TROUBLESHOOTING_GUIDE.md)
- [Operational Runbooks](CONTAINER_OPERATIONAL_RUNBOOKS.md)
- [Developer Guide](CONTAINER_DEVELOPMENT_GUIDE.md)
