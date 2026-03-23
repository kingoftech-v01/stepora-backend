#!/bin/bash
# Run tests app by app with coverage, collecting results
# This uses less memory than running everything at once

export DJANGO_SETTINGS_MODULE=config.settings.testing
PYTEST="venv/bin/python -m pytest"
REPORT="/tmp/app_test_results.txt"
COV_DIR="/tmp/cov_data"

mkdir -p "$COV_DIR"
> "$REPORT"

TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_ERRORS=0
TOTAL_SKIPPED=0

# List all test directories
APPS=(
    apps/ai
    apps/buddies
    apps/calendar
    apps/chat
    apps/circles
    apps/dreams
    apps/gamification
    apps/leagues
    apps/notifications
    apps/plans
    apps/social
    apps/store
    apps/subscriptions
    apps/users
    core
    integrations
)

for app in "${APPS[@]}"; do
    echo "--- Testing $app ---" | tee -a "$REPORT"

    # Run with coverage, collect to separate data file
    result=$($PYTEST "$app/" \
        --cov="$app" \
        --cov-report=term \
        --cov-config=.coveragerc \
        --cov-append \
        -o addopts= \
        --tb=line \
        -q \
        --no-header \
        --timeout=30 \
        2>&1)

    echo "$result" >> "$REPORT"

    # Extract counts from last line (e.g., "123 passed, 2 failed, 1 error")
    summary=$(echo "$result" | tail -5 | grep -E "passed|failed|error|no tests")
    echo "  $summary" | tee -a "$REPORT"

    # Parse numbers
    p=$(echo "$summary" | grep -oP '\d+(?= passed)' || echo 0)
    f=$(echo "$summary" | grep -oP '\d+(?= failed)' || echo 0)
    e=$(echo "$summary" | grep -oP '\d+(?= error)' || echo 0)
    s=$(echo "$summary" | grep -oP '\d+(?= skipped)' || echo 0)

    TOTAL_PASSED=$((TOTAL_PASSED + ${p:-0}))
    TOTAL_FAILED=$((TOTAL_FAILED + ${f:-0}))
    TOTAL_ERRORS=$((TOTAL_ERRORS + ${e:-0}))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + ${s:-0}))

    echo "" >> "$REPORT"
done

echo "" | tee -a "$REPORT"
echo "========================================" | tee -a "$REPORT"
echo "GRAND TOTAL" | tee -a "$REPORT"
echo "========================================" | tee -a "$REPORT"
echo "Passed:  $TOTAL_PASSED" | tee -a "$REPORT"
echo "Failed:  $TOTAL_FAILED" | tee -a "$REPORT"
echo "Errors:  $TOTAL_ERRORS" | tee -a "$REPORT"
echo "Skipped: $TOTAL_SKIPPED" | tee -a "$REPORT"
echo "========================================" | tee -a "$REPORT"

# Now generate combined coverage report
echo "" | tee -a "$REPORT"
echo "=== COVERAGE REPORT ===" | tee -a "$REPORT"
venv/bin/python -m coverage report --rcfile=.coveragerc 2>&1 | tee -a "$REPORT"

echo ""
echo "Full results saved to $REPORT"
