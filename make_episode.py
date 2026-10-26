
#!/usr/bin/env python3
"""Generate an original toddler-friendly dinosaur counting episode with Gemini + Piper TTS.

Outputs:
  output/episode.json
  output/audio/line_001.wav, ...
  output/audio/vocals.wav

Environment:
  GEMINI_API_KEY=...
  PIPER_VOICE=/path/to/en_US-lessac-medium.onnx
  PIPER_CONFIG=/path/to/en_US-lessac-medium.onnx.json  # optional
  GEMINI_MODEL=gemini-3.8-flash  # optional

Install:
  pip install google-genai

Piper must be installed separately and available as `piper` on PATH.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

DINOSAURS = [
    {
        "name": "Stegosaurus",
        "color": "leaf green",
        "action": "waddle and wiggle their tails",
    },
    {
        "name": "Triceratops",
        "color": "sunshine yellow",
        "action": "play and give a gentle happy bounce",
    },
    {
        "name": "Pterodactyl",
        "color": "soft purple",
        "action": "gently flap their wings and float",
    },
    {
        "name": "Brontosaurus",
        "color": "friendly teal",
        "action": "stretch their long necks to nibble leaves",
    },
    {
        "name": "Tyrannosaurus Rex",
        "color": "warm orange",
        "action": "take tiny gentle stomps and smile",
    },
]

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, default=Path("output"))
    p.add_argument("--episode-title", default="10 Little Dinosaurs")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--voice", default=os.getenv("PIPER_VOICE", ""))
    p.add_argument("--piper-config", default=os.getenv("PIPER_CONFIG", ""))
    p.add_argument("--piper-bin", default="piper")
    p.add_argument("--count", type=int, choices=range(1, 11), default=10)
    p.add_argument(
        "--skip-gemini",
        action="store_true",
        help="Use the built-in original lyric template; still generate Piper audio.",
    )
    return p.parse_args()


def built_in_segments(count: int) -> list[dict[str, Any]]:
    """Create a simple original template for early-learning content."""
    segments: list[dict[str, Any]] = []

    for dino in DINOSAURS:
        lines = [
            f"One little, two little, three little {dino['name']}s,",
            f"Four little, five little, six little {dino['name']}s,",
            f"Seven little, eight little, nine little {dino['name']}s,",
            f"{count} little dinosaur babies!",
            f"Little {dino['name']}s, wiggle and play,",
            "Count our dinosaur friends today!",
        ]

        segments.extend(
            {
                "text": line,
                "dinosaur": dino["name"],
                "count": count if i == 3 else None,
            }
            for i, line in enumerate(lines)
        )

    segments.extend(
        [
            {
                "text": "We counted our dinosaurs, hooray, hooray!",
                "dinosaur": "All",
            },
            {
                "text": "Wave goodbye, little friends. Come back and play!",
                "dinosaur": "All",
            },
        ]
    )

    return segments


def gemini_segments(model: str, count: int) -> list[dict[str, Any]]:
    """Generate and validate episode segments using Gemini, with retries."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Set it or pass --skip-gemini."
        )

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency. Install with: pip install google-genai"
        ) from exc

    dino_list = "\n".join(
        f"- {d['name']}: {d['action']}."
        for d in DINOSAURS
    )

    prompt = f"""
Create an ORIGINAL toddler-safe dinosaur counting song script for a YouTube episode.
Use a cheerful, repetitive nursery-rhyme rhythm, but do not imitate or quote any named
artist, channel, or copyrighted song. Use simple vocabulary, warm and non-scary imagery.

There are five sections, in this order:
{dino_list}

Count from 1 to {count} clearly in each section. Each section should have 4-6 short
spoken/sing-song lines, with number words written out (One, two, etc.) so TTS can read
them naturally. Include a tiny action cue in a separate `visual_action` field for each
line, chosen from: hatch, waddle, play, flap, nibble, stomp, wave, sparkle.

Finish with two short goodbye/celebration lines.

Return ONLY valid JSON with this schema:
{{
  "title": "10 Little Dinosaurs",
  "segments": [
    {{
      "text": "line to speak",
      "dinosaur": "Stegosaurus",
      "visual_action": "hatch",
      "count": 1
    }}
  ]
}}

Every segment must have text and dinosaur; visual_action is optional; count is optional.
Do not add markdown fences. Keep the entire script under 55 segments.
The episode title is "10 Little Dinosaurs". Number words should be spoken clearly.
Dinosaur names and pluralization should be easy to pronounce.
"""

    response = None

    for attempt in range(3):
        client = genai.Client(api_key=api_key)

        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            break

        except Exception as exc:
            if attempt == 2:
                raise

            print(
                f"Gemini request failed (attempt {attempt + 1}/3): {exc}. "
                "Retrying..."
            )
            time.sleep(2 ** (attempt + 1))

        finally:
            client.close()

    if response is None:
        raise RuntimeError(
            "Gemini did not return a response after 3 attempts."
        )

    raw = response.text or ""

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Gemini did not return valid JSON: {raw[:500]}"
        ) from exc

    segments = data.get("segments")

    if not isinstance(segments, list) or not segments:
        raise RuntimeError(
            "Gemini response has no non-empty 'segments' list."
        )

    clean: list[dict[str, Any]] = []
    allowed = {d["name"] for d in DINOSAURS} | {"All"}

    for item in segments:
        if not isinstance(item, dict):
            continue

        if not isinstance(item.get("text"), str):
            continue

        text = " ".join(item["text"].split()).strip()

        if not text:
            continue

        dinosaur = item.get("dinosaur", "All")

        if dinosaur not in allowed:
            dinosaur = "All"

        clean.append(
            {
                "text": text,
                "dinosaur": dinosaur,
                "visual_action": item.get("visual_action", "waddle"),
                "count": item.get("count"),
            }
        )

    if not clean:
        raise RuntimeError("Gemini returned no usable lyric lines.")

    return clean


def run_piper(
    text: str,
    output_path: Path,
    args: argparse.Namespace,
) -> None:
    if not args.voice:
        raise RuntimeError(
            "Piper voice model not configured. "
            "Set PIPER_VOICE to a .onnx model path."
        )

    if not shutil.which(args.piper_bin):
        raise RuntimeError(
            f"Piper executable '{args.piper_bin}' was not found on PATH."
        )

    cmd = [
        args.piper_bin,
        "--model",
        args.voice,
        "--output_file",
        str(output_path),
    ]

    if args.piper_config:
        cmd += ["--config", args.piper_config]

    subprocess.run(
        cmd,
        input=text,
        text=True,
        check=True,
    )


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / float(wf.getframerate())


def concatenate_wavs(
    paths: list[Path],
    output_path: Path,
    ffmpeg: str = "ffmpeg",
) -> None:
    if not paths:
        raise RuntimeError("No generated audio segments.")

    if not shutil.which(ffmpeg):
        raise RuntimeError(
            "ffmpeg is required to join Piper WAV files "
            "and was not found on PATH."
        )

    list_path = output_path.parent / "audio_concat.txt"
    normalized: list[Path] = []

    for i, path in enumerate(paths):
        norm = output_path.parent / f"normalized_{i:03d}.wav"

        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(path),
                "-ar",
                "22050",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(norm),
            ],
            check=True,
        )

        normalized.append(norm)

    list_path.write_text(
        "".join(
            f"file '{p.resolve().as_posix()}'\n"
            for p in normalized
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        check=True,
    )

    for path in normalized:
        path.unlink(missing_ok=True)

    list_path.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()

    audio_dir = args.output_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if args.skip_gemini:
        segments = built_in_segments(args.count)
    else:
        try:
            segments = gemini_segments(args.model, args.count)
        except Exception as exc:
            print(
                f"Gemini generation failed: {exc}",
                file=sys.stderr,
            )
            print(
                "Tip: use --skip-gemini for the built-in lyric template.",
                file=sys.stderr,
            )
            return 2

    audio_paths: list[Path] = []
    cursor = 0.0

    for idx, segment in enumerate(segments, start=1):
        path = audio_dir / f"line_{idx:03d}.wav"

        try:
            run_piper(segment["text"], path, args)
        except Exception as exc:
            print(
                f"Piper failed on segment {idx}: {exc}",
                file=sys.stderr,
            )
            return 3

        duration = wav_duration(path)

        segment["audio_file"] = str(
            path.relative_to(args.output_dir)
        )
        segment["duration"] = round(duration, 3)
        segment["start"] = round(cursor, 3)

        cursor += duration
        audio_paths.append(path)

    vocals_path = audio_dir / "vocals.wav"

    try:
        concatenate_wavs(audio_paths, vocals_path)
    except Exception as exc:
        print(
            f"Could not combine voice clips: {exc}",
            file=sys.stderr,
        )
        return 4

    episode = {
        "title": args.episode_title,
        "width": 1280,
        "height": 720,
        "fps": 24,
        "voice_file": str(vocals_path.relative_to(args.output_dir)),
        "total_duration": round(cursor, 3),
        "dinosaurs": DINOSAURS,
        "segments": segments,
        "notes": (
            "Piper produces spoken TTS, not sung vocals. "
            "Replace vocals.wav with licensed singing vocals if desired."
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest = args.output_dir / "episode.json"
    manifest.write_text(
        json.dumps(episode, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Created {manifest}")
    print(f"Created {vocals_path}")
    print(
        f"Segments: {len(segments)} | duration: {cursor:.1f}s"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
