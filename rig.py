"""
rig.py - the puppet engine. Loads a character's layers (assets/rig/<id>/*.png) and
assembles them into one picture for a given pose, so characters can nod, tilt, wave,
flap, jump and squash like cartoon animation instead of being a single flat picture.

pose keys: mouth closed|open|oh   eyes open|blink|wide   brows norm|up
           head (deg)  head_dy (px)  armL armR (deg, + = rotate counter-clockwise)  tail  plates
Angle convention: left arm/wing raises with NEGATIVE degrees, right arm/wing with POSITIVE.
"""
import json
import math
from pathlib import Path

from PIL import Image, ImageEnhance

RIG_DIR = Path(__file__).resolve().parent / "assets" / "rig"
DEFAULT = dict(mouth="closed", eyes="open", brows="norm", head=0.0, head_dy=0.0,
               armL=0.0, armR=0.0, tail=0.0, plates=0.0, look_x=0.0, look_y=0.0)
COLOR_BOOST, BRIGHT_BOOST = 1.18, 1.05          # vibrant, bright colours


def _boost(im, color=COLOR_BOOST, bright=BRIGHT_BOOST):
    r, g, b, a = im.split()
    rgb = Image.merge("RGB", (r, g, b))
    rgb = ImageEnhance.Brightness(ImageEnhance.Color(rgb).enhance(color)).enhance(bright)
    r, g, b = rgb.split()
    return Image.merge("RGBA", (r, g, b, a))


def _shift(img, dx, dy):
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (dx, dy))
    return out


def _blit(canvas, im, x, y):
    """alpha-composite im onto canvas at (x, y), clipping at the edges (negative x/y allowed)."""
    cw, ch = canvas.size
    w, h = im.size
    x0, y0, x1, y1 = max(0, -x), max(0, -y), min(w, cw - x), min(h, ch - y)
    if x1 <= x0 or y1 <= y0:
        return
    if (x0, y0, x1, y1) != (0, 0, w, h):
        im = im.crop((x0, y0, x1, y1))
    canvas.alpha_composite(im, (x + x0, y + y0))


class Rig:
    _all = {}

    @classmethod
    def get(cls, cid):
        if cid not in cls._all:
            cls._all[cid] = cls(cid)
        return cls._all[cid]

    def __init__(self, cid):
        d = RIG_DIR / cid
        self.spec = json.loads((d / "rig.json").read_text())
        color, bright = self.spec.get("boost", [COLOR_BOOST, BRIGHT_BOOST])
        self.base = {p.stem: _boost(Image.open(p).convert("RGBA"), color, bright) for p in d.glob("*.png")}
        self._scaled, self._cropped, self._geom, self._cache = {}, {}, {}, {}

    def _layers(self, size):
        if size not in self._scaled:
            self._scaled[size] = {n: im.resize((size, size), Image.LANCZOS) for n, im in self.base.items()}
        return self._scaled[size]

    def _static(self, size, name):
        """(cropped image, x, y) of a layer's visible part only (fast to paste)."""
        key = (size, name)
        if key not in self._cropped:
            im = self._layers(size)[name]
            bb = im.getbbox()
            self._cropped[key] = (im.crop(bb), bb[0], bb[1]) if bb else (None, 0, 0)
        return self._cropped[key]

    def _geo(self, size, i, item):
        """(pivot x, pivot y, radius R): a square around the pivot that always contains the rotated part."""
        key = (size, i)
        if key not in self._geom:
            L, f = self._layers(size), size / 600.0
            px, py = (int(round(v * f)) for v in item["pivot"])
            if "layer" in item:
                names = [item["layer"]]
            else:
                names = [n for n in L if any(n == m or n.startswith(m + "_") for m in item["members"])]
            xs, ys = [], []
            for n in names:
                bb = L[n].getbbox()
                if bb:
                    xs += [bb[0], bb[2]]
                    ys += [bb[1], bb[3]]
            R = 4 if not xs else int(max(math.hypot(cx - px, cy - py) for cx in (min(xs), max(xs))
                                         for cy in (min(ys), max(ys)))) + 4
            self._geom[key] = (px, py, R)
        return self._geom[key]

    def compose(self, pose, size):
        p = dict(DEFAULT)
        p.update(pose)
        nums = {k: int(round(p[k])) for k in ("head", "head_dy", "armL", "armR", "tail", "plates", "look_x", "look_y")}
        key = (size, p["mouth"], p["eyes"], p["brows"]) + tuple(nums.values())
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        L, f = self._layers(size), size / 600.0
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        for i, item in enumerate(self.spec["order"]):
            ang = nums.get(item.get("param"), 0) if item.get("param") else 0
            if "layer" in item:
                if not ang:
                    im, x, y = self._static(size, item["layer"])
                    if im is not None:
                        _blit(canvas, im, x, y)
                else:
                    px, py, R = self._geo(size, i, item)
                    box = (px - R, py - R, px + R, py + R)
                    part = L[item["layer"]].crop(box).rotate(ang, resample=Image.BILINEAR, center=(R, R))
                    _blit(canvas, part, px - R, py - R)
            else:
                px, py, R = self._geo(size, i, item)
                box = (px - R, py - R, px + R, py + R)
                g = Image.new("RGBA", (2 * R, 2 * R), (0, 0, 0, 0))
                for m in item["members"]:
                    name = m if m in L else f"{m}_{p[m]}"
                    if name in L:
                        part = L[name].crop(box)
                        if m == "eyes" and (nums["look_x"] or nums["look_y"]):
                            part = _shift(part, int(nums["look_x"] * f), int(nums["look_y"] * f))
                        g.alpha_composite(part)
                if ang:
                    g = g.rotate(ang, resample=Image.BILINEAR, center=(R, R))
                _blit(canvas, g, px - R, py - R + int(nums["head_dy"] * f))
        if len(self._cache) > 160:
            self._cache.clear()
        self._cache[key] = canvas
        return canvas
