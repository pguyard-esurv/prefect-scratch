# Database Configuration Guide

This guide provides comprehensive information on configuring database connections for the RPA system using the DatabaseManager class.

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Environment Variables](#environment-variables)
- [Connection String Formats](#connection-string-formats)
- [Configuration Examples](#configuration-examples)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Configuration Validation](#configuration-validation)

## Configuration Overview

The DatabaseManager uses a hierarchical configuration system that supports:

1. **Environment-specific configuration** (development, staging, production)
2. **Database-specific settings** (rpa_db, SurveyHub, etc.)
3. **Connection pooling configuration**
4. **Retry and timeout settings**

### Configuration Hierarchy

Configuration is loaded in the following order (most specific to least specific):

1. Environment variables in `.env` files: `{ENVIRONMENT}_GLOBAL_{DATABASE_NAME}_{SETTING}`
2. Prefect Variables: `{environment}_global_{setting}`
3. Prefect Secrets: `{environment}-global-{setting}`
4. Default values (hardcoded in DatabaseManager)

## Environment Variables

### Naming Convention

All database configuration variables follow this pattern:

```
{ENVIRONMENT}_GLOBAL_{DATABASE_NAME}_{SETTING}
```

Where:

- `ENVIRONMENT`: `DEVELOPMENT`, `STAGING`, or `PRODUCTION`
- `DATABASE_NAME`: `RPA_DB`, `SURVEYHUB`, etc. (uppercase)
- `SETTING`: Configuration parameter name (uppercase)

### Required Settings

For each database, the following settings are required:

| Setting             | Description                  | Example                                                     |
| ------------------- | ---------------------------- | ----------------------------------------------------------- |
| `TYPE`              | Database type                | `postgresql` or `sqlserver`                                 |
| `CONNECTION_STRING` | Full database connection URL | See [Connection String Formats](#connection-string-formats) |

### Optional Settings

| Setting        | Description                  | Default | Example |
| -------------- | ---------------------------- | ------- | ------- |
| `POOL_SIZE`    | Base connection pool size    | `5`     | `10`    |
| `MAX_OVERFLOW` | Maximum overflow connections | `10`    | `20`    |
| `TIMEOUT`      | Query timeout in seconds     | `30`    | `60`    |

### Global Database Settings

These settings apply to all databases:

| Setting                   | Description                  | Default | Example |
| ------------------------- | ---------------------------- | ------- | ------- |
| `DATABASE_RETRY_ATTEMPTS` | Maximum retry attempts       | `3`     | `5`     |
| `DATABASE_RETRY_MIN_WAIT` | Minimum retry wait (seconds) | `1`     | `2`     |
| `DATABASE_RETRY_MAX_WAIT` | Maximum retry wait (seconds) | `10`    | `30`    |

## Connection String Formats

### PostgreSQL Connection Strings

#### Basic Format

```
postgresql://username:password@host:port/database
```

#### With SSL (Recommended for Production)

```
postgresql://username:password@host:port/database?sslmode=require
```

#### With Connection Parameters

```
postgresql://username:password@host:port/database?sslmode=require&connect_timeout=10&application_name=rpa_system
```

#### Common PostgreSQL Parameters

| Parameter          | Description                | Values                                                              |
| ------------------ | -------------------------- | ------------------------------------------------------------------- |
| `sslmode`          | SSL connection mode        | `disable`, `allow`, `prefer`, `require`, `verify-ca`, `verify-full` |
| `connect_timeout`  | Connection timeout         | Integer (seconds)                                                   |
| `application_name` | Application identifier     | String                                                              |
| `search_path`      | Default schema search path | Comma-separated schema names                                        |

### SQL Server Connection Strings

#### Basic Format (Windows Authentication)

```
mssql+pyodbc://server:port/database?driver=ODBC+Driver+17+for+SQL+Server
```

#### With SQL Server Authentication

```
mssql+pyodbc://username:password@server:port/database?driver=ODBC+Driver+17+for+SQL+Server
```

#### With Encryption (Recommended for Production)

```
mssql+pyodbc://username:password@server:port/database?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

#### Common SQL Server Parameters

| Parameter                | Description              | Values                                                           |
| ------------------------ | ------------------------ | ---------------------------------------------------------------- |
| `driver`                 | ODBC driver name         | `ODBC+Driver+17+for+SQL+Server`, `ODBC+Driver+18+for+SQL+Server` |
| `Encrypt`                | Enable encryption        | `yes`, `no`                                                      |
| `TrustServerCertificate` | Trust server certificate | `yes`, `no`                                                      |
| `Connection+Timeout`     | Connection timeout       | Integer (seconds)                                                |
| `Command+Timeout`        | Command timeout          | Integer (seconds)                                                |

## Configuration Examples

### Development Environment

```bash
# core/envs/.env.development

# RPA Database (PostgreSQL) - Local Development
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://rpa_user:dev_password@localhost:5432/rpa_development
DEVELOPMENT_GLOBAL_RPA_DB_POOL_SIZE=5
DEVELOPMENT_GLOBAL_RPA_DB_MAX_OVERFLOW=10
DEVELOPMENT_GLOBAL_RPA_DB_TIMEOUT=30

# SurveyHub (SQL Server) - Local Development
DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE=sqlserver
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://survey_user:dev_password@localhost:1433/SurveyHub_Dev?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes
DEVELOPMENT_GLOBAL_SURVEYHUB_POOL_SIZE=3
DEVELOPMENT_GLOBAL_SURVEYHUB_MAX_OVERFLOW=5
DEVELOPMENT_GLOBAL_SURVEYHUB_TIMEOUT=30

# Global Settings
DEVELOPMENT_GLOBAL_DATABASE_RETRY_ATTEMPTS=3
DEVELOPMENT_GLOBAL_DATABASE_RETRY_MIN_WAIT=1
DEVELOPMENT_GLOBAL_DATABASE_RETRY_MAX_WAIT=10
```

### Staging Environment

```bash
# core/envs/.env.staging

# RPA Database (PostgreSQL) - Staging
STAGING_GLOBAL_RPA_DB_TYPE=postgresql
STAGING_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://rpa_user:staging_password@staging-postgres.internal:5432/rpa_staging
STAGING_GLOBAL_RPA_DB_POOL_SIZE=8
STAGING_GLOBAL_RPA_DB_MAX_OVERFLOW=15
STAGING_GLOBAL_RPA_DB_TIMEOUT=45

# SurveyHub (SQL Server) - Staging
STAGING_GLOBAL_SURVEYHUB_TYPE=sqlserver
STAGING_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://survey_readonly:staging_password@staging-sqlserver.internal:1433/SurveyHub_Staging?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
STAGING_GLOBAL_SURVEYHUB_POOL_SIZE=5
STAGING_GLOBAL_SURVEYHUB_MAX_OVERFLOW=8
STAGING_GLOBAL_SURVEYHUB_TIMEOUT=45

# Global Settings
STAGING_GLOBAL_DATABASE_RETRY_ATTEMPTS=3
STAGING_GLOBAL_DATABASE_RETRY_MIN_WAIT=2
STAGING_GLOBAL_DATABASE_RETRY_MAX_WAIT=15
```

### Production Environment

```bash
# core/envs/.env.production

# RPA Database (PostgreSQL) - Production
PRODUCTION_GLOBAL_RPA_DB_TYPE=postgresql
PRODUCTION_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://rpa_user:${RPA_DB_PASSWORD}@prod-postgres.internal:5432/rpa_production?sslmode=require
PRODUCTION_GLOBAL_RPA_DB_POOL_SIZE=15
PRODUCTION_GLOBAL_RPA_DB_MAX_OVERFLOW=25
PRODUCTION_GLOBAL_RPA_DB_TIMEOUT=60

# SurveyHub (SQL Server) - Production
PRODUCTION_GLOBAL_SURVEYHUB_TYPE=sqlserver
PRODUCTION_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://survey_readonly:${SURVEYHUB_PASSWORD}@prod-sqlserver.internal:1433/SurveyHub_Production?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
PRODUCTION_GLOBAL_SURVEYHUB_POOL_SIZE=10
PRODUCTION_GLOBAL_SURVEYHUB_MAX_OVERFLOW=15
PRODUCTION_GLOBAL_SURVEYHUB_TIMEOUT=60

# Global Settings
PRODUCTION_GLOBAL_DATABASE_RETRY_ATTEMPTS=5
PRODUCTION_GLOBAL_DATABASE_RETRY_MIN_WAIT=2
PRODUCTION_GLOBAL_DATABASE_RETRY_MAX_WAIT=30
```

### Using Environment Variable Substitution

For production environments, use environment variable substitution for sensitive values:

```bash
# Set these as system environment variables or in a secure secrets manager
export RPA_DB_PASSWORD="secure_production_password"
export SURVEYHUB_PASSWORD="secure_surveyhub_password"

# Reference them in connection strings
PRODUCTION_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://rpa_user:${RPA_DB_PASSWORD}@prod-postgres.internal:5432/rpa_production?sslmode=require
```

## Troubleshooting Guide

### Common Configuration Issues

#### 1. Missing Configuration Error

**Error Message:**

```
DatabaseConfigurationError: Missing required configuration for database 'rpa_db'. Required: type, connection_string
```

**Solution:**

- Verify that both `TYPE` and `CONNECTION_STRING` are configured
- Check environment variable naming convention
- Ensure the correct environment is being used

**Example Fix:**

```bash
# Add missing configuration
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/db
```

#### 2. Connection String Format Error

**Error Message:**

```
sqlalchemy.exc.ArgumentError: Could not parse rfc1738 URL from string
```

**Solution:**

- Verify connection string format matches database type
- Check for special characters that need URL encoding
- Ensure proper escaping of passwords with special characters

**Example Fix:**

```bash
# Wrong: Special characters not encoded
CONNECTION_STRING=postgresql://user:p@ssw0rd!@localhost:5432/db

# Correct: Special characters URL-encoded
CONNECTION_STRING=postgresql://user:p%40ssw0rd%21@localhost:5432/db
```

#### 3. Driver Not Found Error

**Error Message:**

```
pyodbc.InterfaceError: ('IM002', '[IM002] [Microsoft][ODBC Driver Manager] Data source name not found')
```

**Solution:**

- Install the correct ODBC driver for SQL Server
- Update the driver name in the connection string
- Verify driver installation

**Example Fix:**

```bash
# Check available drivers
odbcinst -q -d

# Update connection string with correct driver
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://user:pass@server:1433/db?driver=ODBC+Driver+18+for+SQL+Server
```

#### 4. SSL/TLS Connection Issues

**Error Message:**

```
psycopg2.OperationalError: SSL connection has been closed unexpectedly
```

**Solution:**

- Verify SSL configuration on database server
- Adjust SSL mode in connection string
- Check certificate validity

**Example Fix:**

```bash
# For development (less secure)
CONNECTION_STRING=postgresql://user:pass@localhost:5432/db?sslmode=disable

# For production (secure)
CONNECTION_STRING=postgresql://user:pass@server:5432/db?sslmode=require
```

#### 5. Connection Pool Exhaustion

**Error Message:**

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached
```

**Solution:**

- Increase pool size and max overflow
- Check for connection leaks in application code
- Monitor connection usage patterns

**Example Fix:**

```bash
# Increase pool limits
PRODUCTION_GLOBAL_RPA_DB_POOL_SIZE=20
PRODUCTION_GLOBAL_RPA_DB_MAX_OVERFLOW=30
```

### Connection Testing

#### Test PostgreSQL Connection

```bash
# Using psql command line
psql "postgresql://username:password@host:port/database"

# Using Python
python -c "
import psycopg2
conn = psycopg2.connect('postgresql://username:password@host:port/database')
print('PostgreSQL connection successful')
conn.close()
"
```

#### Test SQL Server Connection

```bash
# Using sqlcmd (if available)
sqlcmd -S server,port -U username -P password -d database

# Using Python
python -c "
import pyodbc
conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=server,port;DATABASE=database;UID=username;PWD=password')
print('SQL Server connection successful')
conn.close()
"
```

### Environment Detection Issues

#### Verify Current Environment

```python
import os
from core.config import ConfigManager

# Check detected environment
config = ConfigManager()
print(f"Current environment: {config.environment}")

# Check environment variable
print(f"PREFECT_ENVIRONMENT: {os.getenv('PREFECT_ENVIRONMENT', 'not set')}")
```

#### Set Environment Explicitly

```bash
# Set environment for current session
export PREFECT_ENVIRONMENT=development

# Or set in .env file
echo "PREFECT_ENVIRONMENT=development" >> .env
```

### Logging and Debugging

#### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Use DatabaseManager with debug logging
from core.database import DatabaseManager
with DatabaseManager("rpa_db") as db:
    results = db.execute_query("SELECT 1 as test")
```

#### Check Configuration Loading

```python
from core.config import ConfigManager

config = ConfigManager()
print("RPA DB Type:", config.get_variable("rpa_db_type"))
print("RPA DB Connection String:", config.get_secret("rpa_db_connection_string"))
```

## Configuration Validation

### Manual Validation

Use the configuration validation utility to verify your setup:

```python
from core.database import validate_database_configuration

# Validate all configured databases
validation_results = validate_database_configuration()
for db_name, result in validation_results.items():
    print(f"{db_name}: {'✓' if result['valid'] else '✗'}")
    if not result['valid']:
        print(f"  Errors: {result['errors']}")
```

### Automated Validation

The DatabaseManager automatically validates configuration on initialization:

```python
from core.database import DatabaseManager

try:
    with DatabaseManager("rpa_db") as db:
        print("Configuration valid")
except Exception as e:
    print(f"Configuration error: {e}")
```

### Health Check Validation

Use health checks to verify database connectivity:

```python
from core.database import DatabaseManager

with DatabaseManager("rpa_db") as db:
    health = db.health_check()
    print(f"Database health: {health['status']}")
    if health['status'] != 'healthy':
        print(f"Issues: {health.get('error', 'Unknown')}")
```

## Best Practices

### Security

1. **Never commit passwords** to version control
2. **Use environment variable substitution** for production passwords
3. **Enable SSL/TLS** for production connections
4. **Use read-only accounts** where appropriate
5. **Rotate passwords regularly**

### Performance

1. **Configure appropriate pool sizes** based on expected load
2. **Monitor connection pool usage** in production
3. **Set reasonable timeouts** to prevent hanging connections
4. **Use connection pre-ping** to validate connections

### Reliability

1. **Configure retry logic** for transient failures
2. **Set up health monitoring** for proactive issue detection
3. **Test configuration** in each environment
4. **Monitor database performance** and adjust settings as needed

### Maintenance

1. **Document environment-specific settings**
2. **Keep driver versions updated**
3. **Review and update connection limits** as system grows
4. **Regular configuration audits** for security compliance
