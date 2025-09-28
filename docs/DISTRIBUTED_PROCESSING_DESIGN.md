# 🏗️ Distributed Processing System - MVP Design Document

## 📋 Executive Summary

This document outlines a **minimal viable product (MVP)** for a distributed processing system that prevents duplicate record processing when deploying multiple container instances of Prefect flows. The system uses database-level locking to ensure each record is processed exactly once, even when multiple flow instances are running concurrently.

## 🎯 Core Requirements

### **Primary Goals**
- ✅ **Prevent duplicate processing** when multiple containers run the same flow
- ✅ **Handle individual record failures** gracefully within `.map()` operations
- ✅ **Provide fault tolerance** for container failures and network issues
- ✅ **Enable horizontal scaling** by adding more container instances
- ✅ **Maintain data consistency** across all processing instances

### **MVP Scope**
- ✅ **Database-level locking** using `FOR UPDATE SKIP LOCKED`
- ✅ **Basic error handling** and retry logic
- ✅ **Simple health monitoring** (database connection, queue depth)
- ✅ **Automatic cleanup** of orphaned records
- ✅ **Container deployment** with 2-3 instances

## 🏛️ System Architecture

### **High-Level Overview**
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
                    │  (PostgreSQL/MySQL)       │
                    │  - Processing Queue       │
                    │  - Record Locking         │
                    │  - Status Tracking        │
                    └───────────────────────────┘
```

### **Core Components**

#### **1. Database Manager**
- **Purpose**: Manages the processing queue and record locking
- **Key Features**:
  - Atomic record claiming using `FOR UPDATE SKIP LOCKED`
  - Status tracking (pending, processing, completed, failed)
  - Automatic cleanup of orphaned records
  - Basic retry logic

#### **2. Distributed Processor**
- **Purpose**: Handles the distributed processing logic
- **Key Features**:
  - Claim records in batches
  - Process individual records with error handling
  - Update record status (completed/failed)
  - Basic health monitoring

#### **3. Flow Template**
- **Purpose**: Standardized template for distributed flows
- **Key Features**:
  - Record claiming and processing
  - Error handling and retry logic
  - Status reporting
  - Cleanup operations

## 🗄️ Database Design

### **Core Table: `processing_queue`**
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
    created_at TIMESTAMP DEFAULT NOW()
);

-- Essential indexes for performance
CREATE INDEX idx_processing_queue_status ON processing_queue(status, created_at);
CREATE INDEX idx_processing_queue_claimed ON processing_queue(claimed_at);
CREATE INDEX idx_processing_queue_flow_name ON processing_queue(flow_name, status);
```

### **Key Features**
- **Atomic Locking**: `FOR UPDATE SKIP LOCKED` prevents race conditions
- **Status Tracking**: Clear record lifecycle management
- **Retry Logic**: Built-in retry counter for failed records
- **Cleanup Support**: Timestamps for orphaned record detection

## 📦 **Dependencies**

Add the following to your `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies
    "psycopg2-binary>=2.9.0",  # PostgreSQL adapter
    "sqlalchemy>=2.0.0",       # Database ORM with connection pooling
]
```

## 🔧 Core Components

### **1. Database Manager Integration**
The distributed processing system integrates with the unified DatabaseManager from `core/database.py`. This provides:

- **Multi-Database Support**: Access to both `rpa_db` (PostgreSQL) and `survey_hub` (SQL Server)
- **Connection Pooling**: SQLAlchemy connection pooling for efficient database access
- **Configuration-Driven**: Database types and connections configured via environment variables

**Configuration Example:**
```env
# PostgreSQL for queue and results
DEVELOPMENT_DISTRIBUTED_PROCESSOR_RPA_DB_TYPE=postgresql
DEVELOPMENT_DISTRIBUTED_PROCESSOR_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_db

# SQL Server for source data (read-only)
DEVELOPMENT_DISTRIBUTED_PROCESSOR_SURVEY_HUB_TYPE=sqlserver
DEVELOPMENT_DISTRIBUTED_PROCESSOR_SURVEY_HUB_CONNECTION_STRING=mssql+pyodbc://user:pass@survey-server:1433/survey_hub?driver=ODBC+Driver+17+for+SQL+Server
```

**Usage Pattern:**
```python
from core.database import DatabaseManager

# DatabaseManager automatically knows which database is which type
db = DatabaseManager("survey_processor")

# Read from SQL Server (survey_hub)
source_data = db.execute_query("survey_hub", "SELECT * FROM survey_responses WHERE processed = 0")

# Write to PostgreSQL (rpa_db) 
db.execute_query("rpa_db", "INSERT INTO processed_surveys (...) VALUES (...)", params)
```

### **2. Distributed Processor (`core/distributed.py`)**
```python
class DistributedProcessor:
    """Handles distributed processing with basic error handling."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    def claim_records_batch(self, flow_name: str, batch_size: int) -> List[Dict]:
        """Claim records with basic error handling."""
        try:
            query = """
                UPDATE processing_queue 
                SET status = 'processing', 
                    flow_instance_id = %s, 
                    claimed_at = NOW()
                WHERE id IN (
                    SELECT id FROM processing_queue 
                    WHERE flow_name = %s AND status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, payload, retry_count
            """
            
            # Generate unique instance ID to prevent hostname collisions
            hostname = os.getenv('HOSTNAME', 'unknown')
            instance_id = f"{hostname}-{uuid.uuid4().hex[:8]}"
            
            params = {
                'instance_id': instance_id,
                'flow_name': flow_name,
                'batch_size': batch_size
            }
            
            query = """
                UPDATE processing_queue 
                SET status = 'processing', 
                    flow_instance_id = :instance_id, 
                    claimed_at = NOW()
                WHERE id IN (
                    SELECT id FROM processing_queue 
                    WHERE flow_name = :flow_name AND status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT :batch_size
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING id, payload, retry_count
            """
            
            results = self.db.execute_query("rpa_db", query, params)
            
            return [{"id": r[0], "payload": r[1], "retry_count": r[2]} for r in results]
            
        except Exception as e:
            logger.error(f"Failed to claim records: {e}")
            return []  # Return empty list, flow will retry
    
    def mark_record_completed(self, record_id: int, result: Dict) -> None:
        """Mark record as completed."""
        logger = get_run_logger()
        try:
            query = """
                UPDATE processing_queue 
                SET status = 'completed', 
                    completed_at = NOW(),
                    payload = :result
                WHERE id = :record_id
            """
            params = {'result': json.dumps(result), 'record_id': record_id}
            self.db.execute_query("rpa_db", query, params)
        except Exception as e:
            logger.error(f"Failed to mark record completed: {e}")
    
    def mark_record_failed(self, record_id: int, error: str) -> None:
        """Mark record as failed with error message."""
        logger = get_run_logger()
        try:
            query = """
                UPDATE processing_queue 
                SET status = 'failed', 
                    error_message = :error,
                    retry_count = retry_count + 1
                WHERE id = :record_id
            """
            params = {'error': str(error), 'record_id': record_id}
            self.db.execute_query("rpa_db", query, params)
        except Exception as e:
            logger.error(f"Failed to mark record failed: {e}")
    
    def cleanup_orphaned_records(self) -> int:
        """Clean up orphaned records (processing for >1 hour)."""
        try:
            query = """
                UPDATE processing_queue 
                SET status = 'pending', 
                    flow_instance_id = NULL, 
                    claimed_at = NULL,
                    retry_count = retry_count + 1
                WHERE status = 'processing' 
                AND claimed_at < NOW() - INTERVAL '1 hour'
                RETURNING id
            """
            results = self.db.execute_query("rpa_db", query)
            logger.info(f"Cleaned up {len(results)} orphaned records")
            return len(results)
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned records: {e}")
            return 0
```

### **3. Flow Template (`core/flow_template.py`)**
```python
from datetime import datetime
from typing import Dict, List
from prefect import flow, task, get_run_logger, unmapped
import os
import json

# Initialize shared instances at module level to avoid object creation overhead
# Use unified DatabaseManager that handles multiple databases
from core.database import DatabaseManager

# DatabaseManager will handle both rpa_db (queue + results) and survey_hub (source data)
db_manager = DatabaseManager("distributed_processor")
processor = DistributedProcessor(db_manager)

@flow(name="distributed-survey-processing")
def distributed_processing_flow(flow_name: str, batch_size: int = 100):
    """Distributed survey processing flow with multi-database integration."""
    logger = get_run_logger()
    logger.info(f"Starting distributed survey processing for {flow_name}")
    
    try:
        # Claim records from PostgreSQL queue using shared processor instance
        records = processor.claim_records_batch(flow_name, batch_size)
        if not records:
            logger.info("No survey records to process")
            return {"message": "No survey records to process"}
        
        logger.info(f"Claimed {len(records)} survey records for processing")
        
        # Process each record (reads from survey_hub, writes to rpa_db)
        results = process_survey_record_with_status.map(records)
        
        # Generate summary
        completed = len([r for r in results if r.get('status') == 'completed'])
        failed = len([r for r in results if r.get('status') == 'failed'])
        
        summary = {
            "total": len(records),
            "completed": completed,
            "failed": failed,
            "flow_name": flow_name,
            "processed_at": datetime.now().isoformat(),
            "surveys_processed": completed
        }
        
        logger.info(f"Survey processing complete: {completed}/{len(records)} records completed")
        return summary
        
    except Exception as e:
        logger.error(f"Survey processing flow failed: {e}")
        raise
    finally:
        # Cleanup orphaned records
        processor.cleanup_orphaned_records()

@task(retries=2, retry_delay_seconds=30)  # Reduced retries since DB handles retry counting
def process_survey_record_with_status(record: Dict) -> Dict:
    """Process individual survey record using multi-database approach."""
    logger = get_run_logger()
    record_id = record['id']
    
    try:
        # Process the survey record (reads from survey_hub, writes to rpa_db)
        result = process_survey_logic(record['payload'])
        
        # Mark queue record as completed using shared processor instance
        processor.mark_record_completed(record_id, result)
        
        return {"record_id": record_id, "status": "completed", "result": result}
        
    except Exception as e:
        # Mark queue record as failed using shared processor instance
        processor.mark_record_failed(record_id, str(e))
        
        logger.error(f"Survey record {record_id} processing failed: {e}")
        return {"record_id": record_id, "status": "failed", "error": str(e)}
        # Note: Not re-raising to prevent Prefect retries conflicting with DB retry logic

def process_survey_logic(payload: Dict) -> Dict:
    """Process survey data from queue payload."""
    from core.database import DatabaseManager
    
    # Get survey data from SQL Server based on queue payload
    db = DatabaseManager("record_processor")
    
    # Read source data from survey_hub (SQL Server)
    survey_data = db.execute_query(
        "survey_hub",
        "SELECT survey_id, customer_id, response_data, submitted_at FROM survey_responses WHERE survey_id = :survey_id",
        {"survey_id": payload["survey_id"]}
    )
    
    if not survey_data:
        raise ValueError(f"Survey {payload['survey_id']} not found in survey_hub")
    
    survey = survey_data[0]
    
    # Process the survey data (business logic)
    response_data = json.loads(survey["response_data"])
    satisfaction_score = sum([int(response_data.get(f"q{i}", 0)) for i in range(1, 6)]) / 5
    
    processed_result = {
        "survey_id": survey["survey_id"],
        "customer_id": survey["customer_id"],
        "satisfaction_score": satisfaction_score,
        "submitted_at": survey["submitted_at"],
        "processed_at": datetime.now().isoformat()
    }
    
    # Save results to rpa_db (PostgreSQL)
    db.execute_query(
        "rpa_db",
        """INSERT INTO processed_surveys 
           (survey_id, customer_id, satisfaction_score, submitted_at, processed_at) 
           VALUES (:survey_id, :customer_id, :satisfaction_score, :submitted_at, :processed_at)""",
        processed_result
    )
    
    return processed_result
```

## 🚀 Processing Flow

### **1. Record Preparation**
```python
# Add records to the processing queue
def add_records_to_queue(flow_name: str, records: List[Dict]):
    """Add records to the processing queue."""
    from core.database import DatabaseManager
    db_manager = DatabaseManager("queue_manager")
    
    for record in records:
        query = """
            INSERT INTO processing_queue (flow_name, payload, status)
            VALUES (:flow_name, :payload, 'pending')
        """
        db_manager.execute_query("rpa_db", query, {
            "flow_name": flow_name, 
            "payload": json.dumps(record)
        })
```

### **2. Flow Execution**
```python
# Run the distributed flow
if __name__ == "__main__":
    # Add sample records
    sample_records = [
        {"survey_id": "SURV-001", "customer_id": "CUST-001"},
        {"survey_id": "SURV-002", "customer_id": "CUST-002"},
        {"survey_id": "SURV-003", "customer_id": "CUST-003"},
        # ... more survey records to process
    ]
    
    add_records_to_queue("survey_processor", sample_records)
    
    # Run the flow
    result = distributed_processing_flow("survey_processor", batch_size=50)
    print(f"Processing complete: {result}")
```

### **3. Container Deployment**
```yaml
# Simple Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: distributed-rpa-mvp
spec:
  replicas: 3  # Start with 3 containers
  template:
    spec:
      containers:
      - name: rpa-processor
        image: rpa-solution:mvp
        env:
        - name: PREFECT_ENVIRONMENT
          value: "production"
        - name: HOSTNAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: RPA_DB_URL
          valueFrom:
            secretKeyRef:
              name: rpa-db-secret
              key: connection-string
        - name: SURVEY_HUB_URL
          valueFrom:
            secretKeyRef:
              name: survey-hub-secret
              key: connection-string
```

## 📊 Basic Monitoring

### **Health Check Endpoint**
```python
@task
def basic_health_check() -> dict:
    """Simple health check for MVP using shared database manager."""
    logger = get_run_logger()
    try:
        # Use shared database manager instance
        # Check database connection
        db_healthy = True
        try:
            db_manager.execute_query("rpa_db", "SELECT 1")
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_healthy = False
        
        # Get queue depth
        queue_depth = 0
        if db_healthy:
            try:
                results = db_manager.execute_query(
                    "rpa_db",
                    "SELECT COUNT(*) FROM processing_queue WHERE status = 'pending'"
                )
                queue_depth = results[0][0] if results else 0
            except Exception as e:
                logger.error(f"Queue depth check failed: {e}")
                queue_depth = -1  # Indicate error
        
        return {
            "database_connected": db_healthy,
            "queue_depth": queue_depth,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "database_connected": False,
            "queue_depth": 0,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
```

### **Basic Metrics**
- **Queue Depth**: Number of pending records in processing_queue
- **Processing Rate**: Survey records processed per minute
- **Error Rate**: Percentage of failed survey processing
- **Database Health**: Connection status for both rpa_db and survey_hub
- **Data Flow**: Records read from survey_hub vs results written to rpa_db

## 🔒 Security Considerations

### **Database Security**
- Use connection pooling with limited connections
- Implement proper database user permissions
- Use environment variables for sensitive configuration
- Regular security updates for database dependencies

### **Container Security**
- Use non-root user in containers
- Implement resource limits
- Regular security scanning of container images
- Network policies for container communication

## 🚀 Deployment

### **Prerequisites**
- PostgreSQL database named `rpa_db` (contains both queue and flow tables)
- SQL Server database `survey_hub` (read-only data source)
- Kubernetes cluster (or Docker Compose for local testing)
- Prefect server running
- Container registry access

### **Deployment Steps**
1. **Database Setup**: Create `rpa_db` PostgreSQL database and run migrations
2. **Container Build**: Build and push container images
3. **Kubernetes Deployment**: Deploy with 2-3 replicas
4. **Configuration**: Set `RPA_DB_URL` and `SURVEY_HUB_URL` environment variables and secrets
5. **Testing**: Verify no duplicate processing occurs

### **Scaling**
- **Horizontal**: Add more container replicas
- **Vertical**: Increase container resources
- **Database**: Scale database resources as needed

## 📈 Performance Considerations

### **Database Optimization**
- Proper indexing on status and created_at columns
- **SQLAlchemy connection pooling** automatically handles connection reuse
- Regular VACUUM/OPTIMIZE operations
- Monitor query performance

### **Object Reuse Optimization**
- **Shared instances**: DatabaseManager and DistributedProcessor created once per container
- **Avoids object creation overhead**: No new instances per task execution
- **SQLAlchemy engine reuse**: Single engine instance with automatic connection pooling

### **Container Optimization**
- Resource limits and requests
- Health check intervals
- Graceful shutdown handling
- Log rotation and cleanup

## 🛠️ Maintenance

### **Regular Tasks**
- Monitor queue depth and processing rates
- Clean up old completed records
- Check for orphaned records
- Update container images
- Review error logs

### **Troubleshooting**
- **High Queue Depth**: Check container health, increase replicas
- **Database Errors**: Check connection limits, database health
- **Processing Failures**: Review error logs, check retry logic
- **Orphaned Records**: Run cleanup task, check container health

## 📋 Implementation Checklist

### **Phase 1: Core Setup (Week 1)**
- [ ] Database schema and migrations
- [ ] Basic `DatabaseManager` class
- [ ] `DistributedProcessor` with claiming logic
- [ ] Simple error handling and retry logic
- [ ] Basic unit tests

### **Phase 2: Integration (Week 2)**
- [ ] Update one existing flow (RPA1) to use distributed processing
- [ ] Integration tests with 2 containers
- [ ] Basic health check endpoint
- [ ] Simple cleanup task

### **Phase 3: Deployment (Week 3)**
- [ ] Container build and registry push
- [ ] Kubernetes deployment configuration
- [ ] Environment variable setup
- [ ] Basic monitoring and logging
- [ ] Documentation and runbooks

## 🎯 Success Metrics

### **Functional Requirements**
- ✅ **Zero Duplicate Processing**: No record processed more than once
- ✅ **Individual Record Handling**: Failed records don't affect others
- ✅ **Fault Tolerance**: Container failures don't cause data loss
- ✅ **Horizontal Scaling**: Adding containers increases throughput

### **Performance Targets**
- **Throughput**: 100+ records per minute per container
- **Latency**: <5 seconds average processing time
- **Availability**: 99.9% uptime
- **Error Rate**: <1% processing failures

### **Operational Requirements**
- **Deployment**: <10 minutes to deploy new version
- **Scaling**: <5 minutes to add/remove containers
- **Monitoring**: Real-time visibility into processing status
- **Recovery**: <30 minutes to recover from failures

## 📚 Next Steps

1. **Review and Approve**: Get stakeholder approval for MVP approach
2. **Environment Setup**: Set up development and staging environments
3. **Implementation**: Start with Phase 1 core components
4. **Testing**: Comprehensive testing with multiple containers
5. **Documentation**: Create operational runbooks and troubleshooting guides

---

**Note**: This is an MVP design focused on essential functionality. Advanced features like circuit breakers, distributed tracing, and complex monitoring can be added in future iterations once the core system is proven and stable.