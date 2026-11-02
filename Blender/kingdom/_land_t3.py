# smoke test: build the landscape into the open capital_v23.blend
import os, sys, time
K = r"E:\My World\Blender\kingdom"
if K not in sys.path:
    sys.path.insert(0, K)
import bpy
import hd_landscape as L

t0 = time.time()
n = L.strip_old()
print("stripped", n, "%.1fs" % (time.time() - t0), flush=True)
info = L.build({}, res=20.0, seed=1337)
print("objects", info["count"], "faces", info["faces"],
      "%.1fs" % info["seconds"], flush=True)
# per-category counts
cat = {}
for ob in info["objects"]:
    k = ob.name.split("_")[1]
    a = cat.setdefault(k, [0, 0])
    a[0] += 1
    a[1] += len(ob.data.polygons)
for k in sorted(cat):
    print("  %-8s %3d objs %8d faces" % (k, cat[k][0], cat[k][1]), flush=True)
bpy.ops.wm.save_as_mainfile(
    filepath=r"E:\My World\Blender\renders\kingdom\_land_test.blend")
print("saved  total %.1fs" % (time.time() - t0), flush=True)
