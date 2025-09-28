"""
Integration tests for example flows demonstrating DatabaseManager usage.

These tests validate:
1. Example flow execution with real database connections
2. Migration execution and rollback scenarios
3. Concurrent database operations
4. Health check integration
5. Error handling and recovery mechanisms
6. End-to-end flow functionality
"""

from pathlib import Path

import pytest

from core.database import DatabaseManager
from flows.examples.concurrent_database_processing import (
    concurrent_database_processing_flow,
)
from flows.examples.database_integration_example import (
    database_integration_example_flow,
)
from flows.examples.health_check_integration import health_check_integration_flow
from flows.examples.production_error_handling import production_error_handling_flow


class TestDatabaseIntegrationExample:
    """Test suite for database integration example flow."""

    @pytest.fixture
    def test_database_name(self):
        """Provide test database name."""
        return "rpa_db"

    @pytest.fixture
    def setup_test_data(self, test_database_name):
        """Set up test data before running integration tests."""
        # Ensure test tables exist and have some data
        with DatabaseManager(test_database_name) as db:
            # Run migrations to ensure tables exist
            db.run_migrations()

            # Clean up any existing test data
            cleanup_queries = [
                "DELETE FROM flow_execution_logs WHERE flow_name LIKE '%test%' OR flow_name LIKE '%example%'",
                "DELETE FROM processed_surveys WHERE survey_id LIKE 'TEST-%'",
                "DELETE FROM customer_orders WHERE order_id LIKE 'TEST-%'"
            ]

            for query in cleanup_queries:
                try:
                    db.execute_query(query)
                except Exception:
                    pass  # Ignore errors if tables don't exist yet

        yield

        # Cleanup after tests
        with DatabaseManager(test_database_name) as db:
            for query in cleanup_queries:
                try:
                    db.execute_query(query)
                except Exception:
                    pass

    def test_database_integration_flow_execution(self, test_database_name, setup_test_data):
        """Test complete database integration flow execution."""
        # Run the integration flow
        result = database_integration_example_flow(
            source_database=test_database_name,  # Use same DB for both source and target in test
            target_database=test_database_name,
            run_migrations=True,
            health_check_required=True
        )

        # Validate flow execution results
        assert result is not None
        assert result['flow_execution']['status'] == 'completed'
        assert result['flow_execution']['source_database'] == test_database_name
        assert result['flow_execution']['target_database'] == test_database_name

        # Validate health checks were performed
        assert result['health_checks'] is not None
        assert test_database_name in result['health_checks']
        health_status = result['health_checks'][test_database_name]
        assert health_status['overall_status'] in ['healthy', 'degraded']

        # Validate migrations were run
        assert result['migrations'] is not None
        assert test_database_name in result['migrations']
        migration_result = result['migrations'][test_database_name]
        assert migration_result['success'] is True

        # Validate processing report was generated
        assert result['processing_report'] is not None
        processing_summary = result['processing_report']['processing_summary']
        assert processing_summary['total_surveys'] > 0
        assert processing_summary['processed_successfully'] >= 0

    def test_database_integration_flow_without_migrations(self, test_database_name, setup_test_data):
        """Test database integration flow without running migrations."""
        result = database_integration_example_flow(
            source_database=test_database_name,
            target_database=test_database_name,
            run_migrations=False,
            health_check_required=True
        )

        assert result['flow_execution']['status'] == 'completed'
        assert result['migrations'] is None  # Should be None when migrations are skipped
        assert result['health_checks'] is not None

    def test_database_integration_flow_without_health_checks(self, test_database_name, setup_test_data):
        """Test database integration flow without health checks."""
        result = database_integration_example_flow(
            source_database=test_database_name,
            target_database=test_database_name,
            run_migrations=False,
            health_check_required=False
        )

        assert result['flow_execution']['status'] == 'completed'
        assert result['health_checks'] is None  # Should be None when health checks are skipped


class TestConcurrentDatabaseProcessing:
    """Test suite for concurrent database processing flow."""

    @pytest.fixture
    def test_database_name(self):
        """Provide test database name."""
        return "rpa_db"

    @pytest.fixture
    def setup_concurrent_test_data(self, test_database_name):
        """Set up test data for concurrent processing tests."""
        with DatabaseManager(test_database_name) as db:
            # Ensure migrations are run
            db.run_migrations()

            # Clean up any existing concurrent test data
            cleanup_query = "DELETE FROM customer_orders WHERE order_id LIKE 'CONC-%' OR processed_by_flow = 'concurrent-database-processing'"
            try:
                db.execute_query(cleanup_query)
            except Exception:
                pass

        yield

        # Cleanup after tests
        with DatabaseManager(test_database_name) as db:
            try:
                db.execute_query(cleanup_query)
            except Exception:
                pass

    def test_concurrent_processing_flow_execution(self, test_database_name, setup_concurrent_test_data):
        """Test concurrent database processing flow execution."""
        result = concurrent_database_processing_flow(
            database_name=test_database_name,
            max_concurrent_tasks=3  # Limit concurrency for testing
        )

        # Validate flow execution results
        assert result is not None
        assert result['flow_execution']['status'] == 'completed'
        assert result['flow_execution']['database_name'] == test_database_name
        assert result['flow_execution']['concurrent_tasks'] == 6  # Number of sample orders

        # Validate processing results
        processing_results = result['processing_results']
        assert len(processing_results) == 6  # Should have results for all 6 sample orders

        # Check that all orders were processed
        for order_result in processing_results:
            assert 'order_id' in order_result
            assert 'final_status' in order_result
            assert order_result['final_status'] in ['approved', 'pending', 'rejected', 'error']

        # Validate execution metrics
        execution_metrics = result['execution_metrics']
        assert execution_metrics['total_orders'] == 6
        assert execution_metrics['total_orders'] == (
            execution_metrics.get('successful_orders', 0) +
            execution_metrics.get('pending_orders', 0) +
            execution_metrics.get('rejected_orders', 0)
        )

        # Validate summary
        summary = result['summary']
        assert summary['total_orders'] == 6
        assert summary['successful_processing'] >= 0
        assert summary['inventory_available'] >= 0

    def test_concurrent_processing_database_state(self, test_database_name, setup_concurrent_test_data):
        """Test that concurrent processing correctly updates database state."""
        # Run the concurrent processing flow
        result = concurrent_database_processing_flow(database_name=test_database_name)

        # Verify that orders were actually inserted into the database
        with DatabaseManager(test_database_name) as db:
            # Check that orders were inserted
            orders_query = "SELECT COUNT(*) as count FROM customer_orders WHERE processed_by_flow = 'concurrent-database-processing'"
            orders_count = db.execute_query(orders_query)

            # Should have inserted some orders (successful processing results)
            successful_orders = result['execution_metrics']['successful_orders']
            assert orders_count[0]['count'] >= successful_orders

            # Check that execution was logged
            log_query = "SELECT COUNT(*) as count FROM flow_execution_logs WHERE flow_name = 'concurrent-database-processing'"
            log_count = db.execute_query(log_query)
            assert log_count[0]['count'] >= 1  # At least one log entry should exist


class TestHealthCheckIntegration:
    """Test suite for health check integration flow."""

    @pytest.fixture
    def test_database_name(self):
        """Provide test database name."""
        return "rpa_db"

    def test_health_check_integration_flow_execution(self, test_database_name):
        """Test health check integration flow execution."""
        result = health_check_integration_flow(
            target_databases=[test_database_name],
            minimum_health_level="degraded",  # More lenient for testing
            perform_trend_analysis=True,
            fail_on_prerequisites=False  # Don't fail on prerequisites in tests
        )

        # Validate flow execution results
        assert result is not None
        assert result['flow_execution']['status'] == 'completed'
        assert result['flow_execution']['databases_checked'] == [test_database_name]

        # Validate health checks
        health_checks = result['health_checks']
        assert test_database_name in health_checks

        db_health = health_checks[test_database_name]
        assert 'overall_status' in db_health
        assert db_health['overall_status'] in ['healthy', 'degraded', 'critical_failure']

        # Validate prerequisite validation
        prerequisite_validation = result['prerequisite_validation']
        assert 'overall_status' in prerequisite_validation
        assert prerequisite_validation['overall_status'] in ['passed', 'failed']

        # Validate trend analysis
        trend_analysis = result['trend_analysis']
        assert trend_analysis is not None
        assert 'overall_trends' in trend_analysis

        # Validate recommendations
        recommendations = result['recommendations']
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

    def test_health_check_with_strict_requirements(self, test_database_name):
        """Test health check with strict requirements."""
        result = health_check_integration_flow(
            target_databases=[test_database_name],
            minimum_health_level="healthy",
            perform_trend_analysis=False,
            fail_on_prerequisites=False
        )

        assert result['flow_execution']['status'] == 'completed'
        assert result['trend_analysis'] is None  # Should be None when not requested


class TestProductionErrorHandling:
    """Test suite for production error handling flow."""

    @pytest.fixture
    def test_database_name(self):
        """Provide test database name."""
        return "rpa_db"

    @pytest.fixture
    def setup_error_handling_test_data(self, test_database_name):
        """Set up test data for error handling tests."""
        with DatabaseManager(test_database_name) as db:
            # Ensure migrations are run
            db.run_migrations()

            # Clean up any existing error handling test data
            cleanup_query = "DELETE FROM flow_execution_logs WHERE flow_name = 'production-error-handling-example'"
            try:
                db.execute_query(cleanup_query)
            except Exception:
                pass

        yield

        # Cleanup after tests
        with DatabaseManager(test_database_name) as db:
            try:
                db.execute_query(cleanup_query)
            except Exception:
                pass

    def test_production_error_handling_flow_normal_execution(self, test_database_name, setup_error_handling_test_data):
        """Test production error handling flow with normal execution (no errors)."""
        result = production_error_handling_flow(
            primary_database=test_database_name,
            fallback_database=None,
            simulate_errors=False,
            enable_circuit_breaker=True
        )

        # Validate flow execution results
        assert result is not None
        assert result['flow_execution']['status'] in ['completed_success', 'completed_partial_success']
        assert result['flow_execution']['primary_database'] == test_database_name

        # Validate error handling metrics
        error_handling = result['error_handling']
        assert error_handling['total_operations'] > 0
        assert error_handling['successful_operations'] >= 0

        # Should have some successful operations in normal execution
        assert error_handling['successful_operations'] > 0

    def test_production_error_handling_flow_with_simulated_errors(self, test_database_name, setup_error_handling_test_data):
        """Test production error handling flow with simulated errors."""
        result = production_error_handling_flow(
            primary_database=test_database_name,
            fallback_database=None,
            simulate_errors=True,
            enable_circuit_breaker=True
        )

        # Validate flow execution results
        assert result is not None
        # With simulated errors, we might have partial success or some failures
        assert result['flow_execution']['status'] in [
            'completed_success',
            'completed_partial_success',
            'completed_all_failed'
        ]

        # Validate that errors were handled
        error_handling = result['error_handling']
        assert error_handling['total_operations'] > 0

        # With simulated errors, we should have some failed operations
        # (unless all error simulations were handled gracefully)
        operations = result['operations']
        assert len(operations) > 0

        # Check that error logging occurred for failed operations
        errors_logged = result['errors_logged']
        # May or may not have errors logged depending on how gracefully errors were handled
        assert isinstance(errors_logged, list)

    def test_production_error_handling_with_circuit_breaker_disabled(self, test_database_name, setup_error_handling_test_data):
        """Test production error handling flow with circuit breaker disabled."""
        result = production_error_handling_flow(
            primary_database=test_database_name,
            fallback_database=None,
            simulate_errors=False,
            enable_circuit_breaker=False
        )

        assert result['flow_execution']['status'] in ['completed_success', 'completed_partial_success']
        # Circuit breaker status should not be present when disabled
        assert 'final_circuit_breaker_status' not in result


class TestMigrationExecution:
    """Test suite for migration execution scenarios."""

    @pytest.fixture
    def test_database_name(self):
        """Provide test database name."""
        return "rpa_db"

    def test_migration_execution_and_status(self, test_database_name):
        """Test migration execution and status checking."""
        with DatabaseManager(test_database_name) as db:
            # Get initial migration status
            initial_status = db.get_migration_status()

            # Run migrations
            db.run_migrations()

            # Get final migration status
            final_status = db.get_migration_status()

            # Validate migration status structure
            assert 'database_name' in final_status
            assert 'current_version' in final_status
            assert 'pending_migrations' in final_status
            assert 'total_applied' in final_status

            assert final_status['database_name'] == test_database_name

            # Should have applied migrations (or at least checked for them)
            assert final_status['total_applied'] >= initial_status.get('total_applied', 0)

    def test_migration_directory_structure(self, test_database_name):
        """Test that migration directory structure is correct."""
        with DatabaseManager(test_database_name) as db:
            migration_status = db.get_migration_status()

            # Check that migration directory exists
            migration_dir = Path(migration_status['migration_directory'])
            assert migration_dir.exists()

            # Check for expected migration files
            migration_files = list(migration_dir.glob("V*.sql"))
            assert len(migration_files) > 0  # Should have at least some migration files

            # Validate migration file naming convention
            for migration_file in migration_files:
                assert migration_file.name.startswith("V")
                assert "__" in migration_file.name
                assert migration_file.name.endswith(".sql")

    def test_health_check_includes_migration_status(self, test_database_name):
        """Test that health checks include migration status information."""
        with DatabaseManager(test_database_name) as db:
            health_status = db.health_check()

            # Validate health check structure
            assert 'migration_status' in health_status
            migration_info = health_status['migration_status']

            if migration_info and not isinstance(migration_info, dict) or 'error' not in migration_info:
                # If migration status was retrieved successfully
                assert 'database_name' in migration_info
                assert 'current_version' in migration_info
                assert 'pending_migrations' in migration_info


class TestEndToEndIntegration:
    """End-to-end integration tests combining multiple example flows."""

    @pytest.fixture
    def test_database_name(self):
        """Provide test database name."""
        return "rpa_db"

    @pytest.fixture
    def setup_e2e_test_data(self, test_database_name):
        """Set up comprehensive test data for end-to-end tests."""
        with DatabaseManager(test_database_name) as db:
            # Ensure migrations are run
            db.run_migrations()

            # Clean up any existing test data
            cleanup_queries = [
                "DELETE FROM flow_execution_logs WHERE flow_name LIKE '%test%' OR flow_name LIKE '%example%'",
                "DELETE FROM processed_surveys WHERE survey_id LIKE 'E2E-%'",
                "DELETE FROM customer_orders WHERE order_id LIKE 'E2E-%'"
            ]

            for query in cleanup_queries:
                try:
                    db.execute_query(query)
                except Exception:
                    pass

        yield

        # Cleanup after tests
        with DatabaseManager(test_database_name) as db:
            for query in cleanup_queries:
                try:
                    db.execute_query(query)
                except Exception:
                    pass

    def test_complete_workflow_integration(self, test_database_name, setup_e2e_test_data):
        """Test complete workflow integration across multiple example flows."""
        # Step 1: Run health check integration to validate prerequisites
        health_result = health_check_integration_flow(
            target_databases=[test_database_name],
            minimum_health_level="degraded",
            perform_trend_analysis=False,
            fail_on_prerequisites=False
        )

        assert health_result['flow_execution']['status'] == 'completed'

        # Step 2: Run database integration example
        integration_result = database_integration_example_flow(
            source_database=test_database_name,
            target_database=test_database_name,
            run_migrations=True,
            health_check_required=True
        )

        assert integration_result['flow_execution']['status'] == 'completed'

        # Step 3: Run concurrent processing
        concurrent_result = concurrent_database_processing_flow(
            database_name=test_database_name,
            max_concurrent_tasks=2
        )

        assert concurrent_result['flow_execution']['status'] == 'completed'

        # Step 4: Run error handling example
        error_handling_result = production_error_handling_flow(
            primary_database=test_database_name,
            simulate_errors=False,
            enable_circuit_breaker=True
        )

        assert error_handling_result['flow_execution']['status'] in [
            'completed_success',
            'completed_partial_success'
        ]

        # Validate that all flows executed successfully and left data in the database
        with DatabaseManager(test_database_name) as db:
            # Check that flow execution logs were created
            log_query = """
            SELECT flow_name, COUNT(*) as execution_count
            FROM flow_execution_logs
            WHERE flow_name IN (
                'database-integration-example',
                'concurrent-database-processing',
                'production-error-handling-example'
            )
            GROUP BY flow_name
            """

            log_results = db.execute_query(log_query)

            # Should have log entries for the flows we executed
            flow_names = [result['flow_name'] for result in log_results]
            assert len(flow_names) > 0  # At least some flows should have logged execution

    def test_database_state_consistency_after_multiple_flows(self, test_database_name, setup_e2e_test_data):
        """Test that database state remains consistent after multiple flow executions."""
        # Record initial state
        with DatabaseManager(test_database_name) as db:
            initial_survey_count_query = "SELECT COUNT(*) as count FROM processed_surveys"
            initial_order_count_query = "SELECT COUNT(*) as count FROM customer_orders"
            initial_log_count_query = "SELECT COUNT(*) as count FROM flow_execution_logs"

            initial_survey_count = db.execute_query(initial_survey_count_query)[0]['count']
            initial_order_count = db.execute_query(initial_order_count_query)[0]['count']
            initial_log_count = db.execute_query(initial_log_count_query)[0]['count']

        # Run multiple flows
        flows_to_run = [
            lambda: database_integration_example_flow(
                source_database=test_database_name,
                target_database=test_database_name,
                run_migrations=False,
                health_check_required=False
            ),
            lambda: concurrent_database_processing_flow(database_name=test_database_name),
            lambda: production_error_handling_flow(
                primary_database=test_database_name,
                simulate_errors=False,
                enable_circuit_breaker=False
            )
        ]

        for flow_func in flows_to_run:
            result = flow_func()
            assert result['flow_execution']['status'] in [
                'completed',
                'completed_success',
                'completed_partial_success'
            ]

        # Check final state
        with DatabaseManager(test_database_name) as db:
            final_survey_count = db.execute_query(initial_survey_count_query)[0]['count']
            final_order_count = db.execute_query(initial_order_count_query)[0]['count']
            final_log_count = db.execute_query(initial_log_count_query)[0]['count']

            # Counts should have increased (flows added data)
            assert final_survey_count >= initial_survey_count
            assert final_order_count >= initial_order_count
            assert final_log_count > initial_log_count  # Should definitely have more logs

            # Verify data integrity with a sample query
            integrity_query = """
            SELECT
                COUNT(DISTINCT flow_name) as unique_flows,
                COUNT(*) as total_executions,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_executions
            FROM flow_execution_logs
            WHERE execution_start >= NOW() - INTERVAL '1 hour'
            """

            integrity_results = db.execute_query(integrity_query)[0]
            assert integrity_results['unique_flows'] > 0
            assert integrity_results['total_executions'] > 0
            assert integrity_results['completed_executions'] >= 0


if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "--tb=short"])
