"""Retry, pacing and provider-switching rules shared by every language-model provider."""
from __future__ import annotations

import re
import threading
import time
from typing import Callable, TypeVar

R = TypeVar("R")
BUSY_MARKERS = ("503", "UNAVAILABLE", "overloaded", "high demand")
QUOTA_MARKERS = ("429", "RESOURCE_EXHAUSTED", "rate limit", "rate_limit")
DAILY_MARKERS = ("PerDay", "per day", "RPD", "TPD")
RETRY_HINT = re.compile(
    r"(?:retry(?:Delay)?['\"]?\s*(?:in|:)|try again in)\s*['\"]?([\d.]+)\s*s", re.IGNORECASE
)

_pace_lock = threading.Lock()
_last_call = 0.0


def pace(min_interval: float) -> None:
    """Spaces out model calls so a free-tier requests-per-minute limit is not hit."""
    global _last_call
    with _pace_lock:
        wait = _last_call + min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()


class DailyQuotaExceeded(RuntimeError):
    pass


def _is_quota(exc: Exception) -> bool:
    return getattr(exc, "code", None) == 429 or any(m.lower() in str(exc).lower() for m in QUOTA_MARKERS)


def _is_busy(exc: Exception) -> bool:
    return getattr(exc, "code", None) in (500, 502, 503, 504) or any(m in str(exc) for m in BUSY_MARKERS)


def is_switchable(exc: Exception) -> bool:
    """True when another model might succeed: overload or quota, not a problem with the request."""
    return isinstance(exc, DailyQuotaExceeded) or _is_quota(exc) or _is_busy(exc)


def with_retry(call: Callable[[], R], attempts: int = 4, label: str = "the model") -> R:
    """Retries busy errors quickly and rate-limit errors slowly. A daily quota is not retried."""
    busy_delay = 2.0
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:
            message = str(exc)
            quota, busy = _is_quota(exc), _is_busy(exc)
            if quota and any(m in message for m in DAILY_MARKERS):
                raise DailyQuotaExceeded(
                    f"The free daily quota for {label} is used up. It resets once a day; until then, "
                    "use another model or provider (see LLM_FALLBACK_PROVIDER in .env)."
                ) from exc
            if not (quota or busy) or attempt == attempts:
                raise
            if quota:
                hint = RETRY_HINT.search(message)
                delay = min(float(hint.group(1)) + 1, 90) if hint else 20.0 * attempt
            else:
                delay, busy_delay = busy_delay, busy_delay * 2
            time.sleep(delay)
    raise RuntimeError("unreachable")
