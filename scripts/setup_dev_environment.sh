#!/bin/bash

# =============================================================================
# Development Environment Setup Script
# =============================================================================
# This script sets up the complete distributed processing development environment
# from scratch. It handles all the "hidden" setup steps that would otherwise
# require manual configuration.
#
# Usage: ./scripts/setup_dev_environment.sh [options]
# Options:
#   --clean    : Clean existing containers and volumes before setup
#   --no-build : Skip Docker image building
#   --help     : Show this help message
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
POSTGRES_CONTAINER="rpa-postgres"
PREFECT_CONTAINER="rpa-prefect-server"

# Default options
CLEAN_SETUP=false
SKIP_BUILD=false

# =============================================================================
# Helper Functions
# =============================================================================

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
    exit 1
}

show_help() {
    cat << EOF
Development Environment Setup Script

This script sets up the complete distributed processing development environment
including PostgreSQL databases, Prefect server, container images, and all
required configuration files.

Usage: $0 [options]

Options:
    --clean     Clean existing containers and volumes before setup
    --no-build  Skip Docker image building (use existing images)
    --help      Show this help message

Examples:
    $0                    # Standard setup
    $0 --clean            # Clean setup (removes existing data)
    $0 --no-build         # Setup without rebuilding images
    $0 --clean --no-build # Clean setup with existing images

Prerequisites:
    - Docker and Docker Compose installed
    - uv (Python package manager) installed
    - Git repository cloned

What this script does:
    1. Validates prerequisites
    2. Creates container environment files
    3. Builds Docker images (base + flow images)
    4. Starts PostgreSQL and creates databases
    5. Runs database migrations
    6. Starts Prefect server
    7. Starts flow worker containers
    8. Validates the complete setup
    9. Inserts test data for development

EOF
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    
    if ! docker info &> /dev/null; then
        error "Docker is not running. Please start Docker first."
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
        error "Docker Compose is not available. Please install Docker Compose."
    fi
    
    # Check if we're in the right directory
    if [[ ! -f "$PROJECT_ROOT/pyproject.toml" ]]; then
        error "Please run this script from the project root or scripts directory."
    fi
    
    # Check if uv is installed
    if ! command -v uv &> /dev/null; then
        warning "uv is not installed. This may cause issues with dependency management."
        warning "Install uv with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    fi
    
    success "Prerequisites check passed"
}

clean_environment() {
    if [[ "$CLEAN_SETUP" == true ]]; then
        log "Cleaning existing environment..."
        
        # Stop and remove all containers
        cd "$PROJECT_ROOT"
        docker compose down --volumes --remove-orphans 2>/dev/null || true
        
        # Remove any existing images
        docker rmi rpa-base:latest 2>/dev/null || true
        docker rmi rpa-flow-rpa1:latest 2>/dev/null || true
        docker rmi rpa-flow-rpa2:latest 2>/dev/null || true
        docker rmi rpa-flow-rpa3:latest 2>/dev/null || true
        
        # Clean up any prefect_scratch images
        docker images | grep prefect_scratch | awk '{print $3}' | xargs -r docker rmi 2>/dev/null || true
        
        success "Environment cleaned"
    fi
}

create_environment_files() {
    log "Creating container environment files..."
    
    # Create global container environment file
    cat > "$PROJECT_ROOT/core/envs/.env.container" << 'EOF'
# Container Environment Configuration
# This file contains environment-specific settings for containerized deployments

# Database Configuration
CONTAINER_DATABASE_RPA_DB_TYPE=postgresql
CONTAINER_DATABASE_RPA_DB_CONNECTION_STRING=postgresql://rpa_user:rpa_dev_password@postgres:5432/rpa_db
CONTAINER_DATABASE_SURVEYHUB_TYPE=sqlserver
CONTAINER_DATABASE_SURVEYHUB_CONNECTION_STRING=

# Prefect Configuration
CONTAINER_PREFECT_API_URL=http://prefect-server:4200/api
CONTAINER_PREFECT_SERVER_URL=http://prefect-server:4200

# Distributed Processing Configuration
CONTAINER_DISTRIBUTED_PROCESSOR_DEFAULT_BATCH_SIZE=50
CONTAINER_DISTRIBUTED_PROCESSOR_CLEANUP_TIMEOUT_HOURS=1
CONTAINER_DISTRIBUTED_PROCESSOR_MAX_RETRIES=3
CONTAINER_DISTRIBUTED_PROCESSOR_HEALTH_CHECK_INTERVAL=300
CONTAINER_DISTRIBUTED_PROCESSOR_ENABLE_DISTRIBUTED_PROCESSING=true

# Logging Configuration
CONTAINER_LOGGING_LEVEL=INFO
CONTAINER_LOGGING_FORMAT=json
CONTAINER_LOGGING_INCLUDE_TIMESTAMP=true

# Container Resource Configuration
CONTAINER_MAX_CPU_PERCENT=80
CONTAINER_MAX_MEMORY_MB=1024

# Security Configuration
CONTAINER_ENABLE_SECURITY_MONITORING=true
CONTAINER_LOG_SECURITY_EVENTS=true

# Performance Configuration
CONTAINER_CONNECTION_POOL_SIZE=5
CONTAINER_CONNECTION_MAX_OVERFLOW=10
CONTAINER_QUERY_TIMEOUT=30
EOF

    # Create RPA1 container environment file
    cat > "$PROJECT_ROOT/flows/rpa1/.env.container" << 'EOF'
# RPA1 Container Environment Configuration

# Flow-specific Configuration
CONTAINER_RPA1_FLOW_NAME=rpa1
CONTAINER_RPA1_BATCH_SIZE=25
CONTAINER_RPA1_MAX_RETRIES=3
CONTAINER_RPA1_TIMEOUT=300
CONTAINER_RPA1_ENABLE_MONITORING=true

# Worker Configuration
CONTAINER_RPA1_WORKER_ID=rpa1-worker-1
CONTAINER_RPA1_MAX_CONCURRENT_TASKS=5
CONTAINER_RPA1_HEARTBEAT_INTERVAL=30

# Resource Limits
CONTAINER_RPA1_MAX_CPU_PERCENT=50
CONTAINER_RPA1_MAX_MEMORY_MB=512

# Processing Configuration
CONTAINER_RPA1_PROCESS_SURVEYS=true
CONTAINER_RPA1_OUTPUT_FORMAT=json
CONTAINER_RPA1_ENABLE_VALIDATION=true
EOF

    # Create RPA2 container environment file
    cat > "$PROJECT_ROOT/flows/rpa2/.env.container" << 'EOF'
# RPA2 Container Environment Configuration

# Flow-specific Configuration
CONTAINER_RPA2_FLOW_NAME=rpa2
CONTAINER_RPA2_BATCH_SIZE=30
CONTAINER_RPA2_MAX_RETRIES=3
CONTAINER_RPA2_TIMEOUT=300
CONTAINER_RPA2_ENABLE_MONITORING=true

# Worker Configuration
CONTAINER_RPA2_WORKER_ID=rpa2-worker-1
CONTAINER_RPA2_MAX_CONCURRENT_TASKS=5
CONTAINER_RPA2_HEARTBEAT_INTERVAL=30

# Resource Limits
CONTAINER_RPA2_MAX_CPU_PERCENT=50
CONTAINER_RPA2_MAX_MEMORY_MB=512

# Processing Configuration
CONTAINER_RPA2_PROCESS_ORDERS=true
CONTAINER_RPA2_OUTPUT_FORMAT=json
CONTAINER_RPA2_ENABLE_VALIDATION=true
EOF

    # Create RPA3 container environment file
    cat > "$PROJECT_ROOT/flows/rpa3/.env.container" << 'EOF'
# RPA3 Container Environment Configuration

# Flow-specific Configuration
CONTAINER_RPA3_FLOW_NAME=rpa3
CONTAINER_RPA3_BATCH_SIZE=20
CONTAINER_RPA3_MAX_RETRIES=3
CONTAINER_RPA3_TIMEOUT=300
CONTAINER_RPA3_ENABLE_MONITORING=true

# Worker Configuration
CONTAINER_RPA3_WORKER_ID=rpa3-worker-1
CONTAINER_RPA3_MAX_CONCURRENT_TASKS=5
CONTAINER_RPA3_HEARTBEAT_INTERVAL=30

# Resource Limits
CONTAINER_RPA3_MAX_CPU_PERCENT=50
CONTAINER_RPA3_MAX_MEMORY_MB=512

# Processing Configuration
CONTAINER_RPA3_PROCESS_ANALYTICS=true
CONTAINER_RPA3_OUTPUT_FORMAT=json
CONTAINER_RPA3_ENABLE_VALIDATION=true
EOF

    success "Container environment files created"
}

build_docker_images() {
    if [[ "$SKIP_BUILD" == true ]]; then
        log "Skipping Docker image build"
        return
    fi
    
    log "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
    # Build base image
    log "Building base image..."
    if [[ -x "./scripts/build_base_image.sh" ]]; then
        ./scripts/build_base_image.sh
    else
        docker build -f core/docker/Dockerfile -t rpa-base:latest .
    fi
    
    # Build flow images
    log "Building flow images..."
    if [[ -x "./scripts/build_flow_images.sh" ]]; then
        ./scripts/build_flow_images.sh --all
    else
        docker build -f flows/rpa1/Dockerfile -t rpa-flow-rpa1:latest --build-arg BASE_IMAGE=rpa-base:latest .
        docker build -f flows/rpa2/Dockerfile -t rpa-flow-rpa2:latest --build-arg BASE_IMAGE=rpa-base:latest .
        docker build -f flows/rpa3/Dockerfile -t rpa-flow-rpa3:latest --build-arg BASE_IMAGE=rpa-base:latest .
    fi
    
    success "Docker images built successfully"
}

start_database() {
    log "Starting PostgreSQL database..."
    
    cd "$PROJECT_ROOT"
    
    # Start only PostgreSQL first
    docker compose up -d postgres
    
    # Wait for PostgreSQL to be ready
    log "Waiting for PostgreSQL to be ready..."
    timeout=60
    while ! docker exec $POSTGRES_CONTAINER pg_isready -U rpa_user -d rpa_db >/dev/null 2>&1; do
        sleep 2
        timeout=$((timeout - 2))
        if [[ $timeout -le 0 ]]; then
            error "PostgreSQL failed to start within 60 seconds"
        fi
    done
    
    success "PostgreSQL is running and ready"
}

run_database_migrations() {
    log "Running database migrations..."
    
    # Create Prefect database and user
    log "Setting up Prefect database..."
    docker exec $POSTGRES_CONTAINER psql -U postgres -d postgres -f /docker-entrypoint-initdb.d/01_setup_prefect.sql
    
    # Run RPA database migrations
    log "Running RPA database migrations..."
    for migration in "$PROJECT_ROOT/core/migrations/rpa_db"/*.sql; do
        if [[ -f "$migration" ]]; then
            migration_name=$(basename "$migration")
            log "Applying migration: $migration_name"
            docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -f "/docker-entrypoint-initdb.d/rpa_db/$migration_name"
        fi
    done
    
    success "Database migrations completed"
}

start_prefect_server() {
    log "Starting Prefect server..."
    
    cd "$PROJECT_ROOT"
    
    # Start Prefect server
    docker compose up -d prefect-server
    
    # Wait for Prefect server to be ready
    log "Waiting for Prefect server to be ready..."
    timeout=120
    while ! curl -s http://localhost:4200/api/health >/dev/null 2>&1; do
        sleep 5
        timeout=$((timeout - 5))
        if [[ $timeout -le 0 ]]; then
            error "Prefect server failed to start within 120 seconds"
        fi
    done
    
    success "Prefect server is running and ready"
}

start_workers() {
    log "Starting worker containers..."
    
    cd "$PROJECT_ROOT"
    
    # Start all worker containers
    docker compose up -d rpa1-worker rpa2-worker rpa3-worker
    
    # Wait a bit for workers to start
    sleep 10
    
    success "Worker containers started"
}

insert_test_data() {
    log "Inserting test data..."
    
    # Insert test records for development and testing
    docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db << 'EOF'
-- Clear any existing test data
DELETE FROM processing_queue WHERE payload::text LIKE '%test_setup%';

-- Insert test records for each flow
INSERT INTO processing_queue (flow_name, payload, status) VALUES
('rpa1', '{"test_setup": true, "survey_id": "DEV001", "customer_id": "TESTCUST001", "priority": "high"}', 'pending'),
('rpa1', '{"test_setup": true, "survey_id": "DEV002", "customer_id": "TESTCUST002", "priority": "normal"}', 'pending'),
('rpa2', '{"test_setup": true, "order_id": "TESTORDER001", "customer_id": "TESTCUST001", "amount": 99.99}', 'pending'),
('rpa2', '{"test_setup": true, "order_id": "TESTORDER002", "customer_id": "TESTCUST003", "amount": 149.50}', 'pending'),
('rpa3', '{"test_setup": true, "analytics_batch": "BATCH001", "record_count": 250, "data_source": "test"}', 'pending'),
('rpa3', '{"test_setup": true, "analytics_batch": "BATCH002", "record_count": 175, "data_source": "test"}', 'pending');
EOF
    
    success "Test data inserted"
}

validate_setup() {
    log "Validating setup..."
    
    cd "$PROJECT_ROOT"
    
    # Check container status
    log "Checking container status..."
    if ! docker compose ps | grep -q "healthy\|running"; then
        warning "Some containers may not be fully healthy yet"
    fi
    
    # Test database connectivity
    log "Testing database connectivity..."
    record_count=$(docker exec $POSTGRES_CONTAINER psql -U rpa_user -d rpa_db -t -c "SELECT COUNT(*) FROM processing_queue WHERE payload::text LIKE '%test_setup%';" | tr -d ' ')
    
    if [[ "$record_count" -ge 6 ]]; then
        success "Database connectivity test passed ($record_count test records found)"
    else
        warning "Database test may have issues (found $record_count test records, expected 6)"
    fi
    
    # Test Prefect API
    log "Testing Prefect API..."
    if curl -s http://localhost:4200/api/health | grep -q "ok"; then
        success "Prefect API test passed"
    else
        warning "Prefect API may not be fully ready yet"
    fi
    
    success "Setup validation completed"
}

show_completion_message() {
    echo
    echo "=========================================="
    echo -e "${GREEN}🎉 Development Environment Setup Complete!${NC}"
    echo "=========================================="
    echo
    echo -e "${BLUE}Services Available:${NC}"
    echo "  • PostgreSQL Database: localhost:5432"
    echo "    - RPA Database: rpa_db (user: rpa_user, password: rpa_dev_password)"
    echo "    - Prefect Database: prefect_db (user: prefect_user, password: prefect_dev_password)"
    echo "  • Prefect Server UI: http://localhost:4200"
    echo "  • Worker Containers: rpa1-worker, rpa2-worker, rpa3-worker"
    echo
    echo -e "${BLUE}Next Steps:${NC}"
    echo "  1. Check container status: docker compose ps"
    echo "  2. View worker logs: docker compose logs rpa1-worker"
    echo "  3. Access Prefect UI: open http://localhost:4200"
    echo "  4. Check test data: scripts/check_test_data.sh"
    echo
    echo -e "${BLUE}Useful Commands:${NC}"
    echo "  • Stop all services: docker compose down"
    echo "  • View all logs: docker compose logs -f"
    echo "  • Restart workers: docker compose restart rpa1-worker rpa2-worker rpa3-worker"
    echo "  • Clean setup: $0 --clean"
    echo
    echo -e "${YELLOW}Note:${NC} It may take a few minutes for all health checks to pass."
    echo "Use 'docker compose ps' to monitor container health status."
    echo
}

# =============================================================================
# Main Script Logic
# =============================================================================

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clean)
                CLEAN_SETUP=true
                shift
                ;;
            --no-build)
                SKIP_BUILD=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done
    
    echo
    echo "=========================================="
    echo -e "${BLUE}🚀 Setting Up Development Environment${NC}"
    echo "=========================================="
    echo
    
    # Execute setup steps
    check_prerequisites
    clean_environment
    create_environment_files
    build_docker_images
    start_database
    run_database_migrations
    start_prefect_server
    start_workers
    insert_test_data
    validate_setup
    show_completion_message
}

# Run main function
main "$@"