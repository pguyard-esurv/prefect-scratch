# Build Automation and Optimization Guide

This guide covers the comprehensive build automation and optimization system for the container testing framework.

## Overview

The build automation system provides:

- **Selective Rebuilds**: Only rebuild containers when relevant code changes
- **Build Cache Optimization**: Intelligent Docker layer caching and management
- **Security Scanning**: Automated vulnerability scanning integration
- **Performance Monitoring**: Build time and efficiency analysis
- **Optimization Recommendations**: Automated suggestions for improvement

## Quick Start

### Basic Usage

```bash
# Standard optimized build
./scripts/build_optimizer.sh

# Maximum optimization with all features
./scripts/build_optimizer.sh --level maximum

# CI-optimized build
./scripts/build_optimizer.sh --ci
```

### Advanced Usage

```bash
# Benchmark different optimization levels
./scripts/build_optimizer.sh --benchmark

# Analyze performance and get recommendations
./scripts/build_optimizer.sh --analyze

# Selective rebuild only changed components
./scripts/selective_rebuild.sh

# Security scan all images
./scripts/security_scanner.sh --all
```

## Build Scripts Overview

### 1. build_optimizer.sh (Main Entry Point)

The primary build orchestration script that coordinates all optimization features.

**Features:**

- Multiple optimization levels (minimal, medium, maximum, ci)
- Automatic CI environment detection
- Benchmark mode for performance comparison
- Performance analysis and recommendations

**Usage:**

```bash
./scripts/build_optimizer.sh [OPTIONS] [BUILD_OPTIONS]

Options:
  --level LEVEL       Optimization level: minimal|medium|maximum|ci
  --benchmark         Run benchmark comparing all levels
  --analyze           Show performance analysis and recommendations
  --no-cleanup        Disable automatic cleanup
  --ci                Enable CI mode optimizations
```

### 2. selective_rebuild.sh

Intelligent rebuild system that only rebuilds containers when relevant code changes are detected.

**Features:**

- File checksum-based change detection
- Dependency-aware rebuild ordering
- Build cache management
- Dry-run mode for testing

**Usage:**

```bash
./scripts/selective_rebuild.sh [OPTIONS]

Options:
  --dry-run           Show what would be built without building
  --force             Force rebuild all containers
  --verbose           Enable verbose logging
  --tag TAG           Tag for built images
```

### 3. build_cache_manager.sh

Advanced Docker build cache optimization and management.

**Features:**

- BuildKit configuration optimization
- Cache size management and cleanup
- Performance analysis
- Cache import/export for CI/CD

**Usage:**

```bash
./scripts/build_cache_manager.sh [ACTION] [OPTIONS]

Actions:
  --setup             Initialize cache system
  --cleanup           Clean up old cache entries
  --optimize          Optimize cache size and performance
  --stats             Display cache statistics
  --export PATH       Export cache for CI/CD
  --import PATH       Import cache from CI/CD
```

### 4. security_scanner.sh

Automated security vulnerability scanning integration.

**Features:**

- Multiple scanner support (Trivy, Grype, Docker Scout)
- Configurable severity thresholds
- HTML report generation
- CI/CD integration

**Usage:**

```bash
./scripts/security_scanner.sh [ACTION] [OPTIONS]

Actions:
  --image IMAGE       Scan specific image
  --all              Scan all project images
  --setup            Setup scanning environment

Options:
  --level LEVEL      Scan level: low|medium|high
  --no-fail-high     Don't fail on high severity issues
  --no-report        Don't generate HTML report
```

### 5. build_performance_monitor.py

Python-based build performance monitoring and analysis tool.

**Features:**

- Build time tracking and analysis
- Cache efficiency monitoring
- Performance trend analysis
- Dockerfile optimization suggestions

**Usage:**

```bash
python3 ./scripts/build_performance_monitor.py [OPTIONS]

Actions:
  --action monitor    Monitor a build process
  --action analyze    Analyze historical performance
  --action report     Generate performance report
  --action optimize   Analyze Dockerfile for optimizations
```

## Optimization Levels

### Minimal

- Basic Docker layer caching
- No selective rebuilds
- No security scanning
- Sequential builds

**Best for:** Simple development environments, resource-constrained systems

### Medium (Default)

- Selective rebuilds based on change detection
- Build cache optimization
- Performance monitoring
- Parallel flow builds

**Best for:** Regular development workflow, local testing

### Maximum

- All medium features plus:
- Security vulnerability scanning
- Comprehensive performance reports
- Advanced cache management
- Full automation

**Best for:** Production builds, comprehensive validation

### CI

- Optimized for continuous integration
- Selective rebuilds with caching
- Security scanning
- Parallel builds
- No interactive features

**Best for:** GitHub Actions, GitLab CI, Jenkins

## Configuration

### Environment Variables

```bash
# Build optimization
export OPTIMIZATION_LEVEL="medium"        # minimal|medium|maximum|ci
export AUTO_CLEANUP="true"                # Enable automatic cleanup
export CI_MODE="false"                    # Enable CI optimizations

# Selective rebuilds
export SELECTIVE_BUILD="true"             # Enable selective rebuilds
export FORCE_REBUILD="false"              # Force rebuild all

# Caching
export ENABLE_CACHING="true"              # Enable build caching
export CACHE_SIZE_LIMIT_GB="10"           # Cache size limit
export CACHE_RETENTION_DAYS="7"           # Cache retention period

# Security scanning
export SECURITY_SCAN="false"             # Enable security scanning
export FAIL_ON_HIGH="true"                # Fail on high severity
export FAIL_ON_CRITICAL="true"            # Fail on critical severity
export TRIVY_ENABLED="true"               # Enable Trivy scanner

# Performance monitoring
export PERFORMANCE_MONITOR="false"        # Enable performance monitoring
export GENERATE_REPORT="false"            # Generate performance reports
```

### Cache Configuration

The build cache system uses BuildKit for optimal performance:

```toml
# .build_cache/buildkit.toml
[worker.oci]
  enabled = true
  platforms = [ "linux/amd64" ]

[cache]
  inline = true

[build]
  max-parallelism = 4
  cache-from = ["type=local,src=.build_cache/docker"]
  cache-to = ["type=local,dest=.build_cache/docker,mode=max"]
```

## Performance Optimization Tips

### 1. Dockerfile Optimization

**Layer Ordering:**

```dockerfile
# Good: Dependencies first (cached)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Then application code (changes frequently)
COPY core/ ./core/
COPY flows/ ./flows/
```

**Multi-stage Builds:**

```dockerfile
# Build stage
FROM python:3.11-slim as builder
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.11-slim as runtime
COPY --from=builder /app/.venv /app/.venv
COPY core/ ./core/
```

### 2. Build Context Optimization

Create `.dockerignore`:

```
.git
.pytest_cache
__pycache__
*.pyc
.build_cache
.security_scans
node_modules
```

### 3. Cache Efficiency

**Monitor cache efficiency:**

```bash
# Check cache statistics
./scripts/build_cache_manager.sh --stats

# Analyze build performance
python3 ./scripts/build_performance_monitor.py --action analyze
```

**Improve cache hits:**

- Order Dockerfile instructions from least to most frequently changing
- Use specific COPY commands instead of COPY . .
- Combine related RUN commands
- Use .dockerignore to reduce build context

## CI/CD Integration

### GitHub Actions

```yaml
name: Optimized Container Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Build Cache
        uses: actions/cache@v3
        with:
          path: .build_cache
          key: build-cache-${{ runner.os }}-${{ hashFiles('**/Dockerfile*', 'pyproject.toml') }}
          restore-keys: build-cache-${{ runner.os }}-

      - name: Optimized Build
        run: ./scripts/build_optimizer.sh --ci --tag ${{ github.sha }}

      - name: Security Scan
        run: ./scripts/security_scanner.sh --all --tag ${{ github.sha }}
```

### GitLab CI

```yaml
build:
  stage: build
  script:
    - ./scripts/build_optimizer.sh --ci --tag $CI_COMMIT_SHA
  cache:
    paths:
      - .build_cache/
  artifacts:
    reports:
      junit: .security_scans/*.xml
```

## Troubleshooting

### Common Issues

**1. Build Cache Not Working**

```bash
# Check BuildKit is enabled
export DOCKER_BUILDKIT=1

# Verify cache setup
./scripts/build_cache_manager.sh --stats

# Reset cache if corrupted
./scripts/build_cache_manager.sh --cleanup
```

**2. Selective Rebuild Not Detecting Changes**

```bash
# Check checksums manually
./scripts/selective_rebuild.sh --dry-run --verbose

# Force rebuild if needed
./scripts/selective_rebuild.sh --force
```

**3. Security Scanner Failing**

```bash
# Install Trivy
./scripts/security_scanner.sh --install-trivy

# Setup scanning environment
./scripts/security_scanner.sh --setup

# Check scanner availability
./scripts/security_scanner.sh --help
```

**4. Performance Issues**

```bash
# Analyze build performance
python3 ./scripts/build_performance_monitor.py --action analyze

# Get optimization recommendations
./scripts/build_optimizer.sh --analyze

# Run benchmark to compare levels
./scripts/build_optimizer.sh --benchmark
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Enable verbose mode
export VERBOSE="true"

# Run with debug output
./scripts/selective_rebuild.sh --verbose
./scripts/build_cache_manager.sh --stats
```

## Best Practices

### Development Workflow

1. **Use selective rebuilds for daily development:**

   ```bash
   ./scripts/selective_rebuild.sh
   ```

2. **Monitor performance regularly:**

   ```bash
   ./scripts/build_optimizer.sh --analyze
   ```

3. **Clean up periodically:**
   ```bash
   ./scripts/build_cache_manager.sh --cleanup
   ```

### Production Builds

1. **Use maximum optimization:**

   ```bash
   ./scripts/build_optimizer.sh --level maximum --tag production
   ```

2. **Always run security scans:**

   ```bash
   ./scripts/security_scanner.sh --all --tag production
   ```

3. **Generate build reports:**
   ```bash
   python3 ./scripts/build_performance_monitor.py --action report
   ```

### CI/CD Pipeline

1. **Use CI optimization level:**

   ```bash
   ./scripts/build_optimizer.sh --ci
   ```

2. **Cache build artifacts:**

   - Export cache: `./scripts/build_cache_manager.sh --export cache.tar.gz`
   - Import cache: `./scripts/build_cache_manager.sh --import cache.tar.gz`

3. **Fail on security issues:**
   ```bash
   export FAIL_ON_CRITICAL="true"
   export FAIL_ON_HIGH="true"
   ```

## Monitoring and Metrics

### Build Metrics

The system tracks:

- Build times and trends
- Cache hit/miss ratios
- Image sizes and layer counts
- Build context sizes
- Security vulnerability counts

### Performance Reports

Generate comprehensive reports:

```bash
# HTML performance report
python3 ./scripts/build_performance_monitor.py --action report --output report.html

# Security scan report
./scripts/security_scanner.sh --all --tag latest
```

### Alerting

Set up alerts for:

- Build time regressions
- Cache efficiency drops
- Security vulnerabilities
- Build failures

## Advanced Features

### Custom Build Hooks

Extend the build system with custom hooks:

```bash
# Pre-build hook
if [[ -f "./scripts/pre-build-hook.sh" ]]; then
    ./scripts/pre-build-hook.sh
fi

# Post-build hook
if [[ -f "./scripts/post-build-hook.sh" ]]; then
    ./scripts/post-build-hook.sh
fi
```

### Multi-Architecture Builds

Support for multi-architecture builds:

```bash
# Enable multi-arch
export DOCKER_BUILDKIT=1
export BUILDX_PLATFORMS="linux/amd64,linux/arm64"

# Build with buildx
docker buildx build --platform $BUILDX_PLATFORMS ...
```

### Build Notifications

Integrate with notification systems:

```bash
# Slack notification on build completion
if [[ -n "${SLACK_WEBHOOK:-}" ]]; then
    curl -X POST -H 'Content-type: application/json' \
        --data '{"text":"Build completed successfully"}' \
        "$SLACK_WEBHOOK"
fi
```

This comprehensive build automation system provides enterprise-grade container build optimization with intelligent caching, security scanning, and performance monitoring capabilities.
