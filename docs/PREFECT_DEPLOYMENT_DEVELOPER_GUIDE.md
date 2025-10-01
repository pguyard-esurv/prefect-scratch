# Prefect Deployment System Developer Guide

## Overview

This guide provides comprehensive information about using the Prefect Deployment System, including all available Makefile commands, workflows, and best practices for managing flow deployments.

## Quick Start

```bash
# Discover all flows in the repository
make discover-flows

# Build deployments for all flows
make build-deployments

# Deploy all flows (Python and containers)
make deploy-all

# Check deployment status in Prefect UI
make check-ui
```

## Makefile Commands Reference

### Flow Discovery Commands

#### `make discover-flows`

Scans the repository for Prefect flows and displays discovered flows with their metadata.

**Usage:**

```bash
make discover-flows
```

**Output:**

- List of discovered flows
- Flow validation status
- Dependencies and configuration files
- Any validation errors or warnings

**Example Output:**

```
Discovering flows in flows/ directory...
✓ flows/rpa1/workflow.py - RPA1ProcessingFlow
✓ flows/rpa2/workflow.py - RPA2ProcessingFlow
✓ flows/rpa3/workflow.py - RPA3ProcessingFlow
✗ flows/broken/workflow.py - SyntaxError: invalid syntax

Found 3 valid flows, 1 invalid flow
```

#### `make validate-flows`

Validates all discovered flows for structure, dependencies, and configuration.

**Usage:**

```bash
make validate-flows
```

**Validation Checks:**

- Flow decorator presence and syntax
- Python dependencies availability
- Docker configuration (if applicable)
- Environment file validity

### Deployment Management Commands

#### `make build-deployments`

Creates both Python and Docker deployments for all valid flows.

**Usage:**

```bash
make build-deployments [ENV=environment]
```

**Parameters:**

- `ENV`: Target environment (development, staging, production)
- Default: development

**Example:**

```bash
# Build for development (default)
make build-deployments

# Build for staging
make build-deployments ENV=staging

# Build for production
make build-deployments ENV=production
```

#### `make deploy-python`

Deploys all Python-based flow deployments to Prefect.

**Usage:**

```bash
make deploy-python [ENV=environment]
```

**What it does:**

- Creates Python process deployments
- Configures work pools and parameters
- Registers deployments with Prefect server

#### `make deploy-containers`

Deploys all container-based flow deployments to Prefect.

**Usage:**

```bash
make deploy-containers [ENV=environment]
```

**Prerequisites:**

- Docker images must be built
- Docker work pools must exist
- Container registry access (for remote deployments)

#### `make deploy-all`

Deploys both Python and container deployments for all flows.

**Usage:**

```bash
make deploy-all [ENV=environment]
```

**Equivalent to:**

```bash
make deploy-python ENV=environment
make deploy-containers ENV=environment
```

#### `make clean-deployments`

Removes all existing deployments from Prefect server.

**Usage:**

```bash
make clean-deployments [PATTERN=pattern]
```

**Parameters:**

- `PATTERN`: Optional pattern to match deployment names
- Default: removes all deployments created by the system

**Examples:**

```bash
# Remove all deployments
make clean-deployments

# Remove only RPA1 deployments
make clean-deployments PATTERN="rpa1-*"
```

### Environment-Specific Commands

#### `make deploy-dev`

Deploy to development environment with development-specific configurations.

**Usage:**

```bash
make deploy-dev
```

**Configuration:**

- Uses development work pools
- Enables cleanup parameters
- Sets development resource limits

#### `make deploy-staging`

Deploy to staging environment.

**Usage:**

```bash
make deploy-staging
```

**Configuration:**

- Uses staging work pools
- Production-like settings with safety nets
- Moderate resource allocation

#### `make deploy-prod`

Deploy to production environment.

**Usage:**

```bash
make deploy-prod
```

**Configuration:**

- Uses production work pools
- Optimized for performance and reliability
- Full resource allocation

### Validation and Testing Commands

#### `make validate-deployments`

Validates deployment configurations without creating deployments.

**Usage:**

```bash
make validate-deployments [ENV=environment]
```

**Validation Checks:**

- Configuration file syntax
- Work pool availability
- Parameter validation
- Resource limit validation

#### `make test-deployments`

Creates deployments in test mode (dry run) without registering them.

**Usage:**

```bash
make test-deployments [ENV=environment]
```

**Benefits:**

- Test deployment creation without side effects
- Validate deployment configurations
- Debug deployment issues

#### `make check-ui`

Verifies that deployments appear correctly in the Prefect UI.

**Usage:**

```bash
make check-ui
```

**Checks:**

- Deployment visibility in UI
- Correct deployment names and descriptions
- Proper status and configuration display
- Work pool assignments

### Docker Management Commands

#### `make build-images`

Builds Docker images for all flows with Dockerfiles.

**Usage:**

```bash
make build-images [REGISTRY=registry]
```

**Parameters:**

- `REGISTRY`: Docker registry URL
- Default: local images only

**Example:**

```bash
# Build local images
make build-images

# Build and tag for registry
make build-images REGISTRY=myregistry.com/myproject
```

#### `make push-images`

Pushes built Docker images to the configured registry.

**Usage:**

```bash
make push-images [REGISTRY=registry]
```

**Prerequisites:**

- Images must be built
- Registry authentication configured
- Push permissions available

#### `make pull-images`

Pulls Docker images from the configured registry.

**Usage:**

```bash
make pull-images [REGISTRY=registry]
```

## Workflow Examples

### Development Workflow

```bash
# 1. Discover and validate flows
make discover-flows
make validate-flows

# 2. Build and test deployments
make build-deployments ENV=development
make test-deployments ENV=development

# 3. Deploy to development
make deploy-dev

# 4. Verify in UI
make check-ui
```

### Production Deployment Workflow

```bash
# 1. Validate everything
make validate-flows
make validate-deployments ENV=production

# 2. Build Docker images
make build-images REGISTRY=prod-registry.com/project
make push-images REGISTRY=prod-registry.com/project

# 3. Test deployment configuration
make test-deployments ENV=production

# 4. Deploy to production
make deploy-prod

# 5. Verify deployment
make check-ui
```

### Cleanup and Redeploy Workflow

```bash
# 1. Clean existing deployments
make clean-deployments

# 2. Rebuild and redeploy
make build-deployments ENV=staging
make deploy-staging

# 3. Verify
make check-ui
```

## Configuration Management

### Environment Configuration

The system supports multiple environments through configuration files:

**File Structure:**

```
config/
├── deployment-config.yaml          # Main configuration
├── environments/
│   ├── development.yaml           # Development overrides
│   ├── staging.yaml               # Staging overrides
│   └── production.yaml            # Production overrides
└── templates/
    ├── python_deployment.yaml     # Python deployment template
    └── docker_deployment.yaml     # Docker deployment template
```

### Environment Variables

Key environment variables used by the system:

```bash
# Prefect Configuration
PREFECT_API_URL=http://localhost:4200/api
PREFECT_API_KEY=your-api-key

# Deployment Configuration
DEPLOYMENT_ENV=development
DEPLOYMENT_CONFIG_PATH=config/deployment-config.yaml

# Docker Configuration
DOCKER_REGISTRY=your-registry.com
DOCKER_NAMESPACE=your-namespace
DOCKER_TAG=latest
```

### Work Pool Configuration

Configure work pools for different deployment types:

```yaml
work_pools:
  python:
    name: "python-pool"
    type: "process"
    base_job_template:
      job_configuration:
        command: "python -m prefect.engine"

  docker:
    name: "docker-pool"
    type: "docker"
    base_job_template:
      job_configuration:
        image: "{{ image }}"
        auto_remove: true
```

## Best Practices

### Flow Development

1. **Use consistent naming**: Follow the pattern `{project}_{environment}_{flow_name}`
2. **Include metadata**: Add descriptions, tags, and version information
3. **Environment separation**: Use different parameters for different environments
4. **Resource management**: Set appropriate resource limits for containers

### Deployment Management

1. **Test first**: Always use `test-deployments` before actual deployment
2. **Environment progression**: Deploy to dev → staging → production
3. **Validation**: Run validation commands before deployment
4. **Monitoring**: Use `check-ui` to verify deployments

### Docker Best Practices

1. **Multi-stage builds**: Use multi-stage Dockerfiles for smaller images
2. **Layer caching**: Order Dockerfile commands for optimal caching
3. **Security**: Use non-root users and minimal base images
4. **Registry management**: Tag images appropriately for different environments

## Troubleshooting Commands

### Debug Flow Discovery

```bash
# Verbose flow discovery
make discover-flows VERBOSE=true

# Check specific flow
python -m deployment_system.cli discover --flow flows/rpa1/workflow.py
```

### Debug Deployment Issues

```bash
# Validate specific deployment
python -m deployment_system.cli validate --deployment rpa1-python-dev

# Check deployment configuration
python -m deployment_system.cli config --show --env development
```

### Debug Docker Issues

```bash
# Test Docker connectivity
docker ps

# Check image build
make build-images FLOW=rpa1 VERBOSE=true

# Test container deployment
docker run --rm your-registry/rpa1-worker:latest --help
```

## Advanced Usage

### Custom Deployment Scripts

Create custom deployment scripts for complex scenarios:

```python
#!/usr/bin/env python3
from deployment_system.api import DeploymentAPI
from deployment_system.config import ConfigurationManager

# Custom deployment logic
api = DeploymentAPI()
config = ConfigurationManager()

# Deploy specific flows with custom parameters
flows = ["rpa1", "rpa2"]
for flow in flows:
    deployment = api.create_deployment(
        flow_name=flow,
        environment="production",
        custom_parameters={"batch_size": 1000}
    )
    api.deploy(deployment)
```

### Integration with CI/CD

Example GitHub Actions workflow:

```yaml
name: Deploy Flows
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.9"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Validate flows
        run: make validate-flows

      - name: Deploy to staging
        run: make deploy-staging
        env:
          PREFECT_API_URL: ${{ secrets.PREFECT_API_URL }}
          PREFECT_API_KEY: ${{ secrets.PREFECT_API_KEY }}
```

## Command Reference Summary

| Command                | Purpose                   | Environment Support |
| ---------------------- | ------------------------- | ------------------- |
| `discover-flows`       | Find and validate flows   | N/A                 |
| `validate-flows`       | Validate flow structure   | N/A                 |
| `build-deployments`    | Create deployment configs | ✓                   |
| `deploy-python`        | Deploy Python flows       | ✓                   |
| `deploy-containers`    | Deploy Docker flows       | ✓                   |
| `deploy-all`           | Deploy all flows          | ✓                   |
| `clean-deployments`    | Remove deployments        | Pattern support     |
| `deploy-dev`           | Deploy to development     | Fixed env           |
| `deploy-staging`       | Deploy to staging         | Fixed env           |
| `deploy-prod`          | Deploy to production      | Fixed env           |
| `validate-deployments` | Validate configs          | ✓                   |
| `test-deployments`     | Dry run deployments       | ✓                   |
| `check-ui`             | Verify UI visibility      | N/A                 |
| `build-images`         | Build Docker images       | Registry support    |
| `push-images`          | Push to registry          | Registry support    |
| `pull-images`          | Pull from registry        | Registry support    |

For more detailed troubleshooting, see the [Troubleshooting Guide](PREFECT_DEPLOYMENT_TROUBLESHOOTING_GUIDE.md).
