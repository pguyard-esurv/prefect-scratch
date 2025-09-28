# API Reference

## Overview

This document provides comprehensive API documentation for the distributed processing system components.

## Core Classes

### DistributedProcessor

The main class for handling distributed processing operations.

#### Constructor

```python
class DistributedProcessor:
    def __init__(self, rpa_db_manager: DatabaseManager, source_db_manager: DatabaseManager = None)
```

**Parameters:**

- `rpa_db_manager` (DatabaseManager): DatabaseManager instance for PostgreSQL (queue and results)
- `source_db_manager` (DatabaseManager, optional): DatabaseManager for source data (SQL Server)

**Example:**

```python
from core.database import DatabaseManager
from core.distributed import DistributedProcessor

rpa_db_manager = DatabaseManager("rpa_db")
source_db_manager = DatabaseManager("SurveyHub")
processor = DistributedProcessor(rpa_db_manager, source_db_manager)
```

#### Record Management Methods

##### claim_records_batch()

Claims a batch of records for processing using atomic database locking.

```python
def claim_records_batch(self, flow_name: str, batch_size: int) -> List[Dict]
```

**Parameters:**

- `flow_name` (str): Name of the flow claiming records
- `batch_size` (int): Maximum number of records to claim

**Returns:**

- `List[Dict]`: List of claimed records with id, payload, and retry_count

**Example:**

```python
records = processor.claim_records_batch("survey_processor", 50)
for record in records:
    print(f"Processing record {record['id']}: {record['payload']}")
```

**Behavior:**

- Uses `FOR UPDATE SKIP LOCKED` for atomic claiming
- Orders records by `created_at` (FIFO)
- Returns empty list if no records available
- Assigns unique `flow_instance_id` to claimed records

##### mark_record_completed()

Marks a record as successfully completed.

```python
def mark_record_completed(self, record_id: int, result: Dict) -> None
```

**Parameters:**

- `record_id` (int): ID of the record to mark as completed
- `result` (Dict): Processing result to store

**Example:**

```python
result = {"status": "success", "processed_count": 5}
processor.mark_record_completed(123, result)
```

**Behavior:**

- Updates status to 'completed'
- Sets `completed_at` timestamp
- Stores result in payload field

##### mark_record_failed()

Marks a record as failed with error details.

```python
def mark_record_failed(self, record_id: int, error: str) -> None
```

**Parameters:**

- `record_id` (int): ID of the record to mark as failed
- `error` (str): Error message describing the failure

**Example:**

```python
try:
    process_record(record)
except Exception as e:
    processor.mark_record_failed(record['id'], str(e))
```

**Behavior:**

- Updates status to 'failed'
- Stores error message
- Increments retry_count

#### Queue Management Methods

##### add_records_to_queue()

Adds new records to the processing queue.

```python
def add_records_to_queue(self, flow_name: str, records: List[Dict]) -> int
```

**Parameters:**

- `flow_name` (str): Name of the flow that will process these records
- `records` (List[Dict]): List of record payloads to add

**Returns:**

- `int`: Number of records successfully added

**Example:**

```python
records = [
    {"survey_id": "SURV-001", "customer_id": "CUST-001"},
    {"survey_id": "SURV-002", "customer_id": "CUST-002"}
]
count = processor.add_records_to_queue("survey_processor", records)
print(f"Added {count} records to queue")
```

##### get_queue_status()

Gets current queue status and metrics.

```python
def get_queue_status(self, flow_name: str = None) -> Dict
```

**Parameters:**

- `flow_name` (str, optional): Filter by specific flow name

**Returns:**

- `Dict`: Queue status with record counts by status

**Example:**

```python
# Get status for specific flow
status = processor.get_queue_status("survey_processor")
print(f"Pending: {status['pending_records']}")

# Get system-wide status
status = processor.get_queue_status()
print(f"Total records: {status['total_records']}")
```

**Response Format:**

```python
{
    "total_records": 1250,
    "pending_records": 150,
    "processing_records": 25,
    "completed_records": 1050,
    "failed_records": 25,
    "by_flow": {
        "survey_processor": {
            "pending": 100,
            "processing": 15,
            "completed": 800,
            "failed": 10
        }
    }
}
```

#### Maintenance Methods

##### cleanup_orphaned_records()

Cleans up records stuck in processing state.

```python
def cleanup_orphaned_records(self, timeout_hours: int = 1) -> int
```

**Parameters:**

- `timeout_hours` (int): Hours after which processing records are considered orphaned

**Returns:**

- `int`: Number of records cleaned up

**Example:**

```python
# Clean up records stuck for more than 2 hours
cleaned = processor.cleanup_orphaned_records(timeout_hours=2)
print(f"Cleaned up {cleaned} orphaned records")
```

**Behavior:**

- Resets status from 'processing' to 'pending'
- Clears `flow_instance_id` and `claimed_at`
- Increments retry_count

##### reset_failed_records()

Resets failed records for retry within retry limits.

```python
def reset_failed_records(self, flow_name: str, max_retries: int = 3) -> int
```

**Parameters:**

- `flow_name` (str): Flow name to reset records for
- `max_retries` (int): Maximum retry count before permanent failure

**Returns:**

- `int`: Number of records reset for retry

**Example:**

```python
reset = processor.reset_failed_records("survey_processor", max_retries=3)
print(f"Reset {reset} failed records for retry")
```

#### Health and Monitoring Methods

##### health_check()

Performs comprehensive health check of the distributed processing system.

```python
def health_check(self) -> Dict[str, Any]
```

**Returns:**

- `Dict[str, Any]`: Comprehensive health status

**Example:**

```python
health = processor.health_check()
print(f"System Status: {health['status']}")
print(f"Database Health: {health['databases']}")
```

**Response Format:**

```python
{
    "status": "healthy|degraded|unhealthy",
    "databases": {
        "rpa_db": {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 45.2
        },
        "SurveyHub": {
            "status": "healthy",
            "connection": True,
            "response_time_ms": 32.1
        }
    },
    "queue_status": {
        "pending_records": 150,
        "processing_records": 25,
        "failed_records": 3,
        "total_records": 1250
    },
    "instance_info": {
        "instance_id": "container-1-abc123",
        "hostname": "rpa-worker-1"
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

## Flow Template Functions

### distributed_processing_flow()

Main flow function for distributed processing.

```python
@flow(name="distributed-processing")
def distributed_processing_flow(flow_name: str, batch_size: int = 100) -> Dict
```

**Parameters:**

- `flow_name` (str): Name of the flow for queue filtering
- `batch_size` (int): Number of records to process in this batch

**Returns:**

- `Dict`: Processing summary with counts and metrics

**Example:**

```python
from core.flow_template import distributed_processing_flow

result = distributed_processing_flow("survey_processor", batch_size=50)
print(f"Processed {result['completed']} records successfully")
```

### process_record_with_status()

Task function for processing individual records with status management.

```python
@task(retries=2, retry_delay_seconds=30)
def process_record_with_status(record: Dict) -> Dict
```

**Parameters:**

- `record` (Dict): Record with id, payload, and retry_count

**Returns:**

- `Dict`: Processing result with status and details

**Example:**

```python
# This is typically called via .map() in the flow
results = process_record_with_status.map(records)
```

## Configuration Classes

### ConfigManager

Handles environment-specific configuration management.

#### Constructor

```python
class ConfigManager:
    def __init__(self, flow_name: str = None)
```

**Parameters:**

- `flow_name` (str, optional): Flow name for flow-specific configuration

#### Methods

##### get_variable()

Gets a configuration variable with hierarchical lookup.

```python
def get_variable(self, key: str, default: Any = None) -> Any
```

**Parameters:**

- `key` (str): Configuration key name
- `default` (Any): Default value if not found

**Returns:**

- `Any`: Configuration value

**Example:**

```python
from core.config import ConfigManager

config = ConfigManager("rpa1")
batch_size = config.get_variable("batch_size", 100)
timeout = config.get_variable("timeout", 60)
```

##### get_secret()

Gets a secret value with hierarchical lookup.

```python
def get_secret(self, key: str, default: Any = None) -> Any
```

**Parameters:**

- `key` (str): Secret key name
- `default` (Any): Default value if not found

**Returns:**

- `Any`: Secret value

**Example:**

```python
api_key = config.get_secret("api_key")
db_password = config.get_secret("db_password")
```

## Monitoring Functions

### distributed_queue_monitoring()

Comprehensive queue monitoring and health assessment.

```python
def distributed_queue_monitoring(include_detailed_metrics: bool = False) -> Dict
```

**Parameters:**

- `include_detailed_metrics` (bool): Include detailed performance metrics

**Returns:**

- `Dict`: Queue monitoring results with health assessment

**Example:**

```python
from core.monitoring import distributed_queue_monitoring

status = distributed_queue_monitoring(include_detailed_metrics=True)
print(f"Queue Health: {status['queue_health_assessment']['queue_health']}")
```

### distributed_processing_diagnostics()

System diagnostics and issue detection.

```python
def distributed_processing_diagnostics(
    include_orphaned_analysis: bool = False,
    include_performance_analysis: bool = False
) -> Dict
```

**Parameters:**

- `include_orphaned_analysis` (bool): Include orphaned record analysis
- `include_performance_analysis` (bool): Include performance analysis

**Returns:**

- `Dict`: Diagnostic results with issues and recommendations

**Example:**

```python
from core.monitoring import distributed_processing_diagnostics

diagnostics = distributed_processing_diagnostics(
    include_orphaned_analysis=True,
    include_performance_analysis=True
)

for issue in diagnostics['issues_found']:
    print(f"Issue: {issue}")
```

### processing_performance_monitoring()

Performance monitoring and analysis.

```python
def processing_performance_monitoring(
    time_window_hours: int = 24,
    include_error_analysis: bool = False
) -> Dict
```

**Parameters:**

- `time_window_hours` (int): Time window for analysis in hours
- `include_error_analysis` (bool): Include detailed error analysis

**Returns:**

- `Dict`: Performance metrics and analysis

**Example:**

```python
from core.monitoring import processing_performance_monitoring

performance = processing_performance_monitoring(
    time_window_hours=6,
    include_error_analysis=True
)

print(f"Success Rate: {performance['overall_metrics']['success_rate_percent']}%")
print(f"Processing Rate: {performance['overall_metrics']['avg_processing_rate_per_hour']} records/hour")
```

## Database Schema

### processing_queue Table

Main table for distributed processing queue management.

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

#### Key Indexes

```sql
-- Essential indexes for performance
CREATE INDEX idx_processing_queue_status_created ON processing_queue(status, created_at);
CREATE INDEX idx_processing_queue_flow_name_status ON processing_queue(flow_name, status);
CREATE INDEX idx_processing_queue_claimed_at ON processing_queue(claimed_at) WHERE claimed_at IS NOT NULL;
CREATE INDEX idx_processing_queue_instance_id ON processing_queue(flow_instance_id) WHERE flow_instance_id IS NOT NULL;

-- Partial indexes for common queries
CREATE INDEX idx_processing_queue_pending ON processing_queue(created_at) WHERE status = 'pending';
CREATE INDEX idx_processing_queue_processing ON processing_queue(claimed_at) WHERE status = 'processing';
```

## Error Handling

### Exception Types

The system uses standard Python exceptions with descriptive messages:

- `ValueError`: Invalid configuration or parameters
- `ConnectionError`: Database connectivity issues
- `RuntimeError`: System health check failures
- `Exception`: General processing errors

### Error Response Format

Failed operations return structured error information:

```python
{
    "status": "failed",
    "error": "Descriptive error message",
    "error_type": "ValueError",
    "timestamp": "2024-01-15T10:30:00Z",
    "context": {
        "record_id": 123,
        "flow_name": "survey_processor"
    }
}
```

## Configuration Reference

### Environment Variables

#### Database Configuration

```bash
# PostgreSQL (required)
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_db

# SQL Server (optional)
DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE=sqlserver
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://user:pass@server:1433/survey_hub
```

#### Distributed Processing Configuration

```bash
# Batch processing
DEVELOPMENT_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE=100
DEVELOPMENT_RPA1_DISTRIBUTED_BATCH_SIZE=50

# Timeouts and cleanup
DEVELOPMENT_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS=1
DEVELOPMENT_DISTRIBUTED_PROCESSOR_MAX_RETRIES=3

# Feature flags
DEVELOPMENT_RPA1_USE_DISTRIBUTED_PROCESSING=true
DEVELOPMENT_RPA2_USE_DISTRIBUTED_PROCESSING=false
```

### Configuration Hierarchy

The system follows a hierarchical configuration lookup:

1. `{environment}.{flow}.{key}` (most specific)
2. `{environment}.global.{key}` (environment-specific global)
3. `global.{key}` (base global fallback)

**Example:**
For RPA1 in development looking for `batch_size`:

1. `development.rpa1.batch_size`
2. `development.global.batch_size`
3. `global.batch_size`

## Best Practices

### Performance

- **Reuse instances**: Create DatabaseManager and DistributedProcessor once per container
- **Appropriate batch sizes**: 50-100 records for most workloads
- **Connection pooling**: Use DatabaseManager's built-in connection pooling
- **Index optimization**: Ensure proper indexes on processing_queue table

### Error Handling

- **Individual record failures**: Don't let one failed record stop the batch
- **Retry logic**: Use database-level retry counting, not Prefect retries
- **Graceful degradation**: Handle database unavailability gracefully
- **Comprehensive logging**: Log all errors with sufficient context

### Security

- **Secret management**: Use Prefect secrets for sensitive configuration
- **Database permissions**: Use least-privilege database users
- **Connection security**: Enable SSL for production databases
- **Input validation**: Validate all configuration and input parameters

### Monitoring

- **Health checks**: Regular health monitoring of databases and queue
- **Performance metrics**: Track processing rates and error rates
- **Alerting**: Set up alerts for high error rates or queue depth
- **Capacity planning**: Monitor trends for scaling decisions

## Migration Notes

### From Standard to Distributed Processing

When migrating existing flows:

1. **Add queue population**: Create process to add records to queue
2. **Update flow logic**: Use distributed processing template
3. **Configuration**: Add distributed processing configuration
4. **Testing**: Test both standard and distributed modes
5. **Gradual rollout**: Start with small percentage of traffic

### Version Compatibility

- **Backward compatible**: Distributed processing is opt-in
- **Configuration driven**: Enable/disable per flow via configuration
- **Fallback support**: Graceful fallback to standard processing
- **Migration path**: Clear migration path for existing flows

## Troubleshooting

### Common Issues

#### No Records Claimed

- Check queue has pending records: `processor.get_queue_status()`
- Verify flow_name matches queue records
- Check database connectivity

#### High Error Rates

- Review error messages in failed records
- Check business logic for edge cases
- Verify database connectivity and performance

#### Orphaned Records

- Run cleanup: `processor.cleanup_orphaned_records()`
- Check container health and restart if needed
- Review timeout configuration

#### Performance Issues

- Monitor connection pool utilization
- Optimize batch sizes
- Check database query performance
- Scale container instances

For detailed troubleshooting, see the [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md).
