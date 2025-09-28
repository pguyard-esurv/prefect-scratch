"""
Pytest configuration and fixtures for DatabaseManager tests.

This module provides shared fixtures and configuration for all DatabaseManager tests.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_config_manager():
    """Provide a mock ConfigManager for testing."""
    with patch("core.database.ConfigManager") as mock_config_class:
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "test"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql",
            "test_db_pool_size": "5",
            "test_db_max_overflow": "10",
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://test:test@localhost:5432/test_db"
        )
        yield mock_config


@pytest.fixture
def mock_sqlalchemy_engine():
    """Provide a mock SQLAlchemy engine for testing."""
    with patch("core.database.create_engine") as mock_create_engine:
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup default pool mock
        mock_pool = Mock()
        mock_engine.pool = mock_pool
        mock_pool.size.return_value = 5
        mock_pool.checkedin.return_value = 3
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 0
        mock_pool.invalid.return_value = 0
        mock_pool._max_overflow = 10
        mock_pool.__class__.__name__ = "QueuePool"

        yield mock_engine


@pytest.fixture
def mock_database_connection():
    """Provide a mock database connection for testing."""
    mock_conn = Mock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    # Setup default query result
    mock_result = Mock()
    mock_conn.execute.return_value = mock_result
    mock_row = Mock()
    mock_row._mapping = {"id": 1, "name": "test"}
    mock_result.fetchall.return_value = [mock_row]

    return mock_conn


@pytest.fixture
def temp_migration_directory():
    """Provide a temporary migration directory for testing."""
    temp_dir = tempfile.mkdtemp()
    migration_dir = Path(temp_dir) / "core" / "migrations" / "test_db"
    migration_dir.mkdir(parents=True, exist_ok=True)

    yield migration_dir

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_migration_files(temp_migration_directory):
    """Create sample migration files for testing."""
    migrations = []

    # Migration V001
    migration_v001 = temp_migration_directory / "V001__Create_test_table.sql"
    migration_v001.write_text("""
-- Create test table
CREATE TABLE IF NOT EXISTS test_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO test_table (name) VALUES ('test1');
""")
    migrations.append(migration_v001)

    # Migration V002
    migration_v002 = temp_migration_directory / "V002__Add_index.sql"
    migration_v002.write_text("""
-- Add index to test table
CREATE INDEX IF NOT EXISTS idx_test_table_name ON test_table(name);

ALTER TABLE test_table ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'active';
""")
    migrations.append(migration_v002)

    return migrations


# Test markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests for individual components")
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring actual databases"
    )
    config.addinivalue_line(
        "markers", "performance: Performance tests that may take longer to run"
    )
    config.addinivalue_line("markers", "slow: Slow running tests")


# Skip integration tests by default
def pytest_collection_modifyitems(config, items):
    """Modify test collection to handle integration test skipping."""
    if not config.getoption("--run-integration"):
        skip_integration = pytest.mark.skip(
            reason="need --run-integration option to run"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests",
    )
    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="run performance tests",
    )


# Environment-specific fixtures
@pytest.fixture
def postgresql_available():
    """Check if PostgreSQL is available for testing."""
    try:
        import psycopg2

        # Try to connect to test database
        host = os.getenv("POSTGRES_TEST_HOST", "localhost")
        port = os.getenv("POSTGRES_TEST_PORT", "5432")
        database = os.getenv("POSTGRES_TEST_DB", "test_db")
        username = os.getenv("POSTGRES_TEST_USER", "test_user")
        password = os.getenv("POSTGRES_TEST_PASSWORD", "test_password")

        conn = psycopg2.connect(
            host=host, port=port, database=database, user=username, password=password
        )
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture
def sqlserver_available():
    """Check if SQL Server is available for testing."""
    try:
        import pyodbc

        # Try to connect to test database
        host = os.getenv("SQLSERVER_TEST_HOST", "localhost")
        port = os.getenv("SQLSERVER_TEST_PORT", "1433")
        database = os.getenv("SQLSERVER_TEST_DB", "test_db")
        username = os.getenv("SQLSERVER_TEST_USER", "test_user")
        password = os.getenv("SQLSERVER_TEST_PASSWORD", "test_password")
        driver = os.getenv("SQLSERVER_TEST_DRIVER", "ODBC Driver 17 for SQL Server")

        conn_str = (
            f"DRIVER={{{driver}}};"
            f"SERVER={host},{port};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password}"
        )
        conn = pyodbc.connect(conn_str)
        conn.close()
        return True
    except Exception:
        return False
