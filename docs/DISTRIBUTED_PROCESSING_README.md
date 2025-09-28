# Distributed Processing System - Setup & Quick Start

## Overview

The Distributed Processing System enables horizontal scaling of Prefect flows by preventing duplicate record processing when deploying multiple container instances. It uses database-level locking to ensure each record is processed exactly once, even when multiple flow instances are running concurrently.

## Key Features

- ✅ **Zero Duplicate Processing** - Database-level locking prevents duplicate work
- ✅ **Horizontal Scaling** - Add more containers to increase throughput
- ✅ **Fault Tolerance** - Automatic recovery from container failures
- ✅ **Multi-Database Support** - Read from one DB, write to another
- ✅ **Health Monitoring** - Built-in health checks and metrics
- ✅ **Configuration Management** - Environment-specific settings
- ✅ **Backward Compatibility** - Works with existing flows

## Quick Start (5 Minutes)

### 1. Prerequisites

- PostgreSQL database for processing queue
- Python 3.8+ with Prefect 3.0+
- Database migrations applied

### 2. Verify Setup

```bash
# Check database migrations
python -c "
from core.database import DatabaseManager
db = DatabaseManager('rpa_db')
print('Database connection: OK')
"

# Check distributed processor
python -c "
from core.distributed import DistributedProcessor
from core.database import DatabaseManager
processor = DistributedProcessor(DatabaseManager('rpa_db'))
health = processor.health_check()
print(f'System health: {health[\"status\"]}')
"
```

### 3. Basic Usage

```python
from core.distributed import DistributedProcessor
from core.database import DatabaseManager
from core.flow_template import distributed_processing_flow

# Initialize processor
processor = DistributedProcessor(DatabaseManager('rpa_db'))

# Add records to queue
records = [
    {"survey_id": "SURV-001", "customer_id": "CUST-001"},
    {"survey_id": "SURV-002", "customer_id": "CUST-002"}
]
processor.add_records_to_queue("survey_processor", records)

# Process records
result = distributed_processing_flow("survey_processor", batch_size=50)
print(f"Processed {result['completed']} records")
```

### 4. Configuration

```bash
# Enable distributed processing
DEVELOPMENT_SURVEY_PROCESSOR_USE_DISTRIBUTED_PROCESSING=true
DEVELOPMENT_SURVEY_PROCESSOR_DISTRIBUTED_BATCH_SIZE=50
```

## Architecture

### System Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Container 1   │    │   Container 2   │    │   Container 3   │
│   (RPA Flow)    │    │   (RPA Flow)    │    │   (RPA Flow)    │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │     Database Layer        │
                    │  - Processing Queue       │
                    │  - Record Locking         │
                    │  - Status Tracking        │
                    └───────────────────────────┘
```

### Core Components

- **DistributedProcessor**: Handles atomic record claiming and status management
- **Processing Queue**: PostgreSQL table with `FOR UPDATE SKIP LOCKED` locking
- **Flow Template**: Standardized pattern for distributed flows
- **DatabaseManager**: Unified database access with connection pooling
- **Configuration System**: Environment-specific settings management

## Database Schema

The system uses a `processing_queue` table for coordination:

```sql
CREATE TABLE processing_queue (
    id SERIAL PRIMARY KEY,
    flow_name VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    flow_instance_id VARCHAR(100),
    claimed_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Usage Patterns

### Pattern 1: Simple Record Processing

```python
from core.distributed import DistributedProcessor
from core.database import DatabaseManager

# Initialize
processor = DistributedProcessor(DatabaseManager('rpa_db'))

# Add work to queue
records = [{"file_path": f"/data/file_{i}.csv"} for i in range(100)]
processor.add_records_to_queue("file_processor", records)

# Process with distributed flow
from core.flow_template import distributed_processing_flow
result = distributed_processing_flow("file_processor", batch_size=25)
```

### Pattern 2: Multi-Database Processing

```python
# Read from one database, write to another
from core.database import DatabaseManager

rpa_db = DatabaseManager('rpa_db')      # PostgreSQL for queue
source_db = DatabaseManager('SurveyHub') # SQL Server for source data

processor = DistributedProcessor(rpa_db, source_db)

# Your processing logic can read from source_db and write results to rpa_db
```

### Pattern 3: Existing Flow Migration

```python
@flow(name="my-existing-flow")
def my_flow(use_distributed=None, batch_size=None):
    """Existing flow with distributed processing support."""

    config = ConfigManager("my_flow")
    use_distributed = use_distributed if use_distributed is not None else config.get_variable("use_distributed_processing", False)

    if use_distributed:
        # Use distributed processing
        batch_size = batch_size or config.get_variable("distributed_batch_size", 50)
        return distributed_processing_flow("my_flow", batch_size)
    else:
        # Use original logic
        return my_original_flow_logic()
```

## Configuration

### Environment Variables

```bash
# Database configuration
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_db

# Distributed processing configuration
DEVELOPMENT_MY_FLOW_USE_DISTRIBUTED_PROCESSING=true
DEVELOPMENT_MY_FLOW_DISTRIBUTED_BATCH_SIZE=50
DEVELOPMENT_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS=2
DEVELOPMENT_DISTRIBUTED_PROCESSOR_MAX_RETRIES=3
```

### Configuration Hierarchy

The system uses hierarchical configuration lookup:

1. `{environment}.{flow}.{key}` (most specific)
2. `{environment}.global.{key}` (environment global)
3. `global.{key}` (base global)

Example: For RPA1 in development looking for `batch_size`:

1. `development.rpa1.batch_size`
2. `development.global.batch_size`
3. `global.batch_size`

## Monitoring

### Health Checks

```python
# System health check
processor = DistributedProcessor(DatabaseManager('rpa_db'))
health = processor.health_check()

print(f"Status: {health['status']}")
print(f"Databases: {health['databases']}")
print(f"Queue: {health['queue_status']}")
```

### Queue Monitoring

```python
# Queue status
status = processor.get_queue_status("my_flow")
print(f"Pending: {status['pending_records']}")
print(f"Processing: {status['processing_records']}")
print(f"Failed: {status['failed_records']}")
```

### Performance Monitoring

```python
from core.monitoring import processing_performance_monitoring

# Performance metrics
perf = processing_performance_monitoring(time_window_hours=24)
print(f"Success rate: {perf['overall_metrics']['success_rate_percent']}%")
print(f"Processing rate: {perf['overall_metrics']['avg_processing_rate_per_hour']} records/hour")
```

## Container Deployment

### Kubernetes Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: distributed-rpa-processor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rpa-processor
  template:
    metadata:
      labels:
        app: rpa-processor
    spec:
      containers:
        - name: rpa-processor
          image: rpa-solution:distributed
          env:
            - name: PREFECT_ENVIRONMENT
              value: "production"
            - name: RPA_DB_CONNECTION_STRING
              valueFrom:
                secretKeyRef:
                  name: rpa-db-secret
                  key: connection-string
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
```

### Docker Compose Example

```yaml
version: "3.8"
services:
  rpa-processor:
    image: rpa-solution:distributed
    deploy:
      replicas: 3
    environment:
      - PREFECT_ENVIRONMENT=production
      - RPA_DB_CONNECTION_STRING=postgresql://user:pass@db:5432/rpa_db
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=rpa_db
      - POSTGRES_USER=rpa_user
      - POSTGRES_PASSWORD=rpa_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## Troubleshooting

### Common Issues

#### No Records Being Processed

```python
# Check queue status
status = processor.get_queue_status("your_flow")
print(f"Queue status: {status}")

# Check configuration
from core.config import ConfigManager
config = ConfigManager("your_flow")
print(f"Distributed enabled: {config.get_variable('use_distributed_processing', False)}")

# Test record claiming
records = processor.claim_records_batch("your_flow", 5)
print(f"Claimed {len(records)} records")
```

#### High Error Rates

```python
# Analyze errors
from core.database import DatabaseManager
db = DatabaseManager('rpa_db')

errors = db.execute_query("rpa_db", """
    SELECT error_message, COUNT(*) as count
    FROM processing_queue
    WHERE status = 'failed'
    AND updated_at > NOW() - INTERVAL '24 hours'
    GROUP BY error_message
    ORDER BY count DESC
    LIMIT 5
""")

for error, count in errors:
    print(f"{count}: {error}")
```

#### Orphaned Records

```python
# Clean up orphaned records
cleaned = processor.cleanup_orphaned_records(timeout_hours=2)
print(f"Cleaned up {cleaned} orphaned records")
```

### Performance Issues

```python
# Check performance metrics
from core.monitoring import processing_performance_monitoring

perf = processing_performance_monitoring(time_window_hours=6)
print(f"Success rate: {perf['overall_metrics']['success_rate_percent']}%")
print(f"Processing rate: {perf['overall_metrics']['avg_processing_rate_per_hour']} records/hour")

# Check connection pool
from core.tasks import connection_pool_monitoring
pool_status = connection_pool_monitoring("rpa_db")
print(f"Pool utilization: {pool_status['utilization_percent']}%")
```

## Best Practices

### Development

- Start with distributed processing disabled in development
- Use small batch sizes for testing (10-25 records)
- Test both standard and distributed modes
- Monitor queue depth and processing rates

### Production

- Enable distributed processing for scalability
- Use appropriate batch sizes (50-100 records)
- Set up automated cleanup of old records
- Monitor performance metrics and error rates

### Container Deployment

- Each container gets a unique instance ID automatically
- No coordination between containers is required
- Containers can be scaled up/down independently
- Failed containers have their records automatically recovered

### Error Handling

- Individual record failures don't affect the batch
- Failed records are marked with error details
- Retry logic is handled at the database level
- Monitor failed record counts for operational issues

## Next Steps

1. **Read the Usage Guide**: [DISTRIBUTED_PROCESSING_USAGE.md](DISTRIBUTED_PROCESSING_USAGE.md) for comprehensive examples
2. **Migration Guide**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) to convert existing flows
3. **API Reference**: [API_REFERENCE.md](API_REFERENCE.md) for detailed API documentation
4. **Operations**: [DISTRIBUTED_PROCESSING_OPERATIONS_RUNBOOK.md](DISTRIBUTED_PROCESSING_OPERATIONS_RUNBOOK.md) for production deployment

## Support

For issues or questions:

1. Check the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md)
2. Review the [API Reference](API_REFERENCE.md)
3. Consult the [Operations Runbook](DISTRIBUTED_PROCESSING_OPERATIONS_RUNBOOK.md)

## Examples

Complete working examples are available in `flows/examples/`:

- `distributed_survey_processing.py` - Complete survey processing example
- `distributed_monitoring_example.py` - Monitoring and health checks
- `demo_distributed_survey_processing.py` - Demo with sample data
