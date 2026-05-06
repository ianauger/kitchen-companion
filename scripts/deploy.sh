#!/bin/bash
# ============================================================================
# Sous Chef Deploy — run as kukie on sous-chef CT
# Assumes: docker-compose.yml and .env are next to this script (or in CWD)
# ============================================================================
set -e

# Resolve the directory this script lives in (so paths work from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# If docker-compose.yml is in the project root (one level up from scripts/), use that
if [ -f "$SCRIPT_DIR/../docker-compose.yml" ]; then
  COMPOSE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  COMPOSE_DIR="$SCRIPT_DIR"
fi

echo "=== Sous Chef Deploy ==="

echo "→ Pulling latest image..."
docker pull ghcr.io/ianauger/kitchen-companion:latest

echo "→ Backing up database..."
mkdir -p ~/backups
docker cp kitchen-companion:/app/instance/kitchen_companion.db \
  ~/backups/kitchen_companion_$(date +%Y%m%d_%H%M%S).db 2>/dev/null || \
  echo "  No existing DB to back up"
# Keep only the 10 most recent backups
ls -t ~/backups/*.db 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true

echo "→ Redeploying container..."
docker rm -f kitchen-companion 2>/dev/null || true
docker compose -f "$COMPOSE_DIR/docker-compose.yml" \
  --env-file "$COMPOSE_DIR/.env" up -d

echo "→ Waiting for healthy..."
for i in $(seq 1 15); do
  curl -sf http://localhost:5000/ > /dev/null 2>&1 && break
  sleep 2
done
curl -sf http://localhost:5000/ > /dev/null 2>&1 && echo "  ✓ Container healthy" || echo "  ⚠ Health check timed out"

echo "→ Running migrations..."
docker exec kitchen-companion flask db upgrade

echo "→ Verifying..."
RECIPES=$(curl -s http://localhost:5000/api/recipes?per_page=1 | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['pagination']['total'])" 2>/dev/null || echo "?")
echo "  ✓ $RECIPES recipes in database"

echo "=== Deploy complete ==="
