"""Calibrates the CLIP threshold from reviewer labels and reports how well the checker agrees.

Run from the backend folder after labelling images in the editor:

    python ../evaluation/calibrate.py

It reads every guide in backend/data/guides, uses each labelled image's CLIP similarity, and
treats "the image is wrong" as the case the checker should catch. Nothing is invented: with
few labels, the figures are reported with their counts so their weakness is visible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/guides")


def load_labelled() -> list[dict]:
    rows = []
    for path in sorted(DATA.glob("*.json")):
        guide = json.loads(path.read_text(encoding="utf-8"))
        for step in guide.get("steps", []):
            v = step.get("verification") or {}
            if step.get("human_label") is None or v.get("similarity") is None:
                continue
            rows.append(
                {
                    "guide": guide.get("title", path.stem),
                    "step": step["index"],
                    "similarity": v["similarity"],
                    "checker_passed": v.get("passed"),
                    "wrong": step["human_label"] is False,
                }
            )
    return rows


def confusion(rows: list[dict], predicted_wrong) -> dict:
    tp = sum(1 for r in rows if r["wrong"] and predicted_wrong(r))
    fp = sum(1 for r in rows if not r["wrong"] and predicted_wrong(r))
    fn = sum(1 for r in rows if r["wrong"] and not predicted_wrong(r))
    tn = len(rows) - tp - fp - fn
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision, "recall": recall, "f1": f1,
            "accuracy": (tp + tn) / len(rows)}


def main() -> None:
    rows = load_labelled()
    if not rows:
        print(f"No labelled images found in {DATA.resolve()}. Label images in the editor first.")
        return
    wrong = sum(r["wrong"] for r in rows)
    print(f"Labelled images: {len(rows)} ({wrong} judged wrong, {len(rows) - wrong} judged right)")
    if len(rows) < 30 or min(wrong, len(rows) - wrong) < 5:
        print("Warning: too few labels, or too few of one kind, for a reliable threshold. Report these as preliminary.\n")

    current = confusion(rows, lambda r: r["checker_passed"] is False)
    print("Current checker (all rules) vs reviewer:")
    print(f"  catches {current['tp']} of {wrong} wrong images (recall {current['recall']:.2f}), "
          f"precision {current['precision']:.2f}, accuracy {current['accuracy']:.2f}, "
          f"false alarms {current['fp']}\n")

    thresholds = sorted({round(r["similarity"] + 0.0005, 4) for r in rows} | {0.0})
    results = [(t, confusion(rows, lambda r, t=t: r["similarity"] < t)) for t in thresholds]
    print(f"{'threshold':>9} {'caught':>7} {'false':>6} {'precision':>9} {'recall':>7} {'F1':>5}")
    for t, m in results:
        print(f"{t:>9.4f} {m['tp']:>7} {m['fp']:>6} {m['precision']:>9.2f} {m['recall']:>7.2f} {m['f1']:>5.2f}")
    best_t, best = max(results, key=lambda tm: (tm[1]["f1"], -tm[0]))
    print(f"\nBest threshold by F1: {best_t:.4f} (F1 {best['f1']:.2f}, precision {best['precision']:.2f}, "
          f"recall {best['recall']:.2f}). Set CLIP_MIN_SIMILARITY={best_t:.2f} in backend/.env to use it.")


if __name__ == "__main__":
    main()
