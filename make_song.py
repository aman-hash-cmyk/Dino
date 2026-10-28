#!/usr/bin/env python3
"""
make_song.py - makes a complete "10 Little Dinosaurs" counting-song episode:
music + sung chorus + sound effects, the animated video, the thumbnail and the YouTube text.

  python make_song.py           # real run (uses the free voice engine for the sung words)
  python make_song.py --mock    # offline test with a synthesised "la-la" choir
  python make_song.py --rounds 1
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

import song_audio
import song_video

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "output"
DATA_DIR = ROOT / "data"

TITLES = [
    "10 Little Dinosaurs | Counting Song for Kids",
    "Ten Little Dinosaurs - Count 1 to 10 with Baby Dinos",
    "Baby Dinosaurs Hatch! Counting 1 to 10 Song",
    "Count to 10 with Baby Dinosaurs | Nursery Rhyme for Toddlers",
]
NAMES = {"steg": "Green Stegosaurus", "tri": "Yellow Triceratops", "ptero": "Purple Pterodactyl",
         "bronto": "Teal Brontosaurus", "trex": "Orange T. rex"}


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--rounds", type=int)
    args = ap.parse_args()

    settings = load_json(DATA_DIR / "settings.json", {})
    rounds = args.rounds or int(os.environ.get("SONG_ROUNDS") or settings.get("song_rounds", 2))
    history = load_json(DATA_DIR / "history.json", [])
    ep_no = len(history) + 1
    ep_id = f"{datetime.date.today().isoformat()}_ep{ep_no:04d}"
    ep_dir = OUT_DIR / ep_id
    ep_dir.mkdir(parents=True, exist_ok=True)

    rot = (ep_no - 1) % 5                                     # a different dino starts each day, scenery changes too
    base = song_audio.SPECIES[rot:] + song_audio.SPECIES[:rot]
    order, bpms = [], []
    for r in range(rounds):                                   # round 2 plays the dinos backwards, a bit faster
        names = base if r % 2 == 0 else base[::-1]
        order += names
        bpms += [108 + 10 * r] * len(names)

    print(f"Making counting song #{ep_no}: {len(order)} verses")
    tl = song_audio.build(ep_dir, order, bpms, args.mock, bg_offset=rot)
    song_video.build(ep_dir)
    song_video.thumbnail(ep_dir, tl)

    title = TITLES[(ep_no - 1) % len(TITLES)]
    today = ", ".join(NAMES[s] for s in base)
    script = {
        "title": title,
        "description": ("Count from 1 to 10 with five kinds of baby dinosaurs hatching from their eggs! "
                        "A bouncy sing-along song for toddlers and preschoolers that practises counting, colours and dinosaur names.\n\n"
                        "Lyrics:\nOne little, two little, three little dinosaurs,\nFour little, five little, six little dinosaurs,\n"
                        "Seven little, eight little, nine little dinosaurs,\nTen little dinosaur babies!\n\n"
                        f"Meet the babies: {today}."),
        "tags": ["10 little dinosaurs", "counting song", "dinosaur song for kids", "nursery rhymes", "learn to count",
                 "counting 1 to 10", "baby dinosaurs", "toddler learning", "kids songs", "preschool"],
        "topic": "10 Little Dinosaurs counting song",
        "fact": "Counting from 1 to 10 with five kinds of baby dinosaurs.",
        "scenes": [],
    }
    (ep_dir / "script.json").write_text(json.dumps(script, indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.mock:
        history.append({"episode": ep_no, "id": ep_id, "date": datetime.date.today().isoformat(), "topic": script["topic"],
                        "title": title, "fact": script["fact"], "characters": sorted(set(order)), "format": "song"})
        DATA_DIR.mkdir(exist_ok=True)
        (DATA_DIR / "history.json").write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_DIR.joinpath("latest.txt").write_text(ep_id, encoding="utf-8")
    print("Done:", ep_dir)


if __name__ == "__main__":
    main()
