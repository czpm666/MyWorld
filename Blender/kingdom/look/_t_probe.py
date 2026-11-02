"""TERRAIN scratch probe -- analyse the height field + ground colour without Blender.

Stubs bpy/mathutils, imports hd_landscape, samples the relief on a 40 m grid over
the full 46 km box, and writes three diagnostic images to Logs\\ :

    probe_shade.png   hillshade, sun azim 112 / elev 48 (the morning_town wide sun)
    probe_albedo.png  _ground_col() as sRGB
    probe_look.png    albedo * shade, i.e. a cheap stand-in for the material

Also prints z / slope / albedo statistics per radial band, so the snow line and
the three range layers can be tuned numerically instead of by eye.

    python look/_t_probe.py [res]
"""
import os
import sys
import types

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
KIND = os.path.dirname(HERE)
sys.path.insert(0, KIND)


# --------------------------------------------------------------------------- #
# stub the two Blender modules the landscape imports
# --------------------------------------------------------------------------- #
class _Dummy(object):
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        return _Dummy()

    def __call__(self, *a, **k):
        return _Dummy()

    def __getitem__(self, k):
        return _Dummy()

    def __setitem__(self, k, v):
        pass


def _stub(name, attrs):
    m = types.ModuleType(name)
    for a in attrs:
        setattr(m, a, type(a, (_Dummy,), {}))
    m.__getattr__ = lambda n: _Dummy()
    sys.modules[name] = m
    return m


_stub("bpy", ["data", "ops", "context", "types", "app", "path", "utils",
              "collections", "props"])
_stub("mathutils", ["Matrix", "Vector", "Euler", "Quaternion"])

import hd_landscape as L  # noqa: E402


def srgb8(c):
    c = np.clip(c, 0.0, 1.0)
    s = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)
    return (s * 255.0 + 0.5).astype(np.uint8)


def main(argv):
    res = float(argv[1]) if len(argv) > 1 else 40.0
    half = 23000.0
    n = int(round(2.0 * half / res)) + 1
    xs = np.linspace(-half, half, n)
    X, Y = np.meshgrid(xs, xs, indexing="xy")
    print("[probe] grid %d x %d @ %.0f m" % (n, n, res))
    Z = L.heights(X, Y)
    gy, gx = np.gradient(Z, res)
    R = np.hypot(X, Y)
    slope = np.hypot(gx, gy)

    # sun: morning_town wide, elev 48, azim 112 *compass* (hd_light.py: 0 = south
    # = -Y, 90 = east = +X), so the horizontal direction to the sun is
    # (sin b, -cos b) = (0.927, +0.375): east, a little north.
    el = np.radians(48.0)
    az = np.radians(112.0)
    S = np.array([np.cos(el) * np.sin(az), -np.cos(el) * np.cos(az), np.sin(el)])
    N = np.stack([-gx, -gy, np.ones_like(Z)], -1)
    N /= np.linalg.norm(N, axis=-1)[..., None]
    shade = np.clip((N * S).sum(-1), 0.0, 1.0)

    col = L._ground_col(X, Y, Z, gx, gy, 1337)[..., :3].reshape(Z.shape + (3,))
    print("[probe] z  min %.1f  max %.1f" % (Z.min(), Z.max()))

    bands = [(0, 1000), (1000, 2000), (2000, 3000), (3000, 5000),
             (5000, 7000), (7000, 11000), (11000, 23000)]
    print("%-14s %8s %8s %8s %8s %8s" %
          ("r band", "z mean", "z max", "p99 slope", "snow%", "rock%"))
    for a, b in bands:
        m = (R >= a) & (R < b)
        if not m.any():
            continue
        zz = Z[m]
        sl = slope[m]
        snow = (zz > L.SNOW_Z).mean() * 100.0
        rock = (sl > 1.0).mean() * 100.0
        print("%-14s %8.0f %8.0f %8.2f %8.1f %8.1f" %
              ("%d-%dk" % (a // 1000, b // 1000), zz.mean(), zz.max(),
               np.percentile(sl, 99), snow, rock))

    # bearing profile of the skyline (what the eye reads as "three layers")
    print("\n[skyline] max z by bearing, 0..360 step 15 deg")
    deg = np.degrees(np.arctan2(Y, X)) % 360.0
    for d in range(0, 360, 15):
        m = np.abs(((deg - d + 180.0) % 360.0) - 180.0) < 7.5
        if not m.any():
            continue
        zz = Z[m]
        rr = R[m]
        far = zz[rr > 6000].max() if (rr > 6000).any() else 0.0
        mid = zz[(rr > 2000) & (rr <= 6000)]
        near = zz[(rr > 900) & (rr <= 2000)]
        print("  %3d deg  near(0.9-2k) %6.0f   mid(2-6k) %6.0f   far(>6k) %6.0f"
              % (d, near.max() if near.size else 0.0,
                 mid.max() if mid.size else 0.0, far))

    out = os.path.join(KIND, "..", "..", "Logs")
    out = os.path.abspath(out)
    Image.fromarray(srgb8(col)).save(os.path.join(out, "probe_albedo.png"))
    Image.fromarray(srgb8(np.repeat(shade[..., None], 3, -1))).save(
        os.path.join(out, "probe_shade.png"))
    lit = col * (0.22 + 0.95 * shade[..., None])
    Image.fromarray(srgb8(lit)).save(os.path.join(out, "probe_look.png"))
    # the ground material's aerial perspective: radius 700 -> 9000 m, To Max
    # 0.58, mixed toward HAZE.  This is what the far wall *should* look like.
    fade = np.clip((R - 700.0) / (9000.0 - 700.0), 0.0, 1.0) ** 1.0 * 0.58
    haze = col * (1.0 - fade[..., None]) + np.array(L.HAZE if hasattr(L, "HAZE")
                                                     else (0.556, 0.635, 0.722)) * fade[..., None]
    Image.fromarray(srgb8(haze * (0.22 + 0.95 * shade[..., None]))).save(
        os.path.join(out, "probe_haze.png"))
    for a, b in bands:
        m = (R >= a) & (R < b)
        if not m.any():
            continue
        print("  albedo r=%2d-%2dk  mean %s  max %s" %
              (a // 1000, b // 1000,
               np.round(col[m].mean(0), 3), np.round(col[m].max(0), 3)))
    print("[probe] wrote %s\\probe_{albedo,shade,look,haze}.png" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
