"""Tuning the checker from reviewer labels.

The CLIP threshold decides when a picture "does not match its step". Its starting value was a
guess. Once a reviewer has judged enough pictures, the threshold that best separates their "right"
and "wrong" judgments (highest F1 for catching wrong pictures) is computed and kept in
data/tuning.json, so it survives restarts. Too few labels: nothing changes, and the reason is given.
"""
from __future__ import annotations

import json
from pathlib import Path

MIN_LABELS, MIN_EACH = 12, 3


def best_threshold(rows: list[tuple[float, bool]]) -> dict:
    """rows: (similarity, judged_wrong). Wrong pictures should fall below the threshold."""
    candidates = sorted({round(s + 0.0005, 4) for s, _ in rows})
    best = None
    for t in candidates:
        tp = sum(1 for s, wrong in rows if wrong and s < t)
        fp = sum(1 for s, wrong in rows if not wrong and s < t)
        fn = sum(1 for s, wrong in rows if wrong and s >= t)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        if best is None or f1 > best["f1"]:
            best = {"threshold": t, "f1": round(f1, 3), "precision": round(precision, 3), "recall": round(recall, 3),
                    "caught": tp, "false_alarms": fp}
    return best or {}


def tune(rows: list[tuple[float, bool]], data_dir: Path) -> dict:
    wrong = sum(1 for _, w in rows if w)
    if len(rows) < MIN_LABELS or min(wrong, len(rows) - wrong) < MIN_EACH:
        return {"changed": False, "labels": len(rows), "wrong": wrong,
                "reason": f"Needs at least {MIN_LABELS} judged pictures, with at least {MIN_EACH} judged right and "
                          f"{MIN_EACH} judged wrong. So far: {len(rows)} judged, {wrong} wrong."}
    result = best_threshold(rows)
    (Path(data_dir) / "tuning.json").write_text(json.dumps({"clip_min_similarity": result["threshold"]}))
    return {"changed": True, "labels": len(rows), "wrong": wrong, **result}


def load(data_dir: Path) -> dict:
    path = Path(data_dir) / "tuning.json"
    return json.loads(path.read_text()) if path.exists() else {}
