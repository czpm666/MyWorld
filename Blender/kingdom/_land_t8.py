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
x = np.linspace(1300.0, 1700.0, 41)
y = np.full_like(x, 8900.0)
r = np.hypot(x, y)
deg = np.degrees(np.arctan2(y, x)) % 360.0
print("deg %s" % np.round(deg[:5], 2))
print("ang %s" % np.round(L._ang_strength(deg)[:5], 3))
print("relief %s" % np.round(L._relief(x, y, 1337)[:6], 1))
print("pre    %s" % np.round(L._pre(x, y)[:6], 1))
print("ridge  %s" % np.round(L.ridged(x, y, 1.0 / 2000.0, 4, 1337 + 71,
                                      warp=0.80)[:6], 3))
print("fbm    %s" % np.round(L.fbm(x, y, 1.0 / 620.0, 4, 1337 + 7)[:6], 3))
print("heights %s" % np.round(L.heights(x, y)[:8], 1))
print("wl     %s" % np.round(L._water_level(x, y)[0][:8], 1))
