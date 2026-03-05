"""Model strategy config with DeepSeek default and OpenAI swap."""
import os
from pathlib import Path

MODEL_CONFIGS = {
    "deepseek": {
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
    },
}

ACTIVE_MODEL = os.environ.get("ACTIVE_MODEL", "deepseek")

VOLUME_PATH = Path("/data")


def get_llm_client():
    """Return (AsyncOpenAI client, model_name) tuple for the active model."""
    cfg = MODEL_CONFIGS[ACTIVE_MODEL]
    from openai import AsyncOpenAI

    return (
        AsyncOpenAI(
            api_key=os.environ[cfg["api_key_env"]],
            base_url=cfg["base_url"],
        ),
        cfg["model"],
    )
