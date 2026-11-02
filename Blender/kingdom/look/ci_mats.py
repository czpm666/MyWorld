import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

import bpy
import medkit as K
import hd_castle_int as INT

K.reset_scene()
M = INT.prep(INT.make_mats())
P = INT.build(K, M, origin=(0.0, 0.0), seed=3)
rows = []
for ob in P:
    if ob is None or ob.type != "MESH":
        continue
    vs = len(ob.data.vertices)
    mats = [m.name if m else "None" for m in ob.data.materials]
    rows.append((vs, ob.name, ",".join(mats)))
rows.sort(reverse=True)
for vs, nm, mt in rows[:26]:
    print("%6d %-20s %s" % (vs, nm, mt))
print("---materials in use---")
use = {}
for vs, nm, mt in rows:
    for m in mt.split(","):
        use[m] = use.get(m, 0) + vs
for m, v in sorted(use.items(), key=lambda kv: -kv[1]):
    print("%8d %s" % (v, m))
