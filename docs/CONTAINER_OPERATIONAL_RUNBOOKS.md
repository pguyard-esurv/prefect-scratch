# Container Operational Runbooks

## Overview

This document provides comprehensive operational runbooks for production deployment, maintenance, and incident response for the Container Testing System. These runbooks are designed for operations teams, DevOps engineers, and system administrators managing the containerized distributed processing environment.

## Table of Contents

1. [Deployment Procedures](#deployment-procedures)
2. [Maintenance Operations](#maintenance-operations)
3. [Monitoring and Health Checks](#monitoring-and-health-checks)
4. [Incident Response](#incident-response)
5. [Backup and Recovery](#backup-and-recovery)
6. [Scaling Operations](#scaling-operations)
7. [Security Operations](#security-operations)
8. [Performance Management](#performance-management)
9. [Troubleshooting Procedures](#troubleshooting-procedures)
10. [Emergency Procedures](#emergency-procedures)

## Deployment Procedures

### Pre-Deployment Checklist

Before any deployment, ensure the following items are completed:

```bash
# 1. Verify environment configuration
./scripts/validate_environment.sh production

# 2. Run security scan
./scripts/security_scanner.sh --environment production

# 3. Validate configuration
docker-compose -f docker-compose.prod.yml config --quiet

# 4. Check resource availability
./scripts/check_system_resources.sh

# 5. Verify database connectivity
./scripts/validate_database_config.py --environment production

# 6. Run pre-deployment tests
python core/test/run_container_tests.py --category smoke --environment production
```

### Initial Production Deployment

#### Step 1: Environment Setup

```bash
# Create production environment directory
mkdir -p /opt/rpa-system/production
cd /opt/rpa-system/production

# Clone repository
git clone <repository-url> .
git checkout <production-tag>

# Set up environment files
cp flows/rpa1/.env.production.example flows/rpa1/.env.production
cp flows/rpa2/.env.production.example flows/rpa2/.env.production
cp flows/rpa3/.env.production.example flows/rpa3/.env.production

# Configure production settings
vim flows/rpa1/.env.production
# Set production database URLs, secrets, etc.
```

#### Step 2: Build Production Images

```bash
# Build base image
./scripts/build_base_image.sh --environment production --tag latest

# Build flow images
./scripts/build_flow_images.sh --environment production --tag latest

# Verify images
docker images | grep rpa-
```

#### Step 3: Database Setup

```bash
# Start database container
docker-compose -f docker-compose.prod.yml up -d postgres

# Wait for database to be ready
timeout 300 bash -c 'until docker exec postgres pg_isready -U postgres; do sleep 5; done'

# Run database migrations
docker exec postgres psql -U postgres -f /docker-entrypoint-initdb.d/init.sql

# Verify database setup
docker exec postgres psql -U postgres -c "\l"
```

#### Step 4: Application Deployment

```bash
# Start supporting services
docker-compose -f docker-compose.prod.yml up -d prefect-server prometheus grafana

# Wait for services to be healthy
./scripts/wait_for_services.sh

# Start application containers
docker-compose -f docker-compose.prod.yml up -d rpa-flow1 rpa-flow2 rpa-flow3

# Verify deployment
./scripts/verify_deployment.sh
```

#### Step 5: Post-Deployment Validation

```bash
# Run health checks
curl -f http://localhost:8080/health || exit 1
curl -f http://localhost:8081/health || exit 1
curl -f http://localhost:8082/health || exit 1

# Run integration tests
python core/test/run_container_tests.py --category integration --environment production

# Verify monitoring
curl -f http://localhost:9090/api/v1/query?query=up
curl -f http://localhost:3000/api/health

# Check logs for errors
docker-compose -f docker-compose.prod.yml logs --tail=100 | grep -i error
```

### Rolling Deployment

For zero-downtime deployments:

```bash
#!/bin/bash
# rolling_deployment.sh

set -e

NEW_TAG=$1
if [ -z "$NEW_TAG" ]; then
    echo "Usage: $0 <new-tag>"
    exit 1
fi

echo "Starting rolling deployment to tag: $NEW_TAG"

# Build new images
./scripts/build_all.sh --tag $NEW_TAG

# Deploy one service at a time
for service in rpa-flow1 rpa-flow2 rpa-flow3; do
    echo "Deploying $service..."

    # Update image tag
    sed -i "s/image: rpa-$service:.*/image: rpa-$service:$NEW_TAG/" docker-compose.prod.yml

    # Rolling update
    docker-compose -f docker-compose.prod.yml up -d $service

    # Wait for health check
    timeout 300 bash -c "until curl -f http://localhost:808${service: -1}/health; do sleep 10; done"

    # Verify deployment
    ./scripts/verify_service_health.sh $service

    echo "$service deployed successfully"
    sleep 30  # Allow time for stabilization
done

echo "Rolling deployment completed successfully"
```

### Rollback Procedure

```bash
#!/bin/bash
# rollback_deployment.sh

set -e

PREVIOUS_TAG=$1
if [ -z "$PREVIOUS_TAG" ]; then
    echo "Usage: $0 <previous-tag>"
    exit 1
fi

echo "Starting rollback to tag: $PREVIOUS_TAG"

# Stop current containers
docker-compose -f docker-compose.prod.yml stop rpa-flow1 rpa-flow2 rpa-flow3

# Update to previous tag
for service in rpa-flow1 rpa-flow2 rpa-flow3; do
    sed -i "s/image: rpa-$service:.*/image: rpa-$service:$PREVIOUS_TAG/" docker-compose.prod.yml
done

# Start with previous images
docker-compose -f docker-compose.prod.yml up -d rpa-flow1 rpa-flow2 rpa-flow3

# Verify rollback
./scripts/verify_deployment.sh

echo "Rollback completed successfully"
```

## Maintenance Operations

### Routine Maintenance Schedule

#### Daily Tasks

```bash
#!/bin/bash
# daily_maintenance.sh

# Check system health
./scripts/health_check.py --comprehensive

# Verify backups
./scripts/verify_backups.sh

# Check disk space
df -h | awk '$5 > 80 {print "WARNING: " $0}'

# Review error logs
docker-compose logs --since 24h | grep -i error > /tmp/daily_errors.log

# Update monitoring dashboards
curl -X POST http://grafana:3000/api/dashboards/db -d @monitoring/dashboards/daily_update.json

# Generate daily report
./scripts/generate_daily_report.sh
```

#### Weekly Tasks

```bash
#!/bin/bash
# weekly_maintenance.sh

# Security updates
./scripts/security_scanner.sh --update

# Performance analysis
python scripts/build_performance_monitor.py --weekly-report

# Database maintenance
docker exec postgres psql -U postgres -c "VACUUM ANALYZE;"

# Log rotation
docker-compose exec rpa-flow1 logrotate /etc/logrotate.conf

# Capacity planning review
./scripts/capacity_planning_review.sh

# Update documentation
./scripts/update_operational_docs.sh
```

#### Monthly Tasks

```bash
#!/bin/bash
# monthly_maintenance.sh

# Full system backup
./scripts/full_system_backup.sh

# Security audit
./scripts/security_audit.sh --comprehensive

# Performance benchmarking
python core/test/run_performance_tests.py --benchmark --report

# Dependency updates
./scripts/update_dependencies.sh --security-only

# Disaster recovery test
./scripts/test_disaster_recovery.sh --dry-run

# Compliance reporting
./scripts/generate_compliance_report.sh
```

### Container Maintenance

#### Image Updates

```bash
# Update base images
docker pull python:3.11-slim
docker pull postgres:15

# Rebuild with updated base
./scripts/build_base_image.sh --no-cache

# Test updated images
python core/test/run_container_tests.py --category smoke

# Deploy updated images
./scripts/rolling_deployment.sh $(date +%Y%m%d-%H%M%S)
```

#### Container Cleanup

```bash
# Remove unused containers
docker container prune -f

# Remove unused images
docker image prune -a -f

# Remove unused volumes (be careful!)
docker volume prune -f

# Remove unused networks
docker network prune -f

# Clean up build cache
docker builder prune -a -f
```

### Database Maintenance

#### Regular Database Tasks

```sql
-- Daily maintenance queries
-- Vacuum and analyze tables
VACUUM ANALYZE processed_surveys;
VACUUM ANALYZE customer_orders;
VACUUM ANALYZE flow_execution_logs;

-- Update table statistics
ANALYZE processed_surveys;
ANALYZE customer_orders;

-- Check for bloated tables
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check for long-running queries
SELECT
    pid,
    now() - pg_stat_activity.query_start AS duration,
    query,
    state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
AND state = 'active';
```

#### Database Performance Monitoring

```bash
# Monitor database performance
docker exec postgres psql -U postgres -c "
SELECT
    datname,
    numbackends as connections,
    xact_commit as commits,
    xact_rollback as rollbacks,
    blks_read,
    blks_hit,
    round((blks_hit::float / (blks_hit + blks_read)) * 100, 2) as cache_hit_ratio
FROM pg_stat_database
WHERE datname IN ('rpa_db', 'survey_hub');
"

# Check connection pool status
docker exec rpa-flow1 python -c "
from core.database import get_database_manager
db = get_database_manager()
print('Pool status:', db.get_pool_status())
"
```

## Monitoring and Health Checks

### System Health Monitoring

#### Automated Health Checks

```bash
#!/bin/bash
# health_check_comprehensive.sh

set -e

echo "=== Comprehensive Health Check ==="
echo "Timestamp: $(date)"

# Container health
echo "--- Container Health ---"
docker-compose ps | grep -v "Up (healthy)" | grep "Up" && echo "WARNING: Unhealthy containers detected"

# Service endpoints
echo "--- Service Endpoints ---"
services=("8080" "8081" "8082" "9090" "3000")
for port in "${services[@]}"; do
    if curl -f -s http://localhost:$port/health > /dev/null; then
        echo "✓ Service on port $port is healthy"
    else
        echo "✗ Service on port $port is unhealthy"
    fi
done

# Database connectivity
echo "--- Database Health ---"
if docker exec postgres pg_isready -U postgres > /dev/null; then
    echo "✓ Database is ready"
else
    echo "✗ Database is not ready"
fi

# Resource usage
echo "--- Resource Usage ---"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"

# Disk space
echo "--- Disk Space ---"
df -h | awk 'NR==1 || /^\/dev/'

# Network connectivity
echo "--- Network Connectivity ---"
docker exec rpa-flow1 ping -c 1 postgres > /dev/null && echo "✓ Network connectivity OK" || echo "✗ Network connectivity failed"

echo "=== Health Check Complete ==="
```

#### Monitoring Alerts Configuration

```yaml
# prometheus/alert_rules.yml
groups:
  - name: container_health
    rules:
      - alert: ContainerDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Container {{ $labels.instance }} is down"

      - alert: HighCPUUsage
        expr: container_cpu_usage_percent > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage on {{ $labels.container_name }}"

      - alert: HighMemoryUsage
        expr: container_memory_usage_percent > 90
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "High memory usage on {{ $labels.container_name }}"

      - alert: DatabaseConnectionFailure
        expr: database_connections_failed_total > 10
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database connection failures detected"

      - alert: SlowProcessing
        expr: processing_duration_seconds > 30
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Slow processing detected"
```

### Performance Monitoring

```bash
# Monitor key performance metrics
./scripts/monitor_performance.sh

# Generate performance report
python scripts/build_performance_monitor.py --report --output /tmp/performance_report.json

# Check for performance degradation
./scripts/performance_regression_check.sh
```

## Incident Response

### Incident Classification

#### Severity Levels

- **P0 (Critical)**: Complete system outage, data loss risk
- **P1 (High)**: Major functionality impaired, significant user impact
- **P2 (Medium)**: Minor functionality impaired, limited user impact
- **P3 (Low)**: Cosmetic issues, no user impact

### Incident Response Procedures

#### P0 - Critical Incident Response

```bash
#!/bin/bash
# critical_incident_response.sh

echo "=== CRITICAL INCIDENT RESPONSE ==="
echo "Incident started at: $(date)"

# 1. Immediate assessment
echo "--- Immediate Assessment ---"
docker-compose ps
docker stats --no-stream

# 2. Stop traffic if necessary
echo "--- Traffic Control ---"
# Uncomment if load balancer integration exists
# curl -X POST http://loadbalancer/api/maintenance-mode

# 3. Capture diagnostic information
echo "--- Diagnostic Capture ---"
mkdir -p /tmp/incident-$(date +%Y%m%d-%H%M%S)
cd /tmp/incident-$(date +%Y%m%d-%H%M%S)

docker-compose logs > docker-logs.txt
docker stats --no-stream > docker-stats.txt
docker system df > docker-system.txt
df -h > disk-usage.txt
free -h > memory-usage.txt
ps aux > processes.txt

# 4. Attempt automatic recovery
echo "--- Automatic Recovery ---"
./scripts/emergency_recovery.sh

# 5. Notify stakeholders
echo "--- Notification ---"
# Implement notification system
# ./scripts/send_incident_notification.sh "P0" "Critical system incident detected"

echo "=== CRITICAL INCIDENT RESPONSE COMPLETE ==="
```

#### Service Recovery Procedures

```bash
#!/bin/bash
# service_recovery.sh

SERVICE=$1
if [ -z "$SERVICE" ]; then
    echo "Usage: $0 <service-name>"
    exit 1
fi

echo "Recovering service: $SERVICE"

# 1. Stop the service
docker-compose stop $SERVICE

# 2. Check for resource issues
docker system df
df -h

# 3. Clear any stuck processes
docker exec $SERVICE pkill -f python || true

# 4. Restart the service
docker-compose up -d $SERVICE

# 5. Wait for health check
timeout 300 bash -c "until curl -f http://localhost:8080/health; do sleep 10; done"

# 6. Verify recovery
./scripts/verify_service_health.sh $SERVICE

echo "Service $SERVICE recovery complete"
```

### Incident Documentation

```bash
# Create incident report template
cat > /tmp/incident_report_template.md << 'EOF'
# Incident Report

## Incident Details
- **Incident ID**: INC-$(date +%Y%m%d-%H%M%S)
- **Severity**: [P0/P1/P2/P3]
- **Start Time**: $(date)
- **End Time**: [To be filled]
- **Duration**: [To be calculated]

## Summary
[Brief description of the incident]

## Impact
- **Services Affected**: [List affected services]
- **Users Impacted**: [Number/percentage of users affected]
- **Business Impact**: [Description of business impact]

## Timeline
- **Detection**: [How was the incident detected]
- **Response**: [Initial response actions]
- **Resolution**: [How was the incident resolved]

## Root Cause
[Detailed analysis of the root cause]

## Resolution
[Steps taken to resolve the incident]

## Prevention
[Actions to prevent similar incidents]

## Lessons Learned
[Key takeaways and improvements]
EOF
```

## Backup and Recovery

### Backup Procedures

#### Database Backup

```bash
#!/bin/bash
# database_backup.sh

BACKUP_DIR="/opt/backups/database"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Full database backup
docker exec postgres pg_dumpall -U postgres > $BACKUP_DIR/full_backup_$TIMESTAMP.sql

# Individual database backups
for db in rpa_db survey_hub; do
    docker exec postgres pg_dump -U postgres $db > $BACKUP_DIR/${db}_backup_$TIMESTAMP.sql
done

# Compress backups
gzip $BACKUP_DIR/*_$TIMESTAMP.sql

# Verify backup integrity
for backup in $BACKUP_DIR/*_$TIMESTAMP.sql.gz; do
    if gzip -t $backup; then
        echo "✓ Backup $backup is valid"
    else
        echo "✗ Backup $backup is corrupted"
    fi
done

# Clean old backups (keep 30 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Database backup completed: $TIMESTAMP"
```

#### Application Data Backup

```bash
#!/bin/bash
# application_backup.sh

BACKUP_DIR="/opt/backups/application"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup configuration files
tar -czf $BACKUP_DIR/config_backup_$TIMESTAMP.tar.gz \
    flows/*/env.* \
    docker-compose*.yml \
    monitoring/ \
    scripts/

# Backup logs
tar -czf $BACKUP_DIR/logs_backup_$TIMESTAMP.tar.gz logs/

# Backup persistent data
docker run --rm -v rpa_data:/data -v $BACKUP_DIR:/backup alpine \
    tar -czf /backup/data_backup_$TIMESTAMP.tar.gz -C /data .

echo "Application backup completed: $TIMESTAMP"
```

### Recovery Procedures

#### Database Recovery

```bash
#!/bin/bash
# database_recovery.sh

BACKUP_FILE=$1
if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    exit 1
fi

echo "Starting database recovery from: $BACKUP_FILE"

# Stop application containers
docker-compose stop rpa-flow1 rpa-flow2 rpa-flow3

# Create database backup before recovery
./scripts/database_backup.sh

# Restore database
if [[ $BACKUP_FILE == *"full_backup"* ]]; then
    # Full restore
    gunzip -c $BACKUP_FILE | docker exec -i postgres psql -U postgres
else
    # Individual database restore
    DB_NAME=$(basename $BACKUP_FILE | cut -d'_' -f1)
    docker exec postgres dropdb -U postgres $DB_NAME
    docker exec postgres createdb -U postgres $DB_NAME
    gunzip -c $BACKUP_FILE | docker exec -i postgres psql -U postgres -d $DB_NAME
fi

# Verify recovery
docker exec postgres psql -U postgres -c "\l"

# Restart application containers
docker-compose up -d rpa-flow1 rpa-flow2 rpa-flow3

# Verify application functionality
./scripts/verify_deployment.sh

echo "Database recovery completed"
```

#### Disaster Recovery

```bash
#!/bin/bash
# disaster_recovery.sh

echo "=== DISASTER RECOVERY PROCEDURE ==="

# 1. Assess damage
echo "--- Damage Assessment ---"
docker-compose ps
docker system df

# 2. Stop all services
echo "--- Stopping Services ---"
docker-compose down

# 3. Restore from backup
echo "--- Restoring from Backup ---"
LATEST_BACKUP=$(ls -t /opt/backups/database/full_backup_*.sql.gz | head -1)
./scripts/database_recovery.sh $LATEST_BACKUP

# 4. Restore application data
echo "--- Restoring Application Data ---"
LATEST_APP_BACKUP=$(ls -t /opt/backups/application/data_backup_*.tar.gz | head -1)
docker run --rm -v rpa_data:/data -v /opt/backups/application:/backup alpine \
    tar -xzf /backup/$(basename $LATEST_APP_BACKUP) -C /data

# 5. Rebuild and restart
echo "--- Rebuilding and Restarting ---"
./scripts/build_all.sh
docker-compose up -d

# 6. Verify recovery
echo "--- Verification ---"
sleep 60
./scripts/verify_deployment.sh

echo "=== DISASTER RECOVERY COMPLETE ==="
```

## Scaling Operations

### Horizontal Scaling

#### Auto-scaling Configuration

```yaml
# docker-compose.scale.yml
version: "3.8"
services:
  rpa-flow1:
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 30s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: "2.0"
          memory: 2G
        reservations:
          cpus: "1.0"
          memory: 1G
```

#### Manual Scaling

```bash
# Scale up services
docker-compose up --scale rpa-flow1=5 --scale rpa-flow2=3 --scale rpa-flow3=2

# Scale down services
docker-compose up --scale rpa-flow1=2 --scale rpa-flow2=1 --scale rpa-flow3=1

# Verify scaling
docker-compose ps
```

#### Load-based Scaling

```bash
#!/bin/bash
# auto_scale.sh

# Monitor CPU usage and scale accordingly
while true; do
    CPU_USAGE=$(docker stats --no-stream --format "{{.CPUPerc}}" rpa-flow1 | sed 's/%//')

    if (( $(echo "$CPU_USAGE > 80" | bc -l) )); then
        echo "High CPU usage detected: $CPU_USAGE%. Scaling up..."
        CURRENT_REPLICAS=$(docker-compose ps -q rpa-flow1 | wc -l)
        NEW_REPLICAS=$((CURRENT_REPLICAS + 1))
        docker-compose up --scale rpa-flow1=$NEW_REPLICAS -d
    elif (( $(echo "$CPU_USAGE < 30" | bc -l) )); then
        echo "Low CPU usage detected: $CPU_USAGE%. Scaling down..."
        CURRENT_REPLICAS=$(docker-compose ps -q rpa-flow1 | wc -l)
        if [ $CURRENT_REPLICAS -gt 1 ]; then
            NEW_REPLICAS=$((CURRENT_REPLICAS - 1))
            docker-compose up --scale rpa-flow1=$NEW_REPLICAS -d
        fi
    fi

    sleep 60
done
```

### Vertical Scaling

```bash
# Update resource limits
sed -i 's/cpus: .*/cpus: "4.0"/' docker-compose.yml
sed -i 's/memory: .*/memory: 4G/' docker-compose.yml

# Apply changes
docker-compose up -d --force-recreate
```

## Security Operations

### Security Monitoring

```bash
#!/bin/bash
# security_monitoring.sh

echo "=== Security Monitoring ==="

# Check for security updates
./scripts/security_scanner.sh --check-updates

# Monitor failed login attempts
docker logs postgres | grep "authentication failed" | tail -10

# Check for suspicious network activity
docker exec rpa-flow1 netstat -tuln | grep LISTEN

# Verify container security
docker exec rpa-flow1 id
docker exec rpa-flow1 ls -la /etc/passwd

# Check file permissions
docker exec rpa-flow1 find /app -type f -perm /o+w

echo "=== Security Monitoring Complete ==="
```

### Security Incident Response

```bash
#!/bin/bash
# security_incident_response.sh

INCIDENT_TYPE=$1

case $INCIDENT_TYPE in
    "breach")
        echo "=== SECURITY BREACH RESPONSE ==="
        # Isolate affected containers
        docker network disconnect rpa_default rpa-flow1
        # Capture forensic data
        docker exec rpa-flow1 ps aux > /tmp/forensic_processes.txt
        docker logs rpa-flow1 > /tmp/forensic_logs.txt
        ;;
    "vulnerability")
        echo "=== VULNERABILITY RESPONSE ==="
        # Run security scan
        ./scripts/security_scanner.sh --comprehensive
        # Update vulnerable components
        ./scripts/update_dependencies.sh --security-only
        ;;
    *)
        echo "Usage: $0 <breach|vulnerability>"
        exit 1
        ;;
esac
```

## Performance Management

### Performance Monitoring

```bash
#!/bin/bash
# performance_monitoring.sh

echo "=== Performance Monitoring ==="

# System performance
echo "--- System Performance ---"
docker stats --no-stream

# Application performance
echo "--- Application Performance ---"
curl -s http://localhost:8080/metrics | grep -E "(processing_rate|error_rate|latency)"

# Database performance
echo "--- Database Performance ---"
docker exec postgres psql -U postgres -c "
SELECT
    datname,
    xact_commit,
    xact_rollback,
    blks_read,
    blks_hit,
    tup_returned,
    tup_fetched
FROM pg_stat_database
WHERE datname IN ('rpa_db', 'survey_hub');
"

echo "=== Performance Monitoring Complete ==="
```

### Performance Optimization

```bash
#!/bin/bash
# performance_optimization.sh

echo "=== Performance Optimization ==="

# Optimize database
docker exec postgres psql -U postgres -c "VACUUM ANALYZE;"

# Clear application caches
docker exec rpa-flow1 python -c "
from core.performance_monitor import PerformanceMonitor
monitor = PerformanceMonitor()
monitor.clear_caches()
"

# Restart services for optimization
docker-compose restart rpa-flow1 rpa-flow2 rpa-flow3

echo "=== Performance Optimization Complete ==="
```

## Emergency Procedures

### Emergency Shutdown

```bash
#!/bin/bash
# emergency_shutdown.sh

echo "=== EMERGENCY SHUTDOWN ==="

# Graceful shutdown with timeout
timeout 60 docker-compose down || docker-compose kill

# Force stop if necessary
docker stop $(docker ps -q) || true

# Verify shutdown
docker ps

echo "=== EMERGENCY SHUTDOWN COMPLETE ==="
```

### Emergency Recovery

```bash
#!/bin/bash
# emergency_recovery.sh

echo "=== EMERGENCY RECOVERY ==="

# Quick system check
docker system df
df -h

# Start essential services first
docker-compose up -d postgres
sleep 30

# Start application services
docker-compose up -d rpa-flow1 rpa-flow2 rpa-flow3

# Quick health check
./scripts/health_check.py --quick

echo "=== EMERGENCY RECOVERY COMPLETE ==="
```

## Contact Information

### Escalation Matrix

- **Level 1**: Operations Team - ops@company.com
- **Level 2**: Development Team - dev@company.com
- **Level 3**: Architecture Team - arch@company.com
- **Level 4**: Management - mgmt@company.com

### Emergency Contacts

- **On-call Engineer**: +1-555-0123
- **Database Administrator**: +1-555-0124
- **Security Team**: +1-555-0125
- **Management**: +1-555-0126

## Documentation Updates

This runbook should be reviewed and updated:

- After each incident
- Monthly during maintenance windows
- When new features are deployed
- When infrastructure changes occur

For additional operational support:

- [Container Testing System Documentation](CONTAINER_TESTING_SYSTEM.md)
- [Troubleshooting Guide](CONTAINER_TROUBLESHOOTING_GUIDE.md)
- [Performance Tuning Guide](CONTAINER_PERFORMANCE_TUNING.md)
- [Developer Guide](CONTAINER_DEVELOPMENT_GUIDE.md)
