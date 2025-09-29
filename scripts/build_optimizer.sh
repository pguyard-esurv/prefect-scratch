#!/bin/bash
# Build optimization wrapper script
# Orchestrates all build automation and optimization features

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
OPTIMIZATION_LEVEL="${OPTIMIZATION_LEVEL:-medium}"
AUTO_CLEANUP="${AUTO_CLEANUP:-true}"
BENCHMARK_MODE="${BENCHMARK_MODE:-false}"
CI_MODE="${CI_MODE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [BUILD-OPT] $*" >&2
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

log_step() {
    echo -e "${PURPLE}[STEP]${NC} $1" >&2
}

# Function to detect CI environment
detect_ci_environment() {
    if [[ -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" || -n "${GITLAB_CI:-}" || -n "${JENKINS_URL:-}" ]]; then
        CI_MODE="true"
        log_info "CI environment detected, enabling CI optimizations"
    fi
}

# Function to setup optimization based on level
setup_optimization_level() {
    local level="$1"
    
    case "$level" in
        "minimal")
            export SELECTIVE_BUILD="false"
            export ENABLE_CACHING="true"
            export SECURITY_SCAN="false"
            export PERFORMANCE_MONITOR="false"
            export PARALLEL_BUILD="false"
            log_info "Optimization level: minimal (basic caching only)"
            ;;
        "medium")
            export SELECTIVE_BUILD="true"
            export ENABLE_CACHING="true"
            export SECURITY_SCAN="false"
            export PERFORMANCE_MONITOR="true"
            export PARALLEL_BUILD="true"
            log_info "Optimization level: medium (selective builds, caching, monitoring)"
            ;;
        "maximum")
            export SELECTIVE_BUILD="true"
            export ENABLE_CACHING="true"
            export SECURITY_SCAN="true"
            export PERFORMANCE_MONITOR="true"
            export PARALLEL_BUILD="true"
            export GENERATE_REPORT="true"
            log_info "Optimization level: maximum (all features enabled)"
            ;;
        "ci")
            export SELECTIVE_BUILD="true"
            export ENABLE_CACHING="true"
            export SECURITY_SCAN="true"
            export PERFORMANCE_MONITOR="false"
            export PARALLEL_BUILD="true"
            export GENERATE_REPORT="false"
            log_info "Optimization level: CI (optimized for continuous integration)"
            ;;
        *)
            log_error "Unknown optimization level: $level"
            exit 1
            ;;
    esac
}

# Function to pre-optimize build environment
pre_optimize_environment() {
    log_step "Pre-optimizing build environment..."
    
    # Setup build cache
    if [[ "${ENABLE_CACHING:-true}" == "true" ]]; then
        "$SCRIPT_DIR/build_cache_manager.sh" --setup || {
            log_warning "Failed to setup build cache"
        }
    fi
    
    # Warm up cache if not in CI
    if [[ "$CI_MODE" != "true" && "${ENABLE_CACHING:-true}" == "true" ]]; then
        "$SCRIPT_DIR/build_cache_manager.sh" --warm || {
            log_warning "Failed to warm build cache"
        }
    fi
    
    # Setup security scanning
    if [[ "${SECURITY_SCAN:-false}" == "true" ]]; then
        "$SCRIPT_DIR/security_scanner.sh" --setup || {
            log_warning "Failed to setup security scanning"
        }
    fi
    
    log_success "Environment pre-optimization completed"
}

# Function to run optimized build
run_optimized_build() {
    local build_args=("$@")
    
    log_step "Running optimized build process..."
    
    # Add optimization flags to build command
    if [[ "${SELECTIVE_BUILD:-false}" == "true" ]]; then
        build_args+=("--selective")
    fi
    
    if [[ "${ENABLE_CACHING:-true}" != "true" ]]; then
        build_args+=("--no-cache")
    fi
    
    if [[ "${SECURITY_SCAN:-false}" == "true" ]]; then
        build_args+=("--security-scan")
    fi
    
    if [[ "${PERFORMANCE_MONITOR:-false}" == "true" ]]; then
        build_args+=("--monitor")
    fi
    
    if [[ "${GENERATE_REPORT:-false}" == "true" ]]; then
        build_args+=("--report")
    fi
    
    if [[ "${PARALLEL_BUILD:-false}" == "true" ]]; then
        build_args+=("--parallel")
    fi
    
    # Execute build with monitoring
    local build_start=$(date +%s)
    
    if [[ "${PERFORMANCE_MONITOR:-false}" == "true" ]]; then
        # Monitor the build process
        python3 "$SCRIPT_DIR/build_performance_monitor.py" \
            --action monitor \
            --image "build-process" \
            --build-command "$SCRIPT_DIR/build_all.sh" "${build_args[@]}" || {
            log_error "Monitored build failed"
            return 1
        }
    else
        # Regular build
        "$SCRIPT_DIR/build_all.sh" "${build_args[@]}" || {
            log_error "Build failed"
            return 1
        }
    fi
    
    local build_end=$(date +%s)
    local build_duration=$((build_end - build_start))
    
    log_success "Optimized build completed in ${build_duration}s"
}

# Function to post-optimize and cleanup
post_optimize_cleanup() {
    log_step "Post-build optimization and cleanup..."
    
    # Optimize cache size
    if [[ "${ENABLE_CACHING:-true}" == "true" ]]; then
        "$SCRIPT_DIR/build_cache_manager.sh" --optimize || {
            log_warning "Failed to optimize build cache"
        }
    fi
    
    # Auto cleanup if enabled
    if [[ "$AUTO_CLEANUP" == "true" ]]; then
        # Clean up old images
        docker image prune -f >/dev/null 2>&1 || true
        
        # Clean up build cache if too large
        "$SCRIPT_DIR/build_cache_manager.sh" --cleanup || {
            log_warning "Failed to cleanup build cache"
        }
    fi
    
    log_success "Post-build optimization completed"
}

# Function to run benchmark mode
run_benchmark() {
    log_step "Running build benchmark..."
    
    local benchmark_results=()
    local optimization_levels=("minimal" "medium" "maximum")
    
    for level in "${optimization_levels[@]}"; do
        log_info "Benchmarking optimization level: $level"
        
        # Setup optimization level
        setup_optimization_level "$level"
        
        # Force rebuild for fair comparison
        export FORCE_REBUILD="true"
        
        # Run build with timing
        local start_time=$(date +%s)
        
        if run_optimized_build --tag "benchmark-$level"; then
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            benchmark_results+=("$level:${duration}s")
            log_success "Level $level completed in ${duration}s"
        else
            benchmark_results+=("$level:FAILED")
            log_error "Level $level failed"
        fi
        
        # Cleanup between runs
        docker image prune -f >/dev/null 2>&1 || true
    done
    
    # Display benchmark results
    log_info "Benchmark Results:"
    log_info "=================="
    for result in "${benchmark_results[@]}"; do
        local level duration
        level=$(echo "$result" | cut -d':' -f1)
        duration=$(echo "$result" | cut -d':' -f2)
        log_info "  $level: $duration"
    done
    log_info "=================="
}

# Function to display optimization recommendations
display_recommendations() {
    log_step "Analyzing build performance and generating recommendations..."
    
    # Run Dockerfile analysis
    for dockerfile in Dockerfile.base Dockerfile.flow1 Dockerfile.flow2 Dockerfile.flow3; do
        if [[ -f "$PROJECT_ROOT/$dockerfile" ]]; then
            log_info "Analyzing $dockerfile:"
            python3 "$SCRIPT_DIR/build_performance_monitor.py" \
                --action optimize \
                --dockerfile "$PROJECT_ROOT/$dockerfile" | sed 's/^/  /'
        fi
    done
    
    # Run performance analysis
    log_info "Build Performance Analysis:"
    python3 "$SCRIPT_DIR/build_performance_monitor.py" \
        --action analyze \
        --days 7 | sed 's/^/  /'
}

# Main execution
main() {
    local action="build"
    local build_args=()
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --level)
                OPTIMIZATION_LEVEL="$2"
                shift 2
                ;;
            --benchmark)
                action="benchmark"
                shift
                ;;
            --analyze)
                action="analyze"
                shift
                ;;
            --no-cleanup)
                AUTO_CLEANUP="false"
                shift
                ;;
            --ci)
                CI_MODE="true"
                OPTIMIZATION_LEVEL="ci"
                shift
                ;;
            --help)
                cat << EOF
Usage: $0 [OPTIONS] [BUILD_OPTIONS]

Build optimization wrapper with automated performance tuning.

Optimization Options:
    --level LEVEL       Optimization level: minimal|medium|maximum|ci (default: medium)
    --benchmark         Run benchmark comparing all optimization levels
    --analyze           Analyze build performance and show recommendations
    --no-cleanup        Disable automatic cleanup after build
    --ci                Enable CI mode optimizations

Build Options:
    All options from build_all.sh are supported and passed through.

Optimization Levels:
    minimal    - Basic caching only
    medium     - Selective builds, caching, monitoring, parallel builds
    maximum    - All features: selective builds, caching, security, monitoring, reports
    ci         - Optimized for CI: selective builds, caching, security, parallel builds

Environment Variables:
    OPTIMIZATION_LEVEL  Optimization level (default: medium)
    AUTO_CLEANUP        Enable auto cleanup (default: true)
    BENCHMARK_MODE      Enable benchmark mode (default: false)
    CI_MODE             Enable CI mode (default: auto-detect)

Examples:
    $0                                    # Build with medium optimization
    $0 --level maximum --tag v1.0.0      # Maximum optimization with specific tag
    $0 --benchmark                       # Benchmark all optimization levels
    $0 --analyze                         # Analyze performance and show recommendations
    $0 --ci --tag latest                 # CI-optimized build

EOF
                exit 0
                ;;
            *)
                # Pass unknown arguments to build script
                build_args+=("$1")
                shift
                ;;
        esac
    done
    
    log_info "Starting build optimization process: $action"
    
    # Detect CI environment
    detect_ci_environment
    
    # Execute action
    case "$action" in
        "build")
            setup_optimization_level "$OPTIMIZATION_LEVEL"
            pre_optimize_environment
            run_optimized_build "${build_args[@]}"
            post_optimize_cleanup
            log_success "Optimized build process completed successfully"
            ;;
        "benchmark")
            BENCHMARK_MODE="true"
            run_benchmark
            ;;
        "analyze")
            display_recommendations
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