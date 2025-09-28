-- Migration V003: Create processed_surveys table for RPA workflow data
-- This table stores survey processing results from RPA flows

CREATE TABLE IF NOT EXISTS processed_surveys (
    id SERIAL PRIMARY KEY,
    survey_id VARCHAR(50) NOT NULL,
    customer_id VARCHAR(50) NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    survey_type VARCHAR(100) NOT NULL,
    processing_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    processed_at TIMESTAMP,
    processing_duration_ms INTEGER,
    flow_run_id VARCHAR(255),
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_processed_surveys_survey_id ON processed_surveys(survey_id);
CREATE INDEX IF NOT EXISTS idx_processed_surveys_customer_id ON processed_surveys(customer_id);
CREATE INDEX IF NOT EXISTS idx_processed_surveys_status ON processed_surveys(processing_status);
CREATE INDEX IF NOT EXISTS idx_processed_surveys_processed_at ON processed_surveys(processed_at);
CREATE INDEX IF NOT EXISTS idx_processed_surveys_flow_run_id ON processed_surveys(flow_run_id);

-- Insert sample data for testing
INSERT INTO processed_surveys (survey_id, customer_id, customer_name, survey_type, processing_status, processed_at, processing_duration_ms, flow_run_id) VALUES
('SURV-001', 'CUST-001', 'Alice Johnson', 'Customer Satisfaction', 'completed', NOW() - INTERVAL '1 day', 1250, 'flow-run-001'),
('SURV-002', 'CUST-002', 'Bob Smith', 'Product Feedback', 'completed', NOW() - INTERVAL '2 hours', 980, 'flow-run-002'),
('SURV-003', 'CUST-003', 'Charlie Brown', 'Market Research', 'pending', NULL, NULL, 'flow-run-003'),
('SURV-004', 'CUST-004', 'Diana Prince', 'Customer Satisfaction', 'failed', NOW() - INTERVAL '30 minutes', 2100, 'flow-run-004'),
('SURV-005', 'CUST-005', 'Eve Wilson', 'Product Feedback', 'completed', NOW() - INTERVAL '1 hour', 1450, 'flow-run-005');