# -*- coding: utf-8 -*-
"""Make functional kinds respect their distance rules (QC item 4)."""
import io
import sys

p = r"E:\My World\Blender\kingdom\hd_layout.py"
s = io.open(p, encoding="utf-8").read()
n = 0


def rep(old, new):
    global s, n
    if old not in s:
        print("MISS:", old.splitlines()[0][:70])
        return
    s = s.replace(old, new, 1)
    n += 1


rep("def pick_kind(table, used, quota, near_gate, near_plaza, water, rng):",
    "def pick_kind(table, used, quota, near_gate, near_plaza, water, rng,\n"
    "              near_palace=None):")

rep("""        if kind in UNIQUE:
            ww *= 6.0""",
    """        # a weaponsmith 500 m from the gate it supplies is nonsense, and so
        # is a noble town house halfway across town from the palace: the
        # weights below make the distance rule bite instead of hinting at it
        if kind in ("armory", "weaponsmith", "barracks", "guard_post"):
            ww *= 3.2 if near_gate else 0.08
        if kind in ("stable", "mill"):
            ww *= 2.0 if (near_gate or water) else 0.35
        if kind in ("noble_manor", "manor", "house_manor", "palace_house"):
            if near_palace is None:
                pass
            elif near_palace:
                ww *= 7.0
            else:
                ww *= 0.10
        if kind in UNIQUE:
            ww *= 6.0""")

rep("""def plot_row(block, k, streets, grid, rng, quota, used_global, out, stats,
             plaza_c, gates, force=False, inset=0.0, flip=False):""",
    """def plot_row(block, k, streets, grid, rng, quota, used_global, out, stats,
             plaza_c, gates, force=False, inset=0.0, flip=False,
             palace_c=None):""")

rep("""    near_gate = min((math.hypot(bc[0] - g[0], bc[1] - g[1]) for g in gates),
                    default=1e9) < 150.0 * k""",
    """    near_gate = min((math.hypot(bc[0] - g[0], bc[1] - g[1]) for g in gates),
                    default=1e9) < 190.0 * k
    near_palace = (None if palace_c is None
                   else math.hypot(bc[0] - palace_c[0],
                                   bc[1] - palace_c[1]) < 150.0 * k)""")

rep("""            kind = pick_kind(table, used, quota, near_gate, near_plaza,
                             water, rng)""",
    """            kind = pick_kind(table, used, quota, near_gate, near_plaza,
                             water, rng, near_palace)""")

# find the palace mark once, right after the marks are collected
rep("""    for b in blocks:
        if b["open"]:
            b["buildings"] = 0
            continue""",
    """    pal_c = next((tuple(m[1]) for m in marks if "palace" in str(m[0])),
                 None)
    for b in blocks:
        if b["open"]:
            b["buildings"] = 0
            continue""")

rep("""        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts)
        corner_plots""",
    """        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, palace_c=pal_c)
        corner_plots""")

rep("""        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, inset=13.6, flip=True)""",
    """        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, inset=13.6, flip=True,
                 palace_c=pal_c)""")

rep("""        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, force=True)""",
    """        plot_row(b, k, streets, grid, rng, quota, used_global, plots, stats,
                 plaza["centroid"], gate_pts, force=True, palace_c=pal_c)""")

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("patched %d sites" % n)
if n < 8:
    sys.exit(1)
