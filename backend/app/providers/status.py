"""Whether the AI server (the Kaggle notebook) can be reached, and one clear message when it cannot.

Every request that needs the AI server turns "cannot connect" errors into OFFLINE, so the person
sees what to do instead of a raw connection error.
"""
from __future__ import annotations

import threading
import time

import httpx

OFFLINE = (
    "The AI server is offline: start the Kaggle notebook and paste its lines into backend/.env, "
    "then restart the backend."
)

_MARKERS = ("UNAVAILABLE: could not reach", "Cannot reach the ML server", "The AI server is offline",
            "not connected")


def is_offline(exc: BaseException | None) -> bool:
    """True when the error (or anything that caused it) means the AI server could not be reached."""
    from .base import ProviderNotConfigured

    seen = 0
    while exc is not None and seen < 8:
        if isinstance(exc, (ProviderNotConfigured, httpx.TransportError)):
            return True
        if any(marker in str(exc) for marker in _MARKERS):
            return True
        exc = exc.__cause__ or exc.__context__
        seen += 1
    return False


def explain(exc: BaseException, prefix: str) -> str:
    """The message shown for a failed AI call: OFFLINE when unreachable, otherwise the prefix and error."""
    return OFFLINE if is_offline(exc) else f"{prefix}: {str(exc)[:300]}"


_lock = threading.Lock()
_cache: dict[str, tuple[float, bool]] = {}
CACHE_SECONDS = 15


def probe(ml_url: str, llm_url: str, timeout: float = 4.0) -> bool:
    """Asks the server for its /health (or the language model for its model list).

    Answers are cached for 15 s so the status dot in every open page costs at most one request.
    A tunnel address that no longer exists answers 404/530, which counts as offline. A server that
    accepts the connection but answers slowly (busy with a generation) counts as reachable, so a
    long job never makes other requests fail.
    """
    if ml_url:
        target = ml_url.rstrip("/") + "/health"
    elif llm_url:
        target = llm_url.rstrip("/") + "/models"
    else:
        return False
    now = time.monotonic()
    with _lock:
        hit = _cache.get(target)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    try:
        response = httpx.get(target, timeout=httpx.Timeout(timeout, connect=timeout))
        # 401/403: the server is up but wants the token; it is reachable.
        ok = response.status_code < 400 or response.status_code in (401, 403)
    except httpx.ReadTimeout:
        ok = True  # connected but slow to answer: the notebook is busy generating, not gone
    except httpx.HTTPError:
        ok = False
    with _lock:
        _cache[target] = (time.monotonic(), ok)
    return ok
