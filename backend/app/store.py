"""File-based storage: one JSON file per guide, images on disk.

Chosen so the small version runs with zero database setup. The class is the only
place that touches storage, so MongoDB can replace it later without other changes.
"""
from __future__ import annotations

import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from .schemas import Guide


class GuideStore:
    def __init__(self, data_dir: Path):
        self.guides_dir = data_dir / "guides"
        self.media_dir = data_dir / "media"
        self.guides_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, guide_id: str) -> Path:
        if not guide_id.isalnum():  # blocks path traversal through the id
            raise KeyError(guide_id)
        return self.guides_dir / f"{guide_id}.json"

    def save(self, guide: Guide) -> Guide:
        guide.updated_at = datetime.now(timezone.utc).isoformat()
        with self._lock:
            tmp = self._path(guide.id).with_suffix(".tmp")
            tmp.write_text(guide.model_dump_json(indent=2), encoding="utf-8")
            tmp.replace(self._path(guide.id))
        return guide

    def get(self, guide_id: str) -> Guide | None:
        try:
            path = self._path(guide_id)
        except KeyError:
            return None
        if not path.exists():
            return None
        with self._lock:
            return Guide.model_validate_json(path.read_text(encoding="utf-8"))

    def list(self) -> list[Guide]:
        guides = [g for p in self.guides_dir.glob("*.json") if (g := self.get(p.stem))]
        return sorted(guides, key=lambda g: g.created_at, reverse=True)

    def delete(self, guide_id: str) -> bool:
        guide = self.get(guide_id)
        if guide is None:
            return False
        with self._lock:
            self._path(guide_id).unlink(missing_ok=True)
            shutil.rmtree(self.media_dir / guide_id, ignore_errors=True)
        return True

    def save_image(self, guide_id: str, name: str, data: bytes) -> str:
        """Writes an image and returns the URL path it is served from."""
        folder = self.media_dir / guide_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
        return f"/media/{guide_id}/{name}"
