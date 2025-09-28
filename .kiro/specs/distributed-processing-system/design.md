# Design Document

## Overview

This design document outlines the implementation of a distributed processing system that prevents duplicate record processing when deploying multiple container instances of Prefect flows. The system uses database-level locking to ensure each record is processed exactly once, even when multiple flow instances are running concurrently.

The design builds upon the existing unified DatabaseManager system, leveraging its multi-database support, connection pooling, migration management, and health monitoring capabilities. The system emphasizes performance, reliability, and operational visibility while maintaining simplicity for the MVP implementation.

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Container Layer                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Container 1   │  │   Container 2   │  │ Container 3 │ │
│  │   (RPA Flow)    │  │   (RPA Flow)    │  │ (RPA Flow)  │ │
│  └─────────┬───────┘  └─────────┬───────┘  └─────┬───────┘ │
│            │                    │                │         │
│            └────────────────────┼────────────────┘         │
│                                 │                          │
│  ┌──────────────────────────────▼──────────────────────────┐ │
│  │           Distributed Processing Layer                  │ │
│  │  ┌─────────────────┐  ┌─────────────────┐              │ │
│  │  │ DatabaseManager │  │ DatabaseManager │              │ │
│  │  │    (rpa_db)     │  │  (SurveyHub)    │              │ │
│  │  │   PostgreSQL    │  │   SQL Server    │              │ │
│  │  └─────────────────┘  └─────────────────┘              │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
            │                                    │
            ▼                                    ▼
┌─────────────────────┐                ┌─────────────────────┐
│   PostgreSQL DB     │                │   SQL Server DB     │
│     (rpa_db)        │                │   (SurveyHub)       │
│                     │                │                     │
│ ┌─────────────────┐ │                │ ┌─────────────────┐ │
│ │processing_queue │ │                │ │survey_responses │ │
│ │processed_surveys│ │                │ │customer_data    │ │
│ │flow_logs        │ │                │ │(read-only)      │ │
│ └─────────────────┘ │                │ └─────────────────┘ │
└─────────────────────┘                └─────────────────────┘
```

### Component Architecture

```
core/
├── database.py              # Existing DatabaseManager (already implemented)
├── distributed.py           # New DistributedProcessor class
├── flow_template.py         # New distributed flow template
└── migrations/
    └── rpa_db/             # PostgreSQL migrations for distributed processing
        ├── V006__Create_processing_queue.sql
        └── V007__Add_processing_indexes.sql

flows/
├── examples/
│   └── distributed_survey_processing.py  # Example distributed flow
├── rpa1/
│   └── workflow.py         # Updated to use distributed processing
├── rpa2/
│   └── workflow.py         # Updated to use distributed processing
└── rpa3/
    └── workflow.py         # Updated to use distributed processing
```

## Components and Interfaces

### DistributedProcessor Class

The `DistributedProcessor` class handles the core distributed processing logic, working with the existing DatabaseManager to provide atomic record claiming and status management.

#### Key Responsibilities

- Claim records in batches using `FOR UPDATE SKIP LOCKED`
- Manage record status transitions (pending → processing → completed/failed)
- Handle individual record failures without affecting batch processing
- Provide cleanup operations for orphaned records
- Generate unique instance identifiers for container isolation

#### Core Interface

```python
class DistributedProcessor:
    def __init__(self, rpa_db_manager: DatabaseManager, source_db_manager: DatabaseManager = None)

    # Record Management
    def claim_records_batch(self, flow_name: str, batch_size: int) -> List[Dict]
    def mark_record_completed(self, record_id: int, result: Dict) -> None
    def mark_record_failed(self, record_id: int, error: str) -> None

    # Queue Management
    def add_records_to_queue(self, flow_name: str, records: List[Dict]) -> int
    def get_queue_status(self, flow_name: str = None) -> Dict

    # Maintenance Operations
    def cleanup_orphaned_records(self, timeout_hours: int = 1) -> int
    def reset_failed_records(self, flow_name: str, max_retries: int = 3) -> int

    # Health and Monitoring
    def health_check(self) -> Dict[str, Any]
```

#### DatabaseManager Integration

The DistributedProcessor leverages the existing DatabaseManager's capabilities:

- **Connection Pooling**: Uses DatabaseManager's SQLAlchemy connection pooling
- **Error Handling**: Leverages DatabaseManager's comprehensive error handling
- **Health Monitoring**: Integrates with DatabaseManager's health_check() method
- **Configuration**: Uses DatabaseManager's ConfigManager integration
- **Logging**: Uses DatabaseManager's Prefect logging integration

```python
class DistributedProcessor:
    def __init__(self, rpa_db_manager: DatabaseManager, source_db_manager: DatabaseManager = None):
        """
        Initialize DistributedProcessor with existing DatabaseManager instances.

        Args:
            rpa_db_manager: DatabaseManager instance for PostgreSQL (queue and results)
            source_db_manager: Optional DatabaseManager for source data (SQL Server)
        """
        self.rpa_db = rpa_db_manager
        self.source_db = source_db_manager
        self.logger = self.rpa_db.logger  # Use DatabaseManager's logger
```

### Flow Template System

The flow template provides a standardized pattern for converting existing flows to use distributed processing.

#### Template Structure

```python
# Module-level instances for performance optimization
rpa_db_manager = DatabaseManager("rpa_db")
source_db_manager = DatabaseManager("SurveyHub")
processor = DistributedProcessor(rpa_db_manager, source_db_manager)

@flow(name="distributed-survey-processing")
def distributed_processing_flow(flow_name: str, batch_size: int = 100):
    """Distributed survey processing flow template."""

    # 1. Verify database health before processing
    health_status = processor.health_check()
    if health_status["status"] == "unhealthy":
        raise RuntimeError(f"Database health check failed: {health_status.get('error', 'Unknown error')}")

    # 2. Claim records from queue
    records = processor.claim_records_batch(flow_name, batch_size)

    if not records:
        return {"message": "No records to process"}

    # 3. Process records using Prefect .map()
    results = process_record_with_status.map(records)

    # 4. Generate summary
    return generate_processing_summary(results, flow_name)

@task(retries=2, retry_delay_seconds=30)
def process_record_with_status(record: Dict) -> Dict:
    """Process individual record with status management."""

    try:
        # Process the record (business logic)
        result = process_business_logic(record['payload'])

        # Mark as completed
        processor.mark_record_completed(record['id'], result)

        return {"record_id": record['id'], "status": "completed", "result": result}

    except Exception as e:
        # Mark as failed
        processor.mark_record_failed(record['id'], str(e))

        return {"record_id": record['id'], "status": "failed", "error": str(e)}
        # Note: Not re-raising to prevent Prefect retries conflicting with DB retry logic
```

### Database Schema Design

#### Processing Queue Table

The core table for managing distributed processing state:

```sql
-- V006__Create_processing_queue.sql
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

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_processing_queue_updated_at
    BEFORE UPDATE ON processing_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

#### Performance Indexes

```sql
-- V007__Add_processing_indexes.sql
-- Essential indexes for performance
CREATE INDEX idx_processing_queue_status_created ON processing_queue(status, created_at);
CREATE INDEX idx_processing_queue_flow_name_status ON processing_queue(flow_name, status);
CREATE INDEX idx_processing_queue_claimed_at ON processing_queue(claimed_at) WHERE claimed_at IS NOT NULL;
CREATE INDEX idx_processing_queue_instance_id ON processing_queue(flow_instance_id) WHERE flow_instance_id IS NOT NULL;

-- Partial indexes for common queries
CREATE INDEX idx_processing_queue_pending ON processing_queue(created_at) WHERE status = 'pending';
CREATE INDEX idx_processing_queue_processing ON processing_queue(claimed_at) WHERE status = 'processing';
```

### Record Claiming Algorithm

The core algorithm for atomic record claiming uses PostgreSQL's `FOR UPDATE SKIP LOCKED`:

```sql
-- Atomic record claiming query
UPDATE processing_queue
SET status = 'processing',
    flow_instance_id = :instance_id,
    claimed_at = NOW(),
    updated_at = NOW()
WHERE id IN (
    SELECT id FROM processing_queue
    WHERE flow_name = :flow_name AND status = 'pending'
    ORDER BY created_at ASC
    LIMIT :batch_size
    FOR UPDATE SKIP LOCKED
)
RETURNING id, payload, retry_count, created_at;
```

#### Key Features

- **Atomic Operation**: Entire claim operation is atomic
- **Skip Locked**: Prevents blocking when multiple containers compete
- **FIFO Processing**: Orders by created_at for first-in-first-out processing
- **Unique Instance ID**: Prevents hostname collisions using UUID

### Multi-Database Processing Pattern

The system supports reading from one database and writing to another:

```python
def process_survey_logic(payload: Dict) -> Dict:
    """Process survey data using multi-database pattern."""

    # Read source data from SQL Server
    survey_data = source_db_manager.execute_query(
        """SELECT survey_id, customer_id, response_data, submitted_at
           FROM survey_responses
           WHERE survey_id = :survey_id""",
        {"survey_id": payload["survey_id"]}
    )

    if not survey_data:
        raise ValueError(f"Survey {payload['survey_id']} not found")

    # Process the data (business logic)
    survey = survey_data[0]
    processed_result = transform_survey_data(survey)

    # Write results to PostgreSQL
    rpa_db_manager.execute_query(
        """INSERT INTO processed_surveys
           (survey_id, customer_id, satisfaction_score, processed_at)
           VALUES (:survey_id, :customer_id, :satisfaction_score, :processed_at)""",
        processed_result
    )

    return processed_result
```

## Data Models

### Processing Queue Data Model

```python
# Processing Queue Record
{
    "id": int,                    # Primary key
    "flow_name": str,            # Flow identifier
    "payload": dict,             # Record data (JSONB)
    "status": str,               # pending|processing|completed|failed
    "flow_instance_id": str,     # Container instance identifier
    "claimed_at": datetime,      # When record was claimed
    "completed_at": datetime,    # When processing completed
    "error_message": str,        # Error details if failed
    "retry_count": int,          # Number of retry attempts
    "created_at": datetime,      # Record creation time
    "updated_at": datetime       # Last update time
}
```

### Health Status Data Model

```python
# Distributed Processing Health Status
{
    "status": "healthy|degraded|unhealthy",
    "databases": {
        "rpa_db": {
            "status": "healthy",
            "connection": true,
            "response_time_ms": 45.2
        },
        "SurveyHub": {
            "status": "healthy",
            "connection": true,
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
        "hostname": "rpa-worker-1",
        "active_flows": ["survey_processor", "order_processor"]
    },
    "timestamp": "2024-01-15T10:30:00Z"
}
```

### Configuration Data Model

Building on the existing ConfigManager system:

```env
# Database Configuration (existing pattern)
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_db
DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE=sqlserver
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://user:pass@server:1433/survey_hub

# Distributed Processing Configuration (new)
DEVELOPMENT_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE=100
DEVELOPMENT_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS=1
DEVELOPMENT_DISTRIBUTED_PROCESSOR_MAX_RETRIES=3
DEVELOPMENT_DISTRIBUTED_PROCESSOR_HEALTH_CHECK_INTERVAL=300
```

## Error Handling

### Error Categories and Strategies

#### Database Connection Errors

- **Strategy**: Fail fast when databases are unavailable to prevent data inconsistency
- **Handling**: Use DatabaseManager's health_check() for connection validation before processing
- **Recovery**: Automatic retry with exponential backoff via tenacity integration, but fail if databases remain unavailable
- **Flow Behavior**: Stop processing and raise exceptions when required databases are unhealthy

#### Record Processing Errors

- **Individual Record Failures**: Mark record as failed, continue processing batch
- **Batch Processing Failures**: Log error, return empty result set for retry
- **Transaction Failures**: Use DatabaseManager's transaction rollback capabilities

#### Container Coordination Errors

- **Instance ID Conflicts**: Use UUID-based instance IDs to prevent collisions
- **Orphaned Records**: Automatic cleanup based on configurable timeout
- **Network Partitions**: Each container operates independently without coordination

### Retry Logic Implementation

```python
# Leveraging DatabaseManager's existing retry capabilities
@_create_retry_decorator(max_attempts=3, min_wait=1.0, max_wait=10.0)
def claim_records_batch_with_retry(self, flow_name: str, batch_size: int) -> List[Dict]:
    """Claim records with automatic retry for transient failures."""
    return self.claim_records_batch(flow_name, batch_size)
```

### Graceful Degradation

- **Database Unavailable**: Fail fast and stop processing to prevent data inconsistency
- **Database Connection Issues**: Use DatabaseManager's retry logic, but fail if databases remain unavailable
- **High Error Rates**: Implement circuit breaker pattern for problematic flows
- **Individual Record Failures**: Continue processing other records in the batch, mark failed records appropriately

## Testing Strategy

### Unit Testing

- **DistributedProcessor Class**: Mock DatabaseManager instances for isolated testing
- **Flow Template**: Test flow logic with mocked processor and database operations
- **Record Claiming**: Test atomic claiming logic with concurrent scenarios
- **Error Handling**: Comprehensive error scenario testing

### Integration Testing

- **Multi-Container Testing**: Deploy multiple containers, verify no duplicate processing
- **Database Integration**: Test with actual PostgreSQL and SQL Server databases
- **Migration Testing**: Verify schema creation and migration execution
- **Health Monitoring**: Test health check accuracy across different failure scenarios

### Performance Testing

- **Concurrent Load**: Test with multiple containers processing simultaneously
- **Batch Size Optimization**: Benchmark different batch sizes for throughput
- **Database Performance**: Monitor connection pool utilization and query performance
- **Memory Usage**: Profile memory consumption under various loads

### Chaos Testing

- **Container Failures**: Kill containers during processing, verify recovery
- **Database Failures**: Simulate database outages, test graceful degradation
- **Network Partitions**: Test behavior during network connectivity issues
- **Resource Exhaustion**: Test behavior under high load and resource constraints

## Security Considerations

### Database Security

- **Credential Management**: Use DatabaseManager's ConfigManager integration
- **Connection Security**: Leverage DatabaseManager's SSL/TLS support
- **Query Security**: Use DatabaseManager's parameterized query execution
- **Access Control**: Implement least-privilege database user permissions

### Container Security

- **Instance Isolation**: Unique instance IDs prevent cross-container interference
- **Resource Limits**: Configure appropriate CPU and memory limits
- **Network Security**: Implement network policies for container communication
- **Image Security**: Regular security scanning of container images

### Data Security

- **Payload Encryption**: Consider encrypting sensitive data in processing_queue.payload
- **Audit Logging**: Log all record state transitions for audit trails
- **Data Retention**: Implement policies for cleaning up old processed records
- **Error Sanitization**: Ensure error messages don't expose sensitive information

## Performance Optimization

### Database Optimization

- **Connection Pooling**: Leverage DatabaseManager's SQLAlchemy connection pooling
- **Index Strategy**: Optimize indexes for common query patterns
- **Query Optimization**: Use efficient queries with proper WHERE clauses
- **Batch Operations**: Process records in configurable batch sizes

### Memory Management

- **Object Reuse**: Module-level DatabaseManager and DistributedProcessor instances
- **Result Streaming**: Process large result sets efficiently
- **Garbage Collection**: Proper cleanup of database connections and results
- **Resource Monitoring**: Monitor memory usage patterns

### Container Optimization

- **Resource Allocation**: Right-size CPU and memory based on workload
- **Startup Optimization**: Fast container startup for scaling scenarios
- **Health Checks**: Efficient health check implementation
- **Graceful Shutdown**: Proper cleanup during container termination

### Monitoring and Metrics

- **Processing Metrics**: Track records processed per minute, error rates
- **Database Metrics**: Monitor connection pool utilization, query performance
- **Container Metrics**: CPU, memory, and network usage monitoring
- **Business Metrics**: Track end-to-end processing latency and throughput

## Deployment Architecture

### Container Deployment

```yaml
# Kubernetes Deployment Example
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
          image: rpa-solution:distributed-v1
          env:
            - name: PREFECT_ENVIRONMENT
              value: "production"
            - name: HOSTNAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 5
```

### Scaling Strategy

- **Horizontal Scaling**: Add more container replicas based on queue depth
- **Auto-scaling**: Use Kubernetes HPA based on CPU/memory or custom metrics
- **Load Balancing**: Distribute processing load across available containers
- **Resource Management**: Monitor and adjust resource allocation based on usage

### Environment Configuration

```env
# Production Environment Configuration
PRODUCTION_GLOBAL_RPA_DB_TYPE=postgresql
PRODUCTION_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://rpa_user:${RPA_DB_PASSWORD}@rpa-db:5432/rpa_db
PRODUCTION_GLOBAL_SURVEYHUB_TYPE=sqlserver
PRODUCTION_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://survey_user:${SURVEY_DB_PASSWORD}@survey-db:1433/survey_hub

PRODUCTION_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE=50
PRODUCTION_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS=2
PRODUCTION_DISTRIBUTED_PROCESSOR_MAX_RETRIES=5
```

## Operational Considerations

### Monitoring and Alerting

- **Queue Depth Monitoring**: Alert when queue depth exceeds thresholds
- **Error Rate Monitoring**: Alert on high error rates or processing failures
- **Database Health**: Monitor database connectivity and performance
- **Container Health**: Track container resource usage and availability

### Maintenance Operations

- **Queue Cleanup**: Regular cleanup of old completed/failed records
- **Orphaned Record Recovery**: Automated cleanup of stuck processing records
- **Performance Tuning**: Regular review of batch sizes and resource allocation
- **Schema Evolution**: Manage database schema changes through migrations

### Troubleshooting

- **High Queue Depth**: Check container health, scale up if needed
- **Processing Failures**: Review error logs, check database connectivity
- **Performance Issues**: Monitor connection pool utilization, query performance
- **Container Issues**: Check resource limits, health check status

### Disaster Recovery

- **Database Backup**: Regular backups of processing queue and results
- **Container Recovery**: Fast container restart and scaling capabilities
- **Data Recovery**: Ability to replay failed records from backup
- **Rollback Strategy**: Safe rollback procedures for problematic deployments
