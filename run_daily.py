#!/usr/bin/env python3
"""
run_daily.py - one command that makes and uploads today's episode.

  python run_daily.py          # real run (needs GEMINI_API_KEY + YT_* secrets + Piper voice)
  python run_daily.py --mock   # offline test: fake script, silent audio, no upload
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "output"
HISTORY = ROOT / "data" / "history.json"


def run(*args):
    print("\n>>", " ".join(args))
    subprocess.run([sys.executable, *args], check=True, cwd=ROOT)


def main():
    mock = "--mock" in sys.argv
    settings = json.loads((ROOT / "data" / "settings.json").read_text()) if (ROOT / "data" / "settings.json").exists() else {}
    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    fmt = os.environ.get("EPISODE_FORMAT") or settings.get("format", "song")
    if fmt == "alternate":
        fmt = "song" if len(history) % 2 == 0 else "story"
    print("Episode format:", fmt)
    if fmt == "song":
        run("make_song.py", *(["--mock"] if mock else []))
        ep = (OUT_DIR / "latest.txt").read_text().strip()
    else:
        run("make_episode.py", *(["--mock"] if mock else []))
        ep = (OUT_DIR / "latest.txt").read_text().strip()
        run("assemble_video.py", ep)
        run("make_thumbnail.py", ep)

    seg_file = OUT_DIR / ep / "segments.json"
    if HISTORY.exists() and seg_file.exists():
        history = json.loads(HISTORY.read_text(encoding="utf-8"))
        segs = json.loads(seg_file.read_text())["segments"]
        for h in history:
            if h.get("id") == ep:
                h["segments"] = segs
        HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")

    run("upload_youtube.py", ep, *(["--dry-run"] if mock else []))
    print("\nAll done:", ep)


if __name__ == "__main__":
    main()
