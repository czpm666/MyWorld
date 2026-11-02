# -*- coding: utf-8 -*-
"""Patch offset bugs: panels built at x=0 instead of their bay centre."""
import io
import os

D = r"E:\My World\Blender\kingdom"


def patch(fn, pairs):
    p = os.path.join(D, fn)
    t = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if t.count(old) != 1:
            raise SystemExit("marker %d x in %s: %r" % (t.count(old), fn, old[:60]))
        t = t.replace(old, new)
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    print("PATCHED", fn, len(t))


patch("_cint_p2.py", [(
    '''    E.append(prism("ae_back", hole_pts(hw, 0.0, z_spr, z_apex, 12), sd,
                   y0 + 0.28, y0 + 0.34, axis="y"))''',
    '''    E.append(prism("ae_back", [(cx + x, z) for (x, z) in
                               hole_pts(hw, 0.0, z_spr, z_apex, 12)], sd,
                   y0 + 0.28, y0 + 0.34, axis="y"))''')])

patch("_cint_p3.py", [(
    '''            C.append(prism("sw_ba%d_%d" % (s, j), hole_pts(0.44, 1.10, 3.05, 3.95, 10),
                           sd, y0 - 0.02, y0 + 0.06, axis="y"))''',
    '''            C.append(prism("sw_ba%d_%d" % (s, j),
                           [(xc + x, z) for (x, z) in
                            hole_pts(0.44, 1.10, 3.05, 3.95, 10)],
                           sd, y0 - 0.02, y0 + 0.06, axis="y"))'''), (
    '''        C.append(prism("sw_ni%d" % s, hole_pts(0.62, 1.55, 3.35, 4.45, 10), sd,
                       y1 + 0.01, y1 + 0.05, axis="y"))''',
    '''        C.append(prism("sw_ni%d" % s,
                       [(xn + x, z) for (x, z) in
                        hole_pts(0.62, 1.55, 3.35, 4.45, 10)], sd,
                       y1 + 0.01, y1 + 0.05, axis="y"))'''), (
    '''            C.append(prism("bw_bp%d_%d" % (s, j), hole_pts(0.80, 1.30, 4.00, 5.40, 12),
                           sd, y0 + 0.01, y0 + 0.05, axis="y"))''',
    '''            C.append(prism("bw_bp%d_%d" % (s, j),
                           [(xc + x, z) for (x, z) in
                            hole_pts(0.80, 1.30, 4.00, 5.40, 12)],
                           sd, y0 + 0.01, y0 + 0.05, axis="y"))''')])

patch("_cint_p4.py", [(
    '''    C.append(rod(nm + "_sw", (0.0, 0.20, 1.98), (0.0, 0.20, 1.10), 0.026, iron,
                 seg=6))''',
    '''    C.append(rod(nm + "_sw", (T @ Vector((0.0, 0.20, 1.98))),
                 (T @ Vector((0.0, 0.20, 1.10))), 0.026, iron, seg=6))'''), (
    '''    C.append(prism(nm + "_ha", [(0.60, 2.38), (0.60, 2.60), (0.44, 2.66),
                                (0.44, 2.32)], iron, y - 0.02, y + 0.02, axis="y"))''',
    '''    C.append(prism(nm + "_ha", [(x + 0.60, 2.38), (x + 0.60, 2.60),
                                (x + 0.44, 2.66), (x + 0.44, 2.32)], iron,
                   y - 0.02, y + 0.02, axis="y"))''')])
