"""Chains language-model providers: when one is overloaded or out of quota, the next one answers."""
from __future__ import annotations

import logging

from .base import LLMProvider, T
from .retry import is_switchable

log = logging.getLogger("helpvisual.providers")


class FallbackLLM:
    def __init__(self, providers: list[LLMProvider]):
        self._providers = providers
        self.name = " -> ".join(p.name for p in providers)
        self.last_used = providers[0].name

    def _run(self, method: str, *args, **kwargs):
        for position, provider in enumerate(self._providers):
            try:
                result = getattr(provider, method)(*args, **kwargs)
                self.last_used = provider.name
                return result
            except Exception as exc:
                if not is_switchable(exc) or position == len(self._providers) - 1:
                    raise
                log.warning("%s failed (%s); switching to the next provider", provider.name, str(exc)[:200])
        raise RuntimeError("unreachable")

    def generate_json(self, prompt: str, schema: type[T], images: list[bytes] | None = None) -> T:
        return self._run("generate_json", prompt, schema, images)

    def generate_text(self, prompt: str, images: list[bytes] | None = None) -> str:
        return self._run("generate_text", prompt, images)
