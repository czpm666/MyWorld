"""Numeric probe for the new height field.  No bpy, no lock, ~2 s.

    python look/_land_probe4.py
"""
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KROOT = os.path.dirname(HERE)
if KROOT not in sys.path:
    sys.path.insert(0, KROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import numpy as np

import _land_stub
_land_stub.install()

import hd_landscape as L


def main():
    t0 = time.time()
    L._river_arrays(L._SEED)
    print("[probe] river arrays %.2fs" % (time.time() - t0))

    R = L._RIV
    px, py = R["px"], R["py"]
    r = np.hypot(px, py)
    k = int(np.argmin(r))
    print("[probe] river nodes %d  min radius %.1f at (%.0f,%.0f)"
          % (px.size, r[k], px[k], py[k]))
    print("[probe] lake %.1f %.1f r%.0f wl%.2f" % R["lake"])
    print("[probe] harbour wl at x=-900:%.3f  x=0:%.3f  x=900:%.3f"
          % tuple(R["wl"][int(np.argmin(np.abs(px - q) + np.abs(py + 762)))
                          ] for q in (-900.0, 0.0, 900.0)))

    # ---- city floor ------------------------------------------------------
    g = np.arange(0.0, 360.0, 5.0)
    rr = np.arange(0.0, 980.0, 20.0)
    A, RR = np.meshgrid(np.radians(g), rr)
    zz = L.heights(RR * np.cos(A), RR * np.sin(A))
    sd = L._city_sd(RR * np.cos(A), RR * np.sin(A))
    inside = sd < -6.0
    print("[probe] inside wall: z min %.3f max %.3f  exact0 %.3f%%  n=%d"
          % (zz[inside].min(), zz[inside].max(),
             100.0 * float(np.mean(np.abs(zz[inside]) < 1e-6)), inside.sum()))

    # ---- harbour ---------------------------------------------------------
    for yy in (-762.0, -800.0, -730.0, -710.0, -700.0):
        print("[probe]   z(0,%.0f) = %.2f" % (yy, float(L.height(0.0, yy))))

    # ---- apron -----------------------------------------------------------
    print("[probe] apron offsets", L._apron())
    print("[probe] heights by bearing (deg: r=1000/1200/1500/2000/2600/3200)")
    for deg in (0, 45, 90, 135, 180, 225, 270, 315):
        a = math.radians(deg)
        row = []
        for q in (1000, 1200, 1500, 2000, 2600, 3200):
            row.append("%7.1f" % float(L.height(q * math.cos(a), q * math.sin(a))))
        print("[probe]   %3d° %s" % (deg, " ".join(row)))

    # ---- noise of the foot line -----------------------------------------
    print("[probe] wall-foot distance where z first exceeds 1.0 m:")
    for deg in (0, 45, 90, 135, 180, 225, 270, 315):
        a = math.radians(deg)
        found = -1.0
        for q in np.arange(950.0, 1500.0, 5.0):
            if float(L.height(q * math.cos(a), q * math.sin(a))) > 1.0:
                found = q
                break
        print("[probe]   %3d° %.0f m" % (deg, found))

    # ---- timing of a full grid ------------------------------------------
    t1 = time.time()
    n = 361
    xs = np.linspace(-3600.0, 3600.0, n)
    X, Y = np.meshgrid(xs, xs)
    Z = L.heights(X, Y)
    print("[probe] terrain grid %dx%d in %.2fs  z %.0f..%.0f"
          % (n, n, time.time() - t1, Z.min(), Z.max()))

    t1 = time.time()
    for _ in range(20):
        L.heights(xs, np.full(n, 15000.0))
    print("[probe] 20 far loops in %.2fs" % (time.time() - t1))
    print("[probe] total %.2fs" % (time.time() - t0))


main()
