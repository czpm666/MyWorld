import sys

sys.path.insert(0, r"E:\My World\Blender\kingdom")
sys.path.insert(0, r"E:\My World\Blender")

import hd_common as H  # noqa: E402
import hd_castle_int as CI  # noqa: E402
import medkit as K  # noqa: E402

K.reset_scene()
M = CI.prep(CI.make_mats())
P = CI.build(K, M)
lows = [ob for ob in P if ob is not None and ob.type == "LIGHT"]
print("lights=%d" % len(lows), flush=True)
for ob in lows:
    lo = ob.location
    if lo.z > 19.0:
        e = ob.data.energy
        print("  %-16s (%.2f, %.2f, %.2f) z=%6.2f E=%7.0f  %s  %s"
              % (ob.name, lo.x, lo.y, lo.z, lo.z, e, ob.data.type,
                 tuple(round(a * 57.2958, 1) for a in ob.rotation_euler)), flush=True)
print("--- feast meshes above 19.6 ---", flush=True)
n = 0
for ob in P:
    if ob is None or ob.type != "MESH":
        continue
    a, b = H.bbox([ob])
    if a.z > 19.6 and b.z > 28.0:
        n += 1
        if n < 8:
            print("  %-16s z %.2f..%.2f  y %.2f..%.2f" % (ob.name, a.z, b.z, a.y, b.y), flush=True)
print("tall feast meshes:", n, flush=True)
