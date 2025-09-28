# Database Monitoring and Operational Utilities

This document describes the comprehensive database monitoring and operational utilities provided by the database management system. These utilities enable proactive monitoring, troubleshooting, and operational visibility across all configured databases.

## Overview

The database monitoring utilities provide:

- **Health Monitoring**: Comprehensive health checks across multiple databases
- **Pool Monitoring**: Connection pool utilization and performance metrics
- **Prerequisite Validation**: Database readiness checks for flow startup
- **Connectivity Diagnostics**: Detailed troubleshooting for connectivity issues
- **Performance Monitoring**: Query performance and response time analysis
- **Operational Dashboards**: Multi-database status summaries

## Available Monitoring Tasks

### 1. Database Health Check (`database_health_check`)

Performs comprehensive health checks for individual databases including connectivity, query execution, and migration status.

```python
from core.tasks import database_health_check

# Basic health check
health_result = database_health_check("rpa_db", include_retry=True)

print(f"Database Status: {health_result['status']}")
print(f"Response Time: {health_result['response_time_ms']}ms")
```

**Returns:**

- `status`: "healthy", "degraded", or "unhealthy"
- `connection`: Boolean indicating connectivity
- `query_test`: Boolean indicating query execution success
- `response_time_ms`: Query response time in milliseconds
- `migration_status`: Current migration information
- `error`: Error message if health check failed

### 2. Connection Pool Monitoring (`connection_pool_monitoring`)

Monitors connection pool status and provides utilization metrics for operational visibility.

```python
from core.tasks import connection_pool_monitoring

pool_status = connection_pool_monitoring("rpa_db")

print(f"Pool Utilization: {pool_status['utilization_percent']}%")
print(f"Pool Health: {pool_status['pool_health']}")
print(f"Recommendation: {pool_status['recommendation']}")
```

**Returns:**

- `pool_size`: Configured pool size
- `checked_out`: Connections currently in use
- `utilization_percent`: Pool utilization percentage
- `pool_health`: "optimal", "moderate", or "high"
- `recommendation`: Operational recommendations

### 3. Database Prerequisite Validation (`database_prerequisite_validation`)

Validates database readiness before flow execution, ensuring all prerequisites are met.

```python
from core.tasks import database_prerequisite_validation

validation_result = database_prerequisite_validation(
    database_names=["rpa_db", "SurveyHub"],
    check_migrations=True,
    performance_threshold_ms=1000.0
)

if validation_result["overall_status"] == "failed":
    print("Prerequisites not met!")
    for db_name, db_result in validation_result["databases"].items():
        if db_result["status"] == "failed":
            print(f"  {db_name}: {db_result['issues']}")
```

**Returns:**

- `overall_status`: "passed", "warning", or "failed"
- `databases`: Individual validation results per database
- `summary`: Count of passed, failed, and warning databases

### 4. Database Connectivity Diagnostics (`database_connectivity_diagnostics`)

Provides detailed diagnostics for troubleshooting database connectivity issues.

```python
from core.tasks import database_connectivity_diagnostics

diagnostics = database_connectivity_diagnostics("rpa_db")

print("Configuration Status:", diagnostics["configuration"])
print("Connectivity Status:", diagnostics["connectivity"])
print("Recommendations:")
for rec in diagnostics["recommendations"]:
    print(f"  - {rec}")
```

**Returns:**

- `configuration`: Configuration validation results
- `connectivity`: Connection test results
- `performance`: Performance metrics
- `recommendations`: Troubleshooting recommendations

### 5. Database Performance Monitoring (`database_performance_monitoring`)

Collects performance metrics including query execution times and connection efficiency.

```python
from core.tasks import database_performance_monitoring

performance_result = database_performance_monitoring(
    "rpa_db",
    test_queries=["SELECT 1", "SELECT COUNT(*) FROM customers"],
    iterations=5
)

assessment = performance_result["overall_assessment"]
print(f"Performance Rating: {assessment['performance_rating']}")
print(f"Average Query Time: {assessment['avg_query_time_ms']}ms")
```

**Returns:**

- `connection_metrics`: Connection performance statistics
- `query_performance`: Individual query execution metrics
- `pool_efficiency`: Connection pool efficiency analysis
- `overall_assessment`: Performance rating and recommendations

### 6. Multi-Database Health Summary (`multi_database_health_summary`)

Generates consolidated health status across multiple databases for operational dashboards.

```python
from core.tasks import multi_database_health_summary

summary = multi_database_health_summary(["rpa_db", "SurveyHub"])

print(f"Overall Status: {summary['overall_status']}")
print(f"Healthy: {summary['status_breakdown']['healthy']}")
print(f"Degraded: {summary['status_breakdown']['degraded']}")
print(f"Unhealthy: {summary['status_breakdown']['unhealthy']}")

if summary["alerts"]:
    print("Active Alerts:")
    for alert in summary["alerts"]:
        print(f"  - {alert}")
```

**Returns:**

- `overall_status`: Worst-case status across all databases
- `status_breakdown`: Count of databases by status
- `databases`: Individual database status
- `alerts`: Active alerts requiring attention
- `recommendations`: Operational recommendations

## Integration with Prefect Flows

### Basic Health Monitoring Flow

```python
from prefect import flow
from core.tasks import database_health_check, multi_database_health_summary

@flow
def database_monitoring_flow():
    # Get overall health summary
    summary = multi_database_health_summary(["rpa_db", "SurveyHub"])

    # Detailed health checks if issues detected
    if summary["overall_status"] != "healthy":
        for db_name in ["rpa_db", "SurveyHub"]:
            health_result = database_health_check(db_name)
            if health_result["status"] != "healthy":
                print(f"Issue with {db_name}: {health_result['error']}")

    return summary
```

### Prerequisite Validation Flow

```python
from prefect import flow
from core.tasks import database_prerequisite_validation

@flow
def validate_prerequisites_flow():
    validation = database_prerequisite_validation(
        database_names=["rpa_db", "SurveyHub"],
        check_migrations=True,
        performance_threshold_ms=1000.0
    )

    if validation["overall_status"] == "failed":
        raise RuntimeError("Database prerequisites not met")

    return validation
```

### Operational Monitoring Flow

```python
from prefect import flow, task
from core.tasks import (
    database_health_check,
    connection_pool_monitoring,
    database_performance_monitoring
)

@flow
def operational_monitoring_flow(database_names: list[str]):
    monitoring_data = {}

    for db_name in database_names:
        # Concurrent monitoring tasks
        health = database_health_check(db_name)
        pool = connection_pool_monitoring(db_name)
        performance = database_performance_monitoring(db_name)

        monitoring_data[db_name] = {
            "health": health,
            "pool": pool,
            "performance": performance
        }

    return monitoring_data
```

## Operational Use Cases

### 1. Flow Startup Validation

Use prerequisite validation to ensure databases are ready before processing:

```python
@flow
def data_processing_flow():
    # Validate prerequisites first
    validation = database_prerequisite_validation(["rpa_db"])

    if validation["overall_status"] != "passed":
        raise RuntimeError("Database not ready for processing")

    # Proceed with data processing
    # ... rest of flow logic
```

### 2. Continuous Health Monitoring

Set up scheduled monitoring for operational visibility:

```python
from prefect import flow
from prefect.deployments import Deployment

@flow
def continuous_monitoring():
    summary = multi_database_health_summary(["rpa_db", "SurveyHub"])

    # Log alerts or send notifications
    if summary["alerts"]:
        for alert in summary["alerts"]:
            print(f"ALERT: {alert}")

    return summary

# Schedule every 15 minutes
deployment = Deployment.build_from_flow(
    flow=continuous_monitoring,
    name="database-health-monitoring",
    schedule={"interval": 900}  # 15 minutes
)
```

### 3. Performance Troubleshooting

Use diagnostics for detailed troubleshooting:

```python
@flow
def troubleshoot_database(database_name: str):
    # Run comprehensive diagnostics
    diagnostics = database_connectivity_diagnostics(database_name)
    performance = database_performance_monitoring(database_name)

    # Analyze results
    issues = []

    if not diagnostics["connectivity"]["connection_successful"]:
        issues.append("Connection failure")

    if performance["overall_assessment"]["performance_rating"] == "poor":
        issues.append("Poor performance")

    return {
        "database_name": database_name,
        "issues": issues,
        "diagnostics": diagnostics,
        "performance": performance
    }
```

### 4. Alerting and Notifications

Implement custom alerting based on monitoring results:

```python
@flow
def monitoring_with_alerts():
    summary = multi_database_health_summary(["rpa_db", "SurveyHub"])

    # Check for critical issues
    critical_alerts = []
    for db_name, db_status in summary["databases"].items():
        if db_status["status"] == "unhealthy":
            critical_alerts.append(f"Database {db_name} is unhealthy")

    # Send notifications (implement your notification logic)
    if critical_alerts:
        send_alert_notification(critical_alerts)

    return summary

def send_alert_notification(alerts):
    # Implement your notification system
    # (email, Slack, PagerDuty, etc.)
    pass
```

## Configuration and Customization

### Performance Thresholds

Customize performance thresholds for your environment:

```python
# Custom thresholds for prerequisite validation
validation = database_prerequisite_validation(
    database_names=["rpa_db"],
    performance_threshold_ms=500.0,  # Stricter threshold
    check_migrations=True
)

# Custom performance monitoring
performance = database_performance_monitoring(
    "rpa_db",
    test_queries=[
        "SELECT 1",
        "SELECT COUNT(*) FROM customers WHERE active = true",
        "SELECT AVG(order_amount) FROM orders WHERE created_date >= CURRENT_DATE"
    ],
    iterations=10  # More iterations for better accuracy
)
```

### Alert Thresholds

Configure custom alert thresholds:

```python
alert_thresholds = {
    "response_time_ms": 2000.0,      # Alert if response > 2 seconds
    "pool_utilization_percent": 80.0, # Alert if pool > 80% utilized
    "connection_failure_threshold": 1  # Alert on any connection failure
}

# Use in operational monitoring
monitoring_result = operational_monitoring_flow(
    database_names=["rpa_db", "SurveyHub"],
    alert_thresholds=alert_thresholds
)
```

## Best Practices

### 1. Regular Health Monitoring

- Schedule health checks every 15-30 minutes in production
- Use multi-database summaries for dashboard views
- Set up alerting for unhealthy status

### 2. Prerequisite Validation

- Always validate prerequisites before data processing flows
- Include migration status checks in validation
- Use appropriate performance thresholds for your environment

### 3. Performance Monitoring

- Run performance monitoring during off-peak hours
- Use representative test queries for your workload
- Monitor trends over time, not just point-in-time metrics

### 4. Troubleshooting

- Use connectivity diagnostics for systematic troubleshooting
- Check configuration validation first
- Review recommendations for specific guidance

### 5. Operational Integration

- Integrate with your existing monitoring systems
- Set up automated alerting for critical issues
- Use monitoring data for capacity planning

## Error Handling

All monitoring tasks are designed to be resilient and provide useful information even when databases are unavailable:

```python
# Health checks return status even on failure
health_result = database_health_check("unavailable_db")
print(health_result["status"])  # "unhealthy"
print(health_result["error"])   # Detailed error message

# Prerequisite validation continues even if some databases fail
validation = database_prerequisite_validation(["good_db", "bad_db"])
print(validation["summary"]["failed"])  # Count of failed databases
```

## Monitoring Data Structure

### Health Check Result

```json
{
  "database_name": "rpa_db",
  "status": "healthy",
  "connection": true,
  "query_test": true,
  "migration_status": {
    "current_version": "V003",
    "pending_migrations": []
  },
  "response_time_ms": 45.2,
  "timestamp": "2024-01-15T10:30:00Z",
  "error": null
}
```

### Pool Status Result

```json
{
  "database_name": "rpa_db",
  "pool_size": 5,
  "checked_out": 2,
  "utilization_percent": 13.33,
  "pool_health": "optimal",
  "recommendation": "Pool utilization is healthy",
  "overflow_analysis": "No overflow connections in use"
}
```

### Performance Monitoring Result

```json
{
  "database_name": "rpa_db",
  "connection_metrics": {
    "avg_connection_time_ms": 25.5,
    "successful_connections": 5
  },
  "query_performance": {
    "query_1": {
      "avg_execution_time_ms": 12.3,
      "success_rate": 100.0
    }
  },
  "overall_assessment": {
    "performance_rating": "excellent",
    "recommendations": ["Performance is within acceptable ranges"]
  }
}
```

## Integration Examples

See `flows/examples/database_monitoring_example.py` for complete working examples of:

- Comprehensive health monitoring flows
- Prerequisite validation flows
- Diagnostic troubleshooting flows
- Operational monitoring with alerting

These examples demonstrate real-world usage patterns and can be adapted for your specific operational requirements.
