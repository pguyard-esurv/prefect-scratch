#!/bin/bash
#
# Build script for base container image with caching optimization.
# Implements efficient Docker layer caching and build optimization.
#

set -euo pipefail

# Configuration
BASE_IMAGE_NAME="rpa-base"
BASE_IMAGE_TAG="latest"
DOCKERFILE="core/docker/Dockerfile"
BUILD_CONTEXT="."

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

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if Dockerfile exists
    if [[ ! -f "$DOCKERFILE" ]]; then
        log_error "Dockerfile '$DOCKERFILE' not found"
        exit 1
    fi
    
    # Check if required files exist
    local required_files=("pyproject.toml" "uv.lock" "core/" "conftest.py")
    for file in "${required_files[@]}"; do
        if [[ ! -e "$file" ]]; then
            log_error "Required file/directory '$file' not found"
            exit 1
        fi
    done
    
    log_success "Prerequisites check passed"
}

# Function to clean up old images (optional)
cleanup_old_images() {
    log_info "Cleaning up old images..."
    
    # Remove dangling images
    local dangling_images=$(docker images -f "dangling=true" -q)
    if [[ -n "$dangling_images" ]]; then
        docker rmi $dangling_images || log_warning "Failed to remove some dangling images"
        log_success "Removed dangling images"
    else
        log_info "No dangling images to remove"
    fi
}

# Function to build base image with caching
build_base_image() {
    log_info "Building base image: $BASE_IMAGE_NAME:$BASE_IMAGE_TAG"
    
    # Build arguments for optimization
    local build_args=(
        "--file" "$DOCKERFILE"
        "--tag" "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG"
        "--build-arg" "BUILDKIT_INLINE_CACHE=1"
        "--progress" "plain"
    )
    
    # Add cache-from if previous image exists
    if docker image inspect "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG" &> /dev/null; then
        log_info "Using existing image as cache source"
        build_args+=("--cache-from" "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG")
    fi
    
    # Add build context
    build_args+=("$BUILD_CONTEXT")
    
    # Execute build with timing
    local start_time=$(date +%s)
    
    if docker build "${build_args[@]}"; then
        local end_time=$(date +%s)
        local build_duration=$((end_time - start_time))
        log_success "Base image built successfully in ${build_duration}s"
    else
        log_error "Base image build failed"
        exit 1
    fi
}

# Function to validate built image
validate_image() {
    log_info "Validating built image..."
    
    # Check if image exists
    if ! docker image inspect "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG" &> /dev/null; then
        log_error "Built image not found"
        exit 1
    fi
    
    # Run health check
    log_info "Running health check on built image..."
    if docker run --rm "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG" uv run python scripts/health_check.py; then
        log_success "Image health check passed"
    else
        log_error "Image health check failed"
        exit 1
    fi
    
    # Check image size
    local image_size=$(docker image inspect "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG" --format='{{.Size}}')
    local size_mb=$((image_size / 1024 / 1024))
    log_info "Image size: ${size_mb}MB"
    
    if [[ $size_mb -gt 2000 ]]; then
        log_warning "Image size is quite large (${size_mb}MB). Consider optimization."
    fi
}

# Function to tag image with additional tags
tag_image() {
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local commit_hash=""
    
    # Get git commit hash if available
    if command -v git &> /dev/null && git rev-parse --git-dir &> /dev/null; then
        commit_hash=$(git rev-parse --short HEAD)
        docker tag "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG" "$BASE_IMAGE_NAME:$commit_hash"
        log_info "Tagged image with commit hash: $BASE_IMAGE_NAME:$commit_hash"
    fi
    
    # Tag with timestamp
    docker tag "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG" "$BASE_IMAGE_NAME:$timestamp"
    log_info "Tagged image with timestamp: $BASE_IMAGE_NAME:$timestamp"
}

# Function to display image information
display_image_info() {
    log_info "Base image information:"
    docker image inspect "$BASE_IMAGE_NAME:$BASE_IMAGE_TAG" --format='
Image ID: {{.Id}}
Created: {{.Created}}
Size: {{.Size}} bytes
Architecture: {{.Architecture}}
OS: {{.Os}}
'
    
    log_info "Available tags for $BASE_IMAGE_NAME:"
    docker images "$BASE_IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
}

# Main execution
main() {
    log_info "Starting base image build process..."
    
    # Parse command line arguments
    local cleanup=false
    local validate=true
    local tag_extra=true
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --cleanup)
                cleanup=true
                shift
                ;;
            --no-validate)
                validate=false
                shift
                ;;
            --no-tag)
                tag_extra=false
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --cleanup     Clean up old images before building"
                echo "  --no-validate Skip image validation after build"
                echo "  --no-tag      Skip additional tagging"
                echo "  --help        Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Execute build steps
    check_prerequisites
    
    if [[ "$cleanup" == true ]]; then
        cleanup_old_images
    fi
    
    build_base_image
    
    if [[ "$validate" == true ]]; then
        validate_image
    fi
    
    if [[ "$tag_extra" == true ]]; then
        tag_image
    fi
    
    display_image_info
    
    log_success "Base image build process completed successfully!"
    log_info "You can now use this image to build flow-specific containers"
}

# Execute main function with all arguments
main "$@"