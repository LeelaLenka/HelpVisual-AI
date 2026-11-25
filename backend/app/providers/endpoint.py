"""Client for the HelpVisual ML server (the Kaggle notebook): SDXL generation and CLIP + OCR checks."""
from __future__ import annotations

import base64

import httpx

from .status import OFFLINE

# The tunnel address changes every time the notebook restarts, so an old ML_ENDPOINT_URL is the usual cause.
UNREACHABLE = OFFLINE


class MLEndpoint:
    def __init__(
        self,
        url: str,
        token: str,
        steps: int = 30,
        candidates: int = 2,
        transport: httpx.BaseTransport | None = None,
    ):
        self.name = "endpoint:sdxl+clip"
        self._steps = steps
        self._candidates = candidates
        self.last_generation: dict = {}  # candidate scores and timing of the latest image
        self._control_checked = False
        self._features: dict | None = None
        self._client = httpx.Client(
            base_url=url.rstrip("/"),
            headers={"X-Token": token},
            # The server sends a space every 5 s while it works, so this only trips if it goes silent.
            timeout=httpx.Timeout(120, connect=20),
            transport=transport,
        )

    def _post(self, path: str, payload: dict) -> httpx.Response:
        try:
            response = self._client.post(path, json=payload)
        except httpx.TransportError as exc:
            raise RuntimeError(UNREACHABLE) from exc
        if response.status_code == 401:
            raise RuntimeError("The ML server rejected the token. Update ML_ENDPOINT_TOKEN in .env.")
        if response.status_code in (502, 503, 530) or response.status_code == 404:
            raise RuntimeError(UNREACHABLE)
        if response.status_code >= 400:
            raise RuntimeError(f"ML server error {response.status_code}: {response.text[:200]}")
        return response

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        data = response.json()  # leading keep-alive spaces are valid JSON whitespace
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"ML server error: {data['error'].get('message', data['error'])}")
        return data

    def features(self) -> dict:
        """The server's /health answer, fetched once: which optional models it has loaded."""
        if self._features is None:
            try:
                self._features = self._client.get("/health").json()
            except (httpx.TransportError, ValueError):
                self._features = {}
        return self._features

    def can_read_layout(self) -> bool:
        return bool(self.features().get("ocr_layout"))

    def ocr(self, image: bytes) -> dict:
        """Text on an image with positions: {"width", "height", "words": [{"text", "confidence", "box"}]}."""
        return self._json(self._post("/ocr", {"image_b64": base64.b64encode(image).decode()}))

    def can_translate(self) -> bool:
        return "translator" in self.features()

    def translate(self, texts: list[str], source: str, target: str) -> list[str]:
        """Translates a batch of texts with the server's translation model (NLLB-200)."""
        data = self._json(self._post("/translate", {"texts": texts, "source": source, "target": target}))
        return data["translations"]

    def _require_control(self) -> None:
        if self._control_checked:
            return
        try:
            health = self._client.get("/health").json()
        except (httpx.TransportError, ValueError) as exc:
            raise RuntimeError(UNREACHABLE) from exc
        if "controlnet" not in health:
            raise RuntimeError(
                "This mode needs ControlNet, which the running Kaggle notebook does not have. "
                "Run helpvisual_ml_server_v3.ipynb and paste its new lines into .env."
            )
        self._control_checked = True

    def generate(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: int,
        select_text: str = "",
        control_image: bytes | None = None,
        control_scale: float = 0.85,
    ) -> bytes:
        """Generates several candidates on the server; CLIP keeps the one closest to select_text.

        With a control image (an edge map), SDXL follows its outline through the ControlNet.
        """
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": self._steps,
            "candidates": self._candidates,
            "select_text": select_text,
        }
        if control_image is not None:
            self._require_control()
            payload["control_image_b64"] = base64.b64encode(control_image).decode()
            payload["control_scale"] = control_scale
        data = self._json(self._post("/generate", payload))
        self.last_generation = {k: data.get(k) for k in ("scores", "chosen", "seconds")}
        return base64.b64decode(data["image_b64"])

    def clip_check(self, image: bytes, texts: list[str], target_index: int) -> dict:
        """Returns {"similarities": [...], "ocr_text": [...]} for the image against every text."""
        response = self._post(
            "/verify",
            {"image_b64": base64.b64encode(image).decode(), "texts": texts, "target_index": target_index},
        )
        return self._json(response)
