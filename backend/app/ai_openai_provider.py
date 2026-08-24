"""OpenAI-compatible structured-output provider.

The trading application receives only JSON strategy candidates. API keys must
be supplied through environment/secret management; none are stored in source.
"""
from __future__ import annotations

import json
import os
from typing import Any

from app.ai_provider import AIProvider


class OpenAIStrategyProvider(AIProvider):
    def __init__(self, client: Any | None = None, model: str | None = None):
        self.model = model or os.getenv("AI_STRATEGY_MODEL", "gpt-5-mini")
        self._client = client

    @property
    def client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("OpenAI SDK is not installed") from exc
            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    def generate_structured(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text={"format": {"type": "json_object"}},
        )
        output_text = getattr(response, "output_text", None)
        if not output_text:
            raise RuntimeError("AI provider returned no structured output")
        candidate = json.loads(output_text)
        if not isinstance(candidate, dict):
            raise RuntimeError("AI provider returned a non-object JSON value")
        return candidate
