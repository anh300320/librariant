from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class LlmSettings(BaseSettings):
    """LLM settings, read from LLM_* env vars (e.g. LLM_MODEL, LLM_EFFORT).

    The Anthropic API key itself is read by the SDK from ANTHROPIC_API_KEY.
    """

    model_config = SettingsConfigDict(env_prefix="LLM_")

    model: str = "claude-haiku-5-5"
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    max_tokens: int = 16000
    timeout_sec: float = 120.0
    max_retries: int = 2


llm_settings = LlmSettings()
