#!/usr/bin/env bash
# ============================================================
# run_tests.sh - Run all Astrobot deterministic tests
# ============================================================
#
# Usage:
#   ./run_tests.sh              # Run all tests
#   ./run_tests.sh -v           # Verbose
#   ./run_tests.sh -k channel   # Only tests matching 'channel'
#   ./run_tests.sh --failed     # Re-run last failing tests
#
# ============================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Make sure pytest is installed
if ! python3 -c "import pytest" 2>/dev/null; then
    echo "Installing pytest..."
    pip install pytest --quiet --break-system-packages 2>/dev/null \
        || pip install pytest --quiet
fi

echo "================================================================"
echo "  ASTROBOT TEST SUITE"
echo "  $(date)"
echo "================================================================"
echo ""

# Default: run all tests
EXTRA_ARGS="$@"
if [ -z "$EXTRA_ARGS" ]; then
    EXTRA_ARGS="-v"
fi

python3 -m pytest tests/ $EXTRA_ARGS

EXIT_CODE=$?

echo ""
echo "================================================================"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ✓ ALL TESTS PASSED"
else
    echo "  ✗ SOME TESTS FAILED (exit code $EXIT_CODE)"
fi
echo "================================================================"

exit $EXIT_CODE