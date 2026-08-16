# YOYABA GEO Guard & Autonomous Monitoring Platform

A production-grade, microservice-based SEO monitoring and intent-shift diagnosis system. Built with **Next.js (App Router)**, **FastAPI**, **PostgreSQL**, **Redis**, **Celery**, and **FastMCP**.

*(For environment setup, local development, and Docker deployment, see [INSTALLATION.md](./INSTALLATION.md))*

🎥 **UI Demo & Walkthrough**: <a href="https://youtu.be/gi7ouQmhXZk" target="_blank" rel="noopener noreferrer">Watch on YouTube</a>

---

## 1. System Architecture & Core Stack

The system is decoupled into isolated, specialized components that each handle a distinct responsibility:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Next.js Dashboard (UI)                         │
│              (App Router, Tailwind CSS, Recharts, Dark Mode)            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP / JSON API (JWT Cookie)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Async Backend API                        │
│             (Routers, Pydantic Schemas, SQLAlchemy 2.0 Async)           │
└───────────────┬────────────────────┬────────────────────┬───────────────┘
                │                    │                    │
                ▼                    ▼                    ▼
┌───────────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│      PostgreSQL       │  │      Redis       │  │    FastMCP Server    │
│  (JSONB SERP Storage) │  │ (Broker/Throttles)│  │ (LLM Read-Only Tools)│
└───────────────────────┘  └─────────┬────────┘  └──────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Celery Background Workers                        │
│          (Task A: SERP Fetch  ──▶  Task B: AI Intent Analyzer)          │
└──────────────────────────┬──────────────────┬───────────────────────────┘
                           │                  │
                           ▼                  ▼
                 ┌──────────────────┐  ┌──────────────────┐
                 │ DataForSEO API   │  │ OpenAI / xAI API │
                 └──────────────────┘  └──────────────────┘
```

---

### 1.1 Next.js Frontend — Full Control from the Browser

The entire platform is operated through a Next.js dashboard. Every feature of the system — from scheduling checks, to managing API limits, to reading AI diagnoses — is accessible through the UI without touching code, config files, or the terminal.

**What you can manage directly from the UI:**

- **Clients & Projects**: Create, edit, activate or deactivate clients and projects. Deactivating a client instantly stops all monitoring for every project, URL, and keyword underneath it — with zero API spend.
- **Target URLs & Keywords**: Add the pages and keywords you want to monitor. Each keyword tracks independently so a single page can be checked for multiple search terms simultaneously.
- **Schedule per Project or per URL**: Set when checks should run at the project level (e.g., daily at 06:00 America/New_York), and individual URLs can either follow the project's schedule or define their own. This allows staggering checks across hours to stay within API rate windows.
- **Rank Drop Threshold**: Control the sensitivity of alerts. If a keyword needs to fall 5 positions before triggering AI analysis, set `5`. A high-priority keyword? Set it to `1`. Configurable per project or overridden per URL.
- **Fetch Depth (DataForSEO)**: Control how deep DataForSEO scans the SERP (10 to 100 results). A higher depth finds rankings deeper in the search results; a lower depth costs fewer API credits. Configurable at the project or URL level.
- **Kill Switches**: Instantly stop DataForSEO API calls, AI analysis, or Slack notifications from the `/controls` page without restarting any service.
- **Task Monitor**: A live-polling table showing every background task (green for success, red for failure), with expandable error tracebacks.
- **Analytics**: Recharts line charts showing rank history over time with a reversed Y-axis (Position 1 at the top), selectable date ranges, and visible drop events.
- **CSV Bulk Import**: Upload a CSV to import hundreds of clients, projects, URLs, and keywords at once, with browser-side validation before anything is sent to the server.

---

### 1.2 FastAPI Backend — Async API & Business Logic

The backend is built with **FastAPI** using Python's full async/await stack. It handles:

- **CRUD Endpoints**: Full create, read, update, delete, and activate/deactivate endpoints for every entity (clients, projects, URLs, keywords).
- **Schedule Management API**: Endpoints to set project-level scheduling defaults and per-URL overrides, including `apply_to_all_urls` to bulk-push a new schedule to all inheriting URLs at once.
- **Task Dispatch**: An endpoint to trigger an immediate `Run Now` check on any URL, bypassing the schedule for instant diagnostics.
- **Input Validation**: Every request is validated by **Pydantic** schemas before reaching the database. Constraints like `dataforseo_depth` (10–100) and `rank_drop_threshold` (1–50) are enforced server-side. Invalid requests are rejected with clear, structured field-level error messages that surface directly in the UI.

---

### 1.3 PostgreSQL — Storage & SERP History

PostgreSQL stores all entities and serves as the historical record that makes AI intent-shift analysis possible.

**Key tables:**
- `clients`, `projects`, `target_urls`, `keywords` — the management hierarchy.
- `rankings_history` — every SERP check result. Stores the numeric rank and a **JSONB snapshot** of the top-10 results at that moment (position, title, URL, domain, snippet). This snapshot is what gets compared by the LLM when a drop is detected. Since the snapshot is stored, we **never re-query DataForSEO** for historical analysis — all comparisons are done from our own database.
- `ai_alerts` — stores every AI diagnosis: the detected issue type, confidence score, diagnosis text, actionable advice, and competitor signals.
- `task_execution_logs` — a full audit trail of every background task ever run, including status, duration, and the full error traceback on failure.
- `service_controls` — the kill switch states and their audit history (who paused what and why).

---

### 1.4 Redis — Brokering, Rate-Limiting & Alert Deduplication

Redis serves four completely separated logical databases to avoid any state collision:

| Redis DB | Purpose |
|---|---|
| **DB 0** | Celery task message broker |
| **DB 1** | Celery task result backend |
| **DB 2** | Alert throttling & deduplication state |
| **DB 3** | DataForSEO API rate-limit counters |

---

## 2. Clients, Projects, URLs & Keywords — How It All Connects

The system is organized into a hierarchical structure where settings cascade downward. Deactivating any level immediately pauses everything beneath it.

**Clients** are the top-level accounts. A client might represent one agency customer or one company. They contain one or more **Projects**.

**Projects** are the logical containers for a site or campaign. Each project holds the default monitoring schedule that all its URLs will follow unless told otherwise:
- Default check interval (`daily`, `weekly`, `monthly`)
- Default execution time (e.g., `06:00`)
- Default timezone (e.g., `Europe/Berlin`)
- Default rank drop threshold (positions lost before triggering AI analysis)
- Default DataForSEO fetch depth (how many SERP results to retrieve per check)

**Target URLs** are the individual pages being monitored. Each URL can either inherit all settings from its parent project or define its own independent schedule, threshold, and depth. This lets you stagger high-priority pages to run at 02:00 and lower-priority ones at 08:00, spreading API load across the day.

**Keywords** are the search terms tracked per URL. Each keyword runs independently, so one URL can be tracked for five different queries simultaneously. Keywords include a DataForSEO location code (e.g., `2840` for the United States) and a language code (`en`) — a unique combination constraint prevents the same keyword from being submitted twice, avoiding duplicate API billing.

Every check stores one row in `rankings_history` per keyword per run, preserving the complete SERP snapshot. This historical record is what enables the AI analyzer to compare "what Google showed when the page ranked #2" versus "what Google shows now at #9".

---

## 3. Celery — Background Task Orchestration, Batching & Rate Control

### Why Celery

Calling external APIs (DataForSEO, OpenAI) from a web request would lock up the HTTP server waiting for slow network responses. Celery decouples these slow operations into background tasks that run in separate worker processes, keeping the UI fast and responsive.

### How Batch Dispatch Works

Celery Beat runs a scan every 5 minutes (`dispatch_due_checks`). For each URL that is due — meaning it is active, all parent entities are active, the interval has elapsed, and the current local time is within the execution window — Beat expands the work into one task per keyword and enqueues them all simultaneously.

For example: a project with 10 URLs and 5 keywords each generates 50 parallel tasks in a single Beat tick. Each task is atomic and isolated — if keyword 23 fails, keywords 1–22 and 24–50 still complete normally.

### Two-Task Chain

Each keyword check runs as a Celery **chain** of two sequential tasks:

**Task A — `fetch_serp_data`**
1. Acquires a rate-limit slot from Redis.
2. Calls the DataForSEO Live Advanced API.
3. Resolves the target page's rank using exact domain + path matching (so `/pricing/` and `/pricing` are treated as the same page).
4. Saves the numeric rank and top-10 SERP snapshot into `rankings_history`.
5. Evaluates whether the drop is large enough to warrant AI analysis and passes that signal to Task B.

**Task B — `analyze_intent_shift`**
1. Reads Task A's signal. If the drop threshold was not met, records `SKIPPED` and exits cleanly.
2. If analysis is warranted: loads the historical pre-drop SERP snapshot from the database, passes both snapshots (before and after) to the LLM analyzer, persists the structured `AIAlert`, and sends the Slack notification.

### Distributed Rate Limiting (Redis + Atomic Lua Scripts)

When 50 tasks all start at the same time, firing 50 simultaneous HTTP requests to DataForSEO would hit rate limits immediately. The rate limiter prevents this without using in-process locks (which don't work across multiple Celery worker processes).

Three independent controls enforced in Redis:

| Control | What It Limits | Default |
|---|---|---|
| **Sliding Window** | Max requests per minute across all workers | 60 req/min |
| **Concurrency Ceiling** | Max simultaneous in-flight API calls | 5 concurrent |
| **Daily Budget** | Max total API calls in a UTC day (optional hard cap) | Off by default |

When a slot is not available, the task is not marked as **`FAILED`** — it is marked as **`DEFERRED`** and re-queued with a configurable backoff delay. No Slack alert is fired for a deferral, because it is not a failure. If DataForSEO responds with an HTTP 429 itself, the system reads the `Retry-After` header and saturates the Redis window for all workers simultaneously, preventing sibling tasks from discovering the same limit one by one.

---

## 4. LLM Analyzer & MCP Integration

### How the Analysis Works

When Task B determines that a rank drop warrants investigation, the `llm/intent_analyzer.py` module takes over. It loads two SERP snapshots from the database:

- **Baseline snapshot**: The SERP as it looked when the page was ranking well (the last observation before the drop).
- **Current snapshot**: The SERP as it looks now.

Both snapshots (position, title, URL, domain, snippet for each of the top 10 results) are injected into a detailed system prompt (`llm/prompts.py`) and sent to the configured LLM (OpenAI or xAI). The LLM is not browsing the web — it is comparing two fixed JSON objects and classifying the delta.

### Structured Output with Pydantic Validation

The LLM response is not accepted as free-form text. It must match a strict **Pydantic model** (`llm/output_models.py`):

```python
class AiAnalysisResult(BaseModel):
    issue_type: IssueType          # INTENT_SHIFT, NEW_COMPETITOR, CONTENT_FRESHNESS, etc.
    confidence_score: int          # 0 to 100
    ai_diagnosis: str              # Plain-language explanation of what changed in the SERP
    actionable_advice: list[str]   # Concrete steps for SEO/content teams
    competitor_signals: list[...]  # New entrants: URL, content type, what changed
```

If the LLM returns output that does not match this schema, the system automatically retries the request with the exact Pydantic validation error appended to the prompt, giving the model the precise correction it needs. This retry loop runs up to `OPENAI_MAX_RETRIES` times before failing.

### FastMCP Server — Exposing Data to AI Agents

The platform includes a **FastMCP Server** (`mcp_server.py`) that exposes the ranking database to external LLM clients such as Claude Desktop or Cursor. It is completely **read-only by design** — an AI agent can query historical data but cannot modify anything.

The server exposes two tools that an AI agent can call:

**`get_ranking_history(url, keyword, limit=50)`**
Returns the full time-series of rank observations for a specific URL and keyword, including the raw top-10 SERP snapshots and any AI alert diagnoses that were generated. Domain and keyword normalization handles trailing slashes, casing, and whitespace automatically.

**`list_tracked_urls(client_name=None)`**
Returns a list of all monitored URLs with their parent client/project names, tracked keywords, and active/inactive state. Optionally filtered by client name.

The MCP server runs as its own process and can be started in stdio mode (for editor integrations) or HTTP mode on port 8110 (for Docker deployments).

### LangSmith Observability & Tracing

The entire LLM pipeline is instrumented with **LangSmith**. By setting `LANGSMITH_TRACING=true` in your `.env`, every single AI call is automatically logged to [smith.langchain.com](https://smith.langchain.com). 

This allows you to track:
- **Exact Prompts & Responses**: See the exact JSON payload sent to the LLM and the raw output returned.
- **Latency & Token Usage**: Monitor how long each diagnosis takes and how many tokens it consumes for cost tracking.
- **Validation Errors**: If the LLM hallucinates or breaks the Pydantic schema, you can trace the exact validation error and the subsequent retry.

---

## 5. UI Operational Controls (`/controls`)

The `/controls` page provides real-time kill switches for every subsystem. Changes take effect within seconds — no container restarts, no code changes, no terminal access required.

| Switch | Effect When Paused |
|---|---|
| `SCHEDULER` | Celery Beat stops dispatching checks. Manual "Run now" still works. |
| `SERP_FETCH` | No API calls are made to DataForSEO. Zero billing. Queued tasks are skipped. |
| `AI_ANALYSIS` | Rank drops are still recorded in the database, but no LLM calls are made. |
| `SLACK_ALERTS` | Business alerts are stored and can be resent later, but nothing is pushed to Slack. |
| `ERROR_ALERTS` | System failure alerts are logged but not sent to Slack. |
| `HEALTH_MONITOR` | Background health probing stops. |

**Audit trail**: Every pause requires a written reason in the UI. The database records who paused the switch, when, and why. Resuming a switch records the same information.

**Double enforcement**: Switches are checked at dispatch time (by Celery Beat before enqueuing) and again inside the task body (in case the switch was flipped after a task was already queued). A task already sitting in the Redis queue will be stopped at execution time.

---

## 6. Slack Notifications & Health Monitoring

### Business Alerts

When the LLM confirms an intent shift, a Slack Block Kit message is sent containing:
- The affected URL and keyword.
- The rank movement (e.g., Position 2 → Position 9).
- The AI's diagnosis and confidence score.
- Bulleted actionable advice for the SEO or content team.
- A direct link to the dashboard for deeper analysis.

### System Health & Outage Alerts

An independent background task (`monitor_system_health`) runs every 5 minutes, completely separate from the normal check pipeline. It probes:

- PostgreSQL connectivity
- Redis broker connectivity
- DataForSEO API credentials
- LLM API key configuration

If any dependency fails, a classified alert is sent to a dedicated Slack channel with the error category (e.g., `DATABASE_CONNECTION`, `LLM_QUOTA`, `SERP_AUTH`), a severity level (`CRITICAL` or `WARNING`), and explicit remediation steps.

**Alert deduplication**: If the database is down and 200 keywords are failing simultaneously, those 200 failures produce exactly **one Slack message**, not 200. Alerts are keyed and throttled in Redis DB 2. The next alert after the throttle window reports how many occurrences were suppressed.

**Recovery notices**: When a previously failing component passes its health probe, the system automatically sends a "recovered" notice to Slack and clears the throttle window so fresh failures are reported immediately.

---

## 7. Complete Project Structure

```
.
├── docker-compose.yml           # All services (API, worker, beat, postgres, redis, frontend)
├── .env / .env.example          # Single configuration source for all services
├── README.md                    # This document
├── INSTALLATION.md              # Quickstart & deployment guide
│
├── backend/
│   ├── alembic/                 # Database migration versions
│   ├── tests/                   # Pytest unit tests (analysis logic, alert classification, LLM output)
│   └── app/
│       ├── main.py              # FastAPI app entry point, mounts all routers
│       ├── mcp_server.py        # FastMCP read-only tool server
│       ├── core/
│       │   ├── config.py        # Pydantic Settings — only place that reads env vars
│       │   ├── database.py      # Async SQLAlchemy engine & session factory
│       │   ├── celery_app.py    # Celery app instance + Beat schedule definitions
│       │   └── redis_client.py  # Separate Redis connections per logical DB
│       ├── models/              # SQLAlchemy ORM models (one file per table)
│       ├── schemas/             # Pydantic request & response schemas with validation rules
│       ├── crud/                # All database queries (routers never write raw SQL)
│       ├── api/                 # FastAPI routers: clients, projects, urls, keywords,
│       │                        #   rankings, alerts, tasks, bulk, system, controls
│       ├── llm/
│       │   ├── prompts.py       # System prompt & analysis prompt builder
│       │   ├── output_models.py # AiAnalysisResult Pydantic schema enforced on LLM output
│       │   ├── client.py        # Async LLM client with LangSmith tracing decorator
│       │   └── intent_analyzer.py  # Retry & validation loop, public entry point
│       ├── services/
│       │   ├── dataforseo.py    # SERP API client, rank resolution, typed exceptions
│       │   ├── slack.py         # Slack Block Kit formatter & delivery
│       │   ├── rate_limiter.py  # Redis Lua rate-limiting: window, concurrency, budget
│       │   ├── error_alerts.py  # Error classification, severity levels, throttled dispatch
│       │   ├── health.py        # Dependency health probes & recovery notices
│       │   └── scheduling.py    # Due-check query logic
│       └── worker/
│           ├── tasks.py         # Task A, Task B, Beat dispatcher, health monitor, resend
│           ├── runner.py        # Persistent async event loop per worker process
│           └── logging_ctx.py   # run_logged wrapper: audit log + error alert + re-raise
│
└── frontend/
    └── src/
        ├── app/
        │   ├── login/           # JWT login page
        │   └── (dashboard)/
        │       ├── page.tsx         # Overview: counts, 24h health, recent tasks & alerts
        │       ├── clients/         # Client management table
        │       ├── projects/        # Project management + schedule defaults editor
        │       ├── urls/            # URL management + per-URL schedule modal
        │       ├── keywords/        # Keyword table with latest rank & movement badge
        │       ├── analytics/       # Recharts rank history chart (reversed Y-axis)
        │       ├── alerts/          # AI diagnoses with competitor signals
        │       ├── tasks/           # Live task monitor (auto-polls, pauses when tab hidden)
        │       ├── controls/        # Kill switches + process status
        │       └── upload/          # CSV bulk import with client-side preview
        ├── components/
        │   ├── ui/                  # Shared: Form, Modal, Card, Table, Badge, ToggleSwitch
        │   ├── ProjectsTable.tsx    # Projects CRUD + schedule defaults form
        │   ├── UrlsTable.tsx        # URLs CRUD + per-URL schedule override modal
        │   ├── ClientsTable.tsx     # Clients CRUD with active toggle
        │   ├── KeywordsTable.tsx    # Keywords CRUD with rank column
        │   ├── ScheduleForm.tsx     # Per-URL schedule: interval, time, timezone, depth, threshold
        │   ├── ProjectScheduleForm.tsx  # Project-level schedule defaults
        │   ├── RankChart.tsx        # Recharts line chart, no gap interpolation
        │   ├── TaskMonitor.tsx      # Live-polling task table with status badges
        │   └── CsvUploader.tsx      # CSV drag-drop, validation, preview, submit
        └── lib/
            ├── api.ts               # Typed API client (browser + server component paths)
            ├── types.ts             # TypeScript mirrors of backend Pydantic schemas
            └── format.ts            # Rank formatting, delta badges, date/duration helpers
```
