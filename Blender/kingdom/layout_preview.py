"""layout_preview.py -- top-down schematic of the hd_layout town plan.

    python layout_preview.py                 # capital core + faubourgs
    python layout_preview.py --core          # walled city only
    python layout_preview.py --out foo.png

Draws (1 px = 1 m at --size 1600 for a 700 m wide city):
  streets      dark grey (they are simply the space between blocks)
  blocks       slightly lighter grey, outlined
  houses       by kind (see COL_HOUSE)
  functional   by kind (see COL_SHOP) -- these are the shops the brief asks for
  landmarks    dashed outline + label
  gates        white triangles on the wall circle
Everything is read from hd_layout, so the picture cannot drift from the build.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import hd_layout as L

try:
    from PIL import Image, ImageDraw
except Exception as exc:                                  # pragma: no cover
    raise SystemExit("Pillow is required for the preview: %s" % exc)

COL_BG = (26, 26, 29)
COL_BLOCK = (58, 56, 52)
COL_BLOCK_EDGE = (86, 82, 76)
COL_PLAZA = (96, 92, 82)
COL_LANDMARK = (150, 120, 90)
COL_WALL = (200, 196, 186)
COL_GATE = (255, 250, 230)

COL_HOUSE = {
    "timber": (150, 110, 70),
    "stone": (140, 138, 130),
    "shop": (196, 158, 84),
    "inn": (176, 96, 66),
    "manor": (128, 112, 158),
    "tower": (96, 138, 172),
    "warehouse": (118, 118, 86),
    "craft": (146, 158, 96),
}
COL_SHOP = {
    "tavern": (226, 116, 66),
    "blacksmith": (214, 66, 60),
    "magic_shop": (160, 108, 226),
    "clothier": (66, 176, 158),
    "general_store": (204, 196, 100),
    "bakery": (230, 186, 108),
    "stable": (166, 130, 66),
    "adventurers_guild": (70, 196, 100),
    "chapel": (238, 238, 198),
}


def to_px(p, cx, cy, sc, ox, oy):
    return (ox + (p[0] - cx) * sc, oy - (p[1] - cy) * sc)


def draw_rect(dr, cx, cy, w, d, yaw, col, cx0, cy0, sc, ox, oy, outline=None):
    pts = L.rect_poly(cx, cy, w, d, yaw)
    px = [to_px(p, cx0, cy0, sc, ox, oy) for p in pts]
    dr.polygon(px, fill=col, outline=outline)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", action="store_true", help="walled city only")
    ap.add_argument("--out", default=os.path.join(
        r"E:\My World\Blender\renders\kingdom", "layout_schematic.png"))
    ap.add_argument("--size", type=int, default=1600)
    ap.add_argument("--no-label", action="store_true")
    a = ap.parse_args(argv)

    specs = L.capital_layout_specs(outer=not a.core)
    res = L.layout_city(specs)
    pl = res["placements"]
    st = res["stats"]

    # world bounds of the blocks, padded
    xs = []
    ys = []
    for b in res["blocks"]:
        bx = L.poly_bbox(b["poly"])
        xs += [bx[0], bx[2]]
        ys += [bx[1], bx[3]]
    if not xs:
        xs, ys = [-320, 320], [-320, 320]
    x0, x1 = min(xs) - 24, max(xs) + 24
    y0, y1 = min(ys) - 24, max(ys) + 24
    span = max(x1 - x0, y1 - y0)
    sc = a.size / span
    W = int((x1 - x0) * sc) + 1
    H = int((y1 - y0) * sc) + 1
    img = Image.new("RGB", (W, H), COL_BG)
    dr = ImageDraw.Draw(img)
    ccx = (x0 + x1) * 0.5
    ccy = (y0 + y1) * 0.5
    ox = W * 0.5
    oy = H * 0.5

    # blocks
    for b in res["blocks"]:
        pts = [to_px(p, ccx, ccy, sc, ox, oy) for p in b["poly"]]
        dr.polygon(pts, fill=COL_BLOCK, outline=COL_BLOCK_EDGE)

    # city wall + gates
    wall_r = 300.0
    circ = [(wall_r * math.cos(math.tau * i / 240.0),
             wall_r * math.sin(math.tau * i / 240.0)) for i in range(240)]
    dr.line([to_px(p, ccx, ccy, sc, ox, oy) for p in circ], fill=COL_WALL, width=3)
    for g in ([(300.0, 0.0), (0.0, 300.0), (-300.0, 0.0), (0.0, -300.0)]
              if not a.core else []):
        gp = to_px(g, ccx, ccy, sc, ox, oy)
        dr.rectangle([gp[0] - 5, gp[1] - 5, gp[0] + 5, gp[1] + 5], fill=COL_GATE)

    # landmark reservations
    for (name, spec) in specs:
        for r in spec["reservations"]:
            if r.get("kind") == "disc":
                pts = [to_px((r["x"] + r["r"] * math.cos(math.tau * i / 64.0),
                              r["y"] + r["r"] * math.sin(math.tau * i / 64.0)),
                             ccx, ccy, sc, ox, oy) for i in range(64)]
            else:
                pts = [to_px(p, ccx, ccy, sc, ox, oy)
                       for p in L.rect_poly(r["x"], r["y"], r["w"], r["d"], r.get("rot", 0.0))]
            dr.polygon(pts, outline=COL_LANDMARK, fill=(44, 40, 36))

    # buildings: functional first so houses never hide them
    for p in pl:
        if p["source"] == "shop":
            continue
        col = COL_HOUSE.get(p["kind"], (160, 160, 160))
        draw_rect(dr, p["x"], p["y"], p["w"] + L.HOUSE_EXTRA_W, p["d"] + L.HOUSE_EXTRA_D,
                  p["yaw"], col, ccx, ccy, sc, ox, oy)
    for p in pl:
        if p["source"] != "shop":
            continue
        col = COL_SHOP.get(p["kind"], (255, 0, 255))
        draw_rect(dr, p["x"], p["y"], p["w"], p["d"], p["yaw"], col,
                  ccx, ccy, sc, ox, oy, outline=(20, 20, 20))

    # legend
    if not a.no_label:
        lx, ly = 12, 12
        rows = [("blocks %d  sub %d  buildings %d  (houses %d / shops %d)"
                 % (st["blocks"], st["sub_blocks"], st["buildings"],
                    st["houses"], st["shops"]), None)]
        for k in ("tavern", "blacksmith", "magic_shop", "clothier", "general_store",
                  "bakery", "stable", "adventurers_guild", "chapel"):
            n = st["kinds"].get(k, 0)
            if n:
                rows.append(("%s %d" % (k, n), COL_SHOP[k]))
        for k in ("timber", "stone", "shop", "inn", "manor", "tower", "warehouse", "craft"):
            n = st["kinds"].get(k, 0)
            if n:
                rows.append(("%s %d" % (k, n), COL_HOUSE[k]))
        rows.append(("built %.0f m2 / %.0f m2 = %.1f%%"
                     % (st["build_m2"], st["area_m2"], 100.0 * st["build_m2"] / st["area_m2"]), None))
        h = 15 * len(rows) + 10
        w = 250
        dr.rectangle([lx - 6, ly - 6, lx + w, ly + h], fill=(18, 18, 20), outline=(90, 88, 82))
        for i, (txt, col) in enumerate(rows):
            yy = ly + 5 + i * 15
            if col:
                dr.rectangle([lx, yy + 2, lx + 9, yy + 11], fill=col)
                dr.text((lx + 15, yy), txt, fill=(226, 224, 218))
            else:
                dr.text((lx, yy), txt, fill=(240, 238, 230))
        # scale bar
        bar = 100 * sc
        bx0, by0 = W - bar - 24, H - 26
        dr.rectangle([bx0, by0, bx0 + bar, by0 + 4], fill=(230, 228, 220))
        dr.text((bx0, by0 - 14), "100 m", fill=(230, 228, 220))
        dr.text((W - 250, H - 44), "top = +Y (north)", fill=(140, 138, 130))

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    img.save(a.out)
    print("wrote", a.out, "%dx%d" % (W, H))
    print("blocks      =", st["blocks"])
    print("sub-blocks  =", st["sub_blocks"])
    print("buildings   =", st["buildings"],
          "(houses", st["houses"], "/ shops", st["shops"], ")")
    print("area m2     =", int(st["area_m2"]), " built m2 =", int(st["build_m2"]),
          " coverage = %.1f%%" % (100.0 * st["build_m2"] / st["area_m2"]))
    print("roles       =", st["roles"])
    print("kinds       =", dict(sorted(st["kinds"].items(), key=lambda kv: -kv[1])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
