-- Migration V006: Create processing_queue table for distributed processing system
-- This table manages the queue of records to be processed by multiple container instances
-- Prevents duplicate processing using database-level locking with FOR UPDATE SKIP LOCKED

CREATE TABLE IF NOT EXISTS processing_queue (
    id SERIAL PRIMARY KEY,
    flow_name VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    flow_instance_id VARCHAR(100),
    claimed_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to update updated_at timestamp on every update
CREATE TRIGGER update_processing_queue_updated_at
    BEFORE UPDATE ON processing_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create basic indexes for performance (more comprehensive indexes in V007)
CREATE INDEX IF NOT EXISTS idx_processing_queue_status ON processing_queue(status);
CREATE INDEX IF NOT EXISTS idx_processing_queue_flow_name ON processing_queue(flow_name);
CREATE INDEX IF NOT EXISTS idx_processing_queue_created_at ON processing_queue(created_at);

-- Insert sample data for testing and development
INSERT INTO processing_queue (flow_name, payload, status) VALUES
('survey_processor', '{"survey_id": 1001, "customer_id": "CUST001", "priority": "high"}', 'pending'),
('survey_processor', '{"survey_id": 1002, "customer_id": "CUST002", "priority": "normal"}', 'pending'),
('order_processor', '{"order_id": 2001, "customer_id": "CUST001", "amount": 150.00}', 'pending'),
('order_processor', '{"order_id": 2002, "customer_id": "CUST003", "amount": 75.50}', 'completed'),
('data_validation', '{"batch_id": 3001, "record_count": 500, "validation_rules": ["email", "phone"]}', 'failed');

-- Update sample data to show different statuses and timestamps
UPDATE processing_queue 
SET status = 'completed', 
    completed_at = CURRENT_TIMESTAMP - INTERVAL '1 hour',
    flow_instance_id = 'container-1-abc123'
WHERE flow_name = 'order_processor' AND payload->>'order_id' = '2002';

UPDATE processing_queue 
SET status = 'failed', 
    error_message = 'Validation rule "email" failed: invalid format',
    retry_count = 1,
    flow_instance_id = 'container-2-def456'
WHERE flow_name = 'data_validation';