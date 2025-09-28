# Environment File System (.env)

This document describes the hierarchical .env file system implemented for managing configuration across different environments and flows.

## 🗂️ Directory Structure

```
core/
├── envs/
│   ├── .env.development    # Global development configuration
│   ├── .env.staging        # Global staging configuration
│   └── .env.production     # Global production configuration
flows/
├── rpa1/
│   ├── .env.development    # RPA1 development overrides
│   ├── .env.staging        # RPA1 staging overrides
│   └── .env.production     # RPA1 production overrides
├── rpa2/
│   ├── .env.development    # RPA2 development overrides
│   ├── .env.staging        # RPA2 staging overrides
│   └── .env.production     # RPA2 production overrides
└── rpa3/
    ├── .env.development    # RPA3 development overrides
    ├── .env.staging        # RPA3 staging overrides
    └── .env.production     # RPA3 production overrides
```

## 🔧 Configuration Hierarchy

The system loads configuration in the following order (most specific to least specific):

1. **Flow-specific .env files**: `flows/{flow}/.env.{environment}` (overrides global)
2. **Global .env files**: `core/envs/.env.{environment}` (base configuration)
3. **Prefect Secret/Variable blocks**: Fallback for backwards compatibility

## 📝 Environment Variable Naming Convention

Environment variables must follow this naming pattern:

```
{ENVIRONMENT}_{FLOW}_{KEY}
```

### Examples:

**Global variables:**
```env
DEVELOPMENT_GLOBAL_DATABASE_URL=sqlite:///dev.db
STAGING_GLOBAL_LOG_LEVEL=INFO
PRODUCTION_GLOBAL_API_KEY=prod-api-key
```

**Flow-specific variables:**
```env
DEVELOPMENT_RPA1_BATCH_SIZE=100
STAGING_RPA3_MAX_CONCURRENT_TASKS=8
PRODUCTION_RPA2_VALIDATION_STRICT=true
```

## 🚀 Usage

### 1. Setting Up Environments

```bash
# Set up development environment
make setup-dev

# Set up staging environment
make setup-staging

# Set up production environment
make setup-prod

# Set up all environments
make setup-all
```

### 2. Running Workflows with Environment Configuration

```bash
# Run in development mode
make run-rpa1-dev
make run-rpa2-dev
make run-rpa3-dev

# Run in staging mode
make run-rpa1-staging
make run-rpa2-staging
make run-rpa3-staging

# Run in production mode
make run-rpa1-prod
make run-rpa2-prod
make run-rpa3-prod
```

### 3. Using Configuration in Code

```python
from core.config import ConfigManager

# Global configuration
config = ConfigManager(environment="development")
db_url = config.get_variable("database_url")
api_key = config.get_secret("api_key")

# Flow-specific configuration
rpa1_config = ConfigManager(flow_name="rpa1", environment="development")
batch_size = rpa1_config.get_variable("batch_size")
timeout = rpa1_config.get_variable("timeout")
```

## 📋 Sample .env Files

### Global Development Configuration (`core/envs/.env.development`)

```env
# Global Development Configuration
DEVELOPMENT_GLOBAL_DATABASE_URL=sqlite:///dev.db
DEVELOPMENT_GLOBAL_LOG_LEVEL=DEBUG
DEVELOPMENT_GLOBAL_DEBUG_MODE=true
DEVELOPMENT_GLOBAL_MAX_RETRIES=1
DEVELOPMENT_GLOBAL_TIMEOUT=30

# Global Secrets
DEVELOPMENT_GLOBAL_API_KEY=dev-global-api-key-123
DEVELOPMENT_GLOBAL_DB_PASSWORD=dev-global-db-password
DEVELOPMENT_GLOBAL_EXTERNAL_API_TOKEN=dev-global-external-token
```

### RPA1 Development Configuration (`flows/rpa1/.env.development`)

```env
# RPA1 Development Configuration
DEVELOPMENT_RPA1_BATCH_SIZE=100
DEVELOPMENT_RPA1_TIMEOUT=30
DEVELOPMENT_RPA1_CLEANUP_TEMP_FILES=true
DEVELOPMENT_RPA1_OUTPUT_FORMAT=json

# RPA1 Secrets
DEVELOPMENT_RPA1_API_KEY=dev-rpa1-specific-api-key
```

### RPA3 Staging Configuration (`flows/rpa3/.env.staging`)

```env
# RPA3 Staging Configuration
STAGING_RPA3_MAX_CONCURRENT_TASKS=8
STAGING_RPA3_TIMEOUT=60
STAGING_RPA3_CLEANUP_TEMP_FILES=true
```

## 🔒 Security Considerations

1. **Never commit .env files to version control** - They contain sensitive information
2. **Use .gitignore** - Ensure .env files are ignored by git
3. **Separate secrets from variables** - Use different naming conventions for secrets vs variables
4. **Environment-specific secrets** - Use different secrets for each environment
5. **Regular rotation** - Rotate secrets regularly in production

## 🧪 Testing

The system includes comprehensive tests for:

- .env file loading
- Environment variable parsing
- Hierarchical configuration override
- Flow-specific configuration
- Environment detection
- Error handling for missing files

Run tests with:

```bash
# Run all tests
make test

# Run only .env-related tests
uv run pytest core/test/test_config_env_simple.py -v
```

## 🔄 Migration from Hardcoded Configuration

The system provides backwards compatibility with Prefect Secret/Variable blocks. To migrate:

1. **Create .env files** for each environment and flow
2. **Update configuration calls** to use ConfigManager
3. **Test thoroughly** in each environment
4. **Remove hardcoded values** once migration is complete

## 📊 Benefits

1. **✅ No hardcoded secrets** in code
2. **✅ Environment-specific** configuration
3. **✅ Flow-specific overrides** work seamlessly
4. **✅ Version control safe** (can gitignore .env files)
5. **✅ Easy to manage** (separate files per environment/flow)
6. **✅ Hierarchical** (flow overrides global)
7. **✅ Backwards compatible** with existing Prefect configuration
8. **✅ Testable** with comprehensive test coverage

## 🛠️ Troubleshooting

### Common Issues

1. **Configuration not loading**: Check .env file naming and location
2. **Variables showing as None**: Verify environment variable naming convention
3. **Overrides not working**: Ensure flow .env files are in correct location
4. **Environment detection**: Check PREFECT_ENVIRONMENT environment variable

### Debug Mode

Enable debug logging to see which .env files are being loaded:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will show output like:
```
📁 Loaded global config: /path/to/core/envs/.env.development
📁 Loaded flow config: /path/to/flows/rpa1/.env.development
```

## 📚 Related Documentation

- [Configuration System](CONFIGURATION_SYSTEM.md) - Overall configuration management
- [Testing Strategy](TESTING_STRATEGY.md) - Testing approaches and best practices
- [Mocking Strategy](MOCKING_STRATEGY.md) - Mocking strategies for Prefect workflows
