import json

from openai import OpenAI

from app.ai.providers.base import AIProvider
from app.core.config import settings


class OpenAIProvider(AIProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)

    def complete(self, prompt: str, *, json_mode: bool = False, temperature: float = 0.1) -> str:
        response = self.client.responses.create(
            model=settings.openai_model,
            input=prompt,
            temperature=temperature,
            response_format={"type": "json_object"} if json_mode else None,
        )
        text = response.output_text.strip()
        if json_mode:
            json.loads(text)
        return text
