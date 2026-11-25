"""Gemini image generation over the REST API (free tier), as a second image generator.

Only image generation runs here; checks (CLIP, OCR), the language model and translation stay on the
Kaggle notebook. Availability is reported only from real answers:
- check(): GET models/{model} must succeed and list generateContent. That proves the key and model,
  not the image quota; quota is known only after a generation, so the status says which it is.
- a 429 on generation starts a cool-down (the server's retryDelay, else 60 s; a daily quota lasts
  until it resets at midnight Pacific time), during which Gemini is reported unavailable.
The API key is sent only in the x-goog-api-key header and never logged or returned.
"""
from __future__ import annotations

import base64
import io
import math
import re
import threading
import time
from datetime import datetime, timedelta, timezone

import httpx
from PIL import Image

from .retry import pace

API = "https://generativelanguage.googleapis.com/v1beta"
RATIOS = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"]
CHECK_SECONDS = 300
DEFAULT_COOLDOWN = 60.0


class GeminiUnavailable(RuntimeError):
    """Gemini cannot make an image right now (quota, key, network or server); another provider may."""


def nearest_ratio(width: int, height: int) -> str:
    target = math.log(width / height)
    return min(RATIOS, key=lambda r: abs(math.log(int(r.split(":")[0]) / int(r.split(":")[1])) - target))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_pacific_midnight(now: datetime) -> datetime:
    # Pacific time is UTC-8 (UTC-7 in summer); UTC-8 is used, so the estimate is never early.
    local = now - timedelta(hours=8)
    midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(hours=8)


class GeminiImage:
    def __init__(self, api_key: str, model: str, min_interval: float = 6.0,
                 transport: httpx.BaseTransport | None = None):
        self.name = f"gemini:{model}"
        self.model = model
        self._min_interval = min_interval
        self._client = httpx.Client(
            base_url=API, headers={"x-goog-api-key": api_key},
            timeout=httpx.Timeout(120, connect=10), transport=transport,
        )
        self._lock = threading.Lock()
        self.available = False
        self.detail = "Not checked yet."
        self.checked_at: datetime | None = None
        self.cooldown_until: datetime | None = None
        self.last_image_at: datetime | None = None

    # ---- status -------------------------------------------------------------------------------
    def cooling(self) -> bool:
        return self.cooldown_until is not None and _now() < self.cooldown_until

    def check(self, force: bool = False) -> bool:
        """True when the key and model answered (cached 5 min) and no cool-down is running."""
        with self._lock:
            fresh = self.checked_at and (_now() - self.checked_at).total_seconds() < CHECK_SECONDS
            if force or not fresh:
                self.available, self.detail = self._probe()
                self.checked_at = _now()
            if self.available and self.cooling():
                return False
            return self.available

    def _probe(self) -> tuple[bool, str]:
        try:
            response = self._client.get(f"/models/{self.model}")
        except httpx.HTTPError:
            return False, "Cannot reach the Gemini API (network)."
        if response.status_code in (400, 401, 403):
            return False, "Gemini rejected the API key. Check GEMINI_API_KEY in backend/.env."
        if response.status_code == 404:
            return False, f"Gemini has no model named {self.model}. Check GEMINI_IMAGE_MODEL in backend/.env."
        if response.status_code == 429:
            self._start_cooldown(response)
            return True, "Key and model are valid, but the rate limit was reached."
        if response.status_code >= 400:
            return False, f"Gemini answered {response.status_code} to the model check."
        methods = response.json().get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            return False, f"{self.model} does not support generateContent."
        if self.last_image_at:
            return True, f"Model reachable; last image generated {self.last_image_at:%Y-%m-%d %H:%M} UTC."
        return True, "Key and model are valid. Image quota is confirmed only by the first generation."

    def status_detail(self) -> str:
        if self.cooling():
            return self._cooldown_reason
        return self.detail

    _cooldown_reason = ""

    def _start_cooldown(self, response: httpx.Response) -> str:
        text = response.text
        if re.search(r"PerDay|per day", text, re.IGNORECASE):
            self.cooldown_until = _next_pacific_midnight(_now())
            self._cooldown_reason = ("The free daily Gemini image quota is used up; it resets at midnight "
                                     "Pacific time.")
        else:
            delay = DEFAULT_COOLDOWN
            match = re.search(r'"retryDelay"\s*:\s*"([\d.]+)s"', text)
            if match:
                delay = float(match.group(1)) + 1
            self.cooldown_until = _now() + timedelta(seconds=delay)
            self._cooldown_reason = f"Gemini rate limit reached; available again in about {round(delay)} s."
        if re.search(r"limit:\s*0\b", text):
            # Google's quota for this key and model is zero: waiting will not help. Checked again after
            # the daily reset in case the plan changes.
            self.cooldown_until = _next_pacific_midnight(_now())
            self._cooldown_reason = (
                f"This key's free tier includes no image generation for {self.model} (Google's limit is 0), "
                "so waiting will not help. Enable billing for the key, or set GEMINI_IMAGE_MODEL to a model "
                "with free image quota. Automatic mode uses the Kaggle notebook meanwhile.")
        return self._cooldown_reason

    # ---- generation ---------------------------------------------------------------------------
    def generate(self, prompt: str, negative_prompt: str, width: int, height: int, seed: int,
                 select_text: str = "", control_image: bytes | None = None, **_: object) -> bytes:
        if control_image is not None:
            raise RuntimeError("This picture level needs ControlNet, which only the Kaggle notebook has.")
        if self.cooling():
            raise GeminiUnavailable(self._cooldown_reason)
        text = prompt + (f". Avoid: {negative_prompt}." if negative_prompt else "")
        body = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": nearest_ratio(width, height)}},
        }
        pace(self._min_interval)
        try:
            response = self._client.post(f"/models/{self.model}:generateContent", json=body)
        except httpx.HTTPError as exc:
            raise GeminiUnavailable("Cannot reach the Gemini API (network).") from exc
        if response.status_code == 429:
            raise GeminiUnavailable(self._start_cooldown(response))
        if response.status_code in (400, 401, 403) and "API_KEY" in response.text.upper():
            self.available, self.detail, self.checked_at = False, "Gemini rejected the API key.", _now()
            raise GeminiUnavailable(self.detail)
        if response.status_code >= 500:
            raise GeminiUnavailable(f"Gemini is busy or failing ({response.status_code}); try again later.")
        if response.status_code >= 400:
            raise RuntimeError(f"Gemini refused the request ({response.status_code}): {response.text[:200]}")
        data = response.json()
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    image = Image.open(io.BytesIO(base64.b64decode(inline["data"]))).convert("RGB")
                    if image.size != (width, height):
                        image = image.resize((width, height), Image.LANCZOS)
                    out = io.BytesIO()
                    image.save(out, format="PNG")
                    self.last_image_at = _now()
                    self.available, self.checked_at = True, _now()
                    self.detail = f"Generated an image at {self.last_image_at:%Y-%m-%d %H:%M} UTC."
                    return out.getvalue()
        reason = (data.get("candidates") or [{}])[0].get("finishReason") or \
            data.get("promptFeedback", {}).get("blockReason") or "no image in the reply"
        raise GeminiUnavailable(f"Gemini returned no image ({reason}).")


__all__ = ["GeminiImage", "GeminiUnavailable", "nearest_ratio"]
_ = time  # pacing uses time through retry.pace
