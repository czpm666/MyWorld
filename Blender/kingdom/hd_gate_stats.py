"""Per-object triangle census for hd_gate (diagnostic helper, not shipped art)."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
import hd_gate as G


def main():
    H = G.H
    H._clear()
    MAT = G.make_materials()
    import random
    rng = random.Random(7)
    obs = G.build(MAT, rng)
    rows = []
    tot = 0
    for ob in obs:
        if ob is None or ob.type != "MESH":
            continue
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        n = len(me.loop_triangles)
        tot += n
        rows.append((n, ob.name, len(ob.modifiers)))
        ev.to_mesh_clear()
    rows.sort(reverse=True)
    print("[census] total %d over %d objects" % (tot, len(rows)))
    for n, name, mods in rows[:40]:
        print("[census] %6d  %-22s mods=%d" % (n, name, mods))
    # group by prefix before the first digit or underscore
    groups = {}
    for n, name, mods in rows:
        key = name.split("_")[0]
        groups[key] = groups.get(key, 0) + n
    for k, v in sorted(groups.items(), key=lambda kv: -kv[1])[:30]:
        print("[group] %6d  %s" % (v, k))


main()
