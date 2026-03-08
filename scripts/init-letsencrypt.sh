#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# init-letsencrypt.sh
#
# Run ONCE on first deploy to obtain SSL certificates from Let's Encrypt.
# After this, the certbot container in docker-compose.prod.yml handles renewal.
#
# Usage (on EC2):
#   chmod +x scripts/init-letsencrypt.sh
#   sudo bash scripts/init-letsencrypt.sh
# ──────────────────────────────────────────────────────────────────────────────
set -e

# ── CONFIGURE THESE ──────────────────────────────────────────────────────────
DOMAIN="neural-archaeologist.duckdns.org"  # e.g. neural-archaeologist.com
EMAIL="aashikantkumar2@gmail.com"             # used for expiry notifications
STAGING=0                      # set to 1 to test with Let's Encrypt staging CA
# ─────────────────────────────────────────────────────────────────────────────

if [[ "$DOMAIN" == "YOUR_DOMAIN" ]]; then
  echo "ERROR: Edit DOMAIN and EMAIL in scripts/init-letsencrypt.sh first."
  exit 1
fi

COMPOSE_FILE="docker-compose.prod.yml"
DATA_PATH="/etc/letsencrypt"
RSA_KEY_SIZE=4096

echo "==> Checking required commands..."
command -v docker >/dev/null 2>&1 || { echo "docker not found"; exit 1; }
command -v docker compose >/dev/null 2>&1 || { echo "docker compose not found"; exit 1; }

# Step 1 — Create dummy cert so nginx can start
# Use --entrypoint "" to clear certbot's default entrypoint, then run sh -c
echo "==> Creating dummy certificate for $DOMAIN ..."
docker compose -f "$COMPOSE_FILE" run --rm --entrypoint "" certbot \
  sh -c "mkdir -p $DATA_PATH/live/$DOMAIN && \
         openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE -days 1 \
           -keyout $DATA_PATH/live/$DOMAIN/privkey.pem \
           -out $DATA_PATH/live/$DOMAIN/fullchain.pem \
           -subj /CN=localhost"

# Verify dummy cert was actually created
echo "==> Verifying dummy certificate ..."
docker compose -f "$COMPOSE_FILE" run --rm --entrypoint "" certbot \
  sh -c "test -f $DATA_PATH/live/$DOMAIN/fullchain.pem && echo 'OK — dummy cert exists' || (echo 'ERROR: dummy cert not found!' && exit 1)"

# Step 2 — Start all services (nginx will use the dummy cert)
echo "==> Starting all services ..."
docker compose -f "$COMPOSE_FILE" up --force-recreate -d

# Wait for nginx to be responding on port 80
echo "==> Waiting for nginx to be ready on port 80 ..."
for i in $(seq 1 30); do
  if docker compose -f "$COMPOSE_FILE" exec -T nginx wget -q --spider http://localhost:80/ 2>/dev/null; then
    echo "    nginx is up!"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "WARNING: nginx may not be ready yet, proceeding anyway..."
    docker compose -f "$COMPOSE_FILE" logs nginx --tail 5
  fi
  sleep 2
done

# Step 3 — Request a real certificate
echo "==> Requesting Let's Encrypt certificate for $DOMAIN ..."
STAGING_FLAG=""
if [[ $STAGING -eq 1 ]]; then
  STAGING_FLAG="--staging"
  echo "WARNING: Running in staging mode — certificate will NOT be trusted by browsers."
fi

docker compose -f "$COMPOSE_FILE" run --rm --entrypoint "" certbot \
  certbot certonly --webroot \
    --webroot-path=/var/www/certbot \
    $STAGING_FLAG \
    --email "$EMAIL" \
    --rsa-key-size "$RSA_KEY_SIZE" \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d "$DOMAIN"

# Step 4 — Reload nginx with the real cert
echo "==> Reloading nginx ..."
docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload

echo ""
echo "✅  SSL certificate obtained for $DOMAIN"
echo "    Nginx is running with HTTPS."
echo "    Certbot container will auto-renew every 12 hours."
