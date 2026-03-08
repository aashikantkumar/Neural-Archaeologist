#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# deploy.sh — Zero-downtime redeploy on the EC2 instance
#
# Usage (on EC2, from project root):
#   bash scripts/deploy.sh
# ──────────────────────────────────────────────────────────────────────────────
set -e

COMPOSE_FILE="docker-compose.prod.yml"

echo "==> Pulling latest code ..."
git pull origin main

echo "==> Building new images ..."
docker compose -f "$COMPOSE_FILE" build --no-cache backend frontend

echo "==> Restarting services (rolling) ..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps backend frontend

echo "==> Pruning unused images ..."
docker image prune -f

echo "==> Service status:"
docker compose -f "$COMPOSE_FILE" ps

echo "✅  Deploy complete."
