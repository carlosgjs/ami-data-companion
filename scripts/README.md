# Worker Fault Injection Testing

This directory contains tools for testing the robustness of the AMI worker by simulating various error conditions that can occur in production environments.

## Overview

The fault injection system allows you to simulate:

- **Worker crashes** during job processing
- **Network errors** during API calls (job fetching, result posting)
- **Image errors** (404 Not Found, corrupt data)
- **Transient failures** that should trigger task re-queuing
- **Permanent failures** for specific images

## Quick Start

1. **Set up your environment variables:**
   ```bash
   export AMI_ANTENNA_API_AUTH_TOKEN="your-token-here"
   export AMI_ANTENNA_SERVICE_NAME="Test Worker"
   # Optional: export AMI_ANTENNA_API_BASE_URL="https://your-antenna-api.com/api/v2"
   ```

2. **Choose a test scenario:**
   ```bash
   source scripts/test_scenarios.env
   test_medium  # Configure moderate error rates
   ```

3. **Run the test:**
   ```bash
   ./scripts/test_worker_robustness.sh moth_binary
   ```
## Environment Variables

### Required
- `AMI_ANTENNA_API_AUTH_TOKEN` - Your Antenna API authentication token
- `AMI_ANTENNA_SERVICE_NAME` - Service name for testing

### Fault Injection Controls
- `AMI_TEST_FAULT_INJECTION_ENABLED` - Set to "true" to enable (default: false)
- `AMI_TEST_WORKER_CRASH_RATE` - Probability of worker crashes (0.0-1.0)
- `AMI_TEST_NETWORK_ERROR_RATE` - Probability of network errors (0.0-1.0)
- `AMI_TEST_CORRUPT_IMAGE_RATE` - Probability of corrupt images (0.0-1.0)
- `AMI_TEST_IMAGE_404_RATE` - Probability of image 404 errors (0.0-1.0)
- `AMI_TEST_TRANSIENT_ERROR_RATE` - Probability of transient failures (0.0-1.0)
- `AMI_TEST_PERMANENT_ERROR_IMAGES` - Comma-separated list of images that always fail

### Test Script Controls
- `MAX_RESTARTS` - Maximum worker restarts before giving up (default: 50)
- `RESTART_DELAY` - Seconds to wait before restarting crashed worker (default: 5)


## What to Verify

When running these tests, you should verify that the Antenna service:

1. **Handles worker crashes gracefully**
   - Tasks are re-queued when workers crash
   - New workers can pick up failed tasks
   - No tasks are lost permanently

2. **Handles network errors appropriately**
   - Transient network errors trigger retries
   - Persistent network errors are logged but don't block other tasks
   - API rate limiting and backoff work correctly

3. **Handles image errors correctly**
   - Permanent errors (404, corrupt) are reported as failed tasks
   - Transient image errors trigger retries
   - Failed images don't crash the entire batch

4. **Maintains system stability**
   - High error rates don't cause cascading failures
   - Error reporting is accurate and complete
   - System performance degrades gracefully under stress

## Example Usage

```bash
# Basic testing
source scripts/test_scenarios.env
test_medium
./scripts/test_worker_robustness.sh

# High-stress testing
test_heavy
RESTART_DELAY=2 MAX_RESTARTS=100 ./scripts/test_worker_robustness.sh moth_binary
