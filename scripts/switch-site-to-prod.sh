#!/bin/bash
# Switch DNS for stepora.net from AWS ALB to VPS
# Run this when ready to go live with the site vitrine

set -e

CF_TOKEN="ti6QIZgEipi7JD99_7TvpGqfz8OAVaz076j_cQ0l"
ZONE_ID="1408f2944265cd6800a196f6f851331f"  # stepora.net
VPS_IP="147.93.47.35"

echo "=== Switching stepora.net to VPS ==="

# Get current DNS records
echo "Current DNS records for stepora.net:"
curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_TOKEN" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for r in d['result']:
    print(f\"  {r['type']:6s} {r['name']} -> {r['content']} (id: {r['id']}, proxied: {r['proxied']})\")"

echo ""
echo "This will:"
echo "  1. Delete CNAME for stepora.net (pointing to ALB)"
echo "  2. Create A record for stepora.net -> $VPS_IP"
echo "  3. Get SSL certificate"
echo ""
echo "Press Enter to continue or Ctrl+C to abort..."
read

# Delete the existing CNAME for stepora.net (it points to ALB)
CNAME_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=CNAME&name=stepora.net" \
  -H "Authorization: Bearer $CF_TOKEN" | python3 -c "
import sys,json
d=json.load(sys.stdin)
# Find the CNAME that's not www, dkim, or acm-validation
for r in d['result']:
    if r['name'] == 'stepora.net':
        print(r['id'])
        break
else:
    print('NOT_FOUND')
")

if [ "$CNAME_ID" != "NOT_FOUND" ]; then
    echo "Deleting CNAME record for stepora.net (id: $CNAME_ID)..."
    curl -s -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$CNAME_ID" \
      -H "Authorization: Bearer $CF_TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print('Deleted' if d['success'] else d['errors'])"
fi

# Create A record for stepora.net
echo "Creating A record for stepora.net -> $VPS_IP..."
curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $CF_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"type\":\"A\",\"name\":\"stepora.net\",\"content\":\"$VPS_IP\",\"ttl\":1,\"proxied\":false}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d['success'] else d['errors'])"

# Also update www.stepora.net CNAME to point to stepora.net (it should already)
echo "Verifying www.stepora.net CNAME..."
WWW_ID=$(curl -s -X GET "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=CNAME&name=www.stepora.net" \
  -H "Authorization: Bearer $CF_TOKEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['id'] if d['result'] else 'NOT_FOUND')")

if [ "$WWW_ID" = "NOT_FOUND" ]; then
    echo "Creating www.stepora.net CNAME -> stepora.net..."
    curl -s -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
      -H "Authorization: Bearer $CF_TOKEN" \
      -H "Content-Type: application/json" \
      --data "{\"type\":\"CNAME\",\"name\":\"www.stepora.net\",\"content\":\"stepora.net\",\"ttl\":1,\"proxied\":false}" | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK' if d['success'] else d['errors'])"
else
    echo "www.stepora.net already exists (OK)"
fi

echo ""
echo "DNS updated. Waiting 10 seconds for propagation..."
sleep 10

# Get SSL certs
echo "Getting SSL certificates..."
certbot --nginx -d stepora.net -d www.stepora.net --non-interactive --agree-tos --redirect 2>&1 | tail -5

echo ""
echo "=== stepora.net migration complete ==="
echo "Test: curl -sI https://stepora.net"
