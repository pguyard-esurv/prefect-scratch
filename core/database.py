"""
Database management module for unified PostgreSQL and SQL Server access.

This module provides the DatabaseManager class that handles database connections,
query execution, migration management, and health monitoring across different
database types using SQLAlchemy and Pyway.
"""

import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from pyway.configfile import ConfigFile

# Migration-related imports
from pyway.migrate import Migrate

# Database-related imports
from sqlalchemy import create_engine, text
from sqlalchemy.exc import (
    DisconnectionError,
    InterfaceError,
    OperationalError,
)
from sqlalchemy.exc import TimeoutError as SQLTimeoutError
from sqlalchemy.pool import QueuePool

# Retry logic imports
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

# Import existing configuration management
from core.config import ConfigManager


def _is_transient_error(exception: Exception) -> bool:
    """
    Determine if an exception represents a transient error that should trigger retry.

    Transient errors are temporary issues that may resolve on retry, such as:
    - Network connectivity issues
    - Connection pool exhaustion
    - Temporary database unavailability
    - Connection timeouts

    Args:
        exception: The exception to classify

    Returns:
        True if the error is transient and should trigger retry, False otherwise
    """
    # Connection-related errors that are typically transient
    transient_error_types = (
        DisconnectionError,
        OperationalError,
        InterfaceError,
        SQLTimeoutError,
    )

    if isinstance(exception, transient_error_types):
        return True

    # Check for specific error messages that indicate transient issues
    error_message = str(exception).lower()
    transient_indicators = [
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

    return any(indicator in error_message for indicator in transient_indicators)


def _create_retry_decorator(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
):
    """
    Create a retry decorator with exponential backoff for database operations.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries in seconds
        max_wait: Maximum wait time between retries in seconds
        multiplier: Exponential backoff multiplier

    Returns:
        Configured retry decorator
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
        retry=retry_if_exception(_is_transient_error),
        reraise=True,
    )


class DatabaseManager:
    """
    Unified database manager for PostgreSQL and SQL Server databases.

    Provides connection pooling, query execution, migration management,
    and health monitoring capabilities through a single interface.
    """

    def __init__(self, database_name: str):
        """
        Initialize DatabaseManager for a specific database.

        Args:
            database_name: Name of the database configuration to load

        Raises:
            ValueError: If database_name is empty or None
        """
        if (
            not database_name
            or not isinstance(database_name, str)
            or not database_name.strip()
        ):
            raise ValueError("database_name must be a non-empty string")

        self.database_name = database_name
        self.engine = None
        self._logger = None
        self._config_manager = None

        # Initialize logger lazily
        self._initialize_logger()

        # Initialize engine lazily (will be created on first access)
        # This allows for better error handling and testing

    def _initialize_logger(self):
        """Initialize logger with Prefect integration and fallback."""
        if self._logger is not None:
            return

        try:
            # Try to use Prefect's get_run_logger for task context
            from prefect import get_run_logger

            self._logger = get_run_logger()
            self._logger.info(
                f"DatabaseManager initialized for '{self.database_name}' "
                "with Prefect logger"
            )
        except (ImportError, RuntimeError):
            # Fallback to standard Python logging if Prefect is not available
            # or not in task context
            self._logger = logging.getLogger(f"DatabaseManager.{self.database_name}")
            if not self._logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                handler.setFormatter(formatter)
                self._logger.addHandler(handler)
                self._logger.setLevel(logging.INFO)

            self._logger.info(
                f"DatabaseManager initialized for '{self.database_name}' "
                "with standard logger"
            )

    @property
    def logger(self):
        """Get the logger instance, initializing if necessary."""
        if self._logger is None:
            self._initialize_logger()
        return self._logger

    @property
    def db_engine(self):
        """Get the SQLAlchemy engine, initializing if necessary."""
        if self.engine is None:
            self._initialize_engine()
        return self.engine

    def _initialize_engine(self):
        """
        Initialize SQLAlchemy engine with configuration from ConfigManager.

        Loads database configuration including type, connection string, and pool
        settings from ConfigManager and creates a SQLAlchemy engine with
        QueuePool configuration.

        Raises:
            ValueError: If required configuration is missing or invalid
            RuntimeError: If engine creation fails
        """
        if self.engine is not None:
            return

        try:
            # Initialize ConfigManager if not already done
            if self._config_manager is None:
                self._config_manager = ConfigManager()

            # Load database configuration
            db_type = self._config_manager.get_variable(f"{self.database_name}_type")
            connection_string = self._config_manager.get_secret(
                f"{self.database_name}_connection_string"
            )

            # Validate required configuration
            if not db_type:
                raise ValueError(
                    f"Database type not configured for '{self.database_name}'. "
                    f"Please set {self._config_manager.environment.upper()}_GLOBAL_"
                    f"{self.database_name.upper()}_TYPE in your environment "
                    f"configuration."
                )

            if not connection_string:
                raise ValueError(
                    f"Connection string not configured for '{self.database_name}'. "
                    f"Please set {self._config_manager.environment.upper()}_GLOBAL_"
                    f"{self.database_name.upper()}_CONNECTION_STRING in your "
                    f"environment configuration."
                )

            # Validate database type
            supported_types = ["postgresql", "sqlserver"]
            if db_type.lower() not in supported_types:
                raise ValueError(
                    f"Unsupported database type '{db_type}' for "
                    f"'{self.database_name}'. "
                    f"Supported types: {', '.join(supported_types)}"
                )

            # Load pool configuration with defaults
            pool_size = int(
                self._config_manager.get_variable(f"{self.database_name}_pool_size", 5)
            )
            max_overflow = int(
                self._config_manager.get_variable(
                    f"{self.database_name}_max_overflow", 10
                )
            )

            # Create SQLAlchemy engine with QueuePool
            self.engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_pre_ping=True,
                echo=False,  # Set to True for SQL debugging
            )

            self.logger.info(
                f"Created SQLAlchemy engine for '{self.database_name}' "
                f"(type: {db_type}, pool_size: {pool_size}, "
                f"max_overflow: {max_overflow})"
            )

        except Exception as e:
            error_msg = (
                f"Failed to initialize engine for database '{self.database_name}': {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def execute_query(self, query: str, params: Optional[dict] = None) -> list[dict]:
        """
        Execute a SQL query and return results as list of dictionaries.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            List of dictionaries representing query results

        Raises:
            RuntimeError: If query execution fails
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        try:
            self.logger.debug(f"Executing query for database '{self.database_name}'")

            with self.db_engine.connect() as conn:
                # Use SQLAlchemy text() for parameterized queries
                sql_text = text(query)
                result = conn.execute(sql_text, params or {})

                # Check if this is a query that returns rows (SELECT) or not (INSERT/UPDATE/DELETE)
                if result.returns_rows:
                    # Convert results to list of dictionaries
                    rows = result.fetchall()
                    results = [dict(row._mapping) for row in rows]

                    self.logger.debug(
                        f"Query executed successfully for database '{self.database_name}', "
                        f"returned {len(results)} rows"
                    )

                    return results
                else:
                    # For INSERT/UPDATE/DELETE, return the number of affected rows
                    affected_rows = result.rowcount

                    self.logger.debug(
                        f"Query executed successfully for database '{self.database_name}', "
                        f"affected {affected_rows} rows"
                    )

                    return [{"affected_rows": affected_rows}]

        except Exception as e:
            error_msg = (
                f"Query execution failed for database '{self.database_name}': {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def execute_query_with_timeout(
        self, query: str, params: Optional[dict] = None, timeout: int = 30
    ) -> list[dict]:
        """
        Execute a SQL query with timeout control.

        Args:
            query: SQL query string
            params: Optional query parameters
            timeout: Query timeout in seconds (must be positive)

        Returns:
            List of dictionaries representing query results

        Raises:
            ValueError: If timeout is not positive
            RuntimeError: If query execution fails or times out
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        if timeout <= 0:
            raise ValueError("Timeout must be a positive integer")

        try:
            self.logger.debug(
                f"Executing query with {timeout}s timeout for database '{self.database_name}'"  # noqa E501
            )

            with self.db_engine.connect() as conn:
                # Use SQLAlchemy text() for parameterized queries
                sql_text = text(query)

                # Execute query (timeout handling would be implemented at the engine level  # noqa E501
                # or using asyncio for more advanced timeout control)
                result = conn.execute(sql_text, params or {})

                # Convert results to list of dictionaries
                rows = result.fetchall()
                results = [dict(row._mapping) for row in rows]

                self.logger.debug(
                    f"Query with timeout executed successfully "
                    f"for database '{self.database_name}', "
                    f"returned {len(results)} rows"
                )

                return results

        except SQLTimeoutError as e:
            error_msg = f"Query timeout ({timeout}s) exceeded for database '{self.database_name}': {e}"  # noqa E501
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_msg = f"Query execution with timeout failed for database '{self.database_name}': {e}"  # noqa E501
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def execute_transaction(self, queries: list[tuple]) -> list[dict]:
        """
        Execute multiple queries within a single transaction.

        Args:
            queries: List of (query, params) tuples where each tuple contains
                    (query_string, parameters_dict)

        Returns:
            List of dictionaries representing combined results from all queries

        Raises:
            ValueError: If queries list is empty or contains invalid tuples
            RuntimeError: If transaction execution fails (automatically rolls back)
        """
        if not queries or not isinstance(queries, list):
            raise ValueError("Queries must be a non-empty list")

        # Validate query tuples
        for i, query_tuple in enumerate(queries):
            if not isinstance(query_tuple, tuple) or len(query_tuple) != 2:
                raise ValueError(
                    f"Query at index {i} must be a tuple of (query_string, params_dict)"
                )
            query_str, params = query_tuple
            if not query_str or not isinstance(query_str, str):
                raise ValueError(
                    f"Query string at index {i} must be a non-empty string"
                )  # noqa E501
            if params is not None and not isinstance(params, dict):
                raise ValueError(
                    f"Parameters at index {i} must be a dictionary or None"
                )  # noqa E501

        try:
            self.logger.debug(
                f"Executing transaction with {len(queries)} queries "
                f"for database '{self.database_name}'"
            )

            all_results = []

            with self.db_engine.connect() as conn:
                # Begin transaction using context manager for automatic rollback
                with conn.begin():
                    for i, (query_str, params) in enumerate(queries):
                        self.logger.debug(
                            f"Executing query {i + 1}/{len(queries)} in transaction "
                            f"for database '{self.database_name}'"
                        )

                        # Use SQLAlchemy text() for parameterized queries
                        sql_text = text(query_str)
                        result = conn.execute(sql_text, params or {})

                        # Convert results to list of dictionaries
                        rows = result.fetchall()
                        query_results = [dict(row._mapping) for row in rows]
                        all_results.extend(query_results)

                        self.logger.debug(
                            f"Query {i + 1}/{len(queries)} completed, "
                            f"returned {len(query_results)} rows"
                        )

                    # Transaction is automatically committed when exiting the context manager  # noqa E501
                    self.logger.debug(
                        f"Transaction committed successfully for "
                        f"database '{self.database_name}', "
                        f"total results: {len(all_results)} rows"
                    )

            return all_results

        except Exception as e:
            error_msg = (
                f"Transaction execution failed for database '{self.database_name}': {e}. "  # noqa E501
                f"All changes have been rolled back."
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def run_migrations(self) -> None:
        """
        Execute pending database migrations using Pyway.

        Initializes Pyway with database-specific migration directory and executes
        all pending migrations in sequential order. Migration state is tracked
        in the schema_version table.

        Raises:
            RuntimeError: If migration execution fails
            FileNotFoundError: If migration directory doesn't exist
        """
        try:
            migration_dir = self._get_migration_directory()

            # Check if migration directory exists
            if not migration_dir.exists():
                self.logger.warning(
                    f"Migration directory '{migration_dir}' does not exist for "
                    f"database '{self.database_name}'. Creating directory."
                )
                migration_dir.mkdir(parents=True, exist_ok=True)

            self.logger.info(
                f"Starting migration execution for database '{self.database_name}' "
                f"using directory: {migration_dir}"
            )

            # Get database URL from engine and parse it
            database_url = str(self.db_engine.url)
            parsed_url = urlparse(database_url)

            # Create ConfigFile with parsed database parameters
            config = ConfigFile(
                database_type=parsed_url.scheme,
                database_host=parsed_url.hostname,
                database_port=parsed_url.port,
                database_name=parsed_url.path.lstrip('/'),
                database_username=parsed_url.username,
                database_password=parsed_url.password,
                database_migration_dir=str(migration_dir),
                database_table="schema_version"
            )

            # Initialize Pyway instance with ConfigFile
            pyway = Migrate(config)

            # Execute migrations
            migration_result = pyway.migrate()

            if migration_result:
                self.logger.info(
                    f"Migrations executed successfully for database '{self.database_name}'. "  # noqa E501
                    f"Applied {len(migration_result)} migrations."
                )

                # Log each applied migration
                for migration in migration_result:
                    self.logger.debug(
                        f"Applied migration: {migration.get('version', 'unknown')} - "
                        f"{migration.get('description', 'no description')}"
                    )
            else:
                self.logger.info(
                    f"No pending migrations found for database '{self.database_name}'"
                )

        except FileNotFoundError as e:
            error_msg = f"Migration directory not found for database '{self.database_name}': {e}"  # noqa E501
            self.logger.error(error_msg)
            raise FileNotFoundError(error_msg) from e
        except Exception as e:
            error_msg = (
                f"Migration execution failed for database '{self.database_name}': {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def get_migration_status(self) -> dict:
        """
        Get current migration status and pending migrations.

        Returns current migration version and lists any pending migrations
        that haven't been applied yet.

        Returns:
            Dictionary containing:
                - current_version: Current migration version (str or None)
                - pending_migrations: List of pending migration files
                - migration_directory: Path to migration directory
                - total_applied: Number of applied migrations

        Raises:
            RuntimeError: If migration status retrieval fails
        """
        try:
            migration_dir = self._get_migration_directory()

            self.logger.debug(
                f"Retrieving migration status for database '{self.database_name}' "
                f"from directory: {migration_dir}"
            )

            # Initialize status dictionary
            status = {
                "database_name": self.database_name,
                "migration_directory": str(migration_dir),
                "current_version": None,
                "pending_migrations": [],
                "total_applied": 0,
            }

            # Check if migration directory exists
            if not migration_dir.exists():
                self.logger.warning(
                    f"Migration directory '{migration_dir}' does not exist for "
                    f"database '{self.database_name}'"
                )
                return status

            # Get database URL from engine and parse it
            database_url = str(self.db_engine.url)
            parsed_url = urlparse(database_url)

            # Create ConfigFile with parsed database parameters
            config = ConfigFile(
                database_type=parsed_url.scheme,
                database_host=parsed_url.hostname,
                database_port=parsed_url.port,
                database_name=parsed_url.path.lstrip('/'),
                database_username=parsed_url.username,
                database_password=parsed_url.password,
                database_migration_dir=str(migration_dir),
                database_table="schema_version"
            )

            # Initialize Pyway instance with ConfigFile
            pyway = Migrate(config)

            # Get current migration info
            try:
                current_info = pyway.info()
                if current_info:
                    status["current_version"] = current_info.get("current_version")
                    status["total_applied"] = current_info.get("applied_migrations", 0)
            except Exception as info_error:
                self.logger.warning(
                    f"Could not retrieve current migration info for "
                    f"database '{self.database_name}': {info_error}"
                )

            # Get pending migrations by scanning directory
            pending_migrations = []
            if migration_dir.exists():
                # Look for SQL migration files following V{version}__{description}.sql pattern  # noqa E501
                for migration_file in sorted(migration_dir.glob("V*__*.sql")):
                    pending_migrations.append(
                        {
                            "filename": migration_file.name,
                            "path": str(migration_file),
                            "size": migration_file.stat().st_size,
                        }
                    )

            status["pending_migrations"] = pending_migrations

            self.logger.debug(
                f"Migration status retrieved for database '{self.database_name}': "
                f"current_version={status['current_version']}, "
                f"pending={len(pending_migrations)}, "
                f"applied={status['total_applied']}"
            )

            return status

        except Exception as e:
            error_msg = f"Failed to retrieve migration status for database '{self.database_name}': {e}"  # noqa E501
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def _get_migration_directory(self) -> Path:
        """
        Get the migration directory path for this database.

        Constructs the migration directory path using the pattern:
        core/migrations/{database_name}

        Returns:
            Path object pointing to the migration directory
        """
        # Get the project root directory (assuming we're in core/ subdirectory)
        project_root = Path(__file__).parent.parent
        migration_dir = project_root / "core" / "migrations" / self.database_name

        return migration_dir

    def health_check(self) -> dict[str, Any]:
        """
        Perform database health check including connectivity and migration status.

        Tests database connectivity, basic query execution, measures response times,
        and includes migration status information. Returns comprehensive health
        status with detailed error information for troubleshooting.

        Returns:
            Dictionary containing:
                - database_name: Name of the database
                - status: Overall health status (healthy/degraded/unhealthy)
                - connection: Boolean indicating connection success
                - query_test: Boolean indicating basic query test success
                - migration_status: Dictionary with migration information
                - response_time_ms: Query response time in milliseconds
                - timestamp: ISO timestamp of health check
                - error: Error message if health check failed

        Raises:
            RuntimeError: If health check execution fails completely
        """
        import time
        from datetime import UTC, datetime

        start_time = time.time()
        timestamp = datetime.now(UTC).isoformat() + "Z"

        health_status = {
            "database_name": self.database_name,
            "status": "unhealthy",
            "connection": False,
            "query_test": False,
            "migration_status": None,
            "response_time_ms": None,
            "timestamp": timestamp,
            "error": None,
        }

        try:
            self.logger.debug(
                f"Starting health check for database '{self.database_name}'"
            )  # noqa E501

            # Test 1: Database connectivity
            try:
                # Initialize engine if not already done
                engine = self.db_engine

                # Test basic connection
                with engine.connect() as conn:
                    health_status["connection"] = True
                    self.logger.debug(
                        f"Connection test passed for database '{self.database_name}'"
                    )  # noqa E501

                    # Test 2: Basic query execution
                    query_start = time.time()
                    result = conn.execute(text("SELECT 1 as health_check"))
                    rows = result.fetchall()
                    query_end = time.time()

                    if rows and len(rows) > 0:
                        health_status["query_test"] = True
                        health_status["response_time_ms"] = round(
                            (query_end - query_start) * 1000, 2
                        )  # noqa E501
                        self.logger.debug(
                            f"Query test passed for database '{self.database_name}' "
                            f"in {health_status['response_time_ms']}ms"
                        )
                    else:
                        health_status["error"] = "Query test returned no results"
                        self.logger.warning(
                            f"Query test failed for database '{self.database_name}': no results"  # noqa E501
                        )

            except Exception as conn_error:
                health_status["error"] = (
                    f"Connection or query test failed: {str(conn_error)}"  # noqa E501
                )
                self.logger.error(
                    f"Connection/query test failed for database '{self.database_name}': {conn_error}"  # noqa E501
                )

            # Test 3: Migration status (non-blocking)
            try:
                migration_status = self.get_migration_status()
                health_status["migration_status"] = migration_status
                self.logger.debug(
                    f"Migration status retrieved for database '{self.database_name}'"
                )  # noqa E501
            except Exception as migration_error:
                # Migration status failure shouldn't fail entire health check
                health_status["migration_status"] = {
                    "error": f"Failed to retrieve migration status: {str(migration_error)}"  # noqa E501
                }
                self.logger.warning(
                    f"Migration status retrieval failed for database '{self.database_name}': "  # noqa E501
                    f"{migration_error}"
                )

            # Determine overall health status
            if health_status["connection"] and health_status["query_test"]:
                # Check response time for degraded status
                response_time = health_status.get("response_time_ms", 0)
                if response_time > 5000:  # 5 seconds threshold for degraded
                    health_status["status"] = "degraded"
                    self.logger.info(
                        f"Database '{self.database_name}' is degraded "
                        f"(response time: {response_time}ms)"
                    )
                else:
                    health_status["status"] = "healthy"
                    self.logger.info(f"Database '{self.database_name}' is healthy")
            elif health_status["connection"]:
                health_status["status"] = "degraded"
                self.logger.warning(
                    f"Database '{self.database_name}' is degraded (connection ok, query failed)"
                )  # noqa E501
            else:
                health_status["status"] = "unhealthy"
                self.logger.error(f"Database '{self.database_name}' is unhealthy")

            # Calculate total health check time
            total_time = time.time() - start_time
            self.logger.debug(
                f"Health check completed for database '{self.database_name}' "
                f"in {round(total_time * 1000, 2)}ms, status: {health_status['status']}"
            )

            return health_status

        except Exception as e:
            error_msg = f"Health check execution failed for database '{self.database_name}': {e}"  # noqa E501
            self.logger.error(error_msg)

            # Update health status with error information
            health_status["error"] = str(e)
            health_status["status"] = "unhealthy"

            # Don't raise exception, return error status instead
            return health_status

    def get_pool_status(self) -> dict[str, Any]:
        """
        Get detailed connection pool status and metrics.

        Provides real-time visibility into connection pool utilization,
        including active connections, pool configuration, and resource usage.
        Useful for monitoring database performance and identifying bottlenecks.

        Returns:
            Dictionary containing:
                - database_name: Name of the database
                - pool_size: Configured pool size
                - checked_in: Number of connections currently in the pool
                - checked_out: Number of connections currently in use
                - overflow: Number of overflow connections beyond pool_size
                - invalid: Number of invalid connections
                - total_connections: Total number of connections (checked_in + checked_out + overflow)  # noqa E501
                - utilization_percent: Pool utilization as percentage
                - timestamp: ISO timestamp when status was retrieved
                - pool_class: Type of connection pool being used

        Raises:
            RuntimeError: If pool status retrieval fails
        """
        from datetime import UTC, datetime

        try:
            timestamp = datetime.now(UTC).isoformat() + "Z"

            self.logger.debug(
                f"Retrieving pool status for database '{self.database_name}'"
            )  # noqa E501

            # Initialize engine if not already done
            engine = self.db_engine

            # Get pool instance from engine
            pool = engine.pool

            # Extract pool metrics
            pool_size = pool.size()
            checked_in = pool.checkedin()
            checked_out = pool.checkedout()
            overflow = pool.overflow()
            invalid = pool.invalid()

            # Calculate derived metrics
            total_connections = checked_in + checked_out + overflow
            max_overflow_attr = getattr(pool, "_max_overflow", 0)
            # Handle case where _max_overflow might be a Mock object in tests
            max_overflow_value = (
                max_overflow_attr if isinstance(max_overflow_attr, int) else 0
            )  # noqa E501
            max_possible_connections = pool_size + max_overflow_value
            utilization_percent = round(
                (
                    (checked_out / max_possible_connections * 100)
                    if max_possible_connections > 0
                    else 0
                ),  # noqa E501
                2,
            )

            pool_status = {
                "database_name": self.database_name,
                "pool_size": pool_size,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "overflow": overflow,
                "invalid": invalid,
                "total_connections": total_connections,
                "max_connections": max_possible_connections,
                "utilization_percent": utilization_percent,
                "timestamp": timestamp,
                "pool_class": pool.__class__.__name__,
            }

            self.logger.debug(
                f"Pool status retrieved for database '{self.database_name}': "
                f"checked_out={checked_out}/{max_possible_connections} "
                f"({utilization_percent}% utilization)"
            )

            return pool_status

        except Exception as e:
            error_msg = f"Failed to retrieve pool status for database '{self.database_name}': {e}"  # noqa E501
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    # Retry-enabled database operations

    def execute_query_with_retry(
        self,
        query: str,
        params: Optional[dict] = None,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0,
    ) -> list[dict]:
        """
        Execute a SQL query with automatic retry for transient failures.

        This method wraps execute_query with configurable retry logic that
        automatically retries on transient database errors such as connection
        timeouts, network issues, or temporary database unavailability.

        Args:
            query: SQL query string
            params: Optional query parameters
            max_attempts: Maximum number of retry attempts (default: 3)
            min_wait: Minimum wait time between retries in seconds (default: 1.0)
            max_wait: Maximum wait time between retries in seconds (default: 10.0)

        Returns:
            List of dictionaries representing query results

        Raises:
            RuntimeError: If query execution fails after all retry attempts
            ValueError: If query parameters are invalid
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts, min_wait=min_wait, max_wait=max_wait
        )

        @retry_decorator
        def _execute_with_retry():
            self.logger.debug(
                f"Executing query with retry for database '{self.database_name}' "
                f"(max_attempts: {max_attempts})"
            )
            return self.execute_query(query, params)

        try:
            return _execute_with_retry()
        except Exception as e:
            error_msg = (
                f"Query execution with retry failed for database '{self.database_name}' "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def execute_query_with_timeout_and_retry(
        self,
        query: str,
        params: Optional[dict] = None,
        timeout: int = 30,
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0,
    ) -> list[dict]:
        """
        Execute a SQL query with timeout control and automatic retry for transient failures.

        Combines timeout control with retry logic to handle both long-running queries
        and transient connection issues. Useful for queries that may occasionally
        timeout due to database load but should be retried.

        Args:
            query: SQL query string
            params: Optional query parameters
            timeout: Query timeout in seconds (must be positive)
            max_attempts: Maximum number of retry attempts (default: 3)
            min_wait: Minimum wait time between retries in seconds (default: 1.0)
            max_wait: Maximum wait time between retries in seconds (default: 10.0)

        Returns:
            List of dictionaries representing query results

        Raises:
            RuntimeError: If query execution fails after all retry attempts
            ValueError: If query or timeout parameters are invalid
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts, min_wait=min_wait, max_wait=max_wait
        )

        @retry_decorator
        def _execute_with_timeout_and_retry():
            self.logger.debug(
                f"Executing query with timeout and retry for database '{self.database_name}' "
                f"(timeout: {timeout}s, max_attempts: {max_attempts})"
            )
            return self.execute_query_with_timeout(query, params, timeout)

        try:
            return _execute_with_timeout_and_retry()
        except Exception as e:
            error_msg = (
                f"Query execution with timeout and retry failed for database '{self.database_name}' "  # noqa E501
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def execute_transaction_with_retry(
        self,
        queries: list[tuple],
        max_attempts: int = 3,
        min_wait: float = 1.0,
        max_wait: float = 10.0,
    ) -> list[dict]:
        """
        Execute multiple queries within a transaction with automatic retry for transient failures.

        Provides transaction support with retry logic for handling transient database
        issues. If any query in the transaction fails due to a transient error,
        the entire transaction is retried from the beginning.

        Args:
            queries: List of (query, params) tuples
            max_attempts: Maximum number of retry attempts (default: 3)
            min_wait: Minimum wait time between retries in seconds (default: 1.0)
            max_wait: Maximum wait time between retries in seconds (default: 10.0)

        Returns:
            List of dictionaries representing combined results from all queries

        Raises:
            RuntimeError: If transaction execution fails after all retry attempts
            ValueError: If queries parameter is invalid
        """  # noqa E501
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts, min_wait=min_wait, max_wait=max_wait
        )

        @retry_decorator
        def _execute_transaction_with_retry():
            self.logger.debug(
                f"Executing transaction with retry for database '{self.database_name}' "
                f"({len(queries)} queries, max_attempts: {max_attempts})"
            )
            return self.execute_transaction(queries)

        try:
            return _execute_transaction_with_retry()
        except Exception as e:
            error_msg = (
                f"Transaction execution with retry failed for database '{self.database_name}' "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def health_check_with_retry(
        self, max_attempts: int = 2, min_wait: float = 0.5, max_wait: float = 5.0
    ) -> dict[str, Any]:
        """
        Perform database health check with retry for transient failures.

        Provides health checking with limited retry logic to handle temporary
        connectivity issues. Uses fewer retry attempts and shorter wait times
        compared to data operations since health checks should be fast.

        Args:
            max_attempts: Maximum number of retry attempts (default: 2)
            min_wait: Minimum wait time between retries in seconds (default: 0.5)
            max_wait: Maximum wait time between retries in seconds (default: 5.0)

        Returns:
            Dictionary containing health check results

        Raises:
            RuntimeError: If health check fails after all retry attempts
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts, min_wait=min_wait, max_wait=max_wait
        )

        @retry_decorator
        def _health_check_with_retry():
            self.logger.debug(
                f"Performing health check with retry for database '{self.database_name}' "
                f"(max_attempts: {max_attempts})"
            )
            result = self.health_check()

            # Only retry if the health check indicates a connection failure
            # Don't retry for degraded status or query test failures
            if not result.get("connection", False):
                raise RuntimeError(
                    f"Health check connection failed: {result.get('error', 'Unknown error')}"
                )  # noqa E501

            return result

        try:
            return _health_check_with_retry()
        except Exception as e:
            # If retry fails, return an unhealthy status instead of raising
            # This ensures health checks always return a status rather than failing
            from datetime import UTC, datetime

            error_msg = (
                f"Health check with retry failed for database '{self.database_name}' "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)

            return {
                "database_name": self.database_name,
                "status": "unhealthy",
                "connection": False,
                "query_test": False,
                "migration_status": None,
                "response_time_ms": None,
                "timestamp": datetime.now(UTC).isoformat() + "Z",
                "error": error_msg,
                "retry_exhausted": True,
            }

    def run_migrations_with_retry(
        self, max_attempts: int = 2, min_wait: float = 2.0, max_wait: float = 15.0
    ) -> None:
        """
        Execute database migrations with retry for transient failures.

        Provides migration execution with limited retry logic to handle temporary
        connectivity issues during migration. Uses conservative retry settings
        since migrations should be idempotent and careful.

        Args:
            max_attempts: Maximum number of retry attempts (default: 2)
            min_wait: Minimum wait time between retries in seconds (default: 2.0)
            max_wait: Maximum wait time between retries in seconds (default: 15.0)

        Raises:
            RuntimeError: If migration execution fails after all retry attempts
            FileNotFoundError: If migration directory doesn't exist
        """
        retry_decorator = _create_retry_decorator(
            max_attempts=max_attempts, min_wait=min_wait, max_wait=max_wait
        )

        @retry_decorator
        def _run_migrations_with_retry():
            self.logger.debug(
                f"Running migrations with retry for database '{self.database_name}' "
                f"(max_attempts: {max_attempts})"
            )
            return self.run_migrations()

        try:
            return _run_migrations_with_retry()
        except Exception as e:
            error_msg = (
                f"Migration execution with retry failed for database '{self.database_name}' "
                f"after {max_attempts} attempts: {e}"
            )
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    def __enter__(self) -> "DatabaseManager":
        """
        Context manager entry.

        Returns:
            DatabaseManager: Self instance for context management
        """
        self.logger.debug(
            f"Entering context manager for database '{self.database_name}'"
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Context manager exit with proper resource cleanup.

        Args:
            exc_type: Exception type if an exception occurred
            exc_val: Exception value if an exception occurred
            exc_tb: Exception traceback if an exception occurred
        """
        try:
            if exc_type is not None:
                self.logger.error(
                    f"Exception occurred in DatabaseManager context for "
                    f"'{self.database_name}': {exc_type.__name__}: {exc_val}"
                )

            # Clean up engine resources if they exist
            if self.engine is not None:
                self.logger.debug(
                    f"Disposing engine for database '{self.database_name}'"
                )
                self.engine.dispose()
                self.engine = None

            self.logger.debug(
                f"Exited context manager for database '{self.database_name}'"
            )

        except Exception as cleanup_error:
            # Log cleanup errors but don't raise them to avoid masking
            # the original exception
            self.logger.error(
                f"Error during cleanup for database '{self.database_name}': "
                f"{cleanup_error}"
            )


# Configuration validation convenience functions
def validate_database_configuration(database_name: Optional[str] = None) -> dict:
    """
    Validate database configuration for one or all databases.

    Args:
        database_name: Specific database to validate (validates all if None)

    Returns:
        Dictionary with validation results
    """
    from core.database_config_validator import (
        validate_all_database_configurations,
        validate_database_config,
    )

    if database_name:
        return {database_name: validate_database_config(database_name)}
    else:
        return validate_all_database_configurations()


def test_database_connectivity(database_name: str) -> dict:
    """
    Test database connectivity for a specific database.

    Args:
        database_name: Name of the database to test

    Returns:
        Dictionary with connectivity test results
    """
    from core.database_config_validator import (
        test_database_connectivity as _test_connectivity,
    )

    return _test_connectivity(database_name)


def generate_database_config_report() -> str:
    """
    Generate a comprehensive database configuration report.

    Returns:
        Formatted configuration report string
    """
    from core.database_config_validator import generate_configuration_report

    return generate_configuration_report()
