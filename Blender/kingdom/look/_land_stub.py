"""_land_stub.py -- import hd_landscape in plain CPython (no Blender).

The height field, the field layout, the near-band placement and every
"where should this go" question are pure numpy.  Iterating on them through a
Blender start-up costs 30 s a turn and the machine-wide build lock; this stub
fakes just enough of `bpy` / `mathutils` to let the module import and lets the
pure-maths half run in 0.2 s.

    import _land_stub; _land_stub.install()
    import hd_landscape as LAN
    print(LAN.height(-450, -640))

Only geometry emission (`mk_obj`, `Acc.push`) needs the real Blender.
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
KROOT = os.path.dirname(HERE)


class _No(object):
    """Stands in for any bpy collection: .get() -> None, iteration empty."""

    def __init__(self, *a, **k):
        self._ = {}

    def get(self, *a, **k):
        return None

    def new(self, *a, **k):
        return _No()

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def __getattr__(self, k):
        return _No()

    def __call__(self, *a, **k):
        return _No()


class _Vec(object):
    __slots__ = ("x", "y", "z")

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __repr__(self):
        return "V(%.3f, %.3f, %.3f)" % (self.x, self.y, self.z)


class _Mat(object):
    """4x4 identity-ish transform good enough for translate/rotate/scale."""

    def __init__(self, m=None):
        self.m = m

    def __matmul__(self, o):
        return o

    def __repr__(self):
        return "<Mat>"


def install():
    if "bpy" in sys.modules and getattr(sys.modules["bpy"], "_landstub", False):
        return
    bpy = types.ModuleType("bpy")
    bpy._landstub = True
    bpy.data = _No()
    bpy.context = _No()
    bpy.ops = _No()
    bpy.types = _No()
    sys.modules["bpy"] = bpy

    mu = types.ModuleType("mathutils")
    mu.Vector = _Vec
    mu.Matrix = _Mat
    mu.Euler = _Mat
    mu.Quaternion = _Mat
    sys.modules["mathutils"] = mu

    if KROOT not in sys.path:
        sys.path.insert(0, KROOT)
