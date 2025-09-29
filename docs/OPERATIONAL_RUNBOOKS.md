# Operational Runbooks

This document provides comprehensive operational runbooks for managing the container testing system in production environments.

## Table of Contents

1. [Deployment Operations](#deployment-operations)
2. [Scaling Operations](#scaling-operations)
3. [Incident Response](#incident-response)
4. [Monitoring and Alerting](#monitoring-and-alerting)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Maintenance Procedures](#maintenance-procedures)

## Deployment Operations

### Standard Deployment Process

#### Prerequisites

- Docker Swarm or Kubernetes cluster is healthy
- Base images are built and available
- Configuration files are validated
- Monitoring systems are operational

#### Deployment Steps

1. **Pre-deployment Validation**

   ```bash
   # Validate deployment configuration
   python scripts/deployment_automation.py validate --service <service-name>

   # Check cluster health
   docker service ls
   docker node ls
   ```

2. **Deploy Single Service**

   ```bash
   # Deploy with automatic rollback on failure
   python scripts/deployment_automation.py deploy \
     --service rpa1-worker \
     --image rpa-flow1:v1.2.3 \
     --config deployment-config.json
   ```

3. **Deploy All Services**

   ```bash
   # Deploy from manifest with orchestrated rollout
   python scripts/deployment_automation.py deploy-all \
     --manifest deployment-manifest.json
   ```

4. **Post-deployment Validation**

   ```bash
   # Validate deployment health
   python scripts/deployment_automation.py validate --service <service-name>

   # Check service metrics
   curl http://service-endpoint/metrics
   ```

#### Rollback Procedures

1. **Automatic Rollback**

   - Triggered automatically on health check failures
   - Logs available in deployment automation output
   - No manual intervention required

2. **Manual Rollback**

   ```bash
   # Rollback to previous version
   python scripts/deployment_automation.py rollback --service <service-name>

   # Rollback to specific version
   python scripts/deployment_automation.py rollback \
     --service <service-name> \
     --target-version v1.2.2
   ```

### Emergency Deployment Procedures

#### Critical Bug Fix Deployment

1. **Immediate Actions**

   ```bash
   # Build emergency fix image
   docker build -t rpa-flow1:emergency-fix .

   # Deploy with minimal validation
   python scripts/deployment_automation.py deploy \
     --service rpa1-worker \
     --image rpa-flow1:emergency-fix \
     --config emergency-deployment.json
   ```

2. **Validation**

   ```bash
   # Monitor deployment progress
   watch docker service ps rpa1-worker

   # Validate fix effectiveness
   python scripts/deployment_automation.py validate --service rpa1-worker
   ```

#### Service Recovery

1. **Service Restart**

   ```bash
   # Force service restart
   docker service update --force rpa1-worker

   # Monitor restart progress
   docker service logs -f rpa1-worker
   ```

2. **Complete Service Rebuild**
   ```bash
   # Remove and recreate service
   docker service rm rpa1-worker
   python scripts/deployment_automation.py deploy \
     --service rpa1-worker \
     --image rpa-flow1:latest
   ```

## Scaling Operations

### Horizontal Scaling

#### Manual Scaling

1. **Scale Up Service**

   ```bash
   # Increase replica count
   docker service scale rpa1-worker=5

   # Verify scaling completion
   docker service ps rpa1-worker
   ```

2. **Scale Down Service**

   ```bash
   # Decrease replica count
   docker service scale rpa1-worker=2

   # Monitor graceful shutdown
   docker service logs rpa1-worker
   ```

#### Automatic Scaling Setup

1. **Configure Scaling Policies**

   ```json
   {
     "rpa1-worker": {
       "min_replicas": 2,
       "max_replicas": 10,
       "target_cpu_utilization": 70.0,
       "scale_up_threshold": 85.0,
       "scale_down_threshold": 30.0,
       "cooldown_period": 300
     }
   }
   ```

2. **Enable Auto-scaling**
   ```bash
   python scripts/deployment_automation.py setup-scaling \
     --scaling-config scaling-policies.json
   ```

### Load Balancing

#### Service Discovery Updates

```bash
# Update load balancer configuration
curl -X POST http://load-balancer/api/services \
  -H "Content-Type: application/json" \
  -d '{"service": "rpa1-worker", "replicas": 5}'

# Verify load distribution
curl http://load-balancer/api/health
```

## Incident Response

### Incident Classification

#### Severity Levels

- **Critical**: Complete service outage, data loss risk
- **High**: Significant performance degradation, partial outage
- **Medium**: Minor performance issues, non-critical features affected
- **Low**: Cosmetic issues, minimal impact

### Response Procedures

#### Critical Incidents

1. **Immediate Response (0-5 minutes)**

   ```bash
   # Check overall system health
   python -c "
   from core.operational_manager import OperationalManager
   om = OperationalManager()
   metrics = om.monitor_operations()
   print(f'Active incidents: {metrics.incident_count}')
   print(f'System uptime: {metrics.uptime_percentage}%')
   "

   # Identify failing services
   docker service ls --filter "desired-state=running"
   ```

2. **Assessment (5-15 minutes)**

   ```bash
   # Collect service logs
   for service in $(docker service ls --format "{{.Name}}"); do
     echo "=== $service logs ==="
     docker service logs --tail 50 $service
   done

   # Check resource utilization
   docker stats --no-stream
   ```

3. **Mitigation (15-30 minutes)**

   ```bash
   # Restart failing services
   docker service update --force <failing-service>

   # Scale up healthy services if needed
   docker service scale <healthy-service>=<increased-count>

   # Implement circuit breaker if applicable
   curl -X POST http://api-gateway/circuit-breaker/enable
   ```

#### High Priority Incidents

1. **Performance Degradation**

   ```bash
   # Check resource metrics
   python -c "
   from core.operational_manager import OperationalManager
   om = OperationalManager()
   metrics = om.monitor_operations()
   for service, info in metrics.services.items():
       print(f'{service}: CPU={info[\"metrics\"][\"cpu_usage\"]}%, Memory={info[\"metrics\"][\"memory_usage\"]}%')
   "

   # Scale up if needed
   python scripts/deployment_automation.py setup-scaling --scaling-config emergency-scaling.json
   ```

2. **Database Connectivity Issues**

   ```bash
   # Test database connectivity
   python -c "
   from core.database import DatabaseManager
   db = DatabaseManager()
   try:
       db.test_connection()
       print('Database connection: OK')
   except Exception as e:
       print(f'Database connection: FAILED - {e}')
   "

   # Restart database-dependent services
   docker service update --force rpa1-worker rpa2-worker rpa3-worker
   ```

### Automated Incident Response

The system includes automated incident response capabilities:

```python
# Example: Automated container crash recovery
from core.operational_manager import OperationalManager, Incident, IncidentSeverity

om = OperationalManager()

# Create incident
incident = Incident(
    incident_id="crash_001",
    service_name="rpa1-worker",
    severity=IncidentSeverity.HIGH,
    description="Container crash detected"
)

# Handle automatically
response = om.handle_incidents(incident)
print(f"Resolution successful: {response.resolution_successful}")
print(f"Actions taken: {response.actions_performed}")
```

## Monitoring and Alerting

### Health Check Endpoints

#### Service Health Checks

```bash
# Check individual service health
curl http://rpa1-worker:8000/health
curl http://rpa2-worker:8000/health
curl http://rpa3-worker:8000/health

# Check database health
curl http://postgres:5432/health

# Check Prefect server health
curl http://prefect-server:4200/api/health
```

#### System Metrics Collection

```bash
# Collect operational metrics
python -c "
from core.operational_manager import OperationalManager
import json

om = OperationalManager()
metrics = om.monitor_operations()

print(json.dumps({
    'timestamp': metrics.timestamp.isoformat(),
    'services': len(metrics.services),
    'uptime': metrics.uptime_percentage,
    'incidents': metrics.incident_count,
    'resource_utilization': metrics.resource_utilization
}, indent=2))
"
```

### Alert Configuration

#### Prometheus Alert Rules

```yaml
# /monitoring/alert_rules.yml
groups:
  - name: container_alerts
    rules:
      - alert: ContainerDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.instance }} is down"

      - alert: HighCPUUsage
        expr: cpu_usage_percent > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.service }}"

      - alert: HighMemoryUsage
        expr: memory_usage_percent > 90
        for: 3m
        labels:
          severity: critical
        annotations:
          summary: "High memory usage on {{ $labels.service }}"
```

#### Alert Notification Setup

```bash
# Configure Slack notifications
curl -X POST http://alertmanager:9093/api/v1/receivers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "slack-notifications",
    "slack_configs": [{
      "api_url": "https://hooks.slack.com/services/...",
      "channel": "#ops-alerts",
      "title": "Container Alert",
      "text": "{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}"
    }]
  }'
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Container Startup Failures

**Symptoms:**

- Containers fail to start
- Health checks failing
- Service unavailable errors

**Diagnosis:**

```bash
# Check container logs
docker service logs <service-name>

# Check service events
docker service ps <service-name>

# Verify image availability
docker image ls | grep <image-name>
```

**Solutions:**

```bash
# Rebuild and redeploy
docker build -t <image-name>:latest .
python scripts/deployment_automation.py deploy --service <service-name> --image <image-name>:latest

# Check resource constraints
docker service inspect <service-name> --format '{{.Spec.TaskTemplate.Resources}}'

# Verify network connectivity
docker network ls
docker network inspect <network-name>
```

#### 2. Database Connection Issues

**Symptoms:**

- Database connection timeouts
- SQL execution errors
- Connection pool exhaustion

**Diagnosis:**

```bash
# Test database connectivity
python -c "
from core.database import DatabaseManager
db = DatabaseManager()
db.test_connection()
"

# Check database logs
docker service logs postgres

# Monitor connection count
docker exec -it postgres_container psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
```

**Solutions:**

```bash
# Restart database service
docker service update --force postgres

# Increase connection pool size
# Update database configuration and redeploy

# Clear connection pool
python -c "
from core.database import DatabaseManager
db = DatabaseManager()
db.close_all_connections()
"
```

#### 3. Performance Degradation

**Symptoms:**

- Slow response times
- High resource utilization
- Processing backlogs

**Diagnosis:**

```bash
# Check resource usage
docker stats --no-stream

# Monitor processing queues
python -c "
from core.monitoring import PerformanceMonitor
pm = PerformanceMonitor()
metrics = pm.get_performance_metrics()
print(f'Queue depth: {metrics.queue_depth}')
print(f'Processing rate: {metrics.processing_rate}')
"

# Check for memory leaks
docker exec <container> ps aux --sort=-%mem | head -10
```

**Solutions:**

```bash
# Scale up services
docker service scale <service-name>=<higher-count>

# Optimize resource allocation
python scripts/deployment_automation.py deploy \
  --service <service-name> \
  --config optimized-resources.json

# Clear caches and restart
docker service update --force <service-name>
```

#### 4. Network Connectivity Issues

**Symptoms:**

- Service discovery failures
- Inter-service communication errors
- Load balancer issues

**Diagnosis:**

```bash
# Test service connectivity
docker exec <container> curl http://<target-service>:8000/health

# Check network configuration
docker network inspect <network-name>

# Verify DNS resolution
docker exec <container> nslookup <service-name>
```

**Solutions:**

```bash
# Recreate network
docker network rm <network-name>
docker network create --driver overlay <network-name>

# Update service network configuration
docker service update --network-add <network-name> <service-name>

# Restart networking components
docker service update --force <load-balancer-service>
```

## Maintenance Procedures

### Routine Maintenance

#### Daily Tasks

```bash
# Check system health
python -c "
from core.operational_manager import OperationalManager
om = OperationalManager()
metrics = om.monitor_operations()
print(f'System Status: {\"Healthy\" if metrics.uptime_percentage > 99 else \"Degraded\"}')
print(f'Active Incidents: {metrics.incident_count}')
"

# Clean up old containers and images
docker system prune -f
docker image prune -f

# Backup deployment configurations
cp deployment-config.json backups/deployment-config-$(date +%Y%m%d).json
```

#### Weekly Tasks

```bash
# Update base images
docker pull python:3.11-slim
docker build -t rpa-base:latest -f Dockerfile.base .

# Review deployment history
python -c "
from core.operational_manager import OperationalManager
om = OperationalManager()
for deployment in om.deployment_history[-10:]:
    print(f'{deployment.service_name}: {deployment.status} at {deployment.start_time}')
"

# Performance analysis
python scripts/performance_analysis.py --period weekly
```

#### Monthly Tasks

```bash
# Security updates
docker pull --all-tags <base-image>
python scripts/security_scan.py --all-images

# Capacity planning review
python scripts/capacity_analysis.py --generate-report

# Disaster recovery testing
python scripts/dr_test.py --simulate-failure
```

### Emergency Maintenance

#### Planned Downtime

```bash
# 1. Notify stakeholders
echo "Maintenance window starting at $(date)"

# 2. Drain traffic
curl -X POST http://load-balancer/api/maintenance/enable

# 3. Scale down services
for service in rpa1-worker rpa2-worker rpa3-worker; do
  docker service scale $service=0
done

# 4. Perform maintenance
# ... maintenance tasks ...

# 5. Scale up services
for service in rpa1-worker rpa2-worker rpa3-worker; do
  docker service scale $service=2
done

# 6. Restore traffic
curl -X POST http://load-balancer/api/maintenance/disable

# 7. Validate system health
python scripts/deployment_automation.py validate --service all
```

#### Emergency Patches

```bash
# 1. Build emergency patch
docker build -t rpa-base:emergency-patch -f Dockerfile.base .

# 2. Deploy with minimal testing
python scripts/deployment_automation.py deploy \
  --service <critical-service> \
  --image rpa-base:emergency-patch \
  --config emergency-config.json

# 3. Monitor closely
watch docker service ps <critical-service>

# 4. Rollback if issues
python scripts/deployment_automation.py rollback --service <critical-service>
```

### Backup and Recovery

#### Configuration Backup

```bash
# Backup all configurations
tar -czf config-backup-$(date +%Y%m%d).tar.gz \
  deployment-config.json \
  scaling-policies.json \
  docker-compose.yml \
  monitoring/

# Store in secure location
aws s3 cp config-backup-$(date +%Y%m%d).tar.gz s3://backup-bucket/
```

#### Service Recovery

```bash
# Restore from backup
aws s3 cp s3://backup-bucket/config-backup-latest.tar.gz .
tar -xzf config-backup-latest.tar.gz

# Redeploy services
python scripts/deployment_automation.py deploy-all --manifest deployment-manifest.json

# Validate recovery
python scripts/deployment_automation.py validate --service all
```

This operational runbook provides comprehensive procedures for managing the container testing system in production environments, covering deployment, scaling, incident response, monitoring, troubleshooting, and maintenance operations.
