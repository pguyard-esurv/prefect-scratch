# Prefect Deployment System Setup Guide

## Overview

This guide will help you set up and configure the Prefect Deployment System for automated flow discovery, building, and deployment in both Python and containerized environments.

## Prerequisites

### System Requirements

- **Python**: 3.8 or higher
- **Docker**: 20.10 or higher
- **Docker Compose**: 2.0 or higher
- **Make**: GNU Make 4.0 or higher
- **Git**: 2.20 or higher

### Required Python Packages

The deployment system requires the following Python packages (automatically installed with the project):

```
prefect>=2.10.0
pydantic>=1.10.0
pyyaml>=6.0
docker>=6.0.0
click>=8.0.0
```

### Infrastructure Requirements

- **Prefect Server**: Running instance (local or remote)
- **PostgreSQL**: Database for Prefect backend
- **Docker Registry**: For container deployments (optional for local development)

## Installation Steps

### 1. Clone and Setup Repository

```bash
# Clone the repository
git clone <repository-url>
cd <repository-name>

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create environment configuration files:

```bash
# Copy example environment files
cp .env.example .env
cp config/deployment-config.yaml.example config/deployment-config.yaml
```

Edit `.env` file with your settings:

```bash
# Prefect Configuration
PREFECT_API_URL=http://localhost:4200/api
PREFECT_API_KEY=your-api-key-here

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/prefect

# Docker Configuration
DOCKER_REGISTRY=your-registry.com
DOCKER_NAMESPACE=your-namespace
```

### 3. Start Infrastructure Services

```bash
# Start Prefect server and database
make start-infrastructure

# Verify services are running
make check-services
```

### 4. Configure Deployment Settings

Edit `config/deployment-config.yaml`:

```yaml
environments:
  development:
    prefect_api_url: "http://localhost:4200/api"
    work_pools:
      python: "default-agent-pool"
      docker: "docker-pool"
    default_parameters:
      cleanup: true
      use_distributed: false
    resource_limits:
      memory: "512Mi"
      cpu: "0.5"

  staging:
    prefect_api_url: "http://staging-prefect:4200/api"
    work_pools:
      python: "staging-agent-pool"
      docker: "staging-docker-pool"
    default_parameters:
      cleanup: true
      use_distributed: true
    resource_limits:
      memory: "1Gi"
      cpu: "1.0"

  production:
    prefect_api_url: "http://prod-prefect:4200/api"
    work_pools:
      python: "prod-agent-pool"
      docker: "prod-docker-pool"
    default_parameters:
      cleanup: false
      use_distributed: true
    resource_limits:
      memory: "2Gi"
      cpu: "2.0"
```

### 5. Create Work Pools

Create the required work pools in Prefect:

```bash
# Create Python work pool
prefect work-pool create default-agent-pool --type process

# Create Docker work pool
prefect work-pool create docker-pool --type docker
```

### 6. Verify Installation

Run the verification commands:

```bash
# Discover flows
make discover-flows

# Validate system configuration
make validate-deployments

# Test deployment creation (dry run)
make test-deployments
```

## Configuration Files

### deployment-config.yaml

Main configuration file for deployment settings:

- **environments**: Environment-specific configurations
- **work_pools**: Prefect work pool mappings
- **default_parameters**: Default flow parameters
- **resource_limits**: Container resource constraints

### flow-templates.yaml

Templates for deployment configurations:

- **python_deployment**: Template for Python deployments
- **docker_deployment**: Template for container deployments

### Environment Files

- **`.env`**: Main environment variables
- **`.env.development`**: Development-specific settings
- **`.env.staging`**: Staging-specific settings
- **`.env.production`**: Production-specific settings

## Verification Steps

### 1. Check Prefect Connection

```bash
# Test Prefect API connectivity
prefect server ls

# Check work pools
prefect work-pool ls
```

### 2. Verify Flow Discovery

```bash
# Discover all flows
make discover-flows

# Expected output should list all flows in flows/ directory
```

### 3. Test Deployment Creation

```bash
# Create test deployments (dry run)
make test-deployments

# Build actual deployments
make build-deployments
```

### 4. Verify Prefect UI

1. Open Prefect UI: http://localhost:4200
2. Navigate to Deployments
3. Verify deployments appear with correct names and configurations

## Common Setup Issues

### Prefect Connection Issues

**Problem**: Cannot connect to Prefect server
**Solution**:

- Verify PREFECT_API_URL is correct
- Check if Prefect server is running: `prefect server ls`
- Ensure network connectivity

### Docker Issues

**Problem**: Docker commands fail
**Solution**:

- Verify Docker is running: `docker ps`
- Check Docker permissions: `docker run hello-world`
- Ensure user is in docker group (Linux)

### Work Pool Issues

**Problem**: Work pools not found
**Solution**:

- Create work pools: `prefect work-pool create <name> --type <type>`
- Verify work pools exist: `prefect work-pool ls`
- Check work pool configuration in deployment-config.yaml

### Flow Discovery Issues

**Problem**: Flows not discovered
**Solution**:

- Verify flows have @flow decorator
- Check Python syntax in flow files
- Ensure flows directory structure is correct

## Next Steps

After successful setup:

1. Read the [Developer Guide](PREFECT_DEPLOYMENT_DEVELOPER_GUIDE.md)
2. Review [Flow Structure Guidelines](PREFECT_FLOW_STRUCTURE_GUIDE.md)
3. Check [Troubleshooting Guide](PREFECT_DEPLOYMENT_TROUBLESHOOTING_GUIDE.md) for common issues

## Support

For additional help:

- Check the troubleshooting guide
- Review Prefect documentation: https://docs.prefect.io
- Check project issues and documentation
