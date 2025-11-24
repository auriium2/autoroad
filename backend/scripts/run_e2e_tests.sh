#!/usr/bin/env bash
#
# Run end-to-end integration tests
#
# These tests fetch real data from Fireroad and run the full optimizer flow.
# They are slower and require network access, so they're excluded from normal test runs.
#

set -e

echo "========================================"
echo "Running End-to-End Integration Tests"
echo "========================================"
echo ""
echo "These tests:"
echo "  - Fetch real course and requirement data from Fireroad"
echo "  - Run the full optimizer with prerequisites and requirements"
echo "  - Verify common degree combinations remain feasible"
echo ""
echo "This may take 30-60 seconds..."
echo ""

# Run only e2e tests with verbose output
uv run pytest -v -s -m e2e tests/

echo ""
echo "========================================"
echo "E2E Tests Complete"
echo "========================================"
