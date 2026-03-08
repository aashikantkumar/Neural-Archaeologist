# Deploying Neural Archaeologist on AWS with Docker

## Architecture

```
Internet (port 80 / 443)
        │
  ┌─────┴──────────────────────────────────────┐
  │  EC2 Instance (t3.medium or larger)         │
  │                                             │
  │  ┌─────────────────────────────────────┐   │
  │  │  Nginx container  :80 / :443        │   │
  │  │  • HTTPS termination (Let's Encrypt)│   │
  │  │  • /api/* → backend                 │   │
  │  │  • /socket.io/* → backend (WS)      │   │
  │  │  • /* → frontend                    │   │
  │  └──────────┬──────────────┬───────────┘   │
  │             │              │                │
  │  ┌──────────┴──┐  ┌────────┴──────┐        │
  │  │  Backend    │  │  Frontend     │        │
  │  │  FastAPI    │  │  React/Nginx  │        │
  │  │  :8000      │  │  :80          │        │
  │  └──────┬──────┘  └───────────────┘        │
  │         │                                   │
  │  ┌──────┴──────┐                           │
  │  │  PostgreSQL │  (or AWS RDS)              │
  │  │  :5432      │                           │
  │  └─────────────┘                           │
  └─────────────────────────────────────────────┘
```

**Domain flow:** Route 53 → EC2 Elastic IP → Nginx → services

---

## Step 1 — Create an AWS Account & IAM User

1. Go to [aws.amazon.com](https://aws.amazon.com) and create an account.
2. In IAM, create a user with **EC2FullAccess** and **Route53FullAccess** (or use root for simplicity).
3. Save the Access Key ID and Secret for the AWS CLI.

---

## Step 2 — Register / Transfer a Domain

### Option A — Register via Route 53 (easiest)
1. Console → **Route 53** → **Register Domain**
2. Search for `your-domain.com`, add to cart, complete purchase (~$12/year for `.com`).
3. Route 53 automatically creates a **Hosted Zone**.

### Option B — Use an existing domain registrar
1. In Route 53, **Create Hosted Zone** for your domain.
2. Copy the 4 **NS records** Route 53 gives you.
3. Go to your registrar, replace nameservers with those 4 NS records.
4. DNS propagation takes up to 48 h (usually < 1 h).

---

## Step 3 — Launch an EC2 Instance

1. Console → **EC2** → **Launch Instance**
2. Settings:
   - **AMI**: Ubuntu 24.04 LTS (64-bit x86)
   - **Instance type**: `t3.medium` (2 vCPU, 4 GB RAM) — minimum for this stack
   - **Key pair**: Create a new `.pem` key, download it
   - **Storage**: 20 GB gp3 (SSD)
3. **Security Group** — add inbound rules:

   | Type  | Protocol | Port | Source    |
   |-------|----------|------|-----------|
   | SSH   | TCP      | 22   | My IP     |
   | HTTP  | TCP      | 80   | 0.0.0.0/0 |
   | HTTPS | TCP      | 443  | 0.0.0.0/0 |

4. Launch and wait for the instance to be in **Running** state.

---

## Step 4 — Assign an Elastic IP

1. EC2 → **Elastic IPs** → **Allocate Elastic IP address**
2. Select the new IP → **Actions** → **Associate Elastic IP address**
3. Choose your instance → **Associate**
4. **Note this IP address** — you will point your DNS to it.

---

## Step 5 — Point Domain DNS to EC2

1. Route 53 → **Hosted Zones** → your domain
2. **Create Record**:
   - Record name: `@` (or blank, for root domain)
   - Record type: **A**
   - Value: your Elastic IP
   - TTL: 300
3. Also create a `www` CNAME pointing to the root domain (or another A record).

Wait a few minutes for DNS to propagate. Verify with:
```bash
dig +short yourdomain.com
# should return your Elastic IP
```

---

## Step 6 — Set Up the EC2 Instance

SSH into your instance:
```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@YOUR_ELASTIC_IP
```

Install Docker and Docker Compose:
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
newgrp docker              # apply group without re-login

# Verify
docker --version           # Docker 25+
docker compose version     # Docker Compose 2.x
```

---

## Step 7 — Clone the Repository

```bash
# Install git
sudo apt install git -y

# Clone your repo (use HTTPS or SSH)
git clone https://github.com/YOUR_USERNAME/Neural-Archaeologist.git
cd Neural-Archaeologist
```

---

## Step 8 — Configure Environment

```bash
# Copy the example env file
cp .env.prod.example .env.prod

# Edit with your real values
nano .env.prod
```

Fill in:
- `DOMAIN_NAME` — your domain, e.g. `neural-archaeologist.com`
- `POSTGRES_PASSWORD` — a strong random password
- `DATABASE_URL` — uses the postgres password above
- `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com)
- `SERPAPI_API_KEY` — from [serpapi.com](https://serpapi.com)
- `SECRET_KEY` — run `python3 -c "import secrets; print(secrets.token_hex(32))"`

---

## Step 9 — Update Nginx Config with Your Domain

```bash
# Replace YOUR_DOMAIN with your actual domain in the nginx config
sed -i 's/YOUR_DOMAIN/neural-archaeologist.com/g' nginx/nginx.conf
```

---

## Step 10 — Obtain SSL Certificate (Let's Encrypt)

Edit the script first:
```bash
nano scripts/init-letsencrypt.sh
# Set DOMAIN and EMAIL at the top of the file
```

Run it:
```bash
chmod +x scripts/init-letsencrypt.sh
sudo bash scripts/init-letsencrypt.sh
```

This will:
1. Create a temporary self-signed cert so Nginx can start
2. Request a real cert from Let's Encrypt via HTTP-01 challenge
3. Reload Nginx with the real cert

---

## Step 11 — Start All Services

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Check that everything is running:
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

Test your deployment:
```bash
curl https://your-domain.com/health
# Expected: {"status":"healthy","version":"2.0.0","database":"connected"}
```

Open `https://your-domain.com` in your browser — you should see the app with a valid SSL padlock.

---

## Redeploying After Code Changes

```bash
# On the EC2 instance, from the project root:
bash scripts/deploy.sh
```

This pulls latest code, rebuilds backend + frontend images, and restarts them with zero downtime.

---

## Optional: Use AWS RDS Instead of Containerised PostgreSQL

For production-grade databases, use AWS RDS (managed, automatic backups, Multi-AZ).

1. RDS → **Create Database** → PostgreSQL 15
2. Use the same VPC as your EC2 instance
3. In the Security Group for RDS, allow port 5432 **from the EC2 Security Group**
4. Set `DATABASE_URL` in `.env.prod` to the RDS endpoint:
   ```
   DATABASE_URL=postgresql://admin:password@yourdb.xxxx.rds.amazonaws.com:5432/neural_archaeologist
   ```
5. Comment out the `db` service in `docker-compose.prod.yml`

---

## Optional: GitHub Actions CI/CD

Create `.github/workflows/deploy.yml` to auto-deploy on every push to `main`:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to EC2
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd ~/Neural-Archaeologist
            bash scripts/deploy.sh
```

Add to GitHub Secrets:
- `EC2_HOST` — your Elastic IP
- `EC2_SSH_KEY` — contents of your `.pem` file

---

## Cost Estimate (Monthly)

| Resource            | Type         | ~Cost/month |
|---------------------|--------------|-------------|
| EC2 t3.medium       | On-demand    | ~$30        |
| Elastic IP          | (free if attached) | $0   |
| RDS db.t3.micro     | Optional     | ~$15        |
| Route 53 Hosted Zone| 1 zone       | $0.50       |
| SSL Certificate     | Let's Encrypt| Free        |
| Domain (.com)       | /year        | $1/month    |
| **Total**           |              | **~$32–47** |

Use a **t3.small** (~$15/month) if traffic is low.

---

## Useful Commands

```bash
# View logs
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx

# Restart a single service
docker compose -f docker-compose.prod.yml restart backend

# Stop everything
docker compose -f docker-compose.prod.yml down

# Renew SSL manually (if needed)
docker compose -f docker-compose.prod.yml run --rm certbot certbot renew

# Database shell
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d neural_archaeologist
```
