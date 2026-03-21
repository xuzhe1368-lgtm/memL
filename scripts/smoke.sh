#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${1:-http://127.0.0.1:8000}"
TOKEN="${2:-}"
if [[ -z "$TOKEN" ]]; then
  echo "Usage: $0 <base_url> <token>"
  exit 1
fi

echo "[1/3] health"
curl -fsS "$BASE_URL/health/live" | jq . || curl -fsS "$BASE_URL/health/live"

ID=$(date +%s)
TEXT="smoke-$ID"
echo "[2/3] write"
curl -fsS -X POST "$BASE_URL/memory" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"text\":\"$TEXT\",\"tags\":[\"smoke\"]}" >/tmp/meml_smoke_write.json
cat /tmp/meml_smoke_write.json

echo "[3/3] search"
curl -fsS "$BASE_URL/memory?q=$TEXT&limit=1" \
  -H "Authorization: Bearer $TOKEN"
