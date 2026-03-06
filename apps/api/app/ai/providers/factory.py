from app.ai.providers.base import AIProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.config import settings


class NoopProvider(AIProvider):
    def complete(self, prompt: str, *, json_mode: bool = False, temperature: float = 0.1) -> str:
        if json_mode:
            return "{}"
        return ""


def get_provider() -> AIProvider:
    if settings.ai_provider == "openai" and settings.openai_api_key:
        return OpenAIProvider()
    return NoopProvider()
