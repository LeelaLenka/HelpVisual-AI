from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ProviderNotConfigured(RuntimeError):
    """Raised when a provider's credentials are missing."""


class LLMProvider(Protocol):
    name: str

    def generate_json(self, prompt: str, schema: type[T], images: list[bytes] | None = None) -> T: ...

    def generate_text(self, prompt: str, images: list[bytes] | None = None) -> str: ...


class ImageProvider(Protocol):
    name: str

    def generate(self, prompt: str, negative_prompt: str, width: int, height: int, seed: int) -> bytes:
        """Returns PNG bytes."""
        ...
