from functools import lru_cache

from openai import AsyncOpenAI

from core.config import settings


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.open_ai_api_key)
