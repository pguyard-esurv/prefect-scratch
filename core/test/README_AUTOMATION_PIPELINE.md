# Container Testing Automation Pipeline

A comprehensive test automation pipeline with multiple test categories, chaos testing, continuous integration support, test result reporting, and trend analysis for the container testing system.

## Overview

The Container Testing Automation Pipeline provides:

- **Multiple Test Categories**: Unit, integration, container, distributed, performance, security, and end-to-end tests
- **Chaos Testing**: Automated failure injection and resilience validation
- **CI/CD Integration**: Support for GitHub Actions, GitLab CI, and Jenkins
- **Test Result Reporting**: JSON, HTML, and summary reports with trend analysis
- **Performance Monitoring**: Resource usage tracking and bottleneck detection
- **End-to-End Validation**: Complete system functionality verification

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Test Automation Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ Test        │  │ Chaos       │  │ Performance │  │ Trend   │ │
│  │ Categories  │  │ Testing     │  │ Monitoring  │  │ Analysis│ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ Unit Tests  │  │ Integration │  │ Container   │  │ E2E     │ │
│  │             │  │ Tests       │  │ Tests       │  │ Tests   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ CI/CD       │  │ Reporting   │  │ Validation  │  │ Config  │ │
│  │ Integration │  │ System      │  │ Framework   │  │ Mgmt    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov pytest-xdist pytest-timeout pytest-asyncio

# Verify installation
python -c "from core.test.test_automation_pipeline import TestAutomationPipeline; print('✅ Installation successful')"
```

### 2. Basic Usage

```bash
# Run quick tests for fast feedback
python core/test/run_automation_pipeline.py --mode quick

# Run full pipeline with all tests
python core/test/run_automation_pipeline.py --mode full --report

# Run only chaos tests
python core/test/run_automation_pipeline.py --mode chaos

# Run performance tests
python core/test/run_automation_pipeline.py --mode performance
```

### 3. Generate Reports

```bash
# Generate comprehensive reports
python core/test/run_automation_pipeline.py --mode full --report --report-formats json html summary

# Analyze trends over last 30 days
python core/test/run_automation_pipeline.py --analyze-trends --days-back 30
```

## Test Categories

### Unit Tests

- **Purpose**: Fast unit tests with mocked dependencies
- **Duration**: ~2 minutes
- **Coverage**: Core functionality, configuration, health monitoring
- **Critical**: Yes (pipeline fails if these fail)

```bash
python -m pytest core/test/ -m "unit" -v --cov=core
```

### Integration Tests

- **Purpose**: Integration tests with real database connections
- **Duration**: ~5 minutes
- **Coverage**: Database integration, service orchestration
- **Critical**: Yes

```bash
python -m pytest core/test/ -m "integration" -v
```

### Container Tests

- **Purpose**: Container framework and orchestration tests
- **Duration**: ~10 minutes
- **Coverage**: Container configuration, Docker integration
- **Critical**: Yes

```bash
python -m pytest core/test/ -m "container" -v
```

### Distributed Tests

- **Purpose**: Distributed processing and concurrent execution
- **Duration**: ~15 minutes
- **Coverage**: Multi-container coordination, duplicate prevention
- **Critical**: Yes

```bash
python -m pytest core/test/ -m "distributed" -v
```

### Performance Tests

- **Purpose**: Performance benchmarks and load tests
- **Duration**: ~20 minutes
- **Coverage**: Throughput, latency, resource utilization
- **Critical**: No (warnings only)

```bash
python -m pytest core/test/ -m "performance" -v
```

### Security Tests

- **Purpose**: Security validation and compliance
- **Duration**: ~5 minutes
- **Coverage**: Container security, secret management
- **Critical**: No

```bash
python -m pytest core/test/ -m "security" -v
```

### End-to-End Tests

- **Purpose**: Complete system validation
- **Duration**: ~30 minutes
- **Coverage**: Full workflow validation
- **Critical**: No

```bash
python -m pytest core/test/test_end_to_end_validation.py -v
```

## Chaos Testing

The pipeline includes comprehensive chaos testing scenarios to validate system resilience:

### Available Scenarios

1. **Container Crash Recovery**

   - Simulates container failures
   - Validates graceful degradation
   - Tests automatic recovery

2. **Database Connection Loss**

   - Simulates database failures
   - Tests retry mechanisms
   - Validates data consistency

3. **Network Partition Resilience**

   - Simulates network issues
   - Tests partition tolerance
   - Validates recovery behavior

4. **Resource Exhaustion Handling**

   - Simulates resource pressure
   - Tests backpressure mechanisms
   - Validates performance under load

5. **Random Failure Combinations**
   - Tests multiple simultaneous failures
   - Validates adaptive recovery
   - Tests system limits

### Running Chaos Tests

```bash
# Run all chaos scenarios
python core/test/run_automation_pipeline.py --mode chaos

# Run specific chaos test
python -c "
import asyncio
from core.test.test_automation_pipeline import TestAutomationPipeline, ChaosTestScenario

async def run_chaos():
    pipeline = TestAutomationPipeline()
    scenario = ChaosTestScenario(
        name='custom_test',
        description='Custom chaos test',
        failure_type='container_crash',
        failure_probability=1.0,
        duration_seconds=30,
        recovery_timeout_seconds=60,
        expected_behavior='graceful_degradation'
    )
    result = await pipeline.chaos_engine.execute_chaos_scenario(scenario)
    print(f'Chaos test result: {result.status}')

asyncio.run(run_chaos())
"
```

## Execution Modes

### Quick Mode

- **Purpose**: Fast feedback for development
- **Duration**: ~5 minutes
- **Tests**: Unit + basic integration
- **Chaos**: Disabled
- **Performance**: Disabled

```bash
python core/test/run_automation_pipeline.py --mode quick
```

### Full Mode

- **Purpose**: Complete validation
- **Duration**: ~60 minutes
- **Tests**: All categories
- **Chaos**: Enabled
- **Performance**: Enabled

```bash
python core/test/run_automation_pipeline.py --mode full
```

### Chaos Mode

- **Purpose**: Resilience testing
- **Duration**: ~30 minutes
- **Tests**: Unit + integration + chaos
- **Focus**: System resilience

```bash
python core/test/run_automation_pipeline.py --mode chaos
```

### Performance Mode

- **Purpose**: Performance validation
- **Duration**: ~45 minutes
- **Tests**: Unit + performance
- **Focus**: System performance

```bash
python core/test/run_automation_pipeline.py --mode performance
```

## CI/CD Integration

### GitHub Actions

Generate GitHub Actions workflow:

```bash
python scripts/generate_ci_configs.py github --output .github/workflows/test-pipeline.yml
```

Features:

- Matrix builds across Python versions
- Parallel test execution
- Coverage reporting
- Artifact uploads
- Scheduled runs

### GitLab CI

Generate GitLab CI configuration:

```bash
python scripts/generate_ci_configs.py gitlab --output .gitlab-ci.yml
```

Features:

- Multi-stage pipeline
- Docker-in-Docker support
- Coverage reports
- Pages deployment
- Scheduled pipelines

### Jenkins

Generate Jenkins pipeline:

```bash
python scripts/generate_ci_configs.py jenkins --output Jenkinsfile
```

Features:

- Declarative pipeline
- Parallel stages
- Email notifications
- Artifact archiving
- Post-build actions

### Generate All Configurations

```bash
python scripts/generate_ci_configs.py all --output ./ci_configs
```

## Reporting and Analytics

### Report Formats

#### JSON Report

- Machine-readable format
- Complete test results
- Performance metrics
- Trend data

#### HTML Report

- Human-readable format
- Interactive charts
- Visual summaries
- Responsive design

#### Summary Report

- Text-based summary
- Key metrics
- Recommendations
- Trend highlights

### Trend Analysis

The pipeline automatically tracks test results over time and provides trend analysis:

```bash
# Analyze trends over last 30 days
python core/test/run_automation_pipeline.py --analyze-trends --days-back 30
```

Trend metrics include:

- Success rate trends
- Performance trends
- Failure pattern analysis
- Chaos test resilience trends
- Resource utilization trends

### Sample Report Structure

```json
{
  "pipeline_result": {
    "pipeline_id": "pipeline_20241229_143022",
    "status": "passed",
    "total_duration": 1847.23,
    "total_tests": 156,
    "total_passed": 154,
    "total_failed": 2,
    "categories_executed": ["unit", "integration", "container", "distributed"],
    "categories_passed": ["unit", "integration", "container"],
    "categories_failed": ["distributed"],
    "chaos_tests_executed": 5,
    "chaos_tests_passed": 4,
    "performance_metrics": {
      "system_metrics": {
        "cpu_usage_percent": 45.2,
        "memory_usage_percent": 67.8
      }
    },
    "recommendations": [
      "Distributed test category failed - investigate record processing logic",
      "Chaos test success rate is 80% - review system resilience"
    ]
  }
}
```

## Configuration

### Pipeline Configuration

The pipeline behavior is controlled by `core/test/automation_pipeline_config.json`:

```json
{
  "test_categories": {
    "unit": {
      "enabled": true,
      "timeout_seconds": 120,
      "parallel_workers": 4,
      "critical": true
    }
  },
  "chaos_testing": {
    "enabled": true,
    "scenarios": {
      "container_crash_recovery": {
        "enabled": true,
        "duration_seconds": 30
      }
    }
  },
  "execution_modes": {
    "quick": {
      "include_categories": ["unit", "integration"],
      "include_chaos_tests": false
    }
  }
}
```

### Environment Variables

```bash
# Database configuration
export DATABASE_URL="postgresql://user:pass@localhost:5432/test_db"

# Pipeline configuration
export PIPELINE_MODE="quick"
export ENABLE_CHAOS_TESTS="false"
export REPORT_FORMATS="json,html"

# CI/CD configuration
export CI_ENVIRONMENT="github"
export FAIL_FAST="true"
```

## Performance Optimization

### Parallel Execution

The pipeline supports parallel test execution:

```bash
# Run with 8 parallel workers
python -m pytest core/test/ -n 8

# Auto-detect optimal worker count
python -m pytest core/test/ -n auto
```

### Test Selection

Run only changed tests:

```bash
# Run tests affected by recent changes
python core/test/run_automation_pipeline.py --mode quick --since 30  # last 30 minutes
```

### Resource Management

Monitor resource usage during tests:

```bash
# Enable performance monitoring
python core/test/run_automation_pipeline.py --mode full --verbose
```

## Troubleshooting

### Common Issues

#### Database Connection Failures

```bash
# Check database connectivity
python -c "from core.database import DatabaseManager; db = DatabaseManager('rpa_db'); print('✅ Database connected')"

# Use mock databases for testing
export USE_MOCK_DATABASES="true"
```

#### Container Runtime Issues

```bash
# Check Docker availability
docker --version

# Use container simulation mode
export SIMULATE_CONTAINERS="true"
```

#### Performance Issues

```bash
# Reduce parallel workers
export PYTEST_WORKERS="2"

# Skip performance tests
python core/test/run_automation_pipeline.py --mode quick
```

### Debug Mode

Enable verbose logging:

```bash
python core/test/run_automation_pipeline.py --mode full --verbose --log-file pipeline.log
```

### Test Isolation

Run tests in isolation:

```bash
# Run single test category
python -m pytest core/test/ -m "unit" -v

# Run specific test file
python -m pytest core/test/test_automation_pipeline.py -v

# Run specific test method
python -m pytest core/test/test_automation_pipeline.py::TestAutomationPipeline::test_execute_full_pipeline -v
```

## Development

### Adding New Test Categories

1. Define test category in configuration:

```json
{
  "test_categories": {
    "my_category": {
      "enabled": true,
      "timeout_seconds": 300,
      "parallel_workers": 2,
      "critical": false,
      "markers": ["my_category"]
    }
  }
}
```

2. Create test files with appropriate markers:

```python
import pytest

@pytest.mark.my_category
def test_my_functionality():
    assert True
```

3. Update pipeline execution order if needed.

### Adding New Chaos Scenarios

1. Define scenario in configuration:

```json
{
  "chaos_testing": {
    "scenarios": {
      "my_chaos_scenario": {
        "enabled": true,
        "failure_probability": 1.0,
        "duration_seconds": 60,
        "recovery_timeout_seconds": 120,
        "expected_behavior": "graceful_degradation"
      }
    }
  }
}
```

2. Implement failure injection logic in `ChaosTestEngine`.

### Extending Reporting

1. Add new report format to configuration
2. Implement report generator in `TestAutomationPipeline`
3. Update CLI interface to support new format

## Best Practices

### Test Organization

- Use descriptive test names
- Group related tests with markers
- Keep tests independent and isolated
- Use appropriate timeouts

### Chaos Testing

- Start with simple scenarios
- Gradually increase complexity
- Validate recovery mechanisms
- Document expected behaviors

### CI/CD Integration

- Use appropriate execution modes for different triggers
- Cache dependencies when possible
- Parallelize independent test categories
- Set reasonable timeouts

### Performance

- Monitor resource usage
- Use parallel execution appropriately
- Skip expensive tests in quick mode
- Profile slow tests

## API Reference

### TestAutomationPipeline

Main pipeline class for executing comprehensive test automation.

```python
from core.test.test_automation_pipeline import TestAutomationPipeline

pipeline = TestAutomationPipeline(database_managers, config_manager)
result = await pipeline.execute_full_pipeline(
    include_chaos_tests=True,
    include_performance_tests=True,
    fail_fast=False
)
```

### ChaosTestEngine

Engine for executing chaos testing scenarios.

```python
from core.test.test_automation_pipeline import ChaosTestEngine, ChaosTestScenario

engine = ChaosTestEngine(database_managers)
scenario = ChaosTestScenario(...)
result = await engine.execute_chaos_scenario(scenario)
```

### TestTrendAnalyzer

Analyzes test results over time for trend identification.

```python
from core.test.test_automation_pipeline import TestTrendAnalyzer

analyzer = TestTrendAnalyzer()
trends = analyzer.analyze_trends(days_back=30)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Update documentation
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:

- Create an issue in the repository
- Check the troubleshooting section
- Review the test logs for detailed error information
- Run tests in verbose mode for additional debugging information
