"""
Unit tests for DatabaseManager class foundation.

Tests cover initialization, logger setup, context manager behavior,
configuration integration, and error handling scenarios.
"""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import TimeoutError as SQLTimeoutError
from sqlalchemy.pool import QueuePool

from core.database import DatabaseManager


class TestDatabaseManagerInitialization:
    """Test DatabaseManager initialization and basic functionality."""

    def test_init_with_valid_database_name(self):
        """Test successful initialization with valid database name."""
        db_manager = DatabaseManager("test_db")

        assert db_manager.database_name == "test_db"
        assert db_manager.engine is None
        assert db_manager._logger is not None
        assert db_manager._config_manager is None

    def test_init_with_empty_database_name(self):
        """Test initialization fails with empty database name."""
        with pytest.raises(
            ValueError, match="database_name must be a non-empty string"
        ):
            DatabaseManager("")

    def test_init_with_none_database_name(self):
        """Test initialization fails with None database name."""
        with pytest.raises(
            ValueError, match="database_name must be a non-empty string"
        ):
            DatabaseManager(None)

    def test_init_with_non_string_database_name(self):
        """Test initialization fails with non-string database name."""
        with pytest.raises(
            ValueError, match="database_name must be a non-empty string"
        ):
            DatabaseManager(123)

    def test_init_with_whitespace_only_database_name(self):
        """Test initialization fails with whitespace-only database name."""
        with pytest.raises(
            ValueError, match="database_name must be a non-empty string"
        ):
            DatabaseManager("   ")


class TestDatabaseManagerLogger:
    """Test DatabaseManager logger initialization and behavior."""

    @patch("prefect.get_run_logger")
    def test_logger_initialization_with_prefect(self, mock_get_run_logger):
        """Test logger initialization uses Prefect logger when available."""
        mock_prefect_logger = Mock()
        mock_get_run_logger.return_value = mock_prefect_logger

        db_manager = DatabaseManager("test_db")

        assert db_manager._logger == mock_prefect_logger
        mock_prefect_logger.info.assert_called_once_with(
            "DatabaseManager initialized for 'test_db' with Prefect logger"
        )

    @patch("prefect.get_run_logger")
    def test_logger_initialization_prefect_import_error(self, mock_get_run_logger):
        """Test logger falls back to standard logging when Prefect import fails."""
        mock_get_run_logger.side_effect = ImportError("Prefect not available")

        with patch("core.database.logging.getLogger") as mock_get_logger:
            mock_standard_logger = Mock()
            mock_get_logger.return_value = mock_standard_logger
            mock_standard_logger.handlers = []

            db_manager = DatabaseManager("test_db")

            mock_get_logger.assert_called_once_with("DatabaseManager.test_db")
            assert db_manager._logger == mock_standard_logger

    @patch("prefect.get_run_logger")
    def test_logger_initialization_prefect_runtime_error(self, mock_get_run_logger):
        """Test logger falls back to standard logging when Prefect runtime error occurs."""
        mock_get_run_logger.side_effect = RuntimeError("Not in task context")

        with patch("core.database.logging.getLogger") as mock_get_logger:
            mock_standard_logger = Mock()
            mock_get_logger.return_value = mock_standard_logger
            mock_standard_logger.handlers = []

            db_manager = DatabaseManager("test_db")

            mock_get_logger.assert_called_once_with("DatabaseManager.test_db")
            assert db_manager._logger == mock_standard_logger

    def test_logger_property_returns_initialized_logger(self):
        """Test logger property returns the initialized logger."""
        db_manager = DatabaseManager("test_db")
        logger1 = db_manager.logger
        logger2 = db_manager.logger

        assert logger1 is logger2  # Should return same instance
        assert logger1 is not None

    def test_logger_property_initializes_if_none(self):
        """Test logger property initializes logger if it's None."""
        db_manager = DatabaseManager("test_db")
        original_logger = db_manager._logger
        db_manager._logger = None

        with patch.object(db_manager, "_initialize_logger") as mock_init:

            def restore_logger():
                db_manager._logger = original_logger

            mock_init.side_effect = restore_logger

            logger = db_manager.logger

            mock_init.assert_called_once()
            assert logger is not None


class TestDatabaseManagerContextManager:
    """Test DatabaseManager context manager functionality."""

    def test_context_manager_enter(self):
        """Test context manager __enter__ method."""
        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        result = db_manager.__enter__()

        assert result is db_manager
        mock_logger.debug.assert_called_once_with(
            "Entering context manager for database 'test_db'"
        )

    def test_context_manager_exit_no_exception(self):
        """Test context manager __exit__ method with no exception."""
        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        db_manager.__exit__(None, None, None)

        mock_logger.debug.assert_called_with(
            "Exited context manager for database 'test_db'"
        )
        mock_logger.error.assert_not_called()

    def test_context_manager_exit_with_exception(self):
        """Test context manager __exit__ method with exception."""
        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        exc_type = ValueError
        exc_val = ValueError("Test error")
        exc_tb = None

        db_manager.__exit__(exc_type, exc_val, exc_tb)

        mock_logger.error.assert_called_with(
            "Exception occurred in DatabaseManager context for 'test_db': "
            "ValueError: Test error"
        )

    def test_context_manager_exit_disposes_engine(self):
        """Test context manager __exit__ disposes engine if present."""
        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger
        mock_engine = Mock()
        db_manager.engine = mock_engine

        db_manager.__exit__(None, None, None)

        mock_engine.dispose.assert_called_once()
        assert db_manager.engine is None
        mock_logger.debug.assert_any_call("Disposing engine for database 'test_db'")

    def test_context_manager_exit_no_engine_disposal_if_none(self):
        """Test context manager __exit__ doesn't dispose if engine is None."""
        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger
        db_manager.engine = None

        db_manager.__exit__(None, None, None)

        # Should not call dispose or log disposal message
        debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
        assert not any("Disposing engine" in call for call in debug_calls)

    def test_context_manager_exit_handles_cleanup_error(self):
        """Test context manager __exit__ handles cleanup errors gracefully."""
        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger
        mock_engine = Mock()
        mock_engine.dispose.side_effect = Exception("Cleanup error")
        db_manager.engine = mock_engine

        # Should not raise exception even if cleanup fails
        db_manager.__exit__(None, None, None)

        mock_logger.error.assert_called_with(
            "Error during cleanup for database 'test_db': Cleanup error"
        )

    def test_context_manager_full_usage(self):
        """Test full context manager usage pattern."""
        with DatabaseManager("test_db") as db_manager:
            assert isinstance(db_manager, DatabaseManager)
            assert db_manager.database_name == "test_db"

    def test_context_manager_with_exception_in_block(self):
        """Test context manager handles exceptions in with block."""
        with pytest.raises(ValueError):
            with DatabaseManager("test_db"):
                # Simulate an exception in the with block
                raise ValueError("Test exception in block")


class TestDatabaseManagerErrorHandling:
    """Test DatabaseManager error handling scenarios."""

    def test_logger_initialization_with_existing_handlers(self):
        """Test logger initialization when handlers already exist."""
        with patch("prefect.get_run_logger") as mock_get_run_logger:
            mock_get_run_logger.side_effect = ImportError("No Prefect")

            with patch("core.database.logging.getLogger") as mock_get_logger:
                mock_standard_logger = Mock()
                mock_standard_logger.handlers = [Mock()]  # Existing handler
                mock_get_logger.return_value = mock_standard_logger

                DatabaseManager("test_db")

                # Should not add new handlers if they already exist
                mock_standard_logger.addHandler.assert_not_called()
                mock_standard_logger.setLevel.assert_not_called()

    def test_multiple_logger_initializations(self):
        """Test that logger is only initialized once."""
        db_manager = DatabaseManager("test_db")
        original_logger = db_manager._logger

        # Call initialize again
        db_manager._initialize_logger()

        # Should be the same logger instance
        assert db_manager._logger is original_logger


class TestDatabaseManagerConfigurationIntegration:
    """Test DatabaseManager configuration integration with ConfigManager."""

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_initialize_engine_success_postgresql(
        self, mock_create_engine, mock_config_class
    ):
        """Test successful engine initialization for PostgreSQL."""
        # Setup mock ConfigManager
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql",
            "test_db_pool_size": "5",
            "test_db_max_overflow": "10",
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        # Setup mock engine
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        db_manager = DatabaseManager("test_db")
        db_manager._initialize_engine()

        # Verify ConfigManager was created
        mock_config_class.assert_called_once()

        # Verify configuration was loaded correctly
        mock_config.get_variable.assert_any_call("test_db_type")
        mock_config.get_secret.assert_called_once_with("test_db_connection_string")

        # Verify engine was created with correct parameters
        mock_create_engine.assert_called_once_with(
            "postgresql://user:pass@localhost:5432/test_db",
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )

        assert db_manager.engine == mock_engine

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_initialize_engine_success_sqlserver(
        self, mock_create_engine, mock_config_class
    ):
        """Test successful engine initialization for SQL Server."""
        # Setup mock ConfigManager
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "production"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "survey_hub_type": "sqlserver",
            "survey_hub_pool_size": "8",
            "survey_hub_max_overflow": "15",
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "mssql+pyodbc://user:pass@server:1433/survey_hub"
        )

        # Setup mock engine
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        db_manager = DatabaseManager("survey_hub")
        db_manager._initialize_engine()

        # Verify engine was created with correct parameters
        mock_create_engine.assert_called_once_with(
            "mssql+pyodbc://user:pass@server:1433/survey_hub",
            poolclass=QueuePool,
            pool_size=8,
            max_overflow=15,
            pool_pre_ping=True,
            echo=False,
        )

        assert db_manager.engine == mock_engine

    @patch("core.database.ConfigManager")
    def test_initialize_engine_missing_database_type(self, mock_config_class):
        """Test engine initialization fails when database type is missing."""
        # Setup mock ConfigManager with missing type
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.return_value = None  # Missing type
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError, match="Database type not configured for 'test_db'"
        ):
            db_manager._initialize_engine()

    @patch("core.database.ConfigManager")
    def test_initialize_engine_missing_connection_string(self, mock_config_class):
        """Test engine initialization fails when connection string is missing."""
        # Setup mock ConfigManager with missing connection string
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.return_value = "postgresql"
        mock_config.get_secret.return_value = None  # Missing connection string

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError, match="Connection string not configured for 'test_db'"
        ):
            db_manager._initialize_engine()

    @patch("core.database.ConfigManager")
    def test_initialize_engine_unsupported_database_type(self, mock_config_class):
        """Test engine initialization fails with unsupported database type."""
        # Setup mock ConfigManager with unsupported type
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.return_value = "mysql"  # Unsupported type
        mock_config.get_secret.return_value = "mysql://user:pass@localhost:3306/test_db"

        db_manager = DatabaseManager("test_db")

        with pytest.raises(RuntimeError, match="Unsupported database type 'mysql'"):
            db_manager._initialize_engine()

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_initialize_engine_with_default_pool_settings(
        self, mock_create_engine, mock_config_class
    ):
        """Test engine initialization uses default pool settings when not configured."""
        # Setup mock ConfigManager with minimal configuration
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        # Setup mock engine
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        db_manager = DatabaseManager("test_db")
        db_manager._initialize_engine()

        # Verify engine was created with default pool settings
        mock_create_engine.assert_called_once_with(
            "postgresql://user:pass@localhost:5432/test_db",
            poolclass=QueuePool,
            pool_size=5,  # Default
            max_overflow=10,  # Default
            pool_pre_ping=True,
            echo=False,
        )

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_initialize_engine_sqlalchemy_error(
        self, mock_create_engine, mock_config_class
    ):
        """Test engine initialization handles SQLAlchemy errors."""
        # Setup mock ConfigManager
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        # Setup create_engine to raise an exception
        mock_create_engine.side_effect = Exception("SQLAlchemy connection error")

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError, match="Failed to initialize engine for database 'test_db'"
        ):
            db_manager._initialize_engine()

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_initialize_engine_idempotent(self, mock_create_engine, mock_config_class):
        """Test that engine initialization is idempotent."""
        # Setup mock ConfigManager
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        # Setup mock engine
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        db_manager = DatabaseManager("test_db")

        # Initialize engine twice
        db_manager._initialize_engine()
        first_engine = db_manager.engine

        db_manager._initialize_engine()
        second_engine = db_manager.engine

        # Should be the same engine instance
        assert first_engine is second_engine
        # create_engine should only be called once
        mock_create_engine.assert_called_once()

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_db_engine_property_initializes_engine(
        self, mock_create_engine, mock_config_class
    ):
        """Test that db_engine property initializes engine on first access."""
        # Setup mock ConfigManager
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        # Setup mock engine
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        db_manager = DatabaseManager("test_db")

        # Engine should be None initially
        assert db_manager.engine is None

        # Accessing db_engine property should initialize engine
        engine = db_manager.db_engine

        assert engine == mock_engine
        assert db_manager.engine == mock_engine
        mock_create_engine.assert_called_once()

    @patch("core.database.ConfigManager")
    def test_configuration_error_messages_include_environment_variables(
        self, mock_config_class
    ):
        """Test that configuration error messages include proper environment variable names."""
        # Setup mock ConfigManager
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "staging"
        mock_config.get_variable.return_value = None  # Missing type
        mock_config.get_secret.return_value = None

        db_manager = DatabaseManager("my_database")

        with pytest.raises(RuntimeError) as exc_info:
            db_manager._initialize_engine()

        error_message = str(exc_info.value)
        assert "STAGING_GLOBAL_MY_DATABASE_TYPE" in error_message

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_initialize_engine_logs_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test that successful engine initialization is logged."""
        # Setup mock ConfigManager
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql",
            "test_db_pool_size": "5",
            "test_db_max_overflow": "10",
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        # Setup mock engine
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        db_manager._initialize_engine()

        # Verify success was logged
        mock_logger.info.assert_called_with(
            "Created SQLAlchemy engine for 'test_db' "
            "(type: postgresql, pool_size: 5, max_overflow: 10)"
        )

    @patch("core.database.ConfigManager")
    def test_initialize_engine_logs_errors(self, mock_config_class):
        """Test that engine initialization errors are logged."""
        # Setup mock ConfigManager to cause an error
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.return_value = None  # This will cause an error

        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        with pytest.raises(RuntimeError):
            db_manager._initialize_engine()

        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_call = mock_logger.error.call_args[0][0]
        assert "Failed to initialize engine for database 'test_db'" in error_call


class TestDatabaseManagerQueryExecution:
    """Test DatabaseManager query execution functionality."""

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_success(self, mock_create_engine, mock_config_class):
        """Test successful query execution."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and result mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result

        # Mock result rows
        mock_row1 = Mock()
        mock_row1._mapping = {"id": 1, "name": "test1"}
        mock_row2 = Mock()
        mock_row2._mapping = {"id": 2, "name": "test2"}
        mock_result.fetchall.return_value = [mock_row1, mock_row2]

        db_manager = DatabaseManager("test_db")
        results = db_manager.execute_query(
            "SELECT * FROM test_table", {"param": "value"}
        )

        assert results == [{"id": 1, "name": "test1"}, {"id": 2, "name": "test2"}]
        mock_conn.execute.assert_called_once()

    def test_execute_query_invalid_query(self):
        """Test execute_query with invalid query parameter."""
        db_manager = DatabaseManager("test_db")

        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            db_manager.execute_query("")

        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            db_manager.execute_query(None)

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_database_error(self, mock_create_engine, mock_config_class):
        """Test execute_query handles database errors."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection to raise error
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.execute.side_effect = SQLAlchemyError("Database connection failed")

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError, match="Query execution failed for database 'test_db'"
        ):
            db_manager.execute_query("SELECT * FROM test_table")


class TestDatabaseManagerQueryWithTimeout:
    """Test DatabaseManager query execution with timeout functionality."""

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_with_timeout_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test successful query execution with timeout."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and result mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.execution_options.return_value = mock_conn

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result

        # Mock result rows
        mock_row = Mock()
        mock_row._mapping = {"id": 1, "name": "test"}
        mock_result.fetchall.return_value = [mock_row]

        db_manager = DatabaseManager("test_db")
        results = db_manager.execute_query_with_timeout(
            "SELECT * FROM test_table", {"param": "value"}, timeout=60
        )

        assert results == [{"id": 1, "name": "test"}]
        mock_conn.execute.assert_called_once()

    def test_execute_query_with_timeout_invalid_parameters(self):
        """Test execute_query_with_timeout with invalid parameters."""
        db_manager = DatabaseManager("test_db")

        # Test invalid query
        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            db_manager.execute_query_with_timeout("", timeout=30)

        # Test invalid timeout
        with pytest.raises(ValueError, match="Timeout must be a positive integer"):
            db_manager.execute_query_with_timeout("SELECT 1", timeout=0)

        with pytest.raises(ValueError, match="Timeout must be a positive integer"):
            db_manager.execute_query_with_timeout("SELECT 1", timeout=-5)

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_with_timeout_timeout_error(
        self, mock_create_engine, mock_config_class
    ):
        """Test execute_query_with_timeout handles timeout errors."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection to raise timeout error
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.execute.side_effect = SQLTimeoutError("Query timeout", None, None)

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError,
            match="Query timeout \\(30s\\) exceeded for database 'test_db'",
        ):
            db_manager.execute_query_with_timeout(
                "SELECT * FROM large_table", timeout=30
            )

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_with_timeout_general_error(
        self, mock_create_engine, mock_config_class
    ):
        """Test execute_query_with_timeout handles general errors."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection to raise general error
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.execution_options.return_value = mock_conn
        mock_conn.execute.side_effect = SQLAlchemyError("Database error")

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError,
            match="Query execution with timeout failed for database 'test_db'",
        ):
            db_manager.execute_query_with_timeout(
                "SELECT * FROM test_table", timeout=30
            )


class TestDatabaseManagerTransactionExecution:
    """Test DatabaseManager transaction execution functionality."""

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_transaction_success(self, mock_create_engine, mock_config_class):
        """Test successful transaction execution."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and transaction mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_transaction = Mock()
        mock_conn.begin.return_value = mock_transaction
        mock_transaction.__enter__ = Mock(return_value=mock_transaction)
        mock_transaction.__exit__ = Mock(return_value=None)

        # Setup results for multiple queries
        mock_result1 = Mock()
        mock_result2 = Mock()

        mock_row1 = Mock()
        mock_row1._mapping = {"id": 1}
        mock_row2 = Mock()
        mock_row2._mapping = {"affected_rows": 1}

        mock_result1.fetchall.return_value = [mock_row1]
        mock_result2.fetchall.return_value = [mock_row2]

        mock_conn.execute.side_effect = [mock_result1, mock_result2]

        db_manager = DatabaseManager("test_db")

        queries = [
            ("INSERT INTO users (name) VALUES (:name)", {"name": "John"}),
            ("UPDATE users SET active = true WHERE name = :name", {"name": "John"}),
        ]

        results = db_manager.execute_transaction(queries)

        assert results == [{"id": 1}, {"affected_rows": 1}]
        assert mock_conn.execute.call_count == 2

    def test_execute_transaction_invalid_parameters(self):
        """Test execute_transaction with invalid parameters."""
        db_manager = DatabaseManager("test_db")

        # Test empty queries list
        with pytest.raises(ValueError, match="Queries must be a non-empty list"):
            db_manager.execute_transaction([])

        # Test None queries
        with pytest.raises(ValueError, match="Queries must be a non-empty list"):
            db_manager.execute_transaction(None)

        # Test invalid query tuple format
        with pytest.raises(ValueError, match="Query at index 0 must be a tuple"):
            db_manager.execute_transaction(["invalid"])

        # Test tuple with wrong length
        with pytest.raises(ValueError, match="Query at index 0 must be a tuple"):
            db_manager.execute_transaction([("query",)])

        # Test invalid query string
        with pytest.raises(
            ValueError, match="Query string at index 0 must be a non-empty string"
        ):
            db_manager.execute_transaction([(None, {})])

        # Test invalid parameters type
        with pytest.raises(
            ValueError, match="Parameters at index 0 must be a dictionary or None"
        ):
            db_manager.execute_transaction([("SELECT 1", "invalid")])

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_transaction_rollback_on_error(
        self, mock_create_engine, mock_config_class
    ):
        """Test transaction rollback when error occurs."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection to raise error during transaction
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_transaction = Mock()
        mock_conn.begin.return_value = mock_transaction
        mock_transaction.__enter__ = Mock(return_value=mock_transaction)
        mock_transaction.__exit__ = Mock(return_value=None)

        # First query succeeds, second fails
        mock_result1 = Mock()
        mock_row1 = Mock()
        mock_row1._mapping = {"id": 1}
        mock_result1.fetchall.return_value = [mock_row1]

        mock_conn.execute.side_effect = [
            mock_result1,
            SQLAlchemyError("Constraint violation"),
        ]

        db_manager = DatabaseManager("test_db")

        queries = [
            ("INSERT INTO users (name) VALUES (:name)", {"name": "John"}),
            (
                "INSERT INTO users (name) VALUES (:name)",
                {"name": "John"},
            ),  # Duplicate, should fail
        ]

        with pytest.raises(
            RuntimeError,
            match="Transaction execution failed.*All changes have been rolled back",
        ):
            db_manager.execute_transaction(queries)

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_transaction_with_none_params(
        self, mock_create_engine, mock_config_class
    ):
        """Test transaction execution with None parameters."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and transaction mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_transaction = Mock()
        mock_conn.begin.return_value = mock_transaction
        mock_transaction.__enter__ = Mock(return_value=mock_transaction)
        mock_transaction.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_row = Mock()
        mock_row._mapping = {"count": 5}
        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result

        db_manager = DatabaseManager("test_db")

        queries = [("SELECT COUNT(*) as count FROM users", None)]

        results = db_manager.execute_transaction(queries)

        assert results == [{"count": 5}]
        mock_conn.execute.assert_called_once()

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_transaction_empty_results(
        self, mock_create_engine, mock_config_class
    ):
        """Test transaction execution with queries that return no results."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and transaction mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_transaction = Mock()
        mock_conn.begin.return_value = mock_transaction
        mock_transaction.__enter__ = Mock(return_value=mock_transaction)
        mock_transaction.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_result.fetchall.return_value = []  # No results
        mock_conn.execute.return_value = mock_result

        db_manager = DatabaseManager("test_db")

        queries = [("DELETE FROM users WHERE active = false", {})]

        results = db_manager.execute_transaction(queries)

        assert results == []
        mock_conn.execute.assert_called_once()


class TestDatabaseManagerMigrations:
    """Test DatabaseManager migration functionality using Pyway."""

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    @patch("core.database.Migrate")
    @patch("core.database.ConfigFile")
    def test_run_migrations_success(
        self, mock_config_file_class, mock_pyway_class, mock_create_engine, mock_config_class
    ):
        """Test successful migration execution."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"
        mock_create_engine.return_value = mock_engine

        # Setup ConfigFile mock
        mock_config_file = Mock()
        mock_config_file_class.return_value = mock_config_file

        # Setup Pyway mock
        mock_pyway = Mock()
        mock_pyway_class.return_value = mock_pyway
        mock_pyway.migrate.return_value = [
            {"version": "V001", "description": "Create test table"},
            {"version": "V002", "description": "Add test index"},
        ]

        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        # Mock migration directory exists
        mock_migration_dir = Mock()
        mock_migration_dir.exists.return_value = True

        with patch.object(
            db_manager, "_get_migration_directory", return_value=mock_migration_dir
        ):
            db_manager.run_migrations()

            # Verify ConfigFile was created correctly
            mock_config_file_class.assert_called_once_with(
                database_type="postgresql",
                database_host="localhost",
                database_port=5432,
                database_name="test_db",
                database_username="user",
                database_password="pass",
                database_migration_dir=str(mock_migration_dir),
                database_table="schema_version"
            )

            # Verify Pyway was initialized with ConfigFile
            mock_pyway_class.assert_called_once_with(mock_config_file)

            # Verify migrate was called
            mock_pyway.migrate.assert_called_once()

            # Verify success logging
            mock_logger.info.assert_any_call(
                "Migrations executed successfully for database 'test_db'. Applied 2 migrations."
            )

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    @patch("core.database.Migrate")
    def test_run_migrations_no_pending(
        self, mock_pyway_class, mock_create_engine, mock_config_class
    ):
        """Test migration execution when no pending migrations exist."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"
        mock_create_engine.return_value = mock_engine

        # Setup Pyway mock with no migrations
        mock_pyway = Mock()
        mock_pyway_class.return_value = mock_pyway
        mock_pyway.migrate.return_value = []

        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        # Mock migration directory exists
        mock_migration_dir = Mock()
        mock_migration_dir.exists.return_value = True

        with patch.object(
            db_manager, "_get_migration_directory", return_value=mock_migration_dir
        ):
            db_manager.run_migrations()

            # Verify no pending migrations message
            mock_logger.info.assert_any_call(
                "No pending migrations found for database 'test_db'"
            )

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    @patch("core.database.Migrate")
    def test_run_migrations_creates_directory_if_missing(
        self, mock_pyway_class, mock_create_engine, mock_config_class
    ):
        """Test migration execution creates directory if it doesn't exist."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"
        mock_create_engine.return_value = mock_engine

        # Setup Pyway mock
        mock_pyway = Mock()
        mock_pyway_class.return_value = mock_pyway
        mock_pyway.migrate.return_value = []

        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        # Mock migration directory doesn't exist initially
        mock_migration_dir = Mock()
        mock_migration_dir.exists.return_value = False

        with patch.object(
            db_manager, "_get_migration_directory", return_value=mock_migration_dir
        ):
            db_manager.run_migrations()

            # Verify directory creation was attempted
            mock_migration_dir.mkdir.assert_called_once_with(
                parents=True, exist_ok=True
            )

            # Verify warning was logged
            mock_logger.warning.assert_called_with(
                f"Migration directory '{mock_migration_dir}' does not exist for "
                f"database 'test_db'. Creating directory."
            )

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    @patch("core.database.Migrate")
    def test_run_migrations_pyway_error(
        self, mock_pyway_class, mock_create_engine, mock_config_class
    ):
        """Test migration execution handles Pyway errors."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"
        mock_create_engine.return_value = mock_engine

        # Setup Pyway mock to raise error
        mock_pyway = Mock()
        mock_pyway_class.return_value = mock_pyway
        mock_pyway.migrate.side_effect = Exception("Migration failed")

        db_manager = DatabaseManager("test_db")

        # Mock migration directory exists
        mock_migration_dir = Mock()
        mock_migration_dir.exists.return_value = True

        with patch.object(
            db_manager, "_get_migration_directory", return_value=mock_migration_dir
        ):
            with pytest.raises(
                RuntimeError, match="Migration execution failed for database 'test_db'"
            ):
                db_manager.run_migrations()

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    @patch("core.database.Migrate")
    def test_get_migration_status_success(
        self, mock_pyway_class, mock_create_engine, mock_config_class
    ):
        """Test successful migration status retrieval."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"
        mock_create_engine.return_value = mock_engine

        # Setup Pyway mock
        mock_pyway = Mock()
        mock_pyway_class.return_value = mock_pyway
        mock_pyway.info.return_value = {
            "current_version": "V002",
            "applied_migrations": 2,
        }

        db_manager = DatabaseManager("test_db")

        # Mock migration directory and files
        mock_migration_dir = Mock()
        mock_migration_dir.exists.return_value = True

        # Mock migration files
        mock_file1 = Mock()
        mock_file1.name = "V001__Create_test_table.sql"
        mock_file1.stat.return_value.st_size = 1024
        mock_file2 = Mock()
        mock_file2.name = "V002__Add_test_index.sql"
        mock_file2.stat.return_value.st_size = 512

        # Mock files need to be sortable, so we'll use a custom mock
        mock_file1.__lt__ = Mock(return_value=True)
        mock_file2.__lt__ = Mock(return_value=False)
        mock_migration_dir.glob.return_value = [mock_file1, mock_file2]

        with patch.object(
            db_manager, "_get_migration_directory", return_value=mock_migration_dir
        ):
            status = db_manager.get_migration_status()

            expected_status = {
                "database_name": "test_db",
                "migration_directory": str(mock_migration_dir),
                "current_version": "V002",
                "pending_migrations": [
                    {
                        "filename": "V001__Create_test_table.sql",
                        "path": str(mock_file1),
                        "size": 1024,
                    },
                    {
                        "filename": "V002__Add_test_index.sql",
                        "path": str(mock_file2),
                        "size": 512,
                    },
                ],
                "total_applied": 2,
            }

            assert status == expected_status

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    @patch("core.database.Migrate")
    def test_get_migration_status_no_directory(
        self, mock_pyway_class, mock_create_engine, mock_config_class
    ):
        """Test migration status when directory doesn't exist."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"
        mock_create_engine.return_value = mock_engine

        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        # Mock migration directory doesn't exist
        mock_migration_dir = Mock()
        mock_migration_dir.exists.return_value = False

        with patch.object(
            db_manager, "_get_migration_directory", return_value=mock_migration_dir
        ):
            status = db_manager.get_migration_status()

            expected_status = {
                "database_name": "test_db",
                "migration_directory": str(mock_migration_dir),
                "current_version": None,
                "pending_migrations": [],
                "total_applied": 0,
            }

            assert status == expected_status

            # Verify warning was logged
            mock_logger.warning.assert_called_with(
                f"Migration directory '{mock_migration_dir}' does not exist for "
                f"database 'test_db'"
            )

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    @patch("core.database.Migrate")
    def test_get_migration_status_pyway_info_error(
        self, mock_pyway_class, mock_create_engine, mock_config_class
    ):
        """Test migration status handles Pyway info errors gracefully."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"
        mock_create_engine.return_value = mock_engine

        # Setup Pyway mock to raise error on info()
        mock_pyway = Mock()
        mock_pyway_class.return_value = mock_pyway
        mock_pyway.info.side_effect = Exception("Info failed")

        db_manager = DatabaseManager("test_db")
        mock_logger = Mock()
        db_manager._logger = mock_logger

        # Mock migration directory exists but no files
        mock_migration_dir = Mock()
        mock_migration_dir.exists.return_value = True
        mock_migration_dir.glob.return_value = []

        with patch.object(
            db_manager, "_get_migration_directory", return_value=mock_migration_dir
        ):
            status = db_manager.get_migration_status()

            # Should still return status with defaults
            assert status["current_version"] is None
            assert status["total_applied"] == 0

            # Verify warning was logged
            mock_logger.warning.assert_called_with(
                "Could not retrieve current migration info for database 'test_db': Info failed"
            )

    def test_get_migration_directory_path_construction(self):
        """Test migration directory path construction."""
        db_manager = DatabaseManager("test_db")

        # Test the actual path construction without mocking
        result = db_manager._get_migration_directory()

        # Verify the result is a Path object and contains expected components
        assert result is not None
        assert str(result).endswith("core/migrations/test_db")

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_get_migration_status_general_error(
        self, mock_create_engine, mock_config_class
    ):
        """Test migration status handles general errors."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"
        mock_create_engine.return_value = mock_engine

        db_manager = DatabaseManager("test_db")

        # Mock _get_migration_directory to raise an error
        with patch.object(
            db_manager, "_get_migration_directory", side_effect=Exception("Path error")
        ):
            with pytest.raises(
                RuntimeError,
                match="Failed to retrieve migration status for database 'test_db'",
            ):
                db_manager.get_migration_status()


class TestDatabaseManagerHealthMonitoring:
    """Test DatabaseManager health monitoring and diagnostics functionality."""

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_healthy_status(self, mock_create_engine, mock_config_class):
        """Test health check returns healthy status for working database."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup successful connection and query
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result
        mock_row = Mock()
        mock_row._mapping = {"health_check": 1}
        mock_result.fetchall.return_value = [mock_row]

        # Mock migration status
        db_manager = DatabaseManager("test_db")
        with patch.object(db_manager, "get_migration_status") as mock_migration:
            mock_migration.return_value = {
                "current_version": "V003",
                "pending_migrations": [],
            }

            result = db_manager.health_check()

            assert result["database_name"] == "test_db"
            assert result["status"] == "healthy"
            assert result["connection"] is True
            assert result["query_test"] is True
            assert result["migration_status"]["current_version"] == "V003"
            assert result["response_time_ms"] is not None
            assert result["response_time_ms"] >= 0
            assert result["timestamp"] is not None
            assert result["error"] is None

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_includes_response_time(
        self, mock_create_engine, mock_config_class
    ):
        """Test health check includes response time measurement."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and query
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_row = Mock()
        mock_row._mapping = {"health_check": 1}
        mock_result.fetchall.return_value = [mock_row]
        mock_conn.execute.return_value = mock_result

        db_manager = DatabaseManager("test_db")

        # Mock migration status
        with patch.object(db_manager, "get_migration_status") as mock_migration:
            mock_migration.return_value = {"current_version": "V001"}

            result = db_manager.health_check()

            assert result["status"] == "healthy"
            assert result["connection"] is True
            assert result["query_test"] is True
            assert result["response_time_ms"] is not None
            assert result["response_time_ms"] >= 0

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_degraded_status_query_failure(
        self, mock_create_engine, mock_config_class
    ):
        """Test health check returns degraded status when query fails but connection works."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection success but query failure
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.execute.side_effect = Exception("Query execution failed")

        db_manager = DatabaseManager("test_db")

        # Mock migration status
        with patch.object(db_manager, "get_migration_status") as mock_migration:
            mock_migration.return_value = {"current_version": "V001"}

            result = db_manager.health_check()

            assert result["status"] == "degraded"
            assert result["connection"] is True
            assert result["query_test"] is False
            assert "Query execution failed" in result["error"]

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_unhealthy_status_connection_failure(
        self, mock_create_engine, mock_config_class
    ):
        """Test health check returns unhealthy status when connection fails."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection failure
        mock_engine.connect.side_effect = Exception("Connection failed")

        db_manager = DatabaseManager("test_db")

        # Mock migration status
        with patch.object(db_manager, "get_migration_status") as mock_migration:
            mock_migration.return_value = {"current_version": "V001"}

            result = db_manager.health_check()

            assert result["status"] == "unhealthy"
            assert result["connection"] is False
            assert result["query_test"] is False
            assert "Connection failed" in result["error"]

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_migration_status_failure_non_blocking(
        self, mock_create_engine, mock_config_class
    ):
        """Test health check continues when migration status retrieval fails."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup successful connection and query
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result
        mock_row = Mock()
        mock_row._mapping = {"health_check": 1}
        mock_result.fetchall.return_value = [mock_row]

        db_manager = DatabaseManager("test_db")

        # Mock migration status failure
        with patch.object(db_manager, "get_migration_status") as mock_migration:
            mock_migration.side_effect = Exception("Migration status failed")

            result = db_manager.health_check()

            # Should still be healthy despite migration status failure
            assert result["status"] == "healthy"
            assert result["connection"] is True
            assert result["query_test"] is True
            assert "error" in result["migration_status"]
            assert "Migration status failed" in result["migration_status"]["error"]

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_query_returns_no_results(
        self, mock_create_engine, mock_config_class
    ):
        """Test health check handles query that returns no results."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and query with no results
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result
        mock_result.fetchall.return_value = []  # No results

        db_manager = DatabaseManager("test_db")

        # Mock migration status
        with patch.object(db_manager, "get_migration_status") as mock_migration:
            mock_migration.return_value = {"current_version": "V001"}

            result = db_manager.health_check()

            assert result["status"] == "degraded"
            assert result["connection"] is True
            assert result["query_test"] is False
            assert "Query test returned no results" in result["error"]

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_get_pool_status_success(self, mock_create_engine, mock_config_class):
        """Test successful pool status retrieval."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup pool mock
        mock_pool = Mock()
        mock_engine.pool = mock_pool
        mock_pool.size.return_value = 5
        mock_pool.checkedin.return_value = 3
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 1
        mock_pool.invalid.return_value = 0
        mock_pool._max_overflow = 10
        mock_pool.__class__.__name__ = "QueuePool"

        db_manager = DatabaseManager("test_db")
        result = db_manager.get_pool_status()

        assert result["database_name"] == "test_db"
        assert result["pool_size"] == 5
        assert result["checked_in"] == 3
        assert result["checked_out"] == 2
        assert result["overflow"] == 1
        assert result["invalid"] == 0
        assert result["total_connections"] == 6  # 3 + 2 + 1
        assert result["max_connections"] == 15  # 5 + 10
        assert result["utilization_percent"] == 13.33  # 2/15 * 100
        assert result["pool_class"] == "QueuePool"
        assert result["timestamp"] is not None

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_get_pool_status_high_utilization(
        self, mock_create_engine, mock_config_class
    ):
        """Test pool status with high utilization."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup pool mock with high utilization
        mock_pool = Mock()
        mock_engine.pool = mock_pool
        mock_pool.size.return_value = 5
        mock_pool.checkedin.return_value = 0
        mock_pool.checkedout.return_value = 8  # Using overflow connections
        mock_pool.overflow.return_value = 3
        mock_pool.invalid.return_value = 1
        mock_pool._max_overflow = 5
        mock_pool.__class__.__name__ = "QueuePool"

        db_manager = DatabaseManager("test_db")
        result = db_manager.get_pool_status()

        assert result["checked_out"] == 8
        assert result["overflow"] == 3
        assert result["max_connections"] == 10  # 5 + 5
        assert result["utilization_percent"] == 80.0  # 8/10 * 100

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_get_pool_status_no_max_overflow_attribute(
        self, mock_create_engine, mock_config_class
    ):
        """Test pool status when pool doesn't have _max_overflow attribute."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup pool mock without _max_overflow
        mock_pool = Mock()
        mock_engine.pool = mock_pool
        mock_pool.size.return_value = 5
        mock_pool.checkedin.return_value = 3
        mock_pool.checkedout.return_value = 2
        mock_pool.overflow.return_value = 0
        mock_pool.invalid.return_value = 0
        # Remove _max_overflow attribute to simulate pools that don't have it
        del mock_pool._max_overflow
        mock_pool.__class__.__name__ = "StaticPool"

        db_manager = DatabaseManager("test_db")
        result = db_manager.get_pool_status()

        assert result["max_connections"] == 5  # pool_size + 0 (default)
        assert result["utilization_percent"] == 40.0  # 2/5 * 100

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_get_pool_status_zero_max_connections(
        self, mock_create_engine, mock_config_class
    ):
        """Test pool status handles zero max connections gracefully."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup pool mock with zero size
        mock_pool = Mock()
        mock_engine.pool = mock_pool
        mock_pool.size.return_value = 0
        mock_pool.checkedin.return_value = 0
        mock_pool.checkedout.return_value = 0
        mock_pool.overflow.return_value = 0
        mock_pool.invalid.return_value = 0
        mock_pool._max_overflow = 0
        mock_pool.__class__.__name__ = "NullPool"

        db_manager = DatabaseManager("test_db")
        result = db_manager.get_pool_status()

        assert result["max_connections"] == 0
        assert result["utilization_percent"] == 0  # Should handle division by zero

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_get_pool_status_engine_initialization_error(
        self, mock_create_engine, mock_config_class
    ):
        """Test pool status handles engine initialization errors."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        # Setup engine creation to fail
        mock_create_engine.side_effect = Exception("Engine creation failed")

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError, match="Failed to retrieve pool status for database 'test_db'"
        ):
            db_manager.get_pool_status()

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_get_pool_status_pool_access_error(
        self, mock_create_engine, mock_config_class
    ):
        """Test pool status handles pool access errors."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup pool to raise error on access
        mock_engine.pool.size.side_effect = Exception("Pool access failed")

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError, match="Failed to retrieve pool status for database 'test_db'"
        ):
            db_manager.get_pool_status()


class TestDatabaseManagerRetryLogic:
    """Test DatabaseManager retry logic and resilience features."""

    def test_is_transient_error_connection_errors(self):
        """Test that connection-related errors are classified as transient."""
        from sqlalchemy.exc import DisconnectionError, InterfaceError, OperationalError
        from sqlalchemy.exc import TimeoutError as SQLTimeoutError

        from core.database import _is_transient_error

        # Test specific SQLAlchemy error types
        assert _is_transient_error(DisconnectionError("Connection lost", None, None))
        assert _is_transient_error(OperationalError("Connection refused", None, None))
        assert _is_transient_error(InterfaceError("Network error", None, None))
        assert _is_transient_error(SQLTimeoutError("Query timeout", None, None))

    def test_is_transient_error_message_based(self):
        """Test that errors with transient indicators in messages are classified as transient."""
        from core.database import _is_transient_error

        # Test message-based classification
        transient_messages = [
            "connection refused",
            "connection reset",
            "connection timeout",
            "network error",
            "temporary failure",
            "server closed the connection",
            "connection lost",
            "pool limit exceeded",
            "connection pool exhausted",
            "database is starting up",
            "database is shutting down",
            "too many connections",
            "connection aborted",
            "broken pipe",
        ]

        for message in transient_messages:
            error = Exception(f"Database error: {message}")
            assert _is_transient_error(error), (
                f"Should classify '{message}' as transient"
            )

    def test_is_transient_error_non_transient(self):
        """Test that non-transient errors are not classified as transient."""
        from core.database import _is_transient_error

        # Test non-transient errors
        non_transient_errors = [
            ValueError("Invalid parameter"),
            RuntimeError("Configuration error"),
            Exception("Syntax error in SQL"),
            Exception("Permission denied"),
            Exception("Table does not exist"),
        ]

        for error in non_transient_errors:
            assert not _is_transient_error(error), (
                f"Should not classify {type(error).__name__} as transient"
            )

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_with_retry_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test successful query execution with retry."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and result mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result

        # Mock result rows
        mock_row = Mock()
        mock_row._mapping = {"id": 1, "name": "test"}
        mock_result.fetchall.return_value = [mock_row]

        db_manager = DatabaseManager("test_db")
        results = db_manager.execute_query_with_retry("SELECT * FROM test_table")

        assert results == [{"id": 1, "name": "test"}]
        mock_conn.execute.assert_called_once()

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_with_retry_transient_failure_then_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test query execution with retry recovers from transient failure."""
        from sqlalchemy.exc import DisconnectionError

        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection to fail first, then succeed
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        # First call fails with transient error, second succeeds
        mock_result = Mock()
        mock_row = Mock()
        mock_row._mapping = {"id": 1, "name": "test"}
        mock_result.fetchall.return_value = [mock_row]

        mock_conn.execute.side_effect = [
            DisconnectionError("Connection lost", None, None),
            mock_result,
        ]

        db_manager = DatabaseManager("test_db")
        results = db_manager.execute_query_with_retry(
            "SELECT * FROM test_table", max_attempts=3
        )

        assert results == [{"id": 1, "name": "test"}]
        assert mock_conn.execute.call_count == 2  # Failed once, succeeded on retry

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_with_retry_permanent_failure(
        self, mock_create_engine, mock_config_class
    ):
        """Test query execution with retry fails on permanent error."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection to fail with non-transient error
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.execute.side_effect = ValueError(
            "Invalid SQL syntax"
        )  # Non-transient error

        db_manager = DatabaseManager("test_db")

        with pytest.raises(RuntimeError, match="Query execution with retry failed"):
            db_manager.execute_query_with_retry(
                "SELECT * FROM test_table", max_attempts=3
            )

        # Should only try once since it's not a transient error
        assert mock_conn.execute.call_count == 1

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_with_retry_exhausted_attempts(
        self, mock_create_engine, mock_config_class
    ):
        """Test query execution with retry fails after exhausting all attempts."""
        from sqlalchemy.exc import OperationalError

        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection to always fail with transient error
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.execute.side_effect = OperationalError(
            "Connection timeout", None, None
        )

        db_manager = DatabaseManager("test_db")

        with pytest.raises(
            RuntimeError, match="Query execution with retry failed.*after 2 attempts"
        ):
            db_manager.execute_query_with_retry(
                "SELECT * FROM test_table", max_attempts=2
            )

        # Should try the specified number of attempts
        assert mock_conn.execute.call_count == 2

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_query_with_timeout_and_retry_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test successful query execution with timeout and retry."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and result mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result

        # Mock result rows
        mock_row = Mock()
        mock_row._mapping = {"id": 1, "name": "test"}
        mock_result.fetchall.return_value = [mock_row]

        db_manager = DatabaseManager("test_db")
        results = db_manager.execute_query_with_timeout_and_retry(
            "SELECT * FROM test_table", timeout=60, max_attempts=3
        )

        assert results == [{"id": 1, "name": "test"}]
        mock_conn.execute.assert_called_once()

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_execute_transaction_with_retry_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test successful transaction execution with retry."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and transaction mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_transaction = Mock()
        mock_conn.begin.return_value = mock_transaction
        mock_transaction.__enter__ = Mock(return_value=mock_transaction)
        mock_transaction.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result

        # Mock result rows
        mock_row = Mock()
        mock_row._mapping = {"id": 1}
        mock_result.fetchall.return_value = [mock_row]

        queries = [
            ("INSERT INTO test_table (name) VALUES (:name)", {"name": "test1"}),
            ("INSERT INTO test_table (name) VALUES (:name)", {"name": "test2"}),
        ]

        db_manager = DatabaseManager("test_db")
        results = db_manager.execute_transaction_with_retry(queries, max_attempts=3)

        assert results == [{"id": 1}, {"id": 1}]  # Two queries, each returning one row
        assert mock_conn.execute.call_count == 2

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_with_retry_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test successful health check with retry."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and result mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result

        # Mock result rows for health check query
        mock_row = Mock()
        mock_row._mapping = {"health_check": 1}
        mock_result.fetchall.return_value = [mock_row]

        db_manager = DatabaseManager("test_db")

        # Mock the get_migration_status method to avoid file system operations
        with patch.object(db_manager, "get_migration_status") as mock_migration_status:
            mock_migration_status.return_value = {
                "database_name": "test_db",
                "current_version": "V001",
                "pending_migrations": [],
                "total_applied": 1,
            }

            health_status = db_manager.health_check_with_retry(max_attempts=2)

        assert health_status["status"] == "healthy"
        assert health_status["connection"] is True
        assert health_status["query_test"] is True
        assert health_status["database_name"] == "test_db"

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_with_retry_connection_failure_then_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test health check with retry recovers from connection failure."""
        from sqlalchemy.exc import OperationalError

        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection context manager to fail first, then succeed
        mock_conn_fail = Mock()
        mock_conn_fail.__enter__ = Mock(
            side_effect=OperationalError("Connection refused", None, None)
        )
        mock_conn_fail.__exit__ = Mock(return_value=None)

        mock_conn_success = Mock()
        mock_conn_success.__enter__ = Mock(return_value=mock_conn_success)
        mock_conn_success.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_row = Mock()
        mock_row._mapping = {"health_check": 1}
        mock_result.fetchall.return_value = [mock_row]
        mock_conn_success.execute.return_value = mock_result

        # First connect() call fails, second succeeds
        mock_engine.connect.side_effect = [mock_conn_fail, mock_conn_success]

        db_manager = DatabaseManager("test_db")

        # Mock the get_migration_status method
        with patch.object(db_manager, "get_migration_status") as mock_migration_status:
            mock_migration_status.return_value = {
                "database_name": "test_db",
                "current_version": "V001",
                "pending_migrations": [],
                "total_applied": 1,
            }

            health_status = db_manager.health_check_with_retry(max_attempts=3)

        assert health_status["status"] == "healthy"
        assert health_status["connection"] is True
        assert mock_engine.connect.call_count == 2  # Failed once, succeeded on retry

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_health_check_with_retry_exhausted_attempts(
        self, mock_create_engine, mock_config_class
    ):
        """Test health check with retry returns unhealthy status after exhausting attempts."""
        from sqlalchemy.exc import OperationalError

        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection to always fail
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(
            side_effect=OperationalError("Connection refused", None, None)
        )
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine.connect.return_value = mock_conn

        db_manager = DatabaseManager("test_db")
        health_status = db_manager.health_check_with_retry(max_attempts=2)

        assert health_status["status"] == "unhealthy"
        assert health_status["connection"] is False
        assert health_status["retry_exhausted"] is True
        assert "after 2 attempts" in health_status["error"]

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_run_migrations_with_retry_success(
        self, mock_create_engine, mock_config_class
    ):
        """Test successful migration execution with retry."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        mock_engine.url = "postgresql://user:pass@localhost:5432/test_db"

        db_manager = DatabaseManager("test_db")

        # Mock Pyway and migration directory
        with patch("core.database.Migrate") as mock_migrate_class:
            with patch.object(db_manager, "_get_migration_directory") as mock_get_dir:
                mock_migration_dir = Mock()
                mock_migration_dir.exists.return_value = True
                mock_get_dir.return_value = mock_migration_dir

                mock_migrate = Mock()
                mock_migrate_class.return_value = mock_migrate
                mock_migrate.migrate.return_value = [
                    {"version": "V001", "description": "Create tables"}
                ]

                # Should not raise any exception
                db_manager.run_migrations_with_retry(max_attempts=2)

                mock_migrate.migrate.assert_called_once()

    def test_create_retry_decorator_configuration(self):
        """Test that retry decorator is created with correct configuration."""
        from core.database import _create_retry_decorator

        # Test default configuration
        decorator = _create_retry_decorator()
        assert decorator is not None

        # Test custom configuration
        decorator = _create_retry_decorator(
            max_attempts=5, min_wait=2.0, max_wait=20.0, multiplier=3.0
        )
        assert decorator is not None

    def test_retry_methods_parameter_validation(self):
        """Test that retry methods validate parameters correctly."""
        db_manager = DatabaseManager("test_db")

        # Test execute_query_with_retry parameter validation
        # The retry wrapper will catch the ValueError and re-raise as RuntimeError
        with pytest.raises(
            RuntimeError,
            match="Query execution with retry failed.*Query must be a non-empty string",
        ):
            db_manager.execute_query_with_retry("")

        # Test execute_query_with_timeout_and_retry parameter validation
        with pytest.raises(
            RuntimeError,
            match="Query execution with timeout and retry failed.*Query must be a non-empty string",
        ):
            db_manager.execute_query_with_timeout_and_retry("", timeout=30)

        with pytest.raises(
            RuntimeError,
            match="Query execution with timeout and retry failed.*Timeout must be a positive integer",
        ):
            db_manager.execute_query_with_timeout_and_retry("SELECT 1", timeout=0)

        # Test execute_transaction_with_retry parameter validation
        with pytest.raises(
            RuntimeError,
            match="Transaction execution with retry failed.*Queries must be a non-empty list",
        ):
            db_manager.execute_transaction_with_retry([])

    @patch("core.database.ConfigManager")
    @patch("core.database.create_engine")
    def test_retry_methods_custom_retry_parameters(
        self, mock_create_engine, mock_config_class
    ):
        """Test that retry methods accept and use custom retry parameters."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_config.environment = "development"
        mock_config.get_variable.side_effect = lambda key, default=None: {
            "test_db_type": "postgresql"
        }.get(key, default)
        mock_config.get_secret.return_value = (
            "postgresql://user:pass@localhost:5432/test_db"
        )

        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine

        # Setup connection and result mocks
        mock_conn = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_result = Mock()
        mock_conn.execute.return_value = mock_result
        mock_row = Mock()
        mock_row._mapping = {"id": 1}
        mock_result.fetchall.return_value = [mock_row]

        db_manager = DatabaseManager("test_db")

        # Test custom retry parameters
        results = db_manager.execute_query_with_retry(
            "SELECT 1", max_attempts=5, min_wait=0.1, max_wait=2.0
        )

        assert results == [{"id": 1}]
        mock_conn.execute.assert_called_once()
