# PeruRE Agent — Deployment Guide

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Environment Variables Reference](#2-environment-variables-reference)
3. [Docker Deployment (Recommended)](#3-docker-deployment)
4. [Database Migrations](#4-database-migrations)
5. [SSL / Certbot Setup](#5-ssl--certbot-setup)
6. [Monitoring](#6-monitoring)
7. [Backup Strategy](#7-backup-strategy)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Prerequisites

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Docker | 24.0 | Container runtime |
| Docker Compose | 2.20 | Multi-service orchestration |
| Git | 2.40 | Source checkout |
| Make | 4.3 | Task runner (optional) |

**API Keys required before first run:**

- **Anthropic API key** — coordinator agent
- **Mapbox token** — route optimization maps
- **WhatsApp Business token + phone number ID** — client messaging (optional for dev)

---

## 2. Environment Variables Reference

Copy `.env.example` to `.env` and fill in every required value.

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | — | Anthropic API key. Get from console.anthropic.com |
| `MAPBOX_TOKEN` | **Yes** | — | Mapbox public token. Get from account.mapbox.com |
| `DATABASE_URL` | **Yes (prod)** | SQLite fallback | Full PostgreSQL DSN: `postgresql://user:pass@host:5432/db` |
| `WHATSAPP_BUSINESS_TOKEN` | No | mock mode | Meta Graph API bearer token for WhatsApp Business |
| `WHATSAPP_PHONE_NUMBER_ID` | No | mock mode | Phone number ID from Meta Business Suite |
| `GOOGLE_MAPS_API_KEY` | No | — | Google Maps API key for transit routing (optional) |
| `LOG_LEVEL` | No | `INFO` | Python log level: DEBUG, INFO, WARNING, ERROR |
| `ALLOWED_ORIGINS` | No | `*` | Comma-separated CORS origins for production |

**Docker-specific overrides** (set automatically by docker-compose.yml):

```
DATABASE_URL=postgresql://peru_re:peru_re_pass@postgres:5432/peru_re_db
```

This override ensures the backend container resolves the `postgres` service hostname,
not `localhost`. Do not change it in docker-compose.yml.

---

## 3. Docker Deployment

### 3.1 First-time setup

```bash
# 1. Clone the repository
git clone https://github.com/henryurlo/peru-re-agent.git
cd peru-re-agent

# 2. Create environment file
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and MAPBOX_TOKEN at minimum

# 3. Build all images
docker compose build

# 4. Start the full stack (detached)
docker compose up -d

# 5. Verify all services are healthy
docker compose ps
```

Expected output after `docker compose ps`:

```
NAME                   STATUS         PORTS
peru-re-backend        healthy        0.0.0.0:8000->8000/tcp
peru-re-db             healthy        0.0.0.0:5432->5432/tcp
peru-re-mcp-maps       running        0.0.0.0:8001->8000/tcp
peru-re-mcp-calendar   running        0.0.0.0:8002->8000/tcp
peru-re-mcp-whatsapp   running        0.0.0.0:8003->8000/tcp
peru-re-mcp-property   running        0.0.0.0:8004->8000/tcp
```

### 3.2 Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend / API | http://localhost:8000 | Broker dashboard + REST API |
| Health check | http://localhost:8000/health | Liveness probe |
| Admin dashboard | http://localhost:8000/admin | Request log, broker activity |
| Maps MCP | http://localhost:8001 | Mapbox routing server |
| Calendar MCP | http://localhost:8002 | Appointment management |
| WhatsApp MCP | http://localhost:8003 | Messaging server |
| Property DB MCP | http://localhost:8004 | PostgreSQL property listings |

### 3.3 Stopping and restarting

```bash
# Stop all services (preserves data volumes)
docker compose down

# Stop and remove all data (destructive — removes postgres_data volume)
docker compose down -v

# Restart a single service after a config change
docker compose restart backend

# Pull latest images and recreate
docker compose pull && docker compose up -d --force-recreate
```

### 3.4 Viewing logs

```bash
# Tail all services
docker compose logs -f

# Single service
docker compose logs -f backend

# Last 100 lines
docker compose logs --tail=100 backend
```

### 3.5 Updating to a new version

```bash
git pull
docker compose build backend
docker compose up -d backend
```

For schema migrations see [Section 4](#4-database-migrations).

---

## 4. Database Migrations

### 4.1 How the schema is applied

On first startup, Docker Compose mounts `mcp_servers/property_db/schema.sql`
into the PostgreSQL container at `/docker-entrypoint-initdb.d/01-schema.sql`.
PostgreSQL runs every file in that directory automatically on first init only.

```yaml
# docker-compose.yml (already configured)
volumes:
  - ./mcp_servers/property_db/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
```

### 4.2 Running migrations manually

If the database already exists (volume present) and you add new tables:

```bash
# Connect to running postgres container
docker compose exec postgres psql -U peru_re -d peru_re_db

# Inside psql, run your DDL:
\i /docker-entrypoint-initdb.d/01-schema.sql
-- or paste ALTER TABLE statements directly

\q
```

From the host machine (requires psql installed):

```bash
psql "postgresql://peru_re:peru_re_pass@localhost:5432/peru_re_db" \
  -f mcp_servers/property_db/schema.sql
```

### 4.3 Seeding sample data

```bash
# Copy and run the seed script
docker compose exec postgres psql -U peru_re -d peru_re_db \
  -c "\copy properties FROM '/dev/stdin' CSV" < scripts/seed_data.csv
```

Or use the Python seed helper (requires DATABASE_URL set):

```bash
python scripts/run_priority.sh seed
```

### 4.4 Backup before migration

Always back up before running DDL changes in production:

```bash
docker compose exec postgres pg_dump -U peru_re peru_re_db > backup_$(date +%Y%m%d).sql
```

---

## 5. SSL / Certbot Setup

For production deployments exposed to the internet, terminate TLS at the host
with nginx + certbot (Let's Encrypt).

### 5.1 Install nginx and certbot

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 5.2 nginx reverse-proxy config

Create `/etc/nginx/sites-available/peru-re`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/peru-re /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 5.3 Obtain TLS certificate

```bash
sudo certbot --nginx -d your-domain.com
```

Certbot modifies the nginx config automatically to add HTTPS and redirect HTTP.

### 5.4 Auto-renewal

Certbot installs a systemd timer or cron job automatically. Verify:

```bash
sudo certbot renew --dry-run
```

### 5.5 WebSocket TLS

The admin dashboard WebSocket at `/ws/broker/{id}` requires the nginx config
above (it already includes the `Upgrade` headers). No additional config needed.

---

## 6. Monitoring

### 6.1 Health checks

The backend exposes a liveness endpoint:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"peru-re-agent","version":"1.0.0"}
```

Docker Compose uses this endpoint with a 10s interval / 5-retry policy.
For external uptime monitoring (e.g. UptimeRobot), point it at `/health`.

### 6.2 Structured JSON logs

Every request is logged to stdout as structured JSON:

```json
{"timestamp":"2026-04-28T10:32:15+00:00","method":"POST","path":"/api/v1/coordinate","status_code":200,"duration_ms":342.1,"broker_id":"broker-001"}
```

Collect with any log aggregator:

**Docker + Loki (Grafana stack):**

```yaml
# Add to docker-compose.yml under backend:
logging:
  driver: loki
  options:
    loki-url: "http://localhost:3100/loki/api/v1/push"
    labels: "service=peru-re-backend"
```

**Docker + CloudWatch (AWS):**

```yaml
logging:
  driver: awslogs
  options:
    awslogs-group: /peru-re-agent
    awslogs-region: us-east-1
```

**File-based (simple):**

```bash
docker compose logs -f backend >> /var/log/peru-re/backend.log
```

### 6.3 Admin dashboard

The built-in admin dashboard at `/admin` shows:

- Last 50 requests (ring buffer) with status codes and latency
- Request count per broker ID
- MCP server mount status (green = mounted, red = failed to load)

### 6.4 Prometheus metrics (optional)

Add `prometheus-fastapi-instrumentator` to `requirements.txt`, then in `backend/main.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

This exposes `/metrics` in Prometheus exposition format. Scrape with:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: peru-re-agent
    static_configs:
      - targets: ['localhost:8000']
```

Key metrics to watch:

| Metric | Alert threshold |
|--------|----------------|
| `http_requests_total{status="5xx"}` | > 1% of traffic |
| `http_request_duration_seconds_p99` | > 5 seconds |
| `postgres_up` | == 0 |

---

## 7. Backup Strategy

### 7.1 PostgreSQL continuous backup

**Daily dump (cron):**

```bash
# /etc/cron.d/peru-re-backup
0 2 * * * root docker compose -f /opt/peru-re-agent/docker-compose.yml \
  exec -T postgres pg_dump -U peru_re peru_re_db \
  | gzip > /backups/peru-re-$(date +\%Y\%m\%d).sql.gz
```

**Retention policy:**

```bash
# Keep 7 daily backups
find /backups -name "peru-re-*.sql.gz" -mtime +7 -delete
```

### 7.2 Point-in-time recovery (WAL archiving)

For production, enable WAL archiving in `postgresql.conf`:

```
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://your-bucket/wal/%f'
```

### 7.3 Docker volume backup

The `postgres_data` volume stores all PostgreSQL data. To back up the raw volume:

```bash
docker run --rm \
  -v peru-re-agent_postgres_data:/source:ro \
  -v /backups:/dest \
  alpine tar czf /dest/postgres_data_$(date +%Y%m%d).tar.gz -C /source .
```

### 7.4 Restore from backup

```bash
# Restore SQL dump
gunzip -c /backups/peru-re-20260428.sql.gz \
  | docker compose exec -T postgres psql -U peru_re -d peru_re_db
```

---

## 8. Troubleshooting

### Backend fails to start — "Address already in use"

```bash
lsof -ti:8000 | xargs kill -9
docker compose up -d backend
```

### PostgreSQL unhealthy — keeps restarting

```bash
# Check postgres logs
docker compose logs postgres

# Common cause: data directory from incompatible version
docker compose down -v   # removes postgres_data volume — destroys all data
docker compose up -d
```

### ANTHROPIC_API_KEY not found / coordinator returns 500

```bash
# Verify the key is loaded in the container
docker compose exec backend env | grep ANTHROPIC
# Should print: ANTHROPIC_API_KEY=sk-ant-...

# If missing, check your .env file and restart
docker compose up -d --force-recreate backend
```

### Mapbox routes return mock data instead of real routes

The maps MCP server falls back to mock data when `MAPBOX_TOKEN` is missing or invalid.

```bash
# Check the token is set
docker compose exec mcp-maps env | grep MAPBOX_TOKEN

# Validate the token
curl "https://api.mapbox.com/directions/v5/mapbox/driving/-77.0369,38.9072;-77.0369,38.9172?access_token=YOUR_TOKEN"
```

### WhatsApp messages not sending

1. Check `WHATSAPP_BUSINESS_TOKEN` is set and not expired (tokens rotate every 24h in sandbox mode).
2. Verify `WHATSAPP_PHONE_NUMBER_ID` matches your Meta Business account.
3. The time gate hook blocks messages before 8am and after 8pm Lima time (UTC-5). Check system clock.

### Rate limit 429 errors

The API limits each broker to 10 requests/minute. For development:

```python
# Temporarily increase in backend/main.py
_TokenBucket(rate=100 / 60, capacity=100)
```

Do not raise limits in production without reviewing the coordinator's API cost per call.

### MCP server shows "failed to load" in admin dashboard

```bash
# Check MCP server logs
docker compose logs mcp-maps

# Common causes:
# 1. Missing Python dependency — rebuild the image
docker compose build mcp-maps

# 2. Port conflict — check if 8001-8004 are in use
lsof -ti:8001 -ti:8002 -ti:8003 -ti:8004
```

### Database migration ran twice — duplicate key errors

The `CREATE TABLE IF NOT EXISTS` and `CREATE EXTENSION IF NOT EXISTS` guards in
`schema.sql` are idempotent. Re-running the schema is safe.

For `INSERT` statements in seed scripts, use `ON CONFLICT DO NOTHING`:

```sql
INSERT INTO properties (...) VALUES (...) ON CONFLICT (id) DO NOTHING;
```

---

*For architecture context, see [ARCHITECTURE.md](ARCHITECTURE.md). For contributing, see [README.md](README.md#contributing).*
