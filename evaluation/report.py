"""Builds the evaluation tables and charts from the runs and the stored guides.

From the backend folder, after run_eval.py (and after labelling the images in the editor):

    python ../evaluation/report.py

Writes evaluation/results/summary.md, summary.json and charts (PNG, if matplotlib is installed).
Every figure is computed from stored results; nothing is estimated or filled in.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

HERE = Path(__file__).parent
GUIDES = Path("data/guides")
OUT = HERE / "results"
MODES = ("basic", "context", "state", "integrated")
MODE_NAMES = {
    "basic": "Basic text-to-image",
    "context": "Context-aware",
    "state": "Action-state, screen beside",
    "integrated": "Action-state, screen in scene (ControlNet)",
}


def guide(guide_id: str) -> dict | None:
    path = GUIDES / f"{guide_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.0f}% ({part}/{whole})" if whole else "n/a"


def found(element: str, steps: list[dict]) -> bool:
    needle = element.lower()
    return any(needle in f"{s.get('ui_element', '')} {s.get('action', '')}".lower() for s in steps)


def extraction_section(data: dict, runs: dict, key: str = "extract") -> tuple[list[str], dict]:
    title = "## Step extraction (10 articles)" if key == "extract" else f"## Step extraction, run \"{key.split(':', 1)[1]}\" (10 articles)"
    lines, rows = [title, "",
                   "| Article | Steps found | Expected | Elements found | Suggested steps | Quotes verified | "
                   "Actions not covered | Model calls | Flags raised | Seconds |",
                   "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"], []
    for article in data["articles"]:
        run = runs.get(key, {}).get(article["id"])
        g = guide(run["guide_id"]) if run else None
        if not g:
            continue
        hits = sum(found(e, g["steps"]) for e in article["expected_elements"])
        issues = (g.get("graph") or {}).get("issues", [])
        flags = len(g.get("missing_steps", [])) + sum(1 for i in issues if i["kind"] == "gap")
        quoted = [s for s in g["steps"] if s.get("quote_verified") is not None]
        rows.append({"id": article["id"], "steps": len(g["steps"]), "expected": article["expected_steps"],
                     "elements": hits, "elements_total": len(article["expected_elements"]),
                     "suggested": sum(s.get("is_suggested", False) for s in g["steps"]), "flags": flags,
                     "quotes_ok": sum(1 for s in quoted if s["quote_verified"]), "quotes": len(quoted),
                     "uncovered": len(g["uncovered_instructions"]) if "uncovered_instructions" in g else None,
                     "calls": g.get("extraction_attempts"), "seconds": run["seconds"]})
        r = rows[-1]
        quotes = f"{r['quotes_ok']}/{r['quotes']}" if r["quotes"] else "not checked"
        lines.append(f"| {article['title']} | {r['steps']} | {r['expected']} | {r['elements']}/{r['elements_total']} | "
                     f"{r['suggested']} | {quotes} | {r['uncovered'] if r['uncovered'] is not None else 'not checked'} | "
                     f"{r['calls'] or 1} | {r['flags']} | {r['seconds']} |")
    if rows:
        total_hits = sum(r["elements"] for r in rows)
        total = sum(r["elements_total"] for r in rows)
        lines += ["", f"Interface elements recovered: {pct(total_hits, total)}. "
                      f"Mean extraction time: {mean(r['seconds'] for r in rows):.0f} s per article."]
    return lines, {"rows": rows}


def detection_section(data: dict, runs: dict, key: str = "extract") -> tuple[list[str], dict]:
    suffix = "" if key == "extract" else f", run \"{key.split(':', 1)[1]}\""
    lines = ["", f"## Missing-step detection (5 articles with one sentence removed{suffix})", "",
             "| Variant | Removed | Graph gap | Model flag | Model named it | Intact version flagged |",
             "| --- | --- | --- | --- | --- | --- |"]
    rows = []
    for variant in data["variants"]:
        run, base_run = runs.get(key, {}).get(variant["id"]), runs.get(key, {}).get(variant["base"])
        g = guide(run["guide_id"]) if run else None
        base = guide(base_run["guide_id"]) if base_run else None
        if not g:
            continue
        gaps = sum(1 for i in (g.get("graph") or {}).get("issues", []) if i["kind"] == "gap")
        flags = g.get("missing_steps", [])  # uncovered instructions measure extraction misses, not omissions
        named = any(variant["removed_element"].lower() in f.lower() for f in flags)
        base_flagged = None
        if base:
            base_gaps = sum(1 for i in (base.get("graph") or {}).get("issues", []) if i["kind"] == "gap")
            base_flagged = bool(base_gaps or base.get("missing_steps"))
        rows.append({"id": variant["id"], "graph_gap": gaps > 0, "model_flag": bool(flags), "named": named,
                     "base_flagged": base_flagged})
        yn = lambda b: "yes" if b else ("no" if b is not None else "n/a")
        lines.append(f"| {variant['title']} | {variant['removed_text'][:45]} | {yn(gaps > 0)} | {yn(bool(flags))} | "
                     f"{yn(named)} | {yn(base_flagged)} |")
    if rows:
        n = len(rows)
        either = sum(r["graph_gap"] or r["model_flag"] for r in rows)
        intact = [r["base_flagged"] for r in rows if r["base_flagged"] is not None]
        lines += ["", f"Detected by the graph: {pct(sum(r['graph_gap'] for r in rows), n)}. "
                      f"Flagged by the model: {pct(sum(r['model_flag'] for r in rows), n)}. "
                      f"Either: {pct(either, n)}. Model named the removed element: {pct(sum(r['named'] for r in rows), n)}.",
                  f"Intact versions that were also flagged (false alarms): {pct(sum(intact), len(intact))}."]
    return lines, {"rows": rows}


def image_section(runs: dict) -> tuple[list[str], dict]:
    per_mode: dict[str, list[dict]] = {m: [] for m in MODES}
    for key, run in runs["images"].items():
        _, mode = key.split(":")
        g = guide(run["guide_id"])
        if g and g["status"] == "ready":
            per_mode[mode] += g["steps"]
    lines = ["", "## Images by conditioning level", "",
             "| Level | Images | CLIP similarity (mean) | Passed first try | Passed after repair | Passed at end | "
             "Generated text | No hand (scene) | Confused with another step | Seconds per step | Judged right by reviewer |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    summary = {}
    for mode in MODES:
        steps = [s for s in per_mode[mode] if s.get("verification")]
        if not steps:
            continue
        n = len(steps)
        v = [s["verification"] for s in steps]
        first_ok = [bool(s["attempts"]) and s["attempts"][0]["score"] >= 70 and
                    not any("does not match" in i for i in s["attempts"][0]["issues"]) for s in steps]
        final_ok = [x["passed"] for x in v]
        repaired = sum(1 for f, e in zip(first_ok, final_ok) if not f and e)
        text = sum(any(i.startswith("Generated text") for i in x["issues"]) for x in v)
        confused = sum(any(i.startswith("Looks more like") for i in x["issues"]) for x in v)
        hand_checked = [x for x in v if x.get("hand_margin") is not None]
        no_hand = sum(1 for x in hand_checked if x["hand_margin"] <= 0)
        sims = [x["similarity"] for x in v if x.get("similarity") is not None]
        secs = [s["generation_seconds"] for s in steps if s.get("generation_seconds") is not None]
        labelled = [s["human_label"] for s in steps if s.get("human_label") is not None]
        summary[mode] = {"images": n, "similarity": round(mean(sims), 3) if sims else None,
                         "first_pass": sum(first_ok), "final_pass": sum(final_ok), "repaired": repaired,
                         "failed_first": n - sum(first_ok), "text": text, "confused": confused,
                         "no_hand": no_hand, "hand_checked": len(hand_checked),
                         "seconds": round(mean(secs), 1) if secs else None,
                         "judged_right": sum(labelled), "judged": len(labelled)}
        m = summary[mode]
        lines.append(
            f"| {MODE_NAMES[mode]} | {n} | {m['similarity']} | {pct(m['first_pass'], n)} | "
            f"{pct(repaired, m['failed_first'])} | {pct(m['final_pass'], n)} | {pct(text, n)} | "
            f"{pct(no_hand, len(hand_checked)) if hand_checked else 'not checked'} | {pct(confused, n)} | "
            f"{m['seconds']} | {pct(m['judged_right'], m['judged'])} |")
    if summary:
        lines += ["", "\"Passed after repair\" is the share of images that failed their first check and passed after the "
                      "automatic repair. Reviewer judgments count only labelled images. The hand check runs only at the "
                      "phone-in-scene level, which also shares one seed across a guide's steps."]
    return lines, summary


def charts(summary: dict) -> list[str]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ["", "(Charts skipped: install matplotlib with `pip install matplotlib` to draw them.)"]
    modes = [m for m in MODES if m in summary]
    labels = [MODE_NAMES[m].replace(", ", ",\n").replace(" (", "\n(") for m in modes]
    made = []
    series = [("Passed checker", [100 * summary[m]["final_pass"] / summary[m]["images"] for m in modes])]
    if all(summary[m]["judged"] for m in modes):
        series.append(("Judged right by reviewer", [100 * summary[m]["judged_right"] / summary[m]["judged"] for m in modes]))
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    width = 0.8 / len(series)
    for k, (name, values) in enumerate(series):
        positions = [i + (k - (len(series) - 1) / 2) * width for i in range(len(modes))]
        ax.bar(positions, values, width, label=name)
    ax.set_xticks(range(len(modes)), labels)
    ax.set_ylabel("% of images")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=len(series), frameon=False)
    ax.set_title("Image quality by conditioning level")
    fig.tight_layout()
    fig.savefig(OUT / "image_quality.png", dpi=150)
    made.append("image_quality.png")
    plt.close(fig)
    return ["", "Charts: " + ", ".join(made)]


def main() -> None:
    data = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))
    runs_path = OUT / "runs.json"
    if not runs_path.exists():
        print("No runs yet. Run run_eval.py first.")
        return
    runs = json.loads(runs_path.read_text())
    lines = ["# HelpVisual AI evaluation results", "",
             "All figures are computed from stored runs by evaluation/report.py. Small samples: treat as preliminary.", ""]
    ext_data, det_data = {}, {}
    for key in [k for k in runs if k == "extract" or k.startswith("extract:")]:
        extraction, ext_data[key] = extraction_section(data, runs, key)
        detection, det_data[key] = detection_section(data, runs, key)
        lines += extraction + detection + [""]
    images, img_data = image_section(runs)
    lines += images
    if img_data:
        lines += charts(img_data)
    OUT.mkdir(exist_ok=True)
    (OUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "summary.json").write_text(json.dumps({"extraction": ext_data, "detection": det_data, "images": img_data}, indent=2))
    print("\n".join(lines))
    print(f"\nSaved to {OUT.resolve()}")


if __name__ == "__main__":
    main()
