import sys, math, random
sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")
import bpy
import medkit as K
import capital_hd_glue as G
import capital as C

K.reset_scene()
C.init_mats()
M = G.hd_materials(dict(C.MAT))
rng = random.Random(1)
for k in range(4):
    a = k * math.pi * 0.5
    x, y = 300.0 * math.cos(a), 300.0 * math.sin(a)
    parts = G.gatehouse(M, rng, x, y, a - math.pi * 0.5, 0.0, name="gate%d" % k)
    if not parts:
        print("[t] gate%d EMPTY" % k, flush=True)
        continue
    lo, hi = G.H.bbox(parts)
    print("[t] gate%d n=%-4d x %7.1f..%7.1f y %7.1f..%7.1f z %5.1f..%5.1f"
          % (k, len(parts), lo.x, hi.x, lo.y, hi.y, lo.z, hi.z), flush=True)
print("GATES_DONE", flush=True)
