"""Name census of the saved city: prefix -> object count / verts / radius."""
import math
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
KING = os.path.dirname(HERE)
for _p in (KING, os.path.dirname(KING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy                                                   # noqa: E402
import capital as C                                          # noqa: E402

C.HD["on"] = True
bpy.ops.wm.open_mainfile(filepath=os.path.join(C.OUT_PNG, "capital_full.blend"))

agg = defaultdict(lambda: [0, 0, 0.0])
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    pre = re.match(r"[A-Za-z_]+", ob.name)
    key = pre.group(0).rstrip("_") if pre else "?"
    a = agg[key]
    a[0] += 1
    a[1] += len(ob.data.vertices)
    for v in list(ob.data.vertices)[::37]:
        w = ob.matrix_world @ v.co
        a[2] = max(a[2], math.hypot(w.x, w.y))

print("%-16s %6s %10s %8s" % ("prefix", "objs", "verts(samp)", "rmax"), flush=True)
for k in sorted(agg, key=lambda k: -agg[k][1]):
    n, verts, rmax = agg[k]
    print("%-16s %6d %10d %8.1f" % (k, n, verts, rmax), flush=True)
print("CENSUS_DONE", flush=True)
