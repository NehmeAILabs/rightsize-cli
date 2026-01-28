from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str
    max_concurrency: int = 10
    timeout_seconds: float = 60.0

    model_config = {
        "env_prefix": "RIGHTSIZE_",
        "env_file": ".env",
    }
