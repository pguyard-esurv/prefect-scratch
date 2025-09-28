-- Test migration file for unit testing
-- Adds an index to the test table

CREATE INDEX IF NOT EXISTS idx_test_table_name ON test_table(name);

-- Add a new column
ALTER TABLE test_table ADD COLUMN IF NOT EXISTS description TEXT;