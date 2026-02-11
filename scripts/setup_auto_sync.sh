#!/bin/bash
# Quick setup script for Railway Cron Job
# Run this after setting up Railway Cron Job manually, or use as reference

RAILWAY_URL="${RAILWAY_APP_URL:-https://superb-smile-production.up.railway.app}"
SYNC_KEY="${SYNC_TRIGGER_KEY:-}"

echo "=== Operators Vault - Automatic Sync Setup ==="
echo ""
echo "Railway Cron Job Configuration:"
echo "  Schedule: 0 */3 * * *  (every 3 hours)"
echo "  Command: curl -X GET \"$RAILWAY_URL/trigger-sync\""
if [ -n "$SYNC_KEY" ]; then
    echo "  (With SYNC_TRIGGER_KEY: curl -X GET \"$RAILWAY_URL/trigger-sync?key=$SYNC_KEY\")"
fi
echo ""
echo "Steps to set up in Railway Dashboard:"
echo "  1. Go to: https://railway.app/project/[your-project]"
echo "  2. Click 'New' → 'Cron Job'"
echo "  3. Set schedule: 0 */3 * * *"
echo "  4. Set command: curl -X GET \"$RAILWAY_URL/trigger-sync\""
echo "  5. Save"
echo ""
echo "Test manually:"
echo "  curl -X GET \"$RAILWAY_URL/trigger-sync\""
echo ""
echo "Check status:"
echo "  curl \"$RAILWAY_URL/stats\""
