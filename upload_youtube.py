#!/usr/bin/env python3
"""
upload_youtube.py - uploads output/<episode>/video.mp4 (+ thumbnail) to YouTube.

  * marked "Made for Kids" (selfDeclaredMadeForKids)
  * privacy comes from env UPLOAD_PRIVACY (private | unlisted | public), default private
  * writes video_id / url back into data/history.json

Usage:  python upload_youtube.py [episode_id] [--dry-run]
"""
import datetime
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "output"
HISTORY = ROOT / "data" / "history.json"
BIBLE = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))

FOOTER = (
    "\n\nDino Pals: a new dinosaur adventure every day for kids aged 3-7.\n"
    "Meet Rexy, Trixie, Stego Sam, Pip and Dr. Dina!\n"
    "This video was made with the help of AI (script and voices) and checked for kid-friendly content."
)
DEFAULT_TAGS = ["dinosaurs for kids", "Dino Pals", "kids learning", "dinosaur cartoon", "preschool"]


def build_body(script, privacy):
    tags, total = [], 0
    for t in script.get("tags", []) + DEFAULT_TAGS:
        t = str(t).strip()
        if t and t.lower() not in [x.lower() for x in tags] and total + len(t) + 1 < 450:
            tags.append(t)
            total += len(t) + 1
    return {
        "snippet": {
            "title": script["title"][:100],
            "description": (script["description"] + FOOTER)[:4900],
            "tags": tags,
            "categoryId": "27",          # Education
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": True,
            "embeddable": True,
        },
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    ep_id = args[0] if args else (OUT_DIR / "latest.txt").read_text().strip()
    ep_dir = OUT_DIR / ep_id
    script = json.loads((ep_dir / "script.json").read_text(encoding="utf-8"))
    privacy = os.environ.get("UPLOAD_PRIVACY", "private").strip().lower() or "private"
    if privacy not in ("private", "unlisted", "public"):
        sys.exit("UPLOAD_PRIVACY must be private, unlisted or public")
    body = build_body(script, privacy)

    if dry:
        print("[dry run] would upload", ep_dir / "video.mp4")
        print(json.dumps(body, indent=2)[:1200])
        return

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    from yt_auth import get_credentials

    yt = build("youtube", "v3", credentials=get_credentials(), cache_discovery=False)
    req = yt.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(ep_dir / "video.mp4"), chunksize=8 * 1024 * 1024,
                                   resumable=True, mimetype="video/mp4"))
    resp, retries = None, 0
    while resp is None:
        try:
            status, resp = req.next_chunk()
            if status:
                print(f"  uploaded {int(status.progress() * 100)}%")
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1
                time.sleep(2 ** retries)
                continue
            raise
    vid = resp["id"]
    url = f"https://youtu.be/{vid}"
    print("Uploaded:", url, f"({privacy})")

    thumb = ep_dir / "thumbnail.jpg"
    if thumb.exists():
        try:
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumb), mimetype="image/jpeg")).execute()
            print("Thumbnail set.")
        except HttpError as e:
            print("WARNING: could not set thumbnail (channel may need phone verification):", e)

    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    for h in history:
        if h.get("id") == ep_id:
            h.update({"video_id": vid, "url": url, "privacy": privacy,
                      "uploaded_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"})
    HISTORY.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
