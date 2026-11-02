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
B = np.radians(np.arange(0.0, 360.0, 15.0))
rr = np.arange(1200.0, 24000.0, 60.0)
print("bear  zmax   elev |  3.5k   6k    10k")
for b in B:
    x = rr * np.cos(b)
    y = rr * np.sin(b)
    z = L._pre(x, y)
    k = int(np.argmax(z))
    el = np.degrees(np.arctan2(z[k] - 30.0, rr[k]))

    def zz(r0):
        i = int(np.argmin(np.abs(rr - r0)))
        return float(z[max(0, i - 8):i + 9].max())
    print("%5.0f %6.0f %5.1f | %5.0f %5.0f %5.0f"
          % (np.degrees(b), z[k], el, zz(3500), zz(6000), zz(10000)))
