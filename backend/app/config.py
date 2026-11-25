"""Application settings, read from environment variables or a local .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # The models run on the HelpVisual ML server (the Kaggle notebook); Gemini can optionally paint images.
    # The notebook prints these lines when it starts. Its language model speaks the OpenAI chat
    # format; the OPENAI_* names it prints and LLM_* names are both accepted.
    llm_base_url: str = Field("", validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"))
    llm_api_key: str = Field("", validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"))
    llm_model: str = Field("", validation_alias=AliasChoices("LLM_MODEL", "OPENAI_MODEL"))
    llm_min_interval: float = 0.0  # seconds between model calls (useful only for rate-limited servers)

    # ML server (the Kaggle notebook). Printed by the notebook when it starts.
    ml_endpoint_url: str = ""
    ml_endpoint_token: str = ""
    sdxl_steps: int = 30
    sdxl_candidates: int = 2  # images generated per attempt; CLIP keeps the best one

    # Optional second image generator: Gemini (free tier). The key stays in backend/.env and is never
    # sent to the browser. IMAGE_MODE: auto (Gemini first, Kaggle if Gemini is unavailable), gemini, kaggle.
    # Checks (CLIP, OCR), the language model and translation still run on the Kaggle notebook.
    gemini_api_key: str = ""
    gemini_image_model: str = "gemini-2.5-flash-image"
    gemini_min_interval: float = 6.0  # seconds between Gemini calls (free-tier requests per minute)
    image_mode: str = "auto"

    # "auto" uses CLIP + OCR checks and rule-based repair on the ML server.
    verifier: str = "auto"  # auto | llm | clip
    prompt_optimizer: str = "auto"  # auto | llm | rules
    # Provisional value for CLIP ViT-L/14, from the first real run; set properly from reviewer
    # labels by evaluation/calibrate.py.
    clip_min_similarity: float = 0.19
    # Phone-in-scene hand check. Off by default: on the first real run its margins for scenes with no
    # hand (+0.001 to +0.004) overlapped those for scenes with a hand (+0.003), so it passed everything.
    hand_check: bool = False
    redact_screenshots: bool = True  # blur emails, phone numbers and card-like numbers on screenshots
    control_scale: float = 1.0  # ControlNet strength; 1.0 keeps the drawn phone on the outline

    image_width: int = 1152  # a resolution SDXL was trained on
    image_height: int = 896
    max_repair_attempts: int = 2
    pass_score: int = 70

    data_dir: Path = Path("data")

    # Accounts. SECRET_KEY signs session cookies; when empty, a random key is created in data/.
    secret_key: str = ""
    cookie_secure: bool = False  # set true when the app is served over HTTPS
    app_url: str = "http://localhost:5173"  # used in password reset links
    dev_reset_links: bool = True  # write reset links to the server log (no email service yet)
    cors_origins: str = "http://localhost:5173"
    max_upload_mb: int = 10
    max_video_mb: int = 50
    max_article_chars: int = 20000


@lru_cache
def get_settings() -> Settings:
    return Settings()
