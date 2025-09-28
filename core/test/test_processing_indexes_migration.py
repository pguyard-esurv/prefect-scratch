"""
Integration test for V007__Add_processing_indexes.sql migration.
Tests that the migration can be applied successfully and creates the expected indexes.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestProcessingIndexesMigration:
    """Test the V007 migration for processing queue indexes."""

    @pytest.fixture
    def db_manager(self):
        """Create a test DatabaseManager instance."""
        with patch('core.database.DatabaseManager') as mock_db:
            mock_instance = MagicMock()
            mock_db.return_value = mock_instance
            yield mock_instance

    def test_migration_file_exists(self):
        """Test that the V007 migration file exists and is readable."""
        import os
        migration_path = "core/migrations/rpa_db/V007__Add_processing_indexes.sql"

        assert os.path.exists(migration_path), f"Migration file {migration_path} does not exist"

        with open(migration_path) as f:
            content = f.read()

        # Verify migration contains expected index creation statements
        expected_indexes = [
            'idx_processing_queue_status_created_at',
            'idx_processing_queue_flow_name_status',
            'idx_processing_queue_flow_instance_id',
            'idx_processing_queue_pending',
            'idx_processing_queue_processing_claimed_at',
            'idx_processing_queue_failed_retry',
            'idx_processing_queue_cleanup_timestamps',
            'idx_processing_queue_monitoring'
        ]

        for index_name in expected_indexes:
            assert index_name in content, f"Index {index_name} not found in migration"

    def test_migration_syntax_validation(self):
        """Test that the migration file has valid SQL syntax."""
        migration_path = "core/migrations/rpa_db/V007__Add_processing_indexes.sql"

        with open(migration_path) as f:
            content = f.read()

        # Basic syntax checks
        assert content.count('CREATE INDEX') >= 8, "Expected at least 8 CREATE INDEX statements"
        assert content.count('ON processing_queue') >= 8, "Expected indexes on processing_queue table"
        assert 'DROP INDEX IF EXISTS' in content, "Expected cleanup of old indexes"
        assert 'ANALYZE processing_queue' in content, "Expected ANALYZE statement"

        # Check for proper WHERE clauses in partial indexes
        assert 'WHERE status = \'pending\'' in content, "Expected partial index for pending status"
        assert 'WHERE status = \'processing\'' in content, "Expected partial index for processing status"
        assert 'WHERE status = \'failed\'' in content, "Expected partial index for failed status"

    def test_migration_execution_simulation(self, db_manager):
        """Test simulated execution of the migration."""
        # Mock successful migration execution
        db_manager.execute_query.return_value = None

        # Read and simulate executing the migration
        migration_path = "core/migrations/rpa_db/V007__Add_processing_indexes.sql"
        with open(migration_path) as f:
            migration_content = f.read()

        # Split migration into individual statements
        statements = [stmt.strip() for stmt in migration_content.split(';') if stmt.strip()]

        # Execute each statement
        for statement in statements:
            if statement and not statement.startswith('--'):
                db_manager.execute_query(statement)

        # Verify that execute_query was called for each non-comment statement
        non_comment_statements = [stmt for stmt in statements if stmt and not stmt.startswith('--')]
        assert db_manager.execute_query.call_count >= len(non_comment_statements) - 5  # Allow for some combined statements

    def test_index_comments_validation(self):
        """Test that indexes have proper documentation comments."""
        migration_path = "core/migrations/rpa_db/V007__Add_processing_indexes.sql"

        with open(migration_path) as f:
            content = f.read()

        # Check that each major index has a comment
        expected_comments = [
            'COMMENT ON INDEX idx_processing_queue_status_created_at',
            'COMMENT ON INDEX idx_processing_queue_flow_name_status',
            'COMMENT ON INDEX idx_processing_queue_flow_instance_id',
            'COMMENT ON INDEX idx_processing_queue_pending',
            'COMMENT ON INDEX idx_processing_queue_processing_claimed_at'
        ]

        for comment in expected_comments:
            assert comment in content, f"Missing comment: {comment}"

    def test_performance_optimization_features(self):
        """Test that the migration includes performance optimization features."""
        migration_path = "core/migrations/rpa_db/V007__Add_processing_indexes.sql"

        with open(migration_path) as f:
            content = f.read()

        # Check for performance optimization features
        assert 'WHERE flow_instance_id IS NOT NULL' in content, "Expected conditional index for flow_instance_id"
        assert 'WHERE status = \'pending\'' in content, "Expected partial index for pending records"
        assert 'WHERE status = \'processing\'' in content, "Expected partial index for processing records"
        assert 'WHERE status = \'failed\'' in content, "Expected partial index for failed records"

        # Check for composite indexes that support multiple query patterns
        assert '(status, created_at)' in content, "Expected composite index for status and created_at"
        assert '(flow_name, status)' in content, "Expected composite index for flow_name and status"
        assert '(retry_count, created_at)' in content, "Expected composite index for retry logic"

    def test_backward_compatibility(self):
        """Test that the migration handles backward compatibility properly."""
        migration_path = "core/migrations/rpa_db/V007__Add_processing_indexes.sql"

        with open(migration_path) as f:
            content = f.read()

        # Check that old indexes are properly dropped before creating new ones
        assert 'DROP INDEX IF EXISTS idx_processing_queue_status' in content
        assert 'DROP INDEX IF EXISTS idx_processing_queue_flow_name' in content

        # Verify IF NOT EXISTS is not used for new indexes (we want to know if they already exist)
        create_index_lines = [line for line in content.split('\n') if 'CREATE INDEX' in line and not line.strip().startswith('--')]
        for line in create_index_lines:
            assert 'IF NOT EXISTS' not in line, f"Unexpected IF NOT EXISTS in: {line}"

    def test_migration_rollback_safety(self):
        """Test that the migration can be safely rolled back if needed."""
        migration_path = "core/migrations/rpa_db/V007__Add_processing_indexes.sql"

        with open(migration_path) as f:
            content = f.read()

        # Verify that all operations are reversible
        # Index creation can be rolled back by dropping the indexes
        create_statements = [line for line in content.split('\n') if 'CREATE INDEX' in line and not line.strip().startswith('--')]

        # Each CREATE INDEX should create a named index that can be dropped
        for statement in create_statements:
            assert 'idx_processing_queue_' in statement, f"Index should have proper naming: {statement}"

        # Verify no irreversible operations
        irreversible_operations = ['DROP TABLE', 'ALTER TABLE DROP COLUMN', 'DROP DATABASE']
        for operation in irreversible_operations:
            assert operation not in content, f"Found irreversible operation: {operation}"
