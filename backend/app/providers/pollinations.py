"""Pollinations image API: free, no key. Used when no paid image credits are available."""
from __future__ import annotations

import io
from urllib.parse import quote

import httpx
from PIL import Image


class PollinationsImage:
    def __init__(self, model: str, base_url: str):
        self.name = f"pollinations:{model}"
        self._model = model
        self._base_url = base_url.rstrip("/")

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int, seed: int) -> bytes:
        # This API has no negative-prompt field. Listing unwanted things in the prompt tends to
        # produce them, so the negative prompt is deliberately not used here.
        text = prompt
        url = f"{self._base_url}/{quote(text[:1500], safe='')}"
        params = {"width": width, "height": height, "seed": seed, "model": self._model, "nologo": "true"}
        last_error: Exception | None = None
        for _ in range(2):  # one retry: the free service is sometimes busy
            try:
                response = httpx.get(url, params=params, timeout=180, follow_redirects=True)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content)).convert("RGB")
                if image.size != (width, height):
                    image = image.resize((width, height))
                buffer = io.BytesIO()
                image.save(buffer, format="PNG")
                return buffer.getvalue()
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Pollinations image request failed: {last_error}")
