-- Test migration file for unit testing
-- Creates a simple test table

CREATE TABLE IF NOT EXISTS test_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert test data
INSERT INTO test_table (name) VALUES ('Test Record 1');
INSERT INTO test_table (name) VALUES ('Test Record 2');