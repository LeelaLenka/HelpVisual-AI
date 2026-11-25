"""Stable Diffusion XL through the Hugging Face Inference API (no local GPU needed)."""
from __future__ import annotations

import io

from huggingface_hub import InferenceClient


class HuggingFaceImage:
    def __init__(self, token: str, model: str):
        self.name = f"huggingface:{model}"
        self._model = model
        self._client = InferenceClient(token=token)

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int, seed: int) -> bytes:
        image = self._client.text_to_image(
            prompt,
            negative_prompt=negative_prompt or None,
            model=self._model,
            width=width,
            height=height,
            seed=seed,
        )
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="PNG")
        return buffer.getvalue()
