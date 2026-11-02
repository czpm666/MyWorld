# -*- coding: utf-8 -*-
"""_ci_audit.py - audit the inherited hd_castle_int.py without trusting it.

Builds it in an empty scene, measures it, then renders three cheap views so the
verdict ("usable / half-done / unusable") is based on pixels, not on reading.

    blender -b --factory-startup --python look\\_ci_audit.py
"""
import math
import os
import random
import sys
import time

import bpy
from mathutils import Vector

_HERE = os.path.dirname(os.path.abspath(__file__))
_KING = os.path.dirname(_HERE)
for _p in (_HERE, _KING):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import hd_castle_int as CI  # noqa: E402
import hd_common as H       # noqa: E402

OUT = r"E:\My World\Blender\renders\kingdom\look"
if not os.path.isdir(OUT):
    os.makedirs(OUT)

t0 = time.time()
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------------------------------------------------------------- API audit
print("API build  ->", CI.build.__code__.co_varnames[:CI.build.__code__.co_argcount])
print("API fpsize ->", CI.footprint(), "height", CI.height())
print("API mats   ->", len(CI.MAT_KEYS), "keys")
missing = [k for k in ("stone_floor", "wood_beam", "carpet_red", "tapestry",
                       "cloth_red", "glass_gold", "gold", "fire") if k not in CI.MAT_KEYS]
print("API missing keys ->", missing)

MAT = CI.make_mats()
rng = random.Random(3)
t1 = time.time()
objs = CI.build(MAT, rng)
print("BUILD %.1f s objects %d" % (time.time() - t1, len(objs)))


def ntris(me):
    return sum(len(p.vertices) - 2 for p in me.polygons)


tris = sum(ntris(o.data) for o in objs if o.type == 'MESH')
LO = Vector((1e9, 1e9, 1e9))
HI = Vector((-1e9, -1e9, -1e9))
for o in objs:
    if o.type != 'MESH':
        continue
    for c in o.bound_box:
        v = o.matrix_world @ Vector(c)
        for i in range(3):
            LO[i] = min(LO[i], v[i])
            HI[i] = max(HI[i], v[i])
print("TRIS %d  bbox x %.2f..%.2f y %.2f..%.2f z %.2f..%.2f"
      % (tris, LO.x, HI.x, LO.y, HI.y, LO.z, HI.z))

# does it fit the keep?  hd_castle.keep(): x +-15, y -32..-10, wall >= 1.0
print("FIT keep(30x22) x-span %.2f  y-span %.2f  -> %s"
      % (HI.x - LO.x, HI.y - LO.y,
         "NO" if (HI.x - LO.x) > 28.0 or (HI.y - LO.y) > 20.0 else "yes"))

# ---------------------------------------------------------------- lighting
CI._world()
CI._sun("SUN", (-0.62, -0.26, -0.72), energy=9.5, angle=0.55)
CI._area("FILL_NAVE", (0.0, 3.0, 15.10), (7.0, 6.0), 900.0, (0.0, 0.0, 0.0))
CI._area("FILL_ENTRY", (0.0, -14.20, 14.20), (6.0, 5.0), 520.0, (0.0, 0.0, 0.0))
CI._area("FILL_DAIS", (0.0, 15.60, 14.40), (6.0, 5.0), 700.0,
         (math.radians(14.0), 0.0, 0.0))
CI._area("UP_NAVE", (0.0, 1.0, 9.40), (12.0, 14.0), 950.0, (math.pi, 0.0, 0.0))
for i in (1, 3, 5):
    CI._point("CH_L%d" % i, (0.0, CI.PIERS[i], 11.90), 220.0, (1.0, 0.70, 0.36), 0.5)
for s in (-1, 1):
    CI._point("BZ0_%d" % s, (s * 5.90, 15.10, 1.55), 90.0, (1.0, 0.52, 0.18), 0.3)
    CI._point("CD_%d" % s, (s * 1.86, 21.90, CI.Z_DAIS + 1.95), 45.0,
              (1.0, 0.66, 0.34), 0.18)

H.setup_engine(samples=8, res=(480, 270), gpu=True)
bpy.context.scene.cycles.use_denoising = True

shots = [
    ("A_entry", (0.0, -23.30, 1.70), (0.0, 6.00, 2.90), 22.0),
    ("B_nave", (0.0, -1.20, 1.70), (0.0, 17.00, 3.30), 27.0),
    ("C_dais", (0.0, 11.20, 1.70), (0.0, 21.60, 2.55), 34.0),
]
for nm, loc, tgt, lens in shots:
    cam = H.camera("CAM_" + nm, loc, tgt, lens=lens)
    p = os.path.join(OUT, "AUD_int_%s.png" % nm)
    H.render_to(p, cam)
    print("RENDER", p, flush=True)

print("TOTAL %.1f s" % (time.time() - t0))
