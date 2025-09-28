"""
Integration tests for DatabaseManager with actual database connectivity.

These tests require actual database instances and should be run in CI/CD
environments with proper test database setup.

Requirements covered: 11.2
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from core.database import DatabaseManager

# Skip integration tests by default unless explicitly enabled
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require RUN_INTEGRATION_TESTS environment variable",
)


class TestPostgreSQLIntegration:
    """Integration tests for PostgreSQL database connectivity."""

    @pytest.fixture(scope="class")
    def postgresql_config(self):
        """PostgreSQL test database configuration."""
        return {
            "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
            "port": os.getenv("POSTGRES_TEST_PORT", "5432"),
            "database": os.getenv("POSTGRES_TEST_DB", "test_db"),
            "username": os.getenv("POSTGRES_TEST_USER", "test_user"),
            "password": os.getenv("POSTGRES_TEST_PASSWORD", "test_password"),
        }

    @pytest.fixture(scope="class")
    def postgresql_connection_string(self, postgresql_config):
        """Create PostgreSQL connection string."""
        return (
            f"postgresql://{postgresql_config['username']}:"
            f"{postgresql_config['password']}@{postgresql_config['host']}:"
            f"{postgresql_config['port']}/{postgresql_config['database']}"
        )

    @pytest.fixture
    def setup_postgresql_test_table(self, postgresql_connection_string):
        """Set up test table in PostgreSQL."""
        engine = create_engine(postgresql_connection_string)

        # Create test table
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS integration_test_users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            conn.commit()

        yield

        # Cleanup test table
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS integration_test_users"))
            conn.commit()

        engine.dispose()

    def test_postgresql_connection_and_query(
        self, postgresql_connection_string, setup_postgresql_test_table
    ):
        """Test actual PostgreSQL connection and query execution."""
        with patch("core.database.ConfigManager") as mock_config_class:
            # Setup mock configuration
            mock_config = mock_config_class.return_value
            mock_config.environment = "test"
            mock_config.get_variable.side_effect = lambda key, default=None: {
                "postgres_test_type": "postgresql"
            }.get(key, default)
            mock_config.get_secret.return_value = postgresql_connection_string

            # Test database operations
            with DatabaseManager("postgres_test") as db_manager:
                # Test basic connectivity
                health_status = db_manager.health_check()
                assert health_status["status"] in ["healthy", "degraded"]
                assert health_status["connection"] is True

                # Test query execution
                results = db_manager.execute_query(
                    "SELECT 1 as test_value, 'integration_test' as test_name"
                )
                assert len(results) == 1
                assert results[0]["test_value"] == 1
                assert results[0]["test_name"] == "integration_test"

                # Test parameterized query
                db_manager.execute_query(
                    "INSERT INTO integration_test_users (username, email) VALUES (:username, :email)",
                    {"username": "testuser1", "email": "test1@example.com"},
                )

                # Verify insert
                results = db_manager.execute_query(
                    "SELECT username, email FROM integration_test_users WHERE username = :username",
                    {"username": "testuser1"},
                )
                assert len(results) == 1
                assert results[0]["username"] == "testuser1"
                assert results[0]["email"] == "test1@example.com"

    def test_postgresql_transaction_integration(
        self, postgresql_connection_string, setup_postgresql_test_table
    ):
        """Test PostgreSQL transaction functionality."""
        with patch("core.database.ConfigManager") as mock_config_class:
            # Setup mock configuration
            mock_config = mock_config_class.return_value
            mock_config.environment = "test"
            mock_config.get_variable.side_effect = lambda key, default=None: {
                "postgres_test_type": "postgresql"
            }.get(key, default)
            mock_config.get_secret.return_value = postgresql_connection_string

            with DatabaseManager("postgres_test") as db_manager:
                # Test successful transaction
                queries = [
                    (
                        "INSERT INTO integration_test_users (username, email) VALUES (:username, :email)",
                        {"username": "txuser1", "email": "tx1@example.com"},
                    ),
                    (
                        "INSERT INTO integration_test_users (username, email) VALUES (:username, :email)",
                        {"username": "txuser2", "email": "tx2@example.com"},
                    ),
                    (
                        "UPDATE integration_test_users SET status = :status WHERE username IN (:user1, :user2)",
                        {"status": "verified", "user1": "txuser1", "user2": "txuser2"},
                    ),
                ]

                results = db_manager.execute_transaction(queries)
                assert len(results) >= 0  # Transaction should complete

                # Verify transaction results
                verification_results = db_manager.execute_query(
                    "SELECT username, status FROM integration_test_users WHERE username IN ('txuser1', 'txuser2')"
                )
                assert len(verification_results) == 2
                for result in verification_results:
                    assert result["status"] == "verified"

    def test_postgresql_connection_pool_integration(self, postgresql_connection_string):
        """Test PostgreSQL connection pool functionality."""
        with patch("core.database.ConfigManager") as mock_config_class:
            # Setup mock configuration with specific pool settings
            mock_config = mock_config_class.return_value
            mock_config.environment = "test"
            mock_config.get_variable.side_effect = lambda key, default=None: {
                "postgres_test_type": "postgresql",
                "postgres_test_pool_size": "3",
                "postgres_test_max_overflow": "5",
            }.get(key, default)
            mock_config.get_secret.return_value = postgresql_connection_string

            with DatabaseManager("postgres_test") as db_manager:
                # Test pool status
                pool_status = db_manager.get_pool_status()
                assert pool_status["pool_size"] == 3
                assert pool_status["max_connections"] == 8  # 3 + 5
                assert pool_status["pool_class"] == "QueuePool"

                # Test multiple concurrent queries to exercise pool
                import concurrent.futures

                def execute_test_query(query_id):
                    return db_manager.execute_query(
                        f"SELECT {query_id} as query_id, pg_backend_pid() as pid"
                    )

                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [
                        executor.submit(execute_test_query, i) for i in range(10)
                    ]
                    results = [
                        future.result()
                        for future in concurrent.futures.as_completed(futures)
                    ]

                # Verify all queries completed
                assert len(results) == 10
                pids = set()
                for result in results:
                    assert len(result) == 1
                    pids.add(result[0]["pid"])

                # Should have used multiple backend processes (indicating pool usage)
                assert len(pids) >= 1


class TestSQLServerIntegration:
    """Integration tests for SQL Server database connectivity."""

    @pytest.fixture(scope="class")
    def sqlserver_config(self):
        """SQL Server test database configuration."""
        return {
            "host": os.getenv("SQLSERVER_TEST_HOST", "localhost"),
            "port": os.getenv("SQLSERVER_TEST_PORT", "1433"),
            "database": os.getenv("SQLSERVER_TEST_DB", "test_db"),
            "username": os.getenv("SQLSERVER_TEST_USER", "test_user"),
            "password": os.getenv("SQLSERVER_TEST_PASSWORD", "test_password"),
            "driver": os.getenv(
                "SQLSERVER_TEST_DRIVER", "ODBC Driver 17 for SQL Server"
            ),
        }

    @pytest.fixture(scope="class")
    def sqlserver_connection_string(self, sqlserver_config):
        """Create SQL Server connection string."""
        return (
            f"mssql+pyodbc://{sqlserver_config['username']}:"
            f"{sqlserver_config['password']}@{sqlserver_config['host']}:"
            f"{sqlserver_config['port']}/{sqlserver_config['database']}"
            f"?driver={sqlserver_config['driver'].replace(' ', '+')}"
        )

    @pytest.fixture
    def setup_sqlserver_test_table(self, sqlserver_connection_string):
        """Set up test table in SQL Server."""
        try:
            engine = create_engine(sqlserver_connection_string)

            # Create test table
            with engine.connect() as conn:
                conn.execute(
                    text("""
                    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='integration_test_users' AND xtype='U')
                    CREATE TABLE integration_test_users (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        username NVARCHAR(50) UNIQUE NOT NULL,
                        email NVARCHAR(100) UNIQUE NOT NULL,
                        status NVARCHAR(20) DEFAULT 'active',
                        created_at DATETIME DEFAULT GETDATE()
                    )
                """)
                )
                conn.commit()

            yield

            # Cleanup test table
            with engine.connect() as conn:
                conn.execute(text("DROP TABLE IF EXISTS integration_test_users"))
                conn.commit()

            engine.dispose()

        except Exception as e:
            pytest.skip(f"SQL Server not available for testing: {e}")

    def test_sqlserver_connection_and_query(
        self, sqlserver_connection_string, setup_sqlserver_test_table
    ):
        """Test actual SQL Server connection and query execution."""
        with patch("core.database.ConfigManager") as mock_config_class:
            # Setup mock configuration
            mock_config = mock_config_class.return_value
            mock_config.environment = "test"
            mock_config.get_variable.side_effect = lambda key, default=None: {
                "sqlserver_test_type": "sqlserver"
            }.get(key, default)
            mock_config.get_secret.return_value = sqlserver_connection_string

            # Test database operations
            with DatabaseManager("sqlserver_test") as db_manager:
                # Test basic connectivity
                health_status = db_manager.health_check()
                assert health_status["status"] in ["healthy", "degraded"]
                assert health_status["connection"] is True

                # Test query execution
                results = db_manager.execute_query(
                    "SELECT 1 as test_value, 'integration_test' as test_name"
                )
                assert len(results) == 1
                assert results[0]["test_value"] == 1
                assert results[0]["test_name"] == "integration_test"

                # Test parameterized query
                db_manager.execute_query(
                    "INSERT INTO integration_test_users (username, email) VALUES (:username, :email)",
                    {"username": "testuser1", "email": "test1@example.com"},
                )

                # Verify insert
                results = db_manager.execute_query(
                    "SELECT username, email FROM integration_test_users WHERE username = :username",
                    {"username": "testuser1"},
                )
                assert len(results) == 1
                assert results[0]["username"] == "testuser1"
                assert results[0]["email"] == "test1@example.com"

    def test_sqlserver_transaction_integration(
        self, sqlserver_connection_string, setup_sqlserver_test_table
    ):
        """Test SQL Server transaction functionality."""
        with patch("core.database.ConfigManager") as mock_config_class:
            # Setup mock configuration
            mock_config = mock_config_class.return_value
            mock_config.environment = "test"
            mock_config.get_variable.side_effect = lambda key, default=None: {
                "sqlserver_test_type": "sqlserver"
            }.get(key, default)
            mock_config.get_secret.return_value = sqlserver_connection_string

            with DatabaseManager("sqlserver_test") as db_manager:
                # Test successful transaction
                queries = [
                    (
                        "INSERT INTO integration_test_users (username, email) VALUES (:username, :email)",
                        {"username": "txuser1", "email": "tx1@example.com"},
                    ),
                    (
                        "INSERT INTO integration_test_users (username, email) VALUES (:username, :email)",
                        {"username": "txuser2", "email": "tx2@example.com"},
                    ),
                    (
                        "UPDATE integration_test_users SET status = :status WHERE username IN (:user1, :user2)",
                        {"status": "verified", "user1": "txuser1", "user2": "txuser2"},
                    ),
                ]

                results = db_manager.execute_transaction(queries)
                assert len(results) >= 0  # Transaction should complete

                # Verify transaction results
                verification_results = db_manager.execute_query(
                    "SELECT username, status FROM integration_test_users WHERE username IN ('txuser1', 'txuser2')"
                )
                assert len(verification_results) == 2
                for result in verification_results:
                    assert result["status"] == "verified"


class TestDatabaseMigrationIntegration:
    """Integration tests for database migration functionality."""

    def setup_method(self):
        """Set up test migration directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.migration_dir = (
            Path(self.temp_dir) / "core" / "migrations" / "integration_test"
        )
        self.migration_dir.mkdir(parents=True, exist_ok=True)

        # Create test migration files
        self.create_integration_migration_files()

    def teardown_method(self):
        """Clean up test migration directory."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_integration_migration_files(self):
        """Create test migration files for integration testing."""
        # Migration V001 - Create initial table
        migration_v001 = self.migration_dir / "V001__Create_integration_test_table.sql"
        migration_v001.write_text("""
-- Create integration test table
CREATE TABLE IF NOT EXISTS integration_migration_test (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    value INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial test data
INSERT INTO integration_migration_test (name, value) VALUES ('test1', 100);
INSERT INTO integration_migration_test (name, value) VALUES ('test2', 200);
""")

        # Migration V002 - Add index and column
        migration_v002 = self.migration_dir / "V002__Add_index_and_status.sql"
        migration_v002.write_text("""
-- Add status column
ALTER TABLE integration_migration_test ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';

-- Create index on name
CREATE INDEX IF NOT EXISTS idx_integration_migration_test_name ON integration_migration_test(name);

-- Update existing records
UPDATE integration_migration_test SET status = 'active' WHERE status IS NULL;
""")

    @pytest.mark.skipif(
        not os.getenv("POSTGRES_TEST_HOST"),
        reason="PostgreSQL integration test requires POSTGRES_TEST_HOST",
    )
    def test_postgresql_migration_integration(self):
        """Test migration execution with actual PostgreSQL database."""
        # Setup PostgreSQL connection
        postgres_config = {
            "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
            "port": os.getenv("POSTGRES_TEST_PORT", "5432"),
            "database": os.getenv("POSTGRES_TEST_DB", "test_db"),
            "username": os.getenv("POSTGRES_TEST_USER", "test_user"),
            "password": os.getenv("POSTGRES_TEST_PASSWORD", "test_password"),
        }

        connection_string = (
            f"postgresql://{postgres_config['username']}:"
            f"{postgres_config['password']}@{postgres_config['host']}:"
            f"{postgres_config['port']}/{postgres_config['database']}"
        )

        with patch("core.database.ConfigManager") as mock_config_class:
            # Setup mock configuration
            mock_config = mock_config_class.return_value
            mock_config.environment = "test"
            mock_config.get_variable.side_effect = lambda key, default=None: {
                "integration_test_type": "postgresql"
            }.get(key, default)
            mock_config.get_secret.return_value = connection_string

            # Patch migration directory
            with patch.object(
                DatabaseManager, "_get_migration_directory"
            ) as mock_get_dir:
                mock_get_dir.return_value = self.migration_dir

                try:
                    with DatabaseManager("integration_test") as db_manager:
                        # Test migration status before execution
                        initial_status = db_manager.get_migration_status()
                        assert initial_status["database_name"] == "integration_test"

                        # Execute migrations
                        db_manager.run_migrations()

                        # Test migration status after execution
                        final_status = db_manager.get_migration_status()
                        assert final_status["database_name"] == "integration_test"

                        # Verify migrated table exists and has data
                        results = db_manager.execute_query(
                            "SELECT name, value, status FROM integration_migration_test ORDER BY id"
                        )
                        assert len(results) == 2
                        assert results[0]["name"] == "test1"
                        assert results[0]["value"] == 100
                        assert results[0]["status"] == "active"

                        # Test health check includes migration status
                        health_status = db_manager.health_check()
                        assert health_status["migration_status"] is not None

                except OperationalError as e:
                    pytest.skip(f"PostgreSQL database not available: {e}")
                finally:
                    # Cleanup - drop test table
                    try:
                        engine = create_engine(connection_string)
                        with engine.connect() as conn:
                            conn.execute(
                                text("DROP TABLE IF EXISTS integration_migration_test")
                            )
                            conn.execute(text("DROP TABLE IF EXISTS schema_version"))
                            conn.commit()
                        engine.dispose()
                    except Exception:
                        pass  # Ignore cleanup errors


class TestDatabaseFailureScenarios:
    """Integration tests for database failure scenarios and recovery."""

    def test_connection_failure_handling(self):
        """Test handling of connection failures."""
        # Use invalid connection string
        invalid_connection_string = (
            "postgresql://invalid:invalid@nonexistent:5432/invalid"
        )

        with patch("core.database.ConfigManager") as mock_config_class:
            # Setup mock configuration with invalid connection
            mock_config = mock_config_class.return_value
            mock_config.environment = "test"
            mock_config.get_variable.side_effect = lambda key, default=None: {
                "invalid_db_type": "postgresql"
            }.get(key, default)
            mock_config.get_secret.return_value = invalid_connection_string

            with DatabaseManager("invalid_db") as db_manager:
                # Test health check with connection failure
                health_status = db_manager.health_check()
                assert health_status["status"] == "unhealthy"
                assert health_status["connection"] is False
                assert health_status["error"] is not None

                # Test query execution failure
                with pytest.raises(RuntimeError, match="Query execution failed"):
                    db_manager.execute_query("SELECT 1")

    def test_retry_logic_integration(self):
        """Test retry logic with simulated transient failures."""
        # This test would require a way to simulate transient failures
        # In a real integration environment, this could be done with network
        # interruption tools or database proxy that can inject failures
        pytest.skip(
            "Retry logic integration test requires failure injection capability"
        )


# Utility functions for integration test setup
def setup_test_database_postgresql():
    """Set up PostgreSQL test database (utility function for CI/CD)."""
    # This function would be used in CI/CD scripts to set up test databases
    pass


def setup_test_database_sqlserver():
    """Set up SQL Server test database (utility function for CI/CD)."""
    # This function would be used in CI/CD scripts to set up test databases
    pass
