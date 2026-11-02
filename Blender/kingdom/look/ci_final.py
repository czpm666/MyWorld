"""Final 960x540 acceptance frames through the module's own preview()."""
import sys
import time

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

import bpy
import hd_common as H
import hd_castle_int as CI

t0 = time.time()
CI.preview(samples=128, res=(960, 540), tag="ACC")
print("FINAL total=%.1fs" % (time.time() - t0), flush=True)

tris = 0
nmesh = 0
nlight = 0
lo = [1e9, 1e9, 1e9]
hi = [-1e9, -1e9, -1e9]
for ob in bpy.data.objects:
    if ob.type == "LIGHT":
        nlight += 1
        continue
    if ob.type != "MESH":
        continue
    nmesh += 1
    for pl in ob.data.polygons:
        tris += max(1, len(pl.vertices) - 2)
    a, b = H.bbox([ob])
    for i in range(3):
        lo[i] = min(lo[i], a[i])
        hi[i] = max(hi[i], b[i])
print("FINAL meshes=%d lights=%d tris=%d" % (nmesh, nlight, tris), flush=True)
print("FINAL bbox lo=(%.2f, %.2f, %.2f) hi=(%.2f, %.2f, %.2f)"
      % (lo[0], lo[1], lo[2], hi[0], hi[1], hi[2]), flush=True)
