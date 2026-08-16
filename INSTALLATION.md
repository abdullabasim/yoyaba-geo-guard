# Installation & Setup Guide

This guide walks you through setting up the YOYABA GEO Guard platform from scratch. The entire system — database, backend API, background workers, and frontend dashboard — runs inside **Docker containers**, so Docker is the only tool you need installed on your machine.

---

## Prerequisites

### Required: Docker Desktop

> **Docker is required.** The platform runs as 6 containerized services managed by Docker Compose. You do not need to install Python, Node.js, PostgreSQL, or Redis separately — Docker handles all of that.

**Install Docker Desktop:**
- **macOS**: [docs.docker.com/desktop/install/mac](https://docs.docker.com/desktop/install/mac-install/)
- **Windows**: [docs.docker.com/desktop/install/windows](https://docs.docker.com/desktop/install/windows-install/)
- **Linux**: [docs.docker.com/desktop/install/linux](https://docs.docker.com/desktop/install/linux-install/)

After installing, verify it is running:
```bash
docker --version
docker compose version
```

You should see Docker version `24+` and Compose version `2+`.

---

## Step 1 — Clone & Configure Environment

First, clone the repository to your local machine and enter the directory:
```bash
git clone https://github.com/abdullabasim/yoyaba-geo-guard.git
cd yoyaba-geo-guard
```

Next, copy the example environment file:
```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in the required values (see section below). At minimum you must set the database password, a JWT secret, and the first admin password.

---

## Step 2 — Environment Variables

All configuration for every service lives in a single `.env` file at the project root. Here are all the variables grouped by purpose:

### Core Security (Required)
| Variable | Purpose |
|---|---|
| `POSTGRES_PASSWORD` | PostgreSQL database password. Choose something strong. |
| `JWT_SECRET_KEY` | Secret key for signing authentication tokens. Generate with: `openssl rand -hex 32` |
| `FIRST_ADMIN_EMAIL` | Email for the first admin account (default: `admin@yoyaba.com`) |
| `FIRST_ADMIN_PASSWORD` | Password for the first admin account. Set before first start. |

### DataForSEO (for live SERP data)
| Variable | Purpose |
|---|---|
| `DATAFORSEO_LOGIN` | Your DataForSEO account email |
| `DATAFORSEO_PASSWORD` | Your DataForSEO API password |
| `DATAFORSEO_DEPTH` | How many SERP results to fetch per call (10–100, default: `100`) |

> Leave `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` empty to run in demo mode without spending any API credits.

### OpenAI / LLM (for AI intent shift analysis)
| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `OPENAI_MODEL` | Model to use (default: `gpt-4o-mini`) |
| `OPENAI_BASE_URL` | API base URL (default: `https://api.openai.com/v1`) |

> Leave `OPENAI_API_KEY` empty to disable AI analysis. SERP data will still be fetched and stored.

### Slack (for alerts & notifications)
| Variable | Purpose |
|---|---|
| `SLACK_ENABLED` | Set `true` to enable all Slack delivery, `false` to log only |
| `SLACK_WEBHOOK_ALERTS` | Incoming webhook URL for business alerts (intent shift detected) |
| `SLACK_WEBHOOK_ERRORS` | Incoming webhook URL for system failure alerts (falls back to alerts hook if empty) |

> Set `SLACK_ENABLED=false` during initial setup to avoid noise while you test the system.

### Demo Data
| Variable | Default | Purpose |
|---|---|---|
| `SEED_DEMO_DATA` | `false` | Automatically seeds 3 demo clients, 5 projects, and 11 URLs on first start |
| `SEED_DEMO_HISTORY` | `false` | Generates ~45 days of backdated rank history (no API calls needed, runs offline) |

> Set both to `true` if you want to populate the database with dummy data during initial testing.

### Rate Control
| Variable | Default | Purpose |
|---|---|---|
| `DATAFORSEO_MAX_REQUESTS_PER_MINUTE` | `60` | Requests per minute across all workers |
| `DATAFORSEO_MAX_CONCURRENT_REQUESTS` | `5` | Max simultaneous API calls in-flight |
| `DATAFORSEO_DAILY_REQUEST_BUDGET` | `0` | Daily call ceiling (`0` = unlimited) |

### App & Ports
| Variable | Default | Purpose |
|---|---|---|
| `FRONTEND_HOST_PORT` | `3100` | Port for the Next.js dashboard |
| `BACKEND_HOST_PORT` | `8100` | Port for the FastAPI backend |
| `POSTGRES_HOST_PORT` | `55432` | Host port for PostgreSQL (non-default to avoid conflicts) |
| `REDIS_HOST_PORT` | `56379` | Host port for Redis (non-default to avoid conflicts) |

---

## Step 3 — Start the System

```bash
docker compose up -d --build
```

This command:
1. **Builds** the backend and frontend Docker images.
2. **Starts** all 6 services: PostgreSQL, Redis, FastAPI backend, Celery worker, Celery Beat scheduler, and the Next.js frontend.
3. **Runs database migrations** automatically on backend startup (via Alembic).
4. **Seeds demo data** on first start (if `SEED_DEMO_DATA=true` and no clients exist yet).

Watch the backend finish starting up:
```bash
docker compose logs -f backend
```

You should see `Application startup complete` within 15–30 seconds.

---

## Step 4 — Open the Dashboard

Once all services are running:

| Service | URL |
|---|---|
| **Dashboard** | [http://localhost:3100](http://localhost:3100) |
| **API (Swagger docs)** | [http://localhost:8100/docs](http://localhost:8100/docs) |
| **API Health check** | [http://localhost:8100/health](http://localhost:8100/health) |

Sign in with the credentials set in your `.env` file. The default values (from `.env.example`) are:

| Field | Default Value |
|---|---|
| **Email** | `admin@yoyaba.com` |
| **Password** | `Yyba-x8F2-mP9q-L5k1` |

> **Important:** Change `FIRST_ADMIN_PASSWORD` in `.env` before deploying to any shared or production environment. The admin account is only created on the very first start when the users table is empty — changing `FIRST_ADMIN_EMAIL` or `FIRST_ADMIN_PASSWORD` after that has no effect. Use the **Change Password** option inside the dashboard to update it later.

---

## Step 5 — Enabling Live Features (One at a Time)

Start with the system in demo mode, then add credentials one by one:

### Enable Live SERP Data (DataForSEO)
1. Set `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD` in `.env`.
2. Restart the backend and worker:
   ```bash
   docker compose restart backend worker beat
   ```
3. Go to `/urls` in the dashboard and click **Run now** on any URL.
4. Check `/tasks` — you should see a green `SUCCESS` row with the live rank stored.

### Enable AI Analysis (OpenAI)
1. Set `OPENAI_API_KEY` in `.env`.
2. Restart: `docker compose restart backend worker beat`
3. To test immediately without waiting for a natural rank drop:
   ```bash
   curl -X POST "http://localhost:8100/api/v1/tasks/run" \
     -H "Content-Type: application/json" \
     -H "Cookie: seo_access_token=YOUR_TOKEN" \
     -d '{"target_url_id": 1, "keyword_id": 1, "force_analysis": true}'
   ```
4. Check `/alerts` — an AI diagnosis should appear.

### Enable Slack Alerts
1. Create an [Incoming Webhook](https://api.slack.com/messaging/webhooks) in your Slack workspace.
2. Set `SLACK_WEBHOOK_ALERTS` and `SLACK_ENABLED=true` in `.env`.
3. Restart: `docker compose restart backend worker beat`
4. Send a test alert to verify the webhook:
   ```bash
   curl -X POST "http://localhost:8100/api/v1/system/alerts/test?category=SERP_QUOTA" \
     -H "Cookie: seo_access_token=YOUR_TOKEN"
   ```

---

## Useful Commands

```bash
# View all running services
docker compose ps

# Follow live logs from all services
docker compose logs -f

# Follow logs from just the background workers
docker compose logs -f worker beat

# Follow logs from the API
docker compose logs -f backend

# Run backend unit tests
docker compose exec backend pytest

# Open a PostgreSQL shell
docker compose exec postgres psql -U seo -d seo_intent

# Restart all services after changing .env
docker compose restart backend worker beat

# Stop everything (keeps database data)
docker compose down

# Stop everything and delete all data (full reset)
docker compose down -v
```

---

## Troubleshooting

**The dashboard shows "Something went wrong"**
> The frontend cannot reach the backend API. Check that the backend is running: `docker compose ps`. Check logs: `docker compose logs backend`.

**Tasks are stuck on PENDING**
> The Celery worker likely crashed mid-task. Check: `docker compose logs worker`. Restart it: `docker compose restart worker`.

**Every task fails with SERP_AUTH**
> `DATAFORSEO_LOGIN` or `DATAFORSEO_PASSWORD` is wrong or missing. Verify credentials, update `.env`, and restart.

**Every analysis fails**
> Check `OPENAI_API_KEY`. Visit `http://localhost:8100/health/ready` — it will report `llm_configured: false` if the key is missing.

**No Slack alerts arriving**
> Visit `http://localhost:8100/api/v1/system/slack/status` — it shows exactly which setting is blocking delivery and why.

**Changing `.env` has no effect**
> Settings are loaded once at startup. After editing `.env`, restart the affected services: `docker compose restart backend worker beat`.
