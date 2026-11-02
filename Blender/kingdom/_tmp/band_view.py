"""Draw one block: kerb polygon, the band each edge owns, and the houses placed.

Helps see why a street wall stops: the band is the legal ground for a row, so a
house that lands inside it must be placeable.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw

import hd_layout as L

S = 800
OUT = r"E:\My World\Blender\renders\kingdom\_tmp_band.png"


def draw(poly, bands, rects, path):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pad = 6.0
    sc = (S - 40) / max(x1 - x0 + 2 * pad, y1 - y0 + 2 * pad)

    def T(p):
        return (20 + (p[0] - x0 + pad) * sc, S - 20 - (p[1] - y0 + pad) * sc)

    im = Image.new("RGB", (S, S), (250, 248, 244))
    d = ImageDraw.Draw(im)
    for band in bands:
        d.polygon([T(p) for p in band], fill=(210, 226, 240), outline=(120, 150, 180))
    for r in rects:
        col = (196, 150, 60) if r.get("source") == "shop" else (176, 92, 74)
        d.polygon([T(p) for p in L.rect_pts(r["pos"][0], r["pos"][1],
                                            r["w"], r["d"], r["rz"])],
                  fill=col, outline=(60, 40, 30))
    d.polygon([T(p) for p in poly], outline=(20, 20, 20))
    im.save(path)
    return path


if __name__ == "__main__":
    bid = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    lay = L.generate(radius=636.0, seed=20261022)
    bl = [b for b in lay["blocks"] if not b["open"]]
    b = bl[bid]
    poly = b["poly"]
    bands = [L.edge_band(poly, i, L.SETBACK["main"] + 14.5)
             for i in range(len(poly))]
    rects = [p for p in lay["plots"] if p["block_id"] == b["id"]]
    p = draw(poly, [x for x in bands if len(x) > 2], rects, OUT)
    print("block", b["id"], "area %.0f" % b["area"], "bld", b.get("buildings"),
          "verts", len(poly), "->", p)
