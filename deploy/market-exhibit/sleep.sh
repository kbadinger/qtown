#!/usr/bin/env bash
# Sleep the Market exhibit — stop paying while nothing's being demoed. The public
# site falls back to dormant ("—"), which is honest, not broken.
set -euo pipefail
cd "$(dirname "$0")"
docker compose down
echo "Market exhibit is asleep. Dashboard/landing will show Market as dormant."
