import sys
import types
sys.modules["bpy"] = types.ModuleType("bpy")
sys.modules["bpy"].data = types.SimpleNamespace()
mm = types.ModuleType("mathutils")


class _M(object):
    def __init__(self, *a, **k):
        pass

    def __matmul__(self, o):
        return self


mm.Matrix = _M
mm.Vector = list
sys.modules["mathutils"] = mm
sys.path.insert(0, r"E:\My World\Blender\kingdom")
import numpy as np
import hd_landscape as L

L._river_arrays(1337)

print("== max height on a 3 km grid ==")
g = np.arange(-24000.0, 24001.0, 250.0)
X, Y = np.meshgrid(g, g, indexing="xy")
R = np.hypot(X, Y)
Z = L._pre(X, Y)
print("shapes", X.shape, Y.shape, Z.shape)
i = int(np.argmax(Z))
print("max %.0f at (%.0f,%.0f)" % (Z.ravel()[i], X.ravel()[i], Y.ravel()[i]))

print("== how much ground is above the snow line / tree line ==")
for zz in (500, 860, 1010, 1300, 1800):
    m = Z > zz
    print("  above %5d m: %5.1f%% of the annulus 2..24 km" % (zz, 100.0 * m.sum() / m.size))

print("== silhouette toward bearing 165 deg (p_wide view) ==")
b = np.radians(165.0)
rr = np.arange(1000.0, 24000.0, 100.0)
z = L._pre(rr * np.cos(b), rr * np.sin(b))
for k in range(0, rr.size, 6):
    lo = max(0, k - 3)
    hi = min(rr.size, k + 4)
    print("  r=%6.0f  z=%6.0f  el=%5.1f" % (rr[k], z[lo:hi].max(),
                                            np.degrees(np.arctan2(
                                                z[lo:hi].max() - 300.0, rr[k]))))
