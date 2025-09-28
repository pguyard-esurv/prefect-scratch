# DatabaseManager Integration Examples

This directory contains comprehensive examples demonstrating how to use the `DatabaseManager` class in production Prefect flows. These examples showcase various integration patterns, error handling strategies, and best practices for database operations in RPA workflows.

## Overview

The examples demonstrate:

1. **Multi-database integration** - Working with both PostgreSQL and SQL Server
2. **Concurrent processing** - Using Prefect `.map()` with DatabaseManager
3. **Health monitoring** - Comprehensive health checks and prerequisite validation
4. **Error handling** - Production-ready error handling and recovery patterns
5. **Migration management** - Automated database schema management
6. **Performance monitoring** - Database operation metrics and trend analysis

## Example Flows

### 1. Database Integration Example (`database_integration_example.py`)

Demonstrates comprehensive DatabaseManager usage across multiple databases:

- **Health checks** before processing
- **Migration execution** with status tracking
- **Cross-database operations** (read from one DB, write to another)
- **Transaction management** with batch processing
- **Comprehensive logging** and error handling

**Key Features:**

- Reads survey data from source database (simulated SurveyHub)
- Processes and stores results in target database (PostgreSQL)
- Runs migrations automatically
- Provides detailed execution reporting

**Usage:**

```python
from flows.examples.database_integration_example import database_integration_example_flow

result = database_integration_example_flow(
    source_database="SurveyHub",
    target_database="rpa_db",
    run_migrations=True,
    health_check_required=True
)
```

### 2. Concurrent Database Processing (`concurrent_database_processing.py`)

Shows how to use DatabaseManager safely in concurrent Prefect tasks:

- **Concurrent order processing** using `.map()`
- **Thread-safe database operations**
- **Inventory checking** with simulated API calls
- **Result aggregation** from parallel operations
- **Performance metrics** collection

**Key Features:**

- Processes multiple orders concurrently
- Each task gets its own DatabaseManager instance
- Combines results from multiple concurrent operations
- Demonstrates proper connection management in concurrent scenarios

**Usage:**

```python
from flows.examples.concurrent_database_processing import concurrent_database_processing_flow

result = concurrent_database_processing_flow(
    database_name="rpa_db",
    max_concurrent_tasks=10
)
```

### 3. Health Check Integration (`health_check_integration.py`)

Demonstrates comprehensive health monitoring and prerequisite validation:

- **Multi-database health checks**
- **Prerequisite validation** before flow execution
- **Health trend analysis** over time
- **Operational recommendations**
- **Degradation detection**

**Key Features:**

- Validates all required databases are healthy
- Checks for required tables and migrations
- Analyzes historical performance trends
- Provides actionable operational recommendations
- Supports different health level requirements

**Usage:**

```python
from flows.examples.health_check_integration import health_check_integration_flow

result = health_check_integration_flow(
    target_databases=["rpa_db", "SurveyHub"],
    minimum_health_level="healthy",
    perform_trend_analysis=True,
    fail_on_prerequisites=True
)
```

### 4. Production Error Handling (`production_error_handling.py`)

Shows production-ready error handling patterns:

- **Comprehensive error classification**
- **Retry logic** with exponential backoff
- **Fallback database** support
- **Circuit breaker** pattern implementation
- **Error monitoring** and alerting

**Key Features:**

- Handles different types of database errors appropriately
- Implements fallback strategies for high availability
- Uses circuit breaker to prevent cascade failures
- Logs errors for monitoring and alerting
- Provides graceful degradation options

**Usage:**

```python
from flows.examples.production_error_handling import production_error_handling_flow

result = production_error_handling_flow(
    primary_database="rpa_db",
    fallback_database="rpa_db_backup",
    simulate_errors=False,
    enable_circuit_breaker=True
)
```

## Migration Files

The examples include sample migration files in `core/migrations/rpa_db/`:

- **V003\_\_Create_processed_surveys.sql** - Survey processing results table
- **V004\_\_Create_customer_orders.sql** - Customer order processing table
- **V005\_\_Create_flow_execution_logs.sql** - Flow execution monitoring table

These migrations demonstrate:

- Proper migration file naming conventions
- Index creation for performance
- Sample data insertion
- Production-ready table structures

## Running the Examples

### Quick Start

Run all examples with the provided script:

```bash
python flows/examples/run_example_flows.py
```

### Individual Examples

Run individual examples directly:

```bash
# Database integration example
python flows/examples/database_integration_example.py

# Concurrent processing example
python flows/examples/concurrent_database_processing.py

# Health check integration example
python flows/examples/health_check_integration.py

# Production error handling example
python flows/examples/production_error_handling.py
```

### Integration Tests

Run comprehensive integration tests:

```bash
# Run all integration tests
pytest flows/examples/test/test_example_flows_integration.py -v

# Run specific test class
pytest flows/examples/test/test_example_flows_integration.py::TestDatabaseIntegrationExample -v

# Run with coverage
pytest flows/examples/test/test_example_flows_integration.py --cov=flows.examples
```

## Configuration Requirements

### Database Configuration

Ensure your environment configuration includes:

```env
# Development environment example
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_db
DEVELOPMENT_GLOBAL_RPA_DB_POOL_SIZE=5
DEVELOPMENT_GLOBAL_RPA_DB_MAX_OVERFLOW=10

# Optional: SurveyHub configuration for cross-database examples
DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE=sqlserver
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://user:pass@server:1433/survey_hub?driver=ODBC+Driver+17+for+SQL+Server
```

### Prerequisites

1. **Database Setup**: Ensure target databases exist and are accessible
2. **Migrations**: Migration tables will be created automatically
3. **Permissions**: Database user needs CREATE, INSERT, UPDATE, DELETE permissions
4. **Dependencies**: All required Python packages installed (see `pyproject.toml`)

## Best Practices Demonstrated

### 1. Connection Management

- Use context managers (`with DatabaseManager(db_name) as db:`)
- Let DatabaseManager handle connection pooling
- Don't share DatabaseManager instances across tasks

### 2. Error Handling

- Classify errors appropriately (connection, SQL, resource, etc.)
- Implement retry logic for transient failures
- Use fallback strategies for high availability
- Log errors with sufficient context for debugging

### 3. Health Monitoring

- Perform health checks before critical operations
- Monitor response times and connection pool utilization
- Track migration status and pending changes
- Generate actionable operational recommendations

### 4. Concurrent Processing

- Each concurrent task should create its own DatabaseManager instance
- Use transactions for batch operations
- Aggregate results properly after concurrent execution
- Monitor performance metrics across concurrent operations

### 5. Migration Management

- Follow V{version}\_\_{description}.sql naming convention
- Include rollback considerations in migration design
- Test migrations in development environments first
- Monitor migration status in production

## Troubleshooting

### Common Issues

1. **Connection Errors**

   - Verify database configuration in environment files
   - Check network connectivity and firewall settings
   - Ensure database server is running and accessible

2. **Migration Failures**

   - Check migration file syntax and permissions
   - Verify migration directory structure
   - Review migration logs for specific error details

3. **Performance Issues**

   - Monitor connection pool utilization
   - Check for long-running queries
   - Review database server performance metrics

4. **Concurrent Processing Issues**
   - Ensure each task creates its own DatabaseManager instance
   - Check for connection pool exhaustion
   - Monitor for deadlocks in concurrent operations

### Getting Help

1. Check the comprehensive error messages in flow logs
2. Review health check results for system status
3. Examine migration status for schema issues
4. Use the integration tests to validate setup

## Contributing

When adding new examples:

1. Follow the established patterns for error handling and logging
2. Include comprehensive docstrings and type hints
3. Add corresponding integration tests
4. Update this README with example documentation
5. Ensure examples work with the provided test database setup

## Related Documentation

- [Database Management Design](../../docs/DATABASE_MANAGEMENT_DESIGN.md)
- [DatabaseManager API Documentation](../../core/database.py)
- [Configuration System](../../docs/CONFIGURATION_SYSTEM.md)
- [Testing Strategy](../../docs/TESTING_STRATEGY.md)
