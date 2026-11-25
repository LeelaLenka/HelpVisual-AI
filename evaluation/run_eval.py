"""Runs the evaluation through the running HelpVisual backend.

Start the backend (and the Kaggle notebook) first, then from the backend folder:

    python ../evaluation/run_eval.py extract
        Creates a guide for every article and every variant (one language-model call each).

    python ../evaluation/run_eval.py extract grounded
        The same, kept separately: run it after an extraction change to compare the two.

    python ../evaluation/run_eval.py images a01 a02 a06 a09
        For each named article: copies its guide at the basic, context, state and integrated levels
        (same steps, same seeds) and generates and verifies images for each. Levels already done are
        skipped, so after adding a level only that one runs. Allow about a minute per image.

    python ../evaluation/run_eval.py status
        Shows what has been run so far.

It asks for your HelpVisual account email and password (or reads HV_EMAIL and HV_PASSWORD).
Guides made before accounts existed have no owner, so they stay visible to any account.

Progress is saved in evaluation/results/runs.json after every guide, so an interrupted run can be
started again and continues where it stopped.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).parent
API = "http://localhost:8000/api"
RUNS = HERE / "results" / "runs.json"
MODES = ("basic", "context", "state", "integrated")


def load_runs() -> dict:
    return json.loads(RUNS.read_text()) if RUNS.exists() else {"extract": {}, "images": {}}


def save_runs(runs: dict) -> None:
    RUNS.parent.mkdir(exist_ok=True)
    RUNS.write_text(json.dumps(runs, indent=2))


def client() -> httpx.Client:
    """Signs in with HV_EMAIL and HV_PASSWORD from the environment, or asks for them."""
    c = httpx.Client(base_url=API, timeout=httpx.Timeout(900, connect=10))
    try:
        health = c.get("/health").json()
    except httpx.TransportError:
        sys.exit("The backend is not running. Start it with: uvicorn app.main:app --port 8000")
    email = os.environ.get("HV_EMAIL") or input("HelpVisual account email: ").strip()
    password = os.environ.get("HV_PASSWORD") or getpass.getpass("Password: ")
    response = c.post("/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        sys.exit(f"Sign-in failed: {response.json().get('detail', response.status_code)}")
    print(f"Signed in as {email}. Backend: language model {health['llm']}, images {health['image']}")
    return c


def extract(label: str = "extract") -> None:
    """Creates a guide per article. A label keeps a second run separate, e.g. "grounded" to measure
    extraction after the grounding checks were added, beside the first run."""
    key = "extract" if label == "extract" else f"extract:{label}"
    data = json.loads((HERE / "articles.json").read_text(encoding="utf-8"))
    items = [(a["id"], a["text"]) for a in data["articles"]] + [(v["id"], v["text"]) for v in data["variants"]]
    runs, c = load_runs(), client()
    runs.setdefault(key, {})
    for item_id, text in items:
        if item_id in runs[key]:
            print(f"{item_id}: done already")
            continue
        started = time.monotonic()
        response = c.post("/guides", data={"text": text, "style": "flat", "prompt_mode": "state"})
        if response.status_code != 201:
            print(f"{item_id}: FAILED {response.status_code} {response.text[:200]}")
            continue
        guide = response.json()
        runs[key][item_id] = {"guide_id": guide["id"], "seconds": round(time.monotonic() - started, 1)}
        save_runs(runs)
        print(f"{item_id}: {len(guide['steps'])} steps in {runs[key][item_id]['seconds']} s")


def wait(c: httpx.Client, guide_id: str) -> dict:
    while True:
        guide = c.get(f"/guides/{guide_id}").json()
        if guide["status"] != "generating":
            return guide
        print(f"    {guide['job']['done']}/{guide['job']['total']} images", end="\r")
        time.sleep(10)


def images(article_ids: list[str]) -> None:
    runs, c = load_runs(), client()
    for article_id in article_ids:
        source = runs["extract"].get(article_id)
        if not source:
            print(f"{article_id}: run 'extract' first")
            continue
        for mode in MODES:
            key = f"{article_id}:{mode}"
            if runs["images"].get(key, {}).get("status") == "ready":
                print(f"{key}: done already")
                continue
            existing = runs["images"].get(key, {}).get("guide_id")
            guide_id = existing or c.post(f"/guides/{source['guide_id']}/copy", json={"prompt_mode": mode}).json()["id"]
            started = time.monotonic()
            response = c.post(f"/guides/{guide_id}/generate")
            if response.status_code not in (202, 409):
                print(f"{key}: FAILED {response.status_code} {response.text[:200]}")
                continue
            print(f"{key}: generating")
            guide = wait(c, guide_id)
            runs["images"][key] = {
                "guide_id": guide_id,
                "status": guide["status"],
                "seconds": round(time.monotonic() - started, 1),
                "error": guide["job"].get("error"),
            }
            save_runs(runs)
            print(f"{key}: {guide['status']} in {runs['images'][key]['seconds']} s")


def status() -> None:
    runs = load_runs()
    print(f"Extracted: {len(runs['extract'])} of 15 -> {', '.join(sorted(runs['extract'])) or 'none'}")
    for key, run in sorted(runs["images"].items()):
        print(f"  {key}: {run['status']} ({run['seconds']} s){'  ' + run['error'] if run.get('error') else ''}")


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "extract":
        extract(sys.argv[2] if len(sys.argv) > 2 else "extract")
    elif command == "images":
        images(sys.argv[2:] or ["a01", "a02", "a06", "a09"])
    else:
        status()
