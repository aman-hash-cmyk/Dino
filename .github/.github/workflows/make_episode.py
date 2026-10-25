#!/usr/bin/env python3
"""
make_episode.py  -  Stage 1 of the Dino Pals pipeline.

What it does:
  1. Picks a topic (avoids recent ones, respects data/insights.json hints).
  2. Asks Gemini for a structured, kid-safe episode script (JSON).
  3. Validates the script against the rules in characters.json (retries if invalid).
  4. Voices every line with Piper TTS, one voice per character.
  5. Joins the audio and writes a timeline (start/end of every line) that the
     video-assembly stage will use to show the right character at the right time.

Outputs go to  output/<episode_id>/ :
  script.json, timeline.json, episode_audio.wav, audio/line_001.wav ...

Usage:
  export GEMINI_API_KEY=...            # free key from Google AI Studio
  python make_episode.py               # real run
  python make_episode.py --mock        # no network / no Piper; tests the plumbing
  python make_episode.py --topic "Why did Triceratops have three horns?"
"""
import argparse
import datetime
import json
import os
import random
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BIBLE = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "output"
VOICE_DIR = Path(os.environ.get("PIPER_VOICE_DIR", ROOT / "voices"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")  # check AI Studio for current free models
GAP_SECONDS = 0.30          # pause between lines
MAX_GENERATION_TRIES = 3


# ----------------------------------------------------------------- small helpers
def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_for_tts(text):
    """Remove emoji / markdown so the voice doesn't read symbols aloud."""
    text = re.sub(r"[*_#`~]", "", text)
    text = re.sub(r"[^\w\s.,!?'’\-:;]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


# ----------------------------------------------------------------- topic + prompt
def pick_topic(history, forced=None):
    if forced:
        return forced
    recent = {h.get("topic") for h in history[-30:]}
    pool = [t for t in BIBLE["topic_pool"] if t not in recent] or BIBLE["topic_pool"]
    return random.choice(pool)


def build_prompt(topic, history, insights, problems=None):
    series = BIBLE["series"]
    rules = BIBLE["rules"]
    chars = "\n".join(
        f'- id "{cid}": {c["name"]} ({c["species"]}). {c["personality"]} Catchphrase: "{c["catchphrase"]}"'
        for cid, c in BIBLE["characters"].items()
    )
    recent_titles = [h.get("title", "") for h in history[-10:]]
    style = "\n".join(f"- {s}" for s in rules["style"])

    hints = ""
    if insights:
        hints = (
            "\nWhat has worked well with viewers recently (use as gentle guidance, "
            "do not copy old episodes):\n"
            f"{json.dumps(insights, ensure_ascii=False)}\n"
        )

    fix = ""
    if problems:
        fix = "\nYour previous attempt had these problems. Fix them:\n" + "\n".join(f"- {p}" for p in problems) + "\n"

    return f"""You write scripts for "{series['title']}", a YouTube series for children aged 3 to 7.
Tagline: {series['tagline']}

TOPIC OF TODAY'S EPISODE: {topic}

CHARACTERS (use only these ids as speakers):
{chars}

EPISODE STRUCTURE: segments in this order: {", ".join(series['segments_in_order'])}.
Length: {rules['min_words']} to {rules['max_words']} words of dialogue in total, {rules['min_lines']} to {rules['max_lines']} lines.
Final line of the outro must contain this sign-off: "{series['daily_signoff']}"

STYLE RULES:
{style}

Recent episode titles (do not repeat): {recent_titles}
{hints}{fix}
Backgrounds available (choose one per scene): {", ".join(BIBLE['backgrounds'])}

Return ONLY valid JSON in exactly this shape:
{{
  "title": "catchy YouTube title under 70 characters, kid-friendly",
  "description": "2-3 sentence YouTube description for parents, mentioning the fact taught",
  "tags": ["8 to 12 short tags"],
  "topic": "{topic}",
  "fact": "the one dinosaur fact taught, in one simple sentence",
  "scenes": [
    {{
      "segment": "intro | adventure | fact | song | outro",
      "background": "one of the available backgrounds",
      "lines": [ {{ "speaker": "character id", "text": "what they say" }} ]
    }}
  ]
}}"""


# ----------------------------------------------------------------- Gemini
def call_gemini(prompt):
    import requests  # imported here so --mock works without it

    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY is not set.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    for attempt in range(4):
        r = requests.post(url, headers=headers, json=body, timeout=120)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
            return json.loads(text)
        if r.status_code in (429, 500, 503):      # rate limit / temporary error
            time.sleep(5 * 2 ** attempt)
            continue
        r.raise_for_status()
    raise RuntimeError("Gemini kept failing; try again later.")


# ----------------------------------------------------------------- validation
def validate(script):
    rules = BIBLE["rules"]
    problems = []
    for key in ("title", "description", "tags", "topic", "fact", "scenes"):
        if not script.get(key):
            problems.append(f"missing field: {key}")
    if problems:
        return problems

    banned = re.compile(r"\b(" + "|".join(re.escape(w) for w in rules["banned_words"]) + r")\b", re.I)
    speakers = set(BIBLE["characters"])
    segments_needed = BIBLE["series"]["segments_in_order"]
    segments_seen = []
    n_lines = n_words = 0

    if len(script["title"]) > 70:
        problems.append("title is longer than 70 characters")

    for i, scene in enumerate(script["scenes"], 1):
        seg = scene.get("segment")
        segments_seen.append(seg)
        if seg not in segments_needed:
            problems.append(f"scene {i}: unknown segment '{seg}'")
        if scene.get("background") not in BIBLE["backgrounds"]:
            problems.append(f"scene {i}: unknown background '{scene.get('background')}'")
        for j, line in enumerate(scene.get("lines", []), 1):
            text = (line.get("text") or "").strip()
            if line.get("speaker") not in speakers:
                problems.append(f"scene {i} line {j}: unknown speaker '{line.get('speaker')}'")
            if not text:
                problems.append(f"scene {i} line {j}: empty text")
            if len(text) > rules["max_chars_per_line"]:
                problems.append(f"scene {i} line {j}: longer than {rules['max_chars_per_line']} characters")
            if banned.search(text):
                problems.append(f"scene {i} line {j}: contains a banned word")
            n_lines += 1
            n_words += len(text.split())

    for seg in segments_needed:
        if seg not in segments_seen:
            problems.append(f"missing segment: {seg}")
    if not (rules["min_lines"] <= n_lines <= rules["max_lines"]):
        problems.append(f"{n_lines} lines; need {rules['min_lines']} to {rules['max_lines']}")
    if not (rules["min_words"] <= n_words <= rules["max_words"]):
        problems.append(f"{n_words} words; need {rules['min_words']} to {rules['max_words']}")

    signoff = BIBLE["series"]["daily_signoff"].lower()
    last_scene = script["scenes"][-1]
    if last_scene.get("lines") and signoff not in last_scene["lines"][-1]["text"].lower():
        problems.append("the final line must contain the daily sign-off")
    return problems


def generate_script(topic, history, insights, mock=False):
    if mock:
        return mock_script(topic)
    problems = None
    for attempt in range(1, MAX_GENERATION_TRIES + 1):
        print(f"Generating script (attempt {attempt}) ...")
        try:
            script = call_gemini(build_prompt(topic, history, insights, problems))
        except json.JSONDecodeError:
            problems = ["the reply was not valid JSON; return ONLY the JSON object"]
            continue
        problems = validate(script)
        if not problems:
            return script
        print("  rejected:", "; ".join(problems[:5]))
    sys.exit("Could not get a valid script. Nothing was published or saved.")


# ----------------------------------------------------------------- voices
def synthesize(text, voice, out_path, mock=False):
    if mock:
        write_silence(out_path, max(1.0, len(text.split()) * 0.38))
        return
    model = VOICE_DIR / f"{voice['model']}.onnx"
    if not model.exists():
        sys.exit(f"Voice model not found: {model}\nSee README for the download step.")
    cmd = [sys.executable, "-m", "piper", "--model", str(model),
           "--output_file", str(out_path),
           "--length_scale", str(voice.get("length_scale", 1.0))]
    if "speaker" in voice:
        cmd += ["--speaker", str(voice["speaker"])]
    subprocess.run(cmd, input=text.encode("utf-8"), check=True, capture_output=True)


def write_silence(path, seconds, rate=22050):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * seconds))


def voice_episode(script, ep_dir, mock=False):
    audio_dir = ep_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    clips = []   # (path, scene_index, segment, background, speaker, text)
    n = 0
    for si, scene in enumerate(script["scenes"], 1):
        for line in scene["lines"]:
            n += 1
            path = audio_dir / f"line_{n:03d}.wav"
            text = clean_for_tts(line["text"])
            print(f"  voicing {n}: {line['speaker']}")
            synthesize(text, BIBLE["characters"][line["speaker"]]["voice"], path, mock)
            clips.append((path, si, scene["segment"], scene["background"], line["speaker"], line["text"]))

    # join clips + build timeline
    final_path = ep_dir / "episode_audio.wav"
    timeline, cursor = [], 0.0
    with wave.open(str(clips[0][0]), "rb") as first:
        params = first.getparams()
    gap_frames = b"\x00" * (int(params.framerate * GAP_SECONDS) * params.sampwidth * params.nchannels)

    with wave.open(str(final_path), "wb") as out:
        out.setparams(params)
        for idx, (path, si, seg, bg, speaker, text) in enumerate(clips, 1):
            with wave.open(str(path), "rb") as w:
                if (w.getframerate(), w.getsampwidth(), w.getnchannels()) != \
                        (params.framerate, params.sampwidth, params.nchannels):
                    sys.exit("Voice models use different audio formats; use the same model family for all characters.")
                frames = w.readframes(w.getnframes())
                dur = w.getnframes() / w.getframerate()
            out.writeframes(frames)
            out.writeframes(gap_frames)
            timeline.append({
                "index": idx, "scene": si, "segment": seg, "background": bg,
                "speaker": speaker, "text": text,
                "start": round(cursor, 3), "end": round(cursor + dur, 3),
            })
            cursor += dur + GAP_SECONDS
    return timeline, cursor


# ----------------------------------------------------------------- mock (plumbing test only)
def mock_script(topic):
    ids = list(BIBLE["characters"])
    seg_plan = [("intro", "jungle", 4), ("adventure", "river", 8), ("fact", "museum", 4),
                ("song", "sky", 4), ("outro", "nest", 4)]
    scenes, k = [], 0
    for seg, bg, count in seg_plan:
        lines = []
        for _ in range(count):
            lines.append({"speaker": ids[k % len(ids)],
                          "text": "This is a test line about dinosaurs that is long enough to count as real words for the check."})
            k += 1
        scenes.append({"segment": seg, "background": bg, "lines": lines})
    scenes[-1]["lines"][-1]["text"] = BIBLE["series"]["daily_signoff"] + " Bye bye everyone, and keep on exploring with us!"
    return {"title": f"[TEST] {topic}"[:70], "description": "Test episode.", "tags": ["test"],
            "topic": topic, "fact": "Test fact.", "scenes": scenes}


# ----------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="skip Gemini and Piper (plumbing test)")
    ap.add_argument("--topic", help="force a topic instead of picking one")
    args = ap.parse_args()

    history = load_json(DATA_DIR / "history.json", [])
    insights = load_json(DATA_DIR / "insights.json", {})
    if not insights.get("guidance"):
        insights = {}
    topic = pick_topic(history, args.topic)
    print("Topic:", topic)

    script = generate_script(topic, history, insights, args.mock)

    ep_no = len(history) + 1
    ep_id = f"{datetime.date.today().isoformat()}_ep{ep_no:04d}"
    ep_dir = OUT_DIR / ep_id
    ep_dir.mkdir(parents=True, exist_ok=True)
    save_json(ep_dir / "script.json", script)

    print("Voicing ...")
    timeline, total = voice_episode(script, ep_dir, args.mock)
    save_json(ep_dir / "timeline.json", {"total_seconds": round(total, 2), "lines": timeline})

    if not args.mock:     # only real episodes count towards history
        history.append({
            "episode": ep_no, "id": ep_id, "date": datetime.date.today().isoformat(),
            "topic": topic, "title": script["title"], "fact": script["fact"],
            "characters": sorted({l["speaker"] for l in timeline}),
        })
        save_json(DATA_DIR / "history.json", history)

    (OUT_DIR / "latest.txt").write_text(ep_id, encoding="utf-8")
    print(f"Done: {ep_dir}  ({total / 60:.1f} minutes of audio)")


if __name__ == "__main__":
    main()
