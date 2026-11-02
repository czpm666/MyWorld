# probe the river cross-section at the two bridges (run with blender -b -P)
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa
import hd_landscape as L

r = L.build({}, res=20.0, seed=1337)
print("[t10] build", r["count"], r["faces"], "%.1fs" % r["seconds"])

for (cx, cy, nm, ax) in ((-1000.0, 0.0, "west", "x"), (0.0, -905.0, "south", "y")):
    wl, d, hw = L._water_level(cx, cy)
    print("[t10] %s water wl=%.2f d=%.1f hw=%.2f span=%.1f"
          % (nm, wl, d, hw, max(1.0, hw * 5.4 + 16.0)))
    row = []
    for t in range(-120, 121, 8):
        if ax == "x":
            x, y = cx, cy + t
        else:
            x, y = cx + t, cy
        row.append("%d:%.1f" % (t, float(L._gz(x, y))))
    print("[t10]   bed profile", " ".join(row))
    row = []
    for t in range(-120, 121, 8):
        if ax == "x":
            x, y = cx, cy + t
        else:
            x, y = cx + t, cy
        row.append("%d:%d" % (t, 1 if float(L._gz(x, y)) < wl else 0))
    print("[t10]   underwater  ", " ".join(row))
