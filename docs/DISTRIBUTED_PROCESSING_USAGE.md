# Distributed Processing Usage Guide

This guide explains how to use the distributed processing feature that has been added to the existing RPA workflows (RPA1, RPA2, and RPA3).

## Overview

The distributed processing feature allows multiple container instances to process records from a shared queue without duplicating work. This is particularly useful for:

- Horizontal scaling of processing workloads
- Container-based deployments (Docker, Kubernetes)
- High-volume data processing scenarios
- Fault-tolerant processing (automatic recovery from container failures)

## Configuration

### Environment Variables

Each flow supports distributed processing configuration through environment variables:

#### RPA1 Configuration

```bash
# Enable/disable distributed processing
DEVELOPMENT_RPA1_USE_DISTRIBUTED_PROCESSING=false
PRODUCTION_RPA1_USE_DISTRIBUTED_PROCESSING=true

# Batch size for distributed processing
DEVELOPMENT_RPA1_DISTRIBUTED_BATCH_SIZE=10
PRODUCTION_RPA1_DISTRIBUTED_BATCH_SIZE=50
```

#### RPA2 Configuration

```bash
# Enable/disable distributed processing
DEVELOPMENT_RPA2_USE_DISTRIBUTED_PROCESSING=false
PRODUCTION_RPA2_USE_DISTRIBUTED_PROCESSING=true

# Batch size for distributed processing
DEVELOPMENT_RPA2_DISTRIBUTED_BATCH_SIZE=10
PRODUCTION_RPA2_DISTRIBUTED_BATCH_SIZE=25
```

#### RPA3 Configuration

```bash
# Enable/disable distributed processing
DEVELOPMENT_RPA3_USE_DISTRIBUTED_PROCESSING=false
PRODUCTION_RPA3_USE_DISTRIBUTED_PROCESSING=true

# Batch size for distributed processing
DEVELOPMENT_RPA3_DISTRIBUTED_BATCH_SIZE=10
PRODUCTION_RPA3_DISTRIBUTED_BATCH_SIZE=20
```

### Runtime Parameters

You can also override the configuration at runtime:

```python
# Enable distributed processing for a single run
result = rpa1_workflow(use_distributed=True, batch_size=25)

# Disable distributed processing for a single run
result = rpa2_workflow(use_distributed=False)

# Use custom batch size
result = rpa3_workflow(use_distributed=True, batch_size=15)
```

## Usage Examples

### Standard Mode (Default)

By default, all workflows run in standard mode (non-distributed):

```python
from flows.rpa1.workflow import rpa1_workflow
from flows.rpa2.workflow import rpa2_workflow
from flows.rpa3.workflow import rpa3_workflow

# These will run in standard mode
result1 = rpa1_workflow()
result2 = rpa2_workflow()
result3 = rpa3_workflow()
```

### Distributed Mode

To use distributed processing, you need to:

1. **Set up the database**: Ensure the `processing_queue` table exists (created by migrations)
2. **Add records to the queue**: Use the DistributedProcessor to add records
3. **Run the workflow**: Enable distributed processing

```python
from core.database import DatabaseManager
from core.distributed import DistributedProcessor

# Initialize processor
rpa_db_manager = DatabaseManager("rpa_db")
processor = DistributedProcessor(rpa_db_manager)

# Add records to the queue
records = [
    {"payload": {"file_path": "/data/file1.csv"}},
    {"payload": {"file_path": "/data/file2.csv"}},
    {"payload": {"file_path": "/data/file3.csv"}}
]
processor.add_records_to_queue("rpa1_file_processing", records)

# Run workflow in distributed mode
result = rpa1_workflow(use_distributed=True, batch_size=10)
```

### Environment-Based Configuration

Set up your environment files to automatically enable distributed processing in production:

```bash
# .env.production
PRODUCTION_RPA1_USE_DISTRIBUTED_PROCESSING=true
PRODUCTION_RPA1_DISTRIBUTED_BATCH_SIZE=50

# .env.development
DEVELOPMENT_RPA1_USE_DISTRIBUTED_PROCESSING=false
DEVELOPMENT_RPA1_DISTRIBUTED_BATCH_SIZE=5
```

Then workflows will automatically use the appropriate mode:

```python
# Will use distributed processing in production, standard in development
result = rpa1_workflow()
```

## Backward Compatibility

The distributed processing feature is fully backward compatible:

- **Existing code**: No changes required - workflows continue to work as before
- **Configuration**: Distributed processing is disabled by default
- **Dependencies**: Distributed processing components are lazy-loaded
- **Fallback**: If distributed components are unavailable, workflows fall back to standard mode

## Monitoring and Troubleshooting

### Queue Status

Check the current queue status:

```python
from core.database import DatabaseManager
from core.distributed import DistributedProcessor

processor = DistributedProcessor(DatabaseManager("rpa_db"))

# Get status for specific flow
status = processor.get_queue_status("rpa1_file_processing")
print(f"Pending: {status['pending_records']}")
print(f"Processing: {status['processing_records']}")
print(f"Completed: {status['completed_records']}")
print(f"Failed: {status['failed_records']}")

# Get system-wide status
status = processor.get_queue_status()
print(status['by_flow'])
```

### Health Check

Verify system health before processing:

```python
health = processor.health_check()
print(f"Status: {health['status']}")
print(f"Databases: {health['databases']}")
```

### Cleanup Operations

Clean up orphaned records (stuck in processing):

```python
# Clean up records stuck for more than 2 hours
cleaned = processor.cleanup_orphaned_records(timeout_hours=2)
print(f"Cleaned up {cleaned} orphaned records")

# Reset failed records for retry
reset = processor.reset_failed_records("rpa1_file_processing", max_retries=3)
print(f"Reset {reset} failed records for retry")
```

## Best Practices

### Development

- Keep distributed processing disabled in development
- Use small batch sizes for testing (5-10 records)
- Test both standard and distributed modes

### Production

- Enable distributed processing for scalability
- Use appropriate batch sizes based on workload (25-100 records)
- Monitor queue depth and processing rates
- Set up automated cleanup of old records

### Container Deployment

- Each container instance will have a unique instance ID
- No coordination between containers is required
- Containers can be scaled up/down independently
- Failed containers will have their records automatically recovered

### Error Handling

- Individual record failures don't affect the batch
- Failed records are marked with error details
- Retry logic is handled at the database level
- Monitor failed record counts for operational issues

## Migration from Standard to Distributed

To migrate an existing workflow to use distributed processing:

1. **Update configuration**: Enable distributed processing in your environment
2. **Add queue population**: Create a process to add records to the processing queue
3. **Test thoroughly**: Verify both modes work correctly
4. **Deploy gradually**: Start with a small percentage of traffic
5. **Monitor closely**: Watch for any issues during the transition

Example migration for RPA1:

```python
# Before (standard mode)
def process_files():
    return rpa1_workflow()

# After (distributed mode)
def process_files():
    # Add files to queue
    processor = DistributedProcessor(DatabaseManager("rpa_db"))
    records = [{"payload": {"file_path": f}} for f in get_files_to_process()]
    processor.add_records_to_queue("rpa1_file_processing", records)

    # Process in distributed mode
    return rpa1_workflow(use_distributed=True)
```

This approach ensures a smooth transition while maintaining full backward compatibility.
