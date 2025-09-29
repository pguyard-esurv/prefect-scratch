#!/bin/bash
# Automated security scanning integration for container builds
# Integrates multiple security scanning tools into the build process

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SCAN_RESULTS_DIR="${PROJECT_ROOT}/.security_scans"
SCAN_CONFIG_DIR="${PROJECT_ROOT}/.security_config"

# Default values
SCAN_LEVEL="${SCAN_LEVEL:-medium}"
FAIL_ON_HIGH="${FAIL_ON_HIGH:-true}"
FAIL_ON_CRITICAL="${FAIL_ON_CRITICAL:-true}"
GENERATE_REPORT="${GENERATE_REPORT:-true}"
SCAN_TIMEOUT="${SCAN_TIMEOUT:-300}"

# Security tools configuration
TRIVY_ENABLED="${TRIVY_ENABLED:-true}"
GRYPE_ENABLED="${GRYPE_ENABLED:-false}"
DOCKER_SCOUT_ENABLED="${DOCKER_SCOUT_ENABLED:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SECURITY] $*" >&2
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

log_critical() {
    echo -e "${PURPLE}[CRITICAL]${NC} $1" >&2
}

# Function to setup scan directories
setup_scan_directories() {
    mkdir -p "$SCAN_RESULTS_DIR" "$SCAN_CONFIG_DIR"
    log_info "Scan directories initialized"
}

# Function to check security tool availability
check_security_tools() {
    local tools_available=()
    local tools_missing=()
    
    # Check Trivy
    if [[ "$TRIVY_ENABLED" == "true" ]]; then
        if command -v trivy >/dev/null 2>&1; then
            tools_available+=("trivy")
        else
            tools_missing+=("trivy")
        fi
    fi
    
    # Check Grype
    if [[ "$GRYPE_ENABLED" == "true" ]]; then
        if command -v grype >/dev/null 2>&1; then
            tools_available+=("grype")
        else
            tools_missing+=("grype")
        fi
    fi
    
    # Check Docker Scout
    if [[ "$DOCKER_SCOUT_ENABLED" == "true" ]]; then
        if docker scout version >/dev/null 2>&1; then
            tools_available+=("docker-scout")
        else
            tools_missing+=("docker-scout")
        fi
    fi
    
    log_info "Available security tools: ${tools_available[*]:-none}"
    
    if [[ ${#tools_missing[@]} -gt 0 ]]; then
        log_warning "Missing security tools: ${tools_missing[*]}"
        log_info "Install missing tools or disable them in configuration"
    fi
    
    if [[ ${#tools_available[@]} -eq 0 ]]; then
        log_error "No security scanning tools available"
        return 1
    fi
    
    return 0
}

# Function to install Trivy if not available
install_trivy() {
    log_info "Installing Trivy security scanner..."
    
    case "$(uname -s)" in
        "Darwin")
            if command -v brew >/dev/null 2>&1; then
                brew install trivy
            else
                log_error "Homebrew not available. Please install Trivy manually."
                return 1
            fi
            ;;
        "Linux")
            # Install via package manager or binary
            if command -v apt-get >/dev/null 2>&1; then
                sudo apt-get update && sudo apt-get install -y wget apt-transport-https gnupg lsb-release
                wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
                echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
                sudo apt-get update && sudo apt-get install -y trivy
            else
                log_error "Package manager not supported. Please install Trivy manually."
                return 1
            fi
            ;;
        *)
            log_error "Unsupported OS. Please install Trivy manually."
            return 1
            ;;
    esac
    
    log_success "Trivy installed successfully"
}

# Function to create Trivy configuration
create_trivy_config() {
    local config_file="${SCAN_CONFIG_DIR}/trivy.yaml"
    
    cat > "$config_file" << EOF
# Trivy configuration for container security scanning
format: json
output: ${SCAN_RESULTS_DIR}/trivy-results.json
severity: UNKNOWN,LOW,MEDIUM,HIGH,CRITICAL
vuln-type: os,library
timeout: ${SCAN_TIMEOUT}s
cache-dir: ${SCAN_RESULTS_DIR}/.trivy-cache
db:
  skip-update: false
  light: false

# Ignore unfixed vulnerabilities in certain cases
ignore-unfixed: false

# Exit code configuration
exit-code: 0  # Don't fail on vulnerabilities (we handle this separately)

# Scanning options
scanners: vuln,secret,config
skip-dirs: .git,.trivy-cache,node_modules
skip-files: "*.md,*.txt"

# Secret scanning
secret:
  config: ${SCAN_CONFIG_DIR}/trivy-secret.yaml

# Misconfiguration scanning  
config:
  policy: ${SCAN_CONFIG_DIR}/trivy-policy
EOF

    # Create secret scanning configuration
    cat > "${SCAN_CONFIG_DIR}/trivy-secret.yaml" << EOF
# Secret scanning rules
rules:
  - id: aws-access-key
    category: AWS
    title: AWS Access Key
    severity: HIGH
    regex: 'AKIA[0-9A-Z]{16}'
    
  - id: aws-secret-key
    category: AWS  
    title: AWS Secret Key
    severity: CRITICAL
    regex: '[0-9a-zA-Z/+]{40}'
    
  - id: github-token
    category: GitHub
    title: GitHub Token
    severity: HIGH
    regex: 'ghp_[0-9a-zA-Z]{36}'
    
  - id: docker-config
    category: Docker
    title: Docker Config
    severity: MEDIUM
    regex: '\.dockercfg'
EOF

    log_info "Trivy configuration created: $config_file"
}

# Function to scan image with Trivy
scan_with_trivy() {
    local image_name="$1"
    local scan_timestamp=$(date +%Y%m%d_%H%M%S)
    local results_file="${SCAN_RESULTS_DIR}/trivy_${scan_timestamp}.json"
    
    log_info "Scanning $image_name with Trivy..."
    
    # Update vulnerability database
    trivy image --download-db-only >/dev/null 2>&1 || {
        log_warning "Failed to update Trivy database"
    }
    
    # Run vulnerability scan
    if timeout "$SCAN_TIMEOUT" trivy image \
        --config "${SCAN_CONFIG_DIR}/trivy.yaml" \
        --format json \
        --output "$results_file" \
        "$image_name" >/dev/null 2>&1; then
        
        log_success "Trivy scan completed: $results_file"
        echo "$results_file"
    else
        log_error "Trivy scan failed for $image_name"
        return 1
    fi
}

# Function to scan image with Grype
scan_with_grype() {
    local image_name="$1"
    local scan_timestamp=$(date +%Y%m%d_%H%M%S)
    local results_file="${SCAN_RESULTS_DIR}/grype_${scan_timestamp}.json"
    
    log_info "Scanning $image_name with Grype..."
    
    if timeout "$SCAN_TIMEOUT" grype \
        --output json \
        --file "$results_file" \
        "$image_name" >/dev/null 2>&1; then
        
        log_success "Grype scan completed: $results_file"
        echo "$results_file"
    else
        log_error "Grype scan failed for $image_name"
        return 1
    fi
}

# Function to scan image with Docker Scout
scan_with_docker_scout() {
    local image_name="$1"
    local scan_timestamp=$(date +%Y%m%d_%H%M%S)
    local results_file="${SCAN_RESULTS_DIR}/scout_${scan_timestamp}.json"
    
    log_info "Scanning $image_name with Docker Scout..."
    
    if timeout "$SCAN_TIMEOUT" docker scout cves \
        --format json \
        --output "$results_file" \
        "$image_name" >/dev/null 2>&1; then
        
        log_success "Docker Scout scan completed: $results_file"
        echo "$results_file"
    else
        log_error "Docker Scout scan failed for $image_name"
        return 1
    fi
}

# Function to parse Trivy results
parse_trivy_results() {
    local results_file="$1"
    
    if [[ ! -f "$results_file" ]]; then
        log_error "Trivy results file not found: $results_file"
        return 1
    fi
    
    # Extract vulnerability counts by severity
    local critical high medium low unknown
    critical=$(jq -r '[.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length' "$results_file" 2>/dev/null || echo "0")
    high=$(jq -r '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length' "$results_file" 2>/dev/null || echo "0")
    medium=$(jq -r '[.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM")] | length' "$results_file" 2>/dev/null || echo "0")
    low=$(jq -r '[.Results[]?.Vulnerabilities[]? | select(.Severity == "LOW")] | length' "$results_file" 2>/dev/null || echo "0")
    unknown=$(jq -r '[.Results[]?.Vulnerabilities[]? | select(.Severity == "UNKNOWN")] | length' "$results_file" 2>/dev/null || echo "0")
    
    echo "CRITICAL:$critical HIGH:$high MEDIUM:$medium LOW:$low UNKNOWN:$unknown"
}

# Function to analyze scan results
analyze_scan_results() {
    local results_files=("$@")
    local total_critical=0
    local total_high=0
    local total_medium=0
    local total_low=0
    local scan_failed=false
    
    log_info "Analyzing security scan results..."
    
    for results_file in "${results_files[@]}"; do
        if [[ -f "$results_file" ]]; then
            local tool_name
            tool_name=$(basename "$results_file" | cut -d'_' -f1)
            
            case "$tool_name" in
                "trivy")
                    local counts
                    counts=$(parse_trivy_results "$results_file")
                    local critical high medium low
                    critical=$(echo "$counts" | grep -o "CRITICAL:[0-9]*" | cut -d':' -f2)
                    high=$(echo "$counts" | grep -o "HIGH:[0-9]*" | cut -d':' -f2)
                    medium=$(echo "$counts" | grep -o "MEDIUM:[0-9]*" | cut -d':' -f2)
                    low=$(echo "$counts" | grep -o "LOW:[0-9]*" | cut -d':' -f2)
                    
                    total_critical=$((total_critical + critical))
                    total_high=$((total_high + high))
                    total_medium=$((total_medium + medium))
                    total_low=$((total_low + low))
                    
                    log_info "Trivy results: Critical=$critical, High=$high, Medium=$medium, Low=$low"
                    ;;
                *)
                    log_info "Results from $tool_name: $(basename "$results_file")"
                    ;;
            esac
        fi
    done
    
    # Display summary
    log_info "Security Scan Summary:"
    log_info "====================="
    log_info "Critical vulnerabilities: $total_critical"
    log_info "High vulnerabilities: $total_high"
    log_info "Medium vulnerabilities: $total_medium"
    log_info "Low vulnerabilities: $total_low"
    log_info "====================="
    
    # Determine if scan should fail the build
    if [[ "$FAIL_ON_CRITICAL" == "true" && $total_critical -gt 0 ]]; then
        log_critical "Build failed: $total_critical critical vulnerabilities found"
        scan_failed=true
    fi
    
    if [[ "$FAIL_ON_HIGH" == "true" && $total_high -gt 0 ]]; then
        log_error "Build failed: $total_high high vulnerabilities found"
        scan_failed=true
    fi
    
    if [[ "$scan_failed" == "true" ]]; then
        return 1
    else
        log_success "Security scan passed"
        return 0
    fi
}

# Function to generate security report
generate_security_report() {
    local image_name="$1"
    local results_files=("${@:2}")
    local report_timestamp=$(date +%Y%m%d_%H%M%S)
    local report_file="${SCAN_RESULTS_DIR}/security_report_${report_timestamp}.html"
    
    log_info "Generating security report..."
    
    cat > "$report_file" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>Security Scan Report - $image_name</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 10px; border-radius: 5px; }
        .critical { color: #d32f2f; font-weight: bold; }
        .high { color: #f57c00; font-weight: bold; }
        .medium { color: #fbc02d; font-weight: bold; }
        .low { color: #388e3c; }
        .summary { background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .results { margin: 20px 0; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Security Scan Report</h1>
        <p><strong>Image:</strong> $image_name</p>
        <p><strong>Scan Date:</strong> $(date)</p>
        <p><strong>Report Generated:</strong> $(date)</p>
    </div>
    
    <div class="summary">
        <h2>Executive Summary</h2>
        <p>This report contains the results of automated security scanning performed on the container image.</p>
    </div>
    
    <div class="results">
        <h2>Scan Results</h2>
EOF

    # Add results from each tool
    for results_file in "${results_files[@]}"; do
        if [[ -f "$results_file" ]]; then
            local tool_name
            tool_name=$(basename "$results_file" | cut -d'_' -f1)
            
            echo "<h3>$tool_name Results</h3>" >> "$report_file"
            echo "<p>Results file: $(basename "$results_file")</p>" >> "$report_file"
            
            case "$tool_name" in
                "trivy")
                    local counts
                    counts=$(parse_trivy_results "$results_file")
                    echo "<p>Vulnerability counts: $counts</p>" >> "$report_file"
                    ;;
            esac
        fi
    done
    
    cat >> "$report_file" << EOF
    </div>
    
    <div class="summary">
        <h2>Recommendations</h2>
        <ul>
            <li>Review and address critical and high severity vulnerabilities</li>
            <li>Update base images and dependencies regularly</li>
            <li>Implement security scanning in CI/CD pipeline</li>
            <li>Monitor for new vulnerabilities in deployed images</li>
        </ul>
    </div>
</body>
</html>
EOF

    log_success "Security report generated: $report_file"
    echo "$report_file"
}

# Function to scan single image
scan_image() {
    local image_name="$1"
    local results_files=()
    
    log_info "Starting security scan for image: $image_name"
    
    # Check if image exists
    if ! docker image inspect "$image_name" >/dev/null 2>&1; then
        log_error "Image not found: $image_name"
        return 1
    fi
    
    # Run scans with enabled tools
    if [[ "$TRIVY_ENABLED" == "true" ]] && command -v trivy >/dev/null 2>&1; then
        local trivy_results
        if trivy_results=$(scan_with_trivy "$image_name"); then
            results_files+=("$trivy_results")
        fi
    fi
    
    if [[ "$GRYPE_ENABLED" == "true" ]] && command -v grype >/dev/null 2>&1; then
        local grype_results
        if grype_results=$(scan_with_grype "$image_name"); then
            results_files+=("$grype_results")
        fi
    fi
    
    if [[ "$DOCKER_SCOUT_ENABLED" == "true" ]] && docker scout version >/dev/null 2>&1; then
        local scout_results
        if scout_results=$(scan_with_docker_scout "$image_name"); then
            results_files+=("$scout_results")
        fi
    fi
    
    # Analyze results
    if [[ ${#results_files[@]} -gt 0 ]]; then
        if analyze_scan_results "${results_files[@]}"; then
            # Generate report if requested
            if [[ "$GENERATE_REPORT" == "true" ]]; then
                generate_security_report "$image_name" "${results_files[@]}"
            fi
            return 0
        else
            return 1
        fi
    else
        log_error "No scan results available"
        return 1
    fi
}

# Function to scan all project images
scan_all_images() {
    local image_tag="${1:-latest}"
    local images=("rpa-base:$image_tag" "rpa-flow-rpa1:$image_tag" "rpa-flow-rpa2:$image_tag" "rpa-flow-rpa3:$image_tag")
    local scan_results=()
    local failed_scans=()
    
    log_info "Scanning all project images with tag: $image_tag"
    
    for image in "${images[@]}"; do
        if docker image inspect "$image" >/dev/null 2>&1; then
            log_info "Scanning image: $image"
            if scan_image "$image"; then
                scan_results+=("$image:PASSED")
            else
                scan_results+=("$image:FAILED")
                failed_scans+=("$image")
            fi
        else
            log_warning "Image not found, skipping: $image"
        fi
    done
    
    # Display summary
    log_info "Scan Summary for All Images:"
    log_info "============================"
    for result in "${scan_results[@]}"; do
        local image status
        image=$(echo "$result" | cut -d':' -f1-2)
        status=$(echo "$result" | cut -d':' -f3)
        
        if [[ "$status" == "PASSED" ]]; then
            log_success "$image: PASSED"
        else
            log_error "$image: FAILED"
        fi
    done
    log_info "============================"
    
    if [[ ${#failed_scans[@]} -gt 0 ]]; then
        log_error "Security scan failures: ${failed_scans[*]}"
        return 1
    else
        log_success "All security scans passed"
        return 0
    fi
}

# Main execution
main() {
    local action="scan"
    local image_name=""
    local image_tag="latest"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --image)
                image_name="$2"
                shift 2
                ;;
            --tag)
                image_tag="$2"
                shift 2
                ;;
            --all)
                action="scan-all"
                shift
                ;;
            --setup)
                action="setup"
                shift
                ;;
            --install-trivy)
                action="install-trivy"
                shift
                ;;
            --level)
                SCAN_LEVEL="$2"
                shift 2
                ;;
            --no-fail-high)
                FAIL_ON_HIGH="false"
                shift
                ;;
            --no-fail-critical)
                FAIL_ON_CRITICAL="false"
                shift
                ;;
            --no-report)
                GENERATE_REPORT="false"
                shift
                ;;
            --timeout)
                SCAN_TIMEOUT="$2"
                shift 2
                ;;
            --help)
                cat << EOF
Usage: $0 [ACTION] [OPTIONS]

Automated security scanning for container images.

Actions:
    --image IMAGE       Scan specific image
    --all              Scan all project images
    --setup            Setup security scanning environment
    --install-trivy    Install Trivy security scanner

Options:
    --tag TAG          Image tag to scan (default: latest)
    --level LEVEL      Scan level: low|medium|high (default: medium)
    --no-fail-high     Don't fail build on high severity issues
    --no-fail-critical Don't fail build on critical severity issues
    --no-report        Don't generate HTML report
    --timeout SECONDS  Scan timeout in seconds (default: 300)
    --help             Show this help message

Environment Variables:
    SCAN_LEVEL              Scan level (default: medium)
    FAIL_ON_HIGH           Fail on high severity (default: true)
    FAIL_ON_CRITICAL       Fail on critical severity (default: true)
    GENERATE_REPORT        Generate HTML report (default: true)
    TRIVY_ENABLED          Enable Trivy scanner (default: true)
    GRYPE_ENABLED          Enable Grype scanner (default: false)
    DOCKER_SCOUT_ENABLED   Enable Docker Scout (default: false)

Examples:
    $0 --image rpa-base:latest          # Scan specific image
    $0 --all --tag v1.0.0               # Scan all images with tag
    $0 --setup                          # Setup scanning environment
    $0 --install-trivy                  # Install Trivy scanner

EOF
                exit 0
                ;;
            *)
                log_error "Unknown option: $1. Use --help for usage information."
                exit 1
                ;;
        esac
    done
    
    log_info "Starting security scanning process: $action"
    
    # Execute action
    case "$action" in
        "setup")
            setup_scan_directories
            create_trivy_config
            check_security_tools
            log_success "Security scanning environment setup completed"
            ;;
        "install-trivy")
            install_trivy
            ;;
        "scan")
            if [[ -z "$image_name" ]]; then
                log_error "Image name required for scan action. Use --image IMAGE_NAME"
                exit 1
            fi
            setup_scan_directories
            create_trivy_config
            check_security_tools || exit 1
            scan_image "$image_name"
            ;;
        "scan-all")
            setup_scan_directories
            create_trivy_config
            check_security_tools || exit 1
            scan_all_images "$image_tag"
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