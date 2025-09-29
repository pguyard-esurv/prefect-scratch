#!/bin/bash
# Comprehensive build script for all container images
# Builds base image and all flow images with proper dependency management
# Includes build automation, caching optimization, and security scanning

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
BUILD_BASE="${BUILD_BASE:-true}"
BUILD_FLOWS="${BUILD_FLOWS:-true}"
FORCE_REBUILD="${FORCE_REBUILD:-false}"
PARALLEL_BUILD="${PARALLEL_BUILD:-false}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# New automation features
SELECTIVE_BUILD="${SELECTIVE_BUILD:-false}"
ENABLE_CACHING="${ENABLE_CACHING:-true}"
SECURITY_SCAN="${SECURITY_SCAN:-false}"
PERFORMANCE_MONITOR="${PERFORMANCE_MONITOR:-false}"
GENERATE_REPORT="${GENERATE_REPORT:-false}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [BUILD-ALL] $*" >&2
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Function to check Docker availability
check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        error_exit "Docker is not installed or not in PATH"
    fi
    
    if ! docker info >/dev/null 2>&1; then
        error_exit "Docker daemon is not running or not accessible"
    fi
    
    log "Docker is available and running"
}

# Function to clean up old images if force rebuild is enabled
cleanup_images() {
    if [[ "$FORCE_REBUILD" == "true" ]]; then
        log "Force rebuild enabled, cleaning up existing images..."
        
        # Remove flow images
        for flow in rpa1 rpa2 rpa3; do
            local image_name="rpa-flow-${flow}:${IMAGE_TAG}"
            if docker image inspect "$image_name" >/dev/null 2>&1; then
                log "Removing existing image: $image_name"
                docker rmi "$image_name" || log "Warning: Failed to remove $image_name"
            fi
        done
        
        # Remove base image
        local base_image="rpa-base:${IMAGE_TAG}"
        if docker image inspect "$base_image" >/dev/null 2>&1; then
            log "Removing existing base image: $base_image"
            docker rmi "$base_image" || log "Warning: Failed to remove $base_image"
        fi
    fi
}

# Function to build base image
build_base_image() {
    if [[ "$BUILD_BASE" != "true" ]]; then
        log "Skipping base image build (BUILD_BASE=false)"
        return 0
    fi
    
    log "Building base image..."
    
    if [[ -f "$SCRIPT_DIR/build_base_image.sh" ]]; then
        if BASE_IMAGE_TAG="$IMAGE_TAG" "$SCRIPT_DIR/build_base_image.sh"; then
            log "Base image built successfully"
        else
            error_exit "Failed to build base image"
        fi
    else
        error_exit "Base image build script not found: $SCRIPT_DIR/build_base_image.sh"
    fi
}

# Function to build flow images sequentially
build_flows_sequential() {
    log "Building flow images sequentially..."
    
    local flows=("rpa1" "rpa2" "rpa3")
    
    for flow in "${flows[@]}"; do
        log "Building flow: $flow"
        
        if BASE_IMAGE_TAG="$IMAGE_TAG" FLOW_IMAGE_TAG="$IMAGE_TAG" \
           "$SCRIPT_DIR/build_flow_images.sh" --flow "$flow"; then
            log "Flow $flow built successfully"
        else
            error_exit "Failed to build flow: $flow"
        fi
    done
}

# Function to build flow images in parallel
build_flows_parallel() {
    log "Building flow images in parallel..."
    
    local flows=("rpa1" "rpa2" "rpa3")
    local pids=()
    local failed_flows=()
    
    # Start builds in background
    for flow in "${flows[@]}"; do
        log "Starting parallel build for flow: $flow"
        
        (
            if BASE_IMAGE_TAG="$IMAGE_TAG" FLOW_IMAGE_TAG="$IMAGE_TAG" \
               "$SCRIPT_DIR/build_flow_images.sh" --flow "$flow" >/dev/null 2>&1; then
                echo "SUCCESS:$flow"
            else
                echo "FAILED:$flow"
            fi
        ) &
        
        pids+=($!)
    done
    
    # Wait for all builds to complete
    for i in "${!pids[@]}"; do
        local pid=${pids[$i]}
        local flow=${flows[$i]}
        
        if wait "$pid"; then
            local result
            result=$(jobs -p | grep -q "$pid" && echo "RUNNING" || echo "COMPLETED")
            log "Flow $flow build process completed"
        else
            failed_flows+=("$flow")
            log "Flow $flow build process failed"
        fi
    done
    
    # Check results
    if [[ ${#failed_flows[@]} -gt 0 ]]; then
        error_exit "Failed to build flows: ${failed_flows[*]}"
    fi
    
    log "All flow images built successfully in parallel"
}

# Function to build flow images
build_flow_images() {
    if [[ "$BUILD_FLOWS" != "true" ]]; then
        log "Skipping flow image builds (BUILD_FLOWS=false)"
        return 0
    fi
    
    if [[ "$PARALLEL_BUILD" == "true" ]]; then
        build_flows_parallel
    else
        build_flows_sequential
    fi
}

# Function to verify built images
verify_images() {
    log "Verifying built images..."
    
    local images_to_check=()
    local missing_images=()
    
    # Check base image
    if [[ "$BUILD_BASE" == "true" ]]; then
        images_to_check+=("rpa-base:$IMAGE_TAG")
    fi
    
    # Check flow images
    if [[ "$BUILD_FLOWS" == "true" ]]; then
        images_to_check+=("rpa-flow-rpa1:$IMAGE_TAG")
        images_to_check+=("rpa-flow-rpa2:$IMAGE_TAG")
        images_to_check+=("rpa-flow-rpa3:$IMAGE_TAG")
    fi
    
    for image in "${images_to_check[@]}"; do
        if docker image inspect "$image" >/dev/null 2>&1; then
            local size
            size=$(docker image inspect "$image" --format='{{.Size}}' | numfmt --to=iec)
            log "✓ Image verified: $image ($size)"
        else
            missing_images+=("$image")
        fi
    done
    
    if [[ ${#missing_images[@]} -gt 0 ]]; then
        error_exit "Missing images after build: ${missing_images[*]}"
    fi
    
    log "All images verified successfully"
}

# Function to display build summary
display_summary() {
    log "Build Summary"
    log "============="
    
    # Build configuration
    log "Configuration:"
    log "  - Image Tag: $IMAGE_TAG"
    log "  - Build Base: $BUILD_BASE"
    log "  - Build Flows: $BUILD_FLOWS"
    log "  - Force Rebuild: $FORCE_REBUILD"
    log "  - Parallel Build: $PARALLEL_BUILD"
    
    # Image information
    log ""
    log "Built Images:"
    
    if [[ "$BUILD_BASE" == "true" ]]; then
        local base_image="rpa-base:$IMAGE_TAG"
        if docker image inspect "$base_image" >/dev/null 2>&1; then
            local size created
            size=$(docker image inspect "$base_image" --format='{{.Size}}' | numfmt --to=iec)
            created=$(docker image inspect "$base_image" --format='{{.Created}}' | cut -d'T' -f1)
            log "  - $base_image ($size, created: $created)"
        fi
    fi
    
    if [[ "$BUILD_FLOWS" == "true" ]]; then
        for flow in rpa1 rpa2 rpa3; do
            local flow_image="rpa-flow-${flow}:$IMAGE_TAG"
            if docker image inspect "$flow_image" >/dev/null 2>&1; then
                local size created
                size=$(docker image inspect "$flow_image" --format='{{.Size}}' | numfmt --to=iec)
                created=$(docker image inspect "$flow_image" --format='{{.Created}}' | cut -d'T' -f1)
                log "  - $flow_image ($size, created: $created)"
            fi
        done
    fi
    
    log "============="
}

# Function to setup build optimization
setup_build_optimization() {
    if [[ "$ENABLE_CACHING" == "true" ]]; then
        log "Setting up build cache optimization..."
        "$SCRIPT_DIR/build_cache_manager.sh" --setup >/dev/null 2>&1 || {
            log "Warning: Failed to setup build cache optimization"
        }
    fi
}

# Function to run selective build if enabled
run_selective_build() {
    if [[ "$SELECTIVE_BUILD" == "true" ]]; then
        log "Running selective build based on change detection..."
        
        local selective_args=("--tag" "$IMAGE_TAG")
        
        if [[ "$FORCE_REBUILD" == "true" ]]; then
            selective_args+=("--force")
        fi
        
        if "$SCRIPT_DIR/selective_rebuild.sh" "${selective_args[@]}"; then
            log "Selective build completed successfully"
            return 0
        else
            log "Selective build failed, falling back to full build"
            return 1
        fi
    fi
    
    return 1  # Not using selective build
}

# Function to run security scanning
run_security_scan() {
    if [[ "$SECURITY_SCAN" == "true" ]]; then
        log "Running security scans on built images..."
        
        if "$SCRIPT_DIR/security_scanner.sh" --all --tag "$IMAGE_TAG" --no-report; then
            log "Security scans passed"
        else
            log "Warning: Security scans failed or found issues"
        fi
    fi
}

# Function to run performance monitoring
run_performance_monitoring() {
    if [[ "$PERFORMANCE_MONITOR" == "true" ]]; then
        log "Analyzing build performance..."
        
        python3 "$SCRIPT_DIR/build_performance_monitor.py" --action analyze --days 7 || {
            log "Warning: Performance analysis failed"
        }
    fi
}

# Function to generate build report
generate_build_report() {
    if [[ "$GENERATE_REPORT" == "true" ]]; then
        log "Generating build report..."
        
        local report_file="${PROJECT_ROOT}/.build_cache/build_report_$(date +%Y%m%d_%H%M%S).md"
        
        python3 "$SCRIPT_DIR/build_performance_monitor.py" --action report --output "$report_file" || {
            log "Warning: Failed to generate build report"
        }
    fi
}

# Main execution
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-base)
                BUILD_BASE="false"
                shift
                ;;
            --no-flows)
                BUILD_FLOWS="false"
                shift
                ;;
            --force)
                FORCE_REBUILD="true"
                shift
                ;;
            --parallel)
                PARALLEL_BUILD="true"
                shift
                ;;
            --selective)
                SELECTIVE_BUILD="true"
                shift
                ;;
            --no-cache)
                ENABLE_CACHING="false"
                shift
                ;;
            --security-scan)
                SECURITY_SCAN="true"
                shift
                ;;
            --monitor)
                PERFORMANCE_MONITOR="true"
                shift
                ;;
            --report)
                GENERATE_REPORT="true"
                shift
                ;;
            --tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            --help)
                cat << EOF
Usage: $0 [OPTIONS]

Build all container images (base + flows) with automation and optimization features.

Build Options:
    --no-base       Skip building base image
    --no-flows      Skip building flow images
    --force         Force rebuild (remove existing images first)
    --parallel      Build flow images in parallel
    --tag TAG       Tag for all images (default: latest)

Automation Options:
    --selective     Use selective rebuild based on change detection
    --no-cache      Disable build cache optimization
    --security-scan Run security scans on built images
    --monitor       Enable build performance monitoring
    --report        Generate comprehensive build report

    --help          Show this help message

Environment Variables:
    BUILD_BASE          Build base image (default: true)
    BUILD_FLOWS         Build flow images (default: true)
    FORCE_REBUILD       Force rebuild existing images (default: false)
    PARALLEL_BUILD      Build flows in parallel (default: false)
    IMAGE_TAG           Tag for images (default: latest)
    SELECTIVE_BUILD     Use selective rebuild (default: false)
    ENABLE_CACHING      Enable build caching (default: true)
    SECURITY_SCAN       Run security scans (default: false)
    PERFORMANCE_MONITOR Enable performance monitoring (default: false)
    GENERATE_REPORT     Generate build report (default: false)

Examples:
    $0                                    # Build all images with defaults
    $0 --force --parallel --security-scan # Force rebuild with security scanning
    $0 --selective --monitor --report     # Selective build with monitoring
    $0 --no-base --tag v1.0.0             # Build only flows with specific tag

EOF
                exit 0
                ;;
            *)
                error_exit "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done
    
    local build_start_time
    build_start_time=$(date +%s)
    
    log "Starting comprehensive build process with automation features..."
    log "Configuration: base=$BUILD_BASE, flows=$BUILD_FLOWS, force=$FORCE_REBUILD, parallel=$PARALLEL_BUILD, tag=$IMAGE_TAG"
    log "Automation: selective=$SELECTIVE_BUILD, caching=$ENABLE_CACHING, security=$SECURITY_SCAN, monitor=$PERFORMANCE_MONITOR"
    
    # Pre-build setup
    check_docker
    setup_build_optimization
    
    # Try selective build first if enabled
    if ! run_selective_build; then
        # Fall back to traditional build process
        cleanup_images
        build_base_image
        build_flow_images
    fi
    
    # Post-build verification
    verify_images
    
    # Post-build automation
    run_security_scan
    run_performance_monitoring
    generate_build_report
    
    local build_end_time
    build_end_time=$(date +%s)
    local build_duration=$((build_end_time - build_start_time))
    
    log "Build process completed successfully in ${build_duration}s"
    
    # Display summary
    display_summary
}

# Change to project root
cd "$PROJECT_ROOT"

# Execute main function with all arguments
main "$@"