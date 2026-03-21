#!/bin/bash
# =============================================================================
# Stepora API Health Check — Shell Wrapper
# =============================================================================
#
# Usage:
#   ./scripts/qa_api_health_check.sh                                    # localhost:8000
#   ./scripts/qa_api_health_check.sh http://localhost:8000              # explicit local
#   ./scripts/qa_api_health_check.sh https://dpapi.jhpetitfrere.com    # preprod
#   ./scripts/qa_api_health_check.sh https://api.stepora.app           # production
#
# Options (passed through to Python script):
#   --no-color      Disable colored output
#   --no-cleanup    Keep test data after run (for debugging)
#
# Environment variables:
#   API_BASE         Base URL override (same as first positional arg)
#   ADMIN_EMAIL      Admin email for admin-only endpoints
#   ADMIN_PASSWORD   Admin password
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="${SCRIPT_DIR}/qa_api_health_check.py"

# Determine Python interpreter
if [ -f "${SCRIPT_DIR}/../venv/bin/python" ]; then
    PYTHON="${SCRIPT_DIR}/../venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "ERROR: No Python interpreter found. Install Python 3 or activate a virtualenv." >&2
    exit 2
fi

# Check that the Python script exists
if [ ! -f "${PYTHON_SCRIPT}" ]; then
    echo "ERROR: ${PYTHON_SCRIPT} not found." >&2
    exit 2
fi

# Parse arguments: first positional arg that doesn't start with -- is the base URL
BASE_URL=""
EXTRA_ARGS=()

for arg in "$@"; do
    if [[ -z "${BASE_URL}" && "${arg}" != --* ]]; then
        BASE_URL="${arg}"
    else
        EXTRA_ARGS+=("${arg}")
    fi
done

# Build command
CMD=("${PYTHON}" "${PYTHON_SCRIPT}")

if [ -n "${BASE_URL}" ]; then
    CMD+=("--base-url" "${BASE_URL}")
fi

CMD+=("${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}")

# Run
exec "${CMD[@]}"
