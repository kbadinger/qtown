#!/usr/bin/env bash
# Wake the live Market exhibit. Builds the image (repo-root context) and starts
# market + driver + cloudflared. Safe to re-run — it's idempotent.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "No .env found. Copy .env.example to .env and set TUNNEL_TOKEN first." >&2
  exit 1
fi

docker compose up -d --build
echo
echo "Market exhibit is waking. Check it:"
echo "  docker compose ps"
echo "  docker compose logs -f market-driver   # watch orders being placed"
echo "  curl https://<your-hostname>/api/orderbook?resource=gold"
