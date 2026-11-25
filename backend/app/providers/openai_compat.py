"""Client for the ML server's language model, which speaks the OpenAI chat format.

The same client works with any self-hosted OpenAI-compatible server, such as Ollama.

Structured output: the JSON Schema is put in the prompt, JSON mode is requested where the
service supports it, and the reply is validated with Pydantic. An invalid reply gets one
correction round with the validation error.
"""
from __future__ import annotations

import base64
import json

import httpx
from pydantic import ValidationError

from .base import T
from .retry import pace, with_retry


class ProviderHTTPError(RuntimeError):
    def __init__(self, code: int, message: str):
        super().__init__(f"{code} {message}")
        self.code = code


def extract_json(text: str) -> str:
    """Takes the JSON object out of a reply that may be wrapped in a code fence or prose."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("The reply contained no JSON object.")
    return text[start : end + 1]


class OpenAICompatLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        min_interval: float = 0.0,
        label: str = "openai",
        transport: httpx.BaseTransport | None = None,
    ):
        self.name = f"{label}:{model}"
        self._model = model
        self._min_interval = min_interval
        self._json_mode_supported = True
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=httpx.Timeout(300, connect=15),
            transport=transport,
        )

    @staticmethod
    def _messages(prompt: str, images: list[bytes] | None) -> list[dict]:
        if not images:
            return [{"role": "user", "content": prompt}]
        parts = [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(img).decode()}}
            for img in images
        ]
        return [{"role": "user", "content": [*parts, {"type": "text", "text": prompt}]}]

    def _post(self, body: dict) -> str:
        pace(self._min_interval)
        try:
            response = self._client.post("/chat/completions", json=body)
        except httpx.TransportError as exc:
            raise ProviderHTTPError(503, f"UNAVAILABLE: could not reach {self.name} ({exc})") from exc
        if response.status_code >= 400:
            detail = response.text[:400]
            if retry_after := response.headers.get("retry-after"):
                detail += f" (retry in {retry_after}s)"
            raise ProviderHTTPError(response.status_code, detail)
        data = response.json()
        if "error" in data:  # the Kaggle server reports failures in the body of a streamed reply
            error = data["error"]
            raise ProviderHTTPError(500, str(error.get("message", error) if isinstance(error, dict) else error))
        return data["choices"][0]["message"]["content"] or ""

    def _complete(self, messages: list[dict], json_mode: bool, temperature: float) -> str:
        def once() -> str:
            body = {"model": self._model, "messages": messages, "temperature": temperature}
            if json_mode and self._json_mode_supported:
                body["response_format"] = {"type": "json_object"}
            try:
                return self._post(body)
            except ProviderHTTPError as exc:
                # Some models reject JSON mode; the schema in the prompt still guides them.
                if exc.code == 400 and "response_format" in str(exc) and "response_format" in body:
                    self._json_mode_supported = False
                    del body["response_format"]
                    return self._post(body)
                raise

        return with_retry(once, label=self.name)

    def generate_json(self, prompt: str, schema: type[T], images: list[bytes] | None = None) -> T:
        full = (
            f"{prompt}\n\nReply with one JSON object only, with no other text, "
            f"matching this JSON Schema:\n{json.dumps(schema.model_json_schema())}"
        )
        reply = self._complete(self._messages(full, images), json_mode=True, temperature=0.2)
        try:
            return schema.model_validate_json(extract_json(reply))
        except (ValidationError, ValueError) as exc:
            correction = (
                f"{full}\n\nYour previous reply was not valid: {str(exc)[:600]}\n"
                "Reply again with the corrected JSON object only."
            )
            reply = self._complete(self._messages(correction, images), json_mode=True, temperature=0.0)
            return schema.model_validate_json(extract_json(reply))

    def generate_text(self, prompt: str, images: list[bytes] | None = None) -> str:
        return self._complete(self._messages(prompt, images), json_mode=False, temperature=0.3).strip()
