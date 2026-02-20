#!/bin/bash

# AMI Worker Fault Injection Testing Script
# ==========================================
# This script sets up environment variables for fault injection testing
# and runs the worker in a loop that restarts it when it crashes.
#
# Usage:
#   ./scripts/test_worker_robustness.sh  # all pipelines
#   ./scripts/test_worker_robustness.sh --pipeline moth_binary
#
# Environment Variables (override these to customize error rates):
#   CRASH_RATE: Worker crash probability (default: 0.05 = 5%)
#   NETWORK_ERROR_RATE: Network error probability (default: 0.03 = 3%)
#   IMAGE_ERROR_RATE: Image 404/corrupt probability (default: 0.02 = 2%)
#   TRANSIENT_ERROR_RATE: Transient failure probability (default: 0.04 = 4%)
#   MAX_RESTARTS: Maximum worker restarts before giving up (default: 50)
#   RESTART_DELAY: Seconds to wait before restarting (default: 5)

set -euo pipefail

# Default configuration - override with environment variables
CRASH_RATE="${CRASH_RATE:-0.05}"
NETWORK_ERROR_RATE="${NETWORK_ERROR_RATE:-0.03}"
IMAGE_ERROR_RATE="${IMAGE_ERROR_RATE:-0.02}"
TRANSIENT_ERROR_RATE="${TRANSIENT_ERROR_RATE:-0.04}"
MAX_RESTARTS="${MAX_RESTARTS:-50}"
RESTART_DELAY="${RESTART_DELAY:-5}"

# Default pipelines if none specified
PIPELINES="${*}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Function to check if required environment variables are set
check_prerequisites() {
    local missing_vars=()

    if [[ -z "${AMI_ANTENNA_API_AUTH_TOKEN:-}" ]]; then
        missing_vars+=("AMI_ANTENNA_API_AUTH_TOKEN")
    fi

    if [[ -z "${AMI_ANTENNA_SERVICE_NAME:-}" ]]; then
        missing_vars+=("AMI_ANTENNA_SERVICE_NAME")
    fi

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        echo ""
        echo "Please set these variables before running the test script."
        echo "Example:"
        echo "  export AMI_ANTENNA_API_AUTH_TOKEN='your-token-here'"
        echo "  export AMI_ANTENNA_SERVICE_NAME='Test Worker'"
        exit 1
    fi
}

# Function to setup fault injection environment
setup_fault_injection() {
    export AMI_TEST_FAULT_INJECTION_ENABLED="true"
    export AMI_TEST_WORKER_CRASH_RATE="$CRASH_RATE"
    export AMI_TEST_NETWORK_ERROR_RATE="$NETWORK_ERROR_RATE"
    export AMI_TEST_CORRUPT_IMAGE_RATE="$IMAGE_ERROR_RATE"
    export AMI_TEST_IMAGE_404_RATE="$IMAGE_ERROR_RATE"
    export AMI_TEST_TRANSIENT_ERROR_RATE="$TRANSIENT_ERROR_RATE"

    # Example permanent error images (customize as needed)
    export AMI_TEST_PERMANENT_ERROR_IMAGES="permanent_error_test_1.jpg,permanent_error_test_2.jpg"

    log_info "🧨 Fault injection configured:"
    log_info "  Worker crash rate: ${CRASH_RATE} (${CRASH_RATE}%)"
    log_info "  Network error rate: ${NETWORK_ERROR_RATE} (${NETWORK_ERROR_RATE}%)"
    log_info "  Image error rate: ${IMAGE_ERROR_RATE} (${IMAGE_ERROR_RATE}%)"
    log_info "  Transient error rate: ${TRANSIENT_ERROR_RATE} (${TRANSIENT_ERROR_RATE}%)"
    log_info "  Max restarts: $MAX_RESTARTS"
    log_info "  Restart delay: ${RESTART_DELAY}s"
    log_info "  Pipelines: $PIPELINES"
    echo ""
}

# Function to run worker and handle restarts
run_worker_with_restarts() {
    local restart_count=0
    local total_crashes=0
    local start_time=$(date +%s)

    while [[ $restart_count -lt $MAX_RESTARTS ]]; do
        local worker_start_time=$(date +%s)
        log_info "Starting worker (attempt $((restart_count + 1))/$MAX_RESTARTS)..."

        # Run the worker - it will exit when it crashes or completes normally
        set +e  # Don't exit script on worker failure
        ami worker $PIPELINES
        local exit_code=$?
        set -e

        local worker_end_time=$(date +%s)
        local worker_runtime=$((worker_end_time - worker_start_time))

        if [[ $exit_code -eq 0 ]]; then
            log_success "Worker completed normally after ${worker_runtime}s"
            break
        else
            total_crashes=$((total_crashes + 1))
            log_warn "Worker crashed with exit code $exit_code after ${worker_runtime}s (crash #$total_crashes)"

            restart_count=$((restart_count + 1))

            if [[ $restart_count -lt $MAX_RESTARTS ]]; then
                log_info "Restarting worker in ${RESTART_DELAY}s..."
                sleep "$RESTART_DELAY"
            else
                log_error "Maximum restart attempts reached ($MAX_RESTARTS)"
                break
            fi
        fi
    done

    local end_time=$(date +%s)
    local total_runtime=$((end_time - start_time))

    echo ""
    log_info "=== Test Summary ==="
    log_info "Total runtime: ${total_runtime}s ($((total_runtime / 60))m $((total_runtime % 60))s)"
    log_info "Worker crashes: $total_crashes"
    log_info "Restart attempts: $restart_count"

    if [[ $total_crashes -eq 0 ]]; then
        log_success "No crashes detected - worker ran successfully!"
    else
        log_info "Average time between crashes: $((total_runtime / total_crashes))s"
    fi

    return $total_crashes
}

# Function to cleanup on script exit
cleanup() {
    log_info "Cleaning up..."
    # Kill any background processes if needed
    jobs -p | xargs -r kill 2>/dev/null || true
}

# Main execution
main() {
    echo "🔥 AMI Worker Fault Injection Testing 🔥"
    echo "========================================="

    # Set up cleanup trap
    trap cleanup EXIT INT TERM

    # Check prerequisites
    check_prerequisites

    # Setup fault injection environment
    setup_fault_injection

    log_info "🚀 Starting fault injection test..."

    # Run the worker with automatic restarts
    run_worker_with_restarts
    local crashes=$?

    echo ""
    if [[ $crashes -eq 0 ]]; then
        log_success "✅ Test completed successfully - no crashes!"
        exit 0
    else
        log_warn "⚠️  Test completed with $crashes crashes (this is expected with fault injection)"
        exit 0
    fi
}

main "$@"
