# 🗄️ Database Management System - Design Document

## 📋 Executive Summary

This document outlines the design for a unified database management system that provides transparent access to both PostgreSQL and SQL Server databases across all Prefect flows. The system enables flows to manage their own database tables through simple migration files while leveraging SQLAlchemy's connection pooling and the existing configuration management system.

## 🎯 Core Requirements

### **Primary Goals**

- ✅ **Multi-Database Support**: Seamless access to PostgreSQL and SQL Server
- ✅ **Flow-Specific Tables**: Each flow manages its own database schema
- ✅ **Simple Migrations**: SQL-based migration system with automatic execution
- ✅ **Connection Pooling**: Efficient database connection management
- ✅ **Configuration Integration**: Leverage existing `.env` file system
- ✅ **Transparent Usage**: Flows use simple `execute_query()` calls

### **Secondary Goals**

- ✅ **Performance Optimization**: Connection reuse and pooling
- ✅ **Error Handling**: Robust error handling and logging
- ✅ **Environment Support**: Development, staging, and production configurations
- ✅ **Security**: Secure connection string management
- ✅ **Monitoring**: Database health and performance monitoring

## 🏛️ System Architecture

### **High-Level Overview**

```
┌─────────────────────────────────────────────────────────────┐
│                    Prefect Flow                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   RPA1 Flow     │  │   RPA2 Flow     │  │  RPA3 Flow  │ │
│  └─────────┬───────┘  └─────────┬───────┘  └─────┬───────┘ │
│            │                    │                │         │
│            └────────────────────┼────────────────┘         │
│                                 │                          │
│  ┌──────────────────────────────▼──────────────────────────┐ │
│  │              DatabaseManager                            │ │
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
│ │  RPA1 Tables    │ │                │ │  RPA1 Tables    │ │
│ │  RPA2 Tables    │ │                │ │  RPA2 Tables    │ │
│ │  RPA3 Tables    │ │                │ │  RPA3 Tables    │ │
│ └─────────────────┘ │                │ └─────────────────┘ │
└─────────────────────┘                └─────────────────────┘
```

### **Component Architecture**

```
core/
├── database.py              # DatabaseManager class
├── config.py               # Existing ConfigManager
└── migrations/             # Global migration utilities
    ├── rpa_db/
    │   ├── V001__Create_processed_surveys.sql
    │   ├── V002__Add_survey_indexes.sql
    │   └── V003__Create_views.sql
    └── SurveyHub/
        └── (read-only, no migrations)

flows/
├── rpa1/
│   └── workflow.py         # Uses DatabaseManager("rpa_db") and DatabaseManager("SurveyHub")
├── rpa2/
│   └── workflow.py         # Uses DatabaseManager("rpa_db") and DatabaseManager("SurveyHub")
└── rpa3/
    └── workflow.py         # Uses DatabaseManager("rpa_db") and DatabaseManager("SurveyHub")
```

## 🗄️ Database Design

### **Connection Management**

- **Engine Pooling**: SQLAlchemy QueuePool with configurable pool size
- **Connection Reuse**: Single engine instance per database type per flow
- **Health Checks**: Pre-ping connections before use
- **Environment Isolation**: Separate connections per environment

### **Migration System (Pyway Integration)**

- **Pyway-Based**: Uses Pyway library for migration management
- **SQL-First**: Pure SQL migration files with versioning
- **Sequential Execution**: Files executed in version order (V001, V002, etc.)
- **Flow Isolation**: Each flow manages its own migrations
- **Environment Support**: Migrations run per environment
- **Automatic Tracking**: Pyway handles migration state tracking

### **Configuration Integration**

- **Environment Variables**: Database connection strings from `.env` files
- **Flow-Specific Overrides**: Flow-specific database configurations
- **Secret Management**: Secure storage of connection credentials
- **Environment Detection**: Automatic environment-based configuration

## 🔧 Core Components

### **1. DatabaseManager Class**

**Purpose**: Single database management and connection pooling

**Key Responsibilities**:

- Manage SQLAlchemy engine for one specific database
- Provide unified query execution interface
- Handle connection pooling and health checks
- Execute database migrations using Pyway
- Use global configuration (no flow-specific config needed)

**Key Methods**:

- `execute_query(query, params)`: Execute query and return results
- `run_migrations()`: Execute Pyway migrations for this database
- `get_migration_status()`: Get current migration status and version
- `health_check()`: Get connection health information

**Implementation Example**:

```python
# core/database.py
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from pyway import Pyway
from core.config import ConfigManager
from typing import Dict, List, Any, Optional
import os
import time
from datetime import datetime
from prefect import get_run_logger
from prefect.context import get_run_context

class DatabaseManager:
    """Single database manager with Pyway migration support."""

    def __init__(self, database_name: str):
        self.database_name = database_name
        self.config = ConfigManager()  # Use global config
        self.engine = None
        self.pyway_instance = None
        self._logger = None  # Lazy initialization for task context

        # Initialize engine on first use
        self._initialize_engine()

    @property
    def logger(self):
        """Lazy logger initialization for proper Prefect task context."""
        if self._logger is None:
            try:
                self._logger = get_run_logger()
            except RuntimeError:
                # Fallback for non-task contexts
                import logging
                self._logger = logging.getLogger(f"database.{self.database_name}")
        return self._logger

    def _initialize_engine(self):
        """Initialize SQLAlchemy engine for this database."""
        if self.engine is None:
            # Get database type and connection string from config
            db_type = self.config.get_variable(f"{self.database_name}_type")
            connection_string = self.config.get_secret(f"{self.database_name}_connection_string")

            if not db_type or not connection_string:
                raise ValueError(f"Database '{self.database_name}' not configured globally")

            self.engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True
            )

    def execute_query(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute query and return results as list of dictionaries."""
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return [dict(row._mapping) for row in result.fetchall()]

    def __enter__(self):
        """Context manager entry for proper resource management."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit for proper resource cleanup."""
        try:
            if self.engine:
                self.engine.dispose()
                self.logger.debug(f"Disposed engine for {self.database_name}")
        except Exception as e:
            self.logger.warning(f"Error disposing engine for {self.database_name}: {e}")

    def run_migrations(self) -> None:
        """Run Pyway migrations for this database."""
        if self.pyway_instance is None:
            connection_string = self.config.get_secret(f"{self.database_name}_connection_string")
            migration_dir = f"core/migrations/{self.database_name}"
            self.pyway_instance = Pyway(
                database_url=connection_string,
                migration_dir=migration_dir,
                schema_version_table="schema_version"
            )

        self.logger.info(f"Running migrations for {self.database_name}...")
        self.pyway_instance.migrate()
        self.logger.info(f"Migrations completed for {self.database_name}")

    def get_migration_status(self) -> Dict:
        """Get current migration status and version."""
        if self.pyway_instance:
            return self.pyway_instance.info()
        return {"status": "not_initialized"}

    def health_check(self) -> Dict[str, Any]:
        """Perform health check for this database."""
        health_status = {
            "database_name": self.database_name,
            "status": "unknown",
            "connection": False,
            "query_test": False,
            "migration_status": None,
            "error": None,
            "timestamp": datetime.now().isoformat(),
            "response_time_ms": None
        }

        start_time = time.time()

        try:
            with self.engine.connect() as conn:
                health_status["connection"] = True

                # Test basic query execution
                result = conn.execute(text("SELECT 1 as health_check"))
                if result.fetchone()[0] == 1:
                    health_status["query_test"] = True

                # Get migration status if available
                try:
                    migration_status = self.get_migration_status()
                    health_status["migration_status"] = migration_status
                except Exception:
                    health_status["migration_status"] = "unavailable"

            # Calculate response time
            response_time = (time.time() - start_time) * 1000
            health_status["response_time_ms"] = round(response_time, 2)

            # Overall status
            if health_status["connection"] and health_status["query_test"]:
                health_status["status"] = "healthy"
            else:
                health_status["status"] = "degraded"

        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
            health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
            self.logger.error(f"Health check failed for {self.database_name}: {e}")

        return health_status

    def get_pool_status(self) -> Dict[str, Any]:
        """Get connection pool status for monitoring."""
        if not self.engine:
            return {"status": "not_initialized"}

        try:
            pool = self.engine.pool
            return {
                "database_name": self.database_name,
                "pool_size": pool.size(),
                "checked_in": pool.checkedin(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "invalid": pool.invalid(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "database_name": self.database_name,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def execute_transaction(self, queries: List[tuple]) -> List[Dict]:
        """Execute multiple queries in a single transaction."""
        with self.engine.connect() as conn:
            with conn.begin():
                results = []
                for query, params in queries:
                    result = conn.execute(text(query), params or {})
                    results.append([dict(row._mapping) for row in result.fetchall()])
                return results

    def execute_query_with_timeout(self, query: str, params: Dict = None, timeout: int = 30) -> List[Dict]:
        """Execute query with configurable timeout."""
        with self.engine.connect() as conn:
            result = conn.execute(
                text(query),
                params or {},
                execution_options={"timeout": timeout}
            )
            conn.commit()
            return [dict(row._mapping) for row in result.fetchall()]
```

### **2. Migration System (Pyway Integration)**

**Purpose**: Manage database schema changes per flow using Pyway

**Key Features**:

- **Pyway Integration**: Uses Pyway library for migration management
- **SQL-First Approach**: Pure SQL migration files with versioning
- **Sequential Execution**: Automatic ordering by version number (V001, V002, etc.)
- **Flow Isolation**: Each flow has its own migration directory
- **Environment Support**: Migrations run per environment
- **Automatic Tracking**: Pyway handles migration state and version tracking
- **Checksum Validation**: Prevents tampered migration files
- **Error Handling**: Graceful handling of migration failures

**Migration File Structure**:

```
core/migrations/
├── {database_name}/
│   ├── V001__Create_initial_tables.sql
│   ├── V002__Add_indexes.sql
│   ├── V003__Create_views.sql
│   └── V004__Add_constraints.sql
└── {another_database}/
    ├── V001__Create_initial_tables.sql
    └── V002__Add_indexes.sql
```

**Example Structure**:

```
core/migrations/
├── rpa_db/
│   ├── V001__Create_processed_surveys_table.sql
│   ├── V002__Add_survey_indexes.sql
│   └── V003__Create_survey_summary_view.sql
└── SurveyHub/
    └── (read-only, no migrations)
```

**Migration Naming Convention**:

- Format: `V{version}__{description}.sql`
- Version: Sequential number with leading zeros (V001, V002, etc.)
- Description: Descriptive name with underscores for spaces
- Examples: `V001__Create_customers_table.sql`, `V002__Add_email_index.sql`

### **3. Configuration Integration**

**Purpose**: Leverage existing ConfigManager system

**Integration Points**:

- **ConfigManager**: Use existing configuration system
- **Environment Variables**: Database connection strings from `.env` files
- **Global Configuration**: All database settings in core configuration
- **Secret Management**: Secure credential storage

> **📝 Future Enhancement Note**: Prefect Blocks integration can be added in the future as an alternative credential management approach. This would provide native Prefect credential management while maintaining backward compatibility with the existing ConfigManager system.

**Configuration Hierarchy**:

1. Global database settings (`.env.{environment}`)
2. Default fallback values

**Configuration Examples**:

#### **Global Database Configuration**

```env
# core/envs/.env.development
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_db
DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE=sqlserver
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://user:pass@survey-server:1433/survey_hub?driver=ODBC+Driver+17+for+SQL+Server
DEVELOPMENT_GLOBAL_DATABASE_TIMEOUT=30
DEVELOPMENT_GLOBAL_CONNECTION_POOL_SIZE=5
```

#### **Production Configuration**

```env
# core/envs/.env.production
PRODUCTION_GLOBAL_RPA_DB_TYPE=postgresql
PRODUCTION_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://prod_user:${POSTGRES_PASSWORD}@prod-db:5432/rpa_db
PRODUCTION_GLOBAL_SURVEYHUB_TYPE=sqlserver
PRODUCTION_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://prod_user:${SQL_PASSWORD}@survey-server:1433/survey_hub?driver=ODBC+Driver+17+for+SQL+Server
PRODUCTION_GLOBAL_DATABASE_TIMEOUT=60
PRODUCTION_GLOBAL_CONNECTION_POOL_SIZE=10
```

## 📦 **Dependencies**

Add the following to your `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies
    "psycopg2-binary>=2.9.0",  # PostgreSQL adapter
    "pyodbc>=4.0.0",           # SQL Server adapter
    "pyway>=1.0.0",            # Database migration tool
    "sqlalchemy>=2.0.0",       # Database ORM with connection pooling
    "tenacity>=8.0.0",         # Retry logic for database operations
]
```

### **Dependency Details**

- **psycopg2-binary**: PostgreSQL database adapter for Python
- **pyodbc**: SQL Server database adapter for Python
- **pyway**: Database migration tool inspired by Flyway
- **sqlalchemy**: Database ORM with connection pooling support
- **tenacity**: Retry logic library for resilient database operations

## 🚀 Usage Patterns

### **Flow Integration**

**Pattern**: Flows initialize separate DatabaseManager instances for each database

**Typical Usage**:

1. Initialize separate DatabaseManager instances for each database
2. Run Pyway migrations for required databases
3. Execute queries using `execute_query(query)`
4. Process results in Prefect tasks

**Example Pattern**:

```python
# Initialize database managers using context managers
with DatabaseManager("rpa_db") as rpa_db, \
     DatabaseManager("SurveyHub") as survey_hub:

    # Query from one database
    records = survey_hub.execute_query("SELECT * FROM survey_responses")

    # Process records concurrently using .map()
    processed_records = process_survey_record.map(records)

    # Save results to another database
    write_results = write_processed_record.map(processed_records)
```

**Flow Integration Example**:

```python
# flows/rpa1/workflow.py
from prefect import flow, task, get_run_logger
from core.database import DatabaseManager

@task
def process_survey_data(survey_responses: list[dict]) -> list[dict]:
    """Process survey response data."""
    logger = get_run_logger()
    logger.info(f"Processing {len(survey_responses)} survey responses")

    # Process each survey response
    processed = []
    for response in survey_responses:
        try:
            # Calculate satisfaction score from response data
            response_data = json.loads(response["response_data"])
            satisfaction_score = calculate_satisfaction_score(response_data)

            processed.append({
                "survey_id": response["survey_id"],
                "customer_id": response["customer_id"],
                "satisfaction_score": satisfaction_score,
                "processed_at": datetime.now().isoformat(),
                "status": "completed"
            })
        except Exception as e:
            processed.append({
                "survey_id": response["survey_id"],
                "customer_id": response["customer_id"],
                "satisfaction_score": None,
                "processed_at": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            })

    return processed

def calculate_satisfaction_score(response_data: dict) -> float:
    """Calculate satisfaction score from survey response data."""
    # Simple scoring logic - replace with actual business logic
    ratings = [int(response_data.get(f"question_{i}", 3)) for i in range(1, 6)]
    return sum(ratings) / len(ratings) if ratings else 0.0

@flow(name="rpa1-database-workflow")
def rpa1_workflow():
    """RPA1 workflow with database integration."""
    logger = get_run_logger()
    logger.info("Starting RPA1 database workflow")

    # Initialize database managers - one per database
    rpa_db = DatabaseManager("rpa_db")
    survey_hub = DatabaseManager("SurveyHub")

    # Run migrations for PostgreSQL database
    logger.info("Running database migrations...")
    rpa_db.run_migrations()

    # Query data from SQL Server (SurveyHub) - read-only
    logger.info("Querying survey responses from SurveyHub...")
    survey_responses = survey_hub.execute_query(
        "SELECT survey_id, customer_id, response_data, submitted_at FROM survey_responses WHERE processed = 0"
    )

    # Process survey data
    processed_surveys = process_survey_data(survey_responses)

    # Write results to PostgreSQL (rpa_db)
    for survey in processed_surveys:
        rpa_db.execute_query(
            """INSERT INTO rpa1_processed_surveys
               (survey_id, customer_id, satisfaction_score, processed_at, status)
               VALUES (:survey_id, :customer_id, :satisfaction_score, :processed_at, :status)""",
            {
                "survey_id": survey["survey_id"],
                "customer_id": survey["customer_id"],
                "satisfaction_score": survey["satisfaction_score"],
                "processed_at": survey["processed_at"],
                "status": survey["status"]
            }
        )

    logger.info("RPA1 workflow completed successfully")
    return {"surveys_processed": len(processed_surveys), "responses_found": len(survey_responses)}
```

### **Migration Management with Pyway**

**Pattern**: Versioned SQL files in global migration directories

**Migration Lifecycle**:

1. Create versioned SQL migration files (V001, V002, etc.) in `core/migrations/{database_name}/`
2. Pyway automatically executes pending migrations when DatabaseManager is initialized
3. Sequential execution ensures proper ordering
4. Pyway tracks migration state and prevents re-execution
5. Error handling prevents partial migrations

**User Workflow for Database Changes**:

#### **Step 1: Create Migration File**

```bash
# Create new migration file
touch core/migrations/rpa_db/V005__Add_customer_phone_column.sql
```

#### **Step 2: Write SQL Migration**

```sql
-- V005__Add_customer_phone_column.sql
ALTER TABLE customers ADD COLUMN phone VARCHAR(20);
CREATE INDEX idx_customers_phone ON customers(phone);
```

#### **Step 3: Migration Execution**

- **Automatic**: Runs when flow starts
- **Manual**: Can be run manually for testing
- **Status Check**: View current migration status

### **Migration Types and Examples**

#### **Creating Tables**

```sql
-- V001__Create_customers_table.sql
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### **Adding Columns**

```sql
-- V002__Add_customer_phone.sql
ALTER TABLE customers ADD COLUMN phone VARCHAR(20);
```

#### **Creating Indexes**

```sql
-- V003__Add_customer_indexes.sql
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_phone ON customers(phone);
```

#### **Adding Constraints**

```sql
-- V004__Add_customer_constraints.sql
ALTER TABLE customers
ADD CONSTRAINT chk_customers_email
CHECK (email LIKE '%@%');
```

#### **Simple Data Updates**

```sql
-- V005__Update_customer_data.sql
UPDATE customers
SET phone = 'N/A'
WHERE phone IS NULL;
```

#### **Creating Views**

```sql
-- V006__Create_active_customers_view.sql
CREATE VIEW active_customers AS
SELECT id, name, email, phone
FROM customers
WHERE created_at > '2024-01-01';
```

### **Multi-Database Queries**

**Pattern**: Transparent access to multiple database types

**Common Scenarios**:

- Query PostgreSQL for customer data
- Query SQL Server for order information
- Join data across database types in application logic
- Write results back to appropriate database

### **Migration Status and Monitoring**

**Pattern**: Check migration status and health

**Status Checking**:

```python
# Check migration status
status = db.get_migration_status("rpa_db")
print(f"Current version: {status.current_version}")
print(f"Pending migrations: {status.pending_migrations}")

# Example status response
{
    "current_version": "V003",
    "pending_migrations": ["V004", "V005"],
    "total_migrations": 3,
    "last_migration": "2024-01-15T10:30:00Z"
}
```

**Error Handling Example**:

```python
# flows/rpa1/workflow.py
from prefect import flow, task, get_run_logger
from core.database import DatabaseManager

@flow(name="rpa1-with-error-handling")
def rpa1_workflow():
    """RPA1 workflow with comprehensive error handling."""
    logger = get_run_logger()

    try:
        # Initialize database managers - one per database
        rpa_db = DatabaseManager("rpa_db")
        survey_hub = DatabaseManager("SurveyHub")

        # Run migrations with error handling (only for PostgreSQL)
        try:
            rpa_db.run_migrations()
            logger.info("rpa_db migrations completed successfully")
        except Exception as e:
            logger.error(f"rpa_db migration failed: {e}")
            raise

        # Query data with error handling
        try:
            survey_responses = survey_hub.execute_query(
                "SELECT survey_id, customer_id, response_data FROM survey_responses WHERE processed = 0"
            )
            logger.info(f"Retrieved {len(survey_responses)} survey responses")
        except Exception as e:
            logger.error(f"Failed to query survey responses: {e}")
            raise

        return {"status": "success", "survey_responses_processed": len(survey_responses)}

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        return {"status": "failed", "error": str(e)}
```

### **Concurrent Survey Processing Pattern**

**Purpose**: Process survey data using Prefect's concurrent task execution

**Concurrent Task Implementation**:

```python
# flows/rpa1/workflow.py - Concurrent processing example
from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
from core.database import DatabaseManager
from datetime import datetime
import json

@task(task_run_name="process-survey-{survey_response[survey_id]}")
def process_survey_data_concurrently(survey_response: dict) -> dict:
    """Process individual survey response data concurrently."""
    logger = get_run_logger()

    try:
        # Calculate satisfaction score from response data
        response_data = json.loads(survey_response["response_data"])
        satisfaction_score = calculate_satisfaction_score(response_data)

        logger.info(f"Processed survey {survey_response['survey_id']} with score {satisfaction_score}")

        return {
            "survey_id": survey_response["survey_id"],
            "customer_id": survey_response["customer_id"],
            "satisfaction_score": satisfaction_score,
            "processed_at": datetime.now().isoformat(),
            "status": "completed"
        }
    except Exception as e:
        logger.error(f"Failed to process survey {survey_response['survey_id']}: {e}")
        return {
            "survey_id": survey_response["survey_id"],
            "customer_id": survey_response["customer_id"],
            "satisfaction_score": None,
            "processed_at": datetime.now().isoformat(),
            "status": "failed",
            "error": str(e)
        }

@task(task_run_name="write-survey-results-{processed_survey[survey_id]}")
def write_survey_results(processed_survey: dict) -> dict:
    """Write processed survey results to database."""
    logger = get_run_logger()

    try:
        # Initialize database manager within task context
        with DatabaseManager("rpa_db") as rpa_db:
            rpa_db.execute_query(
                """INSERT INTO rpa1_processed_surveys
                   (survey_id, customer_id, satisfaction_score, processed_at, status)
                   VALUES (:survey_id, :customer_id, :satisfaction_score, :processed_at, :status)""",
                {
                    "survey_id": processed_survey["survey_id"],
                    "customer_id": processed_survey["customer_id"],
                    "satisfaction_score": processed_survey["satisfaction_score"],
                    "processed_at": processed_survey["processed_at"],
                    "status": processed_survey["status"]
                }
            )

        logger.info(f"Successfully wrote survey {processed_survey['survey_id']} to database")
        return {"survey_id": processed_survey["survey_id"], "write_status": "success"}

    except Exception as e:
        logger.error(f"Failed to write survey {processed_survey['survey_id']}: {e}")
        return {"survey_id": processed_survey["survey_id"], "write_status": "failed", "error": str(e)}

@flow(
    name="rpa1-concurrent-workflow",
    task_runner=ConcurrentTaskRunner(max_workers=8),  # Concurrent execution
    description="RPA1 workflow with concurrent survey processing"
)
def rpa1_concurrent_workflow():
    """RPA1 workflow with concurrent task execution."""
    logger = get_run_logger()
    logger.info("Starting RPA1 concurrent workflow")

    # Validate database health first
    database_names = ["rpa_db", "SurveyHub"]
    health_check_passed = validate_database_prerequisites(database_names, "rpa1")

    if not health_check_passed:
        logger.error("Database health check failed - aborting workflow")
        return {"status": "aborted", "reason": "database_health_check_failed"}

    # Initialize database managers using context managers
    with DatabaseManager("rpa_db") as rpa_db, \
         DatabaseManager("SurveyHub") as survey_hub:

        # Run migrations for PostgreSQL database
        logger.info("Running database migrations...")
        rpa_db.run_migrations()

        # Query data from SQL Server (SurveyHub) - read-only
        logger.info("Querying survey responses from SurveyHub...")
        survey_responses = survey_hub.execute_query(
            "SELECT survey_id, customer_id, response_data, submitted_at FROM survey_responses WHERE processed = 0"
        )

         logger.info(f"Found {len(survey_responses)} survey responses to process")

         # Process survey data concurrently (max 8 concurrent tasks)
         if survey_responses:
             processed_surveys = process_survey_data_concurrently.map(survey_responses)

             # Write results to PostgreSQL concurrently
             write_results = write_survey_results.map(processed_surveys)
         else:
             logger.info("No survey responses found to process")
             processed_surveys = []
             write_results = []

        # Analyze results
        successful_writes = sum(1 for result in write_results if result["write_status"] == "success")
        failed_writes = len(write_results) - successful_writes

        logger.info(f"Workflow completed: {successful_writes} successful, {failed_writes} failed")

        return {
            "status": "success",
            "surveys_processed": len(processed_surveys),
            "successful_writes": successful_writes,
            "failed_writes": failed_writes,
            "responses_found": len(survey_responses),
            "timestamp": datetime.now().isoformat()
        }
```

**Migration Tracking**:

- Pyway automatically creates `schema_version` table
- Tracks executed migrations with checksums
- Prevents execution of modified migration files
- Provides audit trail of all migrations

### **Database Health Monitoring**

**Pattern**: Monitor database connectivity and operational status

**Health Check Implementation**:

```python
# core/database.py - Add to DatabaseManager class
def health_check(self, database_name: str) -> Dict[str, Any]:
    """Perform comprehensive health check for specific database."""
    # Get database type from configuration
    try:
        db_type = self.config.get_variable(f"{database_name}_type")
    except Exception:
        db_type = "unknown"

    health_status = {
        "database_name": database_name,
        "database_type": db_type,
        "status": "unknown",
        "connection": False,
        "query_test": False,
        "migration_status": None,
        "error": None,
        "timestamp": datetime.now().isoformat(),
        "response_time_ms": None
    }

    start_time = time.time()

    try:
        # Test basic connection
        engine = self.get_engine(database_name)
        with engine.connect() as conn:
            health_status["connection"] = True

            # Test basic query execution
            result = conn.execute(text("SELECT 1 as health_check"))
            if result.fetchone()[0] == 1:
                health_status["query_test"] = True

            # Get migration status if Pyway is configured (only for writable databases)
            if db_type == "postgresql":
                try:
                    migration_status = self.get_migration_status(database_name)
                    health_status["migration_status"] = migration_status
                except Exception:
                    health_status["migration_status"] = "unavailable"
            else:
                health_status["migration_status"] = "read_only"

        # Calculate response time
        response_time = (time.time() - start_time) * 1000
        health_status["response_time_ms"] = round(response_time, 2)

        # Overall status
        if health_status["connection"] and health_status["query_test"]:
            health_status["status"] = "healthy"
        else:
            health_status["status"] = "degraded"

    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["error"] = str(e)
        health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        self.logger.error(f"Health check failed for {database_name}: {e}")

    return health_status

def health_check_all(self) -> Dict[str, Any]:
    """Perform health check for all configured database types."""
    overall_health = {
        "flow_name": self.flow_name,
        "overall_status": "unknown",
        "databases": {},
        "timestamp": datetime.now().isoformat()
    }

    # Check configured databases
    database_names = ["rpa_db", "survey_hub"]
    healthy_count = 0

    for database_name in database_names:
        try:
            # Only check if connection string is configured
            connection_string = self.config.get_secret(f"{database_name}_connection_string")
            if connection_string:
                health_status = self.health_check(database_name)
                overall_health["databases"][database_name] = health_status

                if health_status["status"] == "healthy":
                    healthy_count += 1
        except Exception as e:
            overall_health["databases"][database_name] = {
                "status": "not_configured",
                "error": f"Configuration missing: {e}"
            }

    # Determine overall status
    total_configured = len([db for db in overall_health["databases"].values()
                           if db.get("status") != "not_configured"])

    if total_configured == 0:
        overall_health["overall_status"] = "not_configured"
    elif healthy_count == total_configured:
        overall_health["overall_status"] = "healthy"
    elif healthy_count > 0:
        overall_health["overall_status"] = "degraded"
    else:
        overall_health["overall_status"] = "unhealthy"

    return overall_health
```

**Health Check Task Integration**:

```python
# flows/rpa1/workflow.py - Add health check task
from prefect import task, get_run_logger
from datetime import datetime
import time

@task(retries=1, retry_delay_seconds=10, task_run_name="health-check-{database_names}")
def database_health_check(database_names: list[str], flow_name: str) -> Dict[str, Any]:
    """Comprehensive database health check task."""
    logger = get_run_logger()
    logger.info(f"Starting database health check for {database_names}")

    overall_health = {
        "flow_name": flow_name,
        "overall_status": "unknown",
        "databases": {},
        "timestamp": datetime.now().isoformat()
    }

    healthy_count = 0

    for database_name in database_names:
        try:
            # Use context manager for proper resource cleanup
            with DatabaseManager(database_name) as db:
                health_status = db.health_check()
                overall_health["databases"][database_name] = health_status

                if health_status["status"] == "healthy":
                    healthy_count += 1

                # Log details
                db_status = health_status.get("status", "unknown")
                response_time = health_status.get("response_time_ms", "N/A")
                logger.info(f"{database_name}: {db_status} ({response_time}ms)")

                if health_status.get("error"):
                    logger.warning(f"{database_name} error: {health_status['error']}")

        except Exception as e:
            overall_health["databases"][database_name] = {
                "status": "error",
                "error": str(e)
            }
            logger.error(f"Health check failed for {database_name}: {e}")

    # Determine overall status
    total_databases = len(database_names)
    if healthy_count == total_databases:
        overall_health["overall_status"] = "healthy"
    elif healthy_count > 0:
        overall_health["overall_status"] = "degraded"
    else:
        overall_health["overall_status"] = "unhealthy"

    logger.info(f"Database health check completed: {overall_health['overall_status']}")
    return overall_health

@task(task_run_name="validate-db-prerequisites")
def validate_database_prerequisites(database_names: list[str], flow_name: str) -> bool:
    """Validate that databases are healthy before starting main workflow."""
    logger = get_run_logger()

    health_status = database_health_check(database_names, flow_name)
    overall_status = health_status.get("overall_status")

    if overall_status in ["healthy", "degraded"]:
        logger.info("Database prerequisites validated successfully")
        return True
    else:
        logger.error(f"Database prerequisites failed: {overall_status}")
        # Log specific database issues
        for db_name, status in health_status.get("databases", {}).items():
            if status.get("status") not in ["healthy"]:
                logger.error(f"{db_name}: {status.get('error', 'Unknown error')}")
        return False
```

**Flow Integration with Health Checks**:

```python
@flow(name="rpa1-with-health-monitoring")
def rpa1_workflow_with_health():
    """RPA1 workflow with comprehensive health monitoring."""
    logger = get_run_logger()
    logger.info("Starting RPA1 workflow with health monitoring")

    # Define databases used by this flow
    database_names = ["rpa_db", "SurveyHub"]

    try:
        # Validate database health before starting
        health_check_passed = validate_database_prerequisites(database_names, "rpa1")

        if not health_check_passed:
            logger.error("Database health check failed - aborting workflow")
            return {
                "status": "aborted",
                "reason": "database_health_check_failed",
                "timestamp": datetime.now().isoformat()
            }

        # Initialize database managers - one per database
        rpa_db = DatabaseManager("rpa_db")
        survey_hub = DatabaseManager("SurveyHub")

        # Run migrations
        logger.info("Running database migrations...")
        rpa_db.run_migrations()

        # Perform periodic health check during processing
        mid_workflow_health = database_health_check(database_names, "rpa1")
        if mid_workflow_health["overall_status"] == "unhealthy":
            logger.warning("Database health degraded during workflow execution")

        # Main workflow logic
        survey_responses = survey_hub.execute_query(
            "SELECT survey_id, customer_id, response_data FROM survey_responses WHERE processed = 0"
        )

        # Process survey data
        processed_surveys = process_survey_data(survey_responses)

        # Write results to PostgreSQL
        for survey in processed_surveys:
            rpa_db.execute_query(
                """INSERT INTO rpa1_processed_surveys
                   (survey_id, customer_id, satisfaction_score, processed_at, status)
                   VALUES (:survey_id, :customer_id, :satisfaction_score, :processed_at, :status)""",
                {
                    "survey_id": survey["survey_id"],
                    "customer_id": survey["customer_id"],
                    "satisfaction_score": survey["satisfaction_score"],
                    "processed_at": survey["processed_at"],
                    "status": survey["status"]
                }
            )

        # Final health check
        final_health = database_health_check(database_names, "rpa1")

        logger.info("RPA1 workflow completed successfully")
        return {
            "status": "success",
            "surveys_processed": len(processed_surveys),
            "responses_found": len(survey_responses),
            "initial_health": health_check_passed,
            "final_health": final_health["overall_status"],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        # Perform health check to diagnose potential database issues
        diagnostic_health = database_health_check(database_names, "rpa1")
        return {
            "status": "failed",
            "error": str(e),
            "diagnostic_health": diagnostic_health,
            "timestamp": datetime.now().isoformat()
        }
```

**Health Check Monitoring Examples**:

```python
# Example health check responses
{
    "flow_name": "rpa1",
    "overall_status": "healthy",
    "databases": {
        "rpa_db": {
            "database_name": "rpa_db",
            "database_type": "postgresql",
            "status": "healthy",
            "connection": true,
            "query_test": true,
            "migration_status": {
                "current_version": "V003",
                "pending_migrations": []
            },
            "response_time_ms": 45.2,
            "timestamp": "2024-01-15T10:30:00Z"
        },
        "survey_hub": {
            "database_name": "survey_hub",
            "database_type": "sqlserver",
            "status": "healthy",
            "connection": true,
            "query_test": true,
            "migration_status": "read_only",
            "response_time_ms": 78.1,
            "timestamp": "2024-01-15T10:30:01Z"
        }
    },
    "timestamp": "2024-01-15T10:30:01Z"
}

# Example degraded health status
{
    "flow_name": "rpa1",
    "overall_status": "degraded",
    "databases": {
        "rpa_db": {
            "database_name": "rpa_db",
            "status": "healthy",
            "response_time_ms": 42.1
        },
        "survey_hub": {
            "database_name": "survey_hub",
            "status": "unhealthy",
            "connection": false,
            "error": "Connection timeout after 30 seconds",
            "response_time_ms": 30000
        }
    }
}
```

### **Pyway Best Practices**

#### **Naming Conventions**

- Use descriptive names: `V001__Create_customers_table.sql`
- Keep names short but clear
- Use underscores for spaces
- Use sequential version numbers with leading zeros

#### **Migration Content**

- Keep migrations small and focused
- Test migrations on development first
- Include rollback information in comments
- Use transactions for complex changes

#### **Version Management**

- Use sequential version numbers (V001, V002, etc.)
- Don't skip version numbers
- Use leading zeros for proper sorting
- Never modify existing migration files

#### **Environment Management**

- Test migrations in development first
- Use separate migration directories if needed
- Document environment-specific changes
- Maintain migration history across environments

## 📊 Performance Considerations

### **Connection Pooling**

- **Pool Size**: Configurable per database type
- **Max Overflow**: Additional connections when needed
- **Pre-ping**: Verify connections before use
- **Connection Reuse**: Single engine per database type per flow

### **Query Optimization**

- **Parameterized Queries**: Prevent SQL injection
- **Connection Management**: Automatic connection lifecycle
- **Result Processing**: Efficient result set handling
- **Error Recovery**: Graceful handling of connection issues

### **Memory Management**

- **Engine Reuse**: Single engine instance per database type
- **Connection Cleanup**: Automatic connection cleanup
- **Result Streaming**: Large result set handling
- **Garbage Collection**: Proper resource cleanup

### **Performance Best Practices**

**Batch Operations**:

```python
# Use transactions for batch operations
with DatabaseManager("rpa_db") as db:
    queries = [
        ("INSERT INTO processed_surveys (survey_id, status) VALUES (:survey_id, :status)",
         {"survey_id": survey["survey_id"], "status": "completed"})
        for survey in processed_surveys
    ]
    db.execute_transaction(queries)
```

**Connection Pool Tuning**:

```python
# Customize connection pool for high-throughput scenarios
class HighThroughputDatabaseManager(DatabaseManager):
    def _initialize_engine(self):
        if self.engine is None:
            connection_string = self.config.get_secret(f"{self.database_name}_connection_string")
            self.engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=20,        # Larger pool for high throughput
                max_overflow=30,     # More overflow connections
                pool_pre_ping=True,
                pool_recycle=3600,   # Recycle connections every hour
                echo=False           # Disable SQL logging in production
            )
```

**Query Performance Monitoring**:

```python
# Monitor query performance
import time

def execute_query_with_timing(self, query: str, params: Dict = None) -> Dict[str, Any]:
    """Execute query and return results with timing information."""
    start_time = time.time()

    try:
        results = self.execute_query(query, params)
        execution_time = time.time() - start_time

        return {
            "results": results,
            "execution_time_ms": round(execution_time * 1000, 2),
            "row_count": len(results),
            "status": "success"
        }
    except Exception as e:
        execution_time = time.time() - start_time
        return {
            "results": [],
            "execution_time_ms": round(execution_time * 1000, 2),
            "row_count": 0,
            "status": "error",
            "error": str(e)
        }
```

## 🔒 Security Considerations

### **Connection Security**

- **Encrypted Connections**: SSL/TLS for database connections
- **Credential Management**: Secure storage of connection strings
- **Environment Isolation**: Separate credentials per environment
- **Access Control**: Database user permissions

### **Query Security**

- **Parameterized Queries**: Prevent SQL injection
- **Input Validation**: Validate query parameters
- **Error Handling**: Don't expose sensitive information
- **Audit Logging**: Log database operations

### **Configuration Security**

- **Secret Management**: Use Prefect secrets for sensitive data
- **Environment Variables**: Secure `.env` file handling
- **Access Control**: Limit access to configuration files
- **Regular Rotation**: Rotate database credentials

## 🚀 Deployment

### **Prerequisites**

- PostgreSQL database access
- SQL Server database access
- Python dependencies (SQLAlchemy, drivers)
- Environment configuration

### **Configuration Setup**

1. **Database Credentials**: Set connection strings in `.env` files
2. **Flow Configuration**: Configure flow-specific database settings
3. **Environment Variables**: Set environment-specific configurations
4. **Secret Management**: Store sensitive credentials securely

### **Migration Deployment**

1. **Migration Files**: Place SQL files in flow migration directories
2. **Automatic Execution**: Migrations run on flow initialization
3. **Environment Isolation**: Migrations run per environment
4. **Error Handling**: Graceful handling of migration failures

**Deployment Example**:

```yaml
# kubernetes/database-workflow-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rpa-database-workflow
spec:
  replicas: 3
  selector:
    matchLabels:
      app: rpa-database-workflow
  template:
    metadata:
      labels:
        app: rpa-database-workflow
    spec:
      containers:
        - name: rpa-processor
          image: rpa-solution:latest
          env:
            - name: PREFECT_ENVIRONMENT
              value: "production"
            - name: HOSTNAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-secrets
                  key: postgres-password
            - name: SQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: db-secrets
                  key: sql-password
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "500m"
```

**Testing Example**:

```python
# flows/rpa1/test/test_database_integration.py
import pytest
from core.database import DatabaseManager

@pytest.mark.integration
def test_database_migrations():
    """Test that migrations run successfully."""
    rpa_db = DatabaseManager("rpa_db")

    # Test rpa_db migrations
    rpa_db.run_migrations()
    status = rpa_db.get_migration_status()
    assert status["current_version"] is not None

@pytest.mark.integration
def test_database_queries():
    """Test database query execution."""
    rpa_db = DatabaseManager("rpa_db")
    survey_hub = DatabaseManager("SurveyHub")

    # Test rpa_db query
    result = rpa_db.execute_query("SELECT 1 as test_value")
    assert result[0]["test_value"] == 1

    # Test SurveyHub query
    result = survey_hub.execute_query("SELECT 1 as test_value")
    assert result[0]["test_value"] == 1

@pytest.mark.integration
def test_health_checks():
    """Test database health checks."""
    rpa_db = DatabaseManager("rpa_db")
    survey_hub = DatabaseManager("SurveyHub")

    # Test individual health checks
    rpa_health = rpa_db.health_check()
    assert rpa_health["status"] == "healthy"

    survey_health = survey_hub.health_check()
    assert survey_health["status"] == "healthy"
```

## 📈 Monitoring and Observability

### **Health Monitoring**

- **Connection Health**: Monitor database connection status
- **Query Performance**: Track query execution times
- **Pool Status**: Monitor connection pool utilization
- **Error Rates**: Track database operation failures

### **Advanced Monitoring with DatabaseManager**

**Pool Status Monitoring**:

```python
# Monitor connection pool status
with DatabaseManager("rpa_db") as db:
    pool_status = db.get_pool_status()
    print(f"Pool size: {pool_status['pool_size']}")
    print(f"Active connections: {pool_status['checked_out']}")
    print(f"Available connections: {pool_status['checked_in']}")
    print(f"Overflow connections: {pool_status['overflow']}")
```

**Transaction Monitoring**:

```python
# Execute multiple queries in a single transaction
queries = [
    ("INSERT INTO processed_surveys (survey_id, status) VALUES (:survey_id, :status)",
     {"survey_id": "123", "status": "completed"}),
    ("UPDATE survey_responses SET processed = 1 WHERE survey_id = :survey_id",
     {"survey_id": "123"})
]

with DatabaseManager("rpa_db") as db:
    results = db.execute_transaction(queries)
    print(f"Transaction completed: {len(results)} queries executed")
```

**Query Timeout Monitoring**:

```python
# Execute query with custom timeout
with DatabaseManager("SurveyHub") as db:
    try:
        results = db.execute_query_with_timeout(
            "SELECT * FROM large_table",
            timeout=60  # 60 second timeout
        )
        print(f"Query completed: {len(results)} rows returned")
    except Exception as e:
        print(f"Query timed out or failed: {e}")
```

### **Error Handling and Retry Logic**

**Retry Configuration**:

```python
# Add retry logic for database operations
from tenacity import retry, stop_after_attempt, wait_exponential

class DatabaseManager:
    # ... existing code ...

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def execute_query_with_retry(self, query: str, params: Dict = None) -> List[Dict]:
        """Execute query with automatic retry on connection failures."""
        return self.execute_query(query, params)

    def execute_query_safe(self, query: str, params: Dict = None, retry_on_failure: bool = True) -> List[Dict]:
        """Execute query with optional retry logic."""
        if retry_on_failure:
            return self.execute_query_with_retry(query, params)
        else:
            return self.execute_query(query, params)
```

**Graceful Degradation**:

```python
# Handle database failures gracefully in flows
@flow(name="rpa1-resilient-workflow")
def rpa1_resilient_workflow():
    """RPA1 workflow with resilient database operations."""
    logger = get_run_logger()

    try:
        with DatabaseManager("rpa_db") as rpa_db, \
             DatabaseManager("SurveyHub") as survey_hub:

            # Try to run migrations with retry
            try:
                rpa_db.run_migrations()
                logger.info("Migrations completed successfully")
            except Exception as e:
                logger.warning(f"Migration failed, continuing with existing schema: {e}")

            # Query with retry logic
            survey_responses = survey_hub.execute_query_safe(
                "SELECT survey_id, customer_id, response_data FROM survey_responses WHERE processed = 0",
                retry_on_failure=True
            )

            if not survey_responses:
                logger.info("No survey responses found")
                return {"status": "success", "message": "No data to process"}

            # Process with error handling
            processed_count = 0
            failed_count = 0

            for response in survey_responses:
                try:
                    # Process individual response
                    processed = process_survey_data_concurrently(response)

                    # Write with retry
                    rpa_db.execute_query_safe(
                        "INSERT INTO processed_surveys (survey_id, status) VALUES (:survey_id, :status)",
                        {"survey_id": response["survey_id"], "status": "completed"},
                        retry_on_failure=True
                    )
                    processed_count += 1

                except Exception as e:
                    logger.error(f"Failed to process survey {response['survey_id']}: {e}")
                    failed_count += 1

            return {
                "status": "success",
                "processed": processed_count,
                "failed": failed_count,
                "total": len(survey_responses)
            }

    except Exception as e:
        logger.error(f"Workflow failed completely: {e}")
        return {"status": "failed", "error": str(e)}
```

### **Logging**

- **Query Logging**: Log all database operations
- **Error Logging**: Detailed error information
- **Performance Logging**: Query execution times
- **Migration Logging**: Migration execution status

### **Metrics**

- **Connection Pool Metrics**: Pool size, active connections
- **Query Metrics**: Execution time, success rate
- **Migration Metrics**: Migration execution time, success rate
- **Error Metrics**: Error frequency, error types

## 🛠️ Maintenance

### **Regular Tasks**

- **Connection Health**: Monitor database connectivity
- **Migration Management**: Maintain migration files
- **Performance Tuning**: Optimize query performance
- **Security Updates**: Update database drivers and dependencies

### **Troubleshooting**

#### **Connection Issues**

**Problem**: Database connectivity problems

```python
# Check connection status
rpa_db = DatabaseManager("rpa_db")
try:
    result = rpa_db.execute_query("SELECT 1")
    print("rpa_db connection: OK")
except Exception as e:
    print(f"rpa_db connection failed: {e}")
    # Check connection string format
    # Verify database is running
    # Check network connectivity

survey_hub = DatabaseManager("SurveyHub")
try:
    result = survey_hub.execute_query("SELECT 1")
    print("SurveyHub connection: OK")
except Exception as e:
    print(f"SurveyHub connection failed: {e}")
```

#### **Migration Failures**

**Problem**: Schema change issues

```python
# Check migration status
rpa_db = DatabaseManager("rpa_db")
status = rpa_db.get_migration_status()
print(f"Current version: {status.get('current_version', 'None')}")
print(f"Pending migrations: {status.get('pending_migrations', [])}")

# Common issues:
# 1. SQL syntax errors in migration files
# 2. Missing permissions for schema changes
# 3. Conflicting migration versions
# 4. Database locks preventing migration
```

#### **Performance Issues**

**Problem**: Slow query execution

```python
# Monitor query performance
import time

survey_hub = DatabaseManager("SurveyHub")
start_time = time.time()
result = survey_hub.execute_query("SELECT * FROM survey_responses")
end_time = time.time()

print(f"Query took {end_time - start_time:.2f} seconds")
print(f"Returned {len(result)} rows")

# Solutions:
# 1. Add appropriate indexes
# 2. Optimize query structure
# 3. Increase connection pool size
# 4. Check database resource usage
```

#### **Configuration Issues**

**Problem**: Incorrect database settings

```python
# Verify configuration loading
from core.config import ConfigManager

config = ConfigManager()
rpa_db_url = config.get_secret("rpa_db_connection_string")
survey_hub_url = config.get_secret("SurveyHub_connection_string")

print(f"rpa_db URL configured: {bool(rpa_db_url)}")
print(f"SurveyHub URL configured: {bool(survey_hub_url)}")

# Common issues:
# 1. Missing .env files
# 2. Incorrect environment variable names
# 3. Invalid connection string format
# 4. Missing database credentials
```

## 📋 Implementation Phases

> **📌 Design Note**: This implementation uses the existing ConfigManager system for credential management. Future enhancements could include Prefect Blocks integration as an alternative approach while maintaining backward compatibility.

### **Phase 1: Core Infrastructure (Week 1)**

- [ ] DatabaseManager class implementation
- [ ] SQLAlchemy engine configuration
- [ ] Basic query execution interface
- [ ] ConfigManager integration
- [ ] Pyway integration setup

### **Phase 2: Migration System (Week 2)**

- [ ] Pyway migration system integration
- [ ] Migration file structure setup
- [ ] Flow-specific migration directories
- [ ] Migration status tracking
- [ ] Error handling and recovery

### **Phase 3: Integration & Testing (Week 3)**

- [ ] Flow integration examples
- [ ] Multi-database testing (PostgreSQL + SQL Server)
- [ ] Migration testing and validation
- [ ] Performance optimization
- [ ] Documentation and examples

## 🎯 Success Metrics

### **Functional Requirements**

- ✅ **Multi-Database Access**: Seamless PostgreSQL and SQL Server access
- ✅ **Flow Isolation**: Each flow manages its own database schema
- ✅ **Migration Management**: Simple SQL-based migration system
- ✅ **Configuration Integration**: Leverage existing configuration system

### **Performance Targets**

- **Connection Pooling**: <100ms connection acquisition
- **Query Execution**: <1s for typical queries
- **Migration Speed**: <30s for typical migration sets
- **Memory Usage**: <50MB per database type per flow

### **Operational Requirements**

- **Setup Time**: <5 minutes to configure new flow
- **Migration Time**: <1 minute to run migrations
- **Error Recovery**: <30 seconds to recover from connection issues
- **Monitoring**: Real-time visibility into database operations

## 📚 Next Steps

1. **Review and Approve**: Get stakeholder approval for design approach
2. **Dependency Planning**: Identify required Python packages
3. **Configuration Design**: Design database configuration structure
4. **Implementation**: Start with Phase 1 core infrastructure
5. **Testing**: Comprehensive testing with multiple database types

---

**Note**: This design focuses on providing a simple, production-ready database management system that integrates seamlessly with the existing Prefect workflow architecture while supporting both PostgreSQL and SQL Server databases.
