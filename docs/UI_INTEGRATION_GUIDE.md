# Prefect UI Integration Guide

This guide covers the UI integration and verification system for the Prefect deployment system.

## Overview

The UI integration system provides comprehensive tools for:

- Checking Prefect UI connectivity and accessibility
- Verifying deployment visibility in the Prefect UI
- Monitoring deployment health and status
- Troubleshooting UI connectivity issues
- Generating status reports and diagnostics

## Components

### 1. UIClient

Handles direct interaction with the Prefect UI and API.

**Key Features:**

- API connectivity checking
- UI accessibility verification
- Deployment visibility verification
- UI URL generation for deployments

### 2. DeploymentStatusChecker

Provides comprehensive deployment health monitoring.

**Key Features:**

- Deployment health checks
- Multi-deployment status reports
- Waiting for deployment readiness
- System health assessment

### 3. UIValidator

Validates deployment configurations and UI presence.

**Key Features:**

- Deployment metadata validation
- UI presence validation
- Configuration optimization for UI display
- Validation reporting

### 4. TroubleshootingUtilities

Diagnoses and troubleshoots UI connectivity issues.

**Key Features:**

- Connectivity diagnosis
- Network-level troubleshooting
- DNS and port connectivity testing
- Comprehensive troubleshooting reports

## Makefile Commands

### Basic UI Commands

```bash
# Check UI connectivity
make check-ui

# Generate deployment status report
make deployment-status-report

# Validate all deployments in UI
make validate-ui

# Run UI troubleshooting
make troubleshoot-ui

# List deployments with UI status
make list-deployments-ui
```

### Deployment-Specific Commands

```bash
# Verify specific deployment in UI
make verify-deployment-ui DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow

# Check deployment health
make check-deployment-health DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow

# Troubleshoot specific deployment
make troubleshoot-deployment DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow

# Wait for deployment to become ready
make wait-deployment-ready DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow

# Get deployment UI URL
make get-deployment-url DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow
```

## CLI Usage

### Direct CLI Commands

```bash
# Check UI connectivity
uv run python -m deployment_system.cli.main check-ui

# Verify deployment in UI
uv run python -m deployment_system.cli.main verify-deployment-ui \
  --deployment-name "my-deployment" --flow-name "my-flow"

# Check deployment health
uv run python -m deployment_system.cli.main check-deployment-health \
  --deployment-name "my-deployment" --flow-name "my-flow"

# Generate status report
uv run python -m deployment_system.cli.main deployment-status-report

# Validate UI presence
uv run python -m deployment_system.cli.main validate-ui

# Run troubleshooting
uv run python -m deployment_system.cli.main troubleshoot-ui
```

## Python API Usage

### Basic Usage

```python
from deployment_system.ui import UIClient, DeploymentStatusChecker

# Initialize clients
ui_client = UIClient("http://localhost:4200/api", "http://localhost:4200")
status_checker = DeploymentStatusChecker("http://localhost:4200/api")

# Check API connectivity
api_check = ui_client.run_async(ui_client.check_api_connectivity())
print(f"API Connected: {api_check['connected']}")

# Check UI accessibility
ui_check = ui_client.run_async(ui_client.check_ui_accessibility())
print(f"UI Accessible: {ui_check['accessible']}")

# Check deployment health
health = status_checker.run_async(
    status_checker.check_deployment_health("my-deployment", "my-flow")
)
print(f"Deployment Healthy: {health['healthy']}")
```

### Advanced Usage

```python
from deployment_system.ui import UIValidator, TroubleshootingUtilities

# Validate deployment configuration for UI
validator = UIValidator()
config = {
    "name": "my-deployment",
    "description": "My deployment",
    "work_pool_name": "default-pool"
}

validation = validator.run_async(
    validator.validate_deployment_configuration_for_ui(config)
)

if not validation["valid"]:
    print("Configuration issues:")
    for error in validation["errors"]:
        print(f"  - {error}")

# Run comprehensive troubleshooting
troubleshooter = TroubleshootingUtilities()
diagnosis = troubleshooter.run_async(
    troubleshooter.diagnose_connectivity_issues()
)

print(f"Diagnosis severity: {diagnosis['severity']}")
for recommendation in diagnosis["recommendations"]:
    print(f"  - {recommendation}")
```

## Configuration

### Environment Variables

```bash
# Prefect API URL (required)
export PREFECT_API_URL="http://localhost:4200/api"

# Prefect UI URL (optional, derived from API URL if not set)
export PREFECT_UI_URL="http://localhost:4200"
```

### Configuration Files

The UI integration system uses the same configuration files as the deployment system:

- `config/deployment-config.yaml` - Environment configurations
- `.env.*` files - Environment-specific settings

## Status Indicators

### Health Status

- **✅ Healthy**: All checks pass, deployment fully operational
- **⚠️ Degraded**: Minor issues, deployment functional but needs attention
- **❌ Unhealthy**: Major issues, deployment may not work properly
- **🚨 Critical**: Severe issues, deployment non-functional

### Connectivity Status

- **✅ Connected**: Service accessible and responding
- **❌ Disconnected**: Service not accessible or not responding
- **⚠️ Partial**: Service accessible but with issues

## Troubleshooting

### Common Issues

#### 1. UI Not Accessible

**Symptoms:**

- UI accessibility check fails
- Deployments not visible in UI

**Solutions:**

```bash
# Check if Prefect UI is running
curl http://localhost:4200

# Verify UI URL configuration
make troubleshoot-ui

# Check firewall/proxy settings
```

#### 2. API Not Connected

**Symptoms:**

- API connectivity check fails
- Cannot retrieve deployment information

**Solutions:**

```bash
# Check if Prefect server is running
curl http://localhost:4200/api/health

# Verify PREFECT_API_URL environment variable
echo $PREFECT_API_URL

# Run connectivity diagnosis
make troubleshoot-ui
```

#### 3. Deployment Not Visible in UI

**Symptoms:**

- Deployment exists in API but not visible in UI
- UI verification fails

**Solutions:**

```bash
# Check deployment health
make check-deployment-health DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow

# Troubleshoot specific deployment
make troubleshoot-deployment DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow

# Wait for UI sync
make wait-deployment-ready DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow
```

#### 4. Work Pool Issues

**Symptoms:**

- Deployment health check fails
- Work pool validation errors

**Solutions:**

```bash
# List available work pools
prefect work-pool ls

# Create missing work pool
prefect work-pool create my-pool

# Check work pool status
prefect work-pool inspect my-pool
```

### Diagnostic Commands

```bash
# Full system diagnosis
make troubleshoot-ui

# Deployment-specific diagnosis
make troubleshoot-deployment DEPLOYMENT_NAME=my-deployment FLOW_NAME=my-flow

# Generate comprehensive status report
make deployment-status-report

# Check all deployments UI status
make validate-ui
```

## Best Practices

### 1. Regular Health Checks

- Run `make deployment-status-report` regularly
- Monitor deployment health after changes
- Set up automated health monitoring

### 2. Proactive Troubleshooting

- Use `make troubleshoot-ui` when issues arise
- Check connectivity before deploying
- Validate configurations before deployment

### 3. UI Optimization

- Use descriptive deployment names
- Add meaningful descriptions and tags
- Keep deployment names under 100 characters
- Limit tags to 10 or fewer per deployment

### 4. Error Handling

- Always check return values from CLI commands
- Use wait commands for deployment readiness
- Implement retry logic for transient failures

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Deployment Health Check
on:
  schedule:
    - cron: "0 */6 * * *" # Every 6 hours

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.9"

      - name: Install dependencies
        run: uv sync

      - name: Check UI connectivity
        run: make check-ui
        env:
          PREFECT_API_URL: ${{ secrets.PREFECT_API_URL }}

      - name: Generate status report
        run: make deployment-status-report
        env:
          PREFECT_API_URL: ${{ secrets.PREFECT_API_URL }}

      - name: Validate deployments
        run: make validate-ui
        env:
          PREFECT_API_URL: ${{ secrets.PREFECT_API_URL }}
```

## API Reference

### UIClient Methods

- `check_api_connectivity()` - Check Prefect API connectivity
- `check_ui_accessibility()` - Check Prefect UI accessibility
- `verify_deployment_in_ui()` - Verify deployment visibility
- `get_deployment_ui_url()` - Get deployment UI URL
- `list_deployments_with_ui_status()` - List deployments with UI status

### DeploymentStatusChecker Methods

- `check_deployment_health()` - Check deployment health
- `get_deployment_status_report()` - Generate status report
- `wait_for_deployment_ready()` - Wait for deployment readiness
- `check_multiple_deployments_health()` - Bulk health check

### UIValidator Methods

- `validate_deployment_ui_presence()` - Validate UI presence
- `validate_deployment_configuration_for_ui()` - Validate config for UI
- `generate_ui_validation_report()` - Generate validation report

### TroubleshootingUtilities Methods

- `diagnose_connectivity_issues()` - Diagnose connectivity
- `diagnose_deployment_visibility_issues()` - Diagnose deployment issues
- `run_comprehensive_troubleshooting()` - Full troubleshooting

## Examples

See `deployment_system/examples/ui_integration_demo.py` for a comprehensive demonstration of all UI integration features.

## Support

For issues with UI integration:

1. Run `make troubleshoot-ui` for diagnosis
2. Check the troubleshooting section above
3. Review Prefect server and UI logs
4. Verify network connectivity and firewall settings
