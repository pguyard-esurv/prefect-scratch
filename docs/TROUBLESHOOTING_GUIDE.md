# Troubleshooting Guide

## Overview

This guide helps you diagnose and resolve common issues with the distributed processing system. It covers symptoms, root causes, and step-by-step solutions.

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [Common Issues](#common-issues)
3. [Performance Issues](#performance-issues)
4. [Configuration Issues](#configuration-issues)
5. [Database Issues](#database-issues)
6. [Container Issues](#container-issues)
7. [Monitoring and Debugging](#monitoring-and-debugging)
8. [Emergency Procedures](#emergency-procedures)

## Quick Diagnostics

### Health Check Commands

Run these commands to quickly assess system health:

```bash
# Overall system health
python -c "
from core.distributed import DistributedProcessor
from core.database import DatabaseManager
processor = DistributedProcessor(DatabaseManager('rpa_db'))
health = processor.health_check()
print(f'System Status: {health[\"status\"]}')
print(f'Database Health: {health[\"databases\"]}')
"

# Queue status
python -c "
from core.monitoring import distributed_queue_monitoring
status = distributed_queue_monitoring()
print(f'Queue Health: {status[\"queue_health_assessment\"][\"queue_health\"]}')
print(f'Pending Records: {status[\"overall_queue_status\"][\"pending_records\"]}')
print(f'Failed Records: {status[\"overall_queue_status\"][\"failed_records\"]}')
"

# Performance metrics
python -c "
from core.monitoring import processing_performance_monitoring
perf = processing_performance_monitoring(time_window_hours=6)
print(f'Success Rate: {perf[\"overall_metrics\"][\"success_rate_percent\"]}%')
print(f'Processing Rate: {perf[\"overall_metrics\"][\"avg_processing_rate_per_hour\"]} records/hour')
"
```

### Quick Status Dashboard

```python
#!/usr/bin/env python3
"""Quick status dashboard for distributed processing system."""

from core.distributed import DistributedProcessor
from core.database import DatabaseManager
from core.monitoring import distributed_queue_monitoring, processing_performance_monitoring

def quick_status():
    """Display quick system status."""

    print("=== Distributed Processing System Status ===\n")

    try:
        # System health
        processor = DistributedProcessor(DatabaseManager('rpa_db'))
        health = processor.health_check()

        print(f"🏥 System Health: {health['status'].upper()}")

        # Database status
        for db_name, db_status in health['databases'].items():
            status_icon = "✅" if db_status['status'] == 'healthy' else "❌"
            print(f"   {status_icon} {db_name}: {db_status['status']} ({db_status['response_time_ms']:.1f}ms)")

        # Queue status
        queue_status = distributed_queue_monitoring()
        queue_health = queue_status['queue_health_assessment']['queue_health']
        queue_icon = "✅" if queue_health == 'healthy' else "⚠️" if queue_health == 'degraded' else "❌"

        print(f"\n📊 Queue Health: {queue_icon} {queue_health.upper()}")

        overall = queue_status['overall_queue_status']
        print(f"   📝 Total Records: {overall['total_records']}")
        print(f"   ⏳ Pending: {overall['pending_records']}")
        print(f"   🔄 Processing: {overall['processing_records']}")
        print(f"   ✅ Completed: {overall['completed_records']}")
        print(f"   ❌ Failed: {overall['failed_records']}")

        # Performance metrics
        perf = processing_performance_monitoring(time_window_hours=6)
        success_rate = perf['overall_metrics']['success_rate_percent']
        processing_rate = perf['overall_metrics']['avg_processing_rate_per_hour']

        perf_icon = "✅" if success_rate >= 95 else "⚠️" if success_rate >= 80 else "❌"

        print(f"\n📈 Performance (6h): {perf_icon}")
        print(f"   ✅ Success Rate: {success_rate:.1f}%")
        print(f"   🚀 Processing Rate: {processing_rate:.1f} records/hour")

        # Alerts
        alerts = queue_status.get('operational_alerts', [])
        if alerts:
            print(f"\n🚨 Alerts:")
            for alert in alerts:
                print(f"   ⚠️  {alert}")
        else:
            print(f"\n✅ No active alerts")

    except Exception as e:
        print(f"❌ Error getting system status: {e}")
        return False

    return True

if __name__ == "__main__":
    quick_status()
```

Save as `scripts/quick_status.py` and run: `python scripts/quick_status.py`

## Common Issues

### Issue 1: No Records Being Processed

**Symptoms:**

- Queue has pending records but processing doesn't start
- `claim_records_batch()` returns empty list
- Containers are running but idle

**Diagnosis:**

```python
# Check queue status
from core.distributed import DistributedProcessor
from core.database import DatabaseManager

processor = DistributedProcessor(DatabaseManager('rpa_db'))
status = processor.get_queue_status()

print(f"Pending records: {status['pending_records']}")
print(f"Processing records: {status['processing_records']}")

# Try manual claim
records = processor.claim_records_batch("your_flow_name", 5)
print(f"Claimed {len(records)} records")
```

**Common Causes & Solutions:**

1. **Flow name mismatch**

   ```python
   # Check what flow names exist in queue
   from core.database import DatabaseManager
   db = DatabaseManager('rpa_db')
   flows = db.execute_query("rpa_db", "SELECT DISTINCT flow_name FROM processing_queue WHERE status = 'pending'")
   print("Available flows:", [f[0] for f in flows])
   ```

2. **Database connectivity issues**

   ```python
   # Test database connection
   from core.tasks import database_health_check
   health = database_health_check("rpa_db")
   print(f"Database health: {health}")
   ```

3. **Records stuck in processing state**

   ```python
   # Clean up orphaned records
   cleaned = processor.cleanup_orphaned_records(timeout_hours=1)
   print(f"Cleaned up {cleaned} orphaned records")
   ```

4. **Configuration issues**
   ```python
   # Check configuration
   from core.config import ConfigManager
   config = ConfigManager("your_flow_name")
   use_distributed = config.get_variable("use_distributed_processing", False)
   print(f"Distributed processing enabled: {use_distributed}")
   ```

### Issue 2: High Error Rates

**Symptoms:**

- Many records marked as failed
- Success rate below 80%
- Error messages in processing_queue.error_message

**Diagnosis:**

```python
# Analyze error patterns
from core.database import DatabaseManager

db = DatabaseManager('rpa_db')

# Get top error messages
errors = db.execute_query("rpa_db", """
    SELECT
        error_message,
        COUNT(*) as count,
        MIN(created_at) as first_seen,
        MAX(updated_at) as last_seen
    FROM processing_queue
    WHERE status = 'failed'
    AND updated_at > NOW() - INTERVAL '24 hours'
    GROUP BY error_message
    ORDER BY count DESC
    LIMIT 10
""")

print("Top errors in last 24 hours:")
for error, count, first, last in errors:
    print(f"{count:3d}: {error[:100]}...")
    print(f"     First: {first}, Last: {last}")
```

**Common Causes & Solutions:**

1. **Business logic errors**

   - Review error messages for patterns
   - Add input validation
   - Handle edge cases gracefully

   ```python
   def process_record_logic(payload):
       try:
           # Validate input
           if not payload.get('required_field'):
               raise ValueError("Missing required field")

           # Your business logic
           result = process_data(payload)
           return result

       except ValueError as e:
           # Handle validation errors
           raise e
       except Exception as e:
           # Log unexpected errors
           logger.error(f"Unexpected error processing {payload}: {e}")
           raise
   ```

2. **External service failures**

   - Implement retry logic with exponential backoff
   - Add circuit breaker pattern
   - Use fallback mechanisms

   ```python
   from tenacity import retry, stop_after_attempt, wait_exponential

   @retry(
       stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=4, max=10)
   )
   def call_external_service(data):
       # External service call
       response = requests.post(api_url, json=data, timeout=30)
       response.raise_for_status()
       return response.json()
   ```

3. **Database connectivity issues**

   ```python
   # Check database health
   from core.tasks import database_health_check
   health = database_health_check("source_db")
   if health['status'] != 'healthy':
       print(f"Source database issue: {health}")
   ```

4. **Resource exhaustion**
   ```python
   # Check connection pool status
   from core.tasks import connection_pool_monitoring
   pool_status = connection_pool_monitoring("rpa_db")
   if pool_status['utilization_percent'] > 90:
       print("Connection pool near capacity")
   ```

### Issue 3: Records Stuck in Processing

**Symptoms:**

- Records with old `claimed_at` timestamps
- Processing count doesn't decrease
- No progress in queue processing

**Diagnosis:**

```python
# Check for orphaned records
from core.database import DatabaseManager

db = DatabaseManager('rpa_db')

orphaned = db.execute_query("rpa_db", """
    SELECT
        flow_name,
        flow_instance_id,
        COUNT(*) as count,
        MIN(claimed_at) as oldest_claim,
        MAX(claimed_at) as newest_claim
    FROM processing_queue
    WHERE status = 'processing'
    AND claimed_at < NOW() - INTERVAL '1 hour'
    GROUP BY flow_name, flow_instance_id
    ORDER BY count DESC
""")

print("Orphaned records by instance:")
for flow, instance, count, oldest, newest in orphaned:
    print(f"{flow} ({instance}): {count} records, oldest: {oldest}")
```

**Common Causes & Solutions:**

1. **Container crashes**

   ```bash
   # Check container status (Kubernetes)
   kubectl get pods -l app=rpa-processor
   kubectl logs -l app=rpa-processor --tail=100

   # Check container status (Docker)
   docker ps --filter "name=rpa"
   docker logs rpa-container --tail=100
   ```

2. **Long-running processes**

   - Optimize business logic
   - Break down large operations
   - Add progress tracking

   ```python
   def process_large_dataset(payload):
       data = payload['large_dataset']

       # Process in chunks
       chunk_size = 1000
       results = []

       for i in range(0, len(data), chunk_size):
           chunk = data[i:i+chunk_size]
           chunk_result = process_chunk(chunk)
           results.extend(chunk_result)

           # Log progress
           logger.info(f"Processed {i+len(chunk)}/{len(data)} records")

       return results
   ```

3. **Database deadlocks**

   ```sql
   -- Check for deadlocks (PostgreSQL)
   SELECT
       blocked_locks.pid AS blocked_pid,
       blocked_activity.usename AS blocked_user,
       blocking_locks.pid AS blocking_pid,
       blocking_activity.usename AS blocking_user,
       blocked_activity.query AS blocked_statement,
       blocking_activity.query AS current_statement_in_blocking_process
   FROM pg_catalog.pg_locks blocked_locks
   JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
   JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
   JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
   WHERE NOT blocked_locks.granted;
   ```

4. **Manual cleanup**

   ```python
   # Clean up orphaned records
   from core.distributed import DistributedProcessor
   from core.database import DatabaseManager

   processor = DistributedProcessor(DatabaseManager('rpa_db'))

   # Clean up records stuck for more than 2 hours
   cleaned = processor.cleanup_orphaned_records(timeout_hours=2)
   print(f"Cleaned up {cleaned} orphaned records")
   ```

### Issue 4: Poor Performance

**Symptoms:**

- Low processing rate (< 50 records/hour)
- High average processing time
- Large pending record backlog

**Diagnosis:**

```python
# Performance analysis
from core.monitoring import processing_performance_monitoring

perf = processing_performance_monitoring(
    time_window_hours=6,
    include_error_analysis=True
)

print(f"Processing rate: {perf['overall_metrics']['avg_processing_rate_per_hour']} records/hour")
print(f"Average processing time: {perf['overall_metrics']['avg_processing_time_minutes']} minutes")
print(f"Success rate: {perf['overall_metrics']['success_rate_percent']}%")

# Check by flow
for flow, metrics in perf['by_flow'].items():
    print(f"{flow}: {metrics['processing_rate_per_hour']} records/hour")
```

**Common Causes & Solutions:**

1. **Insufficient container instances**

   ```bash
   # Scale up containers (Kubernetes)
   kubectl scale deployment rpa-processor --replicas=5

   # Check current scaling
   kubectl get deployment rpa-processor
   ```

2. **Suboptimal batch sizes**

   ```python
   # Test different batch sizes
   from core.config import ConfigManager

   config = ConfigManager("your_flow")
   current_batch = config.get_variable("distributed_batch_size", 50)

   # Try larger batch size
   result = your_flow(use_distributed=True, batch_size=100)
   print(f"Batch size 100 result: {result}")
   ```

3. **Database performance issues**

   ```sql
   -- Check slow queries (PostgreSQL)
   SELECT
       query,
       calls,
       total_time,
       mean_time,
       rows
   FROM pg_stat_statements
   WHERE query LIKE '%processing_queue%'
   ORDER BY mean_time DESC
   LIMIT 10;
   ```

4. **Business logic optimization**

   ```python
   import time
   import cProfile

   def profile_processing():
       """Profile record processing performance."""

       # Sample record
       test_record = {"id": 1, "payload": {"test": "data"}}

       # Profile processing
       profiler = cProfile.Profile()
       profiler.enable()

       start_time = time.time()
       result = process_record_logic(test_record['payload'])
       end_time = time.time()

       profiler.disable()

       print(f"Processing time: {end_time - start_time:.2f} seconds")
       profiler.print_stats(sort='cumulative')

       return result
   ```

## Performance Issues

### Slow Database Queries

**Symptoms:**

- High database response times (> 1 second)
- Connection pool exhaustion
- Query timeouts

**Diagnosis:**

```sql
-- Check query performance (PostgreSQL)
SELECT
    query,
    calls,
    total_time / 1000 as total_seconds,
    mean_time / 1000 as mean_seconds,
    (100 * total_time / sum(total_time) OVER()) as percentage
FROM pg_stat_statements
WHERE query LIKE '%processing_queue%'
ORDER BY total_time DESC
LIMIT 10;

-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'processing_queue'
ORDER BY idx_scan DESC;
```

**Solutions:**

1. **Add missing indexes**

   ```sql
   -- Add indexes for common query patterns
   CREATE INDEX CONCURRENTLY idx_processing_queue_flow_status_created
   ON processing_queue(flow_name, status, created_at);

   CREATE INDEX CONCURRENTLY idx_processing_queue_instance_claimed
   ON processing_queue(flow_instance_id, claimed_at)
   WHERE status = 'processing';
   ```

2. **Optimize queries**

   ```python
   # Use more specific queries
   def get_queue_status_optimized(self, flow_name=None):
       if flow_name:
           # More specific query for single flow
           query = """
               SELECT status, COUNT(*)
               FROM processing_queue
               WHERE flow_name = :flow_name
               GROUP BY status
           """
           params = {"flow_name": flow_name}
       else:
           # General query
           query = """
               SELECT flow_name, status, COUNT(*)
               FROM processing_queue
               GROUP BY flow_name, status
           """
           params = {}

       return self.rpa_db.execute_query("rpa_db", query, params)
   ```

3. **Connection pool tuning**
   ```bash
   # Increase connection pool size
   PRODUCTION_GLOBAL_RPA_DB_POOL_SIZE=20
   PRODUCTION_GLOBAL_RPA_DB_MAX_OVERFLOW=40
   PRODUCTION_GLOBAL_RPA_DB_POOL_TIMEOUT=30
   ```

### Memory Issues

**Symptoms:**

- Container out-of-memory errors
- Gradual memory increase over time
- Slow garbage collection

**Diagnosis:**

```python
import psutil
import gc

def check_memory_usage():
    """Check current memory usage."""

    process = psutil.Process()
    memory_info = process.memory_info()

    print(f"RSS Memory: {memory_info.rss / 1024 / 1024:.1f} MB")
    print(f"VMS Memory: {memory_info.vms / 1024 / 1024:.1f} MB")
    print(f"Memory Percent: {process.memory_percent():.1f}%")

    # Garbage collection stats
    print(f"GC counts: {gc.get_count()}")

    return memory_info

# Monitor memory during processing
def monitor_memory_during_processing():
    """Monitor memory usage during record processing."""

    initial_memory = check_memory_usage()

    # Process some records
    processor = DistributedProcessor(DatabaseManager('rpa_db'))
    records = processor.claim_records_batch("test_flow", 100)

    # Process records and monitor memory
    for i, record in enumerate(records):
        process_record_logic(record['payload'])

        if i % 10 == 0:  # Check every 10 records
            current_memory = check_memory_usage()
            memory_diff = current_memory.rss - initial_memory.rss
            print(f"Record {i}: Memory diff: {memory_diff / 1024 / 1024:.1f} MB")
```

**Solutions:**

1. **Optimize object creation**

   ```python
   # Reuse objects instead of creating new ones
   class OptimizedProcessor:
       def __init__(self):
           # Create reusable objects
           self.db_manager = DatabaseManager('rpa_db')
           self.processor = DistributedProcessor(self.db_manager)
           self.session_cache = {}

       def process_batch(self, flow_name, batch_size):
           # Reuse processor instance
           records = self.processor.claim_records_batch(flow_name, batch_size)

           results = []
           for record in records:
               result = self.process_single_record(record)
               results.append(result)

           return results
   ```

2. **Implement proper cleanup**

   ```python
   def process_with_cleanup(records):
       """Process records with proper cleanup."""

       try:
           results = []
           for record in records:
               result = process_record_logic(record['payload'])
               results.append(result)

               # Clear large objects
               if hasattr(result, 'large_data'):
                   del result.large_data

           return results

       finally:
           # Force garbage collection
           gc.collect()
   ```

3. **Use streaming for large datasets**
   ```python
   def process_large_dataset_streaming(payload):
       """Process large dataset using streaming."""

       # Instead of loading all data into memory
       # data = load_all_data(payload['data_source'])

       # Use streaming
       results = []
       for chunk in stream_data(payload['data_source'], chunk_size=1000):
           chunk_result = process_data_chunk(chunk)
           results.extend(chunk_result)

           # Clear chunk from memory
           del chunk

       return results
   ```

## Configuration Issues

### Environment Configuration Problems

**Symptoms:**

- Configuration not found errors
- Wrong values being used
- Inconsistent behavior across environments

**Diagnosis:**

```python
# Check configuration hierarchy
from core.config import ConfigManager

def debug_configuration(flow_name, key):
    """Debug configuration lookup."""

    config = ConfigManager(flow_name)

    print(f"Environment: {config.environment}")
    print(f"Flow: {config.flow_name}")
    print(f"Looking for key: {key}")

    # Try each level of hierarchy
    levels = [
        f"{config.environment}.{config.flow_name}.{key}",
        f"{config.environment}.global.{key}",
        f"global.{key}"
    ]

    for level in levels:
        try:
            from prefect.blocks.system import Variable
            value = Variable.load(level)
            print(f"✅ Found at {level}: {value.get()}")
            return value.get()
        except ValueError:
            print(f"❌ Not found: {level}")

    print(f"❌ Key '{key}' not found at any level")
    return None

# Example usage
debug_configuration("rpa1", "batch_size")
```

**Solutions:**

1. **Set up missing configuration**

   ```bash
   # Set up all environments
   make setup-dev
   make setup-staging
   make setup-prod

   # Verify configuration
   make list-config
   ```

2. **Fix configuration hierarchy**

   ```python
   # Set configuration at appropriate level
   from prefect.blocks.system import Variable

   # Global default
   Variable(value="50").save("global.batch_size", overwrite=True)

   # Environment-specific
   Variable(value="100").save("production.global.batch_size", overwrite=True)

   # Flow-specific
   Variable(value="25").save("development.rpa1.batch_size", overwrite=True)
   ```

3. **Validate configuration**
   ```python
   def validate_flow_configuration(flow_name):
       """Validate all required configuration for a flow."""

       config = ConfigManager(flow_name)

       required_vars = [
           "use_distributed_processing",
           "distributed_batch_size",
           "cleanup_timeout_hours",
           "max_retries"
       ]

       missing = []
       invalid = []

       for var in required_vars:
           try:
               value = config.get_variable(var)
               if value is None:
                   missing.append(var)
               elif var.endswith("_size") and not isinstance(int(value), int):
                   invalid.append(f"{var}: not a number")
           except Exception as e:
               missing.append(f"{var}: {e}")

       if missing:
           print(f"❌ Missing configuration: {missing}")
       if invalid:
           print(f"❌ Invalid configuration: {invalid}")

       return len(missing) == 0 and len(invalid) == 0
   ```

### Database Configuration Issues

**Symptoms:**

- Connection string errors
- Authentication failures
- SSL/TLS connection issues

**Diagnosis:**

```python
# Test database configuration
from core.database import DatabaseManager

def test_database_config(db_name):
    """Test database configuration."""

    try:
        db = DatabaseManager(db_name)

        # Test connection
        result = db.execute_query(db_name, "SELECT 1 as test")
        print(f"✅ {db_name} connection successful")

        # Test health check
        health = db.health_check()
        print(f"✅ {db_name} health check: {health['status']}")

        return True

    except Exception as e:
        print(f"❌ {db_name} connection failed: {e}")
        return False

# Test all databases
test_database_config("rpa_db")
test_database_config("SurveyHub")
```

**Solutions:**

1. **Fix connection strings**

   ```bash
   # PostgreSQL connection string format
   DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING="postgresql://user:password@localhost:5432/database"

   # SQL Server connection string format
   DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING="mssql+pyodbc://user:password@server:1433/database?driver=ODBC+Driver+17+for+SQL+Server"
   ```

2. **Handle SSL issues**

   ```bash
   # Disable SSL for development
   DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING="postgresql://user:password@localhost:5432/database?sslmode=disable"

   # Enable SSL for production
   PRODUCTION_GLOBAL_RPA_DB_CONNECTION_STRING="postgresql://user:password@server:5432/database?sslmode=require"
   ```

3. **Test connectivity**

   ```bash
   # Test PostgreSQL connection
   psql "postgresql://user:password@localhost:5432/database" -c "SELECT version();"

   # Test SQL Server connection
   sqlcmd -S server -d database -U user -P password -Q "SELECT @@VERSION"
   ```

## Database Issues

### Connection Pool Exhaustion

**Symptoms:**

- "QueuePool limit of size X overflow Y reached" errors
- Long wait times for database connections
- Timeouts during database operations

**Diagnosis:**

```python
# Monitor connection pool
from core.tasks import connection_pool_monitoring

def monitor_all_pools():
    """Monitor all database connection pools."""

    databases = ["rpa_db", "SurveyHub"]

    for db_name in databases:
        try:
            status = connection_pool_monitoring(db_name)

            print(f"\n{db_name} Connection Pool:")
            print(f"  Size: {status['pool_size']}")
            print(f"  Checked out: {status['checked_out']}")
            print(f"  Overflow: {status['overflow']}")
            print(f"  Utilization: {status['utilization_percent']:.1f}%")

            if status['utilization_percent'] > 80:
                print(f"  ⚠️  High utilization!")

        except Exception as e:
            print(f"❌ Error monitoring {db_name}: {e}")

monitor_all_pools()
```

**Solutions:**

1. **Increase pool size**

   ```bash
   # Increase connection pool settings
   PRODUCTION_GLOBAL_RPA_DB_POOL_SIZE=25
   PRODUCTION_GLOBAL_RPA_DB_MAX_OVERFLOW=50
   PRODUCTION_GLOBAL_RPA_DB_POOL_TIMEOUT=60
   ```

2. **Fix connection leaks**

   ```python
   # Ensure proper connection cleanup
   class ProperConnectionUsage:
       def __init__(self):
           self.db = DatabaseManager('rpa_db')

       def process_with_proper_cleanup(self, records):
           """Process records with proper connection management."""

           try:
               # Use context manager for transactions
               with self.db.get_connection() as conn:
                   for record in records:
                       # Process record
                       result = self.process_record(record, conn)

                       # Commit after each record or batch
                       conn.commit()

           except Exception as e:
               # Connection automatically closed by context manager
               raise e
   ```

3. **Optimize connection usage**
   ```python
   # Batch operations to reduce connection usage
   def batch_database_operations(records):
       """Batch database operations for efficiency."""

       db = DatabaseManager('rpa_db')

       # Batch inserts instead of individual operations
       insert_data = []
       for record in records:
           insert_data.append({
               'id': record['id'],
               'result': json.dumps(record['result']),
               'completed_at': datetime.now()
           })

       # Single batch insert
       query = """
           INSERT INTO processed_results (id, result, completed_at)
           VALUES (%(id)s, %(result)s, %(completed_at)s)
       """

       db.execute_batch(query, insert_data)
   ```

### Database Deadlocks

**Symptoms:**

- "deadlock detected" errors
- Transactions that hang indefinitely
- Inconsistent processing results

**Diagnosis:**

```sql
-- Monitor deadlocks (PostgreSQL)
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS current_statement_in_blocking_process
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- Check for long-running transactions
SELECT
    pid,
    usename,
    application_name,
    state,
    query_start,
    NOW() - query_start AS duration,
    query
FROM pg_stat_activity
WHERE state != 'idle'
AND NOW() - query_start > INTERVAL '5 minutes'
ORDER BY duration DESC;
```

**Solutions:**

1. **Optimize locking order**

   ```python
   # Always acquire locks in consistent order
   def update_multiple_records(record_ids):
       """Update multiple records with consistent locking order."""

       # Sort IDs to ensure consistent lock order
       sorted_ids = sorted(record_ids)

       query = """
           UPDATE processing_queue
           SET status = 'completed', completed_at = NOW()
           WHERE id = ANY(%(ids)s)
       """

       db.execute_query("rpa_db", query, {"ids": sorted_ids})
   ```

2. **Use shorter transactions**

   ```python
   # Break long transactions into smaller ones
   def process_large_batch(records):
       """Process large batch in smaller transactions."""

       batch_size = 50  # Smaller batches reduce lock time

       for i in range(0, len(records), batch_size):
           batch = records[i:i+batch_size]

           # Process batch in separate transaction
           with db.get_connection() as conn:
               for record in batch:
                   process_single_record(record, conn)
               conn.commit()
   ```

3. **Add retry logic for deadlocks**

   ```python
   from tenacity import retry, stop_after_attempt, retry_if_exception_type
   import psycopg2

   @retry(
       stop=stop_after_attempt(3),
       retry=retry_if_exception_type(psycopg2.errors.DeadlockDetected),
       wait=wait_exponential(multiplier=1, min=1, max=5)
   )
   def update_with_deadlock_retry(record_id, status):
       """Update record with deadlock retry."""

       query = """
           UPDATE processing_queue
           SET status = %(status)s, updated_at = NOW()
           WHERE id = %(record_id)s
       """

       db.execute_query("rpa_db", query, {
           "status": status,
           "record_id": record_id
       })
   ```

## Container Issues

### Container Startup Problems

**Symptoms:**

- Containers fail to start
- Containers start but immediately exit
- Health check failures

**Diagnosis:**

```bash
# Check container status (Kubernetes)
kubectl get pods -l app=rpa-processor
kubectl describe pod <pod-name>
kubectl logs <pod-name> --previous

# Check container status (Docker)
docker ps -a --filter "name=rpa"
docker logs <container-name>
docker inspect <container-name>
```

**Solutions:**

1. **Fix environment variables**

   ```yaml
   # Kubernetes deployment
   env:
     - name: PREFECT_ENVIRONMENT
       value: "production"
     - name: RPA_DB_CONNECTION_STRING
       valueFrom:
         secretKeyRef:
           name: rpa-db-secret
           key: connection-string
   ```

2. **Add proper health checks**

   ```yaml
   # Health check configuration
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
     failureThreshold: 3
   ```

3. **Resource allocation**
   ```yaml
   # Proper resource limits
   resources:
     requests:
       memory: "512Mi"
       cpu: "250m"
     limits:
       memory: "2Gi"
       cpu: "1000m"
   ```

### Container Memory Issues

**Symptoms:**

- OOMKilled containers
- Gradual memory increase
- Performance degradation over time

**Diagnosis:**

```bash
# Check memory usage (Kubernetes)
kubectl top pods -l app=rpa-processor
kubectl describe pod <pod-name> | grep -A 5 "Limits\|Requests"

# Check memory usage (Docker)
docker stats <container-name>
```

**Solutions:**

1. **Increase memory limits**

   ```yaml
   resources:
     limits:
       memory: "4Gi" # Increase from 2Gi
   ```

2. **Optimize memory usage**

   ```python
   # Process records in smaller batches
   def memory_efficient_processing(flow_name):
       """Process records with memory efficiency."""

       processor = DistributedProcessor(DatabaseManager('rpa_db'))

       # Use smaller batch size
       batch_size = 25  # Reduced from 100

       while True:
           records = processor.claim_records_batch(flow_name, batch_size)
           if not records:
               break

           # Process batch
           for record in records:
               result = process_record_logic(record['payload'])
               processor.mark_record_completed(record['id'], result)

           # Force garbage collection after each batch
           import gc
           gc.collect()
   ```

3. **Add memory monitoring**

   ```python
   import psutil

   def monitor_memory_usage():
       """Monitor and log memory usage."""

       process = psutil.Process()
       memory_mb = process.memory_info().rss / 1024 / 1024

       logger.info(f"Memory usage: {memory_mb:.1f} MB")

       # Alert if memory usage is high
       if memory_mb > 1500:  # 1.5 GB threshold
           logger.warning(f"High memory usage: {memory_mb:.1f} MB")

       return memory_mb
   ```

## Monitoring and Debugging

### Enable Debug Logging

```python
# Enable debug logging for troubleshooting
import logging

# Set up debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable SQL query logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Enable distributed processing debug logs
logging.getLogger('core.distributed').setLevel(logging.DEBUG)
```

### Custom Monitoring Dashboard

```python
#!/usr/bin/env python3
"""Custom monitoring dashboard for distributed processing."""

import time
from datetime import datetime
from core.distributed import DistributedProcessor
from core.database import DatabaseManager
from core.monitoring import distributed_queue_monitoring, processing_performance_monitoring

def monitoring_dashboard():
    """Display real-time monitoring dashboard."""

    processor = DistributedProcessor(DatabaseManager('rpa_db'))

    while True:
        try:
            # Clear screen
            print("\033[2J\033[H")

            print("=== Distributed Processing Dashboard ===")
            print(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print()

            # System health
            health = processor.health_check()
            health_icon = "✅" if health['status'] == 'healthy' else "❌"
            print(f"{health_icon} System Health: {health['status'].upper()}")

            # Queue status
            queue_status = distributed_queue_monitoring()
            overall = queue_status['overall_queue_status']

            print(f"\n📊 Queue Status:")
            print(f"   Total: {overall['total_records']:,}")
            print(f"   Pending: {overall['pending_records']:,}")
            print(f"   Processing: {overall['processing_records']:,}")
            print(f"   Completed: {overall['completed_records']:,}")
            print(f"   Failed: {overall['failed_records']:,}")

            # Performance metrics
            perf = processing_performance_monitoring(time_window_hours=1)
            success_rate = perf['overall_metrics']['success_rate_percent']
            processing_rate = perf['overall_metrics']['avg_processing_rate_per_hour']

            print(f"\n📈 Performance (1h):")
            print(f"   Success Rate: {success_rate:.1f}%")
            print(f"   Processing Rate: {processing_rate:.1f} records/hour")

            # By flow breakdown
            if 'by_flow' in queue_status['overall_queue_status']:
                print(f"\n📋 By Flow:")
                for flow, counts in queue_status['overall_queue_status']['by_flow'].items():
                    pending = counts.get('pending', 0)
                    processing = counts.get('processing', 0)
                    failed = counts.get('failed', 0)
                    print(f"   {flow}: P:{pending} R:{processing} F:{failed}")

            # Alerts
            alerts = queue_status.get('operational_alerts', [])
            if alerts:
                print(f"\n🚨 Alerts:")
                for alert in alerts[:5]:  # Show top 5 alerts
                    print(f"   ⚠️  {alert}")

            print(f"\nPress Ctrl+C to exit...")

            # Update every 30 seconds
            time.sleep(30)

        except KeyboardInterrupt:
            print("\nExiting dashboard...")
            break
        except Exception as e:
            print(f"Error updating dashboard: {e}")
            time.sleep(10)

if __name__ == "__main__":
    monitoring_dashboard()
```

### Debugging Specific Issues

```python
def debug_specific_flow(flow_name):
    """Debug issues with a specific flow."""

    print(f"=== Debugging Flow: {flow_name} ===")

    processor = DistributedProcessor(DatabaseManager('rpa_db'))

    # 1. Check configuration
    from core.config import ConfigManager
    config = ConfigManager(flow_name)

    print(f"\n1. Configuration:")
    print(f"   Environment: {config.environment}")
    print(f"   Use Distributed: {config.get_variable('use_distributed_processing', False)}")
    print(f"   Batch Size: {config.get_variable('distributed_batch_size', 50)}")

    # 2. Check queue status
    status = processor.get_queue_status(flow_name)
    print(f"\n2. Queue Status:")
    for key, value in status.items():
        print(f"   {key}: {value}")

    # 3. Check recent errors
    from core.database import DatabaseManager
    db = DatabaseManager('rpa_db')

    errors = db.execute_query("rpa_db", """
        SELECT error_message, COUNT(*) as count, MAX(updated_at) as last_seen
        FROM processing_queue
        WHERE flow_name = %(flow_name)s
        AND status = 'failed'
        AND updated_at > NOW() - INTERVAL '24 hours'
        GROUP BY error_message
        ORDER BY count DESC
        LIMIT 5
    """, {"flow_name": flow_name})

    print(f"\n3. Recent Errors (24h):")
    if errors:
        for error, count, last_seen in errors:
            print(f"   {count}x: {error[:80]}... (last: {last_seen})")
    else:
        print("   No recent errors")

    # 4. Test record claiming
    print(f"\n4. Test Record Claiming:")
    try:
        test_records = processor.claim_records_batch(flow_name, 1)
        if test_records:
            print(f"   ✅ Successfully claimed {len(test_records)} record(s)")
            # Release the test record
            processor.mark_record_completed(test_records[0]['id'], {"test": True})
        else:
            print(f"   ℹ️  No records available to claim")
    except Exception as e:
        print(f"   ❌ Error claiming records: {e}")

    # 5. Health check
    print(f"\n5. Health Check:")
    try:
        health = processor.health_check()
        print(f"   Status: {health['status']}")
        for db_name, db_health in health['databases'].items():
            print(f"   {db_name}: {db_health['status']} ({db_health['response_time_ms']:.1f}ms)")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")

# Example usage
debug_specific_flow("survey_processor")
```

## Emergency Procedures

### Stop All Processing

```bash
# Emergency stop - scale down all containers
kubectl scale deployment rpa-processor --replicas=0

# Or disable distributed processing globally
python -c "
from prefect.blocks.system import Variable
Variable(value='false').save('production.global.use_distributed_processing', overwrite=True)
print('Distributed processing disabled globally')
"
```

### Emergency Queue Cleanup

```python
def emergency_queue_cleanup():
    """Emergency cleanup of processing queue."""

    processor = DistributedProcessor(DatabaseManager('rpa_db'))

    print("=== Emergency Queue Cleanup ===")

    # 1. Clean up orphaned records
    orphaned = processor.cleanup_orphaned_records(timeout_hours=0.5)  # 30 minutes
    print(f"Cleaned up {orphaned} orphaned records")

    # 2. Reset recent failed records
    from core.database import DatabaseManager
    db = DatabaseManager('rpa_db')

    reset_query = """
        UPDATE processing_queue
        SET status = 'pending',
            error_message = NULL,
            flow_instance_id = NULL,
            claimed_at = NULL
        WHERE status = 'failed'
        AND updated_at > NOW() - INTERVAL '1 hour'
        AND retry_count < 3
    """

    result = db.execute_query("rpa_db", reset_query)
    reset_count = result.rowcount if result else 0
    print(f"Reset {reset_count} failed records for retry")

    # 3. Get final status
    status = processor.get_queue_status()
    print(f"\nFinal queue status:")
    print(f"  Pending: {status['pending_records']}")
    print(f"  Processing: {status['processing_records']}")
    print(f"  Failed: {status['failed_records']}")

    return {
        "orphaned_cleaned": orphaned,
        "failed_reset": reset_count,
        "final_status": status
    }
```

### Data Recovery

```python
def recover_lost_records():
    """Recover records that may have been lost during issues."""

    from core.database import DatabaseManager

    db = DatabaseManager('rpa_db')

    # Find records that should have been processed but weren't
    missing_query = """
        SELECT
            source_table.id,
            source_table.data,
            pq.id as queue_id,
            pq.status as queue_status
        FROM source_data_table source_table
        LEFT JOIN processing_queue pq ON pq.payload->>'source_id' = source_table.id::text
        WHERE source_table.created_at > NOW() - INTERVAL '24 hours'
        AND (pq.id IS NULL OR pq.status = 'failed')
        ORDER BY source_table.created_at DESC
    """

    missing_records = db.execute_query("source_db", missing_query)

    if missing_records:
        print(f"Found {len(missing_records)} records that need recovery")

        # Add missing records to queue
        processor = DistributedProcessor(DatabaseManager('rpa_db'))

        recovery_records = []
        for record in missing_records:
            recovery_records.append({
                "source_id": record[0],
                "data": record[1],
                "recovery": True
            })

        count = processor.add_records_to_queue("recovery_processor", recovery_records)
        print(f"Added {count} records to recovery queue")

        return count
    else:
        print("No missing records found")
        return 0
```

## Getting Help

### Diagnostic Information to Collect

When reporting issues, collect this information:

```bash
# System information
python -c "
import sys, platform
print(f'Python: {sys.version}')
print(f'Platform: {platform.platform()}')
print(f'Architecture: {platform.architecture()}')
"

# Package versions
pip list | grep -E "(prefect|sqlalchemy|psycopg2|pyodbc)"

# Configuration
python -c "
from core.config import ConfigManager
config = ConfigManager('your_flow')
print(f'Environment: {config.environment}')
print(f'Use distributed: {config.get_variable(\"use_distributed_processing\", \"NOT_SET\")}')
"

# Database health
python -c "
from core.distributed import DistributedProcessor
from core.database import DatabaseManager
processor = DistributedProcessor(DatabaseManager('rpa_db'))
health = processor.health_check()
print(f'System health: {health}')
"

# Queue status
python -c "
from core.monitoring import distributed_queue_monitoring
status = distributed_queue_monitoring()
print(f'Queue health: {status[\"queue_health_assessment\"]}')
"
```

### Log Collection

```bash
# Collect relevant logs
kubectl logs -l app=rpa-processor --tail=1000 > rpa-logs.txt

# Or for Docker
docker logs rpa-container --tail=1000 > rpa-logs.txt

# Database logs (PostgreSQL)
tail -n 1000 /var/log/postgresql/postgresql-*.log > db-logs.txt
```

### Support Checklist

Before requesting help:

- [ ] Ran quick diagnostics commands
- [ ] Checked system health
- [ ] Reviewed recent error messages
- [ ] Attempted basic troubleshooting steps
- [ ] Collected diagnostic information
- [ ] Documented steps to reproduce the issue
- [ ] Noted when the issue started
- [ ] Identified any recent changes

For additional support, refer to:

- [API Reference](API_REFERENCE.md) for detailed API documentation
- [Operations Runbook](DISTRIBUTED_PROCESSING_OPERATIONS_RUNBOOK.md) for operational procedures
- [Migration Guide](MIGRATION_GUIDE.md) for migration-specific issues
