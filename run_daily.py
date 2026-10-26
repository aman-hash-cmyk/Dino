
#!/usr/bin/env python3
"""
run_daily.py - one command that makes and uploads today's episode.

  python run_daily.py          # real run (needs GEMINI_API_KEY + YT_* secrets + Piper voice)
  python run_daily.py --mock   # offline test: fake script, silent audio, no upload
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "output"
HISTORY = ROOT / "data" / "history.json"


def run(*args):
    command = [sys.executable, *args]
    print("\n>>", " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=ROOT)


def main():
    mock = "--mock" in sys.argv

    # Generate the episode. If Gemini fails, try the built-in lyric template.
    try:
        if mock:
            run("make_episode.py", "--mock")
        else:
            run("make_episode.py")
    except subprocess.CalledProcessError:
        if mock:
            raise

        print(
            "\nGemini generation failed. "
            "Falling back to built-in lyrics...",
            flush=True,
        )
        run("make_episode.py", "--skip-gemini")

    latest_file = OUT_DIR / "latest.txt"
    if not latest_file.exists():
        raise FileNotFoundError(
            f"Episode pointer not found: {latest_file}"
        )

    ep = latest_file.read_text(encoding="utf-8").strip()
    if not ep:
        raise RuntimeError("output/latest.txt is empty.")

    # Assemble the video and create its thumbnail.
    run("assemble_video.py", ep)
    run("make_thumbnail.py", ep)

    # Update the episode's segments in history when available.
    seg_file = OUT_DIR / ep / "segments.json"
    if HISTORY.exists() and seg_file.exists():
        history = json.loads(HISTORY.read_text(encoding="utf-8"))
        segs = json.loads(
            seg_file.read_text(encoding="utf-8")
        )["segments"]

        for item in history:
            if item.get("id") == ep:
                item["segments"] = segs

        HISTORY.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # Stop the pipeline if the generated episode fails validation.
    run("validate_episode.py", ep)

    # Upload normally, or use dry-run mode for a mock run.
    if mock:
        run("upload_youtube.py", ep, "--dry-run")
    else:
        run("upload_youtube.py", ep)

    print("\nAll done:", ep, flush=True)


if __name__ == "__main__":
    main()
