# Migration Guide: Converting Flows to Distributed Processing

## Overview

This guide helps you convert existing Prefect flows to use distributed processing, enabling horizontal scaling and preventing duplicate record processing across multiple container instances.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Migration Strategy](#migration-strategy)
3. [Step-by-Step Migration](#step-by-step-migration)
4. [Configuration Setup](#configuration-setup)
5. [Testing Your Migration](#testing-your-migration)
6. [Deployment Considerations](#deployment-considerations)
7. [Rollback Plan](#rollback-plan)
8. [Common Migration Patterns](#common-migration-patterns)

## Prerequisites

Before starting the migration:

- [ ] **Database Setup**: Ensure PostgreSQL database with `processing_queue` table
- [ ] **Migrations Applied**: Run database migrations (V006 and V007)
- [ ] **Configuration**: Set up environment-specific configuration
- [ ] **Testing Environment**: Have a test environment for validation
- [ ] **Backup**: Create backups of existing flows and data

### Verify Prerequisites

```bash
# Check database migrations
python -c "
from core.database import DatabaseManager
db = DatabaseManager('rpa_db')
status = db.get_migration_status()
print(f'Migration status: {status}')
"

# Verify configuration
python scripts/validate_database_config.py

# Test distributed processor
python -c "
from core.database import DatabaseManager
from core.distributed import DistributedProcessor
processor = DistributedProcessor(DatabaseManager('rpa_db'))
health = processor.health_check()
print(f'System health: {health[\"status\"]}')
"
```

## Migration Strategy

### Phased Approach

1. **Phase 1**: Configuration and testing setup
2. **Phase 2**: Implement distributed version alongside existing flow
3. **Phase 3**: Gradual traffic migration
4. **Phase 4**: Full migration and cleanup

### Risk Mitigation

- **Backward compatibility**: Keep existing flow working during migration
- **Feature flags**: Use configuration to enable/disable distributed processing
- **Gradual rollout**: Start with small percentage of records
- **Monitoring**: Enhanced monitoring during migration period
- **Rollback plan**: Quick rollback to original flow if issues arise

## Step-by-Step Migration

### Step 1: Analyze Your Current Flow

First, understand your current flow structure:

```python
# Example current flow
@flow(name="survey-processing")
def survey_processing_flow():
    # Get data to process
    surveys = get_surveys_to_process()

    # Process each survey
    results = process_survey.map(surveys)

    # Generate summary
    return generate_summary(results)

@task
def process_survey(survey_data):
    # Business logic here
    return process_survey_logic(survey_data)
```

**Analysis Questions:**

- How does the flow get its input data?
- What's the processing logic for individual items?
- How are results stored or returned?
- Are there any dependencies between items?
- What error handling exists?

### Step 2: Set Up Configuration

Add distributed processing configuration for your flow:

```bash
# Add to your environment configuration
DEVELOPMENT_YOUR_FLOW_USE_DISTRIBUTED_PROCESSING=false  # Start disabled
DEVELOPMENT_YOUR_FLOW_DISTRIBUTED_BATCH_SIZE=50
PRODUCTION_YOUR_FLOW_USE_DISTRIBUTED_PROCESSING=true
PRODUCTION_YOUR_FLOW_DISTRIBUTED_BATCH_SIZE=100
```

Update Prefect configuration:

```bash
# Set up configuration in Prefect
make setup-dev
make setup-prod
```

### Step 3: Create Queue Population Logic

Create a function to add records to the processing queue:

```python
# New queue population function
def populate_survey_queue():
    """Add surveys to processing queue."""
    from core.database import DatabaseManager
    from core.distributed import DistributedProcessor

    # Get surveys that need processing
    surveys = get_surveys_to_process()

    # Convert to queue records
    records = []
    for survey in surveys:
        records.append({
            "survey_id": survey["id"],
            "customer_id": survey["customer_id"],
            "data": survey["data"]
        })

    # Add to queue
    processor = DistributedProcessor(DatabaseManager("rpa_db"))
    count = processor.add_records_to_queue("survey_processor", records)

    print(f"Added {count} surveys to processing queue")
    return count
```

### Step 4: Implement Distributed Version

Create the distributed version of your flow:

```python
from core.config import ConfigManager
from core.flow_template import distributed_processing_flow, process_record_with_status

# Configuration for this flow
config = ConfigManager("survey_processor")

@flow(name="survey-processing-distributed")
def survey_processing_distributed_flow(
    use_distributed: bool = None,
    batch_size: int = None
):
    """Survey processing with optional distributed processing."""

    # Get configuration
    use_distributed = use_distributed if use_distributed is not None else config.get_variable("use_distributed_processing", False)
    batch_size = batch_size if batch_size is not None else config.get_variable("distributed_batch_size", 50)

    if use_distributed:
        # Use distributed processing
        return distributed_processing_flow("survey_processor", batch_size)
    else:
        # Use original logic
        return survey_processing_flow_original()

def survey_processing_flow_original():
    """Original survey processing logic."""
    surveys = get_surveys_to_process()
    results = process_survey.map(surveys)
    return generate_summary(results)

# Override the record processing logic
def process_survey_logic(payload: Dict) -> Dict:
    """Process survey data from queue payload."""

    # Extract survey data from payload
    survey_id = payload["survey_id"]
    customer_id = payload["customer_id"]
    survey_data = payload["data"]

    # Your existing business logic here
    result = {
        "survey_id": survey_id,
        "customer_id": customer_id,
        "processed_at": datetime.now().isoformat(),
        "satisfaction_score": calculate_satisfaction(survey_data),
        "recommendations": generate_recommendations(survey_data)
    }

    # Store results in your target database
    store_survey_results(result)

    return result
```

### Step 5: Update Flow Entry Point

Modify your main flow to support both modes:

```python
@flow(name="survey-processing")
def survey_processing_flow(
    use_distributed: bool = None,
    batch_size: int = None,
    populate_queue: bool = False
):
    """Main survey processing flow with distributed processing support."""

    config = ConfigManager("survey_processor")
    logger = get_run_logger()

    # Get configuration
    use_distributed = use_distributed if use_distributed is not None else config.get_variable("use_distributed_processing", False)

    logger.info(f"Survey processing mode: {'distributed' if use_distributed else 'standard'}")

    if use_distributed:
        # Populate queue if requested
        if populate_queue:
            count = populate_survey_queue()
            logger.info(f"Populated queue with {count} surveys")

        # Run distributed processing
        batch_size = batch_size if batch_size is not None else config.get_variable("distributed_batch_size", 50)
        return distributed_processing_flow("survey_processor", batch_size)
    else:
        # Run original logic
        return survey_processing_flow_original()
```

### Step 6: Test the Migration

Create comprehensive tests for both modes:

```python
# Test file: test_survey_migration.py
import pytest
from unittest.mock import Mock, patch

def test_survey_flow_standard_mode():
    """Test survey flow in standard mode."""
    result = survey_processing_flow(use_distributed=False)

    assert result is not None
    assert "total" in result
    assert "completed" in result

def test_survey_flow_distributed_mode():
    """Test survey flow in distributed mode."""
    # First populate queue
    populate_survey_queue()

    # Then process
    result = survey_processing_flow(use_distributed=True, batch_size=10)

    assert result is not None
    assert "total" in result
    assert "completed" in result

def test_configuration_override():
    """Test configuration can be overridden at runtime."""
    # Test with explicit parameters
    result = survey_processing_flow(
        use_distributed=True,
        batch_size=25
    )

    assert result is not None

@patch('core.database.DatabaseManager')
def test_queue_population(mock_db):
    """Test queue population logic."""
    count = populate_survey_queue()
    assert count >= 0
```

Run tests:

```bash
# Run migration tests
python -m pytest test_survey_migration.py -v

# Test both modes manually
python -c "
from flows.survey.workflow import survey_processing_flow

# Test standard mode
result1 = survey_processing_flow(use_distributed=False)
print(f'Standard mode: {result1}')

# Test distributed mode
result2 = survey_processing_flow(use_distributed=True, populate_queue=True)
print(f'Distributed mode: {result2}')
"
```

## Configuration Setup

### Environment-Specific Configuration

Set up configuration for each environment:

#### Development Configuration

```bash
# Development - start with distributed processing disabled
DEVELOPMENT_SURVEY_PROCESSOR_USE_DISTRIBUTED_PROCESSING=false
DEVELOPMENT_SURVEY_PROCESSOR_DISTRIBUTED_BATCH_SIZE=10
DEVELOPMENT_SURVEY_PROCESSOR_CLEANUP_TIMEOUT_HOURS=1
DEVELOPMENT_SURVEY_PROCESSOR_MAX_RETRIES=2
```

#### Staging Configuration

```bash
# Staging - enable for testing
STAGING_SURVEY_PROCESSOR_USE_DISTRIBUTED_PROCESSING=true
STAGING_SURVEY_PROCESSOR_DISTRIBUTED_BATCH_SIZE=25
STAGING_SURVEY_PROCESSOR_CLEANUP_TIMEOUT_HOURS=2
STAGING_SURVEY_PROCESSOR_MAX_RETRIES=3
```

#### Production Configuration

```bash
# Production - enable with optimized settings
PRODUCTION_SURVEY_PROCESSOR_USE_DISTRIBUTED_PROCESSING=true
PRODUCTION_SURVEY_PROCESSOR_DISTRIBUTED_BATCH_SIZE=100
PRODUCTION_SURVEY_PROCESSOR_CLEANUP_TIMEOUT_HOURS=2
PRODUCTION_SURVEY_PROCESSOR_MAX_RETRIES=5
```

### Apply Configuration

```bash
# Apply configuration to Prefect
make setup-dev
make setup-staging
make setup-prod

# Verify configuration
python -c "
from core.config import ConfigManager
config = ConfigManager('survey_processor')
print(f'Use distributed: {config.get_variable(\"use_distributed_processing\", False)}')
print(f'Batch size: {config.get_variable(\"distributed_batch_size\", 50)}')
"
```

## Testing Your Migration

### Unit Testing

Test individual components:

```python
def test_queue_population():
    """Test adding records to queue."""
    from core.distributed import DistributedProcessor
    from core.database import DatabaseManager

    processor = DistributedProcessor(DatabaseManager("rpa_db"))

    # Add test records
    records = [{"survey_id": f"TEST-{i}"} for i in range(5)]
    count = processor.add_records_to_queue("test_flow", records)

    assert count == 5

    # Verify queue status
    status = processor.get_queue_status("test_flow")
    assert status["pending_records"] >= 5

def test_record_processing():
    """Test individual record processing."""
    test_payload = {
        "survey_id": "TEST-001",
        "customer_id": "CUST-001",
        "data": {"q1": 5, "q2": 4}
    }

    result = process_survey_logic(test_payload)

    assert result["survey_id"] == "TEST-001"
    assert "satisfaction_score" in result
    assert "processed_at" in result
```

### Integration Testing

Test the complete flow:

```bash
# Create test script
cat > test_migration_integration.py << 'EOF'
#!/usr/bin/env python3

import time
from flows.survey.workflow import survey_processing_flow, populate_survey_queue
from core.distributed import DistributedProcessor
from core.database import DatabaseManager

def test_integration():
    """Test complete migration integration."""

    print("=== Integration Test: Survey Processing Migration ===")

    # 1. Test standard mode
    print("\n1. Testing standard mode...")
    result1 = survey_processing_flow(use_distributed=False)
    print(f"Standard mode result: {result1}")

    # 2. Populate queue for distributed mode
    print("\n2. Populating queue...")
    count = populate_survey_queue()
    print(f"Added {count} records to queue")

    # 3. Test distributed mode
    print("\n3. Testing distributed mode...")
    result2 = survey_processing_flow(use_distributed=True, batch_size=10)
    print(f"Distributed mode result: {result2}")

    # 4. Check queue status
    print("\n4. Checking queue status...")
    processor = DistributedProcessor(DatabaseManager("rpa_db"))
    status = processor.get_queue_status("survey_processor")
    print(f"Queue status: {status}")

    # 5. Health check
    print("\n5. Health check...")
    health = processor.health_check()
    print(f"System health: {health['status']}")

    print("\n=== Integration test completed successfully ===")

if __name__ == "__main__":
    test_integration()
EOF

# Run integration test
python test_migration_integration.py
```

### Load Testing

Test with realistic load:

```python
def test_concurrent_processing():
    """Test concurrent processing with multiple containers."""
    import concurrent.futures
    import threading

    # Populate queue with many records
    records = [{"survey_id": f"LOAD-{i}"} for i in range(1000)]
    processor = DistributedProcessor(DatabaseManager("rpa_db"))
    processor.add_records_to_queue("load_test", records)

    # Simulate multiple containers processing
    def process_batch():
        return survey_processing_flow(
            use_distributed=True,
            batch_size=50
        )

    # Run multiple concurrent batches
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_batch) for _ in range(3)]
        results = [f.result() for f in futures]

    # Verify no duplicate processing
    total_processed = sum(r.get("completed", 0) for r in results)
    print(f"Total processed: {total_processed}")

    # Check for any remaining records
    status = processor.get_queue_status("load_test")
    print(f"Remaining in queue: {status}")
```

## Deployment Considerations

### Gradual Rollout Strategy

#### Phase 1: Parallel Deployment (Week 1)

Deploy both versions, use feature flag to control:

```yaml
# Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: survey-processor-v2
spec:
  replicas: 1 # Start with single instance
  template:
    spec:
      containers:
        - name: survey-processor
          image: survey-processor:v2-distributed
          env:
            - name: PREFECT_ENVIRONMENT
              value: "production"
            - name: SURVEY_PROCESSOR_USE_DISTRIBUTED_PROCESSING
              value: "false" # Start disabled
```

#### Phase 2: Limited Traffic (Week 2)

Enable distributed processing for small percentage:

```bash
# Enable for 10% of traffic
PRODUCTION_SURVEY_PROCESSOR_USE_DISTRIBUTED_PROCESSING=true
PRODUCTION_SURVEY_PROCESSOR_DISTRIBUTED_BATCH_SIZE=25  # Small batches initially
```

#### Phase 3: Scale Up (Week 3)

Increase traffic and container count:

```yaml
spec:
  replicas: 3 # Scale to multiple instances
```

```bash
# Increase batch size
PRODUCTION_SURVEY_PROCESSOR_DISTRIBUTED_BATCH_SIZE=100
```

#### Phase 4: Full Migration (Week 4)

Complete migration and remove old code:

```bash
# Full distributed processing
PRODUCTION_SURVEY_PROCESSOR_USE_DISTRIBUTED_PROCESSING=true
```

### Monitoring During Migration

Set up enhanced monitoring:

```python
# Enhanced monitoring during migration
@flow(name="migration-monitoring")
def migration_monitoring_flow():
    """Monitor migration progress and health."""

    from core.monitoring import (
        distributed_queue_monitoring,
        processing_performance_monitoring
    )

    # Queue health
    queue_status = distributed_queue_monitoring()

    # Performance metrics
    performance = processing_performance_monitoring(time_window_hours=1)

    # Alert on issues
    if queue_status["queue_health_assessment"]["queue_health"] != "healthy":
        send_alert(f"Queue health issue: {queue_status}")

    if performance["overall_metrics"]["success_rate_percent"] < 95:
        send_alert(f"Low success rate: {performance}")

    return {
        "queue_health": queue_status["queue_health_assessment"]["queue_health"],
        "success_rate": performance["overall_metrics"]["success_rate_percent"],
        "processing_rate": performance["overall_metrics"]["avg_processing_rate_per_hour"]
    }

# Schedule monitoring every 15 minutes during migration
```

### Database Considerations

#### Connection Pool Sizing

Adjust connection pools for increased load:

```bash
# Increase pool size for distributed processing
PRODUCTION_GLOBAL_RPA_DB_POOL_SIZE=20
PRODUCTION_GLOBAL_RPA_DB_MAX_OVERFLOW=40
```

#### Index Optimization

Ensure optimal indexes:

```sql
-- Monitor index usage during migration
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

#### Cleanup Strategy

Set up automated cleanup:

```python
@flow(name="migration-cleanup")
def migration_cleanup_flow():
    """Clean up old processed records during migration."""

    processor = DistributedProcessor(DatabaseManager("rpa_db"))

    # Clean up orphaned records
    orphaned = processor.cleanup_orphaned_records(timeout_hours=2)

    # Clean up old completed records (older than 7 days)
    from core.database import DatabaseManager
    db = DatabaseManager("rpa_db")

    cleanup_query = """
        DELETE FROM processing_queue
        WHERE status = 'completed'
        AND completed_at < NOW() - INTERVAL '7 days'
    """

    result = db.execute_query("rpa_db", cleanup_query)

    return {
        "orphaned_cleaned": orphaned,
        "old_records_cleaned": result.rowcount if result else 0
    }
```

## Rollback Plan

### Immediate Rollback

If issues arise, quickly disable distributed processing:

```bash
# Emergency rollback - disable distributed processing
kubectl set env deployment/survey-processor SURVEY_PROCESSOR_USE_DISTRIBUTED_PROCESSING=false

# Or update Prefect configuration
python -c "
from prefect.blocks.system import Variable
Variable(value='false').save('production.survey_processor.use_distributed_processing', overwrite=True)
"
```

### Gradual Rollback

For planned rollback:

1. **Stop new queue population**
2. **Process remaining queue records**
3. **Switch back to standard processing**
4. **Scale down distributed containers**

```python
@flow(name="rollback-migration")
def rollback_migration_flow():
    """Rollback from distributed to standard processing."""

    processor = DistributedProcessor(DatabaseManager("rpa_db"))

    # 1. Check queue status
    status = processor.get_queue_status("survey_processor")
    pending = status.get("pending_records", 0)

    if pending > 0:
        print(f"Processing remaining {pending} records...")

        # Process remaining records
        while pending > 0:
            result = survey_processing_flow(use_distributed=True, batch_size=100)
            if result.get("total", 0) == 0:
                break  # No more records to process

            # Check status again
            status = processor.get_queue_status("survey_processor")
            pending = status.get("pending_records", 0)

    # 2. Disable distributed processing
    from prefect.blocks.system import Variable
    Variable(value='false').save('production.survey_processor.use_distributed_processing', overwrite=True)

    print("Rollback completed - distributed processing disabled")

    return {"status": "rollback_completed", "remaining_records": pending}
```

### Data Integrity Verification

Verify no data loss during rollback:

```python
def verify_migration_integrity():
    """Verify no data was lost during migration."""

    # Compare record counts before and after migration
    # Check for any orphaned or stuck records
    # Verify all expected results were produced

    processor = DistributedProcessor(DatabaseManager("rpa_db"))

    # Check for stuck records
    status = processor.get_queue_status("survey_processor")

    issues = []

    if status.get("processing_records", 0) > 0:
        issues.append(f"Found {status['processing_records']} stuck in processing")

    if status.get("failed_records", 0) > 10:  # Threshold
        issues.append(f"High number of failed records: {status['failed_records']}")

    # Check database consistency
    # Add your specific integrity checks here

    return {
        "status": "verified" if not issues else "issues_found",
        "issues": issues,
        "queue_status": status
    }
```

## Common Migration Patterns

### Pattern 1: File Processing Flow

**Before:**

```python
@flow
def file_processing_flow():
    files = get_files_to_process()
    results = process_file.map(files)
    return summarize_results(results)
```

**After:**

```python
@flow
def file_processing_flow(use_distributed=None, populate_queue=False):
    config = ConfigManager("file_processor")
    use_distributed = use_distributed if use_distributed is not None else config.get_variable("use_distributed_processing", False)

    if use_distributed:
        if populate_queue:
            files = get_files_to_process()
            records = [{"file_path": f} for f in files]
            processor = DistributedProcessor(DatabaseManager("rpa_db"))
            processor.add_records_to_queue("file_processor", records)

        return distributed_processing_flow("file_processor", config.get_variable("distributed_batch_size", 50))
    else:
        files = get_files_to_process()
        results = process_file.map(files)
        return summarize_results(results)

def process_file_logic(payload):
    """Process file from queue payload."""
    file_path = payload["file_path"]
    # Your existing file processing logic
    return process_file_content(file_path)
```

### Pattern 2: Database ETL Flow

**Before:**

```python
@flow
def etl_flow():
    records = extract_data()
    transformed = transform_data.map(records)
    load_results = load_data.map(transformed)
    return generate_etl_summary(load_results)
```

**After:**

```python
@flow
def etl_flow(use_distributed=None, populate_queue=False):
    config = ConfigManager("etl_processor")
    use_distributed = use_distributed if use_distributed is not None else config.get_variable("use_distributed_processing", False)

    if use_distributed:
        if populate_queue:
            records = extract_data()
            queue_records = [{"record_id": r["id"], "data": r} for r in records]
            processor = DistributedProcessor(DatabaseManager("rpa_db"))
            processor.add_records_to_queue("etl_processor", queue_records)

        return distributed_processing_flow("etl_processor", config.get_variable("distributed_batch_size", 100))
    else:
        records = extract_data()
        transformed = transform_data.map(records)
        load_results = load_data.map(transformed)
        return generate_etl_summary(load_results)

def process_etl_logic(payload):
    """Process ETL record from queue payload."""
    record_data = payload["data"]

    # Transform
    transformed = transform_record(record_data)

    # Load
    result = load_record(transformed)

    return result
```

### Pattern 3: API Processing Flow

**Before:**

```python
@flow
def api_processing_flow():
    requests = get_pending_requests()
    responses = process_api_request.map(requests)
    return update_request_status(responses)
```

**After:**

```python
@flow
def api_processing_flow(use_distributed=None, populate_queue=False):
    config = ConfigManager("api_processor")
    use_distributed = use_distributed if use_distributed is not None else config.get_variable("use_distributed_processing", False)

    if use_distributed:
        if populate_queue:
            requests = get_pending_requests()
            queue_records = [{"request_id": r["id"], "endpoint": r["endpoint"], "payload": r["payload"]} for r in requests]
            processor = DistributedProcessor(DatabaseManager("rpa_db"))
            processor.add_records_to_queue("api_processor", queue_records)

        return distributed_processing_flow("api_processor", config.get_variable("distributed_batch_size", 25))
    else:
        requests = get_pending_requests()
        responses = process_api_request.map(requests)
        return update_request_status(responses)

def process_api_logic(payload):
    """Process API request from queue payload."""
    request_id = payload["request_id"]
    endpoint = payload["endpoint"]
    request_payload = payload["payload"]

    # Make API call
    response = make_api_call(endpoint, request_payload)

    # Update request status
    update_request_result(request_id, response)

    return {
        "request_id": request_id,
        "status": "completed",
        "response_code": response.status_code
    }
```

## Troubleshooting Migration Issues

### Issue: Records Not Being Claimed

**Symptoms:**

- Queue has pending records but no processing occurs
- `claim_records_batch()` returns empty list

**Solutions:**

1. Check flow_name matches queue records
2. Verify database connectivity
3. Check for database locks or deadlocks
4. Ensure proper indexes exist

```python
# Debug record claiming
processor = DistributedProcessor(DatabaseManager("rpa_db"))

# Check queue status
status = processor.get_queue_status("your_flow_name")
print(f"Queue status: {status}")

# Try manual claim
records = processor.claim_records_batch("your_flow_name", 5)
print(f"Claimed records: {len(records)}")
```

### Issue: High Error Rates After Migration

**Symptoms:**

- Many records marked as failed
- Error messages in processing_queue.error_message

**Solutions:**

1. Review error messages for patterns
2. Check business logic for edge cases
3. Verify database connectivity
4. Update error handling

```python
# Analyze error patterns
from core.database import DatabaseManager

db = DatabaseManager("rpa_db")
errors = db.execute_query("rpa_db", """
    SELECT error_message, COUNT(*) as count
    FROM processing_queue
    WHERE status = 'failed'
    AND created_at > NOW() - INTERVAL '24 hours'
    GROUP BY error_message
    ORDER BY count DESC
    LIMIT 10
""")

for error, count in errors:
    print(f"{count}: {error}")
```

### Issue: Performance Degradation

**Symptoms:**

- Slower processing after migration
- High database CPU usage
- Connection pool exhaustion

**Solutions:**

1. Optimize batch sizes
2. Check database indexes
3. Monitor connection pool usage
4. Scale database resources

```python
# Monitor performance
from core.monitoring import processing_performance_monitoring

performance = processing_performance_monitoring(time_window_hours=6)
print(f"Success rate: {performance['overall_metrics']['success_rate_percent']}%")
print(f"Processing rate: {performance['overall_metrics']['avg_processing_rate_per_hour']} records/hour")

# Check connection pool
from core.tasks import connection_pool_monitoring

pool_status = connection_pool_monitoring("rpa_db")
print(f"Pool utilization: {pool_status['utilization_percent']}%")
```

## Best Practices for Migration

### Planning

- **Start small**: Begin with non-critical flows
- **Test thoroughly**: Comprehensive testing in staging environment
- **Monitor closely**: Enhanced monitoring during migration
- **Have rollback plan**: Quick rollback procedure ready

### Implementation

- **Gradual rollout**: Phased approach with feature flags
- **Backward compatibility**: Keep existing flows working
- **Configuration driven**: Use configuration to control migration
- **Data integrity**: Verify no data loss during migration

### Operations

- **Monitor performance**: Track key metrics during migration
- **Alert on issues**: Set up alerts for problems
- **Document changes**: Keep detailed migration log
- **Team communication**: Keep team informed of migration progress

### Post-Migration

- **Performance tuning**: Optimize based on production usage
- **Cleanup**: Remove old code and unused configuration
- **Documentation**: Update documentation with new patterns
- **Knowledge sharing**: Share lessons learned with team

## Conclusion

Migrating to distributed processing enables horizontal scaling and improved fault tolerance. By following this guide's phased approach, you can safely migrate your flows while maintaining backward compatibility and minimizing risk.

Key success factors:

- Thorough testing in staging environment
- Gradual rollout with monitoring
- Clear rollback plan
- Team coordination and communication

For additional help, refer to:

- [API Reference](API_REFERENCE.md) for detailed API documentation
- [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) for common issues
- [Operations Runbook](DISTRIBUTED_PROCESSING_OPERATIONS_RUNBOOK.md) for production operations
