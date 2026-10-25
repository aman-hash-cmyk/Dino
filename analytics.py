#!/usr/bin/env python3
"""
analytics.py - the feedback loop. Run weekly.

For every uploaded episode (at least 2 days old) it asks the YouTube Analytics API for
views, average % watched and the audience-retention curve, maps the curve onto the
episode's segments (intro / adventure / fact / song / outro), and writes
data/insights.json. make_episode.py feeds that file to the script writer.
"""
import datetime
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "data" / "history.json"
INSIGHTS = ROOT / "data" / "insights.json"
BIBLE = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))
MIN_EPISODES = 3     # below this the data is too thin to steer anything


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def main():
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from yt_auth import get_credentials

    history = json.loads(HISTORY.read_text(encoding="utf-8")) if HISTORY.exists() else []
    ya = build("youtubeAnalytics", "v2", credentials=get_credentials(), cache_discovery=False)
    today = datetime.date.today()
    end = (today - datetime.timedelta(days=1)).isoformat()

    rows, seg_acc = [], defaultdict(list)
    for h in history:
        vid = h.get("video_id")
        if not vid or (today - datetime.date.fromisoformat(h["date"])).days < 2:
            continue
        try:
            m = ya.reports().query(
                ids="channel==MINE", startDate=h["date"], endDate=end,
                metrics="views,averageViewDuration,averageViewPercentage",
                filters=f"video=={vid}").execute().get("rows") or []
            if not m or m[0][0] < 1:
                continue
            curve = ya.reports().query(
                ids="channel==MINE", startDate=h["date"], endDate=end,
                metrics="audienceWatchRatio", dimensions="elapsedVideoTimeRatio",
                filters=f"video=={vid}").execute().get("rows") or []
        except HttpError as e:
            print("skip", vid, e)
            continue
        rows.append({"topic": h["topic"], "title": h["title"], "views": m[0][0],
                     "avg_pct": m[0][2], "characters": h.get("characters", [])})
        for seg in h.get("segments", []):
            vals = [w for r, w in curve if seg["start"] <= r < seg["end"]]
            if vals:
                seg_acc[seg["segment"]].append(mean(vals))

    insights = {"updated": today.isoformat(), "episodes_measured": len(rows), "guidance": []}
    if len(rows) >= MIN_EPISODES:
        by_ret = sorted(rows, key=lambda r: r["avg_pct"], reverse=True)
        by_views = sorted(rows, key=lambda r: r["views"], reverse=True)
        insights["best_topics"] = [r["topic"] for r in by_views[:3]]
        insights["held_attention_topics"] = [r["topic"] for r in by_ret[:3]]
        insights["weakest_topics"] = [r["topic"] for r in by_ret[-2:]]
        insights["segment_retention"] = {k: round(mean(v), 3) for k, v in seg_acc.items() if k not in ("title", "end")}

        char_pct = defaultdict(list)
        for r in rows:
            for c in r["characters"]:
                char_pct[c].append(r["avg_pct"])
        ranked = sorted(((mean(v), c) for c, v in char_pct.items() if len(v) >= 2), reverse=True)
        top_chars = [BIBLE["characters"][c]["name"] for _, c in ranked[:2] if c in BIBLE["characters"]]

        g = insights["guidance"]
        g.append("Topics viewers watched the most or the longest: "
                 + "; ".join(dict.fromkeys(insights["best_topics"] + insights["held_attention_topics"]))
                 + ". Make new episodes on similar themes (never repeat them).")
        seg = insights["segment_retention"]
        if seg:
            worst = min(seg, key=seg.get)
            g.append(f"Viewers leave most during the '{worst}' segment (avg watch ratio {seg[worst]:.0%}); "
                     "make it shorter, livelier and more interactive.")
        if top_chars:
            g.append("Episodes featuring " + " and ".join(top_chars) + " kept viewers watching longest; give them bigger roles.")
        if insights["weakest_topics"]:
            g.append("Avoid themes like: " + "; ".join(insights["weakest_topics"]) + ".")

    INSIGHTS.write_text(json.dumps(insights, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(insights, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
