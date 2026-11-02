"""_land_probe3.py -- pure-python probes of the terrain field.

    python look/_land_probe3.py [section|river|flat|town]

No Blender.  Answers the questions that used to cost a 30 s build:
where does the plateau end, does the river gouge the city, what does the
profile look like along each gate road.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np                                             # noqa: E402

import _land_stub                                              # noqa: E402

_land_stub.install()
import hd_landscape as LAN                                     # noqa: E402


def prof(ang_deg, r0=0.0, r1=2600.0, n=40):
    a = math.radians(ang_deg)
    rs = np.linspace(r0, r1, n)
    z = LAN.heights(rs * math.cos(a), rs * math.sin(a))
    return rs, z


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "section"
    LAN._river_arrays(LAN._SEED)
    print("RIVER lake", LAN._RIV["lake"])
    if what in ("section", "all"):
        for ang in (0, 45, 90, 135, 180, 225, 270, 315):
            rs, z = prof(ang)
            print("az %4d  " % ang + " ".join("%6.1f" % v for v in z[::4]))
    if what in ("river", "all"):
        px, py = LAN._RIV["px"], LAN._RIV["py"]
        r = np.hypot(px, py)
        print("river min radius %.1f at (%.0f, %.0f)"
              % (r.min(), px[int(np.argmin(r))], py[int(np.argmin(r))]))
        i = np.argsort(r)[:12]
        for k in i:
            print("  pt r=%7.1f  (%.0f, %.0f)  z=%.2f  wl=%.2f"
                  % (r[k], px[k], py[k], LAN.height(px[k], py[k]),
                     LAN._RIV["wl"][k]))
    if what in ("flat", "all"):
        for ang in (0, 22, 45, 67, 90, 112, 135, 157, 180):
            rs, z = prof(ang, 0.0, 1300.0, 27)
            print("flat az %4d " % ang + " ".join("%5.2f" % v for v in z))
    if what in ("town", "all"):
        rng = np.random.default_rng(1)
        a = rng.uniform(0, 2 * math.pi, 4000)
        r = np.sqrt(rng.uniform(0, 1, 4000)) * 947.2
        z = LAN.heights(r * np.cos(a), r * np.sin(a))
        print("inside wall: z min %.2f max %.2f mean %.3f  nonzero>|0.05|: %d"
              % (z.min(), z.max(), z.mean(), int(np.sum(np.abs(z) > 0.05))))


if __name__ == "__main__":
    main()
