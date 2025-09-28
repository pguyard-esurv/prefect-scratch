-- Migration V007: Add comprehensive performance indexes for processing_queue table
-- These indexes optimize the most common query patterns for distributed processing:
-- 1. Claiming pending records (status + created_at)
-- 2. Flow-specific queries (flow_name + status)
-- 3. Cleanup operations (flow_instance_id)
-- 4. Partial indexes for high-frequency status queries

-- Drop basic indexes from V006 that will be replaced by more comprehensive ones
DROP INDEX IF EXISTS idx_processing_queue_status;
DROP INDEX IF EXISTS idx_processing_queue_flow_name;

-- Composite index for efficient pending record queries (most critical for claiming)
-- This supports: WHERE status = 'pending' ORDER BY created_at
-- Used by claim_records_batch for FIFO processing
CREATE INDEX idx_processing_queue_status_created_at 
ON processing_queue(status, created_at);

-- Composite index for flow-specific queries
-- This supports: WHERE flow_name = ? AND status = ?
-- Used by get_queue_status and flow-specific monitoring
CREATE INDEX idx_processing_queue_flow_name_status 
ON processing_queue(flow_name, status);

-- Index on flow_instance_id for cleanup operations
-- This supports: WHERE flow_instance_id = ? (for cleanup and monitoring)
-- Used by cleanup_orphaned_records and instance-specific queries
CREATE INDEX idx_processing_queue_flow_instance_id 
ON processing_queue(flow_instance_id) 
WHERE flow_instance_id IS NOT NULL;

-- Partial index for pending records (most frequently queried)
-- This supports very fast queries for: WHERE status = 'pending'
-- Smaller index size since it only includes pending records
CREATE INDEX idx_processing_queue_pending 
ON processing_queue(created_at) 
WHERE status = 'pending';

-- Partial index for processing records (used for orphaned record detection)
-- This supports: WHERE status = 'processing' AND claimed_at < ?
-- Used by cleanup_orphaned_records to find stuck records
CREATE INDEX idx_processing_queue_processing_claimed_at 
ON processing_queue(claimed_at) 
WHERE status = 'processing';

-- Index for retry count queries (used for failed record management)
-- This supports: WHERE status = 'failed' AND retry_count < ?
-- Used by reset_failed_records for retry logic
CREATE INDEX idx_processing_queue_failed_retry 
ON processing_queue(retry_count, created_at) 
WHERE status = 'failed';

-- Composite index for time-based cleanup queries
-- This supports: WHERE completed_at < ? OR (status = 'failed' AND created_at < ?)
-- Used for archiving old records and maintenance operations
CREATE INDEX idx_processing_queue_cleanup_timestamps 
ON processing_queue(completed_at, created_at, status);

-- Index for monitoring and reporting queries
-- This supports efficient GROUP BY flow_name, status queries
-- Used by get_queue_status for dashboard and monitoring
CREATE INDEX idx_processing_queue_monitoring 
ON processing_queue(flow_name, status, created_at);

-- Add comments to document index purposes
COMMENT ON INDEX idx_processing_queue_status_created_at IS 
'Composite index for efficient FIFO record claiming queries';

COMMENT ON INDEX idx_processing_queue_flow_name_status IS 
'Composite index for flow-specific status queries and monitoring';

COMMENT ON INDEX idx_processing_queue_flow_instance_id IS 
'Index for cleanup operations and instance-specific queries';

COMMENT ON INDEX idx_processing_queue_pending IS 
'Partial index for fast pending record queries (most common)';

COMMENT ON INDEX idx_processing_queue_processing_claimed_at IS 
'Partial index for orphaned record detection and cleanup';

COMMENT ON INDEX idx_processing_queue_failed_retry IS 
'Index for failed record retry logic and management';

COMMENT ON INDEX idx_processing_queue_cleanup_timestamps IS 
'Composite index for time-based cleanup and archival operations';

COMMENT ON INDEX idx_processing_queue_monitoring IS 
'Index optimized for monitoring and reporting queries';

-- Analyze table to update statistics after index creation
ANALYZE processing_queue;