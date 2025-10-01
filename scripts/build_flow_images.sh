#!/bin/bash
# Build script for flow-specific container images
# Builds flow images with dependency on base image

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BASE_IMAGE_NAME="rpa-base"
BASE_IMAGE_TAG="${BASE_IMAGE_TAG:-latest}"
FLOW_IMAGE_PREFIX="${FLOW_IMAGE_PREFIX:-rpa-flow}"
BUILD_ARGS="${BUILD_ARGS:-}"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Function to check if base image exists
check_base_image() {
    if ! docker image inspect "${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG}" >/dev/null 2>&1; then
        log "Base image ${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG} not found"
        log "Building base image first..."
        
        if [[ -f "$PROJECT_ROOT/scripts/build_base_image.sh" ]]; then
            "$PROJECT_ROOT/scripts/build_base_image.sh"
        else
            error_exit "Base image build script not found and base image doesn't exist"
        fi
    else
        log "Base image ${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG} found"
    fi
}

# Function to build a single flow image
build_flow_image() {
    local flow_name="$1"
    local dockerfile="flows/${flow_name}/Dockerfile"
    local image_name="${FLOW_IMAGE_PREFIX}-${flow_name}"
    local image_tag="${FLOW_IMAGE_TAG:-latest}"
    
    log "Building flow image: ${image_name}:${image_tag}"
    
    # Check if Dockerfile exists
    if [[ ! -f "$PROJECT_ROOT/$dockerfile" ]]; then
        error_exit "Dockerfile not found: $dockerfile"
    fi
    
    # Check if flow directory exists
    if [[ ! -d "$PROJECT_ROOT/flows/$flow_name" ]]; then
        error_exit "Flow directory not found: flows/$flow_name"
    fi
    
    # Build the image
    local build_cmd=(
        docker build
        -f "$dockerfile"
        -t "${image_name}:${image_tag}"
        --build-arg "BASE_IMAGE=${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG}"
    )
    
    # Add additional build args if provided
    if [[ -n "$BUILD_ARGS" ]]; then
        # shellcheck disable=SC2086
        build_cmd+=($BUILD_ARGS)
    fi
    
    # Add build context (project root)
    build_cmd+=("$PROJECT_ROOT")
    
    log "Executing: ${build_cmd[*]}"
    
    if "${build_cmd[@]}"; then
        log "Successfully built ${image_name}:${image_tag}"
        
        # Tag with additional tags if specified
        if [[ -n "${ADDITIONAL_TAGS:-}" ]]; then
            for tag in $ADDITIONAL_TAGS; do
                docker tag "${image_name}:${image_tag}" "${image_name}:${tag}"
                log "Tagged as ${image_name}:${tag}"
            done
        fi
        
        return 0
    else
        error_exit "Failed to build ${image_name}:${image_tag}"
    fi
}

# Function to get image size
get_image_size() {
    local image_name="$1"
    docker image inspect "$image_name" --format='{{.Size}}' 2>/dev/null || echo "0"
}

# Function to display build summary
display_build_summary() {
    local flows=("$@")
    
    log "Build Summary:"
    log "=============="
    
    # Base image info
    local base_size
    base_size=$(get_image_size "${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG}")
    log "Base Image: ${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG} ($(numfmt --to=iec "$base_size"))"
    
    # Flow images info
    for flow in "${flows[@]}"; do
        local image_name="${FLOW_IMAGE_PREFIX}-${flow}:${FLOW_IMAGE_TAG:-latest}"
        local flow_size
        flow_size=$(get_image_size "$image_name")
        log "Flow Image: $image_name ($(numfmt --to=iec "$flow_size"))"
    done
    
    log "=============="
}

# Main execution
main() {
    local flows_to_build=()
    local build_all=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                build_all=true
                shift
                ;;
            --flow)
                flows_to_build+=("$2")
                shift 2
                ;;
            --base-tag)
                BASE_IMAGE_TAG="$2"
                shift 2
                ;;
            --flow-tag)
                FLOW_IMAGE_TAG="$2"
                shift 2
                ;;
            --additional-tags)
                ADDITIONAL_TAGS="$2"
                shift 2
                ;;
            --build-args)
                BUILD_ARGS="$2"
                shift 2
                ;;
            --help)
                cat << EOF
Usage: $0 [OPTIONS]

Build flow-specific container images.

Options:
    --all                   Build all flow images (rpa1, rpa2, rpa3)
    --flow FLOW_NAME        Build specific flow image (can be used multiple times)
    --base-tag TAG          Base image tag to use (default: latest)
    --flow-tag TAG          Tag for flow images (default: latest)
    --additional-tags TAGS  Additional tags to apply (space-separated)
    --build-args ARGS       Additional Docker build arguments
    --help                  Show this help message

Examples:
    $0 --all                           # Build all flow images
    $0 --flow rpa1 --flow rpa2         # Build specific flows
    $0 --all --flow-tag v1.0.0         # Build all with specific tag
    $0 --flow rpa1 --build-args "--no-cache"  # Build with additional args

EOF
                exit 0
                ;;
            *)
                error_exit "Unknown option: $1. Use --help for usage information."
                ;;
        esac
    done
    
    # Determine which flows to build
    if [[ "$build_all" == true ]]; then
        flows_to_build=("rpa1" "rpa2" "rpa3")
    elif [[ ${#flows_to_build[@]} -eq 0 ]]; then
        error_exit "No flows specified. Use --all or --flow FLOW_NAME. Use --help for more information."
    fi
    
    # Validate flow names
    for flow in "${flows_to_build[@]}"; do
        if [[ ! "$flow" =~ ^rpa[1-3]$ ]]; then
            error_exit "Invalid flow name: $flow. Must be one of: rpa1, rpa2, rpa3"
        fi
    done
    
    log "Starting flow image build process..."
    log "Flows to build: ${flows_to_build[*]}"
    log "Base image: ${BASE_IMAGE_NAME}:${BASE_IMAGE_TAG}"
    log "Flow image tag: ${FLOW_IMAGE_TAG:-latest}"
    
    # Check base image availability
    check_base_image
    
    # Build each flow image
    local build_start_time
    build_start_time=$(date +%s)
    
    for flow in "${flows_to_build[@]}"; do
        log "Building flow: $flow"
        build_flow_image "$flow"
    done
    
    local build_end_time
    build_end_time=$(date +%s)
    local build_duration=$((build_end_time - build_start_time))
    
    log "All flow images built successfully in ${build_duration}s"
    
    # Display build summary
    display_build_summary "${flows_to_build[@]}"
}

# Change to project root
cd "$PROJECT_ROOT"

# Execute main function with all arguments
main "$@"