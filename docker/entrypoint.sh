#!/usr/bin/env sh
set -e

DATA_DIR="/home/node/.n8n"
IMPORT_SENTINEL="$DATA_DIR/.workflows_imported"

if [ ! -f "$IMPORT_SENTINEL" ]; then
  echo "[n8n-init] Importing workflows from /data/workflows..."
  n8n import:workflow --input=/data/workflows || true
  touch "$IMPORT_SENTINEL"
  echo "[n8n-init] Import complete."
fi

exec n8n

