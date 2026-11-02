"""Diagnose why plot_row rejects so much: which predicate fails, and where."""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hd_layout as L

C = {"clr": 0, "poly": 0, "curb": 0, "ok": 0, "tries": 0}
SAMPLES = []

_pic = L.point_in_convex
_clr = L.street_clearance


def pic(point, poly, eps=0.0):
    ok = _pic(point, poly, eps)
    if not ok:
        C["poly"] += 1
    return ok


def clr(pts):
    v = _clr(pts)
    if v < 0.4:
        C["clr"] += 1
    return v


L.point_in_convex = pic
L.street_clearance = clr

lay = L.generate(radius=636.0, seed=20261022)
print("counters", C)
st = lay["city"]["stats"]
print("why", st.get("why"))
pl = lay["plots"]
a = sum(max(1.0, p.get("w", 8.0)) * max(1.0, p.get("d", 9.0)) for p in pl)
print("plots %d footprint %.0f coverage %.1f%%"
      % (len(pl), a, 100.0 * a / (math.pi * 636.0 ** 2)))
bl = [b for b in lay["blocks"] if not b["open"]]
print("blocks", len(bl), "median bld",
      sorted(b.get("buildings", 0) for b in bl)[len(bl) // 2])
for b in bl[:6]:
    print("  block %d area %.0f bld %d verts %d"
          % (b["id"], b["area"], b.get("buildings", 0), len(b["poly"])))
