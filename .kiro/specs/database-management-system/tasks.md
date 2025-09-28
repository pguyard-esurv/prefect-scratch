# Implementation Plan

- [x] 1. Set up project dependencies and core structure

  - Add required database dependencies to pyproject.toml (psycopg2-binary, pyodbc, pyway, sqlalchemy, tenacity)
  - Create core/database.py file with basic module structure
  - Set up migration directory structure at core/migrations/
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Implement core DatabaseManager class foundation

  - Create DatabaseManager class with **init** method that accepts database_name parameter
  - Implement lazy logger initialization with Prefect integration and fallback
  - Add basic error handling and logging structure
  - Implement context manager methods (**enter** and **exit**) with proper resource cleanup
  - Write unit tests for DatabaseManager initialization and context manager behavior
  - _Requirements: 1.1, 1.4, 7.1, 7.3_

- [x] 3. Implement configuration integration with ConfigManager

  - Add \_initialize_engine method that loads database configuration from ConfigManager
  - Implement database type and connection string retrieval using get_variable and get_secret
  - Add configuration validation with clear error messages for missing configuration
  - Create SQLAlchemy engine with QueuePool configuration (pool_size=5, max_overflow=10, pool_pre_ping=True)
  - Write unit tests for configuration loading, validation, and engine creation with mocked ConfigManager
  - _Requirements: 4.1, 4.2, 4.3, 4.5, 5.1, 5.2_

- [x] 4. Implement basic query execution functionality

  - Create execute_query method that accepts SQL query and optional parameters
  - Implement connection management using engine.connect() context manager
  - Add parameterized query execution using SQLAlchemy text() and parameter binding
  - Return results as list of dictionaries using row.\_mapping
  - Add basic error handling and logging for query execution
  - Write unit tests for query execution with mocked database connections and various query scenarios
  - _Requirements: 1.2, 1.4, 9.1_

- [x] 5. Implement advanced query execution methods

  - Create execute_query_with_timeout method with configurable timeout parameter
  - Implement execute_transaction method for multi-query transactions with rollback support
  - Add proper transaction management using conn.begin() context manager
  - Implement timeout handling using SQLAlchemy execution_options
  - Add comprehensive error handling for transaction failures and timeouts
  - Write unit tests for transaction rollback scenarios, timeout handling, and error conditions
  - _Requirements: 10.1, 10.2, 10.4, 10.5_

- [x] 6. Implement Pyway migration system integration

  - Create run_migrations method that initializes Pyway instance with database-specific migration directory
  - Implement get_migration_status method that returns current version and pending migrations
  - Add migration directory path construction using f"core/migrations/{database_name}"
  - Implement Pyway configuration with database_url, migration_dir, and schema_version_table
  - Add migration execution logging and error handling
  - Write unit tests for migration execution with test migration files and mocked Pyway instances
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 7. Implement health monitoring and diagnostics

  - Create health_check method that tests database connectivity and basic query execution
  - Implement response time measurement and status determination (healthy/degraded/unhealthy)
  - Add migration status inclusion in health check results
  - Create get_pool_status method that returns detailed connection pool metrics
  - Implement comprehensive error handling and logging for health check failures
  - Write unit tests for health check scenarios including healthy, degraded, and unhealthy states
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 5.5_

- [x] 8. Add retry logic and resilience features

  - Integrate tenacity library for configurable retry logic on database operations
  - Implement retry decorators for transient failure scenarios
  - Add exponential backoff configuration for connection retries
  - Create retry-enabled versions of key database operations
  - Add proper error classification to determine which errors should trigger retries
  - Write unit tests for retry behavior with simulated transient failures and permanent errors
  - _Requirements: 10.3, 1.4_

- [x] 9. Create comprehensive test suite

  - Write unit tests for DatabaseManager class with mocked SQLAlchemy engines
  - Create integration tests for actual database connectivity (PostgreSQL and SQL Server)
  - Implement migration testing with test migration files and rollback scenarios
  - Add health monitoring tests that verify accuracy of health check results
  - Create performance tests for connection pooling and concurrent query execution
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 10. Implement example migration files and flow integration

  - Create sample migration files in core/migrations/rpa_db/ following V{version}\_\_{description}.sql naming convention
  - Write example flow integration showing DatabaseManager usage with multiple databases
  - Implement concurrent task examples using DatabaseManager within Prefect .map() operations
  - Create health check integration examples for flow prerequisite validation
  - Add comprehensive error handling examples for production-ready flows
  - Write integration tests for example flows and migration execution in test environments
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 11. Add configuration examples and documentation

  - Create example .env configuration files for development, staging, and production environments
  - Document configuration variable naming conventions and required settings
  - Add connection string format examples for both PostgreSQL and SQL Server
  - Create troubleshooting guide for common configuration and connection issues
  - Implement configuration validation utilities for setup verification
  - _Requirements: 4.4, 9.2, 9.3, 9.4_

- [x] 12. Implement monitoring and operational utilities
  - Create database health check task that can be used across multiple flows
  - Implement connection pool monitoring utilities for operational visibility
  - Add database prerequisite validation task for flow startup checks
  - Create diagnostic utilities for troubleshooting database connectivity issues
  - Implement performance monitoring and metrics collection for database operations
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
