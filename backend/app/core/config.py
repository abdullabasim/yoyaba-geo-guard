"""Application settings, read from environment / .env by pydantic-settings.

Every value the code depends on is declared here. Nothing else in the codebase
may read ``os.environ`` directly, so this module is the single source of truth
for configuration and the reference list for ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- General ----------------------------------------------------
    app_env: Literal["local", "staging", "production"] = "local"
    debug: bool = True
    log_level: str = "INFO"
    project_name: str = "YOYABA GEO & IntentShift Guard"
    api_v1_prefix: str = "/api/v1"

    # -- Database ---------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://seo:change-me-postgres@postgres:5432/seo_intent",
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # -- Celery / Redis ---------------------------------------------
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # -- Auth -------------------------------------------------------
    jwt_secret_key: str = "change-me-to-a-long-random-hex-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 720
    first_admin_email: str = "admin@yoyaba.com"
    first_admin_password: str = "Yyba-x8F2-mP9q-L5k1"

    # -- Demo data --------------------------------------------------
    #: Insert a realistic demo hierarchy on first start, but only when the
    #: database has no clients at all. Never touches existing data.
    seed_demo_data: bool = False
    #: Generate backdated ranking history for the demo keywords. Offline and
    #: free: seeding makes no SERP provider calls.
    seed_demo_history: bool = False

    # -- DataForSEO -------------------------------------------------
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    dataforseo_base_url: str = "https://api.dataforseo.com"
    dataforseo_depth: int = 10
    dataforseo_timeout_seconds: float = 60.0
    dataforseo_mock: bool = False
    dataforseo_fallback_mock_on_auth_error: bool = True
    #: Number of keywords sent in a single DataForSEO API call. The provider
    #: accepts up to 100 tasks per request. Start low (10) for initial testing.
    dataforseo_batch_size: int = Field(default=10, ge=1, le=100)

    # -- DataForSEO rate control ------------------------------------
    #: Sliding-window cap shared by every worker process. 0 disables pacing.
    #: Beat expands due URLs into one task per keyword and enqueues them
    #: together, so without this a nightly batch fires as one burst.
    dataforseo_max_requests_per_minute: int = 60
    #: How many provider calls may be in flight at once, across all processes.
    #: An in-process semaphore cannot express this: 4 prefork workers each
    #: honouring "5 concurrent" would allow 20.
    dataforseo_max_concurrent_requests: int = 5
    #: Hard ceiling on requests per UTC day. 0 disables the budget. This is a
    #: cost guardrail; the SERP_FETCH kill switch is the hard stop.
    dataforseo_daily_request_budget: int = 0
    #: How long a task may wait for a slot before deferring. Kept short: a task
    #: sleeping in a worker slot blocks other work.
    dataforseo_rate_limit_max_wait_seconds: float = 30.0
    #: Delay before a rate-limit-deferred check is retried by Celery.
    dataforseo_rate_limit_retry_delay_seconds: int = 120
    #: How many times a deferred check is retried before giving up for this
    #: cycle. The observation is simply skipped; the next interval picks it up.
    dataforseo_rate_limit_max_retries: int = 5
    #: Fallback pause after a 429 that carries no usable Retry-After header.
    dataforseo_rate_limit_penalty_seconds: float = 60.0
    #: Logical Redis DB for rate-limiter state. Separate from broker (0),
    #: results (1) and alert state (2).
    rate_limit_redis_db: int = 3

    # -- OpenAI -------------------------------------------------
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 90.0
    openai_max_retries: int = 3
    openai_mock: bool = False
    openai_fallback_mock_on_auth_error: bool = True

    # -- LangSmith --------------------------------------------------
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_api_key: str = ""
    langsmith_project: str = "seo-intent-shift"

    # -- Slack ------------------------------------------------------
    #: Master switch for ALL Slack delivery. False means no HTTP request is ever
    #: made to Slack, whatever the webhook URLs say. Set false while testing so
    #: a real channel is not filled with noise from generated data.
    slack_enabled: bool = True
    #: Business alerts (intent shift detected). Independent of error alerts so a
    #: noisy customer channel can be silenced without going blind to failures.
    slack_business_alerts_enabled: bool = True
    #: Log the full message that WOULD have been sent whenever delivery is
    #: disabled. This is what makes testing with Slack off useful: the content is
    #: still verifiable, only the network call is skipped.
    slack_log_suppressed_messages: bool = True
    slack_webhook_alerts: str = ""
    slack_webhook_errors: str = ""

    # -- Error alerting --------------------------------------------
    #: Master switch for operator error alerts (business alerts are unaffected).
    error_alerts_enabled: bool = True
    #: Quiet period per (category, scope). Systemic categories use 3x this.
    #: Without throttling, one upstream outage sends one message per keyword.
    alert_throttle_seconds: int = 900
    #: How often the health monitor probes the database, Redis and credentials.
    health_check_interval_seconds: int = 300
    #: Alert when an API request fails on a database error.
    alert_on_api_database_errors: bool = True
    #: Logical Redis DB for alert de-duplication state. Separate from the Celery
    #: broker (0) and result backend (1) so flushing it cannot disturb queued work.
    alert_state_redis_db: int = 2

    # -- Business rules ---------------------------------------------
    rank_drop_threshold: int = 3
    beat_dispatch_interval_seconds: int = 300
    due_window_minutes: int = 30

    # -- Frontend / CORS --------------------------------------------
    frontend_url: str = "http://localhost:3100"

    # -- MCP --------------------------------------------------------
    mcp_server_name: str = "seo-intent-db"

    # -- Derived ----------------------------------------------------
    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origins(self) -> list[str]:
        """Allowed browser origins. Local dev ports are always permitted."""
        origins = {
            self.frontend_url.rstrip("/"),
            "http://localhost:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3100",
        }
        return sorted(o for o in origins if o)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def error_webhook(self) -> str:
        """System-failure webhook, falling back to the business alert hook."""
        return self.slack_webhook_errors or self.slack_webhook_alerts

    @computed_field  # type: ignore[prop-decorator]
    @property
    def business_alerts_deliverable(self) -> bool:
        """Whether an intent-shift alert can actually reach Slack right now.

        Three independent reasons it cannot: the master switch, the per-channel
        switch, or a missing webhook URL. Collapsing them into one property means
        callers cannot check two of the three and forget the rest.
        """
        return bool(
            self.slack_enabled
            and self.slack_business_alerts_enabled
            and self.slack_webhook_alerts
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def error_alerts_deliverable(self) -> bool:
        """Same for operator error alerts."""
        return bool(
            self.slack_enabled and self.error_alerts_enabled and self.error_webhook
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def slack_configured(self) -> bool:
        """At least one webhook URL is present, regardless of the switches."""
        return bool(self.slack_webhook_alerts or self.slack_webhook_errors)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tracing_enabled(self) -> bool:
        """LangSmith is only usable when explicitly enabled AND keyed."""
        return bool(self.langsmith_tracing and self.langsmith_api_key)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def serp_provider_configured(self) -> bool:
        return bool(self.dataforseo_login and self.dataforseo_password)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def alert_state_redis_url(self) -> str:
        """Broker URL with the database index swapped for the alert-state DB."""
        base = self.celery_broker_url.rsplit("/", 1)[0]
        return f"{base}/{self.alert_state_redis_db}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rate_limit_redis_url(self) -> str:
        """Broker URL with the database index swapped for the rate-limit DB."""
        base = self.celery_broker_url.rsplit("/", 1)[0]
        return f"{base}/{self.rate_limit_redis_db}"


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so every module shares one Settings instance."""
    return Settings()


settings = get_settings()
