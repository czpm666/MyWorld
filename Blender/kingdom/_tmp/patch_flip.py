# -*- coding: utf-8 -*-
"""Flip-row geometry: the back row shares the front row's party line."""
import io
import sys

p = r"E:\My World\Blender\kingdom\hd_layout.py"
s = io.open(p, encoding="utf-8").read()
n = 0


def rep(old, new):
    global s, n
    if old not in s:
        print("MISS:", old.splitlines()[0][:70])
        return False
    s = s.replace(old, new, 1)
    n += 1
    return True


rep("""        band = edge_band(poly, i, (inset + 2.0) if flip
                         else (setback + inset + dd))""",
    """        band = edge_band(poly, i, (inset + 16.0) if flip
                         else (setback + inset + dd))""")

rep("""            pc = (inset - depth * 0.5) if flip else (setback + depth * 0.5)""",
    """            pc = (inset + depth * 0.5) if flip else (setback + depth * 0.5)""")

rep("""        if min_width(b["poly"]) < 42.0 * k:
            continue
        n0 = len(plots)
        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, inset=24.8, flip=True)""",
    """        if min_width(b["poly"]) < 44.0 * k:
            continue
        n0 = len(plots)
        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, inset=12.4, flip=True)""")

if n != 3:
    print("only %d/3 patches applied" % n)
    sys.exit(1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched %d sites" % n)
