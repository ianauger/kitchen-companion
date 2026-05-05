#!/bin/bash
# ============================================================================
# Sous Chef Deploy Script
# ============================================================================
# Performs a safe deploy with backup, migration, and rollback capability.
#
# Usage:
#   ./scripts/deploy.sh [--skip-backup] [--skip-migrate]
#
# Requires: docker, docker-compose on the target host
# Run as: root or user with docker permissions
# ============================================================================

set -euo pipefail

COMPOSE_DIR="/root/kitchen-companion"
COMPOSE_FILE="${COMPOSE_DIR}/docker-compose.yml"
BACKUP_DIR="${COMPOSE_DIR}/backups"
CONTAINER="kitchen-companion"
IMAGE="ghcr.io/ianauger/kitchen-companion:latest"
DB_PATH="/app/instance/kitchen_companion.db"

SKIP_BACKUP=false
SKIP_MIGRATE=false

for arg in "$@"; do
    case "$arg" in
        --skip-backup) SKIP_BACKUP=true ;;
        --skip-migrate) SKIP_MIGRATE=true ;;
    esac
done

echo "=== Sous Chef Deploy ==="
echo "Image: $IMAGE"
echo "Backup: $([ "$SKIP_BACKUP" = true ] && echo 'SKIPPED' || echo 'enabled')"
echo "Migrate: $([ "$SKIP_MIGRATE" = true ] && echo 'SKIPPED' || echo 'enabled')"
echo

# --------------------------------------------------------------------------
# 1. Backup database
# --------------------------------------------------------------------------
if [ "$SKIP_BACKUP" = false ]; then
    echo "→ Backing up database..."
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_FILE="${BACKUP_DIR}/kitchen_companion_$(date +%Y%m%d_%H%M%S).db"
    
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
        docker cp "${CONTAINER}:${DB_PATH}" "$BACKUP_FILE" 2>/dev/null && \
            echo "  ✓ Backup saved: $BACKUP_FILE" || \
            echo "  ⚠ No existing DB to back up (fresh deploy)"
    else
        # Container not running — check for stopped container
        STOPPED=$(docker ps -a --format '{{.Names}}' | grep "^${CONTAINER}$" || true)
        if [ -n "$STOPPED" ]; then
            docker cp "${CONTAINER}:${DB_PATH}" "$BACKUP_FILE" 2>/dev/null && \
                echo "  ✓ Backup saved from stopped container: $BACKUP_FILE" || \
                echo "  ⚠ Could not copy DB from stopped container"
        else
            echo "  ⚠ No container found, skipping backup"
        fi
    fi
    
    # Keep only last 10 backups
    ls -t "${BACKUP_DIR}"/*.db 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true
else
    echo "→ Backup skipped"
fi

# --------------------------------------------------------------------------
# 2. Pull latest image
# --------------------------------------------------------------------------
echo "→ Pulling $IMAGE..."
docker pull "$IMAGE"

# --------------------------------------------------------------------------
# 3. Recreate container with new image
# --------------------------------------------------------------------------
echo "→ Restarting container..."
docker rm -f "$CONTAINER" 2>/dev/null || true

cd "$COMPOSE_DIR"
docker compose -f "$COMPOSE_FILE" up -d

# Wait for healthy
echo "→ Waiting for container to be ready..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:5000/ > /dev/null 2>&1; then
        echo "  ✓ Container healthy"
        break
    fi
    sleep 2
    if [ "$i" -eq 15 ]; then
        echo "  ✗ Container failed to become healthy"
        echo "  Logs:"
        docker logs --tail 30 "$CONTAINER"
        exit 1
    fi
done

# --------------------------------------------------------------------------
# 4. Run migrations
# --------------------------------------------------------------------------
if [ "$SKIP_MIGRATE" = false ]; then
    echo "→ Running database migrations..."
    docker exec "$CONTAINER" flask db upgrade 2>&1 | tail -5 || {
        echo "  ✗ Migration failed!"
        echo "  Restore backup with: docker cp ${BACKUP_FILE} ${CONTAINER}:${DB_PATH}"
        exit 1
    }
    echo "  ✓ Migrations complete"
else
    echo "→ Migrations skipped"
fi

# --------------------------------------------------------------------------
# 5. Verify
# --------------------------------------------------------------------------
echo "→ Verifying API..."
HEALTH=$(curl -s http://localhost:5000/api/recipes?per_page=1)
if echo "$HEALTH" | grep -q '"recipes"'; then
    TOTAL=$(echo "$HEALTH" | python3 -c "import json,sys; print(json.load(sys.stdin)['pagination']['total'])" 2>/dev/null || echo "?")
    echo "  ✓ API healthy — $TOTAL recipes in DB"
else
    echo "  ✗ API check failed"
    docker logs --tail 10 "$CONTAINER"
    exit 1
fi

echo
echo "=== Deploy complete ==="
