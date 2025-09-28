-- Migration V005: Create flow_execution_logs table for monitoring RPA flow executions
-- This table tracks flow execution metrics and health monitoring data

CREATE TABLE IF NOT EXISTS flow_execution_logs (
    id SERIAL PRIMARY KEY,
    flow_name VARCHAR(100) NOT NULL,
    flow_run_id VARCHAR(255) NOT NULL,
    database_name VARCHAR(100) NOT NULL,
    execution_start TIMESTAMP NOT NULL,
    execution_end TIMESTAMP,
    execution_duration_ms INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'running',
    records_processed INTEGER DEFAULT 0,
    records_successful INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    database_operations INTEGER DEFAULT 0,
    health_check_status VARCHAR(50),
    health_check_response_time_ms DECIMAL(10, 2),
    error_message TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for monitoring and reporting queries
CREATE INDEX IF NOT EXISTS idx_flow_logs_flow_name ON flow_execution_logs(flow_name);
CREATE INDEX IF NOT EXISTS idx_flow_logs_flow_run_id ON flow_execution_logs(flow_run_id);
CREATE INDEX IF NOT EXISTS idx_flow_logs_database_name ON flow_execution_logs(database_name);
CREATE INDEX IF NOT EXISTS idx_flow_logs_execution_start ON flow_execution_logs(execution_start);
CREATE INDEX IF NOT EXISTS idx_flow_logs_status ON flow_execution_logs(status);
CREATE INDEX IF NOT EXISTS idx_flow_logs_health_status ON flow_execution_logs(health_check_status);

-- Create composite indexes for performance monitoring
CREATE INDEX IF NOT EXISTS idx_flow_logs_name_start ON flow_execution_logs(flow_name, execution_start);
CREATE INDEX IF NOT EXISTS idx_flow_logs_db_status ON flow_execution_logs(database_name, status);

-- Insert sample execution log data
INSERT INTO flow_execution_logs (
    flow_name, flow_run_id, database_name, execution_start, execution_end, 
    execution_duration_ms, status, records_processed, records_successful, 
    records_failed, database_operations, health_check_status, 
    health_check_response_time_ms, metadata
) VALUES
('rpa1-file-processing', 'flow-run-001', 'rpa_db', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours' + INTERVAL '45 seconds', 45000, 'completed', 150, 148, 2, 25, 'healthy', 23.5, '{"batch_size": 1000, "environment": "development"}'),
('rpa2-validation', 'flow-run-002', 'rpa_db', NOW() - INTERVAL '1 hour', NOW() - INTERVAL '1 hour' + INTERVAL '12 seconds', 12000, 'completed', 75, 70, 5, 8, 'healthy', 18.2, '{"validation_strict": true, "max_retries": 3}'),
('rpa3-concurrent-processing', 'flow-run-003', 'rpa_db', NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '30 minutes' + INTERVAL '28 seconds', 28000, 'completed', 8, 8, 0, 32, 'healthy', 15.7, '{"max_concurrent_tasks": 10, "timeout": 60}'),
('rpa1-file-processing', 'flow-run-004', 'SurveyHub', NOW() - INTERVAL '15 minutes', NOW() - INTERVAL '15 minutes' + INTERVAL '52 seconds', 52000, 'completed', 200, 195, 5, 18, 'degraded', 78.3, '{"batch_size": 500, "environment": "development"}'),
('rpa2-validation', 'flow-run-005', 'rpa_db', NOW() - INTERVAL '5 minutes', NULL, NULL, 'running', 0, 0, 0, 0, 'healthy', 21.1, '{"validation_strict": false, "max_retries": 5}');