#!/usr/bin/env bash
# Runs the smoke test inside a python container attached to the compose network,
# so it talks to the emulators by service name. Host needs only docker.
set -euo pipefail

LOCAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$LOCAL_DIR/.." && pwd)"

# Discover the compose project's network so the runner can reach the emulators
# by service name (pubsub / firestore).
PROJECT_NAME="$(basename "$LOCAL_DIR")"
NETWORK="$(docker network ls --format '{{.Name}}' | grep -E "${PROJECT_NAME}_default$" | head -1 || true)"
if [ -z "$NETWORK" ]; then
  # Fallback: compose default network naming.
  NETWORK="${PROJECT_NAME}_default"
fi

echo "Using docker network: $NETWORK"

docker run --rm \
  --network "$NETWORK" \
  -e PUBSUB_EMULATOR_HOST=pubsub:8085 \
  -e FIRESTORE_EMULATOR_HOST=firestore:8086 \
  -e PUBSUB_PROJECT_ID="${PUBSUB_PROJECT_ID:-perditio-platform}" \
  -e PUBSUB_TOPIC="${PUBSUB_TOPIC:-reporium-events}" \
  -e PUBSUB_SUBSCRIPTION="${PUBSUB_SUBSCRIPTION:-reporium-events-smoke}" \
  -e GOOGLE_CLOUD_PROJECT="${PUBSUB_PROJECT_ID:-perditio-platform}" \
  -e PYTHONPATH=/app \
  -v "$REPO_ROOT":/app \
  -w /app \
  python:3.12-slim \
  bash -c "pip install --quiet 'google-cloud-pubsub>=2.20' 'google-cloud-firestore>=2.16' && python local/scripts/smoke.py"
