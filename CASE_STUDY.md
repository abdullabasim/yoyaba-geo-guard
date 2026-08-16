# Technical Case Study: Strategy, Architecture, Build & Real-World Value (Parts 1–4)

This document contains the strategic methodology, enterprise system architecture, production execution answers, and real-world impact case studies for Parts 1, 2, 3, and 4 of the (Senior) SEO AI Engineer technical case study.

<br/><br/>

---

# PART 1: Methodology (The Strategic Layer)

---

<br/>

### The Evolution from Traditional SEO to Generative Engine Optimization (GEO)

**Situation**
In the current state of B2B organic search, technical SEO and baseline content production have largely become commoditized. Most high-growth B2B SaaS companies employ sophisticated tooling to ensure their web properties are crawlable, fast, and technically sound. They maintain extensive libraries of bottom-of-funnel (BOFU) landing pages and top-of-funnel (TOFU) blog content optimized for semantic entities and keyword densities. Historically, organic search success was primarily a function of three variables: technical hygiene, content volume, and backlink authority.

**Complication**
This traditional model is being disrupted by LLM-driven search interfaces (e.g., Google’s AI Overviews, ChatGPT Search, Perplexity). Generative engines are moving away from merely retrieving ten blue links; they synthesize answers dynamically, evaluate search intent with human-like nuance, and cite authoritative brand entities directly. Consequently, traditional SEO operations face critical operational bottlenecks:

1. **Intent Volatility:** A keyword that historically surfaced commercial software landing pages may suddenly trigger educational listicles or comparison matrices because the generative engine determines the user seeks impartial research rather than a direct purchase.
2. **Technical Myopia:** When rankings or traffic drop, traditional SEO teams reflexively audit technical vitals (Core Web Vitals, canonical tags, schema markup, heading hierarchies). They waste weeks fixing non-issues when the underlying reality is that the page simply no longer matches the generative engine's preferred content format or search intent for that query.
3. **Entity Authority Gaps:** Traditional SEO focuses on keyword rankings rather than brand presence within LLM training data and retrieval-augmented generation (RAG) pipelines. Winning in generative search requires becoming a synthesized source of truth, not just ranking a static URL.

**Question**
*What is the core strategic question a high-growth B2B SaaS company must answer to maintain and scale organic visibility today?*

> *"Are we losing organic visibility due to technical or content decay, or has the underlying intent, preferred content format, and LLM entity consensus shifted for this query?"*

**Answer**
My methodology bridges traditional technical SEO and Generative Engine Optimization (GEO) by combining Automated Intent Monitoring with AI-Driven Strategic Diagnostics.

1. **Balancing Technical SEO and GEO:** Technical SEO remains foundational—if a page cannot be crawled and indexed efficiently, it cannot participate in search. However, technical perfection is no longer a competitive moat; it is merely the price of admission. GEO requires us to continually align our content formats (e.g., comparison guides, interactive calculators, listicles, product pages) with what LLMs perceive as the most helpful response, while actively engineering Entity Authority so generative engines cite our SaaS platform as an industry standard.
2. **AI as a Strategic Diagnostician:** We shift AI internally from being a simple "content generator" to being a "strategic diagnostician." By deploying LLMs within automated backend pipelines to evaluate the delta between historical SERP/LLM snapshots and current search compositions, we create an early-warning diagnostic system. When rank drops occur, the AI immediately classifies the root cause—distinguishing between technical regressions and intent/format shifts. This directs growth teams to execute the exact required intervention (e.g., converting a static landing page into an interactive comparison guide) instantly. This minimizes wasted engineering cycles, optimizes content strategy, and accelerates revenue recovery.

<br/><br/>

---

# PART 2: Infrastructure & Architecture (The Systems Layer)

---

<br/>

### Designing an Enterprise SEO-First Tooling Ecosystem

To support an enterprise client managing **5,000+ indexable pages**, we build a decoupled, highly concurrent microservice architecture. The system separates data ingestion, background execution, hybrid storage, AI reasoning with real-time observability, and dashboard monitoring.

---

### 1. High-Level Architecture & Flow

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             API & INGESTION GATEWAY                              │
│  ┌────────────────────────┐      ┌─────────────────────────┐                     │
│  │ Target URLs (5,000+)   │      │ Rank Tracking API       │                     │
│  │ (Async HTML Crawler)   │      │ (Periodic SERP Scrape)  │                     │
│  └───────────┬────────────┘      └────────────┬────────────┘                     │
└──────────────┼────────────────────────────────┼──────────────────────────────────┘
               │                                │
               ▼                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         ASYNC WORKERS & CONCURRENCY LAYER                        │
│               FastAPI (Gateway & Dispatch) + Celery (Worker Fleet)               │
│                   - Throttling & Queues via Redis Broker                         │
└──────────────┬────────────────────────────────┬──────────────────────────────────┘
               │                                │
               ▼                                ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          HYBRID STORAGE ARCHITECTURE                             │
│  ┌─────────────────────────────────┐   ┌──────────────────────────────────────┐  │
│  │ Amazon S3 / Cloud Storage       │   │ PostgreSQL (Relational DB)           │  │
│  │ - Raw HTML DOM Dumps            │   │ - Structured Rank History (1-100)    │  │
│  │ - S3 Object URI Pointers        │   │ - Metadata, Schedules & Clients      │  │
│  │                                 │   │ - Task Logs & AI Diagnostic Alerts   │  │
│  └────────────────┬────────────────┘   └──────────────────┬───────────────────┘  │
└───────────────────┼───────────────────────────────────────┼──────────────────────┘
                    │                                       │
                    │         ┌─────────────────────────────┘
                    │         │ (Rank Drop >= 3 Detected)
                    ▼         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│             LANGGRAPH AI DIAGNOSTIC ENGINE (WITH MCP & OBSERVABILITY)            │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │ Node 1: Quality Inspector (Calls FastMCP tool to fetch S3 HTML & Compare) │  │
│  │ Node 2: Intent Shift & SERP Volatility Analyzer                           │  │
│  │ Node 3: Critic & Double-Check Validator (Runs a distinct second LLM model) │  │
│  │ Node 4: Structured Diagnostic & Alert Generator                            │  │
│  └──────────────────────────────────┬─────────────────────────────────────────┘  │
│                                     │                                            │
│                      [ Trace Prompts, Latency & Tokens ]                         │
│                                     │                                            │
│                                     ▼                                            │
│                    ┌──────────────────────────────────┐                          │
│                    │ LangSmith / Langfuse Tracing     │                          │
│                    └──────────────────────────────────┘                          │
└─────────────────────────────────────┬────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           SURFACING & ACTION LAYER                               │
│  ┌────────────────────────┐   ┌───────────────────────┐   ┌───────────────────┐  │
│  │ Next.js Dashboard      │   │ Real-Time Slack Alert │   │ n8n Automations   │  │
│  │ (Charts & Task Logs)   │   │ (Instant Trigger)     │   │ (Jira / Email)    │  │
│  └────────────────────────┘   └───────────────────────┘   └───────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

### 2. High-Level Concurrency & Execution: FastAPI & Celery

#### FastAPI (API Gateway & Async Dispatcher)
- **Non-Blocking I/O:** FastAPI acts as the lightweight REST gateway, handling UI requests, CSV file uploads, and webhook triggers asynchronously.
- **Background Tasks:** For light, in-process operations (such as triggering an outgoing notification or updating entity toggles), FastAPI handles task execution without blocking HTTP workers.
- **Task Delegation:** Long-running, heavy workloads (batch-crawling thousands of URLs or orchestrating multi-node LLM calls) are offloaded immediately to Celery queues, keeping API responses instant.

#### Celery & Redis (Distributed Worker Fleet & Concurrency)
- **High Concurrency Models:** Celery workers utilize asynchronous execution pools (`gevent` or `eventlet`) to manage thousands of concurrent outbound HTTP calls without exhausting system CPU threads.
- **Queue Partitioning:** Tasks are routed through distinct queues:
  - `high_priority`: Instant manual checks dispatched from the user dashboard.
  - `bulk_monitoring`: Scheduled background checks for the 5,000+ page portfolio.
  - `ai_diagnostics`: Dedicated worker pool reserved for LLM reasoning pipelines.
- **Rate Limiting & Throttling:** Redis maintains sliding-window token buckets across parallel workers to prevent outbound API rate-limit violations (`HTTP 429`).

---

### 3. Hybrid Storage Strategy: PostgreSQL vs. Amazon S3

To prevent database table bloat, buffer-pool crashes, and slow queries, unstructured text payloads are strictly isolated from structured metrics:

| Storage Tier | Technology | Data Stored | Primary Advantage |
|---|---|---|---|
| **Blob Tier** | **Amazon S3** (or GCS) | Raw compressed HTML DOM dumps | Virtually unlimited storage scale; preserves small, fast database indexes by keeping large text files out of SQL tables. |
| **Relational Tier** | **PostgreSQL** | Client hierarchy, target URLs, keywords, numeric rank history (1–100), task execution logs, and AI alert records. | Optimized for high-speed SQL queries, date-range filtering, and UI dashboard visualizer feeds. Stores S3 URI pointers (`s3_html_pointer`). |
| **Retrieval Tier** | **FastMCP Server** | On-demand HTML extraction tool for AI agents | Retrieves S3 HTML objects on demand, parses clean markdown text, and passes it to LLMs without touching PostgreSQL buffer memory. |

---

### 4. Pipeline Stages & Data Lifecycle

1. **Collect (Crawling & SERP Scrape):**
   - Celery workers crawl active URLs via `httpx`, compress raw HTML DOMs, stream them to Amazon S3, and store the resulting S3 pointer.
   - Scheduled tasks asynchronously query rank tracking APIs to fetch position metrics and top-10 competitor SERP snapshots.
2. **Normalize & Validate:**
   - Pydantic schemas validate raw payloads, strip tracking parameters, sanitize canonical paths, and enforce type safety before persistence.
3. **Persist:**
   - Numerical rank metrics, SERP competitor snapshots, and S3 file pointers are saved to PostgreSQL historical tables.
   - Task execution statuses (`PENDING`, `SUCCESS`, `FAILED`) are recorded in execution logs for auditability.
4. **Surface & Trigger:**
   - When a target keyword experiences a rank drop of $\ge 3$ positions, Celery triggers the LangGraph AI Diagnostic Engine.

---

### 5. Multi-Node LangGraph AI Agent (with FastMCP, Multi-Model Double-Checking & Observability)

When triggered by a rank drop, the system invokes a specialized LangGraph agent. The agent uses an MCP (Model Context Protocol) server to pull heavy HTML files from S3 only when needed, and streams all execution metadata to an LLM observability platform (**LangSmith** or **Langfuse**).

```
                           ┌──────────────────────────────┐
                           │   Rank Drop Event (>= 3)     │
                           └──────────────┬───────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────┐
                           │ Node 1: Technical Inspector  │
                           │ - Uses MCP to pull S3 HTML   │
                           │ - Checks tags & canonicals   │
                           └──────────────┬───────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────┐
                           │ Node 2: SERP Intent Analyzer │
                           │ - Compares old vs. new SERP  │
                           │ - Detects Intent Shift       │
                           └──────────────┬───────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────┐
                           │ Node 3: Critic / Validator   │
                           │ - Cross-checks Node 1 & 2    │
                           │   using a DIFFERENT LLM      │
                           │ - Detects hallucinations     │
                           └──────────────┬───────────────┘
                                          │
                                          ▼
                           ┌──────────────────────────────┐
                           │ Node 4: Alert Generator      │
                           │ - Enforces Pydantic JSON     │
                           │ - Triggers Slack Alert       │
                           └──────────────────────────────┘
```

#### Node Roles & Multi-Model Cross-Validation:
- **Node 1: Technical & Quality Inspector (FastMCP Tool):**
  - Calls the FastMCP tool `fetch_page_html_from_s3(s3_pointer)`.
  - Extracts title tags, `<meta name="robots">`, and canonical headers to detect technical regressions (`noindex`, broken tags, content decay).
- **Node 2: SERP Intent Shift Analyzer:**
  - Compares historical competitor SERP snapshots against current search compositions.
  - Identifies whether search engines shifted intent (e.g., from commercial landing pages to informational listicles or AI Overviews).
- **Node 3: Critic & Double-Check Validator (Error Reduction via Distinct Model):**
  - **Independent Verification:** Evaluates the reasoning and outputs from Node 1 and Node 2 using a **completely distinct LLM model** (e.g., cross-evaluating an initial model's analysis against a second vendor or different parameter class model).
  - **Hallucination & Bias Check:** Ensures that the diagnosis matches actual SERP data (e.g., verifying that a claimed "Intent Shift" actually aligns with competitor title changes). If a discrepancy or hallucination is detected, it forces Node 1 or Node 2 to re-evaluate before proceeding.
- **Node 4: Diagnostic & Alert Generator:**
  - Enforces structured JSON output via Pydantic (`issue_type`, `diagnosis`, `actionable_advice`).
  - Dispatches formatted alerts to Slack and records diagnoses in PostgreSQL.

#### LLM Observability (LangSmith / Langfuse Integration):
- **Traceability:** Every node execution is wrapped with tracing decorators (`@traceable` or Langfuse callbacks) to capture full execution graphs.
- **Telemetry Captured:** Prompts sent, raw JSON returned, execution latency per node, token usage, and total cost per client run.
- **Continuous Monitoring:** Allows engineers to review failed validation loops, monitor model drift, and optimize prompt performance directly in the LangSmith/Langfuse dashboard.

---

### 6. System Observability & Robustness

- **LLM Resilience & Retry Loops:** All LLM outputs are validated against Pydantic models. If a model returns malformed JSON, an automated retry loop feeds the validation error back to the LLM (up to 3 retries) to self-correct.
- **Global Error Catching:** Background tasks use global `try/except` handlers. Any unhandled exception updates task execution logs with error tracebacks and sends a critical failure alert to Slack.
- **System Observability UI (Next.js):**
  - **Task Execution Monitor:** Displays real-time task statuses (`PENDING`, `SUCCESS`, `FAILED` with error details).
  - **Analytics Dashboard:** Renders interactive ranking trend charts (using Recharts).
  - **Entity & Schedule Controls:** Offers UI toggles (`is_active`) per Client, Project, or URL, dynamic scheduling selectors, and bulk CSV ingestion.

---

### 7. Future Enterprise Scaling: High-Throughput Streaming Architecture

While Celery + Redis handles periodic batch checking (5,000–100,000 URLs) efficiently, scaling to an **Enterprise Real-Time Data Pipeline** (e.g., analyzing millions of live edge web logs from Cloudflare/Fastly or continuous real-time SERP streams) requires transitioning from task queues to a **Distributed Stream Processing Architecture** with a high-concurrency compiled backend:

```
[ Real-Time Edge Logs / SERP Stream ]
                  │
                  ▼
   [ Golang High-Concurrency Ingestion Gateway ] ──(Low Memory / Goroutines)
                  │
                  ▼
       [ Apache Kafka Event Bus ]
                  │
                  ▼
   [ Apache Flink Stream Engine ] ──(In-Flight Validation & State Windows)
                  │
                  ├──────────────────────────────┐
                  ▼                              ▼
   [ Raw HTML -> S3 Data Lake ]      [ Aggregated Stats -> PostgreSQL ]
```

#### Architecture Evolution Strategy:
1. **High-Concurrency Ingestion Gateway: Golang (Go)**
   - **Purpose:** Replaces Python for the front-door ingestion layer to handle massive volumes of incoming requests.
   - **Advantage:** Go's lightweight concurrency model (Goroutines) and low memory footprint allow a single microservice instance to process tens of thousands of concurrent inbound webhooks, crawler payloads, and edge server logs per second with sub-millisecond overhead—passing them directly to the Kafka event bus without clogging Python runtime threads.
2. **Ingestion & Application-Level Processing: Apache Kafka + Kafka Streams**
   - **Purpose:** Replaces Redis as the primary high-throughput event log broker.
   - **Advantage:** Kafka Streams allows running lightweight stream processing directly inside your application instances (no separate processing cluster required). It manages event routing, partition keying, filtering, and light data transformations directly within application code.
3. **Heavyweight Distributed Stream Processing: Apache Flink**
   - **Purpose:** Replaces batch polling with continuous, stateful, cluster-wide stream processing.
   - **Advantage:** Performs low-latency schema validation, data reformatting, and complex event processing (CEP) in-flight before data hits storage. Flink's tumbling and sliding time windows calculate rank volatility across rolling time windows continuously.
4. **Storage Layer: Lakehouse Architecture (Delta Lake / Apache Iceberg)**
   - **Purpose:** Complements Amazon S3 object storage by organizing compressed raw HTML files and log feeds into queryable, ACID-compliant data lake tables.
   - **Advantage:** Allows analytical engines (e.g., Trino or Snowflake) to run direct SQL queries across petabytes of historical crawl data without degrading production web application performance.

<br/><br/>

---

# PART 3: The Build (The Execution Layer)

---

<br/>

### Mini-Tooling Example: Automated Intent-Shift Detection

Rather than presenting theoretical snippets or static mock files, we built and deployed a complete, production-ready microservice platform in Python (**FastAPI, Celery, Redis, PostgreSQL, OpenAI/xAI, Next.js 14, FastMCP**). 

The full implementation, code files, installation guide, and deployment instructions are documented in [README.md](https://github.com/abdullabasim/yoyaba-geo-guard/blob/main/README.md).

🎥 **Live Platform Demo & Video Walkthrough:** <a href="https://youtu.be/gi7ouQmhXZk" target="_blank" rel="noopener noreferrer">Watch on YouTube</a>

---

### Step-by-Step Task Breakdown & Code Mapping

#### 1. Trigger / Input (Rank Drop Simulation & SERP Ingestion)
- **Scenario:** Client landing page drops from **Position 2 to Position 9** for a high-value keyword.
- **Code Implementation:** `backend/app/tasks/serp_tasks.py` (`fetch_serp_data`)
- **Execution Flow:**
  1. Celery worker executes `fetch_serp_data` for the target URL and keyword.
  2. Pulls live SERP metrics via **DataForSEO API** (or mock SERP JSON in test environments).
  3. Resolves current position (Rank 9) and retrieves historical baseline (Rank 2) from PostgreSQL `rankings_history`.
  4. Calculates drop delta (9 - 2 = 7). Since 7 &ge; `rank_drop_threshold` (3), Task A triggers Task B (`analyze_intent_shift`).

---

#### 2. AI Analysis Logic & Strategic Prompts
- **Code Implementation:** `backend/app/llm/intent_analyzer.py` & `backend/app/llm/prompts.py`
- **Execution Flow:**
  - Loads baseline SERP snapshot (top 10 competitor titles, URLs, domains, snippets at Position 2) and current SERP snapshot (at Position 9) from PostgreSQL.
  - Constructs system prompt (`SYSTEM_PROMPT` in `llm/prompts.py`) directing the LLM to act as a Senior SEO Diagnostician:
    - Analyzes whether Google shifted search intent (e.g., commercial landing page replaced by educational listicles or AI Overviews).
    - Identifies new competitor entrants or technical tag decay (`noindex`, canonical mismatch).

---

#### 3. Guaranteed Structured Output (Pydantic Schema)
- **Code Implementation:** `backend/app/llm/output_models.py` (`IntentShiftAnalysis`)
- **Schema Definition:**
  ```python
  class IssueType(str, Enum):
      INTENT_SHIFT = "INTENT_SHIFT"
      NEW_COMPETITOR = "NEW_COMPETITOR"
      CONTENT_FRESHNESS = "CONTENT_FRESHNESS"
      TECHNICAL_REGRESSION = "TECHNICAL_REGRESSION"

  class IntentShiftAnalysis(BaseModel):
      issue_type: IssueType          # Categorized drop cause
      confidence_score: int          # 0 to 100 confidence rating
      ai_diagnosis: str              # Plain-language SERP delta breakdown
      actionable_advice: list[str]   # Concrete remediation steps
      competitor_signals: list[CompetitorSignal]
  ```
- Enforced via OpenAI / xAI native JSON Structured Outputs (`response_format={"type": "json_object"}`).

---

#### 4. Actionable Slack Alerting (Block Kit Webhooks)
- **Code Implementation:** `backend/app/services/slack_notifier.py` (`send_slack_alert`)
- **Alert Payload Structure:**
  - **Header:** 🚨 *SEO Intent-Shift Alert: Rank Drop Detected*
  - **Metrics:** Target URL, Keyword, Rank Delta (`Position #2 → #9`), Confidence Score badge.
  - **Diagnosis Body:** AI-synthesized explanation of SERP composition shifts.
  - **Actionable Steps:** Formatted bullet list directing content/dev teams on exact remediation steps.

---

#### 5. Handling Hallucinations & API Timeouts in Production Code

1. **Handling Hallucinations & Schema Mismatches (Self-Correcting Retry Loop):**
   - **Location:** `backend/app/llm/intent_analyzer.py`
   - **Mechanism:** When the LLM responds, the raw payload is validated using `IntentShiftAnalysis.model_validate(payload)`.
   - If the model returns malformed JSON or hallucinates an invalid schema key, a Pydantic `ValidationError` is caught.
   - Instead of failing, the system appends the **exact Pydantic error traceback** to the user prompt (`build_retry_prompt`) and retries up to `OPENAI_MAX_RETRIES` times (default 3). This closed-feedback loop teaches the LLM its specific error so it self-corrects immediately.

2. **Handling API Timeouts & Network Resilience:**
   - **Location:** `backend/app/llm/client.py` & `backend/app/tasks/serp_tasks.py`
   - **Timeout Caps:** Outbound HTTP requests to LLM providers are wrapped in `asyncio.timeout(settings.openai_timeout_seconds)` (default 30s).
   - **Celery Backoff:** If an HTTP call times out or encounters network degradation, Celery catches `httpx.TimeoutException`, defers execution with exponential backoff delay, and re-queues the job without marking it as a system failure.
   - **UI Kill Switch:** Global kill switches in the Next.js `/controls` page allow admins to pause LLM calls instantly across all workers during provider outages.

<br/><br/>

---

# PART 4: Real-World Value (The Impact Layer)

---

<br/>

### Example 1: Automated AI Anti-Spam & Content Quality Engine (Locanto)

**The Problem**  
At Locanto (a high-volume classifieds platform similar to Kleinanzeigen), spammers flooded the site with thousands of near-duplicate ads containing minor text variations. This severely degraded content quality, created thin/duplicate content issues across programmatic location pages, and triggered organic search ranking drops due to search engine quality penalties. Manual moderation could not scale with the sheer volume of incoming posts.

**The System**  
Engineered an AI Agent workflow backed by a Vector Database supporting Hybrid Search (combining lexical BM25 matching with dense semantic embeddings). To handle heavy real-time ad ingestion with ultra-low latency, I optimized the embedding model using ONNX Runtime, loading it directly in-memory across parallel multi-worker processes. The AI Agent was equipped with tool-calling capabilities to query the vector database for semantic similarity, automatically quarantine duplicate spam, and apply grammar/formatting corrections to legitimate ad copy before indexing.

**The Value**
- **Automated Moderation:** Reduced manual duplicate detection workload by over 90%.
- **Index Quality & Traffic Recovery:** Eliminated thin/duplicate content penalties across pilot cities, driving a measurable recovery in organic search traffic and ad revenue.
- **Content Polish:** Automated copy refinement, improving page quality scores and user engagement metrics across target landing pages.

---

### Example 2: Ultra-Fast, Low-Cost Automated Ad Classification Engine (Locanto)

**The Problem**  
On Locanto, users frequently posted ads in incorrect categories, severely degrading content quality, search relevance, and user navigation. Relying on external manual reviewers to double-check incoming ads daily created a massive operational cost bottleneck and delayed publication times.

**The System**  
Engineered an automated, high-accuracy classification pipeline optimized for speed and cost efficiency without using expensive LLM inference at runtime:
1. **Data Pipeline & Curation:** Preprocessed multi-language ad data per category and leveraged BERTopic clustering to eliminate over 80% of duplicate/noisy training data. For low-data edge categories, utilized LLMs offline to generate high-quality synthetic training data.
2. **Model Architecture & Deployment:** Fine-tuned a ModernBERT transformer model specialized for multi-class categorization. Quantized and optimized the model using ONNX Runtime to run directly on cost-effective CPU nodes (bypassing GPU costs) across a multi-node FastAPI worker setup.

**The Value**
- **Speed & Accuracy:** Achieved ~99% accuracy with an ultra-low inference latency of 0.3s–0.5s per ad.
- **Operational Savings:** Replaced external manual review teams, eliminated GPU infrastructure expenses, and significantly improved platform content hygiene.

> **Note:** This same architectural framework was also extended to handle text-based Illegal Content Detection (meeting strict regulatory compliance requirements) and Image Illegal Content Detection (using CNNs to flag illegal visual content across categories with high visual overlap, achieving an ultra-fast inference speed of 0.3s to 0.7s per image). Currently, all three systems are deployed and running live in production, saving the company thousands of Euros yearly in operational and moderation costs. None of these systems use LLMs at runtime—while leveraging an LLM is often the easiest path to a working prototype, hosting them locally or calling third-party APIs at high daily volumes introduces unsustainable hosting costs, infrastructure overhead, and latency. Deploying fine-tuned specialized models and CNNs optimized via ONNX Runtime on CPU infrastructure delivers near-zero inference costs while maintaining high speed and precision.

