# Design Document

## Overview

This design document outlines the implementation of a unified database management system that provides transparent access to both PostgreSQL and SQL Server databases across all Prefect flows. The system is built around a single `DatabaseManager` class that handles connection pooling, migration management, and query execution while integrating seamlessly with the existing configuration management system.

The design leverages SQLAlchemy for database abstraction, Pyway for migration management, and provides both ConfigManager and Prefect Blocks integration for credential management. The system emphasizes performance, reliability, and operational visibility through comprehensive monitoring and health checking capabilities.

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Prefect Flow Layer                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   RPA1 Flow     │  │   RPA2 Flow     │  │  RPA3 Flow  │ │
│  └─────────┬───────┘  └─────────┬───────┘  └─────┬───────┘ │
│            │                    │                │         │
│            └────────────────────┼────────────────┘         │
│                                 │                          │
│  ┌──────────────────────────────▼──────────────────────────┐ │
│  │              DatabaseManager Layer                      │ │
│  │  ┌─────────────────┐  ┌─────────────────┐              │ │
│  │  │  PostgreSQL     │  │   SQL Server    │              │ │
│  │  │  Engine Pool    │  │   Engine Pool   │              │ │
│  │  └─────────────────┘  └─────────────────┘              │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
            │                                    │
            ▼                                    ▼
┌─────────────────────┐                ┌─────────────────────┐
│   PostgreSQL DB     │                │   SQL Server DB     │
│                     │                │                     │
│ ┌─────────────────┐ │                │ ┌─────────────────┐ │
│ │  Flow Tables    │ │                │ │  Flow Tables    │ │
│ │  Migrations     │ │                │ │  (Read-Only)    │ │
│ │  Health Status  │ │                │ │  Health Status  │ │
│ └─────────────────┘ │                │ └─────────────────┘ │
└─────────────────────┘                └─────────────────────┘
```

### Component Architecture

```
core/
├── database.py              # DatabaseManager class
├── config.py               # Existing ConfigManager integration
└── migrations/             # Global migration directory
    ├── rpa_db/            # PostgreSQL migrations
    │   ├── V001__Create_processed_surveys.sql
    │   ├── V002__Add_survey_indexes.sql
    │   └── V003__Create_views.sql
    └── SurveyHub/         # SQL Server (read-only, no migrations)

flows/
├── rpa1/
│   └── workflow.py         # Uses DatabaseManager("rpa_db") and DatabaseManager("SurveyHub")
├── rpa2/
│   └── workflow.py         # Uses DatabaseManager("rpa_db") and DatabaseManager("SurveyHub")
└── rpa3/
    └── workflow.py         # Uses DatabaseManager("rpa_db") and DatabaseManager("SurveyHub")
```

## Components and Interfaces

### DatabaseManager Class

The `DatabaseManager` class is the core component that provides a unified interface for database operations. It manages a single database connection and provides methods for query execution, migration management, and health monitoring.

#### Key Responsibilities

- Manage SQLAlchemy engine for one specific database
- Provide unified query execution interface with multiple execution modes
- Handle connection pooling and health checks
- Execute database migrations using Pyway
- Support both ConfigManager and Prefect Blocks for credential management
- Provide comprehensive monitoring and diagnostics

#### Core Interface

```python
class DatabaseManager:
    def __init__(self, database_name: str)

    # Query Execution Methods
    def execute_query(self, query: str, params: Dict = None) -> List[Dict]
    def execute_query_with_timeout(self, query: str, params: Dict = None, timeout: int = 30) -> List[Dict]
    def execute_transaction(self, queries: List[tuple]) -> List[Dict]

    # Migration Management
    def run_migrations(self) -> None
    def get_migration_status(self) -> Dict

    # Health and Monitoring
    def health_check(self) -> Dict[str, Any]
    def get_pool_status(self) -> Dict[str, Any]

    # Context Manager Support
    def __enter__(self) -> 'DatabaseManager'
    def __exit__(self, exc_type, exc_val, exc_tb) -> None
```

#### Configuration Integration

The system uses the existing ConfigManager for all database credential management, maintaining consistency with current project patterns.

**ConfigManager Integration**

- **What it is**: Uses the existing ConfigManager class that reads from `.env` files
- **How it works**: Credentials stored in environment variables in `core/envs/.env.{environment}` files
- **Example**: `DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_db`
- **Benefits**:
  - Consistent with existing project patterns
  - File-based credential management
  - Environment-specific configuration
  - No additional setup required
  - Familiar to development team

**Configuration Structure:**

```env
# core/envs/.env.development
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_db
DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE=sqlserver
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://user:pass@server:1433/survey_hub?driver=ODBC+Driver+17+for+SQL+Server
DEVELOPMENT_GLOBAL_DATABASE_TIMEOUT=30
DEVELOPMENT_GLOBAL_CONNECTION_POOL_SIZE=5
```

**Usage Example:**

```python
# Simple usage - credentials loaded from ConfigManager
with DatabaseManager("rpa_db") as db:
    results = db.execute_query("SELECT * FROM customers")
```

> **📝 Future Enhancement Note**: Prefect Blocks integration can be added in the future as an alternative credential management approach while maintaining backward compatibility with the existing ConfigManager system.

#### Connection Management

**SQLAlchemy Engine Configuration:**

- QueuePool with configurable pool_size (default: 5) and max_overflow (default: 10)
- Pre-ping enabled for connection health validation
- Automatic connection disposal on context manager exit
- Thread-safe operation for concurrent Prefect tasks

**Connection Pool Monitoring:**

- Real-time pool status including active, idle, and overflow connections
- Connection health validation before query execution
- Automatic connection recovery for transient failures

### Migration System

The migration system uses Pyway for database schema management with the following design:

#### Migration File Organization

```
core/migrations/{database_name}/
├── V001__Create_initial_tables.sql
├── V002__Add_indexes.sql
├── V003__Create_views.sql
└── V004__Add_constraints.sql
```

#### Migration Execution Flow

1. **Initialization**: Pyway instance created with database-specific migration directory
2. **Discovery**: Pyway scans for migration files following V{version}\_\_{description}.sql pattern
3. **Validation**: Checksums validated to prevent tampered migration files
4. **Execution**: Sequential execution in version order with transaction support
5. **Tracking**: Migration state tracked in schema_version table

#### Migration Features

- **Automatic Execution**: Migrations run when DatabaseManager initializes (optional)
- **Manual Execution**: Explicit migration execution via run_migrations()
- **Status Tracking**: Current version and pending migrations via get_migration_status()
- **Error Handling**: Graceful failure handling with detailed error reporting
- **Environment Isolation**: Separate migration state per environment

### Query Execution Engine

The system provides multiple query execution modes to handle different use cases:

#### Standard Query Execution

```python
results = db.execute_query(
    "SELECT * FROM customers WHERE status = :status",
    {"status": "active"}
)
```

#### Transaction Support

```python
queries = [
    ("INSERT INTO orders (customer_id, amount) VALUES (:customer_id, :amount)", {"customer_id": 1, "amount": 100}),
    ("UPDATE customers SET last_order = NOW() WHERE id = :customer_id", {"customer_id": 1})
]
results = db.execute_transaction(queries)
```

#### Timeout Control

```python
results = db.execute_query_with_timeout(
    "SELECT * FROM large_table",
    timeout=60  # 60 second timeout
)
```

### Health Monitoring System

The health monitoring system provides comprehensive visibility into database operations:

#### Database Health Checks

- **Connection Testing**: Validates database connectivity
- **Query Testing**: Executes test queries to verify functionality
- **Response Time Measurement**: Tracks query execution performance
- **Migration Status**: Reports current migration version and pending changes
- **Error Reporting**: Detailed error information for troubleshooting

#### Connection Pool Monitoring

- **Pool Metrics**: Active, idle, overflow, and invalid connection counts
- **Pool Configuration**: Current pool size and overflow limits
- **Resource Utilization**: Connection pool utilization percentages
- **Performance Metrics**: Connection acquisition and release times

#### Health Check Response Format

```python
{
    "database_name": "rpa_db",
    "status": "healthy",  # healthy, degraded, unhealthy
    "connection": true,
    "query_test": true,
    "migration_status": {
        "current_version": "V003",
        "pending_migrations": []
    },
    "response_time_ms": 45.2,
    "timestamp": "2024-01-15T10:30:00Z"
}
```

## Data Models

### Configuration Data Model

The system uses a hierarchical configuration model:

```python
# Global Database Configuration Structure
{
    "database_name": {
        "type": "postgresql|sqlserver",
        "connection_string": "database_url",
        "pool_size": 5,
        "max_overflow": 10,
        "timeout": 30
    }
}

# Environment Variable Format
ENVIRONMENT_GLOBAL_{DATABASE_NAME}_TYPE=postgresql
ENVIRONMENT_GLOBAL_{DATABASE_NAME}_CONNECTION_STRING=postgresql://...
ENVIRONMENT_GLOBAL_{DATABASE_NAME}_POOL_SIZE=5
```

### Migration Data Model

Pyway manages migration state using the following schema:

```sql
CREATE TABLE schema_version (
    version_rank INTEGER NOT NULL,
    installed_rank INTEGER NOT NULL,
    version VARCHAR(50) NOT NULL PRIMARY KEY,
    description VARCHAR(200) NOT NULL,
    type VARCHAR(20) NOT NULL,
    script VARCHAR(1000) NOT NULL,
    checksum INTEGER,
    installed_by VARCHAR(100) NOT NULL,
    installed_on TIMESTAMP NOT NULL DEFAULT NOW(),
    execution_time INTEGER NOT NULL,
    success BOOLEAN NOT NULL
);
```

### Health Status Data Model

```python
# Individual Database Health Status
{
    "database_name": str,
    "database_type": str,
    "status": "healthy|degraded|unhealthy",
    "connection": bool,
    "query_test": bool,
    "migration_status": dict,
    "error": str,
    "timestamp": str,
    "response_time_ms": float
}

# Connection Pool Status
{
    "database_name": str,
    "pool_size": int,
    "checked_in": int,
    "checked_out": int,
    "overflow": int,
    "invalid": int,
    "timestamp": str
}
```

## Error Handling

### Error Categories and Handling Strategy

#### Configuration Errors

- **Missing Configuration**: Clear error messages with configuration guidance
- **Invalid Connection Strings**: Validation and format checking
- **Credential Issues**: Security-appropriate error messages without exposing sensitive data

#### Connection Errors

- **Network Issues**: Retry logic with exponential backoff using tenacity
- **Authentication Failures**: Clear error reporting with security considerations
- **Timeout Errors**: Configurable timeout handling with graceful degradation

#### Migration Errors

- **SQL Syntax Errors**: Detailed error reporting with file and line information
- **Permission Issues**: Clear guidance on required database permissions
- **Version Conflicts**: Conflict resolution guidance and rollback options

#### Query Execution Errors

- **SQL Errors**: Parameterized query validation and error reporting
- **Transaction Failures**: Automatic rollback with detailed failure information
- **Timeout Handling**: Graceful timeout with query cancellation

### Retry Logic Implementation

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10)
)
def execute_query_with_retry(self, query: str, params: Dict = None):
    """Execute query with automatic retry for transient failures."""
    return self.execute_query(query, params)
```

### Logging Integration

- **Prefect Integration**: Uses get_run_logger() for task context logging
- **Fallback Logging**: Standard Python logging for non-task contexts
- **Structured Logging**: Consistent log format with database name, operation, and timing
- **Security Considerations**: No sensitive credential information in logs

## Testing Strategy

### Unit Testing

- **DatabaseManager Class**: Mock SQLAlchemy engines for isolated testing
- **Configuration Loading**: Test ConfigManager and Prefect Blocks integration
- **Query Execution**: Mock database responses for query method testing
- **Error Handling**: Comprehensive error scenario testing

### Integration Testing

- **Database Connectivity**: Test actual database connections for both PostgreSQL and SQL Server
- **Migration Execution**: Test Pyway migration execution and rollback
- **Multi-Database Operations**: Test concurrent access to multiple databases
- **Health Monitoring**: Test health check accuracy and performance

### Performance Testing

- **Connection Pool Performance**: Test pool efficiency under concurrent load
- **Query Performance**: Benchmark query execution times
- **Migration Performance**: Test migration execution speed
- **Memory Usage**: Monitor memory consumption under various loads

### Test Database Setup

```python
# Test configuration for isolated testing
TEST_DATABASES = {
    "test_rpa_db": {
        "type": "postgresql",
        "connection_string": "postgresql://test_user:test_pass@localhost:5432/test_rpa_db"
    },
    "test_survey_hub": {
        "type": "sqlserver",
        "connection_string": "mssql+pyodbc://test_user:test_pass@localhost:1433/test_survey_hub"
    }
}
```

### Mock Testing Support

```python
# Mock DatabaseManager for unit testing
class MockDatabaseManager:
    def __init__(self, database_name: str):
        self.database_name = database_name
        self.mock_data = {}

    def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        return self.mock_data.get(query, [])

    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "database_name": self.database_name}
```

## Security Considerations

### Credential Management

- **Secure Storage**: Credentials stored in environment variables or Prefect Blocks
- **No Logging**: Sensitive information excluded from all logging
- **Environment Isolation**: Separate credentials per environment
- **Access Control**: Database user permissions follow principle of least privilege

### Connection Security

- **Encrypted Connections**: SSL/TLS enabled for all database connections
- **Connection String Validation**: Input validation for connection parameters
- **Timeout Controls**: Prevent resource exhaustion through configurable timeouts
- **Connection Pooling**: Secure connection reuse without credential exposure

### Query Security

- **Parameterized Queries**: All queries use parameterized execution to prevent SQL injection
- **Input Validation**: Query parameters validated before execution
- **Error Sanitization**: Database errors sanitized before logging or returning to users
- **Transaction Isolation**: Proper transaction boundaries to prevent data corruption

### Audit and Monitoring

- **Operation Logging**: All database operations logged with timestamps and user context
- **Health Monitoring**: Continuous monitoring of database connectivity and performance
- **Error Tracking**: Comprehensive error logging for security incident analysis
- **Access Patterns**: Monitor for unusual database access patterns

## Performance Optimization

### Connection Pooling Strategy

- **Pool Sizing**: Configurable pool size based on expected concurrent load
- **Connection Reuse**: Efficient connection reuse across multiple queries
- **Pool Monitoring**: Real-time visibility into pool utilization
- **Overflow Handling**: Graceful handling of peak load scenarios

### Query Optimization

- **Connection Management**: Automatic connection lifecycle management
- **Result Processing**: Efficient result set processing and memory management
- **Batch Operations**: Transaction support for batch data operations
- **Timeout Controls**: Prevent long-running queries from blocking resources

### Memory Management

- **Engine Reuse**: Single engine instance per database type for memory efficiency
- **Connection Cleanup**: Automatic resource cleanup on context manager exit
- **Result Streaming**: Efficient handling of large result sets
- **Garbage Collection**: Proper resource disposal to prevent memory leaks

### Monitoring and Metrics

- **Response Time Tracking**: Query execution time monitoring
- **Pool Utilization**: Connection pool usage metrics
- **Error Rate Monitoring**: Database operation success/failure rates
- **Resource Usage**: Memory and CPU usage monitoring for database operations
