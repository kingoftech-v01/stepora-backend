#!/bin/bash
# Switch DNS from AWS to VPS for stepora.app and api.stepora.app
# Run this when ready to go live

set -e

CF_TOKEN="ti6QIZgEipi7JD99_7TvpGqfz8OAVaz076j_cQ0l"
ZONE_ID="9ffc66c3756186d8188a3b90d3ece76f"  # stepora.app
VPS_IP="147.93.47.35"

echo "=== Switching stepora.app production to VPS ==="

# Get current A records
echo "Current DNS records:"
curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=A" \
  -H "Authorization: Bearer $CF_TOKEN" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d['result']:
    print(f\"  {r['name']} -> {r['content']} (id: {r['id']}, proxied: {r['proxied']})\")
"

# Also show CNAME records (CloudFront uses CNAME)
echo ""
echo "Current CNAME records:"
curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=CNAME" \
  -H "Authorization: Bearer $CF_TOKEN" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d['result']:
    print(f\"  {r['name']} -> {r['content']} (id: {r['id']}, proxied: {r['proxied']})\")
"

echo ""
echo "This will update/create A records to point to VPS: $VPS_IP"
echo "Press Enter to continue or Ctrl+C to abort..."
read

# Update each A record for stepora.app
for RECORD_NAME in "stepora.app" "api.stepora.app"; do
    # Check for existing A record
    RECORD_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=A&name=$RECORD_NAME" \
      -H "Authorization: Bearer $CF_TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d['result'] else 'NOT_FOUND')")

    # Also check for CNAME that might conflict
    CNAME_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=CNAME&name=$RECORD_NAME" \
      -H "Authorization: Bearer $CF_TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d['result'] else 'NOT_FOUND')")

    # Delete conflicting CNAME if exists
    if [ "$CNAME_ID" != "NOT_FOUND" ]; then
        echo "Deleting CNAME record for $RECORD_NAME (id: $CNAME_ID)..."
        curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$CNAME_ID" \
          -H "Authorization: Bearer $CF_TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Deleted' if d['success'] else d['errors'])"
    fi

    if [ "$RECORD_ID" = "NOT_FOUND" ]; then
        echo "Creating A record for $RECORD_NAME..."
        curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
          -H "Authorization: Bearer $CF_TOKEN" \
          -H "Content-Type: application/json" \
          --data "{\"type\":\"A\",\"name\":\"$RECORD_NAME\",\"content\":\"$VPS_IP\",\"ttl\":1,\"proxied\":false}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d['success'] else d['errors'])"
    else
        echo "Updating $RECORD_NAME (record $RECORD_ID)..."
        curl -s -X PATCH "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
          -H "Authorization: Bearer $CF_TOKEN" \
          -H "Content-Type: application/json" \
          --data "{\"type\":\"A\",\"content\":\"$VPS_IP\",\"proxied\":false}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d['success'] else d['errors'])"
    fi
done

echo ""
echo "DNS updated. Waiting 10 seconds for propagation..."
sleep 10

# Get SSL certs
echo "Getting SSL certificates..."
certbot --nginx -d stepora.app -d api.stepora.app --non-interactive --agree-tos --redirect 2>&1 | tail -5

echo ""
echo "=== Migration complete ==="
echo "Test: curl -s https://api.stepora.app/api/v1/ | head"
echo "Test: curl -sI https://stepora.app"
