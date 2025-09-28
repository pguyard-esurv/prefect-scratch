# Database Configuration Quick Start

This guide helps you quickly set up database configuration for the RPA system.

## 🚀 Quick Setup (5 minutes)

### 1. Check Your Setup

```bash
# Validate your current configuration
python scripts/validate_database_config.py --check-setup
```

### 2. Create Configuration

```bash
# Create example configuration files
python scripts/validate_database_config.py --create-example

# Copy and edit the configuration
cp core/envs/.env.development.example core/envs/.env.development
```

### 3. Edit Configuration

Edit `core/envs/.env.development` with your database details:

```bash
# Required: Update these with your actual database information
DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://your_user:your_password@localhost:5432/your_database
DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://your_user:your_password@localhost:1433/your_database?driver=ODBC+Driver+17+for+SQL+Server
```

### 4. Validate Configuration

```bash
# Test your configuration
python scripts/validate_database_config.py
```

### 5. Use in Your Code

```python
from core.database import DatabaseManager

# Use the database
with DatabaseManager("rpa_db") as db:
    results = db.execute_query("SELECT * FROM your_table")
    print(f"Found {len(results)} records")
```

## 📋 Configuration Checklist

- [ ] **Environment Variables Set**

  - [ ] `DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql`
  - [ ] `DEVELOPMENT_GLOBAL_RPA_DB_CONNECTION_STRING=postgresql://...`
  - [ ] `DEVELOPMENT_GLOBAL_SURVEYHUB_TYPE=sqlserver`
  - [ ] `DEVELOPMENT_GLOBAL_SURVEYHUB_CONNECTION_STRING=mssql+pyodbc://...`

- [ ] **Database Drivers Installed**

  - [ ] PostgreSQL: `psycopg2-binary` (included in requirements)
  - [ ] SQL Server: ODBC Driver 17+ for SQL Server

- [ ] **Database Access**

  - [ ] PostgreSQL database accessible
  - [ ] SQL Server database accessible
  - [ ] User has required permissions

- [ ] **Configuration Validated**
  - [ ] `python scripts/validate_database_config.py` passes
  - [ ] Connectivity tests successful

## 🔧 Common Connection Strings

### PostgreSQL

```bash
# Local development
postgresql://username:password@localhost:5432/database_name

# With SSL (production)
postgresql://username:password@hostname:5432/database_name?sslmode=require

# With connection timeout
postgresql://username:password@hostname:5432/database_name?connect_timeout=10
```

### SQL Server

```bash
# Local development (Windows Auth)
mssql+pyodbc://hostname:1433/database_name?driver=ODBC+Driver+17+for+SQL+Server&Trusted_Connection=yes

# SQL Server Auth
mssql+pyodbc://username:password@hostname:1433/database_name?driver=ODBC+Driver+17+for+SQL+Server

# With encryption (production)
mssql+pyodbc://username:password@hostname:1433/database_name?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

## 🚨 Troubleshooting

### Issue: "Missing database type"

**Fix:** Add database type to your `.env` file:

```bash
DEVELOPMENT_GLOBAL_RPA_DB_TYPE=postgresql
```

### Issue: "Connection refused"

**Fixes:**

1. Check database is running: `pg_ctl status` (PostgreSQL) or check SQL Server service
2. Verify hostname and port in connection string
3. Check firewall settings

### Issue: "ODBC Driver not found"

**Fix:** Install SQL Server ODBC driver:

- **Windows:** Download from Microsoft
- **macOS:** `brew install msodbcsql17`
- **Linux:** Follow Microsoft's installation guide

### Issue: "Authentication failed"

**Fixes:**

1. Verify username and password in connection string
2. Check user permissions in database
3. For SQL Server, verify authentication mode (Windows vs SQL Server)

### Issue: "SSL connection error"

**Fixes:**

1. For development: Add `?sslmode=disable` to PostgreSQL connection string
2. For production: Ensure SSL certificates are properly configured
3. For SQL Server: Use `TrustServerCertificate=yes` for development only

## 🔍 Validation Commands

```bash
# Full validation report
python scripts/validate_database_config.py

# Check specific database
python scripts/validate_database_config.py --database rpa_db

# Get suggested fixes
python scripts/validate_database_config.py --suggest-fixes

# Check environment setup only
python scripts/validate_database_config.py --check-setup

# Test specific environment
python scripts/validate_database_config.py --environment staging
```

## 📚 Next Steps

1. **Read the full guide:** [DATABASE_CONFIGURATION.md](DATABASE_CONFIGURATION.md)
2. **Set up migrations:** Create migration files in `core/migrations/{database_name}/`
3. **Configure production:** Update production environment variables
4. **Monitor health:** Use `db.health_check()` in your flows

## 💡 Pro Tips

- **Use environment variable substitution** for production passwords
- **Set appropriate pool sizes** based on your expected load
- **Enable SSL** for production databases
- **Monitor connection pools** with `db.get_pool_status()`
- **Use flow-specific overrides** when needed (see example files in `flows/*/`)

## 🆘 Need Help?

1. Run the validation script: `python scripts/validate_database_config.py --suggest-fixes`
2. Check the troubleshooting guide: [DATABASE_CONFIGURATION.md#troubleshooting-guide](DATABASE_CONFIGURATION.md#troubleshooting-guide)
3. Review example configurations in `core/envs/.env.*.example`
4. Test connectivity with individual databases using the validation script
