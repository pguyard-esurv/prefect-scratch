# Performance Optimization Guide

## Overview

This guide provides comprehensive strategies for optimizing the performance of the distributed processing system. It covers database optimization, container tuning, configuration optimization, and monitoring best practices.

## Table of Contents

1. [Performance Baseline](#performance-baseline)
2. [Database Optimization](#database-optimization)
3. [Container Optimization](#container-optimization)
4. [Configuration Tuning](#configuration-tuning)
5. [Batch Size Optimization](#batch-size-optimization)
6. [Memory Management](#memory-management)
7. [Connection Pool Tuning](#connection-pool-tuning)
8. [Monitoring and Metrics](#monitoring-and-metrics)
9. [Scaling Strategies](#scaling-strategies)
10. [Performance Testing](#performance-testing)

## Performance Baseline

### Establishing Baseline Metrics

Before optimization, establish baseline performance metrics:

```python
#!/usr/bin/env python3
"""Establish performance baseline for distributed processing system."""

import time
from datetime import datetime, timedelta
from core.monitoring import processing_performance_monitoring, distributed_queue_monitoring
from core.distributed import DistributedProcessor
from core.database import DatabaseManager

def establish_baseline():
    """Establish performance baseline metrics."""

    print("=== Performance Baseline Assessment ===")

    # 1. Current system performance
    perf = processing_performance_monitoring(time_window_hours=24)

    baseline_metrics = {
        "timestamp": datetime.now().isoformat(),
        "success_rate_percent": perf['overall_metrics']['success_rate_percent'],
        "avg_processing_rate_per_hour": perf['overall_metrics']['avg_processing_rate_per_hour'],
        "avg_processing_time_minutes": perf['overall_metrics']['avg_processing_time_minutes'],
        "total_records_processed": perf['overall_metrics']['total_records_processed']
    }

    print(f"Success Rate: {baseline_metrics['success_rate_percent']:.1f}%")
    print(f"Processing Rate: {baseline_metrics['avg_processing_rate_per_hour']:.1f} records/hour")
    print(f"Avg Processing Time: {baseline_metrics['avg_processing_time_minutes']:.2f} minutes")

    # 2. Database performance
    processor = DistributedProcessor(DatabaseManager('rpa_db'))

    # Test database response time
    start_time = time.time()
    status = processor.get_queue_status()
    db_response_time = (time.time() - start_time) * 1000

    baseline_metrics["db_response_time_ms"] = db_response_time
    print(f"Database Response Time: {db_response_time:.1f}ms")

    # 3. Queue health
    queue_status = distributed_queue_monitoring()
    baseline_metrics["queue_health"] = queue_status['queue_health_assessment']['queue_health']
    baseline_metrics["pending_records"] = queue_status['overall_queue_status']['pending_records']

    print(f"Queue Health: {baseline_metrics['queue_health']}")
    print(f"Pending Records: {baseline_metrics['pending_records']}")

    # 4. Connection pool utilization
    from core.tasks import connection_pool_monitoring

    try:
        pool_status = connection_pool_monitoring("rpa_db")
        baseline_metrics["pool_utilization_percent"] = pool_status['utilization_percent']
        print(f"Pool Utilization: {baseline_metrics['pool_utilization_percent']:.1f}%")
    except Exception as e:
        print(f"Could not get pool status: {e}")

    # Save baseline for comparison
    import json
    with open('performance_baseline.json', 'w') as f:
        json.dump(baseline_metrics, f, indent=2)

    print(f"\nBaseline saved to performance_baseline.json")
    return baseline_metrics

def compare_to_baseline():
    """Compare current performance to baseline."""

    import json

    try:
        with open('performance_baseline.json', 'r') as f:
            baseline = json.load(f)
    except FileNotFoundError:
        print("No baseline found. Run establish_baseline() first.")
        return

    # Get current metrics
    current = establish_baseline()

    print(f"\n=== Performance Comparison ===")

    metrics_to_compare = [
        ("success_rate_percent", "Success Rate", "%", "higher"),
        ("avg_processing_rate_per_hour", "Processing Rate", " records/hour", "higher"),
        ("avg_processing_time_minutes", "Avg Processing Time", " minutes", "lower"),
        ("db_response_time_ms", "DB Response Time", "ms", "lower"),
        ("pool_utilization_percent", "Pool Utilization", "%", "lower")
    ]

    for metric, name, unit, better in metrics_to_compare:
        if metric in baseline and metric in current:
            baseline_val = baseline[metric]
            current_val = current[metric]

            if baseline_val == 0:
                change_pct = 0
            else:
                change_pct = ((current_val - baseline_val) / baseline_val) * 100

            if better == "higher":
                trend = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
            else:
                trend = "📉" if change_pct > 0 else "📈" if change_pct < 0 else "➡️"

            print(f"{trend} {name}: {current_val:.1f}{unit} (was {baseline_val:.1f}{unit}, {change_pct:+.1f}%)")

if __name__ == "__main__":
    establish_baseline()
```

### Performance Targets

Set realistic performance targets based on your workload:

| Metric              | Development      | Staging           | Production         |
| ------------------- | ---------------- | ----------------- | ------------------ |
| Success Rate        | > 95%            | > 98%             | > 99%              |
| Processing Rate     | 50+ records/hour | 200+ records/hour | 1000+ records/hour |
| Avg Processing Time | < 5 minutes      | < 2 minutes       | < 1 minute         |
| DB Response Time    | < 500ms          | < 200ms           | < 100ms            |
| Queue Depth         | < 100            | < 500             | < 1000             |

## Database Optimization

### Index Optimization

Ensure optimal database indexes for query performance:

```sql
-- Essential indexes for processing_queue table
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_queue_status_created
ON processing_queue(status, created_at);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_queue_flow_name_status
ON processing_queue(flow_name, status);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_queue_claimed_at
ON processing_queue(claimed_at) WHERE claimed_at IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_queue_instance_id
ON processing_queue(flow_instance_id) WHERE flow_instance_id IS NOT NULL;

-- Partial indexes for common queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_queue_pending
ON processing_queue(created_at) WHERE status = 'pending';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_queue_processing
ON processing_queue(claimed_at) WHERE status = 'processing';

-- Composite index for cleanup operations
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_processing_queue_cleanup
ON processing_queue(status, claimed_at, retry_count)
WHERE status = 'processing';
```

### Query Optimization

Optimize frequently used queries:

```python
class OptimizedDistributedProcessor(DistributedProcessor):
    """Optimized version with better query performance."""

    def claim_records_batch_optimized(self, flow_name: str, batch_size: int) -> List[Dict]:
        """Optimized record claiming with better query performance."""

        # Use more specific query with proper index usage
        query = """
            WITH claimed_records AS (
                SELECT id
                FROM processing_queue
                WHERE flow_name = :flow_name
                AND status = 'pending'
                ORDER BY created_at ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            )
            UPDATE processing_queue
            SET status = 'processing',
                flow_instance_id = :instance_id,
                claimed_at = NOW(),
                updated_at = NOW()
            FROM claimed_records
            WHERE processing_queue.id = claimed_records.id
            RETURNING processing_queue.id, processing_queue.payload, processing_queue.retry_count
        """

        params = {
            'flow_name': flow_name,
            'batch_size': batch_size,
            'instance_id': self._generate_instance_id()
        }

        try:
            results = self.rpa_db.execute_query("rpa_db", query, params)
            return [{"id": r[0], "payload": r[1], "retry_count": r[2]} for r in results]
        except Exception as e:
            self.logger.error(f"Failed to claim records: {e}")
            return []

    def get_queue_status_optimized(self, flow_name: str = None) -> Dict:
        """Optimized queue status query."""

        if flow_name:
            # Single flow query - more efficient
            query = """
                SELECT
                    status,
                    COUNT(*) as count
                FROM processing_queue
                WHERE flow_name = :flow_name
                GROUP BY status
            """
            params = {"flow_name": flow_name}
        else:
            # System-wide query with aggregation
            query = """
                SELECT
                    flow_name,
                    status,
                    COUNT(*) as count
                FROM processing_queue
                GROUP BY flow_name, status
            """
            params = {}

        results = self.rpa_db.execute_query("rpa_db", query, params)

        # Process results efficiently
        if flow_name:
            status_counts = {status: count for status, count in results}
            return {
                "flow_name": flow_name,
                "pending_records": status_counts.get('pending', 0),
                "processing_records": status_counts.get('processing', 0),
                "completed_records": status_counts.get('completed', 0),
                "failed_records": status_counts.get('failed', 0),
                "total_records": sum(status_counts.values())
            }
        else:
            # Aggregate system-wide results
            by_flow = {}
            totals = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}

            for flow, status, count in results:
                if flow not in by_flow:
                    by_flow[flow] = {}
                by_flow[flow][status] = count
                totals[status] = totals.get(status, 0) + count

            return {
                "total_records": sum(totals.values()),
                "pending_records": totals["pending"],
                "processing_records": totals["processing"],
                "completed_records": totals["completed"],
                "failed_records": totals["failed"],
                "by_flow": by_flow
            }
```

### Database Configuration Tuning

Optimize PostgreSQL configuration for distributed processing:

```sql
-- PostgreSQL configuration optimizations
-- Add to postgresql.conf

-- Memory settings
shared_buffers = '256MB'                    -- 25% of RAM for dedicated DB server
effective_cache_size = '1GB'               -- 75% of RAM
work_mem = '16MB'                          -- Per connection work memory
maintenance_work_mem = '64MB'              -- For maintenance operations

-- Connection settings
max_connections = 200                       -- Adjust based on connection pool size
max_prepared_transactions = 100            -- For prepared statements

-- Checkpoint settings
checkpoint_completion_target = 0.9         -- Spread checkpoints over time
wal_buffers = '16MB'                       -- WAL buffer size
checkpoint_timeout = '10min'               -- Checkpoint frequency

-- Query planner settings
random_page_cost = 1.1                     -- For SSD storage
effective_io_concurrency = 200             -- For SSD storage

-- Logging for performance monitoring
log_min_duration_statement = 1000          -- Log queries > 1 second
log_checkpoints = on                       -- Log checkpoint activity
log_connections = on                       -- Log connections
log_disconnections = on                    -- Log disconnections
log_lock_waits = on                        -- Log lock waits

-- Autovacuum tuning
autovacuum_vacuum_scale_factor = 0.1       -- Vacuum when 10% of table changes
autovacuum_analyze_scale_factor = 0.05     -- Analyze when 5% of table changes
autovacuum_vacuum_cost_limit = 200         -- Increase vacuum speed
```

### Connection Pool Optimization

Optimize connection pool settings:

```python
# Optimized connection pool configuration
OPTIMIZED_POOL_SETTINGS = {
    # Base pool size - connections always available
    "pool_size": 10,

    # Overflow - additional connections when needed
    "max_overflow": 20,

    # Connection timeout - how long to wait for connection
    "pool_timeout": 30,

    # Connection recycling - prevent stale connections
    "pool_recycle": 3600,  # 1 hour

    # Pre-ping - test connections before use
    "pool_pre_ping": True,

    # Pool reset on return - clean up connections
    "pool_reset_on_return": "commit"
}

# Apply optimized settings
def configure_optimized_database():
    """Configure database with optimized settings."""

    import os

    # Set optimized environment variables
    os.environ.update({
        "PRODUCTION_GLOBAL_RPA_DB_POOL_SIZE": "10",
        "PRODUCTION_GLOBAL_RPA_DB_MAX_OVERFLOW": "20",
        "PRODUCTION_GLOBAL_RPA_DB_POOL_TIMEOUT": "30",
        "PRODUCTION_GLOBAL_RPA_DB_POOL_RECYCLE": "3600",
        "PRODUCTION_GLOBAL_RPA_DB_POOL_PRE_PING": "true"
    })

    print("Optimized database configuration applied")
```

## Container Optimization

### Resource Allocation

Optimize container resource allocation:

```yaml
# Optimized Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rpa-processor-optimized
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: rpa-processor
          image: rpa-processor:optimized

          # Optimized resource allocation
          resources:
            requests:
              memory: "1Gi" # Guaranteed memory
              cpu: "500m" # Guaranteed CPU
            limits:
              memory: "2Gi" # Maximum memory
              cpu: "1000m" # Maximum CPU

          # Environment variables for optimization
          env:
            - name: PYTHONUNBUFFERED
              value: "1"
            - name: PYTHONOPTIMIZE
              value: "1" # Enable Python optimizations
            - name: OMP_NUM_THREADS
              value: "2" # Limit OpenMP threads

          # Optimized health checks
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 60
            periodSeconds: 30
            timeoutSeconds: 10
            failureThreshold: 3

          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 5
            failureThreshold: 2

          # Volume mounts for temporary storage
          volumeMounts:
            - name: tmp-storage
              mountPath: /tmp

      volumes:
        - name: tmp-storage
          emptyDir:
            sizeLimit: "1Gi"

      # Node selection for performance
      nodeSelector:
        node-type: "compute-optimized"

      # Pod anti-affinity for distribution
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - rpa-processor
                topologyKey: kubernetes.io/hostname
```

### Container Image Optimization

Optimize container images for performance:

```dockerfile
# Optimized Dockerfile
FROM python:3.11-slim

# Install system dependencies efficiently
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with optimizations
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Set Python optimizations
ENV PYTHONUNBUFFERED=1
ENV PYTHONOPTIMIZE=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "from core.distributed import DistributedProcessor; from core.database import DatabaseManager; DistributedProcessor(DatabaseManager('rpa_db')).health_check()"

# Default command
CMD ["python", "main.py"]
```

## Configuration Tuning

### Batch Size Optimization

Find optimal batch sizes for your workload:

```python
#!/usr/bin/env python3
"""Batch size optimization testing."""

import time
from datetime import datetime
from core.distributed import DistributedProcessor
from core.database import DatabaseManager

def test_batch_sizes(flow_name: str, test_sizes: list = None):
    """Test different batch sizes to find optimal performance."""

    if test_sizes is None:
        test_sizes = [10, 25, 50, 100, 200, 500]

    processor = DistributedProcessor(DatabaseManager('rpa_db'))

    # Ensure we have test data
    test_records = [{"test_id": i, "data": f"test_data_{i}"} for i in range(1000)]
    processor.add_records_to_queue(f"{flow_name}_batch_test", test_records)

    results = []

    for batch_size in test_sizes:
        print(f"\nTesting batch size: {batch_size}")

        # Measure processing time
        start_time = time.time()

        records = processor.claim_records_batch(f"{flow_name}_batch_test", batch_size)

        if not records:
            print(f"No records available for batch size {batch_size}")
            continue

        # Simulate processing
        for record in records:
            # Simulate work
            time.sleep(0.01)  # 10ms per record
            processor.mark_record_completed(record['id'], {"processed": True})

        end_time = time.time()

        processing_time = end_time - start_time
        records_per_second = len(records) / processing_time if processing_time > 0 else 0

        result = {
            "batch_size": batch_size,
            "records_processed": len(records),
            "processing_time": processing_time,
            "records_per_second": records_per_second,
            "time_per_record": processing_time / len(records) if len(records) > 0 else 0
        }

        results.append(result)

        print(f"  Records: {len(records)}")
        print(f"  Time: {processing_time:.2f}s")
        print(f"  Rate: {records_per_second:.1f} records/sec")

    # Find optimal batch size
    if results:
        optimal = max(results, key=lambda x: x['records_per_second'])
        print(f"\n🏆 Optimal batch size: {optimal['batch_size']} ({optimal['records_per_second']:.1f} records/sec)")

    return results

def batch_size_recommendations():
    """Provide batch size recommendations based on workload characteristics."""

    recommendations = {
        "cpu_intensive": {
            "description": "CPU-intensive processing (complex calculations, data transformation)",
            "recommended_batch_size": "25-50",
            "reasoning": "Smaller batches prevent CPU saturation and allow better parallelization"
        },
        "io_intensive": {
            "description": "I/O-intensive processing (file operations, external API calls)",
            "recommended_batch_size": "100-200",
            "reasoning": "Larger batches amortize I/O overhead and improve throughput"
        },
        "memory_intensive": {
            "description": "Memory-intensive processing (large data structures, image processing)",
            "recommended_batch_size": "10-25",
            "reasoning": "Smaller batches prevent memory exhaustion and OOM errors"
        },
        "database_intensive": {
            "description": "Database-intensive processing (complex queries, large transactions)",
            "recommended_batch_size": "50-100",
            "reasoning": "Moderate batches balance transaction size and connection usage"
        },
        "mixed_workload": {
            "description": "Mixed workload with varying processing requirements",
            "recommended_batch_size": "50-75",
            "reasoning": "Balanced approach that works well for most scenarios"
        }
    }

    print("=== Batch Size Recommendations ===\n")

    for workload_type, info in recommendations.items():
        print(f"📊 {workload_type.replace('_', ' ').title()}")
        print(f"   Description: {info['description']}")
        print(f"   Recommended: {info['recommended_batch_size']} records")
        print(f"   Reasoning: {info['reasoning']}\n")

if __name__ == "__main__":
    batch_size_recommendations()
    # test_batch_sizes("performance_test")
```

### Timeout Configuration

Optimize timeout settings:

```python
# Optimized timeout configuration
OPTIMIZED_TIMEOUTS = {
    # Database timeouts
    "database_query_timeout": 30,          # 30 seconds for queries
    "database_connection_timeout": 10,     # 10 seconds to establish connection

    # Processing timeouts
    "record_processing_timeout": 300,      # 5 minutes per record
    "batch_processing_timeout": 1800,      # 30 minutes per batch

    # Cleanup timeouts
    "orphaned_record_timeout_hours": 2,    # 2 hours before cleanup
    "failed_record_retry_hours": 24,       # 24 hours before permanent failure

    # Health check timeouts
    "health_check_timeout": 5,             # 5 seconds for health checks
    "monitoring_query_timeout": 10,        # 10 seconds for monitoring queries
}

def apply_optimized_timeouts():
    """Apply optimized timeout configuration."""

    import os

    # Convert to environment variables
    env_vars = {
        "PRODUCTION_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS": str(OPTIMIZED_TIMEOUTS["orphaned_record_timeout_hours"]),
        "PRODUCTION_DISTRIBUTED_PROCESSOR_QUERY_TIMEOUT": str(OPTIMIZED_TIMEOUTS["database_query_timeout"]),
        "PRODUCTION_DISTRIBUTED_PROCESSOR_CONNECTION_TIMEOUT": str(OPTIMIZED_TIMEOUTS["database_connection_timeout"]),
        "PRODUCTION_DISTRIBUTED_PROCESSOR_PROCESSING_TIMEOUT": str(OPTIMIZED_TIMEOUTS["record_processing_timeout"]),
    }

    for key, value in env_vars.items():
        os.environ[key] = value

    print("Optimized timeout configuration applied")
```

## Memory Management

### Memory-Efficient Processing

Implement memory-efficient processing patterns:

```python
class MemoryEfficientProcessor:
    """Memory-efficient distributed processor."""

    def __init__(self):
        self.db_manager = DatabaseManager('rpa_db')
        self.processor = DistributedProcessor(self.db_manager)

        # Memory monitoring
        self.memory_threshold_mb = 1500  # Alert at 1.5GB
        self.gc_frequency = 100          # Force GC every 100 records

    def process_with_memory_management(self, flow_name: str, batch_size: int = 50):
        """Process records with active memory management."""

        import gc
        import psutil

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024

        records_processed = 0

        while True:
            # Claim smaller batches to manage memory
            records = self.processor.claim_records_batch(flow_name, batch_size)

            if not records:
                break

            # Process records with memory monitoring
            for i, record in enumerate(records):
                try:
                    # Process record
                    result = self.process_record_efficiently(record['payload'])

                    # Mark completed
                    self.processor.mark_record_completed(record['id'], result)

                    records_processed += 1

                    # Memory management
                    if records_processed % self.gc_frequency == 0:
                        # Force garbage collection
                        gc.collect()

                        # Check memory usage
                        current_memory = process.memory_info().rss / 1024 / 1024
                        memory_growth = current_memory - initial_memory

                        if current_memory > self.memory_threshold_mb:
                            logger.warning(f"High memory usage: {current_memory:.1f}MB (growth: {memory_growth:.1f}MB)")

                        # Clear any large objects
                        if hasattr(result, 'large_data'):
                            del result.large_data

                except Exception as e:
                    self.processor.mark_record_failed(record['id'], str(e))

            # Clear batch from memory
            del records
            gc.collect()

        final_memory = process.memory_info().rss / 1024 / 1024
        memory_growth = final_memory - initial_memory

        return {
            "records_processed": records_processed,
            "initial_memory_mb": initial_memory,
            "final_memory_mb": final_memory,
            "memory_growth_mb": memory_growth
        }

    def process_record_efficiently(self, payload: dict) -> dict:
        """Process individual record with memory efficiency."""

        # Use generators for large datasets
        def process_large_dataset(data):
            for chunk in self.chunk_data(data, chunk_size=1000):
                yield self.process_chunk(chunk)

        # Stream processing instead of loading all data
        if 'large_dataset' in payload:
            results = list(process_large_dataset(payload['large_dataset']))
        else:
            results = self.process_standard_record(payload)

        # Return minimal result set
        return {
            "status": "completed",
            "record_count": len(results) if isinstance(results, list) else 1,
            "processed_at": datetime.now().isoformat()
            # Don't include large result data in return value
        }

    def chunk_data(self, data, chunk_size=1000):
        """Yield successive chunks from data."""
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]
```

### Memory Monitoring

Implement memory monitoring and alerting:

```python
import psutil
import gc
from datetime import datetime

class MemoryMonitor:
    """Monitor and manage memory usage."""

    def __init__(self, warning_threshold_mb=1000, critical_threshold_mb=1500):
        self.warning_threshold = warning_threshold_mb
        self.critical_threshold = critical_threshold_mb
        self.process = psutil.Process()
        self.baseline_memory = self.get_memory_usage()

    def get_memory_usage(self):
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024

    def check_memory_usage(self):
        """Check current memory usage and return status."""
        current_memory = self.get_memory_usage()
        memory_growth = current_memory - self.baseline_memory

        status = {
            "current_mb": current_memory,
            "baseline_mb": self.baseline_memory,
            "growth_mb": memory_growth,
            "timestamp": datetime.now().isoformat()
        }

        if current_memory > self.critical_threshold:
            status["level"] = "critical"
            status["message"] = f"Critical memory usage: {current_memory:.1f}MB"
        elif current_memory > self.warning_threshold:
            status["level"] = "warning"
            status["message"] = f"High memory usage: {current_memory:.1f}MB"
        else:
            status["level"] = "normal"
            status["message"] = f"Normal memory usage: {current_memory:.1f}MB"

        return status

    def force_cleanup(self):
        """Force memory cleanup."""
        # Force garbage collection
        collected = gc.collect()

        # Get memory after cleanup
        memory_after = self.get_memory_usage()

        return {
            "objects_collected": collected,
            "memory_after_mb": memory_after,
            "memory_freed_mb": self.get_memory_usage() - memory_after
        }

    def get_memory_stats(self):
        """Get detailed memory statistics."""
        memory_info = self.process.memory_info()

        return {
            "rss_mb": memory_info.rss / 1024 / 1024,      # Resident Set Size
            "vms_mb": memory_info.vms / 1024 / 1024,      # Virtual Memory Size
            "percent": self.process.memory_percent(),       # Percentage of system memory
            "gc_counts": gc.get_count(),                   # Garbage collection counts
            "gc_stats": gc.get_stats()                     # Detailed GC statistics
        }

# Usage in processing flow
memory_monitor = MemoryMonitor(warning_threshold_mb=1000, critical_threshold_mb=1500)

def process_with_memory_monitoring(records):
    """Process records with memory monitoring."""

    for i, record in enumerate(records):
        # Process record
        result = process_record_logic(record['payload'])

        # Check memory every 10 records
        if i % 10 == 0:
            memory_status = memory_monitor.check_memory_usage()

            if memory_status["level"] == "critical":
                logger.error(memory_status["message"])
                # Force cleanup
                cleanup_result = memory_monitor.force_cleanup()
                logger.info(f"Forced cleanup: {cleanup_result}")
            elif memory_status["level"] == "warning":
                logger.warning(memory_status["message"])

        yield result
```

## Scaling Strategies

### Horizontal Scaling

Implement intelligent horizontal scaling:

```python
#!/usr/bin/env python3
"""Intelligent horizontal scaling for distributed processing."""

from datetime import datetime, timedelta
from core.monitoring import distributed_queue_monitoring, processing_performance_monitoring

class AutoScaler:
    """Automatic scaling based on queue depth and performance metrics."""

    def __init__(self):
        self.min_replicas = 1
        self.max_replicas = 10
        self.target_queue_depth = 100
        self.scale_up_threshold = 200
        self.scale_down_threshold = 50
        self.cooldown_minutes = 5

        self.last_scale_action = None

    def should_scale(self):
        """Determine if scaling action is needed."""

        # Check cooldown period
        if self.last_scale_action:
            cooldown_end = self.last_scale_action + timedelta(minutes=self.cooldown_minutes)
            if datetime.now() < cooldown_end:
                return None, "Cooldown period active"

        # Get current metrics
        queue_status = distributed_queue_monitoring()
        pending_records = queue_status['overall_queue_status']['pending_records']

        performance = processing_performance_monitoring(time_window_hours=1)
        processing_rate = performance['overall_metrics']['avg_processing_rate_per_hour']

        # Calculate current capacity utilization
        current_replicas = self.get_current_replicas()

        # Estimate time to clear queue at current rate
        if processing_rate > 0:
            hours_to_clear = pending_records / processing_rate
        else:
            hours_to_clear = float('inf')

        # Scaling decisions
        if pending_records > self.scale_up_threshold and current_replicas < self.max_replicas:
            # Scale up if queue is growing and we're under max replicas
            target_replicas = min(
                current_replicas + 1,
                self.max_replicas,
                max(2, int(pending_records / self.target_queue_depth))
            )
            return "scale_up", f"Queue depth {pending_records} > threshold {self.scale_up_threshold}, scaling to {target_replicas}"

        elif pending_records < self.scale_down_threshold and current_replicas > self.min_replicas and hours_to_clear < 2:
            # Scale down if queue is small and we can handle it with fewer replicas
            target_replicas = max(
                current_replicas - 1,
                self.min_replicas,
                max(1, int(pending_records / self.target_queue_depth))
            )
            return "scale_down", f"Queue depth {pending_records} < threshold {self.scale_down_threshold}, scaling to {target_replicas}"

        return None, f"No scaling needed. Queue: {pending_records}, Rate: {processing_rate:.1f}/hr, Replicas: {current_replicas}"

    def get_current_replicas(self):
        """Get current number of replicas."""
        import subprocess

        try:
            # Kubernetes
            result = subprocess.run(
                ["kubectl", "get", "deployment", "rpa-processor", "-o", "jsonpath={.spec.replicas}"],
                capture_output=True, text=True, check=True
            )
            return int(result.stdout.strip())
        except:
            # Default if can't determine
            return 3

    def scale_deployment(self, target_replicas):
        """Scale the deployment to target replicas."""
        import subprocess

        try:
            # Kubernetes scaling
            subprocess.run(
                ["kubectl", "scale", "deployment", "rpa-processor", f"--replicas={target_replicas}"],
                check=True
            )

            self.last_scale_action = datetime.now()
            return True
        except Exception as e:
            print(f"Failed to scale deployment: {e}")
            return False

    def auto_scale_check(self):
        """Perform automatic scaling check."""

        action, reason = self.should_scale()

        print(f"[{datetime.now()}] Scaling check: {reason}")

        if action == "scale_up":
            current_replicas = self.get_current_replicas()
            target_replicas = min(current_replicas + 1, self.max_replicas)

            if self.scale_deployment(target_replicas):
                print(f"✅ Scaled up from {current_replicas} to {target_replicas} replicas")
            else:
                print(f"❌ Failed to scale up to {target_replicas} replicas")

        elif action == "scale_down":
            current_replicas = self.get_current_replicas()
            target_replicas = max(current_replicas - 1, self.min_replicas)

            if self.scale_deployment(target_replicas):
                print(f"✅ Scaled down from {current_replicas} to {target_replicas} replicas")
            else:
                print(f"❌ Failed to scale down to {target_replicas} replicas")

# Usage
def run_autoscaler():
    """Run autoscaler as a monitoring service."""

    autoscaler = AutoScaler()

    while True:
        try:
            autoscaler.auto_scale_check()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            print("Autoscaler stopped")
            break
        except Exception as e:
            print(f"Autoscaler error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    run_autoscaler()
```

### Vertical Scaling

Optimize resource allocation per container:

```yaml
# Vertical scaling configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: scaling-profiles
data:
  light-workload.yaml: |
    resources:
      requests:
        memory: "512Mi"
        cpu: "250m"
      limits:
        memory: "1Gi"
        cpu: "500m"

  medium-workload.yaml: |
    resources:
      requests:
        memory: "1Gi"
        cpu: "500m"
      limits:
        memory: "2Gi"
        cpu: "1000m"

  heavy-workload.yaml: |
    resources:
      requests:
        memory: "2Gi"
        cpu: "1000m"
      limits:
        memory: "4Gi"
        cpu: "2000m"
```

## Performance Testing

### Load Testing Framework

Implement comprehensive load testing:

```python
#!/usr/bin/env python3
"""Load testing framework for distributed processing system."""

import time
import threading
import concurrent.futures
from datetime import datetime, timedelta
from core.distributed import DistributedProcessor
from core.database import DatabaseManager
from core.monitoring import processing_performance_monitoring

class LoadTester:
    """Load testing framework for distributed processing."""

    def __init__(self):
        self.processor = DistributedProcessor(DatabaseManager('rpa_db'))
        self.results = []

    def generate_test_data(self, num_records: int, flow_name: str):
        """Generate test data for load testing."""

        test_records = []
        for i in range(num_records):
            test_records.append({
                "test_id": f"LOAD_TEST_{i}",
                "data": f"test_data_{i}",
                "complexity": "medium",
                "created_at": datetime.now().isoformat()
            })

        # Add to queue
        count = self.processor.add_records_to_queue(flow_name, test_records)
        print(f"Generated {count} test records for {flow_name}")

        return count

    def simulate_processing_load(self, flow_name: str, batch_size: int, duration_minutes: int):
        """Simulate processing load for specified duration."""

        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)

        records_processed = 0
        batches_processed = 0

        print(f"Starting load test: {duration_minutes} minutes, batch size {batch_size}")

        while datetime.now() < end_time:
            batch_start = time.time()

            # Claim records
            records = self.processor.claim_records_batch(flow_name, batch_size)

            if not records:
                print("No more records to process")
                break

            # Simulate processing
            for record in records:
                # Simulate work (adjust based on your actual processing complexity)
                processing_time = self.simulate_record_processing(record['payload'])

                # Mark completed
                self.processor.mark_record_completed(record['id'], {
                    "processed": True,
                    "processing_time": processing_time
                })

                records_processed += 1

            batch_end = time.time()
            batch_time = batch_end - batch_start
            batches_processed += 1

            # Log progress
            if batches_processed % 10 == 0:
                rate = records_processed / ((datetime.now() - start_time).total_seconds() / 3600)
                print(f"Processed {records_processed} records in {batches_processed} batches (rate: {rate:.1f}/hour)")

        total_time = (datetime.now() - start_time).total_seconds()

        return {
            "records_processed": records_processed,
            "batches_processed": batches_processed,
            "total_time_seconds": total_time,
            "records_per_second": records_processed / total_time if total_time > 0 else 0,
            "records_per_hour": records_processed / (total_time / 3600) if total_time > 0 else 0
        }

    def simulate_record_processing(self, payload: dict) -> float:
        """Simulate record processing with realistic timing."""

        complexity = payload.get('complexity', 'medium')

        # Simulate different processing complexities
        if complexity == 'light':
            time.sleep(0.01)  # 10ms
            return 0.01
        elif complexity == 'medium':
            time.sleep(0.05)  # 50ms
            return 0.05
        elif complexity == 'heavy':
            time.sleep(0.2)   # 200ms
            return 0.2
        else:
            time.sleep(0.05)  # Default 50ms
            return 0.05

    def concurrent_load_test(self, flow_name: str, num_workers: int, batch_size: int, duration_minutes: int):
        """Run concurrent load test with multiple workers."""

        print(f"Starting concurrent load test: {num_workers} workers, {duration_minutes} minutes")

        # Generate enough test data
        total_records_needed = num_workers * batch_size * (duration_minutes * 2)  # Extra buffer
        self.generate_test_data(total_records_needed, flow_name)

        # Run concurrent workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []

            for worker_id in range(num_workers):
                future = executor.submit(
                    self.simulate_processing_load,
                    flow_name,
                    batch_size,
                    duration_minutes
                )
                futures.append(future)

            # Collect results
            worker_results = []
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                result = future.result()
                result['worker_id'] = i
                worker_results.append(result)
                print(f"Worker {i} completed: {result['records_processed']} records")

        # Aggregate results
        total_records = sum(r['records_processed'] for r in worker_results)
        total_time = max(r['total_time_seconds'] for r in worker_results)

        aggregate_result = {
            "num_workers": num_workers,
            "total_records_processed": total_records,
            "total_time_seconds": total_time,
            "aggregate_records_per_second": total_records / total_time if total_time > 0 else 0,
            "aggregate_records_per_hour": total_records / (total_time / 3600) if total_time > 0 else 0,
            "worker_results": worker_results
        }

        return aggregate_result

    def performance_benchmark(self):
        """Run comprehensive performance benchmark."""

        print("=== Performance Benchmark ===")

        test_scenarios = [
            {"workers": 1, "batch_size": 50, "duration": 5, "name": "Single Worker Baseline"},
            {"workers": 2, "batch_size": 50, "duration": 5, "name": "Dual Worker"},
            {"workers": 4, "batch_size": 50, "duration": 5, "name": "Quad Worker"},
            {"workers": 2, "batch_size": 25, "duration": 5, "name": "Small Batch"},
            {"workers": 2, "batch_size": 100, "duration": 5, "name": "Large Batch"},
        ]

        benchmark_results = []

        for scenario in test_scenarios:
            print(f"\n--- Running: {scenario['name']} ---")

            result = self.concurrent_load_test(
                f"benchmark_{scenario['name'].lower().replace(' ', '_')}",
                scenario['workers'],
                scenario['batch_size'],
                scenario['duration']
            )

            result['scenario'] = scenario
            benchmark_results.append(result)

            print(f"Result: {result['aggregate_records_per_hour']:.1f} records/hour")

        # Find best performing scenario
        best_scenario = max(benchmark_results, key=lambda x: x['aggregate_records_per_hour'])

        print(f"\n🏆 Best Performance: {best_scenario['scenario']['name']}")
        print(f"   Rate: {best_scenario['aggregate_records_per_hour']:.1f} records/hour")
        print(f"   Workers: {best_scenario['num_workers']}")
        print(f"   Batch Size: {best_scenario['scenario']['batch_size']}")

        return benchmark_results

# Usage
if __name__ == "__main__":
    tester = LoadTester()

    # Run performance benchmark
    results = tester.performance_benchmark()

    # Save results
    import json
    with open(f'benchmark_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)
```

### Performance Regression Testing

Implement automated performance regression testing:

```python
#!/usr/bin/env python3
"""Performance regression testing."""

import json
from datetime import datetime
from pathlib import Path

class PerformanceRegressionTester:
    """Test for performance regressions."""

    def __init__(self, baseline_file="performance_baseline.json"):
        self.baseline_file = baseline_file
        self.regression_threshold = 0.1  # 10% regression threshold

    def load_baseline(self):
        """Load performance baseline."""
        try:
            with open(self.baseline_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Baseline file {self.baseline_file} not found")
            return None

    def run_regression_test(self):
        """Run performance regression test."""

        baseline = self.load_baseline()
        if not baseline:
            print("No baseline available for regression testing")
            return False

        # Get current performance
        from core.monitoring import processing_performance_monitoring

        current_perf = processing_performance_monitoring(time_window_hours=6)

        # Compare key metrics
        metrics_to_check = [
            ("success_rate_percent", "higher_is_better"),
            ("avg_processing_rate_per_hour", "higher_is_better"),
            ("avg_processing_time_minutes", "lower_is_better")
        ]

        regressions = []

        for metric, direction in metrics_to_check:
            if metric in baseline and metric in current_perf['overall_metrics']:
                baseline_value = baseline[metric]
                current_value = current_perf['overall_metrics'][metric]

                if baseline_value == 0:
                    continue

                change_percent = (current_value - baseline_value) / baseline_value

                # Check for regression
                is_regression = False
                if direction == "higher_is_better" and change_percent < -self.regression_threshold:
                    is_regression = True
                elif direction == "lower_is_better" and change_percent > self.regression_threshold:
                    is_regression = True

                if is_regression:
                    regressions.append({
                        "metric": metric,
                        "baseline_value": baseline_value,
                        "current_value": current_value,
                        "change_percent": change_percent * 100,
                        "direction": direction
                    })

        # Report results
        if regressions:
            print("❌ Performance regressions detected:")
            for regression in regressions:
                print(f"   {regression['metric']}: {regression['change_percent']:+.1f}% "
                      f"({regression['baseline_value']:.2f} → {regression['current_value']:.2f})")
            return False
        else:
            print("✅ No performance regressions detected")
            return True

# Integration with CI/CD
def ci_performance_check():
    """Performance check for CI/CD pipeline."""

    tester = PerformanceRegressionTester()

    # Run regression test
    passed = tester.run_regression_test()

    if not passed:
        print("Performance regression detected - failing build")
        exit(1)
    else:
        print("Performance check passed")
        exit(0)

if __name__ == "__main__":
    ci_performance_check()
```

## Conclusion

Performance optimization is an ongoing process that requires:

1. **Baseline Measurement**: Establish clear performance baselines
2. **Systematic Testing**: Test changes systematically with proper measurement
3. **Monitoring**: Continuous monitoring of key performance metrics
4. **Iterative Improvement**: Regular optimization cycles based on real-world usage
5. **Documentation**: Document optimization changes and their impact

### Key Performance Optimization Areas

- **Database**: Proper indexing, query optimization, connection pooling
- **Application**: Memory management, batch size tuning, efficient algorithms
- **Infrastructure**: Resource allocation, scaling strategies, container optimization
- **Configuration**: Timeout tuning, environment-specific optimization

### Monitoring and Alerting

Set up monitoring for:

- Processing rates and success rates
- Database performance metrics
- Memory and CPU usage
- Queue depth and health
- Error rates and patterns

Regular performance reviews and optimization cycles will ensure your distributed processing system continues to perform optimally as your workload grows and changes.

For additional guidance, refer to:

- [API Reference](API_REFERENCE.md) for detailed API documentation
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) for performance issue resolution
- [Operations Runbook](DISTRIBUTED_PROCESSING_OPERATIONS_RUNBOOK.md) for operational best practices
