#!/bin/bash
# Verify Stepora production deployment
# Usage: ./scripts/verify_prod.sh [api_url] [frontend_url]

set -e

API_BASE="${1:-https://api.stepora.app}"
FRONTEND="${2:-https://stepora.app}"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

pass=0
fail=0
warn=0

check() {
  local name=$1
  local url=$2
  local expected=$3

  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

  if [ "$status" = "$expected" ]; then
    echo -e "  ${GREEN}✓${NC} $name ($status)"
    pass=$((pass + 1))
  elif [ "$status" = "000" ]; then
    echo -e "  ${RED}✗${NC} $name (TIMEOUT/UNREACHABLE)"
    fail=$((fail + 1))
  else
    echo -e "  ${RED}✗${NC} $name (expected $expected, got $status)"
    fail=$((fail + 1))
  fi
}

echo "================================================"
echo "  Stepora Production Verification"
echo "  API: $API_BASE"
echo "  Frontend: $FRONTEND"
echo "  Time: $(date)"
echo "================================================"
echo ""

echo "[HEALTH CHECKS]"
check "Liveness" "$API_BASE/health/liveness/" "200"
check "Readiness" "$API_BASE/health/readiness/" "200"
check "Health" "$API_BASE/health/" "200"

echo ""
echo "[API ENDPOINTS]"
check "Auth login page" "$API_BASE/api/v1/auth/login/" "405"  # GET not allowed
check "Plans list" "$API_BASE/api/v1/subscriptions/plans/" "200"
check "Admin page" "$API_BASE/admin/login/" "200"

echo ""
echo "[FRONTEND]"
check "Frontend loads" "$FRONTEND" "200"
# Assets dir listing is typically disabled (403) or returns SPA fallback (200)
assets_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$FRONTEND/assets/" 2>/dev/null || echo "000")
if [ "$assets_status" = "200" ] || [ "$assets_status" = "403" ]; then
  echo -e "  ${GREEN}✓${NC} Frontend assets reachable ($assets_status)"
  pass=$((pass + 1))
elif [ "$assets_status" = "000" ]; then
  echo -e "  ${RED}✗${NC} Frontend assets (TIMEOUT/UNREACHABLE)"
  fail=$((fail + 1))
else
  echo -e "  ${RED}✗${NC} Frontend assets (unexpected $assets_status)"
  fail=$((fail + 1))
fi

echo ""
echo "[SSL CERTIFICATES]"
# Check SSL expiry
for domain in "$API_BASE" "$FRONTEND"; do
  host=$(echo "$domain" | sed 's|https://||' | sed 's|/.*||')
  expiry=$(echo | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  if [ -n "$expiry" ]; then
    echo -e "  ${GREEN}✓${NC} $host SSL expires: $expiry"
    pass=$((pass + 1))
  else
    echo -e "  ${YELLOW}?${NC} $host SSL check failed"
    warn=$((warn + 1))
  fi
done

echo ""
echo "[DATABASE]"
# This requires ECS exec access, so just check API can serve data
check "API serves data" "$API_BASE/api/v1/subscriptions/plans/" "200"

echo ""
echo "[WEBSOCKET]"
# Basic WS check - just verify the upgrade endpoint exists
ws_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE/ws/" 2>/dev/null || echo "000")
if [ "$ws_status" = "400" ] || [ "$ws_status" = "426" ]; then
  echo -e "  ${GREEN}✓${NC} WebSocket endpoint reachable ($ws_status = upgrade expected)"
  pass=$((pass + 1))
else
  echo -e "  ${YELLOW}?${NC} WebSocket endpoint status: $ws_status"
  warn=$((warn + 1))
fi

echo ""
echo "================================================"
echo "  RESULTS"
echo "  Passed: $pass"
echo "  Failed: $fail"
echo "  Warnings: $warn"
echo "================================================"

if [ $fail -gt 0 ]; then
  echo -e "  ${RED}DEPLOY VERIFICATION FAILED${NC}"
  exit 1
else
  echo -e "  ${GREEN}DEPLOY VERIFICATION PASSED${NC}"
  exit 0
fi
