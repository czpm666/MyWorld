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
print("river pts", L._RIV["px"].size, "lake", L._RIV.get("lake"))

# spike hunt: compare each sample with the median of its 4 neighbours
g = np.arange(900.0, 23001.0, 40.0)
X, Y = np.meshgrid(g, g, indexing="xy")
Z = L.heights(X, Y)
print("global min %.1f max %.1f nan %d" % (np.nanmin(Z), np.nanmax(Z),
                                           int(np.isnan(Z).sum())))
nb = np.stack([Z[1:-1, :-2], Z[1:-1, 2:], Z[:-2, 1:-1], Z[2:, 1:-1]])
med = np.median(nb, axis=0)
d = Z[1:-1, 1:-1] - med
k = np.argsort(-np.abs(d).ravel())[:12]
ii, jj = np.unravel_index(k, d.shape)
for a, b in zip(ii, jj):
    print("  spike at (%.0f,%.0f) z=%.1f  neighbours %.1f  r=%.0f"
          % (X[a + 1, b + 1], Y[a + 1, b + 1], Z[a + 1, b + 1], med[a, b],
             np.hypot(X[a + 1, b + 1], Y[a + 1, b + 1])))
