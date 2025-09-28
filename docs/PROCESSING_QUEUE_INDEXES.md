# Processing Queue Performance Indexes

This document describes the performance indexes created for the `processing_queue` table in the distributed processing system.

## Overview

The V007 migration (`V007__Add_processing_indexes.sql`) creates comprehensive indexes to optimize the most common query patterns in the distributed processing system. These indexes are designed to support high-throughput, concurrent access from multiple container instances.

## Index Descriptions

### Primary Indexes

#### `idx_processing_queue_status_created_at`

- **Columns**: `(status, created_at)`
- **Purpose**: Optimizes the critical record claiming query for FIFO processing
- **Query Pattern**: `WHERE status = 'pending' ORDER BY created_at ASC`
- **Usage**: Used by `claim_records_batch()` for atomic record claiming

#### `idx_processing_queue_flow_name_status`

- **Columns**: `(flow_name, status)`
- **Purpose**: Optimizes flow-specific status queries and monitoring
- **Query Pattern**: `WHERE flow_name = ? AND status = ?`
- **Usage**: Used by `get_queue_status()` and monitoring dashboards

#### `idx_processing_queue_flow_instance_id`

- **Columns**: `(flow_instance_id)` WHERE `flow_instance_id IS NOT NULL`
- **Purpose**: Optimizes cleanup operations and instance-specific queries
- **Query Pattern**: `WHERE flow_instance_id = ?`
- **Usage**: Used by cleanup operations and container monitoring

### Partial Indexes (Status-Specific)

#### `idx_processing_queue_pending`

- **Columns**: `(created_at)` WHERE `status = 'pending'`
- **Purpose**: Ultra-fast queries for pending records (most frequent)
- **Query Pattern**: `WHERE status = 'pending'`
- **Usage**: High-frequency pending record queries

#### `idx_processing_queue_processing_claimed_at`

- **Columns**: `(claimed_at)` WHERE `status = 'processing'`
- **Purpose**: Optimizes orphaned record detection
- **Query Pattern**: `WHERE status = 'processing' AND claimed_at < ?`
- **Usage**: Used by `cleanup_orphaned_records()`

#### `idx_processing_queue_failed_retry`

- **Columns**: `(retry_count, created_at)` WHERE `status = 'failed'`
- **Purpose**: Optimizes failed record retry logic
- **Query Pattern**: `WHERE status = 'failed' AND retry_count < ?`
- **Usage**: Used by `reset_failed_records()`

### Specialized Indexes

#### `idx_processing_queue_cleanup_timestamps`

- **Columns**: `(completed_at, created_at, status)`
- **Purpose**: Optimizes time-based cleanup and archival operations
- **Query Pattern**: `WHERE completed_at < ? OR (status = 'failed' AND created_at < ?)`
- **Usage**: Used for maintenance and archival operations

#### `idx_processing_queue_monitoring`

- **Columns**: `(flow_name, status, created_at)`
- **Purpose**: Optimizes monitoring and reporting queries
- **Query Pattern**: `GROUP BY flow_name, status`
- **Usage**: Used by monitoring dashboards and reporting

## Query Performance Optimization

### Record Claiming (Most Critical)

```sql
-- Optimized by: idx_processing_queue_status_created_at, idx_processing_queue_pending
UPDATE processing_queue
SET status = 'processing', flow_instance_id = ?, claimed_at = NOW()
WHERE id IN (
    SELECT id FROM processing_queue
    WHERE flow_name = ? AND status = 'pending'
    ORDER BY created_at ASC
    LIMIT ?
    FOR UPDATE SKIP LOCKED
)
RETURNING id, payload, retry_count, created_at;
```

### Flow Status Monitoring

```sql
-- Optimized by: idx_processing_queue_flow_name_status
SELECT status, COUNT(*) as count
FROM processing_queue
WHERE flow_name = ?
GROUP BY status;
```

### Orphaned Record Cleanup

```sql
-- Optimized by: idx_processing_queue_processing_claimed_at
SELECT id, flow_instance_id
FROM processing_queue
WHERE status = 'processing'
AND claimed_at < NOW() - INTERVAL '1 hour';
```

### Failed Record Retry

```sql
-- Optimized by: idx_processing_queue_failed_retry
SELECT id FROM processing_queue
WHERE status = 'failed'
AND retry_count < 3
ORDER BY created_at ASC;
```

## Index Maintenance

### Automatic Maintenance

- PostgreSQL automatically maintains index statistics
- The migration includes `ANALYZE processing_queue` to update statistics
- Partial indexes are automatically smaller and more efficient

### Manual Maintenance (if needed)

```sql
-- Reindex if performance degrades
REINDEX INDEX idx_processing_queue_status_created_at;

-- Update statistics manually
ANALYZE processing_queue;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'processing_queue';
```

## Performance Characteristics

### Expected Performance

- **Record claiming**: < 50ms for batches up to 100 records
- **Status queries**: < 10ms for flow-specific status counts
- **Cleanup operations**: < 100ms for orphaned record detection
- **Monitoring queries**: < 50ms for dashboard data

### Scaling Characteristics

- Indexes scale logarithmically with table size
- Partial indexes remain small even with large tables
- Composite indexes support multiple query patterns efficiently

## Troubleshooting

### Slow Queries

1. Check if the query is using the expected index:

   ```sql
   EXPLAIN (ANALYZE, BUFFERS) SELECT ...;
   ```

2. Verify index statistics are up to date:

   ```sql
   SELECT last_analyze FROM pg_stat_user_tables WHERE relname = 'processing_queue';
   ```

3. Check for index bloat:
   ```sql
   SELECT indexname, pg_size_pretty(pg_relation_size(indexname::regclass))
   FROM pg_indexes WHERE tablename = 'processing_queue';
   ```

### High Index Maintenance Overhead

- Monitor index write performance during high-volume inserts
- Consider adjusting batch sizes if index maintenance becomes a bottleneck
- Partial indexes reduce maintenance overhead for status-specific queries

## Migration Notes

### Backward Compatibility

- The migration drops old basic indexes (`idx_processing_queue_status`, `idx_processing_queue_flow_name`)
- New composite indexes provide better performance for the same queries
- No application code changes required

### Rollback Strategy

If rollback is needed:

```sql
-- Drop new indexes
DROP INDEX idx_processing_queue_status_created_at;
DROP INDEX idx_processing_queue_flow_name_status;
-- ... (drop all V007 indexes)

-- Recreate basic indexes
CREATE INDEX idx_processing_queue_status ON processing_queue(status);
CREATE INDEX idx_processing_queue_flow_name ON processing_queue(flow_name);
```

## Testing

The indexes are tested in:

- `core/test/test_processing_indexes_performance.py` - Performance testing with mocked queries
- `core/test/test_processing_indexes_migration.py` - Migration validation and syntax testing

Run tests with:

```bash
python -m pytest core/test/test_processing_indexes_*.py -v
```
