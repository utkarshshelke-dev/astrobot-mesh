#!/bin/bash
# Fast unit-test coverage — ~30 seconds, $0 cost.
cd "$(dirname "$0")"
coverage erase
PYTHONPATH=. coverage run -m pytest data_science_tests/ -v --tb=short
coverage report --skip-empty
coverage html
echo ""
echo "✓ HTML: $(pwd)/htmlcov/index.html  (fast mode — no live tests)"
