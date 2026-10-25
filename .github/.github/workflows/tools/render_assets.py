#!/usr/bin/env python3
"""
render_assets.py - turns assets/**/*.svg into PNG files (one-time step).

Needs:  pip install playwright && playwright install chromium
Characters -> transparent PNG (600x600). Backgrounds -> PNG (1920x1080).
Commit the PNGs to your repo; the daily pipeline then needs no SVG renderer.
"""
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def main():
    files = sorted(ASSETS.glob("*/*.svg"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for f in files:
            m = re.search(r'viewBox="0 0 (\d+) (\d+)"', f.read_text(encoding="utf-8"))
            w, h = int(m.group(1)), int(m.group(2))
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(f.resolve().as_uri())
            page.screenshot(path=str(f.with_suffix(".png")), omit_background=True)
            page.close()
            print("rendered", f.relative_to(ROOT))
        browser.close()


if __name__ == "__main__":
    main()
