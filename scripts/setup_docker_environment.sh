#!/bin/bash

# Docker Environment Setup Script
# Creates necessary directories and initializes the container testing environment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker and Docker Compose are installed
check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    log_success "Dependencies check passed"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    # Data directories for persistent volumes
    mkdir -p data/{postgres,prefect,prometheus}
    
    # Log directories
    mkdir -p logs/{postgres,prefect,rpa1,rpa2,rpa3,rpa1-2,tests}
    
    # Monitoring directory (already created with prometheus.yml)
    mkdir -p monitoring
    
    # Temporary directories
    mkdir -p tmp/{rpa1,rpa2,rpa3}
    
    log_success "Directories created successfully"
}

# Set proper permissions
set_permissions() {
    log_info "Setting proper permissions..."
    
    # Set permissions for data directories
    chmod -R 755 data/
    chmod -R 755 logs/
    chmod -R 755 tmp/
    
    # Set permissions for PostgreSQL data directories
    chmod 700 data/postgres
    
    # Set permissions for scripts
    chmod +x scripts/*.sh
    
    log_success "Permissions set successfully"
}

# Create environment file if it doesn't exist
setup_environment() {
    log_info "Setting up environment configuration..."
    
    if [ ! -f .env ]; then
        log_info "Creating .env file from .env.docker template..."
        cp .env.docker .env
        log_success "Environment file created. Please review and modify as needed."
    else
        log_warning ".env file already exists. Skipping creation."
    fi
}

# Initialize database directories
init_database_dirs() {
    log_info "Initializing database directories..."
    
    # Create PostgreSQL initialization scripts directory if it doesn't exist
    mkdir -p core/migrations/rpa_db
    
    # Create a simple initialization script for Prefect database
    cat > data/postgres/init-prefect-db.sql << 'EOF'
-- Initialize Prefect database
CREATE DATABASE prefect_db;
CREATE USER prefect_user WITH PASSWORD 'prefect_dev_password_secure_789';
GRANT ALL PRIVILEGES ON DATABASE prefect_db TO prefect_user;
EOF
    
    log_success "Database directories initialized"
}

# Validate Docker Compose configuration
validate_compose() {
    log_info "Validating Docker Compose configuration..."
    
    if docker-compose config > /dev/null 2>&1; then
        log_success "Docker Compose configuration is valid"
    else
        log_error "Docker Compose configuration is invalid. Please check your docker-compose.yml file."
        exit 1
    fi
}

# Build base image
build_base_image() {
    log_info "Building base container image..."
    
    if docker build -f Dockerfile.base -t rpa-base:latest .; then
        log_success "Base image built successfully"
    else
        log_error "Failed to build base image"
        exit 1
    fi
}

# Create network if it doesn't exist
create_network() {
    log_info "Creating Docker network..."
    
    if ! docker network ls | grep -q rpa-network; then
        docker network create rpa-network --driver bridge --subnet 172.20.0.0/16
        log_success "Docker network created"
    else
        log_warning "Docker network already exists"
    fi
}

# Main setup function
main() {
    log_info "Starting Docker environment setup..."
    
    check_dependencies
    create_directories
    set_permissions
    setup_environment
    init_database_dirs
    validate_compose
    create_network
    build_base_image
    
    log_success "Docker environment setup completed successfully!"
    
    echo ""
    log_info "Next steps:"
    echo "1. Review and modify .env file if needed"
    echo "2. Start the services: docker-compose up -d"
    echo "3. Check service health: docker-compose ps"
    echo "4. View logs: docker-compose logs -f [service-name]"
    echo ""
    log_info "Available profiles:"
    echo "- Default: Basic services (postgres, prefect-server, flow workers)"
    echo "- load-testing: Includes additional RPA1 worker"
    echo "- monitoring: Includes Prometheus monitoring"
    echo "- debug: Development mode with debugging enabled"
    echo "- testing: Includes test runner service"
    echo ""
    log_info "Example commands:"
    echo "- Start with monitoring: docker-compose --profile monitoring up -d"
    echo "- Start with load testing: docker-compose --profile load-testing up -d"
    echo "- Start in debug mode: docker-compose --profile debug up -d"
}

# Run main function
main "$@"