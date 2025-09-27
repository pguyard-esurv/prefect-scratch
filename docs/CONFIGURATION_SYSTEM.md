# Configuration System

This document describes the modular environmental variable system used in the Prefect RPA solution. The system provides a hierarchical configuration approach that supports multiple environments and flow-specific overrides.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Configuration Hierarchy](#configuration-hierarchy)
- [Environment Setup](#environment-setup)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

The configuration system uses Prefect's built-in secrets and variables system to provide:

- **Environment-specific configuration**: Different settings for development, staging, and production
- **Flow-specific overrides**: Each flow can override global settings
- **Secure secret management**: Sensitive data is encrypted at rest
- **Hierarchical fallback**: Automatic fallback to less specific configurations
- **Easy deployment**: Simple environment variable switching

## Architecture

### Core Components

1. **`ConfigManager`**: Main configuration class in `core/config.py`
2. **Environment Setup Script**: `scripts/setup_environments.py`
3. **Flow Integration**: Each flow uses its own config instance
4. **Makefile Commands**: Environment-specific run commands

### Configuration Types

- **Secrets**: Encrypted sensitive data (API keys, passwords, tokens)
- **Variables**: Plain text configuration (URLs, timeouts, batch sizes)

## Configuration Hierarchy

The system follows a hierarchical lookup pattern (most specific to least specific):

```
1. {environment}.{flow}.{key}     # Flow-specific in specific environment
2. {environment}.global.{key}     # Global in specific environment  
3. global.{key}                   # Base global (backwards compatibility)
```

### Examples

For RPA1 in development environment looking for `api_key`:

1. `development.rpa1.api_key` (most specific)
2. `development.global.api_key` (environment-specific global)
3. `global.api_key` (base global fallback)

## Environment Setup

### Available Environments

- **`development`**: Local development with debug settings
- **`staging`**: Testing environment with production-like settings
- **`production`**: Production environment with optimized settings

### Setting Up Environments

#### 1. Set up a specific environment:

```bash
# Development
make setup-dev

# Staging
make setup-staging

# Production
make setup-prod

# All environments
make setup-all
```

#### 2. List current configurations:

```bash
make list-config
```

#### 3. Manual setup:

```bash
# Using the script directly
uv run python scripts/setup_environments.py development
uv run python scripts/setup_environments.py staging
uv run python scripts/setup_environments.py production
```

### Environment Configuration Details

#### Development Environment

```python
# Secrets
development.global.api_key = "dev-api-key-123"
development.global.db_password = "dev-db-password"
development.rpa1.api_key = "dev-rpa1-specific-key"

# Variables
development.global.database_url = "sqlite:///dev.db"
development.global.log_level = "DEBUG"
development.global.debug_mode = "true"
development.rpa1.batch_size = "100"
development.rpa1.timeout = "30"
```

#### Staging Environment

```python
# Secrets
staging.global.api_key = "staging-api-key-456"
staging.global.db_password = "staging-db-password"
staging.rpa1.api_key = "staging-rpa1-specific-key"

# Variables
staging.global.database_url = "postgresql://staging:pass@staging-db:5432/rpa"
staging.global.log_level = "INFO"
staging.global.debug_mode = "false"
staging.rpa1.batch_size = "500"
staging.rpa1.timeout = "60"
```

#### Production Environment

```python
# Secrets
production.global.api_key = "prod-api-key-789"
production.global.db_password = "prod-db-password"
production.rpa1.api_key = "prod-rpa1-specific-key"

# Variables
production.global.database_url = "postgresql://prod:pass@prod-db:5432/rpa"
production.global.log_level = "WARNING"
production.global.debug_mode = "false"
production.rpa1.batch_size = "1000"
production.rpa1.timeout = "120"
```

## Usage Examples

### Basic Usage

```python
from core.config import rpa1_config, rpa2_config, config

# Get a variable
batch_size = rpa1_config.get_variable("batch_size", 1000)
timeout = rpa1_config.get_variable("timeout", 60)

# Get a secret
api_key = rpa1_config.get_secret("api_key", "default-key")

# Get configuration (auto-detect secret vs variable)
value = rpa1_config.get_config("some_key", default="default", is_secret=True)

# Get multiple values at once
config_values = rpa1_config.get_all_config(
    ["batch_size", "timeout", "output_format"], 
    is_secret=False
)
```

### In Workflows

```python
@flow(name="my-workflow")
def my_workflow():
    logger = get_run_logger()
    
    # Get environment-specific configuration
    config = ConfigManager("my_flow")
    
    batch_size = config.get_variable("batch_size", 1000)
    api_key = config.get_secret("api_key")
    
    logger.info(f"Environment: {config.environment}")
    logger.info(f"Batch size: {batch_size}")
    
    # Use configuration in your workflow logic
    process_data(batch_size=batch_size, api_key=api_key)
```

### Environment-Specific Execution

```bash
# Run in development mode
make run-dev
make run-rpa1-dev
make run-rpa2-dev

# Run in staging mode
make run-staging
make run-rpa1-staging
make run-rpa2-staging

# Run in production mode
make run-prod
make run-rpa1-prod
make run-rpa2-prod

# Or set environment variable manually
PREFECT_ENVIRONMENT=development uv run python main.py
```

## Best Practices

### 1. Configuration Naming

Use descriptive, hierarchical names:

```python
# Good
"database_url"
"api_timeout"
"batch_size"
"validation_strict"

# Avoid
"url"
"timeout"
"size"
"strict"
```

### 2. Secret vs Variable

- **Use Secrets for**: API keys, passwords, tokens, certificates
- **Use Variables for**: URLs, timeouts, batch sizes, feature flags

```python
# Secrets (encrypted)
api_key = config.get_secret("api_key")
db_password = config.get_secret("db_password")

# Variables (plain text)
database_url = config.get_variable("database_url")
timeout = config.get_variable("timeout")
```

### 3. Default Values

Always provide sensible defaults:

```python
# Good
timeout = config.get_variable("timeout", 60)
batch_size = config.get_variable("batch_size", 1000)

# Avoid
timeout = config.get_variable("timeout")  # Could be None
```

### 4. Environment-Specific Overrides

Only override what's different:

```python
# Development: Small batch size for testing
development.rpa1.batch_size = "100"

# Production: Large batch size for efficiency
production.rpa1.batch_size = "1000"
```

### 5. Configuration Validation

Validate configuration values in your workflows:

```python
def validate_config(config: ConfigManager):
    """Validate configuration values."""
    batch_size = config.get_variable("batch_size", 1000)
    if not isinstance(batch_size, int) or batch_size <= 0:
        raise ValueError(f"Invalid batch_size: {batch_size}")
    
    timeout = config.get_variable("timeout", 60)
    if not isinstance(timeout, int) or timeout <= 0:
        raise ValueError(f"Invalid timeout: {timeout}")
```

## Troubleshooting

### Common Issues

#### 1. Configuration Not Found

**Problem**: `ValueError` when loading secrets/variables

**Solution**: Check if configuration exists and is properly set up:

```bash
# List all configurations
make list-config

# Check specific environment
uv run python -c "
from core.config import rpa1_config
print('Environment:', rpa1_config.environment)
print('Batch size:', rpa1_config.get_variable('batch_size', 'NOT_FOUND'))
"
```

#### 2. Wrong Environment

**Problem**: Configuration values don't match expected environment

**Solution**: Check `PREFECT_ENVIRONMENT` variable:

```bash
echo $PREFECT_ENVIRONMENT

# Set environment explicitly
export PREFECT_ENVIRONMENT=development
```

#### 3. Missing Secrets

**Problem**: Secrets return `None` or default values

**Solution**: Verify secrets are set up correctly:

```python
from prefect.blocks.system import Secret

# Check if secret exists
try:
    secret = Secret.load("development.global.api_key")
    print("Secret exists:", secret.get())
except ValueError:
    print("Secret not found")
```

#### 4. Type Conversion Issues

**Problem**: Configuration values are strings when numbers expected

**Solution**: Convert types explicitly:

```python
# Get string and convert
timeout_str = config.get_variable("timeout", "60")
timeout = int(timeout_str)

# Or use a helper function
def get_int_config(config, key, default):
    value = config.get_variable(key, str(default))
    return int(value)

timeout = get_int_config(config, "timeout", 60)
```

### Debugging Configuration

#### 1. Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show configuration lookup attempts
config = ConfigManager("rpa1")
value = config.get_variable("batch_size")
```

#### 2. Print Configuration State

```python
def debug_config(config: ConfigManager):
    print(f"Environment: {config.environment}")
    print(f"Flow: {config.flow_name}")
    
    # Test all lookup levels
    key = "batch_size"
    print(f"Looking for: {key}")
    
    # Try flow-specific
    if config.flow_name:
        try:
            value = Variable.get(f"{config.environment}.{config.flow_name}.{key}")
            print(f"Found flow-specific: {value}")
        except ValueError:
            print("Flow-specific not found")
    
    # Try environment-specific global
    try:
        value = Variable.get(f"{config.environment}.global.{key}")
        print(f"Found environment global: {value}")
    except ValueError:
        print("Environment global not found")
    
    # Try base global
    try:
        value = Variable.get(f"global.{key}")
        print(f"Found base global: {value}")
    except ValueError:
        print("Base global not found")
```

## Migration Guide

### From Environment Variables

If you're migrating from environment variables:

1. **Identify secrets vs variables**:
   ```python
   # Old way
   api_key = os.getenv("API_KEY")
   
   # New way
   api_key = config.get_secret("api_key")
   ```

2. **Set up configurations**:
   ```bash
   make setup-dev
   ```

3. **Update workflow code**:
   ```python
   # Old way
   batch_size = int(os.getenv("BATCH_SIZE", "1000"))
   
   # New way
   batch_size = config.get_variable("batch_size", 1000)
   ```

### From Hardcoded Values

If you're migrating from hardcoded values:

1. **Identify configuration values**:
   ```python
   # Old way
   BATCH_SIZE = 1000
   TIMEOUT = 60
   
   # New way
   batch_size = config.get_variable("batch_size", 1000)
   timeout = config.get_variable("timeout", 60)
   ```

2. **Set up environment-specific values**:
   ```bash
   make setup-dev
   make setup-staging
   make setup-prod
   ```

## Security Considerations

### Secret Management

- **Never commit secrets** to version control
- **Use Prefect's secret blocks** for sensitive data
- **Rotate secrets regularly** in production
- **Use different secrets** for each environment

### Access Control

- **Limit access** to production configurations
- **Use environment-specific deployments** to control access
- **Monitor secret usage** through Prefect's audit logs

### Best Practices

- **Use least privilege** principle for secret access
- **Encrypt secrets at rest** (handled by Prefect)
- **Use environment variables** for deployment-specific overrides
- **Regular security audits** of configuration access

## Related Documentation

- [Prefect Secrets Documentation](https://docs.prefect.io/v3/how-to-guides/configuration/store-secrets)
- [Prefect Variables Documentation](https://docs.prefect.io/v3/how-to-guides/configuration/variables)
- [Testing Strategy](TESTING_STRATEGY.md)
- [Mocking Strategy](MOCKING_STRATEGY.md)
