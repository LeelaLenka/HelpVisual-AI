"""Chooses the image generator for each call: Gemini, the Kaggle notebook, or Gemini then Kaggle.

Modes (saved in data/providers.json, first default from IMAGE_MODE):
- gemini: Gemini only.
- kaggle: the Kaggle notebook only.
- auto:   Gemini when it is configured, answered its check and is not cooling down; otherwise Kaggle
          when its runtime answers. A Gemini quota or availability error during a run is retried on
          Kaggle when Kaggle answers.
Calls that need ControlNet (a control image) always go to Kaggle.

The checks and the other models (CLIP + OCR verification, OCR word boxes, translation) exist only
on the Kaggle notebook. The router offers them (clip_check, ocr, can_read_layout, ...) only while
the notebook answers, so the pipeline's hasattr() tests stay truthful: when Kaggle is down those
abilities are absent, never faked.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .gemini_image import GeminiImage, GeminiUnavailable
from .status import OFFLINE, is_offline

MODES = ("auto", "gemini", "kaggle")
KAGGLE_ONLY = ("clip_check", "ocr", "can_read_layout", "can_translate", "translate", "features")


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class ImageRouter:
    def __init__(self, data_dir: Path, gemini: GeminiImage | None, kaggle, kaggle_probe: Callable[[], bool],
                 default_mode: str = "auto"):
        self._file = Path(data_dir) / "providers.json"
        self.gemini = gemini
        self.kaggle = kaggle  # MLEndpoint or None
        self._probe = kaggle_probe
        self._lock = threading.Lock()
        self.kaggle_checked_at: datetime | None = None
        self._kaggle_up_before = False
        self.last_used: dict | None = None
        self.last_provider = ""
        self.mode = self._load(default_mode if default_mode in MODES else "auto")

    @property
    def name(self) -> str:
        return f"router:{self.mode}"

    # ---- mode ---------------------------------------------------------------------------------
    def _load(self, default: str) -> str:
        try:
            mode = json.loads(self._file.read_text(encoding="utf-8")).get("mode", default)
            return mode if mode in MODES else default
        except (OSError, ValueError):
            return default

    def set_mode(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"Unknown mode. Choose one of: {', '.join(MODES)}.")
        self.mode = mode
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps({"mode": mode}), encoding="utf-8")

    # ---- availability -------------------------------------------------------------------------
    def kaggle_available(self) -> bool:
        if self.kaggle is None:
            return False
        up = bool(self._probe())
        self.kaggle_checked_at = datetime.now(timezone.utc)
        if up and not self._kaggle_up_before and hasattr(self.kaggle, "_features"):
            self.kaggle._features = None  # the notebook came back: read its loaded models again
        self._kaggle_up_before = up
        return up

    def gemini_available(self, force: bool = False) -> bool:
        return self.gemini is not None and self.gemini.check(force)

    def order(self) -> list[str]:
        return {"gemini": ["gemini"], "kaggle": ["kaggle"], "auto": ["gemini", "kaggle"]}[self.mode]

    def active(self) -> str | None:
        """The provider a new image would use right now, or None."""
        for provider in self.order():
            if provider == "gemini" and self.gemini_available():
                return "gemini"
            if provider == "kaggle" and self.kaggle_available():
                return "kaggle"
        return None

    def unavailable_message(self) -> str:
        if self.mode == "kaggle":
            return OFFLINE
        gemini = ("Gemini is not configured: add GEMINI_API_KEY to backend/.env and restart the backend."
                  if self.gemini is None else f"Gemini is not available: {self.gemini.status_detail()}")
        return gemini if self.mode == "gemini" else f"No image generator is available. {gemini} {OFFLINE}"

    @property
    def verifier_offline(self) -> bool:
        """True when the checks (CLIP, OCR) cannot run because the Kaggle notebook does not answer."""
        return not self.kaggle_available()

    def __getattr__(self, name: str):
        # Kaggle-only abilities exist on the router only while the notebook answers.
        if name in KAGGLE_ONLY and self.__dict__.get("kaggle") is not None and self.kaggle_available():
            return getattr(self.kaggle, name)
        raise AttributeError(name)

    # ---- generation ---------------------------------------------------------------------------
    def _record(self, provider: str, ok: bool, detail: str) -> None:
        self.last_used = {"provider": provider, "at": datetime.now(timezone.utc).isoformat(), "ok": ok,
                          "detail": detail[:300]}
        if ok:
            self.last_provider = provider

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int, seed: int, **extra) -> bytes:
        if extra.get("control_image") is not None:
            if self.mode == "gemini":
                raise RuntimeError("This picture level needs ControlNet, which runs only on the Kaggle notebook. "
                                   "Switch image generation to Kaggle or Automatic in Settings.")
            order = ["kaggle"]
        else:
            order = self.order()
        errors: list[str] = []
        for provider in order:
            if provider == "gemini":
                if self.gemini is None or not self.gemini_available():
                    errors.append(self.unavailable_message() if self.mode == "gemini" else
                                  f"Gemini skipped: {self.gemini.status_detail() if self.gemini else 'not configured'}.")
                    continue
                try:
                    image = self.gemini.generate(prompt, negative_prompt, width, height, seed, **extra)
                except GeminiUnavailable as exc:
                    self._record("gemini", False, str(exc))
                    errors.append(f"Gemini: {exc}")
                    continue
                self._record("gemini", True, f"Image from {self.gemini.name}.")
                return image
            if self.kaggle is None or not self.kaggle_available():
                errors.append(OFFLINE)
                continue
            try:
                image = self.kaggle.generate(prompt, negative_prompt, width, height, seed, **extra)
            except Exception as exc:
                self._record("kaggle", False, str(exc))
                raise
            self._record("kaggle", True, "Image from the Kaggle notebook (SDXL).")
            return image
        message = " ".join(dict.fromkeys(errors)) or self.unavailable_message()
        if self.mode == "gemini" and not is_offline(RuntimeError(message)):
            raise GeminiUnavailable(message)
        raise RuntimeError(message)

    # ---- status for the API -------------------------------------------------------------------
    def status(self, force: bool = False) -> dict:
        with self._lock:
            if force and self.gemini is not None:
                self.gemini.check(force=True)
            gemini_ok = self.gemini_available()
            kaggle_ok = self.kaggle_available()
            features: list[str] = []
            if kaggle_ok and self.kaggle is not None and hasattr(self.kaggle, "features"):
                if force:
                    self.kaggle._features = None
                features = sorted(k for k, v in (self.kaggle.features() or {}).items()
                                  if v and k not in ("status", "ok"))
            active = next((p for p in self.order() if (p == "gemini" and gemini_ok) or (p == "kaggle" and kaggle_ok)), None)
            g = self.gemini
            return {
                "mode": self.mode,
                "active": active,
                "gemini": {
                    "configured": g is not None,
                    "available": gemini_ok,
                    "model": g.model if g else None,
                    "detail": (g.status_detail() if g else "Not configured: add GEMINI_API_KEY to backend/.env."),
                    "checked_at": _iso(g.checked_at) if g else None,
                    "cooldown_until": _iso(g.cooldown_until) if g and g.cooling() else None,
                    "last_image_at": _iso(g.last_image_at) if g else None,
                },
                "kaggle": {
                    "configured": self.kaggle is not None,
                    "available": kaggle_ok,
                    "features": features,
                    "detail": ("Notebook answering." if kaggle_ok else
                               OFFLINE if self.kaggle is not None else
                               "Not configured: paste the notebook's ML_ENDPOINT lines into backend/.env."),
                    "checked_at": _iso(self.kaggle_checked_at),
                },
                "last_used": self.last_used,
            }
