"""Runtime configuration loaded from environment variables / .env. """

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Optional LLM drafting. Off by default — rule-based path always works.
    llm_enabled: bool = False
    openai_api_key: str | None = None
    model_name: str | None = None

    # Server.
    port: int = 8000


settings = Settings()
