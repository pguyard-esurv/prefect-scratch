#!/bin/bash
# Flow Container Startup Script
# Handles service dependencies, configuration validation, and graceful shutdown

set -euo pipefail

# Configuration
FLOW_NAME="${1:-unknown}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
HEALTH_CHECK_SCRIPT="$SCRIPT_DIR/health_check.py"
VALIDATE_CONFIG_SCRIPT="$SCRIPT_DIR/validate_database_config.py"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$FLOW_NAME] $*" >&2
}

# Error handling
error_exit() {
    log "ERROR: $1"
    exit 1
}

# Signal handling for graceful shutdown
cleanup() {
    log "Received shutdown signal, performing graceful cleanup..."
    
    # Kill background processes if any
    if [[ -n "${FLOW_PID:-}" ]]; then
        log "Stopping flow process (PID: $FLOW_PID)..."
        kill -TERM "$FLOW_PID" 2>/dev/null || true
        
        # Wait for graceful shutdown
        local count=0
        while kill -0 "$FLOW_PID" 2>/dev/null && [[ $count -lt 30 ]]; do
            sleep 1
            ((count++))
        done
        
        # Force kill if still running
        if kill -0 "$FLOW_PID" 2>/dev/null; then
            log "Force killing flow process..."
            kill -KILL "$FLOW_PID" 2>/dev/null || true
        fi
    fi
    
    log "Cleanup completed"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT SIGQUIT

# Validate flow name
if [[ ! "$FLOW_NAME" =~ ^(rpa1|rpa2|rpa3)$ ]]; then
    error_exit "Invalid flow name: $FLOW_NAME. Must be one of: rpa1, rpa2, rpa3"
fi

log "Starting $FLOW_NAME container..."

# Step 1: Validate container environment
log "Step 1: Validating container environment..."

# Check required environment variables
required_vars=(
    "FLOW_NAME"
    "FLOW_TYPE"
    "PREFECT_FLOW_NAME"
)

for var in "${required_vars[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        error_exit "Required environment variable $var is not set"
    fi
done

log "Environment validation completed"

# Step 2: Wait for service dependencies
log "Step 2: Waiting for service dependencies..."

# Function to wait for service
wait_for_service() {
    local service_name="$1"
    local check_command="$2"
    local timeout="${3:-60}"
    local count=0
    
    log "Waiting for $service_name (timeout: ${timeout}s)..."
    
    while ! eval "$check_command" >/dev/null 2>&1; do
        if [[ $count -ge $timeout ]]; then
            error_exit "$service_name is not available after ${timeout}s"
        fi
        
        sleep 2
        ((count += 2))
        
        if [[ $((count % 10)) -eq 0 ]]; then
            log "Still waiting for $service_name... (${count}s elapsed)"
        fi
    done
    
    log "$service_name is available"
}

# Wait for database (if configuration validation script exists)
if [[ -f "$VALIDATE_CONFIG_SCRIPT" ]]; then
    wait_for_service "Database" "python '$VALIDATE_CONFIG_SCRIPT' --quick-check" 120
else
    log "Database configuration validator not found, skipping database check"
fi

# Wait for Prefect server (if PREFECT_API_URL is set)
if [[ -n "${PREFECT_API_URL:-}" ]]; then
    wait_for_service "Prefect Server" "curl -f -s '$PREFECT_API_URL/api/health' -o /dev/null" 60
else
    log "PREFECT_API_URL not set, skipping Prefect server check"
fi

log "Service dependencies are ready"

# Step 3: Perform startup health check
log "Step 3: Performing startup health check..."

if [[ -f "$HEALTH_CHECK_SCRIPT" ]]; then
    if ! python "$HEALTH_CHECK_SCRIPT" --flow="$FLOW_NAME" --startup-check; then
        error_exit "Startup health check failed"
    fi
    log "Startup health check passed"
else
    log "Health check script not found, skipping startup health check"
fi

# Step 4: Load flow-specific configuration
log "Step 4: Loading flow-specific configuration..."

# Set flow-specific working directory
FLOW_DIR="$APP_DIR/flows/$FLOW_NAME"
if [[ ! -d "$FLOW_DIR" ]]; then
    error_exit "Flow directory not found: $FLOW_DIR"
fi

cd "$FLOW_DIR"
log "Changed to flow directory: $FLOW_DIR"

# Load flow-specific environment file if it exists
ENV_FILE=".env.${ENVIRONMENT:-development}"
if [[ -f "$ENV_FILE" ]]; then
    log "Loading flow-specific environment from $ENV_FILE"
    set -a  # Export all variables
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
else
    log "No flow-specific environment file found ($ENV_FILE), using defaults"
fi

# Step 5: Start the flow
log "Step 5: Starting $FLOW_NAME workflow..."

# Determine the flow execution mode
EXECUTION_MODE="${CONTAINER_EXECUTION_MODE:-daemon}"

case "$EXECUTION_MODE" in
    "daemon")
        log "Starting flow in daemon mode (continuous execution)"
        
        # Start flow in background with continuous execution
        while true; do
            log "Executing $FLOW_NAME workflow..."
            
            # Run the workflow
            python workflow.py &
            FLOW_PID=$!
            
            # Wait for completion
            if wait "$FLOW_PID"; then
                log "Workflow completed successfully"
            else
                log "Workflow failed with exit code $?"
            fi
            
            # Wait before next execution (configurable interval)
            EXECUTION_INTERVAL="${CONTAINER_EXECUTION_INTERVAL:-300}"  # 5 minutes default
            log "Waiting ${EXECUTION_INTERVAL}s before next execution..."
            sleep "$EXECUTION_INTERVAL" &
            wait $!  # This allows signal handling during sleep
        done
        ;;
        
    "single")
        log "Starting flow in single execution mode"
        
        # Run the workflow once
        python workflow.py &
        FLOW_PID=$!
        
        # Wait for completion
        if wait "$FLOW_PID"; then
            log "Workflow completed successfully"
            exit 0
        else
            error_exit "Workflow failed with exit code $?"
        fi
        ;;
        
    "server")
        log "Starting flow in server mode (Prefect agent)"
        
        # Start Prefect agent for this flow
        prefect agent start --pool "${PREFECT_WORK_POOL:-default}" --limit "${PREFECT_AGENT_LIMIT:-1}" &
        FLOW_PID=$!
        
        # Wait for agent
        wait "$FLOW_PID"
        ;;
        
    *)
        error_exit "Invalid execution mode: $EXECUTION_MODE. Must be one of: daemon, single, server"
        ;;
esac