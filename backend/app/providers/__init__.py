"""Provider factories. All AI runs on the self-hosted HelpVisual ML server (the Kaggle notebook).

The rest of the app depends only on the two interfaces in base.py, so another self-hosted server
(for example Ollama on a machine with a GPU) can be used by pointing LLM_BASE_URL at it.
"""
from urllib.parse import urlparse

from ..config import Settings
from .base import ImageProvider, LLMProvider, ProviderNotConfigured

from .status import OFFLINE as NOT_CONNECTED  # one message everywhere


def build_llm(settings: Settings) -> LLMProvider:
    if not settings.llm_base_url or not settings.llm_model:
        raise ProviderNotConfigured(NOT_CONNECTED)
    from .openai_compat import OpenAICompatLLM

    host = urlparse(settings.llm_base_url).hostname or "server"
    label = "kaggle" if host.endswith("trycloudflare.com") else host.split(".")[0]
    return OpenAICompatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model, settings.llm_min_interval, label)


def build_image_provider(settings: Settings) -> ImageProvider:
    if not settings.ml_endpoint_url or not settings.ml_endpoint_token:
        raise ProviderNotConfigured(NOT_CONNECTED)
    from .endpoint import MLEndpoint

    return MLEndpoint(settings.ml_endpoint_url, settings.ml_endpoint_token, settings.sdxl_steps, settings.sdxl_candidates)


__all__ = ["LLMProvider", "ImageProvider", "ProviderNotConfigured", "build_llm", "build_image_provider"]
