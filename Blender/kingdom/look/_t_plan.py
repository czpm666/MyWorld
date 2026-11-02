"""Smoke test for the plan2 wiring: build the layout only, no geometry.

    blender -b --factory-startup --python look/_t_plan.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
for p in (os.path.dirname(KIND), KIND, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import capital as C

C.HD["on"] = True
C.HD_DENSE["on"] = True
C.HD_PLAN["plan2"] = True
print("[t] CITY_SCALE", C.CITY_SCALE, "R_WALL", C.R_WALL, "R_OUTER", C.R_OUTER)

t0 = time.time()
res = C.hd_layout_res()
print("[t] blocks %d streets %d" % (len(res["blocks"]), len(res["streets"])))
t1 = time.time()
pl = C.hd_pick()
print("[t] picked %d in %.1f s (layout %.1f s)" % (len(pl), time.time() - t1, t1 - t0))
kinds = {}
for p in pl:
    kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
for k in sorted(kinds, key=lambda k: -kinds[k])[:12]:
    print("   %-18s %d" % (k, kinds[k]))
w = sorted(p.get("w", 0.0) for p in pl)
d = sorted(p.get("d", 0.0) for p in pl)
print("[t] w median %.1f   d median %.1f   floors %s"
      % (w[len(w) // 2], d[len(d) // 2],
         sorted(set(p.get("floors", 0) for p in pl))))
