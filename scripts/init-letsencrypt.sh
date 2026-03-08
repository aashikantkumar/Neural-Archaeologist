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
echo "==> Creating dummy certificate for $DOMAIN ..."
docker compose -f "$COMPOSE_FILE" run --rm --entrypoint "\
  openssl req -x509 -nodes -newkey rsa:$RSA_KEY_SIZE -days 1 \
    -keyout '$DATA_PATH/live/$DOMAIN/privkey.pem' \
    -out '$DATA_PATH/live/$DOMAIN/fullchain.pem' \
    -subj '/CN=localhost'" certbot

# Step 2 — Start nginx with the dummy cert
echo "==> Starting nginx ..."
docker compose -f "$COMPOSE_FILE" up --force-recreate -d nginx

# Step 3 — Request a real certificate
# NOTE: We keep the dummy cert in place so nginx stays running (nginx would
# crash if the cert files vanished). With --force-renewal certbot overwrites
# the dummy cert while nginx is alive to serve the ACME challenge.
echo "==> Requesting Let's Encrypt certificate for $DOMAIN ..."
STAGING_FLAG=""
if [[ $STAGING -eq 1 ]]; then
  STAGING_FLAG="--staging"
  echo "WARNING: Running in staging mode — certificate will NOT be trusted by browsers."
fi

docker compose -f "$COMPOSE_FILE" run --rm --entrypoint "\
  certbot certonly --webroot \
    --webroot-path=/var/www/certbot \
    $STAGING_FLAG \
    --email $EMAIL \
    --rsa-key-size $RSA_KEY_SIZE \
    --agree-tos \
    --no-eff-email \
    --force-renewal \
    -d $DOMAIN" certbot

# Step 5 — Reload nginx with the real cert
echo "==> Reloading nginx ..."
docker compose -f "$COMPOSE_FILE" exec nginx nginx -s reload

echo ""
echo "✅  SSL certificate obtained for $DOMAIN"
echo "    Nginx is running with HTTPS."
echo "    Certbot container will auto-renew every 12 hours."
