#!/bin/bash
# Full coverage including live BQ + live agent tests — ~15-30 min, ~$1-2 cost.
cd "$(dirname "$0")"
echo "================================================================"
echo "  FULL COVERAGE RUN"
echo "  This will:"
echo "    - Run ~30 unit tests (~30 sec, free)"
echo "    - Run ~12 live BQ tests (~3 min, ~$0.10)"
echo "    - Run ~5 live agent tests (~15-20 min, ~$1)"
echo "  Total: ~20-25 min, ~$1-2"
echo "================================================================"
echo ""
read -p "Continue? [y/N] " ans
[ "$ans" = "y" ] || exit 0

coverage erase
PYTHONPATH=. coverage run -m pytest data_science_tests/ --live -v --tb=short
coverage report --skip-empty
coverage html
echo ""
echo "✓ HTML: $(pwd)/htmlcov/index.html  (full mode — includes live tests)"
