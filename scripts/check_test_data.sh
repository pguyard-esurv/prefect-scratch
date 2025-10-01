#!/bin/bash

# =============================================================================
# Test Data and System Status Checker
# =============================================================================
# This script checks the status of the distributed processing system and
# displays current test data for verification.
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
POSTGRES_CONTAINER="rpa-postgres"
PREFECT_CONTAINER="rpa-prefect-server"

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_container_status() {
    echo
    echo "=========================================="
    echo -e "${BLUE}📋 Container Status${NC}"
    echo "=========================================="
    
    if ! docker compose ps 2>/dev/null; then
        error "Docker Compose services not found. Have you run setup_dev_environment.sh?"
        exit 1
    fi
    
    echo
    log "Checking individual container health..."
    
    # Check PostgreSQL
    if docker compose ps postgres | grep -q "healthy"; then
        success "PostgreSQL: Healthy"
    else
        warning "PostgreSQL: Not healthy"
    fi
    
    # Check Prefect Server
    if docker compose ps prefect-server | grep -q "healthy"; then
        success "Prefect Server: Healthy"
    else
        warning "Prefect Server: Not healthy"
    fi
    
    # Check Workers
    for worker in rpa1-worker rpa2-worker rpa3-worker; do
        status=$(docker compose ps $worker 2>/dev/null | tail -n1 | awk '{print $NF}' || echo "not found")
        if [[ "$status" == *"healthy"* ]]; then
            success "$worker: Healthy"
        elif [[ "$status" == *"starting"* ]]; then
            warning "$worker: Starting..."
        else
            warning "$worker: $status"
        fi
    done
}

check_database_connectivity() {
    echo
    echo "=========================================="
    echo -e "${BLUE}🔌 Database Connectivity${NC}"
    echo "=========================================="
    
    if docker exec $POSTGRES_CONTAINER pg_isready -U rpa_user -d rpa_db >/dev/null 2>&1; then
        success "PostgreSQL connectivity: OK"
    else
        error "PostgreSQL connectivity: FAILED"
        return 1
    fi
    
    # Test query
    table_count=$(docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ' || echo "0")
    log "Database tables found: $table_count"
    
    if [[ "$table_count" -ge 3 ]]; then
        success "Database schema: OK"
    else
        warning "Database schema may be incomplete"
    fi
}

show_processing_queue_status() {
    echo
    echo "=========================================="
    echo -e "${BLUE}📊 Processing Queue Status${NC}"
    echo "=========================================="
    
    # Show queue summary by status
    echo
    log "Queue Summary by Status:"
    docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -c "
        SELECT 
            status,
            COUNT(*) as count,
            MIN(created_at) as oldest,
            MAX(created_at) as newest
        FROM processing_queue 
        GROUP BY status 
        ORDER BY status;
    " 2>/dev/null || warning "Could not retrieve queue status"
    
    # Show queue summary by flow
    echo
    log "Queue Summary by Flow:"
    docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -c "
        SELECT 
            flow_name,
            status,
            COUNT(*) as count
        FROM processing_queue 
        GROUP BY flow_name, status 
        ORDER BY flow_name, status;
    " 2>/dev/null || warning "Could not retrieve flow status"
    
    # Show recent activity
    echo
    log "Recent Activity (last 10 records):"
    docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -c "
        SELECT 
            id,
            flow_name,
            status,
            payload,
            created_at
        FROM processing_queue 
        ORDER BY created_at DESC 
        LIMIT 10;
    " 2>/dev/null || warning "Could not retrieve recent activity"
}

test_distributed_processing() {
    echo
    echo "=========================================="
    echo -e "${BLUE}🧪 Testing Distributed Processing${NC}"
    echo "=========================================="
    
    log "Testing direct database operations..."
    
    # Insert a test record
    test_id=$(date +%s)
    inserted_id=$(docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -c "
        INSERT INTO processing_queue (flow_name, payload, status) 
        VALUES ('test_flow', '{\"test_id\": $test_id, \"message\": \"connectivity_test\"}', 'pending')
        RETURNING id;
    " -t 2>/dev/null | tr -d ' ' || echo "")
    
    if [[ -n "$inserted_id" ]]; then
        success "Test record inserted successfully"
        
        # Try to claim the record
        claimed_id=$(docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -c "
            UPDATE processing_queue 
            SET status = 'processing'
            WHERE flow_name = 'test_flow' AND payload::text LIKE '%$test_id%' AND status = 'pending'
            RETURNING id;
        " -t 2>/dev/null | tr -d ' ' || echo "")
        
        if [[ -n "$claimed_id" ]]; then
            success "Test record claimed successfully"
            
            # Mark as completed
            docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -c "
                UPDATE processing_queue 
                SET status = 'completed'
                WHERE id = $claimed_id;
            " >/dev/null 2>&1
            
            success "Test record completed successfully"
            
            # Clean up test record
            docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -c "
                DELETE FROM processing_queue WHERE id = $claimed_id;
            " >/dev/null 2>&1
            
            success "Distributed processing test: PASSED"
        else
            warning "Could not claim test record"
        fi
    else
        warning "Could not insert test record"
    fi
}

check_prefect_api() {
    echo
    echo "=========================================="
    echo -e "${BLUE}🌊 Prefect API Status${NC}"
    echo "=========================================="
    
    if curl -s http://localhost:4200/api/health >/dev/null 2>&1; then
        success "Prefect API: Accessible"
        
        # Get version info
        version_info=$(curl -s http://localhost:4200/api/admin/version 2>/dev/null || echo "{}")
        if [[ "$version_info" != "{}" ]]; then
            log "Prefect version info: $version_info"
        fi
        
        # Check flows
        flows_count=$(curl -s "http://localhost:4200/api/flows/" 2>/dev/null | grep -o '"id"' | wc -l | tr -d ' ' || echo "0")
        log "Flows registered: $flows_count"
        
    else
        warning "Prefect API: Not accessible at http://localhost:4200"
    fi
}

show_helpful_commands() {
    echo
    echo "=========================================="
    echo -e "${BLUE}🛠️  Helpful Commands${NC}"
    echo "=========================================="
    echo
    echo -e "${YELLOW}Container Management:${NC}"
    echo "  docker compose ps                     # Check container status"
    echo "  docker compose logs -f rpa1-worker    # View worker logs"
    echo "  docker compose restart rpa1-worker    # Restart a worker"
    echo "  docker compose down                   # Stop all services"
    echo
    echo -e "${YELLOW}Database Operations:${NC}"
    echo "  docker exec rpa-postgres psql -U rpa_user -d rpa_db  # Connect to database"
    echo "  # Query processing queue:"
    echo "  # SELECT * FROM processing_queue ORDER BY created_at DESC LIMIT 5;"
    echo
    echo -e "${YELLOW}Monitoring:${NC}"
    echo "  curl http://localhost:4200/api/health # Check Prefect API"
    echo "  docker stats                         # Container resource usage"
    echo "  ./scripts/check_test_data.sh         # Run this script again"
    echo
    echo -e "${YELLOW}Testing:${NC}"
    echo "  # Insert test record:"
    echo "  # INSERT INTO processing_queue (flow_name, payload) VALUES ('test', '{\"test\": true}');"
    echo
}

main() {
    echo
    echo "=========================================="
    echo -e "${BLUE}🔍 System Status Check${NC}"
    echo "=========================================="
    
    check_container_status
    check_database_connectivity
    check_prefect_api
    show_processing_queue_status
    test_distributed_processing
    show_helpful_commands
    
    echo
    echo "=========================================="
    echo -e "${GREEN}✅ Status Check Complete${NC}"
    echo "=========================================="
    echo
}

main "$@"