# Development Workflow Guide

This guide covers the development workflow optimization features implemented for the Container Testing System, providing fast iteration cycles, intelligent testing, and comprehensive debugging tools.

## Quick Start

### 1. Set Up Development Environment

```bash
# Complete development environment setup
make dev-setup

# Or manually
python scripts/dev_workflow.py env setup
```

This will:

- Check Docker availability
- Build base container image
- Start infrastructure services (PostgreSQL, Prefect)
- Wait for services to become healthy
- Run initial smoke tests
- Set up file watcher for hot reloading

### 2. Check Environment Status

```bash
# Quick status check
make dev-status

# Detailed status with debugging info
make dev-debug
```

### 3. Start Development

```bash
# Start file watcher for hot reloading
make dev-watch

# Run smart tests (only changed files)
make test-smart

# Open database inspector
make db-inspect
```

## Development Features

### Hot Reloading and File Watching

The development environment includes automatic file watching and container rebuilding:

- **File Watcher**: Monitors code changes and triggers selective rebuilds
- **Smart Rebuilds**: Only rebuilds affected containers based on change patterns
- **Hot Reloading**: Mounts source code for immediate changes without rebuilds

#### File Change Patterns

| Pattern              | Trigger            | Action                         |
| -------------------- | ------------------ | ------------------------------ |
| `core/**/*.py`       | Base image rebuild | Rebuild base + all flow images |
| `flows/rpa1/**/*.py` | RPA1 changes       | Rebuild RPA1 image only        |
| `Dockerfile.*`       | Container config   | Rebuild specific container     |
| `docker-compose.yml` | Orchestration      | Restart all services           |
| `**/test_*.py`       | Test changes       | Run affected tests             |

### Fast Test Execution

#### Smart Test Runner

```bash
# Run tests for files changed in last 30 minutes
make test-smart

# Run tests for files changed in last 2 hours
python scripts/fast_test_runner.py smart --since 120

# Run specific test suite
make test-suite SUITE=unit

# Run all tests with parallel execution
make test-all
```

#### Test Categories

- **Unit Tests**: Fast, isolated component tests
- **Integration Tests**: Service integration validation
- **Container Tests**: Container-specific functionality
- **Performance Tests**: Load and performance validation

### Debugging Tools

#### Database Inspector

```bash
# Start pgAdmin for database inspection
make db-inspect
# Access at http://localhost:8080
# Email: dev@rpa.local, Password: dev_password
```

#### Container Debugging

```bash
# List all containers with status
make containers-list

# Show container resource usage
make containers-stats

# Execute command in container
make containers-exec CONTAINER=rpa-rpa1-worker CMD="ps aux"

# Get container logs
docker-compose logs -f rpa1-worker
```

#### Log Analysis

```bash
# Search logs for errors
make logs-search PATTERN="error"

# Tail specific log file
make logs-tail FILE="rpa1/workflow.log"

# List all log files
make logs-list
```

### Development Profiles

The system uses Docker Compose profiles for different development modes:

#### Default Profile

```bash
docker-compose up -d
# Starts: postgres, prefect-server, flow workers
```

#### Development Profile

```bash
docker-compose --profile development up -d
# Adds: file-watcher, db-inspector, log-viewer
```

#### Debug Profile

```bash
docker-compose --profile debug up -d
# Adds: debugpy ports, enhanced logging, debug volumes
```

#### Testing Profile

```bash
docker-compose --profile testing up -d
# Adds: test-runner service with full test environment
```

## Development Workflow Commands

### Environment Management

```bash
make dev-setup          # Complete environment setup
make dev-status         # Show environment status
make dev-stop           # Stop all containers
make dev-clean          # Clean up environment
```

### Container Management

```bash
make dev-rebuild        # Rebuild all containers
make docker-build       # Build container images
make docker-up          # Start containers
make docker-down        # Stop containers
```

### Testing

```bash
make test-smart         # Smart test execution
make test-container     # Container-specific tests
make test-distributed   # Distributed processing tests
make test-performance   # Performance tests
```

### Database Operations

```bash
make db-inspect         # Open database inspector
make db-status          # Check database health
make db-query QUERY="SELECT * FROM table"  # Run custom query
```

### Log Management

```bash
make dev-logs           # Show all container logs
make logs-search PATTERN="error"  # Search logs
make logs-tail FILE="rpa1/workflow.log"  # Tail log file
```

## Configuration Files

### Docker Compose Override

The `docker-compose.override.yml` file provides development-specific configurations:

- **Hot Reloading**: Source code volume mounts
- **Debug Ports**: Exposed debugging ports (5678-5680)
- **Enhanced Logging**: Detailed log configuration
- **Development Services**: pgAdmin, log viewer, file watcher

### Environment Variables

Development-specific environment variables:

```bash
CONTAINER_DEBUG_MODE=true
CONTAINER_HOT_RELOAD=true
CONTAINER_LOG_LEVEL=DEBUG
```

## File Watcher Configuration

The file watcher (`scripts/development_watcher.py`) monitors:

- **Core Changes**: Triggers base image rebuild
- **Flow Changes**: Triggers specific flow image rebuild
- **Config Changes**: Triggers service restart
- **Test Changes**: Triggers test execution

### Customizing Watch Patterns

Edit `ChangeDetectionConfig` in `development_watcher.py`:

```python
@dataclass
class ChangeDetectionConfig:
    base_image_patterns: Set[str] = field(default_factory=lambda: {
        "core/**/*.py",
        "requirements.txt",
        "Dockerfile.base"
    })

    flow_patterns: Dict[str, Set[str]] = field(default_factory=lambda: {
        "rpa1": {"flows/rpa1/**/*.py", "Dockerfile.flow1"}
    })
```

## Performance Optimization

### Build Optimization

- **Layer Caching**: Docker layer caching for faster builds
- **Two-Stage Builds**: Base image + flow-specific layers
- **Selective Rebuilds**: Only rebuild affected components

### Test Optimization

- **Parallel Execution**: Multiple test workers
- **Smart Selection**: Only run tests for changed code
- **Fast Feedback**: Immediate results for critical tests

### Resource Management

- **Container Limits**: Defined CPU and memory limits
- **Connection Pooling**: Efficient database connections
- **Volume Optimization**: Optimized volume mounts

## Troubleshooting

### Common Issues

#### File Watcher Not Working

```bash
# Check file watcher status
docker-compose ps file-watcher

# Restart file watcher
docker-compose restart file-watcher

# Check file watcher logs
docker-compose logs file-watcher
```

#### Container Build Failures

```bash
# Clean Docker cache
docker system prune -f

# Rebuild from scratch
docker-compose build --no-cache

# Check build logs
docker-compose build 2>&1 | tee build.log
```

#### Database Connection Issues

```bash
# Check database status
make db-status

# Restart database
docker-compose restart postgres

# Check database logs
docker-compose logs postgres
```

#### Test Failures

```bash
# Run tests with verbose output
python scripts/fast_test_runner.py smart --verbose

# Run specific test file
pytest core/test/test_config.py -v

# Check test environment
docker-compose run --rm test-runner python -c "import core; print('OK')"
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Start containers in debug mode
docker-compose --profile debug up -d

# Connect debugger to RPA1 worker
# Port 5678 for rpa1-worker
# Port 5679 for rpa2-worker
# Port 5680 for rpa3-worker
```

### Performance Monitoring

```bash
# Monitor container resources
python scripts/debug_toolkit.py dashboard monitor

# Check container stats
make containers-stats

# Monitor database performance
make db-query QUERY="SELECT * FROM pg_stat_activity"
```

## Best Practices

### Development Workflow

1. **Start with Environment Setup**: Always run `make dev-setup` first
2. **Use Smart Tests**: Run `make test-smart` frequently for fast feedback
3. **Monitor Status**: Check `make dev-status` regularly
4. **Clean Up**: Use `make dev-clean` when switching branches

### Code Changes

1. **Small Iterations**: Make small, focused changes
2. **Test Early**: Run tests immediately after changes
3. **Check Logs**: Monitor container logs for issues
4. **Use Debugger**: Leverage debug ports for complex issues

### Container Management

1. **Selective Rebuilds**: Let file watcher handle rebuilds automatically
2. **Resource Monitoring**: Keep an eye on container resource usage
3. **Log Management**: Regularly clean up log files
4. **Health Checks**: Monitor service health status

This development workflow provides fast iteration cycles, comprehensive debugging capabilities, and intelligent automation to maximize developer productivity while maintaining system reliability.
