from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ChannelOutbound = Literal["fake", "real"]
TracerSink = Literal["langfuse", "otel", "noop"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    channel_outbound: ChannelOutbound = "fake"
    tracer_sink: TracerSink = "noop"
    llm_stub: bool = True
    gemini_model: str = "gemini-2.5-flash"
    google_cloud_project: str = ""
    vertex_location: str = "global"
    llm_max_retries: int = 2
    run_consumer: bool = False

    database_url: str = "postgresql://revenueflow:revenueflow@localhost:5432/revenueflow"
    pubsub_emulator_host: str = ""
    pubsub_project_id: str = "revenueflow-local"

    pricing_min_margin_pct: Decimal = Decimal("0.15")
    pricing_max_discount_pct: Decimal = Decimal("0.10")

    approval_api_token: str = ""
    approval_ttl_hours: int = 24

    replenishment_threshold: float = 1.5
    quote_recovery_hours: int = 72
    campaign_frequency_cap_days: int = 14

    # PRD-010: the remaining 6 opportunity types (ADR-079). CHURN/REACTIVATION
    # share the same "time since last purchase" signal as REPLENISHMENT, just
    # at a higher multiplier -- REACTIVATION is strictly the more severe tier.
    churn_threshold: float = 3.0
    reactivation_threshold: float = 6.0
    order_recovery_hours: int = 24
    upsell_min_repeat_purchases: int = 2
    inventory_to_cash_stock_threshold: int = 10
    inventory_to_cash_stale_days: int = 60

    bigquery_dataset: str = "revenueflow_analytics"

    lead_stale_days: int = 30

    handoff_api_token: str = ""
    handoff_min_confidence: float = 0.55
    handoff_high_value_threshold: Decimal = Decimal("50000")
    handoff_stale_hours: int = 24

    audit_enabled: bool = True

    llm_call_timeout_s: float = 6.0
    db_statement_timeout_ms: int = 3000
    # 15s wasn't enough headroom for 2 sequential real Gemini calls
    # (classify_intent + recommendation) plus DB overhead in practice — a
    # turn that hit no bug and no retry still took ~30s live, tripping the
    # _SLOW_REPLY fallback instead of returning the real answer.
    turn_budget_s: float = 25.0

    log_level: str = "INFO"
    otel_service_name: str = "revenueflow-api"

    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    @field_validator("langfuse_host", "langfuse_public_key", "langfuse_secret_key", mode="before")
    @classmethod
    def _strip_langfuse_value(cls, value: str) -> str:
        # Found live (2026-09-11): "Langfuse ainda sem dados" traced all the
        # way down to `Illegal header value b'pk-lf-...\r\n'` -- the secret
        # was stored with a trailing CRLF (almost certainly `echo` without
        # `-n`, or a CRLF-terminated file, when the value was populated into
        # Secret Manager). Python's http.client refuses to send a header
        # value containing CR/LF, so the SDK's every request failed before
        # it ever left the process -- with no structured status code, so it
        # always surfaced as the SDK's generic "Unexpected error occurred",
        # never anything actionable. Stripping here fixes it regardless of
        # how the secret gets populated, without needing to touch the stored
        # value itself.
        return value.strip() if isinstance(value, str) else value

    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""

    revenueflow_api_base_url: str = "http://localhost:8080"
    mcp_api_token: str = ""

    portal_viewer_emails: str = ""
    portal_google_client_id: str = ""
    portal_session_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
