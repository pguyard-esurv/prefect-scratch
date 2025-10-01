# Prefect UI Debugging and Connectivity Guide

## Overview

This guide provides comprehensive troubleshooting steps for Prefect UI connectivity issues, deployment visibility problems, and debugging techniques for the Prefect web interface.

## Quick Diagnostics

### Basic UI Health Check

```bash
# Check if UI is accessible
curl -I http://localhost:4200

# Test API endpoint
curl http://localhost:4200/api/health

# Verify deployment visibility
make check-ui

# Check Prefect server status
prefect server ls
```

### Service Status Check

```bash
# Check all Prefect services
docker-compose ps

# Check specific services
docker-compose ps prefect-server prefect-ui

# View service logs
docker-compose logs prefect-server
docker-compose logs prefect-ui
```

## Common UI Issues

### Issue 1: UI Not Loading

**Symptoms:**

- Browser shows "This site can't be reached"
- Connection timeout errors
- Blank page or loading spinner

**Diagnostic Steps:**

1. **Check service status:**

```bash
# Verify Prefect server is running
docker-compose ps prefect-server

# Check if port is accessible
telnet localhost 4200
```

2. **Check network configuration:**

```bash
# Verify port binding
netstat -tlnp | grep 4200

# Check Docker network
docker network ls
docker network inspect rpa-network
```

3. **Review service logs:**

```bash
# Check server startup logs
docker-compose logs prefect-server | tail -50

# Check for error messages
docker-compose logs prefect-server | grep -i error
```

**Solutions:**

1. **Restart services:**

```bash
# Restart Prefect services
docker-compose restart prefect-server

# Full restart if needed
docker-compose down
docker-compose up -d
```

2. **Check configuration:**

```bash
# Verify docker-compose.yml configuration
grep -A 10 "prefect-server:" docker-compose.yml

# Check environment variables
docker-compose config
```

3. **Fix port conflicts:**

```bash
# Check what's using port 4200
lsof -i :4200

# Use different port if needed
PREFECT_UI_PORT=4201 docker-compose up -d
```

### Issue 2: Deployments Not Visible

**Symptoms:**

- Empty deployments list in UI
- Deployments created via CLI but not showing in UI
- Partial deployment information displayed

**Diagnostic Steps:**

1. **Verify deployments exist:**

```bash
# List deployments via CLI
prefect deployment ls

# Check specific deployment
prefect deployment inspect "flow-name/deployment-name"

# Get deployment details
prefect deployment ls --format json | jq '.'
```

2. **Check API connectivity:**

```bash
# Test API endpoints
curl http://localhost:4200/api/deployments

# Check authentication
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
     http://localhost:4200/api/deployments
```

3. **Verify database connection:**

```bash
# Check database connectivity
docker-compose exec prefect-server prefect config view

# Test database queries
docker-compose exec postgres psql -U prefect -d prefect \
    -c "SELECT COUNT(*) FROM deployment;"
```

**Solutions:**

1. **Refresh UI data:**

```bash
# Clear browser cache
# Hard refresh (Ctrl+F5 or Cmd+Shift+R)

# Restart UI service
docker-compose restart prefect-server

# Wait for service to fully start
sleep 30
```

2. **Recreate deployments:**

```bash
# Clean and recreate deployments
make clean-deployments
make build-deployments
make deploy-all

# Verify creation
prefect deployment ls
```

3. **Check deployment names:**

```bash
# Verify deployment naming
prefect deployment ls --format table

# Check for special characters or encoding issues
prefect deployment ls --format json | jq '.[].name' | hexdump -C
```

### Issue 3: Authentication Problems

**Symptoms:**

- "Unauthorized" errors in UI
- Login prompts or access denied messages
- API key validation failures

**Diagnostic Steps:**

1. **Check API key configuration:**

```bash
# Verify API key is set
echo $PREFECT_API_KEY

# Check Prefect configuration
prefect config view

# Test API key validity
prefect auth ls
```

2. **Verify server authentication settings:**

```bash
# Check server configuration
docker-compose exec prefect-server prefect config view

# Review authentication logs
docker-compose logs prefect-server | grep -i auth
```

**Solutions:**

1. **Configure API key:**

```bash
# Set API key
export PREFECT_API_KEY=your-api-key-here
prefect config set PREFECT_API_KEY=your-api-key-here

# Verify configuration
prefect auth ls
```

2. **Reset authentication:**

```bash
# Clear existing configuration
prefect config unset PREFECT_API_KEY

# Reconfigure authentication
prefect auth login
```

### Issue 4: Slow UI Performance

**Symptoms:**

- UI takes long time to load
- Slow navigation between pages
- Timeouts when loading deployment lists

**Diagnostic Steps:**

1. **Check resource usage:**

```bash
# Monitor container resources
docker stats prefect-server

# Check system resources
top
df -h
```

2. **Analyze database performance:**

```bash
# Check database connections
docker-compose exec postgres psql -U prefect -d prefect \
    -c "SELECT count(*) FROM pg_stat_activity;"

# Check database size
docker-compose exec postgres psql -U prefect -d prefect \
    -c "SELECT pg_size_pretty(pg_database_size('prefect'));"
```

**Solutions:**

1. **Optimize database:**

```bash
# Clean old flow runs
prefect flow-run delete --older-than 30d

# Vacuum database
docker-compose exec postgres psql -U prefect -d prefect -c "VACUUM ANALYZE;"
```

2. **Increase resources:**

```yaml
# In docker-compose.yml
services:
  prefect-server:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: "1.0"
```

## Advanced Debugging

### Browser Developer Tools

1. **Open Developer Tools** (F12)
2. **Check Console tab** for JavaScript errors
3. **Review Network tab** for failed API requests
4. **Inspect Elements** for UI rendering issues

**Common Console Errors:**

```javascript
// API connection errors
Failed to fetch: TypeError: NetworkError when attempting to fetch resource

// Authentication errors
401 Unauthorized: Invalid API key

// CORS errors
Access to fetch blocked by CORS policy
```

### API Debugging

#### Test API Endpoints Manually

```bash
# Health check
curl http://localhost:4200/api/health

# List deployments
curl http://localhost:4200/api/deployments

# Get specific deployment
curl http://localhost:4200/api/deployments/{deployment-id}

# List flows
curl http://localhost:4200/api/flows

# Check work pools
curl http://localhost:4200/api/work_pools
```

#### Debug API Responses

```bash
# Get detailed API response
curl -v http://localhost:4200/api/deployments

# Check response headers
curl -I http://localhost:4200/api/deployments

# Test with authentication
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
     http://localhost:4200/api/deployments
```

### Database Debugging

#### Check Database State

```bash
# Connect to database
docker-compose exec postgres psql -U prefect -d prefect

# Check deployment table
SELECT id, name, flow_id, created FROM deployment LIMIT 10;

# Check flow table
SELECT id, name, created FROM flow LIMIT 10;

# Check work pools
SELECT id, name, type FROM work_pool;

# Check for orphaned records
SELECT d.name, f.name FROM deployment d
LEFT JOIN flow f ON d.flow_id = f.id
WHERE f.id IS NULL;
```

#### Database Maintenance

```sql
-- Clean old flow runs (older than 30 days)
DELETE FROM flow_run WHERE created < NOW() - INTERVAL '30 days';

-- Update statistics
ANALYZE;

-- Check database integrity
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats WHERE schemaname = 'public';
```

### Log Analysis

#### Prefect Server Logs

```bash
# View recent logs
docker-compose logs --tail=100 prefect-server

# Follow logs in real-time
docker-compose logs -f prefect-server

# Filter for specific errors
docker-compose logs prefect-server | grep -i "error\|exception\|traceback"

# Search for deployment-related logs
docker-compose logs prefect-server | grep -i deployment
```

#### Common Log Patterns

```bash
# Database connection issues
grep "database\|connection\|postgres" logs/prefect-server.log

# API errors
grep "HTTP\|API\|request" logs/prefect-server.log

# Authentication issues
grep "auth\|token\|unauthorized" logs/prefect-server.log

# Performance issues
grep "timeout\|slow\|performance" logs/prefect-server.log
```

## UI Configuration

### Environment Variables

Key environment variables affecting UI behavior:

```bash
# Prefect server URL
PREFECT_API_URL=http://localhost:4200/api

# UI-specific settings
PREFECT_UI_URL=http://localhost:4200
PREFECT_UI_API_URL=http://localhost:4200/api

# Database connection
PREFECT_API_DATABASE_CONNECTION_URL=postgresql://prefect:prefect@postgres:5432/prefect

# Logging level
PREFECT_LOGGING_LEVEL=INFO

# Server settings
PREFECT_SERVER_API_HOST=0.0.0.0
PREFECT_SERVER_API_PORT=4200
```

### Docker Compose Configuration

```yaml
services:
  prefect-server:
    image: prefecthq/prefect:2-latest
    ports:
      - "4200:4200"
    environment:
      - PREFECT_API_DATABASE_CONNECTION_URL=postgresql+asyncpg://prefect:prefect@postgres:5432/prefect
      - PREFECT_SERVER_API_HOST=0.0.0.0
      - PREFECT_SERVER_API_PORT=4200
    depends_on:
      - postgres
    networks:
      - rpa-network
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4200/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Monitoring and Alerting

### Health Monitoring Script

```bash
#!/bin/bash
# prefect-health-monitor.sh

check_ui_health() {
    local url="http://localhost:4200"
    local api_url="$url/api/health"

    # Check UI accessibility
    if ! curl -s -f "$url" > /dev/null; then
        echo "ERROR: Prefect UI not accessible at $url"
        return 1
    fi

    # Check API health
    if ! curl -s -f "$api_url" > /dev/null; then
        echo "ERROR: Prefect API not healthy at $api_url"
        return 1
    fi

    # Check deployment count
    local deployment_count=$(curl -s "$url/api/deployments" | jq '. | length')
    if [ "$deployment_count" -eq 0 ]; then
        echo "WARNING: No deployments found"
    fi

    echo "OK: Prefect UI and API are healthy"
    return 0
}

# Run health check
check_ui_health
```

### Automated Monitoring

```bash
# Add to crontab for regular monitoring
# */5 * * * * /path/to/prefect-health-monitor.sh >> /var/log/prefect-health.log 2>&1

# Create systemd service for continuous monitoring
cat > /etc/systemd/system/prefect-monitor.service << EOF
[Unit]
Description=Prefect Health Monitor
After=network.target

[Service]
Type=simple
ExecStart=/path/to/prefect-health-monitor.sh
Restart=always
RestartSec=300

[Install]
WantedBy=multi-user.target
EOF
```

## Performance Optimization

### UI Performance Tuning

1. **Database Optimization:**

```sql
-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_deployment_name ON deployment(name);
CREATE INDEX IF NOT EXISTS idx_flow_run_created ON flow_run(created);
CREATE INDEX IF NOT EXISTS idx_flow_run_state ON flow_run(state_type);
```

2. **Server Configuration:**

```yaml
# Increase server resources
services:
  prefect-server:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: "2.0"
    environment:
      - PREFECT_API_SERVICES_SCHEDULER_LOOP_SECONDS=60
      - PREFECT_API_SERVICES_LATE_RUNS_LOOP_SECONDS=300
```

3. **Browser Optimization:**

- Clear browser cache regularly
- Disable browser extensions that might interfere
- Use incognito mode for testing
- Update browser to latest version

### Database Maintenance

```bash
# Regular maintenance script
#!/bin/bash
# prefect-db-maintenance.sh

# Clean old flow runs
docker-compose exec postgres psql -U prefect -d prefect -c "
DELETE FROM flow_run WHERE created < NOW() - INTERVAL '30 days';
"

# Clean old logs
docker-compose exec postgres psql -U prefect -d prefect -c "
DELETE FROM log WHERE created < NOW() - INTERVAL '7 days';
"

# Update statistics
docker-compose exec postgres psql -U prefect -d prefect -c "ANALYZE;"

# Vacuum database
docker-compose exec postgres psql -U prefect -d prefect -c "VACUUM;"

echo "Database maintenance completed"
```

## Troubleshooting Checklist

### Pre-Deployment Checklist

- [ ] Prefect server is running and accessible
- [ ] Database connection is working
- [ ] Work pools are created and configured
- [ ] API key is set and valid (if required)
- [ ] Network connectivity is established
- [ ] Required ports are open and not conflicting

### Post-Deployment Checklist

- [ ] Deployments appear in UI within 30 seconds
- [ ] Deployment names and descriptions are correct
- [ ] Work pool assignments are accurate
- [ ] Parameters and schedules are properly configured
- [ ] Flow runs can be triggered from UI
- [ ] Logs are visible and properly formatted

### Regular Maintenance Checklist

- [ ] Check UI performance weekly
- [ ] Clean old flow runs monthly
- [ ] Update Prefect version quarterly
- [ ] Review and optimize database indexes
- [ ] Monitor disk space and resource usage
- [ ] Backup deployment configurations

## Emergency Procedures

### Complete UI Failure Recovery

```bash
# 1. Stop all services
docker-compose down

# 2. Backup database
docker-compose exec postgres pg_dump -U prefect prefect > prefect_backup.sql

# 3. Clean up containers and volumes
docker-compose down -v
docker system prune -f

# 4. Restart services
docker-compose up -d

# 5. Wait for services to start
sleep 60

# 6. Verify health
make check-ui

# 7. Restore deployments if needed
make build-deployments
make deploy-all
```

### Data Recovery

```bash
# Restore from backup
docker-compose exec -T postgres psql -U prefect prefect < prefect_backup.sql

# Recreate deployments from configuration
make clean-deployments
make build-deployments
make deploy-all

# Verify restoration
prefect deployment ls
make check-ui
```

## Support and Resources

### Diagnostic Information Collection

```bash
# Collect system information
cat > prefect-debug-info.txt << EOF
=== System Information ===
$(uname -a)
$(docker --version)
$(docker-compose --version)

=== Prefect Configuration ===
$(prefect config view)

=== Service Status ===
$(docker-compose ps)

=== Recent Logs ===
$(docker-compose logs --tail=50 prefect-server)

=== Database Status ===
$(docker-compose exec postgres psql -U prefect -d prefect -c "SELECT version();")

=== Network Configuration ===
$(docker network ls)
$(netstat -tlnp | grep 4200)
EOF
```

### Getting Help

1. **Check Documentation**: Review Prefect official documentation
2. **Community Support**: Post on Prefect Discourse forum
3. **GitHub Issues**: Search existing issues or create new ones
4. **Stack Overflow**: Use tags 'prefect' and 'prefect-ui'
5. **Internal Support**: Contact your system administrator

### Useful Resources

- **Prefect Documentation**: https://docs.prefect.io
- **Prefect Community**: https://discourse.prefect.io
- **GitHub Repository**: https://github.com/PrefectHQ/prefect
- **Docker Documentation**: https://docs.docker.com
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
