#!/usr/bin/env python3
"""Pre-upload quality gate for Dino Pals episodes.

Checks that the expected episode files exist and are readable, timeline data is
sane, audio/video durations are plausible, and a thumbnail is present. This is
a technical validation step; it does not verify factual accuracy or guarantee
that a video is appropriate for children.

Usage: python validate_episode.py [episode_id]
"""
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "output"
THUMB_NAMES = ("thumbnail.jpg", "thumbnail.jpeg", "thumbnail.png", "thumbnail.webp",
               "thumb.jpg", "thumb.png", "thumbnail.jpeg")


def fail(errors, message):
    errors.append(message)
    print(f"[FAIL] {message}")


def ok(message):
    print(f"[ OK ] {message}")


def duration_from_wav(path):
    with wave.open(str(path), "rb") as wav:
        if wav.getframerate() <= 0:
            raise ValueError("invalid sample rate")
        return wav.getnframes() / float(wav.getframerate())


def ffprobe_duration(path):
    if not shutil.which("ffprobe"):
        return None
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "ffprobe could not read file")
    return float(result.stdout.strip())


def main():
    if len(sys.argv) > 2:
        print("Usage: python validate_episode.py [episode_id]", file=sys.stderr)
        return 2
    latest_file = OUT_DIR / "latest.txt"
    episode_id = sys.argv[1] if len(sys.argv) == 2 else (
        latest_file.read_text(encoding="utf-8").strip() if latest_file.exists() else ""
    )
    if not episode_id:
        print("[FAIL] No episode ID found. Pass one or create output/latest.txt.")
        return 1

    ep_dir = OUT_DIR / episode_id
    # Prevent an episode ID from escaping the output directory.
    if ep_dir.resolve().parent != OUT_DIR.resolve():
        print("[FAIL] Invalid episode ID/path.")
        return 2
    print(f"\nDino Pals pre-upload check: {episode_id}\n")
    errors = []

    required = ["script.json", "timeline.json", "episode_audio.wav", "video.mp4"]
    for name in required:
        p = ep_dir / name
        if p.is_file() and p.stat().st_size > 0:
            ok(f"Found {name} ({p.stat().st_size:,} bytes)")
        else:
            fail(errors, f"Missing or empty file: {name}")

    script = timeline = None
    try:
        script = json.loads((ep_dir / "script.json").read_text(encoding="utf-8"))
        if not isinstance(script, dict) or not script.get("title"):
            fail(errors, "script.json must contain a non-empty title")
        else:
            ok(f"Script title: {str(script['title'])[:100]}")
    except (OSError, json.JSONDecodeError) as exc:
        fail(errors, f"Cannot read script.json: {exc}")

    try:
        timeline = json.loads((ep_dir / "timeline.json").read_text(encoding="utf-8"))
        lines = timeline.get("lines") if isinstance(timeline, dict) else None
        total = float(timeline.get("total_seconds", 0)) if isinstance(timeline, dict) else 0
        if not isinstance(lines, list) or not lines:
            fail(errors, "timeline.json must contain a non-empty 'lines' list")
        else:
            bad = []
            previous_start = -1.0
            for i, line in enumerate(lines, start=1):
                try:
                    start, end = float(line["start"]), float(line["end"])
                    if start < 0 or end <= start or start < previous_start:
                        bad.append(i)
                    previous_start = start
                except (KeyError, TypeError, ValueError):
                    bad.append(i)
            if bad:
                fail(errors, f"Invalid or out-of-order timeline entries at line(s): {bad[:10]}")
            else:
                ok(f"Timeline has {len(lines)} valid, ordered lines")
            last_end = max((float(x.get("end", 0)) for x in lines if isinstance(x, dict)), default=0)
            if total <= 0 or total + 1 < last_end:
                fail(errors, f"Invalid timeline total_seconds ({total}); last line ends at {last_end:.2f}s")
            else:
                ok(f"Timeline duration: {total:.1f}s")
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        fail(errors, f"Cannot validate timeline.json: {exc}")

    audio_path = ep_dir / "episode_audio.wav"
    if audio_path.is_file() and audio_path.stat().st_size:
        try:
            audio_seconds = duration_from_wav(audio_path)
            if audio_seconds <= 0:
                fail(errors, "episode_audio.wav has zero duration")
            else:
                ok(f"Source audio duration: {audio_seconds:.1f}s")
                if timeline and isinstance(timeline, dict):
                    expected = float(timeline.get("total_seconds", 0))
                    # Audio can include short trailing padding, so allow a small tolerance.
                    if expected > 0 and abs(audio_seconds - expected) > max(5.0, expected * 0.12):
                        fail(errors, f"Audio/timeline duration mismatch ({audio_seconds:.1f}s vs {expected:.1f}s)")
        except (OSError, wave.Error, ValueError) as exc:
            fail(errors, f"Cannot read episode_audio.wav: {exc}")

    video_path = ep_dir / "video.mp4"
    if video_path.is_file() and video_path.stat().st_size:
        try:
            video_seconds = ffprobe_duration(video_path)
            if video_seconds is None:
                print("[WARN] ffprobe not installed; skipped MP4 duration/readability check")
            elif video_seconds <= 0:
                fail(errors, "video.mp4 reports zero duration")
            else:
                ok(f"Video duration: {video_seconds:.1f}s")
                if timeline and isinstance(timeline, dict):
                    expected_video = float(timeline.get("total_seconds", 0)) + 6.5
                    if expected_video > 0 and abs(video_seconds - expected_video) > max(4.0, expected_video * 0.08):
                        fail(errors, f"Video duration differs from expected ~{expected_video:.1f}s (got {video_seconds:.1f}s)")
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            fail(errors, f"Cannot inspect video.mp4: {exc}")

    thumbs = [ep_dir / name for name in THUMB_NAMES if (ep_dir / name).is_file() and (ep_dir / name).stat().st_size > 0]
    if thumbs:
        ok(f"Thumbnail found: {thumbs[0].name}")
    else:
        fail(errors, "No thumbnail found. Expected thumbnail.jpg, thumbnail.png, thumbnail.webp, or thumb.jpg/png")

    print("\n" + (f"PRE-UPLOAD CHECK FAILED: {len(errors)} issue(s). Upload should be skipped."
                    if errors else "PRE-UPLOAD CHECK PASSED. Please still watch the video and verify its facts before publishing."))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
