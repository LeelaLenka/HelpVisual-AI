"""Customer events from the guide player, and the figures computed from them.

Every figure comes from recorded events; nothing is estimated. Events from a guide's owner
previewing it are stored marked internal and left out of the figures, so authors do not inflate
their own numbers.
"""
from __future__ import annotations

import json
import threading
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal["view", "step", "complete", "question", "feedback"]
MAX_FILE_BYTES = 5 * 1024 * 1024  # per guide; stops one guide's log growing without bound


class EventIn(BaseModel):
    type: EventType
    session_id: str = Field(min_length=6, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    step_index: int | None = Field(default=None, ge=1, le=500)
    helpful: bool | None = None  # for feedback: did this step work?
    comment: str = Field(default="", max_length=500)


class Event(EventIn):
    at: str
    internal: bool = False


class EventStore:
    def __init__(self, data_dir: Path):
        self.folder = Path(data_dir) / "events"
        self.folder.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, guide_id: str) -> Path:
        if not guide_id.isalnum():
            raise ValueError("bad guide id")
        return self.folder / f"{guide_id}.jsonl"

    def add(self, guide_id: str, event: EventIn, internal: bool) -> bool:
        path = self._path(guide_id)
        with self._lock:
            if path.exists() and path.stat().st_size > MAX_FILE_BYTES:
                return False
            record = Event(**event.model_dump(), at=datetime.now(timezone.utc).isoformat(), internal=internal)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(record.model_dump_json() + "\n")
        return True

    def events(self, guide_id: str) -> list[Event]:
        path = self._path(guide_id)
        if not path.exists():
            return []
        with self._lock:
            lines = path.read_text(encoding="utf-8").splitlines()
        return [e for e in (Event.model_validate_json(line) for line in lines if line.strip()) if not e.internal]

    def delete(self, guide_id: str) -> None:
        with self._lock:
            self._path(guide_id).unlink(missing_ok=True)


def summarise(events: list[Event], step_count: int) -> dict:
    sessions = {e.session_id for e in events if e.type == "view"}
    completed = {e.session_id for e in events if e.type == "complete"} & sessions
    furthest: dict[str, int] = {}
    for e in events:
        if e.type == "step" and e.step_index:
            furthest[e.session_id] = max(furthest.get(e.session_id, 0), e.step_index)
    stopped = Counter(furthest[s] for s in sessions - completed if s in furthest)
    feedback: dict[int, dict] = {}
    for e in events:
        if e.type == "feedback" and e.step_index:
            row = feedback.setdefault(e.step_index, {"step": e.step_index, "helpful": 0, "not_helpful": 0, "comments": []})
            row["helpful" if e.helpful else "not_helpful"] += 1
            if e.comment.strip():
                row["comments"] = (row["comments"] + [e.comment.strip()])[-5:]
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    return {
        "views": len(sessions),
        "views_7d": len({e.session_id for e in events if e.type == "view" and e.at >= week_ago}),
        "completions": len(completed),
        "completion_rate": round(len(completed) / len(sessions), 3) if sessions else None,
        "drop_off_step": stopped.most_common(1)[0][0] if stopped else None,
        "drop_off_sessions": stopped.most_common(1)[0][1] if stopped else 0,
        "questions": sum(1 for e in events if e.type == "question"),
        "step_reach": [sum(1 for s in sessions if furthest.get(s, 0) >= i) for i in range(1, step_count + 1)],
        "feedback": sorted(feedback.values(), key=lambda r: r["step"]),
    }
