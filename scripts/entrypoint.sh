#!/bin/bash
# ============================================================================
# Docker Entrypoint - Kitchen Companion
# ============================================================================
# Handles first-run DB setup, migrations, and admin bootstrap.
# ============================================================================

set -e

echo "=== Kitchen Companion Startup ==="

# Check if DB exists
DB_PATH="/app/instance/kitchen_companion.db"

if [ ! -f "$DB_PATH" ]; then
    echo "→ No database found, creating..."
    flask db upgrade
    echo "  ✓ Database created"
    
    # Bootstrap admin if credentials provided
    if [ -n "${KITCHEN_COMPANION_USERNAME:-}" ] && [ -n "${KITCHEN_COMPANION_PASSWORD:-}" ]; then
        echo "→ Bootstrapping admin user..."
        python scripts/bootstrap_admin.py --username "$KITCHEN_COMPANION_USERNAME" --password "$KITCHEN_COMPANION_PASSWORD"
    fi
else
    echo "→ Database found, running migrations..."
    flask db upgrade
    echo "  ✓ Migrations complete"
fi

echo "→ Starting application..."
exec "$@"
