# Configuration Management System

The Prefect Deployment System includes a comprehensive configuration management system that handles environment-specific configurations, deployment templates, and flow-specific overrides.

## Overview

The configuration management system provides:

- **Environment Configuration**: Define settings for different environments (development, staging, production)
- **Template System**: Use templates with variable substitution for deployment configurations
- **Flow Overrides**: Customize settings for specific flows
- **Validation**: Comprehensive validation with clear error reporting
- **CLI Tools**: Command-line tools for managing and validating configurations

## Configuration File Structure

The main configuration file is `config/deployment-config.yaml` and follows this structure:

```yaml
# Environment-specific configurations
environments:
  development:
    name: "development"
    prefect_api_url: "http://localhost:4200/api"
    work_pools:
      python: "default-agent-pool"
      docker: "docker-pool"
    default_parameters:
      cleanup: true
      debug_mode: true
      log_level: "DEBUG"
    resource_limits:
      memory: "512Mi"
      cpu: "0.5"
      storage: "1Gi"
    networks:
      - "rpa-network"
    default_tags:
      - "env:development"

# Global configuration settings
global_config:
  validation:
    strict_mode: true
    validate_dependencies: true
    validate_docker_images: true

# Flow-specific overrides
flow_overrides:
  rpa1:
    resource_limits:
      memory: "1Gi"
      cpu: "1.0"
    default_parameters:
      batch_size: 100
```

## Environment Configuration

Each environment defines:

### Required Fields

- `name`: Environment identifier
- `prefect_api_url`: URL to the Prefect API server

### Optional Fields

- `work_pools`: Mapping of deployment types to work pool names
- `default_parameters`: Default parameters for all deployments in this environment
- `resource_limits`: Default resource constraints
- `docker_registry`: Docker registry URL for container deployments
- `image_pull_policy`: Docker image pull policy
- `networks`: List of Docker networks to connect to
- `default_tags`: Tags to apply to all deployments

### Example Environment

```yaml
production:
  name: "production"
  prefect_api_url: "http://prod-prefect:4200/api"
  work_pools:
    python: "prod-agent-pool"
    docker: "prod-docker-pool"
  default_parameters:
    cleanup: false
    use_distributed: true
    log_level: "WARNING"
    retry_count: 5
  resource_limits:
    memory: "2Gi"
    cpu: "2.0"
    storage: "20Gi"
  docker_registry: "prod-registry.company.com"
  image_pull_policy: "Always"
  networks:
    - "rpa-network"
    - "production-network"
  default_tags:
    - "env:production"
    - "tier:prod"
    - "monitoring:enabled"
```

## Global Configuration

Global settings that apply across all environments:

```yaml
global_config:
  # Validation settings
  validation:
    strict_mode: true # Enforce strict validation rules
    validate_dependencies: true # Validate Python dependencies
    validate_docker_images: true # Validate Docker image builds
    validate_work_pools: true # Validate work pool configurations

  # Template settings
  templates:
    use_custom_templates: true # Use custom deployment templates
    template_validation: true # Validate template syntax
    variable_substitution: true # Enable variable substitution

  # Timeout settings
  deployment_timeout: 300 # Deployment operation timeout
  validation_timeout: 60 # Validation timeout

  # Logging configuration
  logging:
    level: "INFO"
    format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    enable_file_logging: true
    log_file: "logs/deployment-system.log"
```

## Flow Overrides

Customize settings for specific flows:

```yaml
flow_overrides:
  # High-resource flow
  data_processing_flow:
    resource_limits:
      memory: "4Gi"
      cpu: "4.0"
      storage: "50Gi"
    default_parameters:
      batch_size: 1000
      parallel_workers: 16
      enable_caching: true

  # Lightweight flow
  notification_flow:
    resource_limits:
      memory: "256Mi"
      cpu: "0.25"
    default_parameters:
      timeout_seconds: 30
      retry_count: 3
```

## Template System

The configuration system uses templates for deployment generation. Templates support variable substitution using the `${variable.path}` syntax.

### Available Variables

- `${flow.name}`: Flow name
- `${flow.path}`: Flow file path
- `${flow.module_path}`: Python module path
- `${environment.name}`: Environment name
- `${environment.prefect_api_url}`: Prefect API URL
- `${environment.work_pools.python}`: Python work pool name
- `${environment.default_parameters}`: Environment default parameters
- `${environment.resource_limits.memory}`: Memory limit

### Template Example

```yaml
# deployment_system/templates/python_deployment.yaml
work_pool: "${environment.work_pools.python}"

job_variables:
  env:
    PREFECT_API_URL: "${environment.prefect_api_url}"
    ENVIRONMENT: "${environment.name}"
    FLOW_NAME: "${flow.name}"

parameters: "${environment.default_parameters}"

tags:
  - "environment:${environment.name}"
  - "type:python"
  - "flow:${flow.name}"

resource_limits:
  memory: "${environment.resource_limits.memory}"
  cpu: "${environment.resource_limits.cpu}"
```

## CLI Tools

### Configuration Validation

Validate all configurations:

```bash
python -m deployment_system.config.config_validator
```

Validate specific environment:

```bash
python -m deployment_system.config.config_validator --environment production
```

Quiet mode (errors only):

```bash
python -m deployment_system.config.config_validator --quiet
```

### Configuration Management CLI

List available environments:

```bash
python -m deployment_system.cli.config_cli list-environments
```

Show environment details:

```bash
python -m deployment_system.cli.config_cli show-environment development
```

Show global configuration:

```bash
python -m deployment_system.cli.config_cli show-global
```

Show flow overrides:

```bash
python -m deployment_system.cli.config_cli show-overrides
python -m deployment_system.cli.config_cli show-overrides --flow rpa1
```

Validate configuration:

```bash
python -m deployment_system.cli.config_cli validate
python -m deployment_system.cli.config_cli validate --environment staging
```

## Python API

### ConfigurationManager

```python
from deployment_system.config.manager import ConfigurationManager

# Initialize configuration manager
config_manager = ConfigurationManager("config")

# List environments
environments = config_manager.list_environments()

# Get environment configuration
env_config = config_manager.get_environment_config("production")

# Generate deployment configuration
deployment_config = config_manager.generate_deployment_config(
    flow_metadata, "python", "production"
)

# Validate configuration
result = config_manager.validate_configuration(deployment_config)

# Get effective resource limits (with flow overrides)
limits = config_manager.get_effective_resource_limits("rpa1", "production")
```

### Configuration Validation

```python
from deployment_system.config.config_validator import ConfigValidator

# Initialize validator
validator = ConfigValidator("config")

# Validate configuration file
result = validator.validate_config_file(Path("config/deployment-config.yaml"))

# Validate all configurations
results = validator.validate_all_configurations()

# Print validation results
validator.print_validation_results(results)
```

## Validation Rules

The configuration system includes comprehensive validation:

### Environment Validation

- **Required Fields**: `prefect_api_url` must be present
- **URL Format**: API URL must be valid HTTP/HTTPS URL
- **Work Pools**: Recommended to have both `python` and `docker` work pools
- **Resource Limits**: Memory and CPU limits should be specified

### Deployment Configuration Validation

- **Flow Name**: Must be non-empty
- **Entrypoint**: Must be in format `module.path:function_name`
- **Deployment Type**: Must be `python` or `docker`
- **Work Pool**: Must match environment configuration (in strict mode)
- **Parameters**: Must be a dictionary
- **Job Variables**: Must be a dictionary
- **Tags**: Must be a list

### Validation Modes

- **Strict Mode**: Enforces all validation rules as errors
- **Lenient Mode**: Converts some errors to warnings for flexibility

## Error Handling

The configuration system provides detailed error reporting:

### Error Types

- **INVALID_ENVIRONMENT**: Environment not found
- **MISSING_REQUIRED_FIELD**: Required configuration field missing
- **INVALID_API_URL**: Malformed Prefect API URL
- **WORK_POOL_MISMATCH**: Work pool doesn't match environment
- **INVALID_YAML**: YAML syntax errors

### Error Format

```python
ValidationError(
    code="INVALID_ENVIRONMENT",
    message="Environment 'staging' is not configured",
    remediation="Add configuration for environment 'staging' or use one of: development, production"
)
```

## Best Practices

### Environment Organization

1. **Separate Environments**: Use distinct environments for development, staging, and production
2. **Consistent Naming**: Use consistent work pool and resource naming across environments
3. **Resource Scaling**: Scale resources appropriately for each environment
4. **Security**: Use different API URLs and credentials for each environment

### Flow Configuration

1. **Override Sparingly**: Only override settings when necessary
2. **Resource Planning**: Set appropriate resource limits based on flow requirements
3. **Parameter Management**: Use environment parameters for configuration, not hardcoded values
4. **Tagging Strategy**: Use consistent tagging for monitoring and organization

### Validation Strategy

1. **Regular Validation**: Run validation checks regularly, especially after configuration changes
2. **CI Integration**: Include configuration validation in CI/CD pipelines
3. **Environment Testing**: Test configurations in lower environments before production
4. **Documentation**: Document any custom configurations or overrides

## Troubleshooting

### Common Issues

1. **Configuration Not Loading**

   - Check file path and permissions
   - Validate YAML syntax
   - Ensure required fields are present

2. **Validation Failures**

   - Review error messages and remediation steps
   - Check environment configuration completeness
   - Verify work pool configurations

3. **Template Substitution Errors**

   - Verify variable paths are correct
   - Check that referenced variables exist
   - Review template syntax

4. **Environment-Specific Issues**
   - Verify Prefect API connectivity
   - Check work pool availability
   - Validate resource limits

### Debug Commands

```bash
# Validate specific configuration
python -m deployment_system.config.config_validator --environment development

# Show detailed environment configuration
python -m deployment_system.cli.config_cli show-environment development

# Check global configuration
python -m deployment_system.cli.config_cli show-global

# Validate with verbose output
python -m deployment_system.config.config_validator --config-dir config
```

## Migration Guide

### From Legacy Configuration

If migrating from older configuration formats:

1. **Backup Existing Configuration**: Save current configuration files
2. **Create New Structure**: Use the new YAML format
3. **Migrate Settings**: Transfer environment-specific settings
4. **Validate Configuration**: Run validation to ensure correctness
5. **Test Deployments**: Test with non-production environments first

### Configuration Updates

When updating configurations:

1. **Validate Changes**: Always validate after making changes
2. **Test in Development**: Test configuration changes in development environment
3. **Gradual Rollout**: Roll out changes gradually across environments
4. **Monitor Deployments**: Monitor deployment success after configuration changes

This configuration management system provides a robust foundation for managing complex deployment scenarios while maintaining flexibility and ease of use.
