#!/bin/bash
# Selective rebuild script based on code change detection
# Only rebuilds containers when relevant code changes are detected

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CACHE_DIR="${PROJECT_ROOT}/.build_cache"
CHECKSUMS_FILE="${CACHE_DIR}/checksums.txt"
BUILD_LOG="${CACHE_DIR}/build.log"

# Default values
DRY_RUN="${DRY_RUN:-false}"
FORCE_REBUILD="${FORCE_REBUILD:-false}"
VERBOSE="${VERBOSE:-false}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SELECTIVE-BUILD] $*" >&2
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

verbose_log() {
    if [[ "$VERBOSE" == "true" ]]; then
        log_info "$1"
    fi
}

# Function to create cache directory
setup_cache_dir() {
    if [[ ! -d "$CACHE_DIR" ]]; then
        mkdir -p "$CACHE_DIR"
        log_info "Created cache directory: $CACHE_DIR"
    fi
}

# Function to calculate checksums for relevant files
calculate_checksums() {
    local checksums_temp="${CACHE_DIR}/checksums_temp.txt"
    
    verbose_log "Calculating checksums for change detection..."
    
    # Base image dependencies
    {
        echo "# Base image dependencies"
        find core/ -type f -name "*.py" -exec sha256sum {} \; 2>/dev/null || true
        sha256sum pyproject.toml uv.lock conftest.py 2>/dev/null || true
        sha256sum Dockerfile.base 2>/dev/null || true
        sha256sum scripts/health_check.py 2>/dev/null || true
    } > "$checksums_temp"
    
    # Flow-specific dependencies
    for flow in rpa1 rpa2 rpa3; do
        echo "# Flow $flow dependencies" >> "$checksums_temp"
        if [[ -d "flows/$flow" ]]; then
            find "flows/$flow" -type f -name "*.py" -exec sha256sum {} \; 2>/dev/null >> "$checksums_temp" || true
        fi
        sha256sum "Dockerfile.flow${flow#rpa}" 2>/dev/null >> "$checksums_temp" || true
    done
    
    # Additional build-related files
    {
        echo "# Build scripts"
        sha256sum scripts/build_*.sh 2>/dev/null || true
        sha256sum scripts/flow_startup.sh 2>/dev/null || true
    } >> "$checksums_temp"
    
    mv "$checksums_temp" "${CACHE_DIR}/checksums_new.txt"
    verbose_log "Checksums calculated and saved"
}

# Function to detect changes
detect_changes() {
    local changes_detected=()
    
    if [[ ! -f "$CHECKSUMS_FILE" ]] || [[ "$FORCE_REBUILD" == "true" ]]; then
        log_info "No previous checksums found or force rebuild requested - rebuilding all"
        changes_detected=("base" "rpa1" "rpa2" "rpa3")
    else
        verbose_log "Comparing checksums to detect changes..."
        
        # Check base image changes
        if ! diff -q <(grep -A 100 "# Base image dependencies" "$CHECKSUMS_FILE" | grep -v "^#" | head -n -1) \
                     <(grep -A 100 "# Base image dependencies" "${CACHE_DIR}/checksums_new.txt" | grep -v "^#" | head -n -1) >/dev/null 2>&1; then
            changes_detected+=("base")
            log_info "Base image changes detected"
        fi
        
        # Check flow-specific changes
        for flow in rpa1 rpa2 rpa3; do
            if ! diff -q <(grep -A 50 "# Flow $flow dependencies" "$CHECKSUMS_FILE" | grep -v "^#" | head -n -1) \
                         <(grep -A 50 "# Flow $flow dependencies" "${CACHE_DIR}/checksums_new.txt" | grep -v "^#" | head -n -1) >/dev/null 2>&1; then
                changes_detected+=("$flow")
                log_info "Flow $flow changes detected"
            fi
        done
        
        # Check build script changes
        if ! diff -q <(grep -A 20 "# Build scripts" "$CHECKSUMS_FILE" | grep -v "^#") \
                     <(grep -A 20 "# Build scripts" "${CACHE_DIR}/checksums_new.txt" | grep -v "^#") >/dev/null 2>&1; then
            log_info "Build script changes detected - rebuilding all"
            changes_detected=("base" "rpa1" "rpa2" "rpa3")
        fi
    fi
    
    echo "${changes_detected[@]}"
}

# Function to determine rebuild order
determine_rebuild_order() {
    local changes=("$@")
    local rebuild_order=()
    
    # If base image needs rebuild, it must be first
    for change in "${changes[@]}"; do
        if [[ "$change" == "base" ]]; then
            rebuild_order+=("base")
            break
        fi
    done
    
    # If base image is being rebuilt, all flows need rebuild
    local base_rebuilding=false
    for change in "${changes[@]}"; do
        if [[ "$change" == "base" ]]; then
            base_rebuilding=true
            rebuild_order+=("rpa1" "rpa2" "rpa3")
            break
        fi
    done
    
    # If base image is not being rebuilt, add only changed flows
    if [[ "$base_rebuilding" == "false" ]]; then
        for change in "${changes[@]}"; do
            if [[ "$change" =~ ^rpa[1-3]$ ]]; then
                rebuild_order+=("$change")
            fi
        done
    fi
    
    echo "${rebuild_order[@]}"
}

# Function to build base image
build_base_image() {
    log_info "Building base image..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would build base image"
        return 0
    fi
    
    local build_start=$(date +%s)
    
    if BASE_IMAGE_TAG="$IMAGE_TAG" "$SCRIPT_DIR/build_base_image.sh" --no-tag; then
        local build_end=$(date +%s)
        local duration=$((build_end - build_start))
        log_success "Base image built successfully in ${duration}s"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Base image built in ${duration}s" >> "$BUILD_LOG"
        return 0
    else
        log_error "Base image build failed"
        return 1
    fi
}

# Function to build flow image
build_flow_image() {
    local flow="$1"
    
    log_info "Building flow image: $flow"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would build flow image: $flow"
        return 0
    fi
    
    local build_start=$(date +%s)
    
    if BASE_IMAGE_TAG="$IMAGE_TAG" FLOW_IMAGE_TAG="$IMAGE_TAG" \
       "$SCRIPT_DIR/build_flow_images.sh" --flow "$flow"; then
        local build_end=$(date +%s)
        local duration=$((build_end - build_start))
        log_success "Flow $flow built successfully in ${duration}s"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Flow $flow built in ${duration}s" >> "$BUILD_LOG"
        return 0
    else
        log_error "Flow $flow build failed"
        return 1
    fi
}

# Function to update checksums after successful build
update_checksums() {
    if [[ "$DRY_RUN" != "true" ]]; then
        mv "${CACHE_DIR}/checksums_new.txt" "$CHECKSUMS_FILE"
        log_info "Updated checksums cache"
    fi
}

# Function to display build summary
display_build_summary() {
    local built_components=("$@")
    
    log_info "Selective Build Summary"
    log_info "======================"
    
    if [[ ${#built_components[@]} -eq 0 ]]; then
        log_success "No changes detected - no rebuilds required"
    else
        log_info "Components rebuilt: ${built_components[*]}"
        
        # Show recent build times
        if [[ -f "$BUILD_LOG" ]]; then
            log_info "Recent build times:"
            tail -n 10 "$BUILD_LOG" | while read -r line; do
                log_info "  $line"
            done
        fi
    fi
    
    log_info "======================"
}

# Function to clean up build cache
cleanup_cache() {
    log_info "Cleaning up build cache..."
    
    if [[ -d "$CACHE_DIR" ]]; then
        # Keep only recent build logs
        if [[ -f "$BUILD_LOG" ]]; then
            tail -n 100 "$BUILD_LOG" > "${BUILD_LOG}.tmp" && mv "${BUILD_LOG}.tmp" "$BUILD_LOG"
        fi
        
        # Remove temporary files
        find "$CACHE_DIR" -name "*.tmp" -delete 2>/dev/null || true
        find "$CACHE_DIR" -name "checksums_new.txt" -delete 2>/dev/null || true
        
        log_success "Build cache cleaned up"
    fi
}

# Main execution
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN="true"
                shift
                ;;
            --force)
                FORCE_REBUILD="true"
                shift
                ;;
            --verbose)
                VERBOSE="true"
                shift
                ;;
            --tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            --cleanup)
                cleanup_cache
                exit 0
                ;;
            --help)
                cat << EOF
Usage: $0 [OPTIONS]

Selective rebuild script that only rebuilds containers when relevant code changes.

Options:
    --dry-run       Show what would be built without actually building
    --force         Force rebuild all containers regardless of changes
    --verbose       Enable verbose logging
    --tag TAG       Tag for built images (default: latest)
    --cleanup       Clean up build cache and exit
    --help          Show this help message

Environment Variables:
    DRY_RUN         Enable dry run mode (default: false)
    FORCE_REBUILD   Force rebuild all (default: false)
    VERBOSE         Enable verbose logging (default: false)
    IMAGE_TAG       Tag for images (default: latest)

Examples:
    $0                      # Build only changed components
    $0 --dry-run            # Show what would be built
    $0 --force --verbose    # Force rebuild all with verbose output
    $0 --tag v1.0.0         # Build with specific tag

EOF
                exit 0
                ;;
            *)
                log_error "Unknown option: $1. Use --help for usage information."
                exit 1
                ;;
        esac
    done
    
    local script_start=$(date +%s)
    
    log_info "Starting selective rebuild process..."
    log_info "Configuration: dry-run=$DRY_RUN, force=$FORCE_REBUILD, verbose=$VERBOSE, tag=$IMAGE_TAG"
    
    # Setup
    setup_cache_dir
    calculate_checksums
    
    # Detect changes
    local changes
    changes=($(detect_changes))
    
    if [[ ${#changes[@]} -eq 0 ]]; then
        log_success "No changes detected - no rebuilds required"
        display_build_summary
        exit 0
    fi
    
    log_info "Changes detected in: ${changes[*]}"
    
    # Determine rebuild order
    local rebuild_order
    rebuild_order=($(determine_rebuild_order "${changes[@]}"))
    
    log_info "Rebuild order: ${rebuild_order[*]}"
    
    # Execute builds
    local built_components=()
    local failed_builds=()
    
    for component in "${rebuild_order[@]}"; do
        if [[ "$component" == "base" ]]; then
            if build_base_image; then
                built_components+=("base")
            else
                failed_builds+=("base")
                break  # Base image failure stops everything
            fi
        else
            if build_flow_image "$component"; then
                built_components+=("$component")
            else
                failed_builds+=("$component")
            fi
        fi
    done
    
    # Handle results
    if [[ ${#failed_builds[@]} -gt 0 ]]; then
        log_error "Build failures: ${failed_builds[*]}"
        exit 1
    fi
    
    # Update checksums on success
    update_checksums
    
    local script_end=$(date +%s)
    local total_duration=$((script_end - script_start))
    
    log_success "Selective rebuild completed successfully in ${total_duration}s"
    display_build_summary "${built_components[@]}"
}

# Change to project root
cd "$PROJECT_ROOT"

# Execute main function with all arguments
main "$@"