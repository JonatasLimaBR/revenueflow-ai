from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ChannelOutbound = Literal["fake", "real"]
TracerSink = Literal["langfuse", "otel", "noop"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    channel_outbound: ChannelOutbound = "fake"
    tracer_sink: TracerSink = "noop"
    llm_stub: bool = True
    gemini_model: str = "gemini-2.0-flash"

    database_url: str = "postgresql://revenueflow:revenueflow@localhost:5432/revenueflow"
    pubsub_emulator_host: str = ""
    pubsub_project_id: str = "revenueflow-local"

    pricing_min_margin_pct: Decimal = Decimal("0.15")
    pricing_max_discount_pct: Decimal = Decimal("0.10")

    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
