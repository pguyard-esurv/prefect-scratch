#!/bin/bash
# Build script for RPA2 flow container image

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Use the main flow build script
exec "$SCRIPT_DIR/build_flow_images.sh" --flow rpa2 "$@"