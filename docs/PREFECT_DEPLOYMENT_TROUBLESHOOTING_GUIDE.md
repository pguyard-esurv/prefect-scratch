# Prefect Deployment System Troubleshooting Guide

## Overview

This guide provides solutions to common issues encountered when using the Prefect Deployment System. Issues are organized by category with step-by-step resolution instructions.

## Quick Diagnostics

Run these commands to quickly identify common issues:

```bash
# Check system status
make check-services

# Validate configuration
make validate-deployments

# Test Prefect connectivity
prefect server ls

# Check Docker status
docker ps
```

## Flow Discovery Issues

### Issue: No Flows Discovered

**Symptoms:**

- `make discover-flows` returns empty list
- "No flows found" message

**Possible Causes:**

1. No flows in flows/ directory
2. Flows missing @flow decorator
3. Python syntax errors in flow files
4. Incorrect directory structure

**Solutions:**

1. **Check directory structure:**

```bash
# Verify flows directory exists and has content
ls -la flows/
find flows/ -name "*.py" -exec grep -l "@flow" {} \;
```

2. **Validate flow syntax:**

```bash
# Check for Python syntax errors
python -m py_compile flows/*/workflow.py

# Check for @flow decorator
grep -r "@flow" flows/
```

3. **Fix flow structure:**

```python
# Correct flow structure
from prefect import flow

@flow(name="my-flow")
def my_flow():
    """Flow description"""
    pass
```

### Issue: Flow Validation Errors

**Symptoms:**

- Flows discovered but marked as invalid
- Validation error messages

**Common Validation Errors:**

1. **Missing Dependencies:**

```
Error: ModuleNotFoundError: No module named 'pandas'
Solution: Add missing packages to requirements.txt
```

2. **Invalid Flow Decorator:**

```
Error: Function missing @flow decorator
Solution: Add @flow decorator to flow function
```

3. **Syntax Errors:**

```
Error: SyntaxError: invalid syntax
Solution: Fix Python syntax in flow file
```

**Resolution Steps:**

```bash
# 1. Check specific flow validation
python -m deployment_system.cli validate --flow flows/rpa1/workflow.py

# 2. Install missing dependencies
pip install -r requirements.txt

# 3. Fix syntax errors
python -m py_compile flows/rpa1/workflow.py
```

## Deployment Creation Issues

### Issue: Deployment Creation Fails

**Symptoms:**

- `make build-deployments` fails
- Error messages during deployment creation

**Common Causes:**

1. **Invalid Configuration:**

```
Error: KeyError: 'work_pools'
Solution: Check deployment-config.yaml structure
```

2. **Missing Work Pools:**

```
Error: Work pool 'default-pool' not found
Solution: Create required work pools
```

3. **Invalid Parameters:**

```
Error: Invalid parameter type for 'batch_size'
Solution: Check parameter types in configuration
```

**Resolution Steps:**

1. **Validate configuration:**

```bash
# Check configuration syntax
python -c "import yaml; yaml.safe_load(open('config/deployment-config.yaml'))"

# Validate deployment configuration
make validate-deployments
```

2. **Create missing work pools:**

```bash
# List existing work pools
prefect work-pool ls

# Create missing work pools
prefect work-pool create default-pool --type process
prefect work-pool create docker-pool --type docker
```

3. **Fix configuration issues:**

```yaml
# Correct deployment-config.yaml structure
environments:
  development:
    prefect_api_url: "http://localhost:4200/api"
    work_pools:
      python: "default-pool"
      docker: "docker-pool"
    default_parameters:
      batch_size: 100 # Ensure correct types
```

### Issue: Docker Deployment Failures

**Symptoms:**

- Container deployments fail to create
- Docker-related error messages

**Common Docker Issues:**

1. **Docker Not Running:**

```bash
# Check Docker status
docker ps
# If fails, start Docker service
sudo systemctl start docker  # Linux
# or start Docker Desktop
```

2. **Missing Dockerfile:**

```
Error: Dockerfile not found for flow 'rpa1'
Solution: Create Dockerfile in flow directory
```

3. **Image Build Failures:**

```bash
# Test image build manually
cd flows/rpa1
docker build -t rpa1-test .

# Check build logs for errors
make build-images FLOW=rpa1 VERBOSE=true
```

4. **Registry Access Issues:**

```bash
# Test registry connectivity
docker login your-registry.com

# Check image push permissions
docker push your-registry.com/test-image:latest
```

## Prefect Connectivity Issues

### Issue: Cannot Connect to Prefect Server

**Symptoms:**

- "Connection refused" errors
- API timeout errors
- Empty responses from Prefect commands

**Diagnostic Steps:**

1. **Check Prefect server status:**

```bash
# Test basic connectivity
curl http://localhost:4200/api/health

# Check Prefect server logs
docker-compose logs prefect-server
```

2. **Verify API URL configuration:**

```bash
# Check current API URL
prefect config view

# Set correct API URL
prefect config set PREFECT_API_URL=http://localhost:4200/api
```

3. **Test API connectivity:**

```bash
# Test API endpoints
prefect server ls
prefect work-pool ls
prefect deployment ls
```

**Common Solutions:**

1. **Start Prefect server:**

```bash
# Using docker-compose
docker-compose up -d prefect-server

# Using Prefect CLI
prefect server start
```

2. **Fix network issues:**

```bash
# Check if port is accessible
telnet localhost 4200

# Check firewall settings
sudo ufw status  # Linux
```

3. **Update configuration:**

```bash
# Reset Prefect configuration
prefect config unset PREFECT_API_URL
prefect config set PREFECT_API_URL=http://localhost:4200/api
```

### Issue: Authentication Errors

**Symptoms:**

- "Unauthorized" errors
- API key validation failures

**Solutions:**

1. **Check API key:**

```bash
# Verify API key is set
echo $PREFECT_API_KEY

# Set API key if missing
export PREFECT_API_KEY=your-api-key
prefect config set PREFECT_API_KEY=your-api-key
```

2. **Validate API key:**

```bash
# Test API key validity
prefect auth ls
```

## Prefect UI Issues

### Issue: Deployments Not Visible in UI

**Symptoms:**

- Deployments created successfully but not showing in UI
- Empty deployments list in Prefect UI

**Diagnostic Steps:**

1. **Check deployment status:**

```bash
# List deployments via CLI
prefect deployment ls

# Check specific deployment
prefect deployment inspect "flow-name/deployment-name"
```

2. **Verify UI connectivity:**

```bash
# Test UI access
curl http://localhost:4200

# Check UI logs
docker-compose logs prefect-ui
```

**Solutions:**

1. **Refresh UI:**

- Hard refresh browser (Ctrl+F5)
- Clear browser cache
- Try incognito/private browsing mode

2. **Check deployment names:**

```bash
# Verify deployment naming
prefect deployment ls --format json | jq '.[].name'

# Check for naming conflicts
make check-ui
```

3. **Restart UI services:**

```bash
# Restart Prefect services
docker-compose restart prefect-server prefect-ui

# Wait for services to start
sleep 30
make check-ui
```

### Issue: Deployment Status Issues

**Symptoms:**

- Deployments show incorrect status
- Deployment details missing or incorrect

**Solutions:**

1. **Update deployment:**

```bash
# Recreate deployment
make clean-deployments PATTERN="problematic-deployment"
make build-deployments
make deploy-all
```

2. **Check work pool status:**

```bash
# Verify work pools are healthy
prefect work-pool ls
prefect work-pool inspect default-pool
```

## Environment Configuration Issues

### Issue: Environment-Specific Deployment Failures

**Symptoms:**

- Deployments work in development but fail in staging/production
- Environment-specific parameter errors

**Diagnostic Steps:**

1. **Compare environment configurations:**

```bash
# Check environment differences
diff config/environments/development.yaml config/environments/production.yaml

# Validate environment-specific config
make validate-deployments ENV=production
```

2. **Test environment connectivity:**

```bash
# Test staging/production Prefect server
PREFECT_API_URL=http://staging-prefect:4200/api prefect server ls
```

**Solutions:**

1. **Fix environment configuration:**

```yaml
# Ensure all required fields are present
environments:
  production:
    prefect_api_url: "http://prod-prefect:4200/api"
    work_pools:
      python: "prod-python-pool"
      docker: "prod-docker-pool"
    default_parameters:
      # All required parameters
    resource_limits:
      # Appropriate limits for production
```

2. **Create environment-specific work pools:**

```bash
# Create production work pools
PREFECT_API_URL=http://prod-prefect:4200/api prefect work-pool create prod-python-pool --type process
PREFECT_API_URL=http://prod-prefect:4200/api prefect work-pool create prod-docker-pool --type docker
```

## Performance Issues

### Issue: Slow Flow Discovery

**Symptoms:**

- `make discover-flows` takes a long time
- Timeout errors during discovery

**Solutions:**

1. **Optimize flow scanning:**

```bash
# Scan specific directories only
python -m deployment_system.cli discover --path flows/rpa1

# Use parallel scanning
make discover-flows PARALLEL=true
```

2. **Check for large files:**

```bash
# Find large Python files
find flows/ -name "*.py" -size +1M

# Exclude unnecessary files
echo "*.log" >> .gitignore
echo "__pycache__/" >> .gitignore
```

### Issue: Slow Deployment Creation

**Symptoms:**

- `make build-deployments` is slow
- Memory usage issues

**Solutions:**

1. **Optimize Docker builds:**

```dockerfile
# Use multi-stage builds
FROM python:3.9-slim as builder
# Build dependencies

FROM python:3.9-slim as runtime
# Copy only necessary files
```

2. **Parallel deployment creation:**

```bash
# Build deployments in parallel
make build-deployments PARALLEL=true

# Build specific flows only
make build-deployments FLOWS="rpa1,rpa2"
```

## Error Code Reference

### Common Error Codes

| Code       | Description            | Solution                            |
| ---------- | ---------------------- | ----------------------------------- |
| FLOW_001   | Flow not found         | Check flow path and filename        |
| FLOW_002   | Invalid flow decorator | Add @flow decorator                 |
| FLOW_003   | Syntax error in flow   | Fix Python syntax                   |
| DEPLOY_001 | Work pool not found    | Create required work pool           |
| DEPLOY_002 | Invalid configuration  | Check deployment-config.yaml        |
| DEPLOY_003 | API connection failed  | Check Prefect server status         |
| DOCKER_001 | Dockerfile not found   | Create Dockerfile in flow directory |
| DOCKER_002 | Image build failed     | Check Dockerfile syntax             |
| DOCKER_003 | Registry access denied | Check registry credentials          |

### Debug Mode

Enable debug mode for detailed error information:

```bash
# Enable debug logging
export DEBUG=true
make discover-flows

# Verbose output
make build-deployments VERBOSE=true

# Debug specific component
python -m deployment_system.cli debug --component discovery
```

## Getting Help

### Log Collection

Collect logs for support:

```bash
# Collect system logs
make collect-logs

# Prefect server logs
docker-compose logs prefect-server > prefect-server.log

# Deployment system logs
python -m deployment_system.cli logs --output deployment-system.log
```

### System Information

Gather system information:

```bash
# System info
make system-info

# Configuration dump
make config-dump

# Dependency versions
pip list > requirements-current.txt
```

### Support Channels

1. **Documentation**: Check project documentation and README
2. **Issues**: Create GitHub issue with logs and system info
3. **Prefect Community**: https://discourse.prefect.io
4. **Stack Overflow**: Tag questions with 'prefect' and 'deployment'

## Prevention Tips

### Regular Maintenance

```bash
# Weekly health check
make health-check

# Monthly cleanup
make clean-deployments
make build-deployments
make deploy-all

# Update dependencies
pip install --upgrade prefect
```

### Monitoring

Set up monitoring for early issue detection:

```bash
# Monitor deployment health
make monitor-deployments

# Check system resources
make check-resources

# Validate configuration regularly
make validate-all
```

### Best Practices

1. **Version Control**: Keep deployment configurations in version control
2. **Testing**: Always test in development before production deployment
3. **Backup**: Backup deployment configurations before major changes
4. **Documentation**: Document custom configurations and procedures
5. **Monitoring**: Set up alerts for deployment failures and system issues
