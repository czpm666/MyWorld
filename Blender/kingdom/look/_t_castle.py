"""Build ONLY the castle (plus its interior) to verifies wiring before a full run.

    blender -b --factory-startup --python look/_t_castle.py -- [--no-int]

`build_castle_hd()` is reached thirteen minutes into a full build, so a NameError
or a bad transform there costs the whole run.  This exercises just that path:
init_mats -> build_castle_hd -> report counts.  ~1-2 minutes.
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
for _p in (os.path.dirname(KIND), KIND, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bpy  # noqa: E402
import capital as C  # noqa: E402

A = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

C.HD["on"] = True
C.HD_INT["on"] = "--no-int" not in A
print("[tc] HD_INT =", C.HD_INT, "CITY_SCALE =", C.CITY_SCALE, flush=True)

t0 = time.time()
C.init_mats()
print("[tc] mats %d in %.1f s" % (len(C.MAT), time.time() - t0), flush=True)

t0 = time.time()
parts = C.build_castle_hd()
dt = time.time() - t0
mesh = [o for o in parts if getattr(o, "type", "") == "MESH"]
lights = [o for o in parts if getattr(o, "type", "") == "LIGHT"]
faces = sum(len(o.data.polygons) for o in mesh)
print("[tc] castle parts=%d mesh=%d lights=%d faces=%d in %.1f s"
      % (len(parts), len(mesh), len(lights), faces, dt), flush=True)

# where the interior ended up, in world space
tot = None
for o in mesh:
    if getattr(o, "name", "").startswith("ci_"):
        bb = [o.matrix_world @ v.co for v in o.data.vertices]
        if not bb:
            continue
        lo = (min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb))
        hi = (max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb))
        if tot is None:
            tot = [lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]]
        else:
            tot = [min(tot[0], lo[0]), min(tot[1], lo[1]), min(tot[2], lo[2]),
                   max(tot[3], hi[0]), max(tot[4], hi[1]), max(tot[5], hi[2])]
print("[tc] interior bbox world:", ["%.2f" % v for v in tot] if tot else "NONE",
      flush=True)
print("[tc] CASTLE_OK", flush=True)
