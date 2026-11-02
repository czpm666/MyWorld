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
EYE = 30.0
print("bearing |  r=2.5k   4.5k    6.5k    9k     14k  (max z, apparent deg)")
for d in range(0, 360, 15):
    b = np.radians(d)
    rr = np.arange(1200.0, 16000.0, 40.0)
    z = L._pre(rr * np.cos(b), rr * np.sin(b))
    out = []
    for r0 in (2500.0, 4500.0, 6500.0, 9000.0, 14000.0):
        i = int(np.argmin(np.abs(rr - r0)))
        zz = float(z[max(0, i - 12):i + 13].max())
        out.append("%5.3g/%4.1f" % (zz, np.degrees(np.arctan2(zz - EYE, r0))))
    k = int(np.argmax(z))
    el = np.degrees(np.arctan2(z[k] - EYE, rr[k]))
    print("%5d | %s   peak %5.0f m @ %5.0f m = %4.1f deg"
          % (d, "  ".join(out), z[k], rr[k], el))
