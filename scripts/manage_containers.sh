#!/bin/bash

# Container Management Script
# Provides convenient commands for managing the container testing environment

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

# Show usage information
show_usage() {
    echo "Container Management Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start [profile]     Start services (optionally with profile)"
    echo "  stop               Stop all services"
    echo "  restart [service]  Restart all services or specific service"
    echo "  status             Show service status"
    echo "  logs [service]     Show logs for all services or specific service"
    echo "  health             Check health of all services"
    echo "  build              Build all container images"
    echo "  rebuild [service]  Rebuild specific service or all services"
    echo "  clean              Clean up containers, networks, and volumes"
    echo "  reset              Reset entire environment (clean + rebuild)"
    echo "  shell <service>    Open shell in running container"
    echo "  exec <service> <command>  Execute command in running container"
    echo "  test               Run container tests"
    echo "  monitor            Start monitoring stack"
    echo "  debug <service>    Start service in debug mode"
    echo ""
    echo "Profiles:"
    echo "  default            Basic services (postgres, prefect-server, workers)"
    echo "  load-testing       Includes additional RPA1 worker"
    echo "  monitoring         Includes Prometheus monitoring"
    echo "  debug              Development mode with debugging"
    echo "  testing            Includes test runner service"
    echo ""
    echo "Examples:"
    echo "  $0 start                    # Start default services"
    echo "  $0 start monitoring         # Start with monitoring"
    echo "  $0 logs rpa1-worker         # Show RPA1 worker logs"
    echo "  $0 shell rpa1-worker        # Open shell in RPA1 worker"
    echo "  $0 health                   # Check all service health"
}

# Start services
start_services() {
    local profile=${1:-""}
    
    log_info "Starting container services..."
    
    if [ -n "$profile" ]; then
        log_info "Using profile: $profile"
        docker-compose --profile "$profile" up -d
    else
        docker-compose up -d
    fi
    
    log_success "Services started successfully"
    show_service_status
}

# Stop services
stop_services() {
    log_info "Stopping container services..."
    docker-compose down
    log_success "Services stopped successfully"
}

# Restart services
restart_services() {
    local service=${1:-""}
    
    if [ -n "$service" ]; then
        log_info "Restarting service: $service"
        docker-compose restart "$service"
    else
        log_info "Restarting all services..."
        docker-compose restart
    fi
    
    log_success "Services restarted successfully"
}

# Show service status
show_service_status() {
    log_info "Service status:"
    docker-compose ps
}

# Show logs
show_logs() {
    local service=${1:-""}
    
    if [ -n "$service" ]; then
        log_info "Showing logs for service: $service"
        docker-compose logs -f "$service"
    else
        log_info "Showing logs for all services:"
        docker-compose logs -f
    fi
}

# Check health of services
check_health() {
    log_info "Checking service health..."
    
    # Check if services are running
    if ! docker-compose ps | grep -q "Up"; then
        log_error "No services are running. Start services first with: $0 start"
        return 1
    fi
    
    # Check individual service health
    services=("postgres" "prefect-server" "rpa1-worker" "rpa2-worker" "rpa3-worker")
    
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up (healthy)"; then
            log_success "$service: Healthy"
        elif docker-compose ps "$service" | grep -q "Up"; then
            log_warning "$service: Running (health check pending)"
        else
            log_error "$service: Not running or unhealthy"
        fi
    done
    
    # Show detailed health information
    echo ""
    log_info "Detailed health information:"
    docker-compose exec rpa1-worker python /app/scripts/health_check.py --flow=rpa1 2>/dev/null || log_warning "RPA1 health check failed"
    docker-compose exec rpa2-worker python /app/scripts/health_check.py --flow=rpa2 2>/dev/null || log_warning "RPA2 health check failed"
    docker-compose exec rpa3-worker python /app/scripts/health_check.py --flow=rpa3 2>/dev/null || log_warning "RPA3 health check failed"
}

# Build container images
build_images() {
    log_info "Building container images..."
    
    # Build base image first
    log_info "Building base image..."
    docker build -f Dockerfile.base -t rpa-base:latest .
    
    # Build flow images
    log_info "Building flow images..."
    docker-compose build
    
    log_success "All images built successfully"
}

# Rebuild services
rebuild_services() {
    local service=${1:-""}
    
    if [ -n "$service" ]; then
        log_info "Rebuilding service: $service"
        docker-compose build --no-cache "$service"
        docker-compose up -d "$service"
    else
        log_info "Rebuilding all services..."
        build_images
        docker-compose up -d --force-recreate
    fi
    
    log_success "Services rebuilt successfully"
}

# Clean up environment
clean_environment() {
    log_warning "This will remove all containers, networks, and volumes. Continue? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "Cleaning up environment..."
        
        # Stop and remove containers
        docker-compose down -v --remove-orphans
        
        # Remove images
        docker images | grep rpa- | awk '{print $3}' | xargs -r docker rmi -f
        
        # Remove network
        docker network rm rpa-network 2>/dev/null || true
        
        # Clean up volumes
        docker volume prune -f
        
        log_success "Environment cleaned up successfully"
    else
        log_info "Clean up cancelled"
    fi
}

# Reset entire environment
reset_environment() {
    log_warning "This will completely reset the environment. Continue? (y/N)"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        clean_environment
        log_info "Rebuilding environment..."
        ./scripts/setup_docker_environment.sh
        build_images
        log_success "Environment reset successfully"
    else
        log_info "Reset cancelled"
    fi
}

# Open shell in container
open_shell() {
    local service=${1:-""}
    
    if [ -z "$service" ]; then
        log_error "Service name required. Usage: $0 shell <service>"
        return 1
    fi
    
    log_info "Opening shell in $service..."
    docker-compose exec "$service" /bin/bash
}

# Execute command in container
exec_command() {
    local service=${1:-""}
    shift
    local command="$*"
    
    if [ -z "$service" ] || [ -z "$command" ]; then
        log_error "Service and command required. Usage: $0 exec <service> <command>"
        return 1
    fi
    
    log_info "Executing '$command' in $service..."
    docker-compose exec "$service" $command
}

# Run tests
run_tests() {
    log_info "Running container tests..."
    
    # Start test environment
    docker-compose --profile testing up -d test-runner
    
    # Wait for services to be ready
    sleep 10
    
    # Run tests
    docker-compose exec test-runner python -m pytest -v --cov=core --cov-report=html --cov-report=term
    
    log_success "Tests completed"
}

# Start monitoring
start_monitoring() {
    log_info "Starting monitoring stack..."
    docker-compose --profile monitoring up -d
    
    log_success "Monitoring started"
    log_info "Prometheus available at: http://localhost:9090"
}

# Start service in debug mode
debug_service() {
    local service=${1:-""}
    
    if [ -z "$service" ]; then
        log_error "Service name required. Usage: $0 debug <service>"
        return 1
    fi
    
    log_info "Starting $service in debug mode..."
    docker-compose --profile debug up -d "$service"
    
    local debug_port
    case "$service" in
        "rpa1-worker") debug_port="5678" ;;
        "rpa2-worker") debug_port="5679" ;;
        "rpa3-worker") debug_port="5680" ;;
        *) debug_port="5678" ;;
    esac
    
    log_success "$service started in debug mode"
    log_info "Debug port: $debug_port"
    log_info "Connect your debugger to localhost:$debug_port"
}

# Main function
main() {
    local command=${1:-""}
    
    if [ -z "$command" ]; then
        show_usage
        exit 1
    fi
    
    case "$command" in
        "start")
            start_services "${2:-}"
            ;;
        "stop")
            stop_services
            ;;
        "restart")
            restart_services "${2:-}"
            ;;
        "status")
            show_service_status
            ;;
        "logs")
            show_logs "${2:-}"
            ;;
        "health")
            check_health
            ;;
        "build")
            build_images
            ;;
        "rebuild")
            rebuild_services "${2:-}"
            ;;
        "clean")
            clean_environment
            ;;
        "reset")
            reset_environment
            ;;
        "shell")
            open_shell "${2:-}"
            ;;
        "exec")
            shift
            exec_command "$@"
            ;;
        "test")
            run_tests
            ;;
        "monitor")
            start_monitoring
            ;;
        "debug")
            debug_service "${2:-}"
            ;;
        "help"|"-h"|"--help")
            show_usage
            ;;
        *)
            log_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"