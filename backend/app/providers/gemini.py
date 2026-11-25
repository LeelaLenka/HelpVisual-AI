"""Gemini adapters for text, vision and (optionally) image generation."""
from __future__ import annotations

import io
import time  # noqa: F401  (tests patch time.sleep through this module)

from google import genai
from google.genai import types
from PIL import Image

from .base import T
from .retry import DailyQuotaExceeded, is_switchable, pace, with_retry  # noqa: F401

class GeminiLLM:
    def __init__(self, api_key: str, model: str, min_interval: float = 0.0, fallback_model: str = ""):
        self._models = [model] + ([fallback_model] if fallback_model and fallback_model != model else [])
        self.name = "gemini:" + " -> ".join(self._models)
        self._min_interval = min_interval
        self._client = genai.Client(api_key=api_key)
        self.last_model = model  # which model answered the most recent call

    def _call(self, contents: list, config: types.GenerateContentConfig):
        """Tries the main model, then the fallback when the main one is overloaded or out of quota.

        Errors caused by the request itself (bad input, invalid key) are raised at once, since a
        different model would fail the same way.
        """
        for position, model in enumerate(self._models):
            def once(model: str = model):
                pace(self._min_interval)
                return self._client.models.generate_content(model=model, contents=contents, config=config)

            try:
                response = with_retry(once, label=f"gemini:{model}")
                self.last_model = model
                return response
            except Exception as exc:
                if not is_switchable(exc) or position == len(self._models) - 1:
                    raise
        raise RuntimeError("unreachable")

    @staticmethod
    def _contents(prompt: str, images: list[bytes] | None) -> list:
        parts = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images or []]
        return [*parts, prompt]

    def generate_json(self, prompt: str, schema: type[T], images: list[bytes] | None = None) -> T:
        config = types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=schema, temperature=0.2
        )
        contents = self._contents(prompt, images)
        response = self._call(contents, config)
        return schema.model_validate_json(response.text or "")

    def generate_text(self, prompt: str, images: list[bytes] | None = None) -> str:
        config = types.GenerateContentConfig(temperature=0.3)
        contents = self._contents(prompt, images)
        response = self._call(contents, config)
        return (response.text or "").strip()


class GeminiImage:
    def __init__(self, api_key: str, model: str):
        self.name = f"gemini:{model}"
        self._model = model
        self._client = genai.Client(api_key=api_key)

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int, seed: int) -> bytes:
        full_prompt = f"{prompt}\nDo not include: {negative_prompt}." if negative_prompt else prompt
        response = self._client.models.generate_content(
            model=self._model,
            contents=full_prompt,
            config=types.GenerateContentConfig(response_modalities=["IMAGE"], seed=seed),
        )
        for candidate in response.candidates or []:
            for part in (candidate.content.parts if candidate.content else []) or []:
                if part.inline_data and part.inline_data.data:
                    image = Image.open(io.BytesIO(part.inline_data.data)).convert("RGB")
                    image = image.resize((width, height))
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG")
                    return buffer.getvalue()
        raise RuntimeError("The image model returned no image.")
