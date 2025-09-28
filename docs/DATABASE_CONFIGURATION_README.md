# Database Configuration System

This directory contains comprehensive documentation and tools for configuring database connections in the RPA system.

## 📚 Documentation Files

| File                                                           | Purpose                          | Audience                      |
| -------------------------------------------------------------- | -------------------------------- | ----------------------------- |
| [DATABASE_QUICK_START.md](DATABASE_QUICK_START.md)             | 5-minute setup guide             | Developers (new to project)   |
| [DATABASE_CONFIGURATION.md](DATABASE_CONFIGURATION.md)         | Complete configuration reference | Developers, DevOps            |
| [DATABASE_MANAGEMENT_DESIGN.md](DATABASE_MANAGEMENT_DESIGN.md) | System architecture and design   | Architects, Senior Developers |

## 🛠️ Configuration Tools

| Tool                                  | Purpose                                 | Usage                                        |
| ------------------------------------- | --------------------------------------- | -------------------------------------------- |
| `scripts/validate_database_config.py` | Validate and troubleshoot configuration | `python scripts/validate_database_config.py` |
| `core/database_config_validator.py`   | Configuration validation library        | Import in Python code                        |
| `core/envs/.env.*`                    | Environment-specific configuration      | Edit with your database settings             |

## 🚀 Quick Start

1. **New to the project?** Start with [DATABASE_QUICK_START.md](DATABASE_QUICK_START.md)
2. **Need detailed configuration?** See [DATABASE_CONFIGURATION.md](DATABASE_CONFIGURATION.md)
3. **Having issues?** Run `python scripts/validate_database_config.py --suggest-fixes`

## 📁 Configuration File Structure

```
core/envs/
├── .env.development          # Development database settings
├── .env.staging             # Staging database settings
├── .env.production          # Production database settings
├── .env.development.example # Example configuration template
├── .env.staging.example     # Example configuration template
└── .env.production.example  # Example configuration template

flows/
├── rpa1/.env.development.example  # Flow-specific overrides
├── rpa2/.env.development.example  # Flow-specific overrides
└── rpa3/.env.development.example  # Flow-specific overrides
```

## 🔧 Configuration Validation

### Quick Validation

```bash
# Check if everything is set up correctly
python scripts/validate_database_config.py --check-setup

# Validate all database configurations
python scripts/validate_database_config.py

# Get help fixing issues
python scripts/validate_database_config.py --suggest-fixes
```

### Programmatic Validation

```python
from core.database import validate_database_configuration

# Validate all databases
results = validate_database_configuration()
for db_name, result in results.items():
    if result['valid']:
        print(f"✅ {db_name}: Configuration valid")
    else:
        print(f"❌ {db_name}: {result['errors']}")
```

## 🏗️ Configuration Examples

### Basic Setup (Development)

```bash
# core/envs/.env.development
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:pass@localhost:5432/rpa_dev
DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE=sqlserver
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://user:pass@localhost:1433/survey_dev?driver=ODBC+Driver+17+for+SQL+Server
```

### Production Setup

```bash
# core/envs/.env.production
PRODUCTION_GLOBAL_RPA_DB_TYPE=postgresql
PRODUCTION_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://user:${RPA_DB_PASSWORD}@prod-db:5432/rpa_prod?sslmode=require
PRODUCTION_GLOBAL_SURVEYHUB_TYPE=sqlserver
PRODUCTION_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://user:${SURVEY_PASSWORD}@prod-sql:1433/survey_prod?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes
```

### Flow-Specific Overrides

```bash
# flows/rpa1/.env.development
DEVELOPMENT_RPA1_RPA_DB_POOL_SIZE=10  # Override global pool size for RPA1
DEVELOPMENT_RPA1_RPA_DB_TIMEOUT=60    # Override global timeout for RPA1
```

## 🔍 Troubleshooting

### Common Issues

| Issue                   | Solution                                               |
| ----------------------- | ------------------------------------------------------ |
| "Missing database type" | Add `{ENV}_GLOBAL_{DB}_TYPE=postgresql` to `.env` file |
| "Connection refused"    | Check database is running and accessible               |
| "ODBC Driver not found" | Install SQL Server ODBC driver                         |
| "SSL connection error"  | Add `?sslmode=disable` for development                 |

### Diagnostic Commands

```bash
# Check environment setup
python scripts/validate_database_config.py --check-setup

# Test specific database
python scripts/validate_database_config.py --database rpa_db

# Create example configuration
python scripts/validate_database_config.py --create-example

# Get suggested fixes
python scripts/validate_database_config.py --suggest-fixes
```

## 🔐 Security Best Practices

1. **Never commit passwords** to version control
2. **Use environment variable substitution** for production: `${PASSWORD}`
3. **Enable SSL/TLS** for production databases
4. **Use read-only accounts** where appropriate
5. **Rotate passwords regularly**

## 📊 Monitoring and Health Checks

```python
from core.database import DatabaseManager

# Check database health
with DatabaseManager("rpa_db") as db:
    health = db.health_check()
    print(f"Status: {health['status']}")

    # Check connection pool status
    pool_status = db.get_pool_status()
    print(f"Pool usage: {pool_status['checked_out']}/{pool_status['pool_size']}")
```

## 🚀 Usage in Flows

```python
from core.database import DatabaseManager

@task
def process_data():
    with DatabaseManager("rpa_db") as db:
        # Execute queries
        results = db.execute_query("SELECT * FROM customers")

        # Execute transactions
        queries = [
            ("INSERT INTO orders (customer_id) VALUES (:id)", {"id": 1}),
            ("UPDATE customers SET last_order = NOW() WHERE id = :id", {"id": 1})
        ]
        db.execute_transaction(queries)

        return len(results)
```

## 📈 Performance Tuning

### Connection Pool Settings

| Environment | Pool Size | Max Overflow | Timeout |
| ----------- | --------- | ------------ | ------- |
| Development | 5         | 10           | 30s     |
| Staging     | 8         | 15           | 45s     |
| Production  | 15        | 25           | 60s     |

### Monitoring Pool Usage

```python
# Check pool utilization
pool_status = db.get_pool_status()
utilization = pool_status['checked_out'] / pool_status['pool_size']
if utilization > 0.8:
    print("⚠️ High pool utilization - consider increasing pool size")
```

## 🔄 Migration Management

Database schema changes are managed through Pyway migrations:

```
core/migrations/
├── rpa_db/
│   ├── V001__Create_initial_tables.sql
│   ├── V002__Add_indexes.sql
│   └── V003__Create_views.sql
└── SurveyHub/
    └── (read-only - no migrations)
```

## 🆘 Getting Help

1. **Start here:** [DATABASE_QUICK_START.md](DATABASE_QUICK_START.md)
2. **Run diagnostics:** `python scripts/validate_database_config.py --suggest-fixes`
3. **Check examples:** Look at `.env.*.example` files
4. **Read full docs:** [DATABASE_CONFIGURATION.md](DATABASE_CONFIGURATION.md)

## 📝 Contributing

When adding new database configurations:

1. Update the example `.env` files
2. Add validation rules in `database_config_validator.py`
3. Update documentation
4. Test with the validation script
