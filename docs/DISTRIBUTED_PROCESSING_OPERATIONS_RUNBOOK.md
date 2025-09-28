# Distributed Processing System - Operations Runbook

## Overview

This runbook provides comprehensive operational guidance for managing and troubleshooting the distributed processing system. It includes monitoring procedures, maintenance tasks, troubleshooting guides, and emergency response procedures.

## Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Monitoring and Health Checks](#monitoring-and-health-checks)
3. [Routine Maintenance](#routine-maintenance)
4. [Troubleshooting Guide](#troubleshooting-guide)
5. [Performance Optimization](#performance-optimization)
6. [Emergency Procedures](#emergency-procedures)
7. [Alerting and Escalation](#alerting-and-escalation)
8. [Capacity Planning](#capacity-planning)

## System Architecture Overview

### Components

- **Processing Queue**: PostgreSQL table storing records to be processed
- **DistributedProcessor**: Core class handling atomic record claiming and status management
- **DatabaseManager**: Unified database access layer with connection pooling
- **Flow Template**: Standardized Prefect flow pattern for distributed processing
- **Container Instances**: Multiple containers running the same flow concurrently

### Key Tables

- `processing_queue`: Main queue table with records and status tracking
- `schema_version`: Migration tracking table
- `processed_surveys`: Example results table
- `flow_execution_logs`: Execution history and metrics

## Monitoring and Health Checks

### Daily Health Check Routine

```python
# Run comprehensive health monitoring
from core.monitoring import (
    distributed_queue_monitoring,
    distributed_processing_diagnostics,
    processing_performance_monitoring
)

# 1. Check overall queue health
queue_status = distributed_queue_monitoring()
print(f"Queue Health: {queue_status['queue_health_assessment']['queue_health']}")

# 2. Run system diagnostics
diagnostics = distributed_processing_diagnostics()
print(f"Issues Found: {len(diagnostics['issues_found'])}")

# 3. Check performance metrics
performance = processing_performance_monitoring(time_window_hours=24)
print(f"Success Rate: {performance['overall_metrics']['success_rate_percent']}%")
```

### Key Metrics to Monitor

#### Queue Metrics

- **Total Records**: Overall queue depth
- **Pending Records**: Records waiting for processing
- **Processing Records**: Records currently being processed
- **Failed Records**: Records that failed processing
- **Success Rate**: Percentage of successfully processed records

#### Performance Metrics

- **Processing Rate**: Records processed per hour
- **Average Processing Time**: Time to process individual records
- **Error Rate**: Percentage of failed processing attempts
- **Queue Throughput**: Records entering vs. leaving the queue

#### System Health Metrics

- **Database Connectivity**: Connection success rate
- **Response Time**: Database query response times
- **Connection Pool Utilization**: Pool usage percentage
- **Orphaned Records**: Records stuck in processing state

### Monitoring Thresholds

| Metric           | Warning   | Critical  | Action                     |
| ---------------- | --------- | --------- | -------------------------- |
| Success Rate     | < 90%     | < 80%     | Investigate failures       |
| Processing Rate  | < 50/hour | < 10/hour | Scale up capacity          |
| Failed Records   | > 100     | > 500     | Emergency investigation    |
| Orphaned Records | > 10      | > 50      | Run cleanup                |
| Response Time    | > 1000ms  | > 5000ms  | Check database performance |
| Pool Utilization | > 80%     | > 95%     | Increase pool size         |

## Routine Maintenance

### Daily Maintenance Tasks

#### 1. Orphaned Record Cleanup

```python
from core.monitoring import distributed_system_maintenance

# Clean up records stuck in processing for > 2 hours
maintenance_result = distributed_system_maintenance(
    cleanup_orphaned_records=True,
    orphaned_timeout_hours=2,
    dry_run=False
)

print(f"Cleaned up {maintenance_result['cleanup_results']['records_cleaned']} orphaned records")
```

**Schedule**: Every 4 hours via cron job
**Purpose**: Prevent records from being permanently stuck in processing state

#### 2. Queue Health Assessment

```python
from core.monitoring import distributed_queue_monitoring

# Monitor queue health and generate alerts
queue_status = distributed_queue_monitoring(include_detailed_metrics=True)

# Check for alerts
alerts = queue_status['operational_alerts']
if alerts:
    print("ALERTS DETECTED:")
    for alert in alerts:
        print(f"  - {alert}")
```

**Schedule**: Every 15 minutes
**Purpose**: Early detection of queue issues and performance problems

#### 3. Performance Trend Analysis

```python
from core.monitoring import processing_performance_monitoring

# Analyze performance over last 24 hours
performance = processing_performance_monitoring(
    time_window_hours=24,
    include_error_analysis=True
)

# Review recommendations
for rec in performance['recommendations']:
    print(f"RECOMMENDATION: {rec}")
```

**Schedule**: Daily at 6 AM
**Purpose**: Identify performance trends and optimization opportunities

### Weekly Maintenance Tasks

#### 1. Failed Record Analysis and Reset

```python
# Analyze failed records before resetting
diagnostics = distributed_processing_diagnostics(
    include_orphaned_analysis=True,
    include_performance_analysis=True
)

# Reset failed records with retry count < 3
maintenance_result = distributed_system_maintenance(
    reset_failed_records=True,
    max_retries=3,
    dry_run=False
)
```

**Schedule**: Weekly on Sunday at 2 AM
**Purpose**: Give failed records another chance while preventing infinite retries

#### 2. Database Performance Review

```python
from core.tasks import database_health_check, connection_pool_monitoring

# Check database health
health = database_health_check("rpa_db", include_retry=True)
pool_status = connection_pool_monitoring("rpa_db")

print(f"Database Health: {health['status']}")
print(f"Pool Utilization: {pool_status['utilization_percent']}%")
```

**Schedule**: Weekly on Monday at 8 AM
**Purpose**: Ensure database performance remains optimal

### Monthly Maintenance Tasks

#### 1. Historical Data Cleanup

```sql
-- Clean up old completed records (older than 30 days)
DELETE FROM processing_queue
WHERE status = 'completed'
AND completed_at < NOW() - INTERVAL '30 days';

-- Clean up old failed records (older than 7 days, retry_count >= 5)
DELETE FROM processing_queue
WHERE status = 'failed'
AND updated_at < NOW() - INTERVAL '7 days'
AND retry_count >= 5;
```

**Schedule**: First Sunday of each month at 3 AM
**Purpose**: Prevent queue table from growing indefinitely

#### 2. Performance Baseline Review

- Review monthly performance trends
- Update alerting thresholds based on observed patterns
- Assess capacity planning needs
- Document any configuration changes

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: High Number of Failed Records

**Symptoms:**

- Failed record count > 100
- Success rate < 80%
- Increasing error alerts

**Diagnosis:**

```python
# Analyze error patterns
from core.monitoring import processing_performance_monitoring

performance = processing_performance_monitoring(
    time_window_hours=24,
    include_error_analysis=True
)

# Review top errors
for error in performance['error_analysis']['top_errors']:
    print(f"Error: {error['error_message']} (Count: {error['error_count']})")
```

**Solutions:**

1. **Data Quality Issues**: Fix upstream data validation
2. **Business Logic Errors**: Update processing logic to handle edge cases
3. **External Service Failures**: Implement better retry logic and circuit breakers
4. **Database Connectivity**: Check database health and connection pool settings

#### Issue: Records Stuck in Processing State

**Symptoms:**

- Processing record count > 50
- Records with old claimed_at timestamps
- No progress in queue processing

**Diagnosis:**

```python
# Check for orphaned records
from core.monitoring import distributed_processing_diagnostics

diagnostics = distributed_processing_diagnostics(
    include_orphaned_analysis=True
)

orphaned_count = diagnostics['orphaned_records_analysis']['total_orphaned_records']
print(f"Orphaned records found: {orphaned_count}")
```

**Solutions:**

1. **Container Crashes**: Check container logs and restart failed containers
2. **Long-Running Processes**: Optimize business logic or increase timeout
3. **Database Locks**: Check for database deadlocks or long-running transactions
4. **Run Cleanup**: Execute orphaned record cleanup maintenance

#### Issue: Low Processing Throughput

**Symptoms:**

- Processing rate < 50 records/hour
- Large pending record backlog
- High average processing time

**Diagnosis:**

```python
# Analyze performance metrics
performance = processing_performance_monitoring(time_window_hours=6)

print(f"Processing Rate: {performance['overall_metrics']['avg_processing_rate_per_hour']} records/hour")
print(f"Avg Processing Time: {performance['overall_metrics']['avg_processing_time_minutes']} minutes")
```

**Solutions:**

1. **Scale Up**: Increase number of container instances
2. **Optimize Logic**: Profile and optimize business logic code
3. **Increase Batch Size**: Adjust batch_size parameter for better throughput
4. **Database Performance**: Optimize database queries and indexes

#### Issue: Database Connection Problems

**Symptoms:**

- Connection failures in health checks
- High database response times
- Pool utilization > 90%

**Diagnosis:**

```python
from core.tasks import database_health_check, connection_pool_monitoring

health = database_health_check("rpa_db")
pool_status = connection_pool_monitoring("rpa_db")

print(f"Connection Status: {health['connection']}")
print(f"Response Time: {health['response_time_ms']}ms")
print(f"Pool Utilization: {pool_status['utilization_percent']}%")
```

**Solutions:**

1. **Increase Pool Size**: Adjust `pool_size` and `max_overflow` settings
2. **Database Tuning**: Optimize database configuration and queries
3. **Network Issues**: Check network connectivity and firewall settings
4. **Resource Limits**: Increase database server resources

### Diagnostic Commands

#### Quick Health Check

```bash
# Run basic health check
python -c "
from core.monitoring import distributed_queue_monitoring
result = distributed_queue_monitoring()
print(f'Queue Health: {result[\"queue_health_assessment\"][\"queue_health\"]}')
print(f'Total Records: {result[\"overall_queue_status\"][\"total_records\"]}')
print(f'Failed Records: {result[\"overall_queue_status\"][\"failed_records\"]}')
"
```

#### Detailed Diagnostics

```bash
# Run comprehensive diagnostics
python -c "
from core.monitoring import distributed_processing_diagnostics
result = distributed_processing_diagnostics()
print(f'Issues Found: {len(result[\"issues_found\"])}')
for issue in result['issues_found']:
    print(f'  - {issue}')
"
```

#### Performance Analysis

```bash
# Check recent performance
python -c "
from core.monitoring import processing_performance_monitoring
result = processing_performance_monitoring(time_window_hours=6)
print(f'Success Rate: {result[\"overall_metrics\"][\"success_rate_percent\"]}%')
print(f'Processing Rate: {result[\"overall_metrics\"][\"avg_processing_rate_per_hour\"]} records/hour')
"
```

## Performance Optimization

### Tuning Parameters

#### Batch Size Optimization

- **Small Batches (10-25)**: Better for low-latency, high-frequency processing
- **Medium Batches (50-100)**: Balanced approach for most workloads
- **Large Batches (200+)**: Better for high-throughput, batch-oriented processing

#### Connection Pool Settings

```python
# Recommended settings based on container count
containers = 3
pool_size = max(5, containers * 2)  # 2 connections per container minimum
max_overflow = pool_size * 2        # Allow 2x overflow for spikes

# Example configuration
DEVELOPMENT_GLOBAL_RPA_DB_POOL_SIZE=10
DEVELOPMENT_GLOBAL_RPA_DB_MAX_OVERFLOW=20
```

#### Processing Timeouts

```python
# Recommended timeout settings
DEVELOPMENT_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS=2  # Orphaned record cleanup
DEVELOPMENT_DISTRIBUTED_PROCESSOR_MAX_RETRIES=3            # Maximum retry attempts
```

### Performance Monitoring Queries

#### Queue Performance Analysis

```sql
-- Processing rate by hour (last 24 hours)
SELECT
    DATE_TRUNC('hour', claimed_at) as hour,
    COUNT(*) as records_processed,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
    ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - claimed_at))/60), 2) as avg_minutes
FROM processing_queue
WHERE claimed_at >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('hour', claimed_at)
ORDER BY hour DESC;
```

#### Error Pattern Analysis

```sql
-- Top error messages (last 7 days)
SELECT
    error_message,
    COUNT(*) as error_count,
    COUNT(DISTINCT flow_name) as affected_flows
FROM processing_queue
WHERE status = 'failed'
AND updated_at >= NOW() - INTERVAL '7 days'
AND error_message IS NOT NULL
GROUP BY error_message
ORDER BY error_count DESC
LIMIT 10;
```

#### Flow Performance Comparison

```sql
-- Performance by flow (last 24 hours)
SELECT
    flow_name,
    COUNT(*) as total_processed,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
    ROUND((COUNT(CASE WHEN status = 'completed' THEN 1 END) * 100.0 / COUNT(*)), 2) as success_rate,
    ROUND(AVG(EXTRACT(EPOCH FROM (completed_at - claimed_at))/60), 2) as avg_processing_minutes
FROM processing_queue
WHERE claimed_at >= NOW() - INTERVAL '24 hours'
GROUP BY flow_name
ORDER BY total_processed DESC;
```

## Emergency Procedures

### Critical System Failure

#### Symptoms

- All processing stopped
- Database connectivity lost
- Multiple container failures

#### Immediate Actions

1. **Stop New Record Ingestion**

   ```python
   # Temporarily disable flows that add records to queue
   # Check container orchestration system (Kubernetes/Docker)
   ```

2. **Assess System Health**

   ```python
   from core.tasks import database_health_check
   health = database_health_check("rpa_db")
   print(f"Database Status: {health['status']}")
   ```

3. **Check Container Status**

   ```bash
   # Kubernetes
   kubectl get pods -l app=rpa-processor
   kubectl logs -l app=rpa-processor --tail=100

   # Docker
   docker ps --filter "name=rpa"
   docker logs rpa-container --tail=100
   ```

#### Recovery Steps

1. **Database Recovery**: Restore database connectivity
2. **Container Restart**: Restart failed containers
3. **Queue Validation**: Verify queue integrity
4. **Gradual Restart**: Resume processing with reduced capacity
5. **Monitor Recovery**: Watch metrics closely during recovery

### Data Corruption Detection

#### Symptoms

- Unexpected record status changes
- Missing records
- Duplicate processing

#### Investigation

```sql
-- Check for data integrity issues
SELECT
    status,
    COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(updated_at) as newest
FROM processing_queue
GROUP BY status;

-- Look for suspicious patterns
SELECT
    flow_instance_id,
    COUNT(*) as records_claimed,
    MIN(claimed_at) as first_claim,
    MAX(claimed_at) as last_claim
FROM processing_queue
WHERE status = 'processing'
GROUP BY flow_instance_id
ORDER BY records_claimed DESC;
```

#### Recovery Actions

1. **Stop Processing**: Halt all containers immediately
2. **Backup Current State**: Create database backup
3. **Analyze Corruption**: Identify scope and cause
4. **Data Recovery**: Restore from backup if necessary
5. **Fix Root Cause**: Address underlying issue
6. **Gradual Restart**: Resume with enhanced monitoring

### Performance Degradation

#### Symptoms

- Processing rate drops significantly
- High error rates
- Increased response times

#### Immediate Actions

1. **Scale Up**: Increase container instances temporarily
2. **Reduce Load**: Decrease batch sizes
3. **Monitor Resources**: Check CPU, memory, database performance
4. **Identify Bottleneck**: Use performance monitoring tools

## Alerting and Escalation

### Alert Levels

#### Level 1: Warning

- Success rate 80-90%
- Processing rate 10-50 records/hour
- Failed records 50-100
- Response time 1-5 seconds

**Action**: Monitor closely, investigate if persists > 30 minutes

#### Level 2: Critical

- Success rate < 80%
- Processing rate < 10 records/hour
- Failed records > 100
- Response time > 5 seconds

**Action**: Immediate investigation required, escalate if not resolved in 15 minutes

#### Level 3: Emergency

- System completely down
- Database connectivity lost
- Data corruption detected
- All containers failed

**Action**: Immediate escalation, emergency response procedures

### Escalation Contacts

1. **Primary On-Call**: Development team lead
2. **Secondary On-Call**: Senior developer
3. **Database Administrator**: For database-related issues
4. **Infrastructure Team**: For container/network issues
5. **Management**: For business impact assessment

### Alert Configuration

```python
# Example alerting thresholds
ALERT_THRESHOLDS = {
    "success_rate_warning": 90,
    "success_rate_critical": 80,
    "processing_rate_warning": 50,
    "processing_rate_critical": 10,
    "failed_records_warning": 50,
    "failed_records_critical": 100,
    "response_time_warning": 1000,
    "response_time_critical": 5000,
    "orphaned_records_warning": 10,
    "orphaned_records_critical": 50
}
```

## Capacity Planning

### Scaling Guidelines

#### Horizontal Scaling (More Containers)

- **Trigger**: Pending records > 500 for > 30 minutes
- **Formula**: `containers = ceil(pending_records / (batch_size * target_processing_rate))`
- **Maximum**: Limited by database connection pool capacity

#### Vertical Scaling (Larger Containers)

- **Trigger**: High CPU/memory usage (> 80%)
- **Considerations**: Business logic complexity, memory requirements
- **Testing**: Validate performance improvement before production

#### Database Scaling

- **Connection Pool**: Increase when utilization > 80%
- **Database Resources**: Scale when response time > 1 second consistently
- **Read Replicas**: Consider for read-heavy monitoring queries

### Capacity Monitoring

```python
# Calculate current capacity utilization
def calculate_capacity_utilization():
    from core.monitoring import distributed_queue_monitoring

    status = distributed_queue_monitoring()

    pending = status['overall_queue_status']['pending_records']
    processing = status['overall_queue_status']['processing_records']

    # Assume 3 containers, batch size 100, 1 batch per 5 minutes
    theoretical_capacity = 3 * 100 * (60 / 5)  # 3600 records/hour

    current_load = pending + processing
    utilization = (current_load / theoretical_capacity) * 100

    return {
        'current_load': current_load,
        'theoretical_capacity': theoretical_capacity,
        'utilization_percent': utilization
    }
```

### Growth Planning

#### Monthly Review

- Analyze processing volume trends
- Review average processing times
- Assess error rate patterns
- Plan capacity adjustments

#### Quarterly Planning

- Evaluate infrastructure costs
- Plan major optimizations
- Review disaster recovery procedures
- Update operational procedures

---

## Quick Reference

### Emergency Commands

```bash
# Stop all processing
kubectl scale deployment rpa-processor --replicas=0

# Emergency cleanup
python -c "from core.monitoring import distributed_system_maintenance; distributed_system_maintenance(cleanup_orphaned_records=True, dry_run=False)"

# Health check
python -c "from core.monitoring import distributed_queue_monitoring; print(distributed_queue_monitoring()['queue_health_assessment']['queue_health'])"
```

### Key Metrics Dashboard

- Queue depth (pending/processing/failed)
- Success rate (last 1h/24h)
- Processing rate (records/hour)
- Error rate and top errors
- Database response time
- Container health status

### Maintenance Schedule

- **Every 15 minutes**: Queue health monitoring
- **Every 4 hours**: Orphaned record cleanup
- **Daily**: Performance analysis and trending
- **Weekly**: Failed record analysis and reset
- **Monthly**: Historical data cleanup and capacity review

---

_This runbook should be reviewed and updated quarterly to reflect operational experience and system changes._
