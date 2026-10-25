#!/usr/bin/env python3
"""download_voice.py - fetches the free Piper voice model into voices/ (skips if present)."""
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "en_US-libritts_r-medium"
BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/libritts_r/medium/"
dest = ROOT / "voices"
dest.mkdir(exist_ok=True)
for ext in (".onnx", ".onnx.json"):
    f = dest / (NAME + ext)
    if f.exists():
        print("have", f.name)
        continue
    print("downloading", f.name, "...")
    urllib.request.urlretrieve(BASE + NAME + ext + "?download=true", f)
print("voice ready")
