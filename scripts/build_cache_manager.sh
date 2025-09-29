#!/bin/bash
# Build cache optimization and layer management script
# Manages Docker build cache for optimal build performance

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CACHE_DIR="${PROJECT_ROOT}/.build_cache"
DOCKER_CACHE_DIR="${CACHE_DIR}/docker"

# Default values
CACHE_SIZE_LIMIT_GB="${CACHE_SIZE_LIMIT_GB:-10}"
CACHE_RETENTION_DAYS="${CACHE_RETENTION_DAYS:-7}"
ENABLE_BUILDKIT="${ENABLE_BUILDKIT:-true}"
CACHE_MODE="${CACHE_MODE:-max}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CACHE-MGR] $*" >&2
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Function to setup BuildKit
setup_buildkit() {
    if [[ "$ENABLE_BUILDKIT" == "true" ]]; then
        export DOCKER_BUILDKIT=1
        export BUILDKIT_PROGRESS=plain
        log_info "BuildKit enabled for optimized builds"
    else
        log_info "Using legacy Docker build"
    fi
}

# Function to create cache directories
setup_cache_directories() {
    mkdir -p "$CACHE_DIR" "$DOCKER_CACHE_DIR"
    log_info "Cache directories initialized"
}

# Function to get cache size in bytes
get_cache_size() {
    if [[ -d "$DOCKER_CACHE_DIR" ]]; then
        du -sb "$DOCKER_CACHE_DIR" 2>/dev/null | cut -f1 || echo "0"
    else
        echo "0"
    fi
}

# Function to get Docker system cache usage
get_docker_cache_usage() {
    docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}\t{{.Reclaimable}}" 2>/dev/null || {
        log_warning "Unable to get Docker cache usage"
        return 1
    }
}

# Function to clean up old cache layers
cleanup_old_cache() {
    local retention_days="$1"
    
    log_info "Cleaning up cache older than $retention_days days..."
    
    # Clean up Docker build cache
    if command -v docker >/dev/null 2>&1; then
        # Remove unused build cache
        local pruned_size
        pruned_size=$(docker builder prune --filter "until=${retention_days}h" --force 2>/dev/null | grep "Total:" | awk '{print $2}' || echo "0B")
        log_info "Pruned Docker build cache: $pruned_size"
        
        # Remove dangling images
        local dangling_images
        dangling_images=$(docker images -f "dangling=true" -q)
        if [[ -n "$dangling_images" ]]; then
            docker rmi $dangling_images >/dev/null 2>&1 || true
            log_info "Removed dangling images"
        fi
    fi
    
    # Clean up local cache directory
    if [[ -d "$DOCKER_CACHE_DIR" ]]; then
        find "$DOCKER_CACHE_DIR" -type f -mtime +$retention_days -delete 2>/dev/null || true
        log_info "Cleaned up local cache files older than $retention_days days"
    fi
}

# Function to optimize cache size
optimize_cache_size() {
    local size_limit_bytes=$((CACHE_SIZE_LIMIT_GB * 1024 * 1024 * 1024))
    local current_size
    current_size=$(get_cache_size)
    
    log_info "Current cache size: $(numfmt --to=iec $current_size)"
    log_info "Cache size limit: $(numfmt --to=iec $size_limit_bytes)"
    
    if [[ $current_size -gt $size_limit_bytes ]]; then
        log_warning "Cache size exceeds limit, cleaning up..."
        
        # Aggressive cleanup
        docker builder prune --all --force >/dev/null 2>&1 || true
        docker system prune --force >/dev/null 2>&1 || true
        
        # Clean local cache
        if [[ -d "$DOCKER_CACHE_DIR" ]]; then
            find "$DOCKER_CACHE_DIR" -type f -delete 2>/dev/null || true
        fi
        
        local new_size
        new_size=$(get_cache_size)
        log_success "Cache optimized: $(numfmt --to=iec $new_size)"
    else
        log_success "Cache size within limits"
    fi
}

# Function to create optimized build configuration
create_build_config() {
    local config_file="${CACHE_DIR}/buildkit.toml"
    
    cat > "$config_file" << EOF
# BuildKit configuration for optimized builds
debug = false

[worker.oci]
  enabled = true
  platforms = [ "linux/amd64" ]

[worker.containerd]
  enabled = false

[registry."docker.io"]
  mirrors = ["mirror.gcr.io"]

# Cache configuration
[cache]
  # Enable inline cache
  inline = true
  
  # Cache mount configuration
  [cache.mount]
    enabled = true
    
  # Registry cache configuration  
  [cache.registry]
    enabled = false

# Build optimization
[build]
  # Enable parallel builds
  max-parallelism = 4
  
  # Cache optimization
  cache-from = ["type=local,src=${DOCKER_CACHE_DIR}"]
  cache-to = ["type=local,dest=${DOCKER_CACHE_DIR},mode=${CACHE_MODE}"]

EOF

    log_info "BuildKit configuration created: $config_file"
    echo "$config_file"
}

# Function to generate optimized build arguments
generate_build_args() {
    local image_type="$1"  # base or flow
    local build_args=()
    
    # Common optimization arguments
    build_args+=(
        "--build-arg" "BUILDKIT_INLINE_CACHE=1"
        "--cache-from" "type=local,src=${DOCKER_CACHE_DIR}"
        "--cache-to" "type=local,dest=${DOCKER_CACHE_DIR},mode=${CACHE_MODE}"
    )
    
    # Image-specific optimizations
    case "$image_type" in
        "base")
            build_args+=(
                "--target" "base"
                "--build-arg" "PIP_NO_CACHE_DIR=1"
                "--build-arg" "PYTHONDONTWRITEBYTECODE=1"
            )
            ;;
        "flow")
            build_args+=(
                "--build-arg" "BASE_IMAGE_CACHE=1"
            )
            ;;
    esac
    
    echo "${build_args[@]}"
}

# Function to analyze build performance
analyze_build_performance() {
    local build_log="$1"
    
    if [[ ! -f "$build_log" ]]; then
        log_warning "Build log not found: $build_log"
        return 1
    fi
    
    log_info "Analyzing build performance..."
    
    # Extract timing information
    local total_time
    total_time=$(grep -o "finished.*in [0-9.]*s" "$build_log" | tail -1 | grep -o "[0-9.]*s" || echo "unknown")
    
    # Count cache hits/misses
    local cache_hits
    local cache_misses
    cache_hits=$(grep -c "CACHED" "$build_log" 2>/dev/null || echo "0")
    cache_misses=$(grep -c "RUN\|COPY\|ADD" "$build_log" 2>/dev/null || echo "0")
    cache_misses=$((cache_misses - cache_hits))
    
    # Calculate cache efficiency
    local total_steps=$((cache_hits + cache_misses))
    local cache_efficiency=0
    if [[ $total_steps -gt 0 ]]; then
        cache_efficiency=$((cache_hits * 100 / total_steps))
    fi
    
    log_info "Build Performance Analysis:"
    log_info "  Total time: $total_time"
    log_info "  Cache hits: $cache_hits"
    log_info "  Cache misses: $cache_misses"
    log_info "  Cache efficiency: ${cache_efficiency}%"
    
    # Recommendations
    if [[ $cache_efficiency -lt 50 ]]; then
        log_warning "Low cache efficiency detected. Consider:"
        log_warning "  - Reordering Dockerfile instructions"
        log_warning "  - Using .dockerignore to reduce context"
        log_warning "  - Splitting large RUN commands"
    fi
}

# Function to create cache warming script
create_cache_warming_script() {
    local warming_script="${SCRIPT_DIR}/warm_build_cache.sh"
    
    cat > "$warming_script" << 'EOF'
#!/bin/bash
# Cache warming script to pre-populate build cache

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [CACHE-WARM] $*" >&2
}

# Warm up base image cache
warm_base_cache() {
    log "Warming base image cache..."
    
    # Pull base Python image
    docker pull python:3.11-slim >/dev/null 2>&1 || true
    
    # Pre-build common layers
    docker build --target base --cache-from type=registry,ref=python:3.11-slim \
        -f Dockerfile.base . >/dev/null 2>&1 || true
    
    log "Base cache warmed"
}

# Warm up dependency cache
warm_dependency_cache() {
    log "Warming dependency cache..."
    
    # Create temporary Dockerfile for dependencies only
    cat > Dockerfile.deps << 'DEPS_EOF'
FROM python:3.11-slim
RUN pip install uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
DEPS_EOF
    
    docker build -f Dockerfile.deps -t temp-deps . >/dev/null 2>&1 || true
    docker rmi temp-deps >/dev/null 2>&1 || true
    rm -f Dockerfile.deps
    
    log "Dependency cache warmed"
}

main() {
    log "Starting cache warming process..."
    
    cd "$PROJECT_ROOT"
    warm_base_cache
    warm_dependency_cache
    
    log "Cache warming completed"
}

main "$@"
EOF

    chmod +x "$warming_script"
    log_info "Cache warming script created: $warming_script"
}

# Function to display cache statistics
display_cache_stats() {
    log_info "Build Cache Statistics"
    log_info "====================="
    
    # Local cache stats
    local cache_size
    cache_size=$(get_cache_size)
    log_info "Local cache size: $(numfmt --to=iec $cache_size)"
    log_info "Cache size limit: ${CACHE_SIZE_LIMIT_GB}GB"
    
    # Docker system stats
    log_info ""
    log_info "Docker System Usage:"
    get_docker_cache_usage || log_warning "Docker stats unavailable"
    
    # Cache directory contents
    if [[ -d "$DOCKER_CACHE_DIR" ]]; then
        local file_count
        file_count=$(find "$DOCKER_CACHE_DIR" -type f | wc -l)
        log_info "Cache files: $file_count"
    fi
    
    log_info "====================="
}

# Function to export cache for CI/CD
export_cache() {
    local export_path="$1"
    
    log_info "Exporting build cache to: $export_path"
    
    # Create export directory
    mkdir -p "$(dirname "$export_path")"
    
    # Export Docker build cache
    if [[ -d "$DOCKER_CACHE_DIR" ]]; then
        tar -czf "$export_path" -C "$CACHE_DIR" docker/ 2>/dev/null || {
            log_error "Failed to export cache"
            return 1
        }
        
        local export_size
        export_size=$(stat -f%z "$export_path" 2>/dev/null || stat -c%s "$export_path" 2>/dev/null || echo "0")
        log_success "Cache exported: $(numfmt --to=iec $export_size)"
    else
        log_warning "No cache to export"
        return 1
    fi
}

# Function to import cache from CI/CD
import_cache() {
    local import_path="$1"
    
    if [[ ! -f "$import_path" ]]; then
        log_error "Cache file not found: $import_path"
        return 1
    fi
    
    log_info "Importing build cache from: $import_path"
    
    # Create cache directory
    mkdir -p "$CACHE_DIR"
    
    # Import cache
    if tar -xzf "$import_path" -C "$CACHE_DIR" 2>/dev/null; then
        log_success "Cache imported successfully"
    else
        log_error "Failed to import cache"
        return 1
    fi
}

# Main execution
main() {
    local action="optimize"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --setup)
                action="setup"
                shift
                ;;
            --cleanup)
                action="cleanup"
                shift
                ;;
            --optimize)
                action="optimize"
                shift
                ;;
            --stats)
                action="stats"
                shift
                ;;
            --warm)
                action="warm"
                shift
                ;;
            --export)
                action="export"
                export_path="$2"
                shift 2
                ;;
            --import)
                action="import"
                import_path="$2"
                shift 2
                ;;
            --analyze)
                action="analyze"
                build_log="$2"
                shift 2
                ;;
            --size-limit)
                CACHE_SIZE_LIMIT_GB="$2"
                shift 2
                ;;
            --retention-days)
                CACHE_RETENTION_DAYS="$2"
                shift 2
                ;;
            --help)
                cat << EOF
Usage: $0 [ACTION] [OPTIONS]

Build cache optimization and layer management.

Actions:
    --setup             Initialize cache system
    --cleanup           Clean up old cache entries
    --optimize          Optimize cache size and performance (default)
    --stats             Display cache statistics
    --warm              Warm up build cache
    --export PATH       Export cache to file
    --import PATH       Import cache from file
    --analyze LOG       Analyze build performance from log

Options:
    --size-limit GB     Cache size limit in GB (default: 10)
    --retention-days N  Cache retention in days (default: 7)
    --help              Show this help message

Environment Variables:
    CACHE_SIZE_LIMIT_GB     Cache size limit (default: 10)
    CACHE_RETENTION_DAYS    Cache retention days (default: 7)
    ENABLE_BUILDKIT         Enable BuildKit (default: true)
    CACHE_MODE              Cache mode: min|max (default: max)

Examples:
    $0 --setup                      # Initialize cache system
    $0 --cleanup --retention-days 3 # Clean cache older than 3 days
    $0 --export cache.tar.gz        # Export cache for CI/CD
    $0 --analyze build.log          # Analyze build performance

EOF
                exit 0
                ;;
            *)
                log_error "Unknown option: $1. Use --help for usage information."
                exit 1
                ;;
        esac
    done
    
    log_info "Starting cache management: $action"
    
    # Execute action
    case "$action" in
        "setup")
            setup_buildkit
            setup_cache_directories
            create_build_config
            create_cache_warming_script
            log_success "Cache system initialized"
            ;;
        "cleanup")
            cleanup_old_cache "$CACHE_RETENTION_DAYS"
            log_success "Cache cleanup completed"
            ;;
        "optimize")
            setup_buildkit
            setup_cache_directories
            cleanup_old_cache "$CACHE_RETENTION_DAYS"
            optimize_cache_size
            log_success "Cache optimization completed"
            ;;
        "stats")
            display_cache_stats
            ;;
        "warm")
            "$SCRIPT_DIR/warm_build_cache.sh"
            ;;
        "export")
            export_cache "$export_path"
            ;;
        "import")
            import_cache "$import_path"
            ;;
        "analyze")
            analyze_build_performance "$build_log"
            ;;
        *)
            log_error "Unknown action: $action"
            exit 1
            ;;
    esac
}

# Change to project root
cd "$PROJECT_ROOT"

# Execute main function with all arguments
main "$@"