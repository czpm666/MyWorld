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
for x0 in (1580.0, 1460.0):
    y = np.arange(8800.0, 9060.0, 20.0)
    x = np.full_like(y, x0)
    print("x=%.0f  pre %s" % (x0, np.round(L._pre(x, y), 1)))
    print("        hgt %s" % np.round(L.heights(x, y), 1))

# and the same points through a 2-D array to see if the shape matters
g = np.arange(8800.0, 9060.0, 20.0)
X, Y = np.meshgrid(np.array([1580.0]), g, indexing="xy")
print("2-D shape %s -> %s" % (X.shape, np.round(L.heights(X, Y)[:, 0], 1)))
