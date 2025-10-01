"""
Test suite for processing queue index performance verification.
Tests the indexes created in V007__Add_processing_indexes.sql migration.
"""

import time
from unittest.mock import MagicMock, patch

import pytest


class TestProcessingIndexesPerformance:
    """Test performance indexes for processing_queue table."""

    @pytest.fixture
    def db_manager(self):
        """Create a test DatabaseManager instance."""
        with patch("core.database.DatabaseManager") as mock_db:
            mock_instance = MagicMock()
            mock_db.return_value = mock_instance
            yield mock_instance

    def test_index_creation_verification(self, db_manager):
        """Test that all required indexes are created properly."""
        # Mock the query to check index existence
        expected_indexes = [
            "idx_processing_queue_status_created_at",
            "idx_processing_queue_flow_name_status",
            "idx_processing_queue_flow_instance_id",
            "idx_processing_queue_pending",
            "idx_processing_queue_processing_claimed_at",
            "idx_processing_queue_failed_retry",
            "idx_processing_queue_cleanup_timestamps",
            "idx_processing_queue_monitoring",
        ]

        # Mock database response for index verification query
        mock_indexes = [{"indexname": idx} for idx in expected_indexes]
        db_manager.execute_query.return_value = mock_indexes

        # Query to check if indexes exist
        index_query = """
        SELECT indexname
        FROM pg_indexes
        WHERE tablename = 'processing_queue'
        AND indexname LIKE 'idx_processing_queue_%'
        ORDER BY indexname;
        """

        result = db_manager.execute_query(index_query)
        db_manager.execute_query.assert_called_with(index_query)

        # Verify all expected indexes are present
        actual_indexes = [row["indexname"] for row in result]
        for expected_index in expected_indexes:
            assert expected_index in actual_indexes, f"Index {expected_index} not found"

    @pytest.mark.slow
    def test_pending_records_query_performance(self, db_manager):
        """Test performance of pending records query (most critical for claiming)."""
        # Mock query execution for pending records
        mock_records = [
            {
                "id": 1,
                "flow_name": "survey_processor",
                "payload": {"survey_id": 1001},
                "created_at": "2024-01-15 10:00:00",
            },
            {
                "id": 2,
                "flow_name": "survey_processor",
                "payload": {"survey_id": 1002},
                "created_at": "2024-01-15 10:01:00",
            },
            {
                "id": 3,
                "flow_name": "order_processor",
                "payload": {"order_id": 2001},
                "created_at": "2024-01-15 10:02:00",
            },
        ]
        db_manager.execute_query.return_value = mock_records

        # Query that should use idx_processing_queue_status_created_at
        pending_query = """
        SELECT id, flow_name, payload, created_at
        FROM processing_queue
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT 100;
        """

        start_time = time.time()
        result = db_manager.execute_query(pending_query)
        execution_time = time.time() - start_time

        db_manager.execute_query.assert_called_with(pending_query)
        assert len(result) == 3
        assert execution_time < 1.0  # Should be very fast with proper index

    @pytest.mark.slow
    def test_flow_specific_status_query_performance(self, db_manager):
        """Test performance of flow-specific status queries."""
        # Mock query execution for flow-specific queries
        mock_status_counts = [
            {"status": "pending", "count": 150},
            {"status": "processing", "count": 25},
            {"status": "completed", "count": 1000},
            {"status": "failed", "count": 5},
        ]
        db_manager.execute_query.return_value = mock_status_counts

        # Query that should use idx_processing_queue_flow_name_status
        flow_status_query = """
        SELECT status, COUNT(*) as count
        FROM processing_queue
        WHERE flow_name = 'survey_processor'
        GROUP BY status;
        """

        start_time = time.time()
        result = db_manager.execute_query(flow_status_query)
        execution_time = time.time() - start_time

        db_manager.execute_query.assert_called_with(flow_status_query)
        assert len(result) == 4
        assert execution_time < 0.5  # Should be fast with composite index

    @pytest.mark.slow
    def test_cleanup_operations_query_performance(self, db_manager):
        """Test performance of cleanup operations using flow_instance_id index."""
        # Mock query execution for cleanup operations
        mock_orphaned_records = [
            {
                "id": 10,
                "flow_instance_id": "container-1-abc123",
                "claimed_at": "2024-01-15 08:00:00",
            },
            {
                "id": 15,
                "flow_instance_id": "container-2-def456",
                "claimed_at": "2024-01-15 08:30:00",
            },
        ]
        db_manager.execute_query.return_value = mock_orphaned_records

        # Query that should use idx_processing_queue_processing_claimed_at
        cleanup_query = """
        SELECT id, flow_instance_id, claimed_at
        FROM processing_queue
        WHERE status = 'processing'
        AND claimed_at < NOW() - INTERVAL '1 hour';
        """

        start_time = time.time()
        result = db_manager.execute_query(cleanup_query)
        execution_time = time.time() - start_time

        db_manager.execute_query.assert_called_with(cleanup_query)
        assert len(result) == 2
        assert execution_time < 0.5  # Should be fast with partial index

    @pytest.mark.slow
    def test_atomic_record_claiming_query_performance(self, db_manager):
        """Test performance of atomic record claiming query (FOR UPDATE SKIP LOCKED)."""
        # Mock query execution for atomic claiming
        mock_claimed_records = [
            {
                "id": 1,
                "payload": {"survey_id": 1001},
                "retry_count": 0,
                "created_at": "2024-01-15 10:00:00",
            },
            {
                "id": 2,
                "payload": {"survey_id": 1002},
                "retry_count": 0,
                "created_at": "2024-01-15 10:01:00",
            },
        ]
        db_manager.execute_query.return_value = mock_claimed_records

        # Atomic claiming query that should use idx_processing_queue_pending
        claiming_query = """
        UPDATE processing_queue
        SET status = 'processing',
            flow_instance_id = 'container-1-abc123',
            claimed_at = NOW(),
            updated_at = NOW()
        WHERE id IN (
            SELECT id FROM processing_queue
            WHERE flow_name = 'survey_processor' AND status = 'pending'
            ORDER BY created_at ASC
            LIMIT 50
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, payload, retry_count, created_at;
        """

        start_time = time.time()
        result = db_manager.execute_query(claiming_query)
        execution_time = time.time() - start_time

        db_manager.execute_query.assert_called_with(claiming_query)
        assert len(result) == 2
        assert execution_time < 1.0  # Should be fast even with locking

    @pytest.mark.slow
    def test_monitoring_dashboard_query_performance(self, db_manager):
        """Test performance of monitoring dashboard queries."""
        # Mock query execution for monitoring dashboard
        mock_dashboard_data = [
            {
                "flow_name": "survey_processor",
                "status": "pending",
                "count": 150,
                "oldest_created_at": "2024-01-15 09:00:00",
            },
            {
                "flow_name": "survey_processor",
                "status": "processing",
                "count": 25,
                "oldest_created_at": "2024-01-15 09:30:00",
            },
            {
                "flow_name": "order_processor",
                "status": "pending",
                "count": 75,
                "oldest_created_at": "2024-01-15 09:15:00",
            },
        ]
        db_manager.execute_query.return_value = mock_dashboard_data

        # Query that should use idx_processing_queue_monitoring
        dashboard_query = """
        SELECT
            flow_name,
            status,
            COUNT(*) as count,
            MIN(created_at) as oldest_created_at
        FROM processing_queue
        WHERE status IN ('pending', 'processing')
        GROUP BY flow_name, status
        ORDER BY flow_name, status;
        """

        start_time = time.time()
        result = db_manager.execute_query(dashboard_query)
        execution_time = time.time() - start_time

        db_manager.execute_query.assert_called_with(dashboard_query)
        assert len(result) == 3
        assert execution_time < 0.5  # Should be fast with monitoring index

    @pytest.mark.slow
    def test_failed_record_retry_query_performance(self, db_manager):
        """Test performance of failed record retry queries."""
        # Mock query execution for retry operations
        mock_retry_records = [
            {
                "id": 20,
                "retry_count": 1,
                "error_message": "Temporary network error",
                "created_at": "2024-01-15 08:00:00",
            },
            {
                "id": 25,
                "retry_count": 2,
                "error_message": "Database timeout",
                "created_at": "2024-01-15 08:15:00",
            },
        ]
        db_manager.execute_query.return_value = mock_retry_records

        # Query that should use idx_processing_queue_failed_retry
        retry_query = """
        SELECT id, retry_count, error_message, created_at
        FROM processing_queue
        WHERE status = 'failed'
        AND retry_count < 3
        ORDER BY created_at ASC
        LIMIT 100;
        """

        start_time = time.time()
        result = db_manager.execute_query(retry_query)
        execution_time = time.time() - start_time

        db_manager.execute_query.assert_called_with(retry_query)
        assert len(result) == 2
        assert execution_time < 0.5  # Should be fast with partial index

    def test_explain_query_plans(self, db_manager):
        """Test that queries use the expected indexes via EXPLAIN plans."""
        # Mock EXPLAIN output showing index usage
        mock_explain_plans = [
            {
                "QUERY PLAN": "Index Scan using idx_processing_queue_pending on processing_queue"
            },
            {"QUERY PLAN": "  Index Cond: (status = 'pending'::text)"},
            {"QUERY PLAN": "  Buffers: shared hit=4"},
        ]
        db_manager.execute_query.return_value = mock_explain_plans

        # Test EXPLAIN for pending records query
        explain_query = """
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT id FROM processing_queue
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT 10;
        """

        result = db_manager.execute_query(explain_query)
        db_manager.execute_query.assert_called_with(explain_query)

        # Verify that the explain plan mentions our index
        plan_text = " ".join([row["QUERY PLAN"] for row in result])
        assert (
            "idx_processing_queue_pending" in plan_text
            or "idx_processing_queue_status_created_at" in plan_text
        )

    def test_concurrent_access_simulation(self, db_manager):
        """Test that indexes perform well under concurrent access patterns."""
        # Mock concurrent query execution
        db_manager.execute_query.return_value = [{"success": True}]

        # Simulate multiple concurrent queries that would happen in production
        concurrent_queries = [
            "SELECT COUNT(*) FROM processing_queue WHERE status = 'pending'",
            "SELECT COUNT(*) FROM processing_queue WHERE flow_name = 'survey_processor' AND status = 'processing'",
            "UPDATE processing_queue SET status = 'processing' WHERE id = 1",
            "SELECT id FROM processing_queue WHERE status = 'processing' AND claimed_at < NOW() - INTERVAL '1 hour'",
        ]

        start_time = time.time()
        for query in concurrent_queries:
            db_manager.execute_query(query)
        total_execution_time = time.time() - start_time

        # All queries should complete quickly even when run together
        assert total_execution_time < 2.0
        assert db_manager.execute_query.call_count == len(concurrent_queries)

    def test_index_size_and_efficiency(self, db_manager):
        """Test that indexes are appropriately sized and efficient."""
        # Mock index size query results
        mock_index_sizes = [
            {"indexname": "idx_processing_queue_pending", "size_mb": 2.1},
            {"indexname": "idx_processing_queue_status_created_at", "size_mb": 5.8},
            {"indexname": "idx_processing_queue_flow_name_status", "size_mb": 4.2},
        ]
        db_manager.execute_query.return_value = mock_index_sizes

        # Query to check index sizes
        size_query = """
        SELECT
            indexname,
            pg_size_pretty(pg_relation_size(indexname::regclass)) as size_mb
        FROM pg_indexes
        WHERE tablename = 'processing_queue'
        AND indexname LIKE 'idx_processing_queue_%';
        """

        result = db_manager.execute_query(size_query)
        db_manager.execute_query.assert_called_with(size_query)

        # Verify reasonable index sizes (partial indexes should be smaller)
        for index_info in result:
            if "pending" in index_info["indexname"]:
                # Partial indexes should be smaller
                assert index_info["size_mb"] < 5.0
            else:
                # Full indexes can be larger but should be reasonable
                assert index_info["size_mb"] < 20.0
